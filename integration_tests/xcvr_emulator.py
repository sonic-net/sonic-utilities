"""A pytest-owned emulator process, its gRPC client and the native SONiC adapter."""

import copy
import os
import signal
import socket
import subprocess
import sys
import time
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

import grpc
import yaml
from sonic_platform_base.sonic_xcvr.sfp_optoe_base import SfpOptoeBase
from xcvr_emu.proto import emulator_pb2 as messages
from xcvr_emu.proto import emulator_pb2_grpc as services


@dataclass(frozen=True)
class Access:
    """Record a completed wire transaction, not a simulated response."""

    write: bool
    page: int
    offset: int
    data: bytes


class Emulator:
    """Access one CMIS module over the emulator's real gRPC service."""

    def __init__(self, channel: grpc.Channel):
        self.channel = channel
        self.stub = services.SfpEmulatorServiceStub(channel)
        self.accesses: list[Access] = []

    def read_page(self, page: int, offset: int, length: int) -> bytes:
        """Read bytes directly from a CMIS page."""
        response = self.stub.Read(
            messages.ReadRequest(index=0, bank=0, page=page, offset=offset, length=length),
            timeout=3,
        )
        data = bytes(response.data)
        if len(data) != length:
            raise IOError(f"Short EEPROM read: page={page}, offset={offset}, expected={length}, got={len(data)}")
        self.accesses.append(Access(False, page, offset, data))
        return data

    def write_page(self, page: int, offset: int, data: bytes) -> None:
        """Write bytes directly to a CMIS page."""
        self.stub.Write(
            messages.WriteRequest(index=0, bank=0, page=page, offset=offset, length=len(data), data=data),
            timeout=3,
        )
        self.accesses.append(Access(True, page, offset, bytes(data)))

    @staticmethod
    def chunks(offset: int, length: int) -> Iterator[tuple[int, int, int]]:
        """Translate optoe's linear bank-zero address space into page windows."""
        if offset < 0 or length < 0:
            raise ValueError("EEPROM offset and length must be nonnegative")
        while length:
            if offset < 128:
                page, page_offset = 0, offset
                count = min(length, 128 - offset)
            else:
                page, page_offset = offset // 128 - 1, 128 + offset % 128
                count = min(length, 256 - page_offset)
            if page > 255:
                raise ValueError("The integration adapter supports CMIS bank zero only")
            yield page, page_offset, count
            offset += count
            length -= count

    def read(self, offset: int, length: int) -> bytearray:
        """Implement the optoe read contract using actual gRPC reads."""
        result = bytearray()
        for page, page_offset, count in self.chunks(offset, length):
            result.extend(self.read_page(page, page_offset, count))
        return result

    def write(self, offset: int, length: int, data: bytes | bytearray) -> bool:
        """Implement the optoe write contract using actual gRPC writes."""
        if length != len(data):
            raise ValueError("EEPROM write length does not match its data")
        position = 0
        for page, page_offset, count in self.chunks(offset, length):
            self.write_page(page, page_offset, bytes(data[position:position + count]))
            position += count
        return True

    def present(self) -> bool:
        """Read insertion state from the emulator, not a platform mock."""
        return self.stub.GetInfo(messages.GetInfoRequest(index=0), timeout=3).present

    def set_present(self, present: bool) -> None:
        """Insert or remove the emulated module."""
        self.stub.UpdateInfo(messages.UpdateInfoRequest(index=0, present=present), timeout=3)

    def set_temperature(self, celsius: float) -> None:
        """Set the full CMIS temperature register in signed 1/256 C units."""
        self.write_page(0, 14, int(celsius * 256).to_bytes(2, "big", signed=True))

    def set_voltage(self, volts: float) -> None:
        """Set the full CMIS supply-voltage register in 100 uV units."""
        self.write_page(0, 16, int(volts * 10000).to_bytes(2, "big"))

    def wait_for(self, predicate: Callable[[], bool], description: str, timeout: float = 3) -> None:
        """Wait for an asynchronous CMIS state transition with a bounded deadline."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.02)
        raise AssertionError(f"xcvr-emu did not reach {description} within {timeout}s")


class EmulatedSfp(SfpOptoeBase):
    """Use SONiC's real CMIS parser/control APIs over the emulated EEPROM."""

    def __init__(self, emulator: Emulator):
        self.emulator = emulator
        super().__init__(bank=0)

    def get_name(self):
        """Name the emulated physical module without consulting platform inventory."""
        return "xcvr-emu0"

    def get_eeprom_path(self):
        """No optoe sysfs file exists when the transport is gRPC."""
        return "/nonexistent/xcvr-emu/eeprom"

    def read_eeprom(self, offset, num_bytes):
        """Read the module through gRPC instead of an optoe sysfs file."""
        return self.emulator.read(offset, num_bytes)

    def write_eeprom(self, offset, num_bytes, write_buffer):
        """Write the module through gRPC instead of an optoe sysfs file."""
        return self.emulator.write(offset, num_bytes, write_buffer)

    def get_presence(self):
        """Return the emulator's actual insertion state."""
        return self.emulator.present()

    def get_error_description(self):
        """Translate insertion state into the platform's basic health description."""
        return "OK" if self.get_presence() else "Unplugged"

    def reset(self):
        """Model the board reset operation with the emulator's CMIS software reset."""
        control = self.emulator.read_page(0, 26, 1)[0]
        self.emulator.write_page(0, 26, bytes([control | 0x08]))
        self.emulator.wait_for(
            lambda: self.get_xcvr_api().get_module_state() == "ModuleLowPwr",
            "ModuleLowPwr after software reset",
        )
        # xcvr-emu does not self-clear the software-reset bit.
        control = self.emulator.read_page(0, 26, 1)[0]
        self.emulator.write_page(0, 26, bytes([control & ~0x08]))
        return True


class EmulatorProcess:
    """Own a daemon and its client with ``with EmulatorProcess(...) as daemon``."""

    def __init__(self, directory: Path, config: dict, startup_timeout: float = 10):
        self.directory = directory
        self.config = config
        self.startup_timeout = startup_timeout
        self.config_path = directory / "config.yaml"
        self.log_path = directory / "xcvr-emud.log"

    @staticmethod
    def load_config(overrides: dict | None = None) -> dict:
        """Read our one-module profile, with independent per-test default overrides."""
        config = yaml.safe_load(Path(__file__).with_name("config.yaml").read_text())
        if overrides is not None:
            config["transceivers"][0]["defaults"].update(copy.deepcopy(overrides))
        return config

    def __enter__(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(yaml.safe_dump(self.config))
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]

        # ExitStack also reaps the child if startup fails before __enter__ returns.
        with ExitStack() as resources:
            with self.log_path.open("w") as log:
                self.process = subprocess.Popen(
                    [sys.executable, "-m", "xcvr_emu.xcvr_emud", "--port", str(port),
                     "--config", str(self.config_path)],
                    cwd=self.directory,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                    env={key: value for key, value in os.environ.items() if not key.startswith("COV_CORE")},
                )
            resources.callback(self.stop)
            channel = resources.enter_context(grpc.insecure_channel(f"127.0.0.1:{port}"))
            self.client = Emulator(channel)
            self._wait_until_ready()
            self._resources = resources.pop_all()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._resources.close()

    def _wait_until_ready(self) -> None:
        try:
            deadline = time.monotonic() + self.startup_timeout
            ready = grpc.channel_ready_future(self.client.channel)
            while True:
                if self.process.poll() is not None:
                    raise AssertionError(f"xcvr-emud exited during startup:\n{self.log_path.read_text()}")
                try:
                    ready.result(timeout=0.1)
                    break
                except grpc.FutureTimeoutError:
                    if time.monotonic() >= deadline:
                        raise
            infos = self.client.stub.List(messages.ListRequest(), timeout=3).infos
            if [info.index for info in infos] != [0]:
                raise AssertionError(f"Unexpected emulator inventory: {infos}")
        except (grpc.FutureTimeoutError, grpc.RpcError) as error:
            raise AssertionError(f"xcvr-emud failed to become ready: {error}\n{self.log_path.read_text()}") from error

    def stop(self) -> None:
        """Stop and reap this child, reporting failures instead of leaking processes."""
        if self.process.poll() is not None:
            self.process.wait()
            return
        self.process.send_signal(signal.SIGINT)
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
            raise AssertionError(f"xcvr-emu did not shut down gracefully:\n{self.log_path.read_text()}")

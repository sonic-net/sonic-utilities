"""Mock SONiC services around a real emulated SFP, without mocking CLI results."""

import importlib
import importlib.util
import sys
from fnmatch import fnmatch
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import click
from click.testing import CliRunner, Result
from sonic_platform_base.sfp_base import SfpBase
from sonic_platform_base.sonic_sfp import sfputilhelper
from sonic_py_common import device_info, multi_asic

from integration_tests.xcvr_emulator import EmulatedSfp, Emulator
from utilities_common import cli as clicommon
from utilities_common import multi_asic as multi_asic_util
from utilities_common import platform_sfputil_helper as helper
from utilities_common.db import Db


class CliCommand:
    """Bind a real Click command to its context and check results consistently."""

    def __init__(self, command: click.Command, obj=None):
        self.command = command
        self.obj = obj
        self.runner = CliRunner()

    def run(self, arguments: list[str]) -> Result:
        """Run without asserting success so wrapper commands can forward failures."""
        return self.runner.invoke(self.command, arguments, obj=self.obj)

    def invoke(self, arguments: list[str], expected_code: int = 0) -> str:
        """Assert the expected exit code and return output for test assertions."""
        result = self.run(arguments)
        assert result.exit_code == expected_code, f"{arguments}\n{result.output}\n{result.exception!r}"
        return result.output


class MockDatabases:
    """Implement the Redis operations used by transceiver commands in memory."""

    CONFIG_DB = "CONFIG_DB"
    STATE_DB = "STATE_DB"
    APPL_DB = "APPL_DB"

    def __init__(self):
        self.config = {
            "PORT|Ethernet0": {"index": "0", "lanes": "0,1,2,3", "subport": "0", "alias": "etp1"},
        }
        self.state: dict[str, dict[str, str]] = {}
        self.appl = {"PORT_TABLE:Ethernet0": {"role": "Ext"}}
        self._tables = {self.CONFIG_DB: self.config, self.STATE_DB: self.state, self.APPL_DB: self.appl}

    def connect(self, db_name: str = CONFIG_DB) -> None:
        """Validate the database name without opening a Redis connection."""
        if db_name not in self._tables:
            raise KeyError(f"Unexpected database: {db_name}")

    def close(self) -> None:
        """No connection needs closing for an in-memory database."""

    def get(self, db_name: str, key: str, field: str) -> str | None:
        """Read one field, returning None for a missing Redis key or field."""
        return self._tables[db_name].get(key, {}).get(field)

    def get_all(self, db_name: str, key: str) -> dict[str, str]:
        """Return a copy so callers cannot mutate the database through a read."""
        return self._tables[db_name].get(key, {}).copy()

    def keys(self, db_name: str, pattern: str) -> list[str]:
        """Match Redis key patterns used by the display commands."""
        return [key for key in self._tables[db_name] if fnmatch(key, pattern)]

    def set(self, db_name: str, key: str, field: str, value: str) -> None:
        """Write one field to the requested database."""
        self._tables[db_name].setdefault(key, {})[field] = value

    def get_entry(self, table: str, key: str) -> dict[str, str]:
        """Read a CONFIG_DB entry through the ConfigDBConnector interface."""
        return self.get_all(self.CONFIG_DB, f"{table}|{key}")

    def get_table(self, table: str) -> dict[str, dict[str, str]]:
        """Read copies of all entries in a CONFIG_DB table."""
        return {key.split("|", 1)[1]: value.copy()
                for key, value in self.config.items() if key.startswith(f"{table}|")}

    def mod_entry(self, table: str, key: str, values: dict[str, str]) -> None:
        """Update a CONFIG_DB entry without replacing its other fields."""
        self.config.setdefault(f"{table}|{key}", {}).update(values)


class MockChassis:
    """Expose only physical port zero, backed by the real CMIS adapter."""

    def __init__(self, sfp: EmulatedSfp):
        self.sfp = sfp

    def get_sfp(self, index: int) -> EmulatedSfp:
        """Look up the emulated physical port, rejecting unmapped indices."""
        if index != 0:
            raise IndexError(f"No emulated transceiver at physical index {index}")
        return self.sfp

    def get_port_or_cage_type(self, index: int) -> int:
        """Report the board's QSFP-DD cage type, not the inserted module's type."""
        self.get_sfp(index)
        return SfpBase.SFP_PORT_TYPE_BIT_QSFPDD


class SonicEnvironment:
    """Wire real sfputil and EEPROM APIs to explicit mock platform/DB services."""

    def __init__(self, patch, emulator: Emulator):
        self.emulator = emulator
        # xcvr-emu's YAML monitor fields expose only the high byte of each register.
        emulator.set_temperature(25)
        emulator.set_voltage(3.3)
        self.sfp = EmulatedSfp(emulator)
        self.chassis = MockChassis(self.sfp)
        self.databases = MockDatabases()
        self._patch_platform(patch)
        sfputil = importlib.import_module("sfputil.main")
        self._patch_services(patch, sfputil)
        self.sfputil = CliCommand(sfputil.cli)
        self.publish()

    def _patch_platform(self, patch) -> None:
        platform = Mock()
        platform.get_chassis.return_value = self.chassis
        platform_module = ModuleType("sonic_platform.platform")
        setattr(platform_module, "Platform", Mock(return_value=platform))
        package = ModuleType("sonic_platform")
        setattr(package, "platform", platform_module)
        patch.setitem(sys.modules, "sonic_platform", package)
        patch.setitem(sys.modules, "sonic_platform.platform", platform_module)

    def _patch_services(self, patch, sfputil) -> None:
        ports = {"Ethernet0": [0]}
        mapping = Mock(spec=sfputilhelper.SfpUtilHelper)
        mapping.logical = list(ports)
        mapping.physical_to_logical = {0: list(ports)}
        mapping.is_logical_port.side_effect = ports.__contains__
        mapping.get_logical_to_physical.side_effect = ports.__getitem__
        mapping.get_physical_to_logical.side_effect = mapping.physical_to_logical.__getitem__
        mapping.get_asic_id_for_logical_port.return_value = 0
        patch.setattr(sfputilhelper, "SfpUtilHelper", Mock(return_value=mapping))

        patch.setattr(sfputil, "sonic_platform", sys.modules["sonic_platform"])
        patch.setattr(sfputil.os, "geteuid", Mock(return_value=0))
        patch.setattr(sfputil, "load_db_config", Mock())
        patch.setattr(device_info, "get_path_to_port_config_file", Mock(return_value="/mock/port_config.ini"))
        patch.setattr(device_info, "is_chassis", Mock(return_value=False))
        patch.setattr(clicommon, "get_interface_naming_mode", Mock(return_value="default"))
        patch.setattr(multi_asic_util, "load_db_config", Mock())
        patch.setattr(multi_asic, "is_multi_asic", Mock(return_value=False))
        patch.setattr(multi_asic, "get_front_end_namespaces", Mock(return_value=[""]))
        patch.setattr(multi_asic, "get_namespace_for_port", Mock(return_value=""))
        patch.setattr(multi_asic, "get_num_asics", Mock(return_value=1))
        for module in (sfputil, helper):
            patch.setattr(module, "platform_chassis", None)
            patch.setattr(module, "platform_sfputil", None)
            patch.setattr(module, "SonicV2Connector", Mock(return_value=self.databases))
        patch.setattr(helper, "platform_sfp_base", SfpBase)
        patch.setattr(helper, "platform_porttab_mapping_read", False)
        patch.setattr(helper, "ConfigDBConnector", Mock(return_value=self.databases))
        patch.setattr(multi_asic, "connect_config_db_for_ns", Mock(return_value=self.databases))
        patch.setattr(multi_asic, "connect_to_all_dbs_for_ns", Mock(return_value=self.databases))

    def publish(self) -> None:
        """Stand in for xcvrd by publishing native API readings to mocked STATE_DB."""
        state = self.databases.state
        state.clear()
        present = self.emulator.present()
        if present:
            self.sfp.refresh_xcvr_api()
            for table, getter in (
                ("TRANSCEIVER_INFO", self.sfp.get_transceiver_info),
                ("TRANSCEIVER_DOM_SENSOR", self.sfp.get_transceiver_dom_real_value),
                ("TRANSCEIVER_DOM_THRESHOLD", self.sfp.get_transceiver_threshold_info),
                ("TRANSCEIVER_STATUS", self.sfp.get_transceiver_status),
                ("TRANSCEIVER_STATUS_FLAG", self.sfp.get_transceiver_status_flags),
                ("TRANSCEIVER_DOM_FLAG", self.sfp.get_transceiver_dom_flags),
                ("TRANSCEIVER_FIRMWARE_INFO", self.sfp.get_transceiver_info_firmware_versions),
            ):
                values = getter()
                if values is not None:
                    state[f"{table}|Ethernet0"] = {key: str(value) for key, value in values.items()}
        state["TRANSCEIVER_STATUS_SW|Ethernet0"] = {"status": "1" if present else "0", "error": "N/A"}


class ShowContext(Db):
    """Supply Click's Db context without constructing any real Redis connectors."""

    def __init__(self, databases: MockDatabases):
        self.cfgdb = databases
        self.db = databases
        self.cfgdb_clients = {"": databases}
        self.db_clients = {"": databases}


class TransceiverCommands:
    """Bind show/config wrappers and forward their subprocess calls to real CLIs."""

    def __init__(self, patch, environment: SonicEnvironment):
        self.environment = environment
        scripts = Path(__file__).resolve().parents[1] / "scripts"
        patch.syspath_prepend(str(scripts))
        patch.setattr(device_info, "is_supervisor", Mock(return_value=False))
        loader = SourceFileLoader("xcvr_integration_sfpshow", str(scripts / "sfpshow"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        if spec is None:
            raise RuntimeError("Unable to load the sfpshow CLI")
        sfpshow = importlib.util.module_from_spec(spec)
        loader.exec_module(sfpshow)
        config = importlib.import_module("config.main")
        interfaces = importlib.import_module("show.interfaces")

        self.sfpshow = CliCommand(sfpshow.cli)
        self.show = CliCommand(interfaces.transceiver, ShowContext(environment.databases))
        self.config = CliCommand(config.transceiver, {"config_db": environment.databases, "namespace": ""})
        patch.setattr(clicommon, "run_command", self.run_command)

    def run_command(self, command: list[str], **kwargs) -> None:
        """Replace only process launching, preserving child output and exit status."""
        arguments = list(command)
        if arguments and arguments[0] == "sudo":
            arguments.pop(0)
        commands = {"sfputil": self.environment.sfputil, "sfpshow": self.sfpshow}
        if not arguments or arguments[0] not in commands:
            raise AssertionError(f"Unexpected external command: {command}")
        executable = arguments.pop(0)
        result = commands[executable].run(arguments)
        click.echo(result.output, nl=False)
        if result.exit_code:
            raise SystemExit(result.exit_code)

#!/usr/bin/env python3
"""Safely orchestrate NIST-compliant erasure of SONiC storage devices."""

import ctypes
import importlib
import json
import importlib.util
import os
import shutil
import signal
import struct
import subprocess
import sys
import sysconfig

import click

from sonic_platform_base.sonic_storage.storage_devices import StorageDevices
from sonic_py_common import device_info, logger


SYSLOG_IDENTIFIER = "secure-erase"
DEFAULT_MAX_SIZE_GB = 6
DEFAULT_EXTRA_PATHS = []
RAMFS_CONFIG = "secure_erase_ramfs.json"
RAMFS_ROOT = "/mnt/secure-erase-root"
LIVE_MOUNTS = ("/dev", "/proc", "/sys", "/run")
REQUIRED_TOOLS = (
    "chroot",
    "docker",
    "findmnt",
    "ldd",
    "lsblk",
    "mount",
    "systemctl",
    "umount",
)
POST_PIVOT_TOOLS = (
    "mount",
    "umount",
    "lsblk",
    "sync",
    "hdparm",
    "dd",
    "blockdev",
    "cmp",
    "nvme",
)
RUNTIME_MODULES = (
    "click",
    "psutil",
    "secureerase",
    "sonic_py_common",
    "sonic_platform_base",
    "sonic_platform",
)
RUNTIME_CONFIG_PATHS = (
    "/etc/ld.so.cache",
    "/etc/ld.so.conf",
    "/etc/ld.so.conf.d",
    "/etc/mtab",
    "/etc/nsswitch.conf",
    "/etc/passwd",
    "/etc/group",
    "/etc/localtime",
    "/etc/locale.conf",
    "/etc/default/locale",
    "/usr/lib/locale/locale-archive",
)
PIVOT_ROOT_SYSCALLS = {
    "x86_64": 155,
    "aarch64": 41,
}
MS_MOVE = 8192
MNT_DETACH = 2

log = logger.Logger(SYSLOG_IDENTIFIER)


class SecureEraseError(RuntimeError):
    """An expected failure which makes it unsafe to continue."""


def _status(message, error=False):
    try:
        if error:
            log.log_error(message)
        else:
            log.log_notice(message)
    except Exception:
        pass
    try:
        click.echo(message, err=error)
    except (BrokenPipeError, OSError):
        pass


def _run(command, **kwargs):
    kwargs.setdefault("check", True)
    kwargs.setdefault("universal_newlines", True)
    return subprocess.run(command, **kwargs)


def _device_path(name, device):
    for attribute in ("device_name", "diskdev", "dev"):
        value = getattr(device, attribute, None)
        if value:
            return value if value.startswith("/dev/") else os.path.join("/dev", value)
    return os.path.join("/dev", name)


def _load_platform_device(name, generic_device):
    """Use a platform plugin when one exists, retaining StorageDevices discovery."""
    module_name = "emmc_util" if name.startswith("mmcblk") else "ssd_util"
    class_name = "EmmcUtil" if module_name == "emmc_util" else "SsdUtil"
    plugin_path = os.path.join(_platform_path(), "plugins", module_name + ".py")
    if not os.path.isfile(plugin_path):
        return generic_device

    unique_name = "_secureerase_{}_{}".format(module_name, name.replace("-", "_"))
    try:
        spec = importlib.util.spec_from_file_location(unique_name, plugin_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        util_class = getattr(module, class_name)
        return util_class(_device_path(name, generic_device))
    except Exception as error:
        raise SecureEraseError(
            "Unable to load platform plugin {}: {}".format(plugin_path, error)
        )


def _root_block_device():
    source = None
    sources = {}
    for mountpoint in ("/", "/host"):
        candidate = _run(
            ["findmnt", "-n", "-o", "SOURCE", mountpoint],
            stdout=subprocess.PIPE,
            check=False,
        ).stdout.strip()
        sources[mountpoint] = candidate
        candidate = candidate.split("[", 1)[0]
        if candidate.startswith("/dev/"):
            source = candidate
            break

    if source is None:
        raise SecureEraseError(
            "Neither / nor /host is backed by a block device: {}".format(
                sources
            )
        )

    current = os.path.realpath(source)
    while True:
        parent = _run(
            ["lsblk", "-ndo", "PKNAME", current],
            stdout=subprocess.PIPE,
        ).stdout.strip()
        if not parent:
            return current
        current = os.path.join("/dev", parent.splitlines()[0])


def resolve_devices():
    """Discover devices and order secondary storage before the boot device."""
    discovered = StorageDevices().devices
    if not discovered:
        raise SecureEraseError("No storage devices were discovered")

    records = []
    for name, device in discovered.items():
        if device is None:
            raise SecureEraseError(
                "Storage device /dev/{} could not be initialized".format(name)
            )
        device = _load_platform_device(name, device)
        records.append({
            "name": name,
            "path": os.path.realpath(_device_path(name, device)),
            "device": device,
        })

    primary = os.path.realpath(_root_block_device())
    matching = [record for record in records if record["path"] == primary]
    if len(matching) != 1:
        raise SecureEraseError(
            "Boot device {} did not match exactly one discovered device".format(primary)
        )

    for record in records:
        record["primary"] = record["path"] == primary
    return sorted(records, key=lambda record: record["primary"])


def _read_mem_available():
    with open("/proc/meminfo") as meminfo:
        for line in meminfo:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    raise SecureEraseError("MemAvailable is missing from /proc/meminfo")


def _platform_path():
    platform_path, _ = device_info.get_paths_to_platform_and_hwsku_dirs()
    return platform_path


def load_ramfs_config():
    config = {
        "paths": list(DEFAULT_EXTRA_PATHS),
        "max_size_gb": DEFAULT_MAX_SIZE_GB,
    }
    path = os.path.join(_platform_path(), RAMFS_CONFIG)
    if os.path.exists(path):
        try:
            with open(path) as config_file:
                override = json.load(config_file)
        except (OSError, ValueError) as error:
            raise SecureEraseError(
                "Unable to read {}: {}".format(path, error)
            )
        if not isinstance(override, dict):
            raise SecureEraseError("{} must contain a JSON object".format(path))
        config.update(override)

    paths = config.get("paths", [])
    legacy_filesystems = config.get("filesystems", [])
    if legacy_filesystems:
        paths = list(paths) + list(legacy_filesystems)
    max_size_gb = config.get("max_size_gb")
    if (
        not isinstance(paths, list)
        or any(not isinstance(path, str) or not path.startswith("/")
               for path in paths)
    ):
        raise SecureEraseError("paths must be a list of absolute paths")
    if "/" in paths:
        raise SecureEraseError(
            "Copying the complete root filesystem is not supported; "
            "list only additional runtime paths"
        )
    missing_paths = [path for path in paths if not os.path.lexists(path)]
    if missing_paths:
        raise SecureEraseError(
            "Configured runtime paths do not exist: {}".format(
                ", ".join(missing_paths)
            )
        )
    if not isinstance(max_size_gb, (int, float)) or max_size_gb <= 0:
        raise SecureEraseError("max_size_gb must be a positive number")

    config["paths"] = sorted(set(os.path.normpath(path) for path in paths))
    config["max_size_bytes"] = int(max_size_gb * 1024 ** 3)
    return config


def _module_paths(module_name):
    try:
        module = sys.modules.get(module_name) or importlib.import_module(module_name)
    except ImportError as error:
        raise SecureEraseError(
            "Required runtime module {} is unavailable: {}".format(
                module_name, error
            )
        )

    paths = list(getattr(module, "__path__", []) or [])
    module_file = getattr(module, "__file__", None)
    if module_file and not paths:
        paths.append(module_file)
    return paths


def _is_elf(path):
    if not os.path.isfile(path):
        return False
    try:
        with open(path, "rb") as source:
            return source.read(4) == b"\x7fELF"
    except OSError:
        return False


def _elf_interpreter(path):
    """Return the PT_INTERP loader named by an ELF executable."""
    try:
        with open(path, "rb") as elf:
            header = elf.read(64)
            if len(header) < 52 or header[:4] != b"\x7fELF":
                return None

            elf_class = header[4]
            byte_order = {1: "<", 2: ">"}.get(header[5])
            if byte_order is None:
                return None
            if elf_class == 2:
                program_offset = struct.unpack_from(byte_order + "Q", header, 32)[0]
                entry_size = struct.unpack_from(byte_order + "H", header, 54)[0]
                entry_count = struct.unpack_from(byte_order + "H", header, 56)[0]
                offset_field, size_field = 8, 32
                offset_format, size_format = "Q", "Q"
            elif elf_class == 1:
                program_offset = struct.unpack_from(byte_order + "I", header, 28)[0]
                entry_size = struct.unpack_from(byte_order + "H", header, 42)[0]
                entry_count = struct.unpack_from(byte_order + "H", header, 44)[0]
                offset_field, size_field = 4, 16
                offset_format, size_format = "I", "I"
            else:
                return None

            for index in range(entry_count):
                elf.seek(program_offset + index * entry_size)
                entry = elf.read(entry_size)
                if len(entry) != entry_size:
                    return None
                entry_type = struct.unpack_from(byte_order + "I", entry, 0)[0]
                if entry_type != 3:  # PT_INTERP
                    continue
                interpreter_offset = struct.unpack_from(
                    byte_order + offset_format, entry, offset_field
                )[0]
                interpreter_size = struct.unpack_from(
                    byte_order + size_format, entry, size_field
                )[0]
                elf.seek(interpreter_offset)
                return os.fsdecode(
                    elf.read(interpreter_size).split(b"\0", 1)[0]
                )
    except (OSError, struct.error, ValueError):
        return None
    return None


def _files_under(paths):
    for path in paths:
        if os.path.isfile(path):
            yield path
        elif os.path.isdir(path):
            for root, _, files in os.walk(path):
                for filename in files:
                    yield os.path.join(root, filename)


def _elf_dependencies(path):
    output = _run(
        ["ldd", path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    ).stdout
    dependencies = set()
    for line in output.splitlines():
        fields = line.strip().split()
        candidate = None
        if "=>" in fields:
            index = fields.index("=>")
            if index + 1 < len(fields):
                candidate = fields[index + 1]
        elif fields and fields[0].startswith("/"):
            candidate = fields[0]
        if candidate and candidate.startswith("/") and os.path.exists(candidate):
            dependencies.add(candidate)
    return dependencies


def _collect_runtime_paths(config):
    paths = set(config["paths"])
    paths.add(sys.executable)

    for key in ("stdlib", "platstdlib"):
        path = sysconfig.get_paths().get(key)
        if path:
            paths.add(path)

    for path in sys.path:
        if path and path.startswith("/opt/") and os.path.exists(path):
            paths.add(path)

    for module_name in RUNTIME_MODULES:
        paths.update(_module_paths(module_name))

    for module in list(sys.modules.values()):
        module_file = getattr(module, "__file__", None)
        if module_file and os.path.isabs(module_file) and os.path.lexists(module_file):
            paths.add(module_file)

    platform_plugins = os.path.join(_platform_path(), "plugins")
    if os.path.isdir(platform_plugins):
        paths.add(platform_plugins)

    for path in RUNTIME_CONFIG_PATHS:
        if os.path.lexists(path):
            paths.add(path)

    for tool in POST_PIVOT_TOOLS:
        tool_path = shutil.which(tool)
        if tool_path:
            paths.add(tool_path)

    for path in list(paths):
        if os.path.islink(path):
            target = os.path.realpath(path)
            if not any(
                target == mountpoint or target.startswith(mountpoint + "/")
                for mountpoint in LIVE_MOUNTS
            ):
                paths.add(target)

    elf_files = [path for path in _files_under(paths) if _is_elf(path)]
    for elf_file in elf_files:
        paths.update(_elf_dependencies(elf_file))
        interpreter = _elf_interpreter(elf_file)
        if interpreter and os.path.exists(interpreter):
            paths.add(interpreter)

    return sorted(path for path in paths if os.path.lexists(path))


def _runtime_size(paths):
    total = 0
    seen = set()
    for path in paths:
        candidates = [path]
        if os.path.isdir(path) and not os.path.islink(path):
            candidates = []
            for root, directories, files in os.walk(path, followlinks=False):
                candidates.append(root)
                candidates.extend(os.path.join(root, name) for name in directories)
                candidates.extend(os.path.join(root, name) for name in files)
        for candidate in candidates:
            try:
                stat_result = os.lstat(candidate)
            except OSError as error:
                raise SecureEraseError(
                    "Unable to size runtime path {}: {}".format(candidate, error)
                )
            identity = (stat_result.st_dev, stat_result.st_ino)
            if identity not in seen:
                seen.add(identity)
                total += stat_result.st_size
    return total


def _copy_runtime_path(source, destination_root):
    destination = os.path.join(destination_root, source.lstrip("/"))
    if os.path.islink(source):
        target = os.path.realpath(source)
        target_is_live = any(
            target == mountpoint or target.startswith(mountpoint + "/")
            for mountpoint in LIVE_MOUNTS
        )
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        if target_is_live:
            if not os.path.lexists(destination):
                os.symlink(os.readlink(source), destination)
        elif os.path.isfile(target):
            # A copied path may have a symlinked parent on the source system
            # (for example /lib64 -> /usr/lib64). Recreating only the final
            # symlink can therefore leave the ELF loader dangling in RAMFS.
            # Dereference file symlinks so each requested runtime path works
            # independently of source-root directory symlinks.
            if not os.path.exists(destination):
                shutil.copy2(target, destination)
            _copy_runtime_path(target, destination_root)
        else:
            if not os.path.lexists(destination):
                os.symlink(os.readlink(source), destination)
            if target != source:
                _copy_runtime_path(target, destination_root)
        return
    if os.path.isdir(source):
        os.makedirs(destination, exist_ok=True)
        for entry in os.scandir(source):
            _copy_runtime_path(entry.path, destination_root)
        shutil.copystat(source, destination, follow_symlinks=False)
        return
    if os.path.isfile(source):
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination, follow_symlinks=False)
        return
    raise SecureEraseError("Unsupported runtime path type: {}".format(source))


def _validate_ramfs_executables():
    """Prove copied executables can load before detaching the disk root."""
    executables = {sys.executable}
    for tool in POST_PIVOT_TOOLS:
        tool_path = shutil.which(tool)
        if tool_path:
            executables.add(tool_path)

    for executable in sorted(executables):
        result = _run(
            ["chroot", RAMFS_ROOT, executable, "--help"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode in (126, 127):
            detail = result.stderr.strip() or "executable could not be loaded"
            raise SecureEraseError(
                "RAM runtime validation failed for {}: {}".format(
                    executable, detail
                )
            )


def _supports_secure_erase(device):
    method = getattr(type(device), "secure_erase", None)
    if method is None:
        return False
    try:
        from sonic_platform_base.sonic_storage.storage_base import StorageBase
        base_method = getattr(StorageBase, "secure_erase", None)
    except ImportError:
        base_method = None
    return base_method is None or method is not base_method


def preflight(records, config):
    missing = [
        tool for tool in REQUIRED_TOOLS if shutil.which(tool) is None
    ]
    if missing:
        raise SecureEraseError(
            "Required tools are missing: {}".format(", ".join(missing))
        )

    unsupported = [
        record["path"] for record in records
        if not _supports_secure_erase(record["device"])
    ]
    if unsupported:
        raise SecureEraseError(
            "secure_erase() is not implemented for: {}".format(
                ", ".join(unsupported)
            )
        )

    runtime_paths = _collect_runtime_paths(config)
    total_size = _runtime_size(runtime_paths)
    if total_size > config["max_size_bytes"]:
        raise SecureEraseError(
            "RAM runtime ({:.2f} GiB) exceeds max_size_gb ({:.2f} GiB)".format(
                total_size / float(1024 ** 3),
                config["max_size_bytes"] / float(1024 ** 3),
            )
        )
    available = _read_mem_available()
    if total_size > available:
        raise SecureEraseError(
            "Insufficient RAM: {:.2f} GiB needed, {:.2f} GiB available".format(
                total_size / float(1024 ** 3),
                available / float(1024 ** 3),
            )
        )
    config["runtime_paths"] = runtime_paths
    config["copy_size_bytes"] = total_size


def _safe_device_detail(device, method_name):
    try:
        value = getattr(device, method_name)()
        return "N/A" if value is None else str(value)
    except Exception:  # Device metadata must not prevent sanitization.
        return "N/A"


def capture_device_metadata(records):
    for record in records:
        record["model"] = _safe_device_detail(record["device"], "get_model")
        record["serial"] = _safe_device_detail(record["device"], "get_serial")


def run_pre_erase_hook():
    hook = os.path.join(_platform_path(), "pre_erase_hook")
    if os.path.exists(hook):
        if not os.access(hook, os.X_OK):
            raise SecureEraseError("{} is not executable".format(hook))
        _status("Running vendor pre-erase hook")
        _run([hook])


def quiesce_system():
    _status("Stopping SONiC services")
    _run(["systemctl", "stop", "sonic.target"])
    services = _run(
        [
            "systemctl", "list-units", "--type=service", "--all",
            "--plain", "--no-legend", "sonic-*",
        ],
        stdout=subprocess.PIPE,
    ).stdout
    service_names = [line.split()[0] for line in services.splitlines() if line.split()]
    if service_names:
        _run(["systemctl", "stop"] + service_names)

    _status("Stopping Docker containers")
    containers = _run(
        ["docker", "ps", "-q"],
        stdout=subprocess.PIPE,
    ).stdout.split()
    if containers:
        subprocess.run(
            ["docker", "stop", "--timeout", "30"] + containers,
            check=False,
            universal_newlines=True,
        )
        remaining = _run(
            ["docker", "ps", "-q"],
            stdout=subprocess.PIPE,
        ).stdout.split()
        if remaining:
            _run(["docker", "kill"] + remaining)

    _status("Disabling kernel console messages")
    with open("/proc/sys/kernel/printk", "w") as printk:
        printk.write("0 0 0 0\n")


def load_ramfs(config):
    _status("Loading minimal secure-erase runtime into RAM")
    os.makedirs(RAMFS_ROOT, exist_ok=True)
    mounted = False
    try:
        _run([
            "mount", "-t", "tmpfs", "-o",
            "size={}".format(config["max_size_bytes"]),
            "secure-erase", RAMFS_ROOT,
        ])
        mounted = True
        os.makedirs(os.path.join(RAMFS_ROOT, ".old_root"), exist_ok=True)

        for source in config["runtime_paths"]:
            _copy_runtime_path(source, RAMFS_ROOT)

        for mountpoint in LIVE_MOUNTS:
            os.makedirs(os.path.join(RAMFS_ROOT, mountpoint.lstrip("/")), exist_ok=True)
        _validate_ramfs_executables()
    except Exception:
        if mounted:
            subprocess.run(["umount", "-l", RAMFS_ROOT], check=False)
        raise


def _pivot_root(new_root, put_old):
    machine = os.uname().machine
    syscall_number = PIVOT_ROOT_SYSCALLS.get(machine)
    if syscall_number is None:
        raise SecureEraseError(
            "pivot_root syscall number is unknown for {}".format(machine)
        )

    libc = ctypes.CDLL(None, use_errno=True)
    result = libc.syscall(
        ctypes.c_long(syscall_number),
        ctypes.c_char_p(os.fsencode(new_root)),
        ctypes.c_char_p(os.fsencode(put_old)),
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))


def _move_mount(source, target):
    libc = ctypes.CDLL(None, use_errno=True)
    result = libc.mount(
        ctypes.c_char_p(os.fsencode(source)),
        ctypes.c_char_p(os.fsencode(target)),
        None,
        ctypes.c_ulong(MS_MOVE),
        None,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), source)


def _lazy_unmount(target):
    libc = ctypes.CDLL(None, use_errno=True)
    result = libc.umount2(
        ctypes.c_char_p(os.fsencode(target)),
        ctypes.c_int(MNT_DETACH),
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), target)


def pivot_to_ramfs():
    _status("Pivoting execution to RAM")
    # systemd configures the root mount as shared. pivot_root(2) rejects a
    # shared current root or new root with EINVAL, so stop mount propagation
    # before changing roots.
    _run(["mount", "--make-rprivate", "/"])
    os.chdir(RAMFS_ROOT)
    try:
        _pivot_root(".", ".old_root")
    except Exception:
        os.chdir("/")
        raise
    os.chdir("/")
    for mountpoint in LIVE_MOUNTS:
        _move_mount("/.old_root{}".format(mountpoint), mountpoint)
    _lazy_unmount("/.old_root")


def erase_devices(records):
    results = []
    for record in records:
        _status("Erasing {}".format(record["path"]))
        try:
            result = record["device"].secure_erase()
        except Exception as error:
            raise SecureEraseError(
                "{} secure erase raised: {}".format(record["path"], error)
            )
        if not isinstance(result, dict):
            raise SecureEraseError(
                "{} secure_erase() returned a non-dict result".format(record["path"])
            )
        record_result = dict(record)
        record_result["result"] = result
        results.append(record_result)
        if not result.get("success"):
            raise SecureEraseError(
                "{} failed: {}".format(record["path"], result.get("message", "unknown error"))
            )
    return results


def print_certificate(records, reason):
    _status("\nCertificate of Sanitization")
    _status("Standard: NIST SP 800-88 Rev.1")
    _status("Reason: {}".format(reason or "Not provided"))
    for record in records:
        result = record["result"]
        _status("\nDevice: {}".format(record["path"]))
        _status("Model: {}".format(record["model"]))
        _status("Serial: {}".format(record["serial"]))
        _status("Method: {}".format(result.get("method_used", "N/A")))
        _status("Result: PASS")
        _status("Detail: {}".format(result.get("message", "")))


def force_reboot():
    _status("Sanitization complete; forcing reboot")
    with open("/proc/sysrq-trigger", "w") as trigger:
        trigger.write("b\n")


def orchestrate(records, config, reason):
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    run_pre_erase_hook()
    quiesce_system()
    load_ramfs(config)
    pivot_to_ramfs()
    results = erase_devices(records)
    print_certificate(results, reason)
    force_reboot()


def _confirm(records):
    names = ", ".join(record["path"] for record in records)
    click.echo("This will IRRECOVERABLY ERASE ALL DATA on: {}".format(names))
    expected = records[-1]["path"]
    typed = click.prompt("Type the primary device name ({}) to confirm".format(expected))
    if typed != expected:
        raise SecureEraseError("Device name did not match; aborting")


@click.command()
@click.option(
    "-y", "--yes", is_flag=True, default=False,
    help="Skip interactive confirmation (requires --reason)",
)
@click.option(
    "-r", "--reason", default=None,
    help="Reason for the erase, for example RMA-653",
)
def cli(yes, reason):
    """Securely and irrecoverably erase all platform storage devices."""
    try:
        if os.geteuid() != 0:
            raise SecureEraseError("Root privileges are required for this operation")
        if yes and not reason:
            raise SecureEraseError("--reason is required when using --yes")

        records = resolve_devices()
        config = load_ramfs_config()
        preflight(records, config)
        capture_device_metadata(records)
        if not yes:
            _confirm(records)

        _status(
            "secure-erase started: devices={} reason={}".format(
                ",".join(record["path"] for record in records),
                reason,
            )
        )
        orchestrate(records, config, reason)
    except (OSError, subprocess.SubprocessError, SecureEraseError) as error:
        _status("secure-erase failed: {}".format(error), error=True)
        raise click.ClickException(str(error))


if __name__ == "__main__":
    cli()

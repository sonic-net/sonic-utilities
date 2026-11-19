import subprocess
import sys
from unittest.mock import MagicMock, mock_open, patch

from click.testing import CliRunner

from secureerase import main


class ErasableDevice:
    def __init__(self, path, success=True):
        self.dev = path
        self.success = success
        self.calls = 0

    def secure_erase(self):
        self.calls += 1
        return {
            "success": self.success,
            "method_used": "test erase + zero-write",
            "message": "verified" if self.success else "verification failed",
        }

    def get_model(self):
        return "Test Model"

    def get_serial(self):
        return "TEST123"


def test_elf_interpreter_is_collected_for_python():
    interpreter = main._elf_interpreter(sys.executable)

    assert interpreter
    assert interpreter.startswith("/")
    assert main.os.path.exists(interpreter)


def test_copy_runtime_dereferences_file_symlink(tmp_path):
    source_root = tmp_path / "source"
    destination_root = tmp_path / "runtime"
    source_root.mkdir()
    destination_root.mkdir()
    target = source_root / "loader.real"
    target.write_bytes(b"loader")
    link = source_root / "loader"
    link.symlink_to(target.name)

    main._copy_runtime_path(str(link), str(destination_root))

    copied_link_path = destination_root / str(link).lstrip("/")
    assert not copied_link_path.is_symlink()
    assert copied_link_path.read_bytes() == b"loader"


def test_resolve_devices_orders_primary_last():
    primary = ErasableDevice("/dev/sda")
    secondary = ErasableDevice("/dev/sdb")

    with patch.object(
        main, "StorageDevices",
        return_value=MagicMock(devices={"sda": primary, "sdb": secondary}),
    ), patch.object(
        main, "_load_platform_device", side_effect=lambda name, device: device
    ), patch.object(main, "_root_block_device", return_value="/dev/sda"):
        records = main.resolve_devices()

    assert [record["path"] for record in records] == ["/dev/sdb", "/dev/sda"]
    assert [record["primary"] for record in records] == [False, True]


def test_root_block_device_uses_host_for_sonic_overlay():
    def fake_run(command, **kwargs):
        if command[:4] == ["findmnt", "-n", "-o", "SOURCE"]:
            source = "root-overlay\n" if command[-1] == "/" else "/dev/sda3\n"
        elif command[-1] == "/dev/sda3":
            source = "sda\n"
        else:
            source = ""
        return subprocess.CompletedProcess(command, 0, source, "")

    with patch.object(main, "_run", side_effect=fake_run):
        assert main._root_block_device() == "/dev/sda"


def test_preflight_rejects_unsupported_device_before_size_checks():
    records = [{"path": "/dev/sda", "device": object()}]
    config = {"paths": [], "max_size_bytes": 1024}

    with patch.object(main.shutil, "which", return_value="/usr/bin/tool"), \
            patch.object(main, "_collect_runtime_paths") as collect:
        try:
            main.preflight(records, config)
            assert False, "preflight should reject unsupported devices"
        except main.SecureEraseError as error:
            assert "not implemented" in str(error)
    collect.assert_not_called()


def test_preflight_checks_ram_and_records_copy_size():
    records = [{"path": "/dev/sda", "device": ErasableDevice("/dev/sda")}]
    config = {"paths": [], "max_size_bytes": 1000}

    with patch.object(main.shutil, "which", return_value="/usr/bin/tool"), \
            patch.object(main, "_collect_runtime_paths", return_value=["/runtime"]), \
            patch.object(main, "_runtime_size", return_value=300), \
            patch.object(main, "_read_mem_available", return_value=500):
        main.preflight(records, config)

    assert config["copy_size_bytes"] == 300
    assert config["runtime_paths"] == ["/runtime"]


def test_quiesce_stops_services_then_containers():
    responses = {
        ("systemctl", "list-units"): subprocess.CompletedProcess(
            [], 0, "sonic-a.service loaded active running\n", ""
        ),
        ("docker", "ps"): subprocess.CompletedProcess([], 0, "abc\n", ""),
    }
    docker_ps_count = [0]

    def fake_run(command, **kwargs):
        if command[:2] == ["systemctl", "list-units"]:
            return responses[("systemctl", "list-units")]
        if command[:3] == ["docker", "ps", "-q"]:
            docker_ps_count[0] += 1
            output = "abc\n" if docker_ps_count[0] == 1 else ""
            return subprocess.CompletedProcess(command, 0, output, "")
        return subprocess.CompletedProcess(command, 0, "", "")

    with patch.object(main, "_run", side_effect=fake_run) as run, \
            patch.object(main.subprocess, "run") as subprocess_run, \
            patch("builtins.open", mock_open()):
        main.quiesce_system()

    commands = [entry.args[0] for entry in run.call_args_list]
    assert commands[0] == ["systemctl", "stop", "sonic.target"]
    assert ["systemctl", "stop", "sonic-a.service"] in commands
    subprocess_run.assert_called_once_with(
        ["docker", "stop", "--timeout", "30", "abc"],
        check=False,
        universal_newlines=True,
    )


def test_pivot_makes_shared_mounts_private_first():
    with patch.object(main, "_run") as run, patch.object(
        main, "_pivot_root"
    ) as pivot, patch.object(main, "_move_mount") as move, patch.object(
        main, "_lazy_unmount"
    ) as unmount, patch.object(main.os, "chdir"):
        main.pivot_to_ramfs()

    commands = [entry.args[0] for entry in run.call_args_list]
    assert commands[0] == ["mount", "--make-rprivate", "/"]
    pivot.assert_called_once_with(".", ".old_root")
    assert move.call_count == len(main.LIVE_MOUNTS)
    unmount.assert_called_once_with("/.old_root")


def test_erase_devices_stops_after_first_failure():
    first = ErasableDevice("/dev/sdb", success=False)
    second = ErasableDevice("/dev/sda", success=True)
    records = [
        {"path": "/dev/sdb", "device": first},
        {"path": "/dev/sda", "device": second},
    ]

    try:
        main.erase_devices(records)
        assert False, "erase_devices should stop on failure"
    except main.SecureEraseError as error:
        assert "verification failed" in str(error)

    assert first.calls == 1
    assert second.calls == 0


def test_orchestrate_runs_erase_then_reboots():
    order = []

    def mark(name, result=None):
        def invoke(*args, **kwargs):
            order.append(name)
            return result
        return invoke

    records = [{"path": "/dev/sda", "device": ErasableDevice("/dev/sda")}]
    erased = [dict(records[0], result={"success": True})]
    with patch.object(main.signal, "signal"), \
            patch.object(main, "run_pre_erase_hook", side_effect=mark("hook")), \
            patch.object(main, "quiesce_system", side_effect=mark("quiesce")), \
            patch.object(main, "load_ramfs", side_effect=mark("load")), \
            patch.object(main, "pivot_to_ramfs", side_effect=mark("pivot")), \
            patch.object(main, "erase_devices", side_effect=mark("erase", erased)), \
            patch.object(main, "print_certificate", side_effect=mark("certificate")), \
            patch.object(main, "force_reboot", side_effect=mark("reboot")):
        main.orchestrate(records, {}, "RMA-1")

    assert order == [
        "hook", "quiesce", "load", "pivot", "erase", "certificate", "reboot"
    ]


def test_cli_requires_reason_for_noninteractive_mode():
    with patch.object(main.os, "geteuid", return_value=0):
        result = CliRunner().invoke(main.cli, ["--yes"])

    assert result.exit_code != 0
    assert "--reason is required" in result.output


def test_cli_preflights_before_confirmation_and_orchestration():
    records = [{"path": "/dev/sda", "device": ErasableDevice("/dev/sda")}]
    config = {"paths": [], "max_size_bytes": 1}

    with patch.object(main.os, "geteuid", return_value=0), \
            patch.object(main, "resolve_devices", return_value=records), \
            patch.object(main, "load_ramfs_config", return_value=config), \
            patch.object(
                main, "preflight", side_effect=main.SecureEraseError("unsafe")
            ), \
            patch.object(main, "_confirm") as confirm, \
            patch.object(main, "orchestrate") as orchestrate:
        result = CliRunner().invoke(main.cli)

    assert result.exit_code != 0
    assert "unsafe" in result.output
    confirm.assert_not_called()
    orchestrate.assert_not_called()

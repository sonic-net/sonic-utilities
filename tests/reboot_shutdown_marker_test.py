import os
import re
import subprocess
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).parents[1] / "scripts"


@pytest.mark.parametrize("script_name", ["reboot", "fast-reboot", "soft-reboot"])
@pytest.mark.parametrize("failure", [None, "mkdir", "touch"])
def test_shutdown_marker(tmp_path, script_name, failure):
    script = (SCRIPTS / script_name).read_text()
    function = re.search(
        r"^function mark_shutdown_in_progress\(\).*?^}", script, re.M | re.S
    ).group()
    marker_dir = tmp_path / "sonic"
    marker = marker_dir / "shutdown-in-progress"
    driver = function + '''
debug() { printf '%s\\n' "$*"; }
'''
    if failure:
        driver += failure + '() { return 1; }\n'
    driver += 'mark_shutdown_in_progress\nmark_shutdown_in_progress\n'
    env = dict(os.environ, SHUTDOWN_IN_PROGRESS_DIR=str(marker_dir),
               SHUTDOWN_IN_PROGRESS_FILE=str(marker))
    result = subprocess.run(["bash", "-e", "-c", driver], env=env,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    if failure:
        assert not marker.exists()
        assert result.stdout.splitlines() == ["Failed to mark shutdown in progress"] * 2
    else:
        assert marker.is_file()
        assert marker.read_bytes() == b""
        assert result.stdout == ""


@pytest.mark.parametrize("script_name", ["reboot", "soft-reboot"])
def test_shutdown_marker_before_service_teardown(script_name):
    script = (SCRIPTS / script_name).read_text()
    call = "\nmark_shutdown_in_progress\n"
    assert script.count(call) == 1
    assert script.index("\nreboot_pre_check\n") < script.index(call)
    assert call + "stop_sonic_services\n" in script
    if script_name == "reboot":
        assert script.index('exit $smart_switch_result') < script.index(call)


def test_fast_reboot_marker_after_commit_before_teardown():
    script = (SCRIPTS / "fast-reboot").read_text()
    call = "\nmark_shutdown_in_progress\n"
    assert script.count(call) == 1
    assert "\nset +e" + call in script
    assert (script.index("    execute_in_namespaces asic pause_orchagent") <
            script.index(call) < script.index("\n    stop_service $service"))


@pytest.mark.parametrize("script_name", ["warm-reboot", "express-reboot"])
def test_reboot_alias_uses_fast_reboot_marker(script_name):
    assert (SCRIPTS / script_name).is_symlink()
    assert (SCRIPTS / script_name).resolve() == SCRIPTS / "fast-reboot"

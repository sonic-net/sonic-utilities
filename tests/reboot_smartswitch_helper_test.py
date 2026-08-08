import os
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "reboot_smartswitch_helper"


def run_helper_function(tmp_path, function_call, docker_rc=0):
    command_log = tmp_path / "command.log"
    env = os.environ.copy()
    env["COMMAND_LOG"] = str(command_log)
    script = f'''
EXIT_SUCCESS=0
EXIT_ERROR=1
source "{SCRIPT}"
docker() {{
    printf '%s\n' "$*" > "$COMMAND_LOG"
    printf '{{"active":false}}\n'
    return "$DOCKER_RC"
}}
jq() {{ printf 'false\n'; }}
get_dpu_ip() {{ printf '169.254.200.1\n'; }}
get_gnmi_port() {{ printf '8080\n'; }}
wait_for_dpu_reboot_status() {{ return 0; }}
{function_call}
'''
    env["DOCKER_RC"] = str(docker_rc)
    result = subprocess.run(
        ["bash", "-c", script], env=env, capture_output=True, text=True
    )
    return result, command_log.read_text()


def test_get_reboot_status_uses_tls(tmp_path):
    result, command = run_helper_function(
        tmp_path, "get_reboot_status 169.254.200.1 8080"
    )
    assert result.returncode == 0
    assert "-insecure" in command
    assert "-notls" not in command
    assert "-rpc RebootStatus" in command


def test_gnmi_reboot_dpu_uses_tls(tmp_path):
    result, command = run_helper_function(tmp_path, "gnmi_reboot_dpu dpu0")
    assert result.returncode == 0
    assert "-insecure" in command
    assert "-notls" not in command
    assert "-rpc Reboot" in command


def test_get_reboot_status_preserves_gnoi_failure(tmp_path):
    result, _ = run_helper_function(
        tmp_path, "get_reboot_status 169.254.200.1 8080", docker_rc=1
    )
    assert result.returncode != 0


def test_gnmi_reboot_dpu_reports_gnoi_failure(tmp_path):
    result, _ = run_helper_function(
        tmp_path, "gnmi_reboot_dpu dpu0", docker_rc=1
    )
    assert result.returncode == 0
    assert "Failed to send gnoi command to halt services" in result.stderr

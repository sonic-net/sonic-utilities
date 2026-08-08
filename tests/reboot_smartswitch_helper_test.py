import os
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "reboot_smartswitch_helper"


def run_helper_function(tmp_path, function_call, docker_rc=0, fail_port=""):
    command_log = tmp_path / "command.log"
    platform_json = tmp_path / "platform.json"
    platform_json.write_text('{"dpu_halt_services_timeout": 1}')
    env = os.environ.copy()
    env["COMMAND_LOG"] = str(command_log)
    env["PLATFORM_JSON_PATH"] = str(platform_json)
    script = f'''
EXIT_SUCCESS=0
EXIT_ERROR=1
source "{SCRIPT}"
docker() {{
    printf '%s\n' "$*" >> "$COMMAND_LOG"
    printf '%s\n' "$DOCKER_OUTPUT"
    if [ -n "$FAIL_PORT" ] && [[ "$*" == *":$FAIL_PORT"* ]]; then
        return 1
    fi
    return "$DOCKER_RC"
}}
timeout() {{ shift; docker "$@"; }}
jq() {{ printf 'false\n'; }}
get_dpu_ip() {{ printf '169.254.200.1\n'; }}
get_gnmi_ports() {{ printf '8080\n50052\n'; }}
{function_call}
'''
    env["DOCKER_RC"] = str(docker_rc)
    env["FAIL_PORT"] = fail_port
    env["DOCKER_OUTPUT"] = '{"active":false}'
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
    assert result.returncode != 0
    assert "Failed to find a reachable gNMI port" in result.stderr


def test_gnmi_reboot_dpu_falls_back_to_native_port(tmp_path):
    result, commands = run_helper_function(
        tmp_path, "gnmi_reboot_dpu dpu0", fail_port="8080"
    )
    assert result.returncode == 0
    assert "-target 169.254.200.1:8080" in commands
    assert "-target 169.254.200.1:50052" in commands
    command_lines = commands.splitlines()
    assert "-rpc Time" in command_lines[0]
    assert "-rpc Time" in command_lines[1]
    assert "-rpc Reboot" in command_lines[2]
    assert "-target 169.254.200.1:50052" in command_lines[3]
    assert "-rpc RebootStatus" in command_lines[3]
    assert sum("-rpc Reboot " in f"{line} " for line in command_lines) == 1


def test_get_reboot_status_rejects_malformed_output(tmp_path):
    command_log = tmp_path / "command.log"
    script = f'''
EXIT_SUCCESS=0
EXIT_ERROR=1
source "{SCRIPT}"
timeout() {{ shift; docker "$@"; }}
docker() {{ printf 'not-json\n'; }}
get_reboot_status 169.254.200.1 50052
'''
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert result.returncode != 0


def test_get_gnmi_ports_orders_and_deduplicates(tmp_path):
    script = f'''
EXIT_SUCCESS=0
EXIT_ERROR=1
source "{SCRIPT}"
sonic-db-cli() {{
    if [ "$2" = "keys" ]; then
        printf 'DPU|dpu0\n'
    else
        printf '%s\n' "$CONFIGURED_PORT"
    fi
}}
get_gnmi_ports dpu0
'''
    env = os.environ.copy()
    env["CONFIGURED_PORT"] = "50052"
    result = subprocess.run(
        ["bash", "-c", script], env=env, capture_output=True, text=True, check=True
    )
    assert result.stdout.splitlines() == ["50052", "8080"]

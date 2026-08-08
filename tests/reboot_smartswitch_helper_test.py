import os
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "reboot_smartswitch_helper"


def run_helper_function(tmp_path, function_call, docker_rc=0, fail_port=""):
    command_log = tmp_path / "command.log"
    platform_json = tmp_path / "platform.json"
    platform_json.write_text('{"dpu_halt_services_timeout": 6}')
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
get_dpu_ip() {{ printf '169.254.200.1\n'; }}
get_gnmi_ports() {{ printf '8080\n50052\n'; }}
{function_call}
'''
    env["DOCKER_RC"] = str(docker_rc)
    env["FAIL_PORT"] = fail_port
    env["DOCKER_OUTPUT"] = '{"active":false,"status":{"status":1}}'
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


def test_get_reboot_status_rejects_failure_status(tmp_path):
    script = f'''
EXIT_SUCCESS=0
EXIT_ERROR=1
source "{SCRIPT}"
timeout() {{ shift; docker "$@"; }}
docker() {{ printf '{{"active":false,"status":{{"status":3}}}}\n'; }}
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


def test_reboot_dpu_continues_hardware_reboot_and_returns_gnoi_failure(tmp_path):
    platform_json = tmp_path / "platform.json"
    platform_json.write_text('{"DPUS":{"dpu0":{"bus_info":"0000:00:00.0"}}}')
    marker = tmp_path / "platform-rebooted"
    script = f'''
EXIT_SUCCESS=0
EXIT_ERROR=1
PLATFORM_JSON_PATH="{platform_json}"
source "{SCRIPT}"
show() {{ printf '  DPU0 test Online up\n'; }}
get_module_state_transition_flag() {{ return 1; }}
set_module_state_transition_flag() {{ return 0; }}
clear_module_state_transition_flag() {{ return 0; }}
gnmi_reboot_dpu() {{ return 1; }}
module_pre_shutdown() {{ return 0; }}
module_post_startup() {{ return 0; }}
reboot_dpu_platform() {{ touch "{marker}"; return 0; }}
reboot_dpu dpu0 DPU
'''
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert result.returncode != 0
    assert marker.exists()


def test_reboot_all_dpus_collects_background_failures():
    script = f'''
EXIT_SUCCESS=0
EXIT_ERROR=1
source "{SCRIPT}"
reboot_dpu() {{ [ "$1" != "dpu1" ]; }}
reboot_all_dpus 3
'''
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert result.returncode == 1


def test_whole_smartswitch_reboot_continues_after_dpu_failure():
    script = f'''
EXIT_SUCCESS=0
EXIT_ERROR=1
source "{SCRIPT}"
get_num_dpus() {{ printf '2\n'; }}
is_dpu() {{ return 1; }}
is_smartswitch() {{ return 0; }}
reboot_all_dpus() {{ return 1; }}
handle_smart_switch no no ""
'''
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert result.returncode == 0
    assert "continuing SmartSwitch reboot" in result.stderr


def test_reboot_dpu_propagates_platform_reboot_failure(tmp_path):
    platform_json = tmp_path / "platform.json"
    platform_json.write_text('{"DPUS":{"dpu0":{"bus_info":"0000:00:00.0"}}}')
    script = f'''
EXIT_SUCCESS=0
EXIT_ERROR=1
PLATFORM_JSON_PATH="{platform_json}"
source "{SCRIPT}"
show() {{ printf '  DPU0 test Online up\n'; }}
get_module_state_transition_flag() {{ return 1; }}
set_module_state_transition_flag() {{ return 0; }}
clear_module_state_transition_flag() {{ return 0; }}
gnmi_reboot_dpu() {{ return 0; }}
module_pre_shutdown() {{ return 0; }}
reboot_dpu_platform() {{ return 1; }}
reboot_dpu dpu0 DPU
'''
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert result.returncode != 0


def test_reboot_dpu_clears_transition_flag_when_bus_info_missing(tmp_path):
    platform_json = tmp_path / "platform.json"
    platform_json.write_text('{"DPUS":{"dpu0":{}}}')
    marker = tmp_path / "cleared"
    script = f'''
EXIT_SUCCESS=0
EXIT_ERROR=1
PLATFORM_JSON_PATH="{platform_json}"
source "{SCRIPT}"
show() {{ printf '  DPU0 test Online up\n'; }}
get_module_state_transition_flag() {{ return 1; }}
set_module_state_transition_flag() {{ return 0; }}
clear_module_state_transition_flag() {{ touch "{marker}"; return 0; }}
gnmi_reboot_dpu() {{ return 0; }}
reboot_dpu dpu0 DPU
'''
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert result.returncode != 0
    assert marker.exists()


def test_reboot_dpu_fails_when_chassis_status_fails(tmp_path):
    script = f'''
EXIT_SUCCESS=0
EXIT_ERROR=1
source "{SCRIPT}"
show() {{ return 1; }}
reboot_dpu dpu0 DPU
'''
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert result.returncode != 0

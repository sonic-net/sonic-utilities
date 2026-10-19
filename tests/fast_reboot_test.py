import os
import re
import pytest
import shutil
import subprocess
import tempfile
from pathlib import Path


FAST_REBOOT = Path(__file__).parents[1] / "scripts" / "fast-reboot"


@pytest.mark.parametrize("reboot_type", ["warm-reboot", "fastfast-reboot", "express-reboot", "fast-reboot"])
@pytest.mark.parametrize("probe_success", [False, True])
@pytest.mark.parametrize("namespace", ["", "asic1"])
def test_lag_keepalive_preserves_only_negotiated_retry_counts(tmp_path, reboot_type, probe_success, namespace):
    script = FAST_REBOOT.read_text()
    function = re.search(r"^function start_lag_keepalive\(\).*?^}", script, re.M | re.S).group()
    # Redirect the marker to a test-owned path, never touching live reboot state.
    dev = namespace.removeprefix("asic")
    marker = tmp_path / f"probe_success{dev}"
    if probe_success:
        marker.touch()
    else:
        (tmp_path / "probe_success_other_asic").touch()
    function = function.replace("/tmp/teamd_retry_count_probe_success", str(tmp_path / "probe_success"))
    driver = function + '''
debug() { :; }
timeout() { printf '<%s>\\n' "$@"; }
sleep() { printf 'sleep:%s\\n' "$1"; }
start_lag_keepalive
'''
    env = dict(os.environ, REBOOT_TYPE=reboot_type, NETNS=namespace, DEV=dev,
               LAG_KEEPALIVE_SCRIPT="/usr/local/bin/lag_keepalive.py")
    result = subprocess.run(["bash", "-e", "-c", driver], env=env,
                            capture_output=True, text=True, timeout=10)
    expected = ["<--foreground>", "<30>", "<python3>", "</usr/local/bin/lag_keepalive.py>",
                "<--fork-into-background>", "<--namespace>", f"<{namespace}>"]
    if probe_success and reboot_type != "fast-reboot":
        expected.append("<--preserve-retry-count>")
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == expected + ["sleep:5"]


def test_lag_keepalive_starts_after_negotiation_before_shutdown():
    script = FAST_REBOOT.read_text()
    start = "execute_in_namespaces asic start_lag_keepalive"
    assert script.count(start) == 1
    assert (script.index("    setup_control_plane_assistant", script.index("execute_in_namespaces all init_warm")) <
            script.index("    execute_in_namespaces asic probe_teamd_retry_count") <
            script.index("    execute_in_namespaces asic pause_orchagent") <
            script.index("    execute_in_namespaces asic increase_teamd_retry_count") <
            script.index("\nset +e") <
            script.index("    execute_in_namespaces asic filter_routes") <
            script.index("trap '' EXIT HUP INT QUIT TERM KILL ABRT ALRM") <
            script.index(start) < script.index("\n    stop_service $service"))


@pytest.mark.parametrize("reboot_type", ["warm-reboot", "fastfast-reboot", "express-reboot", "fast-reboot"])
@pytest.mark.parametrize("increase_status", [0, 1])
@pytest.mark.parametrize("keepalive_status", [0, 1, 124])
def test_lag_keepalive_shutdown_sequence(reboot_type, increase_status, keepalive_status):
    script = FAST_REBOOT.read_text()
    start = script.index("execute_in_namespaces all init_warm_reboot_states")
    keepalive_call = "execute_in_namespaces asic start_lag_keepalive"
    end = script.index(keepalive_call, start) + len(keepalive_call)
    sequence = re.sub(r"^function \w+\(\).*?^}\n", "", script[start:end], flags=re.M | re.S)
    driver = '''
execute_in_namespaces() { shift; "$@"; }
init_warm_reboot_states() { echo init; }
setup_control_plane_assistant() { echo cpa; }
probe_teamd_retry_count() { echo probe; }
pause_orchagent() { echo pause; }
increase_teamd_retry_count() { echo increase; return "$INCREASE_STATUS"; }
filter_routes() { echo filter; }
start_lag_keepalive() { echo keepalive; return "$KEEPALIVE_STATUS"; }
''' + sequence + '\necho shutdown\n'
    env = dict(os.environ, REBOOT_TYPE=reboot_type, NUM_ASIC="1",
               REQUIRE_TEAMD_RETRY_COUNT="no", INCREASE_STATUS=str(increase_status),
               KEEPALIVE_STATUS=str(keepalive_status))
    result = subprocess.run(["bash", "-e", "-c", driver], env=env,
                            capture_output=True, text=True, timeout=10)
    if reboot_type == "fast-reboot":
        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == ["init", "cpa", "pause", "filter", "keepalive", "shutdown"]
    else:
        assert result.returncode == increase_status, result.stderr
        expected = ["init", "cpa", "probe", "pause", "increase"]
        if not increase_status:
            expected.extend(["keepalive", "shutdown"])
        assert result.stdout.splitlines() == expected


def run_cpa_tunnel_check(tmp_path, tunnel_type="", tunnel_term_type=""):
    command_log = tmp_path / "commands.log"
    script = f'''
EXIT_LEFTOVER_CPA_TUNNEL=30
source <(sed -n '/^function abort_reboot_if_cpa_tunnel_is_leftover()/,/^}}/p' "{FAST_REBOOT}")

debug() {{ :; }}
error() {{ printf '%s\n' "$*" >&2; }}
sonic-db-cli() {{
    printf '%s\n' "$*" >> "$COMMAND_LOG"
    if [[ "$3" == "KEYS" && "$4" == "ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL:*" ]]; then
        if [[ -n "$TUNNEL_TYPE" ]]; then
            printf 'ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL:oid:0x1\n'
        fi
    elif [[ "$3" == "HGET" && "$5" == "SAI_TUNNEL_ATTR_TYPE" ]]; then
        printf '%s\n' "$TUNNEL_TYPE"
    elif [[ "$3" == "KEYS" && "$4" == "ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_TERM_TABLE_ENTRY:*" ]]; then
        if [[ -n "$TUNNEL_TERM_TYPE" ]]; then
            printf 'ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_TERM_TABLE_ENTRY:oid:0x2\n'
        fi
    elif [[ "$3" == "HGET" && "$5" == "SAI_TUNNEL_TERM_TABLE_ENTRY_ATTR_TUNNEL_TYPE" ]]; then
        printf '%s\n' "$TUNNEL_TERM_TYPE"
    fi
}}

abort_reboot_if_cpa_tunnel_is_leftover
'''
    env = os.environ.copy()
    env["COMMAND_LOG"] = str(command_log)
    env["TUNNEL_TYPE"] = tunnel_type
    env["TUNNEL_TERM_TYPE"] = tunnel_term_type
    result = subprocess.run(
        ["bash", "-c", script], env=env, capture_output=True, text=True
    )
    return result, command_log.read_text().splitlines()


class TestFastReboot:
    @pytest.mark.parametrize(
        "working_script,failing_script", [
            pytest.param('whoami', 'logname', id='without_logname'),
            pytest.param('logname', 'whoami', id='without_whoami'),
        ]
    )
    def test_fast_reboot_user(self, working_script, failing_script):
        test_path = os.path.dirname(os.path.abspath(__file__))
        fast_reboot = os.path.join(test_path, '..', 'scripts', 'fast-reboot')
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_script_path = os.path.join(tmp_dir, working_script)
            with open(working_script_path, 'w') as f:
                f.write('echo root')
                os.chmod(working_script_path, 0o700)
            shutil.copy('/bin/false', os.path.join(tmp_dir, failing_script))
            shutil.copy('/bin/true', os.path.join(tmp_dir, 'sonic-cfggen'))
            env = os.environ.copy()
            env['PATH'] = f"{tmp_dir}:{env.get('PATH', '')}"
            res = subprocess.run([fast_reboot, '-h'], env=env)
        assert res.returncode == 0

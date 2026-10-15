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
            script.index(start) < script.index("\nset +e", script.index(start)))


@pytest.mark.parametrize("reboot_type", ["warm-reboot", "fastfast-reboot", "express-reboot", "fast-reboot"])
@pytest.mark.parametrize("increase_status", [0, 1])
def test_lag_keepalive_shutdown_sequence(reboot_type, increase_status):
    script = FAST_REBOOT.read_text()
    start = script.index("execute_in_namespaces all init_warm_reboot_states")
    end = script.index("\nset +e", start)
    sequence = re.sub(r"^function \w+\(\).*?^}\n", "", script[start:end], flags=re.M | re.S)
    driver = '''
execute_in_namespaces() { shift; "$@"; }
init_warm_reboot_states() { echo init; }
setup_control_plane_assistant() { echo cpa; }
probe_teamd_retry_count() { echo probe; }
pause_orchagent() { echo pause; }
increase_teamd_retry_count() { echo increase; return "$INCREASE_STATUS"; }
start_lag_keepalive() { echo keepalive; }
''' + sequence
    env = dict(os.environ, REBOOT_TYPE=reboot_type, NUM_ASIC="1",
               REQUIRE_TEAMD_RETRY_COUNT="no", INCREASE_STATUS=str(increase_status))
    result = subprocess.run(["bash", "-e", "-c", driver], env=env,
                            capture_output=True, text=True, timeout=10)
    if reboot_type == "fast-reboot":
        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == ["init", "cpa", "pause", "keepalive"]
    else:
        assert result.returncode == increase_status, result.stderr
        expected = ["init", "cpa", "probe", "pause", "increase"]
        if not increase_status:
            expected.append("keepalive")
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
            shutil.copy('/bin/true', os.path.join(tmp_dir, 'sonic-db-cli'))
            env = os.environ.copy()
            env['PATH'] = f"{tmp_dir}:{env.get('PATH', '')}"
            res = subprocess.run([fast_reboot, '-h'], env=env)
        assert res.returncode == 0

    def test_cpa_tunnel_check_uses_uds_and_continues_without_vxlan(self, tmp_path):
        result, commands = run_cpa_tunnel_check(
            tmp_path,
            tunnel_type="SAI_TUNNEL_TYPE_IPINIP",
            tunnel_term_type="SAI_TUNNEL_TYPE_IPINIP",
        )

        assert result.returncode == 0
        assert commands == [
            "--unixsocket ASIC_DB KEYS ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL:*",
            "--unixsocket ASIC_DB HGET ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL:oid:0x1 SAI_TUNNEL_ATTR_TYPE",
            "--unixsocket ASIC_DB KEYS ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_TERM_TABLE_ENTRY:*",
            "--unixsocket ASIC_DB HGET "
            "ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_TERM_TABLE_ENTRY:oid:0x2 "
            "SAI_TUNNEL_TERM_TABLE_ENTRY_ATTR_TUNNEL_TYPE",
        ]

    @pytest.mark.parametrize(
        "tunnel_type,tunnel_term_type",
        [
            ("SAI_TUNNEL_TYPE_VXLAN", ""),
            ("", "SAI_TUNNEL_TYPE_VXLAN"),
        ],
    )
    def test_cpa_tunnel_check_aborts_for_leftover_vxlan(
        self, tmp_path, tunnel_type, tunnel_term_type
    ):
        result, commands = run_cpa_tunnel_check(
            tmp_path,
            tunnel_type=tunnel_type,
            tunnel_term_type=tunnel_term_type,
        )

        assert result.returncode == 30
        assert "Device has leftover CPA tunnel configuration" in result.stderr
        assert commands
        assert all(command.startswith("--unixsocket ASIC_DB ") for command in commands)

# fast-reboot runs its main flow at the top level and cannot be sourced, so these
# tests extract the CPA functions with sed and run them against stub commands.
CPA_FUNCTIONS = ['debug', 'error', 'abort_reboot_if_cpa_tunnel_is_leftover', 'setup_control_plane_assistant']

# KEYS returns one object of the requested type when FAKE_VXLAN_TUNNEL=yes; HGET reports it as VxLAN.
SONIC_DB_CLI_STUB = '''#!/bin/bash
if [[ "$3" == "KEYS" && "${FAKE_VXLAN_TUNNEL}" == "yes" ]]; then
    echo "${4%\\*}oid:0x2a000000000001"
elif [[ "$3" == "HGET" ]]; then
    echo "SAI_TUNNEL_TYPE_VXLAN"
fi
'''

ASSISTANT_STUB = '''#!/bin/bash
echo "assistant $*" >> "${CALL_LOG}"
'''


def run_setup_control_plane_assistant(tmp_path, vxlan_tunnel, assistant_ip_list, hwsku='Force10-S6000'):
    for name, body in (('sonic-db-cli', SONIC_DB_CLI_STUB), ('neighbor_advertiser', ASSISTANT_STUB),
                       ('logger', '#!/bin/bash\n')):
        stub = tmp_path / name
        stub.write_text(body)
        stub.chmod(0o755)
    call_log = tmp_path / 'calls.log'
    call_log.touch()

    fast_reboot = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts', 'fast-reboot')
    extract = ';'.join('/^function {}()/,/^}}/p'.format(name) for name in CPA_FUNCTIONS)
    driver = (
        f'source <(grep -E "^EXIT_[A-Z_]+=[0-9]+$" "{fast_reboot}")\n'
        f'source <(sed -n \'{extract}\' "{fast_reboot}")\n'
        f'for f in {" ".join(CPA_FUNCTIONS)}; do declare -F $f > /dev/null || exit 99; done\n'
        'check_mirror_session_acls() { echo "check_mirror_session_acls" >> "${CALL_LOG}"; }\n'
        'setup_control_plane_assistant\n'
    )
    env = os.environ.copy()
    env.update({
        'PATH': f"{tmp_path}:{env.get('PATH', '')}",
        'FAKE_VXLAN_TUNNEL': 'yes' if vxlan_tunnel else 'no',
        'ASSISTANT_IP_LIST': assistant_ip_list,
        'ASSISTANT_SCRIPT': str(tmp_path / 'neighbor_advertiser'),
        'HWSKU': hwsku,
        'CALL_LOG': str(call_log),
    })
    res = subprocess.run(['bash', '-e', '-c', driver], env=env, capture_output=True, text=True)
    assert res.returncode != 99, 'functions not extracted from fast-reboot: {}'.format(res.stderr)
    return res, call_log.read_text().splitlines()


class TestControlPlaneAssistantLeftoverTunnel:
    def test_vxlan_tunnel_without_cpa_does_not_abort(self, tmp_path):
        res, calls = run_setup_control_plane_assistant(tmp_path, vxlan_tunnel=True, assistant_ip_list='')
        assert res.returncode == 0, res.stderr
        assert calls == []

    def test_vxlan_tunnel_on_cpa_incapable_hwsku_does_not_abort(self, tmp_path):
        res, calls = run_setup_control_plane_assistant(
            tmp_path, vxlan_tunnel=True, assistant_ip_list='10.0.0.1', hwsku='DellEMC-Z9332f-M-O16C64')
        assert res.returncode == 0, res.stderr
        assert calls == []

    def test_leftover_tunnel_with_cpa_aborts(self, tmp_path):
        res, calls = run_setup_control_plane_assistant(tmp_path, vxlan_tunnel=True, assistant_ip_list='10.0.0.1')
        assert res.returncode == 30
        assert 'leftover CPA tunnel' in res.stderr
        assert calls == []

    def test_no_tunnel_with_cpa_sets_up_assistant(self, tmp_path):
        res, calls = run_setup_control_plane_assistant(tmp_path, vxlan_tunnel=False, assistant_ip_list='10.0.0.1')
        assert res.returncode == 0, res.stderr
        assert calls == ['assistant -s 10.0.0.1 -m set', 'check_mirror_session_acls']

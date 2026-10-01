import os
import pytest
import shutil
import subprocess
import tempfile


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


# fast-reboot runs its main flow at the top level and cannot be sourced, so these
# tests extract the CPA functions with sed and run them against stub commands.
CPA_FUNCTIONS = ['debug', 'error', 'abort_reboot_if_cpa_tunnel_is_leftover', 'setup_control_plane_assistant']

# KEYS returns one object of the requested type when FAKE_VXLAN_TUNNEL=yes; HGET reports it as VxLAN.
REDIS_CLI_STUB = '''#!/bin/bash
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
    for name, body in (('redis-cli', REDIS_CLI_STUB), ('neighbor_advertiser', ASSISTANT_STUB),
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

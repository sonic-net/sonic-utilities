import os
import pytest
import re
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


FAST_REBOOT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'scripts', 'fast-reboot')

EXIT_NOT_SUPPORTED = 2


class TestFastRebootZmqGuard:
    """Cover check_swss_zmq_conflict."""

    def _run_guard(self, reboot_type, statuses, num_asic=1):
        """Run the guard against a stubbed sonic-db-cli. statuses maps a
        namespace ('' for global) to its swss_zmq status."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            status_file = os.path.join(tmp_dir, 'statuses')
            with open(status_file, 'w') as f:
                for namespace, status in statuses.items():
                    f.write('{}={}\n'.format(namespace, status))

            stub = os.path.join(tmp_dir, 'sonic-db-cli')
            with open(stub, 'w') as f:
                f.write(
                    '#!/bin/bash\n'
                    'ns=""\n'
                    'if [[ "$1" == "-n" ]]; then ns="$2"; fi\n'
                    'grep "^${ns}=" ' + status_file + ' | cut -d= -f2-\n'
                )
            os.chmod(stub, 0o700)

            asic_list = ' '.join(str(dev) for dev in range(num_asic))
            harness = (
                'EXIT_NOT_SUPPORTED={exit_code}\n'
                'REBOOT_TYPE={reboot_type}\n'
                'NUM_ASIC={num_asic}\n'
                'ASIC_LIST=({asic_list})\n'
                'function error() {{ echo "$@" >&2; }}\n'
                'eval "$(sed -n \'/^function check_swss_zmq_conflict/,/^}}$/p\' {script})"\n'
                'check_swss_zmq_conflict\n'
                'echo GUARD_PASSED\n'
            ).format(exit_code=EXIT_NOT_SUPPORTED,
                     reboot_type=reboot_type,
                     num_asic=num_asic,
                     asic_list=asic_list,
                     script=FAST_REBOOT)

            env = os.environ.copy()
            env['PATH'] = f"{tmp_dir}:{env.get('PATH', '')}"
            return subprocess.run(['bash', '-c', harness], env=env,
                                  capture_output=True, text=True)

    @pytest.mark.parametrize(
        'reboot_type', ['fast-reboot', 'warm-reboot', 'express-reboot'])
    def test_guard_refuses_when_zmq_enabled(self, reboot_type):
        res = self._run_guard(reboot_type, {'': 'enabled'})
        assert res.returncode == EXIT_NOT_SUPPORTED
        assert 'GUARD_PASSED' not in res.stdout
        assert 'swss_zmq is enabled' in res.stderr
        assert reboot_type in res.stderr

    @pytest.mark.parametrize('zmq_status', ['disabled', ''])
    def test_guard_allows_when_zmq_off(self, zmq_status):
        res = self._run_guard('warm-reboot', {'': zmq_status})
        assert res.returncode == 0
        assert 'GUARD_PASSED' in res.stdout

    def test_guard_runs_before_any_arming(self):
        """The guard must precede the dispatch that arms the restart flags."""
        with open(FAST_REBOOT) as f:
            lines = f.read().splitlines()

        # Ignore function bodies: a definition may precede its call site.
        top_level = []
        in_function = False
        for number, line in enumerate(lines):
            if not in_function and re.match(r'^(function\s+)?\w+\s*\(\)', line):
                in_function = True
            elif in_function and line == '}':
                in_function = False
            elif not in_function:
                top_level.append((number, line))

        guard = next(n for n, line in top_level
                     if line.strip() == 'check_swss_zmq_conflict')
        dispatch = next(n for n, line in top_level
                        if line.startswith('case "$REBOOT_TYPE"'))
        assert guard < dispatch

        arming = [n for n, line in top_level
                  if re.search(r'config warm_restart enable'
                               r'|enable_warm_restart'
                               r'|enable_fast_boot', line)]
        assert arming, 'expected to find the arming statements'
        assert guard < min(arming)

    @pytest.mark.parametrize('armed_namespace', ['asic0', 'asic3'])
    def test_guard_refuses_multi_asic_namespace(self, armed_namespace):
        """swss_zmq enabled in any ASIC namespace refuses the reboot."""
        statuses = {'': 'disabled'}
        statuses.update({'asic{}'.format(dev): 'disabled' for dev in range(4)})
        statuses[armed_namespace] = 'enabled'

        res = self._run_guard('warm-reboot', statuses, num_asic=4)
        assert res.returncode == EXIT_NOT_SUPPORTED
        assert 'GUARD_PASSED' not in res.stdout
        assert 'namespace {}'.format(armed_namespace) in res.stderr

    def test_guard_refuses_multi_asic_global_namespace(self):
        """The global namespace is armed, so it is checked."""
        statuses = {'': 'enabled'}
        statuses.update({'asic{}'.format(dev): 'disabled' for dev in range(4)})

        res = self._run_guard('warm-reboot', statuses, num_asic=4)
        assert res.returncode == EXIT_NOT_SUPPORTED
        assert 'swss_zmq is enabled.' in res.stderr

    def test_guard_allows_multi_asic_when_all_namespaces_clean(self):
        statuses = {'': 'disabled'}
        statuses.update({'asic{}'.format(dev): 'disabled' for dev in range(4)})

        res = self._run_guard('warm-reboot', statuses, num_asic=4)
        assert res.returncode == 0
        assert 'GUARD_PASSED' in res.stdout

    def test_guard_skips_asics_removed_from_asic_list(self):
        """An ASIC absent from ASIC_LIST is not armed, so it is not checked."""
        statuses = {'': 'disabled'}
        statuses.update({'asic{}'.format(dev): 'disabled' for dev in range(4)})
        statuses['asic3'] = 'enabled'

        # num_asic=3 yields ASIC_LIST=(0 1 2): asic3 is skipped.
        res = self._run_guard('warm-reboot', statuses, num_asic=3)
        assert res.returncode == 0
        assert 'GUARD_PASSED' in res.stdout

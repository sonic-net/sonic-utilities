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
            env = os.environ.copy()
            env['PATH'] = f"{tmp_dir}:{env.get('PATH', '')}"
            res = subprocess.run([fast_reboot, '-h'], env=env)
        assert res.returncode == 0

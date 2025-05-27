import os
import tempfile
import shutil
import subprocess

class TestFastReboot:
    def test_fast_reboot_without_login_shell(self):
        test_path = os.path.dirname(os.path.abspath(__file__))
        fast_reboot = os.path.join(test_path, '..', 'scripts', 'fast-reboot')

        with tempfile.TemporaryDirectory() as tmp_dir:
            whoami = os.path.join(tmp_dir, 'whoami')
            with open(whoami, 'w') as f:
                f.write('echo root')
                os.chmod(whoami, 0o700)

            shutil.copy('/bin/false', os.path.join(tmp_dir, 'logname'))
            shutil.copy('/bin/true', os.path.join(tmp_dir, 'sonic-cfggen'))

            env = os.environ.copy()
            env['PATH'] = f"{tmp_dir}:{env.get('PATH', '')}"

            res = subprocess.run([fast_reboot, '-h'], env=env)

        assert res.returncode == 0

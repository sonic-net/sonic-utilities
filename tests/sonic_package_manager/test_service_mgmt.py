"""Exercise the shipped service wrapper without SONiC databases or Docker."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import jinja2


TEMPLATES = Path(__file__).resolve().parents[2] / 'sonic-utilities-data' / 'templates'


class ServiceManagementTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.runtime = self.root / 'runtime'
        self.runtime.mkdir()
        self.calls = self.root / 'calls'
        self.calls.touch()
        self.env = dict(os.environ, RUNTIME_DIRECTORY=str(self.runtime), CALLS=str(self.calls),
                        SERVICE_RESULT='success', PATH=str(self.root) + ':' + os.environ['PATH'])
        self.env.pop('DEV', None)
        self.env.pop('STOP_POST_FORCE', None)
        self.script('controller', '''printf 'controller:%s\\n' "$*" >> "$CALLS"
case "$1" in
    start) exit "${START_EXIT:-0}" ;;
    stop) exit "${STOP_EXIT:-0}" ;;
    is_running) exit "${RUNNING_EXIT:-0}" ;;
esac
''')
        self.script('logger', 'exit 0\n')
        self.script('docker', 'printf "docker:%s\\n" "$*" >> "$CALLS"\n')
        self.script('sonic-db-cli', '''printf 'db:%s\\n' "$*" >> "$CALLS"
if [[ "$BOOT" == warm && "$*" == *WARM_RESTART* ]] || [[ "$BOOT" == fast && "$*" == *FAST_RESTART* ]]; then
    echo true
else
    echo false
fi
''')
        manifest = {'service': {'name': 'test', 'dependent': [], 'pre-shutdown-action': 'shutdown'}}
        rendered = jinja2.Template((TEMPLATES / 'service_mgmt.sh.j2').read_text()).render(
            manifest=manifest, multi_instance_services=[])
        rendered = rendered.replace('/usr/bin/${SERVICE}.sh', str(self.root / 'controller'))
        rendered = rendered.replace('/usr/bin/logger', str(self.root / 'logger'))
        rendered = rendered.replace('TMPDIR="/tmp/"', f'TMPDIR="{self.root}/"')
        self.wrapper = self.script('wrapper', rendered.removeprefix('#!/bin/bash\n'))

    def script(self, name, body):
        path = self.root / name
        path.write_text('#!/bin/bash\n' + body)
        path.chmod(0o755)
        return path

    def run_operation(self, operation, instance=''):
        return subprocess.run([str(self.wrapper), operation, instance], env=self.env,
                              capture_output=True, text=True, timeout=10)

    def operations(self):
        return self.calls.read_text().splitlines()

    def test_cancelled_start_cleans_up_even_when_result_is_success(self):
        self.run_operation('start')
        self.calls.write_text('')
        result = self.run_operation('stop_post')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('docker:exec -t test shutdown', self.operations())
        self.assertIn('controller:stop', self.operations())
        self.assertFalse(any('is_running' in call for call in self.operations()))

    def test_normal_stop_is_not_replayed_after_failure(self):
        self.run_operation('start')
        self.run_operation('stop')
        before = self.operations()
        self.env['SERVICE_RESULT'] = 'exit-code'
        self.run_operation('stop_post')
        self.assertEqual(self.operations(), before)

    def test_condition_skip_does_not_run_shutdown(self):
        self.env['SERVICE_RESULT'] = 'exec-condition'
        self.run_operation('stop_post')
        self.assertEqual(self.operations(), [])

    def test_cleanup_preserves_warm_and_fast_shutdown(self):
        for boot in ('warm', 'fast'):
            with self.subTest(boot=boot):
                for path in self.runtime.iterdir():
                    path.unlink()
                self.env['BOOT'] = boot
                self.run_operation('start')
                self.calls.write_text('')
                self.run_operation('stop_post')
                self.assertIn('docker:kill test', self.operations())
                self.assertIn('docker:exec -t test shutdown', self.operations())
                self.assertNotIn('controller:stop', self.operations())

    def test_instance_cleanup_reads_its_database_namespace(self):
        self.run_operation('start', '1')
        self.calls.write_text('')
        self.run_operation('stop_post', '1')
        self.assertIn('controller:stop 1', self.operations())
        database_calls = [call for call in self.operations() if call.startswith('db:')]
        self.assertTrue(database_calls)
        self.assertTrue(all(call.startswith('db:-n asic1 ') for call in database_calls))

    def test_cleanup_failure_does_not_skip_later_systemd_hooks(self):
        self.run_operation('start')
        self.env['STOP_EXIT'] = '1'
        result = self.run_operation('stop_post')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('controller:stop', self.operations())

    def test_start_fails_before_starting_container_if_marker_cannot_be_written(self):
        self.env['RUNTIME_DIRECTORY'] = str(self.root / 'missing')
        result = self.run_operation('start')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('controller:start', self.operations())

    def test_manual_start_and_stop_do_not_require_systemd(self):
        self.env.pop('RUNTIME_DIRECTORY')
        self.assertEqual(self.run_operation('start').returncode, 0)
        self.assertEqual(self.run_operation('stop').returncode, 0)

    def test_generated_units_have_private_runtime_directories(self):
        template = jinja2.Template((TEMPLATES / 'sonic.service.j2').read_text())
        for kind in ('', 'simple', 'notify', 'exec', 'dbus'):
            for multi in (False, True):
                with self.subTest(kind=kind, multi=multi):
                    rendered = template.render(manifest={'service': {'name': 'test', 'type': kind}},
                                               multi_instance=multi)
                    self.assertIn('RuntimeDirectory=sonic-service-%n\n', rendered)
                    command = 'ExecStopPost=/usr/local/bin/test.sh stop_post' + (' %i' if multi else '')
                    self.assertIn(command, rendered.splitlines())
                    self.assertNotIn('STOP_POST_FORCE', rendered)


if __name__ == '__main__':
    unittest.main()

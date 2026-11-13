"""Install real wheels in scratch prefix and execute isolated installed Python.

No checkout/runfiles on child sys.path. No SONiC stubs, DB/service execution,
network, or host installs. This is intentionally a bounded dependency subset.
"""
import os
import stat
import zipfile
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from installer import install
from installer.destinations import SchemeDictionaryDestination
from installer.sources import WheelFile

WHEELS = [Path(p).resolve() for p in sys.argv[1:]]
del sys.argv[1:]

CHILD = r'''
import importlib, importlib.metadata, importlib.util, os, pathlib, sys, unittest
site = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(site))
from click.testing import CliRunner
import click
from connect.main import connect
from utilities_common.intf_filter import parse_interface_in_filter, interface_in_filter

class InstalledRuntime(unittest.TestCase):
    def test_imports_are_installed(self):
        for name in ['connect.main', 'utilities_common.intf_filter', 'utilities_common.constants', 'config.plugins', 'show.plugins', 'clear.plugins.auto']:
            module = importlib.import_module(name)
            self.assertTrue(pathlib.Path(module.__file__).resolve().is_relative_to(site), module.__file__)
        self.assertEqual(importlib.metadata.version('click'), '8.1.8')
        self.assertEqual(importlib.metadata.version('sonic-utilities'), '1.2')

    def test_console_entry_point(self):
        dist = importlib.metadata.distribution('sonic-utilities')
        ep = next(ep for ep in dist.entry_points if ep.name == 'connect')
        self.assertIs(ep.load(), connect)
        for args in [['--help'], ['line', '--help'], ['device', '--help'], ['li', '--help']]:
            result = CliRunner().invoke(connect, args)
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn('Usage:', result.output)
        result = CliRunner().invoke(connect, ['not-a-command'])
        self.assertEqual(result.exit_code, 2)
        self.assertIn('No such command', result.output)

    def test_installed_plugin_discovery(self):
        import pkgutil
        for command in ['config', 'show', 'clear']:
            auto = importlib.util.find_spec(command + '.plugins.auto')
            self.assertTrue(pathlib.Path(auto.origin).resolve().is_relative_to(site))
        for command in ['config', 'show']:
            plugins = importlib.import_module(command + '.plugins')
            names = {m.name for m in pkgutil.iter_modules(plugins.__path__)}
            self.assertTrue({'pbh', 'sonic-hash', 'sonic-trimming'} <= names, names)
        self.assertTrue((site / 'show/aliases.ini').is_file())

    def test_real_interface_filter(self):
        self.assertEqual(parse_interface_in_filter('Ethernet0-2,PortChannel4,Ethernet-BP0-1'), ['Ethernet0', 'Ethernet1', 'Ethernet2', 'PortChannel4', 'Ethernet-BP0', 'Ethernet-BP1'])
        self.assertEqual(parse_interface_in_filter('Ethernet-Rec0'), [])
        self.assertTrue(interface_in_filter('Ethernet1', 'Ethernet0-2'))
        self.assertFalse(interface_in_filter('Ethernet3', 'Ethernet0-2'))
        for value in ['Ethernet3-0', 'Ethernet0-ff', 'foo0-1']:
            with self.assertRaises(ValueError):
                parse_interface_in_filter(value)

unittest.main(argv=[sys.argv[0]], verbosity=2)
'''

class WheelInstallation(unittest.TestCase):
    def test_installed_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp)
            scheme = {name: str(prefix / path) for name, path in {'purelib':'site', 'platlib':'site', 'headers':'include', 'scripts':'bin', 'data':'.'}.items()}
            # Short stable path avoids Linux's shebang-length limit in deep Bazel sandboxes.
            interpreter = prefix / 'python-selected'
            interpreter.symlink_to(sys.executable)
            destination = SchemeDictionaryDestination(scheme, interpreter=str(interpreter), script_kind='posix', bytecode_optimization_levels=())
            for path in WHEELS:
                with WheelFile.open(path) as source:
                    install(source, destination, additional_metadata={})
            # Inspect every installed utility member, not only selected CLI files.
            with zipfile.ZipFile(WHEELS[0]) as wheel:
                for name in wheel.namelist():
                    if '.data/scripts/' in name:
                        installed = prefix / 'bin' / name.split('.data/scripts/', 1)[1]
                        expected_mode = 0o755
                        header = wheel.read(name).split(b'\n', 1)[0]
                        actual = installed.read_bytes().split(b'\n', 1)[0]
                        if header.startswith(b'#!python'):
                            self.assertEqual(actual, b'#!' + os.fsencode(interpreter), name)
                        else:
                            self.assertEqual(actual, header, name)  # shell/awk unchanged
                    elif '.data/data/' in name:
                        installed = prefix / name.split('.data/data/', 1)[1]
                        expected_mode = 0o755
                    else:
                        installed = prefix / 'site' / name
                        expected_mode = 0o644
                    self.assertEqual(stat.S_IMODE(installed.stat().st_mode), expected_mode, name)
            # Inert probes use actual installed shebangs; no service/script body runs.
            # A hostile PATH cannot select python/python3 for normalized scripts.
            path = prefix / 'hostile-path'
            path.mkdir()
            for command in ('python', 'python3'):
                trap = path / command
                trap.write_text('#!/bin/sh\nexit 97\n')
                trap.chmod(0o755)
            for name in ('centralize_database', 'update_json.py', 'vnet_route_check.py', 'aclshow'):
                probe = prefix / ('probe-' + name)
                header = (prefix / 'bin' / name).read_bytes().split(b'\n', 1)[0]
                probe.write_bytes(header + b'\nimport sys; print(sys.executable)\n')
                probe.chmod(0o755)
                result = subprocess.run([str(probe)], env={'PATH': str(path)}, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(Path(result.stdout.strip()).resolve(), Path(sys.executable).resolve())
            (prefix / 'check.py').write_text(CHILD)
            env = {'PATH':'/usr/bin:/bin', 'HOME':tmp, 'PYTHONDONTWRITEBYTECODE':'1', 'LC_ALL':'C.UTF-8'}
            result = subprocess.run([sys.executable, '-I', str(prefix / 'check.py'), str(prefix / 'site')], cwd=tmp, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            print(result.stdout)
            self.assertEqual(result.returncode, 0)
            # Execute the actual installer-generated console script, not only
            # an entrypoint object; installed-only PYTHONPATH, never runfiles.
            env['PYTHONPATH'] = str(prefix / 'site')
            result = subprocess.run([str(prefix / 'bin/connect'), '--help'], cwd=tmp, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            print(result.stdout)
            self.assertEqual(result.returncode, 0)
            self.assertIn("SONiC command line", result.stdout)
            for name in ['config', 'show', 'sonic-clear', 'aclshow', 'sonic-cli-gen']:
                path = prefix / 'bin' / name
                self.assertTrue(path.is_file(), str(path))
                self.assertTrue(os.access(path, os.X_OK), str(path))
            self.assertTrue((prefix / 'bin/vtFA_RTK_5766_v2').is_file())

if __name__ == '__main__':
    unittest.main()

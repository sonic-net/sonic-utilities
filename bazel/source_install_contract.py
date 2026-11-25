"""Direct installation contract derived from the unchanged setup.py."""

import ast
import base64
import configparser
import csv
import email
import hashlib
import io
import json
from pathlib import Path
import posixpath
import re
import subprocess
import sys
import tarfile
import tempfile
import unittest
from installer import install
from installer.destinations import SchemeDictionaryDestination
from installer.sources import WheelFile

RUNTIME, SETUP, CLICK, METADATA = map(Path, sys.argv[1:])
sys.argv = sys.argv[:1]
ROOT = SETUP.parent
SOURCE = ast.parse(SETUP.read_text())
CALL = next(n for n in ast.walk(SOURCE) if isinstance(n, ast.Call) and getattr(n.func, 'id', '') == 'setup')
KW = {k.arg: k.value for k in CALL.keywords}
SITE = 'usr/local/lib/python3.13/dist-packages/'


class SourceInstallation(unittest.TestCase):
    def test_payload_metadata_and_record(self):
        with tarfile.open(RUNTIME, 'r:') as archive:
            actual = {
                m.name.removeprefix('./'): (m, archive.extractfile(m).read()) for m in archive if m.isfile()
            }
        expected = {}
        for package in ast.literal_eval(KW['packages']):
            for path in (ROOT / package.replace('.', '/')).glob('*.py'):
                expected[SITE + str(path.relative_to(ROOT))] = (path, False)
        for package, patterns in ast.literal_eval(KW['package_data']).items():
            for pattern in patterns:
                for path in (ROOT / package.replace('.', '/')).glob(pattern):
                    if path.is_file():
                        expected[SITE + str(path.relative_to(ROOT))] = (path, False)
        for name in ast.literal_eval(KW['scripts']):
            expected['usr/local/bin/' + Path(name).name] = (ROOT / name, True)
        for target, names in ast.literal_eval(KW['data_files']):
            for name in names:
                expected['usr/local/' + target + '/' + Path(name).name] = (ROOT / name, True)
        console_names = {
            'usr/local/bin/' + value.split(' = ', 1)[0]
            for value in ast.literal_eval(KW['entry_points'])['console_scripts']
        }
        for name in console_names:
            self.assertEqual(actual[name][0].mode, 0o755)
            self.assertEqual(actual[name][1].splitlines()[0], b'#!/usr/bin/python3')
        payload = {name for name in actual if '.dist-info/' not in name and name not in console_names}
        self.assertEqual(set(expected), payload)
        # The source runtime preserves Make's tests selection; the independent
        # existing runtime wheel intentionally has a different selection.
        self.assertTrue(any(name.startswith(SITE + 'tests/') for name in payload))
        for name, (path, executable) in expected.items():
            raw = path.read_bytes()
            if name.startswith('usr/local/bin/'):
                header, separator, body = raw.partition(b'\n')
                if re.fullmatch(br'#!.*python[0-9.]*([ \t].*)?', header):
                    raw = b'#!/usr/bin/python3' + separator + body
            member, installed = actual[name]
            self.assertEqual(installed, raw, name)
            self.assertEqual(
                (member.mode, member.uid, member.gid), (0o755 if executable else 0o644, 0, 0), name
            )
        dist = SITE + 'sonic_utilities-1.2.dist-info/'
        metadata = email.message_from_bytes(actual[dist + 'METADATA'][1])
        for field, key in [
            ('Name', 'name'),
            ('Version', 'version'),
            ('Summary', 'description'),
            ('Author', 'author'),
            ('Author-email', 'author_email'),
            ('Maintainer', 'maintainer'),
            ('Maintainer-email', 'maintainer_email'),
            ('Home-page', 'url'),
            ('License', 'license'),
            ('Keywords', 'keywords'),
        ]:
            self.assertEqual(metadata[field], ast.literal_eval(KW[key]), field)
        sonic = next(
            ast.literal_eval(n.value)
            for n in SOURCE.body
            if isinstance(n, ast.Assign)
            and any(getattr(t, 'id', '') == 'sonic_dependencies' for t in n.targets)
        )
        requirements = ast.literal_eval(KW['install_requires'].left) + sonic
        self.assertCountEqual(
            [v for v in metadata.get_all('Requires-Dist') if 'extra ==' not in v], requirements
        )
        for extra, requirements in ast.literal_eval(KW['extras_require']).items():
            for requirement in requirements:
                self.assertIn(f"{requirement}; extra == '{extra}'", metadata.get_all('Requires-Dist'))
        self.assertCountEqual(metadata.get_all('Classifier'), ast.literal_eval(KW['classifiers']))
        entries = configparser.ConfigParser()
        entries.read_string(actual[dist + 'entry_points.txt'][1].decode())
        self.assertEqual(
            dict(entries['console_scripts']),
            dict(v.split(' = ') for v in ast.literal_eval(KW['entry_points'])['console_scripts']),
        )
        self.assertEqual(actual[dist + 'licenses/LICENSE'][1], (ROOT / 'LICENSE').read_bytes())
        runtime_metadata = json.loads(METADATA.read_text())
        self.assertEqual(runtime_metadata['distribution'], ast.literal_eval(KW['name']))
        self.assertEqual(runtime_metadata['version'], ast.literal_eval(KW['version']))
        self.assertCountEqual(runtime_metadata['requires_dist'], metadata.get_all('Requires-Dist'))
        self.assertEqual(
            runtime_metadata['requires_python'],
            ast.literal_eval(KW['python_requires']) if 'python_requires' in KW else '',
        )
        self.assertEqual(runtime_metadata['entry_points'], ast.literal_eval(KW['entry_points']))
        self.assertCountEqual(runtime_metadata['extras'], ast.literal_eval(KW['extras_require']))
        record_path = dist + 'RECORD'
        records = list(csv.reader(io.StringIO(actual[record_path][1].decode())))
        self.assertEqual(len(records), len(actual))
        seen = set()
        for name, digest, size in records:
            self.assertTrue(name)
            self.assertFalse(posixpath.isabs(name))
            path = posixpath.normpath(SITE + name)
            self.assertNotIn(path, seen)
            self.assertIn(path, actual)
            seen.add(path)
            if path == record_path:
                self.assertEqual((digest, size), ('', ''))
            else:
                self.assertTrue(digest, path)
                self.assertTrue(size, path)
                raw = actual[path][1]
                algorithm, encoded = digest.split('=', 1)
                self.assertEqual(
                    encoded,
                    base64.urlsafe_b64encode(hashlib.new(algorithm, raw).digest()).rstrip(b'=').decode(),
                )
                self.assertEqual(int(size), len(raw))
        self.assertEqual(seen, set(actual))

    def test_installed_cli_and_resource(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp)
            with tarfile.open(RUNTIME, 'r:') as archive:
                for member in archive:
                    archive.extract(member, prefix, filter='data')
            site = prefix / SITE
            scheme = {
                name: str(site if name in ('purelib', 'platlib') else prefix / name)
                for name in ('purelib', 'platlib', 'headers', 'scripts', 'data')
            }
            with WheelFile.open(CLICK) as wheel:
                install(
                    wheel,
                    SchemeDictionaryDestination(
                        scheme, interpreter=sys.executable, script_kind='posix', bytecode_optimization_levels=()
                    ),
                    {},
                )
            code = '''import importlib,importlib.metadata,pathlib,sys
site=pathlib.Path(sys.argv[1]);sys.path.insert(0,str(site))
from click.testing import CliRunner
from connect.main import connect
from utilities_common.intf_filter import parse_interface_in_filter
assert pathlib.Path(importlib.import_module('connect.main').__file__).is_relative_to(site)
assert importlib.metadata.version('sonic-utilities')=='1.2'
for args in [['--help'],['line','--help'],['device','--help'],['li','--help']]:
 result=CliRunner().invoke(connect,args);assert result.exit_code==0,result.output;assert 'Usage:' in result.output
result=CliRunner().invoke(connect,['not-a-command']);assert result.exit_code==2
assert parse_interface_in_filter('Ethernet0-2')==['Ethernet0','Ethernet1','Ethernet2']
assert (site/'show/aliases.ini').is_file()
for group in ['config','show','clear']:
 assert (site/group/'plugins/auto/__init__.py').is_file()
print('source-installed CLI/resource PASS')
'''
            script = prefix / 'check.py'
            script.write_text(code)
            result = subprocess.run(
                [sys.executable, '-I', str(script), str(site)],
                cwd=tmp,
                env={'PATH': '/usr/bin:/bin', 'HOME': tmp, 'PYTHONDONTWRITEBYTECODE': '1'},
                capture_output=True,
                text=True,
            )
            print(result.stdout)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()

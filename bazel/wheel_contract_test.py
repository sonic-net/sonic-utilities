"""Independent setup.py -> wheel contract test (does not execute setup.py)."""
import ast
import base64
import configparser
import csv
import email
import hashlib
import io
import json
import re
import stat
from pathlib import Path
import sys
import unittest
import zipfile

wheel, setup, declaration = map(Path, sys.argv[1:4])
del sys.argv[1:4]
root = setup.parent
source = ast.parse(setup.read_text())
call = next(n for n in ast.walk(source) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'setup')
kw = {k.arg: k.value for k in call.keywords}
sonic = next(ast.literal_eval(n.value) for n in source.body if isinstance(n, ast.Assign) and any(isinstance(x, ast.Name) and x.id == 'sonic_dependencies' for x in n.targets))
contract = {k: ast.literal_eval(kw[k]) for k in ['packages', 'package_data', 'scripts', 'data_files', 'entry_points']}
contract['requires'] = ast.literal_eval(kw['install_requires'].left) + sonic
contract['extra_requires'] = ast.literal_eval(kw['extras_require'])

class WheelContract(unittest.TestCase):
    def test_setup_declaration_matches(self):
        self.assertEqual(json.loads(json.dumps(contract)), json.loads(declaration.read_text()))

    def test_payload_and_metadata(self):
        with zipfile.ZipFile(wheel) as z:
            names = set(z.namelist())
            di = 'sonic_utilities-1.2.dist-info/'
            data = 'sonic_utilities-1.2.data/'
            expected = {}
            for package in contract['packages']:
                for p in (root / package.replace('.', '/')).glob('*.py'):
                    expected[str(p.relative_to(root))] = p
            for package, patterns in contract['package_data'].items():
                for pattern in patterns:
                    for p in (root / package.replace('.', '/')).glob(pattern):
                        if p.is_file():
                            expected[str(p.relative_to(root))] = p
            for script in contract['scripts']:
                expected[data + 'scripts/' + Path(script).name] = root / script
            for target, paths in contract['data_files']:
                for p in paths:
                    expected[data + 'data/' + target + '/' + Path(p).name] = root / p
            self.assertEqual(set(expected), {n for n in names if not n.startswith(di)})
            for name, path in expected.items():
                payload = path.read_bytes()
                if name.startswith(data + 'scripts/'):
                    first, separator, rest = payload.partition(b'\n')
                    # Independent expectation for the setuptools-style transform.
                    if re.fullmatch(br'#!.*python[0-9.]*([ \t].*)?', first):
                        suffix = re.search(br'python[0-9.]*([ \t].*)?$', first).group(1) or b''
                        payload = b'#!python' + suffix + separator + rest
                self.assertEqual(z.read(name), payload, name)
            self.assertEqual(len(expected), 1082)
            self.assertEqual(len([n for n in expected if n.startswith('tests/')]), 709)
            self.assertEqual(len(names - set(expected)), 5)
            for info in z.infolist():
                executable = info.filename.startswith(data + 'scripts/') or info.filename == data + 'data/bin/vtFA_RTK_5766_v2'
                self.assertEqual(stat.S_IMODE(info.external_attr >> 16), 0o755 if executable else 0o644, info.filename)
            metadata = email.message_from_bytes(z.read(di + 'METADATA'))
            self.assertEqual(metadata['Version'], '1.2')
            for field, setup_field in [('Maintainer', 'maintainer'), ('Maintainer-email', 'maintainer_email'), ('Keywords', 'keywords'), ('License', 'license'), ('Summary', 'description'), ('Author', 'author'), ('Author-email', 'author_email'), ('Home-page', 'url')]:
                self.assertEqual(metadata[field], ast.literal_eval(kw[setup_field]), field)
            self.assertEqual(metadata['Metadata-Version'], '2.4')
            self.assertEqual(metadata.get_all('License-File'), ['LICENSE'])
            self.assertEqual(z.read(di + 'licenses/LICENSE'), (root / 'LICENSE').read_bytes())
            actual = metadata.get_all('Requires-Dist')
            ordinary = [x for x in actual if 'extra ==' not in x]
            self.assertCountEqual(contract['requires'], ordinary)
            for extra, reqs in contract['extra_requires'].items():
                for req in reqs:
                    self.assertIn(f"{req}; extra == '{extra}'", actual)
            parser = configparser.ConfigParser()
            parser.read_string(z.read(di + 'entry_points.txt').decode())
            self.assertEqual(dict(parser['console_scripts']), dict(x.split(' = ') for x in contract['entry_points']['console_scripts']))
            self.assertIn('Tag: py3-none-linux_x86_64', z.read(di + 'WHEEL').decode())
            self.assertEqual(z.read(data + 'data/bin/vtFA_RTK_5766_v2')[:4], b'\x7fELF')
            for group in ('config', 'show', 'clear'):
                self.assertIn(group + '/plugins/auto/__init__.py', names)
            records = list(csv.reader(io.StringIO(z.read(di + 'RECORD').decode())))
            self.assertEqual({row[0] for row in records}, names)
            for name, digest, size in records:
                if digest:
                    payload = z.read(name)
                    self.assertEqual(digest, 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b'=').decode())
                    self.assertEqual(int(size), len(payload))
            print(f'Exact payload verified: {len(expected)} files, {len(contract["packages"])} packages, {len(contract["scripts"])} scripts, {len(parser["console_scripts"])} console entries')

if __name__ == '__main__':
    unittest.main()

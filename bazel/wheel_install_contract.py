"""Preserve legacy executable install modes and setuptools Python shebangs.

This is not a wheel producer: native py_wheel owns payload selection and all
metadata. Only script first lines, executable ZIP bits and RECORD are adjusted.
"""
import base64
import csv
import hashlib
import io
import re
import stat
import sys
import zipfile

# Match setuptools build_scripts' Python shebang recognition, not shell scripts.
PYTHON_SHEBANG = re.compile(br'^#!.*python[0-9.]*([ \t].*)?$')


def adjust(source, destination):
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(destination, 'w') as result:
        records = []
        record_info = None
        for info in original.infolist():
            if info.filename.endswith('.dist-info/RECORD'):
                record_info = info
                continue
            payload = original.read(info)
            script = '.data/scripts/' in info.filename
            executable = script or info.filename.endswith('.data/data/bin/vtFA_RTK_5766_v2')
            if script:
                first, separator, rest = payload.partition(b'\n')
                match = PYTHON_SHEBANG.fullmatch(first)
                if match:
                    payload = b'#!python' + (match.group(1) or b'') + separator + rest
            info.external_attr = (stat.S_IFREG | (0o755 if executable else 0o644)) << 16
            result.writestr(info, payload)
            digest = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b'=').decode()
            records.append((info.filename, 'sha256=' + digest, str(len(payload))))
        if record_info is None:
            raise ValueError('native wheel is missing RECORD')
        records.append((record_info.filename, '', ''))
        record = io.StringIO(newline='')
        csv.writer(record, lineterminator='\n').writerows(records)
        record_info.external_attr = (stat.S_IFREG | 0o644) << 16
        result.writestr(record_info, record.getvalue().encode())


if __name__ == '__main__':
    adjust(*sys.argv[1:])

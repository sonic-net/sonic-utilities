"""Run the real dump helper with capture functions instead of collecting a switch."""
import os
from pathlib import Path
import re
import shlex
import subprocess

import pytest


@pytest.mark.parametrize('database,host_namespace,transport', [
    ('CONFIG_DB', False, 'unix_socket'),
    ('STATE_DB', True, 'unix_socket'),
    ('APPL_DB', False, 'unix_socket'),
    ('CHASSIS_APP_DB', True, 'tcp'),
    ('CHASSIS_STATE_DB', True, 'tcp'),
])
def test_dump_keeps_local_sockets_and_chassis_tcp(tmp_path, database, host_namespace, transport):
    path = Path(__file__).resolve().parents[1] / 'scripts/generate_dump'
    function = re.search(r'(?ms)^save_redis\(\) \{.*?^\}', path.read_text()).group()
    capture = tmp_path / 'arguments'
    program = function + '''
handle_error() { return "$1"; }
save_cmd() { printf '%s\\0' host "$@" > "$CAPTURE"; }
save_cmd_all_ns() { printf '%s\\0' namespaces "$@" > "$CAPTURE"; }
save_redis "$DATABASE" dump "$HOST_NAMESPACE" redact_config
'''
    env = dict(os.environ, CAPTURE=str(capture), DATABASE=database,
               HOST_NAMESPACE='true' if host_namespace else 'false')
    subprocess.run(['bash', '-eu', '-c', program], env=env, check=True,
                   capture_output=True, text=True)
    values = capture.read_bytes().split(b'\0')[:-1]
    assert values[0].decode() == ('host' if host_namespace else 'namespaces')
    assert shlex.split(values[1].decode()) == [
        'sonic-db-dump', '-t', transport, '-n', database, '-y']
    assert values[2:] == [b'dump.json', b'false', b'redact_config']

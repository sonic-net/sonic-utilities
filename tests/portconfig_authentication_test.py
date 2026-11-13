from pathlib import Path
import sys
from unittest.mock import MagicMock

import pytest

from .utils import load_source


portconfig = load_source('portconfig_authentication', str(
    Path(__file__).resolve().parents[1] / 'scripts' / 'portconfig'))


@pytest.mark.parametrize('namespace', [None, 'asic0'])
@pytest.mark.parametrize('reader_socket', [False, True])
@pytest.mark.parametrize('write', [False, True])
def test_only_write_commands_request_writer_credentials(monkeypatch, capsys, namespace, reader_socket, write):
    entries = {'Ethernet0': {'speed': '1000'}}
    connection = MagicMock()
    connection.get_table.side_effect = lambda table: entries if table == 'PORT' else {}
    state = MagicMock()
    state.get_all.return_value = {}
    writes = []

    def connect(**options):
        authenticated = options.get('authenticate', False)
        if not write and authenticated:
            raise PermissionError('Reader cannot access writer credentials')

        def modify(table, key, fields):
            if not authenticated:
                raise PermissionError('Writer authentication is required')
            entries[key].update(fields)
            writes.append((table, key, fields))

        connection.mod_entry.side_effect = modify
        return connection

    monkeypatch.setattr(portconfig, 'ConfigDBConnector', connect)
    monkeypatch.setattr(portconfig, 'SonicV2Connector', lambda **options: state)
    monkeypatch.setattr(portconfig, 'use_local_redis_socket', lambda *args: reader_socket)
    monkeypatch.setattr(portconfig, 'load_db_config', lambda: None)
    arguments = ['portconfig', '-p', 'Ethernet0', *(['-m', '9100'] if write else ['-l'])]
    if namespace is not None:
        arguments += ['-n', namespace]
    monkeypatch.setattr(sys, 'argv', arguments)

    portconfig.main()

    if write:
        assert writes == [('PORT', 'Ethernet0', {'mtu': 9100})]
    else:
        assert not writes
        assert '1000' in capsys.readouterr().out

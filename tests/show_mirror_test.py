# flake8: noqa: E501
import os
import sys
import re
from unittest import mock

import pytest
from swsscommon.swsscommon import ConfigDBConnector
import show.main as show_cli
from utilities_common import port_mirror
from .mock_tables import dbconnector
from swsscommon.swsscommon import SonicV2Connector
from click.testing import CliRunner
from utilities_common.db import Db

import acl_loader.main as acl_loader_show
from acl_loader import *
from acl_loader.main import *  # noqa: F403, F401

class TestShowMirror(object):
    def test_mirror_show(self):
        runner = CliRunner()
        aclloader = AclLoader()
        aclloader.configdb.set_entry("MIRROR_SESSION", "session1", {"direction": "BOTH", "dst_port": "Ethernet30", "src_port": "Ethernet40", "type": "SPAN"})
        aclloader.configdb.set_entry("MIRROR_SESSION", "session2", {"direction": "BOTH", "dst_port": "Ethernet7", "src_port": "Ethernet8", "type": "SPAN"})
        aclloader.configdb.set_entry("MIRROR_SESSION", "session11", {"direction": "RX", "dst_port": "Ethernet9", "src_port": "Ethernet10", "type": "SPAN"})
        aclloader.configdb.set_entry("MIRROR_SESSION", "session15", {"direction": "TX", "dst_port": "Ethernet2", "src_port": "Ethernet3", "type": "SPAN"})
        aclloader.read_sessions_info()
        context = {
            "acl_loader": aclloader
        }
        expected_output = """\
ERSPAN Sessions
Name              Status    SRC IP    DST IP    GRE    DSCP    TTL    Queue    Policer    Monitor Port    SRC Port               Direction
----------------  --------  --------  --------  -----  ------  -----  -------  ---------  --------------  ---------------------  -----------
test_session_db1  active                                                                                   Ethernet40,Ethernet48  rx

SPAN Sessions
Name       Status    DST Port    SRC Port    Direction    Queue    Policer
---------  --------  ----------  ----------  -----------  -------  ---------
session1   active     Ethernet30  Ethernet40  both
session2   active     Ethernet7   Ethernet8   both
session11  active     Ethernet9   Ethernet10  rx
session15  active     Ethernet2   Ethernet3   tx
"""
        result = runner.invoke(acl_loader_show.cli.commands['show'].commands['session'], [], obj=context)
        assert result.exit_code == 0
        print (result.output)
        #The state of mirror_session depends on the state_db table entry. This case does not care about the state and is uniformly set to active.
        result_output = result.output.replace('error', 'active')
        result_output = result_output.replace('inactive', 'active')
        assert result_output == expected_output

@pytest.fixture
def sampled_show_db(monkeypatch, tmp_path):
    """Use the existing mock Redis connector with a private, empty CONFIG_DB."""
    fixture = tmp_path / 'sampled_show_config_db.json'
    fixture.write_text('{}')
    monkeypatch.setitem(dbconnector.dedicated_dbs, 'CONFIG_DB', str(fixture.with_suffix('')))

    def create(entries=None):
        database = ConfigDBConnector()
        database.connect()
        for key, value in (entries or {}).items():
            database.set_entry('PORT_MIRROR_SAMPLE', key, value)
        return database

    return create


def assert_sampled_show_output(output, headers, rows):
    """Check every displayed column and row without depending on padding widths."""
    lines = output.strip().splitlines()
    assert lines[0] == 'Sampled ERSPAN Bindings'
    assert re.split(r'\s{2,}', lines[1].strip()) == headers
    assert re.fullmatch(r'[- ]+', lines[2])
    assert [re.split(r'\s{2,}', line.strip()) for line in lines[3:]] == rows


def test_show_sample_bindings(sampled_show_db, monkeypatch):
    database = sampled_show_db({
        ('Ethernet10', 'rx'): {'mirror_session': 'export1', 'sample_rate': '1000'},
        ('Ethernet2', 'tx'): {'mirror_session': 'export2', 'sample_rate': '2',
                              'truncate_size': '128', 'admin_state': 'up'},
        ('PortChannel10', 'rx'): {'mirror_session': 'export3', 'sample_rate': '5000',
                                  'truncate_size': '256', 'admin_state': 'down'},
    })
    before = database.get_table('PORT_MIRROR_SAMPLE')
    monkeypatch.setattr(port_mirror, 'config_databases', lambda: {'': database})
    result = CliRunner().invoke(show_cli.cli.commands['mirror_session'], ['sample'])
    assert result.exit_code == 0, result.output
    assert_sampled_show_output(result.output,
                              ['Source Port', 'Direction', 'Mirror Session', 'Admin State',
                               'Sample Rate', 'Truncate Size'], [
                                  ['Ethernet2', 'tx', 'export2', 'up', '2', '128'],
                                  ['Ethernet10', 'rx', 'export1', 'down', '1000', 'Disabled'],
                                  ['PortChannel10', 'rx', 'export3', 'down', '5000', '256'],
                              ])
    assert database.get_table('PORT_MIRROR_SAMPLE') == before


def test_show_empty_sample_bindings(sampled_show_db, monkeypatch):
    database = sampled_show_db()
    monkeypatch.setattr(port_mirror, 'config_databases', lambda: {'': database})
    result = CliRunner().invoke(show_cli.cli.commands['mirror_session'], ['sample'])
    assert result.exit_code == 0, result.output
    assert_sampled_show_output(result.output,
                              ['Source Port', 'Direction', 'Mirror Session', 'Admin State',
                               'Sample Rate', 'Truncate Size'], [])


def test_show_multi_asic_sample_bindings(sampled_show_db, monkeypatch):
    host = sampled_show_db()
    asic0 = sampled_show_db({
        ('Ethernet0', 'rx'): {'mirror_session': 'export1', 'sample_rate': '1000', 'admin_state': 'up'},
    })
    asic1 = sampled_show_db({
        ('Ethernet4', 'tx'): {'mirror_session': 'export2', 'sample_rate': '2000',
                              'truncate_size': '128', 'admin_state': 'down'},
    })
    monkeypatch.setattr(port_mirror, 'config_databases', lambda: {'': host, 'asic1': asic1, 'asic0': asic0})
    result = CliRunner().invoke(show_cli.cli.commands['mirror_session'], ['sample'])
    assert result.exit_code == 0, result.output
    assert_sampled_show_output(result.output,
                              ['Namespace', 'Source Port', 'Direction', 'Mirror Session', 'Admin State',
                               'Sample Rate', 'Truncate Size'], [
                                  ['asic0', 'Ethernet0', 'rx', 'export1', 'up', '1000', 'Disabled'],
                                  ['asic1', 'Ethernet4', 'tx', 'export2', 'down', '2000', '128'],
                              ])


def test_show_explicit_session_named_sample(monkeypatch):
    command = mock.Mock()
    monkeypatch.setattr(show_cli, 'run_command', command)
    result = CliRunner().invoke(show_cli.cli.commands['mirror_session'], ['--session-name', 'sample'])
    assert result.exit_code == 0, result.output
    command.assert_called_once_with(['acl-loader', 'show', 'session', 'sample'], display_cmd=False)


@pytest.mark.parametrize('args,command', [
    ([], ['acl-loader', 'show', 'session']),
    (['export1'], ['acl-loader', 'show', 'session', 'export1']),
])
def test_existing_show_commands_unchanged(monkeypatch, args, command):
    run = mock.Mock()
    monkeypatch.setattr(show_cli, 'run_command', run)
    result = CliRunner().invoke(show_cli.cli.commands['mirror_session'], args)
    assert result.exit_code == 0, result.output
    run.assert_called_once_with(command, display_cmd=False)


def test_show_rejects_two_session_selectors(monkeypatch):
    run = mock.Mock()
    monkeypatch.setattr(show_cli, 'run_command', run)
    result = CliRunner().invoke(show_cli.cli.commands['mirror_session'], ['export1', '--session-name', 'export2'])
    assert result.exit_code != 0
    assert 'not both' in result.output
    run.assert_not_called()


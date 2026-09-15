import os
import re
from click.testing import CliRunner

import show.main as show
from utilities_common.db import Db


def _ptp_status_cmd():
    return show.cli.commands["ptp"].commands["port"].commands["status"]


def _ptp_protocol_status_cmd():
    return show.cli.commands["ptp"].commands["protocol"].commands["status"]


def _clear_ptp_protocol_config(db):
    db.cfgdb.set_entry('PTP', 'global', None)
    for key in list((db.cfgdb.get_table('PTP_PORT') or {}).keys()):
        db.cfgdb.set_entry('PTP_PORT', key, None)
    for key in list((db.cfgdb.get_table('PTP_UNICAST_MASTER_TABLE_IP') or {}).keys()):
        db.cfgdb.set_entry('PTP_UNICAST_MASTER_TABLE_IP', key, None)
    for key in list((db.cfgdb.get_table('PTP_UNICAST_MASTER_TABLE') or {}).keys()):
        db.cfgdb.set_entry('PTP_UNICAST_MASTER_TABLE', key, None)


class TestShowPtpPortStatus(object):
    @classmethod
    def setup_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    @classmethod
    def teardown_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

    def test_show_ptp_port_status_default_disabled(self):
        runner = CliRunner()
        result = runner.invoke(_ptp_status_cmd(), [], obj=Db())
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert "Interface" in result.output
        assert "PTP" in result.output
        assert "Mode" in result.output
        assert "Ethernet0" in result.output
        assert "Ethernet4" in result.output
        assert "disabled" in result.output
        assert "enabled" not in result.output

    def test_show_ptp_port_status_single_port_disabled(self):
        runner = CliRunner()
        result = runner.invoke(_ptp_status_cmd(), ["Ethernet0"], obj=Db())
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert "Ethernet0" in result.output
        assert "disabled" in result.output
        assert "none" in result.output
        assert "Ethernet4" not in result.output

    def test_show_ptp_port_status_one_step(self):
        db = Db()
        orig_port = db.cfgdb.get_entry('PORT', 'Ethernet0')
        db.cfgdb.mod_entry('PORT', 'Ethernet0', {'ptp_mode': 'one-step'})
        db.cfgdb.set_entry('PTP_PORT', 'Ethernet0', {'unicast_listen': 'false'})
        try:
            runner = CliRunner()
            result = runner.invoke(_ptp_status_cmd(), ["Ethernet0"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert "Ethernet0" in result.output
            assert "enabled" in result.output
            assert "one-step" in result.output
        finally:
            db.cfgdb.set_entry('PORT', 'Ethernet0', orig_port)
            db.cfgdb.set_entry('PTP_PORT', 'Ethernet0', None)

    def test_show_ptp_port_status_two_step(self):
        db = Db()
        orig_port = db.cfgdb.get_entry('PORT', 'Ethernet4')
        db.cfgdb.mod_entry('PORT', 'Ethernet4', {'ptp_mode': 'two-step'})
        try:
            runner = CliRunner()
            result = runner.invoke(_ptp_status_cmd(), ["Ethernet4"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert "Ethernet4" in result.output
            assert "enabled" in result.output
            assert "two-step" in result.output
        finally:
            db.cfgdb.set_entry('PORT', 'Ethernet4', orig_port)

    def test_show_ptp_port_status_invalid_interface(self):
        runner = CliRunner()
        result = runner.invoke(_ptp_status_cmd(), ["Ethernet999"], obj=Db())
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert "does not exist in the PORT table" in result.output


class TestShowPtpProtocolStatus(object):
    @classmethod
    def setup_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    @classmethod
    def teardown_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

    def test_show_ptp_protocol_status_unset(self):
        db = Db()
        _clear_ptp_protocol_config(db)
        runner = CliRunner()
        result = runner.invoke(_ptp_protocol_status_cmd(), [], obj=db)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert "domain-number" in result.output
        assert "sync-interval" in result.output
        assert "announce-interval" in result.output
        assert "not set" in result.output
        assert "No unicast master tables configured" in result.output
        assert "No PTP ports configured" in result.output

    def test_show_ptp_protocol_status_configured(self):
        db = Db()
        _clear_ptp_protocol_config(db)
        db.cfgdb.mod_entry('PTP', 'global', {
            'domain_number': '24',
            'sync_interval': '-3',
            'announce_interval': '1',
        })
        db.cfgdb.set_entry('PTP_UNICAST_MASTER_TABLE', '1', {'NULL': 'NULL'})
        db.cfgdb.set_entry('PTP_UNICAST_MASTER_TABLE', '2', {'NULL': 'NULL'})
        db.cfgdb.set_entry('PTP_UNICAST_MASTER_TABLE_IP', ('1', '192.0.2.10'), {'NULL': 'NULL'})
        db.cfgdb.set_entry('PTP_UNICAST_MASTER_TABLE_IP', ('1', '192.0.2.11'), {'NULL': 'NULL'})
        db.cfgdb.set_entry('PTP_PORT', 'Ethernet0', {
            'unicast_table': '1',
            'unicast_listen': 'false',
        })
        db.cfgdb.set_entry('PTP_PORT', 'Ethernet4', {
            'unicast_listen': 'true',
        })
        db.cfgdb.set_entry('PTP_PORT', 'Ethernet8', {
            'unicast_table': '1',
            'unicast_listen': 'true',
        })
        try:
            runner = CliRunner()
            result = runner.invoke(_ptp_protocol_status_cmd(), [], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert re.search(r"domain-number\s+24", result.output)
            assert re.search(r"sync-interval\s+-3", result.output)
            assert re.search(r"announce-interval\s+1", result.output)
            assert "192.0.2.10" in result.output
            assert "192.0.2.11" in result.output
            assert "not set" in result.output  # table 2 has no addresses
            assert "Ethernet0" in result.output
            assert "slave" in result.output
            assert "Ethernet4" in result.output
            assert "master" in result.output
            assert "Ethernet8" in result.output
            assert "slave/master" in result.output
        finally:
            _clear_ptp_protocol_config(db)

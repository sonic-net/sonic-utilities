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


def _ptp_status_cmd():
    return show.cli.commands["ptp"].commands["status"]


def _ptp_counters_cmd():
    return show.cli.commands["ptp"].commands["counters"]


def _set_ptp_state(db, table, entry_key, fields):
    sep = db.db.get_db_separator(db.db.STATE_DB)
    key = '{}{}{}'.format(table, sep, entry_key)
    for field, value in fields.items():
        db.db.set(db.db.STATE_DB, key, field, str(value))


def _clear_ptp_state(db):
    sep = db.db.get_db_separator(db.db.STATE_DB)
    for table in ('PTP_CONFIG', 'PTP_TIME_STATUS'):
        prefix = table + sep
        for key in db.db.keys(db.db.STATE_DB, prefix + '*') or []:
            db.db.delete(db.db.STATE_DB, key)


def _set_ptp_counters(db, ifname, fields):
    sep = db.db.get_db_separator(db.db.COUNTERS_DB)
    key = 'COUNTERS_PTP{}{}'.format(sep, ifname)
    for field, value in fields.items():
        db.db.set(db.db.COUNTERS_DB, key, field, str(value))


def _clear_ptp_counters(db):
    sep = db.db.get_db_separator(db.db.COUNTERS_DB)
    prefix = 'COUNTERS_PTP' + sep
    for key in db.db.keys(db.db.COUNTERS_DB, prefix + '*') or []:
        db.db.delete(db.db.COUNTERS_DB, key)


class TestShowPtpStatus(object):
    @classmethod
    def setup_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    @classmethod
    def teardown_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

    def test_show_ptp_status_empty(self):
        db = Db()
        _clear_ptp_state(db)
        runner = CliRunner()
        result = runner.invoke(_ptp_status_cmd(), [], obj=db)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert "No PTP operational status in STATE_DB" in result.output

    def test_show_ptp_status_operational(self):
        db = Db()
        _clear_ptp_state(db)
        default_ds = {
            'clock-identity': '00:11:22:ff:fe:33:44:55',
            'domain-number': 24,
        }
        current_ds = {
            'steps-removed': 1,
            'offset-from-master': -42,
            'mean-path-delay': 1200,
        }
        parent_ds = {
            'grandmaster-identity': '00:aa:bb:ff:fe:cc:dd:ee',
            'parent-port-identity': {
                'clock-identity': '00:aa:bb:ff:fe:cc:dd:ee',
                'port-number': 1,
            },
        }
        port_list = [{
            'port-number': 1,
            'port-state': 9,
            'log-sync-interval': -3,
            'peer-mean-path-delay': 1200,
        }]
        _set_ptp_state(db, 'PTP_CONFIG', 'ptp|0', {
            'instance-number': 0,
            'default-ds': default_ds,
            'current-ds': current_ds,
            'parent-ds': parent_ds,
            'port-ds-list': port_list,
        })
        _set_ptp_state(db, 'PTP_TIME_STATUS', 'ptp|0', {
            'master-offset': -42,
            'ingress-time': 999,
        })
        try:
            runner = CliRunner()
            result = runner.invoke(_ptp_status_cmd(), [], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert "PTP Instance: ptp|0" in result.output
            assert "00:11:22:ff:fe:33:44:55" in result.output
            assert re.search(r"domain-number\s+24", result.output)
            assert re.search(r"offset-from-master\s+-42", result.output)
            assert "00:aa:bb:ff:fe:cc:dd:ee/1" in result.output
            assert "SLAVE (9)" in result.output
            assert re.search(r"master-offset\s+-42", result.output)
            assert re.search(r"ingress-time\s+999", result.output)
        finally:
            _clear_ptp_state(db)


class TestShowPtpCounters(object):
    @classmethod
    def setup_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    @classmethod
    def teardown_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

    def test_show_ptp_counters_empty(self):
        db = Db()
        _clear_ptp_counters(db)
        runner = CliRunner()
        result = runner.invoke(_ptp_counters_cmd(), [], obj=db)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert "No PTP counters in COUNTERS_DB" in result.output

    def test_show_ptp_counters_invalid_interface(self):
        runner = CliRunner()
        result = runner.invoke(_ptp_counters_cmd(), ["Ethernet999"], obj=Db())
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert "does not exist in the PORT table" in result.output

    def test_show_ptp_counters_missing_for_interface(self):
        db = Db()
        _clear_ptp_counters(db)
        runner = CliRunner()
        result = runner.invoke(_ptp_counters_cmd(), ["Ethernet0"], obj=db)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert "No PTP counters for interface 'Ethernet0'" in result.output

    def test_show_ptp_counters_one_interface(self):
        db = Db()
        _clear_ptp_counters(db)
        _set_ptp_counters(db, 'Ethernet0', {
            'portIdentity': 'aa:bb:cc.fffe.001122-1',
            'rx_Sync': '10',
            'tx_Sync': '1',
            'rx_Delay_Req': '4',
            'tx_Delay_Req': '4',
            'rx_Announce': '7',
            'tx_Announce': '0',
            'delay_timeout': '33017',
            'unicast_request_timeout': '2069',
        })
        try:
            runner = CliRunner()
            result = runner.invoke(_ptp_counters_cmd(), ["Ethernet0"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert "Ethernet0" in result.output
            assert "aa:bb:cc.fffe.001122-1" in result.output
            assert re.search(r"Sync\s+10\s+1", result.output)
            assert re.search(r"Delay_Req\s+4\s+4", result.output)
            assert re.search(r"Announce\s+7\s+0", result.output)
            assert "Service" in result.output
            assert re.search(r"delay_timeout\s+33017", result.output)
            assert re.search(r"unicast_request_timeout\s+2069", result.output)
            assert "Ethernet4" not in result.output
        finally:
            _clear_ptp_counters(db)

    def test_show_ptp_counters_all_interfaces(self):
        db = Db()
        _clear_ptp_counters(db)
        _set_ptp_counters(db, 'Ethernet0', {'rx_Sync': '10', 'tx_Sync': '0'})
        _set_ptp_counters(db, 'Ethernet4', {'rx_Sync': '0', 'tx_Sync': '8'})
        try:
            runner = CliRunner()
            result = runner.invoke(_ptp_counters_cmd(), [], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert "Ethernet0" in result.output
            assert "Ethernet4" in result.output
            assert re.search(r"Sync\s+10\s+0", result.output)
            assert re.search(r"Sync\s+0\s+8", result.output)
        finally:
            _clear_ptp_counters(db)

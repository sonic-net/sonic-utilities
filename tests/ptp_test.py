import os
import re
from click.testing import CliRunner

import config.ptp as config_ptp
import show.main as show
from utilities_common.db import Db


def _ptp_port_status_cmd():
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
        result = runner.invoke(_ptp_port_status_cmd(), [], obj=Db())
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
        result = runner.invoke(_ptp_port_status_cmd(), ["Ethernet0"], obj=Db())
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
            result = runner.invoke(_ptp_port_status_cmd(), ["Ethernet0"], obj=db)
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
            result = runner.invoke(_ptp_port_status_cmd(), ["Ethernet4"], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert "Ethernet4" in result.output
            assert "enabled" in result.output
            assert "two-step" in result.output
        finally:
            db.cfgdb.set_entry('PORT', 'Ethernet4', orig_port)

    def test_show_ptp_port_status_invalid_interface(self):
        runner = CliRunner()
        result = runner.invoke(_ptp_port_status_cmd(), ["Ethernet999"], obj=Db())
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


def _ptp_instance_status_cmd():
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
        result = runner.invoke(_ptp_instance_status_cmd(), [], obj=db)
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
            result = runner.invoke(_ptp_instance_status_cmd(), [], obj=db)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert "PTP Instance: ptp|0" in result.output
            assert "00:11:22:ff:fe:33:44:55" in result.output
            assert re.search(r"domain\s+24", result.output)
            assert re.search(r"steps removed\s+1", result.output)
            assert "00:aa:bb:ff:fe:cc:dd:ee" in result.output
            assert re.search(r"master offset\s+-42", result.output)
            assert re.search(r"ingress time\s+999", result.output)
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


def _invoke_config_ptp(db, args):
    runner = CliRunner()
    result = runner.invoke(config_ptp.ptp, list(args), obj=db)
    print(result.exit_code, result.output)
    if result.exception is not None and not result.output:
        print(result.exception)
    return result


class TestConfigPtp(object):
    @classmethod
    def setup_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    @classmethod
    def teardown_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

    def test_global_settings(self):
        db = Db()
        cases = [
            (["domain-number", "0"], "PTP domain number set to 0", "domain_number", "0"),
            (["domain-number", "24"], "PTP domain number set to 24", "domain_number", "24"),
            (["domain-number", "127"], "PTP domain number set to 127", "domain_number", "127"),
            (["sync-interval", "--", "-7"], "PTP sync interval set to -7", "sync_interval", "-7"),
            (["sync-interval", "7"], "PTP sync interval set to 7", "sync_interval", "7"),
            (["announce-interval", "--", "-3"], "PTP announce interval set to -3", "announce_interval", "-3"),
            (["announce-interval", "1"], "PTP announce interval set to 1", "announce_interval", "1"),
            (["announce-interval", "4"], "PTP announce interval set to 4", "announce_interval", "4"),
        ]
        for args, message, field, value in cases:
            result = _invoke_config_ptp(db, args)
            assert result.exit_code == 0
            assert message in result.output
            entry = db.cfgdb.get_entry("PTP", "global")
            assert entry[field] == value

    def test_global_settings_out_of_range(self):
        db = Db()
        for args in (
            ["domain-number", "--", "-1"],
            ["domain-number", "128"],
            ["sync-interval", "--", "-8"],
            ["sync-interval", "8"],
            ["announce-interval", "--", "-4"],
            ["announce-interval", "5"],
        ):
            result = _invoke_config_ptp(db, args)
            assert result.exit_code != 0
            assert "Invalid value" in result.output

    def test_unicast_master_table_add_and_duplicate(self):
        db = Db()
        result = _invoke_config_ptp(db, ["unicast-master-table", "add", "0"])
        assert result.exit_code == 0
        assert "PTP unicast master table 0 added" in result.output
        assert "0" in [str(k) for k in db.cfgdb.get_keys("PTP_UNICAST_MASTER_TABLE")]

        result = _invoke_config_ptp(db, ["unicast-master-table", "add", "1"])
        assert result.exit_code == 0
        assert "PTP unicast master table 1 added" in result.output

        result = _invoke_config_ptp(db, ["unicast-master-table", "add", "1"])
        assert result.exit_code != 0
        assert "PTP unicast master table 1 already exists" in result.output

    def test_unicast_master_table_add_negative_id(self):
        db = Db()
        result = _invoke_config_ptp(db, ["unicast-master-table", "add", "--", "-1"])
        assert result.exit_code != 0
        assert "Table ID -1 is invalid" in result.output
        assert db.cfgdb.get_keys("PTP_UNICAST_MASTER_TABLE") == []

    def test_unicast_master_table_remove_missing(self):
        db = Db()
        result = _invoke_config_ptp(db, ["unicast-master-table", "remove", "9"])
        assert result.exit_code != 0
        assert "PTP unicast master table 9 does not exist" in result.output

    def test_unicast_master_table_remove_with_ips(self):
        db = Db()
        assert _invoke_config_ptp(db, ["unicast-master-table", "add", "1"]).exit_code == 0
        assert _invoke_config_ptp(db, ["unicast-master-table", "add", "2"]).exit_code == 0
        assert _invoke_config_ptp(db, ["unicast-master-table", "ip", "add", "1", "192.0.2.10"]).exit_code == 0
        assert _invoke_config_ptp(db, ["unicast-master-table", "ip", "add", "2", "192.0.2.20"]).exit_code == 0

        # ConfigDB normally returns tuple keys. Also feed a 'table|ip' string so
        # the non-tuple branch in unicast_master_table_remove is executed.
        original_get_keys = db.cfgdb.get_keys

        def get_keys(table, split=True):
            keys = original_get_keys(table, split=split)
            if table == "PTP_UNICAST_MASTER_TABLE_IP":
                keys = list(keys) + ["1|192.0.2.77", "2|192.0.2.88"]
            return keys

        db.cfgdb.get_keys = get_keys
        result = _invoke_config_ptp(db, ["unicast-master-table", "remove", "1"])
        assert result.exit_code == 0
        assert "PTP unicast master table 1 removed" in result.output

        table_keys = [str(k) for k in db.cfgdb.get_keys("PTP_UNICAST_MASTER_TABLE")]
        assert "1" not in table_keys
        assert "2" in table_keys
        ip_keys = db.cfgdb.get_keys("PTP_UNICAST_MASTER_TABLE_IP")
        assert ("1", "192.0.2.10") not in ip_keys
        assert ("2", "192.0.2.20") in ip_keys

    def test_unicast_master_ip_add_and_remove(self):
        db = Db()
        assert _invoke_config_ptp(db, ["unicast-master-table", "add", "1"]).exit_code == 0

        result = _invoke_config_ptp(db, ["unicast-master-table", "ip", "add", "1", "192.0.2.10"])
        assert result.exit_code == 0
        assert "IP 192.0.2.10 added to PTP unicast master table 1" in result.output

        result = _invoke_config_ptp(db, ["unicast-master-table", "ip", "add", "1", "2001:db8::10"])
        assert result.exit_code == 0
        assert "IP 2001:db8::10 added to PTP unicast master table 1" in result.output
        ip_keys = db.cfgdb.get_keys("PTP_UNICAST_MASTER_TABLE_IP")
        assert ("1", "192.0.2.10") in ip_keys
        assert ("1", "2001:db8::10") in ip_keys

        result = _invoke_config_ptp(db, ["unicast-master-table", "ip", "add", "1", "192.0.2.10"])
        assert result.exit_code != 0
        assert "IP 192.0.2.10 already exists in PTP unicast master table 1" in result.output

        result = _invoke_config_ptp(db, ["unicast-master-table", "ip", "remove", "1", "192.0.2.10"])
        assert result.exit_code == 0
        assert "IP 192.0.2.10 removed from PTP unicast master table 1" in result.output
        assert ("1", "192.0.2.10") not in db.cfgdb.get_keys("PTP_UNICAST_MASTER_TABLE_IP")
        assert ("1", "2001:db8::10") in db.cfgdb.get_keys("PTP_UNICAST_MASTER_TABLE_IP")

        result = _invoke_config_ptp(db, ["unicast-master-table", "ip", "remove", "1", "2001:db8::10"])
        assert result.exit_code == 0
        assert ("1", "2001:db8::10") not in db.cfgdb.get_keys("PTP_UNICAST_MASTER_TABLE_IP")

    def test_unicast_master_ip_invalid_address(self):
        db = Db()
        assert _invoke_config_ptp(db, ["unicast-master-table", "add", "1"]).exit_code == 0

        result = _invoke_config_ptp(db, ["unicast-master-table", "ip", "add", "1", "not-an-ip"])
        assert result.exit_code != 0
        assert "not a valid IPv4 or IPv6 address" in result.output

        result = _invoke_config_ptp(db, ["unicast-master-table", "ip", "remove", "1", "not-an-ip"])
        assert result.exit_code != 0
        assert "not a valid IPv4 or IPv6 address" in result.output

    def test_unicast_master_ip_missing_table(self):
        db = Db()
        result = _invoke_config_ptp(db, ["unicast-master-table", "ip", "add", "5", "192.0.2.10"])
        assert result.exit_code != 0
        assert "PTP unicast master table 5 does not exist" in result.output

    def test_unicast_master_ip_remove_missing(self):
        db = Db()
        assert _invoke_config_ptp(db, ["unicast-master-table", "add", "1"]).exit_code == 0
        result = _invoke_config_ptp(db, ["unicast-master-table", "ip", "remove", "1", "192.0.2.10"])
        assert result.exit_code != 0
        assert "IP 192.0.2.10 does not exist in PTP unicast master table 1" in result.output

    def test_interface_add_and_remove(self):
        db = Db()
        result = _invoke_config_ptp(db, ["interface", "add", "Ethernet0"])
        assert result.exit_code == 0
        assert "PTP port entry added for interface 'Ethernet0'" in result.output
        assert db.cfgdb.get_entry("PTP_PORT", "Ethernet0") == {"unicast_listen": "false"}
        assert db.cfgdb.get_entry("PORT", "Ethernet0")["ptp_mode"] == "one-step"

        result = _invoke_config_ptp(db, ["interface", "remove", "Ethernet0"])
        assert result.exit_code == 0
        assert "PTP port entry removed for interface 'Ethernet0'" in result.output
        assert db.cfgdb.get_entry("PTP_PORT", "Ethernet0") == {}
        assert db.cfgdb.get_entry("PORT", "Ethernet0")["ptp_mode"] == "none"

    def test_interface_add_with_table_and_listen(self):
        db = Db()
        assert _invoke_config_ptp(db, ["unicast-master-table", "add", "3"]).exit_code == 0
        result = _invoke_config_ptp(
            db, ["interface", "add", "Ethernet4", "3", "--unicast-listen"])
        assert result.exit_code == 0
        assert db.cfgdb.get_entry("PTP_PORT", "Ethernet4") == {
            "unicast_listen": "true",
            "unicast_table": "3",
        }
        assert db.cfgdb.get_entry("PORT", "Ethernet4")["ptp_mode"] == "one-step"

    def test_interface_add_invalid(self):
        db = Db()
        result = _invoke_config_ptp(db, ["interface", "add", "Ethernet999"])
        assert result.exit_code != 0
        assert "Interface 'Ethernet999' does not exist in the PORT table" in result.output

        result = _invoke_config_ptp(db, ["interface", "add", "Ethernet0", "9"])
        assert result.exit_code != 0
        assert "PTP unicast master table 9 does not exist" in result.output

        assert _invoke_config_ptp(db, ["interface", "add", "Ethernet0"]).exit_code == 0
        result = _invoke_config_ptp(db, ["interface", "add", "Ethernet0"])
        assert result.exit_code != 0
        assert "PTP port entry for 'Ethernet0' already exists" in result.output

    def test_interface_remove_missing(self):
        db = Db()
        result = _invoke_config_ptp(db, ["interface", "remove", "Ethernet0"])
        assert result.exit_code != 0
        assert "PTP port entry for 'Ethernet0' does not exist" in result.output

    def test_commands_skip_adhoc_validation(self):
        """ADHOC_VALIDATION is normally on. Cover the bypass path explicitly."""
        db = Db()
        config_ptp.ADHOC_VALIDATION = False
        try:
            result = _invoke_config_ptp(db, ["unicast-master-table", "add", "--", "-1"])
            assert result.exit_code == 0
            assert "-1" in [str(k) for k in db.cfgdb.get_keys("PTP_UNICAST_MASTER_TABLE")]

            result = _invoke_config_ptp(db, ["unicast-master-table", "remove", "9"])
            assert result.exit_code == 0

            result = _invoke_config_ptp(db, ["unicast-master-table", "ip", "add", "5", "not-an-ip"])
            assert result.exit_code == 0
            assert ("5", "not-an-ip") in db.cfgdb.get_keys("PTP_UNICAST_MASTER_TABLE_IP")

            result = _invoke_config_ptp(db, ["unicast-master-table", "ip", "remove", "5", "not-an-ip"])
            assert result.exit_code == 0
            assert ("5", "not-an-ip") not in db.cfgdb.get_keys("PTP_UNICAST_MASTER_TABLE_IP")

            result = _invoke_config_ptp(db, ["interface", "add", "Ethernet999", "9"])
            assert result.exit_code == 0
            assert db.cfgdb.get_entry("PTP_PORT", "Ethernet999")["unicast_table"] == "9"

            result = _invoke_config_ptp(db, ["interface", "remove", "Ethernet8"])
            assert result.exit_code == 0
        finally:
            config_ptp.ADHOC_VALIDATION = True

import os
from click.testing import CliRunner

import show.main as show
from utilities_common.db import Db


def _ptp_status_cmd():
    return show.cli.commands["ptp"].commands["port"].commands["status"]


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

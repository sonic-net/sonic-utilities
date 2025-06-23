import click
import json
import os
import pytest
import mock
import sys
import importlib
from click.testing import CliRunner
from shutil import copyfile
from utilities_common.db import Db

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

from .mock_tables import dbconnector

import counterpoll.main as counterpoll

expected_counterpoll_show = """Type                  Interval (in ms)    Status
--------------------  ------------------  --------
QUEUE_STAT            10000               enable
PORT_STAT             1000                enable
PORT_BUFFER_DROP      60000               enable
QUEUE_WATERMARK_STAT  default (60000)     enable
PG_WATERMARK_STAT     default (60000)     enable
PG_DROP_STAT          10000               enable
ACL                   5000                enable
TUNNEL_STAT           3000                enable
FLOW_CNT_TRAP_STAT    10000               enable
FLOW_CNT_ROUTE_STAT   10000               enable
WRED_ECN_QUEUE_STAT   10000               enable
WRED_ECN_PORT_STAT    1000                enable
SRV6_STAT             10000               enable
"""

expected_counterpoll_show_dpu = """Type                  Interval (in ms)    Status
--------------------  ------------------  --------
QUEUE_STAT            10000               enable
PORT_STAT             1000                enable
PORT_BUFFER_DROP      60000               enable
QUEUE_WATERMARK_STAT  default (60000)     enable
PG_WATERMARK_STAT     default (60000)     enable
PG_DROP_STAT          10000               enable
ACL                   5000                enable
TUNNEL_STAT           3000                enable
FLOW_CNT_TRAP_STAT    10000               enable
FLOW_CNT_ROUTE_STAT   10000               enable
WRED_ECN_QUEUE_STAT   10000               enable
WRED_ECN_PORT_STAT    1000                enable
SRV6_STAT             10000               enable
ENI_STAT              1000                enable
"""

class TestCounterpoll(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_show(self):
        runner = CliRunner()
        result = runner.invoke(counterpoll.cli.commands["show"], [])
        print(result.output)
        assert result.output == expected_counterpoll_show

    @mock.patch('counterpoll.main.device_info.get_platform_info')
    def test_show_dpu(self, mock_get_platform_info):
        mock_get_platform_info.return_value = {'switch_type': 'dpu'}
        runner = CliRunner()
        result = runner.invoke(counterpoll.cli.commands["show"], [])
        assert result.output == expected_counterpoll_show_dpu

    def test_port_buffer_drop_interval(self):
        runner = CliRunner()
        result = runner.invoke(counterpoll.cli.commands["port-buffer-drop"].commands["interval"], ["30000"])
        print(result.output)
        assert result.exit_code == 0

    def test_port_buffer_drop_interval_too_short(self):
        runner = CliRunner()
        result = runner.invoke(counterpoll.cli.commands["port-buffer-drop"].commands["interval"], ["1000"])
        print(result.output)
        expected = "Invalid value for \"POLL_INTERVAL\": 1000 is not in the valid range of 30000 to 300000."
        assert result.exit_code == 2
        assert expected in result.output

    def test_pg_drop_interval_too_long(self):
        runner = CliRunner()
        result = runner.invoke(counterpoll.cli.commands["pg-drop"].commands["interval"], ["50000"])
        print(result.output)
        expected = "Invalid value for \"POLL_INTERVAL\": 50000 is not in the valid range of 1000 to 30000."
        assert result.exit_code == 2
        assert expected in result.output

    @pytest.mark.parametrize("interval", [100, 50000])
    def test_acl_interval_range(self, interval):
        runner = CliRunner()
        result = runner.invoke(counterpoll.cli.commands["acl"].commands["interval"], [str(interval)])
        print(result.output)
        expected = "Invalid value for \"POLL_INTERVAL\": {} is not in the valid range of 1000 to 30000.".format(interval)
        assert result.exit_code == 2
        assert expected in result.output

    @pytest.fixture(scope='class')
    def _get_config_db_file(self):
        sample_config_db_file = os.path.join(test_path, "counterpoll_input", "config_db.json")
        config_db_file = os.path.join('/', "tmp", "config_db.json")
        copyfile(sample_config_db_file, config_db_file)

        yield config_db_file

        os.remove(config_db_file)

    @pytest.mark.parametrize("status", ["disable", "enable"])
    def test_update_pg_drop_status(self, status):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(counterpoll.cli.commands["pg-drop"].commands[status], [], obj=db.cfgdb)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        table = db.cfgdb.get_table('FLEX_COUNTER_TABLE')
        assert status == table["PG_DROP"]["FLEX_COUNTER_STATUS"]

    def test_update_pg_drop_interval(self):
        runner = CliRunner()
        db = Db()
        test_interval = "20000"

        result = runner.invoke(counterpoll.cli.commands["pg-drop"].commands["interval"], [test_interval], obj=db.cfgdb)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        table = db.cfgdb.get_table('FLEX_COUNTER_TABLE')
        assert test_interval == table["PG_DROP"]["POLL_INTERVAL"]

    @pytest.mark.parametrize("status", ["disable", "enable"])
    def test_update_acl_status(self, status):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(counterpoll.cli.commands["acl"].commands[status], [], obj=db.cfgdb)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        table = db.cfgdb.get_table("FLEX_COUNTER_TABLE")
        assert status == table["ACL"]["FLEX_COUNTER_STATUS"]

    def test_update_acl_interval(self):
        runner = CliRunner()
        db = Db()
        test_interval = "20000"

        result = runner.invoke(counterpoll.cli.commands["acl"].commands["interval"], [test_interval], obj=db.cfgdb)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        table = db.cfgdb.get_table("FLEX_COUNTER_TABLE")
        assert test_interval == table["ACL"]["POLL_INTERVAL"]

    @pytest.mark.parametrize("status", ["disable", "enable"])
    def test_update_trap_counter_status(self, status):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(counterpoll.cli.commands["flowcnt-trap"].commands[status], [], obj=db.cfgdb)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        table = db.cfgdb.get_table('FLEX_COUNTER_TABLE')
        assert status == table["FLOW_CNT_TRAP"]["FLEX_COUNTER_STATUS"]

    @pytest.mark.parametrize("status", ["disable", "enable"])
    def test_update_route_flow_counter_status(self, status):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(counterpoll.cli.commands["flowcnt-route"].commands[status], [], obj=db.cfgdb)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        table = db.cfgdb.get_table('FLEX_COUNTER_TABLE')
        assert status == table["FLOW_CNT_ROUTE"]["FLEX_COUNTER_STATUS"]

    def test_update_trap_counter_interval(self):
        runner = CliRunner()
        db = Db()
        test_interval = "20000"

        result = runner.invoke(counterpoll.cli.commands["flowcnt-trap"].commands["interval"], [test_interval], obj=db.cfgdb)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        table = db.cfgdb.get_table('FLEX_COUNTER_TABLE')
        assert test_interval == table["FLOW_CNT_TRAP"]["POLL_INTERVAL"]

        test_interval = "500"
        result = runner.invoke(counterpoll.cli.commands["flowcnt-trap"].commands["interval"], [test_interval], obj=db.cfgdb)
        expected = "Invalid value for \"POLL_INTERVAL\": 500 is not in the valid range of 1000 to 30000."
        assert result.exit_code == 2
        assert expected in result.output

        test_interval = "40000"
        result = runner.invoke(counterpoll.cli.commands["flowcnt-trap"].commands["interval"], [test_interval], obj=db.cfgdb)
        expected = "Invalid value for \"POLL_INTERVAL\": 40000 is not in the valid range of 1000 to 30000."
        assert result.exit_code == 2
        assert expected in result.output

    def test_update_route_counter_interval(self):
        runner = CliRunner()
        db = Db()
        test_interval = "20000"

        result = runner.invoke(counterpoll.cli.commands["flowcnt-route"].commands["interval"], [test_interval],
                               obj=db.cfgdb)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        table = db.cfgdb.get_table('FLEX_COUNTER_TABLE')
        assert test_interval == table["FLOW_CNT_ROUTE"]["POLL_INTERVAL"]

        test_interval = "500"
        result = runner.invoke(counterpoll.cli.commands["flowcnt-route"].commands["interval"], [test_interval],
                               obj=db.cfgdb)
        expected = "Invalid value for \"POLL_INTERVAL\": 500 is not in the valid range of 1000 to 30000."
        assert result.exit_code == 2
        assert expected in result.output

        test_interval = "40000"
        result = runner.invoke(counterpoll.cli.commands["flowcnt-route"].commands["interval"], [test_interval],
                               obj=db.cfgdb)

        expected = "Invalid value for \"POLL_INTERVAL\": 40000 is not in the valid range of 1000 to 30000."
        assert result.exit_code == 2
        assert expected in result.output

    @pytest.mark.parametrize("status", ["disable", "enable"])
    def test_update_eni_status(self, status):
        runner = CliRunner()
        result = runner.invoke(counterpoll.cli, ["eni", status])
        assert 'No such command "eni"' in result.output
        assert result.exit_code == 2

    @pytest.mark.parametrize("status", ["disable", "enable"])
    @mock.patch('counterpoll.main.device_info.get_platform_info')
    def test_update_eni_status_dpu(self, mock_get_platform_info, status):
        mock_get_platform_info.return_value = {'switch_type': 'dpu'}
        importlib.reload(counterpoll)

        runner = CliRunner()
        db = Db()

        result = runner.invoke(counterpoll.cli.commands["eni"].commands[status], [], obj=db.cfgdb)
        assert result.exit_code == 0

        table = db.cfgdb.get_table('FLEX_COUNTER_TABLE')
        assert status == table["ENI"]["FLEX_COUNTER_STATUS"]

    @mock.patch('counterpoll.main.device_info.get_platform_info')
    def test_update_eni_interval(self, mock_get_platform_info):
        mock_get_platform_info.return_value = {'switch_type': 'dpu'}
        importlib.reload(counterpoll)

        runner = CliRunner()
        db = Db()
        test_interval = "2000"

        result = runner.invoke(counterpoll.cli.commands["eni"].commands["interval"], [test_interval], obj=db.cfgdb)
        assert result.exit_code == 0

        table = db.cfgdb.get_table('FLEX_COUNTER_TABLE')
        assert test_interval == table["ENI"]["POLL_INTERVAL"]

    @pytest.mark.parametrize("status", ["disable", "enable"])
    def test_update_wred_port_counter_status(self, status):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(counterpoll.cli.commands["wredport"].commands[status], [], obj=db.cfgdb)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        table = db.cfgdb.get_table('FLEX_COUNTER_TABLE')
        assert status == table["WRED_ECN_PORT"]["FLEX_COUNTER_STATUS"]

        if status == "enable":
            result = runner.invoke(counterpoll.cli.commands["show"], [])
            print(result.output)
            assert "WRED_ECN_PORT_STAT" in result.output

    @pytest.mark.parametrize("status", ["disable", "enable"])
    def test_update_wred_queue_counter_status(self, status):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(counterpoll.cli.commands["wredqueue"].commands[status], [], obj=db.cfgdb)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        table = db.cfgdb.get_table('FLEX_COUNTER_TABLE')
        print(table)
        assert status == table["WRED_ECN_QUEUE"]["FLEX_COUNTER_STATUS"]

        if status == "enable":
            result = runner.invoke(counterpoll.cli.commands["show"], [])
            print(result.output)
            assert "WRED_ECN_QUEUE_STAT" in result.output

    def test_update_wred_port_counter_interval(self):
        runner = CliRunner()
        db = Db()
        test_interval = "15000"

        result = runner.invoke(counterpoll.cli.commands["wredport"].commands["interval"], [test_interval], obj=db.cfgdb)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        table = db.cfgdb.get_table("FLEX_COUNTER_TABLE")
        print(table)
        assert test_interval == table["WRED_ECN_PORT"]["POLL_INTERVAL"]

    def test_update_wred_queue_counter_interval(self):
        runner = CliRunner()
        db = Db()
        test_interval = "18000"

        res = runner.invoke(counterpoll.cli.commands["wredqueue"].commands["interval"], [test_interval], obj=db.cfgdb)
        print(res.exit_code, res.output)
        assert res.exit_code == 0

        table = db.cfgdb.get_table("FLEX_COUNTER_TABLE")
        print(table)
        assert test_interval == table["WRED_ECN_QUEUE"]["POLL_INTERVAL"]

    @pytest.mark.parametrize("status", ["disable", "enable"])
    def test_update_srv6_status(self, status):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(counterpoll.cli.commands["srv6"].commands[status], [], obj=db.cfgdb)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        table = db.cfgdb.get_table("FLEX_COUNTER_TABLE")
        assert status == table["SRV6"]["FLEX_COUNTER_STATUS"]

    def test_update_srv6_interval(self):
        runner = CliRunner()
        db = Db()
        test_interval = "20000"

        result = runner.invoke(counterpoll.cli.commands["srv6"].commands["interval"], [test_interval], obj=db.cfgdb)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        table = db.cfgdb.get_table("FLEX_COUNTER_TABLE")
        assert test_interval == table["SRV6"]["POLL_INTERVAL"]


    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

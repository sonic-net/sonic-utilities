import os
import sys
import pytest
from unittest import mock

from jsonpatch import JsonPatchConflict
from click.testing import CliRunner
from utilities_common.db import Db
from mock import patch

import show.main as show
import config.main as config
import config.validated_config_db_connector as validated_config_db_connector

config.asic_type = mock.MagicMock(return_value = "broadcom")

# Expected output for 'show sflow'
show_sflow_output = """
sFlow Global Information:
  sFlow Admin State:          up
  sFlow Sample Direction:     both
  sFlow Polling Interval:     0
  sFlow AgentID:              default

  2 Collectors configured:
    Name: prod                IP addr: fe80::6e82:6aff:fe1e:cd8e UDP port: 6343   VRF: mgmt
    Name: ser5                IP addr: 172.21.35.15    UDP port: 6343   VRF: default
"""

# Expected output for 'show sflow interface'
show_sflow_intf_output = """
sFlow interface configurations
+-------------+---------------+-----------------+----------------------+
| Interface   | Admin State   |   Sampling Rate | Sampling Direction   |
+=============+===============+=================+======================+
| Ethernet0   | up            |            2500 | both                 |
+-------------+---------------+-----------------+----------------------+
| Ethernet4   | up            |            1000 | tx                   |
+-------------+---------------+-----------------+----------------------+
| Ethernet112 | up            |            1000 | both                 |
+-------------+---------------+-----------------+----------------------+
| Ethernet116 | up            |            5000 | rx                   |
+-------------+---------------+-----------------+----------------------+
"""

class TestShowSflow(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_show_sflow(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["sflow"], [], obj=Db())
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert result.output == show_sflow_output

    def test_show_sflow_intf(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["sflow"].commands["interface"], [], obj=Db())
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert result.output == show_sflow_intf_output

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_config_sflow_disable_enable_yang_validation(self):
        db = Db()
        runner = CliRunner()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["sflow"].commands["enable"], [], obj=obj)
        print(result.exit_code, result.output)
        assert "Invalid ConfigDB. Error" in result.output

        result = runner.invoke(config.config.commands["sflow"].commands["disable"], [], obj=obj)
        print(result.exit_code, result.output)
        assert "Invalid ConfigDB. Error" in result.output

    def test_config_sflow_disable_enable(self):
        # config sflow <enable|disable>
        db = Db()
        runner = CliRunner()
        obj = {'db':db.cfgdb}

        #disable
        result = runner.invoke(config.config.commands["sflow"].commands["disable"], [], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        # change the output
        global show_sflow_output
        show_sflow_output_local = show_sflow_output.replace(
            'Admin State:          up',
            'Admin State:          down')

        # run show and check
        result = runner.invoke(show.cli.commands["sflow"], [], obj=db)
        print(result.exit_code, result.output, show_sflow_output_local)
        assert result.exit_code == 0
        assert result.output == show_sflow_output_local

        # enable
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock()) as mock_run_command:
            result = runner.invoke(config.config.commands["sflow"].commands["enable"], [], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 2

        # run show and check
        result = runner.invoke(show.cli.commands["sflow"], [], obj=db)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert result.output == show_sflow_output

        return

    def test_config_sflow_agent_id(self):
        db = Db()
        runner = CliRunner()
        obj = {'db':db.cfgdb}

        # mock netifaces.interface
        config.netifaces.interfaces = mock.MagicMock(return_value = "Ethernet0")

        # set agent-id
        result = runner.invoke(config.config.commands["sflow"].
            commands["agent-id"].commands["add"], ["Ethernet0"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        # change the output
        global show_sflow_output
        show_sflow_output_local = show_sflow_output.replace(
                'sFlow AgentID:              default',
                'sFlow AgentID:              Ethernet0')

        # run show and check
        result = runner.invoke(show.cli.commands["sflow"], [], obj=db)
        print(result.exit_code, result.output, show_sflow_output_local)
        assert result.exit_code == 0
        assert result.output == show_sflow_output_local

        #del agent id
        result = runner.invoke(config.config.commands["sflow"].
            commands["agent-id"].commands["del"], [], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        # run show and check
        result = runner.invoke(show.cli.commands["sflow"], [], obj=db)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert result.output == show_sflow_output

        return

    def test_config_sflow_collector(self):
        db = Db()
        runner = CliRunner()
        obj = {'db':db.cfgdb}

        # del a collector
        result = runner.invoke(config.config.commands["sflow"].
            commands["collector"].commands["del"], ["prod"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        # change the output
        global show_sflow_output
        show_sflow_output_local = show_sflow_output.replace(
    "2 Collectors configured:\n\
    Name: prod                IP addr: fe80::6e82:6aff:fe1e:cd8e UDP port: 6343   VRF: mgmt\n\
    Name: ser5                IP addr: 172.21.35.15    UDP port: 6343   VRF: default",
    "1 Collectors configured:\n\
    Name: ser5                IP addr: 172.21.35.15    UDP port: 6343   VRF: default")

        # run show and check
        result = runner.invoke(show.cli.commands["sflow"], [], obj=db)
        print(result.exit_code, result.output, show_sflow_output_local)
        assert result.exit_code == 0
        assert result.output == show_sflow_output_local

        # add collector
        result = runner.invoke(config.config.commands["sflow"].
            commands["collector"].commands["add"],
            ["prod", "fe80::6e82:6aff:fe1e:cd8e", "--vrf", "mgmt"], obj=obj)
        assert result.exit_code == 0

        # run show and check
        result = runner.invoke(show.cli.commands["sflow"], [], obj=db)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert result.output == show_sflow_output

        return

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=JsonPatchConflict))
    def test_config_sflow_collector_invalid_yang_validation(self):
        db = Db()
        runner = CliRunner()
        obj = {'db':db.cfgdb}

        config.ADHOC_VALIDTION = False
        result = runner.invoke(config.config.commands["sflow"].
            commands["collector"].commands["del"], ["prod"], obj=obj)
        print(result.exit_code, result.output)
        assert "Invalid ConfigDB. Error" in result.output

        result = runner.invoke(config.config.commands["sflow"].
            commands["collector"].commands["add"],
            ["prod", "fe80::6e82:6aff:fe1e:cd8e", "--vrf", "mgmt"], obj=obj)
        assert "Invalid ConfigDB. Error" in result.output
    
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_config_sflow_polling_interval_yang_validation(self):
        db = Db()
        runner = CliRunner()
        obj = {'db':db.cfgdb}

        config.ADHOC_VALIDATION = False
        result = runner.invoke(config.config.commands["sflow"].
            commands["polling-interval"], ["500"], obj=obj)
        print(result.exit_code, result.output)
        assert "Invalid ConfigDB. Error" in result.output

    def test_config_sflow_polling_interval(self):
        db = Db()
        runner = CliRunner()
        obj = {'db':db.cfgdb}
        config.ADHOC_VALIDATION = True

        # set to 500 out of range
        result = runner.invoke(config.config.commands["sflow"].
            commands["polling-interval"], ["500"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert "Polling interval must be between 5-300" in result.output

        # set to 20
        result = runner.invoke(config.config.commands["sflow"].
            commands["polling-interval"], ["20"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        # change the expected output
        global show_sflow_output
        show_sflow_output_local = show_sflow_output.replace(
            'sFlow Polling Interval:     0',
            'sFlow Polling Interval:     20')

        # run show and check
        result = runner.invoke(show.cli.commands["sflow"], [], obj=db)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert result.output == show_sflow_output_local

        #reset to 0, no need to verify this one
        result = runner.invoke(config.config.commands["sflow"].
            commands["polling-interval"], ["0"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        return

    @patch("config.main.ConfigDBConnector.get_table", mock.Mock(return_value={'Ethernet1': {'admin_state': 'sample_state'}}))
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_config_sflow_existing_intf_enable_yang_validation(self):
        db = Db()
        runner = CliRunner()
        obj = {'db':db.cfgdb}
        config.ADHOC_VALIDATION = False

        result = runner.invoke(config.config.commands["sflow"].
            commands["interface"].commands["enable"], ["Ethernet1"], obj=obj)
        print(result.exit_code, result.output)
        assert "Invalid ConfigDB. Error" in result.output
    
    @patch("config.main.ConfigDBConnector.get_table", mock.Mock(return_value=None))
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_config_sflow_nonexistent_intf_enable_yang_validation(self):
        db = Db()
        runner = CliRunner()
        obj = {'db':db.cfgdb}
 
        result = runner.invoke(config.config.commands["sflow"].
            commands["interface"].commands["enable"], ["Ethernet1"], obj=obj)
        print(result.exit_code, result.output)
        assert "Invalid ConfigDB. Error" in result.output

    def test_config_sflow_intf_enable_disable(self):
        db = Db()
        runner = CliRunner()
        obj = {'db':db.cfgdb}
        config.ADHOC_VALIDATION = True

        # mock interface_name_is_valid
        config.interface_name_is_valid = mock.MagicMock(return_value = True)

        # intf enable
        result = runner.invoke(config.config.commands["sflow"].
            commands["interface"].commands["enable"], ["Ethernet1"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        # we can not use 'show sflow interface', becasue 'show sflow interface'
        # gets data from appDB, we need to fetch data from configDB for verification
        sflowSession = db.cfgdb.get_table('SFLOW_SESSION')
        assert sflowSession["Ethernet1"]["admin_state"] == "up"

        # intf disable
        result = runner.invoke(config.config.commands["sflow"].
            commands["interface"].commands["disable"], ["Ethernet1"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        # verify in configDb
        sflowSession = db.cfgdb.get_table('SFLOW_SESSION')
        assert sflowSession["Ethernet1"]["admin_state"] == "down"

        config.interface_name_is_valid = mock.MagicMock(return_value = False)
        result = runner.invoke(config.config.commands["sflow"].
            commands["interface"].commands["enable"], ["Ethernetx"], obj=obj)
        print(result.exit_code, result.output)
        assert "Invalid interface name" in result.output

        result = runner.invoke(config.config.commands["sflow"].
            commands["interface"].commands["disable"], ["Ethernetx"], obj=obj)
        print(result.exit_code, result.output)
        assert "Invalid interface name" in result.output

        return

    def test_config_sflow_intf_sample_rate(self):
        db = Db()
        runner = CliRunner()
        obj = {'db':db.cfgdb}

        # mock interface_name_is_valid
        config.interface_name_is_valid = mock.MagicMock(return_value = True)

        # set sample-rate to 2500
        result = runner.invoke(config.config.commands["sflow"].
            commands["interface"].commands["sample-rate"],
            ["Ethernet2", "2500"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        # we can not use 'show sflow interface', becasue 'show sflow interface'
        # gets data from appDB, we need to fetch data from configDB for verification
        sflowSession = db.cfgdb.get_table('SFLOW_SESSION')
        assert sflowSession["Ethernet2"]["sample_rate"] == "2500"

        return

    def test_config_disable_all_intf(self):
        db = Db()
        runner = CliRunner()
        obj = {'db':db.cfgdb}

        # disable all interfaces
        result = runner.invoke(config.config.commands["sflow"].
            commands["interface"].commands["disable"], ["all"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        # verify in configDb
        sflowSession = db.cfgdb.get_table('SFLOW_SESSION')
        assert sflowSession["all"]["admin_state"] == "down"

    def test_config_enable_all_intf(self):
        db = Db()
        runner = CliRunner()
        obj = {'db':db.cfgdb}
        # enable all interfaces
        result = runner.invoke(config.config.commands["sflow"].commands["interface"].
                               commands["enable"], ["all"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        
        # verify in configDb
        sflowSession = db.cfgdb.get_table('SFLOW_SESSION')
        assert sflowSession["all"]["admin_state"] == "up"

    def test_config_sflow_intf_sample_rate_default(self):
        db = Db()
        runner = CliRunner()
        obj = {'db':db.cfgdb}

        # mock interface_name_is_valid
        config.interface_name_is_valid = mock.MagicMock(return_value = True)

        result_out1 = runner.invoke(show.cli.commands["sflow"].commands["interface"], [], obj=Db())
        print(result_out1.exit_code, result_out1.output)
        assert result_out1.exit_code == 0
        
        # set sample-rate to 2500
        result = runner.invoke(config.config.commands["sflow"].
            commands["interface"].commands["sample-rate"],
            ["Ethernet2", "2500"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        # we can not use 'show sflow interface', becasue 'show sflow interface'
        # gets data from appDB, we need to fetch data from configDB for verification
        sflowSession = db.cfgdb.get_table('SFLOW_SESSION')
        assert sflowSession["Ethernet2"]["sample_rate"] == "2500"

        # set sample-rate to default
        result = runner.invoke(config.config.commands["sflow"].
            commands["interface"].commands["sample-rate"],
            ["Ethernet2", "default"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        result_out2 = runner.invoke(show.cli.commands["sflow"].commands["interface"], [], obj=Db())
        print(result_out2.exit_code, result_out2.output)
        assert result_out2.exit_code == 0
        assert result_out1.output == result_out2.output

        return

    def test_config_sflow_sample_direction(self):
        # config sflow sample-direction<rx|tx|both>
        db = Db()
        runner = CliRunner()
        obj = {'db':db.cfgdb}

        #Sample direction : Invalid
        result = runner.invoke(config.config.commands["sflow"].commands["sample-direction"], ["NA"], obj=obj)
        print(result.output)
        expected = "Error: Direction NA is invalid"
        assert expected in result.output

        #disable
        result = runner.invoke(config.config.commands["sflow"].commands["sample-direction"], ["tx"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        # change the output
        global show_sflow_output
        show_sflow_output_tx = show_sflow_output.replace(
            'Sample Direction:     both',
            'Sample Direction:     tx')

        show_sflow_output_rx = show_sflow_output.replace(
            'Sample Direction:     both',
            'Sample Direction:     rx')

        # run show and check
        result = runner.invoke(show.cli.commands["sflow"], [], obj=db)
        print(result.exit_code, result.output, show_sflow_output_tx)
        assert result.exit_code == 0
        assert result.output == show_sflow_output_tx

        # sample-direction rx
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock()) as mock_run_command:
            result = runner.invoke(config.config.commands["sflow"].commands["sample-direction"], ["rx"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0

        # run show and check
        result = runner.invoke(show.cli.commands["sflow"], [], obj=db)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert result.output == show_sflow_output_rx

        return

    def test_config_all_intf_sample_direction(self):
        db = Db()
        runner = CliRunner()
        obj = {'db':db.cfgdb}

        # set all direction to both
        result = runner.invoke(config.config.commands["sflow"].
            commands["interface"].commands["sample-direction"], ["all","both"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        # verify in configDb
        sflowSession = db.cfgdb.get_table('SFLOW_SESSION')
        assert sflowSession["all"]["sample_direction"] == "both"

        # set all direction to tx
        result = runner.invoke(config.config.commands["sflow"].
            commands["interface"].commands["sample-direction"], ["all","tx"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        # verify in configDb
        sflowSession = db.cfgdb.get_table('SFLOW_SESSION')
        assert sflowSession["all"]["sample_direction"] == "tx"

        # set all direction to rx
        result = runner.invoke(config.config.commands["sflow"].
            commands["interface"].commands["sample-direction"], ["all","rx"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        # verify in configDb
        sflowSession = db.cfgdb.get_table('SFLOW_SESSION')
        assert sflowSession["all"]["sample_direction"] == "rx"

        return

    def test_config_sflow_intf_sample_direction(self):
        db = Db()
        runner = CliRunner()
        obj = {'db':db.cfgdb}

        # mock interface_name_is_valid
        config.interface_name_is_valid = mock.MagicMock(return_value = True)

        # set sample-direction to Invalid
        result = runner.invoke(config.config.commands["sflow"].
            commands["interface"].commands["sample-direction"],
            ["Ethernet2", "NA"], obj=obj)
        print(result.exit_code, result.output)
        expected = "Error: Direction NA is invalid"
        assert result.exit_code == 2
        assert expected in result.output

        # set sample-direction to both
        result = runner.invoke(config.config.commands["sflow"].
            commands["interface"].commands["sample-direction"],
            ["Ethernet2", "both"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        # we can not use 'show sflow interface', becasue 'show sflow interface'
        # gets data from appDB, we need to fetch data from configDB for verification
        sflowSession = db.cfgdb.get_table('SFLOW_SESSION')
        assert sflowSession["Ethernet2"]["sample_direction"] == "both"

        # set sample-direction to tx
        result = runner.invoke(config.config.commands["sflow"].
            commands["interface"].commands["sample-direction"],
            ["Ethernet2", "tx"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        # we can not use 'show sflow interface', becasue 'show sflow interface'
        # gets data from appDB, we need to fetch data from configDB for verification
        sflowSession = db.cfgdb.get_table('SFLOW_SESSION')
        assert sflowSession["Ethernet2"]["sample_direction"] == "tx"

        # set sample-direction to rx
        result = runner.invoke(config.config.commands["sflow"].
            commands["interface"].commands["sample-direction"],
            ["Ethernet2", "rx"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        # we can not use 'show sflow interface', becasue 'show sflow interface'
        # gets data from appDB, we need to fetch data from configDB for verification
        sflowSession = db.cfgdb.get_table('SFLOW_SESSION')
        assert sflowSession["Ethernet2"]["sample_direction"] == "rx"

        return

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

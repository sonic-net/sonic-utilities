import os
import re
import pytest
import subprocess
import traceback
import mock

from click.testing import CliRunner
from jsonpatch import JsonPatchConflict

import config.main as config
import config.validated_config_db_connector as validated_config_db_connector
import show.main as show
import clear.main as clear
from utilities_common.db import Db
from mock import patch

EXPECTED_SHOW_LACP_INFO_PORTCHANNEL_WITH_NO_MEMBERS_OUTPUT = """\
--------------------------------------------------------------------------
LAG: PortChannel0004 is up, mode LACP
Minimum number of links to bring PortChannel up is 1
address is 52:54:00:f2:e1:23
Fallback: Disabled
Fast_rate: Disabled
Retry_count_feature: Enabled
Retry_count: 3
MTU: 9100
LACP: mode ACTIVE, priority 65535, address 52:54:00:f2:e1:23
LAG MEMBER: None
--------------------------------------------------------------------------
"""

EXPECTED_SHOW_LACP_INFO_PORTCHANNEL_WITH_DESELECTED_MEMBER_OUTPUT = """\
--------------------------------------------------------------------------
LAG: PortChannel0001 is down, mode LACP
Minimum number of links to bring PortChannel up is 1
address is 52:54:00:f2:e1:23
Fallback: Disabled
Fast_rate: Disabled
Retry_count_feature: Enabled
Retry_count: 3
MTU: 9100
LACP: mode ACTIVE, priority 65535, address 52:54:00:f2:e1:23
LAG MEMBER: Ethernet112(deselected)
    LACP Actor: port 113, address 52:54:00:f2:e1:23, key 11
    LACP Actor State: (Act, Agg, Def)
    LACP Partner: port 0, address 00:00:00:00:00:00, key 0
    LACP Partner State: (Tmo)
    Statistics:
        lacpdu_illegal_pkts: 0
        lacpdu_rx_stats: 0
        lacpdu_tx_stats: 1103
        last rx lacpdu at: N/A
        last tx lacpdu at: 2025-06-26T07:54:23.926776098Z
--------------------------------------------------------------------------
"""

EXPECTED_SHOW_LACP_INFO_PORTCHANNEL_WITH_SELECTED_MEMBER_OUTPUT = """\
--------------------------------------------------------------------------
LAG: PortChannel0002 is up, mode LACP
Minimum number of links to bring PortChannel up is 1
address is 52:54:00:f2:e1:23
Fallback: Disabled
Fast_rate: Disabled
Retry_count_feature: Enabled
Retry_count: 3
MTU: 9100
LACP: mode ACTIVE, priority 65535, address 52:54:00:f2:e1:23
LAG MEMBER: Ethernet116(selected)
    LACP Actor: port 117, address 52:54:00:f2:e1:23, key 12
    LACP Actor State: (Act, Agg, Sync, Coll, Dist)
    LACP Partner: port 1, address 1e:af:77:fc:79:ee, key 13
    LACP Partner State: (Act, Agg, Sync, Coll, Dist)
    Statistics:
        lacpdu_illegal_pkts: 0
        lacpdu_rx_stats: 1003
        lacpdu_tx_stats: 1103
        last rx lacpdu at: 2025-06-26T07:54:23.926776098Z
        last tx lacpdu at: 2025-06-26T07:54:23.926776098Z
--------------------------------------------------------------------------
"""

class TestPortChannel(object):

    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

    @patch("config.main.is_portchannel_present_in_db", mock.Mock(return_value=False))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=ValueError))
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    def test_add_portchannel_with_invalid_name_yang_validation(self):
        config.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["portchannel"].commands["add"], ["PortChan005"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChan005 is invalid!, name should have prefix 'PortChannel' and suffix '<0-9999>'" in result.output

    def test_add_portchannel_with_invalid_name_adhoc_validation(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel with invalid name
        result = runner.invoke(config.config.commands["portchannel"].commands["add"], ["PortChan005"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChan005 is invalid!, name should have prefix 'PortChannel' and suffix '<0-9999>' " \
            "and its length should not exceed 15 characters" in result.output

        result = runner.invoke(config.config.commands["portchannel"].commands["add"], ["PortChanl00000"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChanl00000 is invalid!, name should have prefix 'PortChannel' and suffix '<0-9999>' and " \
            "its length should not exceed 15 characters" in result.output

    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=JsonPatchConflict))
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    def test_delete_nonexistent_portchannel_yang_validation(self):
        config.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # delete a portchannel with invalid name
        result = runner.invoke(config.config.commands["portchannel"].commands["del"], ["PortChan005"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "PortChan005 is not present" in result.output

    def test_delete_portchannel_with_invalid_name_adhoc_validation(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # delete a portchannel with invalid name
        result = runner.invoke(config.config.commands["portchannel"].commands["del"], ["PortChan005"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChan005 is invalid!, name should have prefix 'PortChannel' and suffix '<0-9999>'" in result.output

    def test_add_existing_portchannel_again(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel which is already created
        result = runner.invoke(config.config.commands["portchannel"].commands["add"], ["PortChannel0001"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel0001 already exists!" in result.output

    def test_delete_non_existing_portchannel_adhoc_validation(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # delete a portchannel which is not present
        result = runner.invoke(config.config.commands["portchannel"].commands["del"], ["PortChannel0005"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel0005 is not present." in result.output

    @pytest.mark.parametrize("fast_rate", ["False", "True", "false", "true"])
    def test_add_portchannel_with_fast_rate_adhoc_validation(self, fast_rate):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel with fats rate
        result = runner.invoke(config.config.commands["portchannel"].commands["add"], ["PortChannel0005", "--fast-rate", fast_rate], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    @pytest.mark.parametrize("fast_rate", ["Fls", "tru"])
    def test_add_portchannel_with_invalid_fast_rate(self, fast_rate):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel with invalid fats rate
        result = runner.invoke(config.config.commands["portchannel"].commands["add"], ["PortChannel0005", "--fast-rate", fast_rate], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert 'Invalid value for "--fast-rate"'  in result.output

    def test_add_portchannel_member_with_invalid_name(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel member with invalid portchannel name
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChan005", "Ethernet0"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChan005 is invalid!, name should have prefix 'PortChannel' and suffix '<0-9999>'" in result.output

    def test_delete_portchannel_member_with_invalid_name(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # delete a portchannel member with invalid portchannel name
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["del"], ["PortChan005", "Ethernet0"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChan005 is invalid!, name should have prefix 'PortChannel' and suffix '<0-9999>'" in result.output

    def test_add_non_existing_portchannel_member(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel member with portchannel is not yet created
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChannel0005", "Ethernet0"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel0005 is not present." in result.output

    def test_delete_non_existing_portchannel_member(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # delete a portchannel member with portchannel is not yet created
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["del"], ["PortChannel0005", "Ethernet0"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel0005 is not present." in result.output

    def test_add_portchannel_member_which_has_ipaddress(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel member with port which has ip-address
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChannel1001", "Ethernet0"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error:  Ethernet0 has ip address configured" in result.output

    def test_add_portchannel_member_which_has_subintf(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel member with port which has ip-address
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChannel1001", "Ethernet36"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        print(result.output)
        assert "Error:  Ethernet36 has subinterfaces configured" in result.output

    def test_add_portchannel_member_which_is_member_of_vlan(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel member with port which is member of Vlan
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChannel1001", "Ethernet24"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet24 Interface configured as VLAN_MEMBER under vlan : Vlan2000" in result.output

    def test_add_portchannel_member_which_is_member_of_another_po(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel member with port which is member of another PO
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChannel1001", "Ethernet116"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet116 Interface is already member of PortChannel0002 " in result.output

    def test_delete_portchannel_member_which_is_member_of_another_po(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # delete a portchannel member with port which is member of another PO
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["del"], ["PortChannel1001", "Ethernet116"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet116 is not a member of portchannel PortChannel1001" in result.output

    def test_add_portchannel_member_with_acl_bindngs(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb, 'db_wrap':db, 'namespace':''}

        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChannel0002", "Ethernet100"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Port Ethernet100 is already bound to following ACL_TABLES:" in result.output

    def test_add_portchannel_member_with_pbh_bindngs(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb, 'db_wrap':db, 'namespace':''}

        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChannel0002", "Ethernet60"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Port Ethernet60 is already bound to following PBH_TABLES:" in result.output

    def test_delete_portchannel_which_is_member_of_a_vlan(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # try to delete the portchannel when its member of a vlan
        result = runner.invoke(config.config.commands["portchannel"].commands["del"], ["PortChannel1001"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "PortChannel1001 has vlan Vlan4000 configured, remove vlan membership to proceed" in result.output

    def test_get_invalid_portchannel_retry_count(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # get the retry count of a portchannel with an invalid portchannel name
        result = runner.invoke(config.config.commands["portchannel"].commands["retry-count"].commands["get"], ["Ethernet48"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet48 is invalid!" in result.output

    def test_set_invalid_portchannel_retry_count(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # set the retry count of a portchannel with an invalid portchannel name
        result = runner.invoke(config.config.commands["portchannel"].commands["retry-count"].commands["set"], ["Ethernet48", "5"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet48 is invalid!" in result.output

    def test_get_non_existing_portchannel_retry_count(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # get the retry count of a portchannel with portchannel not yet created
        result = runner.invoke(config.config.commands["portchannel"].commands["retry-count"].commands["get"], ["PortChannel0005"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel0005 is not present." in result.output

    def test_set_non_existing_portchannel_retry_count(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # set the retry count of a portchannel with portchannel not yet created
        result = runner.invoke(config.config.commands["portchannel"].commands["retry-count"].commands["set"], ["PortChannel0005", "5"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel0005 is not present." in result.output

    originalSubprocessPopen = subprocess.Popen

    class SubprocessMock:
        def __init__(self, *args, **kwargs):
            self.retryCountEnabled = True
            self.timeout = False

        def __call__(self, *args, **kwargs):
            stdoutResult = ""
            stderrResult = ""
            rc = 0

            commandArgs = args[0]
            if commandArgs[0] != "teamdctl":
                return TestPortChannel.originalSubprocessPopen(*args, **kwargs)
            if self.timeout:
                return TestPortChannel.originalSubprocessPopen(["sleep", "90"], **kwargs)
            if commandArgs[5] == "runner.enable_retry_count_feature":
                return TestPortChannel.originalSubprocessPopen(["echo", "true" if self.retryCountEnabled else "false"], **kwargs)
            elif commandArgs[5] == "runner.retry_count":
                if commandArgs[4] == "get":
                    return TestPortChannel.originalSubprocessPopen(["echo", "3"], **kwargs)
                elif commandArgs[4] == "set":
                    return TestPortChannel.originalSubprocessPopen(["echo", ""], **kwargs)
                else:
                    return TestPortChannel.originalSubprocessPopen(["false"], **kwargs)
            else:
                return TestPortChannel.originalSubprocessPopen(["false"], **kwargs)

    @patch("subprocess.Popen", new_callable=SubprocessMock)
    def test_get_portchannel_retry_count_disabled(self, subprocessMock):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        subprocessMock.retryCountEnabled = False

        # get the retry count of a portchannel, but when the retry count feature is disabled
        result = runner.invoke(config.config.commands["portchannel"].commands["retry-count"].commands["get"], ["PortChannel1001"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Retry count feature is not enabled!" in result.output

    @patch("subprocess.Popen", new_callable=SubprocessMock)
    def test_set_portchannel_retry_count_disabled(self, subprocessMock):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        subprocessMock.retryCountEnabled = False

        # set the retry count of a portchannel, but when the retry count feature is disabled
        result = runner.invoke(config.config.commands["portchannel"].commands["retry-count"].commands["set"], ["PortChannel1001", "5"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Retry count feature is not enabled!" in result.output

    @patch("subprocess.Popen", new_callable=SubprocessMock)
    def test_get_portchannel_retry_count_timeout(self, subprocessMock):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        subprocessMock.retryCountEnabled = True
        subprocessMock.timeout = True

        # get the retry count of a portchannel
        result = runner.invoke(config.config.commands["portchannel"].commands["retry-count"].commands["get"], ["PortChannel1001"], obj=obj)
        # expect a timeout failure
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Unable to get the retry count" in result.output

    @patch("subprocess.Popen", new_callable=SubprocessMock)
    def test_set_portchannel_retry_count_timeout(self, subprocessMock):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        subprocessMock.retryCountEnabled = True
        subprocessMock.timeout = True

        # set the retry count of a portchannel
        result = runner.invoke(config.config.commands["portchannel"].commands["retry-count"].commands["set"], ["PortChannel1001", "5"], obj=obj)
        # expect a timeout failure
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Unable to set the retry count" in result.output

    @patch("subprocess.Popen", new_callable=SubprocessMock)
    def test_get_portchannel_retry_count(self, subprocessMock):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        subprocessMock.retryCountEnabled = True

        # get the retry count of a portchannel
        result = runner.invoke(config.config.commands["portchannel"].commands["retry-count"].commands["get"], ["PortChannel1001"], obj=obj)
        # output has been mocked
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output.strip() == "3"

    @patch("subprocess.Popen", new_callable=SubprocessMock)
    def test_set_portchannel_retry_count(self, subprocessMock):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        subprocessMock.retryCountEnabled = True

        # set the retry count of a portchannel
        result = runner.invoke(config.config.commands["portchannel"].commands["retry-count"].commands["set"], ["PortChannel1001", "5"], obj=obj)
        # output has been mocked
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == ""

    def test_show_interfaces_portchannel_info_portchannel_with_no_members(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands["interfaces"].commands["portchannel"].commands["info"],
                               ["PortChannel0004"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert (re.sub(r'\s+', ' ', result.output.strip())) == (re.sub(
                r'\s+', ' ', EXPECTED_SHOW_LACP_INFO_PORTCHANNEL_WITH_NO_MEMBERS_OUTPUT.strip()))

    def test_show_interfaces_portchannel_info_portchannel_with_deselected_member(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands["interfaces"].commands["portchannel"].commands["info"],
                               ["PortChannel0001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert (re.sub(r'\s+', ' ', result.output.strip())) == (re.sub(
                r'\s+', ' ', EXPECTED_SHOW_LACP_INFO_PORTCHANNEL_WITH_DESELECTED_MEMBER_OUTPUT.strip()))

    def test_show_interfaces_portchannel_info_portchannel_with_selected_member(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands["interfaces"].commands["portchannel"].commands["info"],
                               ["PortChannel0002"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert (re.sub(r'\s+', ' ', result.output.strip())) == (re.sub(
                r'\s+', ' ', EXPECTED_SHOW_LACP_INFO_PORTCHANNEL_WITH_SELECTED_MEMBER_OUTPUT.strip()))

    def test_show_interfaces_portchannel_info_portchannel_non_exists(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands["interfaces"].commands["portchannel"].commands["info"],
                               ["PortChannel107"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert "No such PortChannel interface" in result.output

    def test_show_interfaces_portchannel_info(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands["interfaces"].commands["portchannel"].commands["info"],
                               [], obj=db, catch_exceptions=False)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    @patch('clear.portchannel.clicommon.run_command')
    def test_clear_portchannel_statistics(self, run_command):
        runner = CliRunner()
        db = Db()
        # Clearing stats for all LAGs
        result = runner.invoke(clear.cli.commands['portchannel'].commands['statistics'], obj=db, catch_exceptions=False)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # Clearing stats for specific PortChannel - Exists
        result = runner.invoke(clear.cli.commands['portchannel'].commands['statistics'], ['PortChannel0001'], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        run_command.assert_called_with('sudo teamdctl PortChannel0001 clear statistics', shell=True)
        run_command.reset_mock()

        # Clearing stats for specific PortChannel member - Exists
        result = runner.invoke(clear.cli.commands['portchannel'].commands['statistics'],
                               ['PortChannel0001', 'Ethernet112'], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        run_command.assert_called_with('sudo teamdctl PortChannel0001 clear statistics port Ethernet112', shell=True)
        run_command.reset_mock()

        # Clearing stats for specific PortChannel - Not Exists
        result = runner.invoke(clear.cli.commands['portchannel'].commands['statistics'], ['PortChannel107'], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        if "No such portchannel interface" in result.output:
            assert not run_command.called, "run_command should not be called when PortChannel is missing"

        # Clearing stats for specific PortChannel member - Not Exists
        result = runner.invoke(clear.cli.commands['portchannel'].commands['statistics'],
                               ['PortChannel0001', 'Ethernet4'], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        if "No such portchannel or portchannel member interface" in result.output:
            assert not run_command.called, "run_command should not be called when PortChannel is missing"

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")

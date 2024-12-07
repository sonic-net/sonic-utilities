import os
from click.testing import CliRunner
from utilities_common.db import Db
from unittest import mock
from mock import patch

import config.main as config
import show.main as show

show_interfaces_dhcp_rate_limit_output = """\
Interface    DHCP Mitigation Rate
-----------  ----------------------
Ethernet0    300
Ethernet4    300
Ethernet8    300
Ethernet12   300
Ethernet16   300
Ethernet20   300
Ethernet24   300
Ethernet28   300
Ethernet32   300
Ethernet36   300
Ethernet40   300
Ethernet44   300
Ethernet48   300
Ethernet52   300
Ethernet56   300
Ethernet60   300
Ethernet64   300
Ethernet68   300
Ethernet72
Ethernet76   300
Ethernet80   300
Ethernet84   300
Ethernet88   300
Ethernet92   300
Ethernet96   300
Ethernet100  300
Ethernet104  300
Ethernet108  300
Ethernet112  300
Ethernet116  300
Ethernet120  300
Ethernet124  300
"""

show_dhcp_rate_limit_in_alias_mode_output = """\
Interface    DHCP Mitigation Rate
-----------  ----------------------
etp1         300
etp2         300
etp3         300
etp4         300
etp5         300
etp6         300
etp7         300
etp8         300
etp9         300
etp10        300
etp11        300
etp12        300
etp13        300
etp14        300
etp15        300
etp16        300
etp17        300
etp18        300
etp19
etp20        300
etp21        300
etp22        300
etp23        300
etp24        300
etp25        300
etp26        300
etp27        300
etp28        300
etp29        300
etp30        300
etp31        300
etp32        300
"""

show_dhcp_rate_limit_single_interface_output = """\
Interface      DHCP Mitigation Rate
-----------  ----------------------
Ethernet0                       300
"""


class TestDHCPRate(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

    def test_config_dhcp_rate_add_on_portchannel(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}
        result = runner.invoke(config.config.commands["interface"].commands["dhcp-mitigation-rate"].commands["add"],
                               ["PortChannel0001", "20"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel0001 is a PortChannel!" in result.output

    def test_config_dhcp_rate_del_on_portchannel(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}
        result = runner.invoke(config.config.commands["interface"].commands["dhcp-mitigation-rate"].commands["del"],
                               ["PortChannel0001", "20"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel0001 is a PortChannel!" in result.output

    def test_config_dhcp_rate_add_on_invalid_port(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}
        intf = "test_fail_case"
        result = runner.invoke(config.config.commands["interface"].commands["dhcp-mitigation-rate"].commands["add"],
                               [intf, "20"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: {} does not exist".format(intf) in result.output

    def test_config_dhcp_rate_del_on_invalid_port(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}
        intf = "test_fail_case"
        result = runner.invoke(config.config.commands["interface"].commands["dhcp-mitigation-rate"].commands["del"],
                               [intf, "20"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: {} does not exist".format(intf) in result.output

    def test_config_dhcp_rate_add_invalid_rate(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}
        result = runner.invoke(config.config.commands["interface"].commands["dhcp-mitigation-rate"].commands["add"],
                               ["Ethernet0", "0"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: DHCP rate limit is not valid. \nIt must be greater than 0." in result.output

    def test_config_dhcp_rate_del_invalid_rate(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}
        result = runner.invoke(config.config.commands["interface"].commands["dhcp-mitigation-rate"].commands["del"],
                               ["Ethernet0", "0"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: DHCP rate limit is not valid. \nIt must be greater than 0." in result.output

    def test_config_dhcp_rate_add_rate_with_exist_rate(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}
        result = runner.invoke(config.config.commands["interface"].commands["dhcp-mitigation-rate"].commands["add"],
                               ["Ethernet0", "20"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet0 has DHCP rate limit configured. \nRemove it to add new DHCP rate limit." \
            in result.output

    def test_config_dhcp_rate_del_rate_with_nonexist_rate(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}
        result = runner.invoke(config.config.commands["interface"].commands["dhcp-mitigation-rate"].commands["del"],
                               ["Ethernet0", "20"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: 20 DHCP rate limit does not exist on Ethernet0." in result.output

    def test_config_dhcp_rate_add_del_with_no_rate(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}
        result = runner.invoke(config.config.commands["interface"].commands["dhcp-mitigation-rate"].commands["del"],
                               ["Ethernet72", "80"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: 80 DHCP rate limit does not exist on Ethernet72." in result.output

        result = runner.invoke(config.config.commands["interface"].commands["dhcp-mitigation-rate"].commands["add"],
                               ["Ethernet72", "80"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    def test_config_dhcp_rate_add_del(self):
        db = Db()
        runner = CliRunner()
        # Remove default DHCP rate limit from Ethernet24
        result = runner.invoke(config.config.commands["interface"].commands["dhcp-mitigation-rate"].commands["del"],
                               ["Ethernet24", "300"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        # Remove default DHCP rate limit from Ethernet32
        result = runner.invoke(config.config.commands["interface"].commands["dhcp-mitigation-rate"].commands["del"],
                               ["Ethernet32", "300"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        # Add DHCP rate limit 45 on Ethernet32
        result = runner.invoke(config.config.commands["interface"].commands["dhcp-mitigation-rate"].commands["add"],
                               ["Ethernet32", "45"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    def test_config_dhcp_rate_add_del_in_alias_mode(self):
        db = Db()
        runner = CliRunner()
        # Enable alias mode by setting environment variable
        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        interface_alias = "etp1"
        # Remove default 300 rate limit from the interface using alias
        result = runner.invoke(config.config.commands["interface"].commands["dhcp-mitigation-rate"].commands["del"],
                               [interface_alias, "300"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        # Remove the 300 rate limit again, expecting an error
        result = runner.invoke(config.config.commands["interface"].commands["dhcp-mitigation-rate"].commands["del"],
                               [interface_alias, "300"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "300 DHCP rate limit does not exist on Ethernet0" in result.output
        # Add new rate limit of 80 to the interface using alias
        result = runner.invoke(config.config.commands["interface"].commands["dhcp-mitigation-rate"].commands["add"],
                               [interface_alias, "80"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        # Disable alias mode
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"

    def test_config_dhcp_rate_add_on_invalid_interface(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}
        result = runner.invoke(config.config.commands["interface"].commands["dhcp-mitigation-rate"].commands["add"],
                               ["etp33", "20"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: etp33 does not exist" in result.output

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch(
        "config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry",
        mock.Mock(side_effect=ValueError)
        )
    def test_config_dhcp_rate_add_del_with_value_error(self):
        db = Db()
        runner = CliRunner()
        result = runner.invoke(config.config.commands["interface"].commands["dhcp-mitigation-rate"].commands["del"],
                               ["Ethernet84", "300"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.output != 0
        assert "Ethernet84 invalid or does not exist" in result.output

        result = runner.invoke(config.config.commands["interface"].commands["dhcp-mitigation-rate"].commands["add"],
                               ["Ethernet72", "65"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.output != 0
        assert "Ethernet72 invalid or does not exist" in result.output

    def test_show_dhcp_rate_limit(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["dhcp-mitigation-rate"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_interfaces_dhcp_rate_limit_output

    def test_show_dhcp_rate_limit_in_alias_mode(self):
        runner = CliRunner()
        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        # Run show interfaces dhcp-mitigation-rate command
        result = runner.invoke(show.cli.commands["interfaces"].commands["dhcp-mitigation-rate"])
        # Go back to default mode
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_dhcp_rate_limit_in_alias_mode_output

    def test_show_dhcp_rate_limit_single_interface(self):
        runner = CliRunner()
        # Interface to test
        interface_name = "Ethernet0"
        # Run show interfaces dhcp-mitigation-rate <INTERFACE> command with valid interface
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["dhcp-mitigation-rate"], [interface_name])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_dhcp_rate_limit_single_interface_output

    def test_show_dhcp_rate_limit_single_interface_portchannel(self):
        runner = CliRunner()
        # Portchannel interface to test
        portchannel_name = "PortChannel0001"
        # Run show interfaces dhcp-mitigation-rate <INTERFACE> command with valid portchannel
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["dhcp-mitigation-rate"], [portchannel_name])
        print(result.exit_code)
        print(result.output)
        # Assert error message
        assert result.exit_code != 0
        assert f"{portchannel_name} is a PortChannel!" in result.output

    def test_show_dhcp_rate_limit_single_interface_with_nonexist_interface(self):
        runner = CliRunner()
        # Invalid interface name to test
        invalid_interface_name = "etp35"
        # etp35 is a non-existing interface
        # Run show interfaces dhcp-mitigation-rate <INTERFACE> command with invalid interface
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["dhcp-mitigation-rate"], [invalid_interface_name])
        print(result.exit_code)
        print(result.output)
        # Assert error message
        assert result.exit_code != 0
        assert f"{invalid_interface_name} does not exist" in result.output

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")

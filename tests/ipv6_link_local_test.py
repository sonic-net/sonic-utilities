import os

from click.testing import CliRunner

import config.main as config
import show.main as show
from utilities_common.db import Db

show_ipv6_link_local_mode_output="""\
+------------------+----------+
| Interface Name   | Mode     |
+==================+==========+
| Ethernet0        | Disabled |
+------------------+----------+
| Ethernet4        | Disabled |
+------------------+----------+
| Ethernet8        | Disabled |
+------------------+----------+
| Ethernet12       | Disabled |
+------------------+----------+
| Ethernet16       | Disabled |
+------------------+----------+
| Ethernet20       | Disabled |
+------------------+----------+
| Ethernet24       | Disabled |
+------------------+----------+
| Ethernet28       | Disabled |
+------------------+----------+
| Ethernet32       | Disabled |
+------------------+----------+
| Ethernet36       | Disabled |
+------------------+----------+
| Ethernet40       | Enabled  |
+------------------+----------+
| Ethernet44       | Disabled |
+------------------+----------+
| Ethernet48       | Disabled |
+------------------+----------+
| Ethernet52       | Disabled |
+------------------+----------+
| Ethernet56       | Disabled |
+------------------+----------+
| Ethernet60       | Disabled |
+------------------+----------+
| Ethernet64       | Disabled |
+------------------+----------+
| Ethernet68       | Disabled |
+------------------+----------+
| Ethernet72       | Disabled |
+------------------+----------+
| Ethernet76       | Disabled |
+------------------+----------+
| Ethernet80       | Disabled |
+------------------+----------+
| Ethernet84       | Disabled |
+------------------+----------+
| Ethernet88       | Disabled |
+------------------+----------+
| Ethernet92       | Disabled |
+------------------+----------+
| Ethernet96       | Disabled |
+------------------+----------+
| Ethernet100      | Disabled |
+------------------+----------+
| Ethernet104      | Disabled |
+------------------+----------+
| Ethernet108      | Disabled |
+------------------+----------+
| Ethernet112      | Disabled |
+------------------+----------+
| Ethernet116      | Disabled |
+------------------+----------+
| Ethernet120      | Disabled |
+------------------+----------+
| Ethernet124      | Disabled |
+------------------+----------+
| PortChannel1001  | Disabled |
+------------------+----------+
| PortChannel0001  | Disabled |
+------------------+----------+
| PortChannel0002  | Disabled |
+------------------+----------+
| PortChannel0003  | Disabled |
+------------------+----------+
| PortChannel0004  | Disabled |
+------------------+----------+
| Vlan1000         | Disabled |
+------------------+----------+
| Vlan2000         | Disabled |
+------------------+----------+
| Vlan3000         | Disabled |
+------------------+----------+
| Vlan4000         | Disabled |
+------------------+----------+
"""

class TestIPv6LinkLocal(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

    def test_show_ipv6_link_local_mode(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # show ipv6 link-local-mode output
        result = runner.invoke(show.cli.commands["ipv6"].commands["link-local-mode"], [], obj=obj)
        print(result.output)
        assert result.output == show_ipv6_link_local_mode_output

    def test_config_enable_disable_ipv6_link_local_on_physical_interface(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # Enable ipv6 link local on Ethernet0
        result = runner.invoke(config.config.commands["interface"].commands["ipv6"].commands["enable"].commands["use-link-local-only"], ["Ethernet0"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == ''

        # Disable ipv6 link local on Ethernet0
        result = runner.invoke(config.config.commands["interface"].commands["ipv6"].commands["disable"].commands["use-link-local-only"], ["Ethernet0"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == ''

    def test_config_enable_disable_ipv6_link_local_on_portchannel_interface(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # Enable ipv6 link local on PortChannel0001
        result = runner.invoke(config.config.commands["interface"].commands["ipv6"].commands["enable"].commands["use-link-local-only"], ["PortChannel0001"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == ''

        # Disable ipv6 link local on PortChannel0001
        result = runner.invoke(config.config.commands["interface"].commands["ipv6"].commands["disable"].commands["use-link-local-only"], ["PortChannel0001"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == ''

    def test_config_enable_disable_ipv6_link_local_on_invalid_interface(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # Enable ipv6 link local on PortChannel1
        result = runner.invoke(config.config.commands["interface"].commands["ipv6"].commands["enable"].commands["use-link-local-only"], ["PortChannel1"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert 'Error: Interface name PortChannel1 is invalid. Please enter a valid interface name!!' in result.output

        # Disable ipv6 link local on Ethernet500
        result = runner.invoke(config.config.commands["interface"].commands["ipv6"].commands["disable"].commands["use-link-local-only"], ["Ethernet500"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert 'Error: Interface name Ethernet500 is invalid. Please enter a valid interface name!!' in result.output

    def test_config_enable_disable_ipv6_link_local_on_interface_which_is_member_of_vlan(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # Enable ipv6 link local on Ethernet16
        result = runner.invoke(config.config.commands["interface"].commands["ipv6"].commands["enable"].commands["use-link-local-only"], ["Ethernet16"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert 'Error: Ethernet16 is configured as a member of vlan. Cannot configure the IPv6 link local mode!' in result.output

        # Disable ipv6 link local on Ethernet16
        result = runner.invoke(config.config.commands["interface"].commands["ipv6"].commands["disable"].commands["use-link-local-only"], ["Ethernet16"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert 'Error: Ethernet16 is configured as a member of vlan. Cannot configure the IPv6 link local mode!' in result.output

    def test_config_enable_disable_ipv6_link_local_on_interface_which_is_member_of_portchannel(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}
        
        # Enable ipv6 link local on Ethernet32
        result = runner.invoke(config.config.commands["interface"].commands["ipv6"].commands["enable"].commands["use-link-local-only"], ["Ethernet32"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert 'Error: Ethernet32 is configured as a member of portchannel. Cannot configure the IPv6 link local mode!' in result.output

        # Disable ipv6 link local on Ethernet32
        result = runner.invoke(config.config.commands["interface"].commands["ipv6"].commands["disable"].commands["use-link-local-only"], ["Ethernet32"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert 'Error: Ethernet32 is configured as a member of portchannel. Cannot configure the IPv6 link local mode!' in result.output

    def test_config_enable_disable_ipv6_link_local_on_all_valid_interfaces(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # Enable ipv6 link local on all interfaces
        result = runner.invoke(config.config.commands["ipv6"].commands["enable"].commands["link-local"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == ''

        # Disable ipv6 link local on all interfaces
        result = runner.invoke(config.config.commands["ipv6"].commands["disable"].commands["link-local"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == ''

    def test_vlan_member_add_on_link_local_interface(self):
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb, 'namespace':db.db.namespace}

        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"], ["4000", "Ethernet40"], obj=obj)
        print(result.output)
        assert result.exit_code != 0
        assert 'Error: Ethernet40 is a router interface!' in result.output

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")


import os
import traceback
import pytest
from unittest import mock

from click.testing import CliRunner

import config.main as config
import show.main as show
from utilities_common.db import Db
from importlib import reload
import utilities_common.bgp_util as bgp_util

IP_VERSION_PARAMS_MAP = {
    "ipv4": {
        "table": "VLAN"
    },
    "ipv6": {
        "table": "DHCP_RELAY"
    }
}

show_vlan_brief_output="""\
+-----------+-----------------+-----------------+----------------+-------------+
|   VLAN ID | IP Address      | Ports           | Port Tagging   | Proxy ARP   |
+===========+=================+=================+================+=============+
|      1000 | 192.168.0.1/21  | Ethernet4       | untagged       | disabled    |
|           | fc02:1000::1/64 | Ethernet8       | untagged       |             |
|           |                 | Ethernet12      | untagged       |             |
|           |                 | Ethernet16      | untagged       |             |
+-----------+-----------------+-----------------+----------------+-------------+
|      2000 | 192.168.0.10/21 | Ethernet24      | untagged       | enabled     |
|           | fc02:1011::1/64 | Ethernet28      | untagged       |             |
+-----------+-----------------+-----------------+----------------+-------------+
|      3000 |                 |                 |                | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      4000 |                 | PortChannel1001 | tagged         | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
"""

show_vlan_brief_in_alias_mode_output="""\
+-----------+-----------------+-----------------+----------------+-------------+
|   VLAN ID | IP Address      | Ports           | Port Tagging   | Proxy ARP   |
+===========+=================+=================+================+=============+
|      1000 | 192.168.0.1/21  | etp2            | untagged       | disabled    |
|           | fc02:1000::1/64 | etp3            | untagged       |             |
|           |                 | etp4            | untagged       |             |
|           |                 | etp5            | untagged       |             |
+-----------+-----------------+-----------------+----------------+-------------+
|      2000 | 192.168.0.10/21 | etp7            | untagged       | enabled     |
|           | fc02:1011::1/64 | etp8            | untagged       |             |
+-----------+-----------------+-----------------+----------------+-------------+
|      3000 |                 |                 |                | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      4000 |                 | PortChannel1001 | tagged         | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
"""

show_vlan_brief_empty_output="""\
+-----------+-----------------+-----------------+----------------+-------------+
|   VLAN ID | IP Address      | Ports           | Port Tagging   | Proxy ARP   |
+===========+=================+=================+================+=============+
|      2000 | 192.168.0.10/21 | Ethernet24      | untagged       | enabled     |
|           | fc02:1011::1/64 | Ethernet28      | untagged       |             |
+-----------+-----------------+-----------------+----------------+-------------+
|      3000 |                 |                 |                | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      4000 |                 | PortChannel1001 | tagged         | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
"""

show_vlan_brief_with_portchannel_output="""\
+-----------+-----------------+-----------------+----------------+-------------+
|   VLAN ID | IP Address      | Ports           | Port Tagging   | Proxy ARP   |
+===========+=================+=================+================+=============+
|      1000 | 192.168.0.1/21  | Ethernet4       | untagged       | disabled    |
|           | fc02:1000::1/64 | Ethernet8       | untagged       |             |
|           |                 | Ethernet12      | untagged       |             |
|           |                 | Ethernet16      | untagged       |             |
|           |                 | PortChannel1001 | untagged       |             |
+-----------+-----------------+-----------------+----------------+-------------+
|      2000 | 192.168.0.10/21 | Ethernet24      | untagged       | enabled     |
|           | fc02:1011::1/64 | Ethernet28      | untagged       |             |
+-----------+-----------------+-----------------+----------------+-------------+
|      3000 |                 |                 |                | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      4000 |                 | PortChannel1001 | tagged         | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
"""

show_vlan_config_output="""\
Name        VID  Member           Mode
--------  -----  ---------------  --------
Vlan1000   1000  Ethernet4        untagged
Vlan1000   1000  Ethernet8        untagged
Vlan1000   1000  Ethernet12       untagged
Vlan1000   1000  Ethernet16       untagged
Vlan2000   2000  Ethernet24       untagged
Vlan2000   2000  Ethernet28       untagged
Vlan3000   3000
Vlan4000   4000  PortChannel1001  tagged
"""

show_vlan_config_in_alias_mode_output="""\
Name        VID  Member           Mode
--------  -----  ---------------  --------
Vlan1000   1000  etp2             untagged
Vlan1000   1000  etp3             untagged
Vlan1000   1000  etp4             untagged
Vlan1000   1000  etp5             untagged
Vlan2000   2000  etp7             untagged
Vlan2000   2000  etp8             untagged
Vlan3000   3000
Vlan4000   4000  PortChannel1001  tagged
"""

config_add_del_vlan_and_vlan_member_output="""\
+-----------+-----------------+-----------------+----------------+-------------+
|   VLAN ID | IP Address      | Ports           | Port Tagging   | Proxy ARP   |
+===========+=================+=================+================+=============+
|      1000 | 192.168.0.1/21  | Ethernet4       | untagged       | disabled    |
|           | fc02:1000::1/64 | Ethernet8       | untagged       |             |
|           |                 | Ethernet12      | untagged       |             |
|           |                 | Ethernet16      | untagged       |             |
+-----------+-----------------+-----------------+----------------+-------------+
|      1001 |                 | Ethernet20      | untagged       | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      2000 | 192.168.0.10/21 | Ethernet24      | untagged       | enabled     |
|           | fc02:1011::1/64 | Ethernet28      | untagged       |             |
+-----------+-----------------+-----------------+----------------+-------------+
|      3000 |                 |                 |                | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      4000 |                 | PortChannel1001 | tagged         | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
"""


test_config_add_del_multiple_vlan_and_vlan_member_output="""\
+-----------+-----------------+-----------------+----------------+-------------+
|   VLAN ID | IP Address      | Ports           | Port Tagging   | Proxy ARP   |
+===========+=================+=================+================+=============+
|      1000 | 192.168.0.1/21  | Ethernet4       | untagged       | disabled    |
|           | fc02:1000::1/64 | Ethernet8       | untagged       |             |
|           |                 | Ethernet12      | untagged       |             |
|           |                 | Ethernet16      | untagged       |             |
+-----------+-----------------+-----------------+----------------+-------------+
|      1001 |                 | Ethernet20      | tagged         | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      1002 |                 | Ethernet20      | tagged         | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      1003 |                 | Ethernet20      | tagged         | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      2000 | 192.168.0.10/21 | Ethernet24      | untagged       | enabled     |
|           | fc02:1011::1/64 | Ethernet28      | untagged       |             |
+-----------+-----------------+-----------------+----------------+-------------+
|      3000 |                 |                 |                | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      4000 |                 | PortChannel1001 | tagged         | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
"""

test_config_add_del_add_vlans_and_add_all_vlan_member_output="""\
+-----------+-----------------+-----------------+----------------+-------------+
|   VLAN ID | IP Address      | Ports           | Port Tagging   | Proxy ARP   |
+===========+=================+=================+================+=============+
|      1000 | 192.168.0.1/21  | Ethernet4       | untagged       | disabled    |
|           | fc02:1000::1/64 | Ethernet8       | untagged       |             |
|           |                 | Ethernet12      | untagged       |             |
|           |                 | Ethernet16      | untagged       |             |
|           |                 | Ethernet20      | tagged         |             |
+-----------+-----------------+-----------------+----------------+-------------+
|      1001 |                 | Ethernet20      | tagged         | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      1002 |                 | Ethernet20      | tagged         | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      1003 |                 | Ethernet20      | tagged         | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      2000 | 192.168.0.10/21 | Ethernet20      | tagged         | enabled     |
|           | fc02:1011::1/64 | Ethernet24      | untagged       |             |
|           |                 | Ethernet28      | untagged       |             |
+-----------+-----------------+-----------------+----------------+-------------+
|      3000 |                 | Ethernet20      | tagged         | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      4000 |                 | Ethernet20      | tagged         | disabled    |
|           |                 | PortChannel1001 | tagged         |             |
+-----------+-----------------+-----------------+----------------+-------------+
"""

test_config_add_del_add_vlans_and_add_vlans_member_except_vlan_output = """\
+-----------+-----------------+-----------------+----------------+-------------+
|   VLAN ID | IP Address      | Ports           | Port Tagging   | Proxy ARP   |
+===========+=================+=================+================+=============+
|      1000 | 192.168.0.1/21  | Ethernet4       | untagged       | disabled    |
|           | fc02:1000::1/64 | Ethernet8       | untagged       |             |
|           |                 | Ethernet12      | untagged       |             |
|           |                 | Ethernet16      | untagged       |             |
+-----------+-----------------+-----------------+----------------+-------------+
|      1001 |                 | Ethernet20      | tagged         | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      1002 |                 | Ethernet20      | tagged         | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      2000 | 192.168.0.10/21 | Ethernet20      | tagged         | enabled     |
|           | fc02:1011::1/64 | Ethernet24      | untagged       |             |
|           |                 | Ethernet28      | untagged       |             |
+-----------+-----------------+-----------------+----------------+-------------+
|      3000 |                 | Ethernet20      | tagged         | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      4000 |                 | PortChannel1001 | tagged         | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
"""

test_config_add_del_add_vlans_and_add_vlans_member_except_vlan__after_del_member_output = """\
+-----------+-----------------+-----------------+----------------+-------------+
|   VLAN ID | IP Address      | Ports           | Port Tagging   | Proxy ARP   |
+===========+=================+=================+================+=============+
|      1000 | 192.168.0.1/21  | Ethernet4       | untagged       | disabled    |
|           | fc02:1000::1/64 | Ethernet8       | untagged       |             |
|           |                 | Ethernet12      | untagged       |             |
|           |                 | Ethernet16      | untagged       |             |
+-----------+-----------------+-----------------+----------------+-------------+
|      1001 |                 | Ethernet20      | tagged         | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      1002 |                 | Ethernet20      | tagged         | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      2000 | 192.168.0.10/21 | Ethernet24      | untagged       | enabled     |
|           | fc02:1011::1/64 | Ethernet28      | untagged       |             |
+-----------+-----------------+-----------------+----------------+-------------+
|      3000 |                 |                 |                | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      4000 |                 | PortChannel1001 | tagged         | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
"""

test_config_add_del_vlan_and_vlan_member_with_switchport_modes_output = """\
+-----------+-----------------+-----------------+----------------+-------------+
|   VLAN ID | IP Address      | Ports           | Port Tagging   | Proxy ARP   |
+===========+=================+=================+================+=============+
|      1000 | 192.168.0.1/21  | Ethernet4       | untagged       | disabled    |
|           | fc02:1000::1/64 | Ethernet8       | untagged       |             |
|           |                 | Ethernet12      | untagged       |             |
|           |                 | Ethernet16      | untagged       |             |
|           |                 | Ethernet20      | tagged         |             |
+-----------+-----------------+-----------------+----------------+-------------+
|      1001 |                 | Ethernet20      | untagged       | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      2000 | 192.168.0.10/21 | Ethernet24      | untagged       | enabled     |
|           | fc02:1011::1/64 | Ethernet28      | untagged       |             |
+-----------+-----------------+-----------------+----------------+-------------+
|      3000 |                 |                 |                | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      4000 |                 | PortChannel1001 | tagged         | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
"""

config_add_del_vlan_and_vlan_member_in_alias_mode_output="""\
+-----------+-----------------+-----------------+----------------+-------------+
|   VLAN ID | IP Address      | Ports           | Port Tagging   | Proxy ARP   |
+===========+=================+=================+================+=============+
|      1000 | 192.168.0.1/21  | etp2            | untagged       | disabled    |
|           | fc02:1000::1/64 | etp3            | untagged       |             |
|           |                 | etp4            | untagged       |             |
|           |                 | etp5            | untagged       |             |
+-----------+-----------------+-----------------+----------------+-------------+
|      1001 |                 | etp6            | untagged       | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      2000 | 192.168.0.10/21 | etp7            | untagged       | enabled     |
|           | fc02:1011::1/64 | etp8            | untagged       |             |
+-----------+-----------------+-----------------+----------------+-------------+
|      3000 |                 |                 |                | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      4000 |                 | PortChannel1001 | tagged         | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
"""



test_config_add_del_vlan_and_vlan_member_with_switchport_modes_and_change_mode_types_output = """\
+-----------+-----------------+-----------------+----------------+-------------+
|   VLAN ID | IP Address      | Ports           | Port Tagging   | Proxy ARP   |
+===========+=================+=================+================+=============+
|      1000 | 192.168.0.1/21  | Ethernet4       | untagged       | disabled    |
|           | fc02:1000::1/64 | Ethernet8       | untagged       |             |
|           |                 | Ethernet12      | untagged       |             |
|           |                 | Ethernet16      | untagged       |             |
+-----------+-----------------+-----------------+----------------+-------------+
|      1001 |                 |                 |                | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      2000 | 192.168.0.10/21 | Ethernet24      | untagged       | enabled     |
|           | fc02:1011::1/64 | Ethernet28      | untagged       |             |
+-----------+-----------------+-----------------+----------------+-------------+
|      3000 |                 |                 |                | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
|      4000 |                 | PortChannel1001 | tagged         | disabled    |
+-----------+-----------------+-----------------+----------------+-------------+
"""


class TestVlan(object):
    _old_run_bgp_command = None
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        # ensure that we are working with single asic config
        cls._old_run_bgp_command = bgp_util.run_bgp_command
        bgp_util.run_bgp_command = mock.MagicMock(
            return_value=cls.mock_run_bgp_command())
        from .mock_tables import dbconnector
        from .mock_tables import mock_single_asic
        reload(mock_single_asic)
        dbconnector.load_namespace_config()
        print("SETUP")

    def mock_run_bgp_command():
        return ""

    def test_show_vlan(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vlan"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    def test_show_vlan_brief(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vlan_brief_output

    def test_show_vlan_brief_verbose(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], ["--verbose"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vlan_brief_output

    def test_show_vlan_brief_in_alias_mode(self):
        runner = CliRunner()
        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"])
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vlan_brief_in_alias_mode_output

    def test_show_vlan_brief_explicit_proxy_arp_disable(self):
        runner = CliRunner()
        db = Db()

        db.cfgdb.set_entry("VLAN_INTERFACE", "Vlan1000", {"proxy_arp": "disabled"})

    def test_show_vlan_config(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vlan"].commands["config"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vlan_config_output

    def test_show_vlan_config_in_alias_mode(self):
        runner = CliRunner()
        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["vlan"].commands["config"], [])
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vlan_config_in_alias_mode_output

    def test_config_vlan_add_vlan_with_invalid_vlanid(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["4096"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Invalid VLAN ID 4096 (2-4094)" in result.output

    def test_config_vlan_add_vlan_with_exist_vlanid(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1000"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Vlan1000 already exists" in result.output

    def test_config_vlan_del_vlan_with_invalid_vlanid(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["del"], ["4096"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Invalid VLAN ID 4096 (2-4094)" in result.output

    def test_config_vlan_del_vlan_with_nonexist_vlanid(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1001"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Vlan1001 does not exist" in result.output


    def test_config_vlan_add_vlan_with_multiple_vlanids(self, mock_restart_dhcp_relay_service):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["10,20,30,40", "--multiple"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    def test_config_vlan_add_vlan_with_multiple_vlanids_with_range(self, mock_restart_dhcp_relay_service):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["10-20", "--multiple"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    def  test_config_vlan_add_vlan_with_multiple_vlanids_with_range_and_multiple_ids(self, mock_restart_dhcp_relay_service):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["10-15,20,25,30", "--multiple"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    def  test_config_vlan_add_vlan_with_wrong_range(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["15-10", "--multiple"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "15 is greater than 10. List cannot be generated" in result.output

    def  test_config_vlan_add_vlan_range_with_default_vlan(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1-10", "--multiple"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Vlan1 is default vlan" in result.output
    
    def test_config_vlan_add_vlan_is_digit_fail(self):
        runner = CliRunner()
        vid = "test_fail_case"
        result = runner.invoke(config.config.commands["vlan"].commands["add"], [vid])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "{} is not integer".format(vid) in result.output

    def test_config_vlan_add_vlan_is_default_vlan(self):
        runner = CliRunner()
        default_vid = "1"
        vlan = "Vlan{}".format(default_vid)
        result = runner.invoke(config.config.commands["vlan"].commands["add"], [default_vid])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "{} is default VLAN.".format(vlan) in result.output

    def test_config_vlan_del_vlan_does_not_exist(self):
        runner = CliRunner()
        vid = "3010"
        vlan = "Vlan{}".format(vid)
        result = runner.invoke(config.config.commands["vlan"].commands["del"], [vid])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "{} does not exist".format(vlan) in result.output

    def test_config_vlan_add_member_with_invalid_vlanid(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"], ["4096", "Ethernet4"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Invalid VLAN ID 4096 (2-4094)" in result.output

    def test_config_vlan_add_member_with_nonexist_vlanid(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"], ["1001", "Ethernet4"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Vlan1001 does not exist" in result.output

    def test_config_vlan_add_exist_port_member(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"], ["1000", "Ethernet4"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet4 is already a member of Vlan1000" in result.output

    def test_config_vlan_add_nonexist_port_member(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"], ["1000", "Ethernet3"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet3 does not exist" in result.output


    def test_config_vlan_add_nonexist_portchannel_member(self):
        runner = CliRunner()
        #switch port mode for PortChannel1011 to trunk mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"],["trunk", "PortChannel1011"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel1011 does not exist" in result.output

        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"], \
				["1000", "PortChannel1011"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel1011 does not exist" in result.output


    def test_config_vlan_add_portchannel_member(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"], \
				["1000", "PortChannel1001", "--untagged"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0


        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vlan_brief_with_portchannel_output

    def test_config_vlan_add_rif_portchannel_member(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"], \
				["1000", "PortChannel0001", "--untagged"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel0001 is in routed mode!\nUse switchport mode command to change port mode" in result.output

    def test_config_vlan_with_vxlanmap_del_vlan(self, mock_restart_dhcp_relay_service):
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        # create vlan
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1027"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # create vxlan map
        result = runner.invoke(config.config.commands["vxlan"].commands["map"].commands["add"], ["vtep1", "1027", "11027"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # attempt to del vlan with vxlan map, should fail
        result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1027"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: vlan: 1027 can not be removed. First remove vxlan mapping" in result.output

    def test_config_vlan_del_vlan(self, mock_restart_dhcp_relay_service):
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        # del vlan with IP
        result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1000"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Vlan1000 can not be removed. First remove IP addresses assigned to this VLAN" in result.output

        # remove vlan IP`s
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"], ["Vlan1000", "192.168.0.1/21"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"], ["Vlan1000", "fc02:1000::1/64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

        # del vlan with IP
        result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1000"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: VLAN ID 1000 can not be removed. First remove all members assigned to this VLAN." in result.output

        with mock.patch("config.vlan.delete_db_entry") as delete_db_entry:
            vlan_member = db.cfgdb.get_table('VLAN_MEMBER')
            keys = [ (k, v) for k, v in vlan_member if k == 'Vlan{}'.format(1000) ]
            for k,v in keys:    
                result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"], ["1000", v], obj=db)
                print(result.exit_code)
                print(result.output)
                assert result.exit_code == 0

            result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1000"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            delete_db_entry.assert_has_calls([
                mock.call("DHCPv6_COUNTER_TABLE|Vlan1000", mock.ANY, db.db.STATE_DB),
                mock.call("DHCPv6_COUNTER_TABLE|Ethernet4", mock.ANY, db.db.STATE_DB),
                mock.call("DHCPv6_COUNTER_TABLE|Ethernet8", mock.ANY, db.db.STATE_DB),
                mock.call("DHCPv6_COUNTER_TABLE|Ethernet12", mock.ANY, db.db.STATE_DB),
                mock.call("DHCPv6_COUNTER_TABLE|Ethernet16", mock.ANY, db.db.STATE_DB),
                mock.call("DHCP_COUNTER_TABLE|Vlan1000", mock.ANY, db.db.STATE_DB),
                mock.call("DHCP_COUNTER_TABLE|Ethernet4", mock.ANY, db.db.STATE_DB),
                mock.call("DHCP_COUNTER_TABLE|Ethernet8", mock.ANY, db.db.STATE_DB),
                mock.call("DHCP_COUNTER_TABLE|Ethernet12", mock.ANY, db.db.STATE_DB),
                mock.call("DHCP_COUNTER_TABLE|Ethernet16", mock.ANY, db.db.STATE_DB)
            ], any_order=True)

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vlan_brief_empty_output

    def test_config_vlan_del_last_vlan(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.delete_table("VLAN_MEMBER")
        db.cfgdb.delete_table("VLAN_INTERFACE")
        db.cfgdb.set_entry("VLAN", "Vlan2000", None)
        db.cfgdb.set_entry("VLAN", "Vlan3000", None)
        db.cfgdb.set_entry("VLAN", "Vlan4000", None)

        with mock.patch("utilities_common.cli.run_command", mock.Mock(return_value=("", 0))) as mock_run_command:
            result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1000"], obj=db)
            print(result.exit_code)
            print(result.output)
            mock_run_command.assert_has_calls([
                mock.call(['docker', 'exec', '-i', 'swss', 'supervisorctl', 'status', 'ndppd'], ignore_error=True, return_cmd=True),
                mock.call(['docker', 'exec', '-i', 'swss', 'supervisorctl', 'stop', 'ndppd'], ignore_error=True, return_cmd=True),
                mock.call(['docker', 'exec', '-i', 'swss', 'rm', '-f', '/etc/supervisor/conf.d/ndppd.conf'], ignore_error=True, return_cmd=True),
                mock.call(['docker', 'exec', '-i', 'swss', 'supervisorctl', 'update'], return_cmd=True)
            ])
            assert result.exit_code == 0

    def test_config_vlan_del_nonexist_vlan_member(self):
        runner = CliRunner()

        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"], \
				["1000", "Ethernet0"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet0 is not a member of Vlan1000" in result.output

    def test_config_add_del_vlan_and_vlan_member(self, mock_restart_dhcp_relay_service):
        runner = CliRunner()
        db = Db()

        # add vlan 1001
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # add Ethernet20 to vlan 1001 but Ethernet20 is in routed mode will give error
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                ["1001", "Ethernet20", "--untagged"], obj=db)
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code != 0
        assert "Ethernet20 is in routed mode!\nUse switchport mode command to change port mode" in result.output

        # configure Ethernet20 from routed to access mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"],["access", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet20 switched from routed to access mode" in result.output

        # add Ethernet20 to vlan 1001
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                ["1001", "Ethernet20", "--untagged"], obj=db)
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.output)
        assert result.output == config_add_del_vlan_and_vlan_member_output

        # remove vlan member
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"],
                ["1001", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # add del 1001
        result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vlan_brief_output

    def test_config_add_del_vlan_and_vlan_member_in_alias_mode(self, mock_restart_dhcp_relay_service):
        runner = CliRunner()
        db = Db()

        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"

        # add vlan 1001
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # add etp6 to vlan 1001 but etp6 is in routed mode will give error
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                ["1001", "etp6", "--untagged"], obj=db)
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code != 0
        assert "Ethernet20 is in routed mode!\nUse switchport mode command to change port mode" in result.output

        # configure etp6 from routed to access mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"],["access", "etp6"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet20 switched from routed to access mode" in result.output

        # add etp6 to vlan 1001
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                ["1001", "etp6", "--untagged"], obj=db)
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.output == config_add_del_vlan_and_vlan_member_in_alias_mode_output

        # remove vlan member
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"],
                ["1001", "etp6"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # add del 1001
        result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vlan_brief_in_alias_mode_output

        os.environ['SONIC_CLI_IFACE_MODE'] = "default"


    def test_config_add_del_multiple_vlan_and_vlan_member(self,mock_restart_dhcp_relay_service):
        runner = CliRunner()
        db = Db()

        # add vlan 1001,1002,1003
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1001,1002,1003","--multiple"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # add Ethernet20 to vlan1001, vlan1002, vlan1003 multiple flag but Ethernet20 is in routed mode will give error
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                ["1001,1002,1003", "Ethernet20", "--multiple"], obj=db)
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code != 0
        assert "Ethernet20 is in routed mode!\nUse switchport mode command to change port mode" in result.output

        # configure Ethernet20 from routed to trunk mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"],["trunk", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet20 switched from routed to trunk mode" in result.output

        # add Ethernet20 to vlan 1001
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                ["1001,1002,1003", "Ethernet20", "--multiple"], obj=db)
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.output)
        assert result.output == test_config_add_del_multiple_vlan_and_vlan_member_output

        # remove vlan member
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"],
                ["1001-1003", "Ethernet20", "--multiple"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # add del 1001
        result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1001-1003","--multiple"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vlan_brief_output

    def test_config_add_del_add_vlans_and_add_vlans_member_except_vlan(self, mock_restart_dhcp_relay_service):
        runner = CliRunner()
        db = Db()

        # add vlan 1001,1002
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1001,1002","--multiple"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # add Ethernet20 to vlan1001, vlan1002, vlan1003 multiple flag but Ethernet20 is in routed mode will give error
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                ["1000,4000", "Ethernet20", "--multiple", "--except_flag"], obj=db)
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code != 0
        assert "Ethernet20 is in routed mode!\nUse switchport mode command to change port mode" in result.output

        # configure Ethernet20 from routed to trunk mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"],["trunk", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet20 switched from routed to trunk mode" in result.output

        # add Ethernet20 to vlan1001, vlan1002, vlan1003 multiple flag
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                ["1000,4000", "Ethernet20", "--multiple", "--except_flag"], obj=db)
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.output)
        assert result.output == test_config_add_del_add_vlans_and_add_vlans_member_except_vlan_output

        # remove vlan member except some
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"],
                ["1001,1002", "Ethernet20", "--multiple", "--except_flag"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == test_config_add_del_add_vlans_and_add_vlans_member_except_vlan__after_del_member_output

         # remove vlan member
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"],
                ["1001,1002", "Ethernet20", "--multiple"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # del 1001,1002
        result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1001-1002","--multiple"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vlan_brief_output


    def test_config_add_del_add_vlans_and_add_all_vlan_member(self, mock_restart_dhcp_relay_service):
        runner = CliRunner()
        db = Db()

        # add vlan 1001
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1001,1002,1003","--multiple"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # add Ethernet20 to vlan1001, vlan1002, vlan1003 multiple flag but Ethernet20 is in routed mode will give error
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                ["all", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code != 0
        assert "Ethernet20 is in routed mode!\nUse switchport mode command to change port mode" in result.output

        # configure Ethernet20 from routed to access mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"],["trunk", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet20 switched from routed to trunk mode" in result.output

        # add Ethernet20 to vlan 1001
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                ["all", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.output)
        assert result.output == test_config_add_del_add_vlans_and_add_all_vlan_member_output

        # remove vlan member
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"],
                ["all", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # add del 1001
        result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1001-1003","--multiple"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vlan_brief_output

    def test_config_add_del_vlan_and_vlan_member_with_switchport_modes(self, mock_restart_dhcp_relay_service):
        runner = CliRunner()
        db = Db()

        # add vlan 1001
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # add Ethernet20 to vlan 1001 but Ethernet20 is in routed mode will give error
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                ["1001", "Ethernet20", "--untagged"], obj=db)
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code != 0
        assert "Ethernet20 is in routed mode!\nUse switchport mode command to change port mode" in result.output


        # configure Ethernet20 from routed to access mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"],["access", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet20 switched from routed to access mode" in result.output

        # add Ethernet20 to vlan 1001
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                ["1001", "Ethernet20", "--untagged"], obj=db)
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0

        # add Ethernet20 to vlan 1001 as tagged member
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                ["1000", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code != 0
        assert "Ethernet20 is in access mode! Tagged Members cannot be added" in result.output

        # configure Ethernet20 from access to trunk mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"],["trunk", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet20 switched from access to trunk mode" in result.output

        # add Ethernet20 to vlan 1001 as tagged member
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                ["1000", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.output)
        assert result.output == test_config_add_del_vlan_and_vlan_member_with_switchport_modes_output

        # configure Ethernet20 from trunk to routed mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"],["routed", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Ethernet20 has tagged member(s). \nRemove them to change mode to routed" in result.output

        # remove vlan member
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"],
                ["1000", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # configure Ethernet20 from trunk to routed mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"],["routed", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Ethernet20 has untagged member. \nRemove it to change mode to routed" in result.output

        # remove vlan member
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"],
                ["1001", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # configure Ethernet20 from trunk to routed mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"],["routed", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet20 switched from trunk to routed mode" in result.output

        # add del 1001
        result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vlan_brief_output


    def test_config_add_del_vlan_and_vlan_member_with_switchport_modes_and_change_mode_types(self, mock_restart_dhcp_relay_service):
        runner = CliRunner()
        db = Db()

        # add vlan 1001
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # add Ethernet64 to vlan 1001 but Ethernet64 is in routed mode will give error
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                ["1001", "Ethernet64"], obj=db)
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code != 0
        assert "Ethernet64 is in routed mode!\nUse switchport mode command to change port mode" in result.output

        # configure Ethernet64 from routed to trunk mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"],["trunk", "Ethernet64"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet64 switched from routed to trunk mode" in result.output

        # add Ethernet64 to vlan 1001
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                ["1001", "Ethernet64"], obj=db)
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0

        # configure Ethernet64 from routed to access mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"],["access", "Ethernet64"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Ethernet64 is in trunk mode and have tagged member(s).\nRemove tagged member(s) from Ethernet64 to switch to access mode" in result.output

        # remove vlan member
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"],
                ["1001", "Ethernet64"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # configure Ethernet64 from routed to access mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"],["access", "Ethernet64"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet64 switched from trunk to access mode" in result.output

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == test_config_add_del_vlan_and_vlan_member_with_switchport_modes_and_change_mode_types_output


    def test_config_vlan_proxy_arp_with_nonexist_vlan_intf_table(self):
        modes = ["enabled", "disabled"]
        runner = CliRunner()
        db = Db()
        db.cfgdb.delete_table("VLAN_INTERFACE")

        for mode in modes:
            result = runner.invoke(config.config.commands["vlan"].commands["proxy_arp"], ["1000", mode], obj=db)

            print(result.exit_code)
            print(result.output)

            assert result.exit_code != 0
            assert "Interface Vlan1000 does not exist" in result.output

    def test_config_vlan_proxy_arp_with_nonexist_vlan_intf(self):
        modes = ["enabled", "disabled"]
        runner = CliRunner()
        db = Db()

        for mode in modes:
            result = runner.invoke(config.config.commands["vlan"].commands["proxy_arp"], ["1001", mode], obj=db)

            print(result.exit_code)
            print(result.output)

            assert result.exit_code != 0
            assert "Interface Vlan1001 does not exist" in result.output

    def test_config_vlan_proxy_arp_enable(self):
        mock_cli_returns = [("running", 0),("", 1)] + [("", 0)] * 4
        with mock.patch("utilities_common.cli.run_command", mock.Mock(side_effect=mock_cli_returns)) as mock_run_command:
            runner = CliRunner()
            db = Db()

            result = runner.invoke(config.config.commands["vlan"].commands["proxy_arp"], ["1000", "enabled"], obj=db)

            print(result.exit_code)
            print(result.output)

            expected_calls = [mock.call(['docker', 'container', 'inspect', '-f', '{{.State.Status}}', 'swss'], return_cmd=True),
                              mock.call(['docker', 'exec', '-i', 'swss', 'supervisorctl', 'status', 'ndppd'], ignore_error=True, return_cmd=True),
                              mock.call(['docker', 'exec', '-i', 'swss', 'cp', '/usr/share/sonic/templates/ndppd.conf', '/etc/supervisor/conf.d/']),
                              mock.call(['docker', 'exec', '-i', 'swss', 'supervisorctl', 'update'], return_cmd=True),
                              mock.call(['docker', 'exec', '-i', 'swss', 'sonic-cfggen', '-d', '-t', '/usr/share/sonic/templates/ndppd.conf.j2,/etc/ndppd.conf']),
                              mock.call(['docker', 'exec', '-i', 'swss', 'supervisorctl', 'restart', 'ndppd'], return_cmd=True)]
            mock_run_command.assert_has_calls(expected_calls)

            assert result.exit_code == 0 
            assert db.cfgdb.get_entry("VLAN_INTERFACE", "Vlan1000") == {"proxy_arp": "enabled"}

    def test_config_vlan_proxy_arp_disable(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["vlan"].commands["proxy_arp"], ["2000", "disabled"], obj=db)

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        assert db.cfgdb.get_entry("VLAN_INTERFACE", "Vlan2000") == {"proxy_arp": "disabled"}
        
    def test_config_2_untagged_vlan_on_same_interface(self):
        runner = CliRunner()
        db = Db()
        
        # add Ethernet4 to vlan 2000 as untagged - should fail as ethrnet4 is already untagged member in 1000
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                ["2000", "Ethernet4", "--untagged"], obj=db)
        print(result.exit_code)
        assert result.exit_code != 0
        
        # add Ethernet4 to vlan 2000 as tagged - should succeed
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                ["2000", "Ethernet4" ], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0
        
    def test_config_set_router_port_on_member_interface(self):        
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}
        
        # intf enable
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet4", "10.10.10.1/24"], obj=obj)        
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert 'Interface Ethernet4 is not in routed mode!' in result.output
        
    def test_config_vlan_add_member_of_portchannel(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"], \
				["1000", "Ethernet32", "--untagged"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet32 is part of portchannel!" in result.output

    @pytest.mark.parametrize("ip_version", ["ipv4", "ipv6"])
    def test_config_add_del_vlan_dhcp_relay_with_empty_entry(self, ip_version, mock_restart_dhcp_relay_service):
        runner = CliRunner()
        db = Db()

        # add vlan 1001
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        exp_output = {"vlanid": "1001"} if ip_version == "ipv4" else {}
        assert db.cfgdb.get_entry(IP_VERSION_PARAMS_MAP[ip_version]["table"], "Vlan1001") == exp_output

        # del vlan 1001
        with mock.patch("utilities_common.dhcp_relay_util.handle_restart_dhcp_relay_service") as mock_handle_restart:
            result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1001"], obj=db)
            print(result.exit_code)
            print(result.output)

            assert result.exit_code == 0
            assert "Vlan1001" not in db.cfgdb.get_keys(IP_VERSION_PARAMS_MAP[ip_version]["table"])
            assert "Restart service dhcp_relay failed with error" not in result.output

    @pytest.mark.parametrize("ip_version", ["ipv4", "ipv6"])
    def test_config_add_del_vlan_dhcp_relay_with_non_empty_entry(self, ip_version, mock_restart_dhcp_relay_service):
        runner = CliRunner()
        db = Db()

        # add vlan 1001
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        exp_output = {"vlanid": "1001"} if ip_version == "ipv4" else {}
        assert db.cfgdb.get_entry(IP_VERSION_PARAMS_MAP[ip_version]["table"], "Vlan1001") == exp_output
        db.cfgdb.set_entry("DHCP_RELAY", "Vlan1001", {"dhcpv6_servers": ["fc02:2000::5"]})

        # del vlan 1001
        with mock.patch("utilities_common.dhcp_relay_util.handle_restart_dhcp_relay_service") as mock_handle_restart:
            result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1001"], obj=db)
            print(result.exit_code)
            print(result.output)

            assert result.exit_code == 0
            assert "Vlan1001" not in db.cfgdb.get_keys(IP_VERSION_PARAMS_MAP[ip_version]["table"])
            mock_handle_restart.assert_called_once()
            assert "Restart service dhcp_relay failed with error" not in result.output

    @pytest.mark.parametrize("ip_version", ["ipv4", "ipv6"])
    def test_config_add_del_vlan_with_dhcp_relay_not_running(self, ip_version):
        runner = CliRunner()
        db = Db()

        # add vlan 1001
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        exp_output = {"vlanid": "1001"} if ip_version == "ipv4" else {}
        assert db.cfgdb.get_entry(IP_VERSION_PARAMS_MAP[ip_version]["table"], "Vlan1001") == exp_output

        # del vlan 1001
        with mock.patch("utilities_common.dhcp_relay_util.handle_restart_dhcp_relay_service") \
             as mock_restart_dhcp_relay_service:
            result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1001"], obj=db)
            print(result.exit_code)
            print(result.output)

            assert result.exit_code == 0
            assert "Vlan1001" not in db.cfgdb.get_keys(IP_VERSION_PARAMS_MAP[ip_version]["table"])
            assert mock_restart_dhcp_relay_service.call_count == 0
            assert "Restarting DHCP relay service..." not in result.output
            assert "Restart service dhcp_relay failed with error" not in result.output

    def test_config_add_del_vlan_with_not_restart_dhcp_relay_ipv6(self):
        runner = CliRunner()
        db = Db()

        # add vlan 1001
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        db.cfgdb.set_entry("DHCP_RELAY", "Vlan1001", {"dhcpv6_servers": ["fc02:2000::5"]})

        # del vlan 1001
        with mock.patch("utilities_common.dhcp_relay_util.handle_restart_dhcp_relay_service") \
             as mock_restart_dhcp_relay_service:
            result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1001", "--no_restart_dhcp_relay"],
                                   obj=db)
            print(result.exit_code)
            print(result.output)

            assert result.exit_code != 0
            assert mock_restart_dhcp_relay_service.call_count == 0
            assert "Can't delete Vlan1001 because related DHCPv6 Relay config is exist" in result.output

        db.cfgdb.set_entry("DHCP_RELAY", "Vlan1001", None)
        # del vlan 1001
        with mock.patch("utilities_common.dhcp_relay_util.handle_restart_dhcp_relay_service") \
             as mock_restart_dhcp_relay_service:
            result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1001", "--no_restart_dhcp_relay"],
                                   obj=db)
            print(result.exit_code)
            print(result.output)

            assert result.exit_code == 0
            assert mock_restart_dhcp_relay_service.call_count == 0

    @pytest.mark.parametrize("ip_version", ["ipv6"])
    def test_config_add_exist_vlan_dhcp_relay(self, ip_version):
        runner = CliRunner()
        db = Db()

        db.cfgdb.set_entry("DHCP_RELAY", "Vlan1001", {"vlanid": "1001"})
        # add vlan 1001
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "DHCPv6 relay config for Vlan1001 already exists" in result.output

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        bgp_util.run_bgp_command = cls._old_run_bgp_command
        print("TEARDOWN")

    def test_config_vlan_del_dhcp_relay_restart(self):
        runner = CliRunner()
        db = Db()
        obj = {"config_db": db.cfgdb}

        # remove vlan IP`s
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                               ["Vlan1000", "192.168.0.1/21"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                               ["Vlan1000", "fc02:1000::1/64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

        # remove vlan members
        vlan_member = db.cfgdb.get_table("VLAN_MEMBER")
        keys = [(k, v) for k, v in vlan_member if k == "Vlan{}".format(1000)]
        for _, v in keys:
            result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"], ["1000", v], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0

        origin_run_command_func = config.vlan.clicommon.run_command
        config.vlan.clicommon.run_command = mock.MagicMock(return_value=("active", 0))
        result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1000"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        config.vlan.clicommon.run_command = origin_run_command_func

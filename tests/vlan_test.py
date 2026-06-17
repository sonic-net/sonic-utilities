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

root_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(root_path)
scripts_path = os.path.join(modules_path, "scripts")

IP_VERSION_PARAMS_MAP = {
    "ipv4": {
        "table": "VLAN"

    },
    "ipv6": {
        "table": "DHCP_RELAY"
    }
}

show_vlan_brief_output = """\
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

show_vlan_brief_in_alias_mode_output = """\
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

show_vlan_brief_empty_output = """\
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

show_vlan_brief_with_portchannel_output = """\
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

show_vlan_config_output = """\
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

show_vlan_config_in_alias_mode_output = """\
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

config_add_del_vlan_and_vlan_member_output = """\
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

config_add_del_vlan_and_vlan_member_in_alias_mode_output = """\
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

test_config_add_del_multiple_vlan_and_vlan_member_output = """\
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

test_config_add_del_add_vlans_and_add_all_vlan_member_output = """\
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

test_config_add_del_add_vlans_and_add_vlans_member_except_vlan_after_del_member_output = """\
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
|      1002 |                 |                 |                | disabled    |
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


test_config_add_del_with_switchport_modes_changes_output = """\
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


def get_intf_switchport_status(self, output: str, interface: str) -> str:
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("Interface") or line.startswith("----"):
            continue
        parts = line.split()
        if parts[0] == interface and len(parts) >= 2:
            return parts[1]
    return "interface not found"


class TestVlan(object):
    _old_run_bgp_command = None

    @classmethod
    def setup_class(cls):
        # ensure that we are working with single asic config
        cls._old_run_bgp_command = bgp_util.run_bgp_command
        bgp_util.run_bgp_command = mock.MagicMock(
            return_value=cls.mock_run_bgp_command())
        from .mock_tables import dbconnector
        dbconnector.load_namespace_config()

        cls._test_db = None

        from sonic_py_common import multi_asic
        cls._original_connect_config_db_for_ns = multi_asic.connect_config_db_for_ns
        cls._original_connect_to_all_dbs_for_ns = multi_asic.connect_to_all_dbs_for_ns

        def patched_connect_config_db_for_ns(namespace=None, **kwargs):
            if cls._test_db is not None:
                return cls._test_db.cfgdb
            return cls._original_connect_config_db_for_ns(namespace, **kwargs)

        def patched_connect_to_all_dbs_for_ns(namespace=None, **kwargs):
            if cls._test_db is not None:
                return cls._test_db.db
            return cls._original_connect_to_all_dbs_for_ns(namespace, **kwargs)

        multi_asic.connect_config_db_for_ns = patched_connect_config_db_for_ns
        multi_asic.connect_to_all_dbs_for_ns = patched_connect_to_all_dbs_for_ns

        import config.vlan as vlan_module
        cls._original_get_db_with_namespace = vlan_module.get_db_with_namespace

        def patched_get_db_with_namespace(ctx):
            if cls._test_db is not None:
                return cls._test_db
            return cls._original_get_db_with_namespace(ctx)

        vlan_module.get_db_with_namespace = patched_get_db_with_namespace

        cls._original_invoke = CliRunner.invoke

        def patched_invoke(self, cli, args=None, **kwargs):
            if 'obj' in kwargs:
                obj = kwargs['obj']
                if hasattr(obj, 'cfgdb') and hasattr(obj, 'db') and not isinstance(obj, dict):
                    cls._test_db = obj

            return cls._original_invoke(self, cli, args, **kwargs)

        CliRunner.invoke = patched_invoke
        print("SETUP")

    @classmethod
    def teardown_class(cls):
        # Restore original functions
        if hasattr(cls, '_original_invoke'):
            CliRunner.invoke = cls._original_invoke
        if hasattr(cls, '_original_connect_config_db_for_ns'):
            from sonic_py_common import multi_asic
            multi_asic.connect_config_db_for_ns = cls._original_connect_config_db_for_ns
            multi_asic.connect_to_all_dbs_for_ns = cls._original_connect_to_all_dbs_for_ns
        if hasattr(cls, '_original_get_db_with_namespace'):
            import config.vlan as vlan_module
            vlan_module.get_db_with_namespace = cls._original_get_db_with_namespace
        if cls._old_run_bgp_command:
            bgp_util.run_bgp_command = cls._old_run_bgp_command
        cls._test_db = None
        print("TEARDOWN")

    def setup_method(self):
        """Reset test db before each test for isolation"""
        # Each test will capture its own Db instance on first use
        self.__class__._test_db = None

    def mock_run_bgp_command():
        return ""

    def get_vlan_obj(self, db=None):
        """Helper to create proper context object for vlan commands"""
        if db is None:
            return {'namespace': ''}
        else:
            return {'db': db, 'namespace': ''}

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

    def test_switchport_status(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["switchport"], ["etp33"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: No such command 'etp33'" in result.output

    def test_show_switchport_status_in_alias_mode(self):
        runner = CliRunner()
        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["interfaces"].commands["switchport"], ["etp33"])
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: No such command 'etp33'" in result.output

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

    def test_config_vlan_add_exist_port_member(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"], ["1000", "Ethernet4"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet4 is already a member of Vlan1000" in result.output

    def test_config_vlan_add_rif_portchannel_member(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                               ["1000", "PortChannel0001", "--untagged"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel0001 is a router interface!" in result.output

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

    def test_config_vlan_add_vlan_with_multiple_vlanids_with_range_and_multiple_ids(
            self, mock_restart_dhcp_relay_service):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["10-15,20,25,30", "--multiple"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    def test_config_vlan_add_vlan_with_wrong_range(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["15-10", "--multiple"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "15 is greater than 10. List cannot be generated" in result.output

    def test_config_vlan_add_vlan_range_with_default_vlan(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1-10", "--multiple"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Vlan1 is default vlan" in result.output

    def test_config_vlan_add_vlan_range_with_invalid_vlanid(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["4093-4095", "--multiple"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Invalid VLAN ID must be in (2-4094)" in result.output

    def test_config_vlan_add_vlan_with_multiple_vlanids_is_digit_fail(self):
        runner = CliRunner()
        vid = "test_fail_case"
        result = runner.invoke(config.config.commands["vlan"].commands["add"],
                               ["{},1001,1002".format(vid), "--multiple"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "{} is not integer".format(vid) in result.output

    def test_config_vlan_add_vlan_is_digit_fail(self):
        runner = CliRunner()
        vid = "test_fail_case"
        result = runner.invoke(config.config.commands["vlan"].commands["add"], [vid])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "{} is not integer".format(vid) in result.output

    def test_config_vlan_del_vlan_is_digit_fail(self):
        runner = CliRunner()
        vid = "test_fail_case"
        result = runner.invoke(config.config.commands["vlan"].commands["del"], [vid])
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
        assert "{} is default VLAN".format(vlan) in result.output

    def test_config_vlan_del_vlan_does_not_exist(self):
        runner = CliRunner()
        vid = "3010"
        vlan = "Vlan{}".format(vid)
        result = runner.invoke(config.config.commands["vlan"].commands["del"], [vid])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "{} does not exist".format(vlan) in result.output

    def test_config_vlan_add_member_with_default_vlan(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"], ["1", "Ethernet4"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Vlan1 is default VLAN" in result.output

    def test_config_vlan_add_member_with_invalid_vlanid(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"], ["4096", "Ethernet4"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Invalid VLAN ID 4096 (2-4094)" in result.output

    def test_config_vlan_del_member_with_invalid_vlanid(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"], ["4096", "Ethernet4"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Invalid VLAN ID 4096 (2-4094)" in result.output

    def test_config_vlan_add_member_with_invalid_port(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"], ["4097", "Ethernet4"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Invalid VLAN ID 4097 (2-4094)" in result.output

    def test_config_vlan_del_member_with_invalid_port(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"], ["4097", "Ethernet4"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Invalid VLAN ID 4097 (2-4094)" in result.output

    def test_config_vlan_add_member_with_invalid_long_name(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                               ["123456789012", "Ethernet4"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Invalid VLAN ID 123456789012 (2-4094)" in result.output

    def test_config_vlan_add_member_with_nonexist_vlanid(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"], ["1001", "Ethernet4"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Vlan1001 does not exist" in result.output

    def test_config_vlan_del_member_with_nonexist_vlanid(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"], ["1001", "Ethernet4"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Vlan1001 does not exist" in result.output

    def test_config_vlan_add_member_is_digit_fail(self):
        runner = CliRunner()
        vid = "test_fail_case"
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"], [vid, "Ethernet4"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Vlan is not integer" in result.output

    def test_config_vlan_add_member_with_except_flag_is_digit_fail(self):
        runner = CliRunner()
        vid = "test_fail_case"
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                               [vid, "Ethernet4", "--except_flag"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Vlan is not integer" in result.output

    def test_config_vlan_add_member_multiple_untagged(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                               ["1000,2000", "Ethernet4", "--multiple", "--untagged"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet4 cannot have more than one untagged Vlan" in result.output

    def test_config_vlan_add_nonexist_port_member(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"], ["1000", "Ethernet3"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet3 does not exist" in result.output

    def test_config_vlan_add_nonexist_portchannel_member(self):
        runner = CliRunner()
        # switch port mode for PortChannel1011 to trunk mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"], ["trunk", "PortChannel1011"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel1011 does not exist" in result.output

        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                               ["1000", "PortChannel1011"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel1011 does not exist" in result.output

    def test_config_vlan_add_mirror_destintion_port_member(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                               ["1000", "Ethernet44"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet44 is configured as mirror destination port" in result.output

    def test_show_port_switchport_etp33_in_alias_mode(self):
        runner = CliRunner()
        os.environ["SONIC_CLI_IFACE_MODE"] = "alias"
        result = runner.invoke(config.config.commands["switchport"].commands["mode"],
                               ["trunk", "etp33"])
        os.environ["SONIC_CLI_IFACE_MODE"] = "default"
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: etp33 does not exist" in result.output

    def test_show_port_vlan_etp33_in_alias_mode(self):
        runner = CliRunner()
        os.environ["SONIC_CLI_IFACE_MODE"] = "alias"
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                               ["4000", "etp33"])
        os.environ["SONIC_CLI_IFACE_MODE"] = "default"
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: etp33 does not exist" in result.output

    def test_show_port_vlan_del_etp33_in_alias_mode(self):
        runner = CliRunner()
        os.environ["SONIC_CLI_IFACE_MODE"] = "alias"
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"],
                               ["4000", "etp33"])
        os.environ["SONIC_CLI_IFACE_MODE"] = "default"
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: etp33 is not a member of Vlan4000" in result.output

    def test_config_switchport_mode_with_mirror_destintion_port(self):
        runner = CliRunner()
        result = runner.invoke(config.config.commands["switchport"].commands["mode"], ["trunk", "Ethernet44"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet44 is configured as mirror destination port" in result.output

    def test_config_vlan_add_portchannel_member_with_switchport_modes(self):
        runner = CliRunner()
        db = Db()

        # Configure Ethernet112 to trunk mode; should give error as it is part of PortChannel0001
        result = runner.invoke(config.config.commands["switchport"].commands["mode"], ["trunk", "Ethernet112"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet112 is part of portchannel!" in result.output

        # Configure PortChannel0001 to routed mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"],
                               ["routed", "PortChannel0001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        result = runner.invoke(show.cli.commands["interfaces"].commands["switchport"].commands["status"], obj=db)
        switchport_status = get_intf_switchport_status(self, result.output, "PortChannel0001")
        assert "routed" in switchport_status

        # Configure PortChannel0001 to routed mode again; should give error as it is already in routed mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"],
                               ["routed", "PortChannel0001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel0001 is already in routed mode" in result.output

        # Configure PortChannel0001 to trunk mode; should give error as it is a router interface
        result = runner.invoke(config.config.commands["switchport"].commands["mode"],
                               ["trunk", "PortChannel0001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Remove IP from PortChannel0001 to change mode!" in result.output

        # Remove PortChannel1001 member from Vlan4000
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"],
                               ["4000", "PortChannel1001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # Configure PortChannel1001 to access mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"],
                               ["access", "PortChannel1001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        result = runner.invoke(show.cli.commands["interfaces"].commands["switchport"].commands["status"], obj=db)
        print(result.output)
        switchport_status = get_intf_switchport_status(self, result.output, "PortChannel1001")
        assert "access" in switchport_status

        # Configure PortChannel1001 back to routed mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"],
                               ["routed", "PortChannel1001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        result = runner.invoke(show.cli.commands["interfaces"].commands["switchport"].commands["status"], obj=db)
        switchport_status = get_intf_switchport_status(self, result.output, "PortChannel1001")
        assert "routed" in switchport_status

        # Configure PortChannel1001 to trunk mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"],
                               ["trunk", "PortChannel1001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        result = runner.invoke(show.cli.commands["interfaces"].commands["switchport"].commands["status"], obj=db)
        switchport_status = get_intf_switchport_status(self, result.output, "PortChannel1001")
        assert "trunk" in switchport_status

        # Add back PortChannel1001 tagged member to Vlan4000
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                               ["4000", "PortChannel1001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # Add PortChannel1001 to Vlan1000
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
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

    def test_config_vlan_with_vxlanmap_del_vlan(self, mock_restart_dhcp_relay_service):
        runner = CliRunner()
        db = Db()

        # create vlan
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1027"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # create vxlan map
        result = runner.invoke(config.config.commands["vxlan"].commands["map"].commands["add"],
                               ["vtep1", "1027", "11027"], obj=db)
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
        obj = {'config_db': db.cfgdb}

        # del vlan with IP
        result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1000"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Vlan1000 can not be removed. First remove IP addresses assigned to this VLAN\n" in result.output

        # remove vlan IP`s
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Vlan1000", "192.168.0.1/21"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1

        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Vlan1000", "fc02:1000::1/64"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1

        # del vlan with IP
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1000"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code != 0
            assert ("Error: VLAN ID 1000 can not be removed."
                    " First remove all members assigned to this VLAN") in result.output

        with mock.patch("config.vlan.delete_db_entry") as delete_db_entry:
            vlan_member = db.cfgdb.get_table('VLAN_MEMBER')
            keys = [(k, v) for k, v in vlan_member if k == 'Vlan{}'.format(1000)]
            for k, v in keys:
                result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"],
                                       ["1000", v], obj=db)
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
                mock.call(['docker', 'exec', '-i', 'swss', 'supervisorctl', 'status', 'ndppd'],
                          ignore_error=True, return_cmd=True),
                mock.call(['docker', 'exec', '-i', 'swss', 'supervisorctl', 'stop', 'ndppd'],
                          ignore_error=True, return_cmd=True),
                mock.call(['docker', 'exec', '-i', 'swss', 'rm', '-f', '/etc/supervisor/conf.d/ndppd.conf'],
                          ignore_error=True, return_cmd=True),
                mock.call(['docker', 'exec', '-i', 'swss', 'supervisorctl', 'update'], return_cmd=True)
            ])
            assert result.exit_code == 0

    def test_config_vlan_del_nonexist_vlan_member(self):
        runner = CliRunner()

        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"],
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

        # del 1001
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

    def test_config_add_del_multiple_vlan_and_vlan_member(self, mock_restart_dhcp_relay_service):
        runner = CliRunner()
        db = Db()

        # add vlan 1001,1002,1003
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1001,1002,1003", "--multiple"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # add Ethernet20 to vlan1001, vlan1002, vlan1003 multiple flag
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

        # del 1001
        result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1001-1003", "--multiple"], obj=db)
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
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1001,1002", "--multiple"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # add Ethernet20 to all vlans except vlan1000, vlan4000 with multiple flag
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
                               ["1001,1002,3000", "Ethernet20", "--multiple", "--except_flag"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # remove vlan member except 1001
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"],
                               ["1001", "Ethernet20", "--except_flag"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == test_config_add_del_add_vlans_and_add_vlans_member_except_vlan_after_del_member_output

        # remove vlan member
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"],
                               ["1001", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # del 1001,1002
        result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1001-1002", "--multiple"], obj=db)
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

        # add vlan 1001, 1002, 1003
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1001,1002,1003", "--multiple"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # add Ethernet20 to all vlans
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

        # del 1001, 1002, 1003
        result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1001-1003", "--multiple"], obj=db)
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

        # configure Ethernet20 to routed mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"], ["routed", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet20 switched to routed mode" in result.output

        # configure Ethernet20 to access mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"], ["access", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet20 switched to access mode" in result.output
        result = runner.invoke(show.cli.commands["interfaces"].commands["switchport"].commands["status"], obj=db)
        print(result.output)
        switchport_status = get_intf_switchport_status(self, result.output, "Ethernet20")
        assert "access" in switchport_status

        # configure Ethernet20 to access mode again; should give error as it is already in access mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"], ["access", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Ethernet20 is already in access mode" in result.output

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
        result = runner.invoke(config.config.commands["switchport"].commands["mode"], ["trunk", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet20 switched to trunk mode" in result.output

        # add Ethernet20 to vlan 1001 as tagged member
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                               ["1000", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0
        result = runner.invoke(show.cli.commands["interfaces"].commands["switchport"].commands["status"], obj=db)
        print(result.output)
        switchport_status = get_intf_switchport_status(self, result.output, "Ethernet20")
        assert "trunk" in switchport_status

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.output)
        assert result.output == test_config_add_del_vlan_and_vlan_member_with_switchport_modes_output

        # configure Ethernet20 from trunk to routed mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"], ["routed", "Ethernet20"], obj=db)
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
        result = runner.invoke(config.config.commands["switchport"].commands["mode"], ["routed", "Ethernet20"], obj=db)
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
        result = runner.invoke(config.config.commands["switchport"].commands["mode"], ["routed", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet20 switched to routed mode" in result.output

        result = runner.invoke(show.cli.commands["interfaces"].commands["switchport"].commands["status"], obj=db)
        print(result.output)
        switchport_status = get_intf_switchport_status(self, result.output, "Ethernet20")
        assert "routed" in switchport_status

        # del 1001
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

    def test_config_add_del_with_switchport_modes_changes_output(
            self, mock_restart_dhcp_relay_service):
        runner = CliRunner()
        db = Db()

        # add vlan 1001
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["1001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # configure Ethernet20 to trunk mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"], ["trunk", "Ethernet20"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet20 switched to trunk mode" in result.output

        result = runner.invoke(show.cli.commands["interfaces"].commands["switchport"].commands["status"], obj=db)
        print(result.output)
        switchport_status = get_intf_switchport_status(self, result.output, "Ethernet20")
        assert "trunk" in switchport_status

        # add Ethernet64 to vlan 1001 but Ethernet64 is in routed mode will give error
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                               ["1001", "Ethernet64"], obj=db)
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code != 0
        assert "Ethernet64 is in routed mode!\nUse switchport mode command to change port mode" in result.output

        # configure Ethernet64 from routed to trunk mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"], ["trunk", "Ethernet64"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet64 switched to trunk mode" in result.output
        result = runner.invoke(show.cli.commands["interfaces"].commands["switchport"].commands["status"], obj=db)
        print(result.output)
        switchport_status = get_intf_switchport_status(self, result.output, "Ethernet20")
        assert "trunk" in switchport_status

        # add Ethernet64 to vlan 1001
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
                               ["1001", "Ethernet64"], obj=db)
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0

        # configure Ethernet64 from trunk to access mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"], ["access", "Ethernet64"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Ethernet64 is in trunk mode and have tagged member(s)." in result.output

        # remove vlan member
        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["del"],
                               ["1001", "Ethernet64"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # configure Ethernet64 from routed to access mode
        result = runner.invoke(config.config.commands["switchport"].commands["mode"], ["access", "Ethernet64"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert "Ethernet64 switched to access mode" in result.output

        result = runner.invoke(show.cli.commands["interfaces"].commands["switchport"].commands["status"], obj=db)
        print(result.output)
        switchport_status = get_intf_switchport_status(self, result.output, "Ethernet64")
        assert "access" in switchport_status

        # show output
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == (
            test_config_add_del_with_switchport_modes_changes_output)

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
        mock_cli_returns = [("running", 0), ("", 1)] + [("", 0)] * 4
        with mock.patch(
                "utilities_common.cli.run_command", mock.Mock(side_effect=mock_cli_returns)) as mock_run_command:
            runner = CliRunner()
            db = Db()

            result = runner.invoke(config.config.commands["vlan"].commands["proxy_arp"], ["1000", "enabled"], obj=db)

            print(result.exit_code)
            print(result.output)

            expected_calls = [mock.call(['docker', 'container', 'inspect', '-f', '{{.State.Status}}', 'swss'],
                                        return_cmd=True),
                              mock.call(['docker', 'exec', '-i', 'swss', 'supervisorctl', 'status', 'ndppd'],
                                        ignore_error=True, return_cmd=True),
                              mock.call(['docker', 'exec', '-i', 'swss', 'cp', '/usr/share/sonic/templates/ndppd.conf',
                                         '/etc/supervisor/conf.d/']),
                              mock.call(['docker', 'exec', '-i', 'swss', 'supervisorctl', 'update'], return_cmd=True),
                              mock.call(['docker', 'exec', '-i', 'swss', 'sonic-cfggen', '-d', '-t',
                                         '/usr/share/sonic/templates/ndppd.conf.j2,/etc/ndppd.conf']),
                              mock.call(['docker', 'exec', '-i', 'swss', 'supervisorctl', 'restart', 'ndppd'],
                                        return_cmd=True)]
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
                               ["2000", "Ethernet4"], obj=db)
        print(result.exit_code)
        assert result.exit_code == 0

    def test_config_set_router_port_on_member_interface(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # intf enable
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet4", "10.10.10.1/24"], obj=obj)
        print(result.exit_code, result.output)
        assert 'Interface Ethernet4 is a member of vlan\nAborting!\n' in result.output

    def test_config_vlan_add_member_of_portchannel(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["vlan"].commands["member"].commands["add"],
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

    def test_config_add_del_vlan_dhcpv4_relay_with_non_empty_entry(self, mock_restart_dhcp_relay_service):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["999"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert db.cfgdb.get_entry("VLAN", "Vlan999") == {"vlanid": "999"}

        db.cfgdb.set_entry("DHCPV4_RELAY", "Vlan999", {
            "dhcpv4_servers": ["192.0.2.1"],
            "source_interface": "Ethernet4"
        })

        with mock.patch("utilities_common.dhcp_relay_util.handle_restart_dhcp_relay_service"):
            result = runner.invoke(config.config.commands["vlan"].commands["del"], ["999"], obj=db)
            print(result.exit_code)
            print(result.output)

            assert result.exit_code != 0
            assert "Vlan999 cannot be removed as it is being used in DHCPV4_RELAY table." in result.output

        db.cfgdb.set_entry("DHCPV4_RELAY", "Vlan999", None)

        with mock.patch("utilities_common.dhcp_relay_util.handle_restart_dhcp_relay_service"):
            result = runner.invoke(config.config.commands["vlan"].commands["del"], ["999"], obj=db)
            print(result.exit_code)
            print(result.output)

            assert result.exit_code == 0
            assert "Vlan999" not in db.cfgdb.get_keys("VLAN")

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

    def test_config_vlan_del_dhcp_relay_restart(self):
        runner = CliRunner()
        db = Db()
        obj = {"config_db": db.cfgdb}

        # remove vlan IP`s
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Vlan1000", "192.168.0.1/21"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1

        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Vlan1000", "fc02:1000::1/64"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1

        # remove vlan s
        vlan_ = db.cfgdb.get_table("VLAN_")
        keys = [(k, v) for k, v in vlan_ if k == "Vlan{}".format(1000)]
        for _, v in keys:
            result = runner.invoke(config.config.commands["vlan"].commands[""].commands["del"], ["1000", v], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0

        origin_run_command_func = config.vlan.clicommon.run_command
        config.vlan.clicommon.run_command = mock.MagicMock(return_value=("active", 0))
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["vlan"].commands["del"], ["1000"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code != 0

        config.vlan.clicommon.run_command = origin_run_command_func


class TestVlanBriefCache:
    """Unit and integration tests for the per-invocation index cache
    introduced in show/vlan.py (_get_brief_cache / _clear_brief_cache).
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_ctx(self, vlan_ip_data=None, vlan_ports_data=None):
        """Return a (vlan_cfg, FakeDb) tuple usable by _get_brief_cache
        without touching ConfigDb or the filesystem."""

        class FakeDb:
            pass

        vlan_ip_data = vlan_ip_data or {}
        vlan_ports_data = vlan_ports_data or {}
        vlan_cfg = ({}, vlan_ip_data, vlan_ports_data)
        return (vlan_cfg, FakeDb()), FakeDb.__new__(FakeDb)

    def _make_ctx_shared_db(self, vlan_ip_data=None, vlan_ports_data=None):
        """Like _make_ctx but returns (ctx, the_db_object) where the db
        object IS the one embedded in ctx (so callers can inspect attrs)."""

        class FakeDb:
            pass

        db = FakeDb()
        vlan_ip_data = vlan_ip_data or {}
        vlan_ports_data = vlan_ports_data or {}
        vlan_cfg = ({}, vlan_ip_data, vlan_ports_data)
        ctx = (vlan_cfg, db)
        return ctx, db

    # ------------------------------------------------------------------
    # Unit tests: _get_brief_cache indexing
    # ------------------------------------------------------------------

    def test_cache_returns_same_object_on_repeated_calls(self):
        """Within the same ctx the cache dict must be reused, not rebuilt."""
        from show.vlan import _get_brief_cache

        ctx, db = self._make_ctx_shared_db(
            vlan_ip_data={
                ("Vlan1000", "192.168.0.1/21"): {},
                "Vlan2000": {"proxy_arp": "enabled"},
            },
            vlan_ports_data={
                ("Vlan1000", "Ethernet4"): {"tagging_mode": "untagged"},
            },
        )

        cache1 = _get_brief_cache(ctx)
        cache2 = _get_brief_cache(ctx)
        assert cache1 is cache2

    def test_cache_ip_by_vlan_contains_only_prefix_keys(self):
        """ip_by_vlan must include only (vlan, prefix) entries, not plain
        vlan-name entries."""
        from show.vlan import _get_brief_cache

        ctx, _ = self._make_ctx_shared_db(
            vlan_ip_data={
                ("Vlan1000", "10.0.0.1/24"): {},
                ("Vlan1000", "10.0.1.1/24"): {},
                ("Vlan2000", "10.0.2.1/24"): {},
                "Vlan1000": {"proxy_arp": "enabled"},   # plain key → proxy_arp
            },
        )

        cache = _get_brief_cache(ctx)
        assert set(cache["ip_by_vlan"].keys()) == {"Vlan1000", "Vlan2000"}
        assert "10.0.0.1/24" in cache["ip_by_vlan"]["Vlan1000"]
        assert "10.0.1.1/24" in cache["ip_by_vlan"]["Vlan1000"]
        assert cache["ip_by_vlan"]["Vlan2000"] == ["10.0.2.1/24"]

    def test_cache_proxy_arp_defaults_to_disabled(self):
        """Vlan entries without a proxy_arp field must default to 'disabled'."""
        from show.vlan import _get_brief_cache

        ctx, _ = self._make_ctx_shared_db(
            vlan_ip_data={
                "Vlan1000": {"proxy_arp": "enabled"},
                "Vlan2000": {},                          # no proxy_arp key
            },
        )

        cache = _get_brief_cache(ctx)
        assert cache["proxy_arp_by_vlan"]["Vlan1000"] == "enabled"
        assert cache["proxy_arp_by_vlan"]["Vlan2000"] == "disabled"

    def test_cache_ports_in_natsorted_order(self):
        """ports_by_vlan must list ports in natsorted order."""
        from show.vlan import _get_brief_cache
        from natsort import natsorted

        ports = ["Ethernet12", "Ethernet4", "Ethernet100", "Ethernet8"]
        ctx, _ = self._make_ctx_shared_db(
            vlan_ports_data={("Vlan1000", p): {"tagging_mode": "untagged"} for p in ports},
        )

        cache = _get_brief_cache(ctx)
        assert cache["ports_by_vlan"]["Vlan1000"] == natsorted(ports)

    def test_cache_tagging_aligned_with_ports(self):
        """tagging_by_vlan must have the same order as ports_by_vlan so the
        two columns line up row-for-row in the table."""
        from show.vlan import _get_brief_cache

        members = {
            ("Vlan1000", "Ethernet12"): {"tagging_mode": "untagged"},
            ("Vlan1000", "Ethernet4"): {"tagging_mode": "tagged"},
            ("Vlan1000", "Ethernet8"): {"tagging_mode": "untagged"},
        }
        ctx, _ = self._make_ctx_shared_db(vlan_ports_data=members)

        cache = _get_brief_cache(ctx)
        ports = cache["ports_by_vlan"]["Vlan1000"]
        tags = cache["tagging_by_vlan"]["Vlan1000"]
        assert len(ports) == len(tags)
        # Verify alignment: each port maps to the right tagging mode
        for port, tag in zip(ports, tags):
            expected = members[("Vlan1000", port)]["tagging_mode"]
            assert tag == expected, f"Tagging mismatch for {port}: got {tag!r}, expected {expected!r}"

    def test_cache_no_alias_converter_in_default_mode(self):
        """In 'default' naming mode the alias converter must be None
        (no PORT-table read needed)."""
        from show.vlan import _get_brief_cache
        import os

        os.environ['SONIC_CLI_IFACE_MODE'] = 'default'
        try:
            ctx, _ = self._make_ctx_shared_db()
            cache = _get_brief_cache(ctx)
            assert cache['iface_alias_converter'] is None
            assert cache['naming_mode'] == 'default'
        finally:
            os.environ['SONIC_CLI_IFACE_MODE'] = 'default'

    # ------------------------------------------------------------------
    # Unit tests: _clear_brief_cache
    # ------------------------------------------------------------------

    def test_clear_removes_cache_attribute(self):
        """_clear_brief_cache must delete the stashed attribute."""
        from show.vlan import _get_brief_cache, _clear_brief_cache, _BRIEF_CACHE_ATTR

        ctx, db = self._make_ctx_shared_db()
        _get_brief_cache(ctx)

        assert hasattr(db, _BRIEF_CACHE_ATTR)
        _clear_brief_cache(db)
        assert not hasattr(db, _BRIEF_CACHE_ATTR)

    def test_clear_is_idempotent_when_no_cache(self):
        """_clear_brief_cache must not raise when called on an object
        that has no cache attribute."""
        from show.vlan import _clear_brief_cache

        class FakeDb:
            pass

        _clear_brief_cache(FakeDb())   # must not raise

    def test_clear_allows_rebuild_with_fresh_data(self):
        """After _clear_brief_cache the next _get_brief_cache call must
        rebuild indexes from the current vlan_ip_data in ctx."""
        from show.vlan import _get_brief_cache, _clear_brief_cache

        ctx, db = self._make_ctx_shared_db(
            vlan_ip_data={("Vlan1000", "10.0.0.1/24"): {}},
        )

        cache_before = _get_brief_cache(ctx)
        assert "Vlan1000" in cache_before["ip_by_vlan"]

        _clear_brief_cache(db)

        # Replace vlan_ip_data in ctx with different data
        new_ip_data = {("Vlan2000", "10.0.2.1/24"): {}}
        new_cfg = ({}, new_ip_data, {})
        ctx2 = (new_cfg, db)

        cache_after = _get_brief_cache(ctx2)
        assert "Vlan2000" in cache_after["ip_by_vlan"]
        assert "Vlan1000" not in cache_after["ip_by_vlan"]
        assert cache_before is not cache_after

    # ------------------------------------------------------------------
    # Integration tests: brief() command
    # ------------------------------------------------------------------

    def test_brief_calls_clear_cache_in_finally_on_exception(self):
        """If a column getter raises, brief()'s finally block must still
        invoke _clear_brief_cache so the cache is not left dangling."""
        import show.vlan as vlan_show

        runner = CliRunner()
        db = Db()

        original_cols = vlan_show.VlanBrief.COLUMNS[:]

        def _failing_getter(ctx, vlan):
            raise RuntimeError("simulated getter failure")

        vlan_show.VlanBrief.COLUMNS = [
            ("VLAN ID", vlan_show.get_vlan_id),
            ("Bad", _failing_getter),
        ]
        try:
            with mock.patch.object(
                vlan_show, '_clear_brief_cache',
                wraps=vlan_show._clear_brief_cache,
            ) as mock_clear:
                result = runner.invoke(
                    show.cli.commands["vlan"].commands["brief"], [], obj=db
                )
            # The exception must propagate (exit_code != 0)
            assert result.exit_code != 0
            # _clear_brief_cache must have been called at least once (the
            # finally-block call is guaranteed regardless of exceptions).
            assert mock_clear.call_count >= 1
        finally:
            vlan_show.VlanBrief.COLUMNS = original_cols

    def test_brief_second_invocation_reflects_added_vlan(self, mock_restart_dhcp_relay_service):
        """Mutating the DB between two brief() calls on the same Db object
        must be visible in the second call -- stale cache must not bleed
        across invocations."""
        from sonic_py_common import multi_asic as _sonic_multi_asic

        runner = CliRunner()
        db = Db()

        # Patch DB connections so brief() uses db.cfgdb throughout.
        with mock.patch.object(_sonic_multi_asic, 'connect_config_db_for_ns',
                               return_value=db.cfgdb), \
             mock.patch.object(_sonic_multi_asic, 'connect_to_all_dbs_for_ns',
                               return_value=db.db):

            # First call: baseline -- Vlan1001 must not exist yet.
            # Use '|      1001 |' (the tabulate cell format) to avoid matching
            # 'PortChannel1001' which also contains the substring '1001'.
            result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [])
            assert result.exit_code == 0
            assert "|      1001 |" not in result.output

            # Mutate: add a new VLAN
            result = runner.invoke(
                config.config.commands["vlan"].commands["add"], ["1001"], obj=db
            )
            assert result.exit_code == 0

            # Second call: new VLAN must appear
            result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [])
            assert result.exit_code == 0
            assert "|      1001 |" in result.output

    def test_brief_second_invocation_reflects_removed_member(self):
        """Removing a VLAN member between two brief() calls must be
        visible in the second call -- no stale ports from the first call."""
        from sonic_py_common import multi_asic as _sonic_multi_asic

        runner = CliRunner()
        db = Db()

        # Patch DB connections so brief() uses db.cfgdb throughout.
        with mock.patch.object(_sonic_multi_asic, 'connect_config_db_for_ns',
                               return_value=db.cfgdb), \
             mock.patch.object(_sonic_multi_asic, 'connect_to_all_dbs_for_ns',
                               return_value=db.db):

            # First call: Ethernet4 is a member of Vlan1000
            result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [])
            assert result.exit_code == 0
            assert "Ethernet4" in result.output

            # Mutate: remove Ethernet4 from Vlan1000 directly in the DB
            db.cfgdb.set_entry("VLAN_MEMBER", ("Vlan1000", "Ethernet4"), None)

            # Second call: output must differ from baseline (Ethernet4 removed)
            result = runner.invoke(show.cli.commands["vlan"].commands["brief"], [])
            assert result.exit_code == 0
            assert result.output != show_vlan_brief_output

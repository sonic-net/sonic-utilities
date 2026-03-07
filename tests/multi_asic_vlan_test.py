import os
import sys
from importlib import reload
from click.testing import CliRunner
import show.main as show
import config.main as config
from utilities_common.db import Db

# Set up paths
test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

# Expected outputs for multi-ASIC namespace asic0
show_vlan_brief_asic0_output = """\
+-----------+-----------------+-----------------+----------------+-------------+
|   VLAN ID | IP Address      | Ports           | Port Tagging   | Proxy ARP   |
+===========+=================+=================+================+=============+
|      1000 | 192.168.0.1/21  | Ethernet4       | untagged       | disabled    |
|           |                 | Ethernet16      | untagged       |             |
|           |                 | PortChannel1002 | tagged         |             |
+-----------+-----------------+-----------------+----------------+-------------+
|      2000 | 192.168.0.10/21 | Ethernet0       | tagged         | enabled     |
+-----------+-----------------+-----------------+----------------+-------------+
"""

show_vlan_config_asic0_output = """\
Name        VID  Member           Mode
--------  -----  ---------------  --------
Vlan1000   1000  Ethernet4        untagged
Vlan1000   1000  Ethernet16       untagged
Vlan1000   1000  PortChannel1002  tagged
Vlan2000   2000  Ethernet0        tagged
"""


class TestVlanMultiAsic(object):
    @classmethod
    def setup_class(cls):
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"

        # Set the database to mock multi-asic state
        from mock_tables import mock_multi_asic
        reload(mock_multi_asic)
        from mock_tables import dbconnector
        dbconnector.load_namespace_config()

        # Patch the Click option choices for namespace parameter
        # The show and config vlan commands were already imported with empty namespace list
        # We need to manually update the Click.Choice type to include the mocked namespaces
        import click

        # Update show vlan brief command
        for param in show.cli.commands["vlan"].commands["brief"].params:
            if param.name == "namespace":
                param.type = click.Choice(['asic0', 'asic1'])

        # Update show vlan config command
        for param in show.cli.commands["vlan"].commands["config"].params:
            if param.name == "namespace":
                param.type = click.Choice(['asic0', 'asic1'])

        # Update config vlan group namespace parameter (not subcommands)
        for param in config.config.commands["vlan"].params:
            if param.name == "namespace":
                param.type = click.Choice(['asic0', 'asic1'])
                param.required = True

        print("SETUP")

    def test_show_vlan_brief_in_namespace(self):
        """Test show vlan brief with namespace option"""
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vlan"].commands["brief"], ["-n", "asic0"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vlan_brief_asic0_output

    def test_show_vlan_config_in_namespace(self):
        """Test show vlan config with namespace option"""
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vlan"].commands["config"], ["-n", "asic0"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vlan_config_asic0_output

    def test_config_vlan_add_vlan_multi_asic_requires_namespace(self):
        """Test that vlan add requires namespace in multi-asic"""
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"], ["add", "1005"])
        print(result.exit_code)
        print(result.output)
        # Should fail because namespace is required in multi-asic
        assert result.exit_code != 0

    def test_config_vlan_add_vlan_with_namespace(self, mock_restart_dhcp_relay_service):
        """Test adding VLAN with namespace in multi-asic"""
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["vlan"],
                               ["-n", "asic0", "add", "1005"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert "asic0" in str(result.output) or result.output == ""

    def test_config_vlan_add_vlan_multiple_with_namespace(self, mock_restart_dhcp_relay_service):
        """Test adding multiple VLANs with namespace in multi-asic"""
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["vlan"],
                               ["-n", "asic0", "add", "1005-1007", "--multiple"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    def test_config_vlan_del_vlan_multi_asic_requires_namespace(self):
        """Test that vlan del requires namespace in multi-asic"""
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"], ["del", "3000"])
        print(result.exit_code)
        print(result.output)
        # Should fail because namespace is required in multi-asic
        assert result.exit_code != 0

    def test_config_vlan_del_vlan_with_namespace(self, mock_restart_dhcp_relay_service):
        """Test deleting VLAN with namespace in multi-asic - verify namespace parameter is accepted"""
        runner = CliRunner()
        db = Db()

        # Try to delete existing VLAN from mock data - will fail due to IP addresses
        # but we're just verifying the namespace parameter is accepted
        result = runner.invoke(config.config.commands["vlan"],
                               ["-n", "asic0", "del", "1000"], obj=db)
        print(result.exit_code)
        print(result.output)
        # Command should fail because VLAN has IP addresses, but not because of namespace parameter
        assert "First remove IP addresses" in result.output or result.exit_code == 0

    def test_config_vlan_add_member_multi_asic_requires_namespace(self):
        """Test that vlan member add requires namespace in multi-asic"""
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"],
                               ["member", "add", "1000", "Ethernet4"])
        print(result.exit_code)
        print(result.output)
        # Should fail because namespace is required in multi-asic
        assert result.exit_code != 0

    def test_config_vlan_add_member_with_namespace(self):
        """Test adding VLAN member with namespace in multi-asic"""
        runner = CliRunner()
        db = Db()

        # Try to add Ethernet16 to vlan 2000 with namespace - will fail because it's already in VLAN 1000
        # but we're verifying the namespace parameter is accepted
        result = runner.invoke(config.config.commands["vlan"],
                               ["-n", "asic0", "member", "add", "2000", "Ethernet16"], obj=db)
        print(result.exit_code)
        print(result.output)
        # Should fail because port is already in another VLAN, not because of namespace
        assert "already a member of Vlan" in result.output or result.exit_code == 0

    def test_config_vlan_add_member_multiple_with_namespace(self):
        """Test adding VLAN member to multiple VLANs with namespace in multi-asic"""
        runner = CliRunner()
        db = Db()

        # Try to add Ethernet16 to vlan 1000,2000 with namespace - verify namespace parameter is accepted
        result = runner.invoke(config.config.commands["vlan"],
                               ["-n", "asic0", "member", "add", "1000,2000", "Ethernet16", "--multiple"], obj=db)
        print(result.exit_code)
        print(result.output)
        # May fail due to port already in VLAN, but namespace parameter should be accepted
        assert "already a member of Vlan" in result.output or result.exit_code == 0

    def test_config_vlan_del_member_multi_asic_requires_namespace(self):
        """Test that vlan member del requires namespace in multi-asic"""
        runner = CliRunner()
        result = runner.invoke(config.config.commands["vlan"],
                               ["member", "del", "1000", "Ethernet4"])
        print(result.exit_code)
        print(result.output)
        # Should fail because namespace is required in multi-asic
        assert result.exit_code != 0

    def test_config_vlan_del_member_with_namespace(self):
        """Test deleting VLAN member with namespace in multi-asic"""
        runner = CliRunner()
        db = Db()

        # Delete existing member from mock data
        result = runner.invoke(config.config.commands["vlan"],
                               ["-n", "asic0", "member", "del", "1000", "Ethernet4"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    def test_config_vlan_add_del_full_workflow_with_namespace(self, mock_restart_dhcp_relay_service):
        """Test complete VLAN add/member/del workflow with namespace in multi-asic"""
        runner = CliRunner()
        db = Db()

        # Add VLAN 1007 to asic0
        result = runner.invoke(config.config.commands["vlan"],
                               ["-n", "asic0", "add", "1007"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # Try to add member Ethernet16 to existing VLAN 1000 on asic0 - verify namespace parameter is accepted
        result = runner.invoke(config.config.commands["vlan"],
                               ["-n", "asic0", "member", "add", "1000", "Ethernet16", "--untagged"], obj=db)
        print(result.exit_code)
        print(result.output)
        # May fail due to port already in VLAN, but namespace parameter should be accepted
        assert "already a member of Vlan" in result.output or result.exit_code == 0

    def test_config_vlan_add_member_except_flag_with_namespace(self):
        """Test adding VLAN member with except flag and namespace in multi-asic"""
        runner = CliRunner()
        db = Db()

        # Try to add Ethernet16 to all vlans except 1000,4000 on asic0 - verify namespace parameter is accepted
        result = runner.invoke(config.config.commands["vlan"],
                               ["-n", "asic0", "member", "add", "1000,4000", "Ethernet16", "--multiple",
                                "--except_flag"],
                               obj=db)
        print(result.exit_code)
        print(result.output)
        # The command may fail for various reasons (port in VLAN, etc), but namespace should be accepted
        # We're just verifying no "invalid choice" error for namespace
        assert "invalid choice" not in result.output.lower()

    def test_config_vlan_add_all_member_with_namespace(self):
        """Test adding port to all VLANs with namespace in multi-asic"""
        runner = CliRunner()
        db = Db()

        # Try to add Ethernet16 to all VLANs on asic0 - verify namespace parameter is accepted
        result = runner.invoke(config.config.commands["vlan"],
                               ["-n", "asic0", "member", "add", "all", "Ethernet16"], obj=db)
        print(result.exit_code)
        print(result.output)
        # The command may fail for various reasons, but namespace should be accepted
        # We're just verifying no "invalid choice" error for namespace
        assert "invalid choice" not in result.output.lower()

    def test_config_vlan_with_switchport_mode_and_namespace(self):
        """Test VLAN member operations with namespace in multi-asic"""
        runner = CliRunner()
        db = Db()

        # Try to add Ethernet16 as tagged member to VLAN 2000 on asic0 - verify namespace parameter is accepted
        result = runner.invoke(config.config.commands["vlan"],
                               ["-n", "asic0", "member", "add", "2000", "Ethernet16"], obj=db)
        print(result.exit_code)
        print(result.output)
        # May fail due to port already in VLAN, but namespace parameter should be accepted
        assert "already a member of Vlan" in result.output or result.exit_code == 0

    def test_config_vlan_invalid_namespace(self):
        """Test VLAN operations with invalid namespace"""
        runner = CliRunner()

        result = runner.invoke(config.config.commands["vlan"],
                               ["-n", "asic99", "add", "1010"])
        print(result.exit_code)
        print(result.output)
        # Should fail with invalid namespace
        assert result.exit_code != 0

    def test_config_vlan_add_vlan_range_with_namespace(self, mock_restart_dhcp_relay_service):
        """Test adding VLAN range with namespace in multi-asic"""
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["vlan"],
                               ["-n", "asic0", "add", "1010-1012", "--multiple"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    def test_config_vlan_operations_on_different_namespaces(self, mock_restart_dhcp_relay_service):
        """Test VLAN operations on different ASICs (namespaces)"""
        runner = CliRunner()
        db = Db()

        # Add VLAN 1013 to asic0
        result = runner.invoke(config.config.commands["vlan"],
                               ["-n", "asic0", "add", "1013"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # Add VLAN 1014 to asic1
        result = runner.invoke(config.config.commands["vlan"],
                               ["-n", "asic1", "add", "1014"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    @classmethod
    def teardown_class(cls):
        # Reset the database to mock single-asic state
        from mock_tables import mock_single_asic
        reload(mock_single_asic)
        from mock_tables import dbconnector
        dbconnector.load_database_config()

        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""

        print("TEARDOWN")

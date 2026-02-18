from unittest import mock

import pytest
from click.testing import CliRunner

import config.main as config
import show.main as show
from utilities_common.db import Db


@pytest.mark.usefixtures("setup_multi_asic_env")
class TestSubinterfaceMultiAsic(object):
    """Test subinterface operations on multi-asic platforms."""

    def test_add_del_subintf_with_namespace(self):
        """Test adding and deleting subinterface with namespace option"""
        runner = CliRunner()
        db = Db()
        # asic1 has Ethernet64 which is not a member of any portchannel or vlan
        cfgdb1 = db.cfgdb_clients['asic1']
        obj = {'db': cfgdb1, 'namespace': 'asic1'}

        # Add subinterface on asic1
        result = runner.invoke(config.config.commands["subinterface"].commands["add"],
                               ["Ethernet64.100"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert 'Ethernet64.100' in cfgdb1.get_table('VLAN_SUB_INTERFACE')
        assert cfgdb1.get_table('VLAN_SUB_INTERFACE')['Ethernet64.100']['admin_status'] == 'up'

        # Delete subinterface on asic1
        result = runner.invoke(config.config.commands["subinterface"].commands["del"],
                               ["Ethernet64.100"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert 'Ethernet64.100' not in cfgdb1.get_table('VLAN_SUB_INTERFACE')

    def test_subintf_with_vlan_id_and_namespace(self):
        """Test adding subinterface with VLAN ID using namespace option"""
        runner = CliRunner()
        db = Db()
        cfgdb1 = db.cfgdb_clients['asic1']
        obj = {'db': cfgdb1, 'namespace': 'asic1'}

        # Add subinterface with VLAN ID on asic1
        result = runner.invoke(config.config.commands["subinterface"].commands["add"],
                               ["Eth64.200", "200"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert 'Eth64.200' in cfgdb1.get_table('VLAN_SUB_INTERFACE')
        assert cfgdb1.get_table('VLAN_SUB_INTERFACE')['Eth64.200']['vlan'] == '200'
        assert cfgdb1.get_table('VLAN_SUB_INTERFACE')['Eth64.200']['admin_status'] == 'up'

        # Delete subinterface on asic1
        result = runner.invoke(config.config.commands["subinterface"].commands["del"],
                               ["Eth64.200"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert 'Eth64.200' not in cfgdb1.get_table('VLAN_SUB_INTERFACE')

    def test_subintf_namespace_isolation(self):
        """Test that subinterfaces are isolated between namespaces"""
        runner = CliRunner()
        db = Db()
        cfgdb1 = db.cfgdb_clients['asic1']
        obj = {'db': cfgdb1, 'namespace': 'asic1'}

        # Add subinterface on asic1 with two different subinterfaces
        # to verify they are properly stored
        result = runner.invoke(config.config.commands["subinterface"].commands["add"],
                               ["Ethernet64.100"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        result = runner.invoke(config.config.commands["subinterface"].commands["add"],
                               ["Ethernet64.200"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        # Verify both subinterfaces exist in asic1
        assert 'Ethernet64.100' in cfgdb1.get_table('VLAN_SUB_INTERFACE')
        assert 'Ethernet64.200' in cfgdb1.get_table('VLAN_SUB_INTERFACE')

        # Cleanup
        result = runner.invoke(config.config.commands["subinterface"].commands["del"],
                               ["Ethernet64.100"], obj=obj)
        assert result.exit_code == 0
        result = runner.invoke(config.config.commands["subinterface"].commands["del"],
                               ["Ethernet64.200"], obj=obj)
        assert result.exit_code == 0

    def test_subintf_invalid_parent_in_namespace(self):
        """Test that creating subinterface on non-existent parent interface fails"""
        runner = CliRunner()
        db = Db()
        cfgdb0 = db.cfgdb_clients['asic0']
        obj = {'db': cfgdb0, 'namespace': 'asic0'}

        # Try to add subinterface on a port that doesn't exist in asic0
        # Ethernet64 exists only in asic1
        result = runner.invoke(config.config.commands["subinterface"].commands["add"],
                               ["Ethernet64.100"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert "parent interface not found" in result.output

    def test_subintf_portchannel_with_namespace(self):
        """Test adding subinterface on PortChannel with namespace option"""
        runner = CliRunner()
        db = Db()
        cfgdb1 = db.cfgdb_clients['asic1']
        obj = {'db': cfgdb1, 'namespace': 'asic1'}

        # Add subinterface on PortChannel4009 in asic1
        # PortChannel4009 exists in asic1 and is not a VLAN member
        result = runner.invoke(config.config.commands["subinterface"].commands["add"],
                               ["Po4009.300", "300"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert 'Po4009.300' in cfgdb1.get_table('VLAN_SUB_INTERFACE')
        assert cfgdb1.get_table('VLAN_SUB_INTERFACE')['Po4009.300']['vlan'] == '300'
        assert cfgdb1.get_table('VLAN_SUB_INTERFACE')['Po4009.300']['admin_status'] == 'up'

        # Delete subinterface
        result = runner.invoke(config.config.commands["subinterface"].commands["del"],
                               ["Po4009.300"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert 'Po4009.300' not in cfgdb1.get_table('VLAN_SUB_INTERFACE')

    def test_subintf_on_lag_member_with_namespace(self):
        """Test that creating subinterface on LAG member fails with namespace"""
        runner = CliRunner()
        db = Db()
        cfgdb0 = db.cfgdb_clients['asic0']
        obj = {'db': cfgdb0, 'namespace': 'asic0'}

        # Ethernet0 is a member of PortChannel1002 in asic0
        result = runner.invoke(config.config.commands["subinterface"].commands["add"],
                               ["Ethernet0.100"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert "member of portchannel" in result.output

    def test_del_nonexistent_subintf_with_namespace(self):
        """Test deleting non-existent subinterface with namespace fails"""
        runner = CliRunner()
        db = Db()
        cfgdb1 = db.cfgdb_clients['asic1']
        obj = {'db': cfgdb1, 'namespace': 'asic1'}

        # Try to delete a subinterface that doesn't exist
        result = runner.invoke(config.config.commands["subinterface"].commands["del"],
                               ["Ethernet64.999"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

    def test_add_existing_subintf_with_namespace(self):
        """Test that adding duplicate subinterface fails with namespace"""
        runner = CliRunner()
        db = Db()
        cfgdb1 = db.cfgdb_clients['asic1']
        obj = {'db': cfgdb1, 'namespace': 'asic1'}

        # Add subinterface first time
        result = runner.invoke(config.config.commands["subinterface"].commands["add"],
                               ["Ethernet64.400"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert 'Ethernet64.400' in cfgdb1.get_table('VLAN_SUB_INTERFACE')

        # Try to add same subinterface again - should fail
        result = runner.invoke(config.config.commands["subinterface"].commands["add"],
                               ["Ethernet64.400"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

        # Cleanup
        result = runner.invoke(config.config.commands["subinterface"].commands["del"],
                               ["Ethernet64.400"], obj=obj)
        assert result.exit_code == 0

    def test_subintf_name_too_long_with_namespace(self):
        """Test that subinterface name exceeding 15 characters fails with namespace"""
        runner = CliRunner()
        db = Db()
        cfgdb1 = db.cfgdb_clients['asic1']
        obj = {'db': cfgdb1, 'namespace': 'asic1'}

        # Subinterface name > 15 characters should fail
        result = runner.invoke(config.config.commands["subinterface"].commands["add"],
                               ["Ethernet64.000001", "1"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert "Subinterface name length should not exceed 15 characters" in result.output

    def test_subintf_short_name_without_vid_with_namespace(self):
        """Test that short name subinterface without VLAN ID fails with namespace"""
        runner = CliRunner()
        db = Db()
        cfgdb1 = db.cfgdb_clients['asic1']
        obj = {'db': cfgdb1, 'namespace': 'asic1'}

        # Short name (Eth64.500) without vid should fail
        result = runner.invoke(config.config.commands["subinterface"].commands["add"],
                               ["Eth64.500"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert "Encap vlan is mandatory" in result.output

    def test_subintf_duplicate_encap_vlan_with_namespace(self):
        """Test that duplicate encap VLAN on same parent interface fails with namespace"""
        runner = CliRunner()
        db = Db()
        cfgdb1 = db.cfgdb_clients['asic1']
        obj = {'db': cfgdb1, 'namespace': 'asic1'}

        # Add first subinterface with vlan 600
        result = runner.invoke(config.config.commands["subinterface"].commands["add"],
                               ["Ethernet64.600"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert 'Ethernet64.600' in cfgdb1.get_table('VLAN_SUB_INTERFACE')

        # Try to add another subinterface with same encap vlan 600 - should fail
        result = runner.invoke(config.config.commands["subinterface"].commands["add"],
                               ["Eth64.601", "600"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert "encap already configured" in result.output

        # Cleanup
        result = runner.invoke(config.config.commands["subinterface"].commands["del"],
                               ["Ethernet64.600"], obj=obj)
        assert result.exit_code == 0

    def test_subintf_invalid_format_with_namespace(self):
        """Test that invalid subinterface format fails with namespace"""
        runner = CliRunner()
        db = Db()
        cfgdb1 = db.cfgdb_clients['asic1']
        obj = {'db': cfgdb1, 'namespace': 'asic1'}

        # Missing dot separator - invalid format for add
        result = runner.invoke(config.config.commands["subinterface"].commands["add"],
                               ["Ethernet64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

        # Invalid prefix (not Eth or Po)
        result = runner.invoke(config.config.commands["subinterface"].commands["add"],
                               ["Vlan100.10"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

        # Missing dot separator - invalid format for del
        result = runner.invoke(config.config.commands["subinterface"].commands["del"],
                               ["Ethernet64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

    def test_show_subinterfaces_status_multi_asic(self):
        """Test show subinterfaces status builds correct command in multi-asic mode"""
        status_cmd = show.cli.commands["subinterfaces"].commands["status"]
        with mock.patch.object(show, 'run_command') as mock_run, \
             mock.patch.object(show.multi_asic, 'is_multi_asic', return_value=True):
            status_cmd.callback(
                subinterfacename=None, namespace=None,
                display="frontend", verbose=True
            )
            cmd = mock_run.call_args[0][0]
            assert cmd == ['intfutil', '-c', 'status', '-i', 'subport',
                           '-d', 'frontend']

    def test_show_subinterfaces_status_multi_asic_with_namespace(self):
        """Test show subinterfaces status passes namespace in multi-asic mode"""
        status_cmd = show.cli.commands["subinterfaces"].commands["status"]
        with mock.patch.object(show, 'run_command') as mock_run, \
             mock.patch.object(show.multi_asic, 'is_multi_asic', return_value=True):
            status_cmd.callback(
                subinterfacename=None, namespace="asic0",
                display="frontend", verbose=True
            )
            cmd = mock_run.call_args[0][0]
            assert cmd == ['intfutil', '-c', 'status', '-i', 'subport',
                           '-d', 'frontend', '-n', 'asic0']

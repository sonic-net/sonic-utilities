import os
from click.testing import CliRunner
import config.main as config
import show.main as show
from utilities_common.db import Db

show_ip_interfaces_loopback_action_output="""\
Interface        Action
---------------  --------
Eth36.10         drop
Ethernet0        forward
PortChannel0001  drop
Vlan3000         forward
"""

class TestLoopbackAction(object):
    @classmethod
    def setup_class(cls):
        print("\nSETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "1"

    def test_config_loopback_action_on_physical_interface(self):        
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}
        action = 'drop'
        iface = 'Ethernet0'

        result = runner.invoke(config.config.commands['interface'].commands["ip"].commands['loopback-action'], [iface, action], obj=obj)
    
        table = db.cfgdb.get_table('INTERFACE')
        assert(table[iface]['loopback_action'] == action)
        
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        
    def test_config_loopback_action_on_physical_interface_alias(self):
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}
        action = 'forward'
        iface = 'Ethernet0'
        iface_alias = 'etp1'

        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(config.config.commands['interface'].commands["ip"].commands['loopback-action'], [iface_alias, action], obj=obj)
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"

        table = db.cfgdb.get_table('INTERFACE')
        assert(table[iface]['loopback_action'] == action)

        print(result.exit_code, result.output)
        assert result.exit_code == 0

    def test_config_loopback_action_on_port_channel_interface(self):        
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}
        action = 'forward'
        iface = 'PortChannel0002'

        result = runner.invoke(config.config.commands['interface'].commands["ip"].commands['loopback-action'], [iface, action], obj=obj)
    
        table = db.cfgdb.get_table('PORTCHANNEL_INTERFACE')
        assert(table[iface]['loopback_action'] == action)
        
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        
    def test_config_loopback_action_on_vlan_interface(self):        
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}
        action = 'drop'
        iface = 'Vlan1000'

        result = runner.invoke(config.config.commands['interface'].commands["ip"].commands['loopback-action'], [iface, action], obj=obj)
    
        table = db.cfgdb.get_table('VLAN_INTERFACE')
        assert(table[iface]['loopback_action'] == action)
        
        print(result.exit_code, result.output)
        assert result.exit_code == 0  
            
    def test_config_loopback_action_on_subinterface(self):        
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}
        action = 'forward'
        iface = 'Ethernet0.10'

        result = runner.invoke(config.config.commands['interface'].commands["ip"].commands['loopback-action'], [iface, action], obj=obj)
    
        table = db.cfgdb.get_table('VLAN_SUB_INTERFACE')
        assert(table[iface]['loopback_action'] == action)
        
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        
    def test_show_ip_interfaces_loopback_action(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["ip"].commands["interfaces"].commands["loopback-action"], [])
        
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert result.output == show_ip_interfaces_loopback_action_output

    def test_config_loopback_action_on_non_ip_interface(self):        
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}
        action = 'forward'
        iface = 'Ethernet0.11'
        ERROR_MSG = "Error: Interface {} is not an IP interface".format(iface)

        result = runner.invoke(config.config.commands['interface'].commands["ip"].commands['loopback-action'], [iface, action], obj=obj)
    
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        
    def test_config_loopback_action_invalid_action(self):        
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}
        action = 'xforwardx'
        iface = 'Ethernet0'
        ERROR_MSG = "Error: Invalid action"

        result = runner.invoke(config.config.commands['interface'].commands["ip"].commands['loopback-action'], [iface, action], obj=obj)
    
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert ERROR_MSG in result.output

    @classmethod
    def teardown_class(cls):
        print("\nTEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"

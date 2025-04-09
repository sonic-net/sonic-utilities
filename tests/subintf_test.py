import os
import traceback

from click.testing import CliRunner

import config.main as config
import show.main as show
from utilities_common.db import Db

SUB_INTF_ON_LAG_MEMBER_ERR="""\
Usage: add [OPTIONS] <subinterface_name> <vid>
Try "add --help" for help.

Error: Ethernet32 is configured as a member of portchannel. Cannot configure subinterface
"""

class TestSubinterface(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

    def test_add_del_subintf_short_name(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["subinterface"].commands["add"], ["Eth0.102", "1002"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Eth0.102') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')
        assert db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Eth0.102']['vlan'] == '1002'
        assert db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Eth0.102']['admin_status'] == 'up'

        result = runner.invoke(config.config.commands["subinterface"].commands["add"], ["Po0004.104", "1004"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Po0004.104') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')
        assert db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Po0004.104']['vlan'] == '1004'
        assert db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Po0004.104']['admin_status'] == 'up'

        result = runner.invoke(config.config.commands["subinterface"].commands["del"], ["Eth0.102"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Eth0.102') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')

        result = runner.invoke(config.config.commands["subinterface"].commands["del"], ["Po0004.104"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Po0004.104') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')

    def test_add_del_subintf_with_long_name(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["subinterface"].commands["add"], ["Ethernet0.102"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet0.102') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')
        assert db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Ethernet0.102']['admin_status'] == 'up'

        result = runner.invoke(config.config.commands["subinterface"].commands["del"], ["Ethernet0.102"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet0.102') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')

    def test_add_existing_subintf_again(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["subinterface"].commands["add"], ["Ethernet0.102"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet0.102') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')
        assert db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Ethernet0.102']['admin_status'] == 'up'

        #Check if same long format subintf creation is rejected
        result = runner.invoke(config.config.commands["subinterface"].commands["add"], ["Ethernet0.102"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

        #Check if same short format subintf creation with same encap vlan is rejected
        result = runner.invoke(config.config.commands["subinterface"].commands["add"], ["Eth0.1002", "102"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert ('Eth0.1002') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')


    def test_delete_non_existing_subintf(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["subinterface"].commands["del"], ["Ethernet0.102"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

        result = runner.invoke(config.config.commands["subinterface"].commands["del"], ["Eth0.102"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

        result = runner.invoke(config.config.commands["subinterface"].commands["del"], ["PortChannel0004.104"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

        result = runner.invoke(config.config.commands["subinterface"].commands["del"], ["Po0004.104"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

    def test_invalid_subintf_creation(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["subinterface"].commands["add"], ["Ethernet1000.102"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

        result = runner.invoke(config.config.commands["subinterface"].commands["add"], ["PortChannel0008.102"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

        result = runner.invoke(config.config.commands["subinterface"].commands["add"], ["Ethe0.102"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

        #Short format subintf without encap vlan should be rejected
        result = runner.invoke(config.config.commands["subinterface"].commands["add"], ["Eth0.102"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

        result = runner.invoke(config.config.commands["subinterface"].commands["add"], ["Po0004.102"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

    def test_subintf_creation_on_lag_member(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["subinterface"].commands["add"], ["Ethernet32.10"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert(result.output == SUB_INTF_ON_LAG_MEMBER_ERR)

        result = runner.invoke(config.config.commands["subinterface"].commands["add"], ["Eth32.20"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert(result.output == SUB_INTF_ON_LAG_MEMBER_ERR)

    def test_subintf_vrf_bind_unbind(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["subinterface"].commands["add"], ["Ethernet0.102"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet0.102') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')
        assert db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Ethernet0.102']['admin_status'] == 'up'

        expected_output_bind = "Interface Ethernet0.102 IP disabled and address(es) removed due to binding VRF Vrf1.\n"
        vrf_obj = {'config_db':db.cfgdb, 'namespace':db.db.namespace}
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["bind"], ["Ethernet0.102", "Vrf1"], obj=vrf_obj)
        assert result.exit_code == 0
        assert ('Vrf1') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Ethernet0.102']['vrf_name']
        assert result.output == expected_output_bind

        expected_output_unbind = "Interface Ethernet0.102 IP disabled and address(es) removed due to unbinding VRF.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["unbind"], ["Ethernet0.102"], obj=vrf_obj)
        assert result.exit_code == 0
        assert ('vrf_name') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Ethernet0.102']
        assert result.output == expected_output_unbind

        result = runner.invoke(config.config.commands["subinterface"].commands["del"], ["Ethernet0.102"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet0.102') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')

        #shut name subintf vrf bind unbind check
        result = runner.invoke(config.config.commands["subinterface"].commands["add"], ["Eth0.1002", "2002"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Eth0.1002') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')

        expected_output_bind = "Interface Eth0.1002 IP disabled and address(es) removed due to binding VRF Vrf1.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["bind"], ["Eth0.1002", "Vrf1"], obj=vrf_obj)
        assert result.exit_code == 0
        assert ('Vrf1') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Eth0.1002']['vrf_name']
        assert result.output == expected_output_bind

        expected_output_unbind = "Interface Eth0.1002 IP disabled and address(es) removed due to unbinding VRF.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["unbind"], ["Eth0.1002"], obj=vrf_obj)
        assert result.exit_code == 0
        assert ('vrf_name') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Eth0.1002']
        assert result.output == expected_output_unbind

        result = runner.invoke(config.config.commands["subinterface"].commands["del"], ["Eth0.1002"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Eth0.1002') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')

        #Po subintf vrf bind unbind check
        result = runner.invoke(config.config.commands["subinterface"].commands["add"], ["Po0004.1004", "2004"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Po0004.1004') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')

        expected_output_bind = "Interface Po0004.1004 IP disabled and address(es) removed due to binding VRF Vrf1.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["bind"], ["Po0004.1004", "Vrf1"], obj=vrf_obj)
        assert result.exit_code == 0
        assert ('Vrf1') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Po0004.1004']['vrf_name']
        assert result.output == expected_output_bind

        expected_output_unbind = "Interface Po0004.1004 IP disabled and address(es) removed due to unbinding VRF.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["unbind"], ["Po0004.1004"], obj=vrf_obj)
        assert result.exit_code == 0
        assert ('vrf_name') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Po0004.1004']
        assert result.output == expected_output_unbind

        result = runner.invoke(config.config.commands["subinterface"].commands["del"], ["Po0004.1004"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Po0004.1004') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')

    def test_subintf_vnet_bind_unbind(self):
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb, 'namespace': db.db.namespace}
        intf_obj = {'db': db.cfgdb, 'namespace': db.db.namespace}

        # Add Vnet_1000
        result = runner.invoke(config.config.commands["vnet"].commands["add"], ["Vnet_1000", "222", "tunnel1"], obj=obj)
        print(db.cfgdb.get_table('VNET'))
        assert ('Vnet_1000') in db.cfgdb.get_table('VNET')
        assert result.exit_code == 0

        result = runner.invoke(config.config.commands["subinterface"].commands["add"], ["Ethernet0.102"], obj=intf_obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet0.102') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')
        assert db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Ethernet0.102']['admin_status'] == 'up'

        expected_output = "Interface Ethernet0.102 IP disabled and address(es) removed due to binding VRF Vnet_1000.\n"
        cmds = config.config.commands["interface"].commands["vrf"].commands["bind"]
        result = runner.invoke(cmds, ["Ethernet0.102", "Vnet_1000"], obj=obj)
        assert result.exit_code == 0
        print(result.output)
        assert ('Vnet_1000') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Ethernet0.102']['vnet_name']
        assert result.output == expected_output

        expected_output = "Interface Ethernet0.102 IP disabled and address(es) removed due to unbinding VRF.\n"
        cmds = config.config.commands["interface"].commands["vrf"].commands["unbind"]
        result = runner.invoke(cmds, ["Ethernet0.102"], obj=obj)
        assert result.exit_code == 0
        assert ('vnet_name') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Ethernet0.102']
        assert result.output == expected_output

        result = runner.invoke(config.config.commands["subinterface"].commands["del"], ["Ethernet0.102"], obj=intf_obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet0.102') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')

        # shut name subintf vrf bind unbind check
        result = runner.invoke(config.config.commands["subinterface"].commands["add"], ["Eth0.1002", "2002"], obj=intf_obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Eth0.1002') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')

        output = "Interface Eth0.1002 IP disabled and address(es) removed due to binding VRF Vnet_1000.\n"
        cmds = config.config.commands["interface"].commands["vrf"].commands["bind"]
        result = runner.invoke(cmds, ["Eth0.1002", "Vnet_1000"], obj=obj)
        assert result.exit_code == 0
        assert ('Vnet_1000') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Eth0.1002']['vnet_name']
        assert result.output == output

        output = "Interface Eth0.1002 IP disabled and address(es) removed due to unbinding VRF.\n"
        cmds = config.config.commands["interface"].commands["vrf"].commands["unbind"]
        result = runner.invoke(cmds, ["Eth0.1002"], obj=obj)
        assert result.exit_code == 0
        assert ('vnet_name') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Eth0.1002']
        assert result.output == output

        result = runner.invoke(config.config.commands["subinterface"].commands["del"], ["Eth0.1002"], obj=intf_obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Eth0.1002') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')

        # Po subintf vrf bind unbind check
        cmds = config.config.commands["subinterface"].commands["add"]
        result = runner.invoke(cmds, ["Po0004.1004", "2004"], obj=intf_obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Po0004.1004') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')

        output = "Interface Po0004.1004 IP disabled and address(es) removed due to binding VRF Vnet_1000.\n"
        cmds = config.config.commands["interface"].commands["vrf"].commands["bind"]
        result = runner.invoke(cmds, ["Po0004.1004", "Vnet_1000"], obj=obj)
        assert result.exit_code == 0
        assert ('Vnet_1000') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Po0004.1004']['vnet_name']
        assert result.output == output

        output = "Interface Po0004.1004 IP disabled and address(es) removed due to unbinding VRF.\n"
        cmds = config.config.commands["interface"].commands["vrf"].commands["unbind"]
        result = runner.invoke(cmds, ["Po0004.1004"], obj=obj)
        assert result.exit_code == 0
        assert ('vnet_name') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Po0004.1004']
        assert result.output == output

        result = runner.invoke(config.config.commands["subinterface"].commands["del"], ["Po0004.1004"], obj=intf_obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Po0004.1004') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')


    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")

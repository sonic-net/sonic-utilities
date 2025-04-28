import os
import sys
from click.testing import CliRunner
from swsscommon.swsscommon import SonicV2Connector
from utilities_common.db import Db

import config.main as config
import show.main as show
import threading

DEFAULT_NAMESPACE = ''
test_path = os.path.dirname(os.path.abspath(__file__))
mock_db_path = os.path.join(test_path, "vrf_input")
mock_db_path_vnet = os.path.join(test_path, "vnet_input")

class TestShowVrf(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def update_statedb(self, db, db_name, key):
        import time
        time.sleep(0.5)
        db.delete(db_name, key)

    def test_vrf_show(self):
        from .mock_tables import dbconnector
        jsonfile_config = os.path.join(mock_db_path, "config_db")
        dbconnector.dedicated_dbs['CONFIG_DB'] = jsonfile_config
        runner = CliRunner()
        db = Db()
        expected_output = """\
VRF     Interfaces
------  ---------------
Vrf1
Vrf101  Ethernet0.10
Vrf102  Eth36.10
        PortChannel0002
        Vlan40
Vrf103  Ethernet4
        Loopback0
        Po0002.101
"""

        result = runner.invoke(show.cli.commands['vrf'], [], obj=db)
        dbconnector.dedicated_dbs = {}
        assert result.exit_code == 0
        assert result.output == expected_output

    def test_vrf_bind_unbind(self):
        from .mock_tables import dbconnector
        jsonfile_config = os.path.join(mock_db_path, "config_db")
        dbconnector.dedicated_dbs['CONFIG_DB'] = jsonfile_config
        runner = CliRunner()
        db = Db()
        expected_output = """\
VRF     Interfaces
------  ---------------
Vrf1
Vrf101  Ethernet0.10
Vrf102  Eth36.10
        PortChannel0002
        Vlan40
Vrf103  Ethernet4
        Loopback0
        Po0002.101
"""

        result = runner.invoke(show.cli.commands['vrf'], [], obj=db)
        dbconnector.dedicated_dbs = {}
        assert result.exit_code == 0
        assert result.output == expected_output


        vrf_obj = {'config_db':db.cfgdb, 'namespace':db.db.namespace}

        expected_output_unbind = "Interface Ethernet4 IP disabled and address(es) removed due to unbinding VRF.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["unbind"], ["Ethernet4"], obj=vrf_obj)

        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert 'Ethernet4' not in db.cfgdb.get_table('INTERFACE')
        assert result.output == expected_output_unbind

        expected_output_unbind = "Interface Loopback0 IP disabled and address(es) removed due to unbinding VRF.\n"

        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["unbind"], ["Loopback0"], obj=vrf_obj)

        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert 'Loopback0' not in db.cfgdb.get_table('LOOPBACK_INTERFACE')
        assert result.output == expected_output_unbind

        expected_output_unbind = "Interface Vlan40 IP disabled and address(es) removed due to unbinding VRF.\n"

        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["unbind"], ["Vlan40"], obj=vrf_obj)

        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert 'Vlan40' not in db.cfgdb.get_table('VLAN_INTERFACE')
        assert result.output == expected_output_unbind

        expected_output_unbind = "Interface PortChannel0002 IP disabled and address(es) removed due to unbinding VRF.\n"

        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["unbind"], ["PortChannel0002"], obj=vrf_obj)

        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert 'PortChannel002' not in db.cfgdb.get_table('PORTCHANNEL_INTERFACE')
        assert result.output == expected_output_unbind

        vrf_obj = {'config_db':db.cfgdb, 'namespace':DEFAULT_NAMESPACE}
        state_db = SonicV2Connector(use_unix_socket_path=True, namespace='')
        state_db.connect(state_db.STATE_DB, False)
        _hash = "INTERFACE_TABLE|Eth36.10"
        state_db.set(db.db.STATE_DB, _hash, "state", "ok")
        vrf_obj['state_db'] = state_db

        expected_output_unbind = "Interface Eth36.10 IP disabled and address(es) removed due to unbinding VRF.\n"
        T1 = threading.Thread( target = self.update_statedb, args = (state_db, db.db.STATE_DB, _hash))  
        T1.start()
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["unbind"], ["Eth36.10"], obj=vrf_obj)
        T1.join()
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('vrf_name', 'Vrf102') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Eth36.10']
        assert result.output == expected_output_unbind

        vrf_obj = {'config_db':db.cfgdb, 'namespace':DEFAULT_NAMESPACE}

        expected_output_unbind = "Interface Ethernet0.10 IP disabled and address(es) removed due to unbinding VRF.\n"

        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["unbind"], ["Ethernet0.10"], obj=vrf_obj)

        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('vrf_name', 'Vrf101') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Ethernet0.10']
        assert result.output == expected_output_unbind

        expected_output_unbind = "Interface Po0002.101 IP disabled and address(es) removed due to unbinding VRF.\n"

        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["unbind"], ["Po0002.101"], obj=vrf_obj)

        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('vrf_name', 'Vrf103') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Po0002.101']
        assert result.output == expected_output_unbind

        expected_output_bind = "Interface Ethernet0 IP disabled and address(es) removed due to binding VRF Vrf1.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["bind"], ["Ethernet0", "Vrf1"], obj=vrf_obj)
        assert result.exit_code == 0
        print(db.cfgdb.get_table('INTERFACE'))
        assert result.output == expected_output_bind
        assert ('Vrf1') in db.cfgdb.get_table('INTERFACE')['Ethernet0']['vrf_name']

        expected_output_bind = "Interface Loopback0 IP disabled and address(es) removed due to binding VRF Vrf101.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["bind"], ["Loopback0", "Vrf101"], obj=vrf_obj)
        assert result.exit_code == 0
        assert result.output == expected_output_bind
        assert ('Vrf101') in db.cfgdb.get_table('LOOPBACK_INTERFACE')['Loopback0']['vrf_name']

        expected_output_bind = "Interface Vlan40 IP disabled and address(es) removed due to binding VRF Vrf101.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["bind"], ["Vlan40", "Vrf101"], obj=vrf_obj)
        assert result.exit_code == 0
        assert result.output == expected_output_bind
        assert ('Vrf101') in db.cfgdb.get_table('VLAN_INTERFACE')['Vlan40']['vrf_name']

        expected_output_bind = "Interface PortChannel0002 IP disabled and address(es) removed due to binding VRF Vrf101.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["bind"], ["PortChannel0002", "Vrf101"], obj=vrf_obj)
        assert result.exit_code == 0
        assert result.output == expected_output_bind
        assert ('Vrf101') in db.cfgdb.get_table('PORTCHANNEL_INTERFACE')['PortChannel0002']['vrf_name']

        expected_output_bind = "Interface Eth36.10 IP disabled and address(es) removed due to binding VRF Vrf102.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["bind"], ["Eth36.10", "Vrf102"], obj=vrf_obj)
        assert result.exit_code == 0
        assert result.output == expected_output_bind
        assert ('Vrf102') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Eth36.10']['vrf_name']

        expected_output_bind = "Interface Ethernet0.10 IP disabled and address(es) removed due to binding VRF Vrf103.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["bind"], ["Ethernet0.10", "Vrf103"], obj=vrf_obj)
        assert result.exit_code == 0
        assert result.output == expected_output_bind
        assert ('Vrf103') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Ethernet0.10']['vrf_name']

        expected_output_bind = "Interface Po0002.101 IP disabled and address(es) removed due to binding VRF Vrf1.\n"
        result = runner.invoke(config.config.commands["interface"].commands["vrf"].commands["bind"], ["Po0002.101", "Vrf1"], obj=vrf_obj)
        assert result.exit_code == 0
        assert result.output == expected_output_bind
        assert ('Vrf1') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Po0002.101']['vrf_name']

        jsonfile_config = os.path.join(mock_db_path, "config_db")
        dbconnector.dedicated_dbs['CONFIG_DB'] = jsonfile_config

        expected_output = """\
VRF     Interfaces
------  ---------------
Vrf1
Vrf101  Ethernet0.10
Vrf102  Eth36.10
        PortChannel0002
        Vlan40
Vrf103  Ethernet4
        Loopback0
        Po0002.101
"""

        result = runner.invoke(show.cli.commands['vrf'], [], obj=db)
        dbconnector.dedicated_dbs = {}
        assert result.exit_code == 0
        assert result.output == expected_output

    def test_vnet_bind_unbind(self):
        from .mock_tables import dbconnector
        jsonfile_config = os.path.join(mock_db_path_vnet, "config_db")
        dbconnector.dedicated_dbs['CONFIG_DB'] = jsonfile_config
        runner = CliRunner()
        db = Db()
        expected_output = """\
vnet name    interfaces
-----------  -------------------------------
Vnet_103     Ethernet4,Loopback0,Po0002.101
Vnet_102     Eth36.10,PortChannel0002,Vlan40
Vnet_101     Ethernet0.10
"""

        result = runner.invoke(show.cli.commands['vnet'].commands['interfaces'], [], obj=db)
        dbconnector.dedicated_dbs = {}
        assert result.exit_code == 0
        assert result.output == expected_output

        vnet_obj = {'config_db': db.cfgdb, 'namespace': db.db.namespace}

        expected_output_unbind = "Interface Ethernet4 IP disabled and address(es) removed due to unbinding VRF.\n"
        cmds = config.config.commands["interface"].commands["vrf"].commands["unbind"]
        result = runner.invoke(cmds, ["Ethernet4"], obj=vnet_obj)

        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert 'Ethernet4' not in db.cfgdb.get_table('INTERFACE')
        assert result.output == expected_output_unbind

        expected_output_unbind = "Interface Loopback0 IP disabled and address(es) removed due to unbinding VRF.\n"
        cmds = config.config.commands["interface"].commands["vrf"].commands["unbind"]
        result = runner.invoke(cmds, ["Loopback0"], obj=vnet_obj)

        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert 'Loopback0' not in db.cfgdb.get_table('LOOPBACK_INTERFACE')
        assert result.output == expected_output_unbind

        expected_output_unbind = "Interface Vlan40 IP disabled and address(es) removed due to unbinding VRF.\n"
        cmds = config.config.commands["interface"].commands["vrf"].commands["unbind"]
        result = runner.invoke(cmds, ["Vlan40"], obj=vnet_obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert 'Vlan40' not in db.cfgdb.get_table('VLAN_INTERFACE')
        assert result.output == expected_output_unbind

        expected_output_unbind = "Interface PortChannel0002 IP disabled and address(es) removed due to unbinding VRF.\n"
        cmds = config.config.commands["interface"].commands["vrf"].commands["unbind"]
        result = runner.invoke(cmds, ["PortChannel0002"], obj=vnet_obj)

        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert 'PortChannel002' not in db.cfgdb.get_table('PORTCHANNEL_INTERFACE')
        assert result.output == expected_output_unbind

        vrf_obj = {'config_db': db.cfgdb, 'namespace': DEFAULT_NAMESPACE}
        state_db = SonicV2Connector(use_unix_socket_path=True, namespace='')
        state_db.connect(state_db.STATE_DB, False)
        _hash = "INTERFACE_TABLE|Eth36.10"
        state_db.set(db.db.STATE_DB, _hash, "state", "ok")
        vrf_obj['state_db'] = state_db

        expected_output_unbind = "Interface Eth36.10 IP disabled and address(es) removed due to unbinding VRF.\n"
        T1 = threading.Thread(target=self.update_statedb, args=(state_db, db.db.STATE_DB, _hash))
        T1.start()
        cmds = config.config.commands["interface"].commands["vrf"].commands["unbind"]
        result = runner.invoke(cmds, ["Eth36.10"], obj=vnet_obj)
        T1.join()
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('vnet_name', 'Vnet_102') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Eth36.10']
        assert result.output == expected_output_unbind

        vrf_obj = {'config_db': db.cfgdb, 'namespace': DEFAULT_NAMESPACE}

        expected_output_unbind = "Interface Ethernet0.10 IP disabled and address(es) removed due to unbinding VRF.\n"
        cmds = config.config.commands["interface"].commands["vrf"].commands["unbind"]
        result = runner.invoke(cmds, ["Ethernet0.10"], obj=vnet_obj)

        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('vnet_name', 'Vnet_101') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Ethernet0.10']
        assert result.output == expected_output_unbind

        expected_output_unbind = "Interface Po0002.101 IP disabled and address(es) removed due to unbinding VRF.\n"
        cmds = config.config.commands["interface"].commands["vrf"].commands["unbind"]
        result = runner.invoke(cmds, ["Po0002.101"], obj=vnet_obj)

        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('vnet_name', 'Vnet_103') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Po0002.101']
        assert result.output == expected_output_unbind

        expected_output_bind = "Interface Ethernet0 IP disabled and address(es) removed due to binding VRF Vnet_1.\n"
        cmds = config.config.commands["interface"].commands["vrf"].commands["bind"]
        result = runner.invoke(cmds, ["Ethernet0", "Vnet_1"], obj=vnet_obj)
        assert result.exit_code == 0
        assert result.output == expected_output_bind
        assert ('Vnet_1') in db.cfgdb.get_table('INTERFACE')['Ethernet0']['vnet_name']

        expected_output_bind = "Interface Loopback0 IP disabled and address(es) removed due to binding VRF Vnet_101.\n"
        cmds = config.config.commands["interface"].commands["vrf"].commands["bind"]
        result = runner.invoke(cmds, ["Loopback0", "Vnet_101"], obj=vnet_obj)
        assert result.exit_code == 0
        assert result.output == expected_output_bind
        assert ('Vnet_101') in db.cfgdb.get_table('LOOPBACK_INTERFACE')['Loopback0']['vnet_name']

        expected_output_bind = "Interface Vlan40 IP disabled and address(es) removed due to binding VRF Vnet_101.\n"
        cmds = config.config.commands["interface"].commands["vrf"].commands["bind"]
        result = runner.invoke(cmds, ["Vlan40", "Vnet_101"], obj=vnet_obj)
        assert result.exit_code == 0
        assert result.output == expected_output_bind
        assert ('Vnet_101') in db.cfgdb.get_table('VLAN_INTERFACE')['Vlan40']['vnet_name']

        expected_output = "Interface PortChannel0002 IP disabled and address(es) removed due to binding VRF Vnet_101.\n"
        cmds = config.config.commands["interface"].commands["vrf"].commands["bind"]
        result = runner.invoke(cmds, ["PortChannel0002", "Vnet_101"], obj=vnet_obj)
        assert result.exit_code == 0
        assert result.output == expected_output
        assert ('Vnet_101') in db.cfgdb.get_table('PORTCHANNEL_INTERFACE')['PortChannel0002']['vnet_name']

        expected_output_bind = "Interface Eth36.10 IP disabled and address(es) removed due to binding VRF Vnet_102.\n"
        cmds = config.config.commands["interface"].commands["vrf"].commands["bind"]
        result = runner.invoke(cmds, ["Eth36.10", "Vnet_102"], obj=vnet_obj)
        assert result.exit_code == 0
        assert result.output == expected_output_bind
        assert ('Vnet_102') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Eth36.10']['vnet_name']

        expected_output = "Interface Ethernet0.10 IP disabled and address(es) removed due to binding VRF Vnet_103.\n"
        cmds = config.config.commands["interface"].commands["vrf"].commands["bind"]
        result = runner.invoke(cmds, ["Ethernet0.10", "Vnet_103"], obj=vnet_obj)
        assert result.exit_code == 0
        assert result.output == expected_output
        assert ('Vnet_103') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Ethernet0.10']['vnet_name']

        expected_output_bind = "Interface Po0002.101 IP disabled and address(es) removed due to binding VRF Vnet_1.\n"
        cmds = config.config.commands["interface"].commands["vrf"].commands["bind"]
        result = runner.invoke(cmds, ["Po0002.101", "Vnet_1"], obj=vnet_obj)
        assert result.exit_code == 0
        assert result.output == expected_output_bind
        assert ('Vnet_1') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')['Po0002.101']['vnet_name']

        jsonfile_config = os.path.join(mock_db_path_vnet, "config_db")
        dbconnector.dedicated_dbs['CONFIG_DB'] = jsonfile_config

        expected_output = """\
vnet name    interfaces
-----------  -------------------------------
Vnet_103     Ethernet4,Loopback0,Po0002.101
Vnet_102     Eth36.10,PortChannel0002,Vlan40
Vnet_101     Ethernet0.10
"""
        result = runner.invoke(show.cli.commands["vnet"].commands["interfaces"], [], obj=db)
        dbconnector.dedicated_dbs = {}
        assert result.exit_code == 0
        assert result.output == expected_output

    def test_vrf_add_del(self):
        runner = CliRunner()
        db = Db()
        vrf_obj = {'config_db':db.cfgdb, 'namespace':db.db.namespace}

        result = runner.invoke(config.config.commands["vrf"].commands["add"], ["Vrf100"], obj=vrf_obj)
        assert ('Vrf100') in db.cfgdb.get_table('VRF')
        assert result.exit_code == 0

        result = runner.invoke(config.config.commands["vrf"].commands["add"], ["Vrf1"], obj=vrf_obj)
        assert "VRF Vrf1 already exists!" in result.output
        assert ('Vrf1') in db.cfgdb.get_table('VRF')
        assert result.exit_code != 0

        expected_output_del = "VRF Vrf1 deleted and all associated IP addresses removed.\n"
        result = runner.invoke(config.config.commands["vrf"].commands["del"], ["Vrf1"], obj=vrf_obj)
        assert result.exit_code == 0
        assert result.output == expected_output_del
        assert ('Vrf1') not in db.cfgdb.get_table('VRF')

        result = runner.invoke(config.config.commands["vrf"].commands["del"], ["Vrf200"], obj=vrf_obj)
        assert result.exit_code != 0
        assert ('Vrf200') not in db.cfgdb.get_table('VRF')
        assert "VRF Vrf200 does not exist!" in result.output

    def test_invalid_vrf_name(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}
        expected_output = """\
Error: 'vrf_name' must begin with 'Vrf' or named 'mgmt'/'management' in case of ManagementVRF.
"""
        result = runner.invoke(config.config.commands["vrf"].commands["add"], ["vrf-blue"], obj=obj)
        assert result.exit_code != 0
        assert ('vrf-blue') not in db.cfgdb.get_table('VRF')
        assert expected_output in result.output

        result = runner.invoke(config.config.commands["vrf"].commands["add"], ["VRF2"], obj=obj)
        assert result.exit_code != 0
        assert ('VRF2') not in db.cfgdb.get_table('VRF')
        assert expected_output in result.output

        result = runner.invoke(config.config.commands["vrf"].commands["add"], ["VrF10"], obj=obj)
        assert result.exit_code != 0
        assert ('VrF10') not in db.cfgdb.get_table('VRF')
        assert expected_output in result.output

        result = runner.invoke(config.config.commands["vrf"].commands["del"], ["vrf-blue"], obj=obj)
        assert result.exit_code != 0
        assert expected_output in result.output

        result = runner.invoke(config.config.commands["vrf"].commands["del"], ["VRF2"], obj=obj)
        assert result.exit_code != 0
        assert expected_output in result.output

        result = runner.invoke(config.config.commands["vrf"].commands["del"], ["VrF10"], obj=obj)
        assert result.exit_code != 0
        assert expected_output in result.output

        expected_output = """\
Error: 'vrf_name' length should not exceed 15 characters
"""
        result = runner.invoke(config.config.commands["vrf"].commands["add"], ["VrfNameTooLong!!!"], obj=obj)
        assert result.exit_code != 0
        assert ('VrfNameTooLong!!!') not in db.cfgdb.get_table('VRF')
        assert expected_output in result.output

    def test_vnet_add_del(self):
        runner = CliRunner()
        db = Db()
        vnet_obj = {'config_db': db.cfgdb, 'namespace': db.db.namespace}
        expected_output = """\
Error: 'vnet_name' must begin with 'Vnet_' .
"""
        # Test vnet add using length of vnet name
        vnet_name = "Vnet_ypfbjjhyzivaythuaxlbcibgdgjkqgapedmiosjgsv"
        args = [vnet_name, "222", "tunnel1"]
        result = runner.invoke(config.config.commands["vnet"].commands["add"], args, obj=vnet_obj)
        assert result.exit_code != 0
        assert "'vnet_name' length should not exceed 15 characters" in result.output
        assert vnet_name not in db.cfgdb.get_table('VNET')

        # Test vnet add using mandatory arguments
        args = ["Vnet_3", "2", "tunnel1"]
        result = runner.invoke(config.config.commands["vnet"].commands["add"], args, obj=vnet_obj)
        assert ('Vnet_3') in db.cfgdb.get_table('VNET')
        assert result.exit_code == 0

        # Test vnet add using invalid vnet name
        result = runner.invoke(config.config.commands["vnet"].commands["add"], ["Vnet-2", "6", "tunnel1"], obj=vnet_obj)
        assert result.exit_code != 0
        assert expected_output in result.output

        # Test vnet add when vnet already exists
        result = runner.invoke(config.config.commands["vnet"].commands["add"], ["Vnet_3", "2", "tunnel1"], obj=vnet_obj)
        assert "VNET Vnet_3 already exists!" in result.output
        assert result.exit_code != 0

        # Test vnet add with optional argument peer list
        args = ["Vnet_2000", "455", "tunnel1", "10.0.0.0/32"]
        result = runner.invoke(config.config.commands["vnet"].commands["add"], args, obj=vnet_obj)
        assert ('Vnet_2000') in db.cfgdb.get_table('VNET')
        assert result.exit_code == 0

        # Test vnet add with all optional argument all other optional arguments
        args2 = ["10.0.0.0/32", "559c6ce8-26ab-419-b46-b2", "default", 'true', "11:22:33:44:55:66", "66:55:44:33:22:11"]
        args = ["Vnet_3000", "455", "tunnel1"] + args2
        result = runner.invoke(config.config.commands["vnet"].commands["add"], args, obj=vnet_obj)
        assert ('Vnet_3000') in db.cfgdb.get_table('VNET')
        assert result.exit_code == 0

        # Test vnet del with wrong vnet name
        expected_output_del = "'vnet_name' must begin with 'Vnet_' "
        result = runner.invoke(config.config.commands["vnet"].commands["del"], ["vnet_3"], obj=vnet_obj)
        assert result.exit_code != 0
        assert expected_output_del in result.output

        # Test vnet del with long vnet name
        expected_output_del = "'vnet_name' length should not exceed 15 characters"
        vnet_name = ["Vnet_ypfbjjhyzivaythuaxlbcibgdgjkq"]
        result = runner.invoke(config.config.commands["vnet"].commands["del"], vnet_name, obj=vnet_obj)
        assert result.exit_code != 0
        assert (vnet_name[0]) not in db.cfgdb.get_table('VNET')
        assert expected_output_del in result.output

        # Test vnet del
        expected_output_del = "VNET Vnet_3 deleted and all associated IP addresses and routes removed.\n"
        result = runner.invoke(config.config.commands["vnet"].commands["del"], ["Vnet_3"], obj=vnet_obj)
        assert result.exit_code == 0
        assert ('Vnet_3') not in db.cfgdb.get_table('VNET')
        assert expected_output_del in result.output

        # Test vnet del for vnet that is non existent
        result = runner.invoke(config.config.commands["vnet"].commands["del"], ["Vnet_3"], obj=vnet_obj)
        assert result.exit_code != 0
        assert ('Vnet_3') not in db.cfgdb.get_table('VNET')
        assert "VNET Vnet_3 does not exist!" in result.output

    def test_vnet_add_del_route(self):
        runner = CliRunner()
        db = Db()
        vnet_obj = {'config_db': db.cfgdb, 'namespace': db.db.namespace}
        expected_output = """\
Error: 'vnet_name' must begin with 'Vnet_' .
"""
        # Add the vnet to a vnet table and verify if it exists while route addition
        args = ["Vnet_3", "2", "tunnel1"]
        result = runner.invoke(config.config.commands["vnet"].commands["add"], args, obj=vnet_obj)
        assert ('Vnet_3') in db.cfgdb.get_table('VNET')

        # Test vnet add route using mandatory arguments
        args = ["Vnet_3", "10.10.10.10/32", "10.10.10.1"]
        result = runner.invoke(config.config.commands["vnet"].commands["add-route"], args, obj=vnet_obj)
        assert any(key[0] == 'Vnet_3' for key in db.cfgdb.get_table('VNET_ROUTE_TUNNEL'))
        assert result.exit_code == 0

        # Test vnet add route using invalid vnet name
        args = ["Vnet-3", "10.10.10.10/32", "10.10.10.1"]
        result = runner.invoke(config.config.commands["vnet"].commands["add-route"], args, obj=vnet_obj)
        assert result.exit_code != 0
        assert expected_output in result.output

        # Test vnet add route when vnet doesnt exist
        args = ["Vnet_6", "10.10.10.10/32", "10.10.10.1"]
        result = runner.invoke(config.config.commands["vnet"].commands["add-route"], args, obj=vnet_obj)
        assert "VNET Vnet_6 doesnot exist, cannot add a route!" in result.output
        assert result.exit_code != 0

        # Test vnet add route when vnet route exists
        args = ["Vnet_3", "10.10.10.10/32", "10.10.10.1"]
        result = runner.invoke(config.config.commands["vnet"].commands["add-route"], args, obj=vnet_obj)
        assert "Route already exists for the VNET Vnet_3" in result.output
        assert result.exit_code != 0

        # Test vnet add route with optional args
        args = ["Vnet_4", "22", "tunnel1"]
        result = runner.invoke(config.config.commands["vnet"].commands["add"], args, obj=vnet_obj)
        assert ('Vnet_4') in db.cfgdb.get_table('VNET')

        args = ["Vnet_4", "10.10.10.10/32", "10.10.10.1", "123", "8.8.8.8", "11:22:33:44:55:66"]
        result = runner.invoke(config.config.commands["vnet"].commands["add-route"], args, obj=vnet_obj)
        assert any(key[0] == 'Vnet_4' for key in db.cfgdb.get_table('VNET_ROUTE_TUNNEL'))
        assert result.exit_code == 0

        # Test vnet add route using length of vnet name
        vnet_name = "Vnet_ypfbjjhyzivaythuaxlbcibgdgjkqgapedmiosjgsv"
        args = [vnet_name, "10.10.10.10/32", "10.10.10.1"]
        result = runner.invoke(config.config.commands["vnet"].commands["add-route"], args, obj=vnet_obj)
        assert result.exit_code != 0
        assert "'vnet_name' length should not exceed 15 characters" in result.output
        assert vnet_name not in db.cfgdb.get_table('VNET_ROUTE_TUNNEL')

        # Test vnet del with route deletion
        result = runner.invoke(config.config.commands["vnet"].commands["del"], ["Vnet_4"], obj=vnet_obj)
        assert any(key[0] != 'Vnet_4' for key in db.cfgdb.get_table('VNET_ROUTE_TUNNEL'))

        # Test vnet del route with wrong vnet name
        expected_output_del = "'vnet_name' must begin with 'Vnet_' "
        args = ["vnet_3", "10.10.10.10/32"]
        result = runner.invoke(config.config.commands["vnet"].commands["del-route"], args, obj=vnet_obj)
        assert result.exit_code != 0
        assert expected_output_del in result.output

        # Test vnet del route with long vnet name
        expected_output_del = "'vnet_name' length should not exceed 15 characters"
        vnet_name = "Vnet_ypfbjjhyzivaythuaxlbcibgdgjkq"
        args = [vnet_name, "10.10.10.10/32"]
        result = runner.invoke(config.config.commands["vnet"].commands["del-route"], args, obj=vnet_obj)
        assert result.exit_code != 0
        assert any(key[0] != vnet_name for key in db.cfgdb.get_table('VNET_ROUTE_TUNNEL'))
        assert expected_output_del in result.output

        # Test vnet del route
        args = ["Vnet_3", "10.10.10.10/32"]
        result = runner.invoke(config.config.commands["vnet"].commands["del-route"], args, obj=vnet_obj)
        assert result.exit_code == 0
        assert any(key[0] != 'Vnet_3' for key in db.cfgdb.get_table('VNET_ROUTE_TUNNEL'))

        # Test vnet del route for vnet that is non existent
        args = ["Vnet_100", "10.10.10.10/32"]
        result = runner.invoke(config.config.commands["vnet"].commands["del-route"], args, obj=vnet_obj)
        assert result.exit_code != 0
        assert ('Vnet_100') not in db.cfgdb.get_table('VNET')
        assert "VNET Vnet_100 doesnot exist, cannot delete the route!" in result.output

        # Test vnet del route with non existent route
        args = ["Vnet_3", "10.10.10.10/32"]
        result = runner.invoke(config.config.commands["vnet"].commands["del-route"], args, obj=vnet_obj)
        assert result.exit_code != 0
        assert any(key[0] != 'Vnet_3' for key in db.cfgdb.get_table('VNET_ROUTE_TUNNEL'))
        assert "Route does not exist for the VNET Vnet_3, cant delete it!" in result.output
 
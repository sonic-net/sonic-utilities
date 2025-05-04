import os
from click.testing import CliRunner
from swsscommon.swsscommon import SonicV2Connector
from utilities_common.db import Db

import config.main as config
import show.main as show
import threading

DEFAULT_NAMESPACE = ''
test_path = os.path.dirname(os.path.abspath(__file__))
mock_db_path_vnet = os.path.join(test_path, "vnet_input")


class TestVnet(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def update_statedb(self, db, db_name, key):
        import time
        time.sleep(0.5)
        db.delete(db_name, key)

    def test_vnet_bind_unbind(self):
        from .mock_tables import dbconnector
        jsonfile_config = os.path.join(mock_db_path_vnet, "config_db")
        dbconnector.dedicated_dbs['CONFIG_DB'] = jsonfile_config
        runner = CliRunner()
        db = Db()
        expected_output = """\
vnet name    interfaces
-----------  --------------------------------------------------------
Vnet_2000    Ethernet0.100,Ethernet4,Loopback0,PortChannel0002,Vlan40
Vnet_101     Ethernet0.10
Vnet_102     Eth36.10
Vnet_103     Po0002.101
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
-----------  --------------------------------------------------------
Vnet_2000    Ethernet0.100,Ethernet4,Loopback0,PortChannel0002,Vlan40
Vnet_101     Ethernet0.10
Vnet_102     Eth36.10
Vnet_103     Po0002.101
"""
        result = runner.invoke(show.cli.commands["vnet"].commands["interfaces"], [], obj=db)
        dbconnector.dedicated_dbs = {}
        assert result.exit_code == 0
        assert result.output == expected_output

    def test_vnet_add_del(self):
        runner = CliRunner()
        db = Db()
        vnet_obj = {'config_db': db.cfgdb, 'namespace': db.db.namespace}
        expected_output = """\
Error: 'vnet_name' must begin with 'Vnet'.
"""
        db.cfgdb.set_entry("VXLAN_TUNNEL", "tunnel1", {"src_ip": "10.1.0.1","dst_port": "4789"})
        db.cfgdb.set_entry("VXLAN_TUNNEL_MAP", ("tunnel1","map_100_Vlan100"), {"vni" : "2","vlan": "Vlan100"})

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
        result = runner.invoke(config.config.commands["vnet"].commands["add"], ["vnet-2", "6", "tunnel1"], obj=vnet_obj)
        assert result.exit_code != 0
        assert expected_output in result.output

        # Test vnet add when vnet already exists
        result = runner.invoke(config.config.commands["vnet"].commands["add"], ["Vnet_3", "2", "tunnel1"], obj=vnet_obj)
        assert "VNET Vnet_3 already exists!" in result.output
        assert result.exit_code != 0

        # Test vnet del with wrong vnet name
        expected_output_del = "'vnet_name' must begin with 'Vnet'"
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
Error: 'vnet_name' must begin with 'Vnet'.
"""
        db.cfgdb.set_entry("VXLAN_TUNNEL", "tunnel1", {"src_ip": "10.1.0.1","dst_port": "4789"})
        db.cfgdb.set_entry("VXLAN_TUNNEL_MAP", ("tunnel1","map_100_Vlan100"), {"vni" : "2","vlan": "Vlan100"})

        # Add the vnet to a vnet table and verify if it exists while route addition
        args = ["Vnet3", "2", "tunnel1"]
        result = runner.invoke(config.config.commands["vnet"].commands["add"], args, obj=vnet_obj)
        assert ('Vnet3') in db.cfgdb.get_table('VNET')

        # Test vnet add route using mandatory arguments
        args = ["Vnet3", "9.9.9.9/32", "10.10.10.1"]
        result = runner.invoke(config.config.commands["vnet"].commands["add-route"], args, obj=vnet_obj)
        assert any((key[0] == 'Vnet3' and key[1] == "9.9.9.9/32") for key in db.cfgdb.get_table('VNET_ROUTE_TUNNEL'))
        assert result.exit_code == 0

        # Test vnet add route using invalid vnet name
        args = ["vnet-3", "10.10.10.10/32", "10.10.10.1"]
        result = runner.invoke(config.config.commands["vnet"].commands["add-route"], args, obj=vnet_obj)
        assert result.exit_code != 0
        assert expected_output in result.output

        # Test vnet add route when vnet doesnt exist
        args = ["Vnet_6", "10.10.10.10/32", "10.10.10.1"]
        result = runner.invoke(config.config.commands["vnet"].commands["add-route"], args, obj=vnet_obj)
        assert "VNET Vnet_6 doesnot exist, cannot add a route!" in result.output
        assert result.exit_code != 0

        # Test vnet add route when vnet route exists
        args = ["Vnet3", "9.9.9.9/32", "9.9.9.1"]
        result = runner.invoke(config.config.commands["vnet"].commands["add-route"], args, obj=vnet_obj)
        assert "Route already exists for the VNET Vnet3" in result.output
        assert result.exit_code != 0
        
        # Test vnet add route using length of vnet name
        vnet_name = "Vnetypfbjjhyzivaythuaxlbcibgdgjkqgapedmiosjgsv"
        args = [vnet_name, "10.10.10.10/32", "10.10.10.1"]
        result = runner.invoke(config.config.commands["vnet"].commands["add-route"], args, obj=vnet_obj)
        assert result.exit_code != 0
        assert "'vnet_name' length should not exceed 15 characters" in result.output

        # Test vnet del route with wrong vnet name
        expected_output_del = "'vnet_name' must begin with 'Vnet'"
        args = ["vnet3", "10.10.10.10/32"]
        result = runner.invoke(config.config.commands["vnet"].commands["del-route"], args, obj=vnet_obj)
        assert result.exit_code != 0
        assert expected_output_del in result.output

        # Test vnet del route with long vnet name
        expected_output_del = "'vnet_name' length should not exceed 15 characters"
        vnet_name = "Vnetypfbjjhyzivaythuaxlbcibgdgjkq"
        args = [vnet_name, "10.10.10.10/32"]
        result = runner.invoke(config.config.commands["vnet"].commands["del-route"], args, obj=vnet_obj)
        assert result.exit_code != 0
        assert expected_output_del in result.output

        # Test vnet del route
        args = ["Vnet3", "9.9.9.9/32"]
        result = runner.invoke(config.config.commands["vnet"].commands["del-route"], args, obj=vnet_obj)
        assert result.exit_code == 0
        vnet_route_tunnel = db.cfgdb.get_table('VNET_ROUTE_TUNNEL')
        if vnet_route_tunnel:
            assert not any((key[0] == 'Vnet3' and key[1] == '9.9.9.9/32') for key in vnet_route_tunnel)

        # Test vnet del route of specific prefix should be deleted and other prefix should not be deleted
        args = ["Vnet4", "2", "tunnel1"]
        result = runner.invoke(config.config.commands["vnet"].commands["add"], args, obj=vnet_obj)
        assert ('Vnet4') in db.cfgdb.get_table('VNET')

        args1 = ["Vnet4", "11.11.11.11/32", "11.11.11.12"]
        args2 = ["Vnet4", "11.11.11.11/32"]
        result = runner.invoke(config.config.commands["vnet"].commands["add-route"], args1, obj=vnet_obj)
        result2 = runner.invoke(config.config.commands["vnet"].commands["del-route"], args2, obj=vnet_obj)
        assert result2.exit_code == 0
        vnet_route_tunnel = db.cfgdb.get_table('VNET_ROUTE_TUNNEL')
        if vnet_route_tunnel:
            assert any((key[0] == 'Vnet4' and key[1] == "8.8.8.8/32") for key in vnet_route_tunnel)
            assert not any((key[0] == 'Vnet4' and key[1] == "11.11.11.11/32") for key in vnet_route_tunnel)

        # Test vnet del route for all routes
        result = runner.invoke(config.config.commands["vnet"].commands["del-route"], "Vnet4", obj=vnet_obj)
        vnet_route_tunnel = db.cfgdb.get_table('VNET_ROUTE_TUNNEL')
        if vnet_route_tunnel:
            assert all((key[0] != 'Vnet4') for key in vnet_route_tunnel)

        # Test vnet del route for vnet that is non existent
        args = ["Vnet_100", "10.10.10.10/32"]
        result = runner.invoke(config.config.commands["vnet"].commands["del-route"], args, obj=vnet_obj)
        assert result.exit_code != 0
        assert ('Vnet_100') not in db.cfgdb.get_table('VNET')
        assert "VNET Vnet_100 doesnot exist, cannot delete the route!" in result.output

        # Test vnet del route with non existent route
        args = ["Vnet3", "10.10.10.10/32"]
        result = runner.invoke(config.config.commands["vnet"].commands["del-route"], args, obj=vnet_obj)
        assert result.exit_code != 0
        assert "Routes dont exist for the VNET Vnet3, cant delete it!" in result.output

    def test_vnet_add_del_2(self):
        runner = CliRunner()
        db = Db()
        vnet_obj = {'config_db': db.cfgdb, 'namespace': db.db.namespace}

        db.cfgdb.set_entry("VXLAN_TUNNEL", "tunnel1", {"src_ip": "10.1.0.1","dst_port": "4789"})
        db.cfgdb.set_entry("VXLAN_TUNNEL_MAP", ("tunnel1","map_100_Vlan100"), {"vni" : "12","vlan": "Vlan100"})
        
        # Test vnet add with optional arg-invalid vni
        args = ["Vnet11", "12a", "tunnel1"]
        result = runner.invoke(config.config.commands["vnet"].commands["add"], args, obj=vnet_obj)
        assert "Invalid VNI 12a. Valid range [1 to 16777215]." in result.output

        args = ["Vnet11", "12", "tunnel2"]
        result = runner.invoke(config.config.commands["vnet"].commands["add"], args, obj=vnet_obj)
        assert "Vxlan tunnel tunnel2 does not exist" in result.output

        # Test vnet add with optional arg-invalid tunnel vni mapping
        args = ["Vnet11", "13", "tunnel1"]
        result = runner.invoke(config.config.commands["vnet"].commands["add"], args, obj=vnet_obj)
        assert "VNI 13 is not mapped to Vxlan tunnel tunnel1" in result.output

        # Test vnet add with optional arg-invalid peer list
        args = ["Vnet11", "12", "tunnel1", "Vnet1"]
        result = runner.invoke(config.config.commands["vnet"].commands["add"], args, obj=vnet_obj)
        assert "VNET Vnet1 does not exist!" in result.output

        # Test vnet add with optional arg-invalid guid
        args = ["Vnet4", "12", "tunnel1"]
        result = runner.invoke(config.config.commands["vnet"].commands["add"], args, obj=vnet_obj)
        invalid_guid = "123456789012345"*25
        args = ["Vnet11", "12", "tunnel1", "Vnet4", invalid_guid]
        result = runner.invoke(config.config.commands["vnet"].commands["add"], args, obj=vnet_obj)
        assert "'guid' length should not exceed 255 characters" in result.output

        # Test vnet add with optional arg-invalid scope
        args = ["Vnet11", "12", "tunnel1", "Vnet4", "aaa233_2323", "non_default"]
        result = runner.invoke(config.config.commands["vnet"].commands["add"], args, obj=vnet_obj)
        assert "Only 'default' value is allowed for scope!" in result.output

        # Test vnet add with optional arg-invalid adv_prefix
        args = ["Vnet12", "12", "tunnel1", "Vnet4", "aaa233_2323", "default", "10"]
        result = runner.invoke(config.config.commands["vnet"].commands["add"], args, obj=vnet_obj)
        assert result.exit_code != 0
        
        # Test vnet add with optional arg-invalid overlay_dmac
        args = ["Vnet11", "12", "tunnel1", "Vnet4", "aaa233_2323", "default", "true", "11:22:33:44:556"]
        result = runner.invoke(config.config.commands["vnet"].commands["add"], args, obj=vnet_obj)
        assert "Invalid MAC for overlay dmac 11:22:33:44:556 ." in result.output

        # Test vnet add with optional arg-invalid src_mac
        args = ["Vnet11", "12", "tunnel1", "Vnet4", "aaa233_2323", "default", "TRUE", "11:22:33:44:55:66", "66:55:44:33:11"]
        result = runner.invoke(config.config.commands["vnet"].commands["add"], args, obj=vnet_obj)
        assert "Invalid MAC for src mac 66:55:44:33:11 ." in result.output

        # Test vnet add successfully with all optional arguments 
        args2 = ["Vnet4", "559c6ce8-26ab-419-b46-b2", "default", "TRUE", "11:22:33:44:55:66", "66:55:44:33:22:11"]
        args = ["Vnet_11", "12", "tunnel1"] + args2
        result = runner.invoke(config.config.commands["vnet"].commands["add"], args, obj=vnet_obj)
        assert ('Vnet_11') in db.cfgdb.get_table('VNET')
        assert result.exit_code == 0

    def test_vnet_add_del_route_2(self):
        runner = CliRunner()
        db = Db()
        vnet_obj = {'config_db': db.cfgdb, 'namespace': db.db.namespace}

        db.cfgdb.set_entry("VXLAN_TUNNEL", "tunnel1", {"src_ip": "10.1.0.1","dst_port": "4789"})
        db.cfgdb.set_entry("VXLAN_TUNNEL_MAP", ("tunnel1","map_100_Vlan100"), {"vni" : "12","vlan": "Vlan100"})

        # Add the vnet
        args = ["Vnet4", "12", "tunnel1"]
        result = runner.invoke(config.config.commands["vnet"].commands["add"], args, obj=vnet_obj)
        assert ('Vnet4') in db.cfgdb.get_table('VNET')

        # Test vnet add route with arg-invalid prefix
        args = ["Vnet4", "8.8.8.8.8/32", "10.10.10.1"]
        result = runner.invoke(config.config.commands["vnet"].commands["add-route"], args, obj=vnet_obj)
        assert "Invalid prefix 8.8.8.8.8/32" in result.output

        # Test vnet add route with optional arg-invalid endpoint
        args = ["Vnet4", "8.8.8.8/32", "10.10.1.1,10.10.10.1000"]
        result = runner.invoke(config.config.commands["vnet"].commands["add-route"], args, obj=vnet_obj)
        assert "Endpoint has invalid IP address 10.10.10.1000" in result.output

        # Test vnet add route with optional arg-invalid vni
        args = ["Vnet4", "8.8.8.8/32", "10.10.10.1", "123a"]
        result = runner.invoke(config.config.commands["vnet"].commands["add-route"], args, obj=vnet_obj)
        assert "Invalid VNI 123a. Valid range [1 to 16777215]." in result.output

        # Test vnet add route with optional arg-invalid mac_address
        args = ["Vnet4", "8.8.8.8/32", "10.10.10.1", "123", "11:22:33:AA:55-66"]
        result = runner.invoke(config.config.commands["vnet"].commands["add-route"], args, obj=vnet_obj)
        assert "Invalid MAC 11:22:33:AA:55-66" in result.output

        # Test vnet add route with optional arg-invalid endpoint_monitor
        args = ["Vnet4", "8.8.8.8/32", "10.10.10.1", "123", "11:22:33:AA:55:66", "8.8.8.8,10.10.10.1000"]
        result = runner.invoke(config.config.commands["vnet"].commands["add-route"], args, obj=vnet_obj)
        assert "Endpoint monitor has invalid IP address 10.10.10.1000" in result.output

        # Test vnet add route with optional arg-invalid primary
        args = ["Vnet4", "8.8.8.8/32", "10.10.10.1", "123", "11:22:33:AA:55:66", "8.8.8.8", "test", "192.168.1.999", "custom"]
        result = runner.invoke(config.config.commands["vnet"].commands["add-route"], args, obj=vnet_obj)
        assert "Primary has invalid IP address 192.168.1.999" in result.output

        # Test vnet add route with optional arg-invalid adv_prefix
        args = ["Vnet4", "8.8.8.8/32", "10.10.10.1", "123", "11:22:33:AA:55:66", "8.8.8.8", "test", "192.168.1.9", "custom", "8.8.8.8/33"]
        result = runner.invoke(config.config.commands["vnet"].commands["add-route"], args, obj=vnet_obj)
        assert "Invalid adv_prefix" in result.output

        # Test vnet add route with successful optional args
        args = ["Vnet4", "8.8.8.8/32", "10.10.10.1", "123", "11:22:33:AA:55:66", "8.8.8.8", "test", "192.168.1.9", "custom", "8.8.8.8/24"]
        result = runner.invoke(config.config.commands["vnet"].commands["add-route"], args, obj=vnet_obj)
        assert any((key[0] == 'Vnet4' and key[1] == '8.8.8.8/32') for key in db.cfgdb.get_table('VNET_ROUTE_TUNNEL'))
        assert result.exit_code == 0

        # Test vnet del route with optional arg-invalid prefix
        args = ["Vnet4", "8.8.8.8/35"]
        result = runner.invoke(config.config.commands["vnet"].commands["del-route"], args, obj=vnet_obj)
        assert "Invalid prefix" in result.output
        assert result.exit_code != 0

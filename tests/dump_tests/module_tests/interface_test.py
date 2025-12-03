import json
import os
import sys
import jsonpatch
import unittest
import pytest
from deepdiff import DeepDiff
from mock import patch
from dump.helper import create_template_dict, sort_lists, populate_mock
from dump.plugins.interface import Interface
from dump.match_infra import MatchEngine, ConnectionPool
from swsscommon.swsscommon import SonicV2Connector
from utilities_common.constants import DEFAULT_NAMESPACE

# Location for dedicated db's used for UT
module_tests_path = os.path.dirname(__file__)
dump_tests_path = os.path.join(module_tests_path, "../")
tests_path = os.path.join(dump_tests_path, "../")
dump_test_input = os.path.join(tests_path, "dump_input")
port_files_path = os.path.join(dump_test_input, "interface")

# Define the mock files to read from
dedicated_dbs = {}
dedicated_dbs['CONFIG_DB'] = os.path.join(port_files_path, "config_db.json")
dedicated_dbs['APPL_DB'] = os.path.join(port_files_path, "appl_db.json")
dedicated_dbs['ASIC_DB'] = os.path.join(port_files_path, "asic_db.json")
dedicated_dbs['STATE_DB'] = os.path.join(port_files_path, "state_db.json")


@pytest.fixture(scope="class", autouse=True)
def match_engine():

    print("SETUP")
    os.environ["VERBOSE"] = "1"

    # Monkey Patch the SonicV2Connector Object
    from ...mock_tables import dbconnector
    db = SonicV2Connector()

    # popualate the db with mock data
    db_names = list(dedicated_dbs.keys())
    try:
        populate_mock(db, db_names, dedicated_dbs)
    except Exception as e:
        assert False, "Mock initialization failed: " + str(e)

    # Initialize connection pool
    conn_pool = ConnectionPool()
    conn_pool.fill(DEFAULT_NAMESPACE, db, db_names)

    # Initialize match_engine
    match_engine = MatchEngine(conn_pool)
    yield match_engine
    print("TEARDOWN")
    os.environ["VERBOSE"] = "0"

@pytest.mark.usefixtures("match_engine")
class TestInterfaceModule:
    def test_port_type_interface(self, match_engine):
        """
        Scenario: Test the flow fetching objs related to PORT_TYPE interfac
        """
        params = {Interface.ARG_NAME: "Ethernet16", "namespace": ""}
        m_intf = Interface(match_engine)
        returned = m_intf.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].extend(["INTERFACE|Ethernet16", "INTERFACE|Ethernet16|3.3.3.1/24"])
        expect["APPL_DB"]["keys"].extend(["INTF_TABLE:Ethernet16", "INTF_TABLE:Ethernet16:3.3.3.1/24"])
        expect["STATE_DB"]["keys"].extend(["INTERFACE_TABLE|Ethernet16", "INTERFACE_TABLE|Ethernet16|3.3.3.1/24"])
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_ROUTER_INTERFACE:oid:0x6000000000c7c")
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect), ignore_order=True)
        assert not ddiff, ddiff
    
    def test_vlan_type_interface(self, match_engine):
        """
        Scenario: Test the flow fetching objs related to VLAN_TYPE interfac
        """
        params = {Interface.ARG_NAME: "Vlan10", "namespace": ""}
        m_intf = Interface(match_engine)
        returned = m_intf.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].extend(["VLAN_INTERFACE|Vlan10", "VLAN_INTERFACE|Vlan10|2.2.2.1/24"])
        expect["APPL_DB"]["keys"].extend(["INTF_TABLE:Vlan10", "INTF_TABLE:Vlan10:2.2.2.1/24"])
        expect["STATE_DB"]["keys"].extend(["INTERFACE_TABLE|Vlan10", "INTERFACE_TABLE|Vlan10|2.2.2.1/24"])
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_ROUTER_INTERFACE:oid:0x6000000000c7b")
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect), ignore_order=True)
        assert not ddiff, ddiff
    
    def test_lag_type_interface_no_members(self, match_engine):
        """
        Scenario: Test the flow fetching objs related to LAG_TYPE iface without members
        """
        params = {Interface.ARG_NAME: "PortChannel1111", "namespace": ""}
        m_intf = Interface(match_engine)
        returned = m_intf.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].extend(["PORTCHANNEL_INTERFACE|PortChannel1111", "PORTCHANNEL_INTERFACE|PortChannel1111|1.1.1.1/24"])
        expect["APPL_DB"]["keys"].extend(["INTF_TABLE:PortChannel1111", "INTF_TABLE:PortChannel1111:1.1.1.1/24"])
        expect["STATE_DB"]["keys"].extend(["INTERFACE_TABLE|PortChannel1111", "INTERFACE_TABLE|PortChannel1111|1.1.1.1/24"])
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_ROUTER_INTERFACE")
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect), ignore_order=True)
        assert not ddiff, ddiff
    
    def test_lag_type_interface(self, match_engine):
        """
        Scenario: Test the flow fetching objs related to LAG_TYPE iface
        """
        params = {Interface.ARG_NAME: "PortChannel1234", "namespace": ""}
        m_intf = Interface(match_engine)
        returned = m_intf.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].extend(["PORTCHANNEL_INTERFACE|PortChannel1234", "PORTCHANNEL_INTERFACE|PortChannel1234|7.7.7.1/24"])
        expect["APPL_DB"]["keys"].extend(["INTF_TABLE:PortChannel1234", "INTF_TABLE:PortChannel1234:7.7.7.1/24"])
        expect["STATE_DB"]["keys"].extend(["INTERFACE_TABLE|PortChannel1234", "INTERFACE_TABLE|PortChannel1234|7.7.7.1/24"])
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_ROUTER_INTERFACE:oid:0x60000000005ec")
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect), ignore_order=True)
        assert not ddiff, ddiff
    
    def test_subintf_type_interface(self, match_engine):
        """
        Scenario: Test the flow fetching objs related to Sub-Interface iface
        """
        params = {Interface.ARG_NAME: "Eth0.1", "namespace": ""}
        m_intf = Interface(match_engine)
        returned = m_intf.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].extend(["VLAN_SUB_INTERFACE|Eth0.1", "VLAN_SUB_INTERFACE|Eth0.1|9.9.9.9/24"])
        expect["APPL_DB"]["keys"].extend(["INTF_TABLE:Eth0.1", "INTF_TABLE:Eth0.1:9.9.9.9/24"])
        expect["STATE_DB"]["keys"].extend(["INTERFACE_TABLE|Eth0.1", "INTERFACE_TABLE|Eth0.1|9.9.9.9/24"])
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_ROUTER_INTERFACE:oid:0x60000000005e9")
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect), ignore_order=True)
        assert not ddiff, ddiff
    
    def test_no_interface(self, match_engine):
        """
        Scenario: Test the flow fetching objs related to an interface which is not present
        """
        params = {Interface.ARG_NAME: "Ethernet160", "namespace": ""}
        m_intf = Interface(match_engine)
        returned = m_intf.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["tables_not_found"].extend(["INTERFACE"])
        expect["APPL_DB"]["tables_not_found"].extend(["INTF_TABLE"])
        expect["STATE_DB"]["tables_not_found"].extend(["INTERFACE_TABLE"])
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_ROUTER_INTERFACE")
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect), ignore_order=True)
        assert not ddiff, ddiff
    
    def test_invalid_interface(self, match_engine):
        """
        Scenario: Test the flow fetching objs related to an interface which is invalid
        """
        params = {Interface.ARG_NAME: "Whatever", "namespace": ""}
        m_intf = Interface(match_engine)
        returned = m_intf.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["tables_not_found"].extend(["INTERFACE",
                                                        "PORTCHANNEL_INTERFACE",
                                                        "VLAN_INTERFACE",
                                                        "VLAN_SUB_INTERFACE",
                                                        "LOOPBACK_INTERFACE"])
        expect["APPL_DB"]["tables_not_found"].extend(["INTF_TABLE"])
        expect["STATE_DB"]["tables_not_found"].extend(["INTERFACE_TABLE"])
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_ROUTER_INTERFACE")
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect), ignore_order=True)
        assert not ddiff, ddiff
    
    def test_loopback_interface(self, match_engine):
        """
        Scenario: Test the flow fetching objs related to loopback iface
        """
        params = {Interface.ARG_NAME: "Loopback0", "namespace": ""}
        m_intf = Interface(match_engine)
        returned = m_intf.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].extend(["LOOPBACK_INTERFACE|Loopback0", "LOOPBACK_INTERFACE|Loopback0|10.1.0.1/32"])
        expect["APPL_DB"]["keys"].extend(["INTF_TABLE:Loopback0", "INTF_TABLE:Loopback0:10.1.0.1/32"])
        expect["STATE_DB"]["keys"].extend(["INTERFACE_TABLE|Loopback0", "INTERFACE_TABLE|Loopback0|10.1.0.1/32"])
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect), ignore_order=True)
        assert not ddiff, ddiff

    def test_subintf_with_invalid_vlan(self, match_engine):
        """
        Scenario: Test the flow fetching objs related to a subintf with invalid vlan
        """
        params = {Interface.ARG_NAME: "Eth4.1", "namespace": ""}
        m_intf = Interface(match_engine)
        returned = m_intf.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].extend(["VLAN_SUB_INTERFACE|Eth4.1"])
        expect["APPL_DB"]["keys"].extend(["INTF_TABLE:Eth4.1"])
        expect["STATE_DB"]["tables_not_found"].extend(["INTERFACE_TABLE"])
        expect["ASIC_DB"]["tables_not_found"].extend(["ASIC_STATE:SAI_OBJECT_TYPE_ROUTER_INTERFACE"])
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect), ignore_order=True)
        assert not ddiff, ddiff

    def test_all_args(self, match_engine):
        """
        Scenario: Verify Whether the get_all_args method is working as expected
        """
        params = {}
        m_port = Interface(match_engine)
        returned = m_port.get_all_args("")
        expect = ["Ethernet16", "Vlan10", "PortChannel1111", "PortChannel1234", "Eth0.1", "Loopback0", "Eth4.1"]
        ddiff = DeepDiff(expect, returned, ignore_order=True)
        assert not ddiff, ddiff

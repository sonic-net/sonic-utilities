import json
import os
import sys
import jsonpatch
import unittest
import pytest
from deepdiff import DeepDiff
from mock import patch
from dump.helper import create_template_dict, sort_lists, populate_mock
from dump.plugins.copp import Copp
from dump.match_infra import MatchEngine, ConnectionPool
from swsscommon.swsscommon import SonicV2Connector
from utilities_common.constants import DEFAULT_NAMESPACE

# Location for dedicated db's used for UT
module_tests_path = os.path.dirname(__file__)
dump_tests_path = os.path.join(module_tests_path, "../")
tests_path = os.path.join(dump_tests_path, "../")
dump_test_input = os.path.join(tests_path, "dump_input")
copp_files_path = os.path.join(dump_test_input, "copp")

# Define the mock files to read from
dedicated_dbs = {}
dedicated_dbs['CONFIG_DB'] = os.path.join(copp_files_path, "config_db.json")
dedicated_dbs['APPL_DB'] = os.path.join(copp_files_path, "appl_db.json")
dedicated_dbs['ASIC_DB'] = os.path.join(copp_files_path, "asic_db.json")
dedicated_dbs['STATE_DB'] = os.path.join(copp_files_path, "state_db.json")


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
@patch("dump.plugins.copp.Copp.CONFIG_FILE", os.path.join(dump_test_input, "copp_cfg.json"))
class TestCoppModule:

    def test_usr_cfg_trap_and_copp_cfg_file_grp(self, match_engine):
        '''
        Scenario: A custom COPP_TRAP table entry is defined by the user and the relevant Trap Group is configured through the copp_cfg file
        '''
        params = {Copp.ARG_NAME: "snmp", "namespace": ""}
        m_copp = Copp(match_engine)
        returned = m_copp.execute(params)
        print(returned)
        expect = create_template_dict(dbs=["CONFIG_FILE", "CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_FILE"]["keys"].append("COPP_GROUP|queue4_group2")
        expect["CONFIG_DB"]["keys"].append("COPP_TRAP|snmp_grp")
        expect["APPL_DB"]["keys"].append("COPP_TABLE:queue4_group2")
        expect["STATE_DB"]["keys"].extend(["COPP_GROUP_TABLE|queue4_group2", "COPP_TRAP_TABLE|snmp_grp"])
        expect["ASIC_DB"]["keys"].extend(["ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF_TRAP:oid:0x220000000004dc", "ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF_TRAP_GROUP:oid:0x110000000004da",
                                          "ASIC_STATE:SAI_OBJECT_TYPE_POLICER:oid:0x120000000004db", "ASIC_STATE:SAI_OBJECT_TYPE_QUEUE:oid:0x150000000002a0"])
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_copp_cfg_file_trap_and_copp_cfg_file_grp(self, match_engine):
        '''
        Scenario: Both the Trap ID and Trap Group are configured through copp_cfg file
        '''
        params = {Copp.ARG_NAME: "arp_resp", "namespace": ""}
        m_copp = Copp(match_engine)
        returned = m_copp.execute(params)
        print(returned)
        expect = create_template_dict(dbs=["CONFIG_FILE", "CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_FILE"]["keys"].extend(["COPP_GROUP|queue4_group2", "COPP_TRAP|arp"])
        expect["APPL_DB"]["keys"].append("COPP_TABLE:queue4_group2")
        expect["STATE_DB"]["keys"].extend(["COPP_GROUP_TABLE|queue4_group2", "COPP_TRAP_TABLE|arp"])
        expect["ASIC_DB"]["keys"].extend(["ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF_TRAP:oid:0x220000000004dd", "ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF_TRAP_GROUP:oid:0x110000000004da",
                                          "ASIC_STATE:SAI_OBJECT_TYPE_POLICER:oid:0x120000000004db", "ASIC_STATE:SAI_OBJECT_TYPE_QUEUE:oid:0x150000000002a0"])
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_copp_cfg_file_trap_and_copp_cfg_file_grp_with_diff(self, match_engine):
        '''
        Scenario: Both the Trap ID and Trap Group are configured through copp_cfg file.
                  In addition, User also provided a diff for the COPP_GROUP entry
        '''
        params = {Copp.ARG_NAME: "sample_packet", "namespace": ""}
        m_copp = Copp(match_engine)
        returned = m_copp.execute(params)
        print(json.dumps(returned, indent=2))
        expect = create_template_dict(dbs=["CONFIG_FILE", "CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_FILE"]["keys"].extend(["COPP_GROUP|queue2_group1", "COPP_TRAP|sflow"])
        expect["CONFIG_DB"]["keys"].append("COPP_GROUP|queue2_group1")
        expect["APPL_DB"]["keys"].append("COPP_TABLE:queue2_group1")
        expect["STATE_DB"]["keys"].extend(["COPP_GROUP_TABLE|queue2_group1", "COPP_TRAP_TABLE|sflow"])
        expect["ASIC_DB"]["keys"].extend(["ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF_TRAP:oid:0x220000000004de", "ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF_TRAP_GROUP:oid:0x110000000004db",
                                          "ASIC_STATE:SAI_OBJECT_TYPE_POLICER:oid:0x120000000004dc", "ASIC_STATE:SAI_OBJECT_TYPE_QUEUE:oid:0x150000000002a1",
                                          "ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF:oid:0xd0000000004d6", "ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF_TABLE_ENTRY:oid:0x230000000004d8"])
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_usr_cfg_trap_with_missing_group(self, match_engine):
        '''
        Scenario: A custom COPP_TRAP table entry is defined by the user, but the relevant COPP_GROUP entry is missing
        '''
        params = {Copp.ARG_NAME: "vrrpv6", "namespace": ""}
        m_copp = Copp(match_engine)
        returned = m_copp.execute(params)
        print(returned)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB", "CONFIG_FILE"])
        expect["CONFIG_DB"]["keys"].append("COPP_TRAP|vrrpv6")
        expect["CONFIG_DB"]["tables_not_found"].append("COPP_GROUP")
        expect["APPL_DB"]["tables_not_found"].append("COPP_TABLE")
        expect["STATE_DB"]["tables_not_found"].extend(["COPP_GROUP_TABLE", "COPP_TRAP_TABLE"])
        expect["ASIC_DB"]["tables_not_found"].extend(["ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF_TRAP", "ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF_TRAP_GROUP"])
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_copp_cfg_file_group_and_copp_cfg_file_trap_with_diff(self, match_engine):
        '''
        Scenario: User has added a trap_id to a COPP_TRAP entry. The COPP_TRAP entry is already present in copp_cfg file (i.e diff)
                  and the relevant trap group is in copp_cfg file
        '''
        params = {Copp.ARG_NAME: "ospfv6", "namespace": ""}
        m_copp = Copp(match_engine)
        returned = m_copp.execute(params)
        print(returned)
        expect = create_template_dict(dbs=["CONFIG_FILE", "CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_FILE"]["keys"].extend(["COPP_GROUP|queue4_group1", "COPP_TRAP|bgp"])
        expect["CONFIG_DB"]["keys"].append("COPP_TRAP|bgp")
        expect["APPL_DB"]["keys"].append("COPP_TABLE:queue4_group1")
        expect["STATE_DB"]["keys"].extend(["COPP_GROUP_TABLE|queue4_group1", "COPP_TRAP_TABLE|bgp"])
        expect["ASIC_DB"]["keys"].extend(["ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF_TRAP:oid:0x220000000004df", "ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF_TRAP_GROUP:oid:0x110000000004db",
                                          "ASIC_STATE:SAI_OBJECT_TYPE_POLICER:oid:0x120000000004dc", "ASIC_STATE:SAI_OBJECT_TYPE_QUEUE:oid:0x150000000002a1"])
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_invalid_trap_id(self, match_engine):
        params = {Copp.ARG_NAME: "random", "namespace": ""}
        m_copp = Copp(match_engine)
        returned = m_copp.execute(params)
        print(returned)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB", "CONFIG_FILE"])
        expect["CONFIG_FILE"]["tables_not_found"].extend(["COPP_GROUP", "COPP_TRAP"])
        expect["CONFIG_DB"]["tables_not_found"].extend(["COPP_GROUP", "COPP_TRAP"])
        expect["APPL_DB"]["tables_not_found"].append("COPP_TABLE")
        expect["STATE_DB"]["tables_not_found"].extend(["COPP_GROUP_TABLE", "COPP_TRAP_TABLE"])
        expect["ASIC_DB"]["tables_not_found"].extend(["ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF_TRAP", "ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF_TRAP_GROUP"])
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_missing_asic_dump(self, match_engine):
        params = {Copp.ARG_NAME: "ospf", "namespace": ""}
        m_copp = Copp(match_engine)
        returned = m_copp.execute(params)
        print(returned)
        expect = create_template_dict(dbs=["CONFIG_FILE", "CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_FILE"]["keys"].extend(["COPP_GROUP|queue4_group1", "COPP_TRAP|bgp"])
        expect["CONFIG_DB"]["keys"].append("COPP_TRAP|bgp")
        expect["APPL_DB"]["keys"].append("COPP_TABLE:queue4_group1")
        expect["STATE_DB"]["keys"].extend(["COPP_GROUP_TABLE|queue4_group1", "COPP_TRAP_TABLE|bgp"])
        expect["ASIC_DB"]["tables_not_found"].extend(["ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF_TRAP", "ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF_TRAP_GROUP"])
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_missing_appl(self, match_engine):
        params = {Copp.ARG_NAME: "lldp", "namespace": ""}
        m_copp = Copp(match_engine)
        returned = m_copp.execute(params)
        print(returned)
        expect = create_template_dict(dbs=["CONFIG_FILE", "CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_FILE"]["keys"].extend(["COPP_GROUP|queue4_group3", "COPP_TRAP|lldp"])
        expect["APPL_DB"]["tables_not_found"].append("COPP_TABLE")
        expect["STATE_DB"]["tables_not_found"].extend(["COPP_GROUP_TABLE", "COPP_TRAP_TABLE"])
        expect["ASIC_DB"]["tables_not_found"].extend(["ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF_TRAP", "ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF_TRAP_GROUP"])
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_missing_state(self, match_engine):
        params = {Copp.ARG_NAME: "src_nat_miss", "namespace": ""}
        m_copp = Copp(match_engine)
        returned = m_copp.execute(params)
        print(returned)
        expect = create_template_dict(dbs=["CONFIG_FILE", "APPL_DB", "ASIC_DB", "STATE_DB", "CONFIG_DB"])
        expect["CONFIG_FILE"]["keys"].extend(["COPP_GROUP|queue1_group2", "COPP_TRAP|nat"])
        expect["APPL_DB"]["keys"].append("COPP_TABLE:queue1_group2")
        expect["STATE_DB"]["tables_not_found"].extend(["COPP_GROUP_TABLE", "COPP_TRAP_TABLE"])
        expect["ASIC_DB"]["keys"].extend(["ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF_TRAP:oid:0x220000000004e0", "ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF_TRAP_GROUP:oid:0x110000000004e0",
                                          "ASIC_STATE:SAI_OBJECT_TYPE_QUEUE:oid:0x150000000002a1"])
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_all_args(self, match_engine):
        params = {}
        m_copp = Copp(match_engine)
        returned = m_copp.get_all_args("")
        expect = ["bgp", "bgpv6", "lacp", "arp_req", "arp_resp", "neigh_discovery", "lldp", "dhcp", "dhcp_l2", "dhcpv6", "dhcpv6_l2", "udld", "ip2me", "src_nat_miss", "dest_nat_miss", "sample_packet", "snmp", "bfd", "vrrpv6", "ospf", "ospfv6"]
        ddiff = DeepDiff(expect, returned, ignore_order=True)
        assert not ddiff, ddiff

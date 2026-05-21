import json, os, sys
import jsonpatch
import unittest
import pytest
from deepdiff import DeepDiff
from mock import patch
from dump.helper import create_template_dict, sort_lists, populate_mock
from dump.plugins.vlan import Vlan
from dump.plugins.vlan_member import Vlan_Member
from dump.match_infra import MatchEngine, ConnectionPool
from swsscommon.swsscommon import SonicV2Connector
from utilities_common.constants import DEFAULT_NAMESPACE

module_tests_path = os.path.dirname(__file__)
dump_tests_path = os.path.join(module_tests_path, "../")
tests_path = os.path.join(dump_tests_path, "../")
dump_test_input = os.path.join(tests_path, "dump_input")


# Location for dedicated db's used for UT
vlan_files_path = os.path.join(dump_test_input, "vlan")

dedicated_dbs = {}
dedicated_dbs['CONFIG_DB'] = os.path.join(vlan_files_path, "config_db.json") 
dedicated_dbs['APPL_DB'] = os.path.join(vlan_files_path, "appl_db.json") 
dedicated_dbs['ASIC_DB'] = os.path.join(vlan_files_path, "asic_db.json")
dedicated_dbs['STATE_DB'] = os.path.join(vlan_files_path, "state_db.json")


def verbosity_setup():
    print("SETUP")
    os.environ["VERBOSE"] = "1"
    yield
    print("TEARDOWN")
    os.environ["VERBOSE"] = "0"


@pytest.fixture(scope="class", autouse=True)
def match_engine():

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

@pytest.mark.usefixtures("match_engine")
class TestVlanModule:
    
    def test_working_state_vlan(self, match_engine):
        params = {}
        params["namespace"] = ""
        params[Vlan.ARG_NAME] = "Vlan4"
        m_vlan = Vlan(match_engine)
        returned = m_vlan.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].append("VLAN|Vlan4")
        expect["APPL_DB"]["keys"].append("VLAN_TABLE:Vlan4")
        expect["STATE_DB"]["keys"].append("VLAN_TABLE|Vlan4")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_VLAN:oid:0x26000000000619")
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect), ignore_order=True)
        assert not ddiff, ddiff
        
    def test_working_state_vlan_member1(self, match_engine):
        params = {}
        params["namespace"] = ""
        params[Vlan_Member.ARG_NAME] = "Vlan4|Ethernet16"
        m_vlan = Vlan_Member(match_engine)
        returned = m_vlan.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].append("VLAN_MEMBER|Vlan4|Ethernet16")
        expect["APPL_DB"]["keys"].append("VLAN_MEMBER_TABLE:Vlan4:Ethernet16")
        expect["STATE_DB"]["keys"].append("VLAN_MEMBER_TABLE|Vlan4|Ethernet16")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_VLAN_MEMBER:oid:0x27000000000622")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT:oid:0x3a000000000621")
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect), ignore_order=True)
        assert not ddiff, ddiff

    def test_working_state_vlan_member2(self, match_engine):
        params = {}
        params["namespace"] = ""
        params[Vlan_Member.ARG_NAME] = "Vlan4|Ethernet24"
        m_vlan = Vlan_Member(match_engine)
        returned = m_vlan.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].append("VLAN_MEMBER|Vlan4|Ethernet24")
        expect["APPL_DB"]["keys"].append("VLAN_MEMBER_TABLE:Vlan4:Ethernet24")
        expect["STATE_DB"]["keys"].append("VLAN_MEMBER_TABLE|Vlan4|Ethernet24")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_VLAN_MEMBER:oid:0x27000000000624")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT:oid:0x3a000000000623")
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect), ignore_order=True)
        assert not ddiff, ddiff

    # Wildcard works for CONFIG, APPL & STATE, but not currently suppoerted for ASIC
    def test_working_state_vlan_member_wildcard(self, match_engine):
        params = {}
        params["namespace"] = ""
        params[Vlan_Member.ARG_NAME] = "Vlan4|*"
        m_vlan = Vlan_Member(match_engine)
        returned = m_vlan.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].append("VLAN_MEMBER|Vlan4|Ethernet16")
        expect["CONFIG_DB"]["keys"].append("VLAN_MEMBER|Vlan4|Ethernet24")
        expect["APPL_DB"]["keys"].append("VLAN_MEMBER_TABLE:Vlan4:Ethernet16")
        expect["APPL_DB"]["keys"].append("VLAN_MEMBER_TABLE:Vlan4:Ethernet24")
        expect["STATE_DB"]["keys"].append("VLAN_MEMBER_TABLE|Vlan4|Ethernet16")
        expect["STATE_DB"]["keys"].append("VLAN_MEMBER_TABLE|Vlan4|Ethernet24")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_VLAN_MEMBER")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT")
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect), ignore_order=True)
        assert not ddiff, ddiff

    def test_missing_members(self, match_engine):
        params = {}
        params[Vlan.ARG_NAME] = "Vlan2"
        params["namespace"] = ""
        m_vlan = Vlan(match_engine)
        returned = m_vlan.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].append("VLAN|Vlan2")
        expect["APPL_DB"]["keys"].append("VLAN_TABLE:Vlan2")
        expect["STATE_DB"]["keys"].append("VLAN_TABLE|Vlan2")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_VLAN:oid:0x26000000000617")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff
    
    def test_wrong_case_vlan(self, match_engine):
        params = {}
        params[Vlan.ARG_NAME] = "VLAN4"
        params["namespace"] = ""
        m_vlan = Vlan(match_engine)
        returned = m_vlan.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["tables_not_found"].append("VLAN")
        expect["APPL_DB"]["tables_not_found"].append("VLAN_TABLE")
        expect["STATE_DB"]["tables_not_found"].append("VLAN_TABLE")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_VLAN")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff
    
    def test_wrong_case_vlan_member(self, match_engine):
        params = {}
        params[Vlan_Member.ARG_NAME] = "Vlan4|ETHERNET16"
        params["namespace"] = ""
        m_vlan = Vlan_Member(match_engine)
        returned = m_vlan.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["tables_not_found"].append("VLAN_MEMBER")
        expect["APPL_DB"]["tables_not_found"].append("VLAN_MEMBER_TABLE")
        expect["STATE_DB"]["tables_not_found"].append("VLAN_MEMBER_TABLE")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_VLAN_MEMBER")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff
    
    def test_unconfigured_vlan(self, match_engine):
        params = {}
        params[Vlan.ARG_NAME] = "Vlan5"
        params["namespace"] = ""
        m_vlan = Vlan(match_engine)
        returned = m_vlan.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["tables_not_found"].append("VLAN")
        expect["APPL_DB"]["tables_not_found"].append("VLAN_TABLE")
        expect["STATE_DB"]["tables_not_found"].append("VLAN_TABLE")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_VLAN")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff
    
    def test_unconfigured_vlan_member(self, match_engine):
        params = {}
        params[Vlan_Member.ARG_NAME] = "Vlan4|Ethernet0"   # member but not in that vlan
        params["namespace"] = ""
        m_vlan = Vlan_Member(match_engine)
        returned = m_vlan.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["tables_not_found"].append("VLAN_MEMBER")
        expect["APPL_DB"]["tables_not_found"].append("VLAN_MEMBER_TABLE")
        expect["STATE_DB"]["tables_not_found"].append("VLAN_MEMBER_TABLE")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_VLAN_MEMBER")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff
    
    def test_garbage_alpha_vlan(self, match_engine):
        params = {}
        params[Vlan.ARG_NAME] = "garbage"
        params["namespace"] = ""
        m_vlan = Vlan(match_engine)
        returned = m_vlan.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["tables_not_found"].append("VLAN")
        expect["APPL_DB"]["tables_not_found"].append("VLAN_TABLE")
        expect["STATE_DB"]["tables_not_found"].append("VLAN_TABLE")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_VLAN")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff
    
    def test_garbage_alpha_vlan_member(self, match_engine):
        params = {}
        params[Vlan_Member.ARG_NAME] = "garbage"
        params["namespace"] = ""
        m_vlan = Vlan_Member(match_engine)
        returned = m_vlan.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["tables_not_found"].append("VLAN_MEMBER")
        expect["APPL_DB"]["tables_not_found"].append("VLAN_MEMBER_TABLE")
        expect["STATE_DB"]["tables_not_found"].append("VLAN_MEMBER_TABLE")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_VLAN_MEMBER")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff
    
    def test_garbage_number_vlan(self, match_engine):
        params = {}
        params[Vlan.ARG_NAME] = "614"
        params["namespace"] = ""
        m_vlan = Vlan(match_engine)
        returned = m_vlan.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["tables_not_found"].append("VLAN")
        expect["APPL_DB"]["tables_not_found"].append("VLAN_TABLE")
        expect["STATE_DB"]["tables_not_found"].append("VLAN_TABLE")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_VLAN")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff
    
    def test_garbage_number_vlan_member(self, match_engine):
        params = {}
        params[Vlan_Member.ARG_NAME]= "3892"
        params["namespace"] = ""
        m_vlan = Vlan_Member(match_engine)
        returned = m_vlan.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["tables_not_found"].append("VLAN_MEMBER")
        expect["APPL_DB"]["tables_not_found"].append("VLAN_MEMBER_TABLE")
        expect["STATE_DB"]["tables_not_found"].append("VLAN_MEMBER_TABLE")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_VLAN_MEMBER")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff
    
    # Vlan6 is not defined in appl_db
    def test_missing_appl_db(self, match_engine):
        params = {}
        params[Vlan.ARG_NAME] = "Vlan6"
        params["namespace"] = ""
        m_vlan = Vlan(match_engine)
        returned = m_vlan.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].append("VLAN|Vlan6")
        expect["APPL_DB"]["tables_not_found"].append("VLAN_TABLE")
        expect["STATE_DB"]["keys"].append("VLAN_TABLE|Vlan6")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_VLAN:oid:0x2600000000061a")
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect), ignore_order=True)
        assert not ddiff, ddiff
        
    def test_missing_appl_db_member(self, match_engine):
        params = {}
        params[Vlan_Member.ARG_NAME] = "Vlan6|Ethernet32"
        params["namespace"] = ""
        m_vlan = Vlan_Member(match_engine)
        returned = m_vlan.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].append("VLAN_MEMBER|Vlan6|Ethernet32")
        expect["APPL_DB"]["tables_not_found"].append("VLAN_MEMBER_TABLE")
        expect["STATE_DB"]["keys"].append("VLAN_MEMBER_TABLE|Vlan6|Ethernet32")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_VLAN_MEMBER:oid:0x27000000000626")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT:oid:0x3a000000000625")
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect), ignore_order=True)
        assert not ddiff, ddiff
        
    # Vlan7 is not defined in state_db
    def test_missing_state_db(self, match_engine):
        params = {}
        params[Vlan.ARG_NAME] = "Vlan7"
        params["namespace"] = ""
        m_vlan = Vlan(match_engine)
        returned = m_vlan.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].append("VLAN|Vlan7")
        expect["APPL_DB"]["keys"].append("VLAN_TABLE:Vlan7")
        expect["STATE_DB"]["tables_not_found"].append("VLAN_TABLE")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_VLAN:oid:0x2600000000061b")
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect), ignore_order=True)
        assert not ddiff, ddiff
        
    def test_missing_state_db_member(self, match_engine):
        params = {}
        params[Vlan_Member.ARG_NAME] = "Vlan7|Ethernet56"
        params["namespace"] = ""
        m_vlan = Vlan_Member(match_engine)
        returned = m_vlan.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].append("VLAN_MEMBER|Vlan7|Ethernet56")
        expect["APPL_DB"]["keys"].append("VLAN_MEMBER_TABLE:Vlan7:Ethernet56")
        expect["STATE_DB"]["tables_not_found"].append("VLAN_MEMBER_TABLE")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_VLAN_MEMBER:oid:0x2700000000062c")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT:oid:0x3a00000000062b")
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect), ignore_order=True)
        assert not ddiff, ddiff
        
    # Vlan8 is not defined in asic_db
    def test_missing_asic_db(self, match_engine):
        params = {}
        params[Vlan.ARG_NAME] = "Vlan8"
        params["namespace"] = ""
        m_vlan = Vlan(match_engine)
        returned = m_vlan.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].append("VLAN|Vlan8")
        expect["APPL_DB"]["keys"].append("VLAN_TABLE:Vlan8")
        expect["STATE_DB"]["keys"].append("VLAN_TABLE|Vlan8")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_VLAN")
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect), ignore_order=True)
        assert not ddiff, ddiff
        
    def test_missing_asic_db_member(self, match_engine):
        params = {}
        params[Vlan_Member.ARG_NAME] = "Vlan8|Ethernet72"
        params["namespace"] = ""
        m_vlan = Vlan_Member(match_engine)
        returned = m_vlan.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].append("VLAN_MEMBER|Vlan8|Ethernet72")
        expect["APPL_DB"]["keys"].append("VLAN_MEMBER_TABLE:Vlan8:Ethernet72")
        expect["STATE_DB"]["keys"].append("VLAN_MEMBER_TABLE|Vlan8|Ethernet72")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_VLAN_MEMBER")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT")
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect), ignore_order=True)
        assert not ddiff, ddiff
        
    def test_all_args(self, match_engine):
        params = {}
        m_vlan = Vlan(match_engine)
        returned = m_vlan.get_all_args("")
        expect = ["Vlan2", "Vlan3", "Vlan4", "Vlan6", "Vlan7", "Vlan8"]
        ddiff = DeepDiff(expect, returned, ignore_order=True)
        assert not ddiff, ddiff 

    def test_all_args_member(self, match_engine):
        params = {}
        m_vlan = Vlan_Member(match_engine)
        returned = m_vlan.get_all_args("")
        expect = ["Vlan3|Ethernet0", "Vlan3|Ethernet8", 
                  "Vlan4|Ethernet16", "Vlan4|Ethernet24", 
                  "Vlan6|Ethernet32", "Vlan6|Ethernet40", 
                  "Vlan7|Ethernet48", "Vlan7|Ethernet56", 
                  "Vlan8|Ethernet64", "Vlan8|Ethernet72"]
        ddiff = DeepDiff(expect, returned, ignore_order=True)
        assert not ddiff, ddiff 

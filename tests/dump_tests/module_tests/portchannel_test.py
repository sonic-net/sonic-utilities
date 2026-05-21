import json, os, sys
import jsonpatch
import unittest
import pytest
from deepdiff import DeepDiff
from mock import patch
from dump.helper import create_template_dict, sort_lists, populate_mock
from dump.plugins.portchannel import Portchannel
from dump.match_infra import MatchEngine, ConnectionPool
from swsscommon.swsscommon import SonicV2Connector
from utilities_common.constants import DEFAULT_NAMESPACE

# Location for dedicated db's used for UT
module_tests_path = os.path.dirname(__file__)
dump_tests_path = os.path.join(module_tests_path, "../")
tests_path = os.path.join(dump_tests_path, "../")
dump_test_input = os.path.join(tests_path, "dump_input")
port_files_path = os.path.join(dump_test_input, "portchannel")

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
class TestPortChannelModule:
    def test_get_all_args(self, match_engine):
        """
        Scenario: Verify Whether the get_all_args method is working as expected
        """
        m_lag = Portchannel(match_engine)
        returned = m_lag.get_all_args("")
        expect = ["PortChannel001", "PortChannel002", "PortChannel003"]
        ddiff = DeepDiff(expect, returned, ignore_order=True)
        assert not ddiff, ddiff

    def test_missing_appl_state_asic(self, match_engine):
        '''
        Scenario: When the LAG is configured but the Change is not propagated
        '''
        params = {Portchannel.ARG_NAME:"PortChannel003", "namespace":""}
        m_lag = Portchannel(match_engine)
        returned = m_lag.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].append("PORTCHANNEL|PortChannel003")
        expect["APPL_DB"]["tables_not_found"].append("LAG_TABLE")
        expect["STATE_DB"]["tables_not_found"].append("LAG_TABLE")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_LAG")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_lag_with_no_members(self, match_engine):
        '''
        Scenario: When the PortChannel doesn't have any members, 
                  it is not possible to uniquely identify ASIC LAG Related Key
        '''
        params = {Portchannel.ARG_NAME:"PortChannel002", "namespace":""}
        m_lag = Portchannel(match_engine)
        returned = m_lag.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].append("PORTCHANNEL|PortChannel002")
        expect["APPL_DB"]["keys"].append("LAG_TABLE:PortChannel002")
        expect["STATE_DB"]["keys"].append("LAG_TABLE|PortChannel002")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_LAG")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_lag_with_members(self, match_engine):
        '''
        Scenario: It should be possible to uniquely identify ASIC LAG Related Keys,
                  when the LAG has members
        '''
        params = {Portchannel.ARG_NAME:"PortChannel001", "namespace":""}
        m_lag = Portchannel(match_engine)
        returned = m_lag.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].append("PORTCHANNEL|PortChannel001")
        expect["APPL_DB"]["keys"].append("LAG_TABLE:PortChannel001")
        expect["STATE_DB"]["keys"].append("LAG_TABLE|PortChannel001")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_LAG:oid:0x2000000000d17")
        ddiff = DeepDiff(expect, returned, ignore_order=True)
        print(returned, expect, ddiff)
        assert not ddiff, ddiff

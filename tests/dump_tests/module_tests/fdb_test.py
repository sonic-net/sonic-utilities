import json
import os
import sys
import jsonpatch
import unittest
import pytest
from deepdiff import DeepDiff
from mock import patch
from dump.helper import create_template_dict, populate_mock
from dump.plugins.fdb import Fdb
from dump.match_infra import MatchEngine, ConnectionPool
from swsscommon.swsscommon import SonicV2Connector
from utilities_common.constants import DEFAULT_NAMESPACE

# Location for dedicated db's used for UT
module_tests_path = os.path.dirname(__file__)
dump_tests_path = os.path.join(module_tests_path, "../")
tests_path = os.path.join(dump_tests_path, "../")
dump_test_input = os.path.join(tests_path, "dump_input")
fdb_files_path = os.path.join(dump_test_input, "fdb")

# Define the mock files to read from
dedicated_dbs = {}
dedicated_dbs['APPL_DB'] = os.path.join(fdb_files_path, "appl_db.json")
dedicated_dbs['ASIC_DB'] = os.path.join(fdb_files_path, "asic_db.json")
dedicated_dbs['STATE_DB'] = os.path.join(fdb_files_path, "state_db.json")



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
class TestFdbModule:
    def test_fdb_asic_learn_state(self, match_engine):
        """
        Scenario: When FDB is learnt through hardware
        """
        params = {Fdb.ARG_NAME: "Vlan50:04:3f:72:e3:70:08", "namespace": ""}
        m_fdb = Fdb(match_engine)
        returned = m_fdb.execute(params)
        expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["STATE_DB"]["keys"].append("FDB_TABLE|Vlan50:04:3f:72:e3:70:08")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT:oid:0x3a000000000d23")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_FDB_ENTRY:{\"bvid\":\"oid:0x26000000000d22\",\"mac\":\"04:3F:72:E3:70:08\",\"switch_id\":\"oid:0x21000000000000\"}")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_fdb_app_program_state(self, match_engine):
        """
        Scenario: When FDB is learnt through EVPN
        """
        params = {Fdb.ARG_NAME: "Vlan10:04:3f:72:ce:80:8b", "namespace": ""}
        m_fdb = Fdb(match_engine)
        returned = m_fdb.execute(params)
        expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["APPL_DB"]["keys"].append("FDB_TABLE:Vlan10:04:3f:72:ce:80:8b")
        expect["STATE_DB"]["keys"].append("FDB_TABLE|Vlan10:04:3f:72:ce:80:8b")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT:oid:0x3a000000000d18")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_FDB_ENTRY:{\"bvid\":\"oid:0x26000000000d20\",\"mac\":\"04:3F:72:CE:80:8B\",\"switch_id\":\"oid:0x21000000000000\"}")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_fdb_evpn_learn_state(self, match_engine):
        """
        Scenario: When FDB is learnt through EVPN
        """
        params = {Fdb.ARG_NAME: "Vlan10:04:3f:72:ce:80:8c", "namespace": ""}
        m_fdb = Fdb(match_engine)
        returned = m_fdb.execute(params)
        expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["APPL_DB"]["keys"].append("VXLAN_FDB_TABLE:Vlan10:04:3f:72:ce:80:8c")
        expect["STATE_DB"]["keys"].append("FDB_TABLE|Vlan10:04:3f:72:ce:80:8c")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT:oid:0x3a000000000d18")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_FDB_ENTRY:{\"bvid\":\"oid:0x26000000000d20\",\"mac\":\"04:3F:72:CE:80:8C\",\"switch_id\":\"oid:0x21000000000000\"}")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_fdb_mclag_sync_state(self, match_engine):
        """
        Scenario: When FDB is learnt through EVPN
        """
        params = {Fdb.ARG_NAME: "Vlan10:04:3f:72:ce:80:8d", "namespace": ""}
        m_fdb = Fdb(match_engine)
        returned = m_fdb.execute(params)
        expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["APPL_DB"]["keys"].append("MCLAG_FDB_TABLE:Vlan10:04:3f:72:ce:80:8d")
        expect["STATE_DB"]["keys"].append("FDB_TABLE|Vlan10:04:3f:72:ce:80:8d")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT:oid:0x3a000000000d18")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_FDB_ENTRY:{\"bvid\":\"oid:0x26000000000d20\",\"mac\":\"04:3F:72:CE:80:8D\",\"switch_id\":\"oid:0x21000000000000\"}")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_missing_asic_bridgeport(self, match_engine):
        """
        Scenario: When FDB is learnt through hardware but bridge port is missing
        """
        params = {Fdb.ARG_NAME: "Vlan690:04:3f:72:ce:80:8b", "namespace": ""}
        m_fdb = Fdb(match_engine)
        returned = m_fdb.execute(params)
        expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["STATE_DB"]["keys"].append("FDB_TABLE|Vlan690:04:3f:72:ce:80:8b")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_FDB_ENTRY:{\"bvid\":\"oid:0x26000000000d1c\",\"mac\":\"04:3F:72:CE:80:8B\",\"switch_id\":\"oid:0x21000000000000\"}")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_missing_asic_vlan(self, match_engine):
        """
        Scenario: When FDB is learnt through hardware but vlan is missing
        """
        params = {Fdb.ARG_NAME: "Vlan40:04:3f:72:e3:70:09", "namespace": ""}
        m_fdb = Fdb(match_engine)
        returned = m_fdb.execute(params)
        expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["STATE_DB"]["keys"].append("FDB_TABLE|Vlan40:04:3f:72:e3:70:09")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_FDB_ENTRY")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_missing_asic(self, match_engine):
        """
        Scenario: When FDB is learnt through hardware but asic db is deleted
        """
        params = {Fdb.ARG_NAME: "Vlan691:04:3f:72:ce:80:8b", "namespace": ""}
        m_fdb = Fdb(match_engine)
        returned = m_fdb.execute(params)
        expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["STATE_DB"]["keys"].append("FDB_TABLE|Vlan691:04:3f:72:ce:80:8b")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_FDB_ENTRY")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_no_fdb(self, match_engine):
        """
        Scenario: When no entry for the fdb is present in any of the db's
        """
        params = {Fdb.ARG_NAME: "Vlan691:04:3f:72:ce:80:8c", "namespace": ""}
        m_fdb = Fdb(match_engine)
        returned = m_fdb.execute(params)
        expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["STATE_DB"]["tables_not_found"].append("FDB_TABLE")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_FDB_ENTRY")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_invalid_key(self, match_engine):
        """
        Scenario: When invalid fdb key is given as input
        """
        params = {Fdb.ARG_NAME: "012345abcdef", "namespace": ""}
        m_fdb = Fdb(match_engine)
        returned = m_fdb.execute(params)
        expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["STATE_DB"]["tables_not_found"].append("FDB_TABLE")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_FDB_ENTRY")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_invalid_mac(self, match_engine):
        """
        Scenario: When invalid fdb key is given as input
        """
        params = {Fdb.ARG_NAME: "Vlan690:012345abcdef", "namespace": ""}
        m_fdb = Fdb(match_engine)
        returned = m_fdb.execute(params)
        expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["STATE_DB"]["tables_not_found"].append("FDB_TABLE")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_FDB_ENTRY")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_invalid_vlan(self, match_engine):
        """
        Scenario: When invalid fdb key is given as input
        """
        params = {Fdb.ARG_NAME: "Vlan6900:04:3f:72:ce:80:8b", "namespace": ""}
        m_fdb = Fdb(match_engine)
        returned = m_fdb.execute(params)
        expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["STATE_DB"]["tables_not_found"].append("FDB_TABLE")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_BRIDGE_PORT")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_FDB_ENTRY")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_all_args(self, match_engine):
        """
        Scenario: Verify Whether the get_all_args method is working as expected
        """
        params = {}
        m_fdb = Fdb(match_engine)
        returned = m_fdb.get_all_args("")
        expect = ["Vlan50:04:3f:72:e3:70:08", "Vlan10:04:3f:72:ce:80:8b", "Vlan10:04:3f:72:ce:80:8c", "Vlan10:04:3f:72:ce:80:8d", "Vlan690:04:3f:72:ce:80:8b", "Vlan40:04:3f:72:e3:70:09", "Vlan691:04:3f:72:ce:80:8b"]
        ddiff = DeepDiff(expect, returned, ignore_order=True)
        assert not ddiff, ddiff

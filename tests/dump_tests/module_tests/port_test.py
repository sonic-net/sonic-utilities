import json
import os
import sys
import jsonpatch
import unittest
import pytest
from deepdiff import DeepDiff
from mock import patch
from dump.helper import create_template_dict, sort_lists, populate_mock
from dump.plugins.port import Port
from dump.match_infra import MatchEngine, ConnectionPool
from swsscommon.swsscommon import SonicV2Connector
from utilities_common.constants import DEFAULT_NAMESPACE

# Location for dedicated db's used for UT
module_tests_path = os.path.dirname(__file__)
dump_tests_path = os.path.join(module_tests_path, "../")
tests_path = os.path.join(dump_tests_path, "../")
dump_test_input = os.path.join(tests_path, "dump_input")
port_files_path = os.path.join(dump_test_input, "port")

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
class TestPortModule:
    def test_working_state(self, match_engine):
        """
        Scenario: When the config is properly applied and propagated
        """
        params = {Port.ARG_NAME: "Ethernet176", "namespace": ""}
        m_port = Port(match_engine)
        returned = m_port.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].append("PORT|Ethernet176")
        expect["APPL_DB"]["keys"].append("PORT_TABLE:Ethernet176")
        expect["STATE_DB"]["keys"].append("PORT_TABLE|Ethernet176")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_PORT:oid:0x100000000036a")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF:oid:0xd000000000a4d")
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect), ignore_order=True)
        assert not ddiff, ddiff

    def test_missing_asic_port(self, match_engine):
        """
        Scenario: When the config was applied and just the SAI_OBJECT_TYPE_PORT is missing
        """
        params = {Port.ARG_NAME: "Ethernet160", "namespace": ""}
        m_port = Port(match_engine)
        returned = m_port.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].append("PORT|Ethernet160")
        expect["APPL_DB"]["keys"].append("PORT_TABLE:Ethernet160")
        expect["STATE_DB"]["keys"].append("PORT_TABLE|Ethernet160")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF:oid:0xd000000000a49")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_PORT")
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect), ignore_order=True)
        assert not ddiff, ddiff

    def test_missing_asic_hostif(self, match_engine):
        """
        Scenario: When the config was applied and it did not propagate to ASIC DB
        """
        params = {Port.ARG_NAME: "Ethernet164", "namespace": ""}
        m_port = Port(match_engine)
        returned = m_port.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].append("PORT|Ethernet164")
        expect["APPL_DB"]["keys"].append("PORT_TABLE:Ethernet164")
        expect["STATE_DB"]["keys"].append("PORT_TABLE|Ethernet164")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_PORT")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_missing_state_and_appl(self, match_engine):
        """
        Scenario: When the config was applied and it did not propagate to other db's
        """
        params = {Port.ARG_NAME: "Ethernet156", "namespace": ""}
        m_port = Port(match_engine)
        returned = m_port.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["keys"].append("PORT|Ethernet156")
        expect["APPL_DB"]["tables_not_found"].append("PORT_TABLE")
        expect["STATE_DB"]["tables_not_found"].append("PORT_TABLE")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_PORT")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_no_port(self, match_engine):
        """
        Scenario: When no entry for the port is present in any of the db's
        """
        params = {Port.ARG_NAME: "Ethernet152", "namespace": ""}
        m_port = Port(match_engine)
        returned = m_port.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        expect["CONFIG_DB"]["tables_not_found"].append("PORT")
        expect["APPL_DB"]["tables_not_found"].append("PORT_TABLE")
        expect["STATE_DB"]["tables_not_found"].append("PORT_TABLE")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_PORT")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_all_args(self, match_engine):
        """
        Scenario: Verify Whether the get_all_args method is working as expected
        """
        params = {}
        m_port = Port(match_engine)
        returned = m_port.get_all_args("")
        expect = ["Ethernet156", "Ethernet160", "Ethernet164", "Ethernet176"]
        ddiff = DeepDiff(expect, returned, ignore_order=True)
        assert not ddiff, ddiff

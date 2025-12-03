import json
import os
import pytest
from deepdiff import DeepDiff
from dump.helper import create_template_dict, populate_mock
from dump.plugins.vxlan_tunnel_map import Vxlan_tunnel_map
from dump.match_infra import MatchEngine, ConnectionPool
from swsscommon.swsscommon import SonicV2Connector
from utilities_common.constants import DEFAULT_NAMESPACE

# Location for dedicated db's used for UT
module_tests_path = os.path.dirname(__file__)
dump_tests_path = os.path.join(module_tests_path, "../")
tests_path = os.path.join(dump_tests_path, "../")
dump_test_input = os.path.join(tests_path, "dump_input")
vxlan_tunnel_map_files_path = os.path.join(dump_test_input, "vxlan")

# Define the mock files to read from
dedicated_dbs = {}
dedicated_dbs['CONFIG_DB'] = os.path.join(vxlan_tunnel_map_files_path, "config_db.json")
dedicated_dbs['APPL_DB'] = os.path.join(vxlan_tunnel_map_files_path, "appl_db.json")
dedicated_dbs['ASIC_DB'] = os.path.join(vxlan_tunnel_map_files_path, "asic_db.json")


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
class TestVxlantunnelmapModule:
    def test_working_state(self, match_engine):
        """
        Scenario: When the config is properly applied and propagated
        """
        params = {Vxlan_tunnel_map.ARG_NAME: "vtep_1336|map_1336_Vlan2345", "namespace": ""}
        m_vxlan_tunnel_map = Vxlan_tunnel_map(match_engine)
        returned = m_vxlan_tunnel_map.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB"])
        expect["CONFIG_DB"]["keys"].append("VXLAN_TUNNEL_MAP|vtep_1336|map_1336_Vlan2345")
        expect["APPL_DB"]["keys"].append("VXLAN_TUNNEL_MAP_TABLE:vtep_1336:map_1336_Vlan2345")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP_ENTRY:oid:0x3b0000000007ef")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP:oid:0x290000000007e9")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_missing_asic_vxlan_tunnel_map_entry(self, match_engine):
        """
        Scenario: When the config was applied and asic db tables are missing
        """
        params = {Vxlan_tunnel_map.ARG_NAME: "vtep_1336|map_1337_Vlan2346", "namespace": ""}
        m_vxlan_tunnel_map = Vxlan_tunnel_map(match_engine)
        returned = m_vxlan_tunnel_map.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB"])
        expect["CONFIG_DB"]["keys"].append("VXLAN_TUNNEL_MAP|vtep_1336|map_1337_Vlan2346")
        expect["APPL_DB"]["keys"].append("VXLAN_TUNNEL_MAP_TABLE:vtep_1336:map_1337_Vlan2346")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP_ENTRY")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_missing_appl(self, match_engine):
        """
        Scenario: When the config was applied and it did not propagate to other db's
        """
        params = {Vxlan_tunnel_map.ARG_NAME: "vtep_1338|map_1338_Vlan2347", "namespace": ""}
        m_vxlan_tunnel_map = Vxlan_tunnel_map(match_engine)
        returned = m_vxlan_tunnel_map.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB"])
        expect["CONFIG_DB"]["keys"].append("VXLAN_TUNNEL_MAP|vtep_1338|map_1338_Vlan2347")
        expect["APPL_DB"]["tables_not_found"].append("VXLAN_TUNNEL_MAP_TABLE")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP_ENTRY")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_no_vxlan_tunnel_map(self, match_engine):
        """
        Scenario: When the config was not present
        """
        params = {Vxlan_tunnel_map.ARG_NAME: "vtep_1338|map_1339_Vlan2348", "namespace": ""}
        m_vxlan_tunnel_map = Vxlan_tunnel_map(match_engine)
        returned = m_vxlan_tunnel_map.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB"])
        expect["CONFIG_DB"]["tables_not_found"].append("VXLAN_TUNNEL_MAP")
        expect["APPL_DB"]["tables_not_found"].append("VXLAN_TUNNEL_MAP_TABLE")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP_ENTRY")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_TUNNEL_MAP")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_all_args(self, match_engine):
        """
        Scenario: Verify Whether the get_all_args method is working as expected
        """
        m_vxlan_tunnel_map = Vxlan_tunnel_map(match_engine)
        returned = m_vxlan_tunnel_map.get_all_args("")
        expect = ["vtep_1336|map_1336_Vlan2345", "vtep_1336|map_1337_Vlan2346", "vtep_1338|map_1338_Vlan2347"]
        ddiff = DeepDiff(expect, returned, ignore_order=True)
        assert not ddiff, ddiff

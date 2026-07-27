import os
import pytest
from deepdiff import DeepDiff
from dump.helper import create_template_dict, populate_mock
try:
    from dump.plugins.dash_vnet_mapping import Dash_Vnet_mapping
except ModuleNotFoundError:
    pytest.skip("Skipping Dash tests since it is not supported in this Platform", allow_module_level=True)
from dump.match_infra import MatchEngine, ConnectionPool
from swsscommon.swsscommon import SonicV2Connector
from utilities_common.constants import DEFAULT_NAMESPACE
import redis

# Location for dedicated db's used for UT
module_tests_path = os.path.dirname(__file__)
dump_tests_path = os.path.join(module_tests_path, "../")
tests_path = os.path.join(dump_tests_path, "../")
dump_test_input = os.path.join(tests_path, "dump_input")
dash_input_files_path = os.path.join(dump_test_input, "dash")

# Define the mock files to read from
dedicated_dbs = {}
dedicated_dbs['APPL_DB'] = os.path.join(dash_input_files_path, "appl_db.json")
dedicated_dbs['ASIC_DB'] = os.path.join(dash_input_files_path, "asic_db.json")


@pytest.fixture(scope="class", autouse=True)
def match_engine():

    print("SETUP")
    os.environ["VERBOSE"] = "1"

    # Monkey Patch the SonicV2Connector Object
    db = SonicV2Connector()
    from ...dump_tests import mock_redis
    redis.Redis = mock_redis.RedisMock

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
class TestDashVnetMappingModule:
    def test_working_state(self, match_engine):
        """
        Scenario: When the appl info is properly applied and propagated
        """
        params = {Dash_Vnet_mapping.ARG_NAME: "Vnet1:12.1.1.1", "namespace": ""}
        m_dash_vnet_mapping = Dash_Vnet_mapping(match_engine)
        returned = m_dash_vnet_mapping.execute(params)
        expect = create_template_dict(dbs=["APPL_DB"])
        expect["APPL_DB"]["keys"].append("DASH_VNET_MAPPING_TABLE:Vnet1:12.1.1.1")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_not_working_state(self, match_engine):
        """
        Scenario: Missing Keys
        """
        params = {Dash_Vnet_mapping.ARG_NAME: "Vnet2:12.1.1.1", "namespace": ""}
        m_dash_vnet_mapping = Dash_Vnet_mapping(match_engine)
        returned = m_dash_vnet_mapping.execute(params)
        expect = create_template_dict(dbs=["APPL_DB"])
        expect["APPL_DB"]["tables_not_found"].append("DASH_VNET_MAPPING_TABLE")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        print(returned)
        assert not ddiff, ddiff

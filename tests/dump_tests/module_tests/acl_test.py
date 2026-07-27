import os
import pytest
from deepdiff import DeepDiff
from dump.helper import create_template_dict, sort_lists, populate_mock
from dump.plugins.acl_table import Acl_Table
from dump.plugins.acl_rule import Acl_Rule
from dump.match_infra import MatchEngine, ConnectionPool
from swsscommon.swsscommon import SonicV2Connector
from utilities_common.constants import DEFAULT_NAMESPACE

# Location for dedicated db's used for UT
module_tests_path = os.path.dirname(__file__)
dump_tests_path = os.path.join(module_tests_path, "../")
tests_path = os.path.join(dump_tests_path, "../")
dump_test_input = os.path.join(tests_path, "dump_input")
port_files_path = os.path.join(dump_test_input, "acl")

# Define the mock files to read from
dedicated_dbs = {}
dedicated_dbs['CONFIG_DB'] = os.path.join(port_files_path, "config_db.json")
dedicated_dbs['APPL_DB'] = os.path.join(port_files_path, "appl_db.json")
dedicated_dbs['COUNTERS_DB'] = os.path.join(port_files_path, "counters_db.json")
dedicated_dbs['ASIC_DB'] = os.path.join(port_files_path, "asic_db.json")


@pytest.fixture(scope="class", autouse=True)
def match_engine():
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
    os.environ["VERBOSE"] = "0"


@pytest.mark.usefixtures("match_engine")
class TestAclTableModule:
    def test_basic(self, match_engine):
        """
        Scenario: When the basic config is properly applied and propagated
        """
        params = {Acl_Table.ARG_NAME: "DATAACL", "namespace": ""}
        m_acl_table = Acl_Table(match_engine)
        returned = m_acl_table.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB"])
        expect["CONFIG_DB"]["keys"].append("ACL_TABLE|DATAACL")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_ACL_TABLE:oid:0x7000000000600")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_ACL_TABLE_GROUP_MEMBER:oid:0xc000000000601")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_ACL_TABLE_GROUP_MEMBER:oid:0xc000000000602")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_ACL_TABLE_GROUP:oid:0xb0000000005f5")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_ACL_TABLE_GROUP:oid:0xb0000000005f7")
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect))
        assert not ddiff, ddiff

    def test_no_counter_mapping(self, match_engine):
        """
        Scenario: When there is no ACL_COUNTER_RULE_MAP mapping for rule
        """
        params = {Acl_Table.ARG_NAME: "DATAACL1", "namespace": ""}
        m_acl_table = Acl_Table(match_engine)
        returned = m_acl_table.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB"])
        expect["CONFIG_DB"]["keys"].append("ACL_TABLE|DATAACL1")
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect))
        assert not ddiff, ddiff

    def test_with_table_type(self, match_engine):
        """
        Scenario: When there is ACL_TABLE_TYPE configured for this table
        """
        params = {Acl_Table.ARG_NAME: "DATAACL2", "namespace": ""}
        m_acl_table = Acl_Table(match_engine)
        returned = m_acl_table.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB"])
        expect["APPL_DB"]["keys"].append("ACL_TABLE_TABLE:DATAACL2")
        expect["APPL_DB"]["keys"].append("ACL_TABLE_TYPE_TABLE:MY_TYPE")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_ACL_TABLE:oid:0x7100000000600")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_ACL_TABLE_GROUP_MEMBER:oid:0xc100000000601")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_ACL_TABLE_GROUP_MEMBER:oid:0xc100000000602")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_ACL_TABLE_GROUP:oid:0xb0000000005f5")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_ACL_TABLE_GROUP:oid:0xb0000000005f7")
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect))
        assert not ddiff, ddiff

    def test_all_arg(self, match_engine):
        """
        Scenario: Test if all arg returns from config_db and appl_db
        """
        m_acl_table = Acl_Table(match_engine)
        returned = m_acl_table.get_all_args()
        returned.sort()
        expected = ['DATAACL', 'DATAACL1', 'DATAACL2', 'SNMP_ACL']
        assert returned == expected, returned


@pytest.mark.usefixtures("match_engine")
class TestAclRuleModule:
    def test_basic(self, match_engine):
        """
        Scenario: When the config is properly applied and propagated
        """
        params = {Acl_Rule.ARG_NAME: "DATAACL|R0", "namespace": ""}
        m_acl_rule = Acl_Rule(match_engine)
        returned = m_acl_rule.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB"])
        expect["CONFIG_DB"]["keys"].append("ACL_RULE|DATAACL|R0")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_ACL_COUNTER:oid:0x9000000000606")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_ACL_ENTRY:oid:0x8000000000609")
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect))
        assert not ddiff, ddiff

    def test_with_ranges(self, match_engine):
        """
        Scenario: When ACL rule has range configuration
        """
        params = {Acl_Rule.ARG_NAME: "DATAACL2|R0", "namespace": ""}
        m_acl_rule = Acl_Rule(match_engine)
        returned = m_acl_rule.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB"])
        expect["APPL_DB"]["keys"].append("ACL_RULE_TABLE:DATAACL2:R0")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_ACL_COUNTER:oid:0x9100000000606")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_ACL_ENTRY:oid:0x8100000000609")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_ACL_RANGE:oid:0xa100000000607")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_ACL_RANGE:oid:0xa100000000608")
        ddiff = DeepDiff(sort_lists(returned), sort_lists(expect))
        assert not ddiff, ddiff

    def test_all_arg(self, match_engine):
        """
        Scenario: Test if all arg returns from config_db and appl_db
        """
        m_acl_rule = Acl_Rule(match_engine)
        returned = m_acl_rule.get_all_args()
        returned.sort()
        expected = ['DATAACL2:R0', 'DATAACL|R0']
        assert returned == expected, returned

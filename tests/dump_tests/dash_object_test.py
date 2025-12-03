import os
import pytest
from dump.match_infra import MatchEngine, MatchRequest, ConnectionPool, CONN
try:
    from dump.plugins.dash_acl_out import Dash_Acl_Out
    from dump.plugins.dash_acl_in import Dash_Acl_In
    from dump.plugins.dash_acl_group import Dash_Acl_Group
    from dump.plugins.dash_prefix_tag import Dash_Prefix_Tag
    from dump.plugins.dash_acl_rule import Dash_Acl_Rule
    from dump.plugins.dash_appliance import Dash_Appliance
    from dump.plugins.dash_eni import Dash_Eni
    from dump.plugins.dash_qos import Dash_Qos
    from dump.plugins.dash_vnet import Dash_Vnet
    from dump.plugins.dash_vnet_mapping import Dash_Vnet_mapping
    from dump.plugins.dash_route import Dash_Route
except ModuleNotFoundError:
    pytest.skip("Skipping Dash tests since it is not supported in this Platform", allow_module_level=True)
from utilities_common.constants import DEFAULT_NAMESPACE
from dump.helper import populate_mock
from .mock_redis import RedisMock
from click.testing import CliRunner
from .dump_state_test import compare_json_output
import dump.main as dump

from swsscommon.swsscommon import SonicV2Connector
from ..mock_tables import dbconnector

test_path = os.path.join(os.path.dirname(__file__), "../")
dump_test_input = os.path.join(test_path, "dump_input")


@pytest.fixture(scope="module", autouse=True)
def match_engine():
    print("SETUP")
    os.environ["VERBOSE"] = "1"
    dbconnector.load_namespace_config()

    dump_input = os.path.join(os.path.dirname(__file__), "../dump_input/")
    dedicated_dbs = {}
    redisMock = RedisMock()

    conn = SonicV2Connector()
    # popualate the db ,with mock data
    db_names = list(dedicated_dbs.keys())
    try:
        populate_mock(conn, db_names, dedicated_dbs)
    except Exception as e:
        assert False, "Mock initialization failed: " + str(e)
    conn_pool = ConnectionPool()
    dedicated_dbs['APPL_DB'] = os.path.join(dump_input, "dash/appl_db.json")
    dedicated_dbs['ASIC_DB'] = os.path.join(dump_input, "dash/asic_db.json")
    redisMock.load_file(dedicated_dbs['APPL_DB'])
    conn_pool.fill(DEFAULT_NAMESPACE, conn_pool.initialize_connector(DEFAULT_NAMESPACE), list(dedicated_dbs.keys()))
    conn_pool.fill(DEFAULT_NAMESPACE, redisMock, None, dash_object=True)
    populate_mock(conn_pool.cache[DEFAULT_NAMESPACE][CONN], list(dedicated_dbs.keys()), dedicated_dbs)
    match_engine = MatchEngine(conn_pool)
    yield match_engine
    print("TEARDOWN")


@pytest.mark.usefixtures("match_engine")
class TestMatchEngineDash:

    def test_acl_out(self, match_engine):
        req = MatchRequest(db="APPL_DB", table="DASH_ACL_OUT_TABLE", key_pattern="*", pb=Dash_Acl_Out())
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 1
        assert "DASH_ACL_OUT_TABLE:ENI0:1" in ret['keys']
        runner = CliRunner()
        result = runner.invoke(dump.state, ["dash_acl_out", "all"], obj=match_engine)
        assert result.exit_code == 0, (
            "exit code: {}, Exception: {}, Traceback: {}".format
            (result.exit_code, result.exception, result.exc_info)
            )
        expected = {"ENI0:1":
                    {
                        "APPL_DB":
                            {"keys":
                                [{"DASH_ACL_OUT_TABLE:ENI0:1":
                                    {"v4_acl_group_id": "group1"}}],
                                "tables_not_found": []
                             }
                    }
                    }
        ddiff = compare_json_output(expected, result.output)
        assert not ddiff, ddiff

    def test_acl_in(self, match_engine):
        req = MatchRequest(db="APPL_DB", table="DASH_ACL_IN_TABLE", key_pattern="*", pb=Dash_Acl_In())
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 1
        assert "DASH_ACL_IN_TABLE:F4939FEFC47E:1" in ret['keys']
        runner = CliRunner()
        result = runner.invoke(dump.state, ["dash_acl_in", "all"], obj=match_engine)
        assert result.exit_code == 0, (
            "exit code: {}, Exception: {}, Traceback: {}".format
            (result.exit_code, result.exception, result.exc_info)
            )
        expected = {"F4939FEFC47E:1":
                    {
                        "APPL_DB":
                            {"keys":
                                [{"DASH_ACL_IN_TABLE:F4939FEFC47E:1":
                                    {"v4_acl_group_id": "default_acl_group"}}],
                                "tables_not_found": []
                             }
                    }
                    }
        ddiff = compare_json_output(expected, result.output)
        assert not ddiff, ddiff

    def test_acl_group(self, match_engine):
        req = MatchRequest(db="APPL_DB", table="DASH_ACL_GROUP_TABLE", key_pattern="*", pb=Dash_Acl_Group())
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 1
        assert "DASH_ACL_GROUP_TABLE:group1" in ret['keys']
        runner = CliRunner()
        result = runner.invoke(dump.state, ["dash_acl_group", "all"], obj=match_engine)
        assert result.exit_code == 0, (
            "exit code: {}, Exception: {}, Traceback: {}".format
            (result.exit_code, result.exception, result.exc_info)
            )
        expected = {"group1":
                    {
                        "APPL_DB":
                            {"keys":
                                [{"DASH_ACL_GROUP_TABLE:group1":
                                 {"ip_version": "IP_VERSION_IPV4",
                                  "guid": "eaba0709-2664-43d1-8832-39aaa5613f21"
                                  }}],
                                "tables_not_found": []
                             }
                    }
                    }
        ddiff = compare_json_output(expected, result.output)
        assert not ddiff, ddiff

    def test_acl_rule(self, match_engine):
        req = MatchRequest(db="APPL_DB", table="DASH_ACL_RULE_TABLE", key_pattern="*", pb=Dash_Acl_Rule())
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 1
        assert "DASH_ACL_RULE_TABLE:group1:rule1" in ret['keys']
        runner = CliRunner()
        result = runner.invoke(dump.state, ["dash_acl_rule", "all"], obj=match_engine)
        assert result.exit_code == 0, (
            "exit code: {}, Exception: {}, Traceback: {}".format
            (result.exit_code, result.exception, result.exc_info)
            )
        expected = {"group1:rule1":
                    {
                        "APPL_DB":
                            {
                                "keys":
                                [
                                    {
                                        "DASH_ACL_RULE_TABLE:group1:rule1":
                                        {
                                            "action": "ACTION_PERMIT",
                                            "terminating": True,
                                            "src_addr": ["0.0.0.0/0"],
                                            "dst_addr": ["0.0.0.0/0"],
                                            "src_port": [{"value": 80}],
                                            "dst_port": [{"value": 5355}],
                                        }
                                    }
                                ],
                                "tables_not_found": []
                            }
                    }
                    }
        ddiff = compare_json_output(expected, result.output)
        assert not ddiff, ddiff

    def test_appliance(self, match_engine):
        req = MatchRequest(db="APPL_DB", table="DASH_APPLIANCE_TABLE", key_pattern="*", pb=Dash_Appliance())
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 1
        assert "DASH_APPLIANCE_TABLE:123" in ret['keys']
        runner = CliRunner()
        result = runner.invoke(dump.state, ["dash_appliance", "all"], obj=match_engine)
        assert result.exit_code == 0, (
            "exit code: {}, Exception: {}, Traceback: {}".format
            (result.exit_code, result.exception, result.exc_info)
            )
        expected = {"123":
                    {
                        "APPL_DB":
                        {
                            "keys":
                            [
                                {
                                    "DASH_APPLIANCE_TABLE:123":
                                    {
                                        "sip": "10.1.0.32",
                                        "vm_vni": 101,
                                    }
                                }
                            ],
                            "tables_not_found": []
                        }
                    }
                    }
        ddiff = compare_json_output(expected, result.output)
        assert not ddiff, ddiff

    def test_eni(self, match_engine):
        req = MatchRequest(db="APPL_DB", table="DASH_ENI_TABLE", key_pattern="*", pb=Dash_Eni())
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 2
        assert "DASH_ENI_TABLE:eni0" in ret['keys']
        assert "DASH_ENI_TABLE:F4939FEFC47E" in ret['keys']
        runner = CliRunner()
        result = runner.invoke(dump.state, ["dash_eni", "all"], obj=match_engine)
        assert result.exit_code == 0, (
            "exit code: {}, Exception: {}, Traceback: {}".format
            (result.exit_code, result.exception, result.exc_info)
            )
        expected = {"eni0":
                    {
                        "APPL_DB":
                            {"keys":
                                [
                                    {"DASH_ENI_TABLE:eni0":
                                        {"eni_id": "386e12c6-e0ab-3b88-a87e-48b360d7b6ac",
                                         "mac_address": "00:00:00:00:aa:00",
                                         "qos": "qos100",
                                         "underlay_ip": "10.0.1.2",
                                         "admin_state": "STATE_ENABLED",
                                         "vnet": "Vnet5",
                                         }}],
                                "tables_not_found": []
                             },
                        "ASIC_DB":
                            {"keys":
                                [],
                                "tables_not_found": ["ASIC_STATE:SAI_OBJECT_TYPE_ENI"],
                             }
                    },
                    "F4939FEFC47E":
                    {
                        "APPL_DB":
                            {"keys":
                                [
                                    {"DASH_ENI_TABLE:F4939FEFC47E":
                                        {"eni_id": "497f23d7-f0ac-4c99-a98f-59b470e8c7bd",
                                         "mac_address": "f4:93:9f:ef:c4:7e",
                                         "qos": "qos100",
                                         "underlay_ip": "10.0.1.2",
                                         "admin_state": "STATE_ENABLED",
                                         "vnet": "Vnet1",
                                         }}],
                                "tables_not_found": []
                             },
                        "ASIC_DB":
                            {"keys":
                                [
                                    {"ASIC_STATE:SAI_OBJECT_TYPE_ENI:oid:0x73000000000023":
                                        {"SAI_ENI_ATTR_ADMIN_STATE": "true",
                                         "SAI_ENI_ATTR_VM_UNDERLAY_DIP": "10.0.1.2",
                                         "SAI_ENI_ATTR_VM_VNI": "101",
                                         "SAI_ENI_ATTR_VNET_ID": "oid:0x7a000000000021",
                                         }}],
                                "tables_not_found": [],
                                "vidtorid":
                                {
                                    "oid:0x73000000000023": "Real ID Not Found"
                                }
                             }
                    }
                    }
        ddiff = compare_json_output(expected, result.output)
        assert not ddiff, ddiff

    def test_qos(self, match_engine):
        req = MatchRequest(db="APPL_DB", table="DASH_QOS_TABLE", key_pattern="*", pb=Dash_Qos())
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 1
        assert "DASH_QOS_TABLE:qos100" in ret['keys']
        runner = CliRunner()
        result = runner.invoke(dump.state, ["dash_qos", "all"], obj=match_engine)
        assert result.exit_code == 0, (
            "exit code: {}, Exception: {}, Traceback: {}".format
            (result.exit_code, result.exception, result.exc_info)
            )
        expected = {"qos100":
                    {
                        "APPL_DB":
                            {"keys":
                                [
                                    {"DASH_QOS_TABLE:qos100":
                                        {"qos_id": "100",
                                         "bw": 10000,
                                         "cps": 1000,
                                         "flows": 10,
                                         }}],
                                "tables_not_found": []
                             }
                    }
                    }
        ddiff = compare_json_output(expected, result.output)
        assert not ddiff, ddiff

    def test_route(self, match_engine):
        req = MatchRequest(db="APPL_DB", table="DASH_ROUTE_TABLE", key_pattern="*", pb=Dash_Route())
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 2
        assert "DASH_ROUTE_TABLE:eni0:12.1.1.0/24" in ret['keys']
        assert "DASH_ROUTE_TABLE:F4939FEFC47E:20.2.2.0/24" in ret['keys']
        runner = CliRunner()
        result = runner.invoke(dump.state, ["dash_route", "all"], obj=match_engine)
        assert result.exit_code == 0, (
            "exit code: {}, Exception: {}, Traceback: {}".format
            (result.exit_code, result.exception, result.exc_info)
            )
        expected = {"eni0:12.1.1.0/24":
                    {
                        "APPL_DB":
                            {"keys":
                                [
                                    {"DASH_ROUTE_TABLE:eni0:12.1.1.0/24":
                                        {"action_type": "ROUTING_TYPE_VNET",
                                         "vnet": "Vnet1",
                                         }}],
                                "tables_not_found": []
                             },
                        "ASIC_DB":
                            {"keys":
                                [],
                                "tables_not_found": ["ASIC_STATE:SAI_OBJECT_TYPE_OUTBOUND_ROUTING_ENTRY"],
                             }
                    },
                    "F4939FEFC47E:20.2.2.0/24":
                    {
                        "APPL_DB":
                            {"keys":
                                [
                                    {"DASH_ROUTE_TABLE:F4939FEFC47E:20.2.2.0/24":
                                        {"action_type": "ROUTING_TYPE_VNET",
                                         "vnet": "Vnet2",
                                         }}],
                                "tables_not_found": []
                             },
                        "ASIC_DB":
                            {"keys":
                                [
                                    {"ASIC_STATE:SAI_OBJECT_TYPE_OUTBOUND_ROUTING_ENTRY:"
                                     "{\"destination\":\"20.2.2.0/24\",\"eni_id\":\"oid:0x73000000000023\","
                                     "\"switch_id\":\"oid:0x21000000000000\"}": {
                                        "SAI_OUTBOUND_ROUTING_ENTRY_ATTR_ACTION":
                                        "SAI_OUTBOUND_ROUTING_ENTRY_ACTION_ROUTE_VNET",
                                        "SAI_OUTBOUND_ROUTING_ENTRY_ATTR_DST_VNET_ID": "oid:0x7a000000000022"
                                     }}
                                ],
                                "tables_not_found": [],
                             }
                    }
                    }
        ddiff = compare_json_output(expected, result.output)
        assert not ddiff, ddiff

    def test_vnet_mapping(self, match_engine):
        req = MatchRequest(db="APPL_DB", table="DASH_VNET_MAPPING_TABLE", key_pattern="*", pb=Dash_Vnet_mapping())
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 1
        assert "DASH_VNET_MAPPING_TABLE:Vnet1:12.1.1.1" in ret['keys']
        runner = CliRunner()
        result = runner.invoke(dump.state, ["dash_vnet_mapping", "all"], obj=match_engine)
        assert result.exit_code == 0, (
            "exit code: {}, Exception: {}, Traceback: {}".format
            (result.exit_code, result.exception, result.exc_info)
            )
        expected = {"Vnet1:12.1.1.1":
                    {
                        "APPL_DB":
                            {"keys":
                                [
                                    {"DASH_VNET_MAPPING_TABLE:Vnet1:12.1.1.1":
                                        {"action_type": "ROUTING_TYPE_VNET_ENCAP",
                                         "underlay_ip": "10.0.2.2",
                                         "mac_address": "00:00:00:00:aa:01",
                                         "use_dst_vni": True,
                                         }}],
                                "tables_not_found": []
                             }
                    }
                    }
        ddiff = compare_json_output(expected, result.output)
        assert not ddiff, ddiff

    def test_acl_prefix_tag(self, match_engine):
        req = MatchRequest(db="APPL_DB", table="DASH_PREFIX_TAG_TABLE", key_pattern="*", pb=Dash_Prefix_Tag())
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 1
        assert "DASH_PREFIX_TAG_TABLE:AclTagScale1798" in ret['keys']
        runner = CliRunner()
        result = runner.invoke(dump.state, ["dash_prefix_tag", "all"], obj=match_engine)
        assert result.exit_code == 0, (
            "exit code: {}, Exception: {}, Traceback: {}".format
            (result.exit_code, result.exception, result.exc_info)
            )
        expected = {"AclTagScale1798":
                    {
                        "APPL_DB":
                            {"keys":
                                [
                                    {"DASH_PREFIX_TAG_TABLE:AclTagScale1798":
                                        {"ip_version": "IP_VERSION_IPV4",
                                         "prefix_list": [
                                             "8.0.0.107/32"
                                         ]
                                         }}],
                                "tables_not_found": []
                             }
                    }
                    }
        ddiff = compare_json_output(expected, result.output)
        assert not ddiff, ddiff

    def test_vnet(self, match_engine):
        req = MatchRequest(db="APPL_DB", table="DASH_VNET_TABLE", key_pattern="*", pb=Dash_Vnet())
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 2
        assert "DASH_VNET_TABLE:Vnet1" in ret['keys']
        runner = CliRunner()
        result = runner.invoke(dump.state, ["dash_vnet", "all"], obj=match_engine)
        assert result.exit_code == 0, (
            "exit code: {}, Exception: {}, Traceback: {}".format
            (result.exit_code, result.exception, result.exc_info)
            )
        expected = {"Vnet1":
                    {
                        "APPL_DB":
                            {"keys":
                                [
                                    {"DASH_VNET_TABLE:Vnet1":
                                        {"vni": 1000,
                                         "guid": "559c6ce8-26ab-4193-b946-ccc6e8f930b2",
                                         }}],
                                "tables_not_found": []
                             },
                        "ASIC_DB":
                            {"keys":
                                [
                                    {"ASIC_STATE:SAI_OBJECT_TYPE_VNET:oid:0x7a000000000021":
                                        {"SAI_VNET_ATTR_VNI": "1000",
                                         }}],
                                "tables_not_found": [],
                                "vidtorid": {
                                    "oid:0x7a000000000021": "Real ID Not Found"
                                }
                             }
                    },
                    "Vnet2":
                    {
                        "APPL_DB":
                            {"keys":
                                [
                                    {"DASH_VNET_TABLE:Vnet2":
                                        {"vni": 2000,
                                         "guid": "659c6ce8-26ab-4193-b946-ccc6e8f930b2",
                                         }}],
                                "tables_not_found": []
                             },
                        "ASIC_DB":
                            {"keys":
                                [],
                                "tables_not_found": ["ASIC_STATE:SAI_OBJECT_TYPE_VNET"],
                             }
                    }
                    }
        ddiff = compare_json_output(expected, result.output)
        assert not ddiff, ddiff

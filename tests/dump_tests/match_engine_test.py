import os
import sys
import unittest
import pytest
from dump.match_infra import MatchEngine, EXCEP_DICT, MatchRequest, MatchRequestOptimizer, ConnectionPool, CONN
from utilities_common.constants import DEFAULT_NAMESPACE
from dump.helper import populate_mock
from unittest.mock import MagicMock
from deepdiff import DeepDiff
from importlib import reload

from swsscommon.swsscommon import SonicV2Connector
from ..mock_tables import dbconnector

test_path = os.path.join(os.path.dirname(__file__), "../")
dump_test_input = os.path.join(test_path, "dump_input")

@pytest.fixture(scope="module", autouse=True)
def match_engine():
    print("SETUP")
    os.environ["VERBOSE"] = "1"

    from ..mock_tables import mock_multi_asic
    reload(mock_multi_asic)
    from ..mock_tables import dbconnector
    dbconnector.load_namespace_config()

    dump_input = os.path.join(os.path.dirname(__file__), "../dump_input/")
    dedicated_dbs = {}

    conn = SonicV2Connector()
    # popualate the db ,with mock data
    db_names = list(dedicated_dbs.keys())
    try:
        populate_mock(conn, db_names, dedicated_dbs)
    except Exception as e:
        assert False, "Mock initialization failed: " + str(e)

    conn_pool = ConnectionPool()
    dedicated_dbs['CONFIG_DB'] = os.path.join(dump_input, "dump/default/config_db.json")
    dedicated_dbs['APPL_DB'] = os.path.join(dump_input, "dump/default/appl_db.json")
    dedicated_dbs['STATE_DB'] = os.path.join(dump_input, "dump/default/state_db.json")
    dedicated_dbs['ASIC_DB'] =  os.path.join(dump_input, "dump/default/asic_db.json")
    conn_pool.fill(DEFAULT_NAMESPACE, conn_pool.initialize_connector(DEFAULT_NAMESPACE), list(dedicated_dbs.keys()))
    populate_mock(conn_pool.cache[DEFAULT_NAMESPACE][CONN], list(dedicated_dbs.keys()), dedicated_dbs)

    dedicated_dbs['CONFIG_DB'] = os.path.join(dump_input, "dump/asic0/config_db.json")
    dedicated_dbs['APPL_DB'] = os.path.join(dump_input, "dump/asic0/appl_db.json")
    dedicated_dbs['STATE_DB'] = os.path.join(dump_input, "dump/asic0/state_db.json")
    dedicated_dbs['ASIC_DB'] =  os.path.join(dump_input, "dump/asic0/asic_db.json")
    conn_pool.fill("asic0", conn_pool.initialize_connector("asic0"), list(dedicated_dbs.keys()))
    populate_mock(conn_pool.cache["asic0"][CONN], list(dedicated_dbs.keys()), dedicated_dbs)

    dedicated_dbs['CONFIG_DB'] = os.path.join(dump_input, "dump/asic1/config_db.json")
    dedicated_dbs['APPL_DB'] = os.path.join(dump_input, "dump/asic1/appl_db.json")
    dedicated_dbs['STATE_DB'] = os.path.join(dump_input, "dump/asic1/state_db.json")
    dedicated_dbs['ASIC_DB'] =  os.path.join(dump_input, "dump/asic1/asic_db.json")
    conn_pool.fill("asic1", conn_pool.initialize_connector("asic1"), list(dedicated_dbs.keys()))
    populate_mock(conn_pool.cache["asic1"][CONN], list(dedicated_dbs.keys()), dedicated_dbs)

    match_engine = MatchEngine(conn_pool)
    yield match_engine
    print("TEARDOWN")

class TestMatchRequestValidation:

    def assertRaisesWithMessage(self, msg, func, *args, **kwargs):
        try:
            func(*args, **kwargs)
            assert False, "Expected an exception with msg: " + msg
        except Exception as inst:
            print(inst)
            assert msg in str(inst)

    def test_bad_request(self, match_engine):
        req = []
        ret = match_engine.fetch(req)
        assert ret["error"] == EXCEP_DICT["INV_REQ"]

    def test_no_source(self):
        self.assertRaisesWithMessage(EXCEP_DICT["NO_SRC"], MatchRequest)

    def test_vague_source(self):
        self.assertRaisesWithMessage(EXCEP_DICT["SRC_VAGUE"], MatchRequest, db="CONFIG_DB", file="/etc/sonic/copp_cfg.json")

    def test_no_file(self):
        self.assertRaisesWithMessage(EXCEP_DICT["FILE_R_EXEP"], MatchRequest, file=os.path.join(test_path, "random_db.json"))

    def test_invalid_db(self):
        self.assertRaisesWithMessage(EXCEP_DICT["INV_DB"], MatchRequest, db="CONFIGURATION_DB")

    def test_invalid_namespace(self):
        self.assertRaisesWithMessage(EXCEP_DICT["INV_NS"], MatchRequest, db="APPL_DB", table="PORT_TABLE",
                                     field="lanes", value="202", ns="asic4")

    def test_bad_key_pattern(self, match_engine):
        req = MatchRequest(db="CONFIG_DB", table="PORT", key_pattern="")
        ret = match_engine.fetch(req)
        assert ret["error"] == EXCEP_DICT["NO_KEY"]

    def test_no_value(self):
        self.assertRaisesWithMessage(EXCEP_DICT["NO_VALUE"], MatchRequest, db="APPL_DB", table="COPP_TABLE", key_pattern="*", field="trap_ids", value="")

    def test_no_table(self):
        self.assertRaisesWithMessage(EXCEP_DICT["NO_TABLE"], MatchRequest, db="APPL_DB", table="", key_pattern="*", field="trap_ids", value="bgpv6")

    def test_just_keys_return_fields_compat(self):
        self.assertRaisesWithMessage(EXCEP_DICT["JUST_KEYS_COMPAT"], MatchRequest, db="APPL_DB", return_fields=["trap_group"], table="COPP_TABLE",
                                     key_pattern="*", field="trap_ids", value="", just_keys=False)

    def test_invalid_combination(self, match_engine):
        req = MatchRequest(db="CONFIG_DB", table="COPP_TRAP", key_pattern="*", field="trap_ids", value="sample_packet")
        ret = match_engine.fetch(req)
        assert ret["error"] == EXCEP_DICT["NO_MATCHES"]

    def test_return_fields_bad_format(self):
        self.assertRaisesWithMessage(EXCEP_DICT["BAD_FORMAT_RE_FIELDS"], MatchRequest, db="STATE_DB", table="REBOOT_CAUSE", key_pattern="*", return_fields="cause")

    def test_valid_match_request(self):
        try:
            req = MatchRequest(db="APPL_DB", table="PORT_TABLE", field="lanes", value="202")
        except Exception as e:
            assert False, "Exception Raised for a Valid MatchRequest" + str(e)

@pytest.mark.usefixtures("match_engine")
class TestMatchEngine:

    def test_key_pattern_wildcard(self, match_engine):
        req = MatchRequest(db="CONFIG_DB", table="SFLOW_COLLECTOR", key_pattern="*")
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 2
        assert "SFLOW_COLLECTOR|ser5" in ret['keys']
        assert "SFLOW_COLLECTOR|prod" in ret['keys']

    def test_key_pattern_complex(self, match_engine):
        req = MatchRequest(db="CONFIG_DB", table="ACL_RULE", key_pattern="EVERFLOW*")
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 2
        assert "ACL_RULE|EVERFLOW|RULE_6" in ret['keys']
        assert "ACL_RULE|EVERFLOW|RULE_08" in ret['keys']

    def test_field_value_match(self, match_engine):
        req = MatchRequest(db="CONFIG_DB", table="ACL_TABLE", field="policy_desc", value="SSH_ONLY")
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 1
        assert "ACL_TABLE|SSH_ONLY" in ret['keys']

    def test_field_value_match_list_type(self, match_engine):
        req = MatchRequest(db="APPL_DB", table="PORT_TABLE", field="lanes", value="202")
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 1
        assert "PORT_TABLE:Ethernet200" in ret['keys']

    def test_for_no_match(self, match_engine):
        req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_SWITCH", field="SAI_SWITCH_ATTR_SRC_MAC_ADDRESS", value="DE:AD:EE:EE:EE")
        ret = match_engine.fetch(req)
        assert ret["error"] == EXCEP_DICT["NO_ENTRIES"]
        assert len(ret["keys"]) == 0

    def test_for_no_key_match(self, match_engine):
        req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_SWITCH", key_pattern="oid:0x22*")
        ret = match_engine.fetch(req)
        assert ret["error"] == EXCEP_DICT["NO_MATCHES"]

    def test_field_value_no_match(self, match_engine):
        req = MatchRequest(db="STATE_DB", table="FAN_INFO", key_pattern="*", field="led_status", value="yellow")
        ret = match_engine.fetch(req)
        assert ret["error"] == EXCEP_DICT["NO_ENTRIES"]
        assert len(ret["keys"]) == 0

    def test_return_keys(self, match_engine):
        req = MatchRequest(db="STATE_DB", table="REBOOT_CAUSE", return_fields=["cause"])
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 2
        assert "warm-reboot" == ret["return_values"]["REBOOT_CAUSE|2020_10_09_04_53_58"]["cause"]
        assert "reboot" == ret["return_values"]["REBOOT_CAUSE|2020_10_09_02_33_06"]["cause"]

    def test_return_fields_with_key_filtering(self, match_engine):
        req = MatchRequest(db="STATE_DB", table="REBOOT_CAUSE", key_pattern="2020_10_09_02*", return_fields=["cause"])
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 1
        assert "reboot" == ret["return_values"]["REBOOT_CAUSE|2020_10_09_02_33_06"]["cause"]

    def test_return_fields_with_field_value_filtering(self, match_engine):
        req = MatchRequest(db="STATE_DB", table="CHASSIS_MODULE_TABLE", field="oper_status", value="Offline", return_fields=["slot"])
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 1
        assert "18" == ret["return_values"]["CHASSIS_MODULE_TABLE|FABRIC-CARD1"]["slot"]

    def test_return_fields_with_all_filtering(self, match_engine):
        req = MatchRequest(db="STATE_DB", table="VXLAN_TUNNEL_TABLE", key_pattern="EVPN_25.25.25.2*", field="operstatus", value="down", return_fields=["src_ip"])
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 3
        assert "1.1.1.1" == ret["return_values"]["VXLAN_TUNNEL_TABLE|EVPN_25.25.25.25"]["src_ip"]
        assert "1.1.1.1" == ret["return_values"]["VXLAN_TUNNEL_TABLE|EVPN_25.25.25.26"]["src_ip"]
        assert "1.1.1.1" == ret["return_values"]["VXLAN_TUNNEL_TABLE|EVPN_25.25.25.27"]["src_ip"]

    def test_just_keys_false(self, match_engine):
        req = MatchRequest(db="CONFIG_DB", table="SFLOW", key_pattern="global", just_keys=False)
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 1
        recv_dict = ret["keys"][0]
        assert isinstance(recv_dict, dict)
        exp_dict = {"SFLOW|global": {"admin_state": "up", "polling_interval": "0"}}
        ddiff = DeepDiff(exp_dict, recv_dict)
        assert not ddiff, ddiff

    def test_file_source(self, match_engine):
        file = os.path.join(dump_test_input, "copp_cfg.json")
        req = MatchRequest(file=file, table="COPP_TRAP", field="trap_ids", value="arp_req")
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 1
        assert "COPP_TRAP|arp" in ret["keys"]

    def test_file_source_with_key_ptrn(self, match_engine):
        file = os.path.join(dump_test_input, "copp_cfg.json")
        req = MatchRequest(file=file, table="COPP_GROUP", key_pattern="queue4*", field="red_action", value="drop")
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 1
        assert "COPP_GROUP|queue4_group2" in ret["keys"]

    def test_file_source_with_not_only_return_keys(self, match_engine):
        file = os.path.join(dump_test_input, "copp_cfg.json")
        req = MatchRequest(file=file, table="COPP_GROUP", key_pattern="queue4*", field="red_action", value="drop", just_keys=False)
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 1
        recv_dict = ret["keys"][0]
        exp_dict = {"COPP_GROUP|queue4_group2": {"trap_action": "copy", "trap_priority": "4", "queue": "4", "meter_type": "packets", "mode": "sr_tcm", "cir": "600", "cbs": "600", "red_action": "drop"}}
        ddiff = DeepDiff(exp_dict, recv_dict)
        assert not ddiff, ddiff

    def test_match_entire_list(self, match_engine):
        req = MatchRequest(db="CONFIG_DB", table="PORT", key_pattern="*", field="lanes", value="61,62,63,64", match_entire_list=True, just_keys=True)
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 1
        assert "PORT|Ethernet60" in ret["keys"]

@pytest.mark.usefixtures("match_engine")
class TestNonDefaultNameSpace:

    def test_namespace_asic0(self, match_engine):
        req = MatchRequest(db="CONFIG_DB", table="PORT", key_pattern="*", field="asic_port_name", value="Eth0-ASIC0", ns="asic0")
        match_engine = MatchEngine()
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 1
        assert "PORT|Ethernet0" in ret["keys"]

    def test_namespace_asic1(self, match_engine):
        req = MatchRequest(db="CONFIG_DB", table="PORT", key_pattern="Ethernet-BP256", ns="asic1")
        match_engine = MatchEngine()
        ret = match_engine.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 1
        assert "PORT|Ethernet-BP256" in ret["keys"]

class TestMatchEngineOptimizer:

    def test_caching(self):
        rv = {"COPP_GROUP|queue4_group2": {"trap_action": "copy", "trap_priority": "4", "queue": "4", "meter_type": "packets", "mode": "sr_tcm", "cir": "600", "cbs": "600", "red_action": "drop"}}
        template = {"error": "", "keys": [rv], "return_values": {}}
        m_engine = MatchEngine()
        m_engine.fetch = MagicMock(return_value=template)
        m_engine_optim = MatchRequestOptimizer(m_engine)
        req = MatchRequest(db="CONFIG_DB", table="COPP_GROUP", key_pattern="queue4*", field="red_action", value="drop")
        ret = m_engine_optim.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 1
        assert "COPP_GROUP|queue4_group2" in ret["keys"]

        req = MatchRequest(db="CONFIG_DB", table="COPP_GROUP", key_pattern="queue4_group2")
        ret = m_engine_optim.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 1
        assert "COPP_GROUP|queue4_group2" in ret["keys"]

        assert m_engine.fetch.call_count == 1

    def test_missing_field(self):
        rv = {"COPP_GROUP|queue4_group2": {"trap_action": "copy", "trap_priority": "4", "queue": "4", "meter_type": "packets", "mode": "sr_tcm", "cir": "600", "cbs": "600", "red_action": "drop"}}
        template = {"error": "", "keys": [rv], "return_values": {}}
        m_engine = MatchEngine()
        m_engine.fetch = MagicMock(return_value=template)
        m_engine_optim = MatchRequestOptimizer(m_engine)
        req = MatchRequest(db="CONFIG_DB", table="COPP_GROUP", key_pattern="queue4*", field="red_action", value="drop", return_fields=["whatever"])
        ret = m_engine_optim.fetch(req)
        assert ret["error"] == ""
        assert len(ret["keys"]) == 1
        assert "COPP_GROUP|queue4_group2" in ret["keys"]
        # missing filed should not cause an excpetion in the optimizer
        assert "whatever" in ret["return_values"]["COPP_GROUP|queue4_group2"]
        assert not  ret["return_values"]["COPP_GROUP|queue4_group2"]["whatever"]

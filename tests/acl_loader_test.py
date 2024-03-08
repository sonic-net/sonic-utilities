import importlib
import sys
import os
import pytest
from unittest import mock

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)

from acl_loader import *
from acl_loader.main import *

class TestAclLoader(object):
    @pytest.fixture(scope="class")
    def acl_loader(self):
        yield AclLoader()

    def test_acl_empty(self):
        yang_acl = AclLoader.parse_acl_json(os.path.join(test_path, 'acl_input/empty_acl.json'))
        assert len(yang_acl.acl.acl_sets.acl_set) == 0

    def test_valid(self):
        yang_acl = AclLoader.parse_acl_json(os.path.join(test_path, 'acl_input/acl1.json'))
        assert len(yang_acl.acl.acl_sets.acl_set) == 9

    def test_invalid(self):
        with pytest.raises(AclLoaderException):
            yang_acl = AclLoader.parse_acl_json(os.path.join(test_path, 'acl_input/acl2.json'))

    def test_validate_mirror_action(self, acl_loader):
        ingress_mirror_rule_props = {
            "MIRROR_INGRESS_ACTION": "everflow0"
        }

        egress_mirror_rule_props = {
            "mirror_egress_action": "everflow0"
        }

        # switch capability taken from mock_tables/state_db.json ACL_STAGE_CAPABILITY_TABLE table
        assert acl_loader.validate_actions("EVERFLOW", ingress_mirror_rule_props)
        assert not acl_loader.validate_actions("EVERFLOW", egress_mirror_rule_props)

        assert not acl_loader.validate_actions("EVERFLOW_EGRESS", ingress_mirror_rule_props)
        assert acl_loader.validate_actions("EVERFLOW_EGRESS", egress_mirror_rule_props)

        forward_packet_action = {
            "PACKET_ACTION": "FORWARD"
        }

        drop_packet_action = {
            "PACKET_ACTION": "DROP"
        }

        # switch capability taken from mock_tables/state_db.json ACL_STAGE_CAPABILITY_TABLE table
        assert acl_loader.validate_actions("DATAACL", forward_packet_action)
        assert not acl_loader.validate_actions("DATAACL", drop_packet_action)

    def test_vlan_id_translation(self, acl_loader):
        acl_loader.rules_info = {}
        acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/acl1.json'))
        assert acl_loader.rules_info[("DATAACL", "RULE_2")]
        assert acl_loader.rules_info[("DATAACL", "RULE_2")] == {
            "VLAN_ID": 369,
            "ETHER_TYPE": "2048",
            "IP_PROTOCOL": 6,
            "SRC_IP": "20.0.0.2/32",
            "DST_IP": "30.0.0.3/32",
            "PACKET_ACTION": "FORWARD",
            "PRIORITY": "9998"
        }

    def test_vlan_id_lower_bound(self, acl_loader):
        with pytest.raises(ValueError):
            acl_loader.rules_info = {}
            acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/illegal_vlan_0.json'))

    def test_vlan_id_upper_bound(self, acl_loader):
        with pytest.raises(ValueError):
            acl_loader.rules_info = {}
            acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/illegal_vlan_9000.json'))

    def test_vlan_id_not_a_number(self, acl_loader):
        with pytest.raises(ValueError):
            acl_loader.rules_info = {}
            acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/illegal_vlan_nan.json'))

    def test_ethertype_translation(self, acl_loader):
        acl_loader.rules_info = {}
        acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/acl1.json'))
        assert acl_loader.rules_info[("DATAACL", "RULE_3")]
        assert acl_loader.rules_info[("DATAACL", "RULE_3")] == {
            "VLAN_ID": 369,
            "ETHER_TYPE": 35020,
            "PACKET_ACTION": "FORWARD",
            "PRIORITY": "9997"
        }

    def test_v4_rule_inv4v6_table(self, acl_loader):
        acl_loader.rules_info = {}
        acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/acl1.json'))
        assert acl_loader.rules_info[("DATAACLV4V6", "RULE_1")]
        assert acl_loader.rules_info[("DATAACLV4V6", "RULE_1")] == {
            "VLAN_ID": 369,
            "ETHER_TYPE": 2048,
            "IP_PROTOCOL": 6,
            "SRC_IP": "20.0.0.2/32",
            "DST_IP": "30.0.0.3/32",
            "PACKET_ACTION": "FORWARD",
            "PRIORITY": "9999"
        }

    def test_v6_rule_inv4v6_table(self, acl_loader):
        acl_loader.rules_info = {}
        acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/acl1.json'))
        assert acl_loader.rules_info[("DATAACLV4V6", "RULE_2")]
        assert acl_loader.rules_info[("DATAACLV4V6", "RULE_2")] == {
            "ETHER_TYPE": 34525,
            "IP_PROTOCOL": 58,
            "SRC_IPV6": "::1/128",
            "DST_IPV6": "::1/128",
            "PACKET_ACTION": "FORWARD",
            "PRIORITY": "9998",
            'ICMPV6_CODE': 0,
            'ICMPV6_TYPE': 1
        }

    def test_rule_without_ethertype_inv4v6(self, acl_loader):
        acl_loader.rules_info = {}
        acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/illegal_v4v6_rule_no_ethertype.json'))
        assert not acl_loader.rules_info.get(("DATAACLV4V6", "RULE_1"))
        assert acl_loader.rules_info[("DATAACLV4V6", "RULE_2")]
        assert not acl_loader.rules_info.get(("DATAACLV4V6", "RULE_3"))

    def test_icmp_translation(self, acl_loader):
        acl_loader.rules_info = {}
        acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/acl1.json'))
        assert acl_loader.rules_info[("DATAACL", "RULE_1")]
        assert acl_loader.rules_info[("DATAACL", "RULE_1")] == {
            "ICMP_TYPE": 3,
            "ICMP_CODE": 0,
            "IP_PROTOCOL": 1,
            "SRC_IP": "20.0.0.2/32",
            "DST_IP": "30.0.0.3/32",
            "ETHER_TYPE": "2048",
            "PACKET_ACTION": "FORWARD",
            "PRIORITY": "9999"
        }

    def test_icmpv6_translation(self, acl_loader):
        acl_loader.rules_info = {}
        acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/acl1.json'))
        assert acl_loader.rules_info[("DATAACL_2", "RULE_1")] == {
            "ICMPV6_TYPE": 1,
            "ICMPV6_CODE": 0,
            "IP_PROTOCOL": 58,
            "SRC_IPV6": "::1/128",
            "DST_IPV6": "::1/128",
            "IP_TYPE": "IPV6ANY",
            "PACKET_ACTION": "FORWARD",
            "PRIORITY": "9999"
        }
        assert acl_loader.rules_info[("DATAACL_2", "RULE_100")] == {
            "ICMPV6_TYPE": 128,
            "IP_PROTOCOL": 58,
            "SRC_IPV6": "::1/128",
            "DST_IPV6": "::1/128",
            "IP_TYPE": "IPV6ANY",
            "PACKET_ACTION": "FORWARD",
            "PRIORITY": "9900"
        }

    def test_icmp_translation_in_custom_acl_table_type(self, acl_loader):
        acl_loader.rules_info = {}
        acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/acl1.json'))
        assert acl_loader.rules_info[("BMC_ACL_NORTHBOUND", "RULE_2")]
        assert acl_loader.rules_info[("BMC_ACL_NORTHBOUND", "RULE_2")] == {
            "ICMP_TYPE": 136,
            "ICMP_CODE": 0,
            "IP_PROTOCOL": 1,
            "PACKET_ACTION": "FORWARD",
            "PRIORITY": "9998"
        }

    def test_icmpv6_translation_in_custom_acl_table_type(self, acl_loader):
        acl_loader.rules_info = {}
        acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/acl1.json'))
        assert acl_loader.rules_info[("BMC_ACL_NORTHBOUND_V6", "RULE_2")]
        assert acl_loader.rules_info[("BMC_ACL_NORTHBOUND_V6", "RULE_2")] == {
            "ICMPV6_TYPE": 136,
            "ICMPV6_CODE": 0,
            "IP_PROTOCOL": 58,
            "PACKET_ACTION": "FORWARD",
            "PRIORITY": "9998"
        }

    def test_ingress_default_deny_rule(self, acl_loader):
        acl_loader.set_mirror_stage("ingress")
        acl_loader.get_session_name = mock.MagicMock(return_value="everflow_session_mock")
        acl_loader.rules_info = {}
        acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/acl1.json'))
        # Verify L3 can add default deny rule correctly
        assert acl_loader.rules_info[('DATAACL', 'DEFAULT_RULE')] == {
            'PRIORITY': '1',
            'PACKET_ACTION': 'DROP',
            'ETHER_TYPE': '2048'
        }
        # Verify L3V6 can add default deny rule correctly
        assert acl_loader.rules_info[('DATAACL_2', 'DEFAULT_RULE')] == {
            'PRIORITY': '1',
            'PACKET_ACTION': 'DROP',
            'IP_TYPE': 'IPV6ANY'
        }
        assert acl_loader.rules_info[('DATAACLV4V6', 'DEFAULT_RULE')] == {
            'PRIORITY': '1',
            'PACKET_ACTION': 'DROP',
            'IP_TYPE': 'IP'
        }

        # Verify acl-loader doesn't add default deny rule to MIRROR
        assert ('EVERFLOW', 'DEFAULT_RULE') not in acl_loader.rules_info
        # Verify acl-loader doesn't add default deny rule to MIRRORV6
        assert ('EVERFLOWV6', 'DEFAULT_RULE') not in acl_loader.rules_info
        # Verify acl-loader doesn't add default deny rule to custom ACL table types
        assert ('BMC_ACL_NORTHBOUND', 'DEFAULT_RULE') not in acl_loader.rules_info
        assert ('BMC_ACL_NORTHBOUND_V6', 'DEFAULT_RULE') not in acl_loader.rules_info

    def test_egress_no_default_deny_rule(self, acl_loader):
        acl_loader.rules_info = {}
        acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/acl_egress.json'))
        print(acl_loader.rules_info)
        assert ('DATAACL_3', 'DEFAULT_RULE') not in acl_loader.rules_info
        assert ('DATAACL_4', 'DEFAULT_RULE') not in acl_loader.rules_info

    def test_icmp_type_lower_bound(self, acl_loader):
        with pytest.raises(ValueError):
            acl_loader.rules_info = {}
            acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/illegal_icmp_type_neg_1.json'))

    def test_icmp_type_upper_bound(self, acl_loader):
        with pytest.raises(ValueError):
            acl_loader.rules_info = {}
            acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/illegal_icmp_type_300.json'))

    def test_icmp_type_not_a_number(self, acl_loader):
        with pytest.raises(ValueError):
            acl_loader.rules_info = {}
            acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/illegal_icmp_type_nan.json'))

    def test_icmp_code_lower_bound(self, acl_loader):
        with pytest.raises(ValueError):
            acl_loader.rules_info = {}
            acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/illegal_icmp_code_neg_1.json'))

    def test_icmp_code_upper_bound(self, acl_loader):
        with pytest.raises(ValueError):
            acl_loader.rules_info = {}
            acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/illegal_icmp_code_300.json'))

    def test_icmp_code_not_a_number(self, acl_loader):
        with pytest.raises(ValueError):
            acl_loader.rules_info = {}
            acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/illegal_icmp_code_nan.json'))

    def test_icmp_fields_with_non_icmp_protocol(self, acl_loader):
        acl_loader.rules_info = {}
        acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/icmp_bad_protocol_number.json'))
        assert not acl_loader.rules_info.get("RULE_1")

    def ttest_icmp_fields_with_non_icmpv6_protocol(self, acl_loader):
        acl_loader.rules_info = {}
        acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/icmpv6_bad_protocol_number.json'))
        assert not acl_loader.rules_info.get("RULE_1")


    def test_tcp_fields_with_non_tcp_protocol(self, acl_loader):
        acl_loader.rules_info = {}
        acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/tcp_bad_protocol_number.json'))
        assert not acl_loader.rules_info.get("RULE_1")

    def test_incremental_update(self, acl_loader):
        acl_loader.rules_info = {}
        acl_loader.tables_db_info['NTP_ACL'] = {
            "stage": "INGRESS",
            "type": "CTRLPLANE"
        }
        acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/incremental_1.json'))
        acl_loader.rules_db_info = acl_loader.rules_info
        assert acl_loader.rules_info[(('NTP_ACL', 'RULE_1'))]["PACKET_ACTION"] == "ACCEPT"
        acl_loader.per_npu_configdb = None
        acl_loader.configdb.mod_entry = mock.MagicMock(return_value=True)
        acl_loader.configdb.set_entry = mock.MagicMock(return_value=True)
        acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/incremental_2.json'))
        acl_loader.incremental_update()
        assert acl_loader.rules_info[(('NTP_ACL', 'RULE_1'))]["PACKET_ACTION"] == "DROP"



class TestMasicAclLoader(object):


    @pytest.fixture(scope="class")
    def acl_loader(self):
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        from .mock_tables import dbconnector
        dbconnector.load_namespace_config()

        with mock.patch("sonic_py_common.multi_asic.get_all_namespaces",
                        mock.MagicMock(return_value={'front_ns': ['asic0', 'asic1'], 'back_ns': '', 'fabric_ns': ''})):
            yield AclLoader()

        # mock single asic to avoid affecting other tests
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)

    def test_check_npu_db(self, acl_loader):
        assert len(acl_loader.per_npu_configdb) == 2
        assert len(acl_loader.per_npu_statedb) == 2

    def test_incremental_update(self, acl_loader):
        acl_loader.rules_info = {}
        acl_loader.tables_db_info['NTP_ACL'] = {
            "stage": "INGRESS",
            "type": "CTRLPLANE"
        }
        acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/incremental_1.json'))
        acl_loader.rules_db_info = acl_loader.rules_info
        assert acl_loader.rules_info[(('NTP_ACL', 'RULE_1'))]["PACKET_ACTION"] == "ACCEPT"
        for configdb in acl_loader.per_npu_configdb.values():
            configdb.mod_entry = mock.MagicMock(return_value=True)
            configdb.set_entry = mock.MagicMock(return_value=True)
        acl_loader.load_rules_from_file(os.path.join(test_path, 'acl_input/incremental_2.json'))
        acl_loader.incremental_update()
        assert acl_loader.rules_info[(('NTP_ACL', 'RULE_1'))]["PACKET_ACTION"] == "DROP"

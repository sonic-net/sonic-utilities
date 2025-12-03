from click.testing import CliRunner
import show.main as show

show_p4_table_output = r"""{
    "P4RT_TABLE:ACL_TABLE_DEFINITION_TABLE:ACL_ACL_PRE_INGRESS_TABLE": {
        "stage": "PRE_INGRESS",
        "match/dst_ipv6": "{\"bitwidth\":128,\"format\":\"IPV6\",\"kind\":\"sai_field\",\"sai_field\":\"SAI_ACL_TABLE_ATTR_FIELD_DST_IPV6\"}",
        "match/in_port": "{\"format\":\"STRING\",\"kind\":\"sai_field\",\"sai_field\":\"SAI_ACL_TABLE_ATTR_FIELD_IN_PORT\"}",
        "match/is_ipv4": "{\"bitwidth\":1,\"format\":\"HEX_STRING\",\"kind\":\"sai_field\",\"sai_field\":\"SAI_ACL_TABLE_ATTR_FIELD_ACL_IP_TYPE/IPV4ANY\"}",
        "action/set_vrf": "[{\"action\":\"SAI_PACKET_ACTION_FORWARD\"},{\"action\":\"SAI_ACL_ENTRY_ATTR_ACTION_SET_VRF\",\"param\":\"vrf_id\"}]"
    },
    "P4RT_TABLE:ACL_TABLE_DEFINITION_TABLE:ACL_ACL_INGRESS_TABLE": {
        "stage": "INGRESS",
        "match/arp_tpa": "{\"bitwidth\":32,\"elements\":[{\"base\":\"SAI_UDF_BASE_L3\",\"bitwidth\":16,\"kind\":\"udf\",\"offset\":24},{\"base\":\"SAI_UDF_BASE_L3\",\"bitwidth\":16,\"kind\":\"udf\",\"offset\":26}],\"format\":\"HEX_STRING\",\"kind\":\"composite\"}",
        "action/mirror": "[{\"action\":\"SAI_PACKET_ACTION_FORWARD\"},{\"action\":\"SAI_ACL_ENTRY_ATTR_ACTION_MIRROR_INGRESS\",\"param\":\"mirror_session_id\"}]",
        "match/is_ipv4": "{\"bitwidth\":1,\"format\":\"HEX_STRING\",\"kind\":\"sai_field\",\"sai_field\":\"SAI_ACL_TABLE_ATTR_FIELD_ACL_IP_TYPE/IPV4ANY\"}",
        "action/trap": "[{\"action\":\"SAI_PACKET_ACTION_TRAP\"},{\"action\":\"QOS_QUEUE\",\"param\":\"qos_queue\"}]"
    },
    "P4RT_TABLE:ACL_ACL_INGRESS_TABLE:{\"match/dst_mac\":\"33:33:00:00:00:02&ff:ff:ff:ff:ff:ff\",\"match/icmpv6_type\":\"0x87&0xff\",\"match/ip_protocol\":\"0x3a&0xff\",\"match/is_ipv6\":\"0x1\",\"priority\":2070}": {
        "action": "trap",
        "param/qos_queue": "0x6",
        "meter/cir": "28000",
        "meter/cburst": "7000",
        "meter/pir": "28000",
        "meter/pburst": "7000",
        "controller_metadata": "my metadata"
    },
    "P4RT_TABLE:ACL_ACL_PRE_INGRESS_TABLE:{\"match/dst_ip\":\"10.53.192.0&255.255.240.0\",\"match/is_ipv4\":\"0x1\",\"priority\":1132}": {
        "action": "set_vrf",
        "param/vrf_id": "p4rt-vrf-80",
        "controller_metadata": "my metadata"
    }
}
"""

show_p4_table_filter_acl_table_output = r"""{
    "P4RT_TABLE:ACL_ACL_INGRESS_TABLE:{\"match/dst_mac\":\"33:33:00:00:00:02&ff:ff:ff:ff:ff:ff\",\"match/icmpv6_type\":\"0x87&0xff\",\"match/ip_protocol\":\"0x3a&0xff\",\"match/is_ipv6\":\"0x1\",\"priority\":2070}": {
        "action": "trap",
        "param/qos_queue": "0x6",
        "meter/cir": "28000",
        "meter/cburst": "7000",
        "meter/pir": "28000",
        "meter/pburst": "7000",
        "controller_metadata": "my metadata"
    },
    "P4RT_TABLE:ACL_ACL_PRE_INGRESS_TABLE:{\"match/dst_ip\":\"10.53.192.0&255.255.240.0\",\"match/is_ipv4\":\"0x1\",\"priority\":1132}": {
        "action": "set_vrf",
        "param/vrf_id": "p4rt-vrf-80",
        "controller_metadata": "my metadata"
    }
}
"""


class TestP4Table(object):

  def test_show_p4_table(self):
      runner = CliRunner()
      result = runner.invoke(show.cli.commands["p4-table"], [])
      print(result.output)
      assert result.exit_code == 0
      assert result.output == show_p4_table_output

  def test_show_p4_table_filter_acl_table(self):
      runner = CliRunner()
      result = runner.invoke(show.cli.commands["p4-table"], ["ACL_ACL"])
      print(result.output)
      assert result.exit_code == 0
      assert result.output == show_p4_table_filter_acl_table_output

import os

from click.testing import CliRunner
from utilities_common.general import load_module_from_source
from importlib import reload

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")

# Load the file under test
lldpshow_path = os.path.join(scripts_path, 'lldpshow')
lldpshow = load_module_from_source('lldpshow', lldpshow_path)

# Expected output for 2 remote MACs on same physical interface
expected_2MACs_Ethernet0_output = \
('Capability codes: (R) Router, (B) Bridge, (O) Other\n'
 'LocalPort    RemoteDevice    RemotePortID       Capability    '
 'RemotePortDescr\n'
 '-----------  --------------  -----------------  ------------  '
 '-----------------\n'
 'Ethernet0    dummy           00:00:00:00:00:01  BR            First MAC\n'
 'Ethernet0    dummy           00:00:00:00:00:02  R             Second MAC\n'
 '--------------------------------------------------\n'
 'Total entries displayed:  2')

expected_lldpctl_xml_output = \
['<?xml version="1.0" encoding="UTF-8"?>\n\
        <lldp label="LLDP neighbors">\n\
        <interface label="Interface" name="Ethernet0" via="LLDP" rid="2" age="7 days, 22:11:33">\n\
            <chassis label="Chassis">\n\
                <id label="ChassisID" type="mac">00:00:00:00:00:01</id>\n\
                <name label="SysName">dummy</name>\n\
                <descr label="SysDescr">NA</descr>\n\
                <mgmt-ip label="MgmtIP">00:00:00:00:00:00</mgmt-ip>\n\
                <capability label="Capability" type="Bridge" enabled="on"/>\n\
                <capability label="Capability" type="Router" enabled="on"/>\n\
                <capability label="Capability" type="Wlan" enabled="off"/>\n\
                <capability label="Capability" type="Station" enabled="off"/>\n\
            </chassis>\n\
            <port label="Port">\n\
                <id label="PortID" type="mac">00:00:00:00:00:01</id>\n\
                <descr label="PortDescr">First MAC</descr>\n\
                <ttl label="TTL">120</ttl>\n\
            </port>\n\
        </interface>\n\
        <interface label="Interface" name="Ethernet0" via="LLDP" rid="4" age="7 days, 22:11:34">\n\
            <chassis label="Chassis">\n\
                <id label="ChassisID" type="mac">00:00:00:00:00:02</id>\n\
                <name label="SysName">dummy</name>\n\
                <descr label="SysDescr">NA</descr>\n\
                <mgmt-ip label="MgmtIP">00:00:00:00:00:00</mgmt-ip>\n\
                <capability label="Capability" type="Router" enabled="on"/>\n\
            </chassis>\n\
            <port label="Port">\n\
            <id label="PortID" type="mac">00:00:00:00:00:02</id>\n\
                <descr label="PortDescr">Second MAC</descr>\n\
                <ttl label="TTL">120</ttl>\n\
            </port>\n\
        </interface>\n\
        </lldp>\n']

class TestLldp(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")

    def test_show_lldp_2_macs_same_phy_interface(self):
        runner = CliRunner()
        # Create lldpshow instance
        lldp = lldpshow.Lldpshow()
        # Mock lldpraw to check new functionality in parse_info()
        lldp.lldpraw = expected_lldpctl_xml_output
        lldp.parse_info(lldp_detail_info=False)
        output_summary = lldp.get_summary_output(lldp_detail_info=False)
        assert output_summary == expected_2MACs_Ethernet0_output

    def test_get_info(self):
        lldp = lldpshow.Lldpshow()
        lldp.lldp_instance = ['']
        lldp.lldpraw = expected_lldpctl_xml_output
        lldp.get_info(lldp_detail_info=True, lldp_port='Ethernet0')
        lldp.parse_info(lldp_detail_info=True)
        output = lldp.get_summary_output(lldp_detail_info=True)
        assert output.strip('\n') == expected_lldpctl_xml_output[0].strip('\n')

    def test_get_info_multi_asic(self):
        from .mock_tables import mock_multi_asic
        from .mock_tables import dbconnector
        reload(mock_multi_asic)
        dbconnector.load_namespace_config()
        lldp = lldpshow.Lldpshow()
        from .mock_tables import mock_single_asic
        reload(mock_single_asic)
        dbconnector.load_namespace_config()
        lldp.lldp_instance = ['']
        lldp.lldpraw = expected_lldpctl_xml_output
        lldp.get_info(lldp_detail_info=True, lldp_port='Ethernet0')
        lldp.parse_info(lldp_detail_info=True)
        output = lldp.get_summary_output(lldp_detail_info=True)
        assert output.strip('\n') == expected_lldpctl_xml_output[0].strip('\n')

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")

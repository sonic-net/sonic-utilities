import sys
import os
from unittest import mock
from unittest.mock import MagicMock, patch

from .mock_tables import dbconnector

import pytest
from click.testing import CliRunner
from utilities_common.db import Db

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)

sys.modules['sonic_platform'] = mock.MagicMock()
import sfputil.main as sfputil

EXIT_FAIL = -1
ERROR_NOT_IMPLEMENTED = 5
ERROR_INVALID_PORT = 6

class TestSfputil(object):
    def test_format_dict_value_to_string(self):
        sorted_key_table = [
            'rx1power',
            'rx2power',
            'rx3power',
            'rx4power',
            'tx1bias',
            'tx1power',
            'tx2bias',
            'tx2power',
            'tx3bias',
            'tx3power',
            'tx4bias',
            'tx4power'
        ]

        dom_info_dict = {
            'temperature': '41.7539C',
            'voltage': '3.2577Volts',
            'rx1power': '-1.6622dBm',
            'rx2power': '-1.7901dBm',
            'rx3power': '-1.6973dBm',
            'rx4power': '-2.0915dBm',
            'tx1bias': '35.8400mA',
            'tx2bias': '37.5780mA',
            'tx3bias': '35.8400mA',
            'tx4bias': '35.8400mA',
            'tx1power': 'N/A',
            'tx2power': 'N/A',
            'tx3power': 'N/A',
            'tx4power': 'N/A'
        }

        expected_output = '''\
                RX1Power: -1.6622dBm
                RX2Power: -1.7901dBm
                RX3Power: -1.6973dBm
                RX4Power: -2.0915dBm
                TX1Bias: 35.8400mA
                TX2Bias: 37.5780mA
                TX3Bias: 35.8400mA
                TX4Bias: 35.8400mA
'''

        output = sfputil.format_dict_value_to_string(sorted_key_table,
                                                     dom_info_dict,
                                                     sfputil.QSFP_DOM_CHANNEL_MONITOR_MAP,
                                                     sfputil.DOM_VALUE_UNIT_MAP)
        assert output == expected_output

        # Change temperature and voltage to floats and ensure units get appended
        dom_info_dict['temperature'] = 41.7539
        dom_info_dict['voltage'] = 3.2577

        output = sfputil.format_dict_value_to_string(sorted_key_table,
                                                     dom_info_dict,
                                                     sfputil.QSFP_DOM_CHANNEL_MONITOR_MAP,
                                                     sfputil.DOM_VALUE_UNIT_MAP)
        assert output == expected_output

    @pytest.mark.parametrize("sfp_info_dict, expected_output",[
        # Non-CMIS module
        (
            # sfp_info_dict
            {
                'type': 'QSFP28 or later',
                'type_abbrv_name': 'QSFP28',
                'manufacturer': 'Mellanox',
                'model': 'MCP1600-C003',
                'vendor_rev': 'A2',
                'serial': 'MT1636VS10561',
                'vendor_oui': '00-02-c9',
                'vendor_date': '2016-07-18',
                'connector': 'No separable connector',
                'encoding': '64B66B',
                'ext_identifier': 'Power Class 1(1.5W max)',
                'ext_rateselect_compliance': 'QSFP+ Rate Select Version 1',
                'cable_type': 'Length Cable Assembly(m)',
                'cable_length': '3',
                'application_advertisement': 'N/A',
                'specification_compliance': "{'10/40G Ethernet Compliance Code': '40GBASE-CR4'}",
                'dom_capability': "{'Tx_power_support': 'no', 'Rx_power_support': 'no', 'Voltage_support': 'no', 'Temp_support': 'no'}",
                'nominal_bit_rate': '255'
            },
            # expected_output
            "        Application Advertisement: N/A\n"
            "        Connector: No separable connector\n"
            "        Encoding: 64B66B\n"
            "        Extended Identifier: Power Class 1(1.5W max)\n"
            "        Extended RateSelect Compliance: QSFP+ Rate Select Version 1\n"
            "        Identifier: QSFP28 or later\n"
            "        Length Cable Assembly(m): 3\n"
            "        Nominal Bit Rate(100Mbs): 255\n"
            "        Specification compliance:\n"
            "                10/40G Ethernet Compliance Code: 40GBASE-CR4\n"
            "        Vendor Date Code(YYYY-MM-DD Lot): 2016-07-18\n"
            "        Vendor Name: Mellanox\n"
            "        Vendor OUI: 00-02-c9\n"
            "        Vendor PN: MCP1600-C003\n"
            "        Vendor Rev: A2\n"
            "        Vendor SN: MT1636VS10561\n"
        ),
        # CMIS compliant module
        (
            # sfp_info_dict
            {
                'type': 'QSFP-DD Double Density 8X Pluggable Transceiver',
                'type_abbrv_name': 'QSFP-DD',
                'manufacturer': 'abc',
                'model': 'def',
                'vendor_rev': 'ghi',
                'serial': 'jkl',
                'vendor_oui': '00-00-00',
                'vendor_date': '2000-01-01',
                'connector': 'LC',
                'encoding': 'N/A',
                'ext_identifier': 'Power Class 8 (18.0W Max)',
                'ext_rateselect_compliance': 'N/A',
                'cable_type': 'Length Cable Assembly(m)',
                'cable_length': '0',
                'application_advertisement': "{1: {'host_electrical_interface_id': '400G CR8', \
                                                  'module_media_interface_id': 'Copper cable', \
                                                  'media_lane_count': 8, \
                                                  'host_lane_count': 8, \
                                                  'host_lane_assignment_options': 1, \
                                                  'media_lane_assignment_options': 2}, \
                                              2: {'host_electrical_interface_id': '200GBASE-CR4 (Clause 136)'}}",
                'specification_compliance': "sm_media_interface",
                'dom_capability': "{'Tx_power_support': 'no', 'Rx_power_support': 'no', 'Voltage_support': 'no', 'Temp_support': 'no'}",
                'nominal_bit_rate': '0',
                'hardware_rev': '0.0',
                'media_interface_code': '400ZR, DWDM, amplified',
                'host_electrical_interface': '400GAUI-8 C2M (Annex 120E)',
                'host_lane_count': 8,
                'media_lane_count': 1,
                'host_lane_assignment_option': 1,
                'media_lane_assignment_option': 1,
                'active_apsel_hostlane1': 1,
                'active_apsel_hostlane2': 1,
                'active_apsel_hostlane3': 1,
                'active_apsel_hostlane4': 1,
                'active_apsel_hostlane5': 1,
                'active_apsel_hostlane6': 1,
                'active_apsel_hostlane7': 1,
                'active_apsel_hostlane8': 1,
                'media_interface_technology': 'C-band tunable laser',
                'cmis_rev': '5.0',
                'supported_max_tx_power': 0,
                'supported_min_tx_power': -20,
                'supported_max_laser_freq': 196100,
                'supported_min_laser_freq': 191300
            },
            # expected_output
            "        Active App Selection Host Lane 1: 1\n"
            "        Active App Selection Host Lane 2: 1\n"
            "        Active App Selection Host Lane 3: 1\n"
            "        Active App Selection Host Lane 4: 1\n"
            "        Active App Selection Host Lane 5: 1\n"
            "        Active App Selection Host Lane 6: 1\n"
            "        Active App Selection Host Lane 7: 1\n"
            "        Active App Selection Host Lane 8: 1\n"
            "        Application Advertisement: 400G CR8 - Host Assign (0x1) - Copper cable - Media Assign (0x2)\n"
            "                                   200GBASE-CR4 (Clause 136) - Host Assign (Unknown) - Unknown - Media Assign (Unknown)\n"
            "        CMIS Revision: 5.0\n"
            "        Connector: LC\n"
            "        Encoding: N/A\n"
            "        Extended Identifier: Power Class 8 (18.0W Max)\n"
            "        Extended RateSelect Compliance: N/A\n"
            "        Hardware Revision: 0.0\n"
            "        Host Electrical Interface: 400GAUI-8 C2M (Annex 120E)\n"
            "        Host Lane Assignment Options: 1\n"
            "        Host Lane Count: 8\n"
            "        Identifier: QSFP-DD Double Density 8X Pluggable Transceiver\n"
            "        Length Cable Assembly(m): 0\n"
            "        Media Interface Code: 400ZR, DWDM, amplified\n"
            "        Media Interface Technology: C-band tunable laser\n"
            "        Media Lane Assignment Options: 1\n"
            "        Media Lane Count: 1\n"
            "        Nominal Bit Rate(100Mbs): 0\n"
            "        Specification compliance: sm_media_interface\n"
            "        Supported Max Laser Frequency: 196100GHz\n"
            "        Supported Max TX Power: 0dBm\n"
            "        Supported Min Laser Frequency: 191300GHz\n"
            "        Supported Min TX Power: -20dBm\n"
            "        Vendor Date Code(YYYY-MM-DD Lot): 2000-01-01\n"
            "        Vendor Name: abc\n"
            "        Vendor OUI: 00-00-00\n"
            "        Vendor PN: def\n"
            "        Vendor Rev: ghi\n"
            "        Vendor SN: jkl\n"
        ),
    ])
    def test_convert_sfp_info_to_output_string(self, sfp_info_dict, expected_output):
        output = sfputil.convert_sfp_info_to_output_string(sfp_info_dict)
        assert output == expected_output

    @pytest.mark.parametrize("sfp_type, dom_info_dict, expected_output", [
        (
            'QSFP28 or later',
            {
                'temperature': '41.7539C',
                'voltage': '3.2577Volts',
                'rx1power': '-1.6622dBm',
                'rx2power': '-1.7901dBm',
                'rx3power': '-1.6973dBm',
                'rx4power': '-2.0915dBm',
                'tx1bias': '35.8400mA',
                'tx2bias': '37.5780mA',
                'tx3bias': '35.8400mA',
                'tx4bias': '35.8400mA',
                'tx1power': 'N/A',
                'tx2power': 'N/A',
                'tx3power': 'N/A',
                'tx4power': 'N/A'
            },
            '''\
        ChannelMonitorValues:
                RX1Power: -1.6622dBm
                RX2Power: -1.7901dBm
                RX3Power: -1.6973dBm
                RX4Power: -2.0915dBm
                TX1Bias: 35.8400mA
                TX2Bias: 37.5780mA
                TX3Bias: 35.8400mA
                TX4Bias: 35.8400mA
        ChannelThresholdValues:
        ModuleMonitorValues:
                Temperature: 41.7539C
                Vcc: 3.2577Volts
        ModuleThresholdValues:
'''
        ), 
        (
            'QSFP-DD Double Density 8X Pluggable Transceiver',
            {
                'temperature': '41.7539C',
                'voltage': '3.2577Volts',
                'rx1power': '-1.6622dBm',
                'rx2power': '-1.7901dBm',
                'rx3power': '-1.6973dBm',
                'rx4power': '-2.0915dBm',
                'rx5power': '-1.6622dBm',
                'rx6power': '-1.7901dBm',
                'rx7power': '-1.6973dBm',
                'rx8power': '-2.0915dBm',
                'tx1bias': '35.8400mA',
                'tx2bias': '37.5780mA',
                'tx3bias': '35.8400mA',
                'tx4bias': '35.8400mA',
                'tx5bias': '35.8400mA',
                'tx6bias': '37.5780mA',
                'tx7bias': '35.8400mA',
                'tx8bias': '35.8400mA',
                'tx1power': 'N/A',
                'tx2power': 'N/A',
                'tx3power': 'N/A',
                'tx4power': 'N/A',
                'tx5power': 'N/A',
                'tx6power': 'N/A',
                'tx7power': 'N/A',
                'tx8power': 'N/A'
            },
            '''\
        ChannelMonitorValues:
                RX1Power: -1.6622dBm
                RX2Power: -1.7901dBm
                RX3Power: -1.6973dBm
                RX4Power: -2.0915dBm
                RX5Power: -1.6622dBm
                RX6Power: -1.7901dBm
                RX7Power: -1.6973dBm
                RX8Power: -2.0915dBm
                TX1Bias: 35.8400mA
                TX2Bias: 37.5780mA
                TX3Bias: 35.8400mA
                TX4Bias: 35.8400mA
                TX5Bias: 35.8400mA
                TX6Bias: 37.5780mA
                TX7Bias: 35.8400mA
                TX8Bias: 35.8400mA
        ChannelThresholdValues:
        ModuleMonitorValues:
                Temperature: 41.7539C
                Vcc: 3.2577Volts
        ModuleThresholdValues:
'''
        ),
        (
            'OSFP 8X Pluggable Transceiver',
            {
                'temperature': '41.7539C',
                'voltage': '3.2577Volts',
                'rx1power': '-1.6622dBm',
                'rx2power': '-1.7901dBm',
                'rx3power': '-1.6973dBm',
                'rx4power': '-2.0915dBm',
                'rx5power': '-1.6622dBm',
                'rx6power': '-1.7901dBm',
                'rx7power': '-1.6973dBm',
                'rx8power': '-2.0915dBm',
                'tx1bias': '35.8400mA',
                'tx2bias': '37.5780mA',
                'tx3bias': '35.8400mA',
                'tx4bias': '35.8400mA',
                'tx5bias': '35.8400mA',
                'tx6bias': '37.5780mA',
                'tx7bias': '35.8400mA',
                'tx8bias': '35.8400mA',
                'tx1power': 'N/A',
                'tx2power': 'N/A',
                'tx3power': 'N/A',
                'tx4power': 'N/A',
                'tx5power': 'N/A',
                'tx6power': 'N/A',
                'tx7power': 'N/A',
                'tx8power': 'N/A'
            },
            '''\
        ChannelMonitorValues:
                RX1Power: -1.6622dBm
                RX2Power: -1.7901dBm
                RX3Power: -1.6973dBm
                RX4Power: -2.0915dBm
                RX5Power: -1.6622dBm
                RX6Power: -1.7901dBm
                RX7Power: -1.6973dBm
                RX8Power: -2.0915dBm
                TX1Bias: 35.8400mA
                TX2Bias: 37.5780mA
                TX3Bias: 35.8400mA
                TX4Bias: 35.8400mA
                TX5Bias: 35.8400mA
                TX6Bias: 37.5780mA
                TX7Bias: 35.8400mA
                TX8Bias: 35.8400mA
        ChannelThresholdValues:
        ModuleMonitorValues:
                Temperature: 41.7539C
                Vcc: 3.2577Volts
        ModuleThresholdValues:
'''
        )])
    def test_convert_dom_to_output_string(self, sfp_type, dom_info_dict, expected_output):
        output = sfputil.convert_dom_to_output_string(sfp_type, dom_info_dict)
        assert output == expected_output

    def test_get_physical_port_name(self):
        output = sfputil.get_physical_port_name(0, 0, False)
        assert output == '0'

        output = sfputil.get_physical_port_name('Ethernet0', 0, False)
        assert output == 'Ethernet0'

        output = sfputil.get_physical_port_name('Ethernet0', 0, True)
        assert output == 'Ethernet0:0 (ganged)'

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['version'], [])
        assert result.output.rstrip() == 'sfputil version {}'.format(sfputil.VERSION)

    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=False))
    def test_error_status_from_db(self):
        db = Db()
        expected_output = [['Ethernet0', 'Blocking Error|High temperature'],
                           ['Ethernet4', 'OK'],
                           ['Ethernet8', 'Unplugged'],
                           ['Ethernet12', 'Unknown state: 255'],
                           ['Ethernet16', 'Unplugged'],
                           ['Ethernet28', 'Unplugged'],
                           ['Ethernet36', 'Unknown'],
                           ['Ethernet40', 'Unplugged'],
                           ['Ethernet44', 'OK']]
        output = sfputil.fetch_error_status_from_state_db(None, db.db)
        assert output == expected_output

        expected_output_ethernet0 = expected_output[:1]
        output = sfputil.fetch_error_status_from_state_db('Ethernet0', db.db)
        assert output == expected_output_ethernet0

    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=True))
    def test_error_status_from_db_RJ45(self):
        db = Db()
        expected_output = [['Ethernet0', 'N/A'],
                           ['Ethernet4', 'N/A'],
                           ['Ethernet8', 'N/A'],
                           ['Ethernet12', 'N/A'],
                           ['Ethernet16', 'N/A'],
                           ['Ethernet28', 'N/A'],
                           ['Ethernet36', 'N/A'],
                           ['Ethernet40', 'N/A'],
                           ['Ethernet44', 'N/A']]
        output = sfputil.fetch_error_status_from_state_db(None, db.db)
        assert output == expected_output

        expected_output_ethernet0 = expected_output[:1]
        output = sfputil.fetch_error_status_from_state_db('Ethernet0', db.db)
        assert output == expected_output_ethernet0

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_name_to_physical_port_list', MagicMock(return_value=[1]))
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=False))
    def test_fetch_error_status_from_platform_api(self, mock_chassis):
        mock_sfp = MagicMock()
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        mock_sfp.get_error_description = MagicMock(return_value='OK')

        output = sfputil.fetch_error_status_from_platform_api('Ethernet0')
        assert output == [['Ethernet0', 'OK']]

    @patch('sfputil.main.logical_port_name_to_physical_port_list', MagicMock(return_value=[1]))
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('subprocess.check_output', MagicMock(return_value="['0:OK']"))
    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=True))
    def test_fetch_error_status_from_platform_api_RJ45(self):
        output = sfputil.fetch_error_status_from_platform_api('Ethernet0')
        assert output == [['Ethernet0', 'N/A']]

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=1)))
    @patch('sfputil.main.logical_port_name_to_physical_port_list', MagicMock(return_value=[1]))
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=False))
    def test_fetch_error_status_from_platform_api_exception(self, mock_chassis):
        mock_sfp = MagicMock()
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        mock_sfp.get_error_description = MagicMock(side_effect=NotImplementedError)

        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['show'].commands['error-status'], ["-hw", "-p", "Ethernet0"])
        assert result.exit_code == ERROR_NOT_IMPLEMENTED
        expected_output = "get_error_description NOT implemented for port Ethernet0\n"
        assert result.output == expected_output

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    def test_show_firmware_version(self, mock_chassis):
        mock_sfp = MagicMock()
        mock_api = MagicMock()
        mock_sfp.get_xcvr_api = MagicMock(return_value=mock_api)
        mock_sfp.get_presence.return_value = True
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        mock_api.get_module_fw_info.return_value = {'info' : ""}
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['show'].commands['fwversion'], ["Ethernet0"])
        assert result.exit_code == 0

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('sfputil.main.logical_port_name_to_physical_port_list', MagicMock(return_value=[1]))
    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=1)))
    def test_show_presence(self, mock_chassis):
        mock_sfp = MagicMock()
        mock_api = MagicMock()
        mock_sfp.get_xcvr_api = MagicMock(return_value=mock_api)
        mock_sfp.get_presence.return_value = True
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['show'].commands['presence'], ["-p", "Ethernet16"])
        assert result.exit_code == 0
        expected_output = """Port        Presence
----------  ----------
Ethernet16  Present
"""
        assert result.output == expected_output

        result = runner.invoke(sfputil.cli.commands['show'].commands['presence'], ["-p", "Ethernet28"])
        assert result.exit_code == 0
        expected_output = """Port        Presence
----------  ----------
Ethernet28  Present
"""
        assert result.output == expected_output

        result = runner.invoke(sfputil.cli.commands['show'].commands['presence'], ["-p", "Ethernet36"])
        assert result.exit_code == 0
        expected_output = """Port        Presence
----------  ----------
Ethernet36  Present
"""
        assert result.output == expected_output

    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=False))
    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=1)))
    def test_show_error_status(self):
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['show'].commands['error-status'], [])
        assert result.exit_code == 0
        expected_output = """Port        Error Status
----------  -------------------------------
Ethernet0   Blocking Error|High temperature
Ethernet4   OK
Ethernet8   Unplugged
Ethernet12  Unknown state: 255
Ethernet16  Unplugged
Ethernet28  Unplugged
Ethernet36  Unknown
Ethernet40  Unplugged
Ethernet44  OK
"""
        assert result.output == expected_output

    @patch('sfputil.main.SonicV2Connector', MagicMock(return_value=None))
    def test_show_error_status_error_case(self):
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['show'].commands['error-status'], [])
        assert result.exit_code == 0
        expected_output = """Failed to connect to STATE_DB\n"""
        assert result.output == expected_output


    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_name_to_physical_port_list', MagicMock(return_value=[1]))
    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=1)))
    def test_show_lpmode(self, mock_chassis):
        mock_sfp = MagicMock()
        mock_api = MagicMock()
        mock_sfp.get_xcvr_api = MagicMock(return_value=mock_api)
        mock_sfp.get_lpmode.return_value = True
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['show'].commands['lpmode'], ["-p", "Ethernet0"])
        assert result.exit_code == 0
        expected_output = """Port       Low-power Mode
---------  ----------------
Ethernet0  On
"""
        assert result.output == expected_output

        mock_sfp.get_lpmode.return_value = False
        result = runner.invoke(sfputil.cli.commands['show'].commands['lpmode'], ["-p", "Ethernet0"])
        assert result.exit_code == 0
        expected_output = """Port       Low-power Mode
---------  ----------------
Ethernet0  Off
"""
        assert result.output == expected_output

        mock_sfp.get_lpmode.return_value = False
        mock_sfp.get_transceiver_info = MagicMock(return_value={'type': sfputil.RJ45_PORT_TYPE})
        mock_chassis.get_port_or_cage_type = MagicMock(return_value=sfputil.SfpBase.SFP_PORT_TYPE_BIT_RJ45)
        result = runner.invoke(sfputil.cli.commands['show'].commands['lpmode'], ["-p", "Ethernet0"])
        assert result.exit_code == 0
        expected_output = """Port       Low-power Mode
---------  ----------------
Ethernet0  N/A
"""
        assert result.output == expected_output

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('sfputil.main.logical_port_name_to_physical_port_list', MagicMock(return_value=[1]))
    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=1)))
    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=True))
    def test_show_eeprom_RJ45(self, mock_chassis):
        mock_sfp = MagicMock()
        mock_api = MagicMock()
        mock_sfp.get_xcvr_api = MagicMock(return_value=mock_api)
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['show'].commands['eeprom'], ["-p", "Ethernet16", "-d"])
        assert result.exit_code == 0
        expected_output = "Ethernet16: SFP EEPROM is not applicable for RJ45 port\n\n\n"
        assert result.output == expected_output

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=0)))
    def test_show_eeprom_hexdump_invalid_port(self, mock_chassis):
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['show'].commands['eeprom-hexdump'], ["-p", "Ethernet"])
        assert result.exit_code != 0

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=1)))
    def test_show_eeprom_hexdump_invalid_page(self, mock_chassis):
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['show'].commands['eeprom-hexdump'], ["-p", "Ethernet1", "-n", "INVALID"])
        assert result.exit_code != 0

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=1)))
    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=True))
    def test_show_eeprom_hexdump_RJ45(self, mock_chassis):
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['show'].commands['eeprom-hexdump'], ["-p", "Ethernet16"])
        assert result.exit_code == ERROR_INVALID_PORT
        expected_output = "Ethernet16: SFP EEPROM Hexdump is not applicable for RJ45 port\n"
        assert result.output == expected_output

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=1)))
    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=False))
    def test_show_eeprom_hexdump_xcvr_presence_not_implemented(self, mock_chassis):
        mock_sfp = MagicMock()
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        mock_sfp.get_presence = MagicMock(side_effect=NotImplementedError)
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['show'].commands['eeprom-hexdump'], ["-p", "Ethernet16"])
        assert result.exit_code == ERROR_NOT_IMPLEMENTED
        expected_output = "Sfp.get_presence() is currently not implemented for this platform\n"
        assert result.output == expected_output

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=1)))
    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=False))
    def test_show_eeprom_hexdump_xcvr_not_present(self, mock_chassis):
        mock_sfp = MagicMock()
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        mock_sfp.get_presence.return_value = False
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['show'].commands['eeprom-hexdump'], ["-p", "Ethernet16"])
        assert result.exit_code == ERROR_NOT_IMPLEMENTED
        expected_output = "SFP EEPROM not detected\n"
        assert result.output == expected_output

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=1)))
    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=False))
    def test_show_eeprom_hexdump_read_eeprom_failure(self, mock_chassis):
        mock_sfp = MagicMock()
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        mock_sfp.get_presence.return_value = True
        mock_sfp.get_xcvr_api = MagicMock(return_value=None)
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['show'].commands['eeprom-hexdump'], ["-p", "Ethernet16"])
        assert result.exit_code == ERROR_NOT_IMPLEMENTED
        expected_output = "Error: Failed to read EEPROM for offset 0!\n"
        assert result.output == expected_output

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=1)))
    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=False))
    @patch('sfputil.main.isinstance', MagicMock(return_value=True))
    def test_show_eeprom_hexdump_read_eeprom_not_implemented(self, mock_chassis):
        mock_sfp = MagicMock()
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        mock_sfp.get_presence.return_value = True
        mock_sfp.read_eeprom = MagicMock(side_effect=NotImplementedError)
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['show'].commands['eeprom-hexdump'], ["-p", "Ethernet16"])
        assert result.exit_code == ERROR_NOT_IMPLEMENTED
        expected_output = "Sfp.read_eeprom() is currently not implemented for this platform\n"
        assert result.output == expected_output


    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=1)))
    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=False))
    @patch('sfputil.main.isinstance', MagicMock(return_value=True))
    def test_show_eeprom_hexdump_processing_hex_page_number(self, mock_chassis):
        lower_page_bytearray = bytearray([13, 0, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 129, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        upper_page0_bytearray = bytearray([13, 0, 35, 8, 0, 0, 0, 65, 128, 128, 245, 0, 0, 0, 0, 0, 0, 0, 1, 160, 77, 111, 108, 101, 120, 32, 73, 110, 99, 46, 32, 32, 32, 32, 32, 32, 7, 0, 9, 58, 49, 49, 49, 48, 52, 48, 49, 48, 53, 52, 32, 32, 32, 32, 32, 32, 32, 32, 3, 4, 0, 0, 70, 196, 0, 0, 0, 0, 54, 49, 49, 48, 51, 48, 57, 50, 57, 32, 32, 32, 32, 32, 32, 32, 49, 54, 48, 52, 49, 57, 32, 32, 0, 0, 0, 36, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        page10_expected_output = '''EEPROM hexdump for port Ethernet0 page 10h
        Lower page 0h
        00000000 0d 00 06 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        00000010 00 00 00 00 00 00 01 81  00 00 00 00 00 00 00 00 |................|
        00000020 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        00000030 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        00000040 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        00000050 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        00000060 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        00000070 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|

        Upper page 0h
        00000080 0d 00 23 08 00 00 00 41  80 80 f5 00 00 00 00 00 |..#....A........|
        00000090 00 00 01 a0 4d 6f 6c 65  78 20 49 6e 63 2e 20 20 |....Molex Inc.  |
        000000a0 20 20 20 20 07 00 09 3a  31 31 31 30 34 30 31 30 |    ...:11104010|
        000000b0 35 34 20 20 20 20 20 20  20 20 03 04 00 00 46 c4 |54        ....F.|
        000000c0 00 00 00 00 36 31 31 30  33 30 39 32 39 20 20 20 |....611030929   |
        000000d0 20 20 20 20 31 36 30 34  31 39 20 20 00 00 00 24 |    160419  ...$|
        000000e0 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        000000f0 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|

        Upper page 10h
        00000080 0d 00 23 08 00 00 00 41  80 80 f5 00 00 00 00 00 |..#....A........|
        00000090 00 00 01 a0 4d 6f 6c 65  78 20 49 6e 63 2e 20 20 |....Molex Inc.  |
        000000a0 20 20 20 20 07 00 09 3a  31 31 31 30 34 30 31 30 |    ...:11104010|
        000000b0 35 34 20 20 20 20 20 20  20 20 03 04 00 00 46 c4 |54        ....F.|
        000000c0 00 00 00 00 36 31 31 30  33 30 39 32 39 20 20 20 |....611030929   |
        000000d0 20 20 20 20 31 36 30 34  31 39 20 20 00 00 00 24 |    160419  ...$|
        000000e0 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        000000f0 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|

'''
        page11_expected_output = '''EEPROM hexdump for port Ethernet0 page 11h
        Lower page 0h
        00000000 0d 00 06 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        00000010 00 00 00 00 00 00 01 81  00 00 00 00 00 00 00 00 |................|
        00000020 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        00000030 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        00000040 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        00000050 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        00000060 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        00000070 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|

        Upper page 0h
        00000080 0d 00 23 08 00 00 00 41  80 80 f5 00 00 00 00 00 |..#....A........|
        00000090 00 00 01 a0 4d 6f 6c 65  78 20 49 6e 63 2e 20 20 |....Molex Inc.  |
        000000a0 20 20 20 20 07 00 09 3a  31 31 31 30 34 30 31 30 |    ...:11104010|
        000000b0 35 34 20 20 20 20 20 20  20 20 03 04 00 00 46 c4 |54        ....F.|
        000000c0 00 00 00 00 36 31 31 30  33 30 39 32 39 20 20 20 |....611030929   |
        000000d0 20 20 20 20 31 36 30 34  31 39 20 20 00 00 00 24 |    160419  ...$|
        000000e0 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        000000f0 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|

        Upper page 11h
        00000080 0d 00 23 08 00 00 00 41  80 80 f5 00 00 00 00 00 |..#....A........|
        00000090 00 00 01 a0 4d 6f 6c 65  78 20 49 6e 63 2e 20 20 |....Molex Inc.  |
        000000a0 20 20 20 20 07 00 09 3a  31 31 31 30 34 30 31 30 |    ...:11104010|
        000000b0 35 34 20 20 20 20 20 20  20 20 03 04 00 00 46 c4 |54        ....F.|
        000000c0 00 00 00 00 36 31 31 30  33 30 39 32 39 20 20 20 |....611030929   |
        000000d0 20 20 20 20 31 36 30 34  31 39 20 20 00 00 00 24 |    160419  ...$|
        000000e0 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        000000f0 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|

'''
        def side_effect(offset, num_bytes):
            if offset == 0:
                return lower_page_bytearray
            else:
                return upper_page0_bytearray
        mock_sfp = MagicMock()
        mock_sfp.get_presence.return_value = True
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        mock_sfp.read_eeprom = MagicMock(side_effect=side_effect)
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['show'].commands['eeprom-hexdump'], ["-p", "Ethernet0", "-n", "10"])
        assert result.exit_code == 0
        assert result.output == page10_expected_output
        result = runner.invoke(sfputil.cli.commands['show'].commands['eeprom-hexdump'], ["-p", "Ethernet0", "-n", "11"])
        assert result.exit_code == 0
        assert result.output == page11_expected_output

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=1)))
    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=False))
    @patch('sfputil.main.isinstance', MagicMock(return_value=True))
    def test_show_eeprom_hexdump_sff8636_page(self, mock_chassis):
        lower_page_bytearray = bytearray([13, 0, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 129, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        upper_page0_bytearray = bytearray([13, 0, 35, 8, 0, 0, 0, 65, 128, 128, 245, 0, 0, 0, 0, 0, 0, 0, 1, 160, 77, 111, 108, 101, 120, 32, 73, 110, 99, 46, 32, 32, 32, 32, 32, 32, 7, 0, 9, 58, 49, 49, 49, 48, 52, 48, 49, 48, 53, 52, 32, 32, 32, 32, 32, 32, 32, 32, 3, 4, 0, 0, 70, 196, 0, 0, 0, 0, 54, 49, 49, 48, 51, 48, 57, 50, 57, 32, 32, 32, 32, 32, 32, 32, 49, 54, 48, 52, 49, 57, 32, 32, 0, 0, 0, 36, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        expected_output = '''EEPROM hexdump for port Ethernet0 page 0h
        Lower page 0h
        00000000 0d 00 06 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        00000010 00 00 00 00 00 00 01 81  00 00 00 00 00 00 00 00 |................|
        00000020 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        00000030 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        00000040 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        00000050 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        00000060 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        00000070 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|

        Upper page 0h
        00000080 0d 00 23 08 00 00 00 41  80 80 f5 00 00 00 00 00 |..#....A........|
        00000090 00 00 01 a0 4d 6f 6c 65  78 20 49 6e 63 2e 20 20 |....Molex Inc.  |
        000000a0 20 20 20 20 07 00 09 3a  31 31 31 30 34 30 31 30 |    ...:11104010|
        000000b0 35 34 20 20 20 20 20 20  20 20 03 04 00 00 46 c4 |54        ....F.|
        000000c0 00 00 00 00 36 31 31 30  33 30 39 32 39 20 20 20 |....611030929   |
        000000d0 20 20 20 20 31 36 30 34  31 39 20 20 00 00 00 24 |    160419  ...$|
        000000e0 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        000000f0 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|

'''
        def side_effect(offset, num_bytes):
            if offset == 0:
                return lower_page_bytearray
            else:
                return upper_page0_bytearray
        mock_sfp = MagicMock()
        mock_sfp.get_presence.return_value = True
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        mock_sfp.read_eeprom = MagicMock(side_effect=side_effect)
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['show'].commands['eeprom-hexdump'], ["-p", "Ethernet0", "-n", "0"])
        assert result.exit_code == 0
        assert result.output == expected_output

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=1)))
    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=False))
    @patch('sfputil.main.isinstance', MagicMock(side_effect=[False, False, False, True]))
    def test_show_eeprom_hexdump_sff8472_page(self, mock_chassis):
        a0h_bytearray = bytearray([3, 4, 7, 16, 0, 0, 0, 0, 0, 0, 0, 6, 103, 0, 0, 0, 8, 3, 0, 30, 70, 73, 78, 73, 83, 65, 82, 32, 67, 79, 82, 80, 46, 32, 32, 32, 0, 0, 144, 101, 70, 84, 76, 88, 56, 53, 55, 49, 68, 51, 66, 67, 76, 32, 32, 32, 65, 32, 32, 32, 3, 82, 0, 72, 0, 26, 0, 0, 65, 85, 74, 48, 82, 67, 74, 32, 32, 32, 32, 32, 32, 32, 32, 32, 49, 53, 49, 48, 50, 57, 32, 32, 104, 240, 3, 246, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        a2h_lower_bytearray = bytearray([78, 0, 243, 0, 73, 0, 248, 0, 144, 136, 113, 72, 140, 160, 117, 48, 25, 200, 7, 208, 24, 156, 9, 196, 39, 16, 9, 208, 31, 7, 12, 90, 39, 16, 0, 100, 31, 7, 0, 158, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 63, 128, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 27, 20, 2, 129, 177, 13, 90, 23, 165, 21, 135, 0, 0, 0, 0, 48, 0, 0, 0, 0, 0, 0, 0, 0, 0, 255, 255, 255, 255, 255, 255, 255, 1])
        a2h_upper_bytearray = bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        expected_output = '''EEPROM hexdump for port Ethernet256 page 0h
        A0h dump
        00000000 03 04 07 10 00 00 00 00  00 00 00 06 67 00 00 00 |............g...|
        00000010 08 03 00 1e 46 49 4e 49  53 41 52 20 43 4f 52 50 |....FINISAR CORP|
        00000020 2e 20 20 20 00 00 90 65  46 54 4c 58 38 35 37 31 |.   ...eFTLX8571|
        00000030 44 33 42 43 4c 20 20 20  41 20 20 20 03 52 00 48 |D3BCL   A   .R.H|
        00000040 00 1a 00 00 41 55 4a 30  52 43 4a 20 20 20 20 20 |....AUJ0RCJ     |
        00000050 20 20 20 20 31 35 31 30  32 39 20 20 68 f0 03 f6 |    151029  h...|
        00000060 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        00000070 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        00000080 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        00000090 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        000000a0 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        000000b0 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        000000c0 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        000000d0 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        000000e0 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        000000f0 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|

        A2h dump (lower 128 bytes)
        00000000 4e 00 f3 00 49 00 f8 00  90 88 71 48 8c a0 75 30 |N...I.....qH..u0|
        00000010 19 c8 07 d0 18 9c 09 c4  27 10 09 d0 1f 07 0c 5a |........'......Z|
        00000020 27 10 00 64 1f 07 00 9e  00 00 00 00 00 00 00 00 |'..d............|
        00000030 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        00000040 00 00 00 00 3f 80 00 00  00 00 00 00 01 00 00 00 |....?...........|
        00000050 01 00 00 00 01 00 00 00  01 00 00 00 00 00 00 1b |................|
        00000060 14 02 81 b1 0d 5a 17 a5  15 87 00 00 00 00 30 00 |.....Z........0.|
        00000070 00 00 00 00 00 00 00 00  ff ff ff ff ff ff ff 01 |................|

        A2h dump (upper 128 bytes) page 0h
        00000080 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        00000090 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        000000a0 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        000000b0 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        000000c0 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        000000d0 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        000000e0 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|
        000000f0 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00 |................|

'''
        SFF8472_A0_SIZE = 256
        def side_effect(offset, num_bytes):
            if offset == 0:
                return a0h_bytearray
            elif (offset == SFF8472_A0_SIZE):
                return a2h_lower_bytearray
            else:
                return a2h_upper_bytearray
        mock_sfp = MagicMock()
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        mock_sfp.get_presence.return_value = True
        mock_sfp.read_eeprom = MagicMock(side_effect=side_effect)
        mock_api = MagicMock()
        mock_sfp.get_xcvr_api = MagicMock(return_value=mock_api)
        mock_api.is_copper = MagicMock(return_value=False)
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['show'].commands['eeprom-hexdump'], ["-p", "Ethernet256", "-n", "0"])
        assert result.exit_code == 0
        assert result.output == expected_output

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.platform_sfputil')
    @patch('sfputil.main.isinstance', MagicMock(side_effect=[True, False, False, False, True]))
    def test_eeprom_hexdump_all_falure(self, mock_sfputil, mock_chassis):
        mock_sfputil.logical = ['Ethernet4', 'Ethernet0']
        mock_sfp = MagicMock()
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        mock_sfp.get_presence.return_value = True
        mock_sfp.read_eeprom = MagicMock(return_value=None)

        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['show'].commands['eeprom-hexdump'])
        assert result.exit_code == 0
        expected_output = """EEPROM hexdump for port Ethernet0
        Error: Failed to read EEPROM for page 0h, flat_offset 0, page_offset 0, size 128!

EEPROM hexdump for port Ethernet4
        Error: Failed to read EEPROM for A0h!

"""
        assert result.output == expected_output

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.platform_sfputil')
    @patch('sfputil.main.isinstance', MagicMock(side_effect=[True, False, False, False, True]))
    def test_eeprom_hexdump_all(self, mock_sfputil, mock_chassis):
        mock_sfputil.logical = ['Ethernet4', 'Ethernet0']
        mock_sfp = MagicMock()
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        mock_sfp.get_presence.return_value = True
        mock_sfp.read_eeprom = MagicMock(return_value=None)

        def mock_read_eeprom(offset, num_bytes):
            return bytearray([x for x in range(num_bytes)])

        mock_sfp.read_eeprom.side_effect = mock_read_eeprom

        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['show'].commands['eeprom-hexdump'])
        assert result.exit_code == 0
        expected_output = """EEPROM hexdump for port Ethernet0
        Lower page 0h
        00000000 00 01 02 03 04 05 06 07  08 09 0a 0b 0c 0d 0e 0f |................|
        00000010 10 11 12 13 14 15 16 17  18 19 1a 1b 1c 1d 1e 1f |................|
        00000020 20 21 22 23 24 25 26 27  28 29 2a 2b 2c 2d 2e 2f | !"#$%&'()*+,-./|
        00000030 30 31 32 33 34 35 36 37  38 39 3a 3b 3c 3d 3e 3f |0123456789:;<=>?|
        00000040 40 41 42 43 44 45 46 47  48 49 4a 4b 4c 4d 4e 4f |@ABCDEFGHIJKLMNO|
        00000050 50 51 52 53 54 55 56 57  58 59 5a 5b 5c 5d 5e 5f |PQRSTUVWXYZ[\]^_|
        00000060 60 61 62 63 64 65 66 67  68 69 6a 6b 6c 6d 6e 6f |`abcdefghijklmno|
        00000070 70 71 72 73 74 75 76 77  78 79 7a 7b 7c 7d 7e 7f |pqrstuvwxyz{|}~.|

        Upper page 0h
        00000080 00 01 02 03 04 05 06 07  08 09 0a 0b 0c 0d 0e 0f |................|
        00000090 10 11 12 13 14 15 16 17  18 19 1a 1b 1c 1d 1e 1f |................|
        000000a0 20 21 22 23 24 25 26 27  28 29 2a 2b 2c 2d 2e 2f | !"#$%&'()*+,-./|
        000000b0 30 31 32 33 34 35 36 37  38 39 3a 3b 3c 3d 3e 3f |0123456789:;<=>?|
        000000c0 40 41 42 43 44 45 46 47  48 49 4a 4b 4c 4d 4e 4f |@ABCDEFGHIJKLMNO|
        000000d0 50 51 52 53 54 55 56 57  58 59 5a 5b 5c 5d 5e 5f |PQRSTUVWXYZ[\]^_|
        000000e0 60 61 62 63 64 65 66 67  68 69 6a 6b 6c 6d 6e 6f |`abcdefghijklmno|
        000000f0 70 71 72 73 74 75 76 77  78 79 7a 7b 7c 7d 7e 7f |pqrstuvwxyz{|}~.|

EEPROM hexdump for port Ethernet4
        A0h dump
        00000000 00 01 02 03 04 05 06 07  08 09 0a 0b 0c 0d 0e 0f |................|
        00000010 10 11 12 13 14 15 16 17  18 19 1a 1b 1c 1d 1e 1f |................|
        00000020 20 21 22 23 24 25 26 27  28 29 2a 2b 2c 2d 2e 2f | !"#$%&'()*+,-./|
        00000030 30 31 32 33 34 35 36 37  38 39 3a 3b 3c 3d 3e 3f |0123456789:;<=>?|
        00000040 40 41 42 43 44 45 46 47  48 49 4a 4b 4c 4d 4e 4f |@ABCDEFGHIJKLMNO|
        00000050 50 51 52 53 54 55 56 57  58 59 5a 5b 5c 5d 5e 5f |PQRSTUVWXYZ[\]^_|
        00000060 60 61 62 63 64 65 66 67  68 69 6a 6b 6c 6d 6e 6f |`abcdefghijklmno|
        00000070 70 71 72 73 74 75 76 77  78 79 7a 7b 7c 7d 7e 7f |pqrstuvwxyz{|}~.|

"""
        assert expected_output == result.output

    def test_test_eeprom_hexdump_all_invalid_page(self):
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['show'].commands['eeprom-hexdump'], ['--page', '-1'])
        assert result.exit_code != 0

        result = runner.invoke(sfputil.cli.commands['show'].commands['eeprom-hexdump'], ['--page', '256'])
        assert result.exit_code != 0

        result = runner.invoke(sfputil.cli.commands['show'].commands['eeprom-hexdump'], ['--page', 'invalid_number'])
        assert result.exit_code != 0

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=1)))
    @patch('sfputil.main.eeprom_hexdump_pages_general')
    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=False))
    @patch('sfputil.main.isinstance')
    def test_eeprom_hexdump_single_port(self, mock_isinstance, mock_dump, mock_chassis):
        mock_isinstance.return_value = True
        mock_sfp = MagicMock()
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        mock_sfp.get_presence.return_value = True
        mock_api = MagicMock()
        mock_sfp.get_xcvr_api.return_value = mock_api
        sfputil.eeprom_hexdump_single_port('Ethernet0', 0)
        mock_dump.assert_called_with('Ethernet0', [0], 0)

        mock_dump.reset_mock()
        sfputil.eeprom_hexdump_single_port('Ethernet0', 1)
        mock_dump.assert_called_with('Ethernet0', [0, 1], 1)

        mock_api.is_flat_memory.return_value = False
        mock_api.is_coherent_module.return_value = False
        mock_dump.reset_mock()
        sfputil.eeprom_hexdump_single_port('Ethernet0', None)
        mock_dump.assert_called_with('Ethernet0', [0, 1, 2, 16, 17, 159], None)

        mock_api.is_coherent_module.return_value = True
        mock_dump.reset_mock()
        sfputil.eeprom_hexdump_single_port('Ethernet0', None)
        mock_dump.assert_called_with('Ethernet0', [0, 1, 2, 16, 17, 48, 49, 50, 51, 52, 53, 56, 57, 58, 59, 159], None)

        mock_api.is_flat_memory.return_value = True
        mock_dump.reset_mock()
        sfputil.eeprom_hexdump_single_port('Ethernet0', None)
        mock_dump.assert_called_with('Ethernet0', [0], None)

        mock_isinstance.side_effect = [False, True]
        mock_dump.reset_mock()
        sfputil.eeprom_hexdump_single_port('Ethernet0', None)
        mock_dump.assert_called_with('Ethernet0', [0], None)

        mock_api.is_flat_memory.return_value = False
        mock_isinstance.side_effect = [False, True]
        mock_dump.reset_mock()
        sfputil.eeprom_hexdump_single_port('Ethernet0', None)
        mock_dump.assert_called_with('Ethernet0', [0, 1, 2, 3], None)

        mock_isinstance.side_effect = [False, True]
        mock_dump.reset_mock()
        sfputil.eeprom_hexdump_single_port('Ethernet0', 3)
        mock_dump.assert_called_with('Ethernet0', [0, 3], 3)



    @patch('sfputil.main.logical_port_name_to_physical_port_list', MagicMock(return_value=1))
    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=True))
    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=1)))
    def test_lpmode_set(self):
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['lpmode'].commands['on'], ["Ethernet0"])
        assert result.output == 'Enabling low-power mode is not applicable for RJ45 port Ethernet0.\n'
        assert result.exit_code == EXIT_FAIL

    @patch('sfputil.main.logical_port_name_to_physical_port_list', MagicMock(return_value=1))
    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=True))
    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=1)))
    def test_reset_RJ45(self):
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['reset'], ["Ethernet0"])
        assert result.output == 'Reset is not applicable for RJ45 port Ethernet0.\n'
        assert result.exit_code == EXIT_FAIL

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    def test_unlock_firmware(self, mock_chassis):
        mock_sfp = MagicMock()
        mock_api = MagicMock()
        mock_sfp.get_xcvr_api = MagicMock(return_value=mock_api)
        mock_sfp.get_presence.return_value = True
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        mock_api.cdb_enter_host_password.return_value = 0
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['firmware'].commands['unlock'], ["Ethernet0"])
        assert result.exit_code == 0

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=True))
    def test_show_fwversion_Rj45(self, mock_chassis):
        mock_sfp = MagicMock()
        mock_api = MagicMock()
        mock_sfp.get_xcvr_api = MagicMock(return_value=mock_api)
        mock_sfp.get_presence.return_value = True
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['show'].commands['fwversion'], ["Ethernet0"])
        assert result.output == 'Show firmware version is not applicable for RJ45 port Ethernet0.\n'
        assert result.exit_code == EXIT_FAIL

    @patch('builtins.open')
    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('sfputil.main.update_firmware_info_to_state_db', MagicMock())
    def test_download_firmware(self, mock_chassis, mock_file):
        mock_file.return_value.tell.return_value = 0
        mock_sfp = MagicMock()
        mock_api = MagicMock()
        mock_sfp.get_xcvr_api = MagicMock(return_value=mock_api)
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        mock_api.get_module_fw_mgmt_feature.return_value = {'status': True, 'feature': (0, 0, False, False, 0)}
        mock_api.cdb_start_firmware_download.return_value = 1
        mock_api.cdb_firmware_download_complete.return_value = 1
        mock_sfp.set_optoe_write_max = MagicMock(side_effect=NotImplementedError)
        status = sfputil.download_firmware("Ethernet0", "test.bin")
        assert status == 1
        mock_api.get_module_fw_mgmt_feature.return_value = {'status': True, 'feature': (0, 64, True, False, 0)}
        status = sfputil.download_firmware("Ethernet0", "test.bin")
        assert status == 1

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    def test_run_firmwre(self, mock_chassis):
        mock_sfp = MagicMock()
        mock_api = MagicMock()
        mock_sfp.get_xcvr_api = MagicMock(return_value=mock_api)
        mock_sfp.get_presence.return_value = True
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        mock_api.cdb_run_firmware.return_value = 1
        status = sfputil.run_firmware("Ethernet0", 1)
        assert status == 1

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @pytest.mark.parametrize("mock_response, expected", [
        ({'status': False, 'result': None}                                 , -1),
        ({'status': True,  'result': ("1.0.1", 1, 1, 0, "1.0.2", 0, 0, 0, "1.0.1", "1.0.2")} , -1),
        ({'status': True,  'result': ("1.0.1", 0, 0, 0, "1.0.2", 1, 1, 0, "1.0.2", "1.0.1")} , -1),
        ({'status': True,  'result': ("1.0.1", 1, 0, 0, "1.0.2", 0, 1, 0, "1.0.1", "1.0.2")} ,  1),
        ({'status': True,  'result': ("1.0.1", 0, 1, 0, "1.0.2", 1, 0, 0, "1.0.2", "1.0.1")} ,  1),
        ({'status': True,  'result': ("1.0.1", 1, 0, 1, "1.0.2", 0, 1, 0, "1.0.1", "1.0.2")} , -1),
        ({'status': True,  'result': ("1.0.1", 0, 1, 0, "1.0.2", 1, 0, 1, "1.0.2", "1.0.1")} , -1),

        # "is_fw_switch_done" function will waiting until timeout under below condition, so that this test will spend around 1min.
        ({'status': False, 'result': 0}                                    , -1),
    ])
    def test_is_fw_switch_done(self, mock_chassis, mock_response, expected):
        mock_sfp = MagicMock()
        mock_api = MagicMock()
        mock_sfp.get_xcvr_api = MagicMock(return_value=mock_api)
        mock_sfp.get_presence.return_value = True
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        mock_api.get_module_fw_info.return_value = mock_response
        status = sfputil.is_fw_switch_done("Ethernet0")
        assert status == expected

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    def test_commit_firmwre(self, mock_chassis):
        mock_sfp = MagicMock()
        mock_api = MagicMock()
        mock_sfp.get_xcvr_api = MagicMock(return_value=mock_api)
        mock_sfp.get_presence.return_value = True
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        mock_api.cdb_commit_firmware.return_value = 1
        status = sfputil.commit_firmware("Ethernet0")
        assert status == 1

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=False))
    @patch('sfputil.main.is_sfp_present', MagicMock(return_value=True))
    @patch('sfputil.main.show_firmware_version', MagicMock())
    @patch('sfputil.main.download_firmware', MagicMock(return_value=1))
    @patch('sfputil.main.run_firmware', MagicMock(return_value=1))
    @patch('sfputil.main.is_fw_switch_done', MagicMock(return_value=1))
    @patch('sfputil.main.commit_firmware', MagicMock(return_value=1))
    def test_firmware_upgrade(self, mock_chassis):
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['firmware'].commands['upgrade'], ['Ethernet0', 'path'])
        assert result.output == 'Firmware download complete success\nFirmware run in mode 0 successful\nFirmware commit successful\n'
        assert result.exit_code == 0

    @patch('sfputil.main.is_sfp_present', MagicMock(return_value=True))
    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=True))
    def test_firmware_run_RJ45(self):
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['firmware'].commands['run'], ["--mode", "0", "Ethernet0"])
        assert result.output == 'This functionality is not applicable for RJ45 port Ethernet0.\n'
        assert result.exit_code == EXIT_FAIL

    @patch('sfputil.main.is_sfp_present', MagicMock(return_value=True))
    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=True))
    def test_firmware_commit_RJ45(self):
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['firmware'].commands['commit'], ["Ethernet0"])
        assert result.output == 'This functionality is not applicable for RJ45 port Ethernet0.\n'
        assert result.exit_code == EXIT_FAIL

    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=True))
    @patch('sfputil.main.is_sfp_present', MagicMock(return_value=1))
    def test_firmware_upgrade_RJ45(self):
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['firmware'].commands['upgrade'], ["Ethernet0", "a.b"])
        assert result.output == 'This functionality is not applicable for RJ45 port Ethernet0.\n'
        assert result.exit_code == EXIT_FAIL

    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=True))
    @patch('sfputil.main.is_sfp_present', MagicMock(return_value=1))
    def test_firmware_download_RJ45(self):
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['firmware'].commands['download'], ["Ethernet0", "a.b"])
        assert result.output == 'This functionality is not applicable for RJ45 port Ethernet0.\n'
        assert result.exit_code == EXIT_FAIL

    @patch('sfputil.main.is_sfp_present', MagicMock(return_value=True))
    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=False))
    @patch('sfputil.main.run_firmware', MagicMock(return_value=1))
    @patch('sfputil.main.update_firmware_info_to_state_db', MagicMock())
    def test_firmware_run_cli(self):
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['firmware'].commands['run'], ["Ethernet0"])
        assert result.exit_code == 0

    @patch('sfputil.main.is_sfp_present', MagicMock(return_value=True))
    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=False))
    @patch('sfputil.main.commit_firmware', MagicMock(return_value=1))
    @patch('sfputil.main.update_firmware_info_to_state_db', MagicMock())
    def test_firmware_commit_cli(self):
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['firmware'].commands['commit'], ["Ethernet0"])
        assert result.exit_code == 0

    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('sonic_py_common.multi_asic.get_front_end_namespaces', MagicMock(return_value=['']))
    @patch('sfputil.main.SonicV2Connector', MagicMock())
    @patch('sfputil.main.platform_chassis')
    def test_update_firmware_info_to_state_db(self, mock_chassis):
        mock_sfp = MagicMock()
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        mock_sfp.get_transceiver_info_firmware_versions.return_value = {'active_firmware' : 'a.b.c', 'inactive_firmware' : 'd.e.f'}

        sfputil.update_firmware_info_to_state_db("Ethernet0")

    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=False))
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=1)))
    @patch('sfputil.main.platform_chassis')
    def test_read_eeprom(self, mock_chassis):
        mock_sfp = MagicMock()
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)

        mock_sfp.get_presence = MagicMock(return_value=False)
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['read-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '0', '-s', '1'])
        assert result.exit_code == EXIT_FAIL

        mock_sfp.get_presence.return_value = True
        mock_sfp.read_eeprom = MagicMock(return_value=None)
        result = runner.invoke(sfputil.cli.commands['read-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '0', '-s', '1'])
        assert result.exit_code == ERROR_NOT_IMPLEMENTED

        mock_sfp.read_eeprom.return_value = bytearray([0x00, 0x01])
        result = runner.invoke(sfputil.cli.commands['read-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '0', '-s', '2', '--no-format'])
        assert result.exit_code == 0
        assert result.output == '0001\n'

        result = runner.invoke(sfputil.cli.commands['read-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '5', '-s', '2'])
        assert result.exit_code == 0
        expected_output = """        00000005 00 01                                            |..|
"""
        print(result.output)
        assert result.output == expected_output

        mock_sfp.read_eeprom.side_effect = NotImplementedError
        result = runner.invoke(sfputil.cli.commands['read-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '5', '-s', '2'])
        assert result.exit_code == ERROR_NOT_IMPLEMENTED

        mock_sfp.read_eeprom.side_effect = ValueError
        result = runner.invoke(sfputil.cli.commands['read-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '5', '-s', '2'])
        assert result.exit_code == EXIT_FAIL

    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=False))
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=1)))
    @patch('sfputil.main.platform_chassis')
    def test_write_eeprom(self, mock_chassis):
        mock_sfp = MagicMock()
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)

        mock_sfp.get_presence = MagicMock(return_value=False)
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['write-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '0', '-d', '01'])
        assert result.exit_code == EXIT_FAIL

        # invalid hex string, hex string must have even length
        mock_sfp.get_presence.return_value = True
        result = runner.invoke(sfputil.cli.commands['write-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '0', '-d', '1'])
        assert result.exit_code == EXIT_FAIL

        # invalid hex string
        result = runner.invoke(sfputil.cli.commands['write-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '0', '-d', '+0'])
        assert result.exit_code == EXIT_FAIL

        # write failed
        mock_sfp.write_eeprom = MagicMock(return_value=False)
        result = runner.invoke(sfputil.cli.commands['write-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '0', '-d', '10'])
        print(result.output)
        assert result.exit_code == ERROR_NOT_IMPLEMENTED

        # write success
        mock_sfp.write_eeprom.return_value = True
        result = runner.invoke(sfputil.cli.commands['write-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '0', '-d', '10'])
        assert result.exit_code == 0

        # write verify success
        mock_sfp.read_eeprom = MagicMock(return_value=bytearray([16]))
        result = runner.invoke(sfputil.cli.commands['write-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '0', '-d', '10', '--verify'])
        assert result.exit_code == 0

        # write verify failed
        mock_sfp.read_eeprom = MagicMock(return_value=bytearray([10]))
        result = runner.invoke(sfputil.cli.commands['write-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '0', '-d', '11', '--verify'])
        assert result.exit_code != 0

        # Not implemented
        mock_sfp.write_eeprom.side_effect = NotImplementedError
        result = runner.invoke(sfputil.cli.commands['write-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '0', '-d', '10'])
        assert result.exit_code == ERROR_NOT_IMPLEMENTED

        # Value error
        mock_sfp.write_eeprom.side_effect = ValueError
        result = runner.invoke(sfputil.cli.commands['write-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '0', '-d', '10'])
        assert result.exit_code == EXIT_FAIL

    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=0)))
    def test_read_eeprom_invalid_port(self):
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['read-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '0', '-s', '1'])
        assert result.exit_code == ERROR_INVALID_PORT

    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=0)))
    def test_write_eeprom_invalid_port(self):
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['write-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '0', '-d', '00'])
        assert result.exit_code == ERROR_INVALID_PORT

    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=True))
    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=1)))
    def test_read_eeprom_rj45(self):
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['read-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '0', '-s', '1'])
        assert result.exit_code == EXIT_FAIL

    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=True))
    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=1)))
    def test_write_eeprom_rj45(self):
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['write-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '0', '-d', '00'])
        assert result.exit_code == EXIT_FAIL

    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=False))
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=1)))
    @patch('sfputil.main.platform_chassis')
    def test_get_overall_offset_general(self, mock_chassis):
        api = MagicMock()
        api.is_flat_memory = MagicMock(return_value=False)
        mock_sfp = MagicMock()
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)

        mock_sfp.get_presence = MagicMock(return_value=True)
        mock_sfp.get_xcvr_api = MagicMock(return_value=api)
        
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['write-eeprom'],
                               ['-p', "Ethernet0", '-n', '-1', '-o', '0', '-d', '01'])
        assert result.exit_code != 0
        
        result = runner.invoke(sfputil.cli.commands['write-eeprom'],
                               ['-p', "Ethernet0", '-n', '256', '-o', '0', '-d', '01'])
        assert result.exit_code != 0
        
        result = runner.invoke(sfputil.cli.commands['write-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '-1', '-d', '01'])
        assert result.exit_code != 0
        
        result = runner.invoke(sfputil.cli.commands['write-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '256', '-d', '01'])
        assert result.exit_code != 0
        
        result = runner.invoke(sfputil.cli.commands['write-eeprom'],
                               ['-p', "Ethernet0", '-n', '1', '-o', '127', '-d', '01'])
        assert result.exit_code != 0
        
        result = runner.invoke(sfputil.cli.commands['write-eeprom'],
                               ['-p', "Ethernet0", '-n', '1', '-o', '256', '-d', '01'])
        assert result.exit_code != 0
        
        result = runner.invoke(sfputil.cli.commands['read-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '0', '-s', '0'])
        assert result.exit_code != 0
        
        result = runner.invoke(sfputil.cli.commands['read-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '0', '-s', '257'])
        assert result.exit_code != 0
        
        result = runner.invoke(sfputil.cli.commands['write-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '1', '-d', '01'])
        assert result.exit_code == 0

    @patch('sfputil.main.isinstance', MagicMock(return_value=True))
    @patch('sfputil.main.is_port_type_rj45', MagicMock(return_value=False))
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('sfputil.main.platform_sfputil', MagicMock(is_logical_port=MagicMock(return_value=1)))
    @patch('sfputil.main.platform_chassis')
    def test_get_overall_offset_sff8472(self, mock_chassis):
        api = MagicMock()
        api.is_copper = MagicMock(return_value=False)
        mock_sfp = MagicMock()
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)

        mock_sfp.get_presence = MagicMock(return_value=True)
        mock_sfp.get_xcvr_api = MagicMock(return_value=api)
        
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['read-eeprom'],
                               ['-p', "Ethernet0", '-n', '0', '-o', '0', '-s', '1'])
        assert result.exit_code != 0
        print(result.output)
        
        result = runner.invoke(sfputil.cli.commands['read-eeprom'],
                               ['-p', "Ethernet0", '--wire-addr', 'invalid', '-n', '0', '-o', '0', '-s', '1'])
        assert result.exit_code != 0
        print(result.output)

        result = runner.invoke(sfputil.cli.commands['read-eeprom'],
                               ['-p', "Ethernet0", '--wire-addr', 'a0h', '-n', '1', '-o', '0', '-s', '1'])
        assert result.exit_code != 0
        print(result.output)

        result = runner.invoke(sfputil.cli.commands['read-eeprom'],
                               ['-p', "Ethernet0", '--wire-addr', 'A0h', '-n', '0', '-o', '-1', '-s', '1'])
        assert result.exit_code != 0
        print(result.output)
        
        result = runner.invoke(sfputil.cli.commands['read-eeprom'],
                               ['-p', "Ethernet0", '--wire-addr', 'A0h', '-n', '0', '-o', '256', '-s', '1'])
        assert result.exit_code != 0
        print(result.output)

        result = runner.invoke(sfputil.cli.commands['read-eeprom'], 
                               ['-p', "Ethernet0", '--wire-addr', 'A0h', '-n', '0', '-o', '0', '-s', '0'])
        assert result.exit_code != 0
        print(result.output)
        
        result = runner.invoke(sfputil.cli.commands['read-eeprom'],
                               ['-p', "Ethernet0", '--wire-addr', 'A0h', '-n', '0', '-o', '0', '-s', '257'])
        assert result.exit_code != 0
        print(result.output)
        
        assert sfputil.get_overall_offset_sff8472(api, 0, 2, 2, wire_addr='A0h') == 2
        
        result = runner.invoke(sfputil.cli.commands['read-eeprom'],
                               ['-p', "Ethernet0", '--wire-addr', 'a2h', '-n', '-1', '-o', '0', '-s', '1'])
        assert result.exit_code != 0
        print(result.output)
        
        result = runner.invoke(sfputil.cli.commands['read-eeprom'],
                               ['-p', "Ethernet0", '--wire-addr', 'a2h', '-n', '256', '-o', '0', '-s', '1'])
        assert result.exit_code != 0
        print(result.output)
        
        result = runner.invoke(sfputil.cli.commands['read-eeprom'],
                               ['-p', "Ethernet0", '--wire-addr', 'a2h', '-n', '0', '-o', '-1', '-s', '1'])
        assert result.exit_code != 0
        print(result.output)
        
        result = runner.invoke(sfputil.cli.commands['read-eeprom'],
                               ['-p', "Ethernet0", '--wire-addr', 'a2h', '-n', '0', '-o', '0', '-s', '0'])
        assert result.exit_code != 0
        print(result.output)
        
        result = runner.invoke(sfputil.cli.commands['read-eeprom'],
                               ['-p', "Ethernet0", '--wire-addr', 'a2h', '-n', '0', '-o', '0', '-s', '257'])
        assert result.exit_code != 0
        print(result.output)
        
        assert sfputil.get_overall_offset_sff8472(api, 0, 2, 2, wire_addr='A2h') == 258

    @patch('sfputil.main.platform_chassis')
    @patch('sfputil.main.logical_port_to_physical_port_index', MagicMock(return_value=1))
    def test_target_firmware(self, mock_chassis):
        mock_sfp = MagicMock()
        mock_api = MagicMock()
        mock_sfp.get_xcvr_api = MagicMock(return_value=mock_api)
        mock_sfp.get_presence.return_value = True
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        mock_api.set_firmware_download_target_end.return_value = 1
        runner = CliRunner()
        result = runner.invoke(sfputil.cli.commands['firmware'].commands['target'], ["Ethernet0", "2"])
        assert result.output == 'Target Mode set to 2\n'
        assert result.exit_code == 0

        mock_sfp.get_presence.return_value = False
        result = runner.invoke(sfputil.cli.commands['firmware'].commands['target'], ["Ethernet0", "2"])
        assert result.output == 'Ethernet0: SFP EEPROM not detected\n\n'

        mock_sfp.get_presence.return_value = True
        mock_sfp.get_xcvr_api = MagicMock(side_effect=NotImplementedError)
        result = runner.invoke(sfputil.cli.commands['firmware'].commands['target'], ["Ethernet0", "2"])
        assert result.output == 'Ethernet0: This functionality is currently not implemented for this module\n'
        assert result.exit_code == ERROR_NOT_IMPLEMENTED

        mock_sfp.get_xcvr_api = MagicMock(return_value=mock_api)
        mock_sfp.get_presence.return_value = True
        mock_api.set_firmware_download_target_end.return_value = 0
        result = runner.invoke(sfputil.cli.commands['firmware'].commands['target'], ["Ethernet0", "1"])
        assert result.output == 'Target Mode set failed!\n'
        assert result.exit_code == EXIT_FAIL

    @patch('sfputil.main.multi_asic.is_multi_asic')
    @patch('sfputil.main.platform_sfputil', MagicMock())
    @patch('sfputil.main.device_info.get_paths_to_platform_and_hwsku_dirs',
        MagicMock(return_value=(None, None)))
    @patch('sfputil.main.device_info.get_path_to_port_config_file', MagicMock(return_value=('')))
    def test_load_port_config(self, mock_is_multi_asic):
        mock_is_multi_asic.return_value = True
        assert sfputil.load_port_config() == True

        mock_is_multi_asic.return_value = False
        assert sfputil.load_port_config() == True

import os
import sys
from unittest import mock

import pytest
from click.testing import CliRunner
from utilities_common.general import load_module_from_source

from .mock_tables import dbconnector

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, 'scripts')
sys.path.insert(0, modules_path)

sys.modules['sonic_platform'] = mock.MagicMock()


decode_syseeprom_path = os.path.join(scripts_path, 'decode-syseeprom')
decode_syseeprom = load_module_from_source('decode_syseeprom', decode_syseeprom_path)

# Replace swsscommon objects with mocked objects
decode_syseeprom.SonicV2Connector = dbconnector.SonicV2Connector

SAMPLE_TLV_DICT = {
    'header': {
        'id': 'TlvInfo',
        'version': '1',
        'length': '170'
    },
    'tlv_list': [
        {
            'code': '0x21',
            'name': 'Product Name',
            'length': '8',
            'value': 'S6100-ON'
        },
        {
            'code': '0x22',
            'name': 'Part Number',
            'length': '6',
            'value': '0F6N2R'
        },
        {
            'code': '0x23',
            'name': 'Serial Number',
            'length': '20',
            'value': 'TH0F6N2RCET0007600NG'
        },
        {
            'code': '0x24',
            'name': 'Base MAC Address',
            'length': '6',
            'value': '0C:29:EF:CF:AC:A0'
        },
        {
            'code': '0x25',
            'name': 'Manufacture Date',
            'length': '19',
            'value': '07/07/2020 15:05:34'
        },
        {
            'code': '0x26',
            'name': 'Device Version',
            'length': '1',
            'value': '1'
        },
        {
            'code': '0x27',
            'name': 'Label Revision',
            'length': '3',
            'value': 'A08'
        },
        {
            'code': '0x28',
            'name': 'Platform Name',
            'length': '26',
            'value': 'x86_64-dell_s6100_c2538-r0'
        },
        {
            'code': '0x29',
            'name': 'ONIE Version',
            'length': '8',
            'value': '3.15.1.0'
        },
        {
            'code': '0x2A',
            'name': 'MAC Addresses',
            'length': '2',
            'value': '384'
        },
        {
            'code': '0x2B',
            'name': 'Manufacturer',
            'length': '5',
            'value': 'CET00'
        },
        {
            'code': '0x2C',
            'name': 'Manufacture Country',
            'length': '2',
            'value': 'TH'
        },
        {
            'code': '0x2D',
            'name': 'Vendor Name',
            'length': '4',
            'value': 'DELL'
        },
        {
            'code': '0x2E',
            'name': 'Diag Version',
            'length': '8',
            'value': '3.25.4.1'
        },
        {
            'code': '0x2F',
            'name': 'Service Tag',
            'length': '7',
            'value': 'F3CD9Z2'
        },
        {
            'code': '0xFD',
            'name': 'Vendor Extension',
            'length': '7',
            'value': ''
        },
        {
            'code': '0xFE',
            'name': 'CRC-32',
            'length': '4',
            'value': '0xAC518FB3'
        }
    ],
    'checksum_valid': True
}

class TestDecodeSyseeprom(object):
    def test_print_eeprom_dict(self, capsys):

        expected_output = '''\
TlvInfo Header:
   Id String:    TlvInfo
   Version:      1
   Total Length: 170
TLV Name             Code      Len  Value
-------------------  ------  -----  --------------------------
Product Name         0x21        8  S6100-ON
Part Number          0x22        6  0F6N2R
Serial Number        0x23       20  TH0F6N2RCET0007600NG
Base MAC Address     0x24        6  0C:29:EF:CF:AC:A0
Manufacture Date     0x25       19  07/07/2020 15:05:34
Device Version       0x26        1  1
Label Revision       0x27        3  A08
Platform Name        0x28       26  x86_64-dell_s6100_c2538-r0
ONIE Version         0x29        8  3.15.1.0
MAC Addresses        0x2A        2  384
Manufacturer         0x2B        5  CET00
Manufacture Country  0x2C        2  TH
Vendor Name          0x2D        4  DELL
Diag Version         0x2E        8  3.25.4.1
Service Tag          0x2F        7  F3CD9Z2
Vendor Extension     0xFD        7
CRC-32               0xFE        4  0xAC518FB3

(checksum valid)
'''

        decode_syseeprom.print_eeprom_dict(SAMPLE_TLV_DICT)
        captured = capsys.readouterr()
        assert captured.out == expected_output

    def test_read_eeprom_from_db(self):
        tlv_dict = decode_syseeprom.read_eeprom_from_db()
        assert tlv_dict == SAMPLE_TLV_DICT

    def test_get_tlv_value_from_db(self):
        value = decode_syseeprom.get_tlv_value_from_db(0x28)
        assert value == 'x86_64-dell_s6100_c2538-r0'

    def test_print_mgmt_mac_db(self, capsys):
        decode_syseeprom.print_mgmt_mac(True)
        captured = capsys.readouterr()
        assert captured.out == '0C:29:EF:CF:AC:A0\n'

    def test_print_serial(self, capsys):
        decode_syseeprom.print_serial(True)
        captured = capsys.readouterr()
        assert captured.out == 'TH0F6N2RCET0007600NG\n'

    def test_print_model(self, capsys):
        decode_syseeprom.print_model(True)
        captured = capsys.readouterr()
        assert captured.out == 'S6100-ON\n'

    @mock.patch('os.geteuid', lambda: 0)
    @mock.patch('sonic_py_common.device_info.get_platform', lambda: 'arista')
    @mock.patch.object(sys, 'argv', ["decode-syseeprom"])
    @mock.patch('decode_syseeprom.read_and_print_eeprom')
    @mock.patch('decode_syseeprom.read_eeprom_from_db')
    def test_support_platforms_not_db_based(self, mockDbBased, mockNotDbBased):
        decode_syseeprom.main()
        assert mockNotDbBased.called
        assert not mockDbBased.called

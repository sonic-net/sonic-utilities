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

# Load the file under test
psushow_path = os.path.join(scripts_path, 'psushow')
psushow = load_module_from_source('psushow', psushow_path)

# Replace swsscommon objects with mocked objects
psushow.SonicV2Connector = dbconnector.SonicV2Connector


class TestPsushow(object):
    def test_get_psu_status_list(self):
        expected_psu_status_list = [
            {
                'index': '1',
                'name': 'PSU 1',
                'presence': 'true',
                'status': 'WARNING',
                'led_status': 'green',
                'model': '0J6J4K',
                'serial': 'CN-0J6J4K-17972-5AF-0086-A00',
                'revision': '1',
                'voltage': '12.19',
                'current': '8.37',
                'power': '102.7'
            },
            {
                'index': '2',
                'name': 'PSU 2',
                'presence': 'true',
                'status': 'OK',
                'led_status': 'green',
                'model': '0J6J4K',
                'serial': 'CN-0J6J4K-17972-5AF-008M-A00',
                'revision': 'A',
                'voltage': '12.18',
                'current': '10.07',
                'power': '122.0'
            }
        ]

        psu_status_list = psushow.get_psu_status_list()
        assert psu_status_list == expected_psu_status_list

    def test_status_table(self, capsys):
        expected_output = '''\
PSU    Model    Serial                        HW Rev      Voltage (V)    Current (A)    Power (W)  Status    LED
-----  -------  ----------------------------  --------  -------------  -------------  -----------  --------  -----
PSU 1  0J6J4K   CN-0J6J4K-17972-5AF-0086-A00  1                 12.19           8.37       102.70  WARNING   green
PSU 2  0J6J4K   CN-0J6J4K-17972-5AF-008M-A00  A                 12.18          10.07       122.00  OK        green
'''
        for arg in ['-s', '--status']:
            with mock.patch('sys.argv', ['psushow', arg]):
                ret = psushow.main()
            assert ret == 0
            captured = capsys.readouterr()
            assert captured.out == expected_output

        expected_output = '''\
PSU    Model    Serial                          HW Rev    Voltage (V)    Current (A)    Power (W)  Status    LED
-----  -------  ----------------------------  --------  -------------  -------------  -----------  --------  -----
PSU 1  0J6J4K   CN-0J6J4K-17972-5AF-0086-A00         1          12.19           8.37       102.70  WARNING   green
'''
        for arg in ['-s', '--status']:
            with mock.patch('sys.argv', ['psushow', arg, '-i', '1']):
                ret = psushow.main()
            assert ret == 0
            captured = capsys.readouterr()
            assert captured.out == expected_output

        expected_output = '''\
PSU    Model    Serial                        HW Rev      Voltage (V)    Current (A)    Power (W)  Status    LED
-----  -------  ----------------------------  --------  -------------  -------------  -----------  --------  -----
PSU 2  0J6J4K   CN-0J6J4K-17972-5AF-008M-A00  A                 12.18          10.07       122.00  OK        green
'''
        for arg in ['-s', '--status']:
            with mock.patch('sys.argv', ['psushow', arg, '-i', '2']):
                ret = psushow.main()
            assert ret == 0
            captured = capsys.readouterr()
            assert captured.out == expected_output

        # Test trying to display a non-existent PSU
        expected_output = '''\
Error: PSU 3 is not available. Number of supported PSUs: 2
PSU not detected
'''
        for arg in ['-s', '--status']:
            with mock.patch('sys.argv', ['psushow', arg, '-i', '3']):
                ret = psushow.main()
            assert ret == 1
            captured = capsys.readouterr()
            assert captured.out == expected_output

    def test_status_json(self, capsys):
        expected_output = '''\
[
    {
        "index": "1",
        "name": "PSU 1",
        "presence": "true",
        "status": "WARNING",
        "led_status": "green",
        "model": "0J6J4K",
        "serial": "CN-0J6J4K-17972-5AF-0086-A00",
        "revision": "1",
        "voltage": "12.19",
        "current": "8.37",
        "power": "102.7"
    },
    {
        "index": "2",
        "name": "PSU 2",
        "presence": "true",
        "status": "OK",
        "led_status": "green",
        "model": "0J6J4K",
        "serial": "CN-0J6J4K-17972-5AF-008M-A00",
        "revision": "A",
        "voltage": "12.18",
        "current": "10.07",
        "power": "122.0"
    }
]
'''
        for arg in ['-j', '--json']:
            with mock.patch('sys.argv', ['psushow', '-s', arg]):
                ret = psushow.main()
            assert ret == 0
            captured = capsys.readouterr()
            assert captured.out == expected_output

        expected_output = '''\
[
    {
        "index": "1",
        "name": "PSU 1",
        "presence": "true",
        "status": "WARNING",
        "led_status": "green",
        "model": "0J6J4K",
        "serial": "CN-0J6J4K-17972-5AF-0086-A00",
        "revision": "1",
        "voltage": "12.19",
        "current": "8.37",
        "power": "102.7"
    }
]
'''
        for arg in ['-j', '--json']:
            with mock.patch('sys.argv', ['psushow', '-s', '-i', '1', arg]):
                ret = psushow.main()
            assert ret == 0
            captured = capsys.readouterr()
            assert captured.out == expected_output

        expected_output = '''\
[
    {
        "index": "2",
        "name": "PSU 2",
        "presence": "true",
        "status": "OK",
        "led_status": "green",
        "model": "0J6J4K",
        "serial": "CN-0J6J4K-17972-5AF-008M-A00",
        "revision": "A",
        "voltage": "12.18",
        "current": "10.07",
        "power": "122.0"
    }
]
'''
        for arg in ['-j', '--json']:
            with mock.patch('sys.argv', ['psushow', '-s', '-i', '2', arg]):
                ret = psushow.main()
            assert ret == 0
            captured = capsys.readouterr()
            assert captured.out == expected_output

        # Test trying to display a non-existent PSU
        expected_output = '''\
Error: PSU 3 is not available. Number of supported PSUs: 2
PSU not detected
'''
        for arg in ['-j', '--json']:
            with mock.patch('sys.argv', ['psushow', '-s', '-i', '3', arg]):
                ret = psushow.main()
            assert ret == 1
            captured = capsys.readouterr()
            assert captured.out == expected_output

    def test_version(self, capsys):
        for arg in ['-v', '--version']:
            with pytest.raises(SystemExit) as pytest_wrapped_e:
                with mock.patch('sys.argv', ['psushow', arg]):
                    psushow.main()
            assert pytest_wrapped_e.type == SystemExit
            assert pytest_wrapped_e.value.code == 0
            captured = capsys.readouterr()
            assert captured.out == 'psushow {}\n'.format(psushow.VERSION)

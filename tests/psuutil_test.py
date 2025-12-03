import sys
import os
from sonic_platform_base import device_base
from unittest import mock

import pytest
from click.testing import CliRunner

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)

sys.modules['sonic_platform'] = mock.MagicMock()
import psuutil.main as psuutil

STATUS_OUTPUT = '''\
PSU    Model        Serial    HW Rev      Voltage (V)    Current (A)    Power (W)    Power Warn-supp Thres (W)    Power Crit Thres (W)  Status    LED
-----  -----------  --------  --------  -------------  -------------  -----------  ---------------------------  ----------------------  --------  -----
PSU 1  SampleModel  S001      Rev A             12.00          10.00       120.00                        90.00                  100.00  OK        green
'''

STATUS_OUTPUT_NOT_IMPLEMENT = '''\
PSU    Model        Serial    HW Rev      Voltage (V)    Current (A)    Power (W)  Power Warn-supp Thres (W)    Power Crit Thres (W)    Status    LED
-----  -----------  --------  --------  -------------  -------------  -----------  ---------------------------  ----------------------  --------  -----
PSU 1  SampleModel  S001      N/A               12.00          10.00       120.00  N/A                          N/A                     OK        green
'''

class TestPsuutil(object):

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(psuutil.cli.commands['version'], [])
        assert result.output.rstrip() == 'psuutil version {}'.format(psuutil.VERSION)

    @mock.patch('psuutil.main.load_platform_chassis', mock.MagicMock(return_value=True))
    @mock.patch('psuutil.main.platform_chassis')
    def test_psuutil_status(self, platform_chassis):
        psu = mock.MagicMock()
        psu.get_name = mock.MagicMock(return_value='PSU 1')
        psu.get_presence = mock.MagicMock(return_value=True)
        psu.get_powergood_status = mock.MagicMock(return_value=True)
        psu.get_psu_power_critical_threshold = mock.MagicMock(return_value=100.0)
        psu.get_psu_power_warning_suppress_threshold = mock.MagicMock(return_value=90.0)
        psu.get_model = mock.MagicMock(return_value='SampleModel')
        psu.get_serial = mock.MagicMock(return_value='S001')
        psu.get_revision = mock.MagicMock(return_value='Rev A')
        psu.get_voltage = mock.MagicMock(return_value=12.0)
        psu.get_current = mock.MagicMock(return_value=10.0)
        psu.get_power = mock.MagicMock(return_value=120.0)
        psu.get_status_led = mock.MagicMock(return_value='green')

        psu_list = [psu]
        platform_chassis.get_all_psus = mock.MagicMock(return_value=psu_list)

        runner = CliRunner()
        result = runner.invoke(psuutil.cli.commands['status'])
        assert result.output == STATUS_OUTPUT

        psu.get_psu_power_critical_threshold = mock.MagicMock(side_effect=NotImplementedError(''))
        psu.get_revision = mock.MagicMock(side_effect=NotImplementedError(''))
        runner = CliRunner()
        result = runner.invoke(psuutil.cli.commands['status'])
        assert result.output == STATUS_OUTPUT_NOT_IMPLEMENT

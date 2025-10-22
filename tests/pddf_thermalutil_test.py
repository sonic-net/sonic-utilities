"""
Unit tests for pddf_thermalutil
"""

import sys
import os
import re
from unittest import mock
from click.testing import CliRunner
from pddf_thermalutil.main import cli

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)


class MockThermal:
    """Mock thermal sensor for testing"""

    def __init__(self, name, temp=None, high=None, crit=None, label=None):
        self._name = name
        self._temp = temp
        self._high = high
        self._crit = crit
        self._label = label

    def get_name(self):
        return self._name

    def get_temperature(self):
        return self._temp

    def get_high_threshold(self):
        return self._high

    def get_high_critical_threshold(self):
        return self._crit

    def get_temp_label(self):
        return self._label


class MockThermalNotImplemented:
    """Mock thermal sensor that raises NotImplementedError"""

    def __init__(self, name):
        self._name = name

    def get_name(self):
        return self._name

    def get_temperature(self):
        raise NotImplementedError()

    def get_high_threshold(self):
        raise NotImplementedError()

    def get_high_critical_threshold(self):
        raise NotImplementedError()

    def get_temp_label(self):
        raise NotImplementedError()


class TestPddfThermalutil:
    """Test cases for pddf_thermalutil gettemp command"""

    def test_gettemp_with_na_temperature(self):
        """Test that missing temperature shows N/A"""
        mock_thermals = [
            MockThermal("TEMP1", temp=None, high=120.0, crit=130.0, label=None),
        ]

        with mock.patch("pddf_thermalutil.main.platform_chassis") as mock_chassis:
            mock_chassis.get_all_thermals.return_value = mock_thermals

            runner = CliRunner()
            result = runner.invoke(cli.commands["gettemp"])

            expected_output = """\
Temp Sensor    Value
-------------  --------------------------------------
TEMP1          N/A (high = +120.0 C, crit = +130.0 C)
"""

            assert result.exit_code == 0
            assert expected_output == result.output

    def test_gettemp_with_na_thresholds(self):
        """Test that missing thresholds show N/A"""
        mock_thermals = [
            MockThermal("TEMP1", temp=35.0, high=None, crit=None, label=None),
        ]

        with mock.patch("pddf_thermalutil.main.platform_chassis") as mock_chassis:
            mock_chassis.get_all_thermals.return_value = mock_thermals

            runner = CliRunner()
            result = runner.invoke(cli.commands["gettemp"])

            expected_output = """\
Temp Sensor    Value
-------------  -------
TEMP1          temp1\t +35.0 C (high = N/A, crit = N/A)
"""

            assert result.exit_code == 0
            assert expected_output == result.output

    def test_gettemp_with_all_na(self):
        """Test that all missing values show N/A"""
        mock_thermals = [
            MockThermal("TEMP1", temp=None, high=None, crit=None, label=None),
        ]

        with mock.patch("pddf_thermalutil.main.platform_chassis") as mock_chassis:
            mock_chassis.get_all_thermals.return_value = mock_thermals

            runner = CliRunner()
            result = runner.invoke(cli.commands["gettemp"])

            expected_output = """\
Temp Sensor    Value
-------------  ----------------------------
TEMP1          N/A (high = N/A, crit = N/A)
"""
            assert result.exit_code == 0
            assert expected_output == result.output

    def test_gettemp_zero_temperature(self):
        """Test that 0°C is handled correctly (not shown as N/A)"""
        mock_thermals = [
            MockThermal("TEMP1", temp=0.0, high=120.0, crit=130.0, label=None),
        ]

        with mock.patch("pddf_thermalutil.main.platform_chassis") as mock_chassis:
            mock_chassis.get_all_thermals.return_value = mock_thermals

            runner = CliRunner()
            result = runner.invoke(cli.commands["gettemp"])

            expected_output = """\
Temp Sensor    Value
-------------  -------
TEMP1          temp1\t +0.0 C (high = +120.0 C, crit = +130.0 C)
"""
            assert result.exit_code == 0
            assert expected_output == result.output

    def test_gettemp_with_labels(self):
        """Test sensors with labels produce correct header"""
        mock_thermals = [
            MockThermal("TEMP1", temp=35.0, high=120.0, crit=130.0, label="CPU Temp"),
            MockThermal("TEMP2", temp=36.0, high=120.0, crit=130.0, label="Board Temp"),
        ]

        with mock.patch("pddf_thermalutil.main.platform_chassis") as mock_chassis:
            mock_chassis.get_all_thermals.return_value = mock_thermals

            runner = CliRunner()
            result = runner.invoke(cli.commands["gettemp"])

            expected_output = """\
Temp Sensor    Label       Value
-------------  ----------  -------
TEMP1          CPU Temp    temp1\t +35.0 C (high = +120.0 C, crit = +130.0 C)
TEMP2          Board Temp  temp1\t +36.0 C (high = +120.0 C, crit = +130.0 C)
"""
            assert result.exit_code == 0
            assert expected_output == result.output

    def test_gettemp_without_labels(self):
        """Test sensors without labels produce correct header"""
        mock_thermals = [
            MockThermal("TEMP1", temp=35.0, high=120.0, crit=130.0, label=None),
            MockThermal("TEMP2", temp=36.0, high=120.0, crit=130.0, label=None),
        ]

        with mock.patch("pddf_thermalutil.main.platform_chassis") as mock_chassis:
            mock_chassis.get_all_thermals.return_value = mock_thermals

            runner = CliRunner()
            result = runner.invoke(cli.commands["gettemp"])

            expected_output = """\
Temp Sensor    Value
-------------  -------
TEMP1          temp1\t +35.0 C (high = +120.0 C, crit = +130.0 C)
TEMP2          temp1\t +36.0 C (high = +120.0 C, crit = +130.0 C)
"""
            assert result.exit_code == 0
            assert expected_output == result.output

    def test_gettemp_mixed_labels(self):
        """Test that header is correct when some sensors have labels and some don't"""
        mock_thermals = [
            MockThermal("TEMP1", temp=35.0, high=120.0, crit=130.0, label=None),
            MockThermal("TEMP2", temp=36.0, high=120.0, crit=130.0, label="CPU Temp"),
            MockThermal("TEMP3", temp=37.0, high=120.0, crit=130.0, label=None),
        ]

        with mock.patch("pddf_thermalutil.main.platform_chassis") as mock_chassis:
            mock_chassis.get_all_thermals.return_value = mock_thermals

            runner = CliRunner()
            result = runner.invoke(cli.commands["gettemp"])

            expected_output = """\
Temp Sensor    Label     Value
-------------  --------  -------
TEMP1                    temp1\t +35.0 C (high = +120.0 C, crit = +130.0 C)
TEMP2          CPU Temp  temp1\t +36.0 C (high = +120.0 C, crit = +130.0 C)
TEMP3                    temp1\t +37.0 C (high = +120.0 C, crit = +130.0 C)
"""
            assert result.exit_code == 0
            assert expected_output == result.output

    def test_gettemp_not_implemented_error(self):
        """Test handling of NotImplementedError"""
        mock_thermals = [
            MockThermal("TEMP1", temp=35.0, high=120.0, crit=130.0, label=None),
            MockThermalNotImplemented("TEMP2"),
            MockThermal("TEMP3", temp=37.0, high=120.0, crit=130.0, label=None),
        ]

        with mock.patch("pddf_thermalutil.main.platform_chassis") as mock_chassis:
            mock_chassis.get_all_thermals.return_value = mock_thermals

            runner = CliRunner()
            result = runner.invoke(cli.commands["gettemp"])

            expected_output = """\
Temp Sensor    Value
-------------  -------
TEMP1          temp1\t +35.0 C (high = +120.0 C, crit = +130.0 C)
TEMP2          N/A
TEMP3          temp1\t +37.0 C (high = +120.0 C, crit = +130.0 C)
"""
            assert result.exit_code == 0
            assert expected_output == result.output

    def test_gettemp_empty_sensor_list(self):
        """Test with no thermal sensors"""
        mock_thermals = []

        with mock.patch("pddf_thermalutil.main.platform_chassis") as mock_chassis:
            mock_chassis.get_all_thermals.return_value = mock_thermals

            runner = CliRunner()
            result = runner.invoke(cli.commands["gettemp"])

            # Should complete without error, just no output
            assert result.exit_code == 0
            expected_output = ""
            assert expected_output == result.output

    def test_gettemp_partial_thresholds(self):
        """Test sensors with only high threshold (no critical)"""
        mock_thermals = [
            MockThermal("TEMP1", temp=35.0, high=120.0, crit=None, label=None),
        ]

        with mock.patch("pddf_thermalutil.main.platform_chassis") as mock_chassis:
            mock_chassis.get_all_thermals.return_value = mock_thermals

            runner = CliRunner()
            result = runner.invoke(cli.commands["gettemp"])

            expected_output = """\
Temp Sensor    Value
-------------  -------
TEMP1          temp1\t +35.0 C (high = +120.0 C, crit = N/A)
"""
            assert result.exit_code == 0
            assert expected_output == result.output

    def test_gettemp_mixed_zero_temperaturs(self):
        """
        Test a realistic scenario with multiple DCDC and ASIC sensors
        matching the original bug report
        """
        mock_thermals = [
            # DCDC sensors
            MockThermal("DCDC0", temp=35.0, high=120.0, crit=130.0, label=None),
            MockThermal("DCDC1", temp=36.0, high=120.0, crit=130.0, label=None),
            MockThermal("DCDC2", temp=35.5, high=120.0, crit=130.0, label=None),
            MockThermal("DCDC3", temp=36.5, high=120.0, crit=130.0, label=None),
            MockThermal("DCDC4", temp=35.2, high=120.0, crit=130.0, label=None),
            MockThermal("DCDC5", temp=36.2, high=120.0, crit=130.0, label=None),
            MockThermal("DCDC6", temp=35.8, high=120.0, crit=130.0, label=None),
            MockThermal("DCDC7", temp=36.8, high=120.0, crit=130.0, label=None),
            MockThermal("DCDC8", temp=35.3, high=120.0, crit=130.0, label=None),
            MockThermal("DCDC9", temp=36.3, high=120.0, crit=130.0, label=None),
            # ASIC sensors
            MockThermal("ASIC 1", temp=0.0, high=105.0, crit=115.0, label=None),
            MockThermal("ASIC 2", temp=37.0, high=105.0, crit=115.0, label=None),
            MockThermal("ASIC 3", temp=0.0, high=105.0, crit=115.0, label=None),
            MockThermal("ASIC 4", temp=39.0, high=105.0, crit=115.0, label=None),
            MockThermal("ASIC 5", temp=40.0, high=105.0, crit=115.0, label=None),
        ]

        with mock.patch("pddf_thermalutil.main.platform_chassis") as mock_chassis:
            mock_chassis.get_all_thermals.return_value = mock_thermals

            runner = CliRunner()
            result = runner.invoke(cli.commands["gettemp"])

            expected_output = """\
Temp Sensor    Value
-------------  -------
DCDC0          temp1\t +35.0 C (high = +120.0 C, crit = +130.0 C)
DCDC1          temp1\t +36.0 C (high = +120.0 C, crit = +130.0 C)
DCDC2          temp1\t +35.5 C (high = +120.0 C, crit = +130.0 C)
DCDC3          temp1\t +36.5 C (high = +120.0 C, crit = +130.0 C)
DCDC4          temp1\t +35.2 C (high = +120.0 C, crit = +130.0 C)
DCDC5          temp1\t +36.2 C (high = +120.0 C, crit = +130.0 C)
DCDC6          temp1\t +35.8 C (high = +120.0 C, crit = +130.0 C)
DCDC7          temp1\t +36.8 C (high = +120.0 C, crit = +130.0 C)
DCDC8          temp1\t +35.3 C (high = +120.0 C, crit = +130.0 C)
DCDC9          temp1\t +36.3 C (high = +120.0 C, crit = +130.0 C)
ASIC 1         temp1\t +0.0 C (high = +105.0 C, crit = +115.0 C)
ASIC 2         temp1\t +37.0 C (high = +105.0 C, crit = +115.0 C)
ASIC 3         temp1\t +0.0 C (high = +105.0 C, crit = +115.0 C)
ASIC 4         temp1\t +39.0 C (high = +105.0 C, crit = +115.0 C)
ASIC 5         temp1\t +40.0 C (high = +105.0 C, crit = +115.0 C)
"""
            assert result.exit_code == 0
            assert expected_output == result.output

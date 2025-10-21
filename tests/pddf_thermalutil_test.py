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

    def test_gettemp_no_duplicates_mixed_sensors(self):
        """
        Test that gettemp doesn't produce duplicate threshold strings
        when mixing DCDC and ASIC sensors (the original bug scenario)
        """
        # Simulate DCDC sensors followed by ASIC sensors
        mock_thermals = [
            MockThermal("DCDC0", temp=35.0, high=120.0, crit=130.0, label=None),
            MockThermal("DCDC1", temp=36.0, high=120.0, crit=130.0, label=None),
            MockThermal("ASIC 1", temp=36.0, high=105.0, crit=115.0, label=None),
            MockThermal("ASIC 2", temp=37.0, high=105.0, crit=115.0, label=None),
            MockThermal("ASIC 3", temp=38.0, high=105.0, crit=115.0, label=None),
        ]

        with mock.patch("pddf_thermalutil.main.platform_chassis") as mock_chassis:
            mock_chassis.get_all_thermals.return_value = mock_thermals

            runner = CliRunner()
            result = runner.invoke(cli.commands["gettemp"])

            # Verify no duplicate threshold strings
            assert result.exit_code == 0
            output_lines = result.output.strip().split("\n")

            # Check each sensor line (skip header)
            for line in output_lines[2:]:  # Skip header lines
                # Count occurrences of "high =" - should be exactly 1 per line
                high_count = line.count("high =")
                assert high_count == 1, f"Line has {high_count} 'high =' occurrences (expected 1): {line}"

                # Count occurrences of "crit =" - should be exactly 1 per line
                crit_count = line.count("crit =")
                assert crit_count == 1, f"Line has {crit_count} 'crit =' occurrences (expected 1): {line}"

                # Should not have duplicate closing parentheses
                assert "))" not in line, f"Line has duplicate closing parentheses: {line}"

    def test_gettemp_with_na_temperature(self):
        """Test that missing temperature shows N/A"""
        mock_thermals = [
            MockThermal("TEMP1", temp=None, high=120.0, crit=130.0, label=None),
        ]

        with mock.patch("pddf_thermalutil.main.platform_chassis") as mock_chassis:
            mock_chassis.get_all_thermals.return_value = mock_thermals

            runner = CliRunner()
            result = runner.invoke(cli.commands["gettemp"])

            assert result.exit_code == 0
            assert "N/A (" in result.output
            assert "high = +120.0 C" in result.output

    def test_gettemp_with_na_thresholds(self):
        """Test that missing thresholds show N/A"""
        mock_thermals = [
            MockThermal("TEMP1", temp=35.0, high=None, crit=None, label=None),
        ]

        with mock.patch("pddf_thermalutil.main.platform_chassis") as mock_chassis:
            mock_chassis.get_all_thermals.return_value = mock_thermals

            runner = CliRunner()
            result = runner.invoke(cli.commands["gettemp"])

            assert result.exit_code == 0
            assert "temp1\t +35.0 C" in result.output
            assert "high = N/A" in result.output
            assert "crit = N/A" in result.output

    def test_gettemp_with_all_na(self):
        """Test that all missing values show N/A"""
        mock_thermals = [
            MockThermal("TEMP1", temp=None, high=None, crit=None, label=None),
        ]

        with mock.patch("pddf_thermalutil.main.platform_chassis") as mock_chassis:
            mock_chassis.get_all_thermals.return_value = mock_thermals

            runner = CliRunner()
            result = runner.invoke(cli.commands["gettemp"])

            assert result.exit_code == 0
            assert "N/A (high = N/A, crit = N/A)" in result.output

    def test_gettemp_zero_temperature(self):
        """Test that 0°C is handled correctly (not shown as N/A)"""
        mock_thermals = [
            MockThermal("TEMP1", temp=0.0, high=120.0, crit=130.0, label=None),
        ]

        with mock.patch("pddf_thermalutil.main.platform_chassis") as mock_chassis:
            mock_chassis.get_all_thermals.return_value = mock_thermals

            runner = CliRunner()
            result = runner.invoke(cli.commands["gettemp"])

            assert result.exit_code == 0
            # Should show temperature as 0.0, not N/A
            assert "temp1\t +0.0 C" in result.output
            assert "N/A (" not in result.output

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

            assert result.exit_code == 0
            # Should have 3-column header
            assert "Temp Sensor" in result.output
            assert "Label" in result.output
            assert "Value" in result.output
            assert "CPU Temp" in result.output
            assert "Board Temp" in result.output

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

            assert result.exit_code == 0
            # Should have 2-column header (no Label column)
            assert "Temp Sensor" in result.output
            assert "Value" in result.output
            # Count columns in header - should not have "Label"
            header_line = result.output.split("\n")[0]
            assert "Label" not in header_line

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

            assert result.exit_code == 0
            # Should have 3-column header because at least one sensor has a label
            assert "Temp Sensor" in result.output
            assert "Label" in result.output
            assert "Value" in result.output

            # Verify the table structure - all rows should have 3 columns
            output_lines = result.output.split("\n")
            # Find the data rows (skip header and separator)
            temp1_line = [line for line in output_lines if "TEMP1" in line][0]
            temp2_line = [line for line in output_lines if "TEMP2" in line][0]
            temp3_line = [line for line in output_lines if "TEMP3" in line][0]

            # TEMP2 should have "CPU Temp" in the label column
            assert "CPU Temp" in temp2_line

            # All rows should have the same number of columns (aligned)
            # Split by multiple spaces to get columns
            temp1_cols = [col for col in re.split(r"\s{2,}", temp1_line.strip()) if col]
            temp2_cols = [col for col in re.split(r"\s{2,}", temp2_line.strip()) if col]
            temp3_cols = [col for col in re.split(r"\s{2,}", temp3_line.strip()) if col]

            assert len(temp1_cols) == 3, f"TEMP1 should have 3 columns, got {len(temp1_cols)}: {temp1_cols}"
            assert len(temp2_cols) == 4, f"TEMP2 should have 4 columns, got {len(temp2_cols)}: {temp2_cols}"
            assert len(temp3_cols) == 3, f"TEMP3 should have 3 columns, got {len(temp3_cols)}: {temp3_cols}"

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

            assert result.exit_code == 0
            # Sensor with NotImplementedError should show N/A
            output_lines = result.output.split("\n")
            temp2_line = [line for line in output_lines if "TEMP2" in line]
            assert len(temp2_line) == 1
            assert "N/A" in temp2_line[0]

    def test_gettemp_empty_sensor_list(self):
        """Test with no thermal sensors"""
        mock_thermals = []

        with mock.patch("pddf_thermalutil.main.platform_chassis") as mock_chassis:
            mock_chassis.get_all_thermals.return_value = mock_thermals

            runner = CliRunner()
            result = runner.invoke(cli.commands["gettemp"])

            # Should complete without error, just no output
            assert result.exit_code == 0

    def test_gettemp_partial_thresholds(self):
        """Test sensors with only high threshold (no critical)"""
        mock_thermals = [
            MockThermal("TEMP1", temp=35.0, high=120.0, crit=None, label=None),
        ]

        with mock.patch("pddf_thermalutil.main.platform_chassis") as mock_chassis:
            mock_chassis.get_all_thermals.return_value = mock_thermals

            runner = CliRunner()
            result = runner.invoke(cli.commands["gettemp"])

            assert result.exit_code == 0
            assert "temp1\t +35.0 C" in result.output
            assert "high = +120.0 C" in result.output
            assert "crit = N/A" in result.output

    def test_gettemp_regression_no_accumulation(self):
        """
        Regression test: Verify that running gettemp multiple times
        doesn't cause accumulation (tests for state persistence bugs)
        """
        mock_thermals = [
            MockThermal("TEMP1", temp=35.0, high=120.0, crit=130.0, label=None),
        ]

        with mock.patch("pddf_thermalutil.main.platform_chassis") as mock_chassis:
            mock_chassis.get_all_thermals.return_value = mock_thermals

            runner = CliRunner()

            # Run multiple times
            result1 = runner.invoke(cli.commands["gettemp"])
            result2 = runner.invoke(cli.commands["gettemp"])
            result3 = runner.invoke(cli.commands["gettemp"])

            # All outputs should be identical
            assert result1.output == result2.output
            assert result2.output == result3.output

            # Verify no duplicates in any run
            for result in [result1, result2, result3]:
                assert result.exit_code == 0
                assert result.output.count("high = +120.0 C") == 1
                assert result.output.count("crit = +130.0 C") == 1

    def test_gettemp_realistic_scenario(self):
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

            assert result.exit_code == 0

            # Verify each sensor appears exactly once
            for thermal in mock_thermals:
                assert result.output.count(thermal.get_name()) == 1

            # Verify DCDC sensors have correct thresholds
            dcdc_lines = [line for line in result.output.split("\n") if "DCDC" in line]
            for line in dcdc_lines:
                assert "high = +120.0 C" in line
                assert "crit = +130.0 C" in line
                # Should appear exactly once per line
                assert line.count("high = +120.0 C") == 1
                assert line.count("crit = +130.0 C") == 1

            # Verify ASIC sensors have correct thresholds
            asic_lines = [line for line in result.output.split("\n") if "ASIC" in line]
            for line in asic_lines:
                assert "high = +105.0 C" in line
                assert "crit = +115.0 C" in line
                # Should appear exactly once per line
                assert line.count("high = +105.0 C") == 1
                assert line.count("crit = +115.0 C") == 1

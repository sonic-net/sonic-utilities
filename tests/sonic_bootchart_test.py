import os
import pytest
from click.testing import CliRunner
from unittest.mock import patch, Mock
import utilities_common
from .utils import load_source


sonic_bootchart = load_source('sonic-bootchart', 'scripts/sonic-bootchart', cache_module=True)

BOOTCHART_OUTPUT_FILES = [
    os.path.join(sonic_bootchart.BOOTCHART_DEFAULT_OUTPUT_DIR, "bootchart-20220504-1040.svg"),
    os.path.join(sonic_bootchart.BOOTCHART_DEFAULT_OUTPUT_DIR, "bootchart-20220504-1045.svg"),
]

@pytest.fixture(autouse=True)
def setup(fs):
    # create required file for bootchart installation check
    fs.create_file(sonic_bootchart.SYSTEMD_BOOTCHART)
    fs.create_file(sonic_bootchart.BOOTCHART_CONF)
    for bootchart_output_file in BOOTCHART_OUTPUT_FILES:
        fs.create_file(bootchart_output_file)

    with open(sonic_bootchart.BOOTCHART_CONF, 'w') as config_file:
        config_file.write("""
        [Bootchart]
        Samples=500
        Frequency=25
        """)

    # pass the root user check
    with patch("os.geteuid") as mock:
        mock.return_value = 0
        yield


@patch("utilities_common.cli.run_command")
class TestSonicBootchart:
    def test_enable(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(sonic_bootchart.cli.commands['enable'], [])
        assert not result.exit_code
        mock_run_command.assert_called_with(['systemctl', 'enable', 'systemd-bootchart'], display_cmd=True)

    def test_disable(self, mock_run_command):
        runner = CliRunner()
        result = runner.invoke(sonic_bootchart.cli.commands['disable'], [])
        assert not result.exit_code
        mock_run_command.assert_called_with(['systemctl', 'disable', 'systemd-bootchart'], display_cmd=True)

    def test_config_show(self, mock_run_command):
        def run_command_side_effect(command, **kwargs):
            if "is-enabled" in command:
                return "enabled", 0
            elif "is-active" in command:
                return "active", 0
            else:
                raise Exception("unknown command")

        mock_run_command.side_effect = run_command_side_effect

        runner = CliRunner()
        result = runner.invoke(sonic_bootchart.cli.commands['show'], [])
        assert not result.exit_code
        assert result.output == \
                "Status    Operational Status      Frequency    Time (sec)  Output\n"                               \
                "--------  --------------------  -----------  ------------  ------------------------------------\n" \
                "enabled   active                         25            20  /run/log/bootchart-20220504-1040.svg\n" \
                "                                                           /run/log/bootchart-20220504-1045.svg\n"

        result = runner.invoke(sonic_bootchart.cli.commands["config"], ["--time", "2", "--frequency", "50"])
        assert not result.exit_code

        result = runner.invoke(sonic_bootchart.cli.commands['show'], [])
        assert not result.exit_code
        assert result.output == \
                "Status    Operational Status      Frequency    Time (sec)  Output\n"                               \
                "--------  --------------------  -----------  ------------  ------------------------------------\n" \
                "enabled   active                         50             2  /run/log/bootchart-20220504-1040.svg\n" \
                "                                                           /run/log/bootchart-20220504-1045.svg\n"

        # Input validation tests

        result = runner.invoke(sonic_bootchart.cli.commands["config"], ["--time", "0", "--frequency", "50"])
        assert result.exit_code

        result = runner.invoke(sonic_bootchart.cli.commands["config"], ["--time", "2", "--frequency", "-5"])
        assert result.exit_code

    def test_invalid_config_show(self, mock_run_command):
        with open(sonic_bootchart.BOOTCHART_CONF, 'w') as config_file:
            config_file.write("""
            [Bootchart]
            Samples=100
            """)

        runner = CliRunner()
        result = runner.invoke(sonic_bootchart.cli.commands['show'], [])
        assert result.exit_code
        assert result.output == "Error: Failed to parse bootchart config: 'Frequency' not found\n"

        with open(sonic_bootchart.BOOTCHART_CONF, 'w') as config_file:
            config_file.write("""
            [Bootchart]
            Samples=abc
            Frequency=def
            """)

        runner = CliRunner()
        result = runner.invoke(sonic_bootchart.cli.commands['show'], [])
        assert result.exit_code
        assert result.output == "Error: Failed to parse bootchart config: invalid literal for int() with base 10: 'abc'\n"

        with open(sonic_bootchart.BOOTCHART_CONF, 'w') as config_file:
            config_file.write("""
            [Bootchart]
            Samples=100
            Frequency=0
            """)

        runner = CliRunner()
        result = runner.invoke(sonic_bootchart.cli.commands['show'], [])
        assert result.exit_code
        assert result.output == "Error: Invalid frequency value: 0\n"

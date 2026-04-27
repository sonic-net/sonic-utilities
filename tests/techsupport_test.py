import pytest
import show.main
from unittest.mock import patch
from click.testing import CliRunner

EXPECTED_BASE_COMMAND = ['sudo']

@patch("show.main.run_command")
@pytest.mark.parametrize(
        "cli_arguments,expected",
        [
            ([], ['generate_dump', '-v', '-t', '5']),
            (['--since', '2 days ago'], ['generate_dump', '-v', '-s', '2 days ago', '-t', '5']),
            (['-g', '50'], ['timeout', '--kill-after=300s', '-s', 'SIGTERM', '--foreground', '50m', 'generate_dump', '-v', '-t', '5']),
            (['--allow-process-stop'], ['generate_dump', '-v', '-a', '-t', '5']),
            (['--silent'], ['generate_dump', '-t', '5']),
            (['--debug-dump', '--redirect-stderr'], ['generate_dump', '-v', '-d', '-t', '5', '-r']),
            (['-f', 'custom-filename'], ['generate_dump', '-v', '-f', 'custom-filename', '-t', '5'])
        ]
)
def test_techsupport(run_command, cli_arguments, expected):
    runner = CliRunner()
    result = runner.invoke(show.main.cli.commands['techsupport'], cli_arguments)
    run_command.assert_called_with(EXPECTED_BASE_COMMAND + expected, display_cmd=False)


@patch("show.main.run_command")
@pytest.mark.parametrize(
    "cli_arguments,expected_msg",
    [
        (['-f', '/other/dir/custom-filename'], "no path components"),
        (['-f', '../relative/filepath'], "no path components"),
    ]
)
def test_techsupport_filepath(run_command, cli_arguments, expected_msg):
    runner = CliRunner()
    result = runner.invoke(show.main.cli.commands['techsupport'], cli_arguments)
    assert result.exit_code != 0
    assert expected_msg in result.output
    run_command.assert_not_called()

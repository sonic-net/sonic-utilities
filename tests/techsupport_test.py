import pytest
import show.main
from unittest.mock import patch, Mock
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
        ]
)
def test_techsupport(run_command, cli_arguments, expected):
    runner = CliRunner()
    result = runner.invoke(show.main.cli.commands['techsupport'], cli_arguments)
    run_command.assert_called_with(EXPECTED_BASE_COMMAND + expected, display_cmd=False)


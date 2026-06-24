import os
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
            (['--flow-dump'], ['generate_dump', '-v', '-f', '-t', '5']),
            (['--debug-dump', '--flow-dump'], ['generate_dump', '-v', '-d', '-f', '-t', '5']),
            # tcpdump: flag alone applies defaults (60s, 10k packets) -> -T -P -L
            (['--with-tcpdump'],
             ['generate_dump', '-v', '-t', '5', '-T', '-P', '60', '-L', '10000']),
            # tcpdump: all options forwarded, filter as -F
            (['--with-tcpdump', '--tcpdump-duration', '30',
              '--tcpdump-packet-limit', '500', '--tcpdump-filter', 'udp port 3784'],
             ['generate_dump', '-v', '-t', '5', '-T', '-P', '30', '-L', '500', '-F', 'udp port 3784']),
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
        (['--tcpdump-duration', '30'], "--tcpdump-duration requires --with-tcpdump"),
        (['--tcpdump-packet-limit', '500'], "--tcpdump-packet-limit requires --with-tcpdump"),
        (['--tcpdump-filter', 'port 179'], "--tcpdump-filter requires --with-tcpdump"),
    ]
)
def test_techsupport_tcpdump_requires_flag(run_command, cli_arguments, expected_msg):
    runner = CliRunner()
    result = runner.invoke(show.main.cli.commands['techsupport'], cli_arguments)
    assert result.exit_code != 0
    assert expected_msg in result.output
    run_command.assert_not_called()


@patch("show.main.run_command")
@pytest.mark.parametrize(
    "cli_arguments",
    [
        ['--with-tcpdump', '--tcpdump-duration', '0'],          # below range (1-300)
        ['--with-tcpdump', '--tcpdump-duration', '301'],        # above range
        ['--with-tcpdump', '--tcpdump-packet-limit', '0'],      # below range (1-100000)
        ['--with-tcpdump', '--tcpdump-packet-limit', '100001'],  # above range
    ]
)
def test_techsupport_tcpdump_out_of_range(run_command, cli_arguments):
    runner = CliRunner()
    result = runner.invoke(show.main.cli.commands['techsupport'], cli_arguments)
    assert result.exit_code != 0
    run_command.assert_not_called()


def test_tcpdump_awaited_before_save_to_tar():
    """The tcpdump pcap is written into the dump tree and is only added to the
    archive by save_to_tar (a `tar -rhf` that snapshots file content). So the
    capture must be awaited before save_to_tar, or a still-running capture is
    archived truncated and the completed pcap is lost.
    """
    script = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'generate_dump')
    with open(script) as f:
        lines = [ln.strip() for ln in f]
    wait_idx = next(i for i, ln in enumerate(lines) if ln == 'wait_tcpdump_capture')
    save_idx = next(i for i, ln in enumerate(lines) if ln == 'save_to_tar')
    assert wait_idx < save_idx, (
        "wait_tcpdump_capture (line {}) must precede save_to_tar (line {})".format(
            wait_idx + 1, save_idx + 1))

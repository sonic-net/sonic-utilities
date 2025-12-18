import signal
from click.testing import CliRunner
from unittest.mock import MagicMock, patch

import show.hft as show_hft


def test_build_rows_with_mixed_profiles_and_groups():
    profile_table = {
        'profile10': {'stream_state': 'enabled', 'poll_interval': '2000'},
        'profile2': {'stream_state': 'disabled', 'poll_interval': '15'},
        'profile3': {}
    }
    group_table = {
        'profile2|PORT': {
            'object_names': ['Ethernet0', 'Ethernet1'],
            'object_counters': 'COUNTER0, COUNTER2'
        },
        ('profile2', 'QUEUE'): {
            'object_names': None,
            'object_counters': ['QUEUE_OCCUPANCY']
        },
        'profile10|BUFFER_POOL': {
            'object_names': '',
            'object_counters': []
        }
    }

    rows = show_hft._build_rows(profile_table, group_table)

    assert rows == [
        ['profile2', 'disabled', '15', 'PORT', 'Ethernet0\nEthernet1', 'COUNTER0\nCOUNTER2'],
        ['', '', '', 'QUEUE', '-', 'QUEUE_OCCUPANCY'],
        ['profile3', '-', '-', '-', '-', '-'],
        ['profile10', 'enabled', '2,000', 'BUFFER_POOL', '-', '-']
    ]


def test_format_poll_interval_variants():
    assert show_hft._format_poll_interval('3000') == '3,000'
    assert show_hft._format_poll_interval(15) == '15'
    assert show_hft._format_poll_interval(None) == '-'
    assert show_hft._format_poll_interval('not-a-number') == 'not-a-number'


@patch('show.hft._execute_streaming_command')
def test_hft_counters_builds_expected_docker_command(mock_exec):
    runner = CliRunner()
    result = runner.invoke(
        show_hft.hft_counters,
        [
            '--stats-interval', '2',
            '--max-stats-per-report', '5',
            '--log-level', 'debug',
            '--log-format', 'full'
        ]
    )

    assert result.exit_code == 0
    mock_exec.assert_called_once_with([
        'docker', 'exec', '-i', '-t', 'swss',
        'countersyncd',
        '--enable-stats',
        '--stats-interval', '2',
        '--max-stats-per-report', '5',
        '--log-level', 'debug',
        '--log-format', 'full'
    ])


def test_execute_streaming_command_handles_keyboard_interrupt(monkeypatch):
    proc = MagicMock()
    proc.wait.side_effect = [KeyboardInterrupt, 130]
    proc.send_signal = MagicMock()
    monkeypatch.setattr(show_hft.subprocess, 'Popen', MagicMock(return_value=proc))

    with patch('show.hft.click.echo') as mock_echo:
        show_hft._execute_streaming_command(['docker'])

    proc.send_signal.assert_called_once_with(signal.SIGINT)
    assert mock_echo.call_count == 1


def test_execute_streaming_command_exits_on_unhandled_return_code(monkeypatch):
    proc = MagicMock()
    proc.wait.return_value = 5
    monkeypatch.setattr(show_hft.subprocess, 'Popen', MagicMock(return_value=proc))

    with patch('show.hft.sys.exit') as mock_exit:
        show_hft._execute_streaming_command(['docker'])

    mock_exit.assert_called_once_with(5)

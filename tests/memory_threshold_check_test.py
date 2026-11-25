import json
import os
import sys
import pytest
from unittest import mock
from .mock_tables import dbconnector
from utilities_common.general import load_module_from_source

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, 'scripts')
sys.path.insert(0, scripts_path)

memory_threshold_check_path = os.path.join(scripts_path, 'memory_threshold_check.py')
memory_threshold_check = load_module_from_source('memory_threshold_check.py', memory_threshold_check_path)

@pytest.fixture()
def setup_dbs_regular_mem_usage():
    cfg_db = dbconnector.dedicated_dbs.get('CONFIG_DB')
    state_db = dbconnector.dedicated_dbs.get('STATE_DB')
    dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(test_path, 'memory_threshold_check', 'config_db')
    dbconnector.dedicated_dbs['STATE_DB'] = os.path.join(test_path, 'memory_threshold_check', 'state_db')
    yield
    dbconnector.dedicated_dbs['CONFIG_DB'] = cfg_db
    dbconnector.dedicated_dbs['STATE_DB'] = state_db


@pytest.fixture()
def setup_dbs_telemetry_high_mem_usage():
    memory_threshold_check.MemoryStats.get_sys_memory_stats = mock.Mock(return_value={'MemAvailable': 10000000, 'MemTotal': 20000000})
    cfg_db = dbconnector.dedicated_dbs.get('CONFIG_DB')
    state_db = dbconnector.dedicated_dbs.get('STATE_DB')
    dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(test_path, 'memory_threshold_check', 'config_db')
    dbconnector.dedicated_dbs['STATE_DB'] = os.path.join(test_path, 'memory_threshold_check', 'state_db_2')
    yield
    dbconnector.dedicated_dbs['CONFIG_DB'] = cfg_db
    dbconnector.dedicated_dbs['STATE_DB'] = state_db


@pytest.fixture()
def setup_dbs_swss_high_mem_usage():
    memory_threshold_check.MemoryStats.get_sys_memory_stats = mock.Mock(return_value={'MemAvailable': 10000000, 'MemTotal': 20000000})
    cfg_db = dbconnector.dedicated_dbs.get('CONFIG_DB')
    state_db = dbconnector.dedicated_dbs.get('STATE_DB')
    dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(test_path, 'memory_threshold_check', 'config_db')
    dbconnector.dedicated_dbs['STATE_DB'] = os.path.join(test_path, 'memory_threshold_check', 'state_db_3')
    yield
    dbconnector.dedicated_dbs['CONFIG_DB'] = cfg_db
    dbconnector.dedicated_dbs['STATE_DB'] = state_db


def test_memory_check_host_not_crossed(setup_dbs_regular_mem_usage):
    memory_threshold_check.MemoryStats.get_sys_memory_stats = mock.Mock(return_value={'MemAvailable': 1000000, 'MemTotal': 2000000})
    with mock.patch.object(memory_threshold_check, "handle_log_only_threshold") as mock_handler:
        assert memory_threshold_check.main() == (memory_threshold_check.EXIT_SUCCESS, '')
        mock_handler.assert_not_called()


def test_memory_check_host_60_percent_invokes_handler_and_exits_zero(setup_dbs_regular_mem_usage):
    # 40% available => 60% used; above CONFIG_DB available threshold (10%)
    memory_threshold_check.MemoryStats.get_sys_memory_stats = mock.Mock(return_value={'MemAvailable': 800000, 'MemTotal': 2000000})
    with mock.patch.object(memory_threshold_check, "handle_log_only_threshold") as mock_handler:
        assert memory_threshold_check.main() == (memory_threshold_check.EXIT_SUCCESS, '')
        mock_handler.assert_called_once_with(memory_threshold_check.EXIT_THRESHOLD_60)


def test_memory_check_host_80_percent_invokes_handler_and_exits_zero(setup_dbs_regular_mem_usage):
    # 20% available => 80% used; still above CONFIG_DB available threshold (10%)
    memory_threshold_check.MemoryStats.get_sys_memory_stats = mock.Mock(return_value={'MemAvailable': 400000, 'MemTotal': 2000000})
    with mock.patch.object(memory_threshold_check, "handle_log_only_threshold") as mock_handler:
        assert memory_threshold_check.main() == (memory_threshold_check.EXIT_SUCCESS, '')
        mock_handler.assert_called_once_with(memory_threshold_check.EXIT_THRESHOLD_80)


def test_memory_check_host_90_percent_keeps_non_zero_exit(setup_dbs_regular_mem_usage):
    # 10% free => 90% used. Free 300000 KB is above min_available_mem (204800 KB).
    # Fixture CONFIG_DB available_mem_threshold is 10%, which would take exit 2 first;
    # lower it so the 90% used branch (exit 5) is reachable.
    memory_threshold_check.MemoryStats.get_sys_memory_stats = mock.Mock(
        return_value={'MemAvailable': 300000, 'MemTotal': 3000000}
    )

    class ConfigAllow90(memory_threshold_check.Config):
        def __init__(self, cfg_db):
            super().__init__(cfg_db)
            self.memory_available_threshold = 5.0

    with mock.patch.object(memory_threshold_check, "Config", ConfigAllow90), \
         mock.patch.object(memory_threshold_check, "handle_log_only_threshold") as mock_handler:
        assert memory_threshold_check.main() == (memory_threshold_check.EXIT_THRESHOLD_90, '')
        mock_handler.assert_not_called()


def test_invoke_log_only_handler_oserror_keeps_success(setup_dbs_regular_mem_usage):
    memory_threshold_check.MemoryStats.get_sys_memory_stats = mock.Mock(
        return_value={'MemAvailable': 800000, 'MemTotal': 2000000}
    )
    with mock.patch.object(memory_threshold_check, "should_fire_log_only_handler", return_value=True), \
         mock.patch.object(memory_threshold_check.subprocess, "Popen", side_effect=FileNotFoundError("missing")):
        assert memory_threshold_check.main() == (memory_threshold_check.EXIT_SUCCESS, '')


def test_should_fire_discards_malformed_state(tmp_path):
    state_file = str(tmp_path / "memory_threshold_check.json")
    with open(state_file, "w") as fd:
        json.dump({"3": {"hits": "not-a-list", "last_fired": "bad"}}, fd)
    with mock.patch.object(memory_threshold_check, "LOG_ONLY_STATE_FILE", state_file):
        assert not memory_threshold_check.should_fire_log_only_handler(
            memory_threshold_check.EXIT_THRESHOLD_60, now=1_000_000.0
        )


def test_invoke_log_only_handler_starts_detached_without_monit_env():
    with mock.patch.object(memory_threshold_check.subprocess, "Popen") as mock_popen, \
         mock.patch.dict(os.environ, {"MONIT_DESCRIPTION": "status ok", "MONIT_SERVICE": "memory_check"}):
        assert memory_threshold_check.invoke_log_only_handler(
            memory_threshold_check.EXIT_THRESHOLD_80
        )

    mock_popen.assert_called_once()
    args, kwargs = mock_popen.call_args
    assert args[0] == [
        memory_threshold_check.HANDLER_SCRIPT,
        str(memory_threshold_check.EXIT_THRESHOLD_80),
    ]
    assert kwargs["start_new_session"] is True
    assert "MONIT_DESCRIPTION" not in kwargs["env"]
    assert "MONIT_SERVICE" not in kwargs["env"]


def test_should_fire_log_only_requires_30_hits(tmp_path):
    state_file = str(tmp_path / "memory_threshold_check.json")
    with mock.patch.object(memory_threshold_check, "LOG_ONLY_STATE_FILE", state_file):
        now = 1_000_000.0
        for i in range(29):
            assert not memory_threshold_check.should_fire_log_only_handler(
                memory_threshold_check.EXIT_THRESHOLD_60, now=now + i
            )
        assert memory_threshold_check.should_fire_log_only_handler(
            memory_threshold_check.EXIT_THRESHOLD_60, now=now + 29
        )


def test_should_fire_retries_when_handler_was_not_marked_fired(tmp_path):
    state_file = str(tmp_path / "memory_threshold_check.json")
    with mock.patch.object(memory_threshold_check, "LOG_ONLY_STATE_FILE", state_file):
        now = 1_000_000.0
        for i in range(30):
            fired = memory_threshold_check.should_fire_log_only_handler(
                memory_threshold_check.EXIT_THRESHOLD_60, now=now + i
            )
        assert fired
        # Popen failed: last_fired not set, next cycle still eligible
        assert memory_threshold_check.should_fire_log_only_handler(
            memory_threshold_check.EXIT_THRESHOLD_60, now=now + 30
        )


def test_should_fire_log_only_cools_down_after_first_fire(tmp_path):
    state_file = str(tmp_path / "memory_threshold_check.json")
    with mock.patch.object(memory_threshold_check, "LOG_ONLY_STATE_FILE", state_file):
        now = 1_000_000.0
        for i in range(29):
            memory_threshold_check.should_fire_log_only_handler(
                memory_threshold_check.EXIT_THRESHOLD_60, now=now + i
            )
        assert memory_threshold_check.should_fire_log_only_handler(
            memory_threshold_check.EXIT_THRESHOLD_60, now=now + 29
        )
        memory_threshold_check.mark_log_only_handler_fired(
            memory_threshold_check.EXIT_THRESHOLD_60, now=now + 29
        )
        # Still in band: no re-arm, quiet until 120 minutes after first fire
        assert not memory_threshold_check.should_fire_log_only_handler(
            memory_threshold_check.EXIT_THRESHOLD_60, now=now + 29 + 119 * 60
        )
        assert memory_threshold_check.should_fire_log_only_handler(
            memory_threshold_check.EXIT_THRESHOLD_60, now=now + 29 + 120 * 60
        )


def test_should_fire_80_percent_repeat_after_30_minutes(tmp_path):
    state_file = str(tmp_path / "memory_threshold_check.json")
    with mock.patch.object(memory_threshold_check, "LOG_ONLY_STATE_FILE", state_file):
        now = 1_000_000.0
        for i in range(30):
            fired = memory_threshold_check.should_fire_log_only_handler(
                memory_threshold_check.EXIT_THRESHOLD_80, now=now + i
            )
        assert fired
        memory_threshold_check.mark_log_only_handler_fired(
            memory_threshold_check.EXIT_THRESHOLD_80, now=now + 29
        )
        assert not memory_threshold_check.should_fire_log_only_handler(
            memory_threshold_check.EXIT_THRESHOLD_80, now=now + 29 + 29 * 60
        )
        assert memory_threshold_check.should_fire_log_only_handler(
            memory_threshold_check.EXIT_THRESHOLD_80, now=now + 29 + 30 * 60
        )


def test_should_fire_rearms_after_leaving_band(tmp_path):
    state_file = str(tmp_path / "memory_threshold_check.json")
    with mock.patch.object(memory_threshold_check, "LOG_ONLY_STATE_FILE", state_file):
        now = 1_000_000.0
        for i in range(30):
            memory_threshold_check.should_fire_log_only_handler(
                memory_threshold_check.EXIT_THRESHOLD_60, now=now + i
            )
        memory_threshold_check.reset_log_only_bands()
        assert not memory_threshold_check.should_fire_log_only_handler(
            memory_threshold_check.EXIT_THRESHOLD_60, now=now + 200
        )


def test_memory_check_host_less_then_min_required(setup_dbs_regular_mem_usage):
    memory_threshold_check.MemoryStats.get_sys_memory_stats = mock.Mock(return_value={'MemAvailable': 1000, 'MemTotal': 2000000})
    assert memory_threshold_check.main() == (memory_threshold_check.EXIT_FAILURE, '')


def test_memory_check_host_threshold_crossed(setup_dbs_regular_mem_usage):
    memory_threshold_check.MemoryStats.get_sys_memory_stats = mock.Mock(return_value={'MemAvailable': 2000000, 'MemTotal': 20000000})
    assert memory_threshold_check.main() == (memory_threshold_check.EXIT_THRESHOLD, '')


def test_memory_check_telemetry_threshold_crossed(setup_dbs_telemetry_high_mem_usage):
    assert memory_threshold_check.main() == (memory_threshold_check.EXIT_THRESHOLD, 'telemetry')


def test_memory_check_swss_threshold_crossed(setup_dbs_swss_high_mem_usage):
    assert memory_threshold_check.main() == (memory_threshold_check.EXIT_THRESHOLD, 'swss')

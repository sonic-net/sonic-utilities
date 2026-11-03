import importlib.util
import os
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, modules_path)
sys.path.insert(0, scripts_path)


def _load_memory_gradual_check():
    spec = importlib.util.spec_from_file_location(
        "memory_gradual_check",
        os.path.join(scripts_path, "memory_gradual_check.py"),
    )
    module = importlib.util.module_from_spec(spec)
    fake_psutil = types.ModuleType("psutil")
    with patch.dict(sys.modules, {"psutil": fake_psutil}):
        spec.loader.exec_module(module)
    return module


memory_gradual_check = _load_memory_gradual_check()


def _make_state(window_values, window_size=24, baseline_mb=1000.0):
    return {
        "window_size": window_size,
        "system_memory_window": list(window_values),
        "tracked_containers": {},
        "tracked_processes": {},
        "baseline_snapshot": {
            "timestamp": "2026-01-01T00:00:00",
            "memory_mb": baseline_mb,
            "total_ram_mb": 20000.0,
        },
    }


def test_sync_baseline_skips_partial_window():
    state = _make_state([4000.0, 4050.0, 4100.0])

    memory_gradual_check._sync_baseline_when_window_full(state, 20000.0)

    assert state["baseline_snapshot"]["memory_mb"] == 1000.0


def test_sync_baseline_uses_oldest_sample_when_window_full():
    state = _make_state([1000.0 + i for i in range(24)], baseline_mb=5000.0)
    state["baseline_snapshot"]["total_ram_mb"] = 16000.0

    memory_gradual_check._sync_baseline_when_window_full(state, 20000.0)

    assert state["baseline_snapshot"]["memory_mb"] == 1000.0
    assert state["baseline_snapshot"]["total_ram_mb"] == 20000.0


def test_growth_measured_from_window_start_not_stale_baseline():
    window = [4000.0 + i * (100.0 / 23) for i in range(24)]
    state = _make_state(window, baseline_mb=3000.0)
    state["sample_count"] = 24

    detected, info = memory_gradual_check.check_for_gradual_increase(
        state, "short", window[-1], 20000.0
    )

    assert info["baseline_mb"] == window[0]
    assert info["growth_mb"] == pytest.approx(window[-1] - window[0])
    assert detected is False


def test_invoke_detection_handler_calls_handler_script():
    mock_result = MagicMock(returncode=0)
    with patch.object(memory_gradual_check.subprocess, "run", return_value=mock_result) as mock_run:
        memory_gradual_check.invoke_detection_handler("short")

    mock_run.assert_called_once_with(
        [memory_gradual_check.HANDLER_SCRIPT, "--scale", "short"],
        check=False,
    )


def test_invoke_detection_handler_logs_info_on_nonzero_exit():
    mock_result = MagicMock(returncode=1)
    with patch.object(memory_gradual_check.subprocess, "run", return_value=mock_result), \
         patch.object(memory_gradual_check, "log_info") as mock_log_info:
        memory_gradual_check.invoke_detection_handler("short")

    mock_log_info.assert_called_once_with(
        "Handler exited 1 for scale short; monit check still OK"
    )


def test_run_check_invokes_handler_and_exits_zero_on_detection():
    state = _make_state([4000.0] * 24)
    state_file = "/var/run/memory_gradual_short.json"

    with patch.object(memory_gradual_check, "get_system_memory", return_value=(5000.0, 20000.0)), \
         patch.object(memory_gradual_check, "get_container_memory", return_value={}), \
         patch.object(memory_gradual_check, "get_significant_processes", return_value={}), \
         patch.object(memory_gradual_check, "get_state_file_path", return_value=state_file), \
         patch.object(memory_gradual_check, "load_state", return_value=state), \
         patch.object(memory_gradual_check, "update_state", side_effect=lambda s, *args: s), \
         patch.object(memory_gradual_check, "_sync_baseline_when_window_full"), \
         patch.object(memory_gradual_check, "check_for_gradual_increase", return_value=(True, {})), \
         patch.object(memory_gradual_check, "save_state", return_value=True) as mock_save, \
         patch.object(memory_gradual_check, "invoke_detection_handler") as mock_handler:
        rc = memory_gradual_check.run_check("short")

    assert rc == memory_gradual_check.EXIT_SUCCESS
    mock_save.assert_called_once_with(state_file, state)
    mock_handler.assert_called_once_with("short")


def test_run_check_skips_handler_when_save_state_fails():
    state = _make_state([4000.0] * 24)
    state_file = "/var/run/memory_gradual_short.json"

    with patch.object(memory_gradual_check, "get_system_memory", return_value=(5000.0, 20000.0)), \
         patch.object(memory_gradual_check, "get_container_memory", return_value={}), \
         patch.object(memory_gradual_check, "get_significant_processes", return_value={}), \
         patch.object(memory_gradual_check, "get_state_file_path", return_value=state_file), \
         patch.object(memory_gradual_check, "load_state", return_value=state), \
         patch.object(memory_gradual_check, "update_state", side_effect=lambda s, *args: s), \
         patch.object(memory_gradual_check, "_sync_baseline_when_window_full"), \
         patch.object(memory_gradual_check, "check_for_gradual_increase", return_value=(True, {})), \
         patch.object(memory_gradual_check, "save_state", return_value=False), \
         patch.object(memory_gradual_check, "invoke_detection_handler") as mock_handler, \
         patch.object(memory_gradual_check, "log_error") as mock_log_error:
        rc = memory_gradual_check.run_check("short")

    assert rc == memory_gradual_check.EXIT_SUCCESS
    mock_handler.assert_not_called()
    mock_log_error.assert_called_once_with(
        "Gradual memory detection for scale short could not be "
        "logged; state save failed, handler skipped"
    )

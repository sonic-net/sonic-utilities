#!/usr/bin/env python3
"""
Memory Gradual Increase Detection

Detects memory gradual increase by tracking memory trends using linear regression.
Runs at three time scales to catch fast, medium, and slow memory growth.

Exit Codes:
    0: Normal operation (including after logging a detection via handler)
"""

import json
import os
import subprocess
import sys
import syslog
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

import psutil

from utilities_common.memory_gradual_common import (
    STATE_DIR,
    get_state_file_path,
    linear_regression,
    load_state as _load_state_base,
)

# Exit codes
EXIT_SUCCESS = 0

HANDLER_SCRIPT = "/usr/local/bin/memory_gradual_handler.py"

SYSLOG_IDENTIFIER = "memory_gradual_check"
syslog.openlog(SYSLOG_IDENTIFIER, syslog.LOG_PID)


def log_info(msg: str):
    syslog.syslog(syslog.LOG_INFO, msg)


def log_warning(msg: str):
    syslog.syslog(syslog.LOG_WARNING, msg)


def log_error(msg: str):
    syslog.syslog(syslog.LOG_ERR, msg)

# Time scale configurations
# Each scale: (window_size, check_interval_mins, time_threshold_mins, growth_threshold_pct)
# Production time scale configurations.
#
# Each scale independently collects memory samples into a sliding window,
# then runs linear regression when the window is full.
#
#   window_size          - number of samples before regression runs
#   check_interval_mins  - minutes between samples (must match monit "every N cycles")
#   time_threshold_mins  - alert if predicted time-to-90% is below this
#   growth_threshold_pct - alert if memory growth exceeds this % of FREE memory
#   window_description   - human-readable label for syslog output
#
# Detection fires when:  R² > 0.7  AND  (time_to_90 < threshold  OR  growth% > threshold)
#
# Example: short window = 24 samples × 5 min = 2 hour observation window.
#          Alerts if time-to-90% < 6 hours OR growth > 1% of remaining free memory.
SCALE_CONFIG = {
    "short": {
        "window_size": 24,
        "check_interval_mins": 5,      # every 5 cycles  → 24×5 min = 2 hour window
        "time_threshold_mins": 360,    # alert if OOM in < 6 hours
        "growth_threshold_pct": 1,     # alert if growth > 1% of free memory
        "window_description": "2 hours"
    },
    "medium": {
        "window_size": 24,
        "check_interval_mins": 60,     # every 60 cycles → 24×60 min = 24 hour window
        "time_threshold_mins": 4320,   # alert if OOM in < 3 days
        "growth_threshold_pct": 5,     # alert if growth > 5% of free memory
        "window_description": "24 hours"
    },
    "long": {
        "window_size": 21,
        "check_interval_mins": 480,    # every 480 cycles → 21×8 hr = 7 day window
        "time_threshold_mins": 30240,  # alert if OOM in < 21 days
        "growth_threshold_pct": 5,     # alert if growth > 5% of free memory
        "window_description": "7 days"
    }
}

# Test-mode: accelerated intervals and reduced windows for functional testing
SCALE_CONFIG_TEST_MODE = {
    "short": {
        "window_size": 10,
        "check_interval_mins": 1,      # 1 min (accelerated from 5 min)
        "time_threshold_mins": 30,
        "growth_threshold_pct": 1,     # 1% of free memory
        "window_description": "10 min"
    },
    "medium": {
        "window_size": 10,
        "check_interval_mins": 2,      # 2 min (accelerated from 60 min)
        "time_threshold_mins": 60,
        "growth_threshold_pct": 5,     # 5% of free memory
        "window_description": "20 min"
    },
    "long": {
        "window_size": 10,
        "check_interval_mins": 5,      # 5 min (accelerated from 480 min)
        "time_threshold_mins": 150,
        "growth_threshold_pct": 5,     # 5% of free memory
        "window_description": "50 min"
    }
}

# Detection parameters
R_SQUARED_THRESHOLD = 0.7       # Minimum R² for confident trend
PROCESS_MIN_RAM_PCT = 0.5       # Track processes using >0.5% of RAM
MAX_TRACKED_PROCESSES = 100     # Cap on tracked processes


def _get_running_container_names() -> Set[str]:
    """Dynamically discover running Docker container names on this device."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return set(
                line.strip() for line in result.stdout.strip().split('\n')
                if line.strip()
            )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return set()


# =============================================================================
# Memory Statistics Collection
# =============================================================================

def get_system_memory() -> Tuple[float, float]:
    """
    Get system memory statistics.

    Returns:
        Tuple of (used_mb, total_mb)
    """
    mem = psutil.virtual_memory()
    used_mb = mem.used / (1024 * 1024)
    total_mb = mem.total / (1024 * 1024)
    return used_mb, total_mb


def get_container_memory() -> Dict[str, float]:
    """
    Get memory usage by container.

    Dynamically discovers running containers via docker ps, then maps
    each process to its container by reading /proc/<pid>/cgroup.

    Returns:
        Dict mapping container name to total RSS in MB
    """
    running_containers = _get_running_container_names()
    if not running_containers:
        return {}

    containers = {}

    for proc in psutil.process_iter(['pid', 'memory_info']):
        try:
            pid = proc.info['pid']
            mem_info = proc.info.get('memory_info')
            if mem_info is None:
                continue

            rss_mb = mem_info.rss / (1024 * 1024)

            cgroup_path = f"/proc/{pid}/cgroup"
            if not os.path.exists(cgroup_path):
                continue

            with open(cgroup_path, 'r') as f:
                cgroup_content = f.read()

            for line in cgroup_content.split('\n'):
                if 'docker' in line or 'containerd' in line:
                    parts = line.split('/')
                    for part in parts:
                        if part in running_containers:
                            containers[part] = containers.get(part, 0) + rss_mb
                            break
                    break

        except (psutil.NoSuchProcess, psutil.AccessDenied, IOError, OSError):
            continue

    return containers


def get_significant_processes(total_ram_mb: float) -> Dict[str, float]:
    """
    Get processes using more than PROCESS_MIN_RAM_PCT of total RAM.

    Each process is keyed by "pid:name" so that distinct PIDs sharing a
    common comm name (e.g. python3) are tracked independently.

    Args:
        total_ram_mb: Total system RAM in MB

    Returns:
        Dict mapping "pid:name" to RSS in MB
    """
    min_mem_mb = total_ram_mb * PROCESS_MIN_RAM_PCT / 100
    processes = {}

    for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
        try:
            mem_info = proc.info.get('memory_info')
            if mem_info is None:
                continue
            rss_mb = mem_info.rss / (1024 * 1024)
            if rss_mb >= min_mem_mb:
                key = f"{proc.info['pid']}:{proc.info['name']}"
                processes[key] = rss_mb
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    sorted_procs = sorted(processes.items(), key=lambda x: x[1], reverse=True)
    return dict(sorted_procs[:MAX_TRACKED_PROCESSES])


# =============================================================================
# State Management
# =============================================================================

def load_state(state_file: str) -> Optional[Dict]:
    """Load state from JSON file, logging warnings on failure."""
    return _load_state_base(state_file, log_fn=log_warning)


def save_state(state_file: str, state: Dict) -> bool:
    """Save state to JSON file."""
    try:
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)
        return True
    except (IOError, OSError) as e:
        log_error(f"Failed to save state file {state_file}: {e}")
        return False


def create_initial_state(scale: str, used_mb: float, total_mb: float,
                         containers: Dict[str, float], processes: Dict[str, float],
                         active_config: Optional[Dict] = None) -> Dict:
    """Create initial state structure."""
    if active_config is None:
        active_config = SCALE_CONFIG
    config = active_config[scale]
    return {
        "window_type": scale,
        "window_size": config["window_size"],
        "window_description": config["window_description"],
        "sample_count": 1,
        "system_memory_window": [used_mb],
        "tracked_containers": {name: [mem] for name, mem in containers.items()},
        "tracked_processes": {name: [mem] for name, mem in processes.items()},
        "baseline_snapshot": {
            "timestamp": datetime.now().isoformat(),
            "memory_mb": used_mb,
            "total_ram_mb": total_mb
        },
        "last_regression": None
    }


def _update_tracked_window(tracked: Dict, current: Dict[str, float], 
                           window_size: int, sample_count: int) -> Dict:
    """
    Update a tracked memory window (containers or processes).

    - Appends new sample for existing items
    - Pads with None for new items (wasn't running before)
    - Appends None for missing items (stopped running)
    - Trims to window_size
    """
    for name, mem in current.items():
        if name in tracked:
            tracked[name].append(mem)
        else:
            # New item - pad history with None
            tracked[name] = [None] * (sample_count - 1) + [mem]

        if len(tracked[name]) > window_size:
            tracked[name] = tracked[name][-window_size:]

    # Items that stopped running get None
    for name in list(tracked.keys()):
        if name not in current:
            tracked[name].append(None)
            if len(tracked[name]) > window_size:
                tracked[name] = tracked[name][-window_size:]

    # Prune entries that are entirely None (process gone for full window)
    for name in list(tracked.keys()):
        if all(v is None for v in tracked[name]):
            del tracked[name]

    return tracked


def update_state(state: Dict, used_mb: float, containers: Dict[str, float],
                 processes: Dict[str, float]) -> Dict:
    """Update state with new memory sample."""
    window_size = state["window_size"]

    # Update system memory window
    state["system_memory_window"].append(used_mb)
    if len(state["system_memory_window"]) > window_size:
        state["system_memory_window"] = state["system_memory_window"][-window_size:]

    sample_count = len(state["system_memory_window"])

    # Update container and process windows
    state["tracked_containers"] = _update_tracked_window(
        state.get("tracked_containers", {}), containers, window_size, sample_count)
    state["tracked_processes"] = _update_tracked_window(
        state.get("tracked_processes", {}), processes, window_size, sample_count)

    state["sample_count"] = sample_count
    return state


def _sync_baseline_when_window_full(state: Dict, total_mb: float) -> None:
    """Keep baseline_snapshot aligned with the oldest sample once window is full."""
    window = state.get("system_memory_window") or []
    if len(window) < state.get("window_size", 0):
        return
    state["baseline_snapshot"] = {
        "timestamp": datetime.now().isoformat(),
        "memory_mb": window[0],
        "total_ram_mb": total_mb,
    }


def reset_state(scale: str, used_mb: float, total_mb: float,
                containers: Dict[str, float], processes: Dict[str, float]) -> Dict:
    """Reset state to start fresh window."""
    return create_initial_state(scale, used_mb, total_mb, containers, processes)


# =============================================================================
# Detection Logic
# =============================================================================

def check_for_gradual_increase(state: Dict, scale: str, 
                                current_used_mb: float, 
                                total_ram_mb: float,
                                active_config: Optional[Dict] = None) -> Tuple[bool, Dict]:
    """
    Check if gradual memory increase is detected.

    Detection triggers if:
    - R² > 0.7 (consistent trend) AND
    - (time_to_90% < threshold OR percent_growth > threshold)

    Args:
        state: Current state dict
        scale: Time scale name
        current_used_mb: Current memory usage
        total_ram_mb: Total system RAM
        active_config: Scale configuration dict (defaults to SCALE_CONFIG)

    Returns:
        Tuple of (detected, detection_info)
    """
    if active_config is None:
        active_config = SCALE_CONFIG
    config = active_config[scale]
    window = state["system_memory_window"]

    # Need full window for detection
    if len(window) < config["window_size"]:
        return False, {}

    # Run linear regression
    slope, intercept, r_squared = linear_regression(window)

    # Store regression results
    state["last_regression"] = {
        "slope_mb_per_interval": slope,
        "slope_mb_per_min": slope / config["check_interval_mins"],
        "r_squared": r_squared,
        "calculated_at_sample": state["sample_count"]
    }

    # Check R² threshold first
    if r_squared < R_SQUARED_THRESHOLD:
        return False, {"reason": "low_r_squared", "r_squared": r_squared}

    # Calculate metrics - growth as % of free memory, measured over the
    # current regression window (oldest sample -> latest sample).
    baseline_mb = window[0]
    growth_mb = current_used_mb - baseline_mb
    free_memory_mb = total_ram_mb - current_used_mb
    percent_growth = (growth_mb / free_memory_mb) * 100 if free_memory_mb > 0 else 100.0

    # Calculate time to 90%
    threshold_90_mb = total_ram_mb * 0.9
    headroom_mb = threshold_90_mb - current_used_mb

    # slope is per interval, convert to per minute
    slope_per_min = slope / config["check_interval_mins"]

    if slope_per_min > 0 and headroom_mb > 0:
        time_to_90_mins = headroom_mb / slope_per_min
    else:
        time_to_90_mins = float('inf')

    # Detection logic: R² > threshold AND (time OR growth)
    time_triggered = time_to_90_mins < config["time_threshold_mins"]
    growth_triggered = percent_growth > config["growth_threshold_pct"]

    detection_info = {
        "baseline_mb": baseline_mb,
        "current_mb": current_used_mb,
        "growth_mb": growth_mb,
        "growth_pct": percent_growth,
        "slope_mb_per_min": slope_per_min,
        "r_squared": r_squared,
        "time_to_90_mins": time_to_90_mins,
        "time_triggered": time_triggered,
        "growth_triggered": growth_triggered,
        "total_ram_mb": total_ram_mb,
        "window_description": config["window_description"]
    }

    if time_triggered or growth_triggered:
        return True, detection_info

    return False, detection_info


# =============================================================================
# Main Entry Point
# =============================================================================

def get_active_config(test_mode: bool = False) -> Dict:
    """Return the active scale configuration based on mode."""
    return SCALE_CONFIG_TEST_MODE if test_mode else SCALE_CONFIG


def invoke_detection_handler(scale: str) -> None:
    """Run the handler to log detection details without failing monit."""
    result = subprocess.run(
        [HANDLER_SCRIPT, "--scale", scale],
        check=False,
    )
    if result.returncode != 0:
        log_info(
            f"Handler exited {result.returncode} for scale {scale}; "
            f"monit check still OK"
        )


def run_check(scale: str, test_mode: bool = False) -> int:
    """
    Run memory gradual increase check for specified scale.

    Args:
        scale: Time scale (short, medium, long)
        test_mode: If True, use accelerated test-mode intervals and thresholds

    Returns:
        Exit code (always 0; detections are logged via handler)
    """
    active_config = get_active_config(test_mode)
    if scale not in active_config:
        log_error(f"Invalid scale: {scale}")
        return EXIT_SUCCESS

    try:
        # Get current memory stats
        used_mb, total_mb = get_system_memory()
        containers = get_container_memory()
        processes = get_significant_processes(total_mb)

        # Load or create state
        state_file = get_state_file_path(scale)
        state = load_state(state_file)

        if state is None:
            # First run - initialize state
            state = create_initial_state(scale, used_mb, total_mb, containers, processes,
                                         active_config)
            save_state(state_file, state)
            return EXIT_SUCCESS

        # Update state with new sample
        state = update_state(state, used_mb, containers, processes)
        _sync_baseline_when_window_full(state, total_mb)

        # Check for gradual increase
        detected, info = check_for_gradual_increase(state, scale, used_mb, total_mb,
                                                     active_config)

        if detected:
            # Save state for handler to read (handler resets after reading)
            if save_state(state_file, state):
                invoke_detection_handler(scale)
            else:
                log_error(
                    f"Gradual memory detection for scale {scale} could not be "
                    f"logged; state save failed, handler skipped"
                )
            return EXIT_SUCCESS

        # Save updated state
        save_state(state_file, state)
        return EXIT_SUCCESS

    except Exception as e:
        log_error(f"Error in memory_gradual_check ({scale}): {e}")
        return EXIT_SUCCESS  # Don't trigger handler on errors


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Memory gradual increase detection'
    )
    parser.add_argument(
        '--scale', 
        type=str, 
        required=True,
        choices=['short', 'medium', 'long'],
        help='Time scale for detection'
    )
    parser.add_argument(
        '--test-mode',
        action='store_true',
        default=False,
        help='Use accelerated test-mode intervals and thresholds'
    )

    args = parser.parse_args()
    sys.exit(run_check(args.scale, test_mode=args.test_mode))


if __name__ == "__main__":
    main()

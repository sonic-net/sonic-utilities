#!/usr/bin/env python3
"""
Memory Gradual Increase Handler

Called by memory_gradual_check.py when gradual memory increase is detected.
Reads state file and logs detailed memory information for investigation.

Output Format:
    INFO: Gradual memory increase detected (window: 2 hours)
    INFO:   Current: 8000MB used, 4000MB free (66.7%) ; Growth: 7500MB -> 8000MB (+500MB, +6.7%), time to 90%: 14.0 hours
    INFO:   Memory-consuming processes:
    INFO:     #1 PID:123 python3 - +400MB (+50%) - python3 script.py
    INFO:     #2 PID:456 syncd - 1234MB (10.3%) - /usr/bin/syncd -u -s
    INFO:   Memory-consuming containers: syncd: 1234MB (10.3%); pmon: 450MB (3.8%); bgp: 300MB (2.5%)
"""

import os
import re
import sys
import syslog
import argparse
import subprocess
from typing import Dict, List, Optional

import psutil

from utilities_common.memory_gradual_common import (
    get_state_file_path,
    linear_regression,
    load_state as _load_state_base,
)

SYSLOG_IDENTIFIER = "memory_gradual_handler"
syslog.openlog(SYSLOG_IDENTIFIER, syslog.LOG_PID)


def log_info(msg: str):
    syslog.syslog(syslog.LOG_INFO, msg)


def log_error(msg: str):
    syslog.syslog(syslog.LOG_ERR, msg)

# Filtering thresholds
CONTRIBUTION_PCT = 10       # Must contribute >=10% of system growth
R_SQUARED_MIN = 0.5         # Minimum R² to be reported


def _parse_process_key(key: str):
    """Parse a 'pid:name' tracker key into (pid, name).

    Returns (None, key) for legacy name-only keys so existing state
    files degrade gracefully after an upgrade.
    """
    parts = key.split(':', 1)
    if len(parts) == 2 and parts[0].isdigit():
        return int(parts[0]), parts[1]
    return None, key


def get_top_processes(total_mb: float, top_n: int = 5) -> List[Dict]:
    """Get top N memory-consuming processes with details."""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cmdline']):
        try:
            mem_info = proc.info.get('memory_info')
            if mem_info is None:
                continue
            rss_mb = mem_info.rss / (1024 * 1024)
            cmdline = proc.info.get('cmdline') or []
            cmdline_str = ' '.join(cmdline)[:60] if cmdline else proc.info['name']
            processes.append({
                'pid': proc.info['pid'],
                'name': proc.info['name'],
                'rss_mb': rss_mb,
                'pct': (rss_mb / total_mb * 100) if total_mb > 0 else 0,
                'cmdline': cmdline_str
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    processes.sort(key=lambda x: x['rss_mb'], reverse=True)
    return processes[:top_n]


def parse_memory_size(size_str: str) -> float:
    """Parse memory size string like '1.5GiB' to MB."""
    size_str = size_str.strip()
    match = re.match(r'([0-9.]+)\s*([A-Za-z]+)', size_str)
    if not match:
        return 0.0

    value = float(match.group(1))
    unit = match.group(2).upper()

    unit_multipliers = {
        'GIB': 1024.0, 'GB': 1024.0, 'G': 1024.0,
        'MIB': 1.0, 'MB': 1.0, 'M': 1.0,
        'KIB': 1/1024.0, 'KB': 1/1024.0, 'K': 1/1024.0,
        'B': 1/(1024.0 * 1024.0), 'BYTES': 1/(1024.0 * 1024.0)
    }

    return value * unit_multipliers.get(unit, 1.0)


def get_container_memory() -> Dict[str, float]:
    """Get memory usage by container using docker stats."""
    containers = {}
    try:
        cmd = ["docker", "stats", "--no-stream", "--format", "{{.Name}},{{.MemUsage}}"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return containers

        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            try:
                parts = line.split(',')
                if len(parts) >= 2:
                    name = parts[0]
                    mem_usage_str = parts[1].split('/')[0].strip()
                    mem_mb = parse_memory_size(mem_usage_str)
                    if mem_mb > 0:
                        containers[name] = mem_mb
            except (ValueError, IndexError):
                continue
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return containers


def get_top_containers(total_mb: float, top_n: int = 5) -> List[Dict]:
    """Get top N memory-consuming containers."""
    containers = get_container_memory()
    result = []
    for name, rss_mb in containers.items():
        result.append({
            'name': name,
            'rss_mb': rss_mb,
            'pct': (rss_mb / total_mb * 100) if total_mb > 0 else 0
        })
    result.sort(key=lambda x: x['rss_mb'], reverse=True)
    return result[:top_n]


def load_state(state_file: str) -> Optional[Dict]:
    """Load state from JSON file, logging errors on failure."""
    return _load_state_base(state_file, log_fn=log_error)


def analyze_container_growth(state: Dict, system_growth_mb: float) -> List[Dict]:
    """Analyze container memory growth from tracked history."""
    return _analyze_growth(state.get("tracked_containers", {}), system_growth_mb)


def analyze_process_growth(state: Dict, system_growth_mb: float) -> List[Dict]:
    """Analyze process memory growth from tracked history."""
    return _analyze_growth(state.get("tracked_processes", {}), system_growth_mb)


def _analyze_growth(tracked: Dict, system_growth_mb: float) -> List[Dict]:
    """
    Analyze memory growth from tracked history.

    Reports items where:
    - Growth >= 10% of system growth
    - R² > 0.5 (consistent trend)
    """
    if system_growth_mb <= 0:
        return []

    min_contribution_mb = system_growth_mb * CONTRIBUTION_PCT / 100
    contributors = []

    for name, memory_window in tracked.items():
        valid_samples = [m for m in memory_window if m is not None]

        if len(valid_samples) < 3:
            continue

        slope, intercept, r_squared = linear_regression(valid_samples)

        first_valid = valid_samples[0]
        last_valid = valid_samples[-1]
        growth_mb = last_valid - first_valid
        growth_pct = (growth_mb / first_valid * 100) if first_valid > 0 else 0

        if growth_mb < min_contribution_mb:
            continue

        if r_squared < R_SQUARED_MIN:
            continue

        contributors.append({
            "name": name,
            "growth_mb": growth_mb,
            "growth_pct": growth_pct,
            "r_squared": r_squared,
            "baseline_mb": first_valid,
            "current_mb": last_valid
        })

    contributors.sort(key=lambda x: x["growth_mb"], reverse=True)
    return contributors[:10]  # Return top 10 max


def format_time_str(minutes: float) -> str:
    """Format time in minutes to human-readable string."""
    if minutes == float('inf'):
        return "N/A"
    if minutes < 60:
        return f"{minutes:.0f} min"
    elif minutes < 1440:
        return f"{minutes / 60:.1f} hours"
    else:
        return f"{minutes / 1440:.1f} days"


def log_detection_details(state: Dict, scale: str):
    """Log detection info in human-readable format."""
    baseline = state.get("baseline_snapshot") or {}
    regression = state.get("last_regression") or {}

    baseline_mb = baseline.get("memory_mb", 0)
    total_ram_mb = baseline.get("total_ram_mb", 0)

    mem = psutil.virtual_memory()
    current_mb = mem.used / (1024 * 1024)
    free_mb = mem.available / (1024 * 1024)
    used_pct = mem.percent

    growth_mb = current_mb - baseline_mb
    free_memory_mb = total_ram_mb - current_mb
    growth_pct = (growth_mb / free_memory_mb * 100) if free_memory_mb > 0 else 100.0

    slope_per_min = regression.get("slope_mb_per_min", 0)
    r_squared = regression.get("r_squared", 0)

    threshold_90_mb = total_ram_mb * 0.9
    headroom_mb = threshold_90_mb - current_mb
    if slope_per_min > 0 and headroom_mb > 0:
        time_to_90_mins = headroom_mb / slope_per_min
    else:
        time_to_90_mins = float('inf')

    window_desc = state.get("window_description", scale)

    # Line 1: Detection header
    log_info(f"Gradual memory increase detected (window: {window_desc})")

    # Line 2: Memory stats
    log_info(
        f"  Current: {current_mb:.0f}MB used, {free_mb:.0f}MB free ({used_pct:.1f}%) ; "
        f"Growth: {baseline_mb:.0f}MB -> {current_mb:.0f}MB "
        f"(+{growth_mb:.0f}MB, +{growth_pct:.1f}% of free mem), time to 90%: {format_time_str(time_to_90_mins)}"
    )

    # Lines 3+: Memory-consuming processes (each on own line)
    process_contributors = analyze_process_growth(state, growth_mb)
    contributor_pids = set()
    for c in process_contributors:
        pid, _ = _parse_process_key(c['name'])
        if pid is not None:
            contributor_pids.add(pid)
    top_procs = get_top_processes(total_ram_mb, top_n=15)

    proc_list = []
    # First add growth contributors
    for c in process_contributors:
        pid, proc_name = _parse_process_key(c['name'])
        proc_detail = next((p for p in top_procs if p['pid'] == pid), None) if pid else None
        entry = {
            'name': proc_name,
            'is_contributor': True,
            'growth_mb': c['growth_mb'],
            'growth_pct': c['growth_pct'],
            'r_squared': c['r_squared']
        }
        if proc_detail:
            entry['pid'] = proc_detail['pid']
            entry['rss_mb'] = proc_detail['rss_mb']
            entry['pct'] = proc_detail['pct']
            entry['cmdline'] = proc_detail['cmdline']
        elif pid:
            entry['pid'] = pid
        proc_list.append(entry)

    # Fill to min 5 with top consumers
    for p in top_procs:
        if len(proc_list) >= 10:
            break
        if p['pid'] not in contributor_pids and len(proc_list) < 5:
            proc_list.append({
                'name': p['name'],
                'is_contributor': False,
                'pid': p['pid'],
                'rss_mb': p['rss_mb'],
                'pct': p['pct'],
                'cmdline': p['cmdline']
            })

    log_info("  Memory-consuming processes:")
    for i, p in enumerate(proc_list[:10], 1):
        if p.get('is_contributor'):
            pid_str = f"PID:{p.get('pid', '?')}" if 'pid' in p else ""
            cmdline = p.get('cmdline', p['name'])[:50]
            log_info(
                f"    #{i} {pid_str} {p['name']} - "
                f"+{p['growth_mb']:.0f}MB (+{p['growth_pct']:.0f}%) - {cmdline}"
            )
        else:
            cmdline = p.get('cmdline', p['name'])[:50]
            log_info(
                f"    #{i} PID:{p['pid']} {p['name']} - "
                f"{p['rss_mb']:.0f}MB ({p['pct']:.1f}%) - {cmdline}"
            )

    # Last line: Memory-consuming containers (all on one line)
    container_contributors = analyze_container_growth(state, growth_mb)
    contributor_container_names = {c['name'] for c in container_contributors}
    top_containers = get_top_containers(total_ram_mb, top_n=15)

    cont_parts = []
    # First add growth contributors
    for c in container_contributors:
        cont_parts.append(
            f"{c['name']}: +{c['growth_mb']:.0f}MB (+{c['growth_pct']:.0f}%)"
        )

    # Fill to min 5 with top consumers
    for c in top_containers:
        if len(cont_parts) >= 10:
            break
        if c['name'] not in contributor_container_names and len(cont_parts) < 5:
            cont_parts.append(f"{c['name']}: {c['rss_mb']:.0f}MB ({c['pct']:.1f}%)")

    if cont_parts:
        log_info(f"  Memory-consuming containers: {'; '.join(cont_parts[:10])}")


def reset_state_file(state_file: str) -> bool:
    """Remove the state file so the checker starts a fresh window on next run."""
    try:
        if os.path.exists(state_file):
            os.remove(state_file)
        return True
    except OSError as e:
        log_error(f"Failed to reset state file {state_file}: {e}")
        return False


def run_handler(scale: str) -> int:
    try:
        state_file = get_state_file_path(scale)
        state = load_state(state_file)

        if state is None:
            log_error(f"Could not load state file for scale: {scale}")
            return 1

        log_detection_details(state, scale)

        # Reset state so checker starts a fresh detection window
        reset_state_file(state_file)
        return 0

    except Exception as e:
        log_error(f"Error in memory_gradual_handler ({scale}): {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(description='Memory gradual increase handler')
    parser.add_argument(
        '--scale',
        type=str,
        required=True,
        choices=['short', 'medium', 'long'],
        help='Time scale for which detection occurred'
    )

    args = parser.parse_args()
    sys.exit(run_handler(args.scale))


if __name__ == "__main__":
    main()

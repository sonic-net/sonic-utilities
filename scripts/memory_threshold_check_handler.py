#!/usr/bin/env python3

import sys
import os
import syslog
import subprocess
import re
from heapq import nlargest
import psutil
from swsscommon.swsscommon import SonicV2Connector
from utilities_common.auto_techsupport_helper import (
    CFG_DB,
    STATE_DB,
    invoke_ts_command_rate_limited,
    EVENT_TYPE_MEMORY
)

# Exit codes (must match memory_threshold_check.py)
EXIT_SUCCESS = 0  # Success
EXIT_FAILURE = 1  # General failure, no techsupport is invoked
EXIT_THRESHOLD = 2  # Configurable threshold (logs + techsupport)
EXIT_THRESHOLD_60 = 3  # 60% threshold (logs only)
EXIT_THRESHOLD_80 = 4  # 80% threshold (logs only)
EXIT_THRESHOLD_90 = 5  # 90% threshold (logs only)

# Map exit codes to threshold descriptions
EXIT_CODE_TO_THRESHOLD = {
    EXIT_THRESHOLD_60: "60%",
    EXIT_THRESHOLD_80: "80%",
    EXIT_THRESHOLD_90: "90%",
}


def get_top_memory_processes(count=5):
    """Returns top N memory-consuming processes"""
    try:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'memory_percent', 'cmdline']):
            try:
                pinfo = proc.info
                pid = str(pinfo['pid'])
                mem_percent = pinfo.get('memory_percent', 0.0)

                cmdline = pinfo.get('cmdline', [])
                if cmdline:
                    command = ' '.join(cmdline)
                else:
                    command = pinfo.get('name', 'unknown')

                processes.append((pid, mem_percent, command))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        top_procs = nlargest(count, processes, key=lambda x: x[1])
        return [(pid, f"{mem:.1f}", cmd) for pid, mem, cmd in top_procs]
    except Exception:
        return []


def get_top_memory_containers(count=5):
    """Returns top N memory-consuming containers"""
    try:
        cmd = ["docker", "stats", "--no-stream", "--format", "{{.Name}},{{.MemUsage}},{{.MemPerc}}"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split('\n')

        containers = []
        for line in lines:
            if not line:
                continue
            try:
                parts = line.split(',')
                if len(parts) >= 3:
                    name = parts[0]
                    mem_usage_str = parts[1].split('/')[0].strip()
                    mem_percent_str = parts[2].strip().rstrip('%')

                    mem_mb = parse_memory_size(mem_usage_str)
                    mem_percent = float(mem_percent_str)

                    containers.append((name, mem_mb, mem_percent))
            except (ValueError, IndexError):
                continue

        containers.sort(key=lambda x: x[1], reverse=True)
        return containers[:count]
    except Exception:
        return []


def parse_memory_size(size_str):
    """Parse memory size string like '1.5GiB' to MB"""
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


def log_top_processes_and_containers():
    """Log top 5 memory-consuming processes and containers"""
    # Get system memory info
    try:
        with open("/proc/meminfo") as fd:
            lines = fd.read().split("\n")
            rows = [line.split() for line in lines]
            memory_stats = {row[0][:-1]: int(row[1]) for row in rows if len(row) >= 2}

        memory_total_kb = memory_stats.get("MemTotal", 0)
        memory_free_kb = memory_stats.get("MemAvailable", 0)
        memory_used_kb = memory_total_kb - memory_free_kb
        memory_total_mb = memory_total_kb / 1024.0
        memory_used_mb = memory_used_kb / 1024.0
        memory_free_mb = memory_free_kb / 1024.0
        memory_used_percent = (memory_used_mb / memory_total_mb) * 100 if memory_total_mb > 0 else 0

        # Log memory summary
        syslog.syslog(
            syslog.LOG_INFO,
            f"Current memory: {memory_used_mb:.2f} MB used, {memory_free_mb:.2f} MB free "
            f"({memory_used_percent:.2f}% used)"
        )

        # Get and log top 5 processes
        top_processes = get_top_memory_processes(5)
        if top_processes:
            syslog.syslog(syslog.LOG_INFO, "Top 5 memory-consuming processes:")
            for idx, (pid, mem_percent, command) in enumerate(top_processes, 1):
                mem_mb = (float(mem_percent) / 100.0) * memory_total_mb
                proc_name = command.split()[0].split('/')[-1] if command else "unknown"
                syslog.syslog(
                    syslog.LOG_INFO,
                    f"  #{idx} PID:{pid} {proc_name} - {mem_mb:.2f}MB ({mem_percent}%) - {command[:60]}"
                )

        # Get and log top 5 containers
        top_containers = get_top_memory_containers(5)
        if top_containers:
            container_strs = []
            for name, mem_mb, mem_percent in top_containers:
                container_strs.append(f"{name}: {mem_mb:.2f}MB ({mem_percent:.2f}%)")
            containers_line = "; ".join(container_strs)
            syslog.syslog(syslog.LOG_INFO, f"Top 5 memory-consuming containers: {containers_line}")
    except Exception:
        pass


def main():
    output = os.environ.get("MONIT_DESCRIPTION")
    syslog.openlog(logoption=syslog.LOG_PID)
    db = SonicV2Connector(use_unix_socket_path=True)
    db.connect(CFG_DB)
    db.connect(STATE_DB)

    # Monit passes the exit code. Older sonic-host config execs this script
    # with no argument and means the configurable threshold (exit 2).
    if len(sys.argv) > 1:
        exit_code = int(sys.argv[1])
    else:
        exit_code = EXIT_THRESHOLD

    # Get threshold name - for configurable threshold, read actual value from CONFIG_DB
    if exit_code == EXIT_THRESHOLD:
        config_threshold = db.get(CFG_DB, "AUTO_TECHSUPPORT|GLOBAL", "available_mem_threshold")
        # Convert available threshold to used threshold (e.g., 10% available = 90% used)
        if config_threshold:
            used_threshold = 100 - float(config_threshold)
            threshold_name = f"{used_threshold:.0f}%"
        else:
            threshold_name = ""
    else:
        threshold_name = EXIT_CODE_TO_THRESHOLD.get(exit_code, f"unknown({exit_code})")
    if not output:
        # Checker-spawned 60%/80% has MONIT_* stripped. Other codes (including
        # configurable threshold / techsupport) still require a monit description.
        if exit_code not in (EXIT_THRESHOLD_60, EXIT_THRESHOLD_80):
            syslog.syslog(
                syslog.LOG_ERR,
                "Unexpected value in environment variable MONIT_DESCRIPTION",
            )
            return EXIT_FAILURE
        container = None
    else:
        if "--" not in output:
            syslog.syslog(syslog.LOG_ERR, "Unexpected value in environment variable MONIT_DESCRIPTION")
            return EXIT_FAILURE

        monit_output = output.split("--")[1].strip()
        # If the output of memory_threshold_check is empty
        # that means that memory threshold check failed for the host.
        # In this case monit inserts "no output" string in MONIT_DESCRIPTION
        if monit_output == "no output":
            container = None
        else:
            container = monit_output

    # Log threshold crossed and top processes/containers
    component = f"container:{container}" if container else "host"
    syslog.syslog(
        syslog.LOG_WARNING,
        f"Memory threshold crossed: {threshold_name} ({component})"
    )
    log_top_processes_and_containers()

    # Only generate techsupport for configurable threshold (exit code 2)
    # Fixed thresholds (60%, 80%, 90%) only generate logs
    if exit_code == EXIT_THRESHOLD:
        invoke_ts_command_rate_limited(db, EVENT_TYPE_MEMORY, container)

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())

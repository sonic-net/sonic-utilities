#!/usr/bin/env python3

import sys
import os
import syslog
import subprocess

# Exit codes
EXIT_SUCCESS = 0  # Success
EXIT_FAILURE = 1  # General failure


def get_top_cpu_processes(count=5):
    """Get top N CPU-consuming processes
    
    Args:
        count (int): Number of top processes to return
        
    Returns:
        list: List of tuples (pid, process_name, cpu_percent, command)
    """
    try:
        cmd = ["ps", "aux", "--sort=-%cpu"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        
        if result.returncode != 0:
            return []
        
        lines = result.stdout.strip().split('\n')
        processes = []
        
        for line in lines[1:count+1]:
            parts = line.split()
            if len(parts) >= 11:
                pid = parts[1]
                cpu_percent = parts[2]
                command = ' '.join(parts[10:])
                proc_name = command.split()[0].split('/')[-1] if command else "unknown"
                processes.append((pid, proc_name, cpu_percent, command[:60]))
        
        return processes
    except Exception:
        return []


def get_top_cpu_containers(count=5):
    """Get top N CPU-consuming containers directly from docker stats
    
    Args:
        count (int): Number of top containers to return
        
    Returns:
        list: List of tuples (container_name, cpu_percent)
    """
    try:
        # Use docker stats --no-stream to get current stats (not cached)
        cmd = ["docker", "stats", "--no-stream", "--format", "{{.Name}}\t{{.CPUPerc}}"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            return []
        
        containers = []
        lines = result.stdout.strip().split('\n')
        
        for line in lines:
            if not line:
                continue
            parts = line.split('\t')
            if len(parts) >= 2:
                name = parts[0]
                cpu_str = parts[1].replace('%', '')
                try:
                    cpu_percent = float(cpu_str)
                    containers.append((name, cpu_percent))
                except ValueError:
                    continue
        
        # Sort by CPU usage descending
        containers.sort(key=lambda x: x[1], reverse=True)
        return containers[:count]
    except Exception:
        return []


def main():
    syslog.openlog(logoption=syslog.LOG_PID)
    
    # Get CPU core count for normalization
    try:
        cpu_count = os.cpu_count() or 1
    except Exception:
        cpu_count = 1
    
    syslog.syslog(
        syslog.LOG_INFO,
        f"CPU usage threshold handler triggered - logging top consumers ({cpu_count} CPU cores)"
    )
    
    # Log top 5 processes
    top_processes = get_top_cpu_processes(5)
    if top_processes:
        syslog.syslog(syslog.LOG_INFO, "Top 5 CPU-consuming processes:")
        for idx, (pid, proc_name, cpu_pct, command) in enumerate(top_processes, 1):
            try:
                pct_float = float(cpu_pct)
                # Normalize to system capacity (0-100%)
                normalized_pct = pct_float / cpu_count
                syslog.syslog(
                    syslog.LOG_INFO,
                    f"  #{idx} PID:{pid} {proc_name} - {normalized_pct:.1f}% - {command}"
                )
            except ValueError:
                syslog.syslog(
                    syslog.LOG_INFO,
                    f"  #{idx} PID:{pid} {proc_name} - {cpu_pct}% - {command}"
                )
    else:
        syslog.syslog(syslog.LOG_INFO, "Could not retrieve top CPU-consuming processes")
    
    # Log top 5 containers on single line with semicolons (same format as memory handler)
    top_containers = get_top_cpu_containers(5)
    if top_containers:
        container_strs = []
        for name, cpu_pct in top_containers:
            container_strs.append(f"{name}: {cpu_pct:.2f}%")
        containers_line = "; ".join(container_strs)
        syslog.syslog(syslog.LOG_INFO, f"Top 5 CPU-consuming containers: {containers_line}")
    else:
        syslog.syslog(syslog.LOG_INFO, "Could not retrieve container CPU usage")
    
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())

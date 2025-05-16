import os
import subprocess
from sonic_py_common import device_info

def get_chassis_local_interfaces():
    lst = []
    platform = device_info.get_platform()
    chassisdb_conf=os.path.join('/usr/share/sonic/device/', platform, "chassisdb.conf")
    if os.path.exists(chassisdb_conf):
        lines=[]
        with open(chassisdb_conf, 'r') as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip()
            if "chassis_internal_intfs" in line:
                data = line.split("=")
                lst = data[1].split(",")
                return lst
    return lst


def is_smartswitch():
    return hasattr(device_info, 'is_smartswitch') and device_info.is_smartswitch()


def is_dpu():
    return hasattr(device_info, 'is_dpu') and device_info.is_dpu()


# Utility to get the number of DPUs
def get_num_dpus():
    if hasattr(device_info, 'get_num_dpus'):
        return device_info.get_num_dpus()
    return 0


def is_midplane_reachable(ip):
    """
    Check if the given IP is reachable via ping.

    Args:
        ip: IP address to ping.

    Returns:
        True if reachable, False otherwise.
    """
    try:
        subprocess.check_output(["ping", "-c", "1", "-W", "1", ip], stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False


def get_dpu_ip_list(dpulist):
    """
    Retrieve DPU IPs from the platform.json structure.

    Args:
        dpulist: List of DPU names (e.g., ['dpu0', 'dpu1']) or "all"

    Returns:
        List of tuples: (dpu_name, ip)
    """
    dpu_ips = []
    platform_data = device_info.get_platform_json_data()
    if not platform_data:
        return []

    dhcp_data = platform_data.get("DHCP_SERVER_IPV4_PORT", {})

    for bridge_key, config in dhcp_data.items():
        dpu_name = bridge_key.split('|')[-1]
        if dpulist == "all" or dpu_name in dpulist:
            for ip in config.get("ips", []):
                dpu_ips.append((dpu_name, ip))

    return dpu_ips


# utility to get dpu module name list
def get_all_dpus():
    try:
        # Convert the entries in the list to uppercase
        return [dpu.upper() for dpu in device_info.get_dpu_list()]
    except Exception:
        return []


# utility to get dpu module name list and all
def get_all_dpu_options():
    dpu_list = get_all_dpus()

    # Add 'all' to the list
    dpu_list += ['all']

    return dpu_list

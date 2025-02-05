import os
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

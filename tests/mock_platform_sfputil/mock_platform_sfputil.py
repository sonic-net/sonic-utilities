import json
import os
from sonic_platform_base.platform_base import PlatformBase
from sonic_platform_base.chassis_base import ChassisBase
from sonic_platform_base.sfp_base import SfpBase
import utilities_common.platform_sfputil_helper as platform_sfputil_helper

portMap = None
RJ45Ports = None

class mock_Chassis(ChassisBase):
    def __init__(self):
        ChassisBase.__init__(self)

    def get_port_or_cage_type(self, index):
        if index in RJ45Ports:
            return SfpBase.SFP_PORT_TYPE_BIT_RJ45
        else:
            raise NotImplementedError

def mock_logical_port_name_to_physical_port_list(port_name):
    index = portMap.get(port_name)
    if not index:
        index = 0
    return [index]

def mock_platform_sfputil_read_porttab_mappings():
    global portMap
    global RJ45Ports

    with open(os.path.join(os.path.dirname(__file__), 'portmap.json')) as pm:
        jsonobj = json.load(pm)
        portMap = jsonobj['portMap']
        RJ45Ports = jsonobj['RJ45Ports']

def mock_get_first_subport(logical_port_name):
    """
    Mock function to get the first subport of a logical port.
    """
    return logical_port_name

def mock_platform_sfputil_helper():
    platform_sfputil_helper.platform_chassis = mock_Chassis()
    platform_sfputil_helper.platform_sfputil = True
    platform_sfputil_helper.platform_porttab_mapping_read = False
    platform_sfputil_helper.platform_sfputil_read_porttab_mappings = mock_platform_sfputil_read_porttab_mappings
    platform_sfputil_helper.logical_port_name_to_physical_port_list = mock_logical_port_name_to_physical_port_list
    platform_sfputil_helper.get_first_subport = mock_get_first_subport

"""
Module holding IP/VRF mock data for config CLI command of the syslog_test.py
"""

VRF_LIST = '''
[
    {
        "name": "mgmt"
    },
    {
        "name": "Vrf-Data"
    }
]
'''

VRF_MGMT_MEMBERS = '''
[
    {
        "ifname": "eth0"
    }
]
'''

VRF_DATA_MEMBERS = '''
[
    {
        "ifname": "Ethernet0"
    }
]
'''

IP_ADDR_LIST = '''
[
    {
        "ifname": "Ethernet0",
        "addr_info": [
            {
                "local": "1111::1111"
            }
        ]
    },
    {
        "ifname": "Loopback0",
        "addr_info": [
            {
                "local": "1.1.1.1"
            }
        ]
    },
    {
        "ifname": "eth0",
        "addr_info": [
            {
                "local": "3.3.3.3"
            }
        ]
    }
]
'''

def exec_cmd_mock(cmd):
    if cmd == ['ip', '--json', 'vrf', 'show']:
        return VRF_LIST
    elif cmd == ['ip', '--json', 'link', 'show', 'vrf', 'mgmt']:
        return VRF_MGMT_MEMBERS
    elif cmd == ['ip', '--json', 'link', 'show', 'vrf', 'Vrf-Data']:
        return VRF_DATA_MEMBERS
    elif cmd == ['ip', '--json', 'address', 'show']:
        return IP_ADDR_LIST
    raise Exception("{}: unknown command: {}".format(__name__, cmd))

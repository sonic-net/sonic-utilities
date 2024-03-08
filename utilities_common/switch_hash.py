from collections import Counter

from swsscommon.swsscommon import CFG_SWITCH_HASH_TABLE_NAME as CFG_SWITCH_HASH
from swsscommon.swsscommon import STATE_SWITCH_CAPABILITY_TABLE_NAME as STATE_SWITCH_CAPABILITY

#
# Hash constants ------------------------------------------------------------------------------------------------------
#

SW_CAP_HASH_FIELD_LIST_KEY = "HASH|NATIVE_HASH_FIELD_LIST"

SW_CAP_ECMP_HASH_CAPABLE_KEY = "ECMP_HASH_CAPABLE"
SW_CAP_LAG_HASH_CAPABLE_KEY = "LAG_HASH_CAPABLE"

SW_CAP_ECMP_HASH_ALGORITHM_KEY = "ECMP_HASH_ALGORITHM"
SW_CAP_ECMP_HASH_ALGORITHM_CAPABLE_KEY = "ECMP_HASH_ALGORITHM_CAPABLE"
SW_CAP_LAG_HASH_ALGORITHM_KEY = "LAG_HASH_ALGORITHM"
SW_CAP_LAG_HASH_ALGORITHM_CAPABLE_KEY = "LAG_HASH_ALGORITHM_CAPABLE"

SW_HASH_KEY = "GLOBAL"
SW_CAP_KEY = "switch"

HASH_FIELD_LIST = [
    "IN_PORT",
    "DST_MAC",
    "SRC_MAC",
    "ETHERTYPE",
    "VLAN_ID",
    "IP_PROTOCOL",
    "DST_IP",
    "SRC_IP",
    "L4_DST_PORT",
    "L4_SRC_PORT",
    "INNER_DST_MAC",
    "INNER_SRC_MAC",
    "INNER_ETHERTYPE",
    "INNER_IP_PROTOCOL",
    "INNER_DST_IP",
    "INNER_SRC_IP",
    "INNER_L4_DST_PORT",
    "INNER_L4_SRC_PORT"
]

HASH_ALGORITHM = [
    "CRC",
    "XOR",
    "RANDOM",
    "CRC_32LO",
    "CRC_32HI",
    "CRC_CCITT",
    "CRC_XOR"
]

SYSLOG_IDENTIFIER = "switch_hash"

#
# Hash helpers --------------------------------------------------------------------------------------------------------
#

def get_param(ctx, name):
    """ Get click parameter """
    for param in ctx.command.params:
        if param.name == name:
            return param
    return None


def get_param_hint(ctx, name):
    """ Get click parameter description """
    return get_param(ctx, name).get_error_hint(ctx)


def get_dupes(obj_list):
    """ Get list duplicate items """
    return [k for k, v in Counter(obj_list).items() if v > 1]


def to_str(obj_list):
    """ Convert list to comma-separated representation """
    return ", ".join(obj_list)

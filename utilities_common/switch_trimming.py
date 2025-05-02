from utilities_common import db

from swsscommon.swsscommon import CFG_SWITCH_TRIMMING_TABLE_NAME as CFG_SWITCH_TRIMMING  # noqa: F401
from swsscommon.swsscommon import STATE_SWITCH_CAPABILITY_TABLE_NAME as STATE_SWITCH_CAPABILITY  # noqa: F401


#
# Constants -----------------------------------------------------------------------------------------------------------
#


STATE_CAP_TRIMMING_CAPABLE_KEY = "SWITCH_TRIMMING_CAPABLE"
STATE_CAP_QUEUE_MODE_KEY = "SWITCH|PACKET_TRIMMING_QUEUE_RESOLUTION_MODE"

STATE_CAP_QUEUE_MODE_DYNAMIC = "DYNAMIC"
STATE_CAP_QUEUE_MODE_STATIC = "STATIC"

CFG_TRIM_QUEUE_INDEX_DYNAMIC = "dynamic"

CFG_TRIM_KEY = "GLOBAL"
STATE_CAP_KEY = "switch"

UINT32_MAX = 4294967295
UINT8_MAX = 255

SYSLOG_IDENTIFIER = "switch_trimming"


#
# Helpers -------------------------------------------------------------------------------------------------------------
#


def get_db(ctx):
    """ Get DB object """
    return ctx.find_object(db.Db).db


def to_str(obj_dict):
    """ Convert dict to comma-separated representation """
    return ", ".join(["{}={}".format(k, v) for k, v in obj_dict.items() if v])

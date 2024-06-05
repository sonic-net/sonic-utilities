from swsscommon.swsscommon import CFG_BGP_DEVICE_GLOBAL_TABLE_NAME as CFG_BGP_DEVICE_GLOBAL # noqa

#
# BGP constants -------------------------------------------------------------------------------------------------------
#

BGP_DEVICE_GLOBAL_KEY = "STATE"

SYSLOG_IDENTIFIER = "bgp-cli"


#
# BGP helpers ---------------------------------------------------------------------------------------------------------
#


def to_str(state):
    """ Convert boolean to string representation """
    if state == "true":
        return "enabled"
    elif state == "false":
        return "disabled"
    return state

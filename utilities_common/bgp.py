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
    """ Convert boolean to string representation or integer string to '<state> (Mbps/Gbps)' """
    if state == "true":
        return "enabled"
    elif state == "false":
        return "disabled"
    elif state.isdigit():
        value = int(state)
        if value >= 1000:
            return f"{value / 1000:.2f} Gbps"
        else:
            return f"{value} Mbps"
    return state

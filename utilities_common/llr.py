from sonic_py_common import multi_asic
from swsscommon.swsscommon import SonicV2Connector

LLR_CAPABLE_KEY = "SWITCH_CAPABILITY|switch"
LLR_CAPABLE_FIELD = "LLR_CAPABLE"


def is_llr_capable(namespace=None):
    """
    Check STATE_DB SWITCH_CAPABILITY|switch for LLR_CAPABLE == "true"
    in the given namespace.
    Returns True if supported, False otherwise.
    """
    if namespace is None:
        namespace = multi_asic.DEFAULT_NAMESPACE
    state_db = SonicV2Connector(use_unix_socket_path=True, namespace=str(namespace))
    state_db.connect(state_db.STATE_DB)
    val = state_db.get(state_db.STATE_DB, LLR_CAPABLE_KEY, LLR_CAPABLE_FIELD)
    return val == "true"

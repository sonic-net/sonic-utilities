from swsscommon.swsscommon import SonicV2Connector

SWITCH_CAPABILITY_KEY = "SWITCH_CAPABILITY|switch"
MIRROR_SESSION_LABEL_CAPABLE_FIELD = "MIRROR_SESSION_LABEL_CAPABLE"


def connect_mirror_session_state_db(namespace=None):
    """Open STATE_DB for one ASIC namespace.

    Args:
        namespace: ASIC namespace, or None for the default (single-ASIC) namespace.
    """
    state_db = SonicV2Connector(use_unix_socket_path=True, namespace=namespace)
    state_db.connect(state_db.STATE_DB, False)
    return state_db


def is_mirror_session_label_capable(state_db):
    """Check whether the ASIC supports mirror-session labels.

    Args:
        state_db: Connected STATE_DB client for the target ASIC namespace.

    Returns:
        True only when STATE_DB publishes MIRROR_SESSION_LABEL_CAPABLE=true.
        A missing field is not supported. Orchagent publishes true when the SAI
        capability query itself fails, so adapters without the query stay allowed.
    """
    value = state_db.get(
        state_db.STATE_DB,
        SWITCH_CAPABILITY_KEY,
        MIRROR_SESSION_LABEL_CAPABLE_FIELD,
    )
    return value == "true"

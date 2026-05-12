"""Unit tests for the monitor-link-group integration in scripts/intfutil.

`scripts/intfutil` is a Click script with no .py extension and a heavy
import surface. To keep these tests self-contained and runnable without
the SONiC dev container, we slice just the helper, the two getters under
test, and the constants they reference out of the script via regex and
exec them into a fresh namespace. The functions are pure data
transformations on a SonicV2Connector-like handle, so a small MockDb is
sufficient.
"""

from __future__ import annotations

import os
import re
import types

INTFUTIL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "intfutil"
)


class _MockDb:
    """Mimics swsscommon.SonicV2Connector for the surface scripts/intfutil
    actually uses: db attributes (APPL_DB, STATE_DB, CONFIG_DB) and
    `.get(db, table_id, field)`.
    """

    APPL_DB = "APPL_DB"
    STATE_DB = "STATE_DB"
    CONFIG_DB = "CONFIG_DB"
    COUNTERS_DB = "COUNTERS_DB"

    def __init__(self, data):
        self._data = data  # {db: {table_id: {field: value}}}

    def get(self, db, table_id, field):
        return self._data.get(db, {}).get(table_id, {}).get(field)


def _load_intfutil():
    """Pull the constants, helper, and two modified getters out of the
    intfutil script into a fresh namespace, without executing the heavy
    import block at the top of the file (tabulate, swsssdk, click, etc.).
    """
    src = open(INTFUTIL_PATH).read()
    ns: dict = {
        "natsorted": sorted,
        "RJ45_PORT_TYPE": "RJ45",
        "is_rj45_port": lambda *a, **k: False,
        "multi_asic": types.SimpleNamespace(PORT_ROLE="role", DPU_CONNECT_PORT="Dpc"),
        # Stub helpers the modified getters call but we don't exercise here.
        "port_speed_parse": lambda speed, optics: speed,
        "port_optics_get": lambda *a, **k: "N/A",
    }
    # Pull every top-level constant assignment up to the first `def`.
    first_def = src.find("\ndef ")
    consts = src[:first_def] if first_def > 0 else src
    for line in consts.splitlines():
        line = line.rstrip()
        if not line or line.startswith(("#", "from ", "import ", "try", "    ", "\t")):
            continue
        if re.match(r"^[A-Z_][A-Z0-9_]*\s*=\s*", line):
            try:
                exec(line, ns)
            except Exception:
                pass
    # Pull the three function defs we care about.
    for name in (
        "_is_held_down_by_monitor_link_group",
        "appl_db_port_status_get",
        "appl_db_portchannel_status_get",
    ):
        m = re.search(rf"^def {name}\(.*?(?=^def |\Z)", src, re.M | re.S)
        assert m, f"could not find def {name} in intfutil"
        exec(m.group(0), ns)
    return types.SimpleNamespace(**ns)


_intfutil = _load_intfutil()


# ---------------------------------------------------------------------------
# _is_held_down_by_monitor_link_group
# ---------------------------------------------------------------------------


def test_held_down_returns_false_when_db_is_none():
    assert _intfutil._is_held_down_by_monitor_link_group(None, "Ethernet0") is False


def test_held_down_returns_false_when_no_entry():
    db = _MockDb({"STATE_DB": {}})
    assert _intfutil._is_held_down_by_monitor_link_group(db, "Ethernet0") is False


def test_held_down_returns_false_when_state_field_missing():
    db = _MockDb({"STATE_DB": {"MONITOR_LINK_GROUP_MEMBER|Ethernet0": {}}})
    assert _intfutil._is_held_down_by_monitor_link_group(db, "Ethernet0") is False


def test_held_down_returns_false_when_state_is_allow_up():
    db = _MockDb(
        {
            "STATE_DB": {
                "MONITOR_LINK_GROUP_MEMBER|Ethernet0": {"state": "allow_up"}
            }
        }
    )
    assert _intfutil._is_held_down_by_monitor_link_group(db, "Ethernet0") is False


def test_held_down_returns_true_when_state_is_force_down():
    db = _MockDb(
        {
            "STATE_DB": {
                "MONITOR_LINK_GROUP_MEMBER|Ethernet0": {"state": "force_down"}
            }
        }
    )
    assert _intfutil._is_held_down_by_monitor_link_group(db, "Ethernet0") is True


# ---------------------------------------------------------------------------
# appl_db_port_status_get
# ---------------------------------------------------------------------------


def test_port_status_admin_up_passes_through():
    """admin_status=up: helper is not consulted, value returned as-is."""
    db = _MockDb({"APPL_DB": {"PORT_TABLE:Ethernet0": {"admin_status": "up"}}})
    assert _intfutil.appl_db_port_status_get(db, "Ethernet0", "admin_status") == "up"


def test_port_status_user_shutdown_without_mlg_entry_renders_down():
    """admin_status=down with no MLG entry: plain 'down' (user shutdown)."""
    db = _MockDb({"APPL_DB": {"PORT_TABLE:Ethernet0": {"admin_status": "down"}}})
    assert _intfutil.appl_db_port_status_get(db, "Ethernet0", "admin_status") == "down"


def test_port_status_user_shutdown_with_healthy_group_renders_down():
    """admin_status=down with state=allow_up: plain 'down' (user shutdown)."""
    db = _MockDb(
        {
            "APPL_DB": {"PORT_TABLE:Ethernet0": {"admin_status": "down"}},
            "STATE_DB": {
                "MONITOR_LINK_GROUP_MEMBER|Ethernet0": {"state": "allow_up"}
            },
        }
    )
    assert _intfutil.appl_db_port_status_get(db, "Ethernet0", "admin_status") == "down"


def test_port_status_held_by_mlg_renders_error_down():
    """admin_status=down with state=force_down: 'error-down (mlg)'."""
    db = _MockDb(
        {
            "APPL_DB": {"PORT_TABLE:Ethernet0": {"admin_status": "down"}},
            "STATE_DB": {
                "MONITOR_LINK_GROUP_MEMBER|Ethernet0": {"state": "force_down"}
            },
        }
    )
    assert (
        _intfutil.appl_db_port_status_get(db, "Ethernet0", "admin_status")
        == "error-down (mlg)"
    )


# ---------------------------------------------------------------------------
# appl_db_portchannel_status_get
# ---------------------------------------------------------------------------


def test_portchannel_status_admin_up_passes_through():
    db = _MockDb(
        {
            "APPL_DB": {"LAG_TABLE:PortChannel100": {"admin_status": "up"}},
        }
    )
    assert (
        _intfutil.appl_db_portchannel_status_get(
            db, None, "PortChannel100", "admin_status", {}, None
        )
        == "up"
    )


def test_portchannel_status_user_shutdown_without_mlg_renders_down():
    db = _MockDb(
        {
            "APPL_DB": {"LAG_TABLE:PortChannel100": {"admin_status": "down"}},
        }
    )
    assert (
        _intfutil.appl_db_portchannel_status_get(
            db, None, "PortChannel100", "admin_status", {}, None
        )
        == "down"
    )


def test_portchannel_status_held_by_mlg_renders_error_down():
    db = _MockDb(
        {
            "APPL_DB": {"LAG_TABLE:PortChannel100": {"admin_status": "down"}},
            "STATE_DB": {
                "MONITOR_LINK_GROUP_MEMBER|PortChannel100": {"state": "force_down"}
            },
        }
    )
    assert (
        _intfutil.appl_db_portchannel_status_get(
            db, None, "PortChannel100", "admin_status", {}, None
        )
        == "error-down (mlg)"
    )

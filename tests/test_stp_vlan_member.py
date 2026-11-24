import sys
import types
from unittest.mock import MagicMock, call, patch

for _name in ("sonic_yang", "sonic_yang_ext"):
    sys.modules.setdefault(_name, types.ModuleType(_name))

from config.stp import (  # noqa: E402
    MST_DEFAULT_PORT_PRIORITY,
    clear_stp_config_on_vlan_member_delete,
    ensure_stp_config_on_vlan_member_add,
)
from config.vlan import disable_stp_on_vlan_port, enable_stp_on_port  # noqa: E402


def _db(mode="mst", vlan_members=None, mst_inst=None, mst_port_keys=None, stp_port=None, mst_ports=None):
    db = MagicMock()
    vlan_members = vlan_members if vlan_members is not None else {}
    mst_inst = mst_inst if mst_inst is not None else {"0": {"bridge_priority": "32768"}}
    mst_port_keys = mst_port_keys if mst_port_keys is not None else []
    stp_port = stp_port if stp_port is not None else {}
    mst_ports = mst_ports if mst_ports is not None else {}

    def get_entry(table, key):
        if table == "STP" and key == "GLOBAL":
            return {"mode": mode} if mode else {}
        if table == "STP_PORT":
            return dict(stp_port.get(key, {}))
        if table == "STP_MST_PORT":
            return dict(mst_ports.get(key, {}))
        return {}

    def get_table(table):
        if table == "VLAN_MEMBER":
            return vlan_members
        if table == "STP_MST_INST":
            return mst_inst
        return {}

    db.get_entry.side_effect = get_entry
    db.get_table.side_effect = get_table
    db.get_keys.side_effect = lambda table: list(mst_port_keys) if table == "STP_MST_PORT" else []
    return db


def test_delete_last_mst_member_clears_stp_port_and_mst_port():
    db = _db(
        vlan_members={("Vlan100", "Ethernet4"): {"tagging_mode": "tagged"},
                      ("Vlan100", "Ethernet0"): {"tagging_mode": "tagged"}},
        mst_port_keys=[("0", "Ethernet4"), ("0", "Ethernet0")],
    )

    clear_stp_config_on_vlan_member_delete(db, "Vlan100", "Ethernet4")

    assert call("STP_VLAN_PORT", "Vlan100|Ethernet4", None) in db.set_entry.call_args_list
    assert call("STP_MST_PORT", "0|Ethernet4", None) in db.set_entry.call_args_list
    assert call("STP_PORT", "Ethernet4", None) in db.set_entry.call_args_list
    assert call("STP_MST_PORT", "0|Ethernet0", None) not in db.set_entry.call_args_list
    assert call("STP_PORT", "Ethernet0", None) not in db.set_entry.call_args_list


def test_delete_mst_member_keeps_rows_while_another_vlan_remains():
    db = _db(
        vlan_members={
            ("Vlan100", "Ethernet4"): {"tagging_mode": "tagged"},
            ("Vlan200", "Ethernet4"): {"tagging_mode": "tagged"},
        },
        mst_port_keys=[("0", "Ethernet4")],
    )

    clear_stp_config_on_vlan_member_delete(db, "Vlan100", "Ethernet4")

    assert call("STP_VLAN_PORT", "Vlan100|Ethernet4", None) in db.set_entry.call_args_list
    assert call("STP_MST_PORT", "0|Ethernet4", None) not in db.set_entry.call_args_list
    assert call("STP_PORT", "Ethernet4", None) not in db.set_entry.call_args_list


def test_delete_mst_member_drops_instance_row_and_keeps_cist():
    db = _db(
        vlan_members={
            ("Vlan100", "Ethernet4"): {"tagging_mode": "tagged"},
            ("Vlan200", "Ethernet4"): {"tagging_mode": "tagged"},
        },
        mst_inst={
            "0": {"bridge_priority": "32768"},
            "1": {"bridge_priority": "32768", "vlan_list": "200"},
        },
        mst_port_keys=[("0", "Ethernet4"), ("1", "Ethernet4")],
    )

    clear_stp_config_on_vlan_member_delete(db, "Vlan200", "Ethernet4")

    assert call("STP_MST_PORT", "1|Ethernet4", None) in db.set_entry.call_args_list
    assert call("STP_MST_PORT", "0|Ethernet4", None) not in db.set_entry.call_args_list
    assert call("STP_PORT", "Ethernet4", None) not in db.set_entry.call_args_list


def test_delete_last_pvst_member_clears_stp_port_only():
    db = _db(
        mode="pvst",
        vlan_members={("Vlan100", "Ethernet4"): {"tagging_mode": "untagged"}},
        mst_port_keys=[("0", "Ethernet4")],
    )

    clear_stp_config_on_vlan_member_delete(db, "Vlan100", "Ethernet4")

    assert call("STP_VLAN_PORT", "Vlan100|Ethernet4", None) in db.set_entry.call_args_list
    assert call("STP_PORT", "Ethernet4", None) in db.set_entry.call_args_list
    assert call("STP_MST_PORT", "0|Ethernet4", None) not in db.set_entry.call_args_list


def test_delete_does_nothing_when_stp_disabled():
    db = _db(
        mode=None,
        vlan_members={("Vlan100", "Ethernet4"): {}},
        mst_port_keys=[("0", "Ethernet4")],
    )

    clear_stp_config_on_vlan_member_delete(db, "Vlan100", "Ethernet4")

    db.set_entry.assert_not_called()


def test_add_mst_member_creates_missing_stp_port_and_mst_port():
    db = _db(vlan_members={})

    ensure_stp_config_on_vlan_member_add(db, "Ethernet4", "Vlan100")

    stp_port_calls = [c for c in db.set_entry.call_args_list if c.args[0] == "STP_PORT"]
    assert stp_port_calls
    assert stp_port_calls[0].args[1] == "Ethernet4"
    assert stp_port_calls[0].args[2]["enabled"] == "true"
    assert stp_port_calls[0].args[2]["link_type"] == "auto"
    assert call("STP_MST_PORT", "0|Ethernet4", {"priority": MST_DEFAULT_PORT_PRIORITY}) in db.set_entry.call_args_list


def test_add_mst_member_does_not_overwrite_existing_rows():
    db = _db(
        stp_port={"Ethernet4": {"enabled": "true", "edge_port": "true", "link_type": "shared"}},
        mst_ports={"0|Ethernet4": {"priority": "64"}},
    )

    ensure_stp_config_on_vlan_member_add(db, "Ethernet4", "Vlan100")

    db.set_entry.assert_not_called()


def test_add_mst_member_creates_mapped_instance_and_cist():
    db = _db(
        mst_inst={
            "0": {"bridge_priority": "32768"},
            "1": {"bridge_priority": "32768", "vlan_list": "200"},
        }
    )

    ensure_stp_config_on_vlan_member_add(db, "Ethernet4", "Vlan200")

    assert call("STP_MST_PORT", "0|Ethernet4", {"priority": MST_DEFAULT_PORT_PRIORITY}) in db.set_entry.call_args_list
    assert call("STP_MST_PORT", "1|Ethernet4", {"priority": MST_DEFAULT_PORT_PRIORITY}) in db.set_entry.call_args_list


@patch("config.vlan.stp.clear_stp_config_on_vlan_member_delete")
@patch("config.vlan.stp.ensure_stp_config_on_vlan_member_add")
def test_vlan_member_helpers_delegate_to_stp(mock_ensure, mock_clear):
    db = MagicMock()
    enable_stp_on_port(db, "Ethernet4", "Vlan100")
    disable_stp_on_vlan_port(db, "Vlan100", "Ethernet4")

    mock_ensure.assert_called_once_with(db, "Ethernet4", "Vlan100")
    mock_clear.assert_called_once_with(db, "Vlan100", "Ethernet4")

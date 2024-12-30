import pytest
from unittest.mock import MagicMock
from click import Context
from config.stp import (
    get_intf_list_in_vlan_member_table,
    is_valid_root_guard_timeout,
    is_valid_forward_delay,
    is_valid_hello_interval,
    is_valid_max_age,
    is_valid_bridge_priority,
    validate_params,
    is_valid_stp_vlan_parameters,
    is_valid_stp_global_parameters,
    update_stp_vlan_parameter,
    check_if_vlan_exist_in_db,
    enable_stp_for_vlans,
    get_stp_enabled_vlan_count,
    vlan_enable_stp,
    interface_enable_stp,
    is_vlan_configured_interface,
    is_interface_vlan_member,
    get_vlan_list_for_interface,
    get_pc_member_port_list,
    get_vlan_list_from_stp_vlan_intf_table,
    get_intf_list_from_stp_vlan_intf_table,
    is_portchannel_member_port,
    enable_stp_for_interfaces,
    is_global_stp_enabled,
    check_if_global_stp_enabled,
    get_global_stp_mode,
    get_global_stp_forward_delay,
    get_global_stp_hello_time,
    get_global_stp_max_age,
    get_global_stp_priority,
    get_bridge_mac_address,
    do_vlan_to_instance0,
    enable_mst_for_interfaces,
    disable_global_pvst,
    disable_global_mst
)

def test_get_intf_list_in_vlan_member_table():
    mock_db = MagicMock()
    mock_db.get_table.return_value = {
        ('Vlan10', 'Ethernet0'): {},
        ('Vlan20', 'Ethernet1'): {}
    }

    expected_interfaces = ['Ethernet0', 'Ethernet1']
    result = get_intf_list_in_vlan_member_table(mock_db)

    assert result == expected_interfaces
    mock_db.get_table.assert_called_once_with('VLAN_MEMBER')

def test_is_valid_root_guard_timeout():
    mock_ctx = MagicMock()

    # Valid case
    try:
        is_valid_root_guard_timeout(mock_ctx, 30)
    except SystemExit:
        pytest.fail("Unexpected failure on valid root guard timeout")

    # Invalid case
    with pytest.raises(SystemExit):
        is_valid_root_guard_timeout(mock_ctx, 700)

def test_is_valid_forward_delay():
    mock_ctx = MagicMock()

    # Valid case
    try:
        is_valid_forward_delay(mock_ctx, 15)
    except SystemExit:
        pytest.fail("Unexpected failure on valid forward delay")

    # Invalid case
    with pytest.raises(SystemExit):
        is_valid_forward_delay(mock_ctx, 31)

def test_is_valid_stp_vlan_parameters():
    mock_ctx = MagicMock()
    mock_db = MagicMock()
    mock_db.get_entry.return_value = {
        "forward_delay": 15,
        "max_age": 20,
        "hello_time": 2
    }

    # Valid case
    try:
        is_valid_stp_vlan_parameters(mock_ctx, mock_db, "Vlan10", "max_age", 20)
    except SystemExit:
        pytest.fail("Unexpected failure on valid STP VLAN parameters")

    # Invalid case
    with pytest.raises(SystemExit):
        is_valid_stp_vlan_parameters(mock_ctx, mock_db, "Vlan10", "max_age", 50)

def test_enable_stp_for_vlans():
    mock_db = MagicMock()
    mock_db.get_table.return_value = ["Vlan10", "Vlan20"]

    enable_stp_for_vlans(mock_db)

    mock_db.set_entry.assert_any_call('STP_VLAN', 'Vlan10', {
        'enabled': 'true',
        'forward_delay': mock_db.get_entry.return_value.get('forward_delay'),
        'hello_time': mock_db.get_entry.return_value.get('hello_time'),
        'max_age': mock_db.get_entry.return_value.get('max_age'),
        'priority': mock_db.get_entry.return_value.get('priority')
    })

def test_is_global_stp_enabled():
    mock_db = MagicMock()

    # Enabled case
    mock_db.get_entry.return_value = {"mode": "pvst"}
    assert is_global_stp_enabled(mock_db) is True

    # Disabled case
    mock_db.get_entry.return_value = {"mode": "none"}
    assert is_global_stp_enabled(mock_db) is False

def test_disable_global_pvst():
    mock_db = MagicMock()

    disable_global_pvst(mock_db)

    mock_db.set_entry.assert_called_once_with('STP', "GLOBAL", None)
    mock_db.delete_table.assert_any_call('STP_VLAN')
    mock_db.delete_table.assert_any_call('STP_PORT')
    mock_db.delete_table.assert_any_call('STP_VLAN_PORT')

def test_disable_global_mst():
    mock_db = MagicMock()

    disable_global_mst(mock_db)

    mock_db.set_entry.assert_called_once_with('STP', "GLOBAL", None)
    mock_db.delete_table.assert_any_call('STP_MST')
    mock_db.delete_table.assert_any_call('STP_MST_INST')
    mock_db.delete_table.assert_any_call('STP_MST_PORT')
    mock_db.delete_table.assert_any_call('STP_PORT')

def test_validate_params():
    mock_ctx = MagicMock()

    # Valid parameter
    try:
        validate_params(mock_ctx, "bridge_priority", 32768)
    except SystemExit:
        pytest.fail("Unexpected failure on valid parameter")

    # Invalid parameter
    with pytest.raises(SystemExit):
        validate_params(mock_ctx, "bridge_priority", 99999)

def test_get_bridge_mac_address():
    mock_db = MagicMock()
    mock_db.get_entry.return_value = {"mac_address": "00:11:22:33:44:55"}

    result = get_bridge_mac_address(mock_db)

    assert result == "00:11:22:33:44:55"
    mock_db.get_entry.assert_called_once_with("DEVICE_METADATA", "localhost")

def test_get_global_stp_priority():
    mock_db = MagicMock()
    mock_db.get_entry.return_value = {"priority": "32768"}

    result = get_global_stp_priority(mock_db)

    assert result == 32768
    mock_db.get_entry.assert_called_once_with("STP", "GLOBAL")

def test_get_vlan_list_for_interface():
    mock_db = MagicMock()
    mock_db.get_table.return_value = {
        ("Vlan10", "Ethernet0"): {},
        ("Vlan20", "Ethernet0"): {}
    }

    result = get_vlan_list_for_interface(mock_db, "Ethernet0")

    assert result == ["Vlan10", "Vlan20"]
    mock_db.get_table.assert_called_once_with("VLAN_MEMBER")

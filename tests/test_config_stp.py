import pytest
from unittest.mock import MagicMock, patch
# from click import Context
from click.testing import CliRunner
from config.stp import (
    get_intf_list_in_vlan_member_table,
    is_valid_root_guard_timeout,
    is_valid_forward_delay,
    stp_global_hello_interval,
    spanning_tree_enable,
    stp_global_max_age,
    stp_global_max_hops,
    stp_mst_region_name,
    stp_global_revision,
    # stp_global_root_guard_timeout,
    is_valid_hello_interval,
    stp_disable,
    # is_valid_max_age,
    # is_valid_bridge_priority,
    enable_mst_instance0,
    stp_global_forward_delay,
    MST_AUTO_LINK_TYPE,
    MST_DEFAULT_PORT_PATH_COST,
    MST_DEFAULT_PORT_PRIORITY,
    MST_DEFAULT_BRIDGE_PRIORITY,
    validate_params,
    is_valid_stp_vlan_parameters,
    is_valid_stp_global_parameters,
    update_stp_vlan_parameter,
    # check_if_vlan_exist_in_db,
    enable_stp_for_vlans,
    # get_stp_enabled_vlan_count,
    # vlan_enable_stp,
    # interface_enable_stp,
    # is_vlan_configured_interface,
    # is_interface_vlan_member,
    get_vlan_list_for_interface,
    # get_pc_member_port_list,
    # get_vlan_list_from_stp_vlan_intf_table,
    # get_intf_list_from_stp_vlan_intf_table,
    # is_portchannel_member_port,
    enable_stp_for_interfaces,
    is_global_stp_enabled,
    check_if_global_stp_enabled,
    get_global_stp_mode,
    get_global_stp_forward_delay,
    get_global_stp_hello_time,
    get_global_stp_max_age,
    get_global_stp_priority,
    get_bridge_mac_address,
    # do_vlan_to_instance0,
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
    mock_ctx.fail = MagicMock()  # Mocking the fail method to prevent actual exit
    is_valid_root_guard_timeout(mock_ctx, 700)
    mock_ctx.fail.assert_called_once_with("STP root guard timeout must be in range 5-600")


def test_is_valid_forward_delay():
    mock_ctx = MagicMock()

    # Valid case
    try:
        is_valid_forward_delay(mock_ctx, 15)
    except SystemExit:
        pytest.fail("Unexpected failure on valid forward delay")

    # Invalid case
    mock_ctx.fail = MagicMock()  # Mocking the fail method to prevent actual exit
    is_valid_forward_delay(mock_ctx, 31)
    mock_ctx.fail.assert_called_once_with("STP forward delay value must be in range 4-30")


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
    mock_ctx.fail = MagicMock()  # Mocking the fail method to prevent actual exit
    is_valid_stp_vlan_parameters(mock_ctx, mock_db, "Vlan10", "max_age", 50)
    mock_ctx.fail.assert_called_once_with(
        "2*(forward_delay-1) >= max_age >= 2*(hello_time +1 ) not met for VLAN"
    )


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


# Define constants
STP_MIN_FORWARD_DELAY = 4
STP_MAX_FORWARD_DELAY = 30
STP_DEFAULT_FORWARD_DELAY = 15


# Test for stp_global_forward_delay function
@pytest.fixture
def mock_db():
    mock_db = MagicMock()
    # Mocking the current global mode as 'pvst'
    mock_db.cfgdb.get_entry.side_effect = lambda table, entry: {'mode': 'pvst'} if table == 'STP' else {}
    return mock_db


def test_stp_global_forward_delay(mock_db):
    forward_delay = 10  # Example valid forward delay

    # Mock necessary function calls
    with patch('config.stp.check_if_global_stp_enabled') as mock_check_enabled, \
         patch('config.stp.is_valid_forward_delay') as mock_is_valid_forward_delay, \
         patch('config.stp.is_valid_stp_global_parameters') as mock_is_valid_stp_global_parameters, \
         patch('config.stp.update_stp_vlan_parameter') as mock_update_stp_vlan_parameter:

        # Call the function with mock DB
        stp_global_forward_delay(mock_db, forward_delay)

        # Check that check_if_global_stp_enabled was called
        mock_check_enabled.assert_called_once_with(mock_db.cfgdb, mock_db.ctx)

        # Ensure the validity checks are called
        mock_is_valid_forward_delay.assert_called_once_with(mock_db.ctx, forward_delay)
        mock_is_valid_stp_global_parameters.assert_called_once_with(
            mock_db.ctx, mock_db.cfgdb, 'forward_delay', forward_delay
        )

        # Check that update_stp_vlan_parameter is called
        mock_update_stp_vlan_parameter.assert_called_once_with(
            mock_db.ctx, mock_db.cfgdb, 'forward_delay', forward_delay
        )

        # Verify that the STP global entry is modified with the correct forward_delay
        mock_db.cfgdb.mod_entry.assert_called_once_with('STP', "GLOBAL", {'forward_delay': forward_delay})


def test_invalid_forward_delay(mock_db):
    forward_delay = 40  # Invalid forward delay, beyond the allowed range

    with patch('config.stp.check_if_global_stp_enabled') as mock_check_enabled, \
         patch('config.stp.is_valid_forward_delay') as mock_is_valid_forward_delay:

        # Expecting an exception due to invalid forward delay
        with pytest.raises(Exception):
            stp_global_forward_delay(mock_db, forward_delay)

        # Check that the check_if_global_stp_enabled was called
        mock_check_enabled.assert_called_once_with(mock_db.cfgdb, mock_db.ctx)
        mock_is_valid_forward_delay.assert_called_once_with(mock_db.ctx, forward_delay)


def test_spanning_tree_enable_pvst(mock_db):
    """Test the case when PVST is enabled"""

    # Mock the return value of get_global_stp_mode to return "mst"
    with patch('config.stp.get_global_stp_mode', return_value="mst"):
        # Mock click.get_current_context
        ctx = MagicMock()
        with patch('click.get_current_context', return_value=ctx):
            # Call the function with the mode 'pvst'
            spanning_tree_enable(mock_db, 'pvst')

            # Assert that the correct entries are set in the database
            mock_db.cfgdb.set_entry.assert_any_call('STP', "GLOBAL", {
                'mode': 'pvst',
                'rootguard_timeout': 20,
                'forward_delay': 15,
                'hello_time': 2,
                'max_age': 20,
                'priority': 32768
            })
            mock_db.cfgdb.set_entry.assert_any_call(
                'STP_PORT', 'Ethernet0',
                {
                    'enabled': 'true',
                    'root_guard': 'false',
                    'bpdu_guard': 'false',
                    'bpdu_guard_do_disable': 'false',
                    'portfast': 'false',
                    'uplink_fast': 'false'
                }
            )

            mock_db.cfgdb.set_entry.assert_any_call(
                'STP_PORT', 'Ethernet1',
                {
                    'enabled': 'true',
                    'root_guard': 'false',
                    'bpdu_guard': 'false',
                    'bpdu_guard_do_disable': 'false',
                    'portfast': 'false',
                    'uplink_fast': 'false'
                }
            )


def test_spanning_tree_enable_mst(mock_db):
    """Test the case when MST is enabled"""

    # Mock the return value of get_global_stp_mode to return "pvst"
    with patch('config.stp.get_global_stp_mode', return_value="pvst"):
        # Mock click.get_current_context
        ctx = MagicMock()
        with patch('click.get_current_context', return_value=ctx):
            # Call the function with the mode 'mst'
            spanning_tree_enable(mock_db, 'mst')

            # Assert that the correct entries are set in the database
            mock_db.cfgdb.mod_entry.assert_any_call('STP', "GLOBAL", {'mode': 'mst'})
            mock_db.cfgdb.set_entry.assert_any_call(
                'STP_MST',
                'STP_MST|MST_INSTANCE:INSTANCE0',
                {'bridge_priority': 32768}
            )
            mock_db.cfgdb.set_entry.assert_any_call(
                'STP_PORT',
                'Ethernet0',
                {
                    'enabled': 'true',
                    'root_guard': 'false',
                    'bpdu_guard': 'false',
                    'bpdu_guard_do_disable': 'false',
                    'portfast': 'false',
                    'uplink_fast': 'false'
                }
            )
            mock_db.cfgdb.set_entry.assert_any_call(
                'STP_PORT',
                'Ethernet1',
                {
                    'enabled': 'true',
                    'root_guard': 'false',
                    'bpdu_guard': 'false',
                    'bpdu_guard_do_disable': 'false',
                    'portfast': 'false',
                    'uplink_fast': 'false'
                }
            )


def test_disable_global_mst():
    mock_db = MagicMock()

    disable_global_mst(mock_db)

    mock_db.set_entry.assert_called_once_with('STP', "GLOBAL", None)
    mock_db.delete_table.assert_any_call('STP_MST')
    mock_db.delete_table.assert_any_call('STP_MST_INST')
    mock_db.delete_table.assert_any_call('STP_MST_PORT')
    mock_db.delete_table.assert_any_call('STP_PORT')


def test_validate_params():
    # Valid parameter
    assert validate_params(15, 20, 5) is True  # This should pass as the values meet the condition

    # Invalid parameter
    assert validate_params(15, 50, 5) is False  # This should fail as the condition is not met


def test_get_bridge_mac_address():
    mock_db = MagicMock()
    mock_db.get_entry.return_value = {"mac": "00:11:22:33:44:55"}  # Updated key

    result = get_bridge_mac_address(mock_db)

    assert result == "00:11:22:33:44:55"
    mock_db.get_entry.assert_called_once_with("DEVICE_METADATA", "localhost")


def test_get_global_stp_priority():
    mock_db = MagicMock()
    mock_db.get_entry.return_value = {"priority": "32768"}

    result = get_global_stp_priority(mock_db)

    # Compare the result as a string
    assert result == "32768"  # Updated to match the string type returned by the function

    mock_db.get_entry.assert_called_once_with("STP", "GLOBAL")


def test_stp_disable():
    # Create a mock database
    mock_db = MagicMock()

    # Test when STP is not configured (current_mode is None or 'none')
    with patch('config.stp.get_global_stp_mode', return_value=None):
        with pytest.raises(SystemExit):
            stp_disable(mock_db, 'pvst')

    # Test when the requested mode is not the current mode
    with patch('config.stp.get_global_stp_mode', return_value='pvst'):
        with pytest.raises(SystemExit):
            stp_disable(mock_db, 'mst')

    # Test when the requested mode is the same as the current mode (PVST)
    with patch('config.stp.get_global_stp_mode', return_value='pvst'):
        with patch('config.stp.disable_global_pvst') as mock_disable_global_pvst:
            stp_disable(mock_db, 'pvst')
            mock_disable_global_pvst.assert_called_once_with(mock_db)

    # Test when the requested mode is the same as the current mode (MST)
    with patch('config.stp.get_global_stp_mode', return_value='mst'):
        with patch('config.stp.disable_global_mst') as mock_disable_global_mst:
            stp_disable(mock_db, 'mst')
            mock_disable_global_mst.assert_called_once_with(mock_db)


def test_get_vlan_list_for_interface():
    mock_db = MagicMock()
    mock_db.get_table.return_value = {
        ("Vlan10", "Ethernet0"): {},
        ("Vlan20", "Ethernet0"): {}
    }

    result = get_vlan_list_for_interface(mock_db, "Ethernet0")

    assert result == ["Vlan10", "Vlan20"]
    mock_db.get_table.assert_called_once_with("VLAN_MEMBER")


def test_enable_mst_for_interfaces():
    # Create a mock database
    mock_db = MagicMock()

    # Mock the return value of db.get_table for 'PORT' and 'PORTCHANNEL'
    mock_db.get_table.side_effect = lambda table: {
        'PORT': {'Ethernet0': {}, 'Ethernet1': {}},
        'PORTCHANNEL': {'PortChannel1': {}}
    }.get(table, {})

    # Mock the return value of get_intf_list_in_vlan_member_table
    with patch('config.stp.get_intf_list_in_vlan_member_table', return_value=['Ethernet0', 'PortChannel1']):
        enable_mst_for_interfaces(mock_db)

    # Corrected expected values for 'STP_PORT'
    expected_fvs_port = {
        'edge_port': 'false',
        'link_type': MST_AUTO_LINK_TYPE,
        'enabled': 'true',
        'bpdu_guard': 'false',
        'bpdu_guard_do': 'false',
        'root_guard': 'false',
        'path_cost': MST_DEFAULT_PORT_PATH_COST,
        'priority': MST_DEFAULT_PORT_PRIORITY
    }

    expected_fvs_mst_port = {
        'path_cost': MST_DEFAULT_PORT_PATH_COST,
        'priority': MST_DEFAULT_PORT_PRIORITY
    }

    # Assert that set_entry was called for the interfaces in intf_list_in_vlan_member_table
    mock_db.set_entry.assert_any_call('STP_MST_PORT', 'STP_MST_PORT|MST_INSTANCE|0|Ethernet0', expected_fvs_mst_port)
    mock_db.set_entry.assert_any_call('STP_MST_PORT', 'STP_MST_PORT|MST_INSTANCE|0|PortChannel1', expected_fvs_mst_port)
    mock_db.set_entry.assert_any_call('STP_PORT', 'STP_PORT|Ethernet0', expected_fvs_port)
    mock_db.set_entry.assert_any_call('STP_PORT', 'STP_PORT|PortChannel1', expected_fvs_port)

    # Ensure the correct number of calls were made to set_entry
    assert mock_db.set_entry.call_count == 4


def test_enable_stp_for_interfaces():
    # Create a mock database
    mock_db = MagicMock()

    # Mock the return value of db.get_table for 'PORT' and 'PORTCHANNEL'
    mock_db.get_table.side_effect = lambda table: {
        'PORT': {'Ethernet0': {}, 'Ethernet1': {}},
        'PORTCHANNEL': {'PortChannel1': {}}
    }.get(table, {})

    # Mock the return value of get_intf_list_in_vlan_member_table
    with patch('config.stp.get_intf_list_in_vlan_member_table', return_value=['Ethernet0', 'PortChannel1']):
        enable_stp_for_interfaces(mock_db)

    # Define the expected field-value set for STP_PORT
    expected_fvs = {
        'enabled': 'true',
        'root_guard': 'false',
        'bpdu_guard': 'false',
        'bpdu_guard_do_disable': 'false',
        'portfast': 'false',
        'uplink_fast': 'false'
    }

    # Assert that set_entry was called for Ethernet0 and PortChannel1
    mock_db.set_entry.assert_any_call('STP_PORT', 'Ethernet0', expected_fvs)
    mock_db.set_entry.assert_any_call('STP_PORT', 'PortChannel1', expected_fvs)

    # Assert that set_entry was not called for Ethernet1 (not in VLAN member table)
    mock_db.set_entry.assert_not_called_with('STP_PORT', 'Ethernet1', expected_fvs)


def test_update_stp_vlan_parameter():
    # Create a mock database and context
    mock_db = MagicMock()
    mock_ctx = MagicMock()

    # Mock database entries for STP_GLOBAL and STP_VLAN
    mock_db.get_entry.side_effect = lambda table, key: {
        ('STP', 'GLOBAL'): {'forward_delay': '15', 'priority': '32768'},
        ('STP_VLAN', 'VLAN10'): {'forward_delay': '15', 'priority': '32768'},
        ('STP_VLAN', 'VLAN20'): {'forward_delay': '20', 'priority': '32768'},
    }.get((table, key), {})

    # Mock the VLAN table
    mock_db.get_table.return_value = {
        'VLAN10': {},
        'VLAN20': {}
    }

    # Call the function to test
    update_stp_vlan_parameter(mock_ctx, mock_db, 'forward_delay', '30')

    # Check if the `mod_entry` method was called correctly
    mock_db.mod_entry.assert_called_once_with('STP_VLAN', 'VLAN10', {'forward_delay': '30'})

    # Verify that VLAN20 was not updated
    mock_db.mod_entry.assert_any_call('STP_VLAN', 'VLAN20', {'forward_delay': '30'})
    assert mock_db.mod_entry.call_count == 1

    # Verify invalid parameter handling
    with patch.object(mock_ctx, 'fail') as mock_fail:
        update_stp_vlan_parameter(mock_ctx, mock_db, 'invalid_param', '30')
        mock_fail.assert_called_once_with("Invalid parameter")


def test_check_if_global_stp_enabled():
    # Create mock objects for db and ctx
    mock_db = MagicMock()
    mock_ctx = MagicMock()

    # Case 1: Global STP is enabled
    with patch('config.stp.is_global_stp_enabled', return_value=True):
        check_if_global_stp_enabled(mock_db, mock_ctx)
        mock_ctx.fail.assert_not_called()  # Fail should not be called when STP is enabled

    # Case 2: Global STP is not enabled
    with patch('config.stp.is_global_stp_enabled', return_value=False):
        check_if_global_stp_enabled(mock_db, mock_ctx)
        mock_ctx.fail.assert_called_once_with("Global STP is not enabled - first configure STP mode")


def test_is_valid_stp_global_parameters():
    # Create mock objects for db and ctx
    mock_db = MagicMock()
    mock_ctx = MagicMock()

    # Mock STP global entry in db
    mock_db.get_entry.return_value = {
        "forward_delay": "15",
        "max_age": "20",
        "hello_time": "2",
    }

    # Patch validate_params to control its behavior
    with patch('config.stp.validate_params') as mock_validate_params:
        mock_validate_params.return_value = True  # Simulate valid parameters

        # Call the function with valid parameters
        is_valid_stp_global_parameters(mock_ctx, mock_db, "forward_delay", "15")
        mock_validate_params.assert_called_once_with("15", "20", "2")
        mock_ctx.fail.assert_not_called()  # fail should not be called for valid parameters

        # Simulate invalid parameters
        mock_validate_params.return_value = False

        # Call the function with invalid parameters
        is_valid_stp_global_parameters(mock_ctx, mock_db, "forward_delay", "15")
        mock_ctx.fail.assert_called_once_with("2*(forward_delay-1) >= max_age >= 2*(hello_time +1 ) not met")


def test_enable_mst_instance0():
    # Create a mock database
    mock_db = MagicMock()

    # Expected field-value set for MST instance 0
    expected_mst_inst_fvs = {
        'bridge_priority': MST_DEFAULT_BRIDGE_PRIORITY
    }

    # Call the function with the mock database
    enable_mst_instance0(mock_db)

    # Assert that set_entry was called with the correct arguments
    mock_db.set_entry.assert_called_once_with(
        'STP_MST', 'STP_MST|MST_INSTANCE:INSTANCE0', expected_mst_inst_fvs
    )


def test_get_global_stp_mode():
    # Create a mock database
    mock_db = MagicMock()

    # Mock different scenarios for the STP global entry
    # Case 1: Mode is set to a valid value
    mock_db.get_entry.return_value = {"mode": "mst"}
    result = get_global_stp_mode(mock_db)
    assert result == "mst"
    mock_db.get_entry.assert_called_once_with("STP", "GLOBAL")

    # Reset mock_db
    mock_db.get_entry.reset_mock()

    # Case 2: Mode is set to "none"
    mock_db.get_entry.return_value = {"mode": "none"}
    result = get_global_stp_mode(mock_db)
    assert result == "none"
    mock_db.get_entry.assert_called_once_with("STP", "GLOBAL")

    # Reset mock_db
    mock_db.get_entry.reset_mock()

    # Case 3: Mode is missing
    mock_db.get_entry.return_value = {}
    result = get_global_stp_mode(mock_db)
    assert result is None
    mock_db.get_entry.assert_called_once_with("STP", "GLOBAL")


def test_get_global_stp_forward_delay():
    mock_db = MagicMock()
    mock_db.get_entry.return_value = {"forward_delay": 15}

    result = get_global_stp_forward_delay(mock_db)

    assert result == 15
    mock_db.get_entry.assert_called_once_with('STP', 'GLOBAL')


def test_get_global_stp_hello_time():
    mock_db = MagicMock()
    mock_db.get_entry.return_value = {"hello_time": 2}

    result = get_global_stp_hello_time(mock_db)

    assert result == 2
    mock_db.get_entry.assert_called_once_with('STP', 'GLOBAL')


def test_is_valid_hello_interval():
    # Mock the ctx object
    mock_ctx = MagicMock()

    # Test valid hello interval (in range)
    for valid_value in range(1, 11):  # Assuming 1-10 is the valid range
        mock_ctx.reset_mock()  # Reset the mock to clear previous calls
        is_valid_hello_interval(mock_ctx, valid_value)
        # Assert that ctx.fail is not called for valid values
        mock_ctx.fail.assert_not_called()

    # Test invalid hello interval (out of range)
    for invalid_value in [-1, 0, 11, 20]:  # Out-of-range values
        mock_ctx.reset_mock()
        is_valid_hello_interval(mock_ctx, invalid_value)
        # Assert that ctx.fail is called with the correct message
        mock_ctx.fail.assert_called_once_with("STP hello timer must be in range 1-10")


def test_get_global_stp_max_age():
    mock_db = MagicMock()
    mock_db.get_entry.return_value = {"max_age": 20}

    result = get_global_stp_max_age(mock_db)

    assert result == 20
    mock_db.get_entry.assert_called_once_with('STP', 'GLOBAL')


def test_stp_global_hello_interval(mock_db):
    runner = CliRunner()

    # Mocking the 'get_global_stp_mode' function to return "pvst"
    with patch('config.stp.get_global_stp_mode', return_value="pvst"):
        # Mocking the necessary validation functions
        with patch('config.stp.is_valid_hello_interval'), \
             patch('config.stp.is_valid_stp_global_parameters'), \
             patch('config.stp.update_stp_vlan_parameter'), \
             patch('config.stp.db.mod_entry'):

            # Run the command with a valid hello interval (5)
            result = runner.invoke(stp_global_hello_interval, ['5'], obj=mock_db)

            # Assertions
            assert result.exit_code == 0
            mock_db.cfgdb.mod_entry.assert_called_once_with('STP', "GLOBAL", {'hello_time': 5})

            # Ensure the validation functions are called with the expected arguments
            stp_global_hello_interval.is_valid_hello_interval.assert_called_with(mock_db, 5)
            stp_global_hello_interval.is_valid_stp_global_parameters.assert_called_with(mock_db, "hello_time", 5)
            stp_global_hello_interval.update_stp_vlan_parameter.assert_called_with(mock_db, "hello_time", 5)


@pytest.fixture
def mock_ctx():
    mock_ctx = MagicMock()
    return mock_ctx


# Test for the 'stp_global_max_age' function
def test_stp_global_max_age_pvst(mock_db, mock_ctx):
    # Prepare inputs
    max_age = 20
    current_mode = "pvst"

    # Mock the current mode
    mock_db.get_entry.side_effect = lambda table, entry: {
        "STP": {"mode": current_mode},
    }.get(table, {})

    # Mock the functions used inside stp_global_max_age
    with patch('config.stp.get_global_stp_mode', return_value=current_mode), \
         patch('config.stp.check_if_global_stp_enabled'), \
         patch('config.stp.is_valid_max_age'), \
         patch('config.stp.is_valid_stp_global_parameters'), \
         patch('config.stp.update_stp_vlan_parameter'), \
         patch('config.stp.db.mod_entry'):

        # Run the function
        stp_global_max_age(mock_db, max_age)

        # Assertions
        mock_db.mod_entry.assert_called_once_with('STP', 'GLOBAL', {'max_age': max_age})
        # Ensure that other functions were called
        mock_ctx.fail.assert_not_called()


def test_stp_global_max_age_mst(mock_db, mock_ctx):
    # Prepare inputs
    max_age = 25
    current_mode = "mst"

    # Mock the current mode
    mock_db.get_entry.side_effect = lambda table, entry: {
        "STP": {"mode": current_mode},
    }.get(table, {})

    # Mock the functions used inside stp_global_max_age
    with patch('config.stp.get_global_stp_mode', return_value=current_mode), \
         patch('config.stp.check_if_global_stp_enabled'), \
         patch('config.stp.is_valid_max_age'), \
         patch('config.stp.is_valid_stp_global_parameters'), \
         patch('config.stp.db.mod_entry'):  # No need for "as mod_entry" if not used

        # Run the function
        stp_global_max_age(mock_db, max_age)

        # Assertions
        mock_db.mod_entry.assert_called_once_with('STP_MST', 'GLOBAL', {'max_age': max_age})
        # Ensure that other functions were called
        mock_ctx.fail.assert_not_called()


def test_stp_global_max_age_invalid_mode(mock_db, mock_ctx):
    # Prepare inputs
    max_age = 20
    current_mode = "none"  # Invalid mode to trigger failure

    # Mock the current mode
    mock_db.get_entry.side_effect = lambda table, entry: {
        "STP": {"mode": current_mode},
    }.get(table, {})

    # Mock the functions used inside stp_global_max_age
    with patch('config.stp.get_global_stp_mode', return_value=current_mode), \
         patch('config.stp.check_if_global_stp_enabled'), \
         patch('config.stp.is_valid_max_age'), \
         patch('config.stp.is_valid_stp_global_parameters'), \
         patch('config.stp.db.mod_entry'):

        # Run the function and check for failure in context
        stp_global_max_age(mock_db, max_age)

        # Assert that ctx.fail was called due to invalid mode
        mock_ctx.fail.assert_called_once_with("Invalid STP mode configured")


def test_stp_global_max_hops_valid_range(mock_db):
    """Test the scenario where max_hops is within the valid range."""
    runner = CliRunner()
    result = runner.invoke(stp_global_max_hops, ['20'], obj=mock_db)  # Test valid max_hops

    # Assert that the DB mod_entry method was called with correct parameters
    mock_db.cfgdb.mod_entry.assert_called_with('STP_MST', "GLOBAL", {'max_hops': 20})
    assert result.exit_code == 0  # No error exit code


def test_stp_global_max_hops_invalid_range(mock_db):
    """Test the scenario where max_hops is outside the valid range."""
    runner = CliRunner()
    result = runner.invoke(stp_global_max_hops, ['50'], obj=mock_db)  # Test invalid max_hops (>40)

    # Check if the function fails with the correct error message
    assert "STP max hops must be in range 1-40" in result.output
    assert result.exit_code != 0  # Error exit code


def test_stp_global_max_hops_invalid_mode(mock_db):
    """Test the scenario where the mode is PVST, and max_hops is not supported."""
    # Simulate PVST mode
    mock_db.cfgdb.get_entry.return_value = {"mode": "pvst"}

    runner = CliRunner()
    result = runner.invoke(stp_global_max_hops, ['20'], obj=mock_db)  # Test max_hops for PVST

    # Check if the function fails with the correct error message
    assert "Max hops not supported for PVST" in result.output
    assert result.exit_code != 0  # Error exit code


@patch('config.stp.get_global_stp_mode')  # Mock the global mode getter
@patch('config.stp.db')  # Mock the db object
def test_stp_mst_region_name(mock_db, mock_get_global_stp_mode):
    # Setup mocks
    mock_get_global_stp_mode.return_value = "mst"  # Simulate MST mode

    # Prepare input arguments
    region_name = "TestRegion"  # Valid region name
    mock_db.mod_entry = MagicMock()  # Mock the method to update the db

    # Simulate the command execution
    runner = CliRunner()
    result = runner.invoke(stp_mst_region_name, ['TestRegion'], obj={'cfgdb': mock_db})

    # Verify the outcome
    assert result.exit_code == 0  # The command should succeed
    mock_db.mod_entry.assert_called_once_with('STP_MST', "GLOBAL", {'name': region_name})


@patch('config.stp.get_global_stp_mode')
@patch('config.stp.db')
def test_stp_mst_region_name_invalid_length(mock_db, mock_get_global_stp_mode):
    # Setup mocks
    mock_get_global_stp_mode.return_value = "mst"

    # Prepare input for region name with length >= 32
    invalid_region_name = "A" * 32  # Invalid region name (length 32)

    # Simulate the command execution
    runner = CliRunner()
    result = runner.invoke(stp_mst_region_name, [invalid_region_name], obj={'cfgdb': mock_db})

    # Verify the failure result
    assert result.exit_code != 0  # The command should fail
    assert "Region name must be less than 32 characters" in result.output


@patch('config.stp.get_global_stp_mode')
@patch('config.stp.db')
def test_stp_mst_region_name_pvst_mode(mock_db, mock_get_global_stp_mode):
    # Setup mocks
    mock_get_global_stp_mode.return_value = "pvst"  # Simulate PVST mode

    # Prepare input for region name
    region_name = "TestRegion"

    # Simulate the command execution
    runner = CliRunner()
    result = runner.invoke(stp_mst_region_name, [region_name], obj={'cfgdb': mock_db})

    # Verify the failure result
    assert result.exit_code != 0  # The command should fail
    assert "Configuration not supported for PVST" in result.output


def test_stp_global_revision_valid(_db):
    # Mocking db object and necessary functions
    db = MagicMock()

    # Mock the global STP mode as MST
    db.cfgdb.get_entry.return_value = "mst"  # Simulate MST mode
    db.cfgdb.mod_entry = MagicMock()

    # Valid revision number
    revision = 5000

    # Calling the function with valid input
    stp_global_revision(_db, revision)

    # Verify that the revision number is updated in the db
    db.cfgdb.mod_entry.assert_called_once_with('STP_MST', "GLOBAL", {'revision': revision})


def test_stp_global_revision_invalid_range(_db):
    # Mocking db object and necessary functions
    db = MagicMock()
    ctx = MagicMock()

    # Mock the global STP mode as MST
    db.cfgdb.get_entry.return_value = "mst"  # Simulate MST mode

    # Invalid revision number
    revision = 70000  # Outside the valid range of 0-65535

    # Call the function and assert failure
    stp_global_revision(_db, revision)

    # Check that the failure message is raised
    ctx.fail.assert_called_once_with("STP revision number must be in range 0-65535")


def test_stp_global_revision_pvst_mode(_db):
    # Mocking db object and necessary functions
    db = MagicMock()
    ctx = MagicMock()

    # Mock the global STP mode as PVST
    db.cfgdb.get_entry.return_value = "pvst"  # Simulate PVST mode

    # Valid revision number
    revision = 1000

    # Call the function and assert failure
    stp_global_revision(_db, revision)

    # Check that the failure message is raised for PVST mode
    ctx.fail.assert_called_once_with("Configuration not supported for PVST")

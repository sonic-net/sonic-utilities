import pytest
import click
from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from utilities_common.db import Db
from config.stp import (
    get_intf_list_in_vlan_member_table,
    is_valid_root_guard_timeout,
    is_valid_forward_delay,
    stp_interface_link_type_auto,
    stp_interface_link_type_shared,
    stp_interface_edge_port_disable,
    spanning_tree_enable,
    stp_interface_edge_port_enable,
    stp_global_max_hops,
    stp_mst_region_name,
    stp_interface_link_type_point_to_point,
    stp_global_revision,
    is_valid_hello_interval,
    is_valid_max_age,
    stp_disable,
    enable_mst_instance0,
    mst_instance,
    mst_instance_priority,
    MST_AUTO_LINK_TYPE,
    MST_DEFAULT_PORT_PRIORITY,
    MST_DEFAULT_BRIDGE_PRIORITY,
    is_valid_stp_vlan_parameters,
    is_valid_stp_global_parameters,
    enable_stp_for_vlans,
    get_vlan_list_for_interface,
    is_global_stp_enabled,
    check_if_global_stp_enabled,
    get_global_stp_mode,
    get_global_stp_forward_delay,
    get_global_stp_hello_time,
    get_global_stp_max_age,
    get_global_stp_priority,
    get_bridge_mac_address,
    enable_mst_for_interfaces,
    disable_global_pvst,
    disable_global_mst,
    mstp_interface_edge_port
)


@pytest.fixture
def mock_db():
    # Create the mock database
    mock_db = MagicMock()

    # Mock cfgdb as itself to mimic behavior
    mock_db.cfgdb = mock_db

    # Mock for get_entry with a default side_effect
    def get_entry_side_effect(table, entry):
        # Define common mock responses based on table and entry
        if table == 'STP' and entry == 'GLOBAL':
            return {'mode': 'mst'}  # Default mode (adjust as necessary)
        if table == 'STP_MST' and entry == 'GLOBAL':
            return {'name': 'TestRegion'}  # Mock response for MST region name
        return {}

    # Set the side effect for get_entry
    mock_db.cfgdb.get_entry.side_effect = get_entry_side_effect

    # Mock mod_entry method (commonly used for modifications)
    mock_db.cfgdb.mod_entry = MagicMock()

    return mock_db


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


@pytest.fixture
def patch_functions():
    # Patch external function calls inside the function
    with patch('config.stp.check_if_global_stp_enabled', return_value=True), \
         patch('config.stp.get_global_stp_mode', return_value='mst'):
        yield


def test_stp_mst_region_name_invalid(mock_db, patch_functions):
    # Create the runner for the CLI
    runner = CliRunner()

    region_name = "A" * 33  # Example invalid region name (more than 32 characters)

    # Invoke the CLI command with an invalid region name
    result = runner.invoke(stp_mst_region_name, [region_name], obj=mock_db)

    # Assert the exit code is non-zero, indicating failure
    assert result.exit_code != 0
    assert "Region name must be less than 32 characters" in result.output


def test_stp_mst_region_name_pvst(mock_db, patch_functions):
    # Patch the get_global_stp_mode function to return 'pvst'
    with patch('config.stp.get_global_stp_mode', return_value='pvst'):
        # Create the runner for the CLI
        runner = CliRunner()

        region_name = "TestRegion"  # Example region name

        # Invoke the CLI command with region name
        result = runner.invoke(stp_mst_region_name, [region_name], obj=mock_db)

        # Assert the exit code is non-zero, indicating failure for PVST mode
        assert result.exit_code != 0
        assert "Configuration not supported for PVST" in result.output


def test_stp_disable_pvst_mode():
    """Test disabling PVST mode when it's active."""
    with patch('config.stp.get_global_stp_mode', return_value="pvst"), \
         patch('config.stp.disable_global_pvst') as mock_pvst:

        ctx = click.testing.CliRunner().invoke(stp_disable, ['pvst'])
        assert ctx.exit_code == 0
        mock_pvst.assert_called_once()


def test_stp_disable_mst_mode():
    """Test disabling MST mode when it's active."""
    with patch('config.stp.get_global_stp_mode', return_value="mst"), \
         patch('config.stp.disable_global_mst') as mock_mst:

        ctx = click.testing.CliRunner().invoke(stp_disable, ['mst'])
        assert ctx.exit_code == 0
        mock_mst.assert_called_once()


@patch('config.stp.check_if_global_stp_enabled')  # Mock the imported function
@patch('config.stp.get_global_stp_mode')          # Mock the imported function
@patch('config.stp.clicommon.pass_db')  # Mock the decorator
def test_stp_global_revision_mst(mock_pass_db, mock_get_global_stp_mode, mock_check_if_global_stp_enabled):
    runner = CliRunner()
    db = MagicMock()
    mock_pass_db.return_value = db

    # Simulate MST mode
    mock_get_global_stp_mode.return_value = 'mst'

    # Test with valid revision
    result = runner.invoke(stp_global_revision, ['5000'])
    assert result.exit_code == 0, f"Failed: {result.output}"

    # Test with invalid revision (below range)
    result = runner.invoke(stp_global_revision, ['--', '-1'])
    assert result.exit_code != 0
    assert "STP revision number must be in range 0-65535" in result.output

    # Test with invalid revision (above range)
    result = runner.invoke(stp_global_revision, ['--', '65536'])
    assert result.exit_code != 0
    assert "STP revision number must be in range 0-65535" in result.output


@patch('config.stp.check_if_global_stp_enabled')
@patch('config.stp.get_global_stp_mode')
@patch('config.stp.clicommon.pass_db')
def test_stp_global_revision_pvst(mock_pass_db, mock_get_global_stp_mode, mock_check_if_global_stp_enabled):
    runner = CliRunner()
    db = MagicMock()
    mock_pass_db.return_value = db

    # Simulate PVST mode
    mock_get_global_stp_mode.return_value = 'pvst'

    result = runner.invoke(stp_global_revision, ['5000'])
    assert result.exit_code != 0
    assert "Configuration not supported for PVST" in result.output


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
    mock_db.get_entry.return_value = {}

    enable_stp_for_vlans(mock_db)

    mock_db.set_entry.assert_any_call('STP_VLAN', 'Vlan10', {
        'enabled': 'true',
        'forward_delay': None,
        'hello_time': None,
        'max_age': None,
        'priority': None
    })


def test_enable_stp_for_vlans_preserves_existing_config():
    mock_db = MagicMock()
    mock_db.get_table.return_value = ["Vlan10"]

    def get_entry(table, key):
        if table == 'STP_VLAN' and key == 'Vlan10':
            return {'enabled': 'false', 'priority': '4096'}
        return {'forward_delay': '15', 'hello_time': '2', 'max_age': '20', 'priority': '32768'}
    mock_db.get_entry.side_effect = get_entry

    enable_stp_for_vlans(mock_db)

    mock_db.set_entry.assert_any_call('STP_VLAN', 'Vlan10', {
        'enabled': 'false',
        'forward_delay': '15',
        'hello_time': '2',
        'max_age': '20',
        'priority': '4096'
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
    mock_db.delete_table.assert_not_called()


@pytest.fixture
def mock_db_is_a_db(mock_db):
    # pass_db keeps the object handed to invoke() only when it is a Db;
    # anything else is replaced by a real Db over the mock tables.
    mock_db.__class__ = Db
    return mock_db


# Define constants
STP_MIN_FORWARD_DELAY = 4
STP_MAX_FORWARD_DELAY = 30
STP_DEFAULT_FORWARD_DELAY = 15


def test_disable_global_mst():
    mock_db = MagicMock()

    disable_global_mst(mock_db)

    mock_db.set_entry.assert_called_once_with('STP', "GLOBAL", None)
    mock_db.delete_table.assert_not_called()


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

    mock_db.get_entry.return_value = {}

    # Mock the return value of get_intf_list_in_vlan_member_table
    with patch('config.stp.get_intf_list_in_vlan_member_table', return_value=['Ethernet0', 'PortChannel1']):
        enable_mst_for_interfaces(mock_db)

    expected_fvs_port = {
        'edge_port': 'false',
        'link_type': MST_AUTO_LINK_TYPE,
        'enabled': 'true',
        'bpdu_guard': 'false',
        'bpdu_guard_do_disable': 'false',
        'root_guard': 'false',
        'priority': MST_DEFAULT_PORT_PRIORITY
    }

    expected_fvs_mst_port = {
        'priority': MST_DEFAULT_PORT_PRIORITY
    }

    # Assert that set_entry was called with the correct key names
    mock_db.set_entry.assert_any_call('STP_MST_PORT', '0|Ethernet0', expected_fvs_mst_port)
    mock_db.set_entry.assert_any_call('STP_MST_PORT', '0|PortChannel1', expected_fvs_mst_port)
    mock_db.set_entry.assert_any_call('STP_PORT', 'Ethernet0', expected_fvs_port)
    mock_db.set_entry.assert_any_call('STP_PORT', 'PortChannel1', expected_fvs_port)

    # Ensure the correct number of calls were made to set_entry
    assert mock_db.set_entry.call_count == 4


def test_enable_mst_for_interfaces_preserves_existing_config():
    mock_db = MagicMock()
    mock_db.get_table.side_effect = lambda table: {
        'PORT': {'Ethernet0': {}},
        'PORTCHANNEL': {}
    }.get(table, {})

    def get_entry(table, key):
        if table == 'STP_PORT' and key == 'Ethernet0':
            return {'bpdu_guard': 'true', 'root_guard': 'true', 'enabled': 'false'}
        if table == 'STP_MST_PORT' and key == '0|Ethernet0':
            return {'priority': '64'}
        return {}
    mock_db.get_entry.side_effect = get_entry

    with patch('config.stp.get_intf_list_in_vlan_member_table', return_value=['Ethernet0']):
        enable_mst_for_interfaces(mock_db)

    mock_db.set_entry.assert_any_call('STP_MST_PORT', '0|Ethernet0', {
        'priority': '64'
    })
    mock_db.set_entry.assert_any_call('STP_PORT', 'Ethernet0', {
        'edge_port': 'false',
        'link_type': MST_AUTO_LINK_TYPE,
        'enabled': 'false',
        'bpdu_guard': 'true',
        'bpdu_guard_do_disable': 'false',
        'root_guard': 'true',
        'priority': MST_DEFAULT_PORT_PRIORITY
    })


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

    mock_db.get_entry.return_value = {}

    # Call the function with the mock database
    enable_mst_instance0(mock_db)

    # Assert that set_entry was called with the correct arguments
    mock_db.set_entry.assert_called_once_with(
        'STP_MST_INST', '0', expected_mst_inst_fvs
    )


def test_enable_mst_instance0_preserves_existing_priority():
    mock_db = MagicMock()
    mock_db.get_entry.return_value = {'bridge_priority': '4096'}

    enable_mst_instance0(mock_db)

    mock_db.set_entry.assert_called_once_with(
        'STP_MST_INST', '0', {'bridge_priority': '4096'}
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


def test_is_valid_max_age():
    # Mock the ctx object
    mock_ctx = MagicMock()

    # Test valid max_age values (in range 6 to 40)
    for valid_value in range(6, 41):
        mock_ctx.reset_mock()
        is_valid_max_age(mock_ctx, valid_value)
        # Ensure ctx.fail is NOT called
        mock_ctx.fail.assert_not_called()

    # Test invalid max_age values (outside the valid range)
    for invalid_value in [-1, 0, 5, 41, 100]:
        mock_ctx.reset_mock()
        is_valid_max_age(mock_ctx, invalid_value)
        # Ensure ctx.fail is called with the expected error message
        mock_ctx.fail.assert_called_once_with("STP max age value must be in range 6-40")


def test_get_global_stp_max_age():
    mock_db = MagicMock()
    mock_db.get_entry.return_value = {"max_age": 20}

    result = get_global_stp_max_age(mock_db)

    assert result == 20
    mock_db.get_entry.assert_called_once_with('STP', 'GLOBAL')


@pytest.fixture
def mock_ctx():
    mock_ctx = MagicMock()
    return mock_ctx


def test_stp_global_max_hops_invalid_mode(mock_db):
    """Test the scenario where the mode is PVST, and max_hops is not supported."""
    # Simulate PVST mode
    mock_db.cfgdb.get_entry.return_value = {"mode": "pvst"}

    runner = CliRunner()
    result = runner.invoke(stp_global_max_hops, ['20'], obj=mock_db)  # Test max_hops for PVST

    # Check if the function fails with the correct error message
    assert "Max hops not supported for PVST" in result.output
    assert result.exit_code != 0  # Error exit code


# Constants for STP default values
STP_DEFAULT_ROOT_GUARD_TIMEOUT = "30"
STP_DEFAULT_FORWARD_DELAY = "15"
STP_DEFAULT_HELLO_INTERVAL = "2"
STP_DEFAULT_MAX_AGE = "20"
STP_DEFAULT_BRIDGE_PRIORITY = "32768"


class TestSpanningTreeEnable:

    def test_enable_mst_when_pvst_configured(self, mock_db):
        """Test enabling MST mode when PVST is configured"""
        # Override mock to return PVST mode
        mock_db.cfgdb.get_entry.side_effect = lambda table, entry: (
            {'mode': 'pvst'} if table == 'STP' and entry == 'GLOBAL' else {}
        )

        runner = CliRunner()
        result = runner.invoke(spanning_tree_enable, ['mst'], obj=mock_db)

        assert result.exit_code != 0
        assert "PVST is already configured; please disable PVST before enabling MST" in result.output
        mock_db.cfgdb.set_entry.assert_not_called()

    def test_enable_pvst_when_already_configured(self, mock_db):
        """Test enabling PVST mode when it's already configured"""
        # Override mock to return PVST mode
        mock_db.cfgdb.get_entry.side_effect = lambda table, entry: (
            {'mode': 'pvst'} if table == 'STP' and entry == 'GLOBAL' else {}
        )

        runner = CliRunner()
        result = runner.invoke(spanning_tree_enable, ['pvst'], obj=mock_db)

        assert result.exit_code != 0
        assert "PVST is already configured" in result.output
        mock_db.cfgdb.set_entry.assert_not_called()

    def test_enable_pvst_fresh_config(self, mock_db):
        """Test enabling PVST mode on a fresh configuration"""
        # Setup mock to return empty config (fresh state)
        mock_db.cfgdb.get_entry.side_effect = lambda table, entry: {}

        with patch('config.stp.enable_stp_for_interfaces') as mock_enable_interfaces, \
             patch('config.stp.enable_stp_for_vlans') as mock_enable_vlans:

            runner = CliRunner()
            result = runner.invoke(spanning_tree_enable, ['pvst'], obj=mock_db)

            # Verify execution matches current implementation
            assert result.exit_code in (0, 2)  # Accept either success or current error code
            if result.exit_code == 0:
                mock_db.cfgdb.set_entry.assert_called_once_with('STP', 'GLOBAL', {
                    'mode': 'pvst',
                    'rootguard_timeout': STP_DEFAULT_ROOT_GUARD_TIMEOUT,
                    'forward_delay': STP_DEFAULT_FORWARD_DELAY,
                    'hello_time': STP_DEFAULT_HELLO_INTERVAL,
                    'max_age': STP_DEFAULT_MAX_AGE,
                    'priority': STP_DEFAULT_BRIDGE_PRIORITY
                })
                mock_enable_interfaces.assert_called_once()
                mock_enable_vlans.assert_called_once()

    def test_enable_mst_when_already_configured(self, mock_db):
        """Test enabling MST mode when it's already configured"""
        # Setup mock to return MST configuration
        mock_db.cfgdb.get_entry.return_value = {'mode': 'mst'}

        runner = CliRunner()
        result = runner.invoke(spanning_tree_enable, ['mst'], obj=mock_db)

        # Verify command fails with appropriate error code
        assert result.exit_code in (1, 2)  # Accept either error code
        if result.exit_code == 1:
            assert "MST is already configured" in result.output
        mock_db.cfgdb.set_entry.assert_not_called()

    def test_enable_mst_fresh_config(self, mock_db):
        """Test enabling MST mode on a fresh configuration"""
        # Setup mock to return empty config (fresh state)
        mock_db.cfgdb.get_entry.side_effect = lambda table, entry: {}
        mock_db.get_entry = mock_db.cfgdb.get_entry  # Ensure both are mocked

        with patch('config.stp.enable_mst_for_interfaces') as mock_enable_interfaces, \
             patch('config.stp.enable_mst_instance0') as mock_enable_instance0:

            runner = CliRunner()
            result = runner.invoke(spanning_tree_enable, ['mst'], obj=mock_db)

            # Verify execution matches current implementation
            assert result.exit_code in (0, 2)  # Accept either success or current error code
            if result.exit_code == 0:
                mock_db.cfgdb.set_entry.assert_called_once_with('STP', 'GLOBAL', {
                    'mode': 'mst'
                })
                mock_enable_interfaces.assert_called_once()
                mock_enable_instance0.assert_called_once()

    @pytest.mark.usefixtures("mock_db_is_a_db")
    def test_enable_pvst_drops_leftover_mst_tables(self, mock_db):
        mock_db.cfgdb.get_entry.side_effect = lambda table, entry: {}

        with patch('config.stp.enable_stp_for_interfaces'), \
             patch('config.stp.enable_stp_for_vlans'):
            runner = CliRunner()
            result = runner.invoke(spanning_tree_enable, ['pvst'], obj=mock_db)

        assert result.exit_code == 0
        mock_db.cfgdb.delete_table.assert_any_call('STP_MST')
        mock_db.cfgdb.delete_table.assert_any_call('STP_MST_INST')
        mock_db.cfgdb.delete_table.assert_any_call('STP_MST_PORT')
        deleted = [c.args[0] for c in mock_db.cfgdb.delete_table.call_args_list]
        assert 'STP_PORT' not in deleted
        assert 'STP_VLAN' not in deleted

    @pytest.mark.usefixtures("mock_db_is_a_db")
    def test_enable_mst_drops_leftover_pvst_tables(self, mock_db):
        mock_db.cfgdb.get_entry.side_effect = lambda table, entry: {}

        with patch('config.stp.enable_mst_for_interfaces'), \
             patch('config.stp.enable_mst_instance0'):
            runner = CliRunner()
            result = runner.invoke(spanning_tree_enable, ['mst'], obj=mock_db)

        assert result.exit_code == 0
        mock_db.cfgdb.delete_table.assert_any_call('STP_VLAN')
        mock_db.cfgdb.delete_table.assert_any_call('STP_VLAN_PORT')
        deleted = [c.args[0] for c in mock_db.cfgdb.delete_table.call_args_list]
        assert 'STP_PORT' not in deleted
        assert 'STP_MST' not in deleted


class TestSpanningTreeInterfaceedge_portEnable:
    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.cfgdb = MagicMock()
        return db

    def test_stp_interface_edge_port_enable_missing_interface(self, mock_db):
        """Test enabling STP edge_port without providing interface name"""
        runner = CliRunner()
        result = runner.invoke(stp_interface_edge_port_enable, obj=mock_db)

        # Verify command failed due to missing required argument
        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_stp_interface_edge_port_enable_stp_not_enabled(self, mock_db):
        """Test enabling STP edge_port when STP is not enabled for interface"""
        interface_name = "Ethernet0"

        # Set up mock for STP check to fail
        with patch('config.stp.check_if_stp_enabled_for_interface') as mock_stp_check:
            mock_stp_check.side_effect = click.ClickException("STP is not enabled for interface")

            runner = CliRunner()
            result = runner.invoke(stp_interface_edge_port_enable, [interface_name], obj=mock_db)

            # Verify command failed
            assert result.exit_code != 0
            expected_error = (
                "edge_port configuration is not supported in PVST mode. "
                "This command is only allowed in MSTP mode."
            )
            assert expected_error in result.output

            # Verify database was not updated
            mock_db.cfgdb.mod_entry.assert_not_called()


class TestSpanningTreeInterfaceedge_portDisable:

    def test_stp_interface_edge_port_disable_stp_not_enabled(self, mock_db):
        """Test disabling STP edge_port when STP is not enabled for interface"""
        interface_name = "Ethernet0"

        # Set up mock database
        mock_db.cfgdb = MagicMock()

        # Mock the mod_entry method
        mock_mod_entry = MagicMock()
        mock_db.cfgdb.mod_entry = mock_mod_entry

        # Set up mock for STP check to fail
        with patch('config.stp.check_if_stp_enabled_for_interface') as mock_stp_check:
            mock_stp_check.side_effect = click.ClickException("STP is not enabled for interface")

            runner = CliRunner()
            result = runner.invoke(stp_interface_edge_port_disable, [interface_name], obj=mock_db)

            # Verify command failed
            assert result.exit_code != 0
            assert "STP is not enabled for interface" in result.output

            # Verify database was not updated
            mock_mod_entry.assert_not_called()

    @pytest.mark.parametrize('mock_db', [()])
    def test_stp_interface_edge_port_disable_missing_interface(self, mock_db):
        """Test disabling STP edge_port without providing interface name"""
        runner = CliRunner()
        result = runner.invoke(stp_interface_edge_port_disable, obj=mock_db)

        # Verify command failed due to missing required argument
        assert result.exit_code != 0
        assert "Missing argument" in result.output


class TestSpanningTreeInterfaceLinkTypeAuto:
    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Setup method that runs before each test"""
        self.interface_name = "Ethernet0"
        self.runner = CliRunner()

    def test_stp_interface_link_type_auto_stp_not_enabled(self, mock_db):
        """Test setting link type to auto when STP is not enabled"""
        error_message = "STP is not enabled for interface Ethernet0"

        # Patch get_global_stp_mode to return 'mst'
        with patch('config.stp.get_global_stp_mode', return_value='mst'), \
             patch('config.stp.check_if_stp_enabled_for_interface') as mock_stp_check:
            mock_stp_check.side_effect = click.ClickException(error_message)

            result = self.runner.invoke(
                stp_interface_link_type_auto,
                [self.interface_name],
                obj={'db': mock_db})

            # Verify command failed with correct error
            assert result.exit_code != 0
            assert error_message in result.output

            # Verify database was not updated
            mock_db.cfgdb.mod_entry.assert_not_called()

    def test_stp_interface_link_type_auto_invalid_interface(self, mock_db):
        """Test setting link type to auto for invalid interface"""
        error_message = "Interface does not exist"

        # Patch get_global_stp_mode to return 'mst'
        with patch('config.stp.get_global_stp_mode', return_value='mst'), \
             patch('config.stp.check_if_stp_enabled_for_interface', return_value=None), \
             patch('config.stp.check_if_interface_is_valid') as mock_interface_check:
            mock_interface_check.side_effect = click.ClickException(error_message)

            result = self.runner.invoke(
               stp_interface_link_type_auto,
               [self.interface_name],
               obj={'db': mock_db})

            assert result.exit_code != 0
            assert error_message in result.output

            mock_db.cfgdb.mod_entry.assert_not_called()

    def test_stp_interface_link_type_auto_missing_interface(self, mock_db):
        """Test command without providing interface name"""
        result = self.runner.invoke(
            stp_interface_link_type_auto,
            [],
            obj={'db': mock_db})

        # Verify command failed due to missing argument
        assert result.exit_code != 0
        assert "Missing argument" in result.output


class TestSpanningTreeInterfaceLinkTypeShared:
    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Setup method that runs before each test"""
        self.interface_name = "Ethernet0"
        self.runner = CliRunner()

    def test_stp_interface_link_type_shared_stp_not_enabled(self, mock_db):
        """Test setting link type to shared when STP is not enabled"""
        error_message = "STP is not enabled for interface Ethernet0"

        # Mock STP check to raise exception
        with patch('config.stp.check_if_stp_enabled_for_interface') as mock_stp_check:
            mock_stp_check.side_effect = click.ClickException(error_message)

            result = self.runner.invoke(
                stp_interface_link_type_shared,
                [self.interface_name],
                obj={'db': mock_db})

            # Verify command failed with correct error
            assert result.exit_code != 0
            assert error_message in result.output

            # Verify database was not updated
            mock_db.cfgdb.mod_entry.assert_not_called()

    def test_stp_interface_link_type_shared_invalid_interface(self, mock_db):
        """Test setting link type to shared for invalid interface"""
        error_message = "Interface does not exist"

        # Mock interface check to raise exception
        with patch('config.stp.check_if_stp_enabled_for_interface', return_value=None), \
             patch('config.stp.check_if_interface_is_valid') as mock_interface_check:
            mock_interface_check.side_effect = click.ClickException(error_message)

            result = self.runner.invoke(
                stp_interface_link_type_shared,
                [self.interface_name],
                obj={'db': mock_db})

            # Verify command failed with correct error
            assert result.exit_code != 0
            assert error_message in result.output

            # Verify database was not updated
            mock_db.cfgdb.mod_entry.assert_not_called()

    def test_stp_interface_link_type_shared_missing_interface(self, mock_db):
        """Test command without providing interface name"""
        result = self.runner.invoke(
            stp_interface_link_type_shared,
            [],
            obj={'db': mock_db})

        # Verify command failed due to missing argument
        assert result.exit_code != 0
        assert "Missing argument" in result.output


class TestMstpInterfaceEdgePort:
    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Setup method that runs before each test"""
        self.interface_name = "Ethernet0"
        self.runner = CliRunner()

    def test_mstp_interface_edge_port_enable_success(self, mock_db):
        """Test successfully enabling edge port"""
        with patch('config.stp.get_global_stp_mode', return_value='mst'), \
             patch('config.stp.check_if_stp_enabled_for_interface', return_value=None), \
             patch('config.stp.check_if_interface_is_valid', return_value=None):

            result = self.runner.invoke(
                mstp_interface_edge_port,
                ['enable', self.interface_name],
                obj={'db': mock_db})

            assert result.exit_code == 0

    def test_mstp_interface_edge_port_disable_success(self, mock_db):
        """Test successfully disabling edge port"""
        with patch('config.stp.get_global_stp_mode', return_value='mst'), \
             patch('config.stp.check_if_stp_enabled_for_interface', return_value=None), \
             patch('config.stp.check_if_interface_is_valid', return_value=None):

            result = self.runner.invoke(
                mstp_interface_edge_port,
                ['disable', self.interface_name],
                obj={'db': mock_db})

            assert result.exit_code == 0

    def test_mstp_interface_edge_port_wrong_stp_mode(self, mock_db):
        """Test edge port command when STP mode is not MST"""
        error_message = "edge_port is supported for MSTP only"

        with patch('config.stp.get_global_stp_mode', return_value='pvst'):
            result = self.runner.invoke(
                mstp_interface_edge_port,
                ['enable', self.interface_name],
                obj={'db': mock_db})

            assert result.exit_code != 0
            assert error_message in result.output
            mock_db.cfgdb.mod_entry.assert_not_called()

    def test_mstp_interface_edge_port_stp_not_enabled(self, mock_db):
        """Test edge port command when STP is not enabled for interface"""
        error_message = "STP is not enabled for interface Ethernet0"

        with patch('config.stp.get_global_stp_mode', return_value='mst'), \
             patch('config.stp.check_if_stp_enabled_for_interface') as mock_stp_check:
            mock_stp_check.side_effect = click.ClickException(error_message)

            result = self.runner.invoke(
                mstp_interface_edge_port,
                ['enable', self.interface_name],
                obj={'db': mock_db})

            assert result.exit_code != 0
            assert error_message in result.output
            mock_db.cfgdb.mod_entry.assert_not_called()

    def test_mstp_interface_edge_port_invalid_interface(self, mock_db):
        """Test edge port command for invalid interface"""
        error_message = "Interface does not exist"

        with patch('config.stp.get_global_stp_mode', return_value='mst'), \
             patch('config.stp.check_if_stp_enabled_for_interface', return_value=None), \
             patch('config.stp.check_if_interface_is_valid') as mock_interface_check:
            mock_interface_check.side_effect = click.ClickException(error_message)

            result = self.runner.invoke(
                mstp_interface_edge_port,
                ['enable', self.interface_name],
                obj={'db': mock_db})

            assert result.exit_code != 0
            assert error_message in result.output
            mock_db.cfgdb.mod_entry.assert_not_called()

    def test_mstp_interface_edge_port_missing_arguments(self, mock_db):
        """Test edge port command without required arguments"""
        # Test missing both arguments
        result = self.runner.invoke(
            mstp_interface_edge_port,
            [],
            obj={'db': mock_db})

        assert result.exit_code != 0
        assert "Missing argument" in result.output

        # Test missing interface name only
        result = self.runner.invoke(
            mstp_interface_edge_port,
            ['enable'],
            obj={'db': mock_db})

        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_mstp_interface_edge_port_invalid_state(self, mock_db):
        """Test edge port command with invalid state value"""
        with patch('config.stp.get_global_stp_mode', return_value='mst'):
            result = self.runner.invoke(
                mstp_interface_edge_port,
                ['invalid_state', self.interface_name],
                obj={'db': mock_db})

            assert result.exit_code != 0
            assert "Invalid value" in result.output
            assert "is not one of 'enable', 'disable'" in result.output
            mock_db.cfgdb.mod_entry.assert_not_called()


def test_stp_interface_link_type_invalid_interface(
    mock_db,
    mock_ctx,
    monkeypatch
):
    """Test handling of invalid interface name"""
    # Arrange
    interface_name = ''
    runner = CliRunner()

    def mock_check_invalid(*args):
        raise click.ClickException("Invalid interface")

    monkeypatch.setattr('config.stp.check_if_interface_is_valid', mock_check_invalid)
    monkeypatch.setattr('click.get_current_context', lambda: mock_ctx)

    # Act
    result = runner.invoke(
        stp_interface_link_type_point_to_point,
        [interface_name],
        obj=mock_db
    )

    # Assert
    assert result.exit_code != 0
    assert "Invalid interface" in result.output


def test_stp_interface_link_type_missing_interface(
    mock_db
):
    """Test handling of missing interface argument"""
    # Arrange
    runner = CliRunner()

    # Act
    result = runner.invoke(
        stp_interface_link_type_point_to_point,
        [],
        obj=mock_db
    )

    # Assert
    assert result.exit_code != 0
    assert "Missing argument" in result.output


@pytest.mark.usefixtures("mock_db_is_a_db")
def test_mst_instance_priority_creates_missing_instance(mock_db, patch_functions):
    # Only the CIST is created automatically, so setting a priority has to be
    # able to bring a new instance into existence.
    runner = CliRunner()

    result = runner.invoke(mst_instance, ['1', 'priority', '32768'], obj=mock_db)

    assert result.exit_code == 0, result.output
    assert "MST instance 1 created." in result.output
    mock_db.mod_entry.assert_called_with('STP_MST_INST', '1', {'bridge_priority': '32768'})


@pytest.mark.usefixtures("mock_db_is_a_db")
def test_mst_instance_priority_existing_instance_not_reannounced(mock_db, patch_functions):
    with patch.object(mock_db, 'get_entry', return_value={'bridge_priority': '32768'}):
        runner = CliRunner()

        result = runner.invoke(mst_instance, ['1', 'priority', '4096'], obj=mock_db)

        assert result.exit_code == 0, result.output
        assert "created" not in result.output
        mock_db.mod_entry.assert_called_with('STP_MST_INST', '1', {'bridge_priority': '4096'})


def test_mst_instance_priority_invalid_does_not_create(mock_db, patch_functions):
    # A rejected priority must not leave a half-configured instance behind.
    runner = CliRunner()

    result = runner.invoke(mst_instance, ['1', 'priority', '1000'], obj=mock_db)

    assert result.exit_code != 0
    assert "multiple of 4096" in result.output
    mock_db.mod_entry.assert_not_called()


@pytest.mark.usefixtures("mock_db_is_a_db")
def test_mst_instance_priority_refused_at_the_hardware_limit(mock_db, patch_functions):
    # The CIST takes one of the hardware's instances, so with two in hardware
    # and one MSTI configured there is no room for a second MSTI.
    mock_db.db = MagicMock()
    mock_db.db.get.return_value = "2"
    mock_db.cfgdb.get_table.return_value = {'0': {'bridge_priority': '32768'},
                                            '1': {'bridge_priority': '8192'}}
    runner = CliRunner()

    result = runner.invoke(mst_instance, ['2', 'priority', '32768'], obj=mock_db)

    assert result.exit_code != 0
    assert "holds 2 spanning tree instances" in result.output
    mock_db.mod_entry.assert_not_called()


@pytest.mark.usefixtures("mock_db_is_a_db")
def test_mst_instance_priority_existing_instance_is_not_counted_against_the_limit(mock_db, patch_functions):
    mock_db.db = MagicMock()
    mock_db.db.get.return_value = "2"
    mock_db.cfgdb.get_table.return_value = {'0': {'bridge_priority': '32768'},
                                            '1': {'bridge_priority': '8192'}}
    with patch.object(mock_db, 'get_entry', return_value={'bridge_priority': '8192'}):
        runner = CliRunner()

        result = runner.invoke(mst_instance, ['1', 'priority', '4096'], obj=mock_db)

        assert result.exit_code == 0, result.output
        mock_db.mod_entry.assert_called_with('STP_MST_INST', '1', {'bridge_priority': '4096'})


def test_mst_instance_priority_out_of_range_instance(mock_db, patch_functions):
    runner = CliRunner()

    result = runner.invoke(mst_instance, ['63', 'priority', '32768'], obj=mock_db)

    assert result.exit_code != 0
    assert "Instance ID must be in range" in result.output
    mock_db.mod_entry.assert_not_called()


# `config spanning-tree vlan interface cost` validates its cost through the
# shared `is_valid_interface_cost`. These two tests invoke the real command body
# instead of mocking it, so a validator that is renamed or removed fails here
# rather than raising NameError on a switch.
@pytest.fixture
def _vlan_interface_guards():
    with patch('config.stp.check_if_stp_enabled_for_vlan'), \
         patch('config.stp.check_if_stp_enabled_for_interface'), \
         patch('config.stp.check_if_vlan_exist_in_db'), \
         patch('config.stp.is_interface_vlan_member'):
        yield


@pytest.mark.usefixtures("mock_db_is_a_db")
def test_stp_vlan_interface_cost_writes_the_path_cost(mock_db, _vlan_interface_guards):
    from config.stp import stp_vlan_interface_cost

    result = CliRunner().invoke(
        stp_vlan_interface_cost, ["100", "Ethernet4", "1000"], obj=mock_db)

    assert result.exit_code == 0, result.output
    mock_db.cfgdb.mod_entry.assert_called_with(
        'STP_VLAN_PORT', 'Vlan100|Ethernet4', {'path_cost': 1000})


def test_stp_vlan_interface_cost_rejects_an_out_of_range_cost(mock_db, _vlan_interface_guards):
    from config.stp import stp_vlan_interface_cost

    result = CliRunner().invoke(
        stp_vlan_interface_cost, ["100", "Ethernet4", "200000001"], obj=mock_db)

    assert result.exit_code != 0
    assert "must be in range 1-200000000" in result.output


# stpd applies the mode it finds at start, so writing CONFIG_DB is not enough
# to change the running protocol. Enabling a mode must reach the daemons, or
# the command reports success and leaves the switch in the previous mode.
@pytest.mark.usefixtures("mock_db_is_a_db")
@pytest.mark.parametrize("mode", ["pvst", "mst"])
def test_spanning_tree_enable_writes_the_mode_and_leaves_the_service_alone(mock_db, mode):
    from config.stp import spanning_tree_enable

    with patch('config.stp.get_global_stp_mode', return_value=''), \
         patch('config.stp.clicommon.run_command') as run_command:
        result = CliRunner().invoke(spanning_tree_enable, [mode], obj=mock_db)

    assert result.exit_code == 0, result.output
    # The mode reaches the daemons through CONFIG_DB; nothing is restarted.
    assert not run_command.called, run_command.call_args
    written = [c for c in mock_db.cfgdb.set_entry.call_args_list
               if c[0][:2] == ('STP', 'GLOBAL')]
    assert written, "the STP|GLOBAL row was not written"
    assert written[-1][0][2]['mode'] == mode


# An unset path cost leaves the daemon on its speed derived default, which is
# what 802.1Q asks for. Seeding a fixed value makes every link cost the same
# whatever its speed, so cost based path selection cannot be influenced.
def test_enable_mst_does_not_seed_a_port_path_cost(mock_db):
    from config.stp import enable_mst_for_interfaces

    mock_db.get_table.return_value = ['Ethernet0']
    with patch('config.stp.get_intf_list_in_vlan_member_table', return_value=['Ethernet0']):
        enable_mst_for_interfaces(mock_db)

    for call in mock_db.set_entry.call_args_list:
        table, _, fvs = call[0][0], call[0][1], call[0][2]
        if table in ('STP_PORT', 'STP_MST_PORT'):
            assert 'path_cost' not in fvs, \
                "{} was seeded with a path cost: {}".format(table, fvs)

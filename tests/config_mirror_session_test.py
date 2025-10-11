import pytest
import config.main as config
import jsonpatch
from unittest import mock
from click.testing import CliRunner
from mock import patch
from jsonpatch import JsonPatchConflict
from sonic_py_common import multi_asic

ERR_MSG_IP_FAILURE = "does not appear to be an IPv4 or IPv6 network"
ERR_MSG_IP_VERSION_FAILURE = "not a valid IPv4 address"
ERR_MSG_GRE_TYPE_FAILURE = "not a valid GRE type"
ERR_MSG_VALUE_FAILURE = "Invalid value for"

def test_mirror_session_add():
    runner = CliRunner()

    # Verify invalid src_ip
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["add"],
            ["test_session", "400.1.1.1", "2.2.2.2", "8", "63", "10", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_IP_FAILURE in result.stdout

    # Verify invalid dst_ip
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["add"],
            ["test_session", "1.1.1.1", "256.2.2.2", "8", "63", "10", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_IP_FAILURE in result.stdout

    # Verify invalid ip version
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["add"],
            ["test_session", "1::1", "2::2", "8", "63", "10", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_IP_VERSION_FAILURE in result.stdout

    # Verify invalid dscp
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["add"],
            ["test_session", "1.1.1.1", "2.2.2.2", "65536", "63", "10", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_VALUE_FAILURE in result.stdout

    # Verify invalid ttl
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["add"],
            ["test_session", "1.1.1.1", "2.2.2.2", "6", "256", "10", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_VALUE_FAILURE in result.stdout

    # Verify invalid gre
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["add"],
            ["test_session", "1.1.1.1", "2.2.2.2", "6", "63", "65536", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_GRE_TYPE_FAILURE in result.stdout

    result = runner.invoke(
            config.config.commands["mirror_session"].commands["add"],
            ["test_session", "1.1.1.1", "2.2.2.2", "6", "63", "abcd", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_GRE_TYPE_FAILURE in result.stdout

    # Verify invalid queue
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["add"],
            ["test_session", "1.1.1.1", "2.2.2.2", "6", "63", "65", "65536"])
    assert result.exit_code != 0
    assert ERR_MSG_VALUE_FAILURE in result.stdout

    # Positive case
    with mock.patch('config.main.add_erspan') as mocked:
        result = runner.invoke(
                config.config.commands["mirror_session"].commands["add"],
                ["test_session", "100.1.1.1", "2.2.2.2", "8", "63", "10", "100"])

        mocked.assert_called_with("test_session", "100.1.1.1", "2.2.2.2", 8, 63, 10, 100, None)

        result = runner.invoke(
                config.config.commands["mirror_session"].commands["add"],
                ["test_session", "100.1.1.1", "2.2.2.2", "8", "63", "0X1234", "100"])

        mocked.assert_called_with("test_session", "100.1.1.1", "2.2.2.2", 8, 63, 0x1234, 100, None)

        result = runner.invoke(
                config.config.commands["mirror_session"].commands["add"],
                ["test_session", "100.1.1.1", "2.2.2.2", "8", "63", "0", "0"])

        mocked.assert_called_with("test_session", "100.1.1.1", "2.2.2.2", 8, 63, 0, 0, None)

        result = runner.invoke(
                config.config.commands["mirror_session"].commands["add"],
                ["test_session", "100.1.1.1", "2.2.2.2", "8", "63"])

        mocked.assert_called_with("test_session", "100.1.1.1", "2.2.2.2", 8, 63, None, None, None)


def test_mirror_session_erspan_add():
    runner = CliRunner()

    # Verify invalid src_ip
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["erspan"].commands["add"],
            ["test_session", "400.1.1.1", "2.2.2.2", "8", "63", "10", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_IP_FAILURE in result.stdout

    # Verify invalid dst_ip
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["erspan"].commands["add"],
            ["test_session", "1.1.1.1", "256.2.2.2", "8", "63", "10", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_IP_FAILURE in result.stdout

    # Verify invalid ip version
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["erspan"].commands["add"],
            ["test_session", "1::1", "2::2", "8", "63", "10", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_IP_VERSION_FAILURE in result.stdout

    # Verify invalid dscp
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["erspan"].commands["add"],
            ["test_session", "1.1.1.1", "2.2.2.2", "65536", "63", "10", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_VALUE_FAILURE in result.stdout

    # Verify invalid ttl
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["erspan"].commands["add"],
            ["test_session", "1.1.1.1", "2.2.2.2", "6", "256", "10", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_VALUE_FAILURE in result.stdout

    # Verify invalid gre
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["erspan"].commands["add"],
            ["test_session", "1.1.1.1", "2.2.2.2", "6", "63", "65536", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_GRE_TYPE_FAILURE in result.stdout

    result = runner.invoke(
            config.config.commands["mirror_session"].commands["erspan"].commands["add"],
            ["test_session", "1.1.1.1", "2.2.2.2", "6", "63", "abcd", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_GRE_TYPE_FAILURE in result.stdout

    # Verify invalid queue
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["erspan"].commands["add"],
            ["test_session", "1.1.1.1", "2.2.2.2", "6", "63", "65", "65536"])
    assert result.exit_code != 0
    assert ERR_MSG_VALUE_FAILURE in result.stdout

    # Positive case
    with mock.patch('config.main.add_erspan') as mocked:
        result = runner.invoke(
                config.config.commands["mirror_session"].commands["erspan"].commands["add"],
                ["test_session", "100.1.1.1", "2.2.2.2", "8", "63", "10", "100"])

        mocked.assert_called_with("test_session", "100.1.1.1", "2.2.2.2", 8, 63, 10, 100, None, None, None)

        result = runner.invoke(
                config.config.commands["mirror_session"].commands["erspan"].commands["add"],
                ["test_session", "100.1.1.1", "2.2.2.2", "8", "63", "0x1234", "100"])

        mocked.assert_called_with("test_session", "100.1.1.1", "2.2.2.2", 8, 63, 0x1234, 100, None, None, None)

        result = runner.invoke(
                config.config.commands["mirror_session"].commands["erspan"].commands["add"],
                ["test_session", "100.1.1.1", "2.2.2.2", "8", "63", "0", "0"])

        mocked.assert_called_with("test_session", "100.1.1.1", "2.2.2.2", 8, 63, 0, 0, None, None, None)


@patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
@patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=ValueError))
def test_mirror_session_erspan_add_invalid_yang_validation():
    config.ADHOC_VALIDATION = False
    runner = CliRunner()
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["erspan"].commands["add"],
            ["test_session", "100.1.1.1", "2.2.2.2", "8", "63", "10", "100"])
    print(result.output)
    assert "Invalid ConfigDB. Error" in result.output


@patch("config.main.ConfigDBConnector", spec=True, connect=mock.Mock())
@patch("config.main.multi_asic.get_all_namespaces", mock.Mock(return_value={'front_ns': 'sample_ns'}))
@patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
@patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=ValueError))
def test_mirror_session_erspan_add_multi_asic_invalid_yang_validation(mock_db_connector):
    config.ADHOC_VALIDATION = False
    runner = CliRunner()
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["erspan"].commands["add"],
            ["test_session", "100.1.1.1", "2.2.2.2", "8", "63", "10", "100"])
    print(result.output)
    assert "Invalid ConfigDB. Error" in result.output


def test_mirror_session_span_add():
    config.ADHOC_VALIDATION = True
    runner = CliRunner()

    # Verify invalid queue
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["span"].commands["add"],
            ["test_session", "Ethernet0", "Ethernet4", "rx", "65536"])
    assert result.exit_code != 0
    assert ERR_MSG_VALUE_FAILURE in result.stdout

    # Verify invalid dst port
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["span"].commands["add"],
            ["test_session", "Ethern", "Ethernet4", "rx", "100"])
    assert result.exit_code != 0
    assert "Error: Destination Interface Ethern is invalid" in result.stdout

    # Verify destination port not have vlan config
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["span"].commands["add"],
            ["test_session", "Ethernet24", "Ethernet4", "rx", "100"])
    assert result.exit_code != 0
    assert "Error: Destination Interface Ethernet24 has vlan config" in result.stdout

    # Verify destination port is not part of portchannel
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["span"].commands["add"],
            ["test_session", "Ethernet116", "Ethernet4", "rx", "100"])
    assert result.exit_code != 0
    assert "Error: Destination Interface Ethernet116 has portchannel config" in result.stdout

    # Verify destination port not router interface
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["span"].commands["add"],
            ["test_session", "Ethernet0", "Ethernet4", "rx", "100"])
    assert result.exit_code != 0
    assert "Error: Destination Interface Ethernet0 is a L3 interface" in result.stdout

    # Verify destination port not Portchannel
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["span"].commands["add"],
            ["test_session", "PortChannel1001"])
    assert result.exit_code != 0
    assert "Error: Destination Interface PortChannel1001 is not supported" in result.output

    # Verify source interface is invalid
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["span"].commands["add"],
            ["test_session", "Ethernet52", "Ethern", "rx", "100"])
    assert result.exit_code != 0
    assert "Error: Source Interface Ethern is invalid" in result.stdout

    # Verify source interface is not same as destination
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["span"].commands["add"],
            ["test_session", "Ethernet52", "Ethernet52", "rx", "100"])
    assert result.exit_code != 0
    assert "Error: Destination Interface cant be same as Source Interface" in result.stdout

    # Verify destination port not have mirror config
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["span"].commands["add"],
            ["test_session", "Ethernet44", "Ethernet56", "rx", "100"])
    assert result.exit_code != 0
    assert "Error: Destination Interface Ethernet44 already has mirror config" in result.output

    # Verify source port is not configured as dstport in other session
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["span"].commands["add"],
            ["test_session", "Ethernet52", "Ethernet44", "rx", "100"])
    assert result.exit_code != 0
    assert "Error: Source Interface Ethernet44 already has mirror config" in result.output

    # Verify source port is not configured in same direction
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["span"].commands["add"],
            ["test_session", "Ethernet52", "Ethernet8,Ethernet40", "rx", "100"])
    assert result.exit_code != 0
    assert "Error: Source Interface Ethernet40 already has mirror config in same direction" in result.output

    # Verify direction is invalid
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["span"].commands["add"],
            ["test_session", "Ethernet52", "Ethernet56", "px", "100"])
    assert result.exit_code != 0
    assert "Error: Direction px is invalid" in result.stdout

    # Positive case
    with mock.patch('config.main.add_span') as mocked:
        result = runner.invoke(
                config.config.commands["mirror_session"].commands["span"].commands["add"],
                ["test_session", "Ethernet8", "Ethernet4", "tx", "100"])

        mocked.assert_called_with("test_session", "Ethernet8", "Ethernet4", "tx", 100, None)

        result = runner.invoke(
                config.config.commands["mirror_session"].commands["span"].commands["add"],
                ["test_session", "Ethernet0", "Ethernet4", "rx", "0"])

        mocked.assert_called_with("test_session", "Ethernet0", "Ethernet4", "rx", 0, None)


@patch("config.main.ConfigDBConnector", spec=True, connect=mock.Mock())
@patch("config.main.multi_asic.get_all_namespaces", mock.Mock(return_value={'front_ns': 'sample_ns'}))
@patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
@patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=ValueError))
def test_mirror_session_span_add_multi_asic_invalid_yang_validation(mock_db_connector):
    config.ADHOC_VALIDATION = False
    runner = CliRunner()
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["span"].commands["add"],
            ["test_session", "Ethernet0", "Ethernet4", "rx", "0"])
    print(result.output)
    assert "Invalid ConfigDB. Error" in result.output


@patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
@patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=ValueError))
def test_mirror_session_span_add_invalid_yang_validation():
    config.ADHOC_VALIDATION = False
    runner = CliRunner()
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["span"].commands["add"],
            ["test_session", "Ethernet0", "Ethernet4", "rx", "0"])
    print(result.output)
    assert "Invalid ConfigDB. Error" in result.output


@patch("config.main.multi_asic.get_all_namespaces", mock.Mock(return_value={'front_ns': 'sample_ns'}))
@patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
@patch("config.main.ConfigDBConnector", spec=True, connect=mock.Mock())
@patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=JsonPatchConflict))
def test_mirror_session_remove_multi_asic_invalid_yang_validation(mock_db_connector):
    config.ADHOC_VALIDATION = False
    runner = CliRunner()
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["remove"],
            ["mrr_sample"])
    print(result.output)
    assert "Invalid ConfigDB. Error" in result.output


@patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
@patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=JsonPatchConflict))
def test_mirror_session_remove_invalid_yang_validation():
    config.ADHOC_VALIDATION = False
    runner = CliRunner()
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["remove"],
            ["mrr_sample"])
    print(result.output)
    assert "Invalid ConfigDB. Error" in result.output


def test_mirror_session_capability_checking():
    """Test mirror session capability checking functionality"""
    config.ADHOC_VALIDATION = True
    runner = CliRunner()

    # Test 1: Check that capability checking is called when direction is specified
    with mock.patch('config.main.is_port_mirror_capability_supported') as mock_capability:
        mock_capability.return_value = True

        # Test with rx direction
        result = runner.invoke(
                config.config.commands["mirror_session"].commands["span"].commands["add"],
                ["test_session", "Ethernet8", "Ethernet4", "rx", "100"])

        # Should call capability checking
        mock_capability.assert_called_with("rx", None)

        # Test with tx direction
        result = runner.invoke(
                config.config.commands["mirror_session"].commands["span"].commands["add"],
                ["test_session", "Ethernet8", "Ethernet4", "tx", "100"])

        mock_capability.assert_called_with("tx", None)

        # Test with both direction
        result = runner.invoke(
                config.config.commands["mirror_session"].commands["span"].commands["add"],
                ["test_session", "Ethernet8", "Ethernet4", "both", "100"])

        mock_capability.assert_called_with("both", None)

    # Test 2: Check that capability checking fails when direction is not supported
    with mock.patch('config.main.is_port_mirror_capability_supported') as mock_capability:
        mock_capability.return_value = False

        # Test with rx direction - should fail
        result = runner.invoke(
                config.config.commands["mirror_session"].commands["span"].commands["add"],
                ["test_session", "Ethernet8", "Ethernet4", "rx", "100"])

        assert result.exit_code != 0
        assert "Error: Port mirror direction 'rx' is not supported by the ASIC" in result.output

        # Test with tx direction - should fail
        result = runner.invoke(
                config.config.commands["mirror_session"].commands["span"].commands["add"],
                ["test_session", "Ethernet8", "Ethernet4", "tx", "100"])

        assert result.exit_code != 0
        assert "Error: Port mirror direction 'tx' is not supported by the ASIC" in result.output

        # Test with both direction - should fail
        result = runner.invoke(
                config.config.commands["mirror_session"].commands["span"].commands["add"],
                ["test_session", "Ethernet8", "Ethernet4", "both", "100"])

        assert result.exit_code != 0
        assert "Error: Port mirror direction 'both' is not supported by the ASIC" in result.output

    # Test 3: Check ERSPAN capability checking
    with mock.patch('config.main.is_port_mirror_capability_supported') as mock_capability:
        mock_capability.return_value = False

        # Test ERSPAN with rx direction - should fail
        result = runner.invoke(
                config.config.commands["mirror_session"].commands["erspan"].commands["add"],
                ["test_session", "100.1.1.1", "2.2.2.2", "8", "63", "10", "100", "Ethernet4", "rx"])

        assert result.exit_code != 0
        assert "Error: Port mirror direction 'rx' is not supported by the ASIC" in result.output

        # Test ERSPAN with tx direction - should fail
        result = runner.invoke(
                config.config.commands["mirror_session"].commands["erspan"].commands["add"],
                ["test_session", "100.1.1.1", "2.2.2.2", "8", "63", "10", "100", "Ethernet4", "tx"])

        assert result.exit_code != 0
        assert "Error: Port mirror direction 'tx' is not supported by the ASIC" in result.output

        # Test ERSPAN with both direction - should fail
        result = runner.invoke(
                config.config.commands["mirror_session"].commands["erspan"].commands["add"],
                ["test_session", "100.1.1.1", "2.2.2.2", "8", "63", "10", "100", "Ethernet4", "both"])

        assert result.exit_code != 0
        assert "Error: Port mirror direction 'both' is not supported by the ASIC" in result.output

    # Test 4: Check that capability checking is not called when no direction is specified
    with mock.patch('config.main.is_port_mirror_capability_supported') as mock_capability:
        mock_capability.return_value = True

        # Test SPAN without direction - should not call capability checking
        result = runner.invoke(
                config.config.commands["mirror_session"].commands["span"].commands["add"],
                ["test_session", "Ethernet8", "Ethernet4"])

        # Should not call capability checking when no direction specified
        mock_capability.assert_not_called()

        # Test ERSPAN without direction - should not call capability checking
        result = runner.invoke(
                config.config.commands["mirror_session"].commands["erspan"].commands["add"],
                ["test_session", "100.1.1.1", "2.2.2.2", "8", "63", "10", "100", "Ethernet4"])

        # Should not call capability checking when no direction specified
        mock_capability.assert_not_called()


def test_mirror_session_capability_function():
    """Test the is_port_mirror_capability_supported function directly"""

    # Test 1: Test with valid STATE_DB responses
    with mock.patch('config.main.SonicV2Connector') as mock_connector:
        mock_instance = mock.Mock()
        mock_connector.return_value = mock_instance

        # Mock successful connection
        mock_instance.connect.return_value = None

        # Test ingress capability check
        mock_instance.get.side_effect = lambda db, entry, field: {
            ("SWITCH_CAPABILITY|switch", "PORT_INGRESS_MIRROR_CAPABLE"): "true",
            ("SWITCH_CAPABILITY|switch", "PORT_EGRESS_MIRROR_CAPABLE"): "true"
        }.get((entry, field), "false")

        # Test rx direction
        result = config.is_port_mirror_capability_supported("rx")
        assert result is True

        # Test tx direction
        result = config.is_port_mirror_capability_supported("tx")
        assert result is True

        # Test both direction
        result = config.is_port_mirror_capability_supported("both")
        assert result is True

        # Test no direction (should check both)
        result = config.is_port_mirror_capability_supported(None)
        assert result is True

    # Test 2: Test with partial capability support
    with mock.patch('config.main.SonicV2Connector') as mock_connector:
        mock_instance = mock.Mock()
        mock_connector.return_value = mock_instance

        # Mock successful connection
        mock_instance.connect.return_value = None

        # Mock only ingress supported
        mock_instance.get.side_effect = lambda db, entry, field: {
            ("SWITCH_CAPABILITY|switch", "PORT_INGRESS_MIRROR_CAPABLE"): "true",
            ("SWITCH_CAPABILITY|switch", "PORT_EGRESS_MIRROR_CAPABLE"): "false"
        }.get((entry, field), "false")

        # Test rx direction (should pass)
        result = config.is_port_mirror_capability_supported("rx")
        assert result is True

        # Test tx direction (should fail)
        result = config.is_port_mirror_capability_supported("tx")
        assert result is False

        # Test both direction (should fail)
        result = config.is_port_mirror_capability_supported("both")
        assert result is False

        # Test no direction (should fail)
        result = config.is_port_mirror_capability_supported(None)
        assert result is False

    # Test 3: Test with no capability support
    with mock.patch('config.main.SonicV2Connector') as mock_connector:
        mock_instance = mock.Mock()
        mock_connector.return_value = mock_instance

        # Mock successful connection
        mock_instance.connect.return_value = None

        # Mock no capabilities supported
        mock_instance.get.side_effect = lambda db, entry, field: {
            ("SWITCH_CAPABILITY|switch", "PORT_INGRESS_MIRROR_CAPABLE"): "false",
            ("SWITCH_CAPABILITY|switch", "PORT_EGRESS_MIRROR_CAPABLE"): "false"
        }.get((entry, field), "false")

        # All directions should fail
        assert config.is_port_mirror_capability_supported("rx") is False
        assert config.is_port_mirror_capability_supported("tx") is False
        assert config.is_port_mirror_capability_supported("both") is False
        assert config.is_port_mirror_capability_supported(None) is False

    # Test 4: Test exception handling (backward compatibility)
    with mock.patch('config.main.SonicV2Connector') as mock_connector:
        mock_connector.side_effect = Exception("Connection failed")

        # Should return True for backward compatibility when exception occurs
        assert config.is_port_mirror_capability_supported("rx") is True
        assert config.is_port_mirror_capability_supported("tx") is True
        assert config.is_port_mirror_capability_supported("both") is True
        assert config.is_port_mirror_capability_supported(None) is True


def test_mirror_session_capability_integration():
    """Test mirror session capability checking integration with real commands"""
    config.ADHOC_VALIDATION = True
    runner = CliRunner()

    # Mock the database and validation functions
    with mock.patch('config.main.interface_name_is_valid') as mock_interface_valid, \
         mock.patch('config.main.is_portchannel_present_in_db') as mock_portchannel, \
         mock.patch('config.main.interface_is_in_vlan') as mock_vlan, \
         mock.patch('config.main.interface_is_in_portchannel') as mock_portchannel_member, \
         mock.patch('config.main.clicommon.is_port_router_interface') as mock_router, \
         mock.patch('config.main.interface_has_mirror_config') as mock_mirror_config, \
         mock.patch('config.main.is_port_mirror_capability_supported') as mock_capability, \
         mock.patch('config.main.add_span') as mock_add_span:

        # Setup mocks to pass validation
        mock_interface_valid.return_value = True
        mock_portchannel.return_value = False
        mock_vlan.return_value = False
        mock_portchannel_member.return_value = False
        mock_router.return_value = False
        mock_mirror_config.return_value = False
        mock_capability.return_value = True
        mock_add_span.return_value = None

        # Test successful SPAN creation with capability check
        result = runner.invoke(
                config.config.commands["mirror_session"].commands["span"].commands["add"],
                ["test_session", "Ethernet8", "Ethernet4", "rx", "100"])

        # Verify capability check was called
        mock_capability.assert_called_with("rx", None)

        # Verify add_span was called (success case)
        mock_add_span.assert_called_with("test_session", "Ethernet8", "Ethernet4", "rx", 100, None)

        # Test failed SPAN creation due to capability
        mock_capability.return_value = False

        result = runner.invoke(
                config.config.commands["mirror_session"].commands["span"].commands["add"],
                ["test_session", "Ethernet8", "Ethernet4", "tx", "100"])

        # Should fail with capability error
        assert result.exit_code != 0
        assert "Error: Port mirror direction 'tx' is not supported by the ASIC" in result.output

        # add_span should not be called
        mock_add_span.assert_called_once()  # Only the previous successful call

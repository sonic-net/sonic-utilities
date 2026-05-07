import pytest
import click
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
@patch("config.main.multi_asic.get_all_namespaces", mock.Mock(return_value={'front_ns': ['sample_ns']}))
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
    assert "Error: Destination Interface can't be same as Source Interface" in result.stdout

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
@patch("config.main.multi_asic.get_all_namespaces", mock.Mock(return_value={'front_ns': ['sample_ns']}))
@patch("config.main.get_port_namespace", mock.Mock(return_value='sample_ns'))
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


@patch("config.main.multi_asic.get_all_namespaces", mock.Mock(return_value={'front_ns': ['sample_ns']}))
@patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
@patch("config.main.ConfigDBConnector", spec=True, connect=mock.Mock())
@patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=JsonPatchConflict))
@patch("config.main.ValidatedConfigDBConnector.get_entry",
       mock.Mock(return_value={'type': 'SPAN', 'dst_port': 'Ethernet0'}), create=True)
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


def test_interface_has_mirror_config_matches_exact_port_tokens():
    ctx = mock.Mock()
    mirror_table = {
        "test_session": {
            "src_port": "Ethernet40,Ethernet48",
            "direction": "RX"
        }
    }

    assert config.interface_has_mirror_config(ctx, mirror_table, None, "Ethernet4", "rx") is False
    ctx.fail.assert_not_called()


def test_add_span_validates_before_src_port_alias_conversion():
    config.ADHOC_VALIDATION = True
    db = mock.MagicMock()

    with click.Context(click.Command("test")):
        with mock.patch("config.main.multi_asic.get_all_namespaces", return_value={"front_ns": []}), \
             mock.patch("config.main.ConfigDBConnector", return_value=mock.Mock()), \
             mock.patch("config.main.ValidatedConfigDBConnector", return_value=db), \
             mock.patch("config.main.validate_mirror_session_config", return_value=True) as mock_validate, \
             mock.patch("config.main.clicommon.get_interface_naming_mode", return_value="alias"), \
             mock.patch("config.main.interface_alias_to_name",
                        side_effect=lambda _db, name: {"Eth0": "Ethernet0", "Eth4": "Ethernet4"}.get(name, name)):
            config.add_span("test_session", "Eth0", "Eth4", "rx", 0, None)

    assert mock_validate.call_args[0][3] == "Eth4"
    assert db.set_entry.call_args[0][2]["src_port"] == "Ethernet4"


def test_add_erspan_validates_before_src_port_alias_conversion():
    config.ADHOC_VALIDATION = True
    db = mock.MagicMock()

    with click.Context(click.Command("test")):
        with mock.patch("config.main.multi_asic.get_all_namespaces", return_value={"front_ns": []}), \
             mock.patch("config.main.ConfigDBConnector", return_value=mock.Mock()), \
             mock.patch("config.main.ValidatedConfigDBConnector", return_value=db), \
             mock.patch("config.main.validate_mirror_session_config", return_value=True) as mock_validate, \
             mock.patch("config.main.clicommon.get_interface_naming_mode", return_value="alias"), \
             mock.patch("config.main.interface_alias_to_name",
                        side_effect=lambda _db, name: {"Eth4": "Ethernet4"}.get(name, name)):
            config.add_erspan("test_session", "1.1.1.1", "2.2.2.2", 8, 63, 10, 0, None, "Eth4", "rx")

    assert mock_validate.call_args[0][3] == "Eth4"
    assert db.set_entry.call_args[0][2]["src_port"] == "Ethernet4"


def test_mirror_session_span_add_multi_asic_writes_only_destination_namespace():
    config.ADHOC_VALIDATION = True
    dbs = {"asic0": mock.MagicMock(), "asic1": mock.MagicMock()}

    with click.Context(click.Command("test")):
        with mock.patch('config.main.multi_asic.get_all_namespaces', return_value={'front_ns': ['asic0', 'asic1']}), \
             mock.patch('config.main.get_port_namespace',
                        side_effect=lambda port: {'Ethernet0': 'asic1', 'Ethernet4': 'asic1'}[port]), \
             mock.patch('config.main.ConfigDBConnector',
                        side_effect=lambda **kwargs: mock.MagicMock(namespace=kwargs.get('namespace'))), \
             mock.patch('config.main.ValidatedConfigDBConnector', side_effect=lambda conn: dbs[conn.namespace]), \
             mock.patch('config.main.validate_mirror_session_config', return_value=True) as mock_validate:
            config.add_span("test_session", "Ethernet0", "Ethernet4", "rx", 0, None)

    # asic0 should not have any writes
    dbs["asic0"].set_entry.assert_not_called()
    # asic1 should have exactly one write
    dbs["asic1"].set_entry.assert_called_once()
    _, _, value = dbs["asic1"].set_entry.call_args[0]
    assert value["dst_port"] == "Ethernet0"
    assert value["src_port"] == "Ethernet4"
    assert value["direction"] == "RX"
    assert value["queue"] == 0
    # Validation targeted the destination port's namespace
    assert mock_validate.call_args[0][5] == "asic1"


def test_mirror_session_span_add_multi_asic_rejects_cross_asic_source_port():
    config.ADHOC_VALIDATION = True
    dbs = {"asic0": mock.MagicMock(), "asic1": mock.MagicMock()}

    with click.Context(click.Command("test")):
        with mock.patch('config.main.multi_asic.get_all_namespaces', return_value={'front_ns': ['asic0', 'asic1']}), \
             mock.patch('config.main.get_port_namespace',
                        side_effect=lambda port: {'Ethernet0': 'asic0', 'Ethernet64': 'asic1'}[port]), \
             mock.patch('config.main.ConfigDBConnector',
                        side_effect=lambda **kwargs: mock.MagicMock(namespace=kwargs.get('namespace'))), \
             mock.patch('config.main.ValidatedConfigDBConnector', side_effect=lambda conn: dbs[conn.namespace]):
            with pytest.raises(click.UsageError):
                config.add_span("test_session", "Ethernet0", "Ethernet64", "rx", 0, None)

    # No writes to any namespace
    dbs["asic0"].set_entry.assert_not_called()
    dbs["asic1"].set_entry.assert_not_called()


def test_mirror_session_erspan_add_multi_asic_splits_source_ports_by_namespace():
    config.ADHOC_VALIDATION = True
    dbs = {"asic0": mock.MagicMock(), "asic1": mock.MagicMock(), "asic2": mock.MagicMock()}

    with click.Context(click.Command("test")):
        with mock.patch('config.main.multi_asic.get_all_namespaces',
                        return_value={'front_ns': ['asic0', 'asic1', 'asic2']}), \
             mock.patch('config.main.get_port_namespace',
                        side_effect=lambda port: {'Ethernet0': 'asic0', 'Ethernet8': 'asic1'}[port]), \
             mock.patch('config.main.ConfigDBConnector',
                        side_effect=lambda **kwargs: mock.MagicMock(namespace=kwargs.get('namespace'))), \
             mock.patch('config.main.ValidatedConfigDBConnector', side_effect=lambda conn: dbs[conn.namespace]), \
             mock.patch('config.main.validate_mirror_session_config', return_value=True), \
             mock.patch('config.main.interface_name_is_valid', return_value=True):
            config.add_erspan(
                "test_session", "1.1.1.1", "2.2.2.2", 8, 63, 10, 0, None,
                "Ethernet0,Ethernet8", "rx"
            )

    # Each namespace should get exactly one write
    for ns in ["asic0", "asic1", "asic2"]:
        dbs[ns].set_entry.assert_called_once()

    asic0_value = dbs["asic0"].set_entry.call_args[0][2]
    asic1_value = dbs["asic1"].set_entry.call_args[0][2]
    asic2_value = dbs["asic2"].set_entry.call_args[0][2]

    # asic0 gets Ethernet0's src_port
    assert asic0_value["src_port"] == "Ethernet0"
    assert asic0_value["direction"] == "RX"
    # asic1 gets Ethernet8's src_port
    assert asic1_value["src_port"] == "Ethernet8"
    assert asic1_value["direction"] == "RX"
    # asic2 gets the base ERSPAN session without src_port
    assert "src_port" not in asic2_value
    assert "direction" not in asic2_value


def test_mirror_session_remove_multi_asic_skips_missing_sessions():
    config.ADHOC_VALIDATION = False
    asic0_db = mock.MagicMock()
    asic0_db.get_entry.return_value = {"type": "SPAN", "dst_port": "Ethernet0"}
    asic1_db = mock.MagicMock()
    asic1_db.get_entry.return_value = {}
    dbs = {"asic0": asic0_db, "asic1": asic1_db}

    runner = CliRunner()
    with mock.patch('config.main.multi_asic.get_all_namespaces', return_value={'front_ns': ['asic0', 'asic1']}), \
         mock.patch('config.main.ConfigDBConnector',
                    side_effect=lambda **kwargs: mock.MagicMock(namespace=kwargs.get('namespace'))), \
         mock.patch('config.main.ValidatedConfigDBConnector', side_effect=lambda conn: dbs[conn.namespace]):
        result = runner.invoke(
            config.config.commands["mirror_session"].commands["remove"],
            ["sess1"]
        )
        assert result.exit_code == 0

    # asic0 has the session, so it should be deleted
    dbs["asic0"].set_entry.assert_called_once_with("MIRROR_SESSION", "sess1", None)
    # asic1 does not have the session, so set_entry should not be called
    dbs["asic1"].set_entry.assert_not_called()


def test_split_mirror_ports():
    assert config.split_mirror_ports("Ethernet0,Ethernet4") == ["Ethernet0", "Ethernet4"]
    assert config.split_mirror_ports("Ethernet0 , Ethernet4") == ["Ethernet0", "Ethernet4"]
    assert config.split_mirror_ports("Ethernet0") == ["Ethernet0"]
    assert config.split_mirror_ports("") == []
    assert config.split_mirror_ports(None) == []


def test_normalize_mirror_src_port_alias_mode():
    db = mock.MagicMock()
    alias_map = {"Eth0": "Ethernet0", "Eth4": "Ethernet4"}
    with mock.patch("config.main.clicommon.get_interface_naming_mode",
                    return_value="alias"), \
         mock.patch("config.main.interface_alias_to_name",
                    side_effect=lambda _db, name: alias_map.get(
                        name, name)):
        result = config.normalize_mirror_src_port(db, "Eth0,Eth4")
    assert result == "Ethernet0,Ethernet4"


def test_normalize_mirror_src_port_returns_none_for_empty():
    assert config.normalize_mirror_src_port(mock.MagicMock(), None) is None
    assert config.normalize_mirror_src_port(mock.MagicMock(), "") is None


def test_validate_mirror_session_config_cross_asic_duplicate():
    """validate_mirror_session_config should fail when session exists on another ASIC."""
    config.ADHOC_VALIDATION = True
    local_db = mock.MagicMock()
    local_db.get_entry.return_value = {}  # no session locally
    local_db.get_table.return_value = {}

    other_db = mock.MagicMock()
    other_db.get_entry.return_value = {"type": "ERSPAN"}  # session exists on other ASIC

    with click.Context(click.Command("test")):
        result = config.validate_mirror_session_config(
            local_db, "dup_session", None, None, None,
            namespace="asic0",
            front_asic_configdbs={"asic0": local_db, "asic1": other_db}
        )
    assert result is False


def test_erspan_multi_asic_validation_failure_prevents_all_writes():
    """Validation failure on one ASIC prevents writes to all ASICs."""
    config.ADHOC_VALIDATION = True
    dbs = {"asic0": mock.MagicMock(), "asic1": mock.MagicMock()}
    ns_map = {'Ethernet0': 'asic0', 'Ethernet8': 'asic1'}
    call_count = [0]

    def validate_side_effect(*args, **kwargs):
        call_count[0] += 1
        return call_count[0] < 2

    def make_conn(**kwargs):
        return mock.MagicMock(namespace=kwargs.get('namespace'))

    with click.Context(click.Command("test")):
        with mock.patch('config.main.multi_asic.get_all_namespaces',
                        return_value={
                            'front_ns': ['asic0', 'asic1']}), \
             mock.patch('config.main.get_port_namespace',
                        side_effect=lambda p: ns_map[p]), \
             mock.patch('config.main.ConfigDBConnector',
                        side_effect=make_conn), \
             mock.patch('config.main.ValidatedConfigDBConnector',
                        side_effect=lambda c: dbs[c.namespace]), \
             mock.patch('config.main.validate_mirror_session_config',
                        side_effect=validate_side_effect), \
             mock.patch('config.main.interface_name_is_valid',
                        return_value=True):
            config.add_erspan(
                "test_session", "1.1.1.1", "2.2.2.2",
                8, 63, 10, 0, None,
                "Ethernet0,Ethernet8", "rx"
            )

    dbs["asic0"].set_entry.assert_not_called()
    dbs["asic1"].set_entry.assert_not_called()


def test_erspan_multi_asic_rejects_non_front_panel_source_port():
    """ERSPAN multi-ASIC rejects source ports not in front_ns."""
    config.ADHOC_VALIDATION = True

    with click.Context(click.Command("test")):
        with mock.patch('config.main.multi_asic.get_all_namespaces',
                        return_value={'front_ns': ['asic0']}), \
             mock.patch('config.main.get_port_namespace',
                        return_value='back_ns0'), \
             mock.patch('config.main.interface_name_is_valid',
                        return_value=True):
            with pytest.raises(click.UsageError,
                               match="not a front-panel port"):
                config.add_erspan(
                    "test_session", "1.1.1.1", "2.2.2.2",
                    8, 63, 10, 0, None, "Ethernet128", "rx"
                )


def test_erspan_multi_asic_rejects_invalid_source_port():
    """ERSPAN multi-ASIC rejects invalid source ports."""
    config.ADHOC_VALIDATION = True

    with click.Context(click.Command("test")):
        with mock.patch('config.main.multi_asic.get_all_namespaces',
                        return_value={'front_ns': ['asic0']}), \
             mock.patch('config.main.interface_name_is_valid',
                        return_value=False):
            with pytest.raises(click.UsageError,
                               match="Source Interface.*invalid"):
                config.add_erspan(
                    "test_session", "1.1.1.1", "2.2.2.2",
                    8, 63, 10, 0, None, "InvalidPort", "rx"
                )


def test_span_multi_asic_rejects_invalid_source_port():
    """SPAN multi-ASIC rejects source ports with no namespace."""
    config.ADHOC_VALIDATION = True
    ns_map = {'Ethernet0': 'asic0'}

    with click.Context(click.Command("test")):
        with mock.patch('config.main.multi_asic.get_all_namespaces',
                        return_value={'front_ns': ['asic0']}), \
             mock.patch('config.main.get_port_namespace',
                        side_effect=lambda p: ns_map.get(p)):
            with pytest.raises(click.UsageError,
                               match="Source Interface.*invalid"):
                config.add_span(
                    "test_session", "Ethernet0",
                    "BadPort", "rx", 0, None
                )


def test_mirror_session_capability_checking():
    """Test mirror session capability checking functionality"""
    config.ADHOC_VALIDATION = True
    runner = CliRunner()

    # Test 1: Check that capability checking fails when direction is not supported
    with mock.patch('config.main.is_port_mirror_capability_supported') as mock_capability:
        mock_capability.return_value = False

        # Test with rx direction - should fail
        result = runner.invoke(
                config.config.commands["mirror_session"].commands["span"].commands["add"],
                ["test_session", "Ethernet20", "Ethernet24", "rx", "100"])

        assert result.exit_code != 0
        assert "Error: Port mirror direction 'rx' is not supported by the ASIC" in result.output

        # Test with tx direction - should fail
        result = runner.invoke(
                config.config.commands["mirror_session"].commands["span"].commands["add"],
                ["test_session", "Ethernet20", "Ethernet24", "tx", "100"])

        assert result.exit_code != 0
        assert "Error: Port mirror direction 'tx' is not supported by the ASIC" in result.output

        # Test with both direction - should fail
        result = runner.invoke(
                config.config.commands["mirror_session"].commands["span"].commands["add"],
                ["test_session", "Ethernet20", "Ethernet24", "both", "100"])

        assert result.exit_code != 0
        assert "Error: Port mirror direction 'both' is not supported by the ASIC" in result.output

    # Test 2: ERSPAN sessions bypass capability check even when capability returns False
    with mock.patch('config.main.is_port_mirror_capability_supported') as mock_capability:
        mock_capability.return_value = False

        result = runner.invoke(
                config.config.commands["mirror_session"].commands["erspan"].commands["add"],
                ["test_erspan", "1.1.1.1", "2.2.2.2", "8", "64", "0x88be"])

        # ERSPAN should not be blocked by port mirror capability
        assert "is not supported by the ASIC" not in result.output
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

        # Test no direction (checks both ingress and egress)
        result = config.is_port_mirror_capability_supported(None)
        assert result is False  # egress is "false", so fails

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

        # SPAN directions should fail when explicitly set to "false"
        assert config.is_port_mirror_capability_supported("rx") is False
        assert config.is_port_mirror_capability_supported("tx") is False
        assert config.is_port_mirror_capability_supported("both") is False
        # direction=None checks both; both are "false" so fails
        assert config.is_port_mirror_capability_supported(None) is False

    # Test 4: Test with absent capability keys (None returned from STATE_DB)
    with mock.patch('config.main.SonicV2Connector') as mock_connector:
        mock_instance = mock.Mock()
        mock_connector.return_value = mock_instance
        mock_instance.connect.return_value = None

        # Simulate keys absent from STATE_DB (returns None)
        mock_instance.get.return_value = None

        # All directions should return True (backward compatibility: absent = supported)
        assert config.is_port_mirror_capability_supported("rx") is True
        assert config.is_port_mirror_capability_supported("tx") is True
        assert config.is_port_mirror_capability_supported("both") is True
        assert config.is_port_mirror_capability_supported(None) is True

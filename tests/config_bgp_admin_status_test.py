from unittest import mock

import pytest
from click.testing import CliRunner

import config.main as config


@pytest.fixture
def config_db():
    db = mock.MagicMock()
    db.tables = {}
    db.get_table.side_effect = lambda table: db.tables.get(table, {})
    db.get_entry.side_effect = lambda table, key: db.get_table(table).get(key, {})
    db.get_keys.side_effect = lambda table: list(db.get_table(table))
    return db


@pytest.fixture(params=[("shutdown", "down"), ("startup", "up")])
def action(request):
    return request.param


def invoke_neighbor(config_db, action, neighbor):
    command, _ = action
    with mock.patch.object(config, "ConfigDBConnector", return_value=config_db), \
            mock.patch.object(config.multi_asic, "is_multi_asic", return_value=False):
        return CliRunner().invoke(config.bgp, [command, "neighbor", neighbor])


@pytest.mark.parametrize("interface,table", [
    ("Ethernet16", "INTERFACE"),
    ("PortChannel101", "PORTCHANNEL_INTERFACE"),
    ("Vlan200", "VLAN_INTERFACE"),
    ("Ethernet16.100", "VLAN_SUB_INTERFACE"),
    ("Po101.100", "VLAN_SUB_INTERFACE"),
])
def test_interface_neighbor_preserves_case(config_db, action, interface, table):
    config_db.tables = {
        "BGP_NEIGHBOR": {interface: {"name": "peer1", "asn": "65200"}},
        table: {interface: {}},
    }

    result = invoke_neighbor(config_db, action, interface)

    assert result.exit_code == 0, result.output
    config_db.mod_entry.assert_called_once_with(
        "bgp_neighbor", interface, {"admin_status": action[1]}
    )
    config_db.get_entry.assert_called_once_with("BGP_NEIGHBOR", interface)


def test_exact_key_takes_precedence_over_lowercase_key(config_db, action):
    config_db.tables["BGP_NEIGHBOR"] = {
        "Ethernet16": {"name": "peer1"},
        "ethernet16": {"name": "peer2"},
    }
    config_db.tables["INTERFACE"] = {"Ethernet16": {}}

    result = invoke_neighbor(config_db, action, "Ethernet16")

    assert result.exit_code == 0, result.output
    config_db.mod_entry.assert_called_once_with(
        "bgp_neighbor", "Ethernet16", {"admin_status": action[1]}
    )


@pytest.mark.parametrize("address", ["192.0.2.1", "fc00::1", "FC00::1"])
def test_numbered_neighbor_lookup(config_db, action, address):
    key = address.lower()
    config_db.tables["BGP_NEIGHBOR"] = {key: {"name": "peer1", "asn": "65200"}}

    result = invoke_neighbor(config_db, action, address)

    assert result.exit_code == 0, result.output
    config_db.mod_entry.assert_called_once_with(
        "bgp_neighbor", key, {"admin_status": action[1]}
    )
    config_db.get_keys.assert_not_called()


def test_exact_uppercase_ipv6_key(config_db, action):
    config_db.tables["BGP_NEIGHBOR"] = {"FC00::1": {"name": "peer1", "asn": "65200"}}

    result = invoke_neighbor(config_db, action, "FC00::1")

    assert result.exit_code == 0, result.output
    config_db.mod_entry.assert_called_once_with(
        "bgp_neighbor", "FC00::1", {"admin_status": action[1]}
    )


def test_hostname_lookup_updates_matching_neighbors(config_db, action):
    config_db.tables["BGP_NEIGHBOR"] = {
        "192.0.2.1": {"name": "peer1"},
        "Ethernet16": {"name": "peer1"},
        "PortChannel101": {"name": "peer2"},
    }

    result = invoke_neighbor(config_db, action, "peer1")

    assert result.exit_code == 0, result.output
    assert config_db.mod_entry.call_args_list == [
        mock.call("bgp_neighbor", "192.0.2.1", {"admin_status": action[1]}),
        mock.call("bgp_neighbor", "Ethernet16", {"admin_status": action[1]}),
    ]


@pytest.mark.parametrize("neighbor", ["Ethernet99", "ethernet16", "missing-host"])
def test_missing_neighbor_reports_error(config_db, action, neighbor):
    config_db.tables = {
        "BGP_NEIGHBOR": {"Ethernet16": {"name": "peer1"}},
        "INTERFACE": {"Ethernet16": {}},
    }

    result = invoke_neighbor(config_db, action, neighbor)

    assert result.exit_code != 0
    assert f"Could not locate neighbor '{neighbor}'" in result.output
    config_db.mod_entry.assert_not_called()


def test_interface_neighbor_in_multi_asic_namespace(action):
    databases = {namespace: mock.MagicMock() for namespace in ["asic0", "asic1"]}
    tables = {
        "asic0": {},
        "asic1": {
            "BGP_NEIGHBOR": {"Ethernet16": {"name": "peer1"}},
            "INTERFACE": {"Ethernet16": {}},
        },
    }
    for namespace, db in databases.items():
        db.get_table.side_effect = lambda table, namespace=namespace: tables[namespace].get(table, {})
    for db in databases.values():
        db.get_entry.side_effect = (
            lambda table, key, db=db: db.get_table(table).get(key, {})
        )
        db.get_keys.side_effect = lambda table, db=db: list(db.get_table(table))

    def connect(**kwargs):
        return databases[kwargs["namespace"]]

    with mock.patch.object(config, "ConfigDBConnector", side_effect=connect), \
            mock.patch.object(config.multi_asic, "is_multi_asic", return_value=True), \
            mock.patch.object(
                config.multi_asic, "get_all_namespaces",
                return_value={"front_ns": ["asic0"], "back_ns": ["asic1"]},
            ):
        result = CliRunner().invoke(config.bgp, [action[0], "neighbor", "Ethernet16"])

    assert result.exit_code == 0, result.output
    databases["asic0"].mod_entry.assert_not_called()
    databases["asic1"].mod_entry.assert_called_once_with(
        "bgp_neighbor", "Ethernet16", {"admin_status": action[1]}
    )


def test_neighbor_help_includes_interface_name(action):
    result = CliRunner().invoke(config.bgp, [action[0], "neighbor", "--help"])

    assert result.exit_code == 0
    assert "<ipaddr_or_interface_or_hostname>" in result.output
    assert "interface name" in result.output


@pytest.mark.parametrize("interface,table", [
    ("Ethernet16", "INTERFACE"),
    ("PortChannel101", "PORTCHANNEL_INTERFACE"),
    ("Vlan200", "VLAN_INTERFACE"),
    ("Ethernet16.100", "VLAN_SUB_INTERFACE"),
])
def test_interface_address_tuple_key(config_db, action, interface, table):
    config_db.tables = {
        "BGP_NEIGHBOR": {interface: {"name": "peer1"}},
        table: {(interface, "192.0.2.1/31"): {}},
    }

    result = invoke_neighbor(config_db, action, interface)

    assert result.exit_code == 0, result.output
    config_db.mod_entry.assert_called_once_with(
        "bgp_neighbor", interface, {"admin_status": action[1]}
    )


@pytest.mark.parametrize("missing_table", ["INTERFACE", "BGP_NEIGHBOR"])
def test_interface_requires_both_configurations(config_db, action, missing_table):
    config_db.tables = {
        "BGP_NEIGHBOR": {"Ethernet16": {"name": "peer1"}},
        "INTERFACE": {"Ethernet16": {}},
    }
    del config_db.tables[missing_table]

    result = invoke_neighbor(config_db, action, "Ethernet16")

    assert result.exit_code != 0
    assert "Could not locate neighbor 'Ethernet16'" in result.output
    config_db.mod_entry.assert_not_called()


def test_interface_table_case_must_match(config_db, action):
    config_db.tables = {
        "BGP_NEIGHBOR": {"Ethernet16": {"name": "peer1"}},
        "INTERFACE": {"ethernet16": {}},
    }

    result = invoke_neighbor(config_db, action, "Ethernet16")

    assert result.exit_code != 0
    config_db.mod_entry.assert_not_called()


def test_interface_selection_only_updates_one_same_hostname_session(config_db, action):
    config_db.tables = {
        "BGP_NEIGHBOR": {
            "Ethernet16": {"name": "SPINE01"},
            "Ethernet20": {"name": "SPINE01"},
        },
        "INTERFACE": {"Ethernet16": {}, "Ethernet20": {}},
    }

    result = invoke_neighbor(config_db, action, "Ethernet16")

    assert result.exit_code == 0, result.output
    config_db.mod_entry.assert_called_once_with(
        "bgp_neighbor", "Ethernet16", {"admin_status": action[1]}
    )


def test_interface_helper_does_not_identify_numbered_neighbor(config_db):
    config_db.tables["BGP_NEIGHBOR"] = {"192.0.2.1": {"name": "peer1"}}

    assert config._is_neighbor_interface(config_db, "192.0.2.1") is False

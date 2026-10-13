import importlib.util
import sys
from pathlib import Path
from unittest import mock

import pytest
from scapy.contrib.lacp import LACP, SlowProtocol


ROOT = Path(__file__).parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def lacp(monkeypatch):
    monkeypatch.setitem(sys.modules, "swsscommon.swsscommon", mock.MagicMock())
    return load_module("lacp_test_module", ROOT / "utilities_common" / "lacp.py")


@pytest.fixture
def keepalive(monkeypatch, lacp):
    monkeypatch.setitem(sys.modules, "utilities_common.lacp", lacp)
    monkeypatch.setitem(sys.modules, "sonic_py_common", mock.MagicMock())
    monkeypatch.setitem(sys.modules, "pyroute2", mock.MagicMock())
    return load_module("lag_keepalive_test_module", ROOT / "scripts" / "lag_keepalive.py")


@pytest.fixture
def port_channel():
    return {
        "runner": {"enable_retry_count_feature": True, "retry_count": 5},
        "ports": {
            "Ethernet0": {
                "ifinfo": {"dev_addr": "00:11:22:33:44:55"},
                "runner": {
                    "partner_retry_count": 7,
                    "actor_lacpdu_info": {
                        "system_priority": 65535, "system": "00:11:22:33:44:55",
                        "key": 1, "port_priority": 255, "port": 1, "state": 61,
                    },
                    "partner_lacpdu_info": {
                        "system_priority": 32768, "system": "00:aa:bb:cc:dd:ee",
                        "key": 2, "port_priority": 128, "port": 2, "state": 63,
                    },
                },
            },
        },
    }


@pytest.mark.parametrize("actor,partner", [(5, 7), (255, 255), (4, 1)])
def test_extended_packet_wire_format(keepalive, port_channel, actor, partner):
    port_channel["runner"]["retry_count"] = actor
    port_channel["ports"]["Ethernet0"]["runner"]["partner_retry_count"] = partner
    standard = bytes(keepalive.craft_lacp_packet(port_channel, "Ethernet0"))
    extended = bytes(keepalive.craft_lacp_packet(port_channel, "Ethernet0", True))

    assert len(extended) == len(standard) == 124
    assert extended[:15] == standard[:15]
    assert extended[15] == 0xf1
    assert extended[16:72] == standard[16:72]
    assert extended[72:80] == bytes([0x80, 4, actor, 0, 0x81, 4, partner, 0])
    assert extended[80:] == bytes(44)


def test_standard_packet_does_not_require_retry_state(keepalive, port_channel):
    del port_channel["runner"]
    del port_channel["ports"]["Ethernet0"]["runner"]["partner_retry_count"]
    packet = keepalive.craft_lacp_packet(port_channel, "Ethernet0")
    assert packet[LACP].version == 1
    assert bytes(packet)[72:] == bytes(52)


@pytest.mark.parametrize("new_version,reset", [(False, False), (True, False), (True, True)])
def test_retry_helper_packet_behavior_is_unchanged(keepalive, lacp, port_channel, monkeypatch,
                                                  new_version, reset):
    monkeypatch.setattr(SlowProtocol, "payload_guess", SlowProtocol.payload_guess[:])
    helper = load_module("teamd_retry_test_module", ROOT / "scripts" / "teamd_increase_retry_count.py")
    assert helper.get_retry_count_port_channels is lacp.get_retry_count_port_channels
    packet = bytes(helper.craftLacpPacket(port_channel, "Ethernet0",
                                         isResetPacket=reset, newVersion=new_version))
    standard = bytes(keepalive.craft_lacp_packet(port_channel, "Ethernet0"))
    assert len(packet) == len(standard) == 124
    if new_version:
        assert packet[15] == 0xf1
        assert packet[16:72] == standard[16:72]
        assert packet[72:80] == bytes([0x80, 4, 3 if reset else 5, 0, 0x81, 4, 3, 0])
        assert packet[80:] == bytes(44)
    else:
        assert packet == standard


@pytest.mark.parametrize("field,value", [
    ("retry_count", 3), ("retry_count", 256), ("retry_count", "5"),
    ("retry_count", True), ("retry_count", None),
    ("enable_retry_count_feature", False), ("enable_retry_count_feature", "true"),
    ("partner_retry_count", 0), ("partner_retry_count", 256),
    ("partner_retry_count", "7"), ("partner_retry_count", True),
])
def test_invalid_retry_state_is_not_silently_downgraded(keepalive, port_channel, field, value):
    runner = (port_channel["ports"]["Ethernet0"]["runner"]
              if field == "partner_retry_count" else port_channel["runner"])
    runner[field] = value
    with pytest.raises(ValueError, match="Invalid extended retry-count state"):
        keepalive.craft_lacp_packet(port_channel, "Ethernet0", True)


@pytest.mark.parametrize("field", ["retry_count", "enable_retry_count_feature", "partner_retry_count"])
def test_missing_retry_state_requires_initialization_retry(keepalive, port_channel, field):
    runner = (port_channel["ports"]["Ethernet0"]["runner"]
              if field == "partner_retry_count" else port_channel["runner"])
    del runner[field]
    with pytest.raises(KeyError):
        keepalive.craft_lacp_packet(port_channel, "Ethernet0", True)


@pytest.mark.parametrize("namespace", ["", "asic1"])
@pytest.mark.parametrize("preserve", [False, True])
def test_member_selection_and_namespace(keepalive, port_channel, namespace, preserve):
    app_db = mock.MagicMock()
    config_db = mock.MagicMock()
    app_db.get_keys.return_value = [
        ("PortChannel1", "Ethernet0"), ("PortChannel2", "Ethernet4"),
        ("PortChannel3", "Ethernet8"), ("PortChannel1", "Ethernet12"),
    ]
    app_db.get.side_effect = ["up", "up", "down", "up"]
    config_db.get_entry.side_effect = [{"admin_status": "up"}, {"admin_status": "up"},
                                     {"admin_status": "down"}]
    with mock.patch.object(keepalive, "ConfigDBConnector", side_effect=[app_db, config_db]) as connector, \
            mock.patch.object(keepalive, "get_retry_count_port_channels", return_value={"PortChannel1"}) as select, \
            mock.patch.object(keepalive, "get_port_channel_config", return_value=port_channel) as config, \
            mock.patch.object(keepalive, "craft_lacp_packet") as craft, \
            mock.patch.object(keepalive.conf, "L2socket") as socket:
        active, packets = keepalive.get_lacpdu_per_lag_member(namespace, preserve)

    assert active == ["Ethernet0", "Ethernet4"]
    assert list(packets) == active
    assert connector.call_args_list == [mock.call(namespace=namespace)] * 2
    assert config.call_args_list == [mock.call("PortChannel1", namespace), mock.call("PortChannel2", namespace)]
    assert craft.call_args_list == [
        mock.call(port_channel, "Ethernet0", preserve_retry_count=preserve),
        mock.call(port_channel, "Ethernet4", preserve_retry_count=False),
    ]
    assert socket.call_args_list == [mock.call(iface=port) for port in active]
    if preserve:
        select.assert_called_once_with(namespace)
    else:
        select.assert_not_called()


@pytest.mark.parametrize("default_status,neighbor_status,expected", [
    (None, None, True), ("up", None, True), ("down", None, False),
    ("down", "up", True), ("up", "down", False),
])
@pytest.mark.parametrize("namespace", ["", "asic1"])
def test_retry_count_eligibility(lacp, default_status, neighbor_status, expected, namespace):
    tables = {}
    for name in ("LAG_TABLE", "PORTCHANNEL_INTERFACE", "DEVICE_METADATA", "BGP_NEIGHBOR"):
        tables[name] = mock.MagicMock()
    tables["LAG_TABLE"].getKeys.return_value = ["PortChannel1", "PortChannel2", "PortChannel3"]
    tables["LAG_TABLE"].get.side_effect = [
        (True, [("admin_status", "up"), ("oper_status", "up")]),
        (True, [("admin_status", "up"), ("oper_status", "down")]),
        (True, [("admin_status", "down"), ("oper_status", "up")]),
    ]
    tables["PORTCHANNEL_INTERFACE"].getKeys.return_value = [
        "PortChannel1", "PortChannel1|10.0.0.0/31", "PortChannel2|10.0.0.2/31",
        "PortChannel3|10.0.0.4/31",
    ]
    tables["DEVICE_METADATA"].get.return_value = (
        True, [] if default_status is None else [("default_bgp_status", default_status)])
    tables["BGP_NEIGHBOR"].getKeys.return_value = ["10.0.0.1", "10.0.0.3", "10.0.0.5"]
    status = [] if neighbor_status is None else [("admin_status", neighbor_status)]
    tables["BGP_NEIGHBOR"].get.side_effect = [
        (True, [("local_addr", "10.0.0.0")] + status),
        (True, [("local_addr", "10.0.0.2"), ("admin_status", "up")]),
        (True, [("local_addr", "10.0.0.4"), ("admin_status", "up")]),
    ]
    with mock.patch.object(lacp, "Table", side_effect=lambda db, name: tables[name]):
        assert lacp.get_retry_count_port_channels(namespace) == ({"PortChannel1"} if expected else set())
    lacp.SonicDBKey.assert_called_once_with(namespace)
    assert lacp.DBConnector.call_args_list == [
        mock.call("APPL_DB", 0, False, lacp.SonicDBKey.return_value),
        mock.call("CONFIG_DB", 0, False, lacp.SonicDBKey.return_value),
    ]


def test_keepalive_replays_cached_extended_packet(keepalive, port_channel):
    packet = keepalive.craft_lacp_packet(port_channel, "Ethernet0", True)
    wire_packet = bytes(packet)
    socket = mock.sentinel.socket
    port_channel.clear()
    with mock.patch.object(keepalive, "sendp") as send, \
            mock.patch.object(keepalive.time, "sleep") as sleep, \
            mock.patch.object(keepalive, "get_port_channel_config") as config, \
            mock.patch.object(keepalive, "log_info"):
        keepalive.lag_keepalive({"Ethernet0": (socket, packet)})
    assert send.call_args_list == [mock.call(packet, socket=socket, verbose=False)] * 300
    assert sleep.call_args_list == [mock.call(1)] * 300
    assert bytes(packet) == wire_packet
    config.assert_not_called()


def test_main_retries_then_forks_with_preservation(keepalive, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["lag_keepalive.py", "--namespace", "asic1",
                                     "--preserve-retry-count", "--fork-into-background"])
    packets = {"Ethernet0": (mock.sentinel.socket, mock.sentinel.packet)}
    with mock.patch.object(keepalive, "get_lacpdu_per_lag_member",
                           side_effect=[ValueError("not ready"), (["Ethernet0"], packets)]) as get, \
            mock.patch.object(keepalive.os, "fork", return_value=0) as fork, \
            mock.patch.object(keepalive, "lag_keepalive") as send, \
            mock.patch.object(keepalive, "log_info"), \
            mock.patch.object(keepalive, "log_error") as error:
        keepalive.main()
    assert get.call_args_list == [mock.call("asic1", True)] * 2
    error.assert_called_once()
    fork.assert_called_once()
    send.assert_called_once_with(packets)
    keepalive.netns.setns.assert_called_once_with("asic1")
    keepalive.SonicDBConfig.initializeGlobalConfig.assert_called_once()

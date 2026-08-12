import json
import inspect
from unittest.mock import patch

import pytest

from utilities_common import constants
import utilities_common.multi_asic as multi_asic_util


def _get_target_function():
    if hasattr(multi_asic_util, "multi_asic_get_addr_info_from_ns"):
        return multi_asic_util.multi_asic_get_addr_info_from_ns
    if hasattr(multi_asic_util, "multi_asic_get_ip_addr_db_from_ns"):
        return multi_asic_util.multi_asic_get_ip_addr_db_from_ns
    pytest.skip("No addr info helper found in utilities_common.multi_asic")


def _call_target(target_func, namespace, iface=None):
    params = inspect.signature(target_func).parameters
    if len(params) == 1:
        return target_func(namespace)
    if iface is None:
        return target_func(namespace)
    return target_func(namespace, iface)


def _assert_ip_json_cmd(mock_check_output, namespace):
    called_cmd = mock_check_output.call_args[0][0]
    called_cmd_as_str = " ".join(called_cmd) if isinstance(called_cmd, (list, tuple)) else str(called_cmd)

    assert "ip -json addr show" in called_cmd_as_str
    if namespace == constants.DEFAULT_NAMESPACE:
        assert "netns exec" not in called_cmd_as_str
    else:
        assert f"netns exec {namespace}" in called_cmd_as_str

    assert mock_check_output.call_args[1] == {"shell": True}


@patch("utilities_common.multi_asic.subprocess.check_output", create=True)
def test_get_addr_info_from_ns_default_ns(mock_check_output):
    payload = [
        {
            "ifname": "Ethernet0",
            "addr_info": [
                {"family": "inet", "local": "10.0.0.1", "prefixlen": 24},
                {"family": "inet6", "local": "fc00::1", "prefixlen": 64},
            ],
        },
        {
            "ifname": "lo",
            "addr_info": [{"family": "inet", "local": "127.0.0.1", "prefixlen": 8}],
        },
    ]
    mock_check_output.return_value = json.dumps(payload).encode("utf-8")

    target_func = _get_target_function()

    result = _call_target(target_func, constants.DEFAULT_NAMESPACE, "Ethernet0")

    if isinstance(result, dict):
        assert set(result.keys()) == {"Ethernet0", "lo"}
        assert result["Ethernet0"]["ifname"] == "Ethernet0"
        assert result["lo"]["addr_info"][0]["local"] == "127.0.0.1"
    else:
        assert isinstance(result, list)
        assert any(item.get("local") == "10.0.0.1" for item in result)
        assert any(item.get("family") == "inet6" for item in result)

    _assert_ip_json_cmd(mock_check_output, constants.DEFAULT_NAMESPACE)


@patch("utilities_common.multi_asic.subprocess.check_output", create=True)
def test_get_addr_info_from_ns_asic_ns(mock_check_output):
    payload = [
        {
            "ifname": "Ethernet-BP0",
            "addr_info": [{"family": "inet6", "local": "fe80::1", "prefixlen": 64}],
        }
    ]
    mock_check_output.return_value = json.dumps(payload).encode("utf-8")

    target_func = _get_target_function()

    result = _call_target(target_func, "asic0", "Ethernet-BP0")

    if isinstance(result, dict):
        assert list(result.keys()) == ["Ethernet-BP0"]
        assert result["Ethernet-BP0"]["addr_info"][0]["prefixlen"] == 64
    else:
        assert isinstance(result, list)
        assert any(item.get("local") == "fe80::1" for item in result)

    _assert_ip_json_cmd(mock_check_output, "asic0")


@patch("utilities_common.multi_asic.subprocess.check_output", create=True)
def test_get_addr_info_from_ns_missing_interface(mock_check_output):
    payload = [
        {
            "ifname": "Ethernet0",
            "addr_info": [{"family": "inet", "local": "10.0.0.1", "prefixlen": 24}],
        }
    ]
    mock_check_output.return_value = json.dumps(payload).encode("utf-8")

    target_func = _get_target_function()

    result = _call_target(target_func, constants.DEFAULT_NAMESPACE, "Ethernet999")

    if isinstance(result, dict):
        assert "Ethernet999" not in result
    else:
        assert result in ([], None)

    _assert_ip_json_cmd(mock_check_output, constants.DEFAULT_NAMESPACE)

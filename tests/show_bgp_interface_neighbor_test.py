from unittest import mock

import pytest
from click.testing import CliRunner

import show.main as show_cli  # Load the CLI root before its BGP modules.
from show import bgp_frr_v4, bgp_frr_v6


@pytest.fixture(params=[bgp_frr_v4, bgp_frr_v6], ids=["ipv4", "ipv6"])
def family(request):
    return request.param


def invoke_neighbor(family, neighbor=None, info_type=None, vrf="default", namespace=None):
    arguments = []
    bgp_command = show_cli.cli.commands[
        "ip" if family is bgp_frr_v4 else "ipv6"
    ].commands["bgp"]
    if vrf == "default":
        command = bgp_command.commands["neighbors"]
    else:
        command = bgp_command.commands["vrf"]
        arguments.extend([vrf, "neighbors"])
    if neighbor is not None:
        arguments.append(neighbor)
    if info_type is not None:
        arguments.append(info_type)
    if namespace is not None:
        arguments.extend(["--namespace", namespace])
    return CliRunner().invoke(command, arguments)


def expected_command(family, neighbor="", info_type=None, vrf="default"):
    if family is bgp_frr_v4:
        command = f"show ip bgp vrf {vrf} neighbor"
        if neighbor:
            command += f" {neighbor}"
            if info_type is not None:
                command += f" {info_type}"
        return command
    return f"show bgp vrf {vrf} ipv6 neighbor {neighbor} {info_type or ''}"


@pytest.mark.parametrize("interface", ["Ethernet16", "PortChannel101", "Ethernet16.100"])
@pytest.mark.parametrize("info_type", [None, "routes", "advertised-routes", "received-routes"])
@pytest.mark.parametrize("vrf", ["default", "Vrf-red"])
def test_configured_interface_neighbor(family, interface, info_type, vrf):
    with mock.patch.object(family, "isInterfaceNameValid", return_value=True), \
            mock.patch.object(
                family.bgp_util, "get_namespace_for_bgp_neighbor", return_value="asic1",
            ) as lookup, \
            mock.patch.object(
                family.multi_asic, "get_namespace_list", return_value=["asic1"],
            ), \
            mock.patch.object(
                family.bgp_util, "run_bgp_show_command", return_value="neighbor details\n",
            ) as run:
        result = invoke_neighbor(family, interface, info_type, vrf)

    assert result.exit_code == 0, result.output
    assert result.output == "neighbor details\n"
    lookup.assert_called_once_with(interface, vrf)
    run.assert_called_once_with(expected_command(family, interface, info_type, vrf), "asic1")


def test_numbered_neighbor_unchanged(family):
    address = "192.0.2.1" if family is bgp_frr_v4 else "FC00::1"
    with mock.patch.object(family, "isInterfaceNameValid") as validate, \
            mock.patch.object(
                family.bgp_util, "get_namespace_for_bgp_neighbor", return_value="",
            ) as lookup, \
            mock.patch.object(family.multi_asic, "get_namespace_list", return_value=[""]), \
            mock.patch.object(
                family.bgp_util, "run_bgp_show_command", return_value="neighbor details\n",
            ) as run:
        result = invoke_neighbor(family, address)

    assert result.exit_code == 0, result.output
    validate.assert_not_called()
    lookup.assert_called_once_with(address, "default")
    run.assert_called_once_with(expected_command(family, address), "")


@pytest.mark.parametrize("neighbor", ["invalid;name", "Ethernet16\n", "wrong-family"])
def test_invalid_identifier_or_wrong_address_family(family, neighbor):
    wrong_family = neighbor == "wrong-family"
    if wrong_family:
        neighbor = "fc00::1" if family is bgp_frr_v4 else "192.0.2.1"
    with mock.patch.object(family, "isInterfaceNameValid", return_value=wrong_family), \
            mock.patch.object(family.bgp_util, "get_namespace_for_bgp_neighbor") as lookup, \
            mock.patch.object(family.bgp_util, "run_bgp_show_command") as run:
        result = invoke_neighbor(family, neighbor)

    assert result.exit_code == 2
    version = "ipv4" if family is bgp_frr_v4 else "ipv6"
    assert f"{neighbor} is not valid {version} address" in result.output
    lookup.assert_not_called()
    run.assert_not_called()


@pytest.mark.parametrize("neighbor", ["Ethernet99", "invalid_address"])
def test_unconfigured_interface_is_rejected(family, neighbor):
    with mock.patch.object(family, "isInterfaceNameValid", return_value=True), \
            mock.patch.object(
                family.bgp_util, "get_namespace_for_bgp_neighbor",
                side_effect=ValueError("BGP neighbor not configured"),
            ), \
            mock.patch.object(family.bgp_util, "run_bgp_show_command") as run:
        result = invoke_neighbor(family, neighbor)

    assert result.exit_code == 2
    version = "ipv4" if family is bgp_frr_v4 else "ipv6"
    assert f"{neighbor} is not valid {version} address" in result.output
    run.assert_not_called()


def test_missing_numbered_neighbor_error_unchanged(family):
    address = "192.0.2.99" if family is bgp_frr_v4 else "fc00::99"
    with mock.patch.object(
            family.bgp_util, "get_namespace_for_bgp_neighbor",
            side_effect=ValueError("BGP neighbor not configured"),
    ), mock.patch.object(family.bgp_util, "run_bgp_show_command") as run:
        result = invoke_neighbor(family, address)

    assert result.exit_code == 2
    assert "BGP neighbor not configured" in result.output
    run.assert_not_called()


def test_all_neighbors_unchanged(family):
    with mock.patch.object(family, "isInterfaceNameValid") as validate, \
            mock.patch.object(family.bgp_util, "get_namespace_for_bgp_neighbor") as lookup, \
            mock.patch.object(family.multi_asic, "get_namespace_list", return_value=[""]), \
            mock.patch.object(
                family.bgp_util, "run_bgp_show_command", return_value="all neighbors\n",
            ) as run:
        result = invoke_neighbor(family)

    assert result.exit_code == 0, result.output
    assert result.output == "all neighbors\n"
    validate.assert_not_called()
    lookup.assert_not_called()
    run.assert_called_once_with(expected_command(family), "")


def test_interface_namespace_mismatch_warning(family):
    with mock.patch.object(family, "isInterfaceNameValid", return_value=True), \
            mock.patch.object(
                family.bgp_util, "get_namespace_for_bgp_neighbor", return_value="asic1",
            ), \
            mock.patch.object(family.multi_asic, "get_namespace_list", return_value=["asic1"]), \
            mock.patch.object(
                family.bgp_util, "run_bgp_show_command", return_value="neighbor details\n",
            ) as run:
        result = invoke_neighbor(family, "Ethernet16", namespace="asic0")

    assert result.exit_code == 0, result.output
    assert "present in namespace asic1 not in asic0" in result.output
    run.assert_called_once_with(expected_command(family, "Ethernet16"), "asic1")


@pytest.mark.parametrize("vrf", ["default", "Vrf-red"])
def test_help_includes_interface_name(family, vrf):
    bgp_command = show_cli.cli.commands[
        "ip" if family is bgp_frr_v4 else "ipv6"
    ].commands["bgp"]
    command = bgp_command.commands["neighbors"] if vrf == "default" else bgp_command.commands["vrf"]
    arguments = ["--help"] if vrf == "default" else [vrf, "neighbors", "--help"]

    result = CliRunner().invoke(command, arguments)

    assert result.exit_code == 0, result.output
    assert "<interface-name>" in result.output

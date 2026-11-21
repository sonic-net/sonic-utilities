"""Verify the draft command surface without requiring SONiC or hardware."""

import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest
from click import ClickException
from click.testing import CliRunner


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_COMMANDS = [
    ["map"],
    ["oe", "list"],
    ["oe", "info"],
    ["oe", "status"],
    ["oe", "lpmode"],
    ["oe", "flag"],
    ["oe", "dom"],
    ["oe", "temperature"],
    ["oe", "voltage"],
    ["oe", "firmware-info"],
    ["els", "list"],
    ["els", "presence"],
    ["els", "info"],
    ["els", "status"],
    ["els", "lpmode"],
    ["els", "flag"],
    ["els", "dom"],
    ["els", "temperature"],
    ["els", "voltage"],
    ["els", "firmware-info"],
]
PORT_COMMANDS = ["eeprom", "info", "status", "presence", "lpmode", "error-status"]


def load_source(name, path):
    """Load either script or wrapper without importing the full show CLI."""
    loader = SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script():
    return load_source("cposhow_framework_script", ROOT / "scripts" / "cposhow")


@pytest.fixture(params=["script", "wrapper"])
def entrypoint(request, script):
    if request.param == "script":
        return script.cli
    return load_source("cposhow_framework_wrapper", ROOT / "show" / "cpo.py").cpo


@pytest.mark.parametrize("command", PUBLIC_COMMANDS)
def test_public_help_is_available(entrypoint, command):
    """Every reserved leaf must be inspectable before queries are implemented."""
    result = CliRunner().invoke(entrypoint, command + ["--help"])
    assert result.exit_code == 0, result.output
    assert "--namespace" in result.output
    assert "--json" in result.output


@pytest.mark.parametrize("command", PUBLIC_COMMANDS)
def test_unimplemented_queries_fail_explicitly(entrypoint, command):
    """An empty scaffold must never masquerade as a successful query."""
    result = CliRunner().invoke(entrypoint, command)
    assert result.exit_code == 1, result.output
    assert "not implemented" in result.output
    assert "Traceback" not in result.output


def test_internal_port_group_is_hidden(script):
    result = CliRunner().invoke(script.cli, ["--help"])
    assert result.exit_code == 0
    assert "  port " not in result.output
    assert "  oe " in result.output
    assert "  els " in result.output


@pytest.mark.parametrize("command", PORT_COMMANDS)
def test_internal_port_commands_are_inspectable_but_not_implemented(script, command):
    runner = CliRunner()
    help_result = runner.invoke(script.cli, ["port", command, "--help"])
    assert help_result.exit_code == 0, help_result.output
    assert "--port" in help_result.output
    assert "--all" in help_result.output

    result = runner.invoke(script.cli, ["port", command, "--port", "Ethernet0", "--port", "Ethernet8"])
    assert result.exit_code == 1, result.output
    assert "not implemented" in result.output


def test_conflicting_internal_port_selection_is_rejected(script):
    result = CliRunner().invoke(script.cli, ["port", "info", "--port", "Ethernet0", "--all"])
    assert result.exit_code == 2
    assert "mutually exclusive" in result.output


@pytest.mark.parametrize("bank", ["-1", "invalid"])
def test_invalid_bank_is_rejected_before_query(entrypoint, bank):
    result = CliRunner().invoke(entrypoint, ["oe", "dom", "oe0", "--bank", bank])
    assert result.exit_code == 2
    assert "not implemented" not in result.output


def test_resource_options_reach_explicit_placeholder(entrypoint):
    result = CliRunner().invoke(
        entrypoint,
        ["els", "flag", "els0", "--bank", "0", "--history", "--show-suppressed", "-n", "asic0", "--json"],
    )
    assert result.exit_code == 1, result.output
    assert "not implemented" in result.output


def test_hardware_fetch_is_not_claimed_by_db_only_script(script):
    result = CliRunner().invoke(script.cli, ["port", "error-status", "--port", "Ethernet0", "-hw"])
    assert result.exit_code == 2
    assert "No such option" in result.output


def test_constructor_does_not_open_files_or_devices(script, monkeypatch):
    def unexpected_open(*args, **kwargs):
        pytest.fail("Constructing the framework must not perform file or device I/O")

    monkeypatch.setattr("builtins.open", unexpected_open)
    script.CPOShow(namespace="asic0")


@pytest.mark.parametrize("method, arguments", [
    ("get_map", ()),
    ("get_resource", ("oe", "dom")),
    ("get_port", ("info",)),
    ("display", ()),
])
def test_direct_business_entrypoints_cannot_return_fake_results(script, method, arguments):
    with pytest.raises(ClickException, match="not implemented"):
        getattr(script.CPOShow(), method)(*arguments)

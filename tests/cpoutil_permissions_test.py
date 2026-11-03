from unittest import mock

import pytest
from click.testing import CliRunner

from cpoutil import main as cpoutil


@pytest.mark.parametrize("arguments", [
    ["show", "interface", "presence"],
    ["show", "interface", "map"],
    ["read-eeprom", "els"],
    ["write-eeprom", "els", "-i", "0", "-n", "0xb0", "-o", "132", "-d", "01"],
    ["show", "--help"],
])
def test_non_root_is_rejected_before_platform_loading(monkeypatch, arguments):
    monkeypatch.setattr(cpoutil.os, "geteuid", lambda: 1000)
    initialize = mock.Mock(side_effect=AssertionError("permission denial accessed hardware"))
    monkeypatch.setattr(cpoutil, "initialize_platform", initialize)
    result = CliRunner().invoke(cpoutil.cli, arguments)
    assert result.exit_code == cpoutil.ERROR_PERMISSIONS == 1
    assert result.output == "Root privileges are required for this operation\n"
    initialize.assert_not_called()


@pytest.mark.parametrize("option", ["-h", "--help"])
def test_top_level_help_remains_available_without_root(monkeypatch, option):
    monkeypatch.setattr(cpoutil.os, "geteuid", lambda: 1000)
    initialize = mock.Mock(side_effect=AssertionError("help accessed hardware"))
    monkeypatch.setattr(cpoutil, "initialize_platform", initialize)
    result = CliRunner().invoke(cpoutil.cli, [option])
    assert result.exit_code == 0
    assert "Root privileges are required" in result.output
    assert "Usage:" in result.output
    initialize.assert_not_called()


def test_root_reaches_platform_loading(monkeypatch):
    monkeypatch.setattr(cpoutil.os, "geteuid", lambda: 0)
    initialize = mock.Mock(side_effect=cpoutil.CpoCommandError("test topology unavailable"))
    monkeypatch.setattr(cpoutil, "initialize_platform", initialize)
    result = CliRunner().invoke(cpoutil.cli, ["show", "interface", "presence"])
    assert result.exit_code == 1
    assert "Error: test topology unavailable" in result.output
    assert "Root privileges are required" not in result.output
    initialize.assert_called_once_with()

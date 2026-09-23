"""Transceiver show/config wrappers with a real emulated SFP and mocked SONiC services."""

import pytest


pytestmark = pytest.mark.xcvr_emu


@pytest.mark.parametrize("command", ["eeprom", "info", "presence", "status"])
@pytest.mark.parametrize("through_show", [False, True], ids=["sfpshow", "show-interfaces-transceiver"])
def test_cached_transceiver_views(transceiver_commands, command, through_show):
    """Feed mocked STATE_DB from actual native decoding, then run the real display code."""
    commands = transceiver_commands
    env = commands.environment
    cli = commands.show if through_show else commands.sfpshow
    arguments = [command, "Ethernet0"] if through_show else [command, "-p", "Ethernet0"]
    output = cli.invoke(arguments)
    if command in ("eeprom", "info"):
        assert "Vendor Name: xcvr-emu" in output
        assert "Vendor PN: EMU-CMIS-400G" in output
    elif command == "presence":
        assert "Present" in output
        env.emulator.set_present(False)
        env.publish()
        assert "Not present" in cli.invoke(arguments)
    else:
        assert "Current module state: ModuleLowPwr" in output
        assert env.sfp.set_lpmode(False)
        env.publish()
        assert "Current module state: ModuleReady" in cli.invoke(arguments)


@pytest.mark.parametrize("through_show", [False, True], ids=["sfpshow", "show-interfaces-transceiver"])
def test_cached_dom_changes_follow_real_sensor_values(transceiver_commands, through_show):
    """Prove cached output changes when the emulated sensor bytes change."""
    commands = transceiver_commands
    env = commands.environment
    cli = commands.show if through_show else commands.sfpshow
    arguments = ["eeprom", "Ethernet0", "--dom"] if through_show else ["eeprom", "-p", "Ethernet0", "--dom"]
    output = cli.invoke(arguments)
    assert "25.0C" in output
    env.emulator.set_temperature(42.5)
    env.publish()
    assert "42.5C" in cli.invoke(arguments)


def test_show_lpmode_forwards_to_live_sfputil(transceiver_commands):
    """Exercise the show wrapper's real child command, not a mocked success result."""
    commands = transceiver_commands
    assert "On" in commands.show.invoke(["lpmode", "Ethernet0"])
    assert commands.environment.sfp.set_lpmode(False)
    assert "Off" in commands.show.invoke(["lpmode", "Ethernet0"])


@pytest.mark.parametrize("hardware", [False, True], ids=["state-db", "hardware"])
def test_show_error_status_sources(transceiver_commands, hardware):
    """Verify both cached and direct-hardware error-status routes."""
    commands = transceiver_commands
    arguments = ["error-status", "Ethernet0"]
    if hardware:
        arguments.append("--fetch-from-hardware")
    assert "OK" in commands.show.invoke(arguments)
    commands.environment.emulator.set_present(False)
    commands.environment.publish()
    assert "Unplugged" in commands.show.invoke(arguments)


def test_config_lpmode_and_reset_reach_the_emulated_module(transceiver_commands):
    """Follow config -> sfputil -> SfpOptoeBase -> gRPC -> CMIS state machine."""
    commands = transceiver_commands
    env = commands.environment
    assert "OK" in commands.config.invoke(["lpmode", "Ethernet0", "disable"])
    assert env.sfp.get_xcvr_api().get_module_state() == "ModuleReady"
    assert "OK" in commands.config.invoke(["lpmode", "Ethernet0", "enable"])
    assert env.sfp.get_xcvr_api().get_module_state() == "ModuleLowPwr"
    assert env.sfp.set_lpmode(False)
    assert "Resetting port Ethernet0 ... OK" in commands.config.invoke(["reset", "Ethernet0"])
    assert env.sfp.get_xcvr_api().get_module_state() == "ModuleLowPwr"


@pytest.mark.parametrize("action, value", [("enable", "enabled"), ("disable", "disabled")])
def test_config_dom_only_changes_the_mocked_poller_setting(transceiver_commands, action, value):
    """DOM polling is a CONFIG_DB policy, not an EEPROM control bit."""
    commands = transceiver_commands
    env = commands.environment
    env.emulator.accesses.clear()
    commands.config.invoke(["dom", "Ethernet0", action])
    assert env.databases.config["PORT|Ethernet0"]["dom_polling"] == value
    assert not any(access.write for access in env.emulator.accesses)


@pytest.mark.parametrize("through_show", [False, True], ids=["sfpshow", "show-interfaces-transceiver"])
def test_coherent_pm_is_not_fabricated(transceiver_commands, through_show):
    """A non-coherent CMIS model must not invent C-CMIS performance data."""
    commands = transceiver_commands
    assert not commands.environment.sfp.is_coherent_module()
    cli = commands.show if through_show else commands.sfpshow
    arguments = ["pm", "Ethernet0"] if through_show else ["pm", "-p", "Ethernet0"]
    assert "not applicable" in cli.invoke(arguments).lower()


def test_child_command_failures_are_forwarded(transceiver_commands, capsys):
    """Keep a real child CLI failure visible instead of converting it to success."""
    with pytest.raises(SystemExit) as error:
        transceiver_commands.run_command([
            "sudo", "sfputil", "read-eeprom", "-p", "Ethernet999", "-n", "0", "-o", "0", "-s", "1",
        ])
    assert error.value.code == 6
    assert "invalid port" in capsys.readouterr().out


@pytest.mark.parametrize("command", [[], ["unexpected-tool"]], ids=["empty", "unknown"])
def test_unexpected_external_commands_are_rejected(transceiver_commands, command):
    """Never launch an unrecognized system tool from an integration test."""
    with pytest.raises(AssertionError, match="Unexpected external command"):
        transceiver_commands.run_command(command)

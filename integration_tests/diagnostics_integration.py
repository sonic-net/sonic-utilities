"""CMIS diagnostic controls exercised through sfputil and real EEPROM APIs."""

import ast

import pytest

pytestmark = pytest.mark.xcvr_emu

LOOPBACK_REGISTERS = {
    "media-side-output": 180,
    "media-side-input": 181,
    "host-side-output": 182,
    "host-side-input": 183,
}


def loopback_states(output):
    """Parse the native per-lane host lists and aggregate media booleans."""
    return {
        line.strip().split(":", 1)[0]: ast.literal_eval(line.strip().split(":", 1)[1].strip())
        for line in output.splitlines() if "side-" in line
    }


@pytest.fixture
def diagnostics(sfputil_environment):
    """Advertise CMIS loopback capabilities in the emulator's actual memory."""
    env = sfputil_environment
    env.emulator.write_page(0x13, 128, b"\x7f")
    env.sfp.refresh_xcvr_api()
    assert env.sfp.get_xcvr_api().get_diag_page_support()
    return env


@pytest.mark.parametrize("mode, register", LOOPBACK_REGISTERS.items())
@pytest.mark.parametrize("subport, mask", [("0", 0x0f), ("2", 0xf0)])
def test_loopback_round_trip(diagnostics, mode, register, subport, mask):
    """Check all four loopback modes and breakout lane masks on the wire."""
    env = diagnostics
    env.databases.config["PORT|Ethernet0"]["subport"] = subport
    output = env.sfputil.invoke(["debug", "loopback", "Ethernet0", mode, "enable"])
    assert f"enable {mode} loopback" in output
    assert env.emulator.read_page(0x13, register, 1) == bytes([mask])
    status = env.sfputil.invoke(["debug", "loopback-status", "Ethernet0"])
    value = loopback_states(status)[mode]
    if mode.startswith("host"):
        assert value == [bool(mask & (1 << lane)) for lane in range(8)]
        assert all(isinstance(lane, bool) for lane in value)
    else:
        assert value is True
    env.sfputil.invoke(["debug", "loopback", "Ethernet0", mode, "disable"])
    assert env.emulator.read_page(0x13, register, 1) == b"\x00"
    value = loopback_states(env.sfputil.invoke(["debug", "loopback-status", "Ethernet0"]))[mode]
    if mode.startswith("host"):
        assert value == [False] * 8
    else:
        assert value is False


@pytest.mark.parametrize("selected_port", [[], ["Ethernet0"]], ids=["all-ports", "selected-port"])
def test_loopback_capability_and_status(diagnostics, selected_port):
    """Read capability and status registers rather than supplying canned dictionaries."""
    env = diagnostics
    capability = env.sfputil.invoke(["debug", "loopback-capability", *selected_port])
    for mode in ("host_side_input", "host_side_output", "media_side_input", "media_side_output"):
        assert f"{mode}_loopback_supported: True" in capability
    env.emulator.write_page(0x13, 183, b"\x05")
    status = env.sfputil.invoke(["debug", "loopback-status", *selected_port])
    assert loopback_states(status)["host-side-input"] == [
        True, False, True, False, False, False, False, False,
    ]


@pytest.mark.parametrize("module_config", [{"DiagnosticPagesSupported": 0}], indirect=True)
def test_unadvertised_diagnostics_are_rejected(sfputil_environment, module_config):
    """Reject a real module's lack of diagnostic support before any control write."""
    env = sfputil_environment
    env.emulator.accesses.clear()
    output = env.sfputil.invoke(["debug", "loopback", "Ethernet0", "host-side-input", "enable"], -1)
    assert "does not support diagnostic pages" in output
    assert not any(access.write for access in env.emulator.accesses)
    assert "does not support diagnostic pages" in env.sfputil.invoke(["debug", "loopback-capability", "Ethernet0"])


@pytest.mark.parametrize("direction, register", [("tx", 130), ("rx", 138)])
@pytest.mark.parametrize("subport, mask, untouched", [
    ("0", 0x0f, 0xa0), ("", 0x0f, 0xa0), ("2", 0xf0, 0x05),
])
def test_output_disable_preserves_unselected_lanes(sfputil_environment, direction, register, subport, mask, untouched):
    """Verify the native per-lane disable APIs against CMIS control registers."""
    env = sfputil_environment
    env.databases.config["PORT|Ethernet0"]["subport"] = subport
    env.emulator.write_page(0x10, register, bytes([untouched]))
    output = env.sfputil.invoke(["debug", f"{direction}-output", "Ethernet0", "disable"])
    assert f"{direction.upper()} output disabled" in output
    assert env.emulator.read_page(0x10, register, 1) == bytes([untouched | mask])


@pytest.mark.parametrize("direction, control_register, status_register", [("tx", 130, 133), ("rx", 138, 132)])
def test_output_enable_with_valid_initial_output(sfputil_environment, direction, control_register, status_register):
    """Check idempotent enable against a module whose outputs are already valid."""
    env = sfputil_environment
    assert env.sfp.set_lpmode(False)
    # The emulator stores OutputStatus, but does not derive it from OutputDisable.
    env.emulator.write_page(0x11, status_register, b"\x0f")
    output = env.sfputil.invoke(["debug", f"{direction}-output", "Ethernet0", "enable"])
    assert f"{direction.upper()} output enabled" in output
    assert env.emulator.read_page(0x10, control_register, 1)[0] & 0x0f == 0
    assert env.emulator.read_page(0x11, status_register, 1) == b"\x0f"


@pytest.mark.parametrize("direction, register", [("tx", 130), ("rx", 138)])
def test_output_enable_reports_inactive_hardware(sfputil_environment, direction, register):
    """Do not fake successful output-state propagation that xcvr-emu does not implement."""
    env = sfputil_environment
    env.emulator.write_page(0x10, register, b"\x0f")
    output = env.sfputil.invoke(["debug", f"{direction}-output", "Ethernet0", "enable"], -1)
    assert "still disabled" in output
    assert env.emulator.read_page(0x10, register, 1)[0] & 0x0f == 0


@pytest.mark.parametrize("arguments", [
    ["debug", "loopback", "Ethernet0", "host-side-input", "enable"],
    ["debug", "tx-output", "Ethernet0", "disable"],
    ["debug", "rx-output", "Ethernet0", "disable"],
])
def test_diagnostics_do_not_write_to_removed_modules(sfputil_environment, arguments):
    """Honor actual hot-unplug state before invoking the native control API."""
    env = sfputil_environment
    env.emulator.set_present(False)
    env.emulator.accesses.clear()
    assert "SFP EEPROM not detected" in env.sfputil.invoke(arguments, -1)
    assert not any(access.write for access in env.emulator.accesses)


def test_every_sfputil_leaf_has_a_coverage_decision(sfputil_environment):
    """Fail on new command surfaces until their live coverage or limitation is specified."""
    from click import Group

    exercised = {
        "show eeprom", "show eeprom-hexdump", "show presence", "show error-status",
        "show lpmode", "show fwversion", "lpmode show", "lpmode on", "lpmode off",
        "reset", "power enable", "power disable", "firmware show", "version",
        "read-eeprom", "write-eeprom", "debug loopback", "debug loopback-capability",
        "debug loopback-status", "debug tx-output", "debug rx-output",
    }
    unsupported = {
        "firmware run", "firmware commit", "firmware download", "firmware upgrade",
        "firmware unlock", "firmware target",
    }
    assert sfputil_environment.emulator.read_page(1, 163, 1)[0] & 0xc0 == 0

    def leaves(group, prefix=""):
        for name, command in group.commands.items():
            path = f"{prefix} {name}".strip()
            if isinstance(command, Group):
                yield from leaves(command, path)
            else:
                yield path

    assert set(leaves(sfputil_environment.sfputil.command)) == exercised | unsupported

"""CLI assertions backed by an independently running CMIS emulator."""

import pytest


pytestmark = pytest.mark.xcvr_emu


@pytest.mark.parametrize("module_config", [
    {"SFF8024Identifier": "QSFP_DD", "SFF8024IdentifierCopy": "QSFP_DD"},
    {"SFF8024Identifier": "OSFP", "SFF8024IdentifierCopy": "OSFP"},
], indirect=True, ids=["qsfp-dd", "osfp"])
def test_real_cmis_identity(sfputil_environment, module_config):
    """Decode identity with SONiC's parser rather than an EEPROM-info mock."""
    from sonic_platform_base.sonic_xcvr.api.public.cmis import CmisApi

    env = sfputil_environment
    assert isinstance(env.sfp.get_xcvr_api(), CmisApi)
    output = env.sfputil.invoke(["show", "eeprom", "-p", "Ethernet0"])
    assert "Ethernet0: SFP EEPROM detected" in output
    assert "Vendor Name: xcvr-emu" in output
    assert "Vendor PN: EMU-CMIS-400G" in output
    assert "Vendor SN: EMU000000000001" in output
    assert env.emulator.accesses


def test_lpmode_round_trip(sfputil_environment):
    """Observe real module-state transitions after CLI EEPROM writes."""
    env = sfputil_environment
    assert env.sfp.get_lpmode() is True
    assert "On" in env.sfputil.invoke(["show", "lpmode", "-p", "Ethernet0"])
    assert "OK" in env.sfputil.invoke(["lpmode", "off", "Ethernet0"])
    assert env.sfp.get_xcvr_api().get_module_state() == "ModuleReady"
    assert env.emulator.read_page(0, 26, 1)[0] & 0x10 == 0
    assert "Off" in env.sfputil.invoke(["lpmode", "show", "-p", "Ethernet0"])
    assert "OK" in env.sfputil.invoke(["lpmode", "on", "Ethernet0"])
    assert env.sfp.get_xcvr_api().get_module_state() == "ModuleLowPwr"
    assert env.emulator.read_page(0, 26, 1)[0] & 0x10


@pytest.mark.parametrize("page, offset, spelling", [
    (0, 120, "0"),
    (1, 128, "1"),
    (3, 250, "0o3"),
    (16, 240, "0x10"),
    (17, 240, "17"),
    (255, 252, "0xff"),
])
def test_raw_write_read_verified(sfputil_environment, page, offset, spelling):
    """Verify CLI writes through an independent page-addressed gRPC read."""
    env = sfputil_environment
    arguments = ["-p", "Ethernet0", "-n", spelling, "-o", str(offset)]
    env.sfputil.invoke(["write-eeprom", *arguments, "-d", "00a5ff42", "--verify"])
    assert env.emulator.read_page(page, offset, 4) == bytes.fromhex("00a5ff42")
    assert env.sfputil.invoke(["read-eeprom", *arguments, "-s", "4", "--no-format"]).strip() == "00a5ff42"


@pytest.mark.parametrize("temperature, voltage", [(25.5, 3.3), (-5.25, 3.2)])
def test_dom_decodes_live_sensor_and_threshold_bytes(sfputil_environment, temperature, voltage):
    """Check engineering units from independent CMIS sensor and threshold registers."""
    env = sfputil_environment
    env.emulator.set_temperature(temperature)
    env.emulator.set_voltage(voltage)
    assert env.emulator.read_page(0, 14, 2) == int(temperature * 256).to_bytes(2, "big", signed=True)
    assert env.emulator.read_page(0, 16, 2) == int(voltage * 10000).to_bytes(2, "big")
    env.emulator.write_page(2, 128, (80 * 256).to_bytes(2, "big", signed=True))
    readings = env.sfp.get_transceiver_dom_real_value()
    assert readings["temperature"] == pytest.approx(temperature)
    assert readings["voltage"] == pytest.approx(voltage)
    assert env.sfp.get_transceiver_threshold_info()["temphighalarm"] == 80
    output = env.sfputil.invoke(["show", "eeprom", "-p", "Ethernet0", "--dom"])
    assert f"{temperature}C" in output
    assert f"{voltage}Volts" in output
    assert "TempHighAlarm" in output
    assert "80.0C" in output


@pytest.mark.parametrize("arguments", [
    ["show", "eeprom-hexdump"],
    ["show", "eeprom-hexdump", "-p", "Ethernet0"],
    ["show", "eeprom-hexdump", "-p", "Ethernet0", "-n", "0x03"],
    ["show", "eeprom-hexdump", "-n", "0o3"],
])
def test_hexdump_uses_real_memory(sfputil_environment, arguments):
    """Exercise all-port, selected-port and explicit-page dumps."""
    env = sfputil_environment
    env.emulator.write_page(3, 128, b"EMU!")
    output = env.sfputil.invoke(arguments)
    assert "EEPROM hexdump for port Ethernet0" in output
    assert "Lower page 0h" in output
    assert "Upper page 0h" in output
    if "-n" in arguments:
        assert "Upper page 3h" in output
        assert "45 4d 55 21" in output
        assert "|EMU!" in output
    elif "-p" not in arguments:
        for page in ("1h", "2h", "10h", "11h"):
            assert f"Upper page {page}" in output


def test_formatted_raw_read(sfputil_environment):
    """Verify the formatted and unformatted raw-read paths use the same bytes."""
    env = sfputil_environment
    env.emulator.write_page(3, 128, b"EMU!")
    output = env.sfputil.invoke(["read-eeprom", "-p", "Ethernet0", "-n", "3", "-o", "128", "-s", "4"])
    assert "00000080" in output
    assert "45 4d 55 21" in output
    assert "|EMU!|" in output


def test_transport_splits_page_boundaries(sfputil_environment):
    """Check that the adapter cannot accidentally validate its own wrong mapping."""
    env = sfputil_environment
    assert env.sfp.write_eeprom(254, 4, b"\xaa\xbb\xcc\xdd")
    assert env.emulator.read_page(0, 254, 2) == b"\xaa\xbb"
    assert env.emulator.read_page(1, 128, 2) == b"\xcc\xdd"
    env.emulator.accesses.clear()
    assert env.sfp.read_eeprom(254, 4) == b"\xaa\xbb\xcc\xdd"
    assert [(access.page, access.offset, len(access.data)) for access in env.emulator.accesses] == [
        (0, 254, 2), (1, 128, 2),
    ]


@pytest.mark.parametrize("module_config", [{"MemoryModel": "FLAT", "DiagnosticPagesSupported": 0}], indirect=True)
def test_flat_memory_rejects_other_pages(sfputil_environment, module_config):
    """Respect a real flat-memory advertisement rather than a mocked is_flat_memory."""
    env = sfputil_environment
    assert env.sfp.get_xcvr_api().is_flat_memory()
    output = env.sfputil.invoke(["show", "eeprom-hexdump"])
    assert "Upper page 0h" in output
    assert "Upper page 1h" not in output
    env.emulator.accesses.clear()
    output = env.sfputil.invoke(["write-eeprom", "-p", "Ethernet0", "-n", "1", "-o", "128", "-d", "ff"], -1)
    assert "only page 0 is supported" in output
    assert not any(access.write for access in env.emulator.accesses)


@pytest.mark.parametrize("arguments, code, message", [
    (["read-eeprom", "-p", "Ethernet999", "-n", "0", "-o", "0", "-s", "1"], 6, "invalid port"),
    (["read-eeprom", "-p", "Ethernet0", "-n", "256", "-o", "128", "-s", "1"], 7, "Invalid page"),
    (["read-eeprom", "-p", "Ethernet0", "-n", "not-a-page", "-o", "0", "-s", "1"], 5, "numeric page"),
    (["read-eeprom", "-p", "Ethernet0", "-n", "1", "-o", "127", "-s", "1"], -1, "Invalid offset"),
    (["read-eeprom", "-p", "Ethernet0", "-n", "0", "-o", "255", "-s", "2"], -1, "Invalid size"),
    (["read-eeprom", "-p", "Ethernet0", "-n", "0", "-o", "0", "-s", "0"], 2, "not in the range"),
    (["write-eeprom", "-p", "Ethernet0", "-n", "3", "-o", "128", "-d", "f"], -1, "even length"),
    (["write-eeprom", "-p", "Ethernet0", "-n", "3", "-o", "255", "-d", "aabb"], -1, "Invalid size"),
    (["write-eeprom", "-p", "Ethernet0", "-n", "3", "-o", "128", "-d", "zz"], -1, "hex string"),
])
def test_invalid_requests_do_not_write(sfputil_environment, arguments, code, message):
    """Invalid CLI requests must not mutate the emulated EEPROM."""
    env = sfputil_environment
    env.emulator.accesses.clear()
    assert message in env.sfputil.invoke(arguments, code)
    assert not any(access.write for access in env.emulator.accesses)


def test_presence_hotplug_and_hardware_error_status(sfputil_environment):
    """Propagate real insertion/removal through both presence and hardware health CLIs."""
    env = sfputil_environment
    assert "Present" in env.sfputil.invoke(["show", "presence"])
    assert "OK" in env.sfputil.invoke(["show", "error-status", "-p", "Ethernet0", "-hw"])
    env.emulator.set_present(False)
    assert "Not present" in env.sfputil.invoke(["show", "presence", "-p", "Ethernet0"])
    assert "Unplugged" in env.sfputil.invoke(["show", "error-status", "-hw"])
    assert "not detected" in env.sfputil.invoke(["show", "eeprom"])
    assert "Not Present" in env.sfputil.invoke(["show", "lpmode"])
    env.emulator.set_present(True)
    assert "Present" in env.sfputil.invoke(["show", "presence"])
    assert "Vendor PN: EMU-CMIS-400G" in env.sfputil.invoke(["show", "eeprom"])


@pytest.mark.parametrize("arguments, code, message", [
    (["read-eeprom", "-p", "Ethernet0", "-n", "0", "-o", "0", "-s", "1"], -1, "not detected"),
    (["write-eeprom", "-p", "Ethernet0", "-n", "3", "-o", "128", "-d", "aa"], -1, "not detected"),
    (["show", "eeprom-hexdump", "-p", "Ethernet0"], 5, "not detected"),
    (["lpmode", "on", "Ethernet0"], 0, "not present, skipping"),
    (["lpmode", "off", "Ethernet0"], 0, "not present, skipping"),
    (["reset", "Ethernet0"], 0, "not present, skipping"),
])
def test_removed_module_cannot_be_written(sfputil_environment, arguments, code, message):
    """Check the CLI's actual absent-module behavior and lack of writes."""
    env = sfputil_environment
    env.emulator.set_present(False)
    env.emulator.accesses.clear()
    assert message in env.sfputil.invoke(arguments, code)
    assert not any(access.write for access in env.emulator.accesses)


def test_reset_restarts_the_real_cmis_state_machine(sfputil_environment):
    """Drive the reset CLI through the board adapter into CMIS software reset."""
    env = sfputil_environment
    assert env.sfp.set_lpmode(False)
    assert env.sfp.get_xcvr_api().get_module_state() == "ModuleReady"
    env.emulator.accesses.clear()
    assert "Resetting port Ethernet0 ... OK" in env.sfputil.invoke(["reset", "Ethernet0"])
    assert env.sfp.get_xcvr_api().get_module_state() == "ModuleLowPwr"
    assert any(access.write and access.page == 0 and access.offset == 26 and access.data[0] & 0x08
               for access in env.emulator.accesses)


@pytest.mark.parametrize("arguments", [
    ["show", "lpmode", "--use-lpmode-pin"],
    ["lpmode", "on", "Ethernet0", "--use-lpmode-pin"],
    ["lpmode", "off", "Ethernet0", "--use-lpmode-pin"],
    ["power", "enable", "Ethernet0"],
    ["power", "disable", "Ethernet0"],
])
def test_unemulated_board_gpio_is_not_faked(sfputil_environment, arguments):
    """Do not claim successful GPIO/power-rail emulation for an EEPROM-only backend."""
    assert "not implemented" in sfputil_environment.sfputil.invoke(arguments, 5)


@pytest.mark.parametrize("arguments", [
    ["show", "fwversion", "Ethernet0"],
    ["firmware", "show", "Ethernet0"],
])
def test_firmware_queries_report_real_cdb_capability(sfputil_environment, arguments):
    """Exercise firmware-info aliases without fabricating a CDB firmware engine."""
    env = sfputil_environment
    assert env.emulator.read_page(1, 163, 1)[0] & 0xc0 == 0
    assert "CDB Not supported" in env.sfputil.invoke(arguments)


def test_version_with_real_platform_initialization(sfputil_environment):
    """Keep the initialization-dependent version command runnable with the adapter."""
    assert "sfputil version" in sfputil_environment.sfputil.invoke(["version"])

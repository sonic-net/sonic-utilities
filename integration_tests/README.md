# Transceiver integration tests

These tests run [xcvr-emu](https://github.com/az-pz/xcvr-emu) as a normal child
process. Pytest starts
`python -m xcvr_emu.xcvr_emud` with a temporary configuration and an ephemeral
port, waits for the real gRPC service, and stops and reaps that exact child
after every test. No external emulator setup or physical transceiver is required.

## Test setup

The fixtures in [conftest.py](conftest.py) only compose the following objects:

| Object | Responsibility |
| --- | --- |
| [EmulatorProcess](xcvr_emulator.py) | Load the custom profile, start a child, wait for gRPC readiness, and close/reap it even when startup or a test fails |
| [Emulator](xcvr_emulator.py) | Read/write real gRPC EEPROM bytes, track transactions, and control insertion state |
| [EmulatedSfp](xcvr_emulator.py) | Adapt that transport to SONiC's native transceiver APIs |
| [SonicEnvironment](sonic_environment.py) | Wire sfputil to a mock chassis, port mappings, and in-memory databases; publish decoded values as xcvrd would |
| [CliCommand](sonic_environment.py) | Bind a real Click command to its context and assert the expected exit code |
| [TransceiverCommands](sonic_environment.py) | Bind the show/config wrappers and forward child commands, including their output and failures |

[config.yaml](config.yaml) is the complete test-owned profile. Tests do **not**
load xcvr-emu's packaged example. It describes one bank-zero, paged CMIS 5.2
QSFP-DD module with a 400G application, diagnostic and DOM capabilities, and
identity. `SonicEnvironment` initializes temperature/voltage to 25 C and 3.3 V
using `Emulator.set_temperature()` and `set_voltage()`. These write both bytes
through gRPC: the pinned emulator's YAML monitor fields expose only the high
byte of each register and cannot represent the full values.

Each test loads a fresh copy and the process receives its own temporary YAML.
Tests can override `defaults` using an indirect fixture parameter, for example:

```python
@pytest.mark.parametrize("module_config", [{"MemoryModel": "FLAT"}], indirect=True)
def test_flat_module(sfputil_environment, module_config):
    env = sfputil_environment
    assert env.sfp.get_xcvr_api().is_flat_memory()
    output = env.sfputil.invoke(["show", "eeprom", "-p", "Ethernet0"])
    assert "Vendor Name: xcvr-emu" in output
```

Nested overrides are copied too. The checked-in profile and other tests'
configurations remain untouched. Wrapper tests use the same invocation style,
such as `commands.show.invoke(["lpmode", "Ethernet0"])` or
`commands.config.invoke(["lpmode", "Ethernet0", "enable"])`; the command objects
own their Click contexts so tests do not have to construct anonymous namespaces.

## Run the tests

The repository's [pytest configuration](../pytest.ini) discovers `*_integration.py`
alongside the unit tests. The existing [Azure pipeline](../azure-pipelines.yml)
already installs the [testing extra](../setup.py) and runs both suites:

```bash
pip3 install ".[testing]"
pip3 uninstall --yes sonic-utilities
pytest
```

No pipeline changes or separate dependency installation are needed. Both suites
contribute to the same JUnit and coverage reports. Use `pytest -m xcvr_emu` to
select integration tests or `pytest -m "not xcvr_emu"` to exclude them. Missing
dependencies and daemon startup failures are errors, not skipped tests.

## What is real and what is mocked

The hardware boundary is an `SfpOptoeBase` subclass whose EEPROM reads/writes go
through gRPC. SONiC's actual `XcvrApiFactory`, `CmisApi`, memory maps, decoding,
and control implementations run unchanged. Assertions check independently
addressed emulator registers, decoded values, module states, and CLI output.

Platform discovery, port mappings, privilege checks, CONFIG_DB/STATE_DB/APPL_DB,
and external-command launching are mocked. The show/config wrappers dispatch
to the real child Click commands rather than returning mocked command output.
A small publisher stands in for xcvrd and populates mocked STATE_DB from live
native API readings; Redis and xcvrd are not started.

Each test gets a fresh process and a single physical CMIS module. This also
avoids the emulator's shared-memory behavior between modules in one process.
Breakout metadata is supplied by the mocked port configuration. The adapter
uses CMIS bank zero, which is the address space exposed by these CLI commands.
The integration fixtures temporarily isolate native platform imports and remove
unit-test environment flags, restoring both afterward. This also works when a
single pytest/xdist worker runs both suites.

## Command coverage

| Surface | Checks |
| --- | --- |
| `sfputil show eeprom`, with and without DOM | QSFP-DD/OSFP identity; live temperature, voltage and thresholds |
| `sfputil show eeprom-hexdump`, `read-eeprom`, `write-eeprom` | Selected/all ports, page formats, flat/paged memory, raw/formatted output, read-back verification, page boundaries and invalid inputs |
| `sfputil show presence`, `show error-status` | Real insertion/removal, hardware and cached health paths |
| `sfputil show lpmode`, `lpmode show/on/off` | Real low-power state transitions and register writes |
| `sfputil reset` | Platform reset mapped to the emulator's CMIS software-reset operation |
| `sfputil debug loopback`, `loopback-capability`, `loopback-status` | All four loopback modes; breakout masks; per-lane host lists and aggregate media status |
| `sfputil debug tx-output/rx-output` | Disable masks and untouched lanes, idempotent enable, inactive-output error handling |
| `show interfaces transceiver`, `sfpshow` | EEPROM/info/DOM/presence/status views derived from real decoding; lpmode and error-status forwarding; non-coherent PM rejection |
| `config interface transceiver lpmode/reset/dom` | Forwarding into live sfputil; DOM polling changes only the mocked database policy |
| Lifecycle | Actual child PID, graceful teardown, assertion/startup failures, process reaping, fresh-memory isolation and transport failures |

The command-inventory test fails if a new sfputil leaf is added without a
coverage decision.

## Deliberate limitations

- xcvr-emu models **CMIS**, not SFF-8472/SFF-8636 modules, C-CMIS coherent optics,
  vendor-specific mux/Y-cables, or physical optical traffic.
- There is no CDB firmware execution engine. Firmware-info aliases verify the
  module's unsupported advertisement; firmware run/commit/download/upgrade/
  unlock/target operations are not presented as supported integration cases.
- Board power rails and LPMode GPIO pins are not emulated. Their explicit
  not-implemented responses are tested, without faking successful GPIO control.
- Reset uses the CMIS software-reset equivalent of a board reset. The adapter
  clears the request bit because this emulator does not self-clear it.
- The emulator stores OutputStatus registers but does not derive them from
  OutputDisable. Enable success is tested with valid **initial** output status;
  inactive-output failures are also tested. No post-command state propagation
  is fabricated.
- Coherent frequency/TX-power configuration and coherent PM need a C-CMIS model
  and the relevant SONiC daemons; they are outside this emulator-backed scope.

## Pinned dependencies

[setup.py](../setup.py) declares the emulator in the `testing` extra (also shared
by `tests_require`), pinned to the SONiC-compatible fork commit
`3aca04f89de6dfecf33bea29509234164d917a81`. This installs its compatible gRPC and
protobuf dependencies together with the pytest plugins.

Both Docker and Azure tests use the `sonic-platform-common` SDK installed from
the latest SONiC build artifacts.

The adapter follows the production-API transport pattern used by the
[sonic-platform-common emulator tests](https://github.com/az-pz/sonic-platform-common/tree/5c9096070f6cd8c5e16f74a9a16c362cb0a4f74d/tests/sonic_xcvr/integration).

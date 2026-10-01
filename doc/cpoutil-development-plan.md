# cpoutil development and validation

## Current implementation

The common `cpoutil` command lives in sonic-utilities. It obtains the chassis
through `utilities_common.platform_sfputil_helper.load_chassis()` and resolves
physical ports through `Chassis.get_cpo()`. Platforms can return a public
`CpoBase` with separate OE/ELS endpoints or a supported legacy combined object.
The Micas adapter exposes its existing CPO objects through this interface.

Topology comes from `sonic_py_common.device_info.get_cpo_data()`. Active PORT
configuration and logical-to-physical mapping use the shared sfputil helper.
Common physical-port names, DOM formatting, and hex dumps are shared with
sfputil through `utilities_common.sfp_helper`; CPO topology resolution remains
in `cpoutil.mapping` and `cpoutil.main`.

Platform initialization runs only when an actual hardware command executes.
All command and group `-h`/`--help` paths work without loading the chassis,
ConfigDB, or CPO topology. The default `cpoutil read-eeprom` operation still
initializes the platform before dumping EEPROMs. Operations on a non-CPO
platform fail clearly when topology is unavailable.

## Topology and control boundaries

- Resolve active logical ports and breakout children through physical port
  indexes and ASIC lanes in the topology.
- Use explicit `laser_to_asic_lane_mapping` for breakout laser ownership. Do not
  infer equal contiguous lane groups. Legacy topology without this information
  cannot resolve every breakout command.
- Reject interface Tx-disable when selected lasers are shared with another
  interface, or when the required independent ELS control is unavailable.
- Apply OE-wide Tx-disable to every mapped bank. A single CMIS API object is
  bank-bound, so one call does not establish that every OE bank was changed.
- Treat EEPROM command banks as OE-local and validate the requested range.
  Translate topology-wide bank IDs through the API-reported bank count.
- Keep OE and ELS controls separate. An unsupported ELS operation must not
  accidentally call the combined object's inherited OE control method.

## Platform API capabilities

The public optional ELS contract is provided by platform-common's
`ElsfpApiBase`. Platforms implement supported operations; remaining methods
raise `NotImplementedError`, which cpoutil reports as a command failure.
The placeholder contract does not implement missing hardware behavior.

The current Bailly adapter has the following boundaries:

| Operation | Behavior |
| --- | --- |
| OE state, low-power read/control, temperature, input power, reset, and Tx-disable | Uses the existing CMIS API. |
| ELS presence, low-power read, temperature, and output power | Uses the supported ELS/RLM read APIs. |
| Independent ELS module state and per-laser state | Unsupported placeholders; the corresponding show commands report an error. |
| ELS low-power control, reset, and Tx-disable | Unsupported placeholders. |
| Interface Tx-disable | Requires complete laser ownership and independent ELS control support before writes. |
| OE/ELS/interface raw EEPROM access | Uses the resource's EEPROM access and bank/base-page mapping APIs; availability depends on the platform. |

In particular, `show els lpmode` support does not imply that
`config els lpmode` is supported. `get_elsfp_status()` monitor fields are not a
substitute for an independent ELS module-state API.

## OE reset semantics

`cpoutil config oe reset <index>` calls the selected OE platform API's `reset()`.
The existing CMIS implementation resets module settings to defaults and can
return success in either `ModuleReady` or `ModuleLowPwr`.

A successful reset does not establish that previous application selections,
datapath configuration, or links have recovered. On the tested Bailly device,
reset changed application selection and left datapaths deactivated. Affected
ports may require application and datapath reprovisioning after the reset.
The CLI reports this after a successful reset; it does not restore those settings
or change the platform API's reset contract. A false return or an unsupported
reset is still reported as a failure.

## EEPROM and output behavior

- Show commands provide human-readable output and JSON through `--json`.
- Bare `read-eeprom` dumps all mapped OE and ELS EEPROMs.
- Resource reads without an index iterate over resources of that type.
- Omitting page/offset/size selects the default full-page dump; explicit ranges
  support targeted reads and are checked before access.
- Hex dumps use the common 16-byte-row and ASCII formatter.
- Raw writes validate their target, page, offset, and payload. Successful
  dispatch in unit tests is not evidence that every hardware write was exercised.

## Validation requirements

- Enumerate all help paths with both help flags while platform initialization
  is forbidden. Check that actual commands, including the default EEPROM dump,
  initialize once and reject missing topology.
- Exercise successful, failed, and unsupported reset responses without assuming
  that application selection survives reset.
- Test utilities against both unmodified upstream platform-common and the
  companion ELS API changes. Utilities test doubles must not import an API class
  that exists only in an unmerged companion PR.
- Test the real ELS base/Bailly inheritance and optional-method contracts in
  platform-common's own suite.
- Cover shared sfputil formatting/port helpers, explicit laser mapping, bank
  selection, unsupported operations, and preflight rejection before writes.
- Run the repository's configured pre-commit hook and lint the full PR diff.

Hardware evidence must distinguish successful reads and controls, unsupported
operations, missing-module/invalid-input guards, and help-only coverage. Record
before/after state and reset effects. Focused unit tests and CLI checks do not
establish full CI, forwarding, firmware-update, or reboot-persistence coverage.

## Separate platform integration work

The Micas platform package currently provides its own executable and Python
module named `cpoutil`. Coexistence with the common utility requires a separate
packaging change; this utilities PR does not rename vendor files or claim that
such a migration is complete.

Current master also requires the platform's chassis construction hook to be
implemented. That adapter belongs in the buildimage platform package. Accurate
breakout laser mappings must come from verified hardware topology; the common
CLI retains its safety checks when those mappings are unavailable.

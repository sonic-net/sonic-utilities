# cpoutil development plan

The functional source of truth is CPO-cpoutil-CLI-HLD.md.
The implementation follows the current master platform interface and platform
driver path. On the target platform this path is `Chassis.get_sfp()` ->
`CPO(CpoOptoeBase)` -> `BaillyApi`.

The existing sfputil source is not modified. cpoutil follows its initialization
and port-resolution style and calls the existing SFP/CPO object APIs directly.

## Version 0

Version 0 established the CLI and topology foundation:

- Added the `cpoutil` Python package and console entry point.
- Parsed and validated the current `cpo.json` `oes`, `elss`, and `interfaces`
  model returned by `get_cpo_json_data()`.
- Implemented `cpoutil show interface map [PORT]`.
- Added human-readable table and JSON output.
- Kept `mapping.py` limited to topology parsing and validation.

## Version 0.1

Version 0.1 establishes sfputil-style platform access:

- Maintain process-wide `platform_chassis` and `platform_sfputil` objects.
- Load logical-to-physical mappings through `SfpUtilHelper`.
- Convert a logical port, including a breakout port, through
  `logical_port_name_to_physical_port_list()`.
- Build one global `oe`/`els`/`port` to SFP object table.
- Use the first associated CPO SFP object as the representative object for a
  shared OE or ELS.
- Validate CPO objects against `CpoOptoeBase`.

## Version 0.2

Version 0.2 provides the first read-only commands through existing PI/PD APIs:

- OE `lpmode`, `status`, `temperature`, and `input-power`.
- ELS `presence`, `lpmode`, `status`, `temperature`, and `output-power` through
  the existing Bailly RLM methods.
- Interface `dom`, `tx-disable`, `speed`, and `lane-status`.
- Interface commands obtain each SFP object from the physical port list and
  call SFP or `get_xcvr_api()` methods directly.
- The CLI contains no resource manager, `query_*` layer, or CPO-specific public
  API added solely for command output.

## Version 0.2.1

Version 0.2.1 aligns the implementation with the current master platform:

- Replaced `Chassis.get_cpo()` and `.oe`/`.elsfp` lookup with
  `Chassis.get_sfp()`.
- Replaced the community draft `devices/associated_devices` parser with the
  current platform `oes/elss/interfaces` schema.
- Removed `CpoCmisApi.get_per_lane_speed()`; the speed command calls the
  existing CMIS application APIs directly.
- Added tests for global object mapping, breakout port conversion, direct
  SFP/CMIS/Bailly calls, and invalid resources.

## Version 0.2.2

Version 0.2.2 added low-level read access through existing SFP objects:

- Added OE and ELS raw EEPROM reads.
- Used CMIS bank/page/offset translation from sonic-platform-common.
- Applied the platform ELS base-page mapping before reading.

## Version 0.2.3

Version 0.2.3 made read operations consistent with show commands:

- Made the OE/ELS index optional for reads.
- Reads without `-i` iterate over every mapped resource of that type.
- Kept indexed reads for targeted diagnostics.

## Version 0.2.4

Version 0.2.4 completes the implementable HLD control and EEPROM commands:

- Added interface, OE, and ELS control command groups.
- Added OE low-power, reset, and Tx-disable through the existing SFP API.
- Added ELS low-power and Tx-disable through new Bailly PI/PD API methods.
- Added OE, ELS, and interface raw EEPROM writes through `Sfp.write_eeprom()`.
- Added interface EEPROM read/write target resolution from the CPO mapping.
- Kept ELS reset as an explicit unsupported result because the current topology,
  `CpoOptoeBase`, and Bailly memory map expose no ELS reset signal or register.

## Version 0.2.5

Version 0.2.5 adds active breakout/subport resolution owned by cpoutil:

- Loads the current PORT configuration through `portconfig.get_port_config()`.
- Implements cpoutil-local subport, first-subport, lane, parent-interface, and
  lane-mask helpers without importing sfputil utility helper functions.
- Resolves dynamic logical subports back to the static parent in `cpo.json` by
  physical port index.
- Filters interface Tx-disable, speed, and lane-status output to the subport's
  OE lanes.
- Uses `Sfp.tx_disable_channel()` with the subport OE lane mask.
- Selects the ELS lasers belonging to the subport from the ordered CPO lane and
  laser mapping.
- Rejects interface Tx-disable when an ELS laser is shared with another subport,
  preventing an operation on one child port from disabling its sibling.

## Version 0.2.6

Version 0.2.6 aligns raw EEPROM reads with sfputil dump behavior:

- Makes bare `read-eeprom` dump all mapped OE and ELS EEPROMs.
- Makes `read-eeprom oe/els` dump all resources when `--index` is omitted.
- Dumps the complete default OE or ELS page set when page/offset/size are omitted.
- Preserves explicit bank/page/offset/size reads for targeted diagnostics.
- Uses sfputil-style page headings, 16-byte rows, and ASCII columns.
- Dumps OE non-banked CMIS pages once and pages 10h/11h for every mapped bank.
- Converts topology-wide OE bank IDs to OE-local CMIS banks using the existing API-reported bank count.
- Continues across unreadable resources during an all-resource dump.

## Version 0.3

Version 0.3 separates the public command from the existing platform implementation
and validates the transition on a W6940 CPO device:

- Rename the platform-specific command from `/usr/local/bin/cpoutil` to
  `/usr/local/bin/platformcpoutil` in both the normal and pure-PD W6940 platform
  packages.
- Rename the platform-specific Python module from `cpoutil.py` to `platformcpoutil.py` and
  update every platform consumer, including the legacy CLI, CPO daemon, voltage
  setting utility, and `platform_e2.py`.
- Install the sonic-utilities command as `/usr/local/bin/cpoutil` and retain the
  platform implementation only as `/usr/local/bin/platformcpoutil`.
- Add Bailly ELS low-power and Tx-disable control APIs to the common PI/PD path.
- Migrate one W6940 device with a rollback backup at
  `/home/admin/cpoutil-migration-backup-v0.3`.
- Verify all 14 public `show` commands, the 8-OE/16-ELS full EEPROM dump, the
  public and legacy imports, and representative legacy read-only commands.
- Keep `config els reset` explicitly unsupported: the platform exposes no
  per-ELS reset signal, and using the shared module reset would reset OE0 and
  every ELS associated with it.

## Version 0.3.1

Version 0.3.1 aligns human-readable output with sfputil conventions:

- Render show results as `tabulate(..., tablefmt="simple")` tables while
  preserving structured JSON output.
- Render boolean operating states as `On`/`Off` or
  `Present`/`Not present` instead of Python boolean literals.
- Render control operations with sfputil-style progress and `OK`/`Failed`
  completion text.
- Limit `show interface map` to the interface's OE and ELS relationship.
- Display an OE bank as an OE-local value such as `OE2 bank1`. The current
  `cpo.json` has topology-wide `oe_bank_id` values but no separate global-ID
  field, so the CLI does not label any value as a global ID.
- Display ELS resources as `ELS<n>` without a bank because the current
  topology contains no `els_bank_id`.

## Version 0.3.2

Version 0.3.2 aligns detailed CPO status output with sfputil:

- Format `show interface dom` as sfputil-style EEPROM and DOM sections instead
  of a flattened raw-key table.
- Translate transceiver fields to the same user-facing labels used by sfputil,
  format application advertisements, and append the correct DOM units.
- Group channel monitors, channel thresholds, module monitors, module
  thresholds, ELS monitors, and ELS thresholds in a stable natural order.
- Give interface speed and lane-status commands explicit lane-oriented columns.
- Give OE/ELS power and temperature output explicit channel/laser columns and
  units.
- Keep all formatting code inside cpoutil; sfputil source and helper functions
  remain unchanged and are not imported.

## Version 0.3.3

Version 0.3.3 completes the device-side sfputil output alignment:

- Normalize ELS low-power state to sfputil-style `On`/`Off` values.
- Use human-readable ELS status field names and consistent capitalization.
- Treat every OE EEPROM bank as OE-local. For example, Ethernet136 is shown
  as `OE2 bank1` instead of exposing topology-wide `oe_bank_id` 17.
- Reject out-of-range OE-local banks instead of silently applying modulo
  translation.
- Do not display or accept non-zero ELS banks because the current `cpo.json`
  defines no ELS bank identifier.
- Format EEPROM write progress as an sfputil-style action followed by
  `OK`/`Failed`.
- Preserve the detailed DOM, lane, speed, power, temperature, map, and EEPROM
  formatting introduced in 0.3.1 and 0.3.2.

## Next plan

Version 0.4 will complete package and image validation:

- Build the sonic-utilities wheel, sonic-platform-common wheel, and renamed
  W6940 platform package from the same source revision.
- Inspect the artifacts to confirm that only sonic-utilities owns `cpoutil`,
  while the platform package owns `platformcpoutil` and no longer contains
  `cpoutil.py` or a `cpoutil` executable.
- Install the packages through the normal package manager and confirm upgrade
  and rollback behavior without leaving shadowed Python modules or scripts.
- Run control, EEPROM write, negative, breakout, and concurrency tests on the
  packaged installation.
- Define a portable ELS reset API only after a platform reset signal/register is
  available; then connect `cpoutil config els reset` to that API.

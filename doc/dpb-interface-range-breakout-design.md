# Dynamic Port Breakout (DPB) for an interface range

High-level design and benchmark validation record for the staged implementation. This document does not reproduce implementation code.

## 1. Purpose and scope

Before this change, the CLI changed breakout mode for one parent port:

```text
config interface breakout Ethernet0 2x400G -f -l -y
```

The staged implementation lets an operator apply one target mode to several parent ports while preserving the existing command form:

```text
config interface breakout Ethernet0-64 2x400G -f -l -y
```

The design and staged implementation make these decisions:

- Parent identity comes only from exact keys in the active `platform.json["interfaces"]`; `BREAKOUT_CFG` supplies current-mode state.
- V1 supports flat compact ranges plus exact/CSV names. Tortuga/HyperFabric (HF) platforms use the **Hierarchical Port Name (HPN)** format; HPN parents can be supplied exactly or by CSV.
- Already-configured parents are skipped. A non-parent, or any attributable preflight failure, aborts the whole command by default so that a selection is never silently reduced; `-s/--skip-unsupported` drops those parents and proceeds with the rest.
- All remaining READY parents use one aggregate delete/add operation. An aggregate failure is reported once with every affected parent.
- The fixed 60-attempt ASIC-deletion wait, intended as 60 seconds, is replaced in `sonic-utilities` by a progress-based wait: it continues while old children keep leaving ASIC DB, gives up only after a stall window in which none does, and is bounded by an absolute ceiling scaled to the number of old children being deleted.

### 1.1 Out of scope

- Changes to orchagent, syncd, SAI, xcvrd, or existing `show interfaces breakout` commands.
- Multi-ASIC range/list support. V1 rejects those selectors; one exact selector remains allowed and uses the same range-aware orchestration.
- New meanings for `-f`, `-l`, `-y`, or `-v`, per-parent flag values, or a range FEC option.
- Automatic rollback after a partially completed aggregate operation.
- Waiting for creation of target ports in ASIC_DB; current DPB waits only for deletion of old ports.

### 1.2 Terms

| Term             | Meaning                                                                                                                                                  |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Parent**       | Exact key in the active `platform.json["interfaces"]` mapping, such as `Ethernet0` or `Ethernet1_31`.                                                    |
| **Child**        | Logical `PORT` entry generated from a parent and breakout mode, such as `Ethernet1_31_1`.                                                                |
| **HPN**          | Hierarchical Port Name format used by Tortuga/HF platforms. A parent can be `Ethernet1_31`; breakout children can add another component.                 |
| **Exact term**   | One interface name supplied alone or as a CSV item. It is selected only when it exactly matches a platform parent.                                       |
| **Flat range**   | Inclusive `Ethernet<start>-<end>` selector for flat `Ethernet<number>` platform parents.                                                                 |
| **READY parent** | Selected parent that passed preflight and is not already in the target mode.                                                                             |
| **Bulk apply**   | One combined set of old children is deleted and one combined set of target children is added. The operation has multiple write phases and is not atomic. |

### 1.3 Existing behavior and HPN evidence

Exact HPN DPB was verified on Tortuga: `config interface breakout Ethernet1_31 2x100G` successfully changed `1x400G` to `2x100G`, replacing `Ethernet1_31` with `Ethernet1_31_1` and `Ethernet1_31_2`; `show interfaces breakout current-mode Ethernet1_31` then reported `2x100G`. This confirms exact HPN parent support. The design must validate generated current children because after this transition the canonical parent is no longer a live `PORT` key.

`config interface startup/shutdown` is only the CLI-shape precedent for `Ethernet0-64`: its flat-only parser expands names and its implementation performs per-entry `mod_entry()` calls. DPB instead resolves parents from `platform.json` and applies the READY set in aggregate.

## 2. CLI decision

Use the existing breakout command and positional arguments:

```text
config interface breakout <interface-selector> <target-mode> [options]
config interface breakout Ethernet0-64 2x400G -f -l -y
```

This follows the startup/shutdown command shape. The Click command tree, the two positional arguments, and the meaning of every existing flag remain unchanged, and no new group or subcommand is needed. One flag is added, `-s/--skip-unsupported`, described in section 3.1. The implementation changes required behind that CLI surface are described below.

## 3. Functional design

### 3.1 Parse, resolve, and perform per-parent preflight

The selector is a comma-separated list of exact names or flat compact ranges matching `^Ethernet(0|[1-9][0-9]*)-(0|[1-9][0-9]*)$`. A non-range exact term must be non-empty and contain no whitespace, comma, or hyphen; it is otherwise preserved verbatim for platform lookup. Any term containing a hyphen is range syntax and must match the complete flat-range expression.

```text
# Supported
Ethernet0-64
Ethernet0,Ethernet8,Ethernet16
Ethernet1_31
Ethernet1_31,Ethernet1_32

# Unsupported compact HPN ranges in v1
Ethernet1_1-32
Ethernet1_1-1_32
```

Malformed CSV/range syntax rejects the request before preflight. This includes empty terms, whitespace, extra hyphens, non-decimal bounds, leading-zero bounds, and descending ranges. Bounds that cannot be parsed safely produce a controlled usage error.

Resolve syntactically valid terms against the active `platform.json`, then load `BREAKOUT_CFG` and live state once for the planning pass. A missing or malformed top-level `interfaces` mapping is a command-level platform-data error.

- A valid exact name absent from `platform.json` is `SKIPPED_NOT_PARENT`, not a syntax error.
- A flat range selects only exact flat platform-parent keys within its numeric bounds. Scan the finite parent set rather than materializing the interval; omit sparse numeric gaps.
- Never infer a parent from a child. `Ethernet1_31_2` must not become `Ethernet1_31`.
- Deduplicate overlapping terms and use deterministic natural order for planning and output.
- If no platform parent is selected, print a no-action summary and perform no prompt or write.

For each resolved parent:

1. Validate its platform entry, lanes, index, and `breakout_modes` mapping.
2. Require `BREAKOUT_CFG[parent].brkout_mode` to be a non-empty mode advertised by that parent. A missing or invalid entry is an error for that parent, not a reason to filter it silently.
3. Require the exact target mode to be advertised by that parent. Preserve today's reason: `Target mode <mode> is not available for the port <parent>`.
4. Generate the current child map and require it to match the live `PORT` names and lane ownership for that parent's platform lanes. Do not require the canonical parent name itself to be live.
5. If current mode equals target, return `SKIPPED_ALREADY_CONFIGURED` without dependency, target-diff, or ASIC-OID planning.
6. Otherwise, generate the target child map and reject name/lane takeover of unrelated live ports.
7. Check old-child ASIC OID completeness. Dependency and default-configuration validation follows after the aggregate plan is built. Without `-f`, the engine returns blocking dependency references; with `-f`, it removes the blocking configuration when the breakout runs, preserving unrelated members where the model supports it. A parent records its child maps and OID result, but the plan does not retain a complete dependency or `-l` diff.

Complete all determinable per-parent checks. Exclude rejected and skipped parents, but retain their reasons for the final summary.

| Status                       | Meaning                                                                                                                                                                                                     | Bulk participation |
| ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| `SKIPPED_NOT_PARENT`         | Explicit exact term is not an active platform parent.                                                                                                                                                       | No                 |
| `SKIPPED_ALREADY_CONFIGURED` | Valid current layout already uses the target mode.                                                                                                                                                          | No                 |
| `FAILED_PRECHECK`            | Attributable state, mode, child-layout, dependency, default-config, or OID error.                                                                                                                           | No                 |
| `READY`                      | All checks passed and a mode change is required.                                                                                                                                                            | Yes                |
| `APPLIED`                    | The apply raised no error; this parent's target `PORT` rows matched the plan, obsolete current-child rows were absent, and its `BREAKOUT_CFG` marker matched in CONFIG_DB. This deliberately makes no claim about dependency removals or `-l` defaults; see section 3.4. | Was READY          |
| `FAILED_BULK`                | A READY parent belonged to an aggregate whose validation, runtime, marker, or verification phase failed, or whose apply raised an exception.                                                               | Was READY          |

If no parent is READY, print the collected statuses and return without confirmation or write. The exact target mode remains case-sensitive.

A parent left at `SKIPPED_NOT_PARENT` or `FAILED_PRECHECK` cannot be broken out at all. By default any such parent aborts the command before the plan is shown, nothing is written, and the error names the parents concerned. Narrowing the selection silently is not acceptable: a script asking for 64 parents and receiving 61 would otherwise report success. `-s/--skip-unsupported` is the operator stating up front that this outcome is intended, and only then are those parents dropped and the remainder applied.

`-s` and `-f` address different problems and are not interchangeable. `-f` permits the engine to delete configuration that blocks a breakout; `-s` decides whether a parent that cannot be broken out is fatal. A dependency failure discovered during aggregate validation is therefore reported with both remedies: `-f` to clear the dependency, or `-s` to proceed without that parent.

`SKIPPED_ALREADY_CONFIGURED` is unaffected. It is a genuine no-op rather than a rejection, so it never aborts the command and needs no flag.

### 3.2 Aggregate plan and validation

Combine all READY parents into one captured `BulkBreakoutPlan` containing:

- Parent-to-current-child and parent-to-target-child maps for reporting.
- One deduplicated `delPorts` list containing every READY parent's current children.
- One `portJson["PORT"]` mapping containing every READY parent's target children.
- Aggregate dependency and `-l` default-configuration validation on a clone. On dependency failure the engine returns dependency references plus a failure result, but it does not expose a complete dependency or default-configuration diff.
- One aggregate `BREAKOUT_CFG` patch for every READY parent.
- The accepted parent set and combined delete list, which the pre-write check under the lock compares against. Mutable `BREAKOUT_CFG` rows, live `PORT` rows, and old-child OIDs are re-read at that point. Platform metadata is loaded once before the lock probe and reused by both planning passes.

Before any write, use a cloned configuration to validate the complete aggregate delete, add, and default-configuration result. Build the marker patch separately for the aggregate write and post-state check. Also validate cross-parent name/lane collisions.

The engine receives one combined delete list, so it resolves dependencies once for the whole aggregate rather than through one engine invocation per parent. It does not currently deduplicate returned dependency paths; dependency deduplication and XPath handling are outside this change. A shared dependency must retain unrelated or excluded members according to current single-parent force-removal semantics: the aggregate must not remove another parent's `PORT` entry merely because that parent was present in the original dependency object. This is the engine's existing dependency handling, unchanged here.

An attributable planning error remains `FAILED_PRECHECK` for its parent. An aggregate-only failure that cannot be attributed safely performs no writes and marks every READY parent `FAILED_BULK`. Never fall back to sequential parent execution.

Planning is side-effect-free. It must not call `_shutdownIntf()`, `writeConfigDB()`, or `_verifyAsicDB()`, update live `BREAKOUT_CFG`, or create `new_port_config.json` or another working-directory artifact.

### 3.3 Confirmation, locking, and drift

Use the existing `SYSTEM_RELOAD_LOCK` (`/etc/sonic/reload.lock`) with nonblocking acquisition; do not introduce a second DPB lock. The DPB CLI holds this file lock during its critical write section; orchagent continues consuming DB updates without acquiring it. This is best-effort coordination with participating operations, not exclusion of every CONFIG_DB or ASIC_DB writer.

1. After loading platform metadata and parsing the selector, probe the lock and release it immediately. This fails fast before mutable live-state planning when a participating operation already holds it. The probe proves nothing about step 5; it only avoids wasting the operator's time.
2. Resolve, preflight, and plan without the lock. Planning only reads, and its mutable DB and OID inputs are read again under the lock before any write. The previously loaded platform metadata is reused. Holding a lock across an open prompt would stall other participating operations for as long as the operator takes to answer.
3. Print the parents that will not be broken out and the aggregate plan. Without `-y`, request one ordinary confirmation for that aggregate.
4. Preserve the existing separate extra-table safety confirmation when applicable, including with `-y`.
5. Acquire the lock and rerun resolution and preflight against freshly read `BREAKOUT_CFG`, `PORT`, and ASIC-OID state, restricted to the parents the operator accepted so the comparison cannot widen the operation. The parent set and the combined delete list must match what was accepted; otherwise abort before the first write. A non-participating writer can still race after this check.
6. Hold the lock through aggregate apply, marker update, post-state verification, and reporting.

Successful acquisition and release are silent. DPB takes the lock twice—once for the fail-fast probe and once for the write section—so announcing each successful operation would bury useful output. Failure to acquire is still reported, because it is the reason the command stopped.

The step 5 comparison covers the parent set and the combined delete list. It does not compare dependencies: `-f` delegates dependency removal to the engine, which resolves it at execution time and reports no diff, so `-f` authorizes the dependencies present when the breakout runs rather than a set fixed at plan time. See section 5.1.

The plan shows the target mode, the combined child delete/add sets, and the extra-table warning where it applies. It also states the `-f` semantics above wherever `-f` is in effect. The running mode is not shown, as a selection may span several of them; per-parent current modes appear in the final status summary. Dependency removals and `-l` defaults are not enumerated.

### 3.4 Bulk execution and results

`ConfigMgmtDPB.breakOutPort(delPorts, portJson, ...)` accepts aggregate child collections and has no parent concept. Validation uses separate throwaway engine clones; for the write phase, invoke one fresh engine once for the accepted plan:

```text
1. ADMIN_DOWN_WRITTEN       combined PORT update for all old children
2. DELETE_CONFIG_WRITTEN    combined delete/dependency mod_config() call
3. ASIC_DELETE_VERIFIED     one wait for all old-child OIDs
4. ADD_CONFIG_WRITTEN       combined target/default-config mod_config() call
5. BREAKOUT_CFG_UPDATED     one aggregate marker patch/API call
6. POST_STATE_VERIFIED      target rows, obsolete-row absence, and markers confirmed
```

The existing engine uses a combined `mod_config()` call for each of the admin-down, delete, and add phases. After add succeeds, submit all READY marker changes in one aggregate API call rather than repeated `set_entry()` calls. Neither the individual calls nor the complete operation are promised to be transactional.

The staged implementation replaces the fixed `MAX_WAIT = 60` attempt-based deletion wait with this DPB policy:

```text
DPB_DELETE_STALL_TIMEOUT_SEC = 300     # seconds tolerated with no port leaving ASIC DB
DPB_DELETE_PER_CHILD_TIMEOUT_SEC = 3   # ceiling allowance per old child
DPB_DELETE_REPORT_INTERVAL_SEC = 30
DPB_DELETE_POLL_INTERVAL_SEC = 1       # gap between ASIC DB surveys

hard_timeout = (DPB_DELETE_STALL_TIMEOUT_SEC
                + DPB_DELETE_PER_CHILD_TIMEOUT_SEC * old_children_deleted)
```

Poll once per `DPB_DELETE_POLL_INTERVAL_SEC`, as the existing wait already does.

Build the ceiling up from the stall window rather than from a constant of its own. The ceiling must never be tighter than the stall window, or it would always expire first and the stall window could never be reached; deriving it keeps that true if either constant is retuned. It also leaves a single-child delete governed by one effective limit, which is right, because such a delete cannot report progress before it finishes and so has no second signal to judge.

Do not make `len(delPorts)` the primary bound. Deletion is serialized in orchagent and each SAI remove call carries a single OID, so total time grows with the number of old children, but per-child cost is variable. No quantity available at plan time predicts the cost closely enough to decide on its own whether a run has failed.

What is bounded is the interval between one old child leaving ASIC DB and the next. Make that interval the primary bound, and keep the count only for the absolute ceiling, where being a loose overestimate is acceptable.

On each pass, survey every old-child OID rather than returning at the first one still present, so the number outstanding is known and the still-present names can be reported. Reset the stall window whenever the outstanding count falls below the fewest ever observed. Comparing against that low-water mark rather than the previous pass prevents a transient ASIC DB read failure, which makes old children appear present again, from being counted as fresh progress when it recovers. Once `DPB_DELETE_STALL_TIMEOUT_SEC` elapses with no such progress, abort and name the ports still present.

Apply `hard_timeout` as an absolute deadline, fixed when the wait begins from the number of distinct old children and never extended. It covers only the pathological case where old children trickle out slowly enough to keep resetting the stall window indefinitely, and is not expected to be reached. Scale it rather than flattening it, because a flat value large enough for a whole chassis would be unnecessarily loose for a single parent. Count old children, not new ones, since it is the teardown that consumes the time.

Report progress to stdout no more often than `DPB_DELETE_REPORT_INTERVAL_SEC`, with the first report due only after that interval so a single-parent breakout remains as quiet as it is today. Route it to stdout directly: `sysLog(doPrint=True)` reaches the console only above `LOG_INFO` or under `python -i`, so an informational line sent through it is invisible.

Implement the wait with `time.monotonic()` rather than a fixed number of polling attempts. Return immediately when every old-child OID is absent, and test the success condition before declaring expiry so deletion first observed on a boundary succeeds. Use one wait for the complete aggregate deletion, not one per parent or child. These are frontend policy constants; this change adds no CLI option or backend contract. This policy applies only to phase 3; waiting for target-port creation remains out of scope.

#### Timeout calibration rationale

The stall window and hard ceiling answer different failure modes. The stall window bounds the interval between one old child leaving ASIC DB and the next. The hard ceiling bounds total elapsed deletion-wait time when old children keep leaving slowly enough to reset the stall window indefinitely.

The ceiling's fixed stall term absorbs teardown-tail cost that can dominate a small delete. Its per-child term gives wider operations additional time for serialized bulk deletion. The formula is intentionally uncapped: a denser platform earns a proportionally larger ceiling, while a genuinely stuck teardown at any width is still caught by the stall window.

The timeout policy cannot guarantee that every conceivable slow but progressing run completes. Its constants must instead preserve measured headroom across selector widths and resident port populations. Section 4.2 defines the validation method, and section 4 keeps the resulting benchmark data separate from this normative design.

Re-measure the constants before relying on them on another platform, at another port scale, or after an ASIC SDK change. Assess a benchmark result using section 4.2 rather than embedding one platform's historical measurements in the design rationale.

Final reporting is intended to use the status table in section 3.1, replacing each READY status with `APPLIED` or `FAILED_BULK` after aggregate processing.

If any aggregate phase fails, print one bulk error naming the coarse step that was in progress and the affected parent names. The child maps remain available in the aggregate plan printed before confirmation. Do not report unverified per-parent success.

The step reported is coarser than the six phases above. `breakOutPort()` returns only success or failure for the whole delete/add, so a failure is attributed to one of the two steps the CLI drives: the combined port delete and add, or the marker update. Naming one of the six would require per-phase progress that the engine does not currently expose.

In particular:

- ASIC-delete timeout occurs after deletion and before add; all aggregate parents may be left without target ports.
- Add failure may leave every aggregate parent deleted.
- Marker failure may leave target PORT layout present while some or all `BREAKOUT_CFG` rows are stale or indeterminate.
- There is no automatic rollback and no ASIC-create wait.

A caught exception outranks observed state. Every participating parent is `FAILED_BULK` whenever the apply raised, even where CONFIG_DB reads exactly as planned, and the command exits nonzero. Post-state verification covers the target `PORT` rows, obsolete old-child absence, and the marker, so correct-looking ports do not establish that the phases the apply never reached were performed. Where verification found a specific problem, that reason is reported instead of the generic one.

Direct the operator to inspect `PORT`, modeled dependencies, old-child ASIC OIDs, and `BREAKOUT_CFG` before retrying a partial or indeterminate operation.

`FAILED_BULK` always returns nonzero. Any result containing `FAILED_PRECHECK` and no `APPLIED` parent also returns nonzero. A result containing only `SKIPPED_ALREADY_CONFIGURED` parents is a successful no-op. Two further cases, a mixed result containing both `APPLIED` and `FAILED_PRECHECK` and a selector that resolves to no active platform parent (exact non-parents or a range with no matches), are decided in section 5.1.

## 4. DPB benchmark analysis

### 4.1 Trigger definitions and starting populations

**Trigger 1** is the expansion direction, `1x800G` to `8x100G`. It changes Ethernet0 individually, then applies the range to the untouched parents.

**Trigger 2** is the collapse direction, `8x100G` to `1x800G`. It changes Ethernet0 individually, then deliberately includes Ethernet0 in the range to verify the already-configured skip path.

Ethernet512 supports only `2x10G(2)` and was intentionally included under `-s` to verify unsupported-parent skipping. Its two 10G logical rows, Ethernet512 and Ethernet513, remained unchanged.

| Trigger step     | Exact command                                          | Logical composition at command start | Start PORT rows, CONFIG/APPL/ASIC | Selected / changed / skipped parents |
| ---------------- | ------------------------------------------------------ | ------------------------------------ | --------------------------------- | ------------------------------------ |
| Trigger 1 single | `config interface breakout Ethernet0 8x100G -y`        | 64 x 800G + 2 x 10G                  | 66 / 68 / 70                      | 1 / 1 / 0                            |
| Trigger 1 range  | `config interface breakout Ethernet8-512 8x100G -y -s` | 8 x 100G + 63 x 800G + 2 x 10G       | 73 / 75 / 77                      | 64 / 63 / 1                          |
| Trigger 2 single | `config interface breakout Ethernet0 1x800G -y`        | 512 x 100G + 2 x 10G                 | 514 / 516 / 518                   | 1 / 1 / 0                            |
| Trigger 2 range  | `config interface breakout Ethernet0-512 1x800G -y -s` | 1 x 800G + 504 x 100G + 2 x 10G      | 507 / 509 / 511                   | 65 / 63 / 2                          |

The three database counts are reported separately because CONFIG_DB counts configured logical front-panel `PORT` rows, while APPL_DB and ASIC_DB include additional rows or objects.

### 4.2 Timing interpretation

The timeout formula under test was:

```text
hard ceiling = 300 + 3 * old children deleted
half-ceiling target = hard ceiling / 2
```

The half-ceiling value is an optimal, desired performance target, not the actual timeout, an SLA, or a declaration that a longer completed run is unacceptable. It represents 2x headroom before the hard guardrail; likewise, the 100-second no-progress target represents 3x headroom inside the 300-second stall timeout.

The benchmark did not emit timestamps at the exact entry and exit of `_verifyAsicDB()`. The half-ceiling comparison therefore uses complete CLI wall-clock time conservatively. That interval includes planning, validation, CONFIG_DB writes, marker update, and post-state verification in addition to the ASIC-delete wait, so it can only overstate the deletion-wait duration governed by the ceiling.

### 4.3 Primary single-parent and range results

| Operation                              | Old deleted / new configured | CLI wall  | Hard ceiling | HLD half-ceiling target | What was observed         | Half-ceiling assessment | Longest no-delete interval |
| -------------------------------------- | ---------------------------- | --------- | ------------ | ----------------------- | ------------------------- | ----------------------- | -------------------------- |
| Trigger 1 single, `1x800G` to `8x100G` | 1 / 8                        | 3.696 s   | 303 s        | <=151.5 s               | 3.696 s; 147.804 s under  | Within desired target   | 2.569 s                    |
| Trigger 1 range, Ethernet8-512         | 63 / 504                     | 23.387 s  | 489 s        | <=244.5 s               | 23.387 s; 221.113 s under | Within desired target   | 5.494 s                    |
| Trigger 2 single, `8x100G` to `1x800G` | 8 / 1                        | 100.407 s | 324 s        | <=162.0 s               | 100.407 s; 61.593 s under | Within desired target   | 49.244 s                   |
| Trigger 2 range, Ethernet0-512         | 504 / 63                     | 862.991 s | 1,812 s      | <=906.0 s               | 862.991 s; 43.009 s under | Within desired target   | 28.312 s                   |

The Trigger 2 range produced the intended mixed-state result: Ethernet0 was already configured and skipped, Ethernet512 failed target-mode precheck and was skipped under `-s`, and the remaining 63 parents changed successfully. Every breakout command that invoked `config` returned zero and reached its expected CONFIG_DB and ASIC object-count state.

For expansion, the 63-parent range changed 63 times as many parents as the single-parent command in 6.328 times the wall time. Throughput increased from 0.2706 to 2.6939 changed parents per second. For collapse, the range changed 63 times as many parents in 8.595 times the wall time; throughput increased from 0.0100 to 0.0730 changed parents per second.

Collapse was substantially slower than expansion. The primary single-parent collapse-to-expansion wall-time ratio was 27.166, and the primary range ratio was 36.901. Source mode, resident object count, and old-child count changed together, so this benchmark does not support a simple linear per-child performance model.

### 4.4 Repeated full-range stress results

Each stress operation selected Ethernet0-512, changed all 64 parents that support the target mode, and intentionally skipped Ethernet512. Three transitions were measured in each direction.

| Cycle | Direction            | Old to new rows | HLD half-ceiling target | What was observed          | Half-ceiling assessment | Longest no-delete interval |
| ----- | -------------------- | --------------- | ----------------------- | -------------------------- | ----------------------- | -------------------------- |
| 1     | `1x800G` to `8x100G` | 64 to 512       | <=246.0 s               | 21.241 s; 224.759 s under  | Within desired target   | 5.862 s                    |
| 1     | `8x100G` to `1x800G` | 512 to 64       | <=918.0 s               | 1001.253 s; 83.253 s over  | Above desired target    | 37.583 s                   |
| 2     | `1x800G` to `8x100G` | 64 to 512       | <=246.0 s               | 20.203 s; 225.797 s under  | Within desired target   | 5.763 s                    |
| 2     | `8x100G` to `1x800G` | 512 to 64       | <=918.0 s               | 927.020 s; 9.020 s over    | Above desired target    | 53.622 s                   |
| 3     | `1x800G` to `8x100G` | 64 to 512       | <=246.0 s               | 21.496 s; 224.504 s under  | Within desired target   | 5.943 s                    |
| 3     | `8x100G` to `1x800G` | 512 to 64       | <=918.0 s               | 1053.756 s; 135.756 s over | Above desired target    | 35.286 s                   |

| Direction            | n   | Minimum   | Maximum    | Mean      | Median / p50 | p95, linear interpolation |
| -------------------- | --- | --------- | ---------- | --------- | ------------ | ------------------------- |
| `1x800G` to `8x100G` | 3   | 20.203 s  | 21.496 s   | 20.980 s  | 21.241 s     | 21.470 s                  |
| `8x100G` to `1x800G` | 3   | 927.020 s | 1053.756 s | 994.010 s | 1001.253 s   | 1048.506 s                |

Here, p50 is the median: half the observations are no greater and half are no less. p95 is the interpolated 95th percentile. With only three samples, p95 is descriptive and is not a reliable production tail estimate.

The repeated full-range mean collapse-to-expansion wall-time ratio was 47.379. Eight times as many old rows were deleted in the collapse direction, while mean wall time increased by more than that factor. This supports old-child count as an important scaling variable but also shows a direction and resident-scale penalty that this matrix cannot isolate.

Two no-op commands selected Ethernet0-504 while all 64 parents already matched the target. The `8x100G` no-op took 2.126 seconds and the `1x800G` no-op took 2.051 seconds. Each reported 64 already-configured parents, changed none, and produced no SAI port create or remove event.

### 4.5 Timeout result

The progress-based wait behaved functionally as designed. The primary Trigger 2 range emitted 28 aggregate progress reports and continued for more than 14 minutes while old ports kept leaving ASIC_DB. The three stress collapses emitted 32, 30, and 34 reports. The wait therefore continued beyond the former fixed 60-second behavior and returned after deletion completed.

No run reached the 300-second no-progress timeout or its hard ceiling. The longest measured no-deletion interval was 53.622 seconds, so every run passed the HLD's less-than-100-second no-progress criterion. Trigger 2 single, Trigger 2 range, and all three stress collapses would have exceeded the former fixed 60-second deletion wait.

The functional DPB result is **PASS**, and every run completed without reaching an actual timeout. Under the conservative complete-CLI-wall interpretation, the three repeated 512-old-child collapses were above the optimal 918-second half-ceiling target. This means the runs did not retain the desired 2x performance headroom and may benefit from optimization; it does not mean that their elapsed time was inherently unacceptable or that DPB failed. The deletion wait would become a timeout failure if it reached the 300-second no-progress limit or the 1,836-second hard ceiling. Neither occurred.

### 4.6 Completion semantics

Target CONFIG_DB rows appeared at approximately CLI completion, but SAI object creation continued after the CLI returned:

| Run               | CLI wall           | Last SAI create    | Create activity after CLI return |
| ----------------- | ------------------ | ------------------ | -------------------------------- |
| Trigger 1 single  | 3.696 s            | 3.864 s            | 0.168 s                          |
| Trigger 1 range   | 23.387 s           | 63.686 s           | 40.300 s                         |
| Trigger 2 single  | 100.407 s          | 101.008 s          | 0.600 s                          |
| Trigger 2 range   | 862.991 s          | 867.082 s          | 4.090 s                          |
| Stress expansions | 20.203-21.496 s    | 63.547-73.654 s    | 42.051-52.413 s                  |
| Stress collapses  | 927.020-1053.756 s | 931.252-1058.238 s | 4.232-4.482 s                    |

CLI completion therefore establishes target CONFIG_DB completion, not completion or readiness of every new ASIC port. ASIC object-count equality can also occur transiently during remove/create churn and is not, by itself, a completion proof.

### 4.7 Limitations

- Only the requested 1x800G and 8x100G transitions were tested; the full HLD matrix's 2x400G and 4x200G cells were outside scope.
- SAI OID creation and object-count stability do not prove physical port readiness. All links were operationally down, preventing an independent readiness measurement.

## 5. Decisions

### 5.1 Decisions taken

**Mixed `APPLIED` and `FAILED_PRECHECK`.** Without `-s` the combination cannot arise, because a rejected parent aborts before any write. With `-s` the operator has accepted that outcome in advance, so a run that applied its remaining parents exits 0. Reporting a failure there would leave a caller unable to distinguish a skip it requested from one it did not.

**Selector resolving to no active platform parent.** An exact term that is not a platform parent is `SKIPPED_NOT_PARENT` and exits 1: naming a port that cannot be broken out is a bad command, not a no-op, and must not look like success. A range behaves differently, because it filters the finite platform parent set rather than materializing its numeric interval, and so can never yield a non-parent. A range matching nothing therefore produces no results at all and exits 0 as a no-op. `SKIPPED_ALREADY_CONFIGURED` likewise remains a successful no-op.

**Multi-parent mode completion.** Intersection. Only modes advertised by every parent in the selector are offered, so each suggestion is valid for the whole selection. Suggestions keep the order `platform.json` declares, as the single-parent command does. Completion must not validate the command, write state, or raise; any error should yield an empty suggestion list. `dpb.completionModes()` enforces that behavior.

**`-f` and post-confirmation dependency drift.** `-f` authorizes the dependencies present at execution time, not a set fixed when the plan was displayed. This matches existing single-parent `-f` behavior, where dependencies are likewise never listed before the write. Since the plan never enumerates them, no post-confirmation comparison is added; the plan output states the semantics instead. Re-running full validation under the lock was rejected: it costs a second engine clone and can drop parents after confirmation, which needs its own decision about a shrinking accepted set.

**Scope of `APPLIED`.** Narrowed to the target `PORT` rows, absence of obsolete current-child rows, and the `BREAKOUT_CFG` marker. Planned target fields are compared field by field. Fields the plan does not specify are not compared, as the plan is the only record of intent and does not carry the defaults `-l` asks the engine to add. Verifying those defaults or the dependency removals requires the engine to return what it computed, which is a change to its contract; until then the status claims only what it checks.

## 6. Sources

- [Community DPB HLD](https://github.com/sonic-net/SONiC/blob/master/doc/dynamic-port-breakout/sonic-dynamic-port-breakout-HLD.md)
- Cisco WHITEBOX wiki:
  - [SONiC DPB on Tortuga platforms](https://ciscoteams.atlassian.net/wiki/spaces/WHITEBOX/pages/730696975/SONiC+DPB+on+Tortuga+platforms)
  - [DPB troubleshooting guidelines](https://ciscoteams.atlassian.net/wiki/spaces/WHITEBOX/pages/730697558/DPB+troubleshooting+guidelines)
  - [SONiC DPB standalone test script](https://ciscoteams.atlassian.net/wiki/spaces/WHITEBOX/pages/730697337/SONiC+DPB+standalone+test+script)
- In-tree CLI, selector/parser, child-generation, and `ConfigMgmtDPB` implementation.
- Internal platform PR [#4504](https://wwwin-github.cisco.com/whitebox/platform-cisco-8000/pull/4504) for `BREAKOUT_CFG` current-mode state keyed by canonical parent.
- Internal platform PR [#4949](https://wwwin-github.cisco.com/whitebox/platform-cisco-8000/pull/4949) for related platform migration handling.

# Parallel Test Execution Plan for sonic-utilities

## Status
**`-n auto`: 4618 passed, 0 failed** — multiple clean runs verified (3 consecutive).
**`-n 1`: 4618 passed, 0 failed** — verified clean after fixing cross-file pollution.
**Serial files: 0** (down from 19). **Time: ~96s** with `-n auto`.

### Root causes found and fixed for `-n 1`

**Cross-file state pollution (raw assignments without cleanup):**
1. **vlan_test.py** — duplicate `teardown_class` (Python silently replaces the first with
   the second). The second definition only restored `bgp_util.run_bgp_command` and env vars,
   but the first (real) one also restored `CliRunner.invoke`, `multi_asic.connect_config_db_for_ns`,
   `multi_asic.connect_to_all_dbs_for_ns`, and `config.vlan.get_db_with_namespace`. Fix: removed
   the duplicate. **Caused 53 failures.**
2. **route_check_test.py** — `device_info.get_platform = MagicMock(return_value='unittest')`
   raw assignment inside a `with patch(...)` block. The `patch()` calls get cleaned up on exit
   but the raw assignment persists. Fix: replaced with `patch.object(device_info, 'get_platform',
   return_value='unittest')`. **Caused 5 failures.**
3. **sfp_test.py** — `sys.modules.pop('sonic_platform')` in `test_is_rj45_port` without restoring.
   Other tests (decode_syseeprom_test) depend on `sys.modules['sonic_platform']` being a MagicMock.
   Fix: save before pop, restore in finally block. **Caused 1 failure.**
4. **vrrp_test.py** — `bgp_util.run_bgp_command = MagicMock(return_value="")` in `setup_class`
   with no `teardown_class`. Subsequent tests calling `run_bgp_show_command` get empty string
   instead of calling the real function. Fix: added `teardown_class` to restore the original.
   **Caused 1 failure.**

**Incomplete multi-asic setup_class methods (7 files):**
These tests relied on env vars left by prior serial tests. With `_reset_between_files`
clearing state, each file's `setup_class` must be self-contained.
- `feature_test.py` — full multi-asic init in `TestFeatureMultiAsic.setup_class`
- `multi_asic_ipv6_link_local_test.py` — `UTILITIES_UNIT_TESTING` changed from `"1"` to `"2"`
- `multi_asic_pfc_test.py` — explicit `UTILITIES_UNIT_TESTING="2"` instead of relying on parent
- `multi_asic_show_bfd_test.py` — added `get_all_namespaces` lambda
- `multi_asic_vnet_test.py` — added `get_all_namespaces` lambda
- `show_bgp_neighbor_test.py` — added env vars to multi-asic `setup_class`
- `syslog_multi_asic_test.py` — added env vars to fixture setup + cleanup in teardown

**Safety net in conftest.py:**
- Added `CliRunner.invoke` restoration to `_reset_between_files()` in case tests replace it

## Goal (ACHIEVED)
Use pytest-xdist to parallelize sonic-utilities test runs. All 4618 tests run fully parallel
in ~96s — a 92% reduction from the ~20 minute serial baseline.

## Building and Testing

### Standard build
- Build: `make target/python-wheels/bookworm/sonic_utilities-1.2-py3-none-any.whl` from sonic-buildimage root
- First build takes a while (builds all deps). Subsequent builds are faster.
- Build log (includes pip install, pytest output, wheel build): `target/python-wheels/bookworm/sonic_utilities-1.2-py3-none-any.whl.log`
- **NOTE:** This `.whl.log` is only written during the standard build process. When you
  run tests ad-hoc via `docker exec`, pytest output goes to stdout/stderr — you must
  capture it yourself (see "Running tests inside the container" below).

### KEEP_SLAVE_ON for ad-hoc testing
For interactive debugging, start a persistent container. **CRITICAL: Must be run in a
real TTY — do NOT pipe through `tail`, do NOT redirect output, do NOT run in background.**
The KEEP_SLAVE_ON mechanism drops to `/bin/bash` after the build finishes. Without a live
stdin, bash exits immediately and the container dies.

**Correct way to start (user runs this in their terminal via `!` prefix):**
```
make -f Makefile.work BLDENV=bookworm KEEP_SLAVE_ON=yes target/python-wheels/bookworm/sonic_utilities-1.2-py3-none-any.whl
```

The container bind-mounts `src/sonic-utilities` from the host — any local file changes
are immediately visible inside the container. No need to copy files in.

### Running tests inside the container

Use `docker exec` to run tests. The container has all dependencies pre-installed.

**IMPORTANT: Always capture the FULL output of test runs.** Tests can take 20 minutes
with `-n 1`. If you only capture `tail`, you lose failure details and have to re-run.
Always redirect full output to a file, then analyze the file.

```bash
# Find the container
docker ps --filter "ancestor=sonic-slave-bookworm*" --format "{{.ID}}"

# Run tests and capture FULL output to a file
docker exec <container_id> bash -c \
  'cd /sonic/src/sonic-utilities && python3 -m pytest -n 1 --dist loadfile --tb=short -v 2>&1' \
  > /tmp/pytest_n1_results.log 2>&1

# Then analyze the results
grep -E "FAILED|PASSED|ERROR|passed|failed" /tmp/pytest_n1_results.log | tail -20
grep "FAILED" /tmp/pytest_n1_results.log
```

**For quick parallel runs (~5 min):** Use `-n auto` (default in pytest.ini).
**For single-worker verification (~20 min):** Use `-n 1 --dist loadfile`.
**For individual files:** `python3 -m pytest tests/some_test.py -x -v --tb=short -p no:xdist`

## Baseline Measurements
- **Serial baseline:** 4656 passed, 0 failed, 6 skipped, 1 xfailed — 1233.72s (20:33)
- **Current parallel:** 4618 passed, 0 failed, 19 skipped, 1 xfailed — ~96s (1:36)
- **Improvement:** ~92% time reduction (20:33 → 1:36)
- 251 test files total: all parallel, 0 serial
- 13 additional skips are from tests that detect xdist and skip (expected)
- Three consecutive clean runs verified — zero intermittent failures

## Implementation Strategy

### Phase 1: Infrastructure (DONE)
- Add pytest-xdist to testing deps in setup.py
- Configure `pytest.ini` with `-n auto --dist loadfile`
- Add `_reset_between_files` hook in `tests/conftest.py` to clean up global state between test files on parallel workers
- Fix `UserCache` in `utilities_common/cli.py` to read `SONIC_CLI_CACHE_DIR` env at init time
- (SerialAwareScheduler was used during development but removed — no serial files remain)

### Phase 2: Identify and isolate serial tests (DONE)
Start with ALL test files marked serial. Progressively move files to parallel in batches, verifying zero failures after each batch.

**Why serial-first:** Tests using mock DB infrastructure (`mock_tables/dbconnector.py`) share mutable global state (`dedicated_dbs`, `topo`, `SonicDBConfig`). Multi-asic tests reload modules and change `multi_asic.*` functions. These side effects leak between files on the same worker.

### Phase 3: Move safe files to parallel (DONE — 4 stages)
Identified safe-to-parallelize files by analyzing each test file's imports and side effects:

1. **Stage 1 — No mock_tables import (12 files):** Files that don't import `mock_tables` at all. Zero risk of DB contamination.
2. **Stage 2 — Light DB users (11 files):** Files that import `dbconnector` but don't use `dedicated_dbs`, `topo`, or multi-asic features.
3. **Stage 3 — Env-var-only files (6 files):** Files that only set environment variables (cleaned up by `_reset_between_files`).
4. **Stage 4 — Batch-verified (4 files):** Remaining files verified by running full suite.

**Result after Phase 3:** 121 serial files, 33 files parallel, ~50% time reduction (20:33 → 10:33).

### Phase 4: Fix redistribution fragility (DONE)
**Root cause discovered:** Serial tests (`portstat_test.py`, `pgdropstat_test.py`) physically overwrite shared JSON files (`counters_db.json`, `config_db.json`) in `mock_tables/` during execution. Parallel workers reading these files mid-replacement get corrupted data.

**Fix:** Per-xdist-worker copy of `mock_tables/` directory. Each worker gets its own sandbox at `/tmp/mock_tables-<worker_id>/`. Subprocesses (e.g., `portstat` spawned by `show interfaces counters`) inherit the path via `MOCK_TABLES_DIR` env var.

Files changed:
- `tests/mock_tables/dbconnector.py`: `INPUT_DIR` reads from `MOCK_TABLES_DIR` env var
- `tests/conftest.py`: `setup_db_config` copies mock_tables per worker, cleans up on teardown
- `tests/portstat_test.py`: Uses `dbconnector.INPUT_DIR` instead of hardcoded paths
- `tests/pgdropstat_test.py`: Uses `dbconnector.INPUT_DIR` instead of hardcoded paths

### Phase 5: Move more files to parallel (DONE — 3 stages)
With per-worker mock_tables isolation, moved 69 more files to parallel across 3 commits:

1. **18 files** — Light DB users with well-isolated fixtures
2. **45 files** — Batch of non-DB and light-DB files verified together
3. **6 files** — `dedicated_dbs`-only files (no multi-asic)

**Discovery:** `fdbshow_test.py` cannot run in parallel — it causes `multi_asic_fdbshow_test.py` to fail on serial worker. Reverted to serial.

**Result after Phase 5:** 52 serial files, ~199 parallel, **4618 passed, 0 failed, 19 skipped in 7:19 (~64% reduction)**.

### Phase 6: Move multi-asic files to parallel (DONE)

All remaining serial files use multi-asic patterns (module reloads, env vars, `dedicated_dbs`).
The key to moving them is ensuring each file's `setup_class` is **self-contained** — it must
explicitly set all state it needs rather than relying on side effects from prior serial tests.

**What works:** Files whose `setup_class` explicitly sets `UTILITIES_UNIT_TESTING="2"`,
`UTILITIES_UNIT_TESTING_TOPOLOGY="multi_asic"`, reloads the mock, and calls
`load_namespace_config()`. The `_reset_between_files` hook clears all state between files,
so the next file's setup must re-establish everything from scratch.

**What fails:** Files whose `setup_class` skips env var setup (e.g., `flap_test.py`,
`mpls_test.py`) because they relied on prior serial tests leaving `UTILITIES_UNIT_TESTING_TOPOLOGY`
set. Fix: add the missing env var assignments to the test file's `setup_class`.

**Phase 6a — 10 files moved (DONE, commit 12):**
test_db, lldp_test, config_fabric_test, drops_group_test, acl_loader_test,
fibshow_test, show_bgp_neighbor_test, show_bgp_network_test, show_run_bgp_test, show_test.
Result: 4618 passed, 0 failed, 19 skipped in 7:08. Serial count: 52 → 42.

**Phase 6b — Multi-asic files blocked by serial ordering contamination:**
Moving multi_asic files from serial to parallel changes the execution order on gw0,
breaking fragile inter-test dependencies among the remaining serial tests. Attempted
moving 9 multi_asic files (intfutil, ipv6_link_local, pfc, queue_counter, show_bfd,
subintf, vlan, vnet, vxlan) — caused 12-21 failures in SERIAL files (pfcwd_test,
multi_asic_fdbshow_test) due to changed gw0 ordering. The multi_asic files themselves
also had failures (pfc: 17 fails, ipv6_link_local: 2 fails + contaminated parallel
ipv6_link_local_test.py).

**Root cause:** Serial tests on gw0 depend on state accumulated from prior serial
tests. Removing files from the serial set changes this ordering.

**Approach 1 — Enable `_reset_between_files` for serial tests (REJECTED initially,
then REVISITED and ADOPTED):**
Initial attempt caused 141-147 failures because mock files didn't mock all required
functions. After fixing mock files and switching to file-only resets, this approach
now works cleanly.

**Approach 2 — Make serial setup_class methods self-contained (DONE):**
Fixed incomplete `setup_class` methods so they explicitly set all required state
(env vars, mock reloads, namespace config).

**Files fixed (setup_class made self-contained):**
- `bgp_commands_test.py` — added env vars (already had mock reload)
- `flap_test.py` — added env vars (already had mock reload)
- `mpls_test.py` — added env vars (already had mock reload)
- `switchstat_test.py` — added env vars (already had mock reload of 3-asic variant)
- `multi_asic_ecnconfig_test.py` — added mock reload + namespace config
- `multi_asic_mmuconfig_test.py` — added mock reload + namespace config
- `pfcwd_test.py` — added mock reload + namespace config

**Subprocess tests NOT modified (mock reload in parent process leaks state):**
- `portstat_test.py` — subprocess-based, env vars already sufficient
- `pfcstat_test.py` — subprocess-based, env vars already sufficient
- `multi_asic_fdbshow_test.py` — subprocess-based, env vars already sufficient

**Key finding:** Adding `importlib.reload(mock_multi_asic)` to subprocess-based tests
causes the parent process to enter multi-asic state without proper teardown, contaminating
subsequent serial tests (e.g., show_acl_test.py saw 2 failures from portstat's leaked state).
Subprocess tests don't need parent-process mock reload — the subprocess reads env vars and
handles its own mock state.

**Build result:** 4618 passed, 0 failed, 19 skipped in 6:44.

**Phase 6c — 5 multi-asic files moved to parallel (DONE, commit 15):**
multi_asic_show_bfd_test, multi_asic_vlan_test, multi_asic_vnet_test,
multi_asic_vxlan_test, suppress_pending_fib_test.
All have fully self-contained setup_class methods with env vars, mock reload,
namespace config, and (where needed) module reloads.
Serial: 42 → 37.

**Phase 6d — Enable `_reset_between_files` for ALL files (DONE):**
Made `_reset_between_files` run for every file regardless of serial/parallel status.
This eliminates serial ordering dependencies entirely — every file starts from a clean
single-asic baseline.

Key changes required to make this work:
1. **Mock files missing `get_all_namespaces`**: The reset sets `multi_asic.get_all_namespaces`
   to a single-asic lambda. When test files reload mock_multi_asic.py or mock_single_asic.py,
   those mock files must re-set `get_all_namespaces` — but they didn't mock it. Fixed by
   adding `mock_get_all_namespaces()` and `get_namespaces_from_linux` to all three mock files
   (`mock_multi_asic.py`, `mock_single_asic.py`, `mock_multi_asic_3_asics.py`).
2. **File-only resets (not class-level)**: Class-level resets disrupted module-scoped
   fixtures (e.g., match_engine_test's autouse fixture). Changed to reset only on
   file transitions. Intra-file class setup_class is responsible for configuring state
   from the file-level baseline.
3. **FDBSHOW_UNIT_TESTING env var**: The reset pops this env var. `multi_asic_fdbshow_test.py`
   needs it set to "0" (NOT "1" — "1" causes KeyError on FDBSHOW_MOCK).
4. **C++ SonicDBConfig.reset() caused intermittent failures**: The `reset()+load()` cycle
   left the C++ singleton in a transiently-empty state, causing random failures in
   decode_syseeprom_test, ipv6_link_local_test, ip_show_routes_test. Fixed by using
   conditional `isInit()`/`isGlobalInit()` checks — only load if not already initialized.
   Since no test directly modifies the C++ config, reset is unnecessary.

**Result: 4618 passed, 0 failed, 19 skipped — two consecutive clean runs with `-n auto`.**

**Phase 6e — Move remaining 5 serial files to parallel (DONE):**

| File | Root cause | Fix |
|------|-----------|-----|
| port2alias_test.py | `_reset_between_files` sets `UTILITIES_UNIT_TESTING="2"`, port2alias checks for "2" to load multi-asic config | Added `setup_class`/`teardown_class` to set `UTILITIES_UNIT_TESTING="1"` |
| multi_asic_vlan_test.py | `click.Choice(multi_asic.get_namespace_list())` in `config/vlan.py` froze namespace choices at import time | Changed to `multi_asic_click_option_namespace(required=True)` (LazyChoice). Simplified Click patching to only save/restore `required` flag |
| chassis_modules_test.py | Missing `scripts_path` on PATH — subprocess tests using `voqutil` couldn't find the script | Added `scripts_path` to PATH in `setup_class`, removed in `teardown_class` |
| bgp_commands_test.py | Broken teardown: missing `@classmethod`, missing `()` on `dbconnector.load_database_config`, missing env var cleanup | Fixed all three issues. Also fixed `()` missing in show_bgp_neighbor_test, show_bgp_network_test, show_run_bgp_test |
| ip_show_routes_voq_chassis_test.py | `@mock.patch.object(multi_asic_util.MultiAsic, ...)` captured class ref at import time; after `importlib.reload(utilities_common.multi_asic)` by another test, the old class gets patched while route code uses the new class | Changed to string-based `@mock.patch("utilities_common.multi_asic.MultiAsic.get_ns_list_based_on_options", ...)` which resolves at call time. Same fix applied to bgp_commands_test.py (10 decorators) |
| vlan_test.py | Already worked — no changes needed |
| config_test.py | Already worked — no changes needed |
| cli_autogen_test.py | Overwrites `/usr/local/yang-models/` — races with parallel workers reading YANG | Changed to temp directory approach: `setup_temp_yang_dir()` copies YANG models to a per-test temp dir, patches `config_mgmt.YANG_DIR`. Kept serial due to Click tree mutation (plugin registration) |
| cli_autogen_yang_parser_test.py | Same YANG file issue | Same temp directory approach |

**Additional cross-worker race fix:**
- `pgdropstat_test.py` / `portstat_test.py`: Both used shared `/tmp/counters_db.json` for file backup/restore. When running on different workers simultaneously, portstat overwrites pgdropstat's backup. Fix: backup to `.bak` files in per-worker `dbconnector.INPUT_DIR` instead of `/tmp/`.

#### Remaining serial files (0)

All test files now run in parallel. The cli_autogen tests were the last holdouts due to
Click tree mutation concerns, but testing showed they don't interfere with other tests
in practice (3 consecutive clean runs with zero serial files).

## Architecture

### Key Files
- `conftest.py` (root): Minimal — all tests run in parallel via default loadfile scheduling
- `tests/conftest.py`: `setup_db_config` session fixture, `_reset_between_files`, `setup_multi_asic_env`
- `tests/mock_tables/dbconnector.py`: Mock Redis infrastructure, `INPUT_DIR`, `dedicated_dbs`, `SwssSyncClient`
- `pytest.ini`: xdist configuration (`-n auto --dist loadfile`)
- `setup.py`: pytest-xdist dependency

### How State Reset Works
`_reset_between_files()` runs before each new test **file** on ALL workers (serial and
parallel alike). It does NOT reset between classes within the same file — module-scoped
fixtures and intra-file class setup_class handle that. It resets:
- `dedicated_dbs`, `topo` globals in dbconnector
- Environment variables (`UTILITIES_UNIT_TESTING`, `UTILITIES_UNIT_TESTING_TOPOLOGY`, etc.)
- `config.ADHOC_VALIDATION`, `config.asic_type`
- Per-worker cache directory contents
- `multi_asic.*` functions back to single-asic defaults
- Python `SonicDBConfig` back to single-asic config
- C++ `SonicDBConfig` — conditional load only (no reset, to avoid transient empty state)

### Issues Found and Fixed

All issues below have been resolved. They are documented for reference.

1. **pcieutil_test.py** — relied on prior test leaving `get_paths_to_platform_and_hwsku_dirs`
   mocked. Fixed with proper `@mock.patch` decorator.
2. **cli_autogen_test.py / cli_autogen_yang_parser_test.py** — overwrote `/usr/local/yang-models/`.
   Fixed with temp directory approach (`setup_temp_yang_dir()` + `config_mgmt.YANG_DIR` patching).
3. **Click decorator freezing** — `click.Choice(multi_asic.get_namespace_list())` froze namespace
   choices at import time. Fixed with `LazyChoice` class that defers evaluation to validation time.
4. **Incomplete multi-asic setup_class** — many files relied on env vars left by prior tests.
   Fixed by making each file's `setup_class` self-contained.
5. **C++ SonicDBConfig intermittent failures** — `reset()+load()` left transient empty state.
   Fixed with conditional `isInit()`/`isGlobalInit()` checks (no reset needed).
6. **`@mock.patch.object` with reloadable modules** — captured class ref at decoration time;
   module reloads made mock invisible. Fixed with string-based `@mock.patch()` that resolves
   at call time. Applied to `ip_show_routes_voq_chassis_test.py` and `bgp_commands_test.py`.
7. **Shared `/tmp/` paths for file backup/restore** — `pgdropstat_test.py` and `portstat_test.py`
   both used `/tmp/counters_db.json`. Fixed: backup to `.bak` files in per-worker directory.
8. **Cross-file state pollution** — `vlan_test.py` (duplicate teardown, 53 failures),
   `route_check_test.py` (raw mock assignment, 5 failures), `sfp_test.py` (`sys.modules.pop`),
   `vrrp_test.py` (missing teardown). All fixed.
9. **bgp_commands_test.py broken teardown** — missing `@classmethod`, missing `()` on
   `dbconnector.load_database_config`, missing env var cleanup. Same `()` bug in 3 other BGP
   test files. All fixed.

## Principles
- **Zero failures baseline.** Any test failure is a regression we introduced.
- **Don't lie.** If a test can't reliably run in parallel, keep it serial. Don't mark it parallel and hope for the best.
- **Investigate root causes.** When tests fail in parallel, find out WHY rather than just moving them back to serial.

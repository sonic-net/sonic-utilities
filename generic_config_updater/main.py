"""
GCU (Generic Config Updater) — apply-patch orchestration
=========================================================

This module is the **single source of truth** for all apply-patch logic.
It is consumed by:

* ``config apply-patch``  (config/main.py — thin entry-point / standalone redirect)
* ``scripts/gcu.py``      (raw-script entry point on the host)
* ``gcu-standalone``       (console_scripts entry point installed by the GCU wheel
                            into the GCU container virtual-env at
                            /opt/sonic/gcu/current/bin/gcu-standalone)

No caller should re-implement scope extraction, parallel execution,
pre-processing, or per-scope dispatch — they should call the helpers
exposed here instead.
"""

import copy
import json
import logging
import os
import sys
import argparse
import subprocess
import threading
import concurrent.futures

import jsonpatch
import jsonpointer

from generic_config_updater.generic_updater import (
    GenericUpdater,
    ConfigFormat,
    extract_scope,
)
from generic_config_updater.gu_common import (
    HOST_NAMESPACE,
    GenericConfigUpdaterError,
)
from sonic_py_common import multi_asic

logger = logging.getLogger(__name__)

# Constants
DEFAULT_CONFIG_DB_FILE = '/etc/sonic/config_db.json'


# ---------------------------------------------------------------------------
# Lightweight JSON-Patch format validation (RFC 6902)
# ---------------------------------------------------------------------------

def validate_patch_format(patch):
    """Return *True* if *patch* is a structurally valid JSON Patch list."""
    try:
        if not isinstance(patch, list):
            return False
        for change in patch:
            if not isinstance(change, dict):
                return False
            if 'op' not in change or 'path' not in change:
                return False
            if change['op'] not in (
                'add', 'remove', 'replace', 'move', 'copy', 'test',
            ):
                return False
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Running-config retrieval
# ---------------------------------------------------------------------------

def get_all_running_config():
    """Fetch all running configuration as a JSON string via ``show``."""
    command = ["show", "runningconfiguration", "all"]
    proc = subprocess.Popen(command, text=True, stdout=subprocess.PIPE)
    all_running_config, _ = proc.communicate()
    if proc.returncode:
        raise GenericConfigUpdaterError(
            f"Fetch all runningconfiguration failed with rc={proc.returncode}"
        )
    return all_running_config


# ---------------------------------------------------------------------------
# Patch pre-processing helpers
# ---------------------------------------------------------------------------

def filter_duplicate_patch_operations(patch_ops, all_running_config):
    """Remove leaf-list ``add`` ops that would create duplicate entries."""
    if not any(op.get("path", "").endswith("/-") for op in patch_ops):
        return patch_ops

    config = (
        json.loads(all_running_config)
        if isinstance(all_running_config, str)
        else all_running_config
    )

    patch_copy = jsonpatch.JsonPatch([copy.deepcopy(op) for op in patch_ops])
    all_target_config = patch_copy.apply(config)

    def _find_duplicate_entries(cfg):
        duplicates = {}

        def _check(obj, path=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    _check(v, f"{path}/{k}" if path else f"/{k}")
            elif isinstance(obj, list):
                seen, dups = set(), set()
                for item in obj:
                    (dups if item in seen else seen).add(item)
                if dups:
                    duplicates[path] = list(dups)
                for idx, item in enumerate(obj):
                    _check(item, f"{path}[{idx}]")

        _check(cfg)
        return duplicates

    dups = _find_duplicate_entries(all_target_config)
    if not dups:
        return patch_ops

    ops_to_remove = set()
    for list_path, dup_values in dups.items():
        for op_idx, op in enumerate(patch_ops):
            if (
                op.get("op") == "add"
                and op.get("path", "").endswith("/-")
                and op.get("path").startswith(list_path)
                and op.get("value") in dup_values
            ):
                ops_to_remove.add(op_idx)

    return [op for idx, op in enumerate(patch_ops) if idx not in ops_to_remove]


def append_emptytables_if_required(patch_ops, all_running_config):
    """Insert ``add`` ops for missing top-level tables before the first
    reference to each table so that subsequent ops don't fail."""
    config = (
        json.loads(all_running_config)
        if isinstance(all_running_config, str)
        else all_running_config
    )
    missing_tables = set()
    patch_ops_copy = [copy.deepcopy(op) for op in patch_ops]

    for operation in patch_ops_copy:
        if 'path' not in operation:
            continue
        path_parts = operation['path'].strip('/').split('/')
        if not path_parts:
            continue

        if path_parts[0].startswith('asic') or path_parts[0] == HOST_NAMESPACE:
            if len(path_parts) < 2:
                continue
            table_path = f"/{path_parts[0]}/{path_parts[1]}"
        else:
            table_path = f"/{path_parts[0]}"

        try:
            jsonpointer.resolve_pointer(config, table_path)
        except jsonpointer.JsonPointerException:
            missing_tables.add(table_path)

    if not missing_tables:
        return patch_ops_copy

    for table in missing_tables:
        insert_idx = None
        for idx, op in enumerate(patch_ops_copy):
            if 'path' in op and op['path'].startswith(table):
                insert_idx = idx
                break
        empty_table_patch = {"op": "add", "path": table, "value": {}}
        if insert_idx is not None:
            patch_ops_copy.insert(insert_idx, empty_table_patch)
        else:
            patch_ops_copy.append(empty_table_patch)

    return patch_ops_copy


# ---------------------------------------------------------------------------
# Full YANG validation of a patch against running config
# ---------------------------------------------------------------------------

def validate_patch(patch_ops, all_running_config):
    """Simulate applying *patch_ops* to *all_running_config* and validate
    the result against YANG models.  Returns ``True`` on success.

    Raises ``GenericConfigUpdaterError`` on unexpected failures.
    """
    try:
        from sonic_yang_cfg_generator import SonicYangCfgDbGenerator
    except ImportError:
        # In environments without sonic_yang_cfg_generator (e.g. minimal
        # standalone venv), skip YANG validation.
        logger.warning(
            "sonic_yang_cfg_generator not available; skipping YANG validation"
        )
        return True

    try:
        config = (
            json.loads(all_running_config)
            if isinstance(all_running_config, str)
            else all_running_config
        )
        patch_copy = jsonpatch.JsonPatch(
            [copy.deepcopy(op) for op in patch_ops]
        )
        all_target_config = patch_copy.apply(config)

        target_config = (
            all_target_config.pop(HOST_NAMESPACE)
            if multi_asic.is_multi_asic()
            else all_target_config
        )
        target_config.pop("bgpraw", None)
        if not SonicYangCfgDbGenerator().validate_config_db_json(
            target_config
        ):
            return False

        if multi_asic.is_multi_asic():
            for asic in multi_asic.get_namespace_list():
                target_config = all_target_config.pop(asic)
                target_config.pop("bgpraw", None)
                if not SonicYangCfgDbGenerator().validate_config_db_json(
                    target_config
                ):
                    return False

        return True
    except Exception as e:
        raise GenericConfigUpdaterError(
            f"Validate json patch: {patch_ops} failed due to: {e}"
        )


# ---------------------------------------------------------------------------
# Per-scope dispatch
# ---------------------------------------------------------------------------

def apply_patch_for_scope(scope_changes, results, config_format,
                          verbose, dry_run,
                          ignore_non_yang_tables, ignore_path):
    """Apply a patch for a single ASIC scope and record the outcome in
    *results* (a shared dict)."""
    scope, changes = scope_changes
    if scope.lower() == HOST_NAMESPACE or scope == "":
        scope = multi_asic.DEFAULT_NAMESPACE

    scope_for_log = scope if scope else HOST_NAMESPACE
    thread_id = threading.get_ident()
    logger.info(
        "apply_patch_for_scope started for %s with %d changes in thread %s",
        scope_for_log, len(changes), thread_id,
    )

    try:
        GenericUpdater(scope=scope).apply_patch(
            jsonpatch.JsonPatch(changes),
            config_format,
            verbose,
            dry_run,
            ignore_non_yang_tables,
            ignore_path,
        )
        results[scope_for_log] = {"success": True, "message": "Success"}
        logger.info("apply-patch succeeded for %s", scope_for_log)
    except Exception as e:
        results[scope_for_log] = {"success": False, "message": str(e)}
        logger.error("apply-patch failed for %s: %s", scope_for_log, e)


def _apply_patch_wrapper(args):
    """Thin wrapper so ``ThreadPoolExecutor.submit`` can unpack a tuple."""
    return apply_patch_for_scope(*args)


# ---------------------------------------------------------------------------
# Top-level apply-patch orchestrator
# ---------------------------------------------------------------------------

def apply_patch_from_file(patch_file_path, config_format_name, verbose,
                          dry_run, parallel, ignore_non_yang_tables,
                          ignore_path, preprocess=True):
    """Read a JSON-Patch file and apply it — the single implementation
    used by all entry points.

    Parameters
    ----------
    patch_file_path : str
        Path to the JSON-Patch file.
    config_format_name : str
        ``"CONFIGDB"`` or ``"SONICYANG"``.
    verbose : bool
    dry_run : bool
    parallel : bool
        If *True*, apply per-ASIC changes in parallel threads.
    ignore_non_yang_tables : bool
    ignore_path : tuple/list of str
    preprocess : bool
        When *True* (default), fetch running config and run
        ``append_emptytables_if_required``, ``filter_duplicate_patch_operations``
        and ``validate_patch``.  Callers that already performed these steps
        (or intentionally want to skip them) can pass *False*.

    Raises
    ------
    GenericConfigUpdaterError
        On validation failure or any per-scope failure.
    """
    # 1. Read & validate patch file
    with open(patch_file_path, 'r') as fh:
        patch_json = json.loads(fh.read())

    if not validate_patch_format(patch_json):
        raise GenericConfigUpdaterError(
            f"Invalid patch format in file: {patch_file_path}"
        )

    patch_ops = patch_json
    config_format = ConfigFormat[config_format_name.upper()]

    # 2. Optional pre-processing (running-config fetch + YANG validation)
    if preprocess:
        all_running_config = get_all_running_config()
        patch_ops = append_emptytables_if_required(
            patch_ops, all_running_config
        )
        patch_ops = filter_duplicate_patch_operations(
            patch_ops, all_running_config
        )
        if not validate_patch(patch_ops, all_running_config):
            raise GenericConfigUpdaterError(
                f"Failed validating patch: {patch_ops}"
            )

    # 3. Build a JsonPatch and split by scope
    patch = jsonpatch.JsonPatch(patch_ops)
    changes_by_scope = {}

    for change in patch:
        scope, modified_path = extract_scope(change["path"])
        change["path"] = modified_path
        changes_by_scope.setdefault(scope, []).append(change)

    # Empty case — still force YANG validation per scope
    if not changes_by_scope:
        asic_list = [multi_asic.DEFAULT_NAMESPACE]
        if multi_asic.is_multi_asic():
            asic_list.extend(multi_asic.get_namespace_list())
        for asic in asic_list:
            changes_by_scope[asic] = []

    # 4. Dispatch
    results = {}
    if parallel:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            arguments = [
                (sc, results, config_format, verbose, dry_run,
                 ignore_non_yang_tables, ignore_path)
                for sc in changes_by_scope.items()
            ]
            futures = [
                executor.submit(_apply_patch_wrapper, arg)
                for arg in arguments
            ]
            concurrent.futures.wait(futures)
    else:
        for scope_changes in changes_by_scope.items():
            apply_patch_for_scope(
                scope_changes, results, config_format,
                verbose, dry_run, ignore_non_yang_tables, ignore_path,
            )

    # 5. Aggregate results
    failures = [s for s, r in results.items() if not r['success']]
    if failures:
        msgs = '\n'.join(
            f"- {s}: {results[s]['message']}" for s in failures
        )
        raise GenericConfigUpdaterError(
            f"Failed to apply patch on the following scopes:\n{msgs}"
        )


# ---------------------------------------------------------------------------
# Helper utilities (used by scripts/gcu.py and the gcu-standalone entry point)
# ---------------------------------------------------------------------------

def multiasic_save_to_singlefile(filename):
    """Save all ASIC configurations to a single file in multi-asic mode."""
    all_configs = {}

    # Get host configuration
    cmd = ["sonic-cfggen", "-d", "--print-data"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    host_config = json.loads(result.stdout)
    all_configs['localhost'] = host_config

    # Get each ASIC configuration
    for namespace in multi_asic.get_namespace_list():
        cmd = ["sonic-cfggen", "-d", "--print-data", "-n", namespace]
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True
        )
        asic_config = json.loads(result.stdout)
        all_configs[namespace] = asic_config

    # Save to file
    with open(filename, 'w') as f:
        json.dump(all_configs, f, indent=2)


def print_error(message):
    """Print error message to stderr."""
    print(f"Error: {message}", file=sys.stderr)


def print_success(message):
    """Print success message."""
    print(message)


# ---------------------------------------------------------------------------
# Sub-command implementations (used by gcu-standalone and scripts/gcu.py)
# ---------------------------------------------------------------------------

def create_checkpoint(args):
    """Create a checkpoint of the current configuration."""
    try:
        if args.verbose:
            print(f"Creating checkpoint: {args.checkpoint_name}")

        updater = GenericUpdater()
        updater.checkpoint(args.checkpoint_name, args.verbose)

        print_success(
            f"Checkpoint '{args.checkpoint_name}' created successfully."
        )
    except Exception as ex:
        print_error(
            f"Failed to create checkpoint '{args.checkpoint_name}': {ex}"
        )
        sys.exit(1)


def delete_checkpoint(args):
    """Delete a checkpoint."""
    try:
        if args.verbose:
            print(f"Deleting checkpoint: {args.checkpoint_name}")

        updater = GenericUpdater()
        updater.delete_checkpoint(args.checkpoint_name, args.verbose)

        print_success(
            f"Checkpoint '{args.checkpoint_name}' deleted successfully."
        )
    except Exception as ex:
        print_error(
            f"Failed to delete checkpoint '{args.checkpoint_name}': {ex}"
        )
        sys.exit(1)


def list_checkpoints(args):
    """List all available checkpoints."""
    try:
        updater = GenericUpdater()
        checkpoints = updater.list_checkpoints(args.time, args.verbose)

        if not checkpoints:
            print("No checkpoints found.")
            return

        if args.time and isinstance(checkpoints[0], dict):
            print("Available checkpoints:")
            for checkpoint in checkpoints:
                print(
                    f"  - {checkpoint['name']} "
                    f"(Last Modified: {checkpoint['time']})"
                )
        else:
            print("Available checkpoints:")
            for checkpoint in checkpoints:
                print(f"  - {checkpoint}")
    except Exception as ex:
        print_error(f"Failed to list checkpoints: {ex}")
        sys.exit(1)


def apply_patch(args):
    """Apply a configuration patch — delegates to apply_patch_from_file."""
    try:
        if args.verbose:
            print(f"Applying patch from: {args.patch_file}")
            print(f"Format: {args.format}")
            if args.dry_run:
                print("** DRY RUN EXECUTION **")

        apply_patch_from_file(
            patch_file_path=args.patch_file,
            config_format_name=args.format,
            verbose=args.verbose,
            dry_run=args.dry_run,
            parallel=args.parallel,
            ignore_non_yang_tables=args.ignore_non_yang_tables,
            ignore_path=args.ignore_path,
            preprocess=False,
        )

        print_success("Patch applied successfully.")
    except Exception as ex:
        print_error(f"Failed to apply patch: {ex}")
        sys.exit(1)


def replace_config(args):
    """Replace the entire configuration with a new configuration."""
    try:
        if args.verbose:
            print(f"Replacing configuration from: {args.config_file}")
            print(f"Format: {args.format}")

        with open(args.config_file, 'r') as f:
            target_config = json.loads(f.read())

        config_format = ConfigFormat[args.format.upper()]
        updater = GenericUpdater()
        updater.replace(
            target_config, config_format, args.verbose, False,
            args.ignore_non_yang_tables, args.ignore_path,
        )

        print_success("Configuration replaced successfully.")
    except Exception as ex:
        print_error(f"Failed to replace configuration: {ex}")
        sys.exit(1)


def save_config(args):
    """Save the current configuration to a file."""
    try:
        filename = args.filename if args.filename else DEFAULT_CONFIG_DB_FILE

        if args.verbose:
            print(f"Saving configuration to: {filename}")

        if multi_asic.is_multi_asic():
            multiasic_save_to_singlefile(filename)
        else:
            cmd = ["sonic-cfggen", "-d", "--print-data"]
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True
            )
            config_to_save = json.loads(result.stdout)
            with open(filename, 'w') as f:
                json.dump(config_to_save, f, indent=2)

        print_success(f"Configuration saved successfully to '{filename}'.")
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to get current configuration: {e}")
        sys.exit(1)
    except Exception as ex:
        print_error(f"Failed to save configuration: {ex}")
        sys.exit(1)


def rollback_config(args):
    """Rollback configuration to a checkpoint."""
    try:
        if args.verbose:
            print(f"Rolling back to checkpoint: {args.checkpoint_name}")

        updater = GenericUpdater()
        updater.rollback(
            args.checkpoint_name, args.verbose, False,
            args.ignore_non_yang_tables, args.ignore_path,
        )

        print_success(
            f"Configuration rolled back to "
            f"'{args.checkpoint_name}' successfully."
        )
    except Exception as ex:
        print_error(
            f"Failed to rollback to checkpoint "
            f"'{args.checkpoint_name}': {ex}"
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Argument parser (shared by gcu-standalone entry point and scripts/gcu.py)
# ---------------------------------------------------------------------------

def build_parser():
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            'GCU - Generic Config Updater for SONiC configuration management'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s create-checkpoint my-checkpoint
  %(prog)s apply-patch patch.json
  %(prog)s apply-patch patch.json --dry-run
  %(prog)s replace config.json
  %(prog)s save backup.json
        """,
    )

    subparsers = parser.add_subparsers(
        dest='command', help='Available commands'
    )

    # ---- create-checkpoint ----
    p = subparsers.add_parser(
        'create-checkpoint',
        help='Create a checkpoint of the current configuration',
    )
    p.add_argument('checkpoint_name', help='Name for the checkpoint')
    p.add_argument(
        '-v', '--verbose', action='store_true',
        help='Print additional details',
    )

    # ---- delete-checkpoint ----
    p = subparsers.add_parser(
        'delete-checkpoint', help='Delete a checkpoint',
    )
    p.add_argument(
        'checkpoint_name', help='Name of the checkpoint to delete',
    )
    p.add_argument(
        '-v', '--verbose', action='store_true',
        help='Print additional details',
    )

    # ---- list-checkpoints ----
    p = subparsers.add_parser(
        'list-checkpoints', help='List all available checkpoints',
    )
    p.add_argument(
        '-t', '--time', action='store_true',
        help='Include last modified time for each checkpoint',
    )
    p.add_argument(
        '-v', '--verbose', action='store_true',
        help='Print additional details',
    )

    # ---- apply-patch ----
    p = subparsers.add_parser(
        'apply-patch', help='Apply a configuration patch',
    )
    p.add_argument('patch_file', help='Path to the JSON patch file')
    p.add_argument(
        '-f', '--format', choices=['CONFIGDB', 'SONICYANG'],
        default='CONFIGDB',
        help='Format of the patch file (default: CONFIGDB)',
    )
    p.add_argument(
        '-v', '--verbose', action='store_true',
        help='Print additional details',
    )
    p.add_argument(
        '-d', '--dry-run', action='store_true', default=False,
        help='Test out the command without affecting config state',
    )
    p.add_argument(
        '-p', '--parallel', action='store_true',
        help='Apply changes to all ASICs in parallel (multi-asic only)',
    )
    p.add_argument(
        '-n', '--ignore-non-yang-tables', action='store_true',
        help='Ignore validation for tables without YANG models',
    )
    p.add_argument(
        '-i', '--ignore-path', action='append', default=[],
        help='Ignore validation for config specified by given path '
             '(JsonPointer)',
    )

    # ---- replace ----
    p = subparsers.add_parser(
        'replace', help='Replace the entire configuration',
    )
    p.add_argument('config_file', help='Path to the configuration file')
    p.add_argument(
        '-f', '--format', choices=['CONFIGDB', 'SONICYANG'],
        default='CONFIGDB',
        help='Format of the configuration file (default: CONFIGDB)',
    )
    p.add_argument(
        '-v', '--verbose', action='store_true',
        help='Print additional details',
    )
    p.add_argument(
        '-n', '--ignore-non-yang-tables', action='store_true',
        help='Ignore validation for tables without YANG models',
    )
    p.add_argument(
        '-i', '--ignore-path', action='append', default=[],
        help='Ignore validation for config specified by given path '
             '(JsonPointer)',
    )

    # ---- save ----
    p = subparsers.add_parser(
        'save', help='Save the current configuration to a file',
    )
    p.add_argument(
        'filename', nargs='?',
        help=f'Output filename (default: {DEFAULT_CONFIG_DB_FILE})',
    )
    p.add_argument(
        '-v', '--verbose', action='store_true',
        help='Print additional details',
    )

    # ---- rollback ----
    p = subparsers.add_parser(
        'rollback', help='Rollback configuration to a checkpoint',
    )
    p.add_argument(
        'checkpoint_name',
        help='Name of the checkpoint to rollback to',
    )
    p.add_argument(
        '-v', '--verbose', action='store_true',
        help='Print additional details',
    )
    p.add_argument(
        '-n', '--ignore-non-yang-tables', action='store_true',
        help='Ignore validation for tables without YANG models',
    )
    p.add_argument(
        '-i', '--ignore-path', action='append', default=[],
        help='Ignore validation for config specified by given path '
             '(JsonPointer)',
    )

    return parser


# ---------------------------------------------------------------------------
# Main entry point (used by gcu-standalone console_scripts)
# ---------------------------------------------------------------------------

def main():
    """Main entry point for the gcu-standalone console script."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Validate file paths if provided
    if hasattr(args, 'patch_file') and args.patch_file:
        if not os.path.exists(args.patch_file):
            print_error(f"Patch file not found: {args.patch_file}")
            sys.exit(1)

    if hasattr(args, 'config_file') and args.config_file:
        if not os.path.exists(args.config_file):
            print_error(f"Config file not found: {args.config_file}")
            sys.exit(1)

    command_functions = {
        'create-checkpoint': create_checkpoint,
        'delete-checkpoint': delete_checkpoint,
        'list-checkpoints': list_checkpoints,
        'apply-patch': apply_patch,
        'replace': replace_config,
        'save': save_config,
        'rollback': rollback_config,
    }

    if args.command in command_functions:
        command_functions[args.command](args)
    else:
        print_error(f"Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()

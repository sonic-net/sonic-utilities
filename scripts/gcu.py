#!/usr/bin/env python3

"""
Generic Config Updater (GCU) Script
Provides APIs for configuration management in SONiC:
1. Create checkpoint
2. Delete checkpoint
3. Config apply-patch
4. Config replace
5. Config save
"""

import os
import sys
import json
import argparse
import jsonpatch
import subprocess
import concurrent.futures

# Add the parent directory to Python path to import sonic-utilities modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from generic_config_updater.generic_updater import GenericUpdater, ConfigFormat, extract_scope
    from generic_config_updater.gu_common import GenericConfigUpdaterError, HOST_NAMESPACE
    from sonic_py_common import multi_asic
except ImportError as e:
    print(f"Error importing required modules: {e}", file=sys.stderr)
    sys.exit(1)

# Constants
DEFAULT_CONFIG_DB_FILE = '/etc/sonic/config_db.json'


def print_error(message):
    """Print error message to stderr"""
    print(f"Error: {message}", file=sys.stderr)


def print_success(message):
    """Print success message"""
    print(message)


def print_warning(message):
    """Print warning message"""
    print(f"Warning: {message}")


def print_info(message):
    """Print info message"""
    print(f"Info: {message}")


def validate_patch(patch):
    """Validate that the patch is properly formatted"""
    try:
        if not isinstance(patch, list):
            return False

        for change in patch:
            if not isinstance(change, dict):
                return False
            if 'op' not in change or 'path' not in change:
                return False
            if change['op'] not in ['add', 'remove', 'replace', 'move', 'copy', 'test']:
                return False
        return True
    except Exception:
        return False


def multiasic_save_to_singlefile(filename):
    """Save all ASIC configurations to a single file in multi-asic mode"""
    all_configs = {}

    # Get host configuration
    cmd = ["sonic-cfggen", "-d", "--print-data"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    host_config = json.loads(result.stdout)
    all_configs['localhost'] = host_config

    # Get each ASIC configuration
    for namespace in multi_asic.get_namespace_list():
        cmd = ["sonic-cfggen", "-d", "--print-data", "-n", namespace]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        asic_config = json.loads(result.stdout)
        all_configs[namespace] = asic_config

    # Save to file
    with open(filename, 'w') as f:
        json.dump(all_configs, f, indent=2)


def apply_patch_for_scope(scope_changes, results, config_format, verbose, dry_run, ignore_non_yang_tables, ignore_path):
    """Apply patch for a single ASIC scope"""
    scope, changes = scope_changes
    # Replace localhost to DEFAULT_NAMESPACE which is db definition of Host
    if scope.lower() == HOST_NAMESPACE or scope == "":
        scope = multi_asic.DEFAULT_NAMESPACE

    scope_for_log = scope if scope else HOST_NAMESPACE

    try:
        # Call apply_patch with the ASIC-specific changes
        GenericUpdater(scope=scope).apply_patch(jsonpatch.JsonPatch(changes),
                                                config_format,
                                                verbose,
                                                dry_run,
                                                ignore_non_yang_tables,
                                                ignore_path)
        results[scope_for_log] = {"success": True, "message": "Success"}
    except Exception as e:
        results[scope_for_log] = {"success": False, "message": str(e)}


def apply_patch_wrapper(args):
    """Wrapper for apply_patch_for_scope to support ThreadPoolExecutor"""
    return apply_patch_for_scope(*args)


def create_checkpoint(args):
    """Create a checkpoint of the current configuration"""
    try:
        if args.verbose:
            print(f"Creating checkpoint: {args.checkpoint_name}")

        # Use GenericUpdater to create checkpoint
        updater = GenericUpdater()
        updater.checkpoint(args.checkpoint_name, args.verbose)

        print_success(f"Checkpoint '{args.checkpoint_name}' created successfully.")

    except Exception as ex:
        print_error(f"Failed to create checkpoint '{args.checkpoint_name}': {ex}")
        sys.exit(1)


def delete_checkpoint(args):
    """Delete a checkpoint"""
    try:
        if args.verbose:
            print(f"Deleting checkpoint: {args.checkpoint_name}")

        # Use GenericUpdater to delete checkpoint
        updater = GenericUpdater()
        updater.delete_checkpoint(args.checkpoint_name, args.verbose)

        print_success(f"Checkpoint '{args.checkpoint_name}' deleted successfully.")

    except Exception as ex:
        print_error(f"Failed to delete checkpoint '{args.checkpoint_name}': {ex}")
        sys.exit(1)


def list_checkpoints(args):
    """List all available checkpoints"""
    try:
        updater = GenericUpdater()
        checkpoints = updater.list_checkpoints(args.time, args.verbose)

        if not checkpoints:
            print("No checkpoints found.")
            return

        if args.time and isinstance(checkpoints[0], dict):
            print("Available checkpoints:")
            for checkpoint in checkpoints:
                print(f"  - {checkpoint['name']} (Last Modified: {checkpoint['time']})")
        else:
            print("Available checkpoints:")
            for checkpoint in checkpoints:
                print(f"  - {checkpoint}")

    except Exception as ex:
        print_error(f"Failed to list checkpoints: {ex}")
        sys.exit(1)


def apply_patch(args):
    """Apply a configuration patch"""
    try:
        if args.verbose:
            print(f"Applying patch from: {args.patch_file}")
            print(f"Format: {args.format}")

        # Read and validate patch file
        with open(args.patch_file, 'r') as f:
            patch_content = f.read()
            patch_json = json.loads(patch_content)
            patch = jsonpatch.JsonPatch(patch_json)

        if not validate_patch(patch_json):
            raise GenericConfigUpdaterError(f"Invalid patch format in file: {args.patch_file}")

        config_format = ConfigFormat[args.format.upper()]

        # For multi-asic, extract scope and apply patches per ASIC
        if multi_asic.is_multi_asic():
            results = {}
            changes_by_scope = {}

            # Iterate over each change in the JSON Patch
            for change in patch:
                scope, modified_path = extract_scope(change["path"])

                # Modify the 'path' in the change to remove the scope
                change["path"] = modified_path

                # Check if the scope is already in our dictionary, if not, initialize it
                if scope not in changes_by_scope:
                    changes_by_scope[scope] = []

                # Add the modified change to the appropriate list based on scope
                changes_by_scope[scope].append(change)

            # Empty case to force validate YANG model
            if not changes_by_scope:
                asic_list = [multi_asic.DEFAULT_NAMESPACE]
                asic_list.extend(multi_asic.get_namespace_list())
                for asic in asic_list:
                    changes_by_scope[asic] = []

            # Apply changes for each scope
            if args.parallel:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    # Prepare the argument tuples
                    arguments = [
                        (scope_changes, results, config_format,
                         args.verbose, False, args.ignore_non_yang_tables, args.ignore_path)
                        for scope_changes in changes_by_scope.items()
                    ]

                    # Submit all tasks and wait for them to complete
                    futures = [executor.submit(apply_patch_wrapper, arguments)
                               for arguments in arguments]

                    # Wait for all tasks to complete
                    concurrent.futures.wait(futures)
            else:
                # Apply changes for each scope sequentially
                for scope_changes in changes_by_scope.items():
                    apply_patch_for_scope(scope_changes,
                                          results,
                                          config_format,
                                          args.verbose, False,
                                          args.ignore_non_yang_tables,
                                          args.ignore_path)

            # Check if any updates failed
            failures = [scope for scope, result in results.items() if not result['success']]

            if failures:
                failure_messages = '\n'.join([
                    f"- {failed_scope}: {results[failed_scope]['message']}"
                    for failed_scope in failures
                ])
                raise GenericConfigUpdaterError(
                    f"Failed to apply patch on the following scopes:\n{failure_messages}"
                )
        else:
            # Single ASIC mode - use traditional approach
            updater = GenericUpdater()
            updater.apply_patch(patch, config_format, args.verbose, False,
                                args.ignore_non_yang_tables, args.ignore_path)

        print_success("Patch applied successfully.")

    except Exception as ex:
        print_error(f"Failed to apply patch: {ex}")
        sys.exit(1)


def replace_config(args):
    """Replace the entire configuration with a new configuration"""
    try:
        if args.verbose:
            print(f"Replacing configuration from: {args.config_file}")
            print(f"Format: {args.format}")

        # Read configuration file
        with open(args.config_file, 'r') as f:
            config_content = f.read()
            target_config = json.loads(config_content)

        # Replace configuration using GenericUpdater
        config_format = ConfigFormat[args.format.upper()]
        updater = GenericUpdater()
        updater.replace(target_config, config_format, args.verbose, False,
                        args.ignore_non_yang_tables, args.ignore_path)

        print_success("Configuration replaced successfully.")

    except Exception as ex:
        print_error(f"Failed to replace configuration: {ex}")
        sys.exit(1)


def save_config(args):
    """Save the current configuration to a file"""
    try:
        # Use default filename if not provided
        filename = args.filename if args.filename else DEFAULT_CONFIG_DB_FILE

        if args.verbose:
            print(f"Saving configuration to: {filename}")

        # In multi-asic mode, save all ASIC configurations to single file
        if multi_asic.is_multi_asic():
            multiasic_save_to_singlefile(filename)
            print_success(f"Configuration saved successfully to '{filename}'.")
        else:
            # Single ASIC configuration
            cmd = ["sonic-cfggen", "-d", "--print-data"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            config_to_save = json.loads(result.stdout)

            # Save to file
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
    """Rollback configuration to a checkpoint"""
    try:
        if args.verbose:
            print(f"Rolling back to checkpoint: {args.checkpoint_name}")

        # Rollback using GenericUpdater
        updater = GenericUpdater()
        updater.rollback(args.checkpoint_name, args.verbose, False,
                         args.ignore_non_yang_tables, args.ignore_path)

        print_success(f"Configuration rolled back to '{args.checkpoint_name}' successfully.")

    except Exception as ex:
        print_error(f"Failed to rollback to checkpoint '{args.checkpoint_name}': {ex}")
        sys.exit(1)


def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(
        description='Generic Config Updater (GCU) - Configuration Management Tool for SONiC',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This tool provides configuration management capabilities including:
- Creating and managing checkpoints
- Applying configuration patches
- Replacing entire configurations
- Saving current configuration

Examples:
  %(prog)s create-checkpoint my-checkpoint
  %(prog)s apply-patch patch.json
  %(prog)s replace config.json
  %(prog)s save backup.json
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Create checkpoint command
    create_parser = subparsers.add_parser(
        'create-checkpoint',
        help='Create a checkpoint of the current configuration'
    )
    create_parser.add_argument(
        'checkpoint_name',
        help='Name for the checkpoint'
    )
    create_parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Print additional details of what the operation is doing'
    )

    # Delete checkpoint command
    delete_parser = subparsers.add_parser(
        'delete-checkpoint',
        help='Delete a checkpoint'
    )
    delete_parser.add_argument(
        'checkpoint_name',
        help='Name of the checkpoint to delete'
    )
    delete_parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Print additional details of what the operation is doing'
    )

    # List checkpoints command
    list_parser = subparsers.add_parser(
        'list-checkpoints',
        help='List all available checkpoints'
    )
    list_parser.add_argument(
        '-t', '--time',
        action='store_true',
        help='Include last modified time for each checkpoint'
    )
    list_parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Print additional details of what the operation is doing'
    )

    # Apply patch command
    apply_parser = subparsers.add_parser(
        'apply-patch',
        help='Apply a configuration patch'
    )
    apply_parser.add_argument(
        'patch_file',
        help='Path to the JSON patch file'
    )
    apply_parser.add_argument(
        '-f', '--format',
        choices=['CONFIGDB', 'SONICYANG'],
        default='CONFIGDB',
        help='Format of the patch file (default: CONFIGDB)'
    )
    apply_parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Print additional details of what the operation is doing'
    )
    apply_parser.add_argument(
        '-p', '--parallel',
        action='store_true',
        help='Apply changes to all ASICs in parallel (multi-asic only)'
    )
    apply_parser.add_argument(
        '--ignore-non-yang-tables',
        action='store_true',
        help='Ignore validation for tables without YANG models'
    )
    apply_parser.add_argument(
        '--ignore-path',
        action='append',
        default=[],
        help='Ignore validation for config specified by given path (JsonPointer)'
    )

    # Replace config command
    replace_parser = subparsers.add_parser(
        'replace',
        help='Replace the entire configuration with a new configuration'
    )
    replace_parser.add_argument(
        'config_file',
        help='Path to the configuration file'
    )
    replace_parser.add_argument(
        '-f', '--format',
        choices=['CONFIGDB', 'SONICYANG'],
        default='CONFIGDB',
        help='Format of the configuration file (default: CONFIGDB)'
    )
    replace_parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Print additional details of what the operation is doing'
    )
    replace_parser.add_argument(
        '--ignore-non-yang-tables',
        action='store_true',
        help='Ignore validation for tables without YANG models'
    )
    replace_parser.add_argument(
        '--ignore-path',
        action='append',
        default=[],
        help='Ignore validation for config specified by given path (JsonPointer)'
    )

    # Save config command
    save_parser = subparsers.add_parser(
        'save',
        help='Save the current configuration to a file'
    )
    save_parser.add_argument(
        'filename',
        nargs='?',
        help=f'Output filename (default: {DEFAULT_CONFIG_DB_FILE})'
    )
    save_parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Print additional details of what the operation is doing'
    )

    # Rollback config command
    rollback_parser = subparsers.add_parser(
        'rollback',
        help='Rollback configuration to a checkpoint'
    )
    rollback_parser.add_argument(
        'checkpoint_name',
        help='Name of the checkpoint to rollback to'
    )
    rollback_parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Print additional details of what the operation is doing'
    )
    rollback_parser.add_argument(
        '--ignore-non-yang-tables',
        action='store_true',
        help='Ignore validation for tables without YANG models'
    )
    rollback_parser.add_argument(
        '--ignore-path',
        action='append',
        default=[],
        help='Ignore validation for config specified by given path (JsonPointer)'
    )

    # Parse arguments
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

    # Execute the appropriate command
    command_functions = {
        'create-checkpoint': create_checkpoint,
        'delete-checkpoint': delete_checkpoint,
        'list-checkpoints': list_checkpoints,
        'apply-patch': apply_patch,
        'replace': replace_config,
        'save': save_config,
        'rollback': rollback_config
    }

    if args.command in command_functions:
        command_functions[args.command](args)
    else:
        print_error(f"Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()

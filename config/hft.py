import json
import os
import tempfile

import click

TEMP_FILE_PREFIX = "config-hft-"
TEMP_FILE_SUFFIX = ".json"

DEFAULT_STREAM_STATE = "disabled"
STREAM_STATE_CHOICES = ("enabled", "disabled")
DEFAULT_POLL_INTERVAL_USEC = 10000  # microseconds
GROUP_TYPE_CHOICES = ("PORT", "BUFFER_POOL", "INGRESS_PRIORITY_GROUP", "QUEUE")

PROFILE_TABLE_NAME = "HIGH_FREQUENCY_TELEMETRY_PROFILE"
GROUP_TABLE_NAME = "HIGH_FREQUENCY_TELEMETRY_GROUP"
HARMONIZER_TABLE_NAME = "HIGH_FREQUENCY_TELEMETRY_HARMONIZER"
PROFILE_TABLE_PATH = f"/{PROFILE_TABLE_NAME}"
GROUP_TABLE_PATH = f"/{GROUP_TABLE_NAME}"
HARMONIZER_TABLE_PATH = f"/{HARMONIZER_TABLE_NAME}"
STREAM_STATE_FIELD = "stream_state"


@click.group(name='hft', short_help="Manage high frequency telemetry")
def hft():
    """Top-level command group for HFT operations."""


@hft.command('enable', short_help="Enable an HFT stream for a profile")
@click.argument('profile_name')
@click.pass_context
def hft_enable(ctx, profile_name):
    """Enable the telemetry stream defined by a profile."""
    payload = _build_stream_state_patch(profile_name, "enabled")
    _process_payload(ctx, payload)


@hft.command('disable', short_help="Disable an HFT stream for a profile")
@click.argument('profile_name')
@click.pass_context
def hft_disable(ctx, profile_name):
    """Disable the telemetry stream defined by a profile."""
    payload = _build_stream_state_patch(profile_name, "disabled")
    _process_payload(ctx, payload)


@hft.command('bind-harmonizer', short_help="Bind a harmonizer to an HFT profile")
@click.argument('profile_name')
@click.argument('harmonizer_name')
@click.pass_context
def hft_bind_harmonizer(ctx, profile_name, harmonizer_name):
    """Bind an existing harmonizer to an HFT profile."""
    payload = _build_profile_field_patch(profile_name, "harmonizer", harmonizer_name)
    _process_payload(ctx, payload)


@hft.command('unbind-harmonizer', short_help="Unbind the harmonizer from an HFT profile")
@click.argument('profile_name')
@click.pass_context
def hft_unbind_harmonizer(ctx, profile_name):
    """Remove the harmonizer binding from an HFT profile."""
    payload = _build_profile_field_remove_patch(profile_name, "harmonizer")
    _process_payload(ctx, payload)


@hft.group('add', short_help="Add HFT resources")
def hft_add():
    """Group of add operations for HFT."""


@hft_add.command('profile', short_help="Add or update an HFT profile")
@click.argument('profile_name')
@click.option('--stream_state', 'stream_state', default=DEFAULT_STREAM_STATE,
              type=click.Choice(STREAM_STATE_CHOICES), show_default=True,
              help='Desired stream state for this profile.')
@click.option('--poll_interval', 'poll_interval', default=DEFAULT_POLL_INTERVAL_USEC,
              type=click.IntRange(min=0), show_default=True,
              help='Polling interval in microseconds.')
@click.option('--harmonizer', 'harmonizer', default=None,
              help='Optional harmonizer name to apply to this profile.')
@click.pass_context
def hft_add_profile(ctx, profile_name, stream_state, poll_interval, harmonizer):
    """Create a profile entry for HFT."""
    if _has_existing_profile(ctx):
        click.echo(
            "A profile already exists; this version supports only one profile. "
            "Delete the existing profile before adding another."
        )
        ctx.exit(1)

    attributes = {
        "stream_state": stream_state,
        "poll_interval": str(poll_interval),
    }
    if harmonizer:
        attributes["harmonizer"] = harmonizer

    profile_payload = _build_profile_patch(
        op="add",
        profile_name=profile_name,
        attributes=attributes
    )
    _process_payload(ctx, profile_payload)


@hft_add.command('group', short_help="Add an HFT group to a profile")
@click.argument('profile_name')
@click.option('--group_type', 'group_type', type=click.Choice(GROUP_TYPE_CHOICES),
              required=True, help='Telemetry group type.')
@click.option('--object_names', 'object_names', required=True,
              help='Comma-separated list of object names.')
@click.option('--object_counters', 'object_counters', required=True,
              help='Comma-separated list of counters to collect.')
@click.pass_context
def hft_add_group(ctx, profile_name, group_type, object_names, object_counters):
    """Create a group definition under an HFT profile."""
    group_payload = _build_group_patch(
        op="add",
        profile_name=profile_name,
        group_type=group_type,
        attributes={
            "object_names": _split_csv_items(object_names),
            "object_counters": _split_csv_items(object_counters),
        }
    )
    _process_payload(ctx, group_payload)


@hft_add.command('harmonizer', short_help="Add an HFT harmonizer")
@click.argument('harmonizer_name')
@click.option('--reporting_rate', 'reporting_rate', default=None,
              type=click.IntRange(min=0), help='Reporting interval after harmonization in microseconds.')
@click.option('--rollover_counters', 'rollover_counters', default=None,
              help='Comma-separated list of GROUP|COUNTER entries requiring rollover correction.')
@click.option('--heatmap_counters', 'heatmap_counters', default=None,
              help='Comma-separated list of GROUP|COUNTER entries treated as heatmap data.')
@click.pass_context
def hft_add_harmonizer(ctx, harmonizer_name, reporting_rate, rollover_counters, heatmap_counters):
    """Create a harmonizer definition for HFT."""
    attributes = {}
    if reporting_rate is not None:
        attributes["reporting_rate"] = str(reporting_rate)
    if rollover_counters is not None:
        attributes["rollover_counters"] = _split_csv_items(rollover_counters)
    if heatmap_counters is not None:
        attributes["heatmap_counters"] = _split_csv_items(heatmap_counters)

    harmonizer_payload = _build_harmonizer_patch(
        op="add",
        harmonizer_name=harmonizer_name,
        attributes=attributes
    )
    _process_payload(ctx, harmonizer_payload)


@hft.group('del', short_help="Remove HFT resources")
def hft_delete():
    """Group of delete operations for HFT."""


@hft_delete.command('profile', short_help="Delete an HFT profile")
@click.argument('profile_name')
@click.pass_context
def hft_delete_profile(ctx, profile_name):
    """Remove an existing HFT profile."""
    remove_entire_table = _is_last_entry(ctx, PROFILE_TABLE_NAME)
    profile_payload = _build_profile_remove_patch(profile_name, remove_entire_table)
    _process_payload(ctx, profile_payload)


@hft_delete.command('group', short_help="Delete an HFT group from a profile")
@click.argument('profile_name')
@click.argument('group_type', type=click.Choice(GROUP_TYPE_CHOICES))
@click.pass_context
def hft_delete_group(ctx, profile_name, group_type):
    """Remove a group definition from an HFT profile."""
    remove_entire_table = _is_last_entry(ctx, GROUP_TABLE_NAME)
    group_payload = _build_group_remove_patch(profile_name, group_type, remove_entire_table)
    _process_payload(ctx, group_payload)


@hft_delete.command('harmonizer', short_help="Delete an HFT harmonizer")
@click.argument('harmonizer_name')
@click.pass_context
def hft_delete_harmonizer(ctx, harmonizer_name):
    """Remove an existing HFT harmonizer."""
    profile_users = _get_harmonizer_users(ctx, harmonizer_name)
    if profile_users:
        click.echo(
            "Cannot delete harmonizer '{}'; it is still referenced by HFT profile(s): {}".format(
                harmonizer_name,
                ', '.join(profile_users)
            )
        )
        ctx.exit(1)

    remove_entire_table = _is_last_entry(ctx, HARMONIZER_TABLE_NAME)
    harmonizer_payload = _build_harmonizer_remove_patch(harmonizer_name, remove_entire_table)
    _process_payload(ctx, harmonizer_payload)


def _process_payload(ctx, payload):
    """Serialize JSON Patch ops, run apply-patch with defaults, and clean up."""
    tmp_file_path = None
    try:
        tmp_file_path = _materialize_payload(payload)
        _invoke_apply_patch_with_defaults(ctx, tmp_file_path)
    finally:
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)


def _invoke_apply_patch_with_defaults(ctx, patch_file_path):
    """Invoke apply-patch while honoring its default option values."""
    root_ctx = ctx.find_root()
    apply_patch_cmd = root_ctx.command.commands.get('apply-patch')
    if apply_patch_cmd is None:
        ctx.fail("apply-patch command is unavailable")

    defaults = {}
    for param in apply_patch_cmd.params:
        if isinstance(param, click.Argument):
            continue
        defaults[param.name] = param.get_default(root_ctx)

    root_ctx.invoke(apply_patch_cmd, patch_file_path=patch_file_path, **defaults)


def _materialize_payload(payload):
    """Persist payload into a unique temporary file."""
    fd, tmp_path = tempfile.mkstemp(prefix=TEMP_FILE_PREFIX, suffix=TEMP_FILE_SUFFIX,
                                    dir=tempfile.gettempdir())
    with os.fdopen(fd, 'w', encoding='utf-8') as tmp_file:
        json.dump(payload, tmp_file, indent=4)
        tmp_file.flush()
        os.fsync(tmp_file.fileno())
    return tmp_path


def _split_csv_items(value):
    """Split a comma-separated string into a normalized list."""
    if not value:
        return []
    return [item.strip() for item in value.split(',') if item.strip()]


def _build_profile_patch(op, profile_name, attributes):
    """Construct a JSON Patch entry targeting the profile table."""
    return [
        _build_patch_entry(op, PROFILE_TABLE_PATH, {
            profile_name: attributes
        })
    ]


def _build_group_patch(op, profile_name, group_type, attributes):
    """Construct a JSON Patch entry targeting the group table."""
    return [
        _build_patch_entry(op, GROUP_TABLE_PATH, {
            _compose_group_key(profile_name, group_type): attributes
        })
    ]


def _build_harmonizer_patch(op, harmonizer_name, attributes):
    """Construct a JSON Patch entry targeting the harmonizer table."""
    return [
        _build_patch_entry(op, HARMONIZER_TABLE_PATH, {
            harmonizer_name: attributes
        })
    ]


def _build_stream_state_patch(profile_name, state):
    """Construct a JSON Patch entry to update a profile stream state."""
    return _build_profile_field_patch(profile_name, STREAM_STATE_FIELD, state)


def _build_profile_field_patch(profile_name, field_name, value):
    """Construct a JSON Patch entry to update a profile field."""
    path = _join_pointer(
        _join_pointer(PROFILE_TABLE_PATH, profile_name),
        field_name
    )
    return [
        {
            "op": "add",
            "path": path,
            "value": value,
        }
    ]


def _build_profile_field_remove_patch(profile_name, field_name):
    """Construct a JSON Patch entry to remove a profile field."""
    path = _join_pointer(
        _join_pointer(PROFILE_TABLE_PATH, profile_name),
        field_name
    )
    return [_build_remove_entry(path)]


def _build_profile_remove_patch(profile_name, remove_entire_table):
    """Create a remove operation for a profile or the entire table if requested."""
    if remove_entire_table:
        return [_build_remove_entry(PROFILE_TABLE_PATH)]
    return [_build_remove_entry(_join_pointer(PROFILE_TABLE_PATH, profile_name))]


def _build_group_remove_patch(profile_name, group_type, remove_entire_table):
    """Create a remove operation for a group entry or the entire table if requested."""
    if remove_entire_table:
        return [_build_remove_entry(GROUP_TABLE_PATH)]
    return [
        _build_remove_entry(
            _join_pointer(GROUP_TABLE_PATH, _compose_group_key(profile_name, group_type))
        )
    ]


def _build_harmonizer_remove_patch(harmonizer_name, remove_entire_table):
    """Create a remove operation for a harmonizer or the entire table if requested."""
    if remove_entire_table:
        return [_build_remove_entry(HARMONIZER_TABLE_PATH)]
    return [_build_remove_entry(_join_pointer(HARMONIZER_TABLE_PATH, harmonizer_name))]


def _build_patch_entry(op, path, value):
    """Wrap a JSON Patch add/replace entry."""
    return {
        "op": op,
        "path": path,
        "value": value,
    }


def _build_remove_entry(path):
    """Wrap a JSON Patch remove entry."""
    return {
        "op": "remove",
        "path": path,
    }


def _compose_group_key(profile_name, group_type):
    """Compose the key used by the HFT group table."""
    return f"{profile_name}|{group_type}"


def _join_pointer(base_path, key):
    """Join a base JSON Pointer path with an escaped key."""
    separator = "" if base_path.endswith('/') else '/'
    return f"{base_path}{separator}{_escape_json_pointer(key)}"


def _escape_json_pointer(component):
    """Escape JSON Pointer special characters in a component."""
    return component.replace('~', '~0').replace('/', '~1')


def _is_last_entry(ctx, table_name):
    """Return True if the CFG table has zero or one entries."""
    cfgdb = _get_cfgdb(ctx)
    if cfgdb is None:
        return False
    try:
        entries = cfgdb.get_table(table_name)
    except Exception:
        return False
    return len(entries) <= 1


def _get_cfgdb(ctx):
    """Access the Config DB connector stored on the root context."""
    root_ctx = ctx.find_root()
    db = getattr(root_ctx, 'obj', None)
    if db is None:
        return None
    return getattr(db, 'cfgdb', None)


def _has_existing_profile(ctx):
    """Return True when at least one HFT profile already exists."""
    cfgdb = _get_cfgdb(ctx)
    if cfgdb is None:
        return False
    try:
        entries = cfgdb.get_table(PROFILE_TABLE_NAME) or {}
    except Exception:
        return False
    return bool(entries)


def _get_harmonizer_users(ctx, harmonizer_name):
    """Return profile names that reference the given harmonizer."""
    cfgdb = _get_cfgdb(ctx)
    if cfgdb is None:
        return []
    try:
        profiles = cfgdb.get_table(PROFILE_TABLE_NAME) or {}
    except Exception:
        return []

    users = []
    for profile_name, attributes in profiles.items():
        if isinstance(attributes, dict) and attributes.get('harmonizer') == harmonizer_name:
            users.append(profile_name)
    return sorted(users)

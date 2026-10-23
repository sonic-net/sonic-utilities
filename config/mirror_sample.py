"""Per-port sampled ERSPAN configuration commands."""
import click
import jsonpatch

from jsonpointer import JsonPointer
from sonic_py_common import device_info
from swsscommon.swsscommon import SonicV2Connector

from generic_config_updater.generic_updater import GenericUpdater, ConfigFormat
from generic_config_updater.gu_common import GenericConfigUpdaterError
from utilities_common import cli as clicommon
from utilities_common import port_mirror


def source_database(ctx, databases, port, removing=False):
    """Resolve a physical port or logical PortChannel in front-end namespaces."""
    candidates = []
    front = {ns: db for ns, db in databases.items() if ns} or databases
    for namespace, database in front.items():
        ports = database.get_table('PORT')
        channels = database.get_table('PORTCHANNEL')
        stored_source = removing and any(
            port_mirror.binding_key(key)[0] == port
            for key in database.get_keys(port_mirror.SAMPLE_TABLE))
        if port in ports or port in channels or stored_source:
            candidates.append((namespace, database, port))
        elif clicommon.get_interface_naming_mode() == 'alias':
            candidates.extend((namespace, database, name) for name, entry in ports.items()
                              if entry.get('alias') == port)
    if len(candidates) != 1:
        ctx.fail(f'Source interface {port} must identify one physical port or PortChannel '
                 'in a front-end ASIC namespace.')
    return candidates[0]


def validate_capabilities(ctx, namespace, directions, truncate_size):
    """Allow absent discovery fields, but report STATE_DB access failures."""
    try:
        state_db = SonicV2Connector(use_unix_socket_path=True, namespace=namespace)
        state_db.connect(state_db.STATE_DB, False)
        fields = [('rx', 'PORT_INGRESS_SAMPLE_MIRROR_CAPABLE'),
                  ('tx', 'PORT_EGRESS_SAMPLE_MIRROR_CAPABLE')]
        unsupported = [direction for direction, field in fields
                       if direction in directions and
                       state_db.get(state_db.STATE_DB, 'SWITCH_CAPABILITY|switch', field) == 'false']
        truncation_unsupported = truncate_size is not None and state_db.get(
            state_db.STATE_DB, 'SWITCH_CAPABILITY|switch', 'SAMPLEPACKET_TRUNCATION_CAPABLE') == 'false'
    except Exception as error:
        ctx.fail(f'Unable to read sampled mirror capabilities: {error}')
    if unsupported:
        ctx.fail(f"Sampled mirror direction '{unsupported[0]}' is not supported by the ASIC")
    if truncation_unsupported:
        ctx.fail('Sampled mirror truncation is not supported by the ASIC')


def validate_source_overlap(ctx, database, port, directions):
    """Prevent a logical LAG and its members from owning the same attachment."""
    members = [port_mirror.binding_key(key) for key in database.get_keys('PORTCHANNEL_MEMBER')]
    physical_ports = {member for lag, member in members if lag == port} or {port}
    for key in database.get_keys(port_mirror.SAMPLE_TABLE):
        source, direction = port_mirror.binding_key(key)
        if direction not in directions:
            continue
        existing_ports = {member for lag, member in members if lag == source} or {source}
        if source == port or physical_ports & existing_ports:
            ctx.fail(f'Sampled mirror binding {source}|{direction} already owns this source/direction. '
                     'Remove the existing binding first.')


def apply_bindings(ctx, database, namespace, entries):
    """Submit both directions together when YANG validation is enabled."""
    try:
        if device_info.is_yang_config_validation_enabled(database):
            current = database.get_table(port_mirror.SAMPLE_TABLE)
            target = dict(current)
            operations = []
            if not current and any(value is not None for _, value in entries):
                operations.append({'op': 'add', 'path': '/' + port_mirror.SAMPLE_TABLE, 'value': {}})
            for key, value in entries:
                path = JsonPointer.from_parts([port_mirror.SAMPLE_TABLE, '|'.join(key)]).path
                if value is None:
                    target.pop(key, None)
                    target.pop('|'.join(key), None)
                    operations.append({'op': 'remove', 'path': path})
                else:
                    target[key] = value
                    operations.append({'op': 'add', 'path': path, 'value': value})
            if not target:
                operations = [{'op': 'remove', 'path': '/' + port_mirror.SAMPLE_TABLE}]
            GenericUpdater(scope=namespace).apply_patch(
                patch=jsonpatch.JsonPatch(operations), config_format=ConfigFormat.CONFIGDB,
                verbose=False, dry_run=False, ignore_non_yang_tables=False,
                ignore_paths=None, sort=True)
        else:
            # All requested keys and references have been checked before this loop.
            for key, value in entries:
                database.set_entry(port_mirror.SAMPLE_TABLE, key, value)
    except (ValueError, jsonpatch.JsonPatchException, GenericConfigUpdaterError) as error:
        ctx.fail(f'Invalid ConfigDB. Error: {error}')


@click.group(cls=clicommon.AbbreviationGroup, name='sample')
def sample():
    """Configure per-port sampled ERSPAN bindings."""


@sample.command('add')
@click.argument('session_name')
@click.argument('port')
@click.argument('direction', type=click.Choice(['rx', 'tx', 'both']))
@click.option('--sample-rate', required=True, type=click.IntRange(2, 0xFFFFFFFF))
@click.option('--truncate-size', type=click.IntRange(64, 9216), default=None)
@click.option('--disabled', is_flag=True, help='Create a disabled binding (admin_state=down).')
@click.pass_context
def add(ctx, session_name, port, direction, sample_rate, truncate_size, disabled):
    """Attach a source and its sampling policy to an existing ERSPAN export."""
    databases = port_mirror.config_databases()
    for database in databases.values():
        if 'global' in database.get_keys('SFLOW'):
            ctx.fail(port_mirror.EXCLUSION_ERROR)
    namespace, database, port = source_database(ctx, databases, port)
    session = database.get_entry('MIRROR_SESSION', session_name)
    if not session:
        ctx.fail(f'Mirror session {session_name} does not exist in the source namespace.')
    if session.get('type', 'ERSPAN') != 'ERSPAN':
        ctx.fail('A sampled binding must reference an ERSPAN session.')
    if 'src_port' in session:
        ctx.fail('A sampled export session must not configure src_port.')
    directions = ['rx', 'tx'] if direction == 'both' else [direction]
    validate_source_overlap(ctx, database, port, directions)
    validate_capabilities(ctx, namespace, directions, truncate_size)
    value = {'mirror_session': session_name, 'sample_rate': str(sample_rate),
             'admin_state': 'down' if disabled else 'up'}
    if truncate_size is not None:
        value['truncate_size'] = str(truncate_size)
    apply_bindings(ctx, database, namespace, [((port, d), dict(value)) for d in directions])


@sample.command('remove')
@click.argument('session_name')
@click.argument('port')
@click.argument('direction', type=click.Choice(['rx', 'tx', 'both']))
@click.pass_context
def remove(ctx, session_name, port, direction):
    """Remove selected bindings without deleting their export session."""
    databases = port_mirror.config_databases()
    # Use a stored canonical source name even if the interface was removed.
    namespace, database, port = source_database(ctx, databases, port, removing=True)
    directions = ['rx', 'tx'] if direction == 'both' else [direction]
    entries = []
    for item in directions:
        key = (port, item)
        entry = database.get_entry(port_mirror.SAMPLE_TABLE, key)
        if not entry:
            continue
        if entry.get('mirror_session') != session_name:
            ctx.fail(f'Binding {port}|{item} references a different mirror session.')
        entries.append((key, None))
    if not entries:
        ctx.fail(f'No matching sampled mirror binding exists for {port} {direction}.')
    apply_bindings(ctx, database, namespace, entries)

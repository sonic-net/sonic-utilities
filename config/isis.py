"""IS-IS Click API over the shared ConfigDB model.

Independent AF and MT controls build on gs1571's contributions; lifecycle and
identity changes are incremental adaptations of the same ConfigDB write path.
"""
import copy
import click
from sonic_py_common import logger, multi_asic
from swsscommon.swsscommon import ConfigDBConnector
import utilities_common.cli as clicommon
from sonic_isis import (LEVELS, BACKOFF, FIELDS, PROTOCOLS,
                        identifier, key_tuple, net, routed_vrf, validate, validate_transition, capture, commit)

log = logger.Logger("isis_cli")
log.set_min_log_priority_info()


def _resolve_interface(ctx, db, name):
    _snapshot(ctx)  # Include interface/member changes in the compare-and-commit boundary.
    # Import lazily: main registers this module's command groups.
    from config.main import (interface_alias_to_name, interface_name_is_valid,
                             interface_is_in_portchannel, interface_is_in_vlan)
    if clicommon.get_interface_naming_mode() == 'alias':
        name = interface_alias_to_name(db, name)
    if not db.get_entry("VLAN_INTERFACE", name) and not interface_name_is_valid(db, name):
        ctx.fail("Interface '{}' does not exist".format(name))
    if (interface_is_in_portchannel(db.get_table('PORTCHANNEL_MEMBER'), name) or
            interface_is_in_vlan(db.get_table('VLAN_MEMBER'), name)):
        ctx.fail("Interface '{}' is a PortChannel or VLAN member".format(name))
    return name


def _db(ctx):
    return ctx.obj['config_db'] if isinstance(ctx.obj, dict) else ctx.obj.cfgdb


def _snapshot(ctx):
    if 'isis_snapshot' not in ctx.meta:
        try:
            ctx.meta['isis_snapshot'] = capture(_db(ctx))
        except Exception as error:
            ctx.fail('Cannot read a consistent ConfigDB snapshot: {}'.format(error))
    return ctx.meta['isis_snapshot']


def _row(ctx, table, key):
    return copy.deepcopy(_snapshot(ctx).get(table, {}).get(key, {}))


def _write(ctx, updates):
    """Validate the candidate graph before writing; both-level edits commit together."""
    db = _db(ctx)
    before = _snapshot(ctx)
    after = copy.deepcopy(before)
    for table, key, row in updates:
        # ConfigDB represents composite keys as tuples.
        if row is None:
            after[table].pop(key, None)
        else:
            after[table][key] = row
    try:
        validate(after)
        validate_transition(before, after)
        commit(db, before, updates)
    except Exception as error:
        ctx.fail(str(error))


def _parent(ctx, instance, vrf):
    try:
        identifier(instance)
        identifier(vrf)
    except ValueError as error:
        ctx.fail(str(error))
    row = _row(ctx, 'ISIS_INSTANCE', (vrf, instance))
    if (vrf, instance) not in _snapshot(ctx)['ISIS_INSTANCE']:
        ctx.fail('IS-IS instance {}/{} does not exist'.format(vrf, instance))
    return row


def _binding(ctx, interface, resolve=True):
    db = _db(ctx)
    if resolve:
        interface = _resolve_interface(ctx, db, interface)
    elif not _row(ctx, 'ISIS_INTERFACE', interface) and clicommon.get_interface_naming_mode() == 'alias':
        from config.main import interface_alias_to_name
        interface = interface_alias_to_name(db, interface)
    row = _row(ctx, 'ISIS_INTERFACE', interface)
    if not row:
        ctx.fail('Interface {} is not explicitly bound to IS-IS'.format(interface))
    _parent(ctx, row['instance'], row['vrf'])
    return interface, row


def _fields(table):
    return click.Choice([name.replace('_', '-') for name in FIELDS[table]
                         if name not in ('enabled', 'vrf', 'instance') + BACKOFF])


def _set(ctx, table, key, field, value=None, reset=False):
    field = field.replace('-', '_')
    row = _row(ctx, table, key)
    if reset:
        row.pop(field, None)
    else:
        row[field] = value
    _write(ctx, [(table, key, row)])


@click.group(name='isis', cls=clicommon.AliasedGroup)
@click.option('-n', '--namespace', required=multi_asic.is_multi_asic(),
              type=click.Choice(multi_asic.get_namespace_list()))
@clicommon.pass_db
@click.pass_context
def ISIS(ctx, db, namespace):
    """Configure IS-IS instances and policy."""
    if namespace is not None:
        db.cfgdb = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
        db.cfgdb.connect()
    if db.cfgdb.get_entry('DEVICE_METADATA', 'localhost').get('frr_mgmt_framework_config') != 'true':
        click.echo('Warning: IS-IS requires frr_mgmt_framework_config=true and a bgp container restart.', err=True)


@ISIS.group(name='instance')
def INSTANCE():
    """Create, enable, disable or delete a named instance."""


def _instance_operation(action):
    @INSTANCE.command(name=action)
    @click.argument('instance')
    @click.option('--vrf', default='default', show_default=True)
    @click.pass_context
    def command(ctx, instance, vrf):
        if action in ('add', 'del'):
            row = _row(ctx, 'ISIS_INSTANCE', (vrf, instance)) or {'enabled': 'false'}
        else:
            row = _parent(ctx, instance, vrf)
        if action == 'del':
            for name, binding in _snapshot(ctx)['ISIS_INTERFACE'].items():
                if (binding.get('vrf'), binding.get('instance')) == (vrf, instance):
                    ctx.fail('Unbind IS-IS interface {} first (including disabled bindings)'.format(name))
            updates = [(table, key, None) for table in ('ISIS_INSTANCE_LEVEL', 'ISIS_REDISTRIBUTE')
                       for key in _snapshot(ctx)[table] if key_tuple(key)[:2] == (vrf, instance)]
            updates.append(('ISIS_INSTANCE', (vrf, instance), None))
        else:
            if action in ('enable', 'disable'):
                row['enabled'] = 'true' if action == 'enable' else 'false'
            updates = [('ISIS_INSTANCE', (vrf, instance), row)]
        _write(ctx, updates)
    return command


for _action in ('add', 'enable', 'disable', 'del'):
    _instance_operation(_action)


@ISIS.group(name='net')
def NET():
    """Manage up to three NET addresses with a shared system ID."""


def _net_operation(action):
    @NET.command(name=action)
    @click.argument('instance')
    @click.argument('address')
    @click.option('--vrf', default='default')
    @click.pass_context
    def command(ctx, instance, address, vrf):
        row = _parent(ctx, instance, vrf)
        try:
            address = net(address)
        except ValueError as error:
            ctx.fail(str(error))
        values = list(row.get('net_titles', []))
        if action == 'add' and address not in values:
            values.append(address)
        elif action == 'del' and address in values:
            values.remove(address)
        if values:
            row['net_titles'] = values
        else:
            row.pop('net_titles', None)
        _write(ctx, [('ISIS_INSTANCE', (vrf, instance), row)])
    return command


for _action in ('add', 'del'):
    _net_operation(_action)


@ISIS.command(name='set')
@click.argument('instance')
@click.argument('field', type=_fields('ISIS_INSTANCE'))
@click.argument('value')
@click.option('--vrf', default='default')
@click.pass_context
def instance_set(ctx, instance, field, value, vrf):
    _parent(ctx, instance, vrf)
    _set(ctx, 'ISIS_INSTANCE', (vrf, instance), field, value)


@ISIS.command(name='reset')
@click.argument('instance')
@click.argument('field', type=_fields('ISIS_INSTANCE'))
@click.option('--vrf', default='default')
@click.pass_context
def instance_reset(ctx, instance, field, vrf):
    _parent(ctx, instance, vrf)
    _set(ctx, 'ISIS_INSTANCE', (vrf, instance), field, reset=True)


@ISIS.group(name='spf-backoff')
def SPF():
    """Configure the complete instance-wide IETF SPF backoff tuple in milliseconds."""


@SPF.command(name='set')
@click.argument('instance')
@click.argument('values', nargs=5, type=click.IntRange(0, 60000))
@click.option('--vrf', default='default')
@click.pass_context
def spf_set(ctx, instance, values, vrf):
    row = _parent(ctx, instance, vrf)
    row.update(zip(BACKOFF, map(str, values)))
    _write(ctx, [('ISIS_INSTANCE', (vrf, instance), row)])


@SPF.command(name='reset')
@click.argument('instance')
@click.option('--vrf', default='default')
@click.pass_context
def spf_reset(ctx, instance, vrf):
    row = _parent(ctx, instance, vrf)
    for field in BACKOFF:
        row.pop(field, None)
    _write(ctx, [('ISIS_INSTANCE', (vrf, instance), row)])


@click.group(name='isis', cls=clicommon.AliasedGroup)
@click.pass_context
def INTERFACE_ISIS(ctx):
    """Bind an interface explicitly and configure its IS-IS circuit."""
    if not ctx.obj or 'config_db' not in ctx.obj:
        ctx.fail('config_db is not initialized')


@INTERFACE_ISIS.command(name='bind')
@click.argument('interface')
@click.argument('instance')
@click.option('--vrf', default=None)
@click.pass_context
def interface_bind(ctx, interface, instance, vrf):
    db = _db(ctx)
    interface = _resolve_interface(ctx, db, interface)
    actual = routed_vrf(_snapshot(ctx), interface)
    if actual is None or (vrf is not None and vrf != actual):
        ctx.fail('Binding requires an existing routed interface in the specified VRF')
    _parent(ctx, instance, actual)
    row = _row(ctx, 'ISIS_INTERFACE', interface) or {'enabled': 'false'}
    row.update(vrf=actual, instance=instance)
    _write(ctx, [('ISIS_INTERFACE', interface, row)])


@INTERFACE_ISIS.command(name='unbind')
@click.argument('interface')
@click.pass_context
def interface_unbind(ctx, interface):
    # Cleanup must also work after the interface or parent has been removed.
    if not _row(ctx, 'ISIS_INTERFACE', interface) and clicommon.get_interface_naming_mode() == 'alias':
        from config.main import interface_alias_to_name
        interface = interface_alias_to_name(_db(ctx), interface)
    updates = [('ISIS_INTERFACE_LEVEL', key, None) for key in _snapshot(ctx)['ISIS_INTERFACE_LEVEL']
               if key_tuple(key)[0] == interface]
    _write(ctx, updates + [('ISIS_INTERFACE', interface, None)])


def _interface_admin(action):
    @INTERFACE_ISIS.command(name=action)
    @click.argument('interface')
    @click.pass_context
    def command(ctx, interface):
        interface, row = _binding(ctx, interface, resolve=action == 'enable')
        if action == 'enable' and routed_vrf(_snapshot(ctx), interface) != row['vrf']:
            ctx.fail('Interface VRF changed; explicitly bind it again before enabling')
        row['enabled'] = 'true' if action == 'enable' else 'false'
        _write(ctx, [('ISIS_INTERFACE', interface, row)])
    return command


for _action in ('enable', 'disable'):
    _interface_admin(_action)


@INTERFACE_ISIS.command(name='af')
@click.argument('interface')
@click.argument('family', type=click.Choice(['ipv4', 'ipv6']))
@click.argument('state', type=click.Choice(['enable', 'disable', 'reset']))
@click.pass_context
def interface_af(ctx, interface, family, state):
    """Control each AF independently, retaining unrelated circuit settings."""
    interface, _ = _binding(ctx, interface)
    _set(ctx, 'ISIS_INTERFACE', interface, family + '_enabled',
         'true' if state == 'enable' else 'false', reset=state == 'reset')


def _interface_field(action):
    params = [click.Argument(['interface']), click.Argument(['field'], type=_fields('ISIS_INTERFACE'))]
    if action == 'set':
        params.append(click.Argument(['value']))

    @click.pass_context
    def command(ctx, interface, field, value=None):
        interface, _ = _binding(ctx, interface)
        _set(ctx, 'ISIS_INTERFACE', interface, field, value, reset=action == 'reset')
    INTERFACE_ISIS.add_command(click.Command(action, params=params, callback=command))


for _action in ('set', 'reset'):
    _interface_field(_action)


def _level_commands(group, table):
    level_group = click.Group('level', help='Configure explicit Level-1/Level-2 values; both writes both rows.')
    group.add_command(level_group)
    for action in ('set', 'reset'):
        def register(action):
            params = [click.Argument(['name']), click.Argument(['level'], type=click.Choice([*LEVELS, 'both'])),
                      click.Argument(['field'], type=_fields(table))]
            if action == 'set':
                params.append(click.Argument(['value']))
            if table == 'ISIS_INSTANCE_LEVEL':
                params.append(click.Option(['--vrf'], default='default'))

            @click.pass_context
            def command(ctx, name, level, field, value=None, vrf=None):
                if table == 'ISIS_INSTANCE_LEVEL':
                    _parent(ctx, name, vrf)
                    prefix = (vrf, name)
                else:
                    name, _ = _binding(ctx, name)
                    prefix = (name,)
                updates = []
                for selected in LEVELS if level == 'both' else (level,):
                    key = prefix + (selected,)
                    row = _row(ctx, table, key)
                    if action == 'reset':
                        row.pop(field.replace('-', '_'), None)
                    else:
                        row[field.replace('-', '_')] = value
                    updates.append((table, key, row or None))
                _write(ctx, updates)
            level_group.add_command(click.Command(action, params=params, callback=command))
        register(action)


_level_commands(ISIS, 'ISIS_INSTANCE_LEVEL')
_level_commands(INTERFACE_ISIS, 'ISIS_INTERFACE_LEVEL')


@ISIS.group(name='redistribute')
def REDISTRIBUTE():
    """Configure per-AF, protocol and level redistribution policy."""


def _redistribution(action):
    params = [click.Argument(['instance']), click.Argument(['af'], type=click.Choice(['ipv4', 'ipv6'])),
              click.Argument(['protocol'], type=click.Choice(sorted(set(sum(PROTOCOLS.values(), ()))))),
              click.Argument(['level'], type=click.Choice(LEVELS)), click.Option(['--vrf'], default='default')]
    if action == 'add':
        params += [click.Option(['--metric'], type=click.IntRange(0, 16777215)), click.Option(['--route-map'])]

    @click.pass_context
    def command(ctx, instance, af, protocol, level, vrf, metric=None, route_map=None):
        _parent(ctx, instance, vrf)
        row = {}
        if metric is not None:
            row['metric'] = str(metric)
        if route_map is not None:
            row['route_map'] = route_map
        _write(ctx, [('ISIS_REDISTRIBUTE', (vrf, instance, af, protocol, level),
                      row if action == 'add' else None)])
    REDISTRIBUTE.add_command(click.Command(action, params=params, callback=command))


for _action in ('add', 'del'):
    _redistribution(_action)

"""IS-IS ConfigDB commands for the FRR 10.7.1 three-table contract."""
import re

import click
import utilities_common.cli as clicommon
from sonic_py_common import multi_asic
from swsscommon.swsscommon import ConfigDBConnector


CFG_ISIS_GLOBALS = "ISIS_GLOBALS"
CFG_ISIS_INTERFACE = "ISIS_INTERFACE"
CFG_ISIS_REDISTRIBUTE = "ISIS_REDISTRIBUTE"
LEVELS = {'level-1': {1}, 'level-2': {2}, 'level-1-2': {1, 2}}
GLOBAL_FIELDS = {
    'level': ('level', click.Choice(list(LEVELS)), 'level-1-2'),
    'dynamic-hostname': ('dynamic_hostname', click.Choice(['enable', 'disable']), 'true'),
    'lsp-mtu': ('lsp_mtu', click.IntRange(128, 4352), '1497'),
    'ipv6-multi-topology': ('ipv6_multi_topology', click.Choice(['enable', 'disable']), 'false'),
    'overload': ('overload', click.Choice(['enable', 'disable']), 'false'),
    'overload-on-startup': ('overload_on_startup', click.IntRange(0, 86400), '0'),
}
GLOBAL_LEVEL_FIELDS = {
    'lsp-refresh-interval': ('lsp_refresh_interval', click.IntRange(1, 65235), '900'),
    'max-lsp-lifetime': ('lsp_lifetime', click.IntRange(350, 65535), '1200'),
    'lsp-gen-interval': ('lsp_generation_interval', click.IntRange(1, 120), '30'),
    'spf-interval': ('spf_minimum_interval', click.IntRange(1, 120), '1'),
}
INTERFACE_FIELDS = {
    'level': ('level', click.Choice(list(LEVELS)), 'level-1-2'),
    'network-type': ('network_type', click.Choice(['lan', 'p2p']), 'lan'),
    'passive': ('passive', click.Choice(['enable', 'disable']), 'false'),
}
INTERFACE_LEVEL_FIELDS = {
    'metric': ('metric', click.IntRange(0, 16777215), '10'),
    'hello-interval': ('hello_interval', click.IntRange(1, 600), '3'),
    'hello-multiplier': ('hello_multiplier', click.IntRange(2, 100), '10'),
}
BACKOFF_FIELDS = ('spf_init_delay', 'spf_short_delay', 'spf_long_delay',
                  'spf_hold_down', 'spf_time_to_learn')
COMMON_PROTOCOLS = ['kernel', 'connected', 'local', 'static', 'bgp', 'nhrp',
                    'vnc', 'babel', 'sharp', 'openfabric', 'table']
PROTOCOLS = {'ipv4': COMMON_PROTOCOLS + ['rip', 'ospf', 'eigrp'],
             'ipv6': COMMON_PROTOCOLS + ['ripng', 'ospf6']}


def split_key(key):
    return tuple(key.split('|')) if isinstance(key, str) else tuple(key)


def _instance_key(ctx, db, vrf, instance, require=True):
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}', instance):
        ctx.fail('Instance name must be 1-64 letters, digits, underscores, dots or hyphens')
    if vrf != 'default' and vrf not in db.get_table('VRF'):
        ctx.fail("VRF '{}' does not exist".format(vrf))
    key = (vrf, instance)
    if require and key not in db.get_table(CFG_ISIS_GLOBALS):
        ctx.fail("IS-IS instance '{}' in VRF '{}' does not exist".format(instance, vrf))
    return key


def _write(db, table, key, row):
    # Redis hashes cannot store an empty instance. NULL is SONiC's row sentinel.
    db.set_entry(table, key, row or {'NULL': 'NULL'})


def _row(db, table, key):
    return {k: v for k, v in db.get_entry(table, key).items() if k != 'NULL'}


def _true(value):
    return str(value).lower() == 'true'


def _value(value):
    return {'enable': 'true', 'disable': 'false'}.get(str(value), str(value))


def _level_fields(field, level):
    return [field + '_level_' + str(n) for n in
            ([1, 2] if level == 'both' else [int(level[-1])])]


def _validate_globals(ctx, db, key, row, fields):
    for n in (1, 2):
        suffix = '_level_' + str(n)
        if not any(field + suffix in fields for field in
                   ('lsp_refresh_interval', 'lsp_lifetime', 'lsp_generation_interval')):
            continue
        refresh = int(row.get('lsp_refresh_interval' + suffix, 900))
        lifetime = int(row.get('lsp_lifetime' + suffix, 1200))
        generation = int(row.get('lsp_generation_interval' + suffix, 30))
        if lifetime < refresh + 300 or generation >= refresh:
            ctx.fail('LSP level-{} requires lifetime >= refresh + 300 and generation < refresh'.format(n))
    if 'level' not in fields:
        return
    supported = LEVELS[row.get('level', 'level-1-2')]
    for interface_key, interface in db.get_table(CFG_ISIS_INTERFACE).items():
        if split_key(interface_key)[0] == key[0] and interface.get('instance_name') == key[1]:
            if not supported & LEVELS[interface.get('level', 'level-1-2')]:
                ctx.fail("Level has no intersection with interface '{}'".format(split_key(interface_key)[1]))
    for redistribute_key in db.get_table(CFG_ISIS_REDISTRIBUTE):
        parts = split_key(redistribute_key)
        if parts[:2] == key and int(parts[4][-1]) not in supported:
            ctx.fail('Level excludes an existing redistribution policy')


def _validate_net_system_id(ctx, db, key, new_net):
    """Validate the existing same-VRF NET configuration constraint."""
    new_id = ''.join(new_net.split('.')[-4:-1]).lower()
    for other_key, row in db.get_table(CFG_ISIS_GLOBALS).items():
        other_key = split_key(other_key)
        if other_key == key or other_key[0] != key[0]:
            continue
        net = row.get('net_title')
        if net and ''.join(net.split('.')[-4:-1]).lower() != new_id:
            ctx.fail('Instances in the same VRF must share the NET system ID')


def _interface_vrf(db, name):
    for table in ('INTERFACE', 'PORTCHANNEL_INTERFACE', 'VLAN_INTERFACE',
                  'LOOPBACK_INTERFACE', 'VLAN_SUB_INTERFACE'):
        entry = db.get_entry(table, name)
        if entry.get('vrf_name'):
            return entry['vrf_name']
    return 'default'


def _interface_key(ctx, db, name, vrf, require=True):
    from config.main import (interface_alias_to_name, interface_name_is_valid,
                             interface_is_in_portchannel)
    if clicommon.get_interface_naming_mode() == 'alias':
        name = interface_alias_to_name(db, name)
    if not db.get_entry('VLAN_INTERFACE', name) and not interface_name_is_valid(db, name):
        ctx.fail("Interface '{}' does not exist".format(name))
    if interface_is_in_portchannel(db.get_table('PORTCHANNEL_MEMBER'), name):
        ctx.fail("Interface '{}' is a PortChannel member".format(name))
    if _interface_vrf(db, name) != vrf:
        ctx.fail('Interface VRF does not match --vrf')
    key = (vrf, name)
    if require:
        row = db.get_entry(CFG_ISIS_INTERFACE, key)
        if not (_true(row.get('ipv4_enabled', False)) or _true(row.get('ipv6_enabled', False))):
            ctx.fail('Enable at least one IS-IS address family first')
    return key


def _validate_interface(ctx, db, key, row):
    parent_key = _instance_key(ctx, db, key[0], row['instance_name'])
    parent = db.get_entry(CFG_ISIS_GLOBALS, parent_key)
    if not LEVELS[parent.get('level', 'level-1-2')] & LEVELS[row.get('level', 'level-1-2')]:
        ctx.fail('Interface and instance levels have no intersection')


def _vrf_option(func):
    return click.option('--vrf', default='default', show_default=True)(func)


def _level_option(func):
    return click.option('--level', type=click.Choice(['level-1', 'level-2', 'both']),
                        default='both', show_default=True)(func)


@click.group(name='isis', cls=clicommon.AliasedGroup)
@click.option('-n', '--namespace', required=multi_asic.is_multi_asic(),
              type=click.Choice(multi_asic.get_namespace_list()))
@clicommon.pass_db
@click.pass_context
def ISIS(ctx, db, namespace):
    """Configure IS-IS instances and redistribution."""
    if namespace is not None:
        db.cfgdb = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
        db.cfgdb.connect()
    if db.cfgdb.get_entry('DEVICE_METADATA', 'localhost').get('frr_mgmt_framework_config') != 'true':
        click.echo('Warning: IS-IS requires frr_mgmt_framework_config=true and a bgp container restart.', err=True)


@ISIS.command(name='add')
@click.argument('instance')
@_vrf_option
@clicommon.pass_db
@click.pass_context
def isis_add(ctx, db, instance, vrf):
    """Create an instance, preserving any existing configuration."""
    key = _instance_key(ctx, db.cfgdb, vrf, instance, require=False)
    if key not in db.cfgdb.get_table(CFG_ISIS_GLOBALS):
        _write(db.cfgdb, CFG_ISIS_GLOBALS, key, {})


@ISIS.command(name='del')
@click.argument('instance')
@_vrf_option
@clicommon.pass_db
@click.pass_context
def isis_delete(ctx, db, instance, vrf):
    """Delete an unreferenced instance and its redistribution policies."""
    key = _instance_key(ctx, db.cfgdb, vrf, instance)
    for interface_key, row in db.cfgdb.get_table(CFG_ISIS_INTERFACE).items():
        if split_key(interface_key)[0] == vrf and row.get('instance_name') == instance:
            ctx.fail("Delete IS-IS on interface '{}' first".format(split_key(interface_key)[1]))
    for policy_key in list(db.cfgdb.get_table(CFG_ISIS_REDISTRIBUTE)):
        if split_key(policy_key)[:2] == key:
            db.cfgdb.set_entry(CFG_ISIS_REDISTRIBUTE, policy_key, None)
    db.cfgdb.set_entry(CFG_ISIS_GLOBALS, key, None)


@ISIS.command(name='net')
@click.argument('arguments', nargs=-1, required=True)
@_vrf_option
@clicommon.pass_db
@click.pass_context
def isis_net(ctx, db, arguments, vrf):
    """Set NET: INSTANCE NET; remove NET: del INSTANCE NET."""
    delete = len(arguments) == 3 and arguments[0] == 'del'
    if len(arguments) != (3 if delete else 2):
        ctx.fail('Expected INSTANCE NET or del INSTANCE NET')
    instance, net = arguments[-2:]
    if not re.fullmatch(r'[a-fA-F0-9]{2}(\.[a-fA-F0-9]{4}){3,9}\.00', net):
        ctx.fail('Invalid NET format; example: 49.0001.1921.6800.0001.00')
    key = _instance_key(ctx, db.cfgdb, vrf, instance)
    row = _row(db.cfgdb, CFG_ISIS_GLOBALS, key)
    if delete:
        if row.get('net_title', '').lower() != net.lower():
            ctx.fail('NET does not match the saved value')
        row.pop('net_title')
    else:
        _validate_net_system_id(ctx, db.cfgdb, key, net)
        row['net_title'] = net
    _write(db.cfgdb, CFG_ISIS_GLOBALS, key, row)


def _register_setter(group, command_name, declaration, per_level=False, interface=False):
    field, value_type, _ = declaration

    @click.pass_context
    def setter(ctx, target, value, vrf, level='both'):
        db = ctx.obj['config_db'] if interface else ctx.obj.cfgdb
        key = (_interface_key(ctx, db, target, vrf) if interface
               else _instance_key(ctx, db, vrf, target))
        table = CFG_ISIS_INTERFACE if interface else CFG_ISIS_GLOBALS
        row = _row(db, table, key)
        fields = _level_fields(field, level) if per_level else [field]
        for name in fields:
            row[name] = _value(value)
        if interface:
            _validate_interface(ctx, db, key, row)
        else:
            _validate_globals(ctx, db, key, row, fields)
        _write(db, table, key, row)

    setter = _vrf_option(setter)
    if per_level:
        setter = _level_option(setter)
    setter = click.argument('value', type=value_type)(setter)
    setter = click.argument('target', metavar='IFNAME' if interface else 'INSTANCE')(setter)
    group.command(name=command_name, help='Set {}.'.format(command_name))(setter)


for _name, _declaration in GLOBAL_FIELDS.items():
    _register_setter(ISIS, _name, _declaration)
for _name, _declaration in GLOBAL_LEVEL_FIELDS.items():
    _register_setter(ISIS, _name, _declaration, per_level=True)


@ISIS.command(name='spf-backoff')
@click.argument('arguments', nargs=-1, required=True)
@click.option('--init-delay', type=click.IntRange(0, 60000))
@click.option('--short-delay', type=click.IntRange(0, 60000))
@click.option('--long-delay', type=click.IntRange(0, 60000))
@click.option('--hold-down', type=click.IntRange(0, 60000))
@click.option('--time-to-learn', type=click.IntRange(0, 60000))
@_vrf_option
@clicommon.pass_db
@click.pass_context
def isis_spf_backoff(ctx, db, arguments, vrf, init_delay, short_delay,
                     long_delay, hold_down, time_to_learn):
    """Set five SPF backoff values, or remove them with del INSTANCE."""
    delete = len(arguments) == 2 and arguments[0] == 'del'
    if len(arguments) != (2 if delete else 1):
        ctx.fail('Expected INSTANCE or del INSTANCE')
    values = (init_delay, short_delay, long_delay, hold_down, time_to_learn)
    if delete and any(value is not None for value in values):
        ctx.fail('Deletion does not accept backoff values')
    if not delete and (None in values or hold_down <= time_to_learn):
        ctx.fail('All five values are required and hold-down must exceed time-to-learn')
    key = _instance_key(ctx, db.cfgdb, vrf, arguments[-1])
    row = _row(db.cfgdb, CFG_ISIS_GLOBALS, key)
    for field, value in zip(BACKOFF_FIELDS, values):
        if delete:
            row.pop(field, None)
        else:
            row[field] = str(value)
    _write(db.cfgdb, CFG_ISIS_GLOBALS, key, row)


@ISIS.command(name='reset')
@click.argument('instance')
@click.argument('field', type=click.Choice(list(GLOBAL_FIELDS) + list(GLOBAL_LEVEL_FIELDS)))
@_level_option
@_vrf_option
@clicommon.pass_db
@click.pass_context
def isis_reset(ctx, db, instance, field, level, vrf):
    """Remove explicit attributes and restore their defaults."""
    key = _instance_key(ctx, db.cfgdb, vrf, instance)
    row = _row(db.cfgdb, CFG_ISIS_GLOBALS, key)
    if field in GLOBAL_LEVEL_FIELDS:
        fields = _level_fields(GLOBAL_LEVEL_FIELDS[field][0], level)
    else:
        if ctx.get_parameter_source('level') == click.core.ParameterSource.COMMANDLINE:
            ctx.fail('--level applies only to per-level attributes')
        fields = [GLOBAL_FIELDS[field][0]]
    for name in fields:
        row.pop(name, None)
    _validate_globals(ctx, db.cfgdb, key, row, fields)
    _write(db.cfgdb, CFG_ISIS_GLOBALS, key, row)


@click.group(name='isis', cls=clicommon.AliasedGroup)
@click.option('-n', '--namespace', required=multi_asic.is_multi_asic(),
              type=click.Choice(multi_asic.get_namespace_list()))
@click.pass_context
def INTERFACE_ISIS(ctx, namespace):
    """Configure interface IS-IS address families and attributes."""
    if namespace is not None:
        db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
        db.connect()
        ctx.obj['config_db'] = db
        ctx.obj['namespace'] = namespace


def _register_af(af):
    @INTERFACE_ISIS.command(name=af)
    @click.argument('ifname')
    @click.argument('state', type=click.Choice(['enable', 'disable']))
    @click.option('--instance')
    @_vrf_option
    @click.pass_context
    def address_family(ctx, ifname, state, instance, vrf):
        db = ctx.obj['config_db']
        key = _interface_key(ctx, db, ifname, vrf, require=False)
        row = _row(db, CFG_ISIS_INTERFACE, key)
        if state == 'enable':
            if instance is None:
                ctx.fail('--instance is required for enable')
            _instance_key(ctx, db, vrf, instance)
            if row and row['instance_name'] != instance:
                ctx.fail('Disable both address families before changing instance')
            row.update(instance_name=instance)
            row[af + '_enabled'] = 'true'
            _validate_interface(ctx, db, key, row)
            _write(db, CFG_ISIS_INTERFACE, key, row)
        else:
            if instance is not None:
                ctx.fail('--instance is only accepted for enable')
            if not row:
                return
            row[af + '_enabled'] = 'false'
            if not any(_true(row.get(family + '_enabled', False)) for family in ('ipv4', 'ipv6')):
                db.set_entry(CFG_ISIS_INTERFACE, key, None)
            else:
                _write(db, CFG_ISIS_INTERFACE, key, row)


for _af in ('ipv4', 'ipv6'):
    _register_af(_af)
for _name, _declaration in INTERFACE_FIELDS.items():
    _register_setter(INTERFACE_ISIS, _name, _declaration, interface=True)
for _name, _declaration in INTERFACE_LEVEL_FIELDS.items():
    _register_setter(INTERFACE_ISIS, _name, _declaration, per_level=True, interface=True)


@INTERFACE_ISIS.command(name='del')
@click.argument('ifname')
@_vrf_option
@click.pass_context
def interface_isis_delete(ctx, ifname, vrf):
    """Remove both address families and all interface parameters."""
    db = ctx.obj['config_db']
    key = _interface_key(ctx, db, ifname, vrf, require=False)
    db.set_entry(CFG_ISIS_INTERFACE, key, None)


@INTERFACE_ISIS.command(name='reset')
@click.argument('ifname')
@click.argument('field', type=click.Choice(list(INTERFACE_FIELDS) + list(INTERFACE_LEVEL_FIELDS)))
@_level_option
@_vrf_option
@click.pass_context
def interface_isis_reset(ctx, ifname, field, level, vrf):
    """Restore selected interface attributes, retaining the AF binding."""
    db = ctx.obj['config_db']
    key = _interface_key(ctx, db, ifname, vrf)
    row = _row(db, CFG_ISIS_INTERFACE, key)
    if field in INTERFACE_LEVEL_FIELDS:
        fields = _level_fields(INTERFACE_LEVEL_FIELDS[field][0], level)
    else:
        if ctx.get_parameter_source('level') == click.core.ParameterSource.COMMANDLINE:
            ctx.fail('--level applies only to per-level attributes')
        fields = [INTERFACE_FIELDS[field][0]]
    for name in fields:
        row.pop(name, None)
    _validate_interface(ctx, db, key, row)
    _write(db, CFG_ISIS_INTERFACE, key, row)


@ISIS.group(name='redistribute', cls=clicommon.AliasedGroup)
def redistribute():
    """Configure complete redistribution policies."""


def _register_redistribute(delete):
    @click.pass_context
    def policy(ctx, instance, af, protocol, level, vrf, table_id, metric=0, route_map=None):
        db = ctx.obj.cfgdb
        parent = _instance_key(ctx, db, vrf, instance)
        if protocol not in PROTOCOLS[af]:
            ctx.fail('Unsupported source protocol for {}'.format(af))
        if (protocol == 'table') != (table_id is not None):
            ctx.fail('--table-id is required only for table sources')
        if int(level[-1]) not in LEVELS[db.get_entry(CFG_ISIS_GLOBALS, parent).get('level', 'level-1-2')]:
            ctx.fail('Redistribution level is not supported by the instance')
        key = parent + (af, protocol, level, str(table_id or 0))
        if delete:
            db.set_entry(CFG_ISIS_REDISTRIBUTE, key, None)
        else:
            if route_map and route_map not in db.get_table('ROUTE_MAP_SET'):
                ctx.fail("Route map '{}' does not exist".format(route_map))
            row = {'metric': str(metric)}
            if route_map:
                row['route_map'] = [route_map]
            _write(db, CFG_ISIS_REDISTRIBUTE, key, row)

    policy = _vrf_option(policy)
    policy = click.option('--table-id', type=click.IntRange(1, 65535))(policy)
    if not delete:
        policy = click.option('--metric', type=click.IntRange(0, 16777215), default=0)(policy)
        policy = click.option('--route-map')(policy)
    policy = click.argument('level', type=click.Choice(['level-1', 'level-2']))(policy)
    policy = click.argument('protocol')(policy)
    policy = click.argument('af', type=click.Choice(['ipv4', 'ipv6']))(policy)
    policy = click.argument('instance')(policy)
    redistribute.command(name='del' if delete else 'add')(policy)


_register_redistribute(False)
_register_redistribute(True)

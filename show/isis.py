"""ConfigDB inspection and FRR 10.7.1 IS-IS runtime queries."""
import ipaddress
import json
import re

import click
from sonic_py_common import multi_asic
from swsscommon.swsscommon import ConfigDBConnector
import utilities_common.cli as clicommon
import utilities_common.multi_asic as multi_asic_util
from utilities_common import bgp_util
from config.isis import (GLOBAL_FIELDS, GLOBAL_LEVEL_FIELDS, INTERFACE_FIELDS,
                         INTERFACE_LEVEL_FIELDS, split_key)


def run_vtysh_command(vtysh_cmd, namespace=multi_asic.DEFAULT_NAMESPACE):
    return bgp_util.run_bgp_command(vtysh_cmd, namespace, bgp_util.get_vtysh_shell_cmd())


def _identifier(ctx, param, value):
    if value is not None and not re.fullmatch(r'[A-Za-z0-9_.:/-]+', value):
        raise click.BadParameter('Invalid identifier', ctx=ctx, param=param)
    return value


def _algorithm(ctx, param, value):
    if value is not None and value != 'all':
        try:
            number = int(value)
        except ValueError:
            raise click.BadParameter('Expected 128-255 or all', ctx=ctx, param=param)
        if not 128 <= number <= 255:
            raise click.BadParameter('Expected 128-255 or all', ctx=ctx, param=param)
    return value


def _vrf(func):
    return click.option('--vrf', callback=_identifier)(func)


def _json(func):
    return click.option('-j', '--json', 'json_format', is_flag=True)(func)


def _level(func):
    return click.option('--level', type=click.Choice(['level-1', 'level-2']))(func)


def _algo(func):
    return click.option('--algorithm', callback=_algorithm)(func)


def _run(ctx, words, vrf=None, json_format=False):
    command = ['show', 'isis']
    if vrf is not None:
        command.extend(['vrf', vrf])
    command.extend(str(word) for word in words if word is not None)
    if json_format:
        command.append('json')
    namespace = ctx.find_root().meta.get('isis_namespace', multi_asic.DEFAULT_NAMESPACE)
    click.echo(run_vtysh_command(' '.join(command), namespace).rstrip('\n'))


def _algorithm_words(algorithm):
    return [] if algorithm is None else ['algorithm'] + ([] if algorithm == 'all' else [algorithm])


@click.group(name='isis', cls=clicommon.AliasedGroup)
@click.option('--namespace', '-n', default=multi_asic.DEFAULT_NAMESPACE,
              callback=multi_asic_util.multi_asic_namespace_validation_callback)
@click.pass_context
def isis(ctx, namespace):
    """Show IS-IS configuration and runtime information."""
    ctx.find_root().meta['isis_namespace'] = namespace


@isis.command()
@click.option('--vrf', default='default', callback=_identifier)
@click.option('--instance', callback=_identifier)
@click.pass_context
def configuration(ctx, vrf, instance):
    """Show explicit ConfigDB fields and effective defaults."""
    if vrf == 'all':
        ctx.fail('configuration accepts a single VRF')
    db = ConfigDBConnector(use_unix_socket_path=True,
                           namespace=ctx.find_root().meta.get('isis_namespace', multi_asic.DEFAULT_NAMESPACE))
    db.connect()
    output = {}
    for table, fields, level_fields in (
            ('ISIS_GLOBALS', GLOBAL_FIELDS, GLOBAL_LEVEL_FIELDS),
            ('ISIS_INTERFACE', INTERFACE_FIELDS, INTERFACE_LEVEL_FIELDS),
            ('ISIS_REDISTRIBUTE', {}, {})):
        selected = {}
        for key, row in sorted(db.get_table(table).items()):
            parts = split_key(key)
            parent = row.get('instance_name') if table == 'ISIS_INTERFACE' else parts[1]
            if parts[0] != vrf or (instance is not None and parent != instance):
                continue
            explicit = {field: value for field, value in row.items() if field != 'NULL'}
            effective = {definition[0]: definition[2] for definition in fields.values()}
            for field, _, default in level_fields.values():
                effective.update({field + '_level_' + str(n): default for n in (1, 2)})
            if table == 'ISIS_INTERFACE':
                effective.update(ipv4_enabled='false', ipv6_enabled='false')
            elif table == 'ISIS_REDISTRIBUTE':
                effective['metric'] = '0'
            effective.update(explicit)
            selected['|'.join(parts)] = {'explicit': explicit, 'effective': effective}
        output[table] = selected
    click.echo(json.dumps(output, indent=2))


@isis.command()
@_vrf
@_json
@click.pass_context
def summary(ctx, vrf, json_format):
    _run(ctx, ['summary'], vrf, json_format)


def _register_object_query(name, allow_detail_object=False):
    @click.pass_context
    def query(ctx, identifier, detail, vrf, json_format):
        if identifier and detail and not allow_detail_object:
            ctx.fail('Object argument and --detail are mutually exclusive')
        _run(ctx, [name] + (['detail'] if detail else []) + ([identifier] if identifier else []),
             vrf, json_format)
    query = _json(_vrf(query))
    query = click.option('--detail', is_flag=True)(query)
    query = click.argument('identifier', required=False, callback=_identifier)(query)
    isis.command(name=name)(query)


_register_object_query('interface')
_register_object_query('neighbor')
_register_object_query('database', allow_detail_object=True)


@isis.command()
@_vrf
@_json
@_level
@_algo
@click.option('--prefix-sid', is_flag=True)
@click.option('--backup', is_flag=True)
@click.pass_context
def route(ctx, vrf, json_format, level, algorithm, prefix_sid, backup):
    words = ['route', level] + (['prefix-sid'] if prefix_sid else []) + (['backup'] if backup else [])
    _run(ctx, words + _algorithm_words(algorithm), vrf, json_format)


@isis.command()
@_vrf
@_json
@_level
@_algo
@click.pass_context
def topology(ctx, vrf, json_format, level, algorithm):
    _run(ctx, ['topology', level] + _algorithm_words(algorithm), vrf, json_format)


def _register_simple(group, name, words):
    @click.pass_context
    def query(ctx, vrf):
        _run(ctx, words, vrf)
    group.command(name=name)(_vrf(query))


_register_simple(isis, 'hostname', ['hostname'])
_register_simple(isis, 'spf-delay-ietf', ['spf-delay-ietf'])


@isis.command(name='flex-algo')
@click.argument('algorithm', required=False, type=click.IntRange(128, 255))
@_vrf
@click.pass_context
def flex_algo(ctx, algorithm, vrf):
    _run(ctx, ['flex-algo', algorithm], vrf)


@isis.group(name='fast-reroute', cls=clicommon.AliasedGroup)
def fast_reroute():
    """Show fast reroute state."""


@fast_reroute.command(name='summary')
@_vrf
@_level
@click.pass_context
def fast_reroute_summary(ctx, vrf, level):
    _run(ctx, ['fast-reroute', 'summary', level], vrf)


@isis.group(name='segment-routing', cls=clicommon.AliasedGroup)
def segment_routing():
    """Show segment routing state."""


@segment_routing.command(name='node')
@_algo
@click.pass_context
def segment_routing_node(ctx, algorithm):
    _run(ctx, ['segment-routing', 'node'] + _algorithm_words(algorithm))


@isis.group(name='mpls-te', cls=clicommon.AliasedGroup)
def mpls_te():
    """Show MPLS traffic engineering state."""


_register_simple(mpls_te, 'router', ['mpls-te', 'router'])


@mpls_te.command(name='interface')
@click.argument('ifname', required=False, callback=_identifier)
@click.pass_context
def mpls_te_interface(ctx, ifname):
    _run(ctx, ['mpls-te', 'interface', ifname])


@mpls_te.command(name='database')
@click.argument('kind', required=False, type=click.Choice(['vertex', 'edge', 'subnet']))
@click.argument('identifier', required=False, callback=_identifier)
@click.option('--detail', is_flag=True)
@_vrf
@_json
@click.pass_context
def mpls_te_database(ctx, kind, identifier, detail, vrf, json_format):
    if detail and json_format:
        ctx.fail('--detail and --json are mutually exclusive')
    if identifier:
        try:
            if kind == 'edge':
                ipaddress.ip_address(identifier)
            elif kind == 'subnet':
                ipaddress.ip_network(identifier, strict=False)
            elif kind == 'vertex' and not 0 <= int(identifier) <= 4294967295:
                raise ValueError()
        except ValueError:
            ctx.fail('Invalid {} identifier'.format(kind))
    _run(ctx, ['mpls-te', 'database', kind, identifier] + (['detail'] if detail else []),
         vrf, json_format)


@isis.group(name='mpls', cls=clicommon.AliasedGroup)
def mpls():
    """Show MPLS protocol state."""


@mpls.command(name='ldp-sync')
@click.argument('selector', required=False, type=click.Choice(['interface']))
@click.argument('ifname', required=False, callback=_identifier)
@click.pass_context
def mpls_ldp_sync(ctx, selector, ifname):
    if selector and ifname is None:
        ctx.fail('interface requires an interface name or all')
    _run(ctx, ['mpls', 'ldp-sync', selector, ifname])

import click
import ipaddress

from flow_counter_util.route import FLOW_COUNTER_ROUTE_PATTERN_TABLE, FLOW_COUNTER_ROUTE_MAX_MATCH_FIELD, DEFAULT_VRF, PATTERN_SEPARATOR
from flow_counter_util.route import build_route_pattern, extract_route_pattern, exit_if_route_flow_counter_not_support
from utilities_common.cli import AbbreviationGroup, pass_db
from utilities_common import cli # To make mock work in unit test

#
# 'flowcnt-route' group ('config flowcnt-route ...')
#


@click.group(cls=AbbreviationGroup, invoke_without_command=False)
def flowcnt_route():
    """Route flow counter related configuration tasks"""
    pass


@flowcnt_route.group()
def pattern():
    """Set pattern for route flow counter"""
    pass


@pattern.command(name='add')
@click.option('-y', '--yes', is_flag=True)
@click.option('--vrf', help='VRF/VNET name or default VRF')
@click.option('--max', 'max_allowed_match', type=click.IntRange(1, 50), default=30, show_default=True, help='Max allowed match count')
@click.argument('prefix-pattern', required=True)
@pass_db
def pattern_add(db, yes, vrf, max_allowed_match, prefix_pattern):
    """Add pattern for route flow counter"""
    _update_route_flow_counter_config(db, vrf, max_allowed_match, prefix_pattern, True, yes)


@pattern.command(name='remove')
@click.option('--vrf', help='VRF/VNET name or default VRF')
@click.argument('prefix-pattern', required=True)
@pass_db
def pattern_remove(db, vrf, prefix_pattern):
    """Remove pattern for route flow counter"""
    _update_route_flow_counter_config(db, vrf, None, prefix_pattern, False)


def _update_route_flow_counter_config(db, vrf, max_allowed_match, prefix_pattern, add, yes=False):
    """
    Update route flow counter config
    :param db: db object
    :param vrf: vrf string, empty vrf will be treated as default vrf
    :param max_allowed_match: max allowed match count, $FLOW_COUNTER_ROUTE_MAX_MATCH_FIELD will be used if not specified
    :param prefix_pattern: route prefix pattern, automatically add prefix length if not specified
    :param add: True to add/set the configuration, otherwise remove
    :param yes: Don't ask question if True
    :return:
    """
    exit_if_route_flow_counter_not_support()

    if add:
        try:
            net = ipaddress.ip_network(prefix_pattern, strict=False)
        except ValueError as e:
            click.echo('Invalid prefix pattern: {}'.format(prefix_pattern))
            exit(1)

        if '/' not in prefix_pattern:
            prefix_pattern += '/' + str(net.prefixlen)

        key = build_route_pattern(vrf, prefix_pattern)
        for _, cfgdb in db.cfgdb_clients.items():
            if _try_find_existing_pattern_by_ip_type(cfgdb, net, key, yes):
                entry_data = cfgdb.get_entry(FLOW_COUNTER_ROUTE_PATTERN_TABLE, key)
                old_max_allowed_match = entry_data.get(FLOW_COUNTER_ROUTE_MAX_MATCH_FIELD)
                if old_max_allowed_match is not None and int(old_max_allowed_match) == max_allowed_match:
                    click.echo('The route pattern already exists, nothing to be changed')
                    exit(1)
            cfgdb.mod_entry(FLOW_COUNTER_ROUTE_PATTERN_TABLE,
                            key,
                            {FLOW_COUNTER_ROUTE_MAX_MATCH_FIELD: str(max_allowed_match)})
    else:
        found = False
        key = build_route_pattern(vrf, prefix_pattern)
        for _, cfgdb in db.cfgdb_clients.items():
            pattern_table = cfgdb.get_table(FLOW_COUNTER_ROUTE_PATTERN_TABLE)

            for existing_key in pattern_table:
                exist_vrf, existing_prefix = extract_route_pattern(existing_key)
                if (exist_vrf == vrf or (vrf is None and exist_vrf == DEFAULT_VRF)) and existing_prefix == prefix_pattern:
                    found = True
                    cfgdb.set_entry(FLOW_COUNTER_ROUTE_PATTERN_TABLE, key, None)
        if not found:
            click.echo("Failed to remove route pattern: {} does not exist".format(key))
            exit(1)


def _try_find_existing_pattern_by_ip_type(cfgdb, input_net, input_key, yes):
    """Try to find the same IP type pattern from CONFIG DB. 
        1. If found a pattern with the same IP type, but the patter does not equal, ask user if need to replace the old with new one
            a. If user types "yes", remove the old one, return False
            b. If user types "no", exit
        2. If found a pattern with the same IP type and the pattern equal, return True
        3. If not found a pattern with the same IP type, return False

    Args:
        cfgdb (object): CONFIG DB object
        input_net (object): Input ip_network object
        input_key (str): Input key
        yes (bool): Whether ask user question

    Returns:
        bool: True if found the same pattern in CONFIG DB
    """
    input_type = type(input_net) # IPv4 or IPv6
    found_invalid = []
    found = None
    pattern_table = cfgdb.get_table(FLOW_COUNTER_ROUTE_PATTERN_TABLE)
    for existing_key in pattern_table:
        if isinstance(existing_key, tuple):
            existing_prefix = existing_key[1]
            existing_key = PATTERN_SEPARATOR.join(existing_key)
        else:
            _, existing_prefix = extract_route_pattern(existing_key)

        # In case user configures an invalid pattern via CONFIG DB.
        if not existing_prefix: # Invalid pattern such as: "vrf1|"
            click.echo('Detect invalid route pattern in existing configuration {}'.format(existing_key))
            found_invalid.append(existing_key)
            continue

        try:
            existing_net = ipaddress.ip_network(existing_prefix, strict=False)
        except ValueError as e: # Invalid pattern such as: "vrf1|invalid"
            click.echo('Detect invalid route pattern in existing configuration {}'.format(existing_key))
            found_invalid.append(existing_key)
            continue

        if type(existing_net) == input_type:
            found = existing_key
            break

    if found == input_key:
        return True

    if not found and found_invalid:
        # If not found but there is an invalid one, ask user to replace the invalid one
        found = found_invalid[0]

    if found:
        if not yes:
            answer = cli.query_yes_no('Only support 1 IPv4 route pattern and 1 IPv6 route pattern, remove existing pattern {}?'.format(found))
        else:
            answer = True
        if answer:
            click.echo('Replacing existing route pattern {} with {}'.format(existing_key, input_key))
            cfgdb.set_entry(FLOW_COUNTER_ROUTE_PATTERN_TABLE, existing_key, None)
        else:
            exit(0)
    return False

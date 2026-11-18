"""IS-IS northbound contract: mutations, validation, and FRR query syntax."""
import copy
import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

import config.isis as config_isis
import show.isis as show_isis
from utilities_common.db import Db


class ConfigDB:
    """In-memory rows with ConfigDB's tuple-key and replacement semantics."""
    def __init__(self, **kwargs):
        self.tables = {
            'PORT': {'Ethernet0': {'alias': 'etp1'}, 'Ethernet4': {'alias': 'etp2'}},
            'INTERFACE': {'Ethernet0': {}, 'Ethernet4': {'vrf_name': 'VrfBlue'}},
            'VRF': {'VrfBlue': {'NULL': 'NULL'}},
            'DEVICE_METADATA': {'localhost': {'frr_mgmt_framework_config': 'true'}},
            'ROUTE_MAP_SET': {'FILTER': {'NULL': 'NULL'}},
        }

    def connect(self):
        pass

    def get_table(self, table):
        return copy.deepcopy(self.tables.get(table, {}))

    def get_entry(self, table, key):
        return self.get_table(table).get(key, {})

    def set_entry(self, table, key, row):
        rows = self.tables.setdefault(table, {})
        if row is None:
            rows.pop(key, None)
        else:
            rows[key] = copy.deepcopy(row)


@pytest.fixture
def cli():
    db = Db()
    db.cfgdb = ConfigDB()
    runner = CliRunner()

    def invoke(args, interface=False, ok=True):
        group = config_isis.INTERFACE_ISIS if interface else config_isis.ISIS
        obj = {'config_db': db.cfgdb, 'namespace': None} if interface else db
        with patch('utilities_common.cli.get_interface_naming_mode', return_value='default'):
            result = runner.invoke(group, args, obj=obj)
        if ok:
            assert result.exit_code == 0, result.output + repr(result.exception)
        else:
            assert result.exit_code != 0, result.output
        return result

    return db.cfgdb, invoke


def test_instance_empty_row_and_reset(cli):
    db, invoke = cli
    invoke(['add', 'CORE'])
    key = ('default', 'CORE')
    assert db.get_entry('ISIS_GLOBALS', key) == {'NULL': 'NULL'}
    invoke(['lsp-mtu', 'CORE', '1497'])
    assert db.get_entry('ISIS_GLOBALS', key) == {'lsp_mtu': '1497'}
    invoke(['add', 'CORE'])
    assert db.get_entry('ISIS_GLOBALS', key) == {'lsp_mtu': '1497'}
    invoke(['reset', 'CORE', 'lsp-mtu'])
    assert db.get_entry('ISIS_GLOBALS', key) == {'NULL': 'NULL'}
    invoke(['enable', 'CORE'], ok=False)
    invoke(['timer', 'lsp-mtu', 'CORE', '1400'], ok=False)
    invoke(['add', '-bad'], ok=False)
    invoke(['add', 'X' * 65], ok=False)
    invoke(['add', 'CORE', '--vrf', 'missing'], ok=False)


def test_net_mutations_preserve_shared_peer_configuration(cli):
    db, invoke = cli
    first = '49.abcd.0000.0000.0001.00'
    second = '49.0002.0000.0000.0001.00'
    different = '49.0001.0000.0000.0002.00'
    for name in ('A', 'B'):
        invoke(['add', name])
    invoke(['net', 'A', first])
    invoke(['net', 'B', different], ok=False)
    invoke(['net', 'B', second])
    peer = db.get_entry('ISIS_GLOBALS', ('default', 'B'))
    invoke(['net', 'A', different], ok=False)
    invoke(['net', 'del', 'A', second], ok=False)
    invoke(['net', 'A', first.upper()])
    assert db.get_entry('ISIS_GLOBALS', ('default', 'A'))['net_title'] == first.upper()
    # Matching deletion ignores case; the stored value retains the user's input.
    invoke(['net', 'del', 'A', first])
    assert db.get_entry('ISIS_GLOBALS', ('default', 'A')) == {'NULL': 'NULL'}
    invoke(['net', 'A', first])
    invoke(['net', 'A', second])
    assert db.get_entry('ISIS_GLOBALS', ('default', 'A'))['net_title'] == second
    invoke(['net', 'del', 'A', second])
    assert db.get_entry('ISIS_GLOBALS', ('default', 'A')) == {'NULL': 'NULL'}
    invoke(['net', 'A', 'invalid'], ok=False)
    invoke(['add', 'del'])
    invoke(['net', 'del', first])
    assert db.get_entry('ISIS_GLOBALS', ('default', 'del'))['net_title'] == first
    assert db.get_entry('ISIS_GLOBALS', ('default', 'B')) == peer


@pytest.mark.parametrize('has_net,peer_count,referenced', [
    (True, 2, True),
    (True, 0, False),
    (False, 2, False),
])
def test_instance_delete_preserves_peers_and_cascades_own_policy(cli, has_net, peer_count, referenced):
    db, invoke = cli
    invoke(['add', 'A'])
    if has_net:
        invoke(['net', 'A', '49.0001.0000.0000.0001.00'])
    for name, area in [('B', '0002'), ('C', '0003')][:peer_count]:
        invoke(['add', name])
        invoke(['net', name, '49.{}.0000.0000.0001.00'.format(area)])
    invoke(['add', 'A', '--vrf', 'VrfBlue'])
    invoke(['net', 'A', '49.0001.0000.0000.0002.00', '--vrf', 'VrfBlue'])
    invoke(['redistribute', 'add', 'A', 'ipv4', 'bgp', 'level-2', '--vrf', 'VrfBlue'])
    invoke(['redistribute', 'add', 'A', 'ipv4', 'bgp', 'level-2'])
    if referenced:
        invoke(['ipv4', 'Ethernet0', 'enable', '--instance', 'A'], interface=True)
        before = copy.deepcopy(db.tables)
        with patch.object(db, 'set_entry', wraps=db.set_entry) as write:
            result = invoke(['del', 'A'], ok=False)
        write.assert_not_called()
        assert db.tables == before
        assert "Delete IS-IS on interface 'Ethernet0' first" in result.output
        invoke(['del', 'Ethernet0'], interface=True)
    peers = {key: row for key, row in db.get_table('ISIS_GLOBALS').items()
             if key != ('default', 'A')}
    peer_policies = {key: row for key, row in db.get_table('ISIS_REDISTRIBUTE').items()
                     if key[:2] != ('default', 'A')}
    invoke(['del', 'A'])
    assert db.get_table('ISIS_GLOBALS') == peers
    assert db.get_table('ISIS_REDISTRIBUTE') == peer_policies
    for name in ('B', 'C')[:peer_count]:
        invoke(['del', name])
    invoke(['del', 'A', '--vrf', 'VrfBlue'])
    assert not db.get_table('ISIS_GLOBALS')
    assert not db.get_table('ISIS_REDISTRIBUTE')


def test_lsp_both_validation_is_atomic_and_reset_preserves_other_fields(cli):
    db, invoke = cli
    invoke(['add', 'A'])
    invoke(['max-lsp-lifetime', 'A', '1500', '--level', 'level-1'])
    invoke(['lsp-refresh-interval', 'A', '1000'], ok=False)
    row = db.get_entry('ISIS_GLOBALS', ('default', 'A'))
    assert row == {'lsp_lifetime_level_1': '1500'}
    invoke(['lsp-refresh-interval', 'A', '1000', '--level', 'level-1'])
    invoke(['lsp-gen-interval', 'A', '120', '--level', 'level-1'])
    invoke(['reset', 'A', 'max-lsp-lifetime', '--level', 'level-1'], ok=False)
    invoke(['reset', 'A', 'lsp-refresh-interval', '--level', 'level-1'])
    row = db.get_entry('ISIS_GLOBALS', ('default', 'A'))
    assert row == {'lsp_lifetime_level_1': '1500', 'lsp_generation_interval_level_1': '120'}
    invoke(['reset', 'A', 'lsp-mtu', '--level', 'both'], ok=False)
    invoke(['spf-interval', 'A', '0'], ok=False)


def test_unrelated_global_attributes_do_not_validate_existing_level_or_timer_conflicts(cli):
    db, invoke = cli
    invoke(['add', 'A'])
    # Existing ConfigDB conflicts do not belong to a hostname or MTU mutation.
    db.set_entry('ISIS_GLOBALS', ('default', 'A'),
                 {'level': 'level-1', 'lsp_refresh_interval_level_2': '1000'})
    db.set_entry('ISIS_INTERFACE', ('default', 'Ethernet0'),
                 {'instance_name': 'A', 'ipv4_enabled': 'true', 'level': 'level-2'})
    db.set_entry('ISIS_REDISTRIBUTE', ('default', 'A', 'ipv4', 'table', 'level-2', '10'),
                 {'metric': '20'})
    invoke(['dynamic-hostname', 'A', 'disable'])
    invoke(['lsp-mtu', 'A', '1400'])
    invoke(['reset', 'A', 'lsp-mtu'])
    row = db.get_entry('ISIS_GLOBALS', ('default', 'A'))
    assert row['dynamic_hostname'] == 'false'
    assert 'lsp_mtu' not in row
    invoke(['level', 'A', 'level-1'], ok=False)


def test_lsp_validation_only_checks_mutated_levels(cli):
    db, invoke = cli
    invoke(['add', 'A'])
    db.set_entry('ISIS_GLOBALS', ('default', 'A'), {'lsp_refresh_interval_level_2': '1000'})
    invoke(['lsp-gen-interval', 'A', '40', '--level', 'level-1'])
    invoke(['reset', 'A', 'lsp-gen-interval', '--level', 'level-1'])
    before = db.get_entry('ISIS_GLOBALS', ('default', 'A'))
    invoke(['lsp-gen-interval', 'A', '40'], ok=False)
    assert db.get_entry('ISIS_GLOBALS', ('default', 'A')) == before


def test_backoff_all_or_none_and_reserved_instance_name(cli):
    db, invoke = cli
    invoke(['add', 'del'])
    invoke(['spf-backoff', 'del', '--init-delay', '0'], ok=False)
    args = ['spf-backoff', 'del', '--init-delay', '0', '--short-delay', '50',
            '--long-delay', '100', '--hold-down', '1000', '--time-to-learn', '500']
    invoke(args)
    row = db.get_entry('ISIS_GLOBALS', ('default', 'del'))
    assert all(field in row for field in config_isis.BACKOFF_FIELDS)
    invoke(args[:-1] + ['1000'], ok=False)
    invoke(['spf-backoff', 'del', 'del', '--init-delay', '1'], ok=False)
    invoke(['spf-backoff', 'del', 'del'])
    assert db.get_entry('ISIS_GLOBALS', ('default', 'del')) == {'NULL': 'NULL'}


def test_af_lifecycle_binding_and_per_level_parameters(cli):
    db, invoke = cli
    invoke(['add', 'A'])
    invoke(['add', 'B'])
    invoke(['metric', 'Ethernet0', '0'], interface=True, ok=False)
    invoke(['ipv4', 'Ethernet0', 'enable'], interface=True, ok=False)
    invoke(['ipv4', 'Ethernet0', 'enable', '--instance', 'A'], interface=True)
    invoke(['ipv6', 'Ethernet0', 'enable', '--instance', 'B'], interface=True, ok=False)
    invoke(['ipv6', 'Ethernet0', 'enable', '--instance', 'A'], interface=True)
    invoke(['metric', 'Ethernet0', '0', '--level', 'level-1'], interface=True)
    invoke(['hello-interval', 'Ethernet0', '10', '--level', 'level-2'], interface=True)
    invoke(['network-type', 'Ethernet0', 'p2p'], interface=True)
    key = ('default', 'Ethernet0')
    assert db.get_entry('ISIS_INTERFACE', key)['hello_interval_level_2'] == '10'
    before = db.get_entry('ISIS_INTERFACE', key)
    invoke(['ipv4', 'Ethernet0', 'enable', '--instance', 'A'], interface=True)
    assert db.get_entry('ISIS_INTERFACE', key) == before
    invoke(['ipv4', 'Ethernet0', 'disable'], interface=True)
    assert db.get_entry('ISIS_INTERFACE', key)['metric_level_1'] == '0'
    invoke(['del', 'A'], ok=False)
    invoke(['ipv6', 'Ethernet0', 'disable'], interface=True)
    assert key not in db.get_table('ISIS_INTERFACE')
    invoke(['ipv4', 'Ethernet0', 'enable', '--instance', 'B'], interface=True)
    assert db.get_entry('ISIS_INTERFACE', key) == {'instance_name': 'B', 'ipv4_enabled': 'true'}
    invoke(['reset', 'Ethernet0', 'ipv4'], interface=True, ok=False)
    invoke(['del', 'Ethernet0'], interface=True)


def test_vrf_members_and_level_intersection(cli):
    db, invoke = cli
    invoke(['add', 'A', '--vrf', 'VrfBlue'])
    invoke(['ipv4', 'Ethernet4', 'enable', '--instance', 'A'], interface=True, ok=False)
    invoke(['ipv4', 'Ethernet4', 'enable', '--instance', 'A', '--vrf', 'VrfBlue'], interface=True)
    invoke(['level', 'A', 'level-1', '--vrf', 'VrfBlue'])
    invoke(['level', 'Ethernet4', 'level-2', '--vrf', 'VrfBlue'], interface=True, ok=False)
    invoke(['level', 'Ethernet4', 'level-1', '--vrf', 'VrfBlue'], interface=True)
    invoke(['level', 'A', 'level-2', '--vrf', 'VrfBlue'], ok=False)
    assert db.get_entry('ISIS_INTERFACE', ('VrfBlue', 'Ethernet4'))['level'] == 'level-1'
    db.set_entry('PORTCHANNEL_MEMBER', ('PortChannel1', 'Ethernet0'), {'NULL': 'NULL'})
    invoke(['add', 'B'])
    invoke(['ipv4', 'Ethernet0', 'enable', '--instance', 'B'], interface=True, ok=False)


def test_redistribution_complete_replacement_and_cascade(cli):
    db, invoke = cli
    invoke(['add', 'A'])
    prefix = ['redistribute', 'add', 'A', 'ipv4', 'table', 'level-2']
    invoke(prefix, ok=False)
    invoke(prefix + ['--table-id', '10', '--metric', '20', '--route-map', 'FILTER'])
    invoke(prefix + ['--table-id', '11', '--metric', '30'])
    invoke(prefix + ['--table-id', '10'])
    key = ('default', 'A', 'ipv4', 'table', 'level-2', '10')
    assert db.get_entry('ISIS_REDISTRIBUTE', key) == {'metric': '0'}
    assert len(db.get_table('ISIS_REDISTRIBUTE')) == 2
    invoke(['redistribute', 'add', 'A', 'ipv4', 'bgp', 'level-1', '--table-id', '5'], ok=False)
    invoke(['redistribute', 'add', 'A', 'ipv6', 'ospf', 'level-1'], ok=False)
    invoke(['redistribute', 'add', 'A', 'ipv4', 'bgp', 'level-1', '--route-map', 'missing'], ok=False)
    invoke(['level', 'A', 'level-1'], ok=False)
    invoke(['del', 'A'])
    assert not db.get_table('ISIS_REDISTRIBUTE')


@pytest.mark.parametrize('args,expected', [
    (['summary'], 'show isis summary'),
    (['interface', 'Ethernet0', '--json'], 'show isis interface Ethernet0 json'),
    (['neighbor', '--detail', '--vrf', 'all'], 'show isis vrf all neighbor detail'),
    (['database', '0000.0000.0001.00-00', '--detail', '--json'],
     'show isis database detail 0000.0000.0001.00-00 json'),
    (['route', '--level', 'level-2', '--prefix-sid', '--backup', '--algorithm', '128',
      '--vrf', 'VrfBlue', '--json'],
     'show isis vrf VrfBlue route level-2 prefix-sid backup algorithm 128 json'),
    (['topology', '--algorithm', 'all'], 'show isis topology algorithm'),
    (['hostname'], 'show isis hostname'),
    (['spf-delay-ietf'], 'show isis spf-delay-ietf'),
    (['flex-algo', '255'], 'show isis flex-algo 255'),
    (['fast-reroute', 'summary', '--level', 'level-1'], 'show isis fast-reroute summary level-1'),
    (['segment-routing', 'node', '--algorithm', 'all'], 'show isis segment-routing node algorithm'),
    (['mpls-te', 'router', '--vrf', 'VrfBlue'], 'show isis vrf VrfBlue mpls-te router'),
    (['mpls-te', 'interface', 'Ethernet0'], 'show isis mpls-te interface Ethernet0'),
    (['mpls-te', 'database', 'edge', '2001:db8::1', '--json'],
     'show isis mpls-te database edge 2001:db8::1 json'),
    (['mpls-te', 'database', 'subnet', '192.0.2.0/24', '--detail'],
     'show isis mpls-te database subnet 192.0.2.0/24 detail'),
    (['mpls', 'ldp-sync', 'interface', 'all'], 'show isis mpls ldp-sync interface all'),
])
def test_show_mapping(args, expected):
    with patch.object(show_isis, 'run_vtysh_command', return_value='state\n') as run:
        result = CliRunner().invoke(show_isis.isis, args)
    assert result.exit_code == 0, result.output + repr(result.exception)
    run.assert_called_once_with(expected, None)


@pytest.mark.parametrize('args', [
    ['interface', 'Ethernet0', '--detail'], ['neighbor', '0000.0000.0001', '--detail'],
    ['mpls-te', 'database', '--detail', '--json'], ['route', '--algorithm', '127'],
    ['flex-algo', '256'], ['segment-routing', 'node', '--vrf', 'all'],
    ['hostname', '--json'], ['mpls', 'ldp-sync', 'interface'],
    ['mpls-te', 'database', 'edge', 'invalid'], ['summary', '--instance', 'A'],
])
def test_show_rejects_invalid_options(args):
    with patch.object(show_isis, 'run_vtysh_command') as run:
        result = CliRunner().invoke(show_isis.isis, args)
    assert result.exit_code != 0
    run.assert_not_called()


def test_configuration_defaults_and_instance_filter(cli):
    db, invoke = cli
    invoke(['add', 'A'])
    invoke(['add', 'B'])
    invoke(['ipv4', 'Ethernet0', 'enable', '--instance', 'A'], interface=True)
    with patch.object(show_isis, 'ConfigDBConnector', return_value=db):
        result = CliRunner().invoke(show_isis.isis, ['configuration', '--instance', 'A'])
    assert result.exit_code == 0, result.output
    output = json.loads(result.output)
    assert list(output['ISIS_GLOBALS']) == ['default|A']
    assert output['ISIS_GLOBALS']['default|A']['explicit'] == {}
    assert output['ISIS_GLOBALS']['default|A']['effective']['lsp_mtu'] == '1497'
    assert output['ISIS_INTERFACE']['default|Ethernet0']['effective']['ipv6_enabled'] == 'false'


def test_group_namespace_routes_config_and_show(cli):
    db, invoke = cli
    with patch.object(config_isis, 'ConfigDBConnector', return_value=db) as connector:
        # Multi-ASIC namespace enumeration is resolved when the module loads.
        namespace_option = next(p for p in config_isis.ISIS.params if p.name == 'namespace')
        with patch.object(namespace_option.type, 'choices', ['asic0']):
            invoke(['--namespace', 'asic0', 'add', 'A'])
    connector.assert_called_once_with(use_unix_socket_path=True, namespace='asic0')
    option = next(p for p in show_isis.isis.params if p.name == 'namespace')
    with patch.object(option, 'callback', None), patch.object(
            show_isis, 'run_vtysh_command', return_value='state') as run:
        result = CliRunner().invoke(show_isis.isis, ['--namespace', 'asic0', 'summary'])
    assert result.exit_code == 0
    run.assert_called_once_with('show isis summary', 'asic0')


@pytest.mark.parametrize('interface,command,field,first,second', [
    (False, 'level', 'level', 'level-1', 'level-2'),
    (False, 'dynamic-hostname', 'dynamic_hostname', 'disable', 'enable'),
    (False, 'lsp-mtu', 'lsp_mtu', '1400', '1497'),
    (False, 'ipv6-multi-topology', 'ipv6_multi_topology', 'enable', 'disable'),
    (False, 'overload', 'overload', 'enable', 'disable'),
    (False, 'overload-on-startup', 'overload_on_startup', '60', '120'),
    (True, 'level', 'level', 'level-1', 'level-2'),
    (True, 'network-type', 'network_type', 'p2p', 'lan'),
    (True, 'passive', 'passive', 'enable', 'disable'),
])
def test_scalar_attribute_set_update_reset(cli, interface, command, field, first, second):
    db, invoke = cli
    invoke(['add', 'A'])
    invoke(['net', 'A', '49.0001.0000.0000.0001.00'])
    if interface:
        invoke(['ipv4', 'Ethernet0', 'enable', '--instance', 'A'], interface=True)
    target = 'Ethernet0' if interface else 'A'
    table = 'ISIS_INTERFACE' if interface else 'ISIS_GLOBALS'
    key = ('default', target)
    baseline = db.get_entry(table, key)
    for value in (first, second):
        invoke([command, target, value], interface=interface)
        stored = {'enable': 'true', 'disable': 'false'}.get(value, value)
        assert db.get_entry(table, key) == dict(baseline, **{field: stored})
    invoke(['reset', target, command], interface=interface)
    assert db.get_entry(table, key) == baseline


@pytest.mark.parametrize('interface,command,field,l1,l2,updated,level', [
    values + (level,)
    for values in [
        (False, 'lsp-gen-interval', 'lsp_generation_interval', '40', '50', '60'),
        (False, 'lsp-refresh-interval', 'lsp_refresh_interval', '500', '600', '700'),
        (False, 'max-lsp-lifetime', 'lsp_lifetime', '1500', '1600', '1700'),
        (False, 'spf-interval', 'spf_minimum_interval', '5', '6', '7'),
        (True, 'metric', 'metric', '20', '30', '40'),
        (True, 'hello-interval', 'hello_interval', '5', '6', '7'),
        (True, 'hello-multiplier', 'hello_multiplier', '4', '5', '6'),
    ]
    for level in ('level-1', 'level-2', 'both')
])
def test_per_level_attribute_update_reset_preserves_siblings(
        cli, interface, command, field, l1, l2, updated, level):
    db, invoke = cli
    invoke(['add', 'A'])
    if interface:
        invoke(['ipv4', 'Ethernet0', 'enable', '--instance', 'A'], interface=True)
    else:
        invoke(['net', 'A', '49.0001.0000.0000.0001.00'])
    target = 'Ethernet0' if interface else 'A'
    table = 'ISIS_INTERFACE' if interface else 'ISIS_GLOBALS'
    key = ('default', target)
    baseline = db.get_entry(table, key)
    fields = [field + '_level_1', field + '_level_2']
    for n, value in ((1, l1), (2, l2)):
        invoke([command, target, value, '--level', 'level-' + str(n)], interface=interface)
    expected = dict(baseline, **dict(zip(fields, (l1, l2))))
    assert db.get_entry(table, key) == expected
    selected = fields if level == 'both' else [fields[int(level[-1]) - 1]]
    invoke([command, target, updated, '--level', level], interface=interface)
    expected.update({name: updated for name in selected})
    assert db.get_entry(table, key) == expected
    invoke(['reset', target, command, '--level', level], interface=interface)
    for name in selected:
        expected.pop(name)
    assert db.get_entry(table, key) == expected


@pytest.mark.parametrize('interface,command,low,high', [
    (False, 'lsp-mtu', '127', '4353'),
    (False, 'overload-on-startup', '-1', '86401'),
    (False, 'lsp-gen-interval', '0', '121'),
    (False, 'lsp-refresh-interval', '0', '65236'),
    (False, 'max-lsp-lifetime', '349', '65536'),
    (False, 'spf-interval', '0', '121'),
    (True, 'metric', '-1', '16777216'),
    (True, 'hello-interval', '0', '601'),
    (True, 'hello-multiplier', '1', '101'),
])
def test_numeric_attribute_rejects_out_of_range_without_writes(cli, interface, command, low, high):
    db, invoke = cli
    invoke(['add', 'A'])
    if interface:
        invoke(['ipv4', 'Ethernet0', 'enable', '--instance', 'A'], interface=True)
    before = copy.deepcopy(db.tables)
    for value in (low, high):
        with patch.object(db, 'set_entry', wraps=db.set_entry) as write:
            invoke([command, 'Ethernet0' if interface else 'A', value], interface=interface, ok=False)
        write.assert_not_called()
        assert db.tables == before


@pytest.mark.parametrize('af,source', [('ipv4', 'ospf'), ('ipv6', 'ospf6')])
def test_ordinary_redistribution_af_update_and_delete(cli, af, source):
    db, invoke = cli
    invoke(['add', 'A'])
    prefix = ['redistribute', 'add', 'A', af, source, 'level-1']
    key = ('default', 'A', af, source, 'level-1', '0')
    invoke(prefix + ['--metric', '16777215', '--route-map', 'FILTER'])
    assert db.get_entry('ISIS_REDISTRIBUTE', key) == {'metric': '16777215', 'route_map': ['FILTER']}
    invoke(prefix)
    assert db.get_entry('ISIS_REDISTRIBUTE', key) == {'metric': '0'}
    invoke(['redistribute', 'del', 'A', af, source, 'level-1'])
    assert not db.get_table('ISIS_REDISTRIBUTE')
    assert db.get_entry('ISIS_GLOBALS', ('default', 'A')) == {'NULL': 'NULL'}


def test_show_propagates_daemon_failure():
    with patch.object(show_isis.bgp_util, 'get_vtysh_shell_cmd', return_value='vtysh', create=True), \
            patch.object(show_isis.bgp_util, 'run_bgp_command', side_effect=SystemExit(1), create=True) as run:
        result = CliRunner().invoke(show_isis.isis, ['neighbor', '--json'])
    assert result.exit_code == 1
    run.assert_called_once_with('show isis neighbor json', None, 'vtysh')

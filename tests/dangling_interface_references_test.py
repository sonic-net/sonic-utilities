import re
from unittest import mock

import pytest

from utilities_common.dangling_interface_references import (INTERFACE_REFERENCES, Dangling, InterfaceRule,
                                                            ScopedTarget, _is_ip_address,
                                                            find_dangling_interface_references,
                                                            interface_reference_rules, may_dangle,
                                                            plan_dangling_interface_repairs)

PORT_PATH = '/port:sonic-port/port:PORT/port:PORT_LIST/port:name'
PORTCHANNEL_PATH = '/lag:sonic-portchannel/lag:PORTCHANNEL/lag:PORTCHANNEL_LIST/lag:name'
VLAN_PATH = '/vlan:sonic-vlan/vlan:VLAN/vlan:VLAN_LIST/vlan:name'
LOOPBACK_PATH = '/lointf:sonic-loopback-interface/lointf:LOOPBACK_INTERFACE/lointf:LOOPBACK_INTERFACE_LIST/lointf:name'
MGMT_PATH = '/mgmt-port:sonic-mgmt_port/mgmt-port:MGMT_PORT/mgmt-port:MGMT_PORT_LIST/mgmt-port:name'

LAG_TARGETS = ('PORT', 'PORTCHANNEL')
SOURCE_TARGETS = ('PORT', 'PORTCHANNEL', 'VLAN', 'LOOPBACK_INTERFACE', 'MGMT_PORT')
NO_VLAN_SOURCES = ('PORT', 'PORTCHANNEL', 'LOOPBACK_INTERFACE', 'MGMT_PORT')
VLAN_PATTERN = 'Vlan([0-9]{1,3}|[1-3][0-9]{3}|[4][0][0-8][0-9]|[4][0][9][0-4])'


def spec(table, leaf):
    return next(s for s in INTERFACE_REFERENCES if s.table == table and s.leaf == leaf)


TACACS = spec('TACPLUS', 'src_intf')
SFLOW = spec('SFLOW', 'agent_id')
NTP = spec('NTP', 'src_intf')
RADIUS = spec('RADIUS_SERVER', 'src_intf')


@pytest.fixture(autouse=True)
def union_member_types():
    """
    SonicYang.union_member_types for the stand-in union types below; a real
    libyang type goes to the real method.
    """
    import sonic_yang
    real = getattr(sonic_yang.SonicYang, 'union_member_types', None)

    def members(leaf_type):
        if isinstance(leaf_type, mock.Mock):
            return list(leaf_type.union_types(with_typedefs=True))
        if real is None:
            pytest.skip('this sonic_yang has no SonicYang.union_member_types')
        return real(leaf_type)
    with mock.patch.object(sonic_yang.SonicYang, 'union_member_types', staticmethod(members), create=True):
        yield


def pattern(expression, inverted=False):
    detail = mock.Mock()
    detail.expression.return_value = expression
    detail.inverted.return_value = inverted
    return detail


def string_type(*patterns):
    leaf_type = mock.Mock()
    leaf_type.basename.return_value = 'string'
    leaf_type.leafref_path.return_value = None
    leaf_type.pattern_details.side_effect = lambda: iter(patterns)
    return leaf_type


def leafref_type(path):
    leaf_type = mock.Mock()
    leaf_type.basename.return_value = 'leafref'
    leaf_type.leafref_path.return_value = path
    return leaf_type


def union_type(*members):
    leaf_type = mock.Mock()
    leaf_type.basename.return_value = 'union'
    leaf_type.union_types.side_effect = lambda with_typedefs=False: iter(members)
    return leaf_type


def yang_leaf(name, leaf_type, keyword='leaf', mandatory=False, min_elements=0):
    leaf = mock.Mock()
    leaf.keyword.return_value = keyword
    leaf.name.return_value = name
    leaf.type.return_value = leaf_type
    leaf.mandatory.return_value = mandatory
    leaf.min_elements.return_value = min_elements
    return leaf


def models_with(leaves):
    """A SonicYang whose tables each hold one entry with the given leaves ({table: [leaf, ...]})."""
    sy = mock.Mock()
    sy.confDbYangMap = {}
    for table, table_leaves in leaves.items():
        entry = mock.Mock()
        entry.children.return_value = [yang_leaf('other', string_type())] + table_leaves
        container = mock.Mock()
        container.children.return_value = [entry]
        sy.confDbYangMap[table] = {'container': container}
    return sy


def leafrefs(*paths):
    return union_type(*[leafref_type(path) for path in paths])


SOURCE_PATHS = (PORT_PATH, PORTCHANNEL_PATH, VLAN_PATH, LOOPBACK_PATH, MGMT_PATH)
NO_VLAN_PATHS = (PORT_PATH, PORTCHANNEL_PATH, LOOPBACK_PATH, MGMT_PATH)


def new_models():
    return models_with({
        'TACPLUS': [yang_leaf('src_intf', leafrefs(*SOURCE_PATHS))],
        'SFLOW': [yang_leaf('agent_id', leafrefs(*SOURCE_PATHS))],
        'NTP': [yang_leaf('src_intf', union_type(*[leafref_type(path) for path in NO_VLAN_PATHS],
                                                 string_type(pattern('eth0'))), keyword='leaf-list')],
        'RADIUS_SERVER': [yang_leaf('src_intf', union_type(*[leafref_type(path) for path in NO_VLAN_PATHS],
                                                           string_type(pattern(VLAN_PATTERN))))],
    })


def rule(targets, patterns=(), required=0):
    return InterfaceRule(tuple(tuple((re.compile(p), False) for p in group) for group in patterns), targets, required)


RULES = {
    TACACS: rule(SOURCE_TARGETS),
    # The current sFlow agent_id: the leafrefs and a Vlan pattern.
    SFLOW: rule(SOURCE_TARGETS, [[VLAN_PATTERN]]),
    # The current NTP src_intf (no VLAN) and RADIUS_SERVER src_intf (a Vlan pattern).
    NTP: rule(NO_VLAN_SOURCES, [['eth0']]),
    RADIUS: rule(NO_VLAN_SOURCES, [[VLAN_PATTERN]]),
}


class TestInterfaceReferenceRules(object):

    def test_new_models(self):
        rules = interface_reference_rules(new_models())
        assert list(rules) == [TACACS, SFLOW, NTP, RADIUS]
        assert rules[TACACS] == InterfaceRule((), SOURCE_TARGETS, 0)
        assert rules[SFLOW] == InterfaceRule((), SOURCE_TARGETS, 0)
        assert rules[NTP].targets == NO_VLAN_SOURCES
        assert [[(regex.pattern, inverted) for regex, inverted in group]
                for group in rules[NTP].patterns] == [[('eth0', False)]]
        assert [[regex.pattern for regex, _ in group] for group in rules[RADIUS].patterns] == [[VLAN_PATTERN]]

    def test_current_source_interface_with_leafrefs_and_a_vlan_pattern(self):
        sy = models_with({'SFLOW': [yang_leaf('agent_id', union_type(
            leafref_type(PORT_PATH), leafref_type(PORTCHANNEL_PATH), leafref_type(MGMT_PATH),
            leafref_type(LOOPBACK_PATH), leafref_type(VLAN_PATH), string_type(pattern(VLAN_PATTERN))))]})
        sflow = interface_reference_rules(sy)[SFLOW]
        assert sflow.targets == ('PORT', 'PORTCHANNEL', 'MGMT_PORT', 'LOOPBACK_INTERFACE', 'VLAN')
        assert [[regex.pattern for regex, _ in group] for group in sflow.patterns] == [[VLAN_PATTERN]]

    def test_patterns_only_have_no_rule(self):
        sy = models_with({
            'TACPLUS': [yang_leaf('src_intf', string_type(pattern('Ethernet[0-9]+|Vlan[0-9]+')))],
            'NTP': [yang_leaf('src_intf', string_type(pattern('Ethernet[0-9]+')), keyword='leaf-list')],
            'SFLOW': [yang_leaf('agent_id', string_type())],
        })
        assert interface_reference_rules(sy) == {}

    def test_a_leaf_of_the_wrong_kind_has_no_rule(self):
        sy = models_with({'NTP': [yang_leaf('src_intf', leafref_type(PORT_PATH))]})
        assert interface_reference_rules(sy) == {}

    def test_a_plain_leafref(self):
        rules = interface_reference_rules(models_with({'TACPLUS': [yang_leaf('src_intf', leafref_type(PORT_PATH))]}))
        assert rules == {TACACS: InterfaceRule((), ('PORT',), 0)}

    def test_a_mandatory_leaf_is_required(self):
        rules = interface_reference_rules(models_with({'RADIUS_SERVER': [
            yang_leaf('src_intf', leafref_type(PORT_PATH), mandatory=True)]}))
        assert rules == {RADIUS: InterfaceRule((), ('PORT',), 1)}

    def test_a_leaf_lists_min_elements_are_required(self):
        rules = interface_reference_rules(models_with({'NTP': [
            yang_leaf('src_intf', leafref_type(PORT_PATH), keyword='leaf-list', min_elements=2)]}))
        assert rules == {NTP: InterfaceRule((), ('PORT',), 2)}

    def test_nested_unions_are_flattened(self):
        sy = models_with({'TACPLUS': [yang_leaf('src_intf', union_type(
            union_type(leafref_type(PORT_PATH), string_type(pattern('Vlan[0-9]+'))), leafref_type(VLAN_PATH)))]})
        tacacs = interface_reference_rules(sy)[TACACS]
        assert tacacs.targets == ('PORT', 'VLAN')
        assert [regex.pattern for group in tacacs.patterns for regex, _ in group] == ['Vlan[0-9]+']

    def test_a_pattern_python_cannot_compile_is_kept_as_none(self):
        sy = models_with({'TACPLUS': [yang_leaf('src_intf', union_type(
            string_type(pattern(r'\i\c*')), leafref_type(PORT_PATH)))]})
        assert interface_reference_rules(sy)[TACACS].patterns == (((None, False),),)

    @pytest.mark.parametrize('member', [string_type(), leafref_type('/foo:bar/foo:name')])
    def test_a_member_accepting_anything_is_an_empty_group(self, member):
        sy = models_with({'TACPLUS': [yang_leaf('src_intf', union_type(member, leafref_type(PORT_PATH)))]})
        assert interface_reference_rules(sy)[TACACS].patterns == ((),)

    def test_models_without_the_tables(self):
        assert interface_reference_rules(models_with({})) == {}


def config_file(**tables):
    config = {
        'PORT': {'Ethernet0': {'lanes': '0'}, 'Ethernet4': {'lanes': '4'}},
        'PORTCHANNEL': {'PortChannel1': {'mtu': '9100'}},
        'VLAN': {'Vlan100': {'vlanid': '100'}},
        'VLAN_SUB_INTERFACE': {'Ethernet0.10': {}, 'Ethernet0.10|10.2.0.1/24': {}},
        'LOOPBACK_INTERFACE': {'Loopback0|10.3.0.1/32': {}},
        'MGMT_PORT': {'eth0': {}},
    }
    config.update(tables)
    return config


def split(config, rules):
    """
    (kept, removed, reasons): config with each repair plan_dangling_interface_repairs
    plans applied, what each repair removed, and its reasons. config is left as it was.
    """
    kept = dict(config)
    removed = {}
    reasons = []
    for repair in plan_dangling_interface_repairs(config, rules):
        if kept[repair.table] is config[repair.table]:
            kept[repair.table] = dict(config[repair.table])
        if repair.entry is None:
            del kept[repair.table][repair.key]
        else:
            kept[repair.table][repair.key] = repair.entry
        removed.setdefault(repair.table, {})[repair.key] = repair.removed
        reasons.extend(repair.reasons)
    return kept, removed, reasons


class TestFindDanglingInterfaceReferences(object):

    def test_fields_and_leaf_list_elements(self):
        config = config_file(
            TACPLUS={'global': {'src_intf': 'Ethernet8'}},
            SFLOW={'global': {'agent_id': 'Loopback0'}},
            NTP={'global': {'src_intf': ['eth0', 'Ethernet8', 'PortChannel2']}},
            RADIUS_SERVER={'10.0.0.9': {'src_intf': 'Ethernet12'}, '10.0.0.10': {'src_intf': 'PortChannel1'}})
        assert find_dangling_interface_references(config, RULES) == [
            Dangling(TACACS, 'global', ('Ethernet8',)),
            Dangling(NTP, 'global', ('Ethernet8', 'PortChannel2')),
            Dangling(RADIUS, '10.0.0.9', ('Ethernet12',)),
        ]

    def test_a_comma_separated_leaf_list(self):
        config = config_file(NTP={'global': {'src_intf': 'Loopback0,Ethernet8'}})
        assert find_dangling_interface_references(config, RULES) == [Dangling(NTP, 'global', ('Ethernet8',))]

    @pytest.mark.parametrize('agent_id,dangling', [
        ('Ethernet0', False), ('Vlan100', False), ('Loopback0', False), ('eth0', False),
        # The current Vlan pattern accepts a VLAN that does not exist, and so does this.
        ('Vlan200', False),
        ('Ethernet8', True), ('Loopback1', True), ('eth1', True),
    ])
    def test_current_sflow_agent_id(self, agent_id, dangling):
        config = config_file(SFLOW={'global': {'admin_state': 'up', 'agent_id': agent_id}})
        found = find_dangling_interface_references(config, RULES)
        assert found == ([Dangling(SFLOW, 'global', (agent_id,))] if dangling else [])

    @pytest.mark.parametrize('src_intf,dangling', [
        ('Ethernet0', False), ('PortChannel1', False), ('Vlan100', False), ('Loopback0', False), ('eth0', False),
        ('Vlan200', True), ('Ethernet8', True),
    ])
    def test_tacacs_source_interface(self, src_intf, dangling):
        config = config_file(TACPLUS={'global': {'src_intf': src_intf}})
        found = find_dangling_interface_references(config, RULES)
        assert found == ([Dangling(TACACS, 'global', (src_intf,))] if dangling else [])

    @pytest.mark.parametrize('src_intf,dangling', [
        (['Loopback0', 'eth0'], ()), (['Ethernet8', 'Loopback0'], ('Ethernet8',)),
        # NTP's models leave VLAN out, so no VLAN is a valid source.
        (['Vlan100'], ('Vlan100',)),
    ])
    def test_ntp_source_interfaces(self, src_intf, dangling):
        config = config_file(NTP={'global': {'src_intf': src_intf}})
        found = find_dangling_interface_references(config, RULES)
        assert found == ([Dangling(NTP, 'global', dangling)] if dangling else [])

    @pytest.mark.parametrize('src_intf,dangling', [
        ('Loopback0', False), ('Vlan200', False), ('Ethernet8', True)])
    def test_radius_server_source_interface(self, src_intf, dangling):
        config = config_file(RADIUS_SERVER={'10.0.0.9': {'src_intf': src_intf, 'priority': '1'}})
        found = find_dangling_interface_references(config, RULES)
        assert found == ([Dangling(RADIUS, '10.0.0.9', (src_intf,))] if dangling else [])

    def test_only_specs_with_a_rule(self):
        config = config_file(TACPLUS={'global': {'src_intf': 'Ethernet8'}})
        assert find_dangling_interface_references(config, {NTP: RULES[NTP]}) == []

    def test_an_empty_port_table_keeps_references_to_ports(self):
        # A loopback is left, so the targets are not all empty, but PORT reading empty is a broken read.
        config = {'PORT': {}, 'LOOPBACK_INTERFACE': {'Loopback0|10.3.0.1/32': {}},
                  'TACPLUS': {'global': {'src_intf': 'Ethernet8'}},
                  'NTP': {'global': {'src_intf': ['Loopback0', 'Ethernet8']}}}
        assert find_dangling_interface_references(config, RULES) == []
        assert plan_dangling_interface_repairs(config, RULES) == []

    def test_empty_targets_find_nothing(self):
        config = {'TACPLUS': {'global': {'src_intf': 'Ethernet8'}}, 'NTP': {'global': {'src_intf': ['Ethernet8']}}}
        assert find_dangling_interface_references(config, RULES) == []

    def test_a_pattern_python_cannot_compile_matches_everything(self):
        rules = {TACACS: InterfaceRule((((None, False),),), ('PORT',), 0)}
        config = config_file(TACPLUS={'global': {'src_intf': 'Ethernet8'}})
        assert find_dangling_interface_references(config, rules) == []

    def test_an_inverted_pattern(self):
        rules = {RADIUS: InterfaceRule((((re.compile('Ethernet.*'), True),),), ('PORT',), 0)}
        config = config_file(RADIUS_SERVER={'10.0.0.9': {'src_intf': 'Ethernet12'},
                                            '10.0.0.10': {'src_intf': 'Foo1'}})
        assert find_dangling_interface_references(config, rules) == [Dangling(RADIUS, '10.0.0.9', ('Ethernet12',))]


class TestPlanDanglingInterfaceRepairs(object):
    """One test per action: drop the row, delete the field, remove the element."""

    def repairs(self, rules=None, **tables):
        return {(r.table, r.key): (r.entry, r.removed, r.reasons)
                for r in plan_dangling_interface_repairs(config_file(**tables), RULES if rules is None else rules)}

    def test_a_mandatory_field_drops_the_row(self):
        row = {'src_intf': 'Ethernet8', 'priority': '1'}
        assert self.repairs({RADIUS: rule(('PORT',), required=1)}, RADIUS_SERVER={'10.0.0.9': row}) == {
            ('RADIUS_SERVER', '10.0.0.9'): (None, row, [
                "RADIUS_SERVER|10.0.0.9 dropped: src_intf Ethernet8 is in none of PORT"])}

    def test_an_optional_field_is_deleted(self):
        assert self.repairs(RADIUS_SERVER={'10.0.0.9': {'src_intf': 'Ethernet8', 'priority': '1'}}) == {
            ('RADIUS_SERVER', '10.0.0.9'): ({'priority': '1'}, {'src_intf': 'Ethernet8'}, [
                "RADIUS_SERVER|10.0.0.9 src_intf Ethernet8 dropped: it is in none of PORT, PORTCHANNEL, "
                "LOOPBACK_INTERFACE, MGMT_PORT"])}

    def test_a_singleton_rows_field_is_deleted(self):
        assert self.repairs(TACPLUS={'global': {'src_intf': 'Vlan200', 'timeout': '5'}}) == {
            ('TACPLUS', 'global'): ({'timeout': '5'}, {'src_intf': 'Vlan200'}, [
                "TACPLUS|global src_intf Vlan200 dropped: it is in none of PORT, PORTCHANNEL, VLAN, "
                "LOOPBACK_INTERFACE, MGMT_PORT"])}

    def test_a_leaf_list_loses_the_element(self):
        assert self.repairs(NTP={'global': {'src_intf': ['eth0', 'Ethernet8'], 'vrf': 'default'}}) == {
            ('NTP', 'global'): (
                {'src_intf': ['eth0'], 'vrf': 'default'}, {'src_intf': ['eth0', 'Ethernet8']},
                ["NTP|global src_intf Ethernet8 dropped: in none of PORT, PORTCHANNEL, LOOPBACK_INTERFACE, "
                 "MGMT_PORT"])}

    def test_an_emptied_leaf_list_is_deleted(self):
        assert self.repairs(NTP={'global': {'src_intf': ['Ethernet8', 'Ethernet12'], 'vrf': 'default'}}) == {
            ('NTP', 'global'): (
                {'vrf': 'default'}, {'src_intf': ['Ethernet8', 'Ethernet12']},
                ["NTP|global src_intf dropped: Ethernet8, Ethernet12 are in none of PORT, PORTCHANNEL, "
                 "LOOPBACK_INTERFACE, MGMT_PORT, and it held nothing else"])}

    def test_a_leaf_list_below_its_min_elements_drops_the_row(self):
        # A stand-in model giving src_intf min-elements 1; no shipped model does.
        row = {'src_intf': ['Ethernet8'], 'vrf': 'default'}
        assert self.repairs({NTP: rule(LAG_TARGETS, required=1)}, NTP={'global': row}) == {
            ('NTP', 'global'): (None, row, [
                "NTP|global dropped: src_intf Ethernet8 is in none of PORT, PORTCHANNEL, which leaves fewer than "
                "its 1 required"])}

    def test_the_input_is_left_as_it_was(self):
        row = {'src_intf': ['eth0', 'Ethernet8']}
        self.repairs(NTP={'global': row})
        assert row == {'src_intf': ['eth0', 'Ethernet8']}

    def test_merging_removed_back_restores_a_leaf_list(self):
        row = {'src_intf': ['eth0', 'Ethernet8'], 'vrf': 'default'}
        kept, removed, _ = split(config_file(NTP={'global': row}), RULES)
        assert dict(kept['NTP']['global'], **removed['NTP']['global']) == row


class TestApplyingTheRepairs(object):

    def test_fields_and_elements_are_repaired(self):
        config = config_file(
            TACPLUS={'global': {'src_intf': 'Vlan200', 'timeout': '5'}},
            SFLOW={'global': {'agent_id': 'Ethernet8', 'admin_state': 'up'}},
            NTP={'global': {'src_intf': ['eth0', 'Ethernet8']}},
            RADIUS_SERVER={'10.0.0.9': {'src_intf': 'Loopback0'}})
        kept, removed, reasons = split(config, RULES)
        assert kept == config_file(
            TACPLUS={'global': {'timeout': '5'}},
            SFLOW={'global': {'admin_state': 'up'}},
            NTP={'global': {'src_intf': ['eth0']}},
            RADIUS_SERVER={'10.0.0.9': {'src_intf': 'Loopback0'}})
        assert removed == {
            'TACPLUS': {'global': {'src_intf': 'Vlan200'}},
            'SFLOW': {'global': {'agent_id': 'Ethernet8'}},
            'NTP': {'global': {'src_intf': ['eth0', 'Ethernet8']}},
        }
        assert reasons == [
            "TACPLUS|global src_intf Vlan200 dropped: it is in none of PORT, PORTCHANNEL, VLAN, LOOPBACK_INTERFACE, "
            "MGMT_PORT",
            "SFLOW|global agent_id Ethernet8 dropped: it is in none of PORT, PORTCHANNEL, VLAN, LOOPBACK_INTERFACE, "
            "MGMT_PORT",
            "NTP|global src_intf Ethernet8 dropped: in none of PORT, PORTCHANNEL, LOOPBACK_INTERFACE, MGMT_PORT",
        ]
        assert config['NTP']['global']['src_intf'] == ['eth0', 'Ethernet8'], "the input is left as it was"

    def test_no_rules_keep_everything(self):
        config = config_file(TACPLUS={'global': {'src_intf': 'Ethernet8'}})
        assert split(config, {}) == (config, {}, [])

    @pytest.mark.parametrize('config', [
        {},
        config_file(TACPLUS={'global': {'src_intf': 'Ethernet0'}}),
    ])
    def test_nothing_dangling(self, config):
        assert split(config, RULES) == (config, {}, [])


class TestMayDangle(object):
    CONFIG = {
        "PORT": {"Ethernet0": {}},
        "VLAN": {"Vlan100": {}},
        "LOOPBACK_INTERFACE": {("Loopback0", "10.1.0.1/32"): {}},
    }

    def config(self, **tables):
        return dict(self.CONFIG, **tables)

    @pytest.mark.parametrize("src_intf,expected", [
        ("Loopback0", False), ("Vlan100", False), ("Vlan200", True), ("Ethernet8", True)])
    def test_tacacs_source_interface(self, src_intf, expected):
        assert may_dangle(self.config(TACPLUS={"global": {"src_intf": src_intf}})) is expected

    def test_eth0_without_a_mgmt_port_row(self):
        # ZTP brings eth0 up with no MGMT_PORT row; NTP's pattern accepts it, TACACS+ has none.
        assert not may_dangle(self.config(NTP={"global": {"src_intf": ["eth0"]}}))
        assert may_dangle(self.config(TACPLUS={"global": {"src_intf": "eth0"}}))
        assert not may_dangle(self.config(TACPLUS={"global": {"src_intf": "eth0"}}, MGMT_PORT={"eth0": {}}))

    def test_leaf_list_elements(self):
        assert not may_dangle(self.config(NTP={"global": {"src_intf": ["Ethernet0"]}}))
        assert may_dangle(self.config(NTP={"global": {"src_intf": ["Ethernet0", "Ethernet8"]}}))

    def test_a_value_only_a_table_outside_the_known_targets_holds__true(self):
        # A VLAN exists, but NTP's known targets leave VLAN out.
        assert may_dangle(self.config(NTP={"global": {"src_intf": ["Vlan100"]}}))

    def test_a_row_without_the_field(self):
        assert not may_dangle(self.config(SFLOW={"global": {"admin_state": "up"}}))


# Mirrors the shapes of the referencing models: TACPLUS|global src_intf an optional
# scalar in a singleton container, and NTP|global src_intf a leaf-list.
MODELS_YANG = '''
module test-dangling-interface-references {{
  namespace "http://example.com/test-dangling-interface-references";
  prefix tdir;

  container sonic-test {{
    container PORT {{ list PORT_LIST {{ key "name"; leaf name {{ type string; }} }} }}
    container PORTCHANNEL {{ list PORTCHANNEL_LIST {{ key "name"; leaf name {{ type string; }} }} }}
    container VLAN {{ list VLAN_LIST {{ key "name"; leaf name {{ type string; }} }} }}
    container LOOPBACK_INTERFACE {{ list LOOPBACK_INTERFACE_LIST {{ key "name"; leaf name {{ type string; }} }} }}
    container MGMT_PORT {{ list MGMT_PORT_LIST {{ key "name"; leaf name {{ type string; }} }} }}
    container TACPLUS {{
      container global {{
        leaf timeout {{ type string; }}
        leaf src_intf {{
          {src_intf_type}
        }}
      }}
    }}
    container NTP {{
      container global {{
        leaf vrf {{ type string; }}
        leaf-list src_intf {{
          {ntp_type}
        }}
      }}
    }}
  }}
}}
'''


def leafref(table):
    return 'type leafref {{ path "/tdir:sonic-test/tdir:{0}/tdir:{0}_LIST/tdir:name"; }}'.format(table)


def union_of(*tables, pattern=None):
    members = (['type string {{ pattern "{}"; }}'.format(pattern)] if pattern else []) + [leafref(t) for t in tables]
    return 'type union { ' + ' '.join(members) + ' }'


NEW_SHAPES = dict(
    src_intf_type=union_of(*SOURCE_TARGETS),
    ntp_type=union_of(*NO_VLAN_SOURCES, pattern='eth0'))
CURRENT_SHAPES = dict(
    # The current TACPLUS src_intf has leafrefs beside its Vlan pattern.
    src_intf_type=union_of('PORT', 'PORTCHANNEL', 'LOOPBACK_INTERFACE', 'MGMT_PORT', pattern=VLAN_PATTERN),
    ntp_type="type string { pattern 'Ethernet[0-9]+|Loopback[0-9]+|eth0'; }")


class TestInterfaceReferenceRulesWithLibyang(object):
    """The rules against libyang's own schema nodes rather than stand-ins."""

    def rules(self, shapes):
        libyang = pytest.importorskip('libyang')
        ctx = libyang.Context()
        try:
            module = ctx.parse_module_str(MODELS_YANG.format(**shapes))
            sy = mock.Mock()
            sy.confDbYangMap = {table.name(): {'container': table}
                                for top in module.children() for table in top.children()}
            return interface_reference_rules(sy)
        finally:
            ctx.destroy()

    def test_new_shapes(self):
        rules = self.rules(NEW_SHAPES)
        assert {s: (r.targets, r.required) for s, r in rules.items()} == {
            TACACS: (SOURCE_TARGETS, 0),
            NTP: (NO_VLAN_SOURCES, 0),
        }
        config = config_file(
            TACPLUS={'global': {'timeout': '5', 'src_intf': 'Vlan200'}},
            NTP={'global': {'src_intf': ['eth0', 'Ethernet8']}})
        kept, _, _ = split(config, rules)
        assert kept == config_file(
            TACPLUS={'global': {'timeout': '5'}},
            NTP={'global': {'src_intf': ['eth0']}})

    def test_current_shapes(self):
        rules = self.rules(CURRENT_SHAPES)
        assert list(rules) == [TACACS]
        assert rules[TACACS].targets == ('PORT', 'PORTCHANNEL', 'LOOPBACK_INTERFACE', 'MGMT_PORT')
        config = config_file(
            NTP={'global': {'src_intf': ['Ethernet8']}},
            TACPLUS={'global': {'src_intf': 'Vlan200'}})
        assert split(config, rules) == (config, {}, [])
        config['TACPLUS'] = {'global': {'src_intf': 'Ethernet8'}}
        assert split(config, rules)[1] == {'TACPLUS': {'global': {'src_intf': 'Ethernet8'}}}


BGP_NEIGHBOR = spec('BGP_NEIGHBOR', 'neighbor')
BGP_NEIGHBOR_AF = spec('BGP_NEIGHBOR_AF', 'neighbor')
BGP_LOCAL_ADDR = spec('BGP_NEIGHBOR', 'local_addr')
DHCP_SERVER = spec('DHCP_SERVER_IPV4', 'name')
DHCP_SERVER_PORT = spec('DHCP_SERVER_IPV4_PORT', 'name')
DHCP_RELAY = spec('DHCPV4_RELAY', 'name')
MATCH_NEIGHBOR = spec('ROUTE_MAP', 'match_neighbor')
DPU_VLAN = spec('DASH_HA_GLOBAL_CONFIG', 'dpu_vlan')
IPV4_OCTET = r'([0-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-5])'
IPV4_PATTERN = r'({0}\.){{3}}{0}'.format(IPV4_OCTET)
IPV6_PATTERN = r'[0-9a-fA-F:.]*:[0-9a-fA-F:.]*(%[\w]+)?'
NEIGHBOR_TARGETS = ('PORT', 'PORTCHANNEL', 'VLAN', 'VLAN_SUB_INTERFACE')
MIDPLANE = ('MID_PLANE_BRIDGE', 'GLOBAL', 'bridge')
SAME_VRF_NEIGHBOR = ScopedTarget('BGP_NEIGHBOR', 2, 0, 1, 0, 'vrf_name')
STP_VLAN_PORT = spec('STP_VLAN_PORT', 'vlan-name')
VLAN_MEMBER = spec('VLAN_MEMBER', 'name')
VLAN_INTERFACE = spec('VLAN_INTERFACE', 'name')

VLAN_RULES = {
    BGP_NEIGHBOR: rule(NEIGHBOR_TARGETS, [[IPV4_PATTERN], [IPV6_PATTERN]], 1),
    BGP_NEIGHBOR_AF: rule((SAME_VRF_NEIGHBOR,), required=1),
    BGP_LOCAL_ADDR: rule(('PORT', 'PORTCHANNEL', 'LOOPBACK_INTERFACE', 'VLAN'), [[IPV4_PATTERN], [IPV6_PATTERN]]),
    DHCP_SERVER: rule((MIDPLANE, 'VLAN'), required=1),
    DHCP_SERVER_PORT: rule(('DHCP_SERVER_IPV4',), required=1),
    DHCP_RELAY: rule(('PORT', 'VLAN'), required=1),
    MATCH_NEIGHBOR: rule(('PORT', 'PORTCHANNEL', 'VLAN'), [[IPV4_PATTERN], [IPV6_PATTERN]]),
    DPU_VLAN: rule(('VLAN',)),
    STP_VLAN_PORT: rule(('VLAN',), required=1),
    VLAN_MEMBER: rule(('VLAN',), required=1),
    VLAN_INTERFACE: rule(('VLAN',), required=1),
}


class TestVlanReferences(object):
    """References the VLAN models make leafrefs: BGP, DHCP, route maps and the DPU VLAN."""

    def test_a_bgp_neighbor_on_a_missing_vlan_drops_with_its_address_families(self):
        config = config_file(
            BGP_NEIGHBOR={'default|Vlan200': {'asn': '65001'}, 'default|Vlan100': {'asn': '65002'},
                          '10.0.0.1': {'asn': '65003'}, 'default|fe80::1%Vlan100': {'asn': '65004'},
                          'default|Ethernet0.10': {'asn': '65005'}, 'default|Ethernet0.20': {'asn': '65006'}},
            BGP_NEIGHBOR_AF={'default|Vlan200|ipv4_unicast': {'admin_status': 'up'},
                             'default|Vlan100|ipv4_unicast': {'admin_status': 'up'},
                             'default|Ethernet0.20|ipv6_unicast': {'admin_status': 'up'}})
        kept, removed, reasons = split(config, VLAN_RULES)
        assert set(kept['BGP_NEIGHBOR']) == {'default|Vlan100', '10.0.0.1', 'default|fe80::1%Vlan100',
                                             'default|Ethernet0.10'}
        assert set(kept['BGP_NEIGHBOR_AF']) == {'default|Vlan100|ipv4_unicast'}
        assert removed['BGP_NEIGHBOR_AF'] == {'default|Vlan200|ipv4_unicast': {'admin_status': 'up'},
                                              'default|Ethernet0.20|ipv6_unicast': {'admin_status': 'up'}}
        assert "BGP_NEIGHBOR|default|Vlan200 dropped: neighbor Vlan200 is in none of PORT, PORTCHANNEL, VLAN, " \
               "VLAN_SUB_INTERFACE" in reasons
        assert "BGP_NEIGHBOR_AF|default|Vlan200|ipv4_unicast dropped: neighbor Vlan200 is in none of " \
               "BGP_NEIGHBOR of the same vrf_name" in reasons

    def test_an_address_family_names_a_neighbor_of_its_own_vrf(self):
        config = config_file(BGP_NEIGHBOR={'default|10.0.0.1': {}, 'Vrf1|10.0.0.2': {}},
                             BGP_NEIGHBOR_AF={'Vrf1|10.0.0.1|ipv4_unicast': {}, 'default|10.0.0.1|ipv4_unicast': {},
                                              'Vrf1|10.0.0.2|ipv4_unicast': {}})
        kept, _, _ = split(config, VLAN_RULES)
        assert set(kept['BGP_NEIGHBOR_AF']) == {'default|10.0.0.1|ipv4_unicast', 'Vrf1|10.0.0.2|ipv4_unicast'}

    def test_a_vlan_drops_its_stp_ports_members_and_interface_rows(self):
        config = config_file(STP_VLAN_PORT={'Vlan200|Ethernet0': {}, 'Vlan100|Ethernet0': {}},
                             VLAN_MEMBER={'Vlan200|Ethernet4': {}, 'Vlan100|Ethernet4': {}},
                             VLAN_INTERFACE={'Vlan200': {}, 'Vlan200|10.0.0.1/24': {}, 'Vlan100': {},
                                             'Vlan100|10.0.1.1/24': {}})
        kept, _, _ = split(config, VLAN_RULES)
        assert set(kept['STP_VLAN_PORT']) == {'Vlan100|Ethernet0'}
        assert set(kept['VLAN_MEMBER']) == {'Vlan100|Ethernet4'}
        assert set(kept['VLAN_INTERFACE']) == {'Vlan100', 'Vlan100|10.0.1.1/24'}

    def test_rows_under_an_unwritable_row_stay(self):
        config = config_file(BGP_NEIGHBOR={'default|Vlan200': {}},
                             BGP_NEIGHBOR_AF={'default|Vlan200|ipv4_unicast': {}})
        assert plan_dangling_interface_repairs(config, VLAN_RULES, {('BGP_NEIGHBOR', 'default|Vlan200')}) == []

    def test_an_address_family_of_a_kept_neighbor_stays(self):
        config = config_file(BGP_NEIGHBOR={'default|10.0.0.1': {}},
                             BGP_NEIGHBOR_AF={'default|10.0.0.1|ipv4_unicast': {}})
        assert split(config, VLAN_RULES) == (config, {}, [])

    def test_address_families_are_left_alone_when_no_bgp_neighbor_was_read(self):
        config = config_file(BGP_NEIGHBOR_AF={'default|10.0.0.1|ipv4_unicast': {}})
        assert split(config, VLAN_RULES) == (config, {}, [])

    def test_a_local_addr_on_a_missing_vlan_is_deleted(self):
        config = config_file(BGP_NEIGHBOR={'10.0.0.1': {'asn': '65001', 'local_addr': 'Vlan200'},
                                           '10.0.0.2': {'asn': '65002', 'local_addr': '10.1.0.1'}})
        kept, removed, _ = split(config, VLAN_RULES)
        assert kept['BGP_NEIGHBOR'] == {'10.0.0.1': {'asn': '65001'},
                                        '10.0.0.2': {'asn': '65002', 'local_addr': '10.1.0.1'}}
        assert removed == {'BGP_NEIGHBOR': {'10.0.0.1': {'local_addr': 'Vlan200'}}}

    def test_a_dhcp_server_on_a_missing_vlan_drops_with_its_ports(self):
        config = config_file(
            MID_PLANE_BRIDGE={'GLOBAL': {'bridge': 'bridge-midplane'}},
            DHCP_SERVER_IPV4={'Vlan200': {'mode': 'PORT'}, 'Vlan100': {'mode': 'PORT'},
                              'bridge-midplane': {'mode': 'PORT'}},
            DHCP_SERVER_IPV4_PORT={'Vlan200|Ethernet4': {'ips@': '10.0.0.2'},
                                   'Vlan100|Ethernet0': {'ips@': '10.0.0.3'}})
        kept, _, reasons = split(config, VLAN_RULES)
        assert set(kept['DHCP_SERVER_IPV4']) == {'Vlan100', 'bridge-midplane'}
        assert set(kept['DHCP_SERVER_IPV4_PORT']) == {'Vlan100|Ethernet0'}
        assert "DHCP_SERVER_IPV4|Vlan200 dropped: name Vlan200 is in none of MID_PLANE_BRIDGE|GLOBAL bridge, " \
               "VLAN" in reasons

    def test_a_dhcp_relay_on_a_missing_vlan_drops(self):
        config = config_file(DHCPV4_RELAY={'Vlan200': {'dhcpv4_servers': ['10.0.0.1']},
                                           'Vlan100': {'dhcpv4_servers': ['10.0.0.1']}})
        kept, _, _ = split(config, VLAN_RULES)
        assert set(kept['DHCPV4_RELAY']) == {'Vlan100'}

    def test_a_route_map_neighbor_on_a_missing_vlan_is_deleted(self):
        config = config_file(ROUTE_MAP={'rm|10': {'route_operation': 'permit', 'match_neighbor': ['Vlan200']},
                                        'rm|20': {'route_operation': 'permit', 'match_neighbor': ['10.0.0.1']}})
        kept, _, _ = split(config, VLAN_RULES)
        assert kept['ROUTE_MAP'] == {'rm|10': {'route_operation': 'permit'},
                                     'rm|20': {'route_operation': 'permit', 'match_neighbor': ['10.0.0.1']}}

    def test_the_dpu_vlan_of_a_missing_vlan_is_deleted(self):
        config = config_file(DASH_HA_GLOBAL_CONFIG={'global': {'dpu_vlan': 'Vlan200', 'cp_data_channel_port': '1'}})
        kept, _, _ = split(config, VLAN_RULES)
        assert kept['DASH_HA_GLOBAL_CONFIG'] == {'global': {'cp_data_channel_port': '1'}}

    def test_current_bgp_neighbor_keeps_a_vlan_its_pattern_accepts(self):
        # The current neighbor: an address, leafrefs to PORT and PORTCHANNEL, and a Vlan pattern.
        rules = {BGP_NEIGHBOR: rule(LAG_TARGETS, [[IPV4_PATTERN], [IPV6_PATTERN], [VLAN_PATTERN]], 1)}
        config = config_file(BGP_NEIGHBOR={'default|Vlan200': {}, 'default|10.0.0.1': {}})
        assert split(config, rules) == (config, {}, [])

    @pytest.mark.parametrize("neighbor,expected", [
        ("10.0.0.1", False), ("fe80::1%Vlan100", False), ("Vlan100", False), ("Ethernet0.10", False),
        ("Vlan200", True), ("Ethernet0.20", True)])
    def test_may_dangle_bgp_neighbor(self, neighbor, expected):
        assert may_dangle(config_file(BGP_NEIGHBOR={('default', neighbor): {}})) is expected

    def test_may_dangle_bgp_neighbor_af(self):
        config = config_file(BGP_NEIGHBOR={('default', '10.0.0.1'): {}})
        assert not may_dangle(dict(config, BGP_NEIGHBOR_AF={('default', '10.0.0.1', 'ipv4_unicast'): {}}))
        assert may_dangle(dict(config, BGP_NEIGHBOR_AF={('default', '10.0.0.2', 'ipv4_unicast'): {}}))
        assert may_dangle(dict(config, BGP_NEIGHBOR_AF={('Vrf1', '10.0.0.1', 'ipv4_unicast'): {}}))

    def test_may_dangle_dhcp_server_on_the_midplane_bridge(self):
        config = config_file(MID_PLANE_BRIDGE={'GLOBAL': {'bridge': 'bridge-midplane'}})
        assert not may_dangle(dict(config, DHCP_SERVER_IPV4={'bridge-midplane': {}, 'Vlan100': {}}))
        assert may_dangle(dict(config, DHCP_SERVER_IPV4={'Vlan200': {}}))

    @pytest.mark.parametrize("value,expected", [
        ("10.0.0.1", True), ("fe80::1", True), ("fe80::1%Vlan100", True), ("::", True),
        ("999.1.1.1", False), ("a:", False), (":", False), ("010.0.0.1", False), ("fe80::1%Ethernet0.10", False),
        ("fe80::1%", False), ("Vlan100", False)])
    def test_is_ip_address(self, value, expected):
        assert _is_ip_address(value) is expected


# A neighbor union holding inet:ip-address, itself a union, ahead of its leafrefs;
# an address family list keyed off it; and a DHCP server name that may name the
# bridge of a singleton container.
VLAN_MODELS_YANG = '''
module test-dangling-vlan-references {
  namespace "http://example.com/test-dangling-vlan-references";
  prefix tdvr;

  typedef ip-address {
    type union {
      type string { pattern "''' + IPV4_PATTERN.replace('\\', '\\\\') + '''"; }
      type string { pattern "[0-9a-fA-F:.]*:[0-9a-fA-F:.]*(%[\\\\p{N}\\\\p{L}]+)?"; }
    }
  }

  container sonic-test {
    container PORT { list PORT_LIST { key "name"; leaf name { type string; } } }
    container PORTCHANNEL { list PORTCHANNEL_LIST { key "name"; leaf name { type string; } } }
    container VLAN { list VLAN_LIST { key "name"; leaf name { type string; } } }
    container VLAN_SUB_INTERFACE { list VLAN_SUB_INTERFACE_LIST { key "name"; leaf name { type string; } } }
    container MID_PLANE_BRIDGE { container GLOBAL { leaf bridge { type string; } } }
    container BGP_NEIGHBOR {
      list BGP_NEIGHBOR_LIST {
        key "vrf_name neighbor";
        leaf vrf_name { type string; }
        leaf neighbor {
          type union {
            type ip-address;
            type leafref { path "/tdvr:sonic-test/tdvr:PORT/tdvr:PORT_LIST/tdvr:name"; }
            type leafref { path "/tdvr:sonic-test/tdvr:PORTCHANNEL/tdvr:PORTCHANNEL_LIST/tdvr:name"; }
            type leafref { path "/tdvr:sonic-test/tdvr:VLAN/tdvr:VLAN_LIST/tdvr:name"; }
            type leafref { path "/tdvr:sonic-test/tdvr:VLAN_SUB_INTERFACE/tdvr:VLAN_SUB_INTERFACE_LIST/tdvr:name"; }
          }
        }
      }
    }
    container BGP_NEIGHBOR_AF {
      list BGP_NEIGHBOR_AF_LIST {
        key "vrf_name neighbor afi_safi";
        leaf vrf_name { type string; }
        leaf neighbor {
          type leafref { path "../../../BGP_NEIGHBOR/BGP_NEIGHBOR_LIST[vrf_name=current()/../vrf_name]/neighbor"; }
        }
        leaf afi_safi { type string; }
      }
    }
    container VLAN_INTERFACE {
      list VLAN_INTERFACE_LIST {
        key "name";
        leaf name { type leafref { path "/tdvr:sonic-test/tdvr:VLAN/tdvr:VLAN_LIST/tdvr:name"; } }
      }
      list VLAN_INTERFACE_IPPREFIX_LIST {
        key "name ip-prefix";
        leaf name { type leafref { path "../../VLAN_INTERFACE_LIST/name"; } }
        leaf ip-prefix { type string; }
      }
    }
    container DHCP_SERVER_IPV4 {
      list DHCP_SERVER_IPV4_LIST {
        key "name";
        leaf name {
          type union {
            type leafref { path "/tdvr:sonic-test/tdvr:MID_PLANE_BRIDGE/tdvr:GLOBAL/tdvr:bridge"; }
            type leafref { path "/tdvr:sonic-test/tdvr:VLAN/tdvr:VLAN_LIST/tdvr:name"; }
          }
        }
      }
    }
  }
}
'''


def test_vlan_reference_rules_with_libyang():
    libyang = pytest.importorskip('libyang')
    ctx = libyang.Context()
    try:
        module = ctx.parse_module_str(VLAN_MODELS_YANG)
        sy = mock.Mock()
        sy.confDbYangMap = {table.name(): {'container': table}
                            for top in module.children() for table in top.children()}
        rules = interface_reference_rules(sy)
        assert {s: (r.targets, r.required) for s, r in rules.items()} == {
            BGP_NEIGHBOR: (NEIGHBOR_TARGETS, 1),
            BGP_NEIGHBOR_AF: ((SAME_VRF_NEIGHBOR,), 1),
            DHCP_SERVER: ((MIDPLANE, 'VLAN'), 1),
            VLAN_INTERFACE: (('VLAN',), 1),
        }
        assert rules[VLAN_INTERFACE].patterns == (), "the prefix rows' leafref to their own table accepts nothing"
        config = config_file(
            BGP_NEIGHBOR={'default|10.0.0.1': {}, 'default|fe80::1%Vlan100': {}, 'default|Vlan200': {}},
            BGP_NEIGHBOR_AF={'default|Vlan200|ipv4_unicast': {}, 'default|10.0.0.1|ipv4_unicast': {},
                             'Vrf1|10.0.0.1|ipv4_unicast': {}},
            VLAN_INTERFACE={'Vlan200': {}, 'Vlan200|10.0.0.1/24': {}, 'Vlan100|10.0.1.1/24': {}},
            MID_PLANE_BRIDGE={'GLOBAL': {'bridge': 'bridge-midplane'}},
            DHCP_SERVER_IPV4={'bridge-midplane': {}, 'Vlan200': {}})
        kept, _, _ = split(config, rules)
        assert set(kept['BGP_NEIGHBOR']) == {'default|10.0.0.1', 'default|fe80::1%Vlan100'}
        assert set(kept['BGP_NEIGHBOR_AF']) == {'default|10.0.0.1|ipv4_unicast'}
        assert set(kept['DHCP_SERVER_IPV4']) == {'bridge-midplane'}
        assert set(kept['VLAN_INTERFACE']) == {'Vlan100|10.0.1.1/24'}
    finally:
        ctx.destroy()

import ipaddress
import re
from collections import namedtuple


def key_parts(key):
    """Split a ConfigDB key given either as a tuple or as a '|'-joined string."""
    return list(key) if isinstance(key, tuple) else key.split('|')


# Where a reference lives in its row, which also decides what a dangling value
# costs: a key part drops the row, a scalar field is deleted (or drops the row
# when the model makes it mandatory), and a leaf-list loses the element (and
# drops the row when fewer than the model's min-elements are left). A field
# whose leaf no model makes a leafref has no spec.
KEY = 'key'
FIELD = 'field'
LEAF_LIST = 'leaf-list'

# One interface reference: the table and leaf, and where the leaf lives
# (position is the key part for KEY). known_targets and known_forms only let
# may_dangle skip loading the models: a value in a known_targets target, or of
# a form known_forms (a regex, or a predicate) accepts, is one every model for
# the spec accepts. Leaving them empty costs a load, never a drop, since the loaded
# models decide.
ReferenceSpec = namedtuple('ReferenceSpec', ['table', 'leaf', 'where', 'position', 'known_targets', 'known_forms'])

# A target whose leafref predicate ties one of its key leaves to one of the
# referencing row's, as BGP_NEIGHBOR_AF names a BGP_NEIGHBOR of its own VRF:
# a value names a row of table whose key has length parts, holding the value at
# name and the referencing key's part own_scope at scope. scope_leaf names the
# tied leaf in log lines.
ScopedTarget = namedtuple('ScopedTarget', ['table', 'length', 'scope', 'name', 'own_scope', 'scope_leaf'])


def _is_ip_address(value):
    """Whether value is an IPv4 or IPv6 address, with an optional zone, as inet:ip-address accepts it."""
    address, separator, zone = value.partition('%')
    if separator and not re.fullmatch(r'[^\W_]+', zone):
        return False
    try:
        ipaddress.ip_address(address)
    except ValueError:
        return False
    return True


_SOURCE_INTERFACES = ('PORT', 'PORTCHANNEL', 'VLAN', 'LOOPBACK_INTERFACE', 'MGMT_PORT')
_NEIGHBORS = ('PORT', 'PORTCHANNEL', 'VLAN', 'VLAN_SUB_INTERFACE')
_LAYER3_SOURCES = ('PORT', 'PORTCHANNEL', 'LOOPBACK_INTERFACE', 'VLAN')

INTERFACE_REFERENCES = (
    # TACPLUS|global and SFLOW|global
    ReferenceSpec('TACPLUS', 'src_intf', FIELD, None, _SOURCE_INTERFACES, None),
    ReferenceSpec('SFLOW', 'agent_id', FIELD, None, _SOURCE_INTERFACES, None),
    # NTP|global, whose models leave VLAN out
    ReferenceSpec('NTP', 'src_intf', LEAF_LIST, None, ('PORT', 'PORTCHANNEL', 'LOOPBACK_INTERFACE', 'MGMT_PORT'),
                  r'eth0'),
    # RADIUS_SERVER|<ipaddress>
    ReferenceSpec('RADIUS_SERVER', 'src_intf', FIELD, None, _SOURCE_INTERFACES, None),
    # BGP_NEIGHBOR|[<vrf_name>|]<neighbor>, BGP_INTERNAL_NEIGHBOR|<neighbor>, BGP_VOQ_CHASSIS_NEIGHBOR|<neighbor>
    ReferenceSpec('BGP_NEIGHBOR', 'neighbor', KEY, -1, _NEIGHBORS, _is_ip_address),
    ReferenceSpec('BGP_INTERNAL_NEIGHBOR', 'neighbor', KEY, -1, _NEIGHBORS, _is_ip_address),
    ReferenceSpec('BGP_VOQ_CHASSIS_NEIGHBOR', 'neighbor', KEY, -1, _NEIGHBORS, _is_ip_address),
    # BGP_NEIGHBOR_AF|<vrf_name>|<neighbor>|<afi_safi>, after the BGP_NEIGHBOR|<vrf_name>|<neighbor> rows it names
    ReferenceSpec('BGP_NEIGHBOR_AF', 'neighbor', KEY, 1,
                  (ScopedTarget('BGP_NEIGHBOR', 2, 0, 1, 0, 'vrf_name'),), None),
    ReferenceSpec('BGP_NEIGHBOR', 'local_addr', FIELD, None, _LAYER3_SOURCES, _is_ip_address),
    ReferenceSpec('BGP_PEER_GROUP', 'local_addr', FIELD, None, _LAYER3_SOURCES, _is_ip_address),
    # DHCPV4_RELAY|<name>
    ReferenceSpec('DHCPV4_RELAY', 'name', KEY, 0, ('PORT', 'VLAN'), None),
    ReferenceSpec('DHCPV4_RELAY', 'source_interface', FIELD, None, _LAYER3_SOURCES, None),
    # DHCP_SERVER_IPV4|<name>, then DHCP_SERVER_IPV4_PORT|<name>|<port> under it
    ReferenceSpec('DHCP_SERVER_IPV4', 'name', KEY, 0, ('VLAN', ('MID_PLANE_BRIDGE', 'GLOBAL', 'bridge')), None),
    ReferenceSpec('DHCP_SERVER_IPV4_PORT', 'name', KEY, 0, ('DHCP_SERVER_IPV4',), None),
    # ROUTE_MAP|<name>|<stmt_name>
    ReferenceSpec('ROUTE_MAP', 'match_interface', FIELD, None, ('PORT', 'PORTCHANNEL', 'VLAN'), None),
    ReferenceSpec('ROUTE_MAP', 'match_neighbor', LEAF_LIST, None, ('PORT', 'PORTCHANNEL', 'VLAN'), _is_ip_address),
    # SRV6_MY_SIDS|<locator>|<ip_prefix>
    ReferenceSpec('SRV6_MY_SIDS', 'interface', FIELD, None, ('PORT', 'PORTCHANNEL', 'VLAN'), None),
    # NEIGH|<port>|<neighbor>
    ReferenceSpec('NEIGH', 'port', KEY, 0, ('PORT', 'PORTCHANNEL', 'VLAN'), None),
    # MCLAG_UNIQUE_IP|<if_name>
    ReferenceSpec('MCLAG_UNIQUE_IP', 'if_name', KEY, 0, ('VLAN',), None),
    # STP_VLAN|<name>, STP_VLAN_PORT|<vlan-name>|<ifname>
    ReferenceSpec('STP_VLAN', 'name', KEY, 0, ('VLAN',), None),
    ReferenceSpec('STP_VLAN_PORT', 'vlan-name', KEY, 0, ('VLAN',), None),
    # VLAN_MEMBER|<name>|<port>, VLAN_INTERFACE|<name>[|<ip-prefix>]
    ReferenceSpec('VLAN_MEMBER', 'name', KEY, 0, ('VLAN',), None),
    ReferenceSpec('VLAN_INTERFACE', 'name', KEY, 0, ('VLAN',), None),
    # DASH_HA_GLOBAL_CONFIG|global
    ReferenceSpec('DASH_HA_GLOBAL_CONFIG', 'dpu_vlan', FIELD, None, ('VLAN',), None),
)

REFERENCE_TABLES = tuple(dict.fromkeys(spec.table for spec in INTERFACE_REFERENCES))


def _target_table(target):
    """The CONFIG_DB table a target is in."""
    if isinstance(target, ScopedTarget):
        return target.table
    return target if isinstance(target, str) else target[0]


KNOWN_TARGETS = tuple(dict.fromkeys(_target_table(target) for spec in INTERFACE_REFERENCES
                                    for target in spec.known_targets))

# What the loaded models accept for one ReferenceSpec. patterns holds one tuple
# per non-leafref member of the leaf's union, of (regex, inverted) pairs a value
# must all satisfy, so an empty tuple accepts any value. A regex Python cannot
# compile is None and satisfied by every value. targets are the CONFIG_DB
# tables the union's leafrefs name. required is 1 for a mandatory leaf and a
# leaf-list's min-elements, else 0.
InterfaceRule = namedtuple('InterfaceRule', ['patterns', 'targets', 'required'])

# The values of one row's reference that name nothing.
Dangling = namedtuple('Dangling', ['spec', 'key', 'values'])

# What one row becomes: entry is None when the row is dropped. removed is the
# whole row when it is dropped, else the original value of each field changed in it.
Repair = namedtuple('Repair', ['table', 'key', 'entry', 'removed', 'reasons'])


def _union_members(leaf_type):
    """
    The compiled member types of a union. libyang compiles a nested union
    (inet:ip-address) flat, and Type.union_types pairs those members with the
    parsed ones, so it loses as many trailing members as the nesting added.
    SonicYang.union_member_types reads the compiled members themselves.
    """
    import sonic_yang
    return list(sonic_yang.SonicYang.union_member_types(leaf_type))


def _members(leaf_type):
    """The member types of a union, nested unions flattened; the type itself otherwise."""
    if leaf_type.basename() != 'union':
        yield leaf_type
        return
    for member in _union_members(leaf_type):
        yield from _members(member)


# Python's re has no Unicode property classes. \w is a superset of the letter
# and number ones, so the translated pattern accepts at least what the YANG
# pattern does; ietf-inet-types needs it for an address's zone.
_PROPERTY_CLASS = re.compile(r'\\p\{[LN][a-z]?\}')


def _compile(expression):
    try:
        return re.compile(_PROPERTY_CLASS.sub(lambda _: r'\w', expression))
    except re.error:
        return None


# A leafref to a sibling list of the same table (VLAN_INTERFACE's prefix rows
# naming its VLAN_INTERFACE_LIST row), whose row is itself checked.
SAME_TABLE = 'same table'

_PREDICATE = re.compile(r'\[\s*(?:[\w-]+:)?([\w-]+)\s*=\s*current\(\)\s*/\s*\.\.\s*/\s*(?:[\w-]+:)?([\w-]+)\s*\]')


def _leafref_table(path):
    """
    What a leafref path names in CONFIG_DB: the table holding its list, e.g.
    VLAN for .../VLAN/VLAN_LIST/name, (table, row, field) for a leaf of a
    singleton container, e.g. ('MID_PLANE_BRIDGE', 'GLOBAL', 'bridge'), or
    SAME_TABLE.
    """
    segments = [segment.rpartition(':')[2] for segment in re.sub(r'\[[^\]]*\]', '', path).split('/') if segment]
    if len(segments) >= 3 and segments[-3] == '..' and segments[-2].endswith('_LIST'):
        return SAME_TABLE
    if len(segments) < 3 or segments[-3] in ('', '..'):
        return None
    if segments[-2].endswith('_LIST'):
        return segments[-3]
    return tuple(segments[-3:])


def _key_names(node):
    try:
        return [key.name() for key in node.keys()]
    except Exception:
        return None


def _scoped(sy, table, path, entry):
    """
    The ScopedTarget a leafref path with a [leaf=current()/../leaf] predicate
    names, when both leaves are keys; table otherwise, which matches the value
    in any row and so never drops more.
    """
    match = _PREDICATE.search(path)
    model = sy.confDbYangMap.get(table)
    if match is None or model is None:
        return table
    segments = [segment.rpartition(':')[2] for segment in re.sub(r'\[[^\]]*\]', '', path).split('/') if segment]
    lists = [child for child in model['container'].children() if child.name() == segments[-2]]
    target_keys = _key_names(lists[0]) if lists else None
    own_keys = _key_names(entry)
    scope, own_scope = match.groups()
    if not target_keys or not own_keys or scope not in target_keys or segments[-1] not in target_keys \
            or own_scope not in own_keys:
        return table
    return ScopedTarget(table, len(target_keys), target_keys.index(scope), target_keys.index(segments[-1]),
                        own_keys.index(own_scope), scope)


def target_name(target):
    """A target of an InterfaceRule as a log line names it."""
    if isinstance(target, ScopedTarget):
        return '{} of the same {}'.format(target.table, target.scope_leaf)
    return target if isinstance(target, str) else '{}|{} {}'.format(*target)


def target_tables(rules):
    """The CONFIG_DB tables the targets of rules are in, sorted."""
    return sorted({_target_table(target) for rule in rules.values() for target in rule.targets})


def _required(spec, leaf):
    if spec.where == LEAF_LIST:
        return leaf.min_elements() or 0
    return 1 if spec.where == KEY or leaf.mandatory() else 0


def interface_reference_rules(sy):
    """
    The InterfaceRule of each INTERFACE_REFERENCES spec whose loaded models (a
    SonicYang) give its leaf at least one leafref. A spec whose leaf is
    patterns only, or whose table or leaf the models lack, has no rule, so
    nothing is dropped for it.
    """
    rules = {}
    for spec in INTERFACE_REFERENCES:
        model = sy.confDbYangMap.get(spec.table)
        if model is None:
            continue
        keyword = 'leaf-list' if spec.where == LEAF_LIST else 'leaf'
        patterns = []
        targets = []
        required = 0
        for entry in model['container'].children():
            for leaf in entry.children():
                if leaf.keyword() != keyword or leaf.name() != spec.leaf:
                    continue
                required = max(required, _required(spec, leaf))
                for member in _members(leaf.type()):
                    path = (member.leafref_path() or '') if member.basename() == 'leafref' else ''
                    target = _leafref_table(path) if path else None
                    if target == SAME_TABLE:
                        continue
                    if isinstance(target, str):
                        target = _scoped(sy, target, path, entry)
                    if target is not None:
                        if target not in targets:
                            targets.append(target)
                    elif member.basename() == 'string':
                        patterns.append(tuple((_compile(pattern.expression()), bool(pattern.inverted()))
                                              for pattern in member.pattern_details()))
                    else:
                        # A leafref to no table, or any other type: accept every value.
                        patterns.append(())
        if targets:
            rules[spec] = InterfaceRule(tuple(patterns), tuple(targets), required)
    return rules


def _matches_a_pattern(rule, value):
    return any(all(regex is None or bool(regex.fullmatch(value)) != inverted for regex, inverted in group)
               for group in rule.patterns)


def _values(spec, key, entry):
    """The interface names a row holds for spec."""
    if spec.where == KEY:
        parts = key_parts(key)
        return [parts[spec.position]] if -len(parts) <= spec.position < len(parts) else []
    value = entry.get(spec.leaf) if isinstance(entry, dict) else None
    if spec.where == LEAF_LIST and isinstance(value, str):
        value = value.split(',')
    if isinstance(value, list):
        return [element for element in value if isinstance(element, str) and element]
    return [value] if isinstance(value, str) and value else []


def _names(config, targets):
    """
    The names the targets hold: every part of each key of a table, the value
    of a singleton row's field, and the (scope, name) pair of each key of a
    ScopedTarget. A reference names one key leaf of its target, and the other
    parts (an IP prefix, a VRF, an address family) never take the form of the
    names it holds.
    """
    names = set()
    for target in targets:
        if isinstance(target, ScopedTarget):
            names.update((parts[target.scope], parts[target.name])
                         for parts in map(key_parts, config.get(target.table) or {}) if len(parts) == target.length)
            continue
        if isinstance(target, str):
            names.update(part for key in (config.get(target) or {}) for part in key_parts(key))
            continue
        table, row, field = target
        value = ((config.get(table) or {}).get(row) or {}).get(field)
        if isinstance(value, str) and value:
            names.add(value)
    return names


def _named(names, targets, key, value):
    """Whether names (from _names of targets) holds value as the row with key references it."""
    if value in names:
        return True
    parts = key_parts(key)
    return any(isinstance(target, ScopedTarget) and target.own_scope < len(parts)
               and (parts[target.own_scope], value) in names for target in targets)


def may_dangle(config):
    """
    Whether a row of a REFERENCE_TABLES table holds a value that is in none of
    its spec's known_targets and has none of its known_forms, so that
    find_dangling_interface_references could find it. config needs the
    REFERENCE_TABLES and KNOWN_TARGETS tables.
    """
    for spec in INTERFACE_REFERENCES:
        names = _names(config, spec.known_targets)
        forms = spec.known_forms
        if isinstance(forms, str):
            forms = re.compile(forms).fullmatch
        for key, entry in (config.get(spec.table) or {}).items():
            if any(not _named(names, spec.known_targets, key, value) and not (forms and forms(value))
                   for value in _values(spec, key, entry)):
                return True
    return False


def ports_missing(config, rule):
    """
    Whether rule's targets include PORT while config has no PORT rows. A
    switch always has ports, so that is a broken read, and a value naming an
    EthernetN would look dangling while other target tables still have rows.
    """
    return 'PORT' in rule.targets and not config.get('PORT')


def _dangling(spec, rule, config, original):
    """
    The Dangling rows of one spec in config, left alone when its targets are
    all empty in original, or it targets PORT and PORT is empty there
    (ports_missing).
    """
    entries = config.get(spec.table)
    if not isinstance(entries, dict) or not entries or not _names(original, rule.targets) \
            or ports_missing(original, rule):
        return []
    names = _names(config, rule.targets)
    dangling = []
    for key in sorted(entries, key=key_parts):
        values = tuple(value for value in _values(spec, key, entries[key])
                       if not _named(names, rule.targets, key, value) and not _matches_a_pattern(rule, value))
        if values:
            dangling.append(Dangling(spec, key, values))
    return dangling


def find_dangling_interface_references(config, rules):
    """
    The values of each spec in rules (from interface_reference_rules) that
    match none of the rule's patterns and name no row of any of its targets
    (see _names), as Dangling rows in INTERFACE_REFERENCES order.

    config holds CONFIG_DB tables with tuple keys, or one scope of a config
    file with '|'-joined keys. A spec whose targets are all empty, or that
    targets PORT while PORT is empty (ports_missing), is left alone: a switch
    always has ports, so that is a broken read, not a reason to drop every
    reference.
    """
    return [dangling for spec in INTERFACE_REFERENCES if spec in rules
            for dangling in _dangling(spec, rules[spec], config, config)]


def plan_dangling_interface_repairs(config, rules, unwritable=()):
    """
    The Repair of each row with a dangling value, in INTERFACE_REFERENCES
    order, with one reason per change naming the row, the leaf, the values
    and the tables they were looked up in. A row a spec drops gets no reason
    from a later spec.

    Each spec is checked against the config as the specs before it left it,
    so a row referencing a row they drop (BGP_NEIGHBOR_AF under a dropped
    BGP_NEIGHBOR) is repaired too, beyond what
    find_dangling_interface_references reports. A row in unwritable, a
    (table, key) pair whose repair could not be written, is planned as it
    stands, so the rows under it stay. A spec's targets count as empty only
    when they are empty in config.
    """
    repairs = {}
    working = dict(config)
    for spec in INTERFACE_REFERENCES:
        rule = rules.get(spec)
        if rule is None:
            continue
        touched = []
        for _, key, values in _dangling(spec, rule, working, config):
            row = (spec.table, key)
            if row in unwritable:
                continue
            touched.append(row)
            if row not in repairs:
                entry = config[spec.table][key]
                repairs[row] = Repair(spec.table, key, dict(entry) if isinstance(entry, dict) else {}, {}, [])
            repairs[row] = _repair(repairs[row], spec, rule, key, values, config[spec.table][key])
        for row in touched:
            table, key = row
            if working[table] is config[table]:
                working[table] = dict(config[table])
            if repairs[row].entry is None:
                working[table].pop(key, None)
            else:
                working[table][key] = dict(repairs[row].entry)
    return [repair if repair.entry is not None else repair._replace(removed=config[repair.table][repair.key])
            for repair in repairs.values()]


def _repair(repair, spec, rule, key, values, original):
    """
    repair with the dangling values of spec in its row taken out. A changed
    field is recorded in removed with its original value, so merging removed
    back restores a leaf-list as it was rather than replacing it with the
    removed elements.
    """
    entry = repair.entry
    if entry is None:
        return repair
    name = '{}|{}'.format(spec.table, '|'.join(key_parts(key)))
    where = "in none of {}".format(', '.join(target_name(target) for target in rule.targets))
    shown = ', '.join(values)
    if spec.where == LEAF_LIST:
        left = [value for value in _values(spec, key, entry) if value not in values]
        if len(left) < rule.required:
            repair.reasons.append("{} dropped: {} {} {} {}, which leaves fewer than its {} required".format(
                name, spec.leaf, shown, 'is' if len(values) == 1 else 'are', where, rule.required))
            return repair._replace(entry=None)
        repair.removed[spec.leaf] = original[spec.leaf]
        if left:
            entry[spec.leaf] = left
            repair.reasons.append("{} {} {} dropped: {}".format(name, spec.leaf, shown, where))
        else:
            entry.pop(spec.leaf, None)
            repair.reasons.append("{} {} dropped: {} {} {}, and it held nothing else".format(
                name, spec.leaf, shown, 'is' if len(values) == 1 else 'are', where))
        return repair
    if spec.where == KEY or rule.required:
        repair.reasons.append("{} dropped: {} {} is {}".format(name, spec.leaf, shown, where))
        return repair._replace(entry=None)
    repair.removed[spec.leaf] = entry.pop(spec.leaf)
    repair.reasons.append("{} {} {} dropped: it is {}".format(name, spec.leaf, shown, where))
    return repair


def references_to(get_table, table, name, skip=()):
    """
    The references naming name, a row of table, as 'TABLE|<key> <leaf>'
    lines, from each spec whose known_targets hold table, which is every spec
    whose leaf names a row of table under some model; a spec on a table in
    skip is left out. get_table reads one CONFIG_DB table.
    """
    found = []
    for spec in INTERFACE_REFERENCES:
        if spec.table in skip or table not in spec.known_targets:
            continue
        entries = get_table(spec.table) or {}
        for key in sorted(entries, key=key_parts):
            if name in _values(spec, key, entries[key]):
                found.append('{}|{} {}'.format(spec.table, '|'.join(key_parts(key)), spec.leaf))
    return found

import re
from collections import namedtuple


def key_parts(key):
    """Split a ConfigDB key given either as a tuple or as a '|'-joined string."""
    return list(key) if isinstance(key, tuple) else key.split('|')


# Where a reference lives in its row, which also decides what a dangling value
# costs: a scalar field is deleted (or drops the row when the model makes it
# mandatory), and a leaf-list loses the element (and drops the row when fewer
# than the model's min-elements are left). A field whose leaf no model makes a
# leafref has no spec.
FIELD = 'field'
LEAF_LIST = 'leaf-list'

# One interface reference: the table and leaf, and where the leaf lives.
# known_targets and known_forms only let may_dangle skip loading the models: a
# value in a known_targets table, or with a form the known_forms regex matches,
# is one every model for the spec accepts. Leaving them empty costs a load,
# never a drop, since the loaded models decide.
ReferenceSpec = namedtuple('ReferenceSpec', ['table', 'leaf', 'where', 'known_targets', 'known_forms'])

_SOURCE_INTERFACES = ('PORT', 'PORTCHANNEL', 'VLAN', 'LOOPBACK_INTERFACE', 'MGMT_PORT')

INTERFACE_REFERENCES = (
    # TACPLUS|global and SFLOW|global
    ReferenceSpec('TACPLUS', 'src_intf', FIELD, _SOURCE_INTERFACES, None),
    ReferenceSpec('SFLOW', 'agent_id', FIELD, _SOURCE_INTERFACES, None),
    # NTP|global, whose models leave VLAN out
    ReferenceSpec('NTP', 'src_intf', LEAF_LIST, ('PORT', 'PORTCHANNEL', 'LOOPBACK_INTERFACE', 'MGMT_PORT'), r'eth0'),
    # RADIUS_SERVER|<ipaddress>
    ReferenceSpec('RADIUS_SERVER', 'src_intf', FIELD, _SOURCE_INTERFACES, None),
)

REFERENCE_TABLES = tuple(dict.fromkeys(spec.table for spec in INTERFACE_REFERENCES))
KNOWN_TARGETS = tuple(dict.fromkeys(table for spec in INTERFACE_REFERENCES for table in spec.known_targets))

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


def _members(leaf_type):
    """The member types of a union, nested unions flattened; the type itself otherwise."""
    if leaf_type.basename() != 'union':
        yield leaf_type
        return
    for member in leaf_type.union_types(with_typedefs=True):
        yield from _members(member)


def _compile(expression):
    try:
        return re.compile(expression)
    except re.error:
        return None


def _leafref_table(path):
    """The CONFIG_DB table a leafref path names: the container of its list, e.g. VLAN for .../VLAN/VLAN_LIST/name."""
    segments = [segment.rpartition(':')[2] for segment in path.split('/') if segment]
    if len(segments) >= 3 and segments[-2].endswith('_LIST'):
        return segments[-3]
    return None


def _required(spec, leaf):
    if spec.where == LEAF_LIST:
        return leaf.min_elements() or 0
    return 1 if leaf.mandatory() else 0


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
                    target = _leafref_table(member.leafref_path() or '') if member.basename() == 'leafref' else None
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


def _values(spec, entry):
    """The interface names a row holds for spec."""
    value = entry.get(spec.leaf) if isinstance(entry, dict) else None
    if spec.where == LEAF_LIST and isinstance(value, str):
        value = value.split(',')
    if isinstance(value, list):
        return [element for element in value if isinstance(element, str) and element]
    return [value] if isinstance(value, str) and value else []


def _names(config, tables):
    """The interface names the rows of tables hold: the first part of each key."""
    return {key_parts(key)[0] for table in tables for key in (config.get(table) or {})}


def may_dangle(config):
    """
    Whether a row of a REFERENCE_TABLES table holds a value that is in none of
    its spec's known_targets and has none of its known_forms, so that
    find_dangling_interface_references could find it. config needs the
    REFERENCE_TABLES and KNOWN_TARGETS tables.
    """
    for spec in INTERFACE_REFERENCES:
        names = _names(config, spec.known_targets)
        forms = re.compile(spec.known_forms) if spec.known_forms else None
        for key, entry in (config.get(spec.table) or {}).items():
            if any(value not in names and not (forms and forms.fullmatch(value))
                   for value in _values(spec, entry)):
                return True
    return False


def ports_missing(config, rule):
    """
    Whether rule's targets include PORT while config has no PORT rows. A
    switch always has ports, so that is a broken read, and a value naming an
    EthernetN would look dangling while other target tables still have rows.
    """
    return 'PORT' in rule.targets and not config.get('PORT')


def find_dangling_interface_references(config, rules):
    """
    The values of each spec in rules (from interface_reference_rules) that
    match none of the rule's patterns and name no row of any of its targets,
    as Dangling rows in INTERFACE_REFERENCES order. A target row's name is the
    first part of its key, so LOOPBACK_INTERFACE|Loopback0|<prefix> names
    Loopback0.

    config holds CONFIG_DB tables with tuple keys, or one scope of a config
    file with '|'-joined keys. A spec whose targets are all empty, or that
    targets PORT while PORT is empty (ports_missing), is left alone: a switch
    always has ports, so that is a broken read, not a reason to drop every
    reference.
    """
    dangling = []
    for spec in INTERFACE_REFERENCES:
        rule = rules.get(spec)
        entries = config.get(spec.table)
        if rule is None or not isinstance(entries, dict) or not entries:
            continue
        names = _names(config, rule.targets)
        if not names or ports_missing(config, rule):
            continue
        for key in sorted(entries, key=key_parts):
            values = tuple(value for value in _values(spec, entries[key])
                           if value not in names and not _matches_a_pattern(rule, value))
            if values:
                dangling.append(Dangling(spec, key, values))
    return dangling


def plan_dangling_interface_repairs(config, rules):
    """
    The Repair of each row find_dangling_interface_references finds something
    in, in the order found, with one reason per change naming the row, the
    leaf, the values and the tables they were looked up in. A row a spec drops
    gets no reason from a later spec.
    """
    repairs = {}
    for spec, key, values in find_dangling_interface_references(config, rules):
        row = (spec.table, key)
        if row not in repairs:
            entry = config[spec.table][key]
            repairs[row] = Repair(spec.table, key, dict(entry) if isinstance(entry, dict) else {}, {}, [])
        repairs[row] = _repair(repairs[row], spec, rules[spec], key, values, config[spec.table][key])
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
    where = "in none of {}".format(', '.join(rule.targets))
    shown = ', '.join(values)
    if spec.where == LEAF_LIST:
        left = [value for value in _values(spec, entry) if value not in values]
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
    if rule.required:
        repair.reasons.append("{} dropped: {} {} is {}".format(name, spec.leaf, shown, where))
        return repair._replace(entry=None)
    repair.removed[spec.leaf] = entry.pop(spec.leaf)
    repair.reasons.append("{} {} {} dropped: it is {}".format(name, spec.leaf, shown, where))
    return repair

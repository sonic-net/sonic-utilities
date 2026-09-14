"""Per-parent preflight for Dynamic Port Breakout (DPB) over an interface range.

Each selected platform parent is checked independently so that one bad parent
rejects only itself while the remaining parents continue towards the aggregate
apply.  Preflight is side-effect free: it reads platform data, BREAKOUT_CFG and
the live PORT table, and produces a status per parent.
"""

import json
import os
import re
from collections import namedtuple

import click
from natsort import natsorted
from portconfig import get_child_ports
from sonic_py_common import device_info, multi_asic

from utilities_common.flock import FileLock

INTF_KEY = 'interfaces'

# A selector term is either an exact interface name or an inclusive flat range.
# Exact names are kept verbatim so Hierarchical Port Names (HPN) such as
# Ethernet1_31, used on Tortuga/HyperFabric, resolve unchanged.
ExactTerm = namedtuple('ExactTerm', ['name'])
RangeTerm = namedtuple('RangeTerm', ['start', 'end'])
ParentResolution = namedtuple('ParentResolution', ['parents', 'notParents'])

FLAT_RANGE_RE = re.compile(r'^Ethernet(0|[1-9][0-9]*)-(0|[1-9][0-9]*)$')
FLAT_PARENT_RE = re.compile(r'^Ethernet(0|[1-9][0-9]*)$')

# Bounds longer than this are rejected rather than handed to int(), so a
# pathological selector cannot turn into an unbounded conversion.
MAX_BOUND_DIGITS = 9

# Parent did not resolve to an active platform parent.
SKIPPED_NOT_PARENT = 'SKIPPED_NOT_PARENT'
# Parent already runs the target mode over a valid current layout.
SKIPPED_ALREADY_CONFIGURED = 'SKIPPED_ALREADY_CONFIGURED'
# Attributable per-parent failure; other parents still proceed.
FAILED_PRECHECK = 'FAILED_PRECHECK'
# Passed preflight and needs a mode change.
READY = 'READY'
# Aggregate apply ran without error and this parent's target PORT rows and
# BREAKOUT_CFG marker were verified in CONFIG_DB. It is deliberately not a
# claim about dependency removals or -l default config: the engine computes
# both internally and returns neither, so the plan has nothing to compare them
# against. Widening this status needs the engine to report what it changed.
APPLIED = 'APPLIED'
# Belonged to an aggregate whose apply failed.
FAILED_BULK = 'FAILED_BULK'

BREAKOUT_CFG_TABLE = 'BREAKOUT_CFG'
BRKOUT_MODE_FIELD = 'brkout_mode'


class DpbSelectorError(ValueError):
    """Raised when a selector cannot be parsed, before any preflight runs."""


class DpbPlatformDataError(ValueError):
    """Raised when the active platform.json has no usable interfaces mapping."""


def parseSelector(selector):
    """Parse a comma separated selector of exact names and flat ranges.

    Today's breakout command uses the interface name directly as a
    platform.json key, which cannot express a range. This grows that lookup
    into a real selector while keeping the same CLI shape as
    `config interface startup Ethernet0-64`.

    Unlike parse_interface_in_filter(), which expands a range into candidate
    names and silently drops anything malformed, this rejects bad syntax and
    leaves name selection to resolveParents(). Silently selecting nothing is
    acceptable for an admin-state filter but not before a destructive breakout.
    """
    if selector is None:
        raise DpbSelectorError("Interface selector is required")

    return [_parseTerm(term, selector) for term in selector.split(',')]


def _parseTerm(term, selector):
    if not term:
        raise DpbSelectorError(
            "Empty interface term in selector '{}'. Terms must be separated by "
            "a single comma with no spaces.".format(selector))

    if any(char.isspace() for char in term):
        raise DpbSelectorError(
            "Interface term '{}' contains whitespace. Use a comma separated "
            "selector with no spaces, for example "
            "'Ethernet0,Ethernet8'.".format(term))

    # A hyphen anywhere makes the term range syntax, so a near miss such as
    # 'Ethernet1_1-32' is reported as a bad range instead of being looked up
    # verbatim as a parent name.
    if '-' in term:
        return _parseRangeTerm(term)

    return ExactTerm(term)


def _parseRangeTerm(term):
    match = FLAT_RANGE_RE.match(term)
    if not match:
        raise DpbSelectorError(
            "'{}' is not a valid interface range. Expected "
            "Ethernet<start>-<end> with decimal bounds and no leading zeros, "
            "for example 'Ethernet0-64'. Compact ranges over hierarchical port "
            "names are not supported; list them as comma separated names "
            "instead.".format(term))

    startText, endText = match.group(1), match.group(2)
    for bound in (startText, endText):
        if len(bound) > MAX_BOUND_DIGITS:
            raise DpbSelectorError(
                "Interface range '{}' has a bound with more than {} digits, "
                "which is not a usable port index.".format(
                    term, MAX_BOUND_DIGITS))

    start, end = int(startText), int(endText)
    if start > end:
        raise DpbSelectorError(
            "Interface range '{}' is descending. The start index must not be "
            "greater than the end index.".format(term))

    return RangeTerm(start, end)


def getPlatformParents(platformData):
    """Return the parent-name mapping from parsed platform.json content."""
    if not isinstance(platformData, dict):
        raise DpbPlatformDataError("platform.json content is not a JSON object")

    interfaces = platformData.get(INTF_KEY)
    if not isinstance(interfaces, dict) or not interfaces:
        raise DpbPlatformDataError(
            "platform.json has no usable '{}' mapping".format(INTF_KEY))

    return interfaces


def resolveParents(terms, platformInterfaces):
    """Select the platform parents named by the parsed terms.

    A range filters the finite platform parent set rather than materializing
    its numeric interval, so sparse gaps are omitted, no name is invented, and
    a child is never folded back into its parent.
    """
    parents, notParents = set(), set()

    flatParents = []
    if any(isinstance(term, RangeTerm) for term in terms):
        for name in platformInterfaces:
            match = FLAT_PARENT_RE.match(name)
            if match:
                flatParents.append((name, int(match.group(1))))

    for term in terms:
        if isinstance(term, ExactTerm):
            if term.name in platformInterfaces:
                parents.add(term.name)
            else:
                notParents.add(term.name)
        else:
            for name, index in flatParents:
                if term.start <= index <= term.end:
                    parents.add(name)

    return ParentResolution(parents=natsorted(parents),
                            notParents=natsorted(notParents))


class ParentResult(object):
    """Preflight outcome for one platform parent."""

    def __init__(self, name, status, reason=None, curMode=None, targetMode=None,
                 curChildren=None, targetChildren=None):
        self.name = name
        self.status = status
        self.reason = reason
        self.curMode = curMode
        self.targetMode = targetMode
        self.curChildren = curChildren or {}
        self.targetChildren = targetChildren or {}

    @property
    def isReady(self):
        return self.status == READY

    def __repr__(self):
        return 'ParentResult({!r}, {}, reason={!r})'.format(
            self.name, self.status, self.reason)


def _splitLanes(lanes):
    if not lanes:
        return set()
    return {lane.strip() for lane in str(lanes).split(',') if lane.strip()}


def _portLanes(portConfig):
    return _splitLanes((portConfig or {}).get('lanes'))


def _failed(name, reason, **kwargs):
    return ParentResult(name, FAILED_PRECHECK, reason=reason, **kwargs)


def _validatePlatformEntry(name, platformInterfaces):
    """Return (entry, reason). reason is None when the entry is usable."""
    entry = platformInterfaces.get(name)
    if not isinstance(entry, dict):
        return None, "no usable platform.json entry"

    if not _splitLanes(entry.get('lanes')):
        return None, "platform.json entry has no lanes"

    if not str(entry.get('index', '')).strip():
        return None, "platform.json entry has no index"

    modes = entry.get('breakout_modes')
    if not isinstance(modes, dict) or not modes:
        return None, "platform.json entry has no breakout_modes"

    return entry, None


def _currentMode(name, brkoutCfg, advertisedModes):
    """Return (mode, reason). A missing or unusable marker is an error for this
    parent rather than a reason to drop it silently."""
    if name not in brkoutCfg:
        return None, "not present in {} table of CONFIG DB".format(
            BREAKOUT_CFG_TABLE)

    entry = brkoutCfg.get(name) or {}
    mode = (entry.get(BRKOUT_MODE_FIELD) or '').strip()
    if not mode:
        return None, "{} table has an empty {}".format(
            BREAKOUT_CFG_TABLE, BRKOUT_MODE_FIELD)

    if mode not in advertisedModes:
        return None, (
            "current mode {} is not advertised by this port in "
            "platform.json".format(mode))

    return mode, None


def _generateChildren(name, mode, platformFile):
    try:
        children = get_child_ports(name, mode, platformFile)
    except Exception as e:
        return None, "failed to generate {} ports: {}".format(mode, e)

    if not children:
        return None, "mode {} generates no ports".format(mode)

    return children, None


def _validateCurrentLayout(name, curChildren, parentLanes, portTable):
    """Confirm the generated current children are the live owners of this
    parent's lanes.

    The canonical parent name is deliberately not required to be live: after an
    earlier breakout the live ports are the children, not the parent.
    """
    childLanes = set()
    for childName, childConfig in curChildren.items():
        livePort = portTable.get(childName)
        if livePort is None:
            return ("current child {} is missing from the PORT table; the "
                    "recorded mode does not match the running "
                    "configuration".format(childName))

        expectedLanes = _portLanes(childConfig)
        if _portLanes(livePort) != expectedLanes:
            return ("current child {} owns lanes {} in the PORT table but {} "
                    "in the generated layout".format(
                        childName,
                        ','.join(sorted(_portLanes(livePort))),
                        ','.join(sorted(expectedLanes))))

        childLanes |= expectedLanes

    if childLanes != parentLanes:
        return ("generated current children cover lanes {} but the platform "
                "parent owns {}".format(
                    ','.join(sorted(childLanes)), ','.join(sorted(parentLanes))))

    for portName, portConfig in portTable.items():
        if portName in curChildren:
            continue
        overlap = _portLanes(portConfig) & parentLanes
        if overlap:
            return ("port {} already owns lanes {} belonging to this "
                    "parent".format(portName, ','.join(sorted(overlap))))

    return None


def _validateTargetLayout(name, curChildren, targetChildren, parentLanes,
                          portTable):
    """Reject a target layout that would take over an unrelated live port."""
    targetLanes = set()
    for childName, childConfig in targetChildren.items():
        if childName not in curChildren and childName in portTable:
            return ("target child {} already exists as an unrelated "
                    "port".format(childName))
        targetLanes |= _portLanes(childConfig)

    if not targetLanes <= parentLanes:
        return ("target children claim lanes {} outside this parent".format(
            ','.join(sorted(targetLanes - parentLanes))))

    for portName, portConfig in portTable.items():
        if portName in curChildren or portName in targetChildren:
            continue
        overlap = _portLanes(portConfig) & targetLanes
        if overlap:
            return ("target children would take over lanes {} owned by "
                    "{}".format(','.join(sorted(overlap)), portName))

    return None


def preflightParent(name, platformInterfaces, platformFile, brkoutCfg,
                    portTable, targetMode, oidPorts=None):
    """Run every determinable check for one parent and return a ParentResult.

    Never raises for an attributable problem; the caller keeps the reason for
    the final summary and continues with the remaining parents.

    oidPorts is the set of port names that currently hold an ASIC DB OID. It
    is optional because the engine refuses the aggregate outright when an OID
    is missing, so omitting it cannot let an unverifiable delete through; what
    it buys is attributing the problem to one parent, which is what lets -s
    skip that parent and keep going.
    """
    entry, reason = _validatePlatformEntry(name, platformInterfaces)
    if reason:
        return _failed(name, reason, targetMode=targetMode)

    advertisedModes = entry['breakout_modes']
    parentLanes = _splitLanes(entry['lanes'])

    curMode, reason = _currentMode(name, brkoutCfg, advertisedModes)
    if reason:
        return _failed(name, reason, targetMode=targetMode)

    if targetMode not in advertisedModes:
        return _failed(
            name,
            'Target mode {} is not available for the port {}'.format(
                targetMode, name),
            curMode=curMode, targetMode=targetMode)

    curChildren, reason = _generateChildren(name, curMode, platformFile)
    if reason:
        return _failed(name, reason, curMode=curMode, targetMode=targetMode)

    reason = _validateCurrentLayout(name, curChildren, parentLanes, portTable)
    if reason:
        return _failed(name, reason, curMode=curMode, targetMode=targetMode,
                       curChildren=curChildren)

    # The current layout is valid, so an unchanged mode is a clean skip. No
    # target, dependency or OID planning is done for this parent.
    if curMode == targetMode:
        return ParentResult(name, SKIPPED_ALREADY_CONFIGURED,
                            reason='already in mode {}'.format(targetMode),
                            curMode=curMode, targetMode=targetMode,
                            curChildren=curChildren)

    targetChildren, reason = _generateChildren(name, targetMode, platformFile)
    if reason:
        return _failed(name, reason, curMode=curMode, targetMode=targetMode,
                       curChildren=curChildren)

    reason = _validateTargetLayout(name, curChildren, targetChildren,
                                   parentLanes, portTable)
    if reason:
        return _failed(name, reason, curMode=curMode, targetMode=targetMode,
                       curChildren=curChildren,
                       targetChildren=targetChildren)

    if oidPorts is not None:
        noOid = [child for child in natsorted(curChildren)
                 if child not in oidPorts]
        if noOid:
            return _failed(
                name,
                'no ASIC DB OID for current child {}, so its removal could '
                'not be verified'.format(', '.join(noOid)),
                curMode=curMode, targetMode=targetMode,
                curChildren=curChildren, targetChildren=targetChildren)

    return ParentResult(name, READY, curMode=curMode, targetMode=targetMode,
                        curChildren=curChildren,
                        targetChildren=targetChildren)


def preflightParents(parents, notParents, platformInterfaces, platformFile,
                     brkoutCfg, portTable, targetMode, oidPorts=None):
    """Preflight every resolved parent and record the non-parent skips.

    Results follow the resolver's natural order, with the non-parent skips
    reported alongside so the summary covers everything the operator named.
    """
    results = [
        ParentResult(name, SKIPPED_NOT_PARENT,
                     reason='not an active platform parent',
                     targetMode=targetMode)
        for name in notParents
    ]

    results.extend(
        preflightParent(name, platformInterfaces, platformFile, brkoutCfg,
                        portTable, targetMode, oidPorts=oidPorts)
        for name in parents
    )

    return results


def readyParents(results):
    return [result for result in results if result.isReady]


class BulkBreakoutPlan(object):
    """One aggregate delete/add covering every READY parent.

    The engine has no parent concept, so the plan flattens the READY parents
    into a single deduplicated delete list and a single PORT mapping, while
    keeping the per-parent maps for reporting.
    """

    def __init__(self, results, targetMode):
        self.results = results
        self.targetMode = targetMode
        self.ready = readyParents(results)

        self.delPorts = []
        self.portJson = {'PORT': {}}
        self.markerPatch = {}

        seen = set()
        for result in self.ready:
            for child in natsorted(result.curChildren):
                if child not in seen:
                    seen.add(child)
                    self.delPorts.append(child)
            for child, config in result.targetChildren.items():
                self.portJson['PORT'][child] = config
            self.markerPatch[result.name] = {BRKOUT_MODE_FIELD: targetMode}

    @property
    def isEmpty(self):
        return not self.ready

    @property
    def parents(self):
        return [result.name for result in self.ready]

    def markReady(self, status, reason):
        """Carry an aggregate outcome back to every parent that took part."""
        for result in self.ready:
            result.status = status
            result.reason = reason


def validateCrossParent(readyResults):
    """Reject collisions that only become visible once parents are combined.

    Returns a reason string, or None when the combined layout is coherent.
    """
    targetOwners = {}
    laneOwners = {}

    for result in readyResults:
        for child, config in result.targetChildren.items():
            owner = targetOwners.get(child)
            if owner is not None:
                return ("{} and {} would both create port {}".format(
                    owner, result.name, child))
            targetOwners[child] = result.name

            for lane in _portLanes(config):
                owner = laneOwners.get(lane)
                if owner is not None:
                    return ("{} and {} would both claim lane {}".format(
                        owner, result.name, lane))
                laneOwners[lane] = result.name

    currentOwners = {}
    for result in readyResults:
        for child in result.curChildren:
            currentOwners[child] = result.name

    for child, owner in targetOwners.items():
        currentOwner = currentOwners.get(child)
        if currentOwner is not None and currentOwner != owner:
            return ("target port {} of {} would take over the current layout "
                    "of {}".format(child, owner, currentOwner))

    return None


def buildBulkPlan(results, targetMode):
    """Build the aggregate plan and validate it across parents.

    Returns (plan, reason). A non-None reason is an aggregate-only failure
    that cannot be attributed to a single parent, so no write may follow.
    """
    plan = BulkBreakoutPlan(results, targetMode)
    if plan.isEmpty:
        return plan, None

    return plan, validateCrossParent(plan.ready)


def _mentions(text, portName):
    """Match a port name as a whole token, so Ethernet1 does not match
    Ethernet10."""
    return re.search(r'(?<![0-9A-Za-z_]){}(?![0-9A-Za-z_])'.format(
        re.escape(portName)), text) is not None


def attributeDependencies(deps, readyResults):
    """Blame aggregate dependency entries on the parents that own them.

    The engine reports dependencies for the combined delete set with no parent
    concept, so a dependency is attributed to a parent when it names one of
    that parent's current children.

    Returns a dict of parent name to the sorted dependency entries naming it.
    Anything that names no parent's child stays unattributed and must be
    treated as an aggregate failure.
    """
    blamed = {}
    texts = [dep if isinstance(dep, str) else json.dumps(dep, sort_keys=True)
             for dep in deps]

    for result in readyResults:
        for text in texts:
            if any(_mentions(text, child) for child in result.curChildren):
                blamed.setdefault(result.name, set()).add(text)

    return {name: sorted(entries) for name, entries in blamed.items()}


def summaryLines(results):
    """Render one line per parent for the final status table."""
    if not results:
        return []

    width = max(len(result.name) for result in results)
    lines = []
    for result in results:
        line = '  {:<{}}  {}'.format(result.name, width, result.status)
        if result.reason:
            line += '  ({})'.format(result.reason)
        lines.append(line)

    return lines


def planLines(plan):
    """Render the aggregate operation in the historical breakout format.

    One combined pair of port maps rather than a per-parent breakdown, because
    the engine is handed one aggregate delete and one aggregate add. The
    running mode is not shown: a selection may span several of them, so there
    is no single value to print.
    """
    delPorts, addPorts = {}, {}
    for result in plan.ready:
        for port in natsorted(result.curChildren):
            delPorts[port] = result.curChildren[port].get('speed')
        for port in natsorted(result.targetChildren):
            addPorts[port] = result.targetChildren[port].get('speed')

    return ["Target Breakout Mode : {}\n".format(plan.targetMode),
            "Ports to be deleted : \n {}".format(
                json.dumps(delPorts, indent=4)),
            "Ports to be added : \n {}".format(
                json.dumps(addPorts, indent=4))]


def noticeLines(results):
    """Render only the parents that will not be broken out.

    The READY parents are already described by the plan, so repeating them
    here just pads what the operator has to read before deciding.
    """
    return summaryLines([result for result in results if not result.isReady])


class DpbUsageError(Exception):
    """A selector problem the CLI should report as a usage error."""


def completionModes(platformData, selector):
    """Breakout modes to offer for an interface selector.

    For a selector naming several parents only modes advertised by every one
    of them are offered, so each suggestion applies to the whole selection.
    Completion never validates the command and never has side effects.
    """
    try:
        platformInterfaces = getPlatformParents(platformData)
        parents = resolveParents(
            parseSelector(selector), platformInterfaces).parents

        common = None
        order = []
        for parent in parents:
            modes = platformInterfaces[parent].get('breakout_modes', {})
            if common is None:
                # Offer modes in the order platform.json declares them. That
                # is the order the single-parent command has always offered,
                # and it keeps related modes together where sorting by name
                # interleaves them.
                order = list(modes)
                common = set(modes)
            else:
                common &= set(modes)

        return [mode for mode in order if mode in common]
    except Exception:
        # A shell completion callback must never raise.
        return []


def _platformInterfaces():
    """Return (platform.json path, interfaces mapping)."""
    platformFile = device_info.get_path_to_port_config_file()

    if not os.path.isfile(platformFile) or not platformFile.endswith('.json'):
        click.secho("[ERROR] Breakout feature is not available without "
                    "platform.json file", fg='red')
        raise click.Abort()

    try:
        with open(platformFile) as f:
            platformInterfaces = getPlatformParents(json.load(f))
    except DpbPlatformDataError as e:
        click.secho("[ERROR] {}".format(e), fg='red')
        raise click.Abort()
    except Exception as e:
        click.secho("[ERROR] Failed to read {}: {}".format(platformFile, e),
                    fg='red')
        raise click.Abort()

    return platformFile, platformInterfaces


def _exitCode(results):
    """Nonzero when anything the operator named failed.

    SKIPPED_NOT_PARENT counts as a failure because only an exact term can
    produce it: a range filters the platform parent set, so it never yields a
    non-parent. An explicitly named port that cannot be broken out is a bad
    command, not a no-op, and must not look like success to a caller.
    Being already in the target mode is a genuine no-op and stays at 0.
    """
    statuses = {result.status for result in results}
    if statuses & {FAILED_BULK, FAILED_PRECHECK, SKIPPED_NOT_PARENT}:
        return 1
    return 0


def _report(results):
    click.echo("\nBreakout result:")
    for line in summaryLines(results):
        click.echo(line)


def _reportNoAction(results):
    """Report a selection that left nothing to do, and return its exit code."""
    _report(results)

    exitCode = _exitCode(results)
    if exitCode:
        click.secho("[ERROR] No breakout was performed; see the result "
                    "above.", fg='red')
    else:
        click.secho("No port needs a breakout mode change. No action taken.",
                    fg='cyan')

    return exitCode


def _validatePlan(engineFactory, results, plan, mode, force, skipUnsupported,
                  loadDefConfig):
    """Validate the aggregate against a cloned config before any write.

    Without -s, any blamed parent aborts the whole command, so the operator is
    never given a silently reduced selection. With -s the blamed parents are
    dropped and the plan is rebuilt once without them. Anything that cannot be
    attributed is an aggregate failure and no write may follow.

    force only decides whether the engine may delete blocking dependencies;
    skipUnsupported decides whether a rejected parent is fatal.

    Returns (plan, error). A non-None error means give up.
    """
    for attempt in range(2):
        # _deletePorts()/_addPorts() mutate the engine's data tree, so every
        # attempt needs its own clone of the running configuration.
        deps, ok = engineFactory().validateBreakOutPort(
            delPorts=plan.delPorts, portJson=plan.portJson, force=force,
            loadDefConfig=loadDefConfig)
        if ok:
            return plan, None

        blamed = attributeDependencies(deps or [], plan.ready)
        if not blamed or attempt:
            plan.markReady(FAILED_BULK,
                           'aggregate validation failed before any write')
            return plan, ("Breakout validation failed for the whole "
                          "selection. No change was made.")

        if not skipUnsupported:
            return plan, ("Dependencies exist for: {}. Nothing was changed. "
                          "Re-run with -f to clear them, or -s to break out "
                          "the remaining ports.".format(
                              ', '.join(sorted(blamed))))

        for result in plan.ready:
            if result.name in blamed:
                result.status = FAILED_PRECHECK
                result.reason = 'dependencies exist: {}'.format(
                    '; '.join(blamed[result.name]))

        plan, crossReason = buildBulkPlan(results, mode)
        if crossReason or plan.isEmpty:
            return plan, crossReason

    return plan, None


def _fieldMatches(field, planned, live):
    """Compare one planned PORT field against the value CONFIG_DB holds.

    Lanes compare as a set, as the current-layout check already compares live
    PORT rows that way, so a difference in ordering or spacing is not mistaken
    for a bad write. Everything else compares as text, since CONFIG_DB stores
    every value as a string whatever platform.json used.
    """
    if field == 'lanes':
        return _splitLanes(planned) == _splitLanes(live)

    return str(planned) == str(live)


def _observeParents(configDb, plan):
    """Re-read CONFIG_DB and judge every parent against what was planned.

    Reporting from observed state rather than from how far the writes are
    believed to have got means a partial result names the parents that really
    changed, and also catches a write that failed without raising.

    Scope is the target PORT rows, leftover old ports and the BREAKOUT_CFG
    marker. Dependency removals and -l default config are out of scope because
    the engine derives both internally and reports neither, so there is
    nothing recorded to compare against; the caller must not read a clean
    result here as covering them.

    Returns {parent: reason}, where a None reason means the parent arrived.
    """
    portTable = configDb.get_table('PORT')
    brkoutCfg = configDb.get_table(BREAKOUT_CFG_TABLE)
    intended = plan.portJson['PORT']

    observed = {}
    for result in plan.ready:
        reasons = []

        missing = [port for port in natsorted(result.targetChildren)
                   if port not in portTable]
        if missing:
            reasons.append('absent from PORT: {}'.format(', '.join(missing)))

        # A port can arrive under the right name and still carry the wrong
        # lanes, speed, alias, index or subport, so compare every field the
        # plan specified. Fields the plan did not specify are left alone: the
        # plan is the only record of intent available here, and it does not
        # carry the default config -l asks the engine to add.
        wrong = []
        for port in natsorted(result.targetChildren):
            live = portTable.get(port)
            if live is None:
                # Already reported as absent above.
                continue
            planned = intended.get(port) or {}
            bad = [field for field in sorted(planned)
                   if not _fieldMatches(field, planned[field],
                                        live.get(field))]
            if bad:
                wrong.append('{} ({})'.format(port, ', '.join(bad)))

        if wrong:
            reasons.append('wrong values in PORT: {}'.format(
                '; '.join(wrong)))

        # An old child kept by another parent's target layout is rejected by
        # validateCrossParent(), so anything still present here is a leftover.
        leftover = [port for port in natsorted(result.curChildren)
                    if port in portTable and port not in intended]
        if leftover:
            reasons.append('old ports still in PORT: {}'.format(
                ', '.join(leftover)))

        marker = (brkoutCfg.get(result.name) or {}).get(BRKOUT_MODE_FIELD)
        if marker != plan.targetMode:
            reasons.append('{} reads {}'.format(
                BREAKOUT_CFG_TABLE, marker or 'nothing'))

        observed[result.name] = '; '.join(reasons) or None

    return observed


def _blocked(results):
    """Parents the operator named that cannot be broken out at all."""
    return [result for result in results
            if result.status in (FAILED_PRECHECK, SKIPPED_NOT_PARENT)]


def _apply(configDb, plan, engineFactory, applyPorts, force, loadDefConfig):
    """Run the accepted aggregate, then report what CONFIG_DB actually holds."""
    error = None
    # The engine reports only success or failure for the whole delete/add, so
    # this is the finest attribution available here. It is still worth having:
    # it tells the operator whether the ports were written before the run
    # stopped, which decides where to look first.
    phase = 'port delete and add'

    try:
        # applyPorts() aborts the operation on failure.
        applyPorts(engineFactory(), plan.delPorts, plan.portJson, force,
                   loadDefConfig)

        # One aggregate marker update rather than one call per parent.
        phase = '{} update'.format(BREAKOUT_CFG_TABLE)
        configDb.mod_config({BREAKOUT_CFG_TABLE: plan.markerPatch})
    except (Exception, SystemExit) as e:
        # applyPorts() exits rather than raising on a dependency failure, so
        # SystemExit must not slip past the reporting below.
        error = e

    observed = _observeParents(configDb, plan)

    if error is not None:
        click.secho("\n[ERROR] Breakout did not run to completion during the "
                    "{}: {}".format(phase, error), fg='red')
        # Success must never be claimed after an exception, even where
        # CONFIG_DB reads correctly. The run stopped partway, so everything it
        # had not reached was never attempted, and the checks below cover only
        # the target PORT rows and the marker: a parent whose ports happen to
        # look right may still be missing dependency or default-config work
        # that nothing here inspects.
        observed = {
            name: reason or 'apply stopped during the {}: {}'.format(
                phase, error)
            for name, reason in observed.items()
        }

    for result in plan.ready:
        reason = observed[result.name]
        result.status = FAILED_BULK if reason else APPLIED
        result.reason = reason

    failed = natsorted(name for name, reason in observed.items() if reason)
    if failed:
        click.secho("[ERROR] Did not reach {}: {}".format(
            plan.targetMode, ', '.join(failed)), fg='red')
        click.secho("There is no automatic rollback, and old ports may still "
                    "exist in ASIC DB even where CONFIG_DB looks correct. "
                    "Inspect PORT, its dependencies and {} before retrying."
                    .format(BREAKOUT_CFG_TABLE), fg='red')
        return False

    click.secho("Breakout process got successfully completed.",
                fg="cyan", underline=True)
    click.echo("Run `show interfaces breakout current-mode` to check the "
               "resulting modes.")
    # get_child_ports() does not emit admin_status, so a newly created port has
    # none and is therefore admin down.
    click.echo("The new ports are created without an admin state, so they are "
               "admin down. Use `config interface startup` to bring up the "
               "ones you need.")
    click.echo("Please note loaded setting will be lost after system reboot. "
               "To preserve setting, run `config save`.")
    return True


def runBreakout(configDb, selector, mode, force, skipUnsupported,
                loadDefConfig, yes, engineFactory, applyPorts, warnExtraTables,
                lockFile, readOidPorts):
    """Apply one target breakout mode to every parent named by the selector.

    force:          let the engine delete config that blocks the breakout.
    skipUnsupported: continue with the remaining parents when one cannot be
                    broken out, instead of aborting the whole command.
    configDb:       connector used for all reads and the marker write.
    engineFactory:  returns a fresh ConfigMgmtDPB on each call.
    applyPorts:     (cm, delPorts, portJson, force, loadDefConfig) -> None,
                    aborting on failure.
    warnExtraTables: (cm, delPorts) -> None, may prompt.
    lockFile:       path of the shared system reload lock.
    readOidPorts:   () -> set of port names holding an ASIC DB OID.

    Returns the process exit code. Raises DpbUsageError for a bad selector.
    """
    platformFile, platformInterfaces = _platformInterfaces()

    try:
        terms = parseSelector(selector)
    except DpbSelectorError as e:
        raise DpbUsageError(str(e))

    isSingleExactTerm = len(terms) == 1 and isinstance(terms[0], ExactTerm)
    if multi_asic.is_multi_asic() and not isSingleExactTerm:
        raise DpbUsageError(
            "Interface ranges and lists are not supported on multi-ASIC "
            "platforms. Break out one parent port at a time.")

    def buildPlan(onlyParents=None):
        """Resolve, preflight and plan. Reads only; no writes, no prompts.

        onlyParents restricts planning to an already accepted set, so the
        post-confirmation check compares like with like and can never widen
        the operation past what the operator agreed to.
        """
        resolution = resolveParents(terms, platformInterfaces)
        # Read afresh on every call, including the one under the lock, so a
        # parent that lost its OID while the operator was answering the prompt
        # is caught rather than carried over from the first plan.
        results = preflightParents(
            resolution.parents, resolution.notParents, platformInterfaces,
            platformFile, configDb.get_table(BREAKOUT_CFG_TABLE),
            configDb.get_table('PORT'), mode, oidPorts=readOidPorts())
        if onlyParents is not None:
            results = [result for result in results
                       if result.name in onlyParents]
        plan, reason = buildBulkPlan(results, mode)
        return results, plan, reason

    # Fail fast if a participating operation already holds the lock, rather
    # than after the operator has read the plan and confirmed. This is only a
    # probe, so it cannot promise the write phase below will get the lock.
    with FileLock(lockFile, owner='breakout precheck', timeout=0):
        pass

    # Planning only reads, so it does not need the lock. Holding a lock across
    # an open prompt would stall other participating operations for as long as
    # the operator takes to answer, and everything read here is read again
    # under the lock before any write.
    results, plan, crossReason = buildPlan()

    if plan.isEmpty:
        return _reportNoAction(results)

    if crossReason:
        plan.markReady(FAILED_BULK, crossReason)
        _report(results)
        click.secho("[ERROR] {}".format(crossReason), fg='red')
        return 1

    # A parent the operator named that cannot be broken out aborts everything
    # unless -s is given. Quietly narrowing the selection would let a script
    # ask for 64 ports, get 61, and report success.
    blocked = _blocked(results)
    if blocked and not skipUnsupported:
        _report(results)
        click.secho("[ERROR] {} cannot be broken out to {}. Nothing was "
                    "changed. Re-run with -s to break out the remaining "
                    "ports.".format(
                        ', '.join(result.name for result in blocked), mode),
                    fg='red')
        return 1

    plan, validationError = _validatePlan(
        engineFactory, results, plan, mode, force, skipUnsupported,
        loadDefConfig)
    if validationError:
        _report(results)
        click.secho("[ERROR] {}".format(validationError), fg='red')
        return 1

    if plan.isEmpty:
        return _reportNoAction(results)

    # Validation may have dropped further parents under -f.
    dropped = _blocked(results)

    acceptedParents = list(plan.parents)
    acceptedDelPorts = list(plan.delPorts)

    notices = noticeLines(results)
    if notices:
        click.echo("\nNot breaking out:")
        for line in notices:
            click.echo(line)

    click.echo("")
    for line in planLines(plan):
        click.echo(line)

    if force:
        # -f hands dependency removal to the engine, which finds and deletes
        # dependencies as they stand when it runs, so they are never
        # enumerated in the plan above and one created between now and then
        # would be removed too. Say so rather than imply the plan is a
        # complete list of what will change.
        click.secho("\n-f is set, so any configuration that depends on the "
                    "deleted ports will be removed as it stands when the "
                    "breakout runs. Dependencies are not listed above and "
                    "are not re-checked after this prompt.", fg='yellow')

    # Warn about tables without yang models that reference deleted ports.
    # This confirmation is kept even with -y.
    warnExtraTables(engineFactory(), acceptedDelPorts)

    if not yes:
        click.confirm('Do you want to Breakout the port, continue?',
                      abort=True)

    with FileLock(lockFile, owner='breakout', timeout=0):
        # Anything read before the prompt may be stale now, and cross-DB reads
        # are not transactional, so plan again under the lock.
        results, plan, crossReason = buildPlan(acceptedParents)
        if crossReason or plan.parents != acceptedParents or \
                plan.delPorts != acceptedDelPorts:
            click.secho("[ERROR] The configuration changed while waiting for "
                        "confirmation. Nothing was written; please re-run the "
                        "command.", fg='red')
            return 1

        applied = _apply(configDb, plan, engineFactory, applyPorts, force,
                         loadDefConfig)
        if not applied:
            _report(results)

        # -s is the operator accepting up front that unsupported parents get
        # skipped, so skipping them is the requested outcome rather than a
        # failure; reporting one would leave a script unable to tell the two
        # apart. A name that is not a parent at all still fails, because that
        # is a bad command and no flag was asked to tolerate it.
        unrequested = [result for result in dropped
                       if result.status == SKIPPED_NOT_PARENT
                       or not skipUnsupported]

        return 0 if applied and not unrequested else 1

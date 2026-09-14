"""Tests for the destructive orchestration in runBreakout() and _validatePlan().

These cover the ordering that makes the command safe rather than the planning
arithmetic covered elsewhere: which locks are taken and when, that the plan is
rebuilt under the write lock, that drift there writes nothing at all, that the
prompt is honoured, and the exit code each outcome produces.

Every dependency runBreakout() takes is injected, so the harness below fakes
CONFIG_DB, the engine, the apply, the lock and the prompt, and records what was
called. A write is only ever observed through those records, which is what lets
"nothing was written" be asserted rather than assumed.
"""
import copy
import sys

import click
import pytest
from unittest import mock

from config import dpb
from tests.dpb_preflight_test import (
    PLATFORM_FILE, PLATFORM_INTERFACES, fake_get_child_ports)

TARGET = '4x25G'
LOCK_FILE = '/tmp/dpb-orchestration-test.lock'

PRECHECK_LOCK = 'breakout precheck'
WRITE_LOCK = 'breakout'
CONFIRM = 'confirm'

# Two flat parents at 1x100G, matching PLATFORM_INTERFACES.
INITIAL_PORTS = {
    'Ethernet0': {'lanes': '0,1,2,3', 'speed': '100000'},
    'Ethernet4': {'lanes': '4,5,6,7', 'speed': '100000'},
}

INITIAL_BRKOUT_CFG = {
    'Ethernet0': {'brkout_mode': '1x100G'},
    'Ethernet4': {'brkout_mode': '1x100G'},
}

# The 4x25G layout of both parents, for a selection that needs no change.
BROKEN_OUT_PORTS = {
    'Ethernet{}'.format(lane): {'lanes': str(lane), 'speed': '25000'}
    for lane in range(8)
}


def okValidate(harness, delPorts, force):
    return [], True


def dependsOn(child):
    """A validate hook reporting one dependency naming child, unless forced."""
    dep = 'VLAN_MEMBER|Vlan100|{}'.format(child)

    def validate(harness, delPorts, force):
        if force or child not in delPorts:
            return [], True
        return [dep], False

    return validate


class Harness(object):
    """runBreakout() with every injected dependency faked and recorded.

    Doubles as the configDb argument, since runBreakout() only ever calls
    get_table() and mod_config() on it.
    """

    def __init__(self, ports=None, brkoutCfg=None, validate=okValidate,
                 applyError=None, beforeWrite=None, missingOids=(),
                 lockFailures=(), confirmAbort=False):
        self.ports = copy.deepcopy(
            INITIAL_PORTS if ports is None else ports)
        self.brkoutCfg = copy.deepcopy(
            INITIAL_BRKOUT_CFG if brkoutCfg is None else brkoutCfg)
        self.validate = validate
        self.applyError = applyError
        # Called on acquiring the write lock, standing in for the
        # configuration changing while the operator answered the prompt.
        self.beforeWrite = beforeWrite
        self.missingOids = set(missingOids)
        self.lockFailures = set(lockFailures)
        self.confirmAbort = confirmAbort

        self._initialPorts = copy.deepcopy(self.ports)
        self._initialBrkoutCfg = copy.deepcopy(self.brkoutCfg)

        # Lock acquisitions and the prompt, in the order they happened.
        self.events = []
        self.lockReleases = []
        self.tableReads = []
        self.oidReads = 0
        self.engineCount = 0
        self.validateCalls = []
        self.applyCalls = []
        self.markerWrites = []
        self.warnCalls = []
        self.confirmMock = None

    @property
    def lockEvents(self):
        return [event for event in self.events if event != CONFIRM]

    # --- CONFIG_DB ---

    def get_table(self, name):
        self.tableReads.append(name)
        if name == 'PORT':
            return copy.deepcopy(self.ports)
        if name == dpb.BREAKOUT_CFG_TABLE:
            return copy.deepcopy(self.brkoutCfg)
        return {}

    def mod_config(self, patch):
        self.markerWrites.append(copy.deepcopy(patch))
        for name, fields in patch[dpb.BREAKOUT_CFG_TABLE].items():
            self.brkoutCfg.setdefault(name, {}).update(fields)

    # --- injected dependencies ---

    def _readOidPorts(self):
        self.oidReads += 1
        return set(self.ports) - self.missingOids

    def _engineFactory(self):
        self.engineCount += 1
        harness = self

        class _Engine(object):
            def validateBreakOutPort(self, delPorts=None, portJson=None,
                                     force=False, loadDefConfig=True):
                harness.validateCalls.append(
                    {'delPorts': list(delPorts or []), 'force': force,
                     'loadDefConfig': loadDefConfig})
                return harness.validate(harness, list(delPorts or []), force)

        return _Engine()

    def _applyPorts(self, cm, delPorts, portJson, force, loadDefConfig):
        self.applyCalls.append({'delPorts': list(delPorts), 'force': force,
                                'loadDefConfig': loadDefConfig})
        if self.applyError is not None:
            raise self.applyError

        for port in delPorts:
            self.ports.pop(port, None)
        for port, fields in portJson['PORT'].items():
            self.ports[port] = dict(fields)

    def _warnExtraTables(self, cm, delPorts):
        self.warnCalls.append(list(delPorts))

    def _lock(self, lockFile, owner, timeout=0):
        assert lockFile == LOCK_FILE
        harness = self

        class _Ctx(object):
            def __enter__(ctx):
                harness.events.append(owner)
                if owner in harness.lockFailures:
                    # The real FileLock exits rather than raising.
                    sys.exit(1)
                if owner == WRITE_LOCK and harness.beforeWrite is not None:
                    harness.beforeWrite(harness)
                return ctx

            def __exit__(ctx, *exc):
                harness.lockReleases.append(owner)
                return False

        return _Ctx()

    def _confirm(self, *args, **kwargs):
        self.events.append(CONFIRM)
        if self.confirmAbort:
            raise click.Abort()

    # --- the call under test ---

    def run(self, selector='Ethernet0-4', mode=TARGET, force=False,
            skipUnsupported=False, loadDefConfig=False, yes=True,
            multiAsic=False):
        self.confirmMock = mock.Mock(side_effect=self._confirm)

        with mock.patch.object(
                    dpb, '_platformInterfaces',
                    return_value=(PLATFORM_FILE, PLATFORM_INTERFACES)), \
                mock.patch.object(dpb, 'get_child_ports',
                                  fake_get_child_ports), \
                mock.patch.object(dpb.multi_asic, 'is_multi_asic',
                                  return_value=multiAsic), \
                mock.patch.object(dpb, 'FileLock', self._lock), \
                mock.patch.object(click, 'confirm', self.confirmMock):
            return dpb.runBreakout(
                self, selector, mode, force, skipUnsupported, loadDefConfig,
                yes, self._engineFactory, self._applyPorts,
                self._warnExtraTables, LOCK_FILE, self._readOidPorts)

    # --- assertions ---

    def assertNothingWritten(self):
        assert self.applyCalls == []
        assert self.markerWrites == []
        assert self.ports == self._initialPorts
        assert self.brkoutCfg == self._initialBrkoutCfg


class TestLockOrdering:
    """The lock is probed early, then held only across the write."""

    def test_both_locks_are_taken_in_order_and_released(self):
        harness = Harness()

        assert harness.run() == 0
        assert harness.lockEvents == [PRECHECK_LOCK, WRITE_LOCK]
        assert harness.lockReleases == [PRECHECK_LOCK, WRITE_LOCK]

    def test_the_probe_is_released_before_planning_reads_anything(self):
        harness = Harness()

        assert harness.run() == 0
        assert harness.lockReleases[0] == PRECHECK_LOCK
        assert harness.tableReads

    def test_a_busy_lock_stops_the_command_before_it_reads_anything(self):
        harness = Harness(lockFailures=[PRECHECK_LOCK])

        with pytest.raises(SystemExit):
            harness.run()

        assert harness.lockEvents == [PRECHECK_LOCK]
        assert harness.tableReads == []
        harness.assertNothingWritten()

    def test_losing_the_write_lock_writes_nothing(self):
        """Planning succeeded, but the write phase never got the lock."""
        harness = Harness(lockFailures=[WRITE_LOCK])

        with pytest.raises(SystemExit):
            harness.run()

        assert harness.lockEvents == [PRECHECK_LOCK, WRITE_LOCK]
        harness.assertNothingWritten()

    def test_the_prompt_is_answered_before_the_write_lock_is_taken(self):
        """Holding the lock across an open prompt would stall other writers."""
        harness = Harness()

        assert harness.run(yes=False) == 0
        assert harness.events == [PRECHECK_LOCK, CONFIRM, WRITE_LOCK]


class TestReplanningUnderTheLock:
    """Everything read before the prompt is read again before writing."""

    def test_the_plan_is_rebuilt_and_oids_reread_under_the_lock(self):
        harness = Harness()

        assert harness.run() == 0
        # Once before the prompt, once under the write lock.
        assert harness.oidReads == 2
        # The same two plans, plus the verification read after the apply.
        assert harness.tableReads.count('PORT') == 3
        assert harness.tableReads.count(dpb.BREAKOUT_CFG_TABLE) == 3

    def test_a_parent_that_changed_mode_during_the_prompt_blocks_the_write(self):
        def drift(harness):
            harness.brkoutCfg['Ethernet4'] = {'brkout_mode': TARGET}

        harness = Harness(beforeWrite=drift)

        assert harness.run() == 1
        assert harness.applyCalls == []
        assert harness.markerWrites == []

    def test_a_parent_that_lost_its_oid_during_the_prompt_blocks_the_write(self):
        def drift(harness):
            harness.missingOids.add('Ethernet4')

        harness = Harness(beforeWrite=drift)

        assert harness.run() == 1
        assert harness.applyCalls == []
        assert harness.markerWrites == []

    def test_a_new_port_taking_target_lanes_blocks_the_write(self):
        def drift(harness):
            harness.ports['Ethernet5'] = {'lanes': '5', 'speed': '25000'}

        harness = Harness(beforeWrite=drift)

        assert harness.run() == 1
        assert harness.applyCalls == []

    def test_drift_reduces_nothing_silently(self):
        """A shrunken plan is refused, not applied to the parents that remain."""
        def drift(harness):
            harness.brkoutCfg['Ethernet4'] = {'brkout_mode': TARGET}

        harness = Harness(beforeWrite=drift)
        harness.run()

        # Ethernet0 was still valid, but no partial write was made.
        assert 'Ethernet1' not in harness.ports
        assert harness.brkoutCfg['Ethernet0'] == {'brkout_mode': '1x100G'}

    def test_replanning_cannot_widen_past_the_accepted_parents(self):
        """A parent that became eligible during the prompt is not picked up."""
        ports = dict(BROKEN_OUT_PORTS)
        ports['Ethernet0'] = dict(INITIAL_PORTS['Ethernet0'])
        for lane in (1, 2, 3):
            ports.pop('Ethernet{}'.format(lane))

        # Ethernet4 is already at the target, so it is skipped, not accepted.
        harness = Harness(
            ports=ports,
            brkoutCfg={'Ethernet0': {'brkout_mode': '1x100G'},
                       'Ethernet4': {'brkout_mode': TARGET}})

        def drift(h):
            for lane in (5, 6, 7):
                h.ports.pop('Ethernet{}'.format(lane))
            h.ports['Ethernet4'] = dict(INITIAL_PORTS['Ethernet4'])
            h.brkoutCfg['Ethernet4'] = {'brkout_mode': '1x100G'}

        harness.beforeWrite = drift

        assert harness.run() == 0
        assert harness.applyCalls[0]['delPorts'] == ['Ethernet0']
        assert list(harness.markerWrites[0][dpb.BREAKOUT_CFG_TABLE]) == \
            ['Ethernet0']


class TestConfirmation:
    def test_yes_skips_the_prompt(self):
        harness = Harness()

        assert harness.run(yes=True) == 0
        assert harness.confirmMock.call_count == 0

    def test_without_yes_the_operator_is_asked(self):
        harness = Harness()

        assert harness.run(yes=False) == 0
        assert harness.confirmMock.call_count == 1

    def test_declining_the_prompt_writes_nothing(self):
        harness = Harness(confirmAbort=True)

        with pytest.raises(click.Abort):
            harness.run(yes=False)

        assert harness.lockEvents == [PRECHECK_LOCK]
        harness.assertNothingWritten()

    def test_the_extra_table_warning_is_kept_even_with_yes(self):
        harness = Harness()

        assert harness.run(yes=True) == 0
        assert harness.warnCalls == [['Ethernet0', 'Ethernet4']]


class TestSkipAndForce:
    """-s decides whether a rejected parent is fatal; -f only clears deps."""

    # Ethernet4 does not advertise 2x50G, so it fails precheck for that mode.
    MIXED_MODE = '2x50G'

    def test_an_unsupported_parent_aborts_everything_without_skip(self):
        harness = Harness()

        assert harness.run(mode=self.MIXED_MODE, skipUnsupported=False) == 1
        harness.assertNothingWritten()

    def test_skip_breaks_out_the_remaining_parent_and_exits_zero(self):
        harness = Harness()

        assert harness.run(mode=self.MIXED_MODE, skipUnsupported=True) == 0
        assert harness.applyCalls[0]['delPorts'] == ['Ethernet0']
        assert harness.ports['Ethernet0'] == {'lanes': '0,1',
                                              'speed': '50000'}
        assert harness.ports['Ethernet2'] == {'lanes': '2,3',
                                              'speed': '50000'}
        # The skipped parent is untouched.
        assert harness.ports['Ethernet4'] == INITIAL_PORTS['Ethernet4']
        assert harness.brkoutCfg['Ethernet4'] == {'brkout_mode': '1x100G'}

    def test_a_misspelled_port_is_a_failure_even_with_skip(self):
        """-s tolerates unsupported parents, not a bad command."""
        harness = Harness()

        code = harness.run(selector='Ethernet0,Ethernet4,Ethernet999',
                           skipUnsupported=True)

        # The real parents were broken out, but the exit code still reports
        # the name that is not a parent at all.
        assert code == 1
        assert harness.applyCalls[0]['delPorts'] == ['Ethernet0', 'Ethernet4']

    def test_a_misspelled_port_aborts_everything_without_skip(self):
        harness = Harness()

        assert harness.run(selector='Ethernet0,Ethernet999') == 1
        harness.assertNothingWritten()

    def test_force_is_passed_through_to_validation_and_apply(self):
        harness = Harness()

        assert harness.run(force=True) == 0
        assert all(call['force'] for call in harness.validateCalls)
        assert harness.applyCalls[0]['force'] is True

    def test_dependencies_abort_the_command_without_force(self):
        harness = Harness(validate=dependsOn('Ethernet4'))

        assert harness.run(force=False, skipUnsupported=False) == 1
        harness.assertNothingWritten()

    def test_skip_drops_the_parent_holding_a_dependency(self):
        harness = Harness(validate=dependsOn('Ethernet4'))

        assert harness.run(force=False, skipUnsupported=True) == 0
        assert harness.applyCalls[0]['delPorts'] == ['Ethernet0']
        assert harness.ports['Ethernet4'] == INITIAL_PORTS['Ethernet4']

    def test_force_keeps_the_parent_that_skip_would_have_dropped(self):
        harness = Harness(validate=dependsOn('Ethernet4'))

        assert harness.run(force=True, skipUnsupported=True) == 0
        assert harness.applyCalls[0]['delPorts'] == ['Ethernet0', 'Ethernet4']


class TestExitCodes:
    def test_a_clean_breakout_exits_zero(self):
        harness = Harness()

        assert harness.run() == 0
        assert sorted(harness.ports) == sorted(BROKEN_OUT_PORTS)
        assert harness.brkoutCfg['Ethernet0'] == {'brkout_mode': TARGET}
        assert harness.brkoutCfg['Ethernet4'] == {'brkout_mode': TARGET}

    def test_an_already_configured_selection_is_a_no_op_at_zero(self):
        harness = Harness(
            ports=BROKEN_OUT_PORTS,
            brkoutCfg={'Ethernet0': {'brkout_mode': TARGET},
                       'Ethernet4': {'brkout_mode': TARGET}})

        assert harness.run() == 0
        assert harness.applyCalls == []
        # The write lock is never taken, because there is nothing to write.
        assert harness.lockEvents == [PRECHECK_LOCK]

    def test_an_apply_exception_exits_nonzero(self):
        harness = Harness(applyError=RuntimeError('engine blew up'))

        assert harness.run() == 1
        assert harness.markerWrites == []

    def test_an_apply_exception_that_leaves_config_db_correct_still_fails(self):
        """The run stopped partway, so success must not be claimed.

        The apply here performs every write and only then raises, so the
        verification read afterwards finds exactly the intended state. The
        exception still has to decide the outcome.
        """
        harness = Harness()
        realApply = harness._applyPorts

        def applyThenFail(cm, delPorts, portJson, force, loadDefConfig):
            realApply(cm, delPorts, portJson, force, loadDefConfig)
            harness.brkoutCfg['Ethernet0'] = {'brkout_mode': TARGET}
            harness.brkoutCfg['Ethernet4'] = {'brkout_mode': TARGET}
            raise RuntimeError('lost the connection after writing')

        harness._applyPorts = applyThenFail

        assert harness.run() == 1

    def test_a_bad_selector_raises_a_usage_error(self):
        harness = Harness()

        with pytest.raises(dpb.DpbUsageError):
            harness.run(selector='Ethernet0 ,Ethernet4')

        # The selector is parsed before the lock is even probed.
        assert harness.lockEvents == []
        harness.assertNothingWritten()

    def test_a_range_is_refused_on_multi_asic(self):
        harness = Harness()

        with pytest.raises(dpb.DpbUsageError):
            harness.run(selector='Ethernet0-4', multiAsic=True)

        assert harness.lockEvents == []
        harness.assertNothingWritten()

    def test_a_single_parent_is_still_allowed_on_multi_asic(self):
        harness = Harness()

        assert harness.run(selector='Ethernet0', multiAsic=True) == 0
        assert harness.applyCalls[0]['delPorts'] == ['Ethernet0']


class TestValidatePlan:
    """_validatePlan() runs on throwaway clones and never writes."""

    @pytest.fixture(autouse=True)
    def _children(self):
        with mock.patch.object(dpb, 'get_child_ports', fake_get_child_ports):
            yield

    @staticmethod
    def _plan():
        results = dpb.preflightParents(
            ['Ethernet0', 'Ethernet4'], [], PLATFORM_INTERFACES,
            PLATFORM_FILE, copy.deepcopy(INITIAL_BRKOUT_CFG),
            copy.deepcopy(INITIAL_PORTS), TARGET)
        plan, reason = dpb.buildBulkPlan(results, TARGET)
        assert reason is None
        assert plan.parents == ['Ethernet0', 'Ethernet4']
        return results, plan

    def test_a_clean_validation_returns_the_plan_unchanged(self):
        results, plan = self._plan()
        harness = Harness()

        out, error = dpb._validatePlan(
            harness._engineFactory, results, plan, TARGET, False, False, False)

        assert error is None
        assert out.parents == ['Ethernet0', 'Ethernet4']
        assert harness.engineCount == 1

    def test_every_attempt_gets_a_fresh_engine_clone(self):
        """_deletePorts()/_addPorts() mutate the tree, so reuse would be wrong."""
        results, plan = self._plan()
        harness = Harness(validate=dependsOn('Ethernet4'))

        out, error = dpb._validatePlan(
            harness._engineFactory, results, plan, TARGET, False, True, False)

        assert error is None
        assert harness.engineCount == 2
        assert out.parents == ['Ethernet0']

    def test_an_attributable_dependency_without_skip_is_an_error(self):
        results, plan = self._plan()
        harness = Harness(validate=dependsOn('Ethernet4'))
        ready = list(plan.ready)

        out, error = dpb._validatePlan(
            harness._engineFactory, results, plan, TARGET, False, False, False)

        assert error is not None
        assert 'Ethernet4' in error
        assert '-f' in error and '-s' in error
        # Nothing is marked failed by a check that wrote nothing, so the
        # caller can still report the plan as it stood.
        assert all(result.isReady for result in ready)

    def test_skip_blames_the_owning_parent_and_replans(self):
        results, plan = self._plan()
        harness = Harness(validate=dependsOn('Ethernet4'))

        out, error = dpb._validatePlan(
            harness._engineFactory, results, plan, TARGET, False, True, False)

        assert error is None
        byName = {result.name: result for result in results}
        assert byName['Ethernet4'].status == dpb.FAILED_PRECHECK
        assert 'Vlan100' in byName['Ethernet4'].reason
        assert byName['Ethernet0'].isReady
        assert out.delPorts == ['Ethernet0']

    def test_an_unattributable_dependency_fails_the_aggregate(self):
        results, plan = self._plan()

        def deps(harness, delPorts, force):
            return ['SOME_TABLE|nothing-to-do-with-a-parent'], False

        harness = Harness(validate=deps)

        out, error = dpb._validatePlan(
            harness._engineFactory, results, plan, TARGET, False, True, False)

        assert error is not None
        assert all(result.status == dpb.FAILED_BULK for result in results)
        # There is no point re-planning what could not be blamed on anyone.
        assert harness.engineCount == 1

    def test_a_second_failure_after_replanning_fails_the_aggregate(self):
        results, plan = self._plan()

        def deps(harness, delPorts, force):
            child = 'Ethernet4' if 'Ethernet4' in delPorts else 'Ethernet0'
            return ['VLAN_MEMBER|Vlan100|{}'.format(child)], False

        harness = Harness(validate=deps)

        out, error = dpb._validatePlan(
            harness._engineFactory, results, plan, TARGET, False, True, False)

        assert error is not None
        assert harness.engineCount == 2

    def test_force_lets_the_dependency_through(self):
        results, plan = self._plan()
        harness = Harness(validate=dependsOn('Ethernet4'))

        out, error = dpb._validatePlan(
            harness._engineFactory, results, plan, TARGET, True, False, False)

        assert error is None
        assert out.parents == ['Ethernet0', 'Ethernet4']
        assert harness.engineCount == 1

    def test_load_default_config_is_passed_through(self):
        results, plan = self._plan()
        harness = Harness()

        dpb._validatePlan(harness._engineFactory, results, plan, TARGET,
                          False, False, True)

        assert harness.validateCalls[0]['loadDefConfig'] is True

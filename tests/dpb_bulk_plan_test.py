from config import dpb


def ready(name, curMode, targetMode, curChildren, targetChildren):
    return dpb.ParentResult(name, dpb.READY, curMode=curMode,
                            targetMode=targetMode, curChildren=curChildren,
                            targetChildren=targetChildren)


def lanes(spec):
    return {'lanes': spec, 'speed': '25000'}


ETH0_READY = ready(
    'Ethernet0', '1x100G', '4x25G',
    curChildren={'Ethernet0': lanes('0,1,2,3')},
    targetChildren={'Ethernet0': lanes('0'), 'Ethernet1': lanes('1'),
                    'Ethernet2': lanes('2'), 'Ethernet3': lanes('3')})

ETH4_READY = ready(
    'Ethernet4', '1x100G', '4x25G',
    curChildren={'Ethernet4': lanes('4,5,6,7')},
    targetChildren={'Ethernet4': lanes('4'), 'Ethernet5': lanes('5'),
                    'Ethernet6': lanes('6'), 'Ethernet7': lanes('7')})


def readyPair():
    """Two fresh READY results equivalent to ETH0_READY and ETH4_READY.

    markReady() and _apply() both write status and reason onto the results
    they are handed, so anything exercising them needs its own results rather
    than the shared constants above, which would otherwise carry an outcome
    from one test into the next depending on the order they run in.
    """
    return [
        ready('Ethernet0', '1x100G', '4x25G',
              curChildren={'Ethernet0': lanes('0,1,2,3')},
              targetChildren={'Ethernet0': lanes('0'),
                              'Ethernet1': lanes('1'),
                              'Ethernet2': lanes('2'),
                              'Ethernet3': lanes('3')}),
        ready('Ethernet4', '1x100G', '4x25G',
              curChildren={'Ethernet4': lanes('4,5,6,7')},
              targetChildren={'Ethernet4': lanes('4'),
                              'Ethernet5': lanes('5'),
                              'Ethernet6': lanes('6'),
                              'Ethernet7': lanes('7')}),
    ]


class TestPlanAggregation:
    def test_ready_parents_are_flattened_into_one_operation(self):
        plan, reason = dpb.buildBulkPlan([ETH0_READY, ETH4_READY], '4x25G')

        assert reason is None
        assert plan.delPorts == ['Ethernet0', 'Ethernet4']
        assert sorted(plan.portJson['PORT']) == [
            'Ethernet0', 'Ethernet1', 'Ethernet2', 'Ethernet3',
            'Ethernet4', 'Ethernet5', 'Ethernet6', 'Ethernet7']
        assert plan.markerPatch == {
            'Ethernet0': {'brkout_mode': '4x25G'},
            'Ethernet4': {'brkout_mode': '4x25G'},
        }

    def test_non_ready_parents_never_reach_the_apply_inputs(self):
        skipped = dpb.ParentResult(
            'Ethernet8', dpb.SKIPPED_ALREADY_CONFIGURED, curMode='4x25G',
            curChildren={'Ethernet8': lanes('8')})
        failed = dpb.ParentResult(
            'Ethernet12', dpb.FAILED_PRECHECK, reason='missing marker',
            curChildren={'Ethernet12': lanes('12')},
            targetChildren={'Ethernet12': lanes('12')})
        notParent = dpb.ParentResult('Ethernet999', dpb.SKIPPED_NOT_PARENT)

        plan, reason = dpb.buildBulkPlan(
            [notParent, ETH0_READY, skipped, failed], '4x25G')

        assert reason is None
        assert plan.parents == ['Ethernet0']
        assert 'Ethernet8' not in plan.delPorts
        assert 'Ethernet12' not in plan.delPorts
        assert 'Ethernet12' not in plan.portJson['PORT']
        assert set(plan.markerPatch) == {'Ethernet0'}

    def test_delete_list_is_deduplicated_and_naturally_ordered(self):
        """Deduplication is defensive: a child belongs to one parent in
        practice, but the delete list must never name a port twice."""
        first = ready(
            'Ethernet0', '4x25G', '1x100G',
            curChildren={'Ethernet0': lanes('0'), 'Ethernet2': lanes('2')},
            targetChildren={'Ethernet40': lanes('0,2')})
        second = ready(
            'Ethernet4', '4x25G', '1x100G',
            curChildren={'Ethernet2': lanes('2'), 'Ethernet10': lanes('10')},
            targetChildren={'Ethernet44': lanes('10,11')})

        plan, reason = dpb.buildBulkPlan([first, second], '1x100G')

        assert reason is None
        assert plan.delPorts.count('Ethernet2') == 1
        # Ethernet2 sorts before Ethernet10, not after it.
        assert plan.delPorts == ['Ethernet0', 'Ethernet2', 'Ethernet10']

    def test_empty_plan_is_reported_as_empty(self):
        plan, reason = dpb.buildBulkPlan(
            [dpb.ParentResult('Ethernet999', dpb.SKIPPED_NOT_PARENT)], '4x25G')

        assert reason is None
        assert plan.isEmpty
        assert plan.delPorts == []
        assert plan.portJson == {'PORT': {}}
        assert plan.markerPatch == {}


class TestCrossParentValidation:
    def test_two_parents_creating_the_same_port_is_rejected(self):
        clash = ready(
            'Ethernet4', '1x100G', '4x25G',
            curChildren={'Ethernet4': lanes('4,5,6,7')},
            targetChildren={'Ethernet2': lanes('4'), 'Ethernet5': lanes('5')})

        plan, reason = dpb.buildBulkPlan([ETH0_READY, clash], '4x25G')

        assert reason is not None
        assert 'Ethernet2' in reason
        assert plan.isEmpty is False

    def test_two_parents_claiming_the_same_lane_is_rejected(self):
        clash = ready(
            'Ethernet4', '1x100G', '4x25G',
            curChildren={'Ethernet4': lanes('4,5,6,7')},
            targetChildren={'Ethernet4': lanes('3'), 'Ethernet5': lanes('5')})

        _, reason = dpb.buildBulkPlan([ETH0_READY, clash], '4x25G')

        assert reason is not None
        assert 'lane 3' in reason

    def test_target_taking_over_another_parents_current_port_is_rejected(self):
        victim = ready(
            'Ethernet2', '1x100G', '4x25G',
            curChildren={'Ethernet2': lanes('8,9,10,11')},
            targetChildren={'Ethernet20': lanes('8'), 'Ethernet21': lanes('9'),
                            'Ethernet22': lanes('10'),
                            'Ethernet23': lanes('11')})

        # ETH0_READY creates Ethernet2, which is Ethernet2's own current port.
        _, reason = dpb.buildBulkPlan([ETH0_READY, victim], '4x25G')

        assert reason is not None
        assert 'take over' in reason

    def test_coherent_multi_parent_plan_passes(self):
        _, reason = dpb.buildBulkPlan([ETH0_READY, ETH4_READY], '4x25G')
        assert reason is None


class TestAggregateOutcomeMarking:
    def test_bulk_failure_marks_every_participating_parent(self):
        eth0, eth4 = readyPair()
        skipped = dpb.ParentResult('Ethernet999', dpb.SKIPPED_NOT_PARENT)
        plan, _ = dpb.buildBulkPlan([eth0, eth4, skipped], '4x25G')

        plan.markReady(dpb.FAILED_BULK, 'delete phase failed')

        assert eth0.status == dpb.FAILED_BULK
        assert eth4.status == dpb.FAILED_BULK
        assert eth0.reason == 'delete phase failed'
        # A parent that never took part keeps its own status.
        assert skipped.status == dpb.SKIPPED_NOT_PARENT


class FakeConfigDb:
    """CONFIG_DB stand-in returning fixed PORT and BREAKOUT_CFG tables."""

    def __init__(self, portTable, brkoutCfg, modConfigError=None):
        self._tables = {'PORT': portTable,
                        dpb.BREAKOUT_CFG_TABLE: brkoutCfg}
        self._modConfigError = modConfigError
        self.written = []

    def get_table(self, name):
        return dict(self._tables.get(name, {}))

    def mod_config(self, patch):
        self.written.append(patch)
        if self._modConfigError is not None:
            raise self._modConfigError


def appliedPortTable(plan, **overrides):
    """The PORT table a fully successful apply of this plan would leave."""
    table = {port: dict(fields)
             for port, fields in plan.portJson['PORT'].items()}
    table.update(overrides)
    return table


def appliedMarkers(plan):
    return dict(plan.markerPatch)


def runApply(plan, portTable, brkoutCfg, applyError=None,
             modConfigError=None):
    configDb = FakeConfigDb(portTable, brkoutCfg,
                            modConfigError=modConfigError)

    def applyPorts(cm, delPorts, portJson, force, loadDefConfig):
        if applyError is not None:
            raise applyError

    ok = dpb._apply(configDb, plan, lambda: object(), applyPorts,
                    False, False)
    return ok, configDb


class TestApplyReporting:
    """_apply() must never report success it has not verified."""

    @staticmethod
    def _plan():
        plan, reason = dpb.buildBulkPlan(readyPair(), '4x25G')
        assert reason is None
        assert len(plan.ready) == 2
        return plan

    def test_a_verified_apply_is_applied(self):
        plan = self._plan()

        ok, _ = runApply(plan, appliedPortTable(plan), appliedMarkers(plan))

        assert ok is True
        assert [r.status for r in plan.ready] == [dpb.APPLIED, dpb.APPLIED]
        assert all(r.reason is None for r in plan.ready)

    def test_an_apply_exception_fails_even_when_config_db_looks_correct(self):
        """The run stopped partway, so the unreached phases are unknown."""
        plan = self._plan()

        ok, _ = runApply(plan, appliedPortTable(plan), appliedMarkers(plan),
                         applyError=RuntimeError('engine blew up'))

        assert ok is False
        assert [r.status for r in plan.ready] == [dpb.FAILED_BULK,
                                                  dpb.FAILED_BULK]
        assert all('engine blew up' in r.reason for r in plan.ready)

    def test_a_systemexit_from_the_engine_is_not_success(self):
        """applyPorts() aborts rather than raising on dependency failure."""
        plan = self._plan()

        ok, _ = runApply(plan, appliedPortTable(plan), appliedMarkers(plan),
                         applyError=SystemExit(1))

        assert ok is False
        assert all(r.status == dpb.FAILED_BULK for r in plan.ready)

    def test_a_marker_write_exception_is_not_success(self):
        plan = self._plan()

        ok, _ = runApply(plan, appliedPortTable(plan), appliedMarkers(plan),
                         modConfigError=RuntimeError('redis gone'))

        assert ok is False
        assert all(dpb.BREAKOUT_CFG_TABLE in r.reason for r in plan.ready)

    def test_the_failing_phase_is_named(self):
        plan = self._plan()

        ok, _ = runApply(plan, appliedPortTable(plan), appliedMarkers(plan),
                         applyError=RuntimeError('boom'))
        assert 'port delete and add' in plan.ready[0].reason

        plan = self._plan()
        ok, _ = runApply(plan, appliedPortTable(plan), appliedMarkers(plan),
                         modConfigError=RuntimeError('boom'))
        assert dpb.BREAKOUT_CFG_TABLE in plan.ready[0].reason

    def test_an_observed_problem_outranks_the_generic_reason(self):
        """A specific finding is more useful than 'the apply stopped'."""
        plan = self._plan()
        portTable = appliedPortTable(plan)
        del portTable['Ethernet1']

        ok, _ = runApply(plan, portTable, appliedMarkers(plan),
                         applyError=RuntimeError('boom'))

        assert ok is False
        byName = {r.name: r for r in plan.ready}
        assert 'absent from PORT: Ethernet1' in byName['Ethernet0'].reason
        assert 'boom' in byName['Ethernet4'].reason

    def test_a_wrong_field_fails_a_clean_run(self):
        plan = self._plan()
        portTable = appliedPortTable(plan)
        portTable['Ethernet2'] = dict(portTable['Ethernet2'], speed='40000')

        ok, _ = runApply(plan, portTable, appliedMarkers(plan))

        assert ok is False
        byName = {r.name: r for r in plan.ready}
        assert 'speed' in byName['Ethernet0'].reason
        assert byName['Ethernet4'].status == dpb.APPLIED

    def test_a_missing_marker_fails_a_clean_run(self):
        plan = self._plan()
        markers = appliedMarkers(plan)
        del markers['Ethernet4']

        ok, _ = runApply(plan, appliedPortTable(plan), markers)

        assert ok is False
        byName = {r.name: r for r in plan.ready}
        assert byName['Ethernet0'].status == dpb.APPLIED
        assert dpb.BREAKOUT_CFG_TABLE in byName['Ethernet4'].reason

    def test_reordered_lanes_are_not_a_failure(self):
        plan = self._plan()
        portTable = appliedPortTable(plan)
        portTable['Ethernet0'] = dict(portTable['Ethernet0'], lanes=' 0 ')

        ok, _ = runApply(plan, portTable, appliedMarkers(plan))

        assert ok is True

    def test_extra_live_fields_are_not_a_failure(self):
        """-l defaults and unrelated fields are outside what the plan records."""
        plan = self._plan()
        portTable = appliedPortTable(plan)
        portTable['Ethernet0'] = dict(portTable['Ethernet0'],
                                      mtu='9100', admin_status='up')

        ok, _ = runApply(plan, portTable, appliedMarkers(plan))

        assert ok is True

import pytest
from unittest import mock

from config import config_mgmt


class FakeClock:
    """Monotonic clock that only advances when the code under test sleeps."""

    def __init__(self):
        self.now = 0.0
        self.slept = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


class VerifyAsicDbHarness:
    """Minimal stand-in for ConfigMgmtDPB.

    _verifyAsicDB only reaches back into sysLog and _portsStillInAsicDb, so the
    real object (and its yang model load) is not needed here.
    """

    def __init__(self, pending):
        # pending(call, ports) -> ports still in ASIC DB on that poll.
        self._pending = pending
        self.checkCalls = 0

    def sysLog(self, *args, **kwargs):
        pass

    def _portsStillInAsicDb(self, db, ports, portMap):
        self.checkCalls += 1
        return self._pending(self.checkCalls, ports)

    def verify(self, timeout, ports=None):
        return config_mgmt.ConfigMgmtDPB._verifyAsicDB(
            self, db=None, ports=ports if ports is not None else ['Ethernet0'],
            portMap={}, timeout=timeout)


def clearsAfter(seconds, clock):
    """All ports vanish once the clock reaches `seconds`."""
    return lambda call, ports: [] if clock.now >= seconds else list(ports)


class TestVerifyAsicDbWaitsWhileProgressing:
    def test_returns_immediately_when_ports_are_already_gone(self):
        clock = FakeClock()
        harness = VerifyAsicDbHarness(lambda call, ports: [])

        with mock.patch.object(config_mgmt, 'monotonic', clock.monotonic), \
                mock.patch.object(config_mgmt, 'tsleep', clock.sleep):
            assert harness.verify(timeout=300) is True

        assert harness.checkCalls == 1
        assert clock.slept == []

    def test_waits_well_past_the_stall_window_while_ports_keep_clearing(self):
        """The case a total budget gets wrong.

        Ports leave one per poll, so the whole delete takes far longer than the
        stall window. It must still succeed, because it never stopped
        progressing.
        """
        ports = ['Ethernet{}'.format(i) for i in range(64)]
        clock = FakeClock()
        # Nothing has gone on the first look; one port clears per poll after.
        harness = VerifyAsicDbHarness(lambda call, p: ports[call - 1:])

        with mock.patch.object(config_mgmt, 'monotonic', clock.monotonic), \
                mock.patch.object(config_mgmt, 'tsleep', clock.sleep):
            assert harness.verify(timeout=10, ports=ports) is True

        # 64 polls at one second each: far beyond the 10s stall window.
        assert clock.now == pytest.approx(len(ports))
        assert harness.checkCalls == len(ports) + 1

    def test_raises_once_nothing_has_cleared_for_the_stall_window(self):
        clock = FakeClock()
        harness = VerifyAsicDbHarness(lambda call, ports: list(ports))

        with mock.patch.object(config_mgmt, 'monotonic', clock.monotonic), \
                mock.patch.object(config_mgmt, 'tsleep', clock.sleep):
            with pytest.raises(Exception) as excinfo:
                harness.verify(timeout=60)

        assert 'without progress' in str(excinfo.value)
        assert clock.now == 60

    def test_stall_timer_restarts_on_every_port_that_clears(self):
        """Partial progress must buy a fresh stall window, then still time out."""
        ports = ['Ethernet0', 'Ethernet1']
        clock = FakeClock()
        # Ethernet0 goes at t=8s; Ethernet1 never does.
        harness = VerifyAsicDbHarness(
            lambda call, p: ports[1:] if clock.now >= 8 else list(ports))

        with mock.patch.object(config_mgmt, 'monotonic', clock.monotonic), \
                mock.patch.object(config_mgmt, 'tsleep', clock.sleep):
            with pytest.raises(Exception):
                harness.verify(timeout=10, ports=ports)

        # Without the restart this would have failed at 10s.
        assert clock.now == pytest.approx(18)

    def test_stuck_ports_are_named_in_the_failure(self):
        ports = ['Ethernet0', 'Ethernet4', 'Ethernet8']
        clock = FakeClock()
        harness = VerifyAsicDbHarness(lambda call, p: ['Ethernet4'])

        with mock.patch.object(config_mgmt, 'monotonic', clock.monotonic), \
                mock.patch.object(config_mgmt, 'tsleep', clock.sleep):
            with pytest.raises(Exception) as excinfo:
                harness.verify(timeout=5, ports=ports)

        message = str(excinfo.value)
        assert 'Ethernet4' in message
        # The ports that did clear are not blamed.
        assert 'Ethernet0' not in message and 'Ethernet8' not in message

    def test_a_recovering_db_read_failure_does_not_count_as_progress(self):
        """_portsStillInAsicDb reports everything outstanding when it cannot read.

        A count that jumps back up must not let the next drop look like fresh
        progress and extend the wait indefinitely.
        """
        ports = ['Ethernet0', 'Ethernet4']
        clock = FakeClock()

        def flapping(call, p):
            # Steady state is one port pending; every third poll "fails".
            return list(ports) if call % 3 == 0 else ['Ethernet4']

        harness = VerifyAsicDbHarness(flapping)

        with mock.patch.object(config_mgmt, 'monotonic', clock.monotonic), \
                mock.patch.object(config_mgmt, 'tsleep', clock.sleep):
            with pytest.raises(Exception):
                harness.verify(timeout=10, ports=ports)

        # Ethernet0 was already gone on the first look, so the flapping count
        # never establishes new progress and the window is never extended.
        assert clock.now == pytest.approx(10)

    @pytest.mark.parametrize('numPorts', [8, 64])
    def test_ceiling_stops_a_delete_that_trickles_forever(self, numPorts):
        """Endless slow progress still terminates, at this delete's ceiling.

        Ports leave 250s apart, which keeps resetting the 300s stall window, so
        only the ceiling can end this. Parametrised because the whole point of
        scaling is that a small delete does not inherit a wide one's ceiling.
        """
        clock = FakeClock()
        ports = ['Ethernet{}'.format(i) for i in range(numPorts)]
        harness = VerifyAsicDbHarness(
            lambda call, p: ports[int(clock.now // 250):])

        with mock.patch.object(config_mgmt, 'monotonic', clock.monotonic), \
                mock.patch.object(config_mgmt, 'tsleep', clock.sleep):
            with pytest.raises(Exception) as excinfo:
                harness.verify(timeout=300, ports=ports)

        expected = config_mgmt.getAsicDeleteHardTimeout(numPorts)
        assert clock.now == pytest.approx(expected)
        assert str(expected) in str(excinfo.value)

    def test_progress_reaches_stdout_on_a_long_wait(self, capsys):
        """The report must be printed, not merely handed to sysLog.

        sysLog(doPrint=True) only writes to the console above LOG_INFO or
        under python -i, so an informational progress line routed through it
        is invisible to an operator watching a multi-minute breakout.
        """
        ports = ['Ethernet{}'.format(i) for i in range(512)]
        clock = FakeClock()
        harness = VerifyAsicDbHarness(lambda call, p: ports[call - 1:])

        with mock.patch.object(config_mgmt, 'monotonic', clock.monotonic), \
                mock.patch.object(config_mgmt, 'tsleep', clock.sleep):
            assert harness.verify(timeout=300, ports=ports) is True

        progress = [l for l in capsys.readouterr().out.splitlines()
                    if 'Deleted' in l]
        assert progress, 'a multi-minute wait must report on stdout'
        assert 'of 512 ports' in progress[0]
        # 512 polls at one second each, reported at most every 30s.
        assert len(progress) <= \
            clock.now // config_mgmt.DPB_DELETE_REPORT_INTERVAL_SEC + 1

    def test_a_wait_shorter_than_the_interval_stays_silent(self, capsys):
        """Single-parent breakouts must look exactly as they always have."""
        ports = ['Ethernet0', 'Ethernet4']
        clock = FakeClock()
        interval = config_mgmt.DPB_DELETE_REPORT_INTERVAL_SEC
        harness = VerifyAsicDbHarness(
            lambda call, p: [] if clock.now >= interval - 5 else list(ports))

        with mock.patch.object(config_mgmt, 'monotonic', clock.monotonic), \
                mock.patch.object(config_mgmt, 'tsleep', clock.sleep):
            assert harness.verify(timeout=300, ports=ports) is True

        assert 'Deleted' not in capsys.readouterr().out

    def test_no_progress_chatter_when_ports_are_already_gone(self, capsys):
        clock = FakeClock()
        harness = VerifyAsicDbHarness(lambda call, ports: [])

        with mock.patch.object(config_mgmt, 'monotonic', clock.monotonic), \
                mock.patch.object(config_mgmt, 'tsleep', clock.sleep):
            harness.verify(timeout=300)

        assert capsys.readouterr().out == ''

    def test_wait_is_time_based_not_attempt_based(self):
        """A slow ASIC DB poll must not consume the stall window in one pass."""
        clock = FakeClock()

        def slowCheck(call, ports):
            # Each probe itself costs 4s; success arrives after three probes.
            clock.now += 4
            return [] if call >= 3 else list(ports)

        harness = VerifyAsicDbHarness(slowCheck)

        with mock.patch.object(config_mgmt, 'monotonic', clock.monotonic), \
                mock.patch.object(config_mgmt, 'tsleep', clock.sleep):
            assert harness.verify(timeout=300) is True

        assert harness.checkCalls == 3


class TestPortsStillInAsicDb:
    """The progress signal has to survey every port, not stop at the first."""

    def makeCm(self, present):
        cm = mock.MagicMock(spec=config_mgmt.ConfigMgmtDPB)
        cm.oidKey = 'ASIC_STATE:SAI_OBJECT_TYPE_PORT:oid:'
        cm._checkKeyinAsicDB.side_effect = \
            lambda key, db: key.rsplit(':', 1)[-1] in present
        return cm

    def test_reports_every_pending_port_not_just_the_first(self):
        portMap = {'Ethernet0': '0xa', 'Ethernet4': '0xb', 'Ethernet8': '0xc'}
        cm = self.makeCm(present={'0xa', '0xc'})

        pending = config_mgmt.ConfigMgmtDPB._portsStillInAsicDb(
            cm, db=mock.MagicMock(), ports=list(portMap), portMap=portMap)

        assert pending == ['Ethernet0', 'Ethernet8']
        # Every port probed: a first-hit check would have stopped at Ethernet0.
        assert cm._checkKeyinAsicDB.call_count == 3

    def test_empty_when_all_ports_are_gone(self):
        portMap = {'Ethernet0': '0xa', 'Ethernet4': '0xb'}
        cm = self.makeCm(present=set())

        assert config_mgmt.ConfigMgmtDPB._portsStillInAsicDb(
            cm, db=mock.MagicMock(), ports=list(portMap),
            portMap=portMap) == []

    def test_unreadable_db_reports_all_ports_outstanding(self):
        portMap = {'Ethernet0': '0xa', 'Ethernet4': '0xb'}
        cm = mock.MagicMock(spec=config_mgmt.ConfigMgmtDPB)
        cm.oidKey = 'oid:'
        cm._checkKeyinAsicDB.side_effect = Exception('ASIC DB unreachable')

        assert config_mgmt.ConfigMgmtDPB._portsStillInAsicDb(
            cm, db=mock.MagicMock(), ports=list(portMap),
            portMap=portMap) == ['Ethernet0', 'Ethernet4']

    def test_checkNoPorts_wrapper_agrees_with_the_survey(self):
        portMap = {'Ethernet0': '0xa'}
        cm = self.makeCm(present={'0xa'})
        cm._portsStillInAsicDb = \
            lambda db, ports, pm: config_mgmt.ConfigMgmtDPB._portsStillInAsicDb(
                cm, db, ports, pm)

        assert config_mgmt.ConfigMgmtDPB._checkNoPortsInAsicDb(
            cm, db=mock.MagicMock(), ports=['Ethernet0'],
            portMap=portMap) is False


class TestAsicDeleteHardTimeout:
    """The ceiling has to cover what was measured, without being unreadable."""

    # (old children deleted, worst wait measured on a Cisco 8122)
    MEASURED = [(8, 132), (64, 14), (498, 675)]

    def test_every_measured_delete_finishes_inside_its_ceiling(self):
        for count, observed in self.MEASURED:
            ceiling = config_mgmt.getAsicDeleteHardTimeout(count)
            assert ceiling > observed * 2, \
                '{} children: {}s ceiling leaves too little over {}s'.format(
                    count, ceiling, observed)

    def test_a_single_parent_ceiling_clears_the_worst_gap_for_every_child(self):
        """The eight-child case cannot false-fail even at the worst gap seen.

        The longest measured gap between consecutive removals is 33s. Paying
        that for all eight children of one 8x100G parent still has to fit.
        """
        assert config_mgmt.getAsicDeleteHardTimeout(8) > 8 * 33

    def test_scales_with_the_delete_count(self):
        assert config_mgmt.getAsicDeleteHardTimeout(1) \
            < config_mgmt.getAsicDeleteHardTimeout(8) \
            < config_mgmt.getAsicDeleteHardTimeout(512)

    def test_never_tighter_than_the_stall_window(self):
        """Otherwise the ceiling always expires first and the window is dead."""
        for count in (0, 1, 8, 64, 512):
            assert config_mgmt.getAsicDeleteHardTimeout(count) >= \
                config_mgmt.DPB_DELETE_STALL_TIMEOUT_SEC

    def test_a_single_child_delete_gets_essentially_the_stall_window(self):
        """With no progress signal available, one limit should govern.

        A one-child delete cannot report progress before it finishes, so the
        stall window is the only limit that can fire; the ceiling agreeing with
        it to within a few seconds keeps that from being two answers.
        """
        assert config_mgmt.getAsicDeleteHardTimeout(1) - \
            config_mgmt.DPB_DELETE_STALL_TIMEOUT_SEC < 10


class TestBreakOutPortUsesStallTimeout:
    def test_timeout_does_not_vary_with_the_delete_count(self):
        """The stall window is one constant whatever the selection.

        Only the ceiling scales, and the wait derives that itself from the port
        set, so nothing about the count reaches this call.
        """
        cmdpb = mock.MagicMock(spec=config_mgmt.ConfigMgmtDPB)
        cmdpb._deletePorts.return_value = ({}, None, True)
        cmdpb._addPorts.return_value = ({}, True)

        seen = []
        for numPorts in (1, 8, 512):
            delPorts = ['Ethernet{}'.format(i) for i in range(numPorts)]
            # Every port needs an OID, or the delete is refused before the
            # wait is reached and this would stop testing the timeout.
            oidMap = {port: '{:x}'.format(0x1000 + i)
                      for i, port in enumerate(delPorts)}
            with mock.patch.object(config_mgmt, 'SonicV2Connector'), \
                    mock.patch.object(config_mgmt.port_util,
                                      'get_interface_oid_map',
                                      return_value=(oidMap, {})):
                deps, ret = config_mgmt.ConfigMgmtDPB.breakOutPort(
                    cmdpb, delPorts=delPorts, portJson={'PORT': {}})

            assert ret is True
            seen.append(cmdpb._verifyAsicDB.call_args.kwargs['timeout'])

        assert seen == [config_mgmt.DPB_DELETE_STALL_TIMEOUT_SEC] * 3


class TestBreakOutPortRefusesUnverifiableDeletes:
    """A delete the wait cannot watch must be refused before any write.

    Without the OID map, _portsStillInAsicDb() raises KeyError, which it
    cannot tell apart from an unreadable DB and so reports every port as
    outstanding. No progress is ever observable, so the wait would burn the
    whole stall window and only then fail, with the ports already gone from
    Config DB.
    """

    @staticmethod
    def _engine():
        cmdpb = mock.MagicMock(spec=config_mgmt.ConfigMgmtDPB)
        cmdpb._deletePorts.return_value = ({}, None, True)
        cmdpb._addPorts.return_value = ({}, True)
        return cmdpb

    @staticmethod
    def _run(cmdpb, delPorts, oidMap):
        with mock.patch.object(config_mgmt, 'SonicV2Connector'), \
                mock.patch.object(config_mgmt.port_util,
                                  'get_interface_oid_map',
                                  return_value=(oidMap, {})):
            return config_mgmt.ConfigMgmtDPB.breakOutPort(
                cmdpb, delPorts=delPorts, portJson={'PORT': {}})

    def test_a_missing_oid_writes_nothing(self):
        cmdpb = self._engine()

        deps, ret = self._run(cmdpb, ['Ethernet0', 'Ethernet1'],
                              {'Ethernet0': '1000'})

        assert ret is False
        assert deps is None
        cmdpb._shutdownIntf.assert_not_called()
        cmdpb.writeConfigDB.assert_not_called()
        cmdpb._verifyAsicDB.assert_not_called()

    def test_an_empty_oid_map_writes_nothing(self):
        cmdpb = self._engine()

        deps, ret = self._run(cmdpb, ['Ethernet0'], {})

        assert ret is False
        cmdpb._shutdownIntf.assert_not_called()
        cmdpb.writeConfigDB.assert_not_called()

    def test_a_complete_oid_map_proceeds_to_the_wait(self):
        cmdpb = self._engine()

        deps, ret = self._run(cmdpb, ['Ethernet0', 'Ethernet1'],
                              {'Ethernet0': '1000', 'Ethernet1': '1001'})

        assert ret is True
        cmdpb._shutdownIntf.assert_called_once_with(['Ethernet0', 'Ethernet1'])
        cmdpb._verifyAsicDB.assert_called_once()
        # Delete is written before the wait, add only after it.
        assert cmdpb.writeConfigDB.call_count == 2

    def test_an_unrelated_port_without_an_oid_is_not_blamed(self):
        """Only the ports being deleted need to be watchable."""
        cmdpb = self._engine()

        deps, ret = self._run(cmdpb, ['Ethernet0'],
                              {'Ethernet0': '1000', 'Ethernet8': '1008'})

        assert ret is True
        cmdpb._verifyAsicDB.assert_called_once()

    def test_the_failure_names_every_port_without_an_oid(self):
        cmdpb = self._engine()
        logged = []
        cmdpb.sysLog.side_effect = \
            lambda *a, **kw: logged.append(str(kw.get('msg', '')))

        self._run(cmdpb, ['Ethernet2', 'Ethernet0', 'Ethernet1'],
                  {'Ethernet1': '1001'})

        blamed = [msg for msg in logged if 'No ASIC DB OID' in msg]
        assert blamed, 'the refusal was never logged'
        assert 'Ethernet0' in blamed[0] and 'Ethernet2' in blamed[0]
        assert 'Ethernet1' not in blamed[0]

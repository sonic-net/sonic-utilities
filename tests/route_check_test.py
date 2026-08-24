import copy
from io import BytesIO, StringIO
import json
import logging
import os
import shlex
import signal
import subprocess
import syslog
import sys
import threading
import time
from sonic_py_common import device_info
from unittest.mock import MagicMock, patch
from tests.route_check_test_data import (
    APPL_DB, MULTI_ASIC, NAMESPACE, DEFAULTNS, ARGS, ASIC_DB, CONFIG_DB,
    DEFAULT_CONFIG_DB, APPL_STATE_DB, OP_DEL, OP_SET, PRE, RESULT, RET, TEST_DATA,
    UPD, FRR_ROUTES
)

import pytest

logger = logging.getLogger(__name__)

sys.path.append("scripts")
import route_check  # noqa: E402

current_test_data = None
selector_returned = None
subscribers_returned = {}
db_conns = {}


def set_test_case_data(ctdata):
    global current_test_data, db_conns, selector_returned, subscribers_returned
    current_test_data = ctdata
    selector_returned = None
    subscribers_returned = {}


def recursive_update(d, t):
    assert type(t) is dict
    for k in t.keys():
        if type(t[k]) is not dict:
            d.update(t)
            return
        if k not in d:
            d[k] = {}
        recursive_update(d[k], t[k])


class Table:
    def __init__(self, db, tbl):
        self.db = db
        self.tbl = tbl
        self.data = copy.deepcopy(self.get_val(current_test_data[PRE], [db["namespace"], db["name"], tbl]))

    def update(self):
        t = copy.deepcopy(self.get_val(current_test_data.get(UPD, {}),
                          [self.db["namespace"],
                          self.db["name"],
                          self.tbl, OP_SET]))
        drop = copy.deepcopy(self.get_val(current_test_data.get(UPD, {}),
                             [self.db["namespace"],
                             self.db["name"],
                             self.tbl, OP_DEL]))
        if t:
            recursive_update(self.data, t)

        for k in drop:
            self.data.pop(k, None)
        return (list(t.keys()), list(drop.keys()))

    def get_val(self, d, keys):
        for k in keys:
            d = d[k] if k in d else {}
        return d

    def getKeys(self):
        return list(self.data.keys())

    def get(self, key):
        ret = copy.deepcopy(self.data.get(key, {}))
        return (True, ret)

    def hget(self, key, field):
        ret = copy.deepcopy(self.data.get(key, {}).get(field, {}))
        return True, ret


def conn_side_effect(arg, _1, _2, namespace):
    return db_conns[namespace][arg]


def init_db_conns(namespaces):
    for ns in namespaces:
        db_conns[ns] = {
            "APPL_DB": {"namespace": ns, "name": APPL_DB},
            "ASIC_DB": {"namespace": ns, "name": ASIC_DB},
            "APPL_STATE_DB": {"namespace": ns, "name": APPL_STATE_DB},
            "CONFIG_DB": ConfigDB(ns)
            }


def table_side_effect(db, tbl):
    if tbl not in db.keys():
        db[tbl] = Table(db, tbl)
    return db[tbl]


class MockSelector:
    TIMEOUT = 1
    EMULATE_HANG = False

    def __init__(self):
        self.select_state = 0
        self.select_cnt = 0
        self.subs = None
        logger.debug("Mock Selector constructed")

    def addSelectable(self, subs):
        self.subs = subs
        return 0

    def select(self, timeout):
        # Toggle between good & timeout
        #
        state = self.select_state
        self.subs.update()

        if MockSelector.EMULATE_HANG:
            time.sleep(60)

        if self.select_state == 0:
            self.select_state = self.TIMEOUT
        else:
            time.sleep(timeout)

        return (state, None)


class MockSubscriber:
    def __init__(self, db, tbl):
        self.state = PRE
        self.db = db
        self.tbl = tbl
        self.mock_tbl = table_side_effect(self.db, self.tbl)
        self.set_keys = list(self.mock_tbl.data.keys())
        self.del_keys = []

    def update(self):
        if self.state == PRE:
            s_keys, d_keys = self.mock_tbl.update()
            self.set_keys += s_keys
            self.del_keys += d_keys
            self.state = UPD

    def pop(self):
        v = None
        if self.set_keys:
            op = OP_SET
            k = self.set_keys.pop(0)
            v = self.mock_tbl.get(k)[1]
        elif self.del_keys:
            op = OP_DEL
            k = self.del_keys.pop(0)
        else:
            k = ""
            op = ""

        return (k, op, v)


def subscriber_side_effect(db, tbl):
    global subscribers_returned
    key = "db_{}_{}_tbl_{}".format(db["namespace"], db["name"], tbl)
    if key not in subscribers_returned:
        subscribers_returned[key] = MockSubscriber(db, tbl)
    return subscribers_returned[key]


def select_side_effect():
    global selector_returned

    if not selector_returned:
        selector_returned = MockSelector()
    return selector_returned


def config_db_side_effect(namespace):
    return db_conns[namespace]["CONFIG_DB"]


class ConfigDB:
    def __init__(self, namespace):
        self.namespace = namespace
        self.name = CONFIG_DB
        self.db = current_test_data.get(PRE, {}).get(namespace, {}).get(CONFIG_DB, DEFAULT_CONFIG_DB) if current_test_data is not None else DEFAULT_CONFIG_DB

    def get_table(self, table):
        return self.db.get(table, {})

    def get_entry(self, table, key):
        return self.get_table(table).get(key, {})


def set_mock(mock_table, mock_conn, mock_sel, mock_subs, mock_config_db):
    mock_conn.side_effect = conn_side_effect
    mock_table.side_effect = table_side_effect
    mock_sel.side_effect = select_side_effect
    mock_subs.side_effect = subscriber_side_effect
    mock_config_db.side_effect = config_db_side_effect


class TestRouteCheck(object):
    def setup_method(self):
        pass

    def init(self):
        route_check.UNIT_TESTING = 1
        route_check.FRR_WAIT_TIME = 0

    @pytest.fixture
    def force_hang(self):
        old_timeout = route_check.TIMEOUT_SECONDS
        route_check.TIMEOUT_SECONDS = 5
        MockSelector.EMULATE_HANG = True

        yield

        route_check.TIMEOUT_SECONDS = old_timeout
        MockSelector.EMULATE_HANG = False

    @pytest.fixture
    def mock_dbs(self):
        with patch("route_check.swsscommon.DBConnector") as mock_conn, \
             patch("route_check.swsscommon.Table") as mock_table, \
             patch("route_check.swsscommon.Select") as mock_sel, \
             patch("route_check.swsscommon.SubscriberStateTable") as mock_subs, \
             patch("sonic_py_common.multi_asic.connect_config_db_for_ns") as mock_config_db, \
             patch("route_check.swsscommon.NotificationProducer"), \
             patch.object(device_info, 'get_platform', return_value='unittest'):
            set_mock(mock_table, mock_conn, mock_sel, mock_subs, mock_config_db)
            yield

    @pytest.mark.parametrize("test_num", TEST_DATA.keys())
    def test_route_check(self, mock_dbs, test_num):
        logger.debug("test_route_check: test_num={}".format(test_num))
        self.init()
        ct_data = TEST_DATA[test_num]
        set_test_case_data(ct_data)
        self.run_test(ct_data)

    def run_test(self, ct_data):
        with patch('sys.argv', ct_data[ARGS].split()), \
            patch('sonic_py_common.multi_asic.get_namespace_list', return_value=ct_data[NAMESPACE]), \
            patch('sonic_py_common.multi_asic.is_multi_asic', return_value=ct_data[MULTI_ASIC]), \
            patch('route_check.check_frr_pending_routes',
                  side_effect=lambda *args, **kwargs:
                  self.mock_fetch_routes(ct_data, *args, **kwargs)), \
            patch('route_check.mitigate_installed_not_offloaded_frr_routes',
                  side_effect=lambda *args, **kwargs: None), \
            patch('route_check.load_db_config',
                  side_effect=lambda: init_db_conns(ct_data[NAMESPACE])):

            ret, res = route_check.main()
            self.assert_results(ct_data, ret, res)

    def mock_fetch_routes(self, ct_data, *args, **kwargs):
        ns = args[0]
        routes = ct_data.get(FRR_ROUTES, {}).get(ns, {})
        if not routes:
            return [], []  # Return tuple of (missed_routes, failed_routes)
        missed_route_list = []
        failed_route_list = []
        for r, v in routes.items():
            for e in v:
                if e.get('protocol') in ('connected', 'kernel', 'static'):
                    continue
                if e.get('vrfName') != 'default':
                    continue
                if not e.get('selected', False):
                    continue
                if not e.get('offloaded', False):
                    missed_route_list.append({'prefix': r, 'protocol': e.get('protocol', '')})
                if e.get('failed', False):
                    failed_route_list.append(r)
        return missed_route_list, failed_route_list  # Return tuple of (missed_routes, failed_routes)

    def assert_results(self, ct_data, ret, res):
        expect_ret = ct_data.get(RET, 0)
        expect_res = ct_data.get(RESULT, None)

        if res:
            logger.debug("res={}".format(json.dumps(res, indent=4)))
        if expect_res:
            logger.debug("expect_res={}".format(json.dumps(expect_res, indent=4)))

        assert ret == expect_ret
        assert res == expect_res

    def test_timeout(self, mock_dbs, force_hang):
        # Test timeout
        ex_raised = False
        # Use an expected failing test case to trigger the select
        ct_data = TEST_DATA['2']
        set_test_case_data(ct_data)
        try:
            with patch('sys.argv', [route_check.__file__.split('/')[-1]]), \
                 patch('route_check.load_db_config',
                       side_effect=lambda: init_db_conns(ct_data[NAMESPACE])):

                ret, res = route_check.main()

        except Exception as err:
            ex_raised = True
            expect = "timeout occurred"
            ex_str = str(err)
            assert ex_str == expect, "{} != {}".format(ex_str, expect)
        assert ex_raised, "Exception expected"

    def test_logging(self):
        # Test print_msg
        route_check.PRINT_MSG_LEN_MAX = 5
        msg = route_check.print_message(syslog.LOG_ERR, "abcdefghi")
        assert len(msg) == 5
        msg = route_check.print_message(syslog.LOG_ERR, "ab")
        assert len(msg) == 2
        msg = route_check.print_message(syslog.LOG_ERR, "abcde")
        assert len(msg) == 5
        msg = route_check.print_message(syslog.LOG_ERR, "a", "b", "c", "d", "e", "f")
        assert len(msg) == 5

    def test_mitigate_routes(self, mock_dbs):
        namespace = DEFAULTNS
        missed_frr_rt = [{'prefix': '192.168.0.1', 'protocol': 'bgp'}]
        rt_appl = ['192.168.0.1']
        init_db_conns([namespace])
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            route_check.mitigate_installed_not_offloaded_frr_routes(namespace, missed_frr_rt, rt_appl)
        # Verify that the stdout are suppressed in this function
        assert not mock_stdout.getvalue()


# fetch_routes runs "sudo vtysh", and /usr/bin/vtysh is a wrapper that runs
# "docker exec -i bgp vtysh ...". The process holding the exec session into
# the bgp container is a grandchild of what Popen returns, and it is the one
# left blocked in write() when a parse is abandoned - out of reach of
# proc.kill(), but not of closing the read end. The fakes below reproduce
# that shape without docker: the process that floods the pipe is a
# grandchild, not the direct child.
GOOD_ROUTES = {
    "10.0.0.0/24": [{"protocol": "bgp", "vrfName": "default", "selected": True, "offloaded": False}],
    "10.0.1.0/24": [{"protocol": "bgp", "vrfName": "default", "selected": True,
                     "offloaded": True, "failed": True}],
    "10.0.2.0/24": [{"protocol": "connected", "vrfName": "default", "selected": True}],
}

# Emits a truncated JSON object so ijson raises, then floods stdout from a
# grandchild so it blocks in write() once the 64KB pipe fills up.
FLOOD_MARKER = "ROUTE_CHECK_TEST_FLOOD"

# fetch_routes must not take anywhere near this long; it is only here so a
# regression shows up as a failure instead of hanging the test run forever.
FETCH_TIMEOUT_SECONDS = 60


def _proc_readable():
    """/proc must be usable or the liveness checks below silently pass."""
    try:
        with open('/proc/self/stat'):
            return True
    except OSError:
        return False


def _pid_running(pid):
    """True only while pid exists and has not become a zombie."""
    try:
        with open('/proc/{}/stat'.format(pid)) as f:
            state = f.read().rsplit(')', 1)[1].split()[0]
    except OSError:
        return False
    return state != 'Z'


def _wait_until(predicate, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return predicate()


def _wait_until_gone(pid, timeout=10):
    return _wait_until(lambda: not _pid_running(pid), timeout)


def _pid_exists(pid):
    """True while pid is in the process table at all, zombies included.

    _pid_running() deliberately forgives a zombie, so it cannot see a child
    that died but was never reaped. This one can.
    """
    return os.path.exists('/proc/{}'.format(pid))


def _wait_until_reaped(pid, timeout=10):
    return _wait_until(lambda: not _pid_exists(pid), timeout)


@pytest.mark.skipif(not _proc_readable(),
                    reason="needs a readable /proc to prove the chain is gone")
class TestFetchRoutesCleanup(object):
    """fetch_routes must never leave the vtysh / docker exec chain behind."""

    @staticmethod
    def _fake_popen(fake_cmd, captured):
        """Run fake_cmd instead of vtysh, keeping real pipe semantics."""
        real_popen = subprocess.Popen

        def _popen(cmd, **kwargs):
            proc = real_popen(fake_cmd, **kwargs)
            captured['pid'] = proc.pid
            captured['kwargs'] = kwargs
            return proc
        return _popen

    @staticmethod
    def _flooding_cmd(pidfile):
        """A three level chain whose deepest process floods the pipe.

        The grandchild is the stand-in for the docker exec client: it is the
        one blocked in write(), and closing the read end is what has to reach
        it. It records its own pid before emitting anything, so the file is
        always in place by the time the parse fails and cleanup runs. Writing
        it from the parent after the fork loses that race. exec keeps the pid,
        so it identifies the flooding process too.
        """
        tmp = shlex.quote(str(pidfile) + '.tmp')
        final = shlex.quote(str(pidfile))
        inner = ("echo $$ > " + tmp + "; mv " + tmp + " " + final
                 + "; printf '%s' '{\"10.0.0.0/24\": zzz'; exec yes " + FLOOD_MARKER)
        return ['sh', '-c', 'sh -c ' + shlex.quote(inner) + ' & wait']

    @staticmethod
    def _writer_cmd():
        """Emits a JSON object then keeps writing, like vtysh with more to send.

        It has to keep writing: closing the read end only releases a process
        that goes on to write. A sleeper would sit there untouched until the
        bounded wait expired, which is a different code path.
        """
        return ['sh', '-c', "printf '%s' '{}'; exec yes " + FLOOD_MARKER]

    @staticmethod
    def _reap(*pids):
        """Best effort cleanup so a failing assertion does not leak the chain.

        Never killpg here: fetch_routes no longer starts a new session, so the
        child shares the test runner's process group and killpg would take the
        whole test session down with it.
        """
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except (OSError, TypeError):
                pass

    def _run_fetch_routes(self):
        """Call fetch_routes off the main thread so a deadlock fails the test."""
        outcome = {}

        def run():
            try:
                outcome['result'] = route_check.fetch_routes()
            except BaseException as e:  # noqa: B036, BLE001 - the point is to capture anything
                outcome['exc'] = e

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        thread.join(timeout=FETCH_TIMEOUT_SECONDS)
        assert not thread.is_alive(), \
            "fetch_routes deadlocked: the read end was not closed before waiting"
        return outcome

    def test_releases_whole_process_chain_on_parse_error(self, tmp_path):
        """The regression guard: with wait() before close() this deadlocks."""
        pidfile = tmp_path / 'grandchild.pid'
        captured = {}
        grandchild = None
        cmd = self._flooding_cmd(pidfile)
        try:
            with patch('route_check.subprocess.Popen', side_effect=self._fake_popen(cmd, captured)):
                outcome = self._run_fetch_routes()

            # The parse error itself stays swallowed, as it always was.
            assert 'exc' not in outcome, outcome.get('exc')
            assert outcome['result'] == ([], [])

            # The grandchild is two levels below the process Popen returned, so
            # proc.kill() would never have reached it. Closing the read end does.
            assert _wait_until(pidfile.exists), "the fake chain never recorded its grandchild"
            grandchild = int(pidfile.read_text().strip())
            assert _wait_until_gone(grandchild), \
                "grandchild {} survived: the chain was not released".format(grandchild)
        finally:
            self._reap(captured.get('pid'), grandchild)

    def test_stdout_is_closed_before_wait(self):
        """The whole deadlock was wait() running before the read end was closed.

        Ordering is the fix. Closing afterwards is what the context manager did
        on its own, and it never got there because wait() blocked first.
        """
        events = []
        proc = MagicMock()
        proc.pid = 424242
        proc.stdout.close.side_effect = lambda: events.append('close')
        proc.wait.side_effect = lambda **kwargs: (events.append('wait'), 0)[1]

        with patch('route_check.subprocess.Popen', return_value=proc), \
                patch('route_check.ijson.kvitems', side_effect=ValueError('boom')):
            assert route_check.fetch_routes() == ([], [])

        assert events == ['close', 'wait'], \
            "the read end must be closed before vtysh is waited on"

    @pytest.mark.parametrize("error", [
        UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'invalid start byte'),
        ValueError('something unexpected'),
    ])
    def test_other_parse_errors_take_the_same_cleanup_path(self, error):
        """Every branch that abandons the read has to release the chain."""
        captured = {}
        try:
            with patch('route_check.subprocess.Popen',
                       side_effect=self._fake_popen(self._writer_cmd(), captured)), \
                    patch('route_check.ijson.kvitems', side_effect=error):
                outcome = self._run_fetch_routes()

            assert 'exc' not in outcome, outcome.get('exc')
            assert outcome['result'] == ([], [])
            assert _wait_until_gone(captured['pid']), \
                "vtysh stand-in survived a {}".format(type(error).__name__)
        finally:
            self._reap(captured.get('pid'))

    def test_cleanup_runs_for_non_exception_interrupts(self):
        """KeyboardInterrupt is not an Exception, so a flag would miss it."""
        captured = {}
        try:
            with patch('route_check.subprocess.Popen',
                       side_effect=self._fake_popen(self._writer_cmd(), captured)), \
                    patch('route_check.ijson.kvitems', side_effect=KeyboardInterrupt):
                outcome = self._run_fetch_routes()

            assert isinstance(outcome.get('exc'), KeyboardInterrupt), \
                "KeyboardInterrupt must still propagate"
            assert _wait_until_gone(captured['pid']), \
                "the chain outlived a KeyboardInterrupt"
            assert _wait_until_reaped(captured['pid']), \
                "child {} left unreaped: the bounded wait was skipped".format(captured['pid'])
        finally:
            self._reap(captured.get('pid'))

    def test_child_is_reaped_when_keyboard_interrupt_propagates(self):
        """An interrupt must not skip the wait and leave the child a zombie.

        KeyboardInterrupt is not an Exception, so it leaves the parse through
        the finally and would skip anything placed after it. The process level
        test above cannot see the difference on its own, because _pid_running()
        reports a zombie as gone.
        """
        events = []
        proc = MagicMock()
        proc.pid = 424242
        proc.stdout.close.side_effect = lambda: events.append('close')
        proc.wait.side_effect = lambda **kwargs: (events.append('wait'), 0)[1]

        with patch('route_check.subprocess.Popen', return_value=proc), \
                patch('route_check.ijson.kvitems', side_effect=KeyboardInterrupt), \
                pytest.raises(KeyboardInterrupt):
            route_check.fetch_routes()

        assert events == ['close', 'wait'], \
            "the interrupt must not skip closing the pipe and reaping the child"

    def test_clean_parse_returns_parsed_routes(self):
        """The happy path must be untouched by the cleanup change."""
        captured = {}
        cmd = ['sh', '-c', "printf '%s' " + shlex.quote(json.dumps(GOOD_ROUTES))]
        with patch('route_check.subprocess.Popen', side_effect=self._fake_popen(cmd, captured)), \
                patch('route_check.print_message') as mock_msg:
            outcome = self._run_fetch_routes()

        assert 'exc' not in outcome, outcome.get('exc')
        missing, failing = outcome['result']
        assert missing == [{'prefix': '10.0.0.0/24', 'protocol': 'bgp'}]
        assert failing == ['10.0.1.0/24']
        assert not any('non-zero return code' in str(c) for c in mock_msg.call_args_list)

    def test_non_zero_exit_is_reported_after_a_clean_parse(self):
        """A real vtysh failure must survive the SIGPIPE suppression."""
        captured = {}
        cmd = ['sh', '-c', "printf '%s' " + shlex.quote(json.dumps(GOOD_ROUTES)) + "; exit 3"]
        with patch('route_check.subprocess.Popen', side_effect=self._fake_popen(cmd, captured)), \
                patch('route_check.print_message') as mock_msg:
            outcome = self._run_fetch_routes()

        assert 'exc' not in outcome, outcome.get('exc')
        missing, failing = outcome['result']
        assert missing == [{'prefix': '10.0.0.0/24', 'protocol': 'bgp'}]
        assert any('non-zero return code: 3' in str(c) for c in mock_msg.call_args_list)

    def test_sigpipe_from_our_own_close_is_not_reported_as_a_crash(self):
        """Closing the read end kills vtysh with SIGPIPE; sudo reports 141.

        That exit code is this function's own doing, so reporting it would send
        a misleading warning to syslog on every parse failure.
        """
        captured = {}
        try:
            with patch('route_check.subprocess.Popen',
                       side_effect=self._fake_popen(self._writer_cmd(), captured)), \
                    patch('route_check.ijson.kvitems', side_effect=ValueError('boom')), \
                    patch('route_check.print_message') as mock_msg:
                outcome = self._run_fetch_routes()

            assert 'exc' not in outcome, outcome.get('exc')
            assert not any('non-zero return code' in str(c) for c in mock_msg.call_args_list)
        finally:
            self._reap(captured.get('pid'))

    def test_process_that_never_exits_is_killed_then_abandoned(self):
        """Closing only releases a writer; one hung without writing needs the signal.

        Walking away would leak a child on every timeout, and route_check runs
        on a timer. It still must not block: fetch_routes runs on a worker
        thread the SIGALRM watchdog cannot interrupt, so both waits are bounded.
        """
        proc = MagicMock()
        proc.pid = 424242
        proc.stdout = BytesIO(json.dumps(GOOD_ROUTES).encode())
        proc.wait.side_effect = subprocess.TimeoutExpired(
            cmd='vtysh', timeout=route_check.VTYSH_EXIT_TIMEOUT_SECONDS)

        with patch('route_check.subprocess.Popen', return_value=proc), \
                patch('route_check.print_message') as mock_msg:
            missing, failing = route_check.fetch_routes()

        # Whatever was parsed before the hang still comes back.
        assert missing == [{'prefix': '10.0.0.0/24', 'protocol': 'bgp'}]
        assert failing == ['10.0.1.0/24']
        proc.kill.assert_called_once_with()
        assert any('did not exit; killing the direct child' in str(c)
                   for c in mock_msg.call_args_list)
        assert any('survived SIGKILL' in str(c) for c in mock_msg.call_args_list)

    def test_kill_after_timeout_reaps_without_reporting_a_crash(self):
        """The -9 from our own SIGKILL must not surface as a vtysh failure.

        A real non-zero exit still has to be reported, so the suppression has
        to come from not recording our own exit code rather than from a blanket
        rule.
        """
        proc = MagicMock()
        proc.pid = 424242
        proc.stdout = BytesIO(json.dumps(GOOD_ROUTES).encode())
        proc.wait.side_effect = [
            subprocess.TimeoutExpired(cmd='vtysh', timeout=route_check.VTYSH_EXIT_TIMEOUT_SECONDS),
            -9,
        ]

        with patch('route_check.subprocess.Popen', return_value=proc), \
                patch('route_check.print_message') as mock_msg:
            missing, failing = route_check.fetch_routes()

        assert missing == [{'prefix': '10.0.0.0/24', 'protocol': 'bgp'}]
        proc.kill.assert_called_once_with()
        assert not any('survived SIGKILL' in str(c) for c in mock_msg.call_args_list)
        assert not any('non-zero return code' in str(c) for c in mock_msg.call_args_list)

    def test_unexpected_route_entry_format_is_reported(self):
        """FRR should never emit this, but the guard must still be exercised."""
        captured = {}
        payload = json.dumps({"10.0.0.0/24": "not-a-list"})
        cmd = ['sh', '-c', "printf '%s' " + shlex.quote(payload)]
        with patch('route_check.subprocess.Popen', side_effect=self._fake_popen(cmd, captured)), \
                patch('route_check.print_message') as mock_msg:
            outcome = self._run_fetch_routes()

        assert 'exc' not in outcome, outcome.get('exc')
        assert outcome['result'] == ([], [])
        assert any('Unexpected route entry format' in str(c) for c in mock_msg.call_args_list)

    def test_does_not_start_a_new_session(self):
        """Nothing needs the child detached now that cleanup is a close().

        Leaving it in our session keeps a terminal SIGINT reaching vtysh on its
        own, and keeps the test helpers from having to reason about groups.
        """
        captured = {}
        cmd = ['sh', '-c', "printf '%s' " + shlex.quote(json.dumps(GOOD_ROUTES))]
        with patch('route_check.subprocess.Popen', side_effect=self._fake_popen(cmd, captured)):
            self._run_fetch_routes()

        assert 'start_new_session' not in captured['kwargs']

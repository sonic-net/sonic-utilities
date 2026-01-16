import copy
from io import StringIO
import json
import logging
import syslog
import sys
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
    @staticmethod
    def extract_namespace_from_args(args):
        # args: ['show', 'ip', 'route', '-n', 'asic0', 'json'],
        for i, arg in enumerate(args):
            if arg == "-n" and i + 1 < len(args):
                return args[i + 1]
        return DEFAULTNS

    def setup(self):
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
             patch("route_check.swsscommon.NotificationProducer"):
            device_info.get_platform = MagicMock(return_value='unittest')
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
            patch('route_check.subprocess.check_output', side_effect=lambda *args, **kwargs: self.mock_check_output(ct_data, *args, **kwargs)), \
            patch('route_check.check_frr_pending_routes',
                  side_effect=lambda *args, **kwargs:
                  self.mock_fetch_routes(ct_data, *args, **kwargs)), \
            patch('route_check.mitigate_installed_not_offloaded_frr_routes',
                  side_effect=lambda *args, **kwargs: None), \
            patch('route_check.load_db_config',
                  side_effect=lambda: init_db_conns(ct_data[NAMESPACE])):

            ret, res = route_check.main()
            self.assert_results(ct_data, ret, res)

    def mock_check_output(self, ct_data, *args, **kwargs):
        ns = self.extract_namespace_from_args(args[0])
        routes = ct_data.get(FRR_ROUTES, {}).get(ns, {})
        return json.dumps(routes)

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
                    missed_route_list.append(r)
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

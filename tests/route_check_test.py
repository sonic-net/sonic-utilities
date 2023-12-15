import copy
from io import StringIO
import json
import os
import logging
import sys
import syslog
import time
from sonic_py_common import device_info
from unittest.mock import MagicMock, patch
from tests.route_check_test_data import APPL_DB, ARGS, ASIC_DB, CONFIG_DB, DEFAULT_CONFIG_DB, APPL_STATE_DB, DESCR, OP_DEL, OP_SET, PRE, RESULT, RET, TEST_DATA, UPD, FRR_ROUTES

import pytest

logger = logging.getLogger(__name__)

sys.path.append("scripts")
import route_check

current_test_data = None

tables_returned = {}
selector_returned = None
subscribers_returned = {}

def set_test_case_data(ctdata):
    """
    Setup global variables for each test case
    """
    global current_test_data, tables_returned, selector_returned, subscribers_returned

    current_test_data = ctdata
    tables_returned = {}

    selector_returned = None
    subscribers_returned = {}


def recursive_update(d, t):
    assert (type(t) is dict)
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
        self.data = copy.deepcopy(self.get_val(current_test_data[PRE], [db, tbl]))
        # print("Table:init: db={} tbl={} data={}".format(db, tbl, json.dumps(self.data, indent=4)))


    def update(self):
        t = copy.deepcopy(self.get_val(current_test_data.get(UPD, {}),
            [self.db, self.tbl, OP_SET]))
        drop = copy.deepcopy(self.get_val(current_test_data.get(UPD, {}),
                        [self.db, self.tbl, OP_DEL]))
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


db_conns = {"APPL_DB": APPL_DB, "ASIC_DB": ASIC_DB, "APPL_STATE_DB": APPL_STATE_DB }
def conn_side_effect(arg, _):
    return db_conns[arg]


def table_side_effect(db, tbl):
    if not db in tables_returned:
        tables_returned[db] = {}
    if not tbl in tables_returned[db]:
        tables_returned[db][tbl] = Table(db, tbl)
    return tables_returned[db][tbl]


class mock_selector:
    TIMEOUT = 1
    EMULATE_HANG = False

    def __init__(self):
        self.select_state = 0
        self.select_cnt = 0
        self.subs = None
        # print("Mock Selector constructed")


    def addSelectable(self, subs):
        self.subs = subs
        return 0


    def select(self, timeout):
        # Toggle between good & timeout
        #
        state = self.select_state
        self.subs.update()

        if mock_selector.EMULATE_HANG:
            time.sleep(60)

        if self.select_state == 0:
            self.select_state = self.TIMEOUT
        else:
            time.sleep(timeout)

        return (state, None)


class mock_db_conn:
    def __init__(self, db):
        self.db_name = None
        for (k, v) in db_conns.items():
            if v == db:
                self.db_name = k
        assert self.db_name != None

    def getDbName(self):
        return self.db_name


class mock_subscriber:
    def __init__(self, db, tbl):
        self.state = PRE
        self.db = db
        self.tbl = tbl
        self.dbconn = mock_db_conn(db)
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

        print("state={} k={} op={} v={}".format(self.state, k, op, str(v)))
        return (k, op, v)
   

    def getDbConnector(self):
        return self.dbconn


    def getTableName(self):
        return self.tbl


def subscriber_side_effect(db, tbl):
    global subscribers_returned

    key = "db_{}_tbl_{}".format(db, tbl)
    if not key in subscribers_returned:
        subscribers_returned[key] = mock_subscriber(db, tbl)
    return subscribers_returned[key]


def select_side_effect():
    global selector_returned

    if not selector_returned:
        selector_returned = mock_selector()
    return selector_returned


def table_side_effect(db, tbl):
    if not db in tables_returned:
        tables_returned[db] = {}
    if not tbl in tables_returned[db]:
        tables_returned[db][tbl] = Table(db, tbl)
    return tables_returned[db][tbl]


def config_db_side_effect(table):
    if CONFIG_DB not in current_test_data[PRE]:
        return DEFAULT_CONFIG_DB[table]
    if not CONFIG_DB in tables_returned:
        tables_returned[CONFIG_DB] = {}
    if not table in tables_returned[CONFIG_DB]:
        tables_returned[CONFIG_DB][table] = current_test_data[PRE][CONFIG_DB].get(table, {})
    return tables_returned[CONFIG_DB][table]


def set_mock(mock_table, mock_conn, mock_sel, mock_subs, mock_config_db):
    mock_conn.side_effect = conn_side_effect
    mock_table.side_effect = table_side_effect
    mock_sel.side_effect = select_side_effect
    mock_subs.side_effect = subscriber_side_effect
    mock_config_db.get_table = MagicMock(side_effect=config_db_side_effect)

class TestRouteCheck(object):
    def setup(self):
        pass

    def init(self):
        route_check.UNIT_TESTING = 1
        route_check.FRR_WAIT_TIME = 0

    @pytest.fixture
    def force_hang(self):
        old_timeout = route_check.TIMEOUT_SECONDS
        route_check.TIMEOUT_SECONDS = 5
        mock_selector.EMULATE_HANG = True

        yield

        route_check.TIMEOUT_SECONDS = old_timeout
        mock_selector.EMULATE_HANG = False

    @pytest.fixture
    def mock_dbs(self):
        mock_config_db = MagicMock()
        with patch("route_check.swsscommon.DBConnector") as mock_conn, \
             patch("route_check.swsscommon.Table") as mock_table, \
             patch("route_check.swsscommon.Select") as mock_sel, \
             patch("route_check.swsscommon.SubscriberStateTable") as mock_subs, \
             patch("route_check.swsscommon.ConfigDBConnector", return_value=mock_config_db), \
             patch("route_check.swsscommon.NotificationProducer"):
            device_info.get_platform = MagicMock(return_value='unittest')
            set_mock(mock_table, mock_conn, mock_sel, mock_subs, mock_config_db)
            yield

    @pytest.mark.parametrize("test_num", TEST_DATA.keys())
    def test_route_check(self, mock_dbs, test_num):
        self.init()
        ret = 0

        ct_data = TEST_DATA[test_num]
        set_test_case_data(ct_data)
        logger.info("Running test case {}: {}".format(test_num, ct_data[DESCR]))

        with patch('sys.argv', ct_data[ARGS].split()), \
            patch('route_check.subprocess.check_output') as mock_check_output:

            routes = ct_data.get(FRR_ROUTES, {})

            def side_effect(*args, **kwargs):
                return json.dumps(routes)

            mock_check_output.side_effect = side_effect

            ret, res = route_check.main()
            expect_ret = ct_data[RET] if RET in ct_data else 0
            expect_res = ct_data[RESULT] if RESULT in ct_data else None
            if res:
                print("res={}".format(json.dumps(res, indent=4)))
            if expect_res:
                print("expect_res={}".format(json.dumps(expect_res, indent=4)))
            assert ret == expect_ret
            assert res == expect_res

    def test_timeout(self, mock_dbs, force_hang):
        # Test timeout
        ex_raised = False
        # Use an expected failing test case to trigger the select
        set_test_case_data(TEST_DATA['2'])

        try:
            with patch('sys.argv', [route_check.__file__.split('/')[-1]]):
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
        missed_frr_rt = [ { 'prefix': '192.168.0.1', 'protocol': 'bgp' } ]
        rt_appl = [ '192.168.0.1' ]
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
           route_check.mitigate_installed_not_offloaded_frr_routes(missed_frr_rt, rt_appl)
        # Verify that the stdout are suppressed in this function
        assert not mock_stdout.getvalue()

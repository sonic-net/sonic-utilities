import json
import os
import sys
from io import StringIO
from unittest import mock

from utilities_common.general import load_module_from_source

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, modules_path)

# Load the file under test
aclshow_path = os.path.join(scripts_path, 'aclshow')
aclshow = load_module_from_source('aclshow', aclshow_path)

from .mock_tables import dbconnector


# Expected output for aclshow
default_output = """\
RULE NAME     TABLE NAME      PRIO    PACKETS COUNT    BYTES COUNT
------------  ------------  ------  ---------------  -------------
RULE_1        DATAACL         9999              101            100
RULE_2        DATAACL         9998              201            200
RULE_3        DATAACL         9997              301            300
RULE_4        DATAACL         9996              401            400
RULE_7        DATAACL         9993              701            700
RULE_9        DATAACL         9991              901            900
RULE_10       DATAACL         9989             1001           1000
DEFAULT_RULE  DATAACL            1                2              1
RULE_6        EVERFLOW        9994              601            600
"""

# Expected output for aclshow -a
all_output = '' + \
"""RULE NAME                              TABLE NAME            PRIO  PACKETS COUNT    BYTES COUNT
-------------------------------------  ------------------  ------  ---------------  -------------
RULE_1                                 DATAACL               9999  101              100
RULE_2                                 DATAACL               9998  201              200
RULE_3                                 DATAACL               9997  301              300
RULE_4                                 DATAACL               9996  401              400
RULE_05                                DATAACL               9995  0                0
RULE_7                                 DATAACL               9993  701              700
RULE_9                                 DATAACL               9991  901              900
RULE_10                                DATAACL               9989  1001             1000
DEFAULT_RULE                           DATAACL                  1  2                1
RULE_1                                 DATAACL_5             9999  N/A              N/A
RULE_NO_COUNTER                        DATAACL_NO_COUNTER    9995  N/A              N/A
RULE_6                                 EVERFLOW              9994  601              600
RULE_08                                EVERFLOW              9992  0                0
RULE_1                                 NULL_ROUTE_V4         9999  N/A              N/A
BLOCK_RULE_10.0.0.2/32                 NULL_ROUTE_V4         9999  N/A              N/A
BLOCK_RULE_10.0.0.3/32                 NULL_ROUTE_V4         9999  N/A              N/A
DEFAULT_RULE                           NULL_ROUTE_V4            1  N/A              N/A
RULE_1                                 NULL_ROUTE_V6         9999  N/A              N/A
BLOCK_RULE_1000:1000:1000:1000::2/128  NULL_ROUTE_V6         9999  N/A              N/A
BLOCK_RULE_1000:1000:1000:1000::3/128  NULL_ROUTE_V6         9999  N/A              N/A
DEFAULT_RULE                           NULL_ROUTE_V6            1  N/A              N/A
"""

# Expected output for aclshow -r RULE_1 -t DATAACL
rule1_dataacl_output = """\
RULE NAME    TABLE NAME      PRIO    PACKETS COUNT    BYTES COUNT
-----------  ------------  ------  ---------------  -------------
RULE_1       DATAACL         9999              101            100
"""

# Expected output for aclshow -r RULE_1 -t DATAACL
rule10_dataacl_output = """\
RULE NAME    TABLE NAME      PRIO    PACKETS COUNT    BYTES COUNT
-----------  ------------  ------  ---------------  -------------
RULE_10      DATAACL         9989             1001           1000
"""

# Expected output for aclshow -a -r RULE_05
rule05_all_output = """\
RULE NAME    TABLE NAME      PRIO    PACKETS COUNT    BYTES COUNT
-----------  ------------  ------  ---------------  -------------
RULE_05      DATAACL         9995                0              0
"""

# Expected output for aclshow -r RULE_0
rule0_output = """\
RULE NAME    TABLE NAME    PRIO    PACKETS COUNT    BYTES COUNT
-----------  ------------  ------  ---------------  -------------
"""

# Expected output for aclshow -r RULE_4,RULE_6 -vv
rule4_rule6_verbose_output = '' + \
"""Reading ACL info...
Total number of ACL Tables: 16
Total number of ACL Rules: 21

RULE NAME    TABLE NAME      PRIO    PACKETS COUNT    BYTES COUNT
-----------  ------------  ------  ---------------  -------------
RULE_4       DATAACL         9996              401            400
RULE_6       EVERFLOW        9994              601            600
"""

# Expected output for aclshow -t EVERFLOW
everflow_output = """\
RULE NAME    TABLE NAME      PRIO    PACKETS COUNT    BYTES COUNT
-----------  ------------  ------  ---------------  -------------
RULE_6       EVERFLOW        9994              601            600
"""

# Expected output for aclshow -t DATAACL
dataacl_output = """\
RULE NAME     TABLE NAME      PRIO    PACKETS COUNT    BYTES COUNT
------------  ------------  ------  ---------------  -------------
RULE_1        DATAACL         9999              101            100
RULE_2        DATAACL         9998              201            200
RULE_3        DATAACL         9997              301            300
RULE_4        DATAACL         9996              401            400
RULE_7        DATAACL         9993              701            700
RULE_9        DATAACL         9991              901            900
RULE_10       DATAACL         9989             1001           1000
DEFAULT_RULE  DATAACL            1                2              1
"""

# Expected output for aclshow -c
clear_output = ''

# Expected output for
# aclshow -a -c ; aclshow -a
all_after_clear_output = '' + \
"""RULE NAME                              TABLE NAME            PRIO  PACKETS COUNT    BYTES COUNT
-------------------------------------  ------------------  ------  ---------------  -------------
RULE_1                                 DATAACL               9999  0                0
RULE_2                                 DATAACL               9998  0                0
RULE_3                                 DATAACL               9997  0                0
RULE_4                                 DATAACL               9996  0                0
RULE_05                                DATAACL               9995  0                0
RULE_7                                 DATAACL               9993  0                0
RULE_9                                 DATAACL               9991  0                0
RULE_10                                DATAACL               9989  0                0
DEFAULT_RULE                           DATAACL                  1  0                0
RULE_1                                 DATAACL_5             9999  N/A              N/A
RULE_NO_COUNTER                        DATAACL_NO_COUNTER    9995  N/A              N/A
RULE_6                                 EVERFLOW              9994  0                0
RULE_08                                EVERFLOW              9992  0                0
RULE_1                                 NULL_ROUTE_V4         9999  N/A              N/A
BLOCK_RULE_10.0.0.2/32                 NULL_ROUTE_V4         9999  N/A              N/A
BLOCK_RULE_10.0.0.3/32                 NULL_ROUTE_V4         9999  N/A              N/A
DEFAULT_RULE                           NULL_ROUTE_V4            1  N/A              N/A
RULE_1                                 NULL_ROUTE_V6         9999  N/A              N/A
BLOCK_RULE_1000:1000:1000:1000::2/128  NULL_ROUTE_V6         9999  N/A              N/A
BLOCK_RULE_1000:1000:1000:1000::3/128  NULL_ROUTE_V6         9999  N/A              N/A
DEFAULT_RULE                           NULL_ROUTE_V6            1  N/A              N/A
"""

all_after_clear_and_populate_output = '' + \
"""RULE NAME                              TABLE NAME            PRIO  PACKETS COUNT    BYTES COUNT
-------------------------------------  ------------------  ------  ---------------  -------------
RULE_1                                 DATAACL               9999  0                0
RULE_2                                 DATAACL               9998  0                0
RULE_3                                 DATAACL               9997  0                0
RULE_4                                 DATAACL               9996  0                0
RULE_05                                DATAACL               9995  0                0
RULE_7                                 DATAACL               9993  0                0
RULE_9                                 DATAACL               9991  0                0
RULE_10                                DATAACL               9989  0                0
DEFAULT_RULE                           DATAACL                  1  0                0
RULE_1                                 DATAACL_5             9999  N/A              N/A
RULE_NO_COUNTER                        DATAACL_NO_COUNTER    9995  100              100
RULE_6                                 EVERFLOW              9994  0                0
RULE_08                                EVERFLOW              9992  0                0
RULE_1                                 NULL_ROUTE_V4         9999  N/A              N/A
BLOCK_RULE_10.0.0.2/32                 NULL_ROUTE_V4         9999  N/A              N/A
BLOCK_RULE_10.0.0.3/32                 NULL_ROUTE_V4         9999  N/A              N/A
DEFAULT_RULE                           NULL_ROUTE_V4            1  N/A              N/A
RULE_1                                 NULL_ROUTE_V6         9999  N/A              N/A
BLOCK_RULE_1000:1000:1000:1000::2/128  NULL_ROUTE_V6         9999  N/A              N/A
BLOCK_RULE_1000:1000:1000:1000::3/128  NULL_ROUTE_V6         9999  N/A              N/A
DEFAULT_RULE                           NULL_ROUTE_V6            1  N/A              N/A
"""


class Aclshow():
    def __init__(self, *args, **kwargs):
        """
        nullify_on_start, nullify_on_exit will call nullify_counters()
        before and/or after the test. By default - clear on start and exit.
        """
        self.nullify_on_start, self.nullify_on_exit = args if args else (True, True)
        self.kwargs = kwargs
        self.setUp()
        self.runTest()
        self.tearDown()

    def nullify_counters(self):
        """
        This method is used to empty dumped counters
        if exist in /tmp/.counters_acl.p (by default).
        """
        if os.path.isfile(aclshow.COUNTERS_CACHE):
            with open(aclshow.COUNTERS_CACHE, 'w') as fp:
                json.dump([], fp)

    def runTest(self):
        """
        This method invokes main() from aclshow utility (parametrized by argparse)
        parametrized by mock argparse.
        """
        with mock.patch.object(aclshow.argparse.ArgumentParser,
                               'parse_args',
                               return_value=aclshow.argparse.Namespace(**self.kwargs)):
            aclshow.main()

    def setUp(self):
        if self.nullify_on_start:
            self.nullify_counters()
        self.old_stdout = sys.stdout
        self.result = StringIO()
        sys.stdout = self.result

    def tearDown(self):
        if self.nullify_on_exit:
            self.nullify_counters()
        sys.stdout = self.old_stdout

# aclshow


def test_default():
    test = Aclshow(all=None, clear=None, rules=None, tables=None, verbose=None)
    assert test.result.getvalue() == default_output

# aclshow -a


def test_all():
    test = Aclshow(all=True, clear=None, rules=None, tables=None, verbose=None)
    assert test.result.getvalue() == all_output

# aclshow -r RULE_1 -t DATAACL


def test_rule1_dataacl():
    test = Aclshow(all=None, clear=None, rules='RULE_1', tables='DATAACL', verbose=None)
    assert test.result.getvalue() == rule1_dataacl_output

# aclshow -a -r RULE_05


def test_rule05_all():
    test = Aclshow(all=True, clear=None, rules='RULE_05', tables=None, verbose=None)
    assert test.result.getvalue() == rule05_all_output

# aclshow -r RULE_0


def test_rule0():
    test = Aclshow(all=None, clear=None, rules='RULE_0', tables=None, verbose=None)
    assert test.result.getvalue() == rule0_output

# aclshow -r RULE_10 -t DATAACL


def test_rule10_lowercase_priority():
    test = Aclshow(all=None, clear=None, rules='RULE_10', tables='DATAACL', verbose=None)
    assert test.result.getvalue() == rule10_dataacl_output

# aclshow -r RULE_4,RULE_6 -vv


def test_rule4_rule6_verbose():
    test = Aclshow(all=None, clear=None, rules='RULE_4,RULE_6', tables=None, verbose=True)
    assert test.result.getvalue() == rule4_rule6_verbose_output

# aclshow -t EVERFLOW


def test_everflow():
    test = Aclshow(all=None, clear=None, rules=None, tables='EVERFLOW', verbose=None)
    assert test.result.getvalue() == everflow_output

# aclshow -t DATAACL


def test_dataacl():
    test = Aclshow(all=None, clear=None, rules=None, tables='DATAACL', verbose=None)
    assert test.result.getvalue() == dataacl_output

# aclshow -c


def test_clear():
    test = Aclshow(all=None, clear=True, rules=None, tables=None, verbose=None)
    assert test.result.getvalue() == clear_output

# aclshow -a -c ; aclshow -a


def test_all_after_clear():
    nullify_on_start, nullify_on_exit = True, False
    test = Aclshow(nullify_on_start, nullify_on_exit, all=True, clear=True, rules=None, tables=None, verbose=None)
    assert test.result.getvalue() == clear_output
    nullify_on_start, nullify_on_exit = False, True
    test = Aclshow(nullify_on_start, nullify_on_exit, all=True, clear=False, rules=None, tables=None, verbose=None)
    assert test.result.getvalue() == all_after_clear_output


def test_clear_and_populate_counters_db():
    # No counters yet for DATAACL_NO_COUNTER:RULE_NO_COUNTER
    nullify_on_start, nullify_on_exit = True, False
    test = Aclshow(nullify_on_start, nullify_on_exit, all=True, clear=True, rules=None, tables=None, verbose=None)
    assert test.result.getvalue() == clear_output
    nullify_on_start, nullify_on_exit = False, True

    # Counters populated.
    conn = dbconnector.SonicV2Connector()
    conn.connect(conn.COUNTERS_DB)
    conn.set(conn.COUNTERS_DB, aclshow.COUNTERS + ':oid:0x900000000000b', aclshow.COUNTER_PACKETS_ATTR, '100')
    conn.set(conn.COUNTERS_DB, aclshow.COUNTERS + ':oid:0x900000000000b', aclshow.COUNTER_BYTES_ATTR, '100')

    with mock.patch('aclshow.SonicV2Connector', return_value=conn):
        test = Aclshow(nullify_on_start, nullify_on_exit, all=True, clear=False, rules=None, tables=None, verbose=None)
    assert test.result.getvalue() == all_after_clear_and_populate_output

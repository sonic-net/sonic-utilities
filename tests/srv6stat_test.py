import os
import sys
from io import StringIO
from unittest import mock

from utilities_common.general import load_module_from_source
from .mock_tables import dbconnector

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, modules_path)

srv6stat_path = os.path.join(scripts_path, 'srv6stat')
srv6stat = load_module_from_source('srv6stat', srv6stat_path)


# srv6stat
default_output = """\
MySID             Packets    Bytes
--------------  ---------  -------
1000:2:30::/48        100   102400
2000:2:30::/48        200   204800
"""

specific_sid_output = """\
MySID             Packets    Bytes
--------------  ---------  -------
1000:2:30::/48        100   102400
"""
# srv6stat -c
clear_output = ''

# srv6stat after clear
after_clear_output = """\
MySID             Packets    Bytes
--------------  ---------  -------
1000:2:30::/48          0        0
2000:2:30::/48          0        0
"""

update_after_clear_output = """\
MySID             Packets    Bytes
--------------  ---------  -------
1000:2:30::/48        200     2000
2000:2:30::/48        300     3000
"""


class SRv6StatRunner():
    def __init__(self, delete_cache_on_start=True, clear=None, delete=None, sid=None):
        self.setup(delete_cache_on_start)
        self.result = self.run_srv6stat(clear=clear, delete=delete, sid=sid)

    def get_result(self):
        return self.result

    def setup(self, delete_cache_on_start):
        if delete_cache_on_start:
            self.run_srv6stat(delete=True)

    def run_srv6stat(self, clear=None, delete=None, sid=None):
        old_stdout = sys.stdout
        result = StringIO()
        sys.stdout = result
        with mock.patch.object(srv6stat.argparse.ArgumentParser,
                               'parse_args',
                               return_value=srv6stat.argparse.Namespace(clear=clear, delete=delete, sid=sid)):
            srv6stat.main()
        sys.stdout = old_stdout
        return result.getvalue()


def test_show():
    result = SRv6StatRunner().get_result()
    assert result == default_output


def test_show_specific_sid():
    result = SRv6StatRunner(sid='1000:2:30::/48').get_result()
    assert result == specific_sid_output


def test_clear():
    result = SRv6StatRunner(clear=True).get_result()
    assert result == clear_output

    result = SRv6StatRunner(delete_cache_on_start=False).get_result()
    assert result == after_clear_output


def test_delete_cache():
    SRv6StatRunner(clear=True)
    SRv6StatRunner(delete=True)
    result = SRv6StatRunner().get_result()
    assert result == default_output


def test_clear_and_populate_counters_db():
    SRv6StatRunner(clear=True)
    db = dbconnector.SonicV2Connector()
    db.connect(db.COUNTERS_DB)
    db.set(db.COUNTERS_DB, srv6stat.SRv6Stat.SRV6_COUNTERS_MAP, '1000:2:30::/48', 'oid:0x17000000001000')
    db.set(db.COUNTERS_DB, srv6stat.SRv6Stat.SRV6_COUNTERS_MAP, '2000:2:30::/48', 'oid:0x17000000002000')
    db.set(db.COUNTERS_DB, 'COUNTERS:oid:0x17000000001000', srv6stat.SRv6Stat.COUNTER_PACKETS, '300')
    db.set(db.COUNTERS_DB, 'COUNTERS:oid:0x17000000001000', srv6stat.SRv6Stat.COUNTER_BYTES, '104400')
    db.set(db.COUNTERS_DB, 'COUNTERS:oid:0x17000000002000', srv6stat.SRv6Stat.COUNTER_PACKETS, '500')
    db.set(db.COUNTERS_DB, 'COUNTERS:oid:0x17000000002000', srv6stat.SRv6Stat.COUNTER_BYTES, '207800')
    with mock.patch('utilities_common.srv6stat.SonicV2Connector', return_value=db):
        result = SRv6StatRunner(delete_cache_on_start=False).get_result()
        assert result == update_after_clear_output

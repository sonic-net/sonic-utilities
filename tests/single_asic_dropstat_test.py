import os
import sys
from .utils import get_result_and_return_code

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

dropstat_result = """\
    IFACE    STATE    RX_ERR    RX_DROPS    TX_ERR    TX_DROPS    DEBUG_0    DEBUG_2
---------  -------  --------  ----------  --------  ----------  ---------  ---------
Ethernet0        D        10         100         0           0         80         20
Ethernet4      N/A         0        1000         0           0        800        100
Ethernet8      N/A       100          10         0           0         10          0

          DEVICE    SWITCH_DROPS    lowercase_counter
----------------  --------------  -------------------
sonic_drops_test            1000                    0
"""

dropstat_result_clear_all = """\
    IFACE    STATE    RX_ERR    RX_DROPS    TX_ERR    TX_DROPS    DEBUG_0    DEBUG_2
---------  -------  --------  ----------  --------  ----------  ---------  ---------
Ethernet0        D         0           0         0           0          0          0
Ethernet4      N/A         0           0         0           0          0          0
Ethernet8      N/A         0           0         0           0          0          0

          DEVICE    SWITCH_DROPS    lowercase_counter
----------------  --------------  -------------------
sonic_drops_test               0                    0
"""


class TestMultiAsicDropstat(object):
    @classmethod
    def setup_class(cls):
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "1"
        print("SETUP")

    def test_show_dropcount_and_clear(self):
        os.environ["UTILITIES_UNIT_TESTING_DROPSTAT_CLEAN_CACHE"] = "1"
        return_code, result = get_result_and_return_code([
            'dropstat', '-c', 'show'
        ])
        os.environ.pop("UTILITIES_UNIT_TESTING_DROPSTAT_CLEAN_CACHE")
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert result == dropstat_result
        assert return_code == 0

        return_code, result = get_result_and_return_code([
            'dropstat', '-c', 'clear'
        ])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert result == 'Cleared drop counters\n' and return_code == 0

        return_code, result = get_result_and_return_code([
            'dropstat', '-c', 'show'
        ])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert result == dropstat_result_clear_all and return_code == 0

    @classmethod
    def teardown_class(cls):
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ.pop("UTILITIES_UNIT_TESTING")
        print("TEARDOWN")

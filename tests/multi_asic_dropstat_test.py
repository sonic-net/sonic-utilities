import os
import sys
import shutil
from utils import get_result_and_return_code

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

dropstat_path = "/tmp/dropstat-27"

dropstat_masic_result="""\
       IFACE    STATE    RX_ERR    RX_DROPS    TX_ERR    TX_DROPS    DEBUG_0    DEBUG_2
------------  -------  --------  ----------  --------  ----------  ---------  ---------
   Ethernet0        U         0           0         0           0          0          0
   Ethernet4        U         0           0         0           0          0          0
Ethernet-BP0        U         0        1000         0           0        800        100
Ethernet-BP4        U         0        1000         0           0        800        100

          DEVICE    DEBUG_1
----------------  ---------
sonic_drops_test       1000
"""

class TestMultiAsicDropstat(object):
   @classmethod
   def setup_class(cls):
      if os.path.exists(dropstat_path):
         shutil.rmtree(dropstat_path)
      os.environ["PATH"] += os.pathsep + scripts_path
      os.environ["UTILITIES_UNIT_TESTING"] = "1"
      os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
      print("SETUP")

   def test_show_pg_drop_masic(self):
      return_code, result = get_result_and_return_code([
         'dropstat', '-c', 'show', '-n', 'asic0'
      ])
      print("return_code: {}".format(return_code))
      print("result = {}".format(result))
      assert return_code == 0
      assert result == dropstat_masic_result

   def test_show_pg_drop_masic_invalid_ns(self):
      return_code, result = get_result_and_return_code([
         'dropstat', '-c', 'show', '-n', 'asic5'
      ])
      print("return_code: {}".format(return_code))
      print("result = {}".format(result))
      assert return_code == 1

   @classmethod
   def teardown_class(cls):
      os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
      os.environ['UTILITIES_UNIT_TESTING'] = "0"
      os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
      print("TEARDOWN")

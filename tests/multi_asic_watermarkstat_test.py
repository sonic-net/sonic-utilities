import os
import sys

from wm_input.wm_test_vectors import *
from utils import get_result_and_return_code

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)


class TestWatermarkstatMultiAsic(object):
   @classmethod
   def setup_class(cls):
      os.environ["PATH"] += os.pathsep + scripts_path
      os.environ['UTILITIES_UNIT_TESTING'] = "2"
      os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
      print("SETUP")

   def execute(self, command, expected_code=0, expected_result=None):
      return_code, result = get_result_and_return_code(command)
      print("return_code: {}".format(return_code))
      print("result = {}".format(result))
      assert return_code == expected_code
      if expected_result:
         assert result == expected_result

   def test_show_pg_shared_masic(self):
      self.execute(['watermarkstat', '-t', 'pg_shared', '-n', 'asic1'],
                   expected_result=show_pg_wm_shared_output_masic)

   def test_show_headroom_pool_masic(self):
      self.execute(['watermarkstat', '-t', 'headroom_pool', '-n', 'asic1'],
                   expected_result=show_hdrm_pool_wm_output)

   def test_show_invalid_asic_masic(self):
      self.execute(['watermarkstat', '-t', 'headroom_pool', '-n', 'asic15'],
                   expected_code=1)

   @classmethod
   def teardown_class(cls):
      os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
      os.environ['UTILITIES_UNIT_TESTING'] = "0"
      os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
      print("TEARDOWN")

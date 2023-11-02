import os
import sys

from utils import get_result_and_return_code
from mmuconfig_input.mmuconfig_test_vectors import *
from json import load

root_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(root_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, root_path)
sys.path.insert(0, modules_path)

class TestMmuconfigMultiAsic(object):
   @classmethod
   def setup_class(cls):
      os.environ["PATH"] += os.pathsep + scripts_path
      os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
      os.environ['UTILITIES_UNIT_TESTING'] = "2"
      print("SETUP")

   def executor(self, command, expected_result=None):
      return_code, result = get_result_and_return_code(command)
      print("return_code: {}".format(return_code))
      print("result = {}".format(result))
      assert return_code == 0
      if expected_result:
         assert result == expected_result

   def test_mmu_show_config_one_masic(self):
      self.executor(['mmuconfig', '-l', '-n', 'asic0'], show_mmu_config_one)

   def test_mmu_show_config_all_masic(self):
      self.executor(['mmuconfig', '-l'], show_mmu_config)

   def test_mmu_alpha_config_masic(self):
      self.executor(['mmuconfig', '-p', 'alpha_profile', '-a', '2', '-n', 'asic0'])
      fd = open('/tmp/mmuconfig', 'r')
      cmp_data = load(fd)
      assert cmp_data['alpha_profile']['dynamic_th'] == '2'

   @classmethod
   def teardown_class(cls):
      os.environ['PATH'] = os.pathsep.join(os.environ['PATH'].split(os.pathsep)[:-1])
      os.environ['UTILITIES_UNIT_TESTING'] = "0"
      os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
      if os.path.isfile('/tmp/mmuconfig'):
         os.remove('/tmp/mmuconfig')
      print("TEARDOWN")

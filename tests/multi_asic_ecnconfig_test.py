import os
import sys
from ecn_test import TestEcnConfigBase
from ecn_input.ecn_test_vectors import *

root_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(root_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, root_path)
sys.path.insert(0, modules_path)

class TestEcnConfigMultiAsic(TestEcnConfigBase):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"

    def test_ecn_show_config_all_masic(self):
        self.executor(testData['ecn_show_config_masic'])

    def test_ecn_show_config_all_verbose_masic(self):
        self.executor(testData['test_ecn_show_config_verbose_masic'])

    def test_ecn_show_config_one_masic(self):
        self.executor(testData['test_ecn_show_config_namespace'])

    def test_ecn_show_config_one_verbose_masic(self):
        self.executor(testData['test_ecn_show_config_namespace_verbose'])

    def test_ecn_config_change_other_threshold_masic(self):
        self.executor(testData['ecn_cfg_threshold_masic'])

    def test_ecn_config_change_other_prob_masic(self):
        self.executor(testData['ecn_cfg_probability_masic'])

    @classmethod
    def teardown_class(cls):
        super().teardown_class()
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""

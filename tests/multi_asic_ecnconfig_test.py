import os
import sys
from .ecn_test import TestEcnConfigBase
from .ecn_input.ecn_test_vectors import testData

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

    def test_ecn_config_change_gdrop_verbose_all_masic(self):
        self.executor(testData['ecn_cfg_gdrop_verbose_all_masic'])

    def test_ecn_config_multi_set_verbose_all_masic(self):
        self.executor(testData['ecn_cfg_multi_set_verbose_all_masic'])

    def test_ecn_queue_get_masic(self):
        self.executor(testData['ecn_q_get_masic'])

    def test_ecn_queue_get_verbose_masic(self):
        self.executor(testData['ecn_q_get_verbose_masic'])

    def test_ecn_queue_get_all_masic(self):
        self.executor(testData['ecn_q_get_all_ns_masic'])

    def test_ecn_queue_get_all_verbose_masic(self):
        self.executor(testData['ecn_q_get_all_ns_verbose_masic'])

    def test_ecn_q_set_off_all_masic(self):
        self.executor(testData['ecn_cfg_q_all_ns_off_masic'])

    def test_ecn_q_set_off_one_masic(self):
        self.executor(testData['ecn_cfg_q_one_ns_off_verbose_masic'])

    def test_ecn_queue_set_q_on_voq(self):
        os.environ['UTILITIES_UNIT_TESTING_VOQ'] = "1"
        self.executor(testData['ecn_cfg_q_voq'])
        os.environ['UTILITIES_UNIT_TESTING_VOQ'] = "0"

    @classmethod
    def teardown_class(cls):
        super().teardown_class()
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""

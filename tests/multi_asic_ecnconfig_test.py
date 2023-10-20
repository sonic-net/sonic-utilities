import os

from ecn_test import *

root_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(root_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, root_path)
sys.path.insert(0, modules_path)


class TestEcnConfigMultiAsic(object):
    @classmethod
    def setup_class(cls):
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        print("SETUP")

    def test_ecn_show_config_all_masic(self):
        TestEcnConfig.executor(testData['ecn_show_config_masic'])

    def test_ecn_show_config_all_verbose_masic(self):
        TestEcnConfig.executor(testData['test_ecn_show_config_verbose_masic'])

    def test_ecn_show_config_one_masic(self):
        TestEcnConfig.executor(testData['test_ecn_show_config_namespace'])

    def test_ecn_show_config_one_verbose_masic(self):
        TestEcnConfig.executor(testData['test_ecn_show_config_namespace_verbose'])

    def test_ecn_config_change_other_threshold_masic(self):
        TestEcnConfig.executor(testData['ecn_cfg_threshold_masic'])

    def test_ecn_config_change_other_prob_masic(self):
        TestEcnConfig.executor(testData['ecn_cfg_probability_masic'])

    @classmethod
    def teardown_class(cls):
        os.environ['PATH'] = os.pathsep.join(os.environ['PATH'].split(os.pathsep)[:-1])
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        if os.path.isfile('/tmp/ecnconfig'):
            os.remove('/tmp/ecnconfig')
        print("TEARDOWN")

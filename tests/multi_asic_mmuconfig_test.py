import os
import sys
from .mmuconfig_test import TestMmuConfigBase
from .mmuconfig_input.mmuconfig_test_vectors import testData

root_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(root_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, root_path)
sys.path.insert(0, modules_path)


class TestMmuConfigMultiAsic(TestMmuConfigBase):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"

    def test_mmu_show_config_one_masic(self):
        self.executor(testData['mmu_cfg_list_one_masic'])

    def test_mmu_show_config_one_verbose_masic(self):
        self.executor(testData['mmu_cfg_list_one_verbose_masic'])

    def test_mmu_show_config_all_masic(self):
        self.executor(testData['mmu_cfg_list_all_masic'])

    def test_mmu_alpha_config_one_masic(self):
        self.executor(testData['mmu_cfg_alpha_one_masic'])

    def test_mmu_alpha_config_all_verbose_masic(self):
        self.executor(testData['mmu_cfg_alpha_all_verbose_masic'])

    def test_mmu_staticth_config_one_masic(self):
        self.executor(testData['mmu_cfg_static_th_one_masic'])

    def test_mmu_staticth_config_all_verbose_masic(self):
        self.executor(testData['mmu_cfg_static_th_all_verbose_masic'])

    def test_mmu_alpha_config_invalid_masic(self):
        self.executor(testData['mmu_cfg_alpha_invalid_masic'])

    def test_mmu_staticth_config_invalid_masic(self):
        self.executor(testData['mmu_cfg_static_th_invalid_masic'])

    @classmethod
    def teardown_class(cls):
        super().teardown_class()
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""

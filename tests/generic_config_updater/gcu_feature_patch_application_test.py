import jsonpatch
import unittest
import copy
import mock
from unittest.mock import MagicMock, Mock
from mock import patch

import generic_config_updater.change_applier
import generic_config_updater.gu_common
import generic_config_updater.patch_sorter as ps
import generic_config_updater.generic_updater as gu
from .gutest_helpers import Files
from generic_config_updater.gu_common import ConfigWrapper, PatchWrapper

running_config = {}


def set_entry(config_db, tbl, key, data):
    global running_config
    if data != None:
        if tbl not in running_config:
            running_config[tbl] = {}
        running_config[tbl][key] = data
    else:
        assert tbl in running_config
        assert key in running_config[tbl]
        running_config[tbl].pop(key)
        if not running_config[tbl]:
            running_config.pop(tbl)


def get_running_config(scope="localhost"):
    return running_config


class TestFeaturePatchApplication(unittest.TestCase):
    def setUp(self):
        self.config_wrapper = ConfigWrapper()
    
    @patch("generic_config_updater.field_operation_validators.rdma_config_update_validator", mock.Mock(return_value=True))
    def test_feature_patch_application_success(self):
        # Format of the JSON file containing the test-cases:
        #
        # {
        #     "<unique_name_for_the_test>":{
        #         "desc":"<brief explanation of the test case>",
        #         "current_config":<the running config to be modified>,
        #         "patch":<the JsonPatch to apply>,
        #         "expected_config":<the config after jsonpatch modification>
        #     },
        #     .
        #     .
        #     .
        # }
        data = Files.FEATURE_PATCH_APPLICATION_TEST_SUCCESS
        
        for test_case_name in data:
            with self.subTest(name=test_case_name):
                self.run_single_success_case_applier(data[test_case_name])

    @patch("generic_config_updater.field_operation_validators.rdma_config_update_validator", mock.Mock(return_value=True))
    def test_feature_patch_application_failure(self):
        # Fromat of the JSON file containing the test-cases:
        #
        # {
        #     "<unique_name_for_the_test>":{
        #         "desc":"<brief explanation of the test case>",
        #         "current_config":<the running config to be modified>,
        #         "patch":<the JsonPatch to apply>,
        #         "expected_error_substrings":<error substrings expected in failure output>
        #     },
        #     .
        #     .
        #     .
        # }
        data = Files.FEATURE_PATCH_APPLICATION_TEST_FAILURE
        
        for test_case_name in data:
            with self.subTest(name=test_case_name):
                self.run_single_failure_case_applier(data[test_case_name])
    
    def create_strict_patch_sorter(self, config):
        config_wrapper = self.config_wrapper
        config_wrapper.get_config_db_as_json = MagicMock(return_value=config)
        patch_wrapper = PatchWrapper(config_wrapper)
        return ps.StrictPatchSorter(config_wrapper, patch_wrapper)

    def create_patch_applier(self, config):
        global running_config
        running_config = copy.deepcopy(config)
        config_wrapper = self.config_wrapper
        config_wrapper.get_config_db_as_json = MagicMock(side_effect=get_running_config)
        change_applier = generic_config_updater.change_applier.ChangeApplier()
        patch_wrapper = PatchWrapper(config_wrapper)
        return gu.PatchApplier(config_wrapper=config_wrapper, patch_wrapper=patch_wrapper, changeapplier=change_applier)
    
    @patch('generic_config_updater.change_applier.get_config_db_as_json', side_effect=get_running_config)
    @patch("generic_config_updater.change_applier.get_config_db")
    @patch("generic_config_updater.change_applier.set_config")
    def run_single_success_case_applier(self, data, mock_set, mock_db, mock_get_config_db_as_json):
        current_config = data["current_config"]
        expected_config = data["expected_config"]
        patch = jsonpatch.JsonPatch(data["patch"])
        
        # Test patch applier
        mock_set.side_effect = set_entry
        patch_applier = self.create_patch_applier(current_config)
        patch_applier.apply(patch)
        result_config = patch_applier.config_wrapper.get_config_db_as_json()

        self.assertEqual(expected_config, result_config)

        # Test steps in change applier
        sorter = self.create_strict_patch_sorter(current_config)
        actual_changes = sorter.sort(patch)
        target_config = patch.apply(current_config)
        simulated_config = current_config

        for change in actual_changes:
            simulated_config = change.apply(simulated_config)
            is_valid, error = self.config_wrapper.validate_config_db_config(simulated_config)
            self.assertTrue(is_valid, f"Change will produce invalid config. Error: {error}")

        self.assertEqual(target_config, simulated_config)
        self.assertEqual(simulated_config, expected_config)
    
    @patch("generic_config_updater.change_applier.get_config_db")
    @patch('generic_config_updater.change_applier.get_config_db_as_json', side_effect=get_running_config)
    def run_single_failure_case_applier(self, data, mock_db, mock_get_config_db_as_json):
        current_config = data["current_config"]
        patch = jsonpatch.JsonPatch(data["patch"])
        expected_error_substrings = data["expected_error_substrings"]

        try:
            patch_applier = self.create_patch_applier(current_config)
            patch_applier.apply(patch)
            self.fail("An exception was supposed to be thrown")
        except Exception as ex:
            notfound_substrings = []
            error = str(ex)
            
            for substring in expected_error_substrings:
                if substring not in error:
                    notfound_substrings.append(substring)

            if notfound_substrings:
                self.fail(f"Did not find the expected substrings {notfound_substrings} in the error: '{error}'")

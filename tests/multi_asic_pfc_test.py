import os
import sys
import json
import importlib
import pfc.main as pfc
from .pfc_test import TestPfcBase
from click.testing import CliRunner
from .pfc_input.pfc_test_vectors import testData

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "pfc")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)


class TestPfcMultiAsic(TestPfcBase):
    @classmethod
    def setup_class(cls):
        super().setup_class()
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"

        # Multi-asic utils rely on the database that is loaded
        # We reload the multi_asic database and update the multi-asic utils
        # Pfc uses click cmds that use multi_asic utils, hence we reload pfc too

        import mock_tables.mock_multi_asic
        importlib.reload(mock_tables.mock_multi_asic)
        mock_tables.dbconnector.load_namespace_config()

        import utilities_common
        importlib.reload(utilities_common.multi_asic)
        importlib.reload(pfc)

    def executor(self, input):
        runner = CliRunner()
        result = runner.invoke(pfc.cli, input['cmd'])
        exit_code = result.exit_code
        output = result.output

        print(exit_code)
        print(output)

        assert exit_code == input['rc']

        # For config commands we dump modified value in a tmp JSON file for testing
        if 'cmp_args' in input:
            fd = open('/tmp/pfc_testdata.json', 'r')
            cmp_data = json.load(fd)

            # Verify assignments
            for args in input['cmp_args']:
                namespace, table, key, field, expected_val = args
                assert(cmp_data[namespace][table][key][field] == expected_val)
            fd.close()

        if 'rc_msg' in input:
            assert input['rc_msg'] in output

        if 'rc_output' in input:
            assert output == input['rc_output']

    def test_pfc_show_asymmetric_all_asic0_masic(self):
        self.executor(testData['pfc_show_asymmetric_all_asic0_masic'])

    def test_pfc_show_asymmetric_all_asic1_masic(self):
        self.executor(testData['pfc_show_asymmetric_all_asic1_masic'])

    def test_pfc_show_asymmetric_all_masic(self):
        self.executor(testData['pfc_show_asymmetric_all_masic'])

    def test_pfc_show_asymmetric_intf_one_masic(self):
        self.executor(testData['pfc_show_asymmetric_intf_one_masic'])

    def test_pfc_show_asymmetric_intf_all_masic(self):
        self.executor(testData['pfc_show_asymmetric_intf_all_masic'])

    def test_pfc_show_asymmetric_intf_fake_one_masic(self):
        self.executor(testData['pfc_show_asymmetric_intf_fake_one_masic'])

    def test_pfc_show_priority_all_asic0_masic(self):
        self.executor(testData['pfc_show_priority_all_asic0_masic'])

    def test_pfc_show_priority_all_asic1_masic(self):
        self.executor(testData['pfc_show_priority_all_asic1_masic'])

    def test_pfc_show_priority_all_masic(self):
        self.executor(testData['pfc_show_priority_all_masic'])

    def test_pfc_show_priority_intf_one_masic(self):
        self.executor(testData['pfc_show_priority_intf_one_masic'])

    def test_pfc_show_priority_intf_all_masic(self):
        self.executor(testData['pfc_show_priority_intf_all_masic'])

    def test_pfc_show_priority_intf_fake_one_masic(self):
        self.executor(testData['pfc_show_priority_intf_fake_one_masic'])

    def test_pfc_show_priority_intf_fake_all_masic(self):
        self.executor(testData['pfc_show_priority_intf_fake_all_masic'])

    def test_pfc_config_asymmetric_one_masic(self):
        self.executor(testData['pfc_config_asymmetric_one_masic'])

    def test_pfc_config_asymmetric_invalid_one_masic(self):
        self.executor(testData['pfc_config_asymmetric_invalid_one_masic'])

    def test_pfc_config_asymmetric_all_masic(self):
        self.executor(testData['pfc_config_asymmetric_all_masic'])

    def test_pfc_config_asymmetric_invalid_all_masic(self):
        self.executor(testData['pfc_config_asymmetric_invalid_all_masic'])

    def test_pfc_config_priority_one_masic(self):
        self.executor(testData['pfc_config_priority_one_masic'])

    def test_pfc_config_priority_invalid_one_masic(self):
        self.executor(testData['pfc_config_priority_invalid_one_masic'])

    def test_pfc_config_priority_all_masic(self):
        self.executor(testData['pfc_config_priority_all_masic'])

    def test_pfc_config_priority_invalid_all_masic(self):
        self.executor(testData['pfc_config_priority_invalid_all_masic'])

    @classmethod
    def teardown_class(cls):
        # Reset the database to mock single-asic state
        import mock_tables.mock_single_asic
        mock_tables.dbconnector.load_database_config()

        super().teardown_class()
        os.environ.pop("UTILITIES_UNIT_TESTING_TOPOLOGY")

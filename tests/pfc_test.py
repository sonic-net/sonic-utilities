import os
import sys
import json
import pfc.main as pfc
from .pfc_input.assert_show_output import pfc_cannot_find_intf, pfc_show_asymmetric_all, \
   pfc_show_asymmetric_intf, pfc_show_priority_all, pfc_show_priority_intf, \
   pfc_config_priority_on, pfc_asym_cannot_find_intf

from click.testing import CliRunner
from importlib import reload

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "pfc")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)


class TestPfcBase(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"

    def executor(self, cliobj, command, expected_rc=0, expected_output=None, expected_cfgdb_entries=None,
                 runner=CliRunner()):
        result = runner.invoke(cliobj, command)
        print(result.exit_code)
        print(result.output)

        if result.exit_code != expected_rc:
            print(result.exception)
        assert result.exit_code == expected_rc

        if expected_output:
            assert result.output == expected_output

        if expected_cfgdb_entries:
            fd = open('/tmp/pfc_testdata.json', 'r')
            cmp_data = json.load(fd)
            for expected_cfgdb_entry in expected_cfgdb_entries:
                (namespace, table, key, field, expected_val) = expected_cfgdb_entry
                entry = cmp_data[namespace][table][key][field]
                assert entry == expected_val

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(
            os.environ["PATH"].split(os.pathsep)[:-1]
        )
        os.environ.pop("UTILITIES_UNIT_TESTING")
        if os.path.isfile('/tmp/pfc_testdata.json'):
            os.remove('/tmp/pfc_testdata.json')

class TestPfc(TestPfcBase):
    @classmethod
    def setup_class(cls):
        super().setup_class()

        from mock_tables import dbconnector
        from mock_tables import mock_single_asic
        reload(mock_single_asic)
        dbconnector.load_database_config()

        import utilities_common
        reload(utilities_common.multi_asic)
        reload(pfc)

    def test_pfc_show_asymmetric_all(self):
        self.executor(pfc.cli, ['show', 'asymmetric'],
                      expected_output=pfc_show_asymmetric_all)

    def test_pfc_show_asymmetric_intf(self):
        self.executor(pfc.cli, ['show', 'asymmetric', 'Ethernet0'],
                      expected_output=pfc_show_asymmetric_intf)

    def test_pfc_show_asymmetric_intf_fake(self):
        self.executor(pfc.cli, ['show', 'asymmetric', 'Ethernet1234'],
                      expected_output=pfc_asym_cannot_find_intf)

    def test_pfc_show_priority_all(self):
        self.executor(pfc.cli, ['show', 'priority'],
                      expected_output=pfc_show_priority_all)

    def test_pfc_show_priority_intf(self):
        self.executor(pfc.cli, ['show', 'priority', 'Ethernet0'],
                      expected_output=pfc_show_priority_intf)

    def test_pfc_show_priority_intf_fake(self):
        self.executor(pfc.cli, ['show', 'priority', 'Ethernet1234'],
                      expected_output=pfc_cannot_find_intf)

    def test_pfc_config_asymmetric(self):
        self.executor(pfc.cli, ['config', 'asymmetric', 'on', 'Ethernet0'],
                      # namespace, table, key, field, expected_val
                      expected_cfgdb_entries=[('', 'PORT', 'Ethernet0', 'pfc_asym', 'on')])

    def test_pfc_config_priority(self):
        self.executor(pfc.cli, ['config', 'priority', 'on', 'Ethernet0', '5'],
                      # namespace, table, key, field, expected_val
                      expected_cfgdb_entries=[('', 'PORT_QOS_MAP', 'Ethernet0', 'pfc_enable', '3,4,5')])

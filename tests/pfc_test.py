import os
import sys
import pfc.main as pfc
from .pfc_input.assert_show_output import pfc_cannot_find_intf, pfc_show_asymmetric_all, \
   pfc_show_asymmetric_intf, pfc_show_priority_all, pfc_show_priority_intf, \
   pfc_config_priority_on, pfc_asym_cannot_find_intf
from utilities_common.db import Db

from click.testing import CliRunner
from importlib import reload

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "pfc")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)


class TestPfcBase(object):

    def executor(self, cliobj, command, expected_rc=0, expected_output=None, expected_cfgdb_entry=None,
                 runner=CliRunner()):
        db = Db()
        result = runner.invoke(cliobj, command, obj=db)
        print(result.exit_code)
        print(result.output)

        if result.exit_code != expected_rc:
            print(result.exception)
        assert result.exit_code == expected_rc

        if expected_output:
            assert result.output == expected_output

        if expected_cfgdb_entry:
            (table, key, field, expected_val) = expected_cfgdb_entry
            configdb = db.cfgdb
            entry = configdb.get_entry(table, key)
            assert entry.get(field) == expected_val


class TestPfc(TestPfcBase):

    @classmethod
    def setup_class(cls):
        from mock_tables import dbconnector
        from mock_tables import mock_single_asic
        reload(mock_single_asic)
        dbconnector.load_namespace_config()

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
                      expected_cfgdb_entry=('PORT', 'Ethernet0', 'pfc_asym', 'on'))

    def test_pfc_config_priority(self):
        self.executor(pfc.cli, ['config', 'priority', 'on', 'Ethernet0', '5'],
                      expected_output=pfc_config_priority_on)

import os
import sys
import json
import pytest

from click.testing import CliRunner
import config.main as config
import show.main as show
from utilities_common.db import Db
from .mmuconfig_input.mmuconfig_test_vectors import testData

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)


class TestMmuConfigBase(object):
    # Per-worker file path to avoid race conditions in parallel test runs.
    _mmuconfig_file = None

    @classmethod
    def setup_class(cls):
        print('SETUP')
        worker_tmp = os.environ.get('WORKER_TMP', '/tmp')
        cls._mmuconfig_file = os.path.join(worker_tmp, 'mmuconfig')
        os.environ['MMUCONFIG_FILE'] = cls._mmuconfig_file

    def executor(self, input):
        runner = CliRunner()

        if 'db_table' in input:
            db = Db()
            data_list = list(db.cfgdb.get_table(input['db_table']))
            input['rc_msg'] = input['rc_msg'].format(",".join(data_list))

        if 'show' in input['cmd']:
            exec_cmd = show.cli.commands["mmu"]
            result = runner.invoke(exec_cmd, input['args'])
            exit_code = result.exit_code
            output = result.output

        elif 'config' in input['cmd']:
            exec_cmd = config.config.commands["mmu"]
            result = runner.invoke(exec_cmd, input['args'], catch_exceptions=False)
            exit_code = result.exit_code
            output = result.output

        print(exit_code)
        print(output)

        if input['rc'] == 0:
            assert exit_code == 0
        else:
            assert exit_code != 0

        if 'cmp_args' in input:
            fd = open(self._mmuconfig_file, 'r')
            cmp_data = json.load(fd)
            for args in input['cmp_args']:
                namespace, profile, name, value = args.split(',')
                assert(cmp_data[namespace][profile][name] == value)
            fd.close()

        if 'rc_msg' in input:
            assert input['rc_msg'] in output

        if 'rc_output' in input:
            assert output == input['rc_output']

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        if cls._mmuconfig_file and os.path.isfile(cls._mmuconfig_file):
            os.remove(cls._mmuconfig_file)
        os.environ.pop('MMUCONFIG_FILE', None)
        print("TEARDOWN")


class TestMmuConfig(TestMmuConfigBase):
    def test_mmu_show_config(self):
        self.executor(testData['mmuconfig_list'])

    def test_mmu_alpha_config(self):
        self.executor(testData['mmu_cfg_alpha'])

    def test_mmu_alpha_invalid_config(self):
        self.executor(testData['mmu_cfg_alpha_invalid'])

    def test_mmu_staticth_config(self):
        self.executor(testData['mmu_cfg_static_th'])

    def test_mmu_alpha_zero_config(self):
        self.executor(testData['mmu_cfg_alpha_zero'])

    def test_mmu_staticth_zero_config(self):
        self.executor(testData['mmu_cfg_static_th_zero'])

    def test_mmu_trim_config(self):
        self.executor(testData['mmu_cfg_trim'])

    def test_mmu_trim_invalid_config(self):
        self.executor(testData['mmu_cfg_trim_invalid'])

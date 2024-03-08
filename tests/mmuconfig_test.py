import os
import sys
import json
import pytest

from click.testing import CliRunner
import config.main as config
import show.main as show
from utilities_common.db import Db
from .mmuconfig_input.mmuconfig_test_vectors import *

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)


class Testmmuconfig(object):
    @classmethod
    def setup_class(cls):
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        print("SETUP")

    def test_mmu_show_config(self):
        self.executor(testData['mmuconfig_list'])

    def test_mmu_alpha_config(self):
        self.executor(testData['mmu_cfg_alpha'])

    def test_mmu_alpha_invalid_config(self):
        self.executor(testData['mmu_cfg_alpha_invalid'])

    def test_mmu_staticth_config(self):
        self.executor(testData['mmu_cfg_static_th'])

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
            fd = open('/tmp/mmuconfig', 'r')
            cmp_data = json.load(fd)
            for args in input['cmp_args']:
                profile, name, value = args.split(',')
                assert(cmp_data[profile][name] == value)
            fd.close()

        if 'rc_msg' in input:
            assert input['rc_msg'] in output

        if 'rc_output' in input:
            assert output == input['rc_output']


    @classmethod
    def teardown_class(cls):
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        if os.path.isfile('/tmp/mmuconfig'):
            os.remove('/tmp/mmuconfig')
        print("TEARDOWN")

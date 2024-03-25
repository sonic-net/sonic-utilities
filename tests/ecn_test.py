import ast
import json
import os
import sys

from click.testing import CliRunner

import config.main as config
from ecn_input.ecn_test_vectors import *
from utils import get_result_and_return_code
from utilities_common.db import Db
import show.main as show

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)


class TestEcnConfigBase(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ['UTILITIES_UNIT_TESTING'] = "2"

    def process_cmp_args(self, cmp_args):
        if cmp_args is None:
            return (None, None)
        return cmp_args.split(',')

    def verify_profile(self, queue_db_entry, profile, value):
        if profile != None:
            assert queue_db_entry[profile] == value
        else:
            assert profile not in queue_db_entry,\
                   "Profile needs to be fully removed from table to propagate NULL OID to SAI"

    def executor(self, input):
        runner = CliRunner()

        if 'db_table' in input:
            db = Db()
            data_list = list(db.cfgdb.get_table(input['db_table']))
            input['rc_msg'] = input['rc_msg'].format(",".join(data_list))

        if 'show' in input['cmd']:
            exec_cmd = show.cli.commands["ecn"]
            result = runner.invoke(exec_cmd, input['args'])
            exit_code = result.exit_code
            output = result.output
        elif 'q_cmd' in input['cmd'] or 'show_masic' in input['cmd'] or 'config_masic' in input['cmd']:
            exit_code, output = get_result_and_return_code(["ecnconfig"] + input['args'])
        else:
            exec_cmd = config.config.commands["ecn"]
            result = runner.invoke(exec_cmd, input['args'])
            exit_code = result.exit_code
            output = result.output

        print(exit_code)
        print(output)

        if input['rc'] == 0:
            assert exit_code == 0
        else:
            assert exit_code != 0

        if 'cmp_args' in input:
            fd = open('/tmp/ecnconfig', 'r')
            cmp_data = json.load(fd)
            if 'cmp_q_args' in input:
                profile, value = self.process_cmp_args(input['cmp_args'][0])
                if 'other_q' in input:
                    profile1, value1 = self.process_cmp_args(input['cmp_args'][-1])
                for key in cmp_data:
                    queue_idx = ast.literal_eval(key)[-1]
                    if queue_idx in input['cmp_q_args']:
                        self.verify_profile(cmp_data[key], profile, value)
                    if 'other_q' in input and queue_idx in input['other_q']:
                        self.verify_profile(cmp_data[key], profile1, value1)
            else:
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
        os.environ['PATH'] = os.pathsep.join(os.environ['PATH'].split(os.pathsep)[:-1])
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        if os.path.isfile('/tmp/ecnconfig'):
            os.remove('/tmp/ecnconfig')
        print("TEARDOWN")

class TestEcnConfig(TestEcnConfigBase):
    def test_ecn_show_config(self):
        self.executor(testData['ecn_show_config'])

    def test_ecn_show_config_verbose(self):
        self.executor(testData['ecn_show_config_verbose'])

    def test_ecn_config_gmin(self):
        self.executor(testData['ecn_cfg_gmin'])

    def test_ecn_config_gmin_verbose(self):
        self.executor(testData['ecn_cfg_gmin_verbose'])

    def test_ecn_config_gmax(self):
        self.executor(testData['ecn_cfg_gmax'])

    def test_ecn_config_ymin(self):
        self.executor(testData['ecn_cfg_ymin'])

    def test_ecn_config_ymax(self):
        self.executor(testData['ecn_cfg_ymax'])

    def test_ecn_config_rmin(self):
        self.executor(testData['ecn_cfg_gmin'])

    def test_ecn_config_rmax(self):
        self.executor(testData['ecn_cfg_gmax'])

    def test_ecn_config_gdrop(self):
        self.executor(testData['ecn_cfg_gdrop'])

    def test_ecn_config_gdrop_verbose(self):
        self.executor(testData['ecn_cfg_gdrop_verbose'])

    def test_ecn_config_ydrop(self):
        self.executor(testData['ecn_cfg_ydrop'])

    def test_ecn_config_rdrop(self):
        self.executor(testData['ecn_cfg_rdrop'])

    def test_ecn_config_multi_set(self):
        self.executor(testData['ecn_cfg_multi_set'])

    def test_ecn_config_gmin_gmax_invalid(self):
        self.executor(testData['ecn_cfg_gmin_gmax_invalid'])

    def test_ecn_config_ymin_ymax_invalid(self):
        self.executor(testData['ecn_cfg_ymin_ymax_invalid'])

    def test_ecn_config_rmin_rmax_invalid(self):
        self.executor(testData['ecn_cfg_rmin_rmax_invalid'])

    def test_ecn_config_rmax_invalid(self):
        self.executor(testData['ecn_cfg_rmax_invalid'])

    def test_ecn_config_rdrop_invalid(self):
        self.executor(testData['ecn_cfg_rdrop_invalid'])

    def test_ecn_queue_get(self):
        self.executor(testData['ecn_q_get'])

    def test_ecn_queue_get_verbose(self):
        self.executor(testData['ecn_q_get_verbose'])

    def test_ecn_queue_get_lossy(self):
        self.executor(testData['ecn_lossy_q_get'])

    def test_ecn_all_queue_get(self):
        self.executor(testData['ecn_q_all_get'])

    def test_ecn_queue_all_get_verbose(self):
        self.executor(testData['ecn_q_all_get_verbose'])

    def test_ecn_queue_set_q_off(self):
        self.executor(testData['ecn_cfg_q_off'])

    def test_ecn_queue_set_q_off_verbose(self):
        self.executor(testData['ecn_cfg_q_off_verbose'])

    def test_ecn_queue_set_all_off(self):
        self.executor(testData['ecn_cfg_q_all_off'])

    def test_ecn_queue_set_all_off_verbose(self):
        self.executor(testData['ecn_cfg_q_all_off_verbose'])

    def test_ecn_queue_set_q_on(self):
        self.executor(testData['ecn_cfg_q_on'])

    def test_ecn_queue_set_q_on_verbose(self):
        self.executor(testData['ecn_cfg_q_on_verbose'])

    def test_ecn_queue_set_all_on(self):
        self.executor(testData['ecn_cfg_q_all_on'])

    def test_ecn_queue_set_all_on_verbose(self):
        self.executor(testData['ecn_cfg_q_all_on_verbose'])

    def test_ecn_queue_set_lossy_q_on(self):
        self.executor(testData['ecn_cfg_lossy_q_on'])

import os
import sys
from .wm_input.wm_test_vectors import testData
from .utils import get_result_and_return_code
from click.testing import CliRunner
import show.main as show

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)


class TestWatermarkstatMultiAsic(object):
    @classmethod
    def setup_class(cls):
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        print("SETUP")

    def executor(self, testcase):
        runner = CliRunner()
        for input in testcase:
            if 'clear' in input['cmd']:
                exec_cmd = input['cmd'][1:]
                print(exec_cmd)
                exit_code, output = get_result_and_return_code(exec_cmd)
            else:
                if len(input['cmd']) == 3:
                    exec_cmd = show.cli.commands[input['cmd'][0]].commands[input['cmd'][1]].commands[input['cmd'][2]]
                else:
                    exec_cmd = show.cli.commands[input['cmd'][0]].commands[input['cmd'][1]]
                args = [] if 'args' not in input else input['args']
                result = runner.invoke(exec_cmd, args)
                exit_code = result.exit_code
                output = result.output

            print(exit_code)
            print(output)

            expected_code = 0 if 'rc' not in input else input['rc']
            assert exit_code == expected_code
            assert output == input['rc_output']

    def test_show_pg_shared_one_masic(self):
        self.executor(testData['show_pg_wm_shared_one_masic'])

    def test_show_pg_shared_all_masic(self):
        self.executor(testData['show_pg_wm_shared_all_masic'])

    def test_show_pg_headroom_wm_one_masic(self):
        self.executor(testData['show_pg_wm_hdrm_one_masic'])

    def test_show_pg_headroom_wm_all_masic(self):
        self.executor(testData['show_pg_wm_hdrm_all_masic'])

    def test_show_pg_shared_pwm_one_masic(self):
        self.executor(testData['show_pg_pwm_shared_one_masic'])

    def test_show_pg_shared_pwm_all_masic(self):
        self.executor(testData['show_pg_pwm_shared_all_masic'])

    def test_show_pg_headroom_pwm_one_masic(self):
        self.executor(testData['show_pg_pwm_hdrm_one_masic'])

    def test_show_pg_headroom_pwm_all_masic(self):
        self.executor(testData['show_pg_pwm_hdrm_all_masic'])

    def test_show_queue_unicast_wm_one_masic(self):
        self.executor(testData['show_q_wm_unicast_one_masic'])

    def test_show_queue_unicast_wm_all_masic(self):
        self.executor(testData['show_q_wm_unicast_all_masic'])

    def test_show_queue_unicast_pwm_one_masic(self):
        self.executor(testData['show_q_pwm_unicast_one_masic'])

    def test_show_queue_unicast_pwm_all_masic(self):
        self.executor(testData['show_q_pwm_unicast_all_masic'])

    def test_show_queue_multicast_wm_one_masic(self):
        self.executor(testData['show_q_wm_multicast_one_masic'])

    def test_show_queue_multicast_wm_all_masic(self):
        self.executor(testData['show_q_wm_multicast_all_masic'])

    def test_show_queue_multicast_pwm_one_masic(self):
        self.executor(testData['show_q_pwm_multicast_one_masic'])

    def test_show_queue_multicast_pwm_all_masic(self):
        self.executor(testData['show_q_pwm_multicast_all_masic'])

    def test_show_queue_all_wm_one_masic(self):
        self.executor(testData['show_q_wm_all_one_masic'])

    def test_show_queue_all_wm_all_masic(self):
        self.executor(testData['show_q_wm_all_all_masic'])

    def test_show_queue_all_pwm_one_masic(self):
        self.executor(testData['show_q_pwm_all_one_masic'])

    def test_show_queue_all_pwm_all_masic(self):
        self.executor(testData['show_q_pwm_all_all_masic'])

    def test_show_buffer_pool_wm_one_masic(self):
        self.executor(testData['show_buffer_pool_wm_one_masic'])

    def test_show_buffer_pool_wm_all_masic(self):
        self.executor(testData['show_buffer_pool_wm_all_masic'])

    def test_show_buffer_pool_pwm_one_masic(self):
        self.executor(testData['show_buffer_pool_pwm_one_masic'])

    def test_show_buffer_pool_pwm_all_masic(self):
        self.executor(testData['show_buffer_pool_pwm_all_masic'])

    def test_show_headroom_pool_wm_one_masic(self):
        self.executor(testData['show_hdrm_pool_wm_one_masic'])

    def test_show_headroom_pool_wm_all_masic(self):
        self.executor(testData['show_hdrm_pool_wm_all_masic'])

    def test_show_headroom_pool_pwm_one_masic(self):
        self.executor(testData['show_hdrm_pool_pwm_one_masic'])

    def test_show_headroom_pool_pwm_all_masic(self):
        self.executor(testData['show_hdrm_pool_pwm_all_masic'])

    def test_show_invalid_namespace_masic(self):
        self.executor(testData['show_invalid_namespace_masic'])

    def test_clear_headroom_one_masic(self):
        self.executor(testData['clear_hdrm_pool_wm_one_masic'])

    def test_clear_headroom_all_masic(self):
        self.executor(testData['clear_hdrm_pool_wm_all_masic'])

    @classmethod
    def teardown_class(cls):
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        print("TEARDOWN")

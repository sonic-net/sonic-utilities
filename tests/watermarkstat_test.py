import os
import sys
import pytest
import show.main as show
from click.testing import CliRunner
from wm_input.wm_test_vectors import testData

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)


@pytest.fixture(scope="function")
def q_multicast_wm_neg():
    print("Setup watermarkstat sample data: no queue multicast watermark counters")
    os.environ['WATERMARKSTAT_UNIT_TESTING'] = "1"
    yield
    del os.environ['WATERMARKSTAT_UNIT_TESTING']
    print("Teardown watermarkstat sample data: no queue multicast watermark counters")


class TestWatermarkstat(object):
    @classmethod
    def setup_class(cls):
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        print("SETUP")

    def test_show_pg_shared_wm(self):
        self.executor(testData['show_pg_wm_shared'])

    def test_show_pg_headroom_wm(self):
        self.executor(testData['show_pg_wm_hdrm'])

    def test_show_queue_unicast_wm(self):
        self.executor(testData['show_q_wm_unicast'])

    def test_show_queue_multicast_wm(self):
        self.executor(testData['show_q_wm_multicast'])

    def test_show_queue_multicast_wm_neg(self, q_multicast_wm_neg):
        self.executor(testData['show_q_wm_multicast_neg'])

    def test_show_queue_all_wm(self):
        self.executor(testData['show_q_wm_all'])

    def test_show_buffer_pool_wm(self):
        self.executor(testData['show_buffer_pool_wm'])

    def test_show_headroom_pool_wm(self):
        self.executor(testData['show_hdrm_pool_wm'])

    def test_show_pg_shared_peristent_wm(self):
        self.executor(testData['show_pg_pwm_shared'])

    def test_show_pg_headroom_persistent_wm(self):
        self.executor(testData['show_pg_pwm_hdrm'])

    def test_show_queue_unicast_persistent_wm(self):
        self.executor(testData['show_q_pwm_unicast'])

    def test_show_queue_multicast_persistent_wm(self):
        self.executor(testData['show_q_pwm_multicast'])

    def test_show_queue_all_persistent_wm(self):
        self.executor(testData['show_q_pwm_all'])

    def test_show_buffer_pool_persistent_wm(self):
        self.executor(testData['show_buffer_pool_pwm'])

    def test_show_headroom_pool_persistent_wm(self):
        self.executor(testData['show_hdrm_pool_pwm'])

    def executor(self, testcase):
        runner = CliRunner()

        for input in testcase:
            if len(input['cmd']) == 3:
                exec_cmd = show.cli.commands[input['cmd'][0]].commands[input['cmd'][1]].commands[input['cmd'][2]]
            else:
                exec_cmd = show.cli.commands[input['cmd'][0]].commands[input['cmd'][1]]

            args = [] if 'args' not in input else input['args']
            result = runner.invoke(exec_cmd, args)

            print(result.exit_code)
            print(result.output)

            expected_code = 0 if 'rc' not in input else input['rc']
            assert result.exit_code == expected_code
            assert result.output == input['rc_output']

    @classmethod
    def teardown_class(cls):
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")

import os
import sys
from utilities_common.cli import UserCache
from .utils import get_result_and_return_code

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

pg_drop_masic_one_result = """\
Ingress PG dropped packets:
          Port    PG0    PG1    PG2    PG3    PG4    PG5    PG6    PG7    PG8    PG9    PG10    PG11    PG12    PG13\
    PG14    PG15
--------------  -----  -----  -----  -----  -----  -----  -----  -----  -----  -----  ------  ------  ------  ------\
  ------  ------
Ethernet-BP256    N/A    N/A    N/A    N/A    N/A    N/A    N/A    N/A    N/A    N/A     N/A     N/A     N/A     N/A\
     N/A     N/A
Ethernet-BP260    N/A    N/A    N/A    N/A    N/A    N/A    N/A    N/A    N/A    N/A     N/A     N/A     N/A     N/A\
     N/A     N/A
"""

pg_drop_masic_all_result = """\
Ingress PG dropped packets:
          Port    PG0    PG1    PG2    PG3    PG4    PG5    PG6    PG7    PG8    PG9    PG10    PG11    PG12    PG13\
    PG14    PG15
--------------  -----  -----  -----  -----  -----  -----  -----  -----  -----  -----  ------  ------  ------  ------\
  ------  ------
     Ethernet0      0      0      0      0      0      0      0      0      0      0       0       0       0       0\
       0       0
     Ethernet4      0      0      0      0      0      0      0      0      0      0       0       0       0       0\
       0       0
  Ethernet-BP0      0      0      0      0      0      0      0      0      0      0       0       0       0       0\
       0       0
  Ethernet-BP4      0      0      0      0      0      0      0      0      0      0       0       0       0       0\
       0       0
Ethernet-BP256    N/A    N/A    N/A    N/A    N/A    N/A    N/A    N/A    N/A    N/A     N/A     N/A     N/A     N/A\
     N/A     N/A
Ethernet-BP260    N/A    N/A    N/A    N/A    N/A    N/A    N/A    N/A    N/A    N/A     N/A     N/A     N/A     N/A\
     N/A     N/A
"""


class TestMultiAsicPgDropstat(object):
    @classmethod
    def setup_class(cls):
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        print("SETUP")

    def test_show_pg_drop_masic_all(self):
        return_code, result = get_result_and_return_code([
            'pg-drop', '-c', 'show'
        ])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == pg_drop_masic_all_result

    def test_show_pg_drop_masic(self):
        return_code, result = get_result_and_return_code([
            'pg-drop', '-c', 'show', '-n', 'asic1'
        ])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == pg_drop_masic_one_result

    def test_show_pg_drop_masic_not_exist(self):
        return_code, result = get_result_and_return_code([
            'pg-drop', '-c', 'show', '-n', 'asic5'
        ])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 1
        assert result == "Input value for '--namespace' / '-n'. Choose from one of (asic0, asic1)"

    def test_clear_pg_drop(self):
        return_code, result = get_result_and_return_code([
            'pg-drop', '-c', 'clear'
        ])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == "Cleared PG drop counter\n"

    @classmethod
    def teardown_class(cls):
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        UserCache('pg-drop').remove_all()
        print("TEARDOWN")

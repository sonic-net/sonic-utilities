import os
import shutil

from click.testing import CliRunner

import clear.main as clear
import show.main as show
from .utils import get_result_and_return_code

root_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(root_path)
scripts_path = os.path.join(modules_path, "scripts")

multi_asic_fabric_counters = """\
  ASIC    PORT    STATE    IN_CELL    IN_OCTET    OUT_CELL    OUT_OCTET    CRC    FEC_CORRECTABLE    FEC_UNCORRECTABLE    SYMBOL_ERR
------  ------  -------  ---------  ----------  ----------  -----------  -----  -----------------  -------------------  ------------
     0       0       up          6       1,113           0            0      0                  5        1,759,692,040             5
     0       1     down          0           0           0            0      0                  0       58,977,677,898             0
     0       2       up          2         371           0            0      0                  0        1,769,448,760             0
     0       3     down          0           0           0            0      0                  0       58,976,477,608             0
     0       4       up         10       1,855           0            0      0                 73        1,763,293,100            73
     0       5     down          0           0           0            0      0             44,196       58,975,150,569             0
     0       6       up          4         742           0            0      0                 10        1,763,174,090             0
     0       7       up         10       1,855           0            0      0                187        1,768,439,529         1,331

  ASIC    PORT    STATE    IN_CELL    IN_OCTET    OUT_CELL    OUT_OCTET    CRC    FEC_CORRECTABLE    FEC_UNCORRECTABLE      SYMBOL_ERR
------  ------  -------  ---------  ----------  ----------  -----------  -----  -----------------  -------------------  --------------
     1       0       up         16       2,968           0            0      0                  0        1,763,890,500               0
     1       1     down          0           0           0            0      0                  0      105,269,481,425               0
     1       2     down          0           0           0            0      0                  0      105,268,895,944               0
     1       3     down          0           0           0            0      0                  0      105,268,290,607               0
     1       4       up         14       2,597           0            0      0                  0        1,762,188,940               0
     1       5     down          0           0           0            0      0                968      105,267,020,477               0
     1       6     down          0           0           0            0      0     53,192,703,023            1,422,986  41,913,682,074
     1       7     down          0           0           0            0      0                  0      105,264,567,398               0

"""
multi_asic_fabric_counters_asic0 = """\
  ASIC    PORT    STATE    IN_CELL    IN_OCTET    OUT_CELL    OUT_OCTET    CRC    FEC_CORRECTABLE    FEC_UNCORRECTABLE    SYMBOL_ERR
------  ------  -------  ---------  ----------  ----------  -----------  -----  -----------------  -------------------  ------------
     0       0       up          6       1,113           0            0      0                  5        1,759,692,040             5
     0       1     down          0           0           0            0      0                  0       58,977,677,898             0
     0       2       up          2         371           0            0      0                  0        1,769,448,760             0
     0       3     down          0           0           0            0      0                  0       58,976,477,608             0
     0       4       up         10       1,855           0            0      0                 73        1,763,293,100            73
     0       5     down          0           0           0            0      0             44,196       58,975,150,569             0
     0       6       up          4         742           0            0      0                 10        1,763,174,090             0
     0       7       up         10       1,855           0            0      0                187        1,768,439,529         1,331

"""

clear_counter = """\
Clear and update saved counters port"""

multi_asic_fabric_counters_asic0_clear = """\
  ASIC    PORT    STATE    IN_CELL    IN_OCTET    OUT_CELL    OUT_OCTET    CRC    FEC_CORRECTABLE    FEC_UNCORRECTABLE    SYMBOL_ERR
------  ------  -------  ---------  ----------  ----------  -----------  -----  -----------------  -------------------  ------------
     0       0       up          0           0           0            0      0                  0                    0             0
     0       1     down          0           0           0            0      0                  0                    0             0
     0       2       up          0           0           0            0      0                  0                    0             0
     0       3     down          0           0           0            0      0                  0                    0             0
     0       4       up          0           0           0            0      0                  0                    0             0
     0       5     down          0           0           0            0      0                  0                    0             0
     0       6       up          0           0           0            0      0                  0                    0             0
     0       7       up          0           0           0            0      0                  0                    0             0

"""

fabric_invalid_asic_error = """ValueError: Unknown Namespace asic99"""

multi_asic_fabric_counters_queue = """\
  ASIC    PORT    STATE    QUEUE_ID    CURRENT_BYTE    CURRENT_LEVEL    WATERMARK_LEVEL
------  ------  -------  ----------  --------------  ---------------  -----------------
     0       0       up           0             763               12                 20
     0       1     down           0               0                0                  0
     0       2       up           0             104                8                  8
     0       3     down           0               0                0                  0
     0       4       up           0           1,147               14                 22
     0       5     down           0               0                0                  0
     0       6       up           0             527                8                 10
     0       7       up           0           1,147               14                 17

  ASIC    PORT    STATE    QUEUE_ID    CURRENT_BYTE    CURRENT_LEVEL    WATERMARK_LEVEL
------  ------  -------  ----------  --------------  ---------------  -----------------
     1       0       up           0           1,942               18                 24
     1       1     down           0               0                0                  0
     1       2     down           0               0                0                  0
     1       3     down           0               0                0                  0
     1       4       up           0           1,362               15                 24
     1       5     down           0               0                0                  0
     1       6     down           0               0                0                  0
     1       7     down           0               0                0                  0

"""

multi_asic_fabric_counters_queue_asic0 = """\
  ASIC    PORT    STATE    QUEUE_ID    CURRENT_BYTE    CURRENT_LEVEL    WATERMARK_LEVEL
------  ------  -------  ----------  --------------  ---------------  -----------------
     0       0       up           0             763               12                 20
     0       1     down           0               0                0                  0
     0       2       up           0             104                8                  8
     0       3     down           0               0                0                  0
     0       4       up           0           1,147               14                 22
     0       5     down           0               0                0                  0
     0       6       up           0             527                8                 10
     0       7       up           0           1,147               14                 17

"""

multi_asic_fabric_counters_queue_asic0_clear = """\
  ASIC    PORT    STATE    QUEUE_ID    CURRENT_BYTE    CURRENT_LEVEL    WATERMARK_LEVEL
------  ------  -------  ----------  --------------  ---------------  -----------------
     0       0       up           0               0                0                  0
     0       1     down           0               0                0                  0
     0       2       up           0               0                0                  0
     0       3     down           0               0                0                  0
     0       4       up           0               0                0                  0
     0       5     down           0               0                0                  0
     0       6       up           0               0                0                  0
     0       7       up           0               0                0                  0

"""

multi_asic_fabric_reachability = """\

asic0
  Local Link    Remote Module    Remote Link    Status
------------  ---------------  -------------  --------
           0                0             79        up
           2                0             94        up
           4                0             85        up
           6                0             84        up
           7                0             93        up

asic1
  Local Link    Remote Module    Remote Link    Status
------------  ---------------  -------------  --------
           0                0             69        up
           4                0             75        up
"""

multi_asic_fabric_reachability_asic0 = """\

asic0
  Local Link    Remote Module    Remote Link    Status
------------  ---------------  -------------  --------
           0                0             79        up
           2                0             94        up
           4                0             85        up
           6                0             84        up
           7                0             93        up
"""

multi_asic_fabric_capacity = """\
Monitored fabric capacity threshold: 100%

  ASIC    Operating     Total #     %    Last Event    Last Time
              Links    of Links
------  -----------  ----------  ----  ------------  -----------
 asic0            5           8  62.5          None        Never
 asic1            2           8  25            None        Never
"""

multi_asic_fabric_capacity_asic0 = """\
Monitored fabric capacity threshold: 100%

  ASIC    Operating     Total #     %    Last Event    Last Time
              Links    of Links
------  -----------  ----------  ----  ------------  -----------
 asic0            5           8  62.5          None        Never
"""

multi_asic_fabric_isolation = """\

asic0
  Local Link    Auto Isolated    Manual Isolated    Isolated
------------  ---------------  -----------------  ----------
           0                0                  0           0
           2                0                  0           0
           4                0                  0           0
           6                0                  0           0
           7                0                  0           0

asic1
  Local Link    Auto Isolated    Manual Isolated    Isolated
------------  ---------------  -----------------  ----------
           0                0                  0           0
           4                0                  0           0
"""

multi_asic_fabric_isolation_asic0 = """\

asic0
  Local Link    Auto Isolated    Manual Isolated    Isolated
------------  ---------------  -----------------  ----------
           0                0                  0           0
           2                0                  0           0
           4                0                  0           0
           6                0                  0           0
           7                0                  0           0
"""

class TestFabricStat(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_single_show_fabric_counters(self):
        return_code, result = get_result_and_return_code(['fabricstat', '-D'])
        assert return_code == 0

        return_code, result = get_result_and_return_code(['fabricstat'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_fabric_counters_asic0

    def test_single_clear_fabric_counters(self):
        return_code, result = get_result_and_return_code(['fabricstat', '-C'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result.rstrip() == clear_counter

        return_code, result = get_result_and_return_code(['fabricstat'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_fabric_counters_asic0_clear

        return_code, result = get_result_and_return_code(['fabricstat', '-D'])
        assert return_code == 0

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(
            os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""


class TestMultiAsicFabricStat(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"

    def test_multi_show_fabric_counters(self):
        return_code, result = get_result_and_return_code(['fabricstat'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_fabric_counters

    def test_multi_show_fabric_counters_asic(self):
        return_code, result = get_result_and_return_code(['fabricstat', '-n', 'asic0'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_fabric_counters_asic0

    def test_multi_asic_invalid_asic(self):
        return_code, result = get_result_and_return_code(['fabricstat', '-n', 'asic99'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 1
        assert result == fabric_invalid_asic_error

    def test_multi_show_fabric_counters_queue(self):
        return_code, result = get_result_and_return_code(['fabricstat', '-q'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_fabric_counters_queue

    def test_multi_show_fabric_counters_queue_asic(self):
        return_code, result = get_result_and_return_code(['fabricstat', '-q', '-n', 'asic0'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_fabric_counters_queue_asic0

    def test_multi_show_fabric_counters_queue_clear(self):
        return_code, result = get_result_and_return_code(['fabricstat', '-C', '-q'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0

        return_code, result = get_result_and_return_code(['fabricstat', '-q', '-n', 'asic0'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_fabric_counters_queue_asic0_clear

        return_code, result = get_result_and_return_code(['fabricstat', '-D'])
        assert return_code == 0

        return_code, result = get_result_and_return_code(['fabricstat', '-q', '-n', 'asic0'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_fabric_counters_queue_asic0

    def test_multi_show_fabric_reachability(self):
        return_code, result = get_result_and_return_code(['fabricstat', '-r'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_fabric_reachability

    def test_multi_show_fabric_reachability_asic(self):
        return_code, result = get_result_and_return_code(['fabricstat', '-r', '-n', 'asic0'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_fabric_reachability_asic0

    def test_mutli_show_fabric_capacity(self):
        return_code, result = get_result_and_return_code(['fabricstat', '-c'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_fabric_capacity

    def test_multi_show_fabric_capacity_asic(self):
        return_code, result = get_result_and_return_code(['fabricstat', '-c', '-n', 'asic0'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_fabric_capacity_asic0

    def test_multi_show_fabric_isolation(self):
        return_code, result = get_result_and_return_code(['fabricstat', '-i'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_fabric_isolation

    def test_multi_show_fabric_isolation_asic(self):
        return_code, result = get_result_and_return_code(['fabricstat', '-i', '-n', 'asic0'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == multi_asic_fabric_isolation_asic0

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(
            os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""


class TestMultiAsicFabricStatCmd(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"

    def test_clear_command(self):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands["fabriccountersqueue"], [])
        assert result.exit_code == 0

        result = runner.invoke(clear.cli.commands["fabriccountersport"], [])
        assert result.exit_code == 0

        return_code, result = get_result_and_return_code(['fabricstat', '-D'])
        assert return_code == 0

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(
            os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""

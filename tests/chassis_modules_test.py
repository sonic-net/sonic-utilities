import sys
import os
from click.testing import CliRunner

import show.main as show
import config.main as config
import tests.mock_tables.dbconnector
from utilities_common.db import Db
from .utils import get_result_and_return_code

show_linecard0_shutdown_output="""\
LINE-CARD0 line-card 1 Empty down LC1000101
"""

show_linecard0_startup_output="""\
LINE-CARD0 line-card 1 Empty up LC1000101
"""
header_lines = 2
warning_lines = 0

show_chassis_modules_output="""\
        Name      Description    Physical-Slot    Oper-Status    Admin-Status     Serial
------------  ---------------  ---------------  -------------  --------------  ---------
FABRIC-CARD0      fabric-card               17         Online              up  FC1000101
FABRIC-CARD1      fabric-card               18        Offline              up  FC1000102
  LINE-CARD0        line-card                1          Empty              up  LC1000101
  LINE-CARD1        line-card                2         Online            down  LC1000102
 SUPERVISOR0  supervisor-card               16         Online              up  RP1000101
"""

show_chassis_midplane_output="""\
      Name     IP-Address    Reachability
----------  -------------  --------------
LINE-CARD0  192.168.1.100            True
LINE-CARD1    192.168.1.2           False
LINE-CARD2    192.168.1.1            True
"""

show_chassis_system_ports_output_asic0="""\
            System Port Name    Port Id    Switch Id    Core    Core Port    Speed
----------------------------  ---------  -----------  ------  -----------  -------
   Linecard1|Asic0|Ethernet0          1            0       0            1     100G
Linecard1|Asic0|Ethernet-IB0         13            0       1            6      10G
  Linecard1|Asic1|Ethernet12         65            2       0            1     100G
  Linecard1|Asic2|Ethernet24        129            4       0            1     100G
   Linecard2|Asic0|Ethernet0        193            6       0            1     100G
"""

show_chassis_system_ports_output_1_asic0="""\
         System Port Name    Port Id    Switch Id    Core    Core Port    Speed
-------------------------  ---------  -----------  ------  -----------  -------
Linecard1|Asic0|Ethernet0          1            0       0            1     100G
"""

show_chassis_system_neighbors_output_all="""\
          System Port Interface    Neighbor                MAC    Encap Index
-------------------------------  ----------  -----------------  -------------
      Linecard2|Asic0|Ethernet4    10.0.0.5  b6:8c:4f:18:67:ff     1074790406
      Linecard2|Asic0|Ethernet4     fc00::a  b6:8c:4f:18:67:ff     1074790407
   Linecard2|Asic0|Ethernet-IB0     3.3.3.4  24:21:24:05:81:f7     1074790404
   Linecard2|Asic0|Ethernet-IB0   3333::3:4  24:21:24:05:81:f7     1074790405
Linecard2|Asic1|PortChannel0002    10.0.0.1  26:8b:37:fa:8e:67     1074790406
Linecard2|Asic1|PortChannel0002     fc00::2  26:8b:37:fa:8e:67     1074790407
      Linecard4|Asic0|Ethernet5   10.0.0.11  46:c3:71:8c:dd:2d     1074790406
      Linecard4|Asic0|Ethernet5    fc00::16  46:c3:71:8c:dd:2d     1074790407
"""

show_chassis_system_neighbors_output_ipv4="""\
    System Port Interface    Neighbor                MAC    Encap Index
-------------------------  ----------  -----------------  -------------
Linecard2|Asic0|Ethernet4    10.0.0.5  b6:8c:4f:18:67:ff     1074790406
"""

show_chassis_system_neighbors_output_ipv6="""\
    System Port Interface    Neighbor                MAC    Encap Index
-------------------------  ----------  -----------------  -------------
Linecard4|Asic0|Ethernet5    fc00::16  46:c3:71:8c:dd:2d     1074790407
"""

show_chassis_system_neighbors_output_asic0="""\
       System Port Interface    Neighbor                MAC    Encap Index
----------------------------  ----------  -----------------  -------------
   Linecard2|Asic0|Ethernet4    10.0.0.5  b6:8c:4f:18:67:ff     1074790406
   Linecard2|Asic0|Ethernet4     fc00::a  b6:8c:4f:18:67:ff     1074790407
Linecard2|Asic0|Ethernet-IB0     3.3.3.4  24:21:24:05:81:f7     1074790404
Linecard2|Asic0|Ethernet-IB0   3333::3:4  24:21:24:05:81:f7     1074790405
   Linecard4|Asic0|Ethernet5   10.0.0.11  46:c3:71:8c:dd:2d     1074790406
   Linecard4|Asic0|Ethernet5    fc00::16  46:c3:71:8c:dd:2d     1074790407
"""

show_chassis_system_lags_output="""\
                System Lag Name    Lag Id    Switch Id                                     Member System Ports
-------------------------------  --------  -----------  ------------------------------------------------------
Linecard2|Asic1|PortChannel0002         1            8  Linecard2|Asic1|Ethernet16, Linecard2|Asic1|Ethernet17
Linecard4|Asic2|PortChannel0001         2           22  Linecard4|Asic2|Ethernet29, Linecard4|Asic2|Ethernet30
"""

show_chassis_system_lags_output_1="""\
                System Lag Name    Lag Id    Switch Id                                     Member System Ports
-------------------------------  --------  -----------  ------------------------------------------------------
Linecard4|Asic2|PortChannel0001         2           22  Linecard4|Asic2|Ethernet29, Linecard4|Asic2|Ethernet30
"""

show_chassis_system_lags_output_asic1="""\
                System Lag Name    Lag Id    Switch Id                                     Member System Ports
-------------------------------  --------  -----------  ------------------------------------------------------
Linecard2|Asic1|PortChannel0002         1            8  Linecard2|Asic1|Ethernet16, Linecard2|Asic1|Ethernet17
"""

show_chassis_system_lags_output_lc4="""\
                System Lag Name    Lag Id    Switch Id                                     Member System Ports
-------------------------------  --------  -----------  ------------------------------------------------------
Linecard4|Asic2|PortChannel0001         2           22  Linecard4|Asic2|Ethernet29, Linecard4|Asic2|Ethernet30
"""

class TestChassisModules(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_show_and_verify_output(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["chassis"].commands["modules"].commands["status"], [])
        print(result.output)
        assert(result.output == show_chassis_modules_output)

    def test_show_all_count_lines(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["chassis"].commands["modules"].commands["status"], [])
        print(result.output)
        result_lines = result.output.strip('\n').split('\n')
        modules = ["FABRIC-CARD0", "FABRIC-CARD1", "LINE-CARD0", "LINE-CARD1", "SUPERVISOR0"]
        for i, module in enumerate(modules):
            assert module in result_lines[i + warning_lines + header_lines]
        assert len(result_lines) == warning_lines + header_lines + len(modules)

    def test_show_single_count_lines(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["chassis"].commands["modules"].commands["status"], ["LINE-CARD0"])
        print(result.output)
        result_lines = result.output.strip('\n').split('\n')
        modules = ["LINE-CARD0"]
        for i, module in enumerate(modules):
            assert module in result_lines[i+header_lines]
        assert len(result_lines) == header_lines + len(modules)

    def test_show_module_down(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["chassis"].commands["modules"].commands["status"], ["LINE-CARD1"])
        result_lines = result.output.strip('\n').split('\n')
        assert result.exit_code == 0
        result_out = (result_lines[header_lines]).split()
        assert result_out[4] == 'down'

    def test_show_incorrect_command(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["chassis"].commands["modules"], [])
        print(result.output)
        print(result.exit_code)
        assert result.exit_code == 0

    def test_show_incorrect_module(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["chassis"].commands["modules"].commands["status"], ["TEST-CARD1"])
        print(result.output)
        print(result.exit_code)
        assert result.exit_code == 0

    def test_config_shutdown_module(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(config.config.commands["chassis"].commands["modules"].commands["shutdown"], ["LINE-CARD0"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(show.cli.commands["chassis"].commands["modules"].commands["status"], ["LINE-CARD0"], obj=db)
        print(result.exit_code)
        print(result.output)
        result_lines = result.output.strip('\n').split('\n')
        assert result.exit_code == 0
        header_lines = 2
        result_out = " ".join((result_lines[header_lines]).split())
        assert result_out.strip('\n') == show_linecard0_shutdown_output.strip('\n')
        #db.cfgdb.set_entry("CHASSIS_MODULE", "LINE-CARD0", { "admin_status" : "down" })
        #db.get_data("CHASSIS_MODULE", "LINE-CARD0")

    def test_config_startup_module(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(config.config.commands["chassis"].commands["modules"].commands["startup"], ["LINE-CARD0"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(show.cli.commands["chassis"].commands["modules"].commands["status"], ["LINE-CARD0"], obj=db)
        print(result.exit_code)
        print(result.output)
        result_lines = result.output.strip('\n').split('\n')
        assert result.exit_code == 0
        result_out = " ".join((result_lines[header_lines]).split())
        assert result_out.strip('\n') == show_linecard0_startup_output.strip('\n')

    def test_config_incorrect_module(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(config.config.commands["chassis"].commands["modules"].commands["shutdown"], ["TEST-CARD0"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0

    def test_show_and_verify_midplane_output(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["chassis"].commands["modules"].commands["midplane-status"], [])
        print(result.output)
        assert(result.output == show_chassis_midplane_output)

    def test_midplane_show_all_count_lines(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["chassis"].commands["modules"].commands["midplane-status"], [])
        print(result.output)
        result_lines = result.output.strip('\n').split('\n')
        modules = ["LINE-CARD0", "LINE-CARD1", "LINE-CARD2"]
        for i, module in enumerate(modules):
            assert module in result_lines[i + warning_lines + header_lines]
        assert len(result_lines) == warning_lines + header_lines + len(modules)

    def test_midplane_show_single_count_lines(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["chassis"].commands["modules"].commands["midplane-status"], ["LINE-CARD0"])
        print(result.output)
        result_lines = result.output.strip('\n').split('\n')
        modules = ["LINE-CARD0"]
        for i, module in enumerate(modules):
            assert module in result_lines[i+header_lines]
        assert len(result_lines) == header_lines + len(modules)

    def test_midplane_show_module_down(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["chassis"].commands["modules"].commands["midplane-status"], ["LINE-CARD1"])
        print(result.output)
        result_lines = result.output.strip('\n').split('\n')
        assert result.exit_code == 0
        result_out = (result_lines[header_lines]).split()
        print(result_out)
        assert result_out[2] == 'False'

    def test_midplane_show_incorrect_module(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["chassis"].commands["modules"].commands["midplane-status"], ["TEST-CARD1"])
        print(result.output)
        print(result.exit_code)
        assert result.exit_code == 0

    def test_show_and_verify_system_ports_output_asic0(self):
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        return_code, result = get_result_and_return_code(['voqutil', '-c', 'system_ports', '-n', 'asic0'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_chassis_system_ports_output_asic0

    def test_show_and_verify_system_ports_output_1_asic0(self):
        return_code, result = get_result_and_return_code(['voqutil', '-c', 'system_ports', '-i', "Linecard1|Asic0|Ethernet0", '-n', 'asic0'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_chassis_system_ports_output_1_asic0
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""

    def test_show_and_verify_system_neighbors_output_all(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["chassis"].commands["system-neighbors"], [])
        print(result.output)
        assert(result.output == show_chassis_system_neighbors_output_all)

    def test_show_and_verify_system_neighbors_output_ipv4(self):
        return_code, result = get_result_and_return_code(['voqutil', '-c', 'system_neighbors', '-a', '10.0.0.5'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_chassis_system_neighbors_output_ipv4

    def test_show_and_verify_system_neighbors_output_ipv6(self):
        return_code, result = get_result_and_return_code(['voqutil', '-c', 'system_neighbors', '-a', 'fc00::16'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_chassis_system_neighbors_output_ipv6

    def test_show_and_verify_system_neighbors_output_asic0(self):
        return_code, result = get_result_and_return_code(['voqutil', '-c', 'system_neighbors', '-n', 'Asic0'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_chassis_system_neighbors_output_asic0

    def test_show_and_verify_system_lags_output(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["chassis"].commands["system-lags"], [])
        print(result.output)
        assert(result.output == show_chassis_system_lags_output)

    def test_show_and_verify_system_lags_output_1(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["chassis"].commands["system-lags"], ["""Linecard4|Asic2|PortChannel0001"""])
        print(result.output)
        assert(result.output == show_chassis_system_lags_output_1)

    def test_show_and_verify_system_lags_output_asic1(self):
        return_code, result = get_result_and_return_code(['voqutil', '-c', 'system_lags', '-n', 'Asic1'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_chassis_system_lags_output_asic1

    def test_show_and_verify_system_lags_output_lc4(self):
        return_code, result = get_result_and_return_code(['voqutil', '-c', 'system_lags', '-l', 'Linecard4'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_chassis_system_lags_output_lc4

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

import sys
import os
from click.testing import CliRunner
from datetime import datetime, timedelta
from config.chassis_modules import (
    set_state_transition_in_progress,
    is_transition_timed_out,
    TRANSITION_TIMEOUT
)

import show.main as show
import config.main as config
import tests.mock_tables.dbconnector
from utilities_common.db import Db
from .utils import get_result_and_return_code
from unittest import mock
sys.modules['clicommon'] = mock.Mock()

show_linecard0_shutdown_output="""\
LINE-CARD0 line-card 1 Empty down LC1000101
"""

show_linecard0_startup_output="""\
LINE-CARD0 line-card 1 Empty up LC1000101
"""

show_fabriccard0_shutdown_output = """\
FABRIC-CARD0 fabric-card 17 Online down FC1000101
"""

show_fabriccard0_startup_output = """\
FABRIC-CARD0 fabric-card 17 Online up FC1000101
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


def mock_run_command_side_effect(*args, **kwargs):
    print("command: {}".format(*args))
    if isinstance(*args, list):
        return '', 0
    else:
        print("Expected type of command is list. Actual type is {}".format(*args))
        assert 0
        return '', 0


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

    def test_config_shutdown_module_fabric(self):
        with mock.patch("utilities_common.cli.run_command",
                        mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            runner = CliRunner()
            db = Db()

            chassisdb = db.db
            chassisdb.connect("CHASSIS_STATE_DB")
            chassisdb.set("CHASSIS_STATE_DB", "CHASSIS_FABRIC_ASIC_TABLE|asic6", "asic_id_in_module", "0")
            chassisdb.set("CHASSIS_STATE_DB", "CHASSIS_FABRIC_ASIC_TABLE|asic6", "asic_pci_address", "nokia-bdb:4:0")
            chassisdb.set("CHASSIS_STATE_DB", "CHASSIS_FABRIC_ASIC_TABLE|asic6", "name", "FABRIC-CARD0")
            chassisdb.set("CHASSIS_STATE_DB", "CHASSIS_FABRIC_ASIC_TABLE|asic7", "asic_id_in_module", "1")
            chassisdb.set("CHASSIS_STATE_DB", "CHASSIS_FABRIC_ASIC_TABLE|asic7", "asic_pci_address", "nokia-bdb:4:1")
            chassisdb.set("CHASSIS_STATE_DB", "CHASSIS_FABRIC_ASIC_TABLE|asic7", "name", "FABRIC-CARD0")
            chassisdb.close("CHASSIS_STATE_DB")

            result = runner.invoke(config.config.commands["chassis"].commands["modules"].commands["shutdown"],
                                   ["FABRIC-CARD0"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0

            result = runner.invoke(show.cli.commands["chassis"].commands["modules"].commands["status"],
                                   ["FABRIC-CARD0"], obj=db)
            print(result.exit_code)
            print(result.output)
            result_lines = result.output.strip('\n').split('\n')
            assert result.exit_code == 0
            header_lines = 2
            result_out = " ".join((result_lines[header_lines]).split())
            assert result_out.strip('\n') == show_fabriccard0_shutdown_output.strip('\n')

            fvs = {'admin_status': 'down'}
            db.cfgdb.set_entry('CHASSIS_MODULE', "FABRIC-CARD0", fvs)
            result = runner.invoke(config.config.commands["chassis"].commands["modules"].commands["shutdown"],
                                   ["FABRIC-CARD0"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 6

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

    def test_config_startup_module_fabric(self):
        with mock.patch("utilities_common.cli.run_command",
                        mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            runner = CliRunner()
            db = Db()

            chassisdb = db.db
            chassisdb.connect("CHASSIS_STATE_DB")
            chassisdb.set("CHASSIS_STATE_DB", "CHASSIS_FABRIC_ASIC_TABLE|asic6", "asic_id_in_module", "0")
            chassisdb.set("CHASSIS_STATE_DB", "CHASSIS_FABRIC_ASIC_TABLE|asic6", "asic_pci_address", "nokia-bdb:4:0")
            chassisdb.set("CHASSIS_STATE_DB", "CHASSIS_FABRIC_ASIC_TABLE|asic6", "name", "FABRIC-CARD0")
            chassisdb.set("CHASSIS_STATE_DB", "CHASSIS_FABRIC_ASIC_TABLE|asic7", "asic_id_in_module", "1")
            chassisdb.set("CHASSIS_STATE_DB", "CHASSIS_FABRIC_ASIC_TABLE|asic7", "asic_pci_address", "nokia-bdb:4:1")
            chassisdb.set("CHASSIS_STATE_DB", "CHASSIS_FABRIC_ASIC_TABLE|asic7", "name", "FABRIC-CARD0")
            chassisdb.close("CHASSIS_STATE_DB")

            # FC is down and doing startup
            fvs = {'admin_status': 'down'}
            db.cfgdb.set_entry('CHASSIS_MODULE', "FABRIC-CARD0", fvs)

            result = runner.invoke(config.config.commands["chassis"].commands["modules"].commands["startup"],
                                   ["FABRIC-CARD0"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0

            result = runner.invoke(show.cli.commands["chassis"].commands["modules"].commands["status"],
                                   ["FABRIC-CARD0"], obj=db)
            print(result.exit_code)
            print(result.output)
            result_lines = result.output.strip('\n').split('\n')
            assert result.exit_code == 0
            result_out = " ".join((result_lines[header_lines]).split())
            assert result_out.strip('\n') == show_fabriccard0_startup_output.strip('\n')
            assert mock_run_command.call_count == 2

            # FC is up and doing startup
            fvs = {'admin_status': 'up'}
            db.cfgdb.set_entry('CHASSIS_MODULE', "FABRIC-CARD0", fvs)

            result = runner.invoke(config.config.commands["chassis"].commands["modules"].commands["startup"],
                                   ["FABRIC-CARD0"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0

            result = runner.invoke(show.cli.commands["chassis"].commands["modules"].commands["status"],
                                   ["FABRIC-CARD0"], obj=db)
            print(result.exit_code)
            print(result.output)
            result_lines = result.output.strip('\n').split('\n')
            assert result.exit_code == 0
            result_out = " ".join((result_lines[header_lines]).split())
            assert result_out.strip('\n') == show_fabriccard0_startup_output.strip('\n')
            assert mock_run_command.call_count == 2

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

    def test_shutdown_triggers_transition_tracking(self):
        with mock.patch("config.chassis_modules.is_smartswitch", return_value=True), \
             mock.patch("config.chassis_modules.get_config_module_state", return_value='up'):

            runner = CliRunner()
            db = Db()
            result = runner.invoke(
                config.config.commands["chassis"].commands["modules"].commands["shutdown"],
                ["DPU0"],
                obj=db
            )
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0

            # Check CONFIG_DB for admin_status
            cfg_fvs = db.cfgdb.get_entry("CHASSIS_MODULE", "DPU0")
            admin_status = cfg_fvs.get("admin_status")
            print(f"admin_status: {admin_status}")
            assert admin_status == "down"

            # Check STATE_DB for transition flags
            state_fvs = db.db.get_all("STATE_DB", "CHASSIS_MODULE_TABLE|DPU0")
            transition_flag = state_fvs.get("state_transition_in_progress")
            transition_time = state_fvs.get("transition_start_time")

            print(f"state_transition_in_progress: {transition_flag}")
            print(f"transition_start_time: {transition_time}")

            assert transition_flag == "True"
            assert transition_time is not None

    def test_shutdown_triggers_transition_in_progress(self):
        with mock.patch("config.chassis_modules.is_smartswitch", return_value=True), \
             mock.patch("config.chassis_modules.get_config_module_state", return_value='up'):

            runner = CliRunner()
            db = Db()

            fvs = {
                'admin_status': 'up',
                'state_transition_in_progress': 'True',
                'transition_start_time': datetime.utcnow().isoformat()
            }
            db.cfgdb.set_entry('CHASSIS_MODULE', "DPU0", fvs)

            result = runner.invoke(
                config.config.commands["chassis"].commands["modules"].commands["shutdown"],
                ["DPU0"],
                obj=db
            )
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0

            fvs = db.db.get_all("STATE_DB", "CHASSIS_MODULE_TABLE|DPU0")
            print(f"state_transition_in_progress:{fvs['state_transition_in_progress']}")
            print(f"transition_start_time:{fvs['transition_start_time']}")

    def test_shutdown_triggers_transition_timeout(self):
        with mock.patch("config.chassis_modules.is_smartswitch", return_value=True), \
             mock.patch("config.chassis_modules.get_config_module_state", return_value='up'):

            runner = CliRunner()
            db = Db()

            fvs = {
                'admin_status': 'up',
                'state_transition_in_progress': 'True',
                'transition_start_time': (datetime.utcnow() - timedelta(minutes=30)).isoformat()
            }
            db.cfgdb.set_entry('CHASSIS_MODULE', "DPU0", fvs)

            result = runner.invoke(
                config.config.commands["chassis"].commands["modules"].commands["shutdown"],
                ["DPU0"],
                obj=db
            )
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0

            fvs = db.db.get_all("STATE_DB", "CHASSIS_MODULE_TABLE|DPU0")
            print(f"state_transition_in_progress:{fvs['state_transition_in_progress']}")
            print(f"transition_start_time:{fvs['transition_start_time']}")

    def test_startup_triggers_transition_tracking(self):
        with mock.patch("config.chassis_modules.is_smartswitch", return_value=True), \
             mock.patch("config.chassis_modules.get_config_module_state", return_value='down'):

            runner = CliRunner()
            db = Db()
            result = runner.invoke(
                config.config.commands["chassis"].commands["modules"].commands["startup"],
                ["DPU0"],
                obj=db
            )
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0

            fvs = db.db.get_all("STATE_DB", "CHASSIS_MODULE_TABLE|DPU0")
            print(f"state_transition_in_progress:{fvs['state_transition_in_progress']}")
            print(f"transition_start_time:{fvs['transition_start_time']}")

    def test_set_state_transition_in_progress_sets_and_removes_timestamp(self):
        db = mock.MagicMock()
        db.statedb = mock.MagicMock()

        # Case 1: Set to 'True' adds timestamp
        db.statedb.get_entry.return_value = {}
        set_state_transition_in_progress(db, "DPU0", "True")
        args = db.statedb.set_entry.call_args[0]
        updated_entry = args[2]
        assert updated_entry["state_transition_in_progress"] == "True"
        assert "transition_start_time" in updated_entry

        # Case 2: Set to 'False' removes timestamp
        db.statedb.get_entry.return_value = {
            "state_transition_in_progress": "True",
            "transition_start_time": "2025-05-01T01:00:00"
        }
        set_state_transition_in_progress(db, "DPU0", "False")
        args = db.statedb.set_entry.call_args[0]
        updated_entry = args[2]
        assert updated_entry["state_transition_in_progress"] == "False"
        assert "transition_start_time" not in updated_entry

    def test_is_transition_timed_out_all_paths(self):
        db = mock.MagicMock()
        db.statedb = mock.MagicMock()

        # Case 1: No entry
        db.statedb.get_entry.return_value = None
        assert is_transition_timed_out(db, "DPU0") is False

        # Case 2: No transition_start_time
        db.statedb.get_entry.return_value = {"state_transition_in_progress": "True"}
        assert is_transition_timed_out(db, "DPU0") is False

        # Case 3: Invalid format
        db.statedb.get_entry.return_value = {"transition_start_time": "not-a-date"}
        assert is_transition_timed_out(db, "DPU0") is False

        # Case 4: Timed out
        old_time = (datetime.utcnow() - TRANSITION_TIMEOUT - timedelta(seconds=1)).isoformat()
        db.statedb.get_entry.return_value = {"transition_start_time": old_time}
        assert is_transition_timed_out(db, "DPU0") is True

        # Case 5: Not timed out yet
        now = datetime.utcnow().isoformat()
        db.statedb.get_entry.return_value = {"transition_start_time": now}
        assert is_transition_timed_out(db, "DPU0") is False

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

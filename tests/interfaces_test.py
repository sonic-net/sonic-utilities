import os
import traceback

from click.testing import CliRunner
from unittest import mock
from utilities_common.intf_filter import parse_interface_in_filter

import show.main as show

show_interfaces_alias_output="""\
Name         Alias
-----------  -------
Ethernet0    etp1
Ethernet4    etp2
Ethernet8    etp3
Ethernet12   etp4
Ethernet16   etp5
Ethernet20   etp6
Ethernet24   etp7
Ethernet28   etp8
Ethernet32   etp9
Ethernet36   etp10
Ethernet40   etp11
Ethernet44   etp12
Ethernet48   etp13
Ethernet52   etp14
Ethernet56   etp15
Ethernet60   etp16
Ethernet64   etp17
Ethernet68   etp18
Ethernet72   etp19
Ethernet76   etp20
Ethernet80   etp21
Ethernet84   etp22
Ethernet88   etp23
Ethernet92   etp24
Ethernet96   etp25
Ethernet100  etp26
Ethernet104  etp27
Ethernet108  etp28
Ethernet112  etp29
Ethernet116  etp30
Ethernet120  etp31
Ethernet124  etp32
"""

show_interfaces_alias_Ethernet0_output="""\
Name       Alias
---------  -------
Ethernet0  etp1
"""

show_interfaces_neighbor_expected_output="""\
LocalPort    Neighbor    NeighborPort    NeighborLoopback    NeighborMgmt    NeighborType
-----------  ----------  --------------  ------------------  --------------  --------------
Ethernet112  ARISTA01T1  Ethernet1       None                10.250.0.51     LeafRouter
Ethernet116  ARISTA02T1  Ethernet1       None                10.250.0.52     LeafRouter
Ethernet120  ARISTA03T1  Ethernet1       None                10.250.0.53     LeafRouter
Ethernet124  ARISTA04T1  Ethernet1       None                10.250.0.54     LeafRouter
"""

show_interfaces_neighbor_expected_output_t1="""\
LocalPort    Neighbor    NeighborPort    NeighborLoopback    NeighborMgmt    NeighborType
-----------  ----------  --------------  ------------------  --------------  --------------
Ethernet0    ARISTA01T2  Ethernet1       None                172.16.137.56   SpineRouter
Ethernet4    ARISTA01T2  Ethernet2       None                172.16.137.56   SpineRouter
Ethernet8    ARISTA03T2  Ethernet1       None                172.16.137.57   SpineRouter
Ethernet12   ARISTA03T2  Ethernet2       None                172.16.137.57   SpineRouter
Ethernet16   ARISTA05T2  Ethernet1       None                172.16.137.58   SpineRouter
Ethernet20   ARISTA05T2  Ethernet2       None                172.16.137.58   SpineRouter
Ethernet24   ARISTA07T2  Ethernet1       None                172.16.137.59   SpineRouter
Ethernet28   ARISTA07T2  Ethernet2       None                172.16.137.59   SpineRouter
Ethernet32   ARISTA09T2  Ethernet1       None                172.16.137.60   SpineRouter
Ethernet36   ARISTA09T2  Ethernet2       None                172.16.137.60   SpineRouter
Ethernet40   ARISTA11T2  Ethernet1       None                172.16.137.61   SpineRouter
Ethernet44   ARISTA11T2  Ethernet2       None                172.16.137.61   SpineRouter
Ethernet48   ARISTA13T2  Ethernet1       None                172.16.137.62   SpineRouter
Ethernet52   ARISTA13T2  Ethernet2       None                172.16.137.62   SpineRouter
Ethernet56   ARISTA15T2  Ethernet1       None                172.16.137.63   SpineRouter
Ethernet60   ARISTA15T2  Ethernet2       None                172.16.137.63   SpineRouter
Ethernet64   ARISTA01T0  Ethernet1       None                172.16.137.64   ToRRouter
Ethernet68   ARISTA02T0  Ethernet1       None                172.16.137.65   ToRRouter
Ethernet72   ARISTA03T0  Ethernet1       None                172.16.137.66   ToRRouter
Ethernet76   ARISTA04T0  Ethernet1       None                172.16.137.67   ToRRouter
Ethernet80   ARISTA05T0  Ethernet1       None                172.16.137.68   ToRRouter
Ethernet84   ARISTA06T0  Ethernet1       None                172.16.137.69   ToRRouter
Ethernet88   ARISTA07T0  Ethernet1       None                172.16.137.70   ToRRouter
Ethernet92   ARISTA08T0  Ethernet1       None                172.16.137.71   ToRRouter
Ethernet96   ARISTA09T0  Ethernet1       None                172.16.137.72   ToRRouter
Ethernet100  ARISTA10T0  Ethernet1       None                172.16.137.73   ToRRouter
Ethernet104  ARISTA11T0  Ethernet1       None                172.16.137.74   ToRRouter
Ethernet108  ARISTA12T0  Ethernet1       None                172.16.137.75   ToRRouter
Ethernet112  ARISTA13T0  Ethernet1       None                172.16.137.76   ToRRouter
Ethernet116  ARISTA14T0  Ethernet1       None                172.16.137.77   ToRRouter
Ethernet120  ARISTA15T0  Ethernet1       None                172.16.137.78   ToRRouter
Ethernet124  ARISTA16T0  Ethernet1       None                172.16.137.79   ToRRouter
"""

show_interfaces_neighbor_expected_output_Ethernet112="""\
LocalPort    Neighbor    NeighborPort    NeighborLoopback    NeighborMgmt    NeighborType
-----------  ----------  --------------  ------------------  --------------  --------------
Ethernet112  ARISTA01T1  Ethernet1       None                10.250.0.51     LeafRouter
"""

show_interfaces_neighbor_expected_output_t1_Ethernet0="""\
LocalPort    Neighbor    NeighborPort    NeighborLoopback    NeighborMgmt    NeighborType
-----------  ----------  --------------  ------------------  --------------  --------------
Ethernet0    ARISTA01T2  Ethernet1       None                172.16.137.56   SpineRouter
"""

show_interfaces_neighbor_expected_output_etp29="""\
LocalPort    Neighbor    NeighborPort    NeighborLoopback    NeighborMgmt    NeighborType
-----------  ----------  --------------  ------------------  --------------  --------------
etp29        ARISTA01T1  Ethernet1       None                10.250.0.51     LeafRouter
"""

show_interfaces_neighbor_expected_output_t1_Ethernet1_1="""\
LocalPort    Neighbor    NeighborPort    NeighborLoopback    NeighborMgmt    NeighborType
-----------  ----------  --------------  ------------------  --------------  --------------
Ethernet1/1  ARISTA01T2  Ethernet1       None                172.16.137.56   SpineRouter
"""

show_interfaces_portchannel_output="""\
Flags: A - active, I - inactive, Up - up, Dw - Down, N/A - not available,
       S - selected, D - deselected, * - not synced
  No.  Team Dev         Protocol     Ports
-----  ---------------  -----------  --------------
 0001  PortChannel0001  LACP(A)(Dw)  Ethernet112(D)
 0002  PortChannel0002  LACP(A)(Up)  Ethernet116(S)
 0003  PortChannel0003  LACP(A)(Up)  Ethernet120(S)
 0004  PortChannel0004  LACP(A)(Up)  N/A
 1001  PortChannel1001  N/A
"""

show_interfaces_portchannel_in_alias_mode_output="""\
Flags: A - active, I - inactive, Up - up, Dw - Down, N/A - not available,
       S - selected, D - deselected, * - not synced
  No.  Team Dev         Protocol     Ports
-----  ---------------  -----------  --------
 0001  PortChannel0001  LACP(A)(Dw)  etp29(D)
 0002  PortChannel0002  LACP(A)(Up)  etp30(S)
 0003  PortChannel0003  LACP(A)(Up)  etp31(S)
 0004  PortChannel0004  LACP(A)(Up)  N/A
 1001  PortChannel1001  N/A
"""

class TestInterfaces(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")

    def test_show_interfaces(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    def test_show_interfaces_alias(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["alias"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_interfaces_alias_output

    def test_show_interfaces_alias_Ethernet0(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["alias"], ["Ethernet0"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_interfaces_alias_Ethernet0_output

    def test_show_interfaces_alias_etp1(self):
        runner = CliRunner()
        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["interfaces"].commands["alias"], ["etp1"])
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_interfaces_alias_Ethernet0_output

    def test_show_interfaces_alias_invalid_name(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["alias"], ["Ethernet3"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Invalid interface name Ethernet3" in result.output

    def test_show_interfaces_naming_mode_default(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["naming_mode"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output.rstrip() == "default"

    def test_show_interfaces_naming_mode_alias(self):
        runner = CliRunner()
        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["interfaces"].commands["naming_mode"], [])
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output.rstrip() == "alias"

    def test_show_interfaces_neighbor_expected(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["neighbor"].commands["expected"], [])
        print(result.exit_code)
        print(result.output)
        # traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0
        assert result.output == show_interfaces_neighbor_expected_output

    def test_show_interfaces_neighbor_expected_t1(self, setup_t1_topo):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["neighbor"].commands["expected"], [])
        print(result.exit_code)
        print(result.output)
        # traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0
        assert result.output == show_interfaces_neighbor_expected_output_t1

    def test_show_interfaces_neighbor_expected_Ethernet112(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["neighbor"].commands["expected"], ["Ethernet112"])
        print(result.exit_code)
        print(result.output)
        # traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0
        assert result.output == show_interfaces_neighbor_expected_output_Ethernet112

    def test_show_interfaces_neighbor_expected_t1_Ethernet0(self, setup_t1_topo):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["neighbor"].commands["expected"], ["Ethernet0"])
        print(result.exit_code)
        print(result.output)
        # traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0
        assert result.output == show_interfaces_neighbor_expected_output_t1_Ethernet0

    def test_show_interfaces_neighbor_expected_etp29(self):
        runner = CliRunner()
        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["interfaces"].commands["neighbor"].commands["expected"], ["etp29"])
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        print(result.exit_code)
        print(result.output)
        # traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0
        assert result.output == show_interfaces_neighbor_expected_output_etp29

    def test_show_interfaces_neighbor_expected_t1_Ethernet1_1(self, setup_t1_topo):
        runner = CliRunner()
        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["interfaces"].commands["neighbor"].commands["expected"], ["Ethernet1/1"])
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        print(result.exit_code)
        print(result.output)
        # traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0
        assert result.output == show_interfaces_neighbor_expected_output_t1_Ethernet1_1

    def test_show_interfaces_neighbor_expected_Ethernet0(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["neighbor"].commands["expected"], ["Ethernet0"])
        print(result.exit_code)
        print(result.output)
        # traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0
        assert result.output.rstrip() == "No neighbor information available for interface Ethernet0"

    def test_show_interfaces_portchannel(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["portchannel"], [])
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0
        assert result.output == show_interfaces_portchannel_output

    def test_show_interfaces_portchannel_in_alias_mode(self):
        runner = CliRunner()
        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["interfaces"].commands["portchannel"], [])
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0
        assert result.output == show_interfaces_portchannel_in_alias_mode_output
       
    @mock.patch('sonic_py_common.multi_asic.get_port_table', mock.MagicMock(return_value={}))
    def test_supervisor_show_interfaces_alias_etp1_with_waring(self):
        runner = CliRunner()
        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["interfaces"].commands["alias"], ["etp1"])
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0

    @mock.patch('sonic_py_common.multi_asic.get_port_table', mock.MagicMock(return_value={}))
    @mock.patch('sonic_py_common.device_info.is_supervisor', mock.MagicMock(return_value=True))
    def test_supervisor_show_interfaces_alias_etp1_without_waring(self):
        runner = CliRunner()
        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["interfaces"].commands["alias"], ["etp1"])
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0

    def test_parse_interface_in_filter(self):
        intf_filter = "Ethernet0"
        intf_list = parse_interface_in_filter(intf_filter)
        assert len(intf_list) == 1
        assert intf_list[0] == "Ethernet0"

        intf_filter = "Ethernet1-3"
        intf_list = parse_interface_in_filter(intf_filter)
        assert len(intf_list) == 3
        assert intf_list == ["Ethernet1", "Ethernet2", "Ethernet3"]

        intf_filter = "Ethernet-BP10"
        intf_list = parse_interface_in_filter(intf_filter)
        assert len(intf_list) == 1
        assert intf_list[0] == "Ethernet-BP10"

        intf_filter = "Ethernet-BP10-12"
        intf_list = parse_interface_in_filter(intf_filter)
        assert len(intf_list) == 3
        assert intf_list == ["Ethernet-BP10", "Ethernet-BP11", "Ethernet-BP12"]

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")

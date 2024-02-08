import os

import pytest
import importlib
import mock

from click.testing import CliRunner

from utilities_common import multi_asic
from utilities_common import constants
from utilities_common import bgp_util
from utilities_common.db import Db

from unittest.mock import patch

from sonic_py_common import device_info
from sonic_py_common import multi_asic as masic
show_bgp_summary_v4 = """\

IPv4 Unicast Summary:
BGP router identifier 10.1.0.32, local AS number 65100 vrf-id 0
BGP table version 12811
RIB entries 12817, using 2358328 bytes of memory
Peers 24, using 502080 KiB of memory
Peer groups 4, using 256 bytes of memory


Neighbhor      V     AS    MsgRcvd    MsgSent    TblVer    InQ    OutQ  Up/Down    State/PfxRcd    NeighborName
-----------  ---  -----  ---------  ---------  --------  -----  ------  ---------  --------------  --------------
10.0.0.1       4  65200       5919       2717         0      0       0  1d21h11m   6402            ARISTA01T2
10.0.0.5       4  65200       5916       2714         0      0       0  1d21h10m   6402            ARISTA03T2
10.0.0.9       4  65200       5915       2713         0      0       0  1d21h09m   6402            ARISTA05T2
10.0.0.13      4  65200       5917       2716         0      0       0  1d21h11m   6402            ARISTA07T2
10.0.0.17      4  65200       5916       2713         0      0       0  1d21h09m   6402            ARISTA09T2
10.0.0.21      4  65200       5917       2716         0      0       0  1d21h11m   6402            ARISTA11T2
10.0.0.25      4  65200       5917       2716         0      0       0  1d21h11m   6402            ARISTA13T2
10.0.0.29      4  65200       5916       2714         0      0       0  1d21h10m   6402            ARISTA15T2
10.0.0.33      4  64001          0          0         0      0       0  never      Active          ARISTA01T0
10.0.0.35      4  64002          0          0         0      0       0  never      Active          ARISTA02T0
10.0.0.37      4  64003          0          0         0      0       0  never      Active          ARISTA03T0
10.0.0.39      4  64004          0          0         0      0       0  never      Active          ARISTA04T0
10.0.0.41      4  64005          0          0         0      0       0  never      Active          ARISTA05T0
10.0.0.43      4  64006          0          0         0      0       0  never      Active          ARISTA06T0
10.0.0.45      4  64007          0          0         0      0       0  never      Active          ARISTA07T0
10.0.0.47      4  64008          0          0         0      0       0  never      Active          ARISTA08T0
10.0.0.49      4  64009          0          0         0      0       0  never      Active          ARISTA09T0
10.0.0.51      4  64010          0          0         0      0       0  never      Active          ARISTA10T0
10.0.0.53      4  64011          0          0         0      0       0  never      Active          ARISTA11T0
10.0.0.55      4  64012          0          0         0      0       0  never      Active          ARISTA12T0
10.0.0.57      4  64013          0          0         0      0       0  never      Active          ARISTA13T0
10.0.0.59      4  64014          0          0         0      0       0  never      Active          ARISTA14T0
10.0.0.61      4  64015          0          0         0      0       0  never      Active          INT_NEIGH0
10.0.0.63      4  64016          0          0         0      0       0  never      Active          INT_NEIGH1

Total number of neighbors 24
"""

show_bgp_summary_v6 = """\

IPv6 Unicast Summary:
BGP router identifier 10.1.0.32, local AS number 65100 vrf-id 0
BGP table version 8972
RIB entries 12817, using 2358328 bytes of memory
Peers 24, using 502080 KiB of memory
Peer groups 4, using 256 bytes of memory


Neighbhor      V     AS    MsgRcvd    MsgSent    TblVer    InQ    OutQ  Up/Down    State/PfxRcd    NeighborName
-----------  ---  -----  ---------  ---------  --------  -----  ------  ---------  --------------  --------------
fc00::1a       4  65200       6665       6672         0      0       0  2d09h39m   6402            ARISTA07T2
fc00::2        4  65200       6666       7913         0      0       0  2d09h39m   6402            ARISTA01T2
fc00::2a       4  65200       6666       7913         0      0       0  2d09h39m   6402            ARISTA11T2
fc00::3a       4  65200       6666       7912         0      0       0  2d09h39m   6402            ARISTA15T2
fc00::4a       4  64003          0          0         0      0       0  never      Active          ARISTA03T0
fc00::4e       4  64004          0          0         0      0       0  never      Active          ARISTA04T0
fc00::5a       4  64007          0          0         0      0       0  never      Active          ARISTA07T0
fc00::5e       4  64008          0          0         0      0       0  never      Active          ARISTA08T0
fc00::6a       4  64011          0          0         0      0       0  never      Connect         ARISTA11T0
fc00::6e       4  64012          0          0         0      0       0  never      Active          ARISTA12T0
fc00::7a       4  64015          0          0         0      0       0  never      Active          ARISTA15T0
fc00::7e       4  64016          0          0         0      0       0  never      Active          ARISTA16T0
fc00::12       4  65200       6666       7915         0      0       0  2d09h39m   6402            ARISTA05T2
fc00::22       4  65200       6667       7915         0      0       0  2d09h39m   6402            ARISTA09T2
fc00::32       4  65200       6663       6669         0      0       0  2d09h36m   6402            ARISTA13T2
fc00::42       4  64001          0          0         0      0       0  never      Active          ARISTA01T0
fc00::46       4  64002          0          0         0      0       0  never      Active          ARISTA02T0
fc00::52       4  64005          0          0         0      0       0  never      Active          ARISTA05T0
fc00::56       4  64006          0          0         0      0       0  never      Active          ARISTA06T0
fc00::62       4  64009          0          0         0      0       0  never      Active          ARISTA09T0
fc00::66       4  64010          0          0         0      0       0  never      Active          ARISTA10T0
fc00::72       4  64013          0          0         0      0       0  never      Active          ARISTA13T0
fc00::76       4  64014          0          0         0      0       0  never      Active          INT_NEIGH0
fc00::a        4  65200       6665       6671         0      0       0  2d09h38m   6402            INT_NEIGH1

Total number of neighbors 24
"""

show_error_invalid_json = """\
Usage: summary [OPTIONS]
Try "summary --help" for help.

Error: bgp summary from bgp container not in json format
"""

show_error_no_v6_neighbor_single_asic = """\

IPv6 Unicast Summary:
BGP router identifier 10.1.0.32, local AS number 65100 vrf-id 0
BGP table version 8972
RIB entries 0, using 0 bytes of memory
Peers 0, using 0 KiB of memory
Peer groups 0, using 0 bytes of memory


Neighbhor    V    AS    MsgRcvd    MsgSent    TblVer    InQ    OutQ    Up/Down    State/PfxRcd    NeighborName
-----------  ---  ----  ---------  ---------  --------  -----  ------  ---------  --------------  --------------

Total number of neighbors 0
"""

show_error_no_v4_neighbor_single_asic = """\

IPv4 Unicast Summary:
BGP router identifier 10.1.0.32, local AS number 65100 vrf-id 0
BGP table version 8972
RIB entries 0, using 0 bytes of memory
Peers 0, using 0 KiB of memory
Peer groups 0, using 0 bytes of memory


Neighbhor    V    AS    MsgRcvd    MsgSent    TblVer    InQ    OutQ    Up/Down    State/PfxRcd    NeighborName
-----------  ---  ----  ---------  ---------  --------  -----  ------  ---------  --------------  --------------

Total number of neighbors 0
"""

show_error_no_v6_neighbor_multi_asic = """\

IPv6 Unicast Summary:
asic0: BGP router identifier 10.1.0.32, local AS number 65100 vrf-id 0
BGP table version 8972
asic1: BGP router identifier 10.1.0.32, local AS number 65100 vrf-id 0
BGP table version 8972
RIB entries 0, using 0 bytes of memory
Peers 0, using 0 KiB of memory
Peer groups 0, using 0 bytes of memory


Neighbhor    V    AS    MsgRcvd    MsgSent    TblVer    InQ    OutQ    Up/Down    State/PfxRcd    NeighborName
-----------  ---  ----  ---------  ---------  --------  -----  ------  ---------  --------------  --------------

Total number of neighbors 0
"""

show_error_no_v4_neighbor_multi_asic = """\

IPv4 Unicast Summary:
asic0: BGP router identifier 10.1.0.32, local AS number 65100 vrf-id 0
BGP table version 8972
asic1: BGP router identifier 10.1.0.32, local AS number 65100 vrf-id 0
BGP table version 8972
RIB entries 0, using 0 bytes of memory
Peers 0, using 0 KiB of memory
Peer groups 0, using 0 bytes of memory


Neighbhor    V    AS    MsgRcvd    MsgSent    TblVer    InQ    OutQ    Up/Down    State/PfxRcd    NeighborName
-----------  ---  ----  ---------  ---------  --------  -----  ------  ---------  --------------  --------------

Total number of neighbors 0
"""

show_bgp_summary_v4_chassis = """\

IPv4 Unicast Summary:
BGP router identifier 10.3.147.15, local AS number 65100 vrf-id 0
BGP table version 21464
RIB entries 25783, using 4950336 bytes of memory
Peers 23, using 501768 KiB of memory
Peer groups 3, using 192 bytes of memory


Neighbhor      V     AS    MsgRcvd    MsgSent    TblVer    InQ    OutQ  Up/Down      State/PfxRcd  NeighborName
-----------  ---  -----  ---------  ---------  --------  -----  ------  ---------  --------------  --------------
10.0.0.1       4  65200       4632      11028         0      0       0  00:18:31             8514  ARISTA01T2
10.0.0.9       4  65202       4632      11029         0      0       0  00:18:33             8514  ARISTA05T2
10.0.0.13      4  65203       4632      11028         0      0       0  00:18:33             8514  ARISTA07T2
10.0.0.17      4  65204       4631      11028         0      0       0  00:18:31             8514  ARISTA09T2
10.0.0.21      4  65205       4632      11031         0      0       0  00:18:33             8514  ARISTA11T2
10.0.0.25      4  65206       4632      11031         0      0       0  00:18:33             8514  ARISTA13T2
10.0.0.29      4  65207       4632      11028         0      0       0  00:18:31             8514  ARISTA15T2
10.0.0.33      4  65208       4633      11029         0      0       0  00:18:33             8514  ARISTA01T0
10.0.0.37      4  65210       4632      11028         0      0       0  00:18:32             8514  ARISTA03T0
10.0.0.39      4  65211       4629       6767         0      0       0  00:18:22             8514  ARISTA04T0
10.0.0.41      4  65212       4632      11028         0      0       0  00:18:32             8514  ARISTA05T0
10.0.0.43      4  65213       4629       6767         0      0       0  00:18:23             8514  ARISTA06T0
10.0.0.45      4  65214       4633      11029         0      0       0  00:18:33             8514  ARISTA07T0
10.0.0.47      4  65215       4629       6767         0      0       0  00:18:23             8514  ARISTA08T0
10.0.0.49      4  65216       4633      11029         0      0       0  00:18:35             8514  ARISTA09T0
10.0.0.51      4  65217       4633      11029         0      0       0  00:18:33             8514  ARISTA10T0
10.0.0.53      4  65218       4632      11029         0      0       0  00:18:35             8514  ARISTA11T0
10.0.0.55      4  65219       4632      11029         0      0       0  00:18:33             8514  ARISTA12T0
10.0.0.57      4  65220       4632      11029         0      0       0  00:18:35             8514  ARISTA13T0
10.0.0.59      4  65221       4632      11029         0      0       0  00:18:33             8514  ARISTA14T0

Total number of neighbors 20
"""

show_bgp_summary_v6_chassis = """\

IPv6 Unicast Summary:
BGP router identifier 10.3.147.15, local AS number 65100 vrf-id 0
BGP table version 12971
RIB entries 25783, using 4950336 bytes of memory
Peers 23, using 501768 KiB of memory
Peer groups 3, using 192 bytes of memory


Neighbhor      V     AS    MsgRcvd    MsgSent    TblVer    InQ    OutQ  Up/Down      State/PfxRcd  NeighborName
-----------  ---  -----  ---------  ---------  --------  -----  ------  ---------  --------------  --------------
fc00::1a       4  65203       4438       6578         0      0       0  00:08:57             8514  ARISTA07T2
fc00::2        4  65200       4439       6578         0      0       0  00:08:56             8513  ARISTA01T2
fc00::2a       4  65205       4439       6578         0      0       0  00:08:57             8514  ARISTA11T2
fc00::3a       4  65207       4439       6578         0      0       0  00:08:57             8514  ARISTA15T2
fc00::4a       4  65210       4439       6579         0      0       0  00:08:59             8514  ARISTA03T0
fc00::4e       4  65211       4440       6579         0      0       0  00:09:00             8514  ARISTA04T0
fc00::5a       4  65214       4440       6579         0      0       0  00:09:00             8514  ARISTA07T0
fc00::5e       4  65215       4438       6576         0      0       0  00:08:50             8514  ARISTA08T0
fc00::6a       4  65218       4441       6580         0      0       0  00:09:01             8514  ARISTA11T0
fc00::6e       4  65219       4442       6580         0      0       0  00:09:01             8514  ARISTA12T0
fc00::7a       4  65222       4441       6580         0      0       0  00:09:01             8514  ARISTA15T0
fc00::12       4  65202       4438       6578         0      0       0  00:08:57             8514  ARISTA05T2
fc00::22       4  65204       4438       6578         0      0       0  00:08:57             8514  ARISTA09T2
fc00::32       4  65206       4438       6578         0      0       0  00:08:57             8514  ARISTA13T2
fc00::42       4  65208       4442       6580         0      0       0  00:09:01             8514  ARISTA01T0
fc00::52       4  65212       4439       6579         0      0       0  00:08:59             8514  ARISTA05T0
fc00::56       4  65213       4439       6579         0      0       0  00:08:59             8514  ARISTA06T0
fc00::62       4  65216       4438       6576         0      0       0  00:08:50             8514  ARISTA09T0
fc00::66       4  65217       4442       6580         0      0       0  00:09:01             8514  ARISTA10T0
fc00::72       4  65220       4441       6580         0      0       0  00:09:01             8514  ARISTA13T0

Total number of neighbors 20
"""

show_bgp_summary_v4_all_chassis = """\

IPv4 Unicast Summary:
BGP router identifier 10.3.147.15, local AS number 65100 vrf-id 0
BGP table version 21464
RIB entries 25783, using 4950336 bytes of memory
Peers 23, using 501768 KiB of memory
Peer groups 3, using 192 bytes of memory


Neighbhor      V     AS    MsgRcvd    MsgSent    TblVer    InQ    OutQ  Up/Down    State/PfxRcd    NeighborName
-----------  ---  -----  ---------  ---------  --------  -----  ------  ---------  --------------  ------------------
3.3.3.6        4  65100          0          0         0      0       0  never      Connect         str2-chassis-lc6-1
3.3.3.7        4  65100        808     178891         0      0       0  00:17:47   1458            str2-chassis-lc7-1
10.0.0.1       4  65200       4632      11028         0      0       0  00:18:31   8514            ARISTA01T2
10.0.0.9       4  65202       4632      11029         0      0       0  00:18:33   8514            ARISTA05T2
10.0.0.13      4  65203       4632      11028         0      0       0  00:18:33   8514            ARISTA07T2
10.0.0.17      4  65204       4631      11028         0      0       0  00:18:31   8514            ARISTA09T2
10.0.0.21      4  65205       4632      11031         0      0       0  00:18:33   8514            ARISTA11T2
10.0.0.25      4  65206       4632      11031         0      0       0  00:18:33   8514            ARISTA13T2
10.0.0.29      4  65207       4632      11028         0      0       0  00:18:31   8514            ARISTA15T2
10.0.0.33      4  65208       4633      11029         0      0       0  00:18:33   8514            ARISTA01T0
10.0.0.37      4  65210       4632      11028         0      0       0  00:18:32   8514            ARISTA03T0
10.0.0.39      4  65211       4629       6767         0      0       0  00:18:22   8514            ARISTA04T0
10.0.0.41      4  65212       4632      11028         0      0       0  00:18:32   8514            ARISTA05T0
10.0.0.43      4  65213       4629       6767         0      0       0  00:18:23   8514            ARISTA06T0
10.0.0.45      4  65214       4633      11029         0      0       0  00:18:33   8514            ARISTA07T0
10.0.0.47      4  65215       4629       6767         0      0       0  00:18:23   8514            ARISTA08T0
10.0.0.49      4  65216       4633      11029         0      0       0  00:18:35   8514            ARISTA09T0
10.0.0.51      4  65217       4633      11029         0      0       0  00:18:33   8514            ARISTA10T0
10.0.0.53      4  65218       4632      11029         0      0       0  00:18:35   8514            ARISTA11T0
10.0.0.55      4  65219       4632      11029         0      0       0  00:18:33   8514            ARISTA12T0
10.0.0.57      4  65220       4632      11029         0      0       0  00:18:35   8514            ARISTA13T0
10.0.0.59      4  65221       4632      11029         0      0       0  00:18:33   8514            ARISTA14T0
10.0.0.61      4  65222       4633      11029         0      0       0  00:18:33   8514            INT_NEIGH0

Total number of neighbors 23
"""
SHOW_BGP_SUMMARY_V4_NO_EXT_NEIGHBORS_ON_ALL_ASIC = """
IPv4 Unicast Summary:
asic0: BGP router identifier 10.1.0.32, local AS number 65100 vrf-id 0
BGP table version 8972
asic1: BGP router identifier 10.1.0.32, local AS number 65100 vrf-id 0
BGP table version 8972
RIB entries 0, using 0 bytes of memory
Peers 0, using 0 KiB of memory
Peer groups 0, using 0 bytes of memory


Neighbhor    V    AS    MsgRcvd    MsgSent    TblVer    InQ    OutQ    Up/Down    State/PfxRcd    NeighborName
-----------  ---  ----  ---------  ---------  --------  -----  ------  ---------  --------------  --------------

Total number of neighbors 0
"""

SHOW_BGP_SUMMARY_V4_NO_EXT_NEIGHBORS_ON_ASIC1 = """
IPv4 Unicast Summary:
asic0: BGP router identifier 192.0.0.6, local AS number 65100 vrf-id 0
BGP table version 59923
asic1: BGP router identifier 10.1.0.32, local AS number 65100 vrf-id 0
BGP table version 8972
RIB entries 3, using 3 bytes of memory
Peers 3, using 3 KiB of memory
Peer groups 3, using 3 bytes of memory


Neighbhor      V     AS    MsgRcvd    MsgSent    TblVer    InQ    OutQ  Up/Down      State/PfxRcd  NeighborName
-----------  ---  -----  ---------  ---------  --------  -----  ------  ---------  --------------  --------------
10.0.0.1       4  65222       4633      11029         0      0       0  00:18:33             8514  ARISTA01T2

Total number of neighbors 1
"""

SHOW_BGP_SUMMARY_ALL_V4_NO_EXT_NEIGHBORS = """
IPv4 Unicast Summary:
asic0: BGP router identifier 192.0.0.6, local AS number 65100 vrf-id 0
BGP table version 59923
asic1: BGP router identifier 192.0.0.8, local AS number 65100 vrf-id 0
BGP table version 64918
RIB entries 202298, using 37222832 bytes of memory
Peers 6, using 4444848 KiB of memory
Peer groups 4, using 256 bytes of memory


Neighbhor      V     AS    MsgRcvd    MsgSent    TblVer    InQ    OutQ  Up/Down      State/PfxRcd  NeighborName
-----------  ---  -----  ---------  ---------  --------  -----  ------  ---------  --------------  ----------------------
3.3.3.1        4  65100        277          9         0      0       0  00:00:14            33798  str2-sonic-lc1-1-ASIC0
3.3.3.1        4  65100        280         14         0      0       0  00:00:22            33798  str2-sonic-lc1-1-ASIC1
3.3.3.2        4  65100        277          9         0      0       0  00:00:14            33798  str2-sonic-lc2-1-ASIC0
3.3.3.2        4  65100        280         14         0      0       0  00:00:22            33798  str2-sonic-lc3-1-ASIC0
3.3.3.6        4  65100         14         14         0      0       0  00:00:23                4  str2-sonic-lc3-1-ASIC1
3.3.3.8        4  65100         12         10         0      0       0  00:00:15                4  str2-sonic-lc1-1-ASIC1

Total number of neighbors 6
"""


class TestBgpCommandsSingleAsic(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        from .mock_tables import dbconnector
        dbconnector.load_namespace_config()

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['v4'], indirect=['setup_single_bgp_instance'])
    def test_bgp_summary_v4(
            self,
            setup_bgp_commands,
            setup_single_bgp_instance):
        show = setup_bgp_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["bgp"].commands["summary"], [])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_bgp_summary_v4

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['v6'], indirect=['setup_single_bgp_instance'])
    def test_bgp_summary_v6(
            self,
            setup_bgp_commands,
            setup_single_bgp_instance):
        show = setup_bgp_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ipv6"].commands["bgp"].commands["summary"], [])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_bgp_summary_v6

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             [' '], indirect=['setup_single_bgp_instance'])
    def test_bgp_summary_error(
            self,
            setup_bgp_commands,
            setup_single_bgp_instance):
        show = setup_bgp_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ipv6"].commands["bgp"].commands["summary"], [])
        print("{}".format(result.output))
        assert result.exit_code == 2
        assert result.output == show_error_invalid_json

    def display_external(self):
        return constants.DISPLAY_EXTERNAL

    def display_all(self):
        return constants.DISPLAY_ALL

    @pytest.mark.parametrize(
        'setup_single_bgp_instance_chassis', ['v4'],
        indirect=['setup_single_bgp_instance_chassis']
    )
    @patch.object(multi_asic.MultiAsic, 'get_display_option', display_external)
    @patch('sonic_py_common.device_info.get_platform_info')
    def test_bgp_summary_v4_chassis(
        self, mock_is_chassis, setup_bgp_commands,
        setup_single_bgp_instance_chassis
    ):
        mock_is_chassis.return_value = {'switch_type': 'voq'}
        show = setup_bgp_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["bgp"].commands["summary"], [])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_bgp_summary_v4_chassis

    @pytest.mark.parametrize(
        'setup_single_bgp_instance_chassis', ['v6'],
        indirect=['setup_single_bgp_instance_chassis']
    )
    @patch.object(multi_asic.MultiAsic, 'get_display_option', display_external)
    @patch('sonic_py_common.device_info.get_platform_info')
    def test_bgp_summary_v6_chassis(
        self, mock_is_chassis, setup_bgp_commands,
        setup_single_bgp_instance_chassis
    ):
        mock_is_chassis.return_value = {'switch_type': 'voq'}
        show = setup_bgp_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ipv6"].commands["bgp"].commands["summary"], [])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_bgp_summary_v6_chassis

    @pytest.mark.parametrize(
        'setup_single_bgp_instance_chassis', ['v4'],
        indirect=['setup_single_bgp_instance_chassis']
    )
    @patch.object(multi_asic.MultiAsic, 'get_display_option', display_all)
    @patch('sonic_py_common.device_info.get_platform_info')
    def test_bgp_summary_v4_all_chassis(
        self, mock_is_chassis, setup_bgp_commands,
        setup_single_bgp_instance_chassis
    ):
        mock_is_chassis.return_value = {'switch_type': 'voq'}
        show = setup_bgp_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["bgp"].commands["summary"], [])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_bgp_summary_v4_all_chassis

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['show_bgp_summary_no_neigh'], indirect=['setup_single_bgp_instance'])
    def test_bgp_summary_no_v4_neigh(
            self,
            setup_bgp_commands,
            setup_single_bgp_instance):
        show = setup_bgp_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["bgp"].commands["summary"], [])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_error_no_v4_neighbor_single_asic

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['show_bgp_summary_no_neigh'], indirect=['setup_single_bgp_instance'])
    def test_bgp_summary_no_v6_neigh(
            self,
            setup_bgp_commands,
            setup_single_bgp_instance):
        show = setup_bgp_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ipv6"].commands["bgp"].commands["summary"], [])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_error_no_v6_neighbor_single_asic

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        from .mock_tables import dbconnector
        dbconnector.load_database_config()



class TestBgpCommandsMultiAsic(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        from .mock_tables import dbconnector
        dbconnector.load_namespace_config()



    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['show_bgp_summary_no_neigh'], indirect=['setup_multi_asic_bgp_instance'])
    def test_bgp_summary_multi_asic_no_v4_neigh(
            self,
            setup_bgp_commands,
            setup_multi_asic_bgp_instance):
        show = setup_bgp_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["bgp"].commands["summary"], [])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_error_no_v4_neighbor_multi_asic


    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['show_bgp_summary_no_neigh'], indirect=['setup_multi_asic_bgp_instance'])
    def test_bgp_summary_multi_asic_no_v6_neigh(
            self,
            setup_bgp_commands,
            setup_multi_asic_bgp_instance):
        show = setup_bgp_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ipv6"].commands["bgp"].commands["summary"], [])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_error_no_v6_neighbor_multi_asic

    @patch.object(bgp_util, 'get_external_bgp_neighbors_dict', mock.MagicMock(return_value={}))
    @patch.object(multi_asic.MultiAsic, 'get_ns_list_based_on_options', mock.Mock(return_value=['asic0', 'asic1']))
    @patch.object(multi_asic.MultiAsic, 'get_display_option', mock.MagicMock(return_value=constants.DISPLAY_EXTERNAL))
    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['show_bgp_summary_no_ext_neigh_on_all_asic'],
                             indirect=['setup_multi_asic_bgp_instance'])
    @patch.object(device_info, 'is_chassis', mock.MagicMock(return_value=True))
    def test_bgp_summary_multi_asic_no_external_neighbors_on_all_asic(
            self,
            setup_bgp_commands,
            setup_multi_asic_bgp_instance):
        show = setup_bgp_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["bgp"].commands["summary"], [])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == SHOW_BGP_SUMMARY_V4_NO_EXT_NEIGHBORS_ON_ALL_ASIC     


    @patch.object(multi_asic.MultiAsic, 'get_ns_list_based_on_options', mock.Mock(return_value=['asic0', 'asic1']))
    @patch.object(multi_asic.MultiAsic, 'get_display_option', mock.MagicMock(return_value=constants.DISPLAY_EXTERNAL))
    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['show_bgp_summary_no_ext_neigh_on_asic1'],
                             indirect=['setup_multi_asic_bgp_instance'])
    @patch.object(device_info, 'is_chassis', mock.MagicMock(return_value=True))
    def test_bgp_summary_multi_asic_no_external_neighbor_on_asic1(
            self,
            setup_bgp_commands,
            setup_multi_asic_bgp_instance):
        show = setup_bgp_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["bgp"].commands["summary"], [])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == SHOW_BGP_SUMMARY_V4_NO_EXT_NEIGHBORS_ON_ASIC1

    
    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['show_bgp_summary_no_ext_neigh_on_all_asic'], indirect=['setup_multi_asic_bgp_instance'])
    def test_bgp_summary_multi_asic_display_with_no_external_neighbor(
            self,
            setup_bgp_commands,
            setup_multi_asic_bgp_instance):
        show = setup_bgp_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["bgp"].commands["summary"], ["-dall"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == SHOW_BGP_SUMMARY_ALL_V4_NO_EXT_NEIGHBORS
        
    def teardown_class(cls):
        print("TEARDOWN")
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        from .mock_tables import dbconnector
        dbconnector.load_database_config

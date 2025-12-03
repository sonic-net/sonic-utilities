import os
import pytest
import importlib
from click.testing import CliRunner

from utilities_common import multi_asic
from utilities_common import constants

from unittest.mock import patch

from sonic_py_common import device_info
import show.main as show


show_run_bgp_sasic = \
"""router bgp 65100
bgp router-id 10.1.0.32
bgp log-neighbor-changes
no bgp ebgp-requires-policy
no bgp default ipv4-unicast
bgp graceful-restart restart-time 240
bgp graceful-restart select-defer-time 45
bgp graceful-restart
bgp graceful-restart preserve-fw-state
bgp bestpath as-path multipath-relax
neighbor BGPSLBPassive peer-group
neighbor BGPSLBPassive remote-as 65432
neighbor BGPSLBPassive passive
neighbor BGPSLBPassive ebgp-multihop 255
neighbor BGPSLBPassive update-source 10.1.0.32
neighbor BGPVac peer-group
neighbor BGPVac remote-as 65432
neighbor BGPVac passive
neighbor BGPVac ebgp-multihop 255
neighbor BGPVac update-source 10.1.0.32
neighbor PEER_V4 peer-group
neighbor PEER_V6 peer-group
neighbor 10.0.0.57 remote-as 64600
neighbor 10.0.0.57 peer-group PEER_V4
neighbor 10.0.0.57 description ARISTA01T1
neighbor 10.0.0.57 timers 3 10
neighbor 10.0.0.57 timers connect 10
neighbor 10.0.0.59 remote-as 64600
neighbor 10.0.0.59 peer-group PEER_V4
neighbor 10.0.0.59 description ARISTA02T1
neighbor 10.0.0.59 timers 3 10
neighbor 10.0.0.59 timers connect 10
neighbor 10.0.0.61 remote-as 64600
neighbor 10.0.0.61 peer-group PEER_V4
neighbor 10.0.0.61 description ARISTA03T1
neighbor 10.0.0.61 timers 3 10
neighbor 10.0.0.61 timers connect 10
neighbor 10.0.0.63 remote-as 64600
neighbor 10.0.0.63 peer-group PEER_V4
neighbor 10.0.0.63 description ARISTA04T1
neighbor 10.0.0.63 timers 3 10
neighbor 10.0.0.63 timers connect 10
neighbor fc00::72 remote-as 64600
neighbor fc00::72 peer-group PEER_V6
neighbor fc00::72 description ARISTA01T1
neighbor fc00::72 timers 3 10
neighbor fc00::72 timers connect 10
neighbor fc00::76 remote-as 64600
neighbor fc00::76 peer-group PEER_V6
neighbor fc00::76 description ARISTA02T1
neighbor fc00::76 timers 3 10
neighbor fc00::76 timers connect 10
neighbor fc00::7a remote-as 64600
neighbor fc00::7a peer-group PEER_V6
neighbor fc00::7a description ARISTA03T1
neighbor fc00::7a timers 3 10
neighbor fc00::7a timers connect 10
neighbor fc00::7e remote-as 64600
neighbor fc00::7e peer-group PEER_V6
neighbor fc00::7e description ARISTA04T1
neighbor fc00::7e timers 3 10
neighbor fc00::7e timers connect 10
bgp listen range 10.255.0.0/25 peer-group BGPSLBPassive
bgp listen range 192.168.0.0/21 peer-group BGPVac

"""

show_run_bgp_masic = \
"""
------------Showing running config bgp on asic0------------
neighbor 10.0.0.1 remote-as 65200
neighbor 10.0.0.1 peer-group TIER2_V4
neighbor 10.0.0.1 description ARISTA01T2
neighbor 10.0.0.5 remote-as 65200
neighbor 10.0.0.5 peer-group TIER2_V4
neighbor 10.0.0.5 description ARISTA03T2
neighbor fc00::2 remote-as 65200
neighbor fc00::2 peer-group TIER2_V6
neighbor fc00::2 description ARISTA01T2
neighbor fc00::6 remote-as 65200
neighbor fc00::6 peer-group TIER2_V6
neighbor fc00::6 description ARISTA03T2

------------Showing running config bgp on asic1------------
neighbor 10.0.0.9 remote-as 65200
neighbor 10.0.0.9 peer-group TIER2_V4
neighbor 10.0.0.9 description ARISTA05T2
neighbor 10.0.0.13 remote-as 65200
neighbor 10.0.0.13 peer-group TIER2_V4
neighbor 10.0.0.13 description ARISTA07T2
neighbor fc00::a remote-as 65200
neighbor fc00::a peer-group TIER2_V6
neighbor fc00::a description ARISTA05T2
neighbor fc00::e remote-as 65200
neighbor fc00::e peer-group TIER2_V6
neighbor fc00::e description ARISTA07T2

"""

show_run_bgp_masic_asic0 = \
"""
------------Showing running config bgp on asic0------------
neighbor 10.0.0.1 remote-as 65200
neighbor 10.0.0.1 peer-group TIER2_V4
neighbor 10.0.0.1 description ARISTA01T2
neighbor 10.0.0.5 remote-as 65200
neighbor 10.0.0.5 peer-group TIER2_V4
neighbor 10.0.0.5 description ARISTA03T2
neighbor fc00::2 remote-as 65200
neighbor fc00::2 peer-group TIER2_V6
neighbor fc00::2 description ARISTA01T2
neighbor fc00::6 remote-as 65200
neighbor fc00::6 peer-group TIER2_V6
neighbor fc00::6 description ARISTA03T2

"""

show_run_bgp_not_running = \
"""
------------Showing running config bgp on asic0------------
Error response from daemon: Container 70e3d3bafd1ab5faf796892acff3e2ccbea3dcd5dcfefcc34f25f7cc916b67bb is not running

"""

class TestShowRunBgpSingleAsic(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        from .mock_tables import dbconnector
        dbconnector.load_namespace_config()

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             [
			        'show_run_bgp',
                             ],
                             indirect=['setup_single_bgp_instance'])

    def test_show_run_bgp_single(self,
                                 setup_single_bgp_instance):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["runningconfiguration"].commands["bgp"], [])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_run_bgp_sasic

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        from .mock_tables import dbconnector
        dbconnector.load_database_config()


class TestShowRunBgpMultiAsic(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        from .mock_tables import dbconnector
        dbconnector.load_namespace_config()

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             [
				'show_run_bgp',
                             ],
                             indirect=['setup_multi_asic_bgp_instance'])
    def test_show_run_bgp_all_asics(self,
                           setup_multi_asic_bgp_instance):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["runningconfiguration"].commands["bgp"], [])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_run_bgp_masic


    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             [
				'show_run_bgp',
                             ],
                             indirect=['setup_multi_asic_bgp_instance'])
    def test_show_run_bgp_asic0(self,
                                setup_multi_asic_bgp_instance):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["runningconfiguration"].commands["bgp"], ["-nasic0"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_run_bgp_masic_asic0
	
    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             [
                             'show_not_running_bgp',
                             ],
                             indirect=['setup_multi_asic_bgp_instance'])
    def test_bgp0_not_running(self,
                             setup_multi_asic_bgp_instance):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["runningconfiguration"].commands["bgp"], ["-nasic0"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_run_bgp_not_running
	
    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        from .mock_tables import dbconnector
        dbconnector.load_database_config

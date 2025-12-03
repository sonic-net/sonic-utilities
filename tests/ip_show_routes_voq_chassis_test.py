import os
from importlib import reload
import pytest
from unittest import mock

import show.main as show
from . import show_ip_route_common
import utilities_common.multi_asic as multi_asic_util
from click.testing import CliRunner

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")


class TestMultiAsicVoqLcShowIpRouteDisplayAllCommands(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        from .mock_tables import mock_multi_asic
        reload(mock_multi_asic)
        from .mock_tables import dbconnector
        dbconnector.load_namespace_config()

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ip_route_lc'], indirect=['setup_multi_asic_bgp_instance'])
    @mock.patch("sonic_py_common.device_info.is_voq_chassis", mock.MagicMock(return_value=True))
    def test_voq_chassis_lc(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):

        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["-dfrontend"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.SHOW_IP_ROUTE_LC

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ip_route_remote_lc'], indirect=['setup_multi_asic_bgp_instance'])
    @mock.patch("sonic_py_common.device_info.is_voq_chassis", mock.MagicMock(return_value=True))
    def test_voq_chassis_remote_lc(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):

        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["-dfrontend"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.SHOW_IP_ROUTE_REMOTE_LC

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ip_route_lc'], indirect=['setup_multi_asic_bgp_instance'])
    @mock.patch("sonic_py_common.device_info.is_voq_chassis", mock.MagicMock(return_value=True))
    def test_voq_chassis_lc_def_route(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):

        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["0.0.0.0/0"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.SHOW_IP_ROUTE_LC_DEFAULT_ROUTE

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ip_route_remote_lc'], indirect=['setup_multi_asic_bgp_instance'])
    @mock.patch("sonic_py_common.device_info.is_voq_chassis", mock.MagicMock(return_value=True))
    def test_voq_chassis_remote_lc_default_route(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):

        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["0.0.0.0/0"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.SHOW_IP_ROUTE_REMOTE_LC_DEFAULT_ROUTE

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ip_route_lc_2'], indirect=['setup_multi_asic_bgp_instance'])
    @mock.patch("sonic_py_common.device_info.is_voq_chassis", mock.MagicMock(return_value=True))
    @mock.patch.object(multi_asic_util.MultiAsic, "get_ns_list_based_on_options",
                       mock.MagicMock(return_value=["asic0", "asic1"]))
    def test_voq_chassis_lc_def_route_2(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):

        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["0.0.0.0/0"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.SHOW_IP_ROUTE_LC_DEFAULT_ROUTE_2

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        from .mock_tables import mock_single_asic
        reload(mock_single_asic)

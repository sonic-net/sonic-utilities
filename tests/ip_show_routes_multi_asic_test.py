import os
from importlib import reload
import pytest


from . import show_ip_route_common
from click.testing import CliRunner

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")

class TestMultiAiscShowIpRouteDisplayAllCommands(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        from .mock_tables import mock_multi_asic_3_asics
        reload(mock_multi_asic_3_asics)
        from .mock_tables import dbconnector
        dbconnector.load_namespace_config()

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ip_route'], indirect=['setup_multi_asic_bgp_instance'])
    def test_show_multi_asic_ip_route_front_end(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["-dfrontend"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_ip_route_multi_asic_display_all_front_expected_output

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ip_route'], indirect=['setup_multi_asic_bgp_instance'])
    def test_show_multi_asic_ip_route_all(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["-dall"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_ip_route_multi_asic_display_all_expected_output

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ip_specific_route'], indirect=['setup_multi_asic_bgp_instance'])
    def test_show_multi_asic_ip_route_specific(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["10.0.0.4"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_ip_route_multi_asic_specific_route_output

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ip_specific_route_on_1_asic'], indirect=['setup_multi_asic_bgp_instance'])
    def test_show_multi_asic_ip_route_specific_on_1_asic(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["192.168.0.1"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_specific_ip_route_expected_output

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ip_specific_recursive_route'], indirect=['setup_multi_asic_bgp_instance'])
    def test_show_multi_asic_ip_route_specific_recursive_route(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["193.11.208.0/25"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_specific_recursive_route_expected_output

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ipv6_specific_route'], indirect=['setup_multi_asic_bgp_instance'])
    def test_show_multi_asic_ipv6_route_specific(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ipv6"].commands["route"], ["2603:10e2:400::"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_ipv6_route_multi_asic_specific_route_output

    # note that we purposely use the single bgp instance setup to cause trigger a param error bad 
    # just bail out while executing in multi-asic show ipv6 route handling.
    # This is to test out the error parm handling code path
    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['ipv6_route_err'], indirect=['setup_single_bgp_instance'])
    def test_show_imulti_asic_ipv6_route_err(
            self,
            setup_ip_route_commands,
            setup_single_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ipv6"].commands["route"], ["garbage"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_ipv6_route_err_expected_output + "\n"

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ip_route'], indirect=['setup_multi_asic_bgp_instance'])
    def test_show_multi_asic_ip_route_namespace_option_err(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["-nasic7"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_ip_route_multi_asic_invalid_namespace_err_output

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ip_route'], indirect=['setup_multi_asic_bgp_instance'])
    def test_show_multi_asic_ip_route_display_option_err(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["-deverything"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_ip_route_multi_asic_invalid_display_err_output

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ipv6_route'], indirect=['setup_multi_asic_bgp_instance'])
    def test_show_multi_asic_ipv6_route_all_namespace(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ipv6"].commands["route"], ["-dfrontend"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_ipv6_route_multi_asic_all_namespace_output

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ipv6_route'], indirect=['setup_multi_asic_bgp_instance'])
    def test_show_multi_asic_ipv6_route_all_namespace_alias(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(
            show.cli.commands["ipv6"].commands["route"], ["-dfrontend"])
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_ipv6_route_multi_asic_all_namespace_alias_output

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ipv6_route'], indirect=['setup_multi_asic_bgp_instance'])
    def test_show_multi_asic_ipv6_route_single_namespace(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ipv6"].commands["route"], ["-nasic2"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_ipv6_route_multi_asic_single_namespace_output

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ipv6_specific_route'], indirect=['setup_multi_asic_bgp_instance'])
    def test_show_multi_asic_ipv6_route_specific_route_json(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ipv6"].commands["route"], ["json"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_ipv6_route_multi_asic_json_output

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ip_special_route'], indirect=['setup_multi_asic_bgp_instance'])
    def test_show_multi_asic_ip_route_special_route(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["-nasic0"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_special_ip_route_expected_output

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ip_empty_route'], indirect=['setup_multi_asic_bgp_instance'])
    def test_show_multi_asic_ip_route_empty_route(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["-dfrontend"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == "" 

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ip_route_summary'], indirect=['setup_multi_asic_bgp_instance'])
    def test_show_multi_asic_ip_route_summay(
            self,
            setup_ip_route_commands,
            setup_multi_asic_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["summary"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_ip_route_summary_expected_output

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        from .mock_tables import mock_single_asic
        reload(mock_single_asic)

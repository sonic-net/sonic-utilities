import importlib
import os

import pytest

from click.testing import CliRunner
from .bgp_commands_input import bgp_network_test_vector


def executor(test_vector, show):
    runner = CliRunner()
    input = bgp_network_test_vector.testData[test_vector]
    if test_vector.startswith('bgp_v6'):
        exec_cmd = show.cli.commands["ipv6"].commands["bgp"].commands["network"]
    else:
        exec_cmd = show.cli.commands["ip"].commands["bgp"].commands["network"]

    result = runner.invoke(exec_cmd, input['args'])

    print(result.exit_code)
    print(result.output)

    if input['rc'] == 0:
        assert result.exit_code == 0
    else:
        assert result.exit_code == input['rc']

    if 'rc_err_msg' in input:
        output = result.output.strip().split("\n")[-1]
        assert input['rc_err_msg'] in output

    if 'rc_output' in input:
        assert result.output == input['rc_output']

    if 'rc_warning_msg' in input:
        output = result.output.strip().split("\n")[0]
        assert input['rc_warning_msg'] in output


class TestBgpNetwork(object):

    @classmethod
    def setup_class(cls):
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        from .mock_tables import dbconnector
        dbconnector.load_database_config


    @pytest.mark.parametrize(
        'setup_single_bgp_instance, test_vector',
        [('bgp_v4_network', 'bgp_v4_network'),
         ('bgp_v6_network', 'bgp_v6_network'),
         ('bgp_v4_network_ip_address', 'bgp_v4_network_ip_address'),
         ('bgp_v6_network_ip_address', 'bgp_v6_network_ip_address'),
         ('bgp_v6_network_bestpath', 'bgp_v6_network_bestpath'),
         ('bgp_v4_network_bestpath', 'bgp_v4_network_bestpath'),
         ('bgp_v6_network_longer_prefixes', 'bgp_v6_network_longer_prefixes'),
         ('bgp_v4_network', 'bgp_v4_network_longer_prefixes_error'),
         ('bgp_v4_network', 'bgp_v6_network_longer_prefixes_error'),
         ('bgp_v4_network', 'bgp_v4_network_all_asic_on_single_asic')],
        indirect=['setup_single_bgp_instance'])
    def test_bgp_network(self, setup_bgp_commands, test_vector,
                         setup_single_bgp_instance):
        show = setup_bgp_commands
        executor(test_vector, show)


class TestMultiAsicBgpNetwork(object):

    @classmethod
    def setup_class(cls):
        print("SETUP")
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        from .mock_tables import dbconnector
        dbconnector.load_namespace_config()

    @pytest.mark.parametrize(
        'setup_multi_asic_bgp_instance, test_vector',
        [('bgp_v4_network', 'bgp_v4_network_multi_asic'),
         ('bgp_v6_network', 'bgp_v6_network_multi_asic'),
         ('bgp_v4_network_asic0', 'bgp_v4_network_asic0'),
         ('bgp_v4_network_ip_address_asic0', 'bgp_v4_network_ip_address_asic0'),
         ('bgp_v4_network_bestpath_asic0', 'bgp_v4_network_bestpath_asic0'),
        ('bgp_v6_network_asic0', 'bgp_v6_network_asic0'),
         ('bgp_v6_network_ip_address_asic0', 'bgp_v6_network_ip_address_asic0'),
         ('bgp_v6_network_bestpath_asic0', 'bgp_v6_network_bestpath_asic0'),
         ('bgp_v4_network_all_asic', 'bgp_v4_network_all_asic'),
         ('bgp_v4_network', 'bgp_v4_network_asic_unknown')],
        indirect=['setup_multi_asic_bgp_instance'])
    def test_bgp_network(self, setup_bgp_commands, test_vector,
                         setup_multi_asic_bgp_instance):
        show = setup_bgp_commands
        executor(test_vector, show)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        from .mock_tables import dbconnector
        dbconnector.load_database_config

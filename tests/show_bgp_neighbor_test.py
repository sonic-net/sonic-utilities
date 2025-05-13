import importlib
import os

import pytest

from click.testing import CliRunner
from .bgp_commands_input import bgp_neighbors_test_vector


def executor(test_vector, show):
    runner = CliRunner()
    input = bgp_neighbors_test_vector.testData[test_vector]
    if test_vector.startswith('bgp_v6'):
        exec_cmd = show.cli.commands["ipv6"].commands["bgp"].commands["neighbors"]
    else:
        exec_cmd = show.cli.commands["ip"].commands["bgp"].commands["neighbors"]

    result = runner.invoke(exec_cmd, input['args'])
    check_result(result, input)


def executor_vrf(test_vector, show):
    runner = CliRunner()
    input = bgp_neighbors_test_vector.testData[test_vector]
    if test_vector.startswith('bgp_v6'):
        exec_cmd = show.cli.commands["ipv6"].commands["bgp"].commands["vrf"]
    else:
        exec_cmd = show.cli.commands["ip"].commands["bgp"].commands["vrf"]

    result = runner.invoke(exec_cmd, [input['vrf'], 'neighbors'] + input['args'])
    check_result(result, input)


def check_result(result, input):
    print(result.exit_code)
    print(result.output)

    if input['rc'] == 0:
        assert result.exit_code == 0
    else:
        assert result.exit_code == input['rc']

    if 'rc_err_msg' in input:
        output = result.output.strip().split("\n")[-1]
        assert input['rc_err_msg'] == output

    if 'rc_output' in input:
        assert result.output == input['rc_output']

    if 'rc_warning_msg' in input:
        output = result.output.strip().split("\n")[0]
        assert input['rc_warning_msg'] in output


class TestBgpNeighbors(object):

    @classmethod
    def setup_class(cls):
        print("SETUP")
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        from .mock_tables import dbconnector
        dbconnector.load_namespace_config()

    @pytest.mark.parametrize('setup_single_bgp_instance, test_vector',
                             [
                                 ('bgp_v4_neighbors_output', 'bgp_v4_neighbors'),
                                 ('bgp_v4_neighbors_output', 'bgp_v4_neighbors_vrf'),
                                 ('bgp_v4_neighbors_output',
                                     'bgp_v4_neighbor_ip_address'),
                                 ('bgp_v4_neighbor_invalid_neigh',
                                     'bgp_v4_neighbor_invalid'),
                                 ('bgp_v4_neighbor_invalid_address',
                                     'bgp_v4_neighbor_invalid_address'),
                                 ('bgp_v4_neighbor_output_adv_routes',
                                     'bgp_v4_neighbor_adv_routes'),
                                 ('bgp_v4_neighbor_output_recv_routes',
                                     'bgp_v4_neighbor_recv_routes'),
                                 ('bgp_v6_neighbors_output', 'bgp_v6_neighbors'),
                                 ('bgp_v6_neighbors_output', 'bgp_v6_neighbors_vrf'),
                                 ('bgp_v6_neighbors_output',
                                     'bgp_v6_neighbor_ip_address'),
                                 ('bgp_v6_neighbor_invalid',
                                     'bgp_v6_neighbor_invalid'),
                                 ('bgp_v6_neighbor_invalid_address',
                                     'bgp_v6_neighbor_invalid_address'),
                                 ('bgp_v6_neighbor_output_adv_routes',
                                     'bgp_v6_neighbor_adv_routes'),
                                 ('bgp_v6_neighbor_output_recv_routes',
                                     'bgp_v6_neighbor_recv_routes'),
                             ],
                             indirect=['setup_single_bgp_instance'])
    def test_bgp_neighbors(self,
                           setup_bgp_commands,
                           setup_single_bgp_instance,
                           test_vector):
        show = setup_bgp_commands
        executor(test_vector, show)
        executor_vrf(test_vector, show)


class TestBgpNeighborsMultiAsic(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        from .mock_tables import dbconnector
        dbconnector.load_namespace_config()

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance, test_vector',
                             [
                                ('bgp_v4_neighbors_output_all_asics',
                                'bgp_v4_neighbors_multi_asic'),
                                ('bgp_v4_neighbors_output_asic1',
                                'bgp_v4_neighbors_asic'),
                                ('bgp_v4_neighbors_output_asic1',
                                'bgp_v4_neighbors_internal'),
                                ('bgp_v4_neighbors_output_asic0',
                                'bgp_v4_neighbors_external'),
                                ('bgp_v6_neighbor_output_warning',
                                'bgp_v6_neighbor_warning'),
                                ('bgp_v6_neighbors_output_all_asics',
                                'bgp_v6_neighbors_multi_asic'),
                                ('bgp_v6_neighbors_output_asic0',
                                'bgp_v6_neighbors_asic'),
                                ('bgp_v6_neighbors_output_asic0',
                                'bgp_v6_neighbors_external'),
                                ('bgp_v6_neighbors_output_asic1',
                                'bgp_v6_neighbors_internal')
                             ],
                             indirect=['setup_multi_asic_bgp_instance'])
    def test_bgp_neighbors(self,
                           setup_bgp_commands,
                           setup_multi_asic_bgp_instance,
                           test_vector):
        show = setup_bgp_commands
        executor(test_vector, show)
        executor_vrf(test_vector, show)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        from .mock_tables import dbconnector
        dbconnector.load_database_config

import pytest

from click.testing import CliRunner
import show.main as show
from .isis_frr_input.isis_frr_test_vector import *


def executor(test_vector, show, exec_cmd):
    runner = CliRunner()
    input = testData[test_vector]

    result = runner.invoke(exec_cmd, input['args'])

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


class TestIsisNeighbors(object):

    @classmethod
    def setup_class(cls):
        print("SETUP")

    @pytest.mark.parametrize('setup_single_isis_instance, test_vector',
                             [
                                 ('isis_neighbors_output', 'isis_neighbors'),
                                 ('isis_neighbors_system_id_output', 'isis_neighbors_system_id'),
                                 ('isis_neighbors_hostname_output', 'isis_neighbors_hostname'),
                                 ('isis_neighbors_verbose_output', 'isis_neighbors_verbose'),
                                 ('isis_neighbors_invalid_hostname_output', 'isis_neighbors_invalid_hostname'),
                                 ('isis_neighbors_invalid_system_id_output', 'isis_neighbors_invalid_system_id'),
                                 ('isis_neighbors_invalid_help_output', 'isis_neighbors_invalid_help')
                             ],
                             indirect=['setup_single_isis_instance'])
    def test_isis_neighbors(self,
                            setup_isis_commands,
                            setup_single_isis_instance,
                            test_vector):
        show = setup_isis_commands
        exec_cmd = show.cli.commands["isis"].commands["neighbors"]
        executor(test_vector, show, exec_cmd)


class TestIsisDatabase(object):

    @classmethod
    def setup_class(cls):
        print("SETUP")

    @pytest.mark.parametrize('setup_single_isis_instance, test_vector',
                             [
                                 ('isis_database_output', 'isis_database'),
                                 ('isis_database_lsp_id_output', 'isis_database_lsp_id'),
                                 ('isis_database_verbose_output', 'isis_database_verbose'),
                                 ('isis_database_lsp_id_verbose_output', 'isis_database_lsp_id_verbose'),
                                 ('isis_database_unknown_lsp_id_output', 'isis_database_unknown_lsp_id'),
                                 ('isis_database_invalid_help_output', 'isis_database_invalid_help')
                             ],
                             indirect=['setup_single_isis_instance'])
    def test_isis_database(self,
                           setup_isis_commands,
                           setup_single_isis_instance,
                           test_vector):
        show = setup_isis_commands
        exec_cmd = show.cli.commands["isis"].commands["database"]
        executor(test_vector, show, exec_cmd)


class TestIsisHostname(object):

    @classmethod
    def setup_class(cls):
        print("SETUP")

    @pytest.mark.parametrize('setup_single_isis_instance, test_vector',
                             [
                                 ('isis_hostname_output', 'isis_hostname'),
                                 ('isis_hostname_invalid_help_output', 'isis_hostname_invalid_help')
                             ],
                             indirect=['setup_single_isis_instance'])
    def test_bgp_neighbors(self,
                           setup_isis_commands,
                           setup_single_isis_instance,
                           test_vector):
        show = setup_isis_commands
        exec_cmd = show.cli.commands["isis"].commands["hostname"]
        executor(test_vector, show, exec_cmd)


class TestIsisInterface(object):

    @classmethod
    def setup_class(cls):
        print("SETUP")

    @pytest.mark.parametrize('setup_single_isis_instance, test_vector',
                             [
                                 ('isis_interface_output', 'isis_interface'),
                                 ('isis_interface_ifname_output', 'isis_interface_ifname'),
                                 ('isis_interface_verbose_output', 'isis_interface_verbose'),
                                 ('isis_interface_ifname_verbose_output', 'isis_interface_ifname_verbose'),
                                 ('isis_interface_unknown_ifname_output', 'isis_interface_unknown_ifname'),
                                 ('isis_interface_unknown_ifname_output', 'isis_interface_unknown_ifname'),
                                 ('isis_interface_display_output', 'isis_interface_display')
                             ],
                             indirect=['setup_single_isis_instance'])
    def test_isis_interface(self,
                            setup_isis_commands,
                            setup_single_isis_instance,
                            test_vector):
        show = setup_isis_commands
        exec_cmd = show.cli.commands["isis"].commands["interface"]
        executor(test_vector, show, exec_cmd)


class TestIsisTopology(object):

    @classmethod
    def setup_class(cls):
        print("SETUP")

    @pytest.mark.parametrize('setup_single_isis_instance, test_vector',
                             [
                                 ('isis_topology_output', 'isis_topology'),
                                 ('isis_topology_invalid_help_output', 'isis_topology_invalid_help'),
                                 ('isis_topology_level_1_output', 'isis_topology_level_1'),
                                 ('isis_topology_level_2_output', 'isis_topology_level_2')
                             ],
                             indirect=['setup_single_isis_instance'])
    def test_isis_topology(self,
                           setup_isis_commands,
                           setup_single_isis_instance,
                           test_vector):
        show = setup_isis_commands
        exec_cmd = show.cli.commands["isis"].commands["topology"]
        executor(test_vector, show, exec_cmd)


class TestIsisSummary(object):

    @classmethod
    def setup_class(cls):
        print("SETUP")

    @pytest.mark.parametrize('setup_single_isis_instance, test_vector',
                            [
                                ('isis_summary_output', 'isis_summary'),
                                ('isis_summary_invalid_help_output', 'isis_summary_invalid_help')
                            ],
                            indirect=['setup_single_isis_instance'])
    def test_isis_summary(self,
                        setup_isis_commands,
                        setup_single_isis_instance,
                        test_vector):
        show = setup_isis_commands
        exec_cmd = show.cli.commands["isis"].commands["summary"]
        executor(test_vector, show, exec_cmd)


class TestShowRunIsis(object):

    @classmethod
    def setup_class(cls):
        print("SETUP")

    @pytest.mark.parametrize('setup_single_isis_instance, test_vector',
                             [
                                ('show_run_isis_output', 'show_run_isis'),
                                ('show_run_isis_invalid_help_output', 'show_run_isis_invalid_help')
                             ],
                             indirect=['setup_single_isis_instance'])
    def test_show_run_isis(self,
                           setup_isis_commands,
                           setup_single_isis_instance,
                           test_vector):
        show = setup_isis_commands
        exec_cmd = show.cli.commands["runningconfiguration"].commands["isis"]
        executor(test_vector, show, exec_cmd)

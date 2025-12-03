import os
import sys
import pytest
import mock
from importlib import reload

from click.testing import CliRunner

from utilities_common.db import Db

modules_path = os.path.join(os.path.dirname(__file__), "..")
test_path = os.path.join(modules_path, "tests")
sys.path.insert(0, modules_path)
sys.path.insert(0, test_path)
mock_db_path = os.path.join(test_path, "int_ip_input")


class TestIntIp(object):
    @pytest.fixture(scope="class", autouse=True)
    def setup_class(cls):
        print("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        import config.main as config
        reload(config)
        yield
        print("TEARDOWN")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        from .mock_tables import dbconnector
        dbconnector.dedicated_dbs = {}

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['ip_route_for_int_ip'], indirect=['setup_single_bgp_instance'])
    def test_config_int_ip_rem(
            self,
            get_cmd_module,
            setup_single_bgp_instance):
        (config, show) = get_cmd_module
        jsonfile_config = os.path.join(mock_db_path, "config_db.json")
        from .mock_tables import dbconnector
        dbconnector.dedicated_dbs['CONFIG_DB'] = jsonfile_config

        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        # remove vlan IP`s
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet16", "192.168.10.1/24"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['ip_route_for_int_ip'], indirect=['setup_single_bgp_instance'])
    def test_config_int_ip_rem_static(
            self,
            get_cmd_module,
            setup_single_bgp_instance):
        (config, show) = get_cmd_module
        jsonfile_config = os.path.join(mock_db_path, "config_db")
        from .mock_tables import dbconnector
        dbconnector.dedicated_dbs['CONFIG_DB'] = jsonfile_config

        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet2", "192.168.0.1/24"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code != 0
            assert "Error: Cannot remove the last IP entry of interface Ethernet2. A static ip route is still bound to the RIF." in result.output
            assert mock_run_command.call_count == 0

        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet8", "192.168.3.1/24"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code != 0
            assert "Error: Cannot remove the last IP entry of interface Ethernet8. A static ipv6 route is still bound to the RIF." in result.output
            assert mock_run_command.call_count == 0

        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Vlan2", "192.168.1.1/21"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code != 0
            assert "Error: Cannot remove the last IP entry of interface Vlan2. A static ip route is still bound to the RIF." in result.output
            assert mock_run_command.call_count == 0

        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["PortChannel2", "10.0.0.56/31"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code != 0
            assert "Error: Cannot remove the last IP entry of interface PortChannel2. A static ip route is still bound to the RIF." in result.output
            assert mock_run_command.call_count == 0

        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet4", "192.168.4.1/24"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['ip_route_for_int_ip'], indirect=['setup_single_bgp_instance'])
    def test_config_int_ip_rem_sub_intf(
            self,
            get_cmd_module,
            setup_single_bgp_instance):
        (config, _) = get_cmd_module
        jsonfile_config = os.path.join(mock_db_path, "config_db")
        from .mock_tables import dbconnector
        dbconnector.dedicated_dbs['CONFIG_DB'] = jsonfile_config

        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        # remove vlan IP`s
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            print(db.cfgdb.get_table('INTERFACE'))
            assert ('Ethernet16.16', '16.1.1.1/16') in db.cfgdb.get_table('VLAN_SUB_INTERFACE')
            assert 'Ethernet16.16' in db.cfgdb.get_table('VLAN_SUB_INTERFACE')
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet16.16", "16.1.1.1/16"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            # removing IP should only remove the INTERFACE,IP key. The regular INTERFACE key should still exists for sub interface
            assert ('Ethernet16.16', '16.1.1.1/16') not in db.cfgdb.get_table('VLAN_SUB_INTERFACE')
            assert 'Ethernet16.16' in db.cfgdb.get_table('VLAN_SUB_INTERFACE')


class TestIntIpMultiasic(object):
    @pytest.fixture(scope="class", autouse=True)
    def setup_class(cls):
        print("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        from .mock_tables import dbconnector
        from .mock_tables import mock_multi_asic
        reload(mock_multi_asic)
        dbconnector.load_namespace_config()
        yield
        print("TEARDOWN")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        # change back to single asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_single_asic
        reload(mock_single_asic)
        dbconnector.dedicated_dbs = {}
        dbconnector.load_namespace_config()

    @pytest.mark.parametrize('setup_multi_asic_bgp_instance',
                             ['ip_route_for_int_ip'], indirect=['setup_multi_asic_bgp_instance'])
    def test_config_int_ip_rem_static_multiasic(
            self,
            get_cmd_module,
            setup_multi_asic_bgp_instance):
        (config, show) = get_cmd_module
        jsonfile_config = os.path.join(mock_db_path, "config_db")
        from .mock_tables import dbconnector
        dbconnector.dedicated_dbs['CONFIG_DB'] = jsonfile_config

        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb, 'namespace': 'test_ns'}

        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet2", "192.168.0.1/24"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code != 0
            assert "Error: Cannot remove the last IP entry of interface Ethernet2. A static ip route is still bound to the RIF." in result.output
            assert mock_run_command.call_count == 0

        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet8", "192.168.3.1/24"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code != 0
            assert "Error: Cannot remove the last IP entry of interface Ethernet8. A static ipv6 route is still bound to the RIF." in result.output
            assert mock_run_command.call_count == 0

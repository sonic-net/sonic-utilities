import os
from unittest import mock

from click.testing import CliRunner

import config.main as config
from utilities_common.db import Db
import utilities_common.bgp_util as bgp_util


class TestConfigVRRP(object):
    _old_run_bgp_command = None

    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        cls._old_run_bgp_command = bgp_util.run_bgp_command
        bgp_util.run_bgp_command = mock.MagicMock(
            return_value=cls.mock_run_bgp_command())
        print("SETUP")

    ''' Tests for VRRPv4 and VRRPv6  '''

    def mock_run_bgp_command():
        return ""

    def test_add_del_vrrp_instance_without_vip(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config int ip add Ethernet64 10.10.10.1/24
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet64", "10.10.10.1/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '10.10.10.1/24') in db.cfgdb.get_table('INTERFACE')

        # config int ip add Ethernet63 9.9.9.1/24
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet63", "9.9.9.1/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet63', '9.9.9.1/24') in db.cfgdb.get_table('INTERFACE')

        # config int vrrp remove Ethernet63 7
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["remove"],
                               ["Ethernet63", "7"], obj=obj)
        print(result.exit_code, result.output)
        assert "Ethernet63 dose not configured the vrrp instance 7!" in result.output
        assert result.exit_code != 0

        # config int vrrp add Ethernet64 8
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["add"],
                               ["Ethernet64", "8"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP')

        # config int vrrp add Ethernet64 8
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["add"],
                               ["Ethernet64", "8"], obj=obj)
        print(result.exit_code, result.output)
        assert "Ethernet64 has already configured the vrrp instance 8!" in result.output
        assert result.exit_code != 0

        # config int vrrp add Ethernet63 7
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["add"],
                               ["Ethernet63", "7"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet63', '7') in db.cfgdb.get_table('VRRP')

        # config int vrrp remove Ethernet64 8
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["remove"],
                               ["Ethernet64", "8"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') not in db.cfgdb.get_table('VRRP')

        # config int vrrp remove Ethernet63 7
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["remove"],
                               ["Ethernet63", "7"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet63', '7') not in db.cfgdb.get_table('VRRP')

        # check interface_name is valid
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["add"],
                               ["Ethernt64", "8"], obj=obj)
        print(result.exit_code, result.output)
        assert "'interface_name' is not valid" in result.output
        assert result.exit_code != 0

        # check interface is Router interface
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["add"],
                               ["Ethernet2", "7"], obj=obj)
        print(result.exit_code, result.output)
        assert "Router Interface 'Ethernet2' not found" in result.output
        assert result.exit_code != 0

        # check interface_name is valid
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["remove"],
                               ["Ethernt64", "8"], obj=obj)
        print(result.exit_code, result.output)
        assert "'interface_name' is not valid" in result.output
        assert result.exit_code != 0

        # check interface is Router interface
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["remove"],
                               ["Ethernet2", "7"], obj=obj)
        print(result.exit_code, result.output)
        assert "Router Interface 'Ethernet2' not found" in result.output
        assert result.exit_code != 0

        # config int ip remove Ethernet64 10.10.10.1/24
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet64", "10.10.10.1/24"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet64', '10.10.10.1/24') not in db.cfgdb.get_table('INTERFACE')

        # config int ip remove Ethernet63 9.9.9.1/24
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet63", "9.9.9.1/24"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet63', '9.9.9.1/24') not in db.cfgdb.get_table('INTERFACE')

    def test_add_del_vrrp6_instance_without_vip(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config int ip add Ethernet64 100::64/64
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet64", "100::64/64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '100::64/64') in db.cfgdb.get_table('INTERFACE')

        # config int ip add Ethernet63 99::64/64
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet63", "99::64/64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet63', '99::64/64') in db.cfgdb.get_table('INTERFACE')

        # config int vrrp6 add Ethernet64 8
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["add"],
                               ["Ethernet64", "8"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP6')

        # config int vrrp6 add Ethernet63 7
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["add"],
                               ["Ethernet63", "7"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet63', '7') in db.cfgdb.get_table('VRRP6')

        # config int vrrp6 add Ethernet64 8
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["add"],
                               ["Ethernet64", "8"], obj=obj)
        print(result.exit_code, result.output)
        assert "Ethernet64 has already configured the Vrrpv6 instance 8!" in result.output
        assert result.exit_code != 0

        # check interface_name is valid
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["add"],
                               ["Ethernt64", "8"], obj=obj)
        print(result.exit_code, result.output)
        assert "'interface_name' is not valid" in result.output
        assert result.exit_code != 0

        # check interface is Router interface
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["add"],
                               ["Ethernet2", "7"], obj=obj)
        print(result.exit_code, result.output)
        assert "Router Interface 'Ethernet2' not found" in result.output
        assert result.exit_code != 0

        # config int vrrp6 remove Ethernet64 8
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["remove"],
                               ["Ethernet64", "8"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') not in db.cfgdb.get_table('VRRP6')

        # config int ip remove Ethernet64 100::64/64
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet64", "100::64/64"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet64', '100::64/64') not in db.cfgdb.get_table('INTERFACE')

        # config int ip remove Ethernet63 99::64/64
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet63", "99::64/64"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet63', '99::64/64') not in db.cfgdb.get_table('INTERFACE')

    def test_add_del_vrrp_instance(self):
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        # config int ip add Ethernet64 10.10.10.1/24
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet64", "10.10.10.1/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '10.10.10.1/24') in db.cfgdb.get_table('INTERFACE')

        # config int ip add Ethernet63 9.9.9.1/24
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet63", "9.9.9.1/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet63', '9.9.9.1/24') in db.cfgdb.get_table('INTERFACE')

        # config int ip add Ethernet62 8.8.8.1/24
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet62", "8.8.8.1/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet62', '8.8.8.1/24') in db.cfgdb.get_table('INTERFACE')

        # check interface_name is valid
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["ip"].commands["add"],
                               ["Ethernt64", "8", "10.10.10.8/24"], obj=obj)
        print(result.exit_code, result.output)
        assert "'interface_name' is not valid" in result.output
        assert result.exit_code != 0

        # check interface is Router interface
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["ip"].commands["add"],
                               ["Ethernet2", "8", "10.10.10.8/24"], obj=obj)
        print(result.exit_code, result.output)
        assert "Router Interface 'Ethernet2' not found" in result.output
        assert result.exit_code != 0

        # config int vrrp ip add Ethernet64 8 10.10.10.8/24
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["ip"].commands["add"],
                               ["Ethernet64", "8", "10.10.10.8/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP')
        assert db.cfgdb.get_table('VRRP')['Ethernet64', '8']['vip'] == ['10.10.10.8/24']

        # config int vrrp ip add Ethernet64 8 10.10.10.16/24
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["ip"].commands["add"],
                               ["Ethernet64", "8", "10.10.10.16/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP')
        assert db.cfgdb.get_table('VRRP')['Ethernet64', '8']['vip'] == ['10.10.10.8/24', '10.10.10.16/24']

        # config int vrrp ip add Ethernet62 7 8.8.8.16/24
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["ip"].commands["add"],
                               ["Ethernet62", "7", "8.8.8.16/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet62', '7') in db.cfgdb.get_table('VRRP')
        assert db.cfgdb.get_table('VRRP')['Ethernet62', '7']['vip'] == ['8.8.8.16/24']

        # config int vrrp ip add Ethernet62 7 8.8.8.16/24
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["ip"].commands["add"],
                               ["Ethernet62", "7", "8.8.8.16/24"], obj=obj)
        print(result.exit_code, result.output)
        assert "8.8.8.16/24 has already configured" in result.output
        assert result.exit_code != 0

        # config int vrrp ip add Ethernet62 7 0.0.0.0
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["ip"].commands["add"],
                               ["Ethernet62", "7", "0.0.0.0"], obj=obj)
        print(result.exit_code, result.output)
        assert "IPv4 address 0.0.0.0/32 is Zero" in result.output
        assert result.exit_code != 0

        # config int vrrp ip add Ethernet62 7 777.256.1.1/24
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["ip"].commands["add"],
                               ["Ethernet62", "7", "777.256.1.1/24"], obj=obj)
        print(result.exit_code, result.output)
        assert "IP address 777.256.1.1/24 is not valid" in result.output
        assert result.exit_code != 0

        # config int vrrp ip add Ethernet62 7 224.0.0.41/24
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["ip"].commands["add"],
                               ["Ethernet62", "7", "224.0.0.41/24"], obj=obj)
        print(result.exit_code, result.output)
        assert "IP address 224.0.0.41/24 is multicast" in result.output
        assert result.exit_code != 0

        # config int vrrp ip add Ethernet62 7 6.6.6.6
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["ip"].commands["add"],
                               ["Ethernet62", "7", "6.6.6.6"], obj=obj)
        print(result.exit_code, result.output)
        assert "IP address 6.6.6.6 is missing a mask." in result.output
        assert result.exit_code != 0

        # config int vrrp ip remove Ethernet64 8 10.10.10.8/24
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["ip"].commands["remove"],
                               ["Ethernet64", "8", "10.10.10.8/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP')
        assert db.cfgdb.get_table('VRRP')['Ethernet64', '8']['vip'] == ['10.10.10.16/24']

        # config int vrrp ip remove Ethernet64 8 10.10.10.8/24
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["ip"].commands["remove"],
                               ["Ethernet64", "8", "10.10.10.8/24"], obj=obj)
        print(result.exit_code, result.output)
        assert "10.10.10.8/24 is not configured on the vrrp instance" in result.output
        assert result.exit_code != 0

        # config int vrrp ip remove Ethernet64 8 10.10.10.888/24
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["ip"].commands["remove"],
                               ["Ethernet64", "8", "10.10.10.888/24"], obj=obj)
        print(result.exit_code, result.output)
        assert "IP address is not valid:" in result.output
        assert result.exit_code != 0

        # config int vrrp ip remove Ethernet64 8 10.10.10.16/24
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["ip"].commands["remove"],
                               ["Ethernet64", "8", "10.10.10.16/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP')
        assert db.cfgdb.get_table('VRRP')['Ethernet64', '8']['vip'] == ['']

        # config int vrrp remove Ethernet64 8
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["remove"],
                               ["Ethernet64", "8"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') not in db.cfgdb.get_table('VRRP')

        # check interface_name is valid
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["ip"].commands["remove"],
                               ["Ethernt64", "8", "10.10.10.16/24"], obj=obj)
        print(result.exit_code, result.output)
        assert "'interface_name' is not valid" in result.output
        assert result.exit_code != 0

        # check interface is Router interface
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["ip"].commands["remove"],
                               ["Ethernet2", "8", "10.10.10.16/24"], obj=obj)
        print(result.exit_code, result.output)
        assert "Router Interface 'Ethernet2' not found" in result.output
        assert result.exit_code != 0

        # config int vrrp remove Ethernet63 9
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["ip"].commands["remove"],
                               ["Ethernet63", "9", "10.10.10.16/24"], obj=obj)
        print(result.exit_code, result.output)
        assert "10.10.10.16/24 is not configured on the vrrp instance" in result.output
        assert result.exit_code != 0

        # config int ip remove Ethernet64 10.10.10.1/24
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet64", "10.10.10.1/24"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet64', '10.10.10.1/24') not in db.cfgdb.get_table('INTERFACE')

        # config int ip remove Ethernet63 9.9.9.1/24
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet63", "9.9.9.1/24"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet63', '9.9.9.1/24') not in db.cfgdb.get_table('INTERFACE')

        # config int ip remove Ethernet62 8.8.8.1/24
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet62", "8.8.8.1/24"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet62', '8.8.8.1/24') not in db.cfgdb.get_table('INTERFACE')

    def test_add_del_vrrp6_instance(self):
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        # config int ip add Ethernet64 100::1/64
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet64", "100::1/64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '100::1/64') in db.cfgdb.get_table('INTERFACE')

        # config int ip add Ethernet63 99::1/64
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet63", "99::1/64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet63', '99::1/64') in db.cfgdb.get_table('INTERFACE')

        # config int ip add Ethernet62 88::1/64
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet62", "88::1/64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet62', '88::1/64') in db.cfgdb.get_table('INTERFACE')

        # check interface_name is valid
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["ipv6"].commands["add"],
                               ["Ethernt64", "8", "100::8/64"], obj=obj)
        print(result.exit_code, result.output)
        assert "'interface_name' is not valid" in result.output
        assert result.exit_code != 0

        # check interface is Router interface
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["ipv6"].commands["add"],
                               ["Ethernet2", "8", "100::8/64"], obj=obj)
        print(result.exit_code, result.output)
        assert "Router Interface 'Ethernet2' not found" in result.output
        assert result.exit_code != 0

        # config int vrrp6 ipv6 add Ethernet64 8 100::8/64
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["ipv6"].commands["add"],
                               ["Ethernet64", "8", "100::8/64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP6')
        assert db.cfgdb.get_table('VRRP6')['Ethernet64', '8']['vip'] == ['100::8/64']

        # config int vrrp6 ipv6 add Ethernet64 8 100::16/64
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["ipv6"].commands["add"],
                               ["Ethernet64", "8", "100::16/64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP6')
        assert db.cfgdb.get_table('VRRP6')['Ethernet64', '8']['vip'] == ['100::8/64', '100::16/64']

        # config int vrrp6 ipv6 add Ethernet62 7 88::16/64
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["ipv6"].commands["add"],
                               ["Ethernet62", "7", "88::16/64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet62', '7') in db.cfgdb.get_table('VRRP6')
        assert db.cfgdb.get_table('VRRP6')['Ethernet62', '7']['vip'] == ['88::16/64']

        # config int vrrp6 ipv6 add Ethernet62 7 88::16/64
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["ipv6"].commands["add"],
                               ["Ethernet62", "7", "88::16/64"], obj=obj)
        print(result.exit_code, result.output)
        assert "88::16/64 has already configured" in result.output
        assert result.exit_code != 0

        # config int vrrp6 ipv6 add Ethernet62 7 ::
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["ipv6"].commands["add"],
                               ["Ethernet62", "7", "::"], obj=obj)
        print(result.exit_code, result.output)
        assert "IPv6 address ::/128 is unspecified" in result.output
        assert result.exit_code != 0

        # config int vrrp6 ipv6 add Ethernet62 7 785h::12/64
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["ipv6"].commands["add"],
                               ["Ethernet62", "7", "785h::12/64"], obj=obj)
        print(result.exit_code, result.output)
        assert "IP address 785h::12/64 is not valid" in result.output
        assert result.exit_code != 0

        # config int vrrp6 ipv6 add Ethernet62 7 88::2
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["ipv6"].commands["add"],
                               ["Ethernet62", "7", "88::2"], obj=obj)
        print(result.exit_code, result.output)
        assert "IPv6 address 88::2 is missing a mask." in result.output
        assert result.exit_code != 0

        # config int vrrp6 ipv6 remove Ethernet64 8 100::8/64
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp6"].commands["ipv6"].commands["remove"],
            ["Ethernet64", "8", "100::8/64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP6')
        assert db.cfgdb.get_table('VRRP6')['Ethernet64', '8']['vip'] == ['100::16/64']

        # config int vrrp6 ipv6 remove Ethernet64 8 100::8/64
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp6"].commands["ipv6"].commands["remove"],
            ["Ethernet64", "8", "100::8/64"], obj=obj)
        print(result.exit_code, result.output)
        assert "100::8/64 is not configured on the Vrrpv6 instance 8!" in result.output
        assert result.exit_code != 0

        # config int vrrp6 ipv6 remove Ethernet64 8 100::16/64
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp6"].commands["ipv6"].commands["remove"],
            ["Ethernet64", "8", "100::16/64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP6')
        assert db.cfgdb.get_table('VRRP6')['Ethernet64', '8']['vip'] == ['']

        # config int vrrp6 remove Ethernet64 8
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["remove"],
                               ["Ethernet64", "8"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') not in db.cfgdb.get_table('VRRP6')

        # check interface_name is valid
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp6"].commands["ipv6"].commands["remove"],
            ["Ethernt64", "8", "100::16/64"], obj=obj)
        print(result.exit_code, result.output)
        assert "'interface_name' is not valid" in result.output
        assert result.exit_code != 0

        # check interface is Router interface
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp6"].commands["ipv6"].commands["remove"],
            ["Ethernet2", "8", "100::16/64"], obj=obj)
        print(result.exit_code, result.output)
        assert "Router Interface 'Ethernet2' not found" in result.output
        assert result.exit_code != 0

        # config int vrrp remove Ethernet63 9
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp6"].commands["ipv6"].commands["remove"],
            ["Ethernet63", "9", "100::16/64"], obj=obj)
        print(result.exit_code, result.output)
        assert "100::16/64 is not configured on the Vrrpv6 instance 9" in result.output
        assert result.exit_code != 0

        # config int vrrp6 ipv6 remove Ethernet64 8 88cg::2/64
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp6"].commands["ipv6"].commands["remove"],
            ["Ethernet64", "8", "88cg::2/64"], obj=obj)
        print(result.exit_code, result.output)
        assert "IPv6 address is not valid:" in result.output
        assert result.exit_code != 0

        # config int ip remove Ethernet64 100::1/64
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet64", "100::1/64"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet64', '100::1/64') not in db.cfgdb.get_table('INTERFACE')

        # config int ip remove Ethernet63 99::1/64
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet63", "99::1/64"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet63', '99::1/64') not in db.cfgdb.get_table('INTERFACE')

        # config int ip remove Ethernet62 88::1/64
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet62", "88::1/64"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet62', '88::1/64') not in db.cfgdb.get_table('INTERFACE')

    def test_add_del_vrrp_instance_track_intf(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config int ip add Ethernet64 10.10.10.1/24
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet64", "10.10.10.1/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '10.10.10.1/24') in db.cfgdb.get_table('INTERFACE')

        # config int ip add Ethernet5 10.10.10.5/24
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet5", "10.10.10.5/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet5', '10.10.10.5/24') in db.cfgdb.get_table('INTERFACE')

        # config int ip add Ethernet6 10.10.10.6/24
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet6", "10.10.10.6/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet6', '10.10.10.6/24') in db.cfgdb.get_table('INTERFACE')

        # config int ip add Ethernet7 10.10.10.7/24
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet7", "10.10.10.7/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet7', '10.10.10.7/24') in db.cfgdb.get_table('INTERFACE')

        # config int vrrp ip add Ethernet64 8 10.10.10.8/24
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["ip"].commands["add"],
                               ["Ethernet64", "8", "10.10.10.8/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP')
        assert db.cfgdb.get_table('VRRP')['Ethernet64', '8']['vip'] == ['10.10.10.8/24']

        # check interface_name is valid
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp"].commands["track_interface"].commands["add"],
            ["Ethernt64", "8", "Ethernet5", "20"], obj=obj)
        print(result.exit_code, result.output)
        assert "'interface_name' is not valid" in result.output
        assert result.exit_code != 0

        # check interface is Router interface
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp"].commands["track_interface"].commands["add"],
            ["Ethernet2", "8", "Ethernet5", "20"], obj=obj)
        print(result.exit_code, result.output)
        assert "Router Interface 'Ethernet2' not found" in result.output
        assert result.exit_code != 0

        # check track_interface_name is valid
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp"].commands["track_interface"].commands["add"],
            ["Ethernet64", "8", "Ethernt5", "20"], obj=obj)
        print(result.exit_code, result.output)
        assert "'track_interface' is not valid." in result.output
        assert result.exit_code != 0

        # check track_interface_name is valid
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp"].commands["track_interface"].commands["add"],
            ["Ethernet64", "8", "Ethernet2", "20"], obj=obj)
        print(result.exit_code, result.output)
        assert "Router Interface 'Ethernet2' not found" in result.output
        assert result.exit_code != 0

        # config interface vrrp track_interface add Ethernet64 8 Ethernet5 20
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp"].commands["track_interface"].commands["add"],
            ["Ethernet64", "8", "Ethernet5", "20"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8', 'Ethernet5') in db.cfgdb.get_table('VRRP_TRACK')
        assert db.cfgdb.get_table('VRRP_TRACK')['Ethernet64', '8', 'Ethernet5']['priority_increment'] == '20'

        # config interface vrrp track_interface add Ethernet64 8 Ethernet6 30
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp"].commands["track_interface"].commands["add"],
            ["Ethernet64", "8", "Ethernet6", "30"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8', 'Ethernet6') in db.cfgdb.get_table('VRRP_TRACK')
        assert db.cfgdb.get_table('VRRP_TRACK')['Ethernet64', '8', 'Ethernet6']['priority_increment'] == '30'

        # config interface vrrp track_interface add Ethernet64 8 Ethernet6 25
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp"].commands["track_interface"].commands["add"],
            ["Ethernet64", "8", "Ethernet6", "25"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8', 'Ethernet6') in db.cfgdb.get_table('VRRP_TRACK')
        assert db.cfgdb.get_table('VRRP_TRACK')['Ethernet64', '8', 'Ethernet6']['priority_increment'] == '25'

        # config interface vrrp track_interface add Ethernet64 8 Ethernet7 80
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp"].commands["track_interface"].commands["add"],
            ["Ethernet64", "8", "Ethernet7", "80"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

        # config interface vrrp track_interface add Ethernet7 7 Ethernet5 40
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp"].commands["track_interface"].commands["add"],
            ["Ethernet7", "7", "Ethernet5", "40"], obj=obj)
        print(result.exit_code, result.output)
        assert "vrrp instance 7 not found on interface Ethernet7" in result.output
        assert result.exit_code != 0

        # config interface vrrp track_interface remove Ethernet64 8 Ethernet6
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp"].commands["track_interface"].commands["remove"],
            ["Ethernet64", "8", "Ethernet6"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8', 'Ethernet6') not in db.cfgdb.get_table('VRRP_TRACK')

        # config interface vrrp track_interface remove Ethernet64 8 Ethernet5
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp"].commands["track_interface"].commands["remove"],
            ["Ethernet64", "8", "Ethernet5"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8', 'Ethernet5') not in db.cfgdb.get_table('VRRP_TRACK')

        # check interface_name is valid
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp"].commands["track_interface"].commands["remove"],
            ["Ethernt64", "8", "Ethernet5"], obj=obj)
        print(result.exit_code, result.output)
        assert "'interface_name' is not valid" in result.output
        assert result.exit_code != 0

        # check interface is Router interface
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp"].commands["track_interface"].commands["remove"],
            ["Ethernet2", "8", "Ethernet5"], obj=obj)
        print(result.exit_code, result.output)
        assert "Router Interface 'Ethernet2' not found" in result.output
        assert result.exit_code != 0

        # check track_interface_name is valid
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp"].commands["track_interface"].commands["remove"],
            ["Ethernet64", "8", "Ethernt5"], obj=obj)
        print(result.exit_code, result.output)
        assert "'track_interface' is not valid." in result.output
        assert result.exit_code != 0

        # check track_interface_name is valid
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp"].commands["track_interface"].commands["remove"],
            ["Ethernet64", "8", "Ethernet2"], obj=obj)
        print(result.exit_code, result.output)
        assert "Ethernet2 is not configured on the vrrp instance 8" in result.output
        assert result.exit_code != 0

        # config interface vrrp track_interface remove Ethernet7 7 Ethernet5
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp"].commands["track_interface"].commands["remove"],
            ["Ethernet7", "7", "Ethernet5"], obj=obj)
        print(result.exit_code, result.output)
        assert "vrrp instance 7 not found on interface Ethernet7" in result.output
        assert result.exit_code != 0

        # config int vrrp remove Ethernet64 8
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["remove"],
                               ["Ethernet64", "8"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') not in db.cfgdb.get_table('VRRP')

        # config int ip remove Ethernet7 10.10.10.7/24
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet7", "10.10.10.7/24"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet7', '10.10.10.7/24') not in db.cfgdb.get_table('INTERFACE')

        # config int ip remove Ethernet6 10.10.10.6/24
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet6", "10.10.10.6/24"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet6', '10.10.10.6/24') not in db.cfgdb.get_table('INTERFACE')

        # config int ip remove Ethernet5 10.10.10.5/24
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet5", "10.10.10.5/24"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet5', '10.10.10.5/24') not in db.cfgdb.get_table('INTERFACE')

        # config int ip remove Ethernet64 10.10.10.1/24
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet64", "10.10.10.1/24"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet64', '10.10.10.1/24') not in db.cfgdb.get_table('INTERFACE')

    def test_add_del_vrrp6_instance_track_intf(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config int ip add Ethernet64 100::64/64
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet64", "100::64/64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '100::64/64') in db.cfgdb.get_table('INTERFACE')

        # config int ip add Ethernet5 100::5/64
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet5", "100::5/64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet5', '100::5/64') in db.cfgdb.get_table('INTERFACE')

        # config int ip add Ethernet6 100::6/64
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet6", "100::6/64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet6', '100::6/64') in db.cfgdb.get_table('INTERFACE')

        # config int ip add Ethernet7 100::7/64
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet7", "100::7/64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet7', '100::7/64') in db.cfgdb.get_table('INTERFACE')

        # config int vrrp6 ipv6 add Ethernet64 8 100::1/64
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["ipv6"].commands["add"],
                               ["Ethernet64", "8", "100::1/64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP6')
        assert db.cfgdb.get_table('VRRP6')['Ethernet64', '8']['vip'] == ['100::1/64']

        # check interface_name is valid
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp6"].commands["track_interface"].commands["add"],
            ["Ethernt64", "8", "Ethernet", "20"], obj=obj)
        print(result.exit_code, result.output)
        assert "'interface_name' is not valid" in result.output
        assert result.exit_code != 0

        # check interface is Router interface
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp6"].commands["track_interface"].commands["add"],
            ["Ethernet2", "8", "Ethernet5", "20"], obj=obj)
        print(result.exit_code, result.output)
        assert "Router Interface 'Ethernet2' not found" in result.output
        assert result.exit_code != 0

        # check track_interface_name is valid
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp6"].commands["track_interface"].commands["add"],
            ["Ethernet64", "8", "Ethernt5", "20"], obj=obj)
        print(result.exit_code, result.output)
        assert "'track_interface' is not valid." in result.output
        assert result.exit_code != 0

        # check track_interface_name is valid
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp6"].commands["track_interface"].commands["add"],
            ["Ethernet64", "8", "Ethernet2", "20"], obj=obj)
        print(result.exit_code, result.output)
        assert "Router Interface 'Ethernet2' not found" in result.output
        assert result.exit_code != 0

        # config interface vrrp6 track_interface add Ethernet7 8 Ethernet5 20
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp6"].commands["track_interface"].commands["add"],
            ["Ethernet7", "8", "Ethernet5", "20"], obj=obj)
        print(result.exit_code, result.output)
        assert "vrrp6 instance 8 not found on interface Ethernet7" in result.output
        assert result.exit_code != 0

        # config interface vrrp6 track_interface add Ethernet64 8 Ethernet5 20
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp6"].commands["track_interface"].commands["add"],
            ["Ethernet64", "8", "Ethernet5", "20"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8', 'Ethernet5') in db.cfgdb.get_table('VRRP6_TRACK')
        assert db.cfgdb.get_table('VRRP6_TRACK')['Ethernet64', '8', 'Ethernet5']['priority_increment'] == '20'

        # config interface vrrp6 track_interface add Ethernet64 8 Ethernet6 30
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp6"].commands["track_interface"].commands["add"],
            ["Ethernet64", "8", "Ethernet6", "30"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8', 'Ethernet6') in db.cfgdb.get_table('VRRP6_TRACK')
        assert db.cfgdb.get_table('VRRP6_TRACK')['Ethernet64', '8', 'Ethernet6']['priority_increment'] == '30'

        # config interface vrrp6 track_interface add Ethernet64 8 Ethernet7 80
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp6"].commands["track_interface"].commands["add"],
            ["Ethernet64", "8", "Ethernet7", "80"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

        # config interface vrrp6 track_interface remove Ethernet64 8 Ethernet6
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp6"].commands["track_interface"].commands["remove"],
            ["Ethernet64", "8", "Ethernet6"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8', 'Ethernet6') not in db.cfgdb.get_table('VRRP6_TRACK')

        # config interface vrrp6 track_interface remove Ethernet64 8 Ethernet5
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp6"].commands["track_interface"].commands["remove"],
            ["Ethernet64", "8", "Ethernet5"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8', 'Ethernet5') not in db.cfgdb.get_table('VRRP6_TRACK')

        # config interface vrrp6 track_interface remove Ethernet7 8 Ethernet5
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp6"].commands["track_interface"].commands["remove"],
            ["Ethernet7", "8", "Ethernet5"], obj=obj)
        print(result.exit_code, result.output)
        assert "vrrp6 instance 8 not found on interface Ethernet7" in result.output
        assert result.exit_code != 0

        # check interface_name is valid
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp6"].commands["track_interface"].commands["remove"],
            ["Ethernt64", "8", "Ethernet5"], obj=obj)
        print(result.exit_code, result.output)
        assert "'interface_name' is not valid" in result.output
        assert result.exit_code != 0

        # check interface is Router interface
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp6"].commands["track_interface"].commands["remove"],
            ["Ethernet2", "8", "Ethernet5"], obj=obj)
        print(result.exit_code, result.output)
        assert "Router Interface 'Ethernet2' not found" in result.output
        assert result.exit_code != 0

        # check track_interface_name is valid
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp6"].commands["track_interface"].commands["remove"],
            ["Ethernet64", "8", "Ethernt5"], obj=obj)
        print(result.exit_code, result.output)
        assert "'track_interface' is not valid." in result.output
        assert result.exit_code != 0

        # check track_interface_name is valid
        result = runner.invoke(
            config.config.commands["interface"].commands["vrrp6"].commands["track_interface"].commands["remove"],
            ["Ethernet64", "8", "Ethernet2"], obj=obj)
        print(result.exit_code, result.output)
        assert "Ethernet2 is not configured on the vrrp6 instance 8" in result.output
        assert result.exit_code != 0

        # config int vrrp6 remove Ethernet64 8
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["remove"],
                               ["Ethernet64", "8"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') not in db.cfgdb.get_table('VRRP6')

        # config int ip remove Ethernet7 100::7/64
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet7", "100::7/64"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet7', '100::7/64') not in db.cfgdb.get_table('INTERFACE')

        # config int ip remove Ethernet6 100::6/64
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet6", "100::6/64"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet6', '100::6/64') not in db.cfgdb.get_table('INTERFACE')

        # config int ip remove Ethernet5 100::5/64
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet5", "100::5/64"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet5', '100::5/64') not in db.cfgdb.get_table('INTERFACE')

        # config int ip remove Ethernet64 100::64/64
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet64", "100::64/64"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet64', '100::64/64') not in db.cfgdb.get_table('INTERFACE')

    def test_enable_disable_vrrp_instance_preempt(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config int ip add Ethernet64 10.10.10.1/24
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet64", "10.10.10.1/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '10.10.10.1/24') in db.cfgdb.get_table('INTERFACE')

        # config int vrrp ip add Ethernet64 8 10.10.10.8/24
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["ip"].commands["add"],
                               ["Ethernet64", "8", "10.10.10.8/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP')
        assert db.cfgdb.get_table('VRRP')['Ethernet64', '8']['vip'] == ['10.10.10.8/24']

        # check interface_name is valid
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["pre_empt"],
                               ["Ethernt64", "8", "disabled"], obj=obj)
        print(result.exit_code, result.output)
        assert "'interface_name' is not valid" in result.output
        assert result.exit_code != 0

        # check interface is Router interface
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["pre_empt"],
                               ["Ethernet2", "8", "disabled"], obj=obj)
        print(result.exit_code, result.output)
        assert "Router Interface 'Ethernet2' not found" in result.output
        assert result.exit_code != 0

        # check the vrrp instance is valid
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["pre_empt"],
                               ["Ethernet64", "9", "disabled"], obj=obj)
        print(result.exit_code, result.output)
        assert "vrrp instance 9 not found on interface Ethernet64" in result.output
        assert result.exit_code != 0

        # config interface vrrp vrrp pre_empt Ethernet64 8 disabled
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["pre_empt"],
                               ["Ethernet64", "8", "disabled"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP')
        assert db.cfgdb.get_table('VRRP')['Ethernet64', '8']['preempt'] == 'disabled'

        # config interface vrrp vrrp pre_empt Ethernet64 8 enabled
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["pre_empt"],
                               ["Ethernet64", "8", "enabled"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP')
        assert db.cfgdb.get_table('VRRP')['Ethernet64', '8']['preempt'] == 'enabled'

        # config int vrrp remove Ethernet64 8
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["remove"],
                               ["Ethernet64", "8"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') not in db.cfgdb.get_table('VRRP')

        # config int ip remove Ethernet64 10.10.10.1/24
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet64", "10.10.10.1/24"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet64', '10.10.10.1/24') not in db.cfgdb.get_table('INTERFACE')

    def test_enable_disable_vrrp6_instance_preempt(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config int ip add Ethernet64 10::8/64
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet64", "10::8/64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '10::8/64') in db.cfgdb.get_table('INTERFACE')

        # config int vrrp6 ipv6 add Ethernet64 8 10::1/64
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["ipv6"].commands["add"],
                               ["Ethernet64", "8", "10::1/64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP6')
        assert db.cfgdb.get_table('VRRP6')['Ethernet64', '8']['vip'] == ['10::1/64']

        # check interface_name is valid
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["pre_empt"],
                               ["Ethernt64", "8", "disabled"], obj=obj)
        print(result.exit_code, result.output)
        assert "'interface_name' is not valid" in result.output
        assert result.exit_code != 0

        # check interface is Router interface
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["pre_empt"],
                               ["Ethernet2", "8", "disabled"], obj=obj)
        print(result.exit_code, result.output)
        assert "Router Interface 'Ethernet2' not found" in result.output
        assert result.exit_code != 0

        # check the vrrp6 instance is valid
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["pre_empt"],
                               ["Ethernet64", "9", "disabled"], obj=obj)
        print(result.exit_code, result.output)
        assert "Vrrpv6 instance 9 not found on interface Ethernet64" in result.output
        assert result.exit_code != 0

        # config interface vrrp6 pre_empt Ethernet64 8 disabled
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["pre_empt"],
                               ["Ethernet64", "8", "disabled"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP6')
        assert db.cfgdb.get_table('VRRP6')['Ethernet64', '8']['preempt'] == 'disabled'

        # config interface vrrp vrrp pre_empt Ethernet64 8 enabled
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["pre_empt"],
                               ["Ethernet64", "8", "enabled"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP6')
        assert db.cfgdb.get_table('VRRP6')['Ethernet64', '8']['preempt'] == 'enabled'

        # config int vrrp remove Ethernet64 8
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["remove"],
                               ["Ethernet64", "8"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') not in db.cfgdb.get_table('VRRP6')

        # config int ip remove Ethernet64 10::8/64
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet64", "10::8/64"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet64', '10::8/64') not in db.cfgdb.get_table('INTERFACE')

    def test_config_vrrp_instance_adv_interval(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config int ip add Ethernet64 10.10.10.1/24
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet64", "10.10.10.1/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '10.10.10.1/24') in db.cfgdb.get_table('INTERFACE')

        # config int vrrp ip add Ethernet64 8 10.10.10.8/24
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["ip"].commands["add"],
                               ["Ethernet64", "8", "10.10.10.8/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP')
        assert db.cfgdb.get_table('VRRP')['Ethernet64', '8']['vip'] == ['10.10.10.8/24']

        # check interface_name is valid
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["adv_interval"],
                               ["Ethernt64", "8", "2"], obj=obj)
        print(result.exit_code, result.output)
        assert "'interface_name' is not valid" in result.output
        assert result.exit_code != 0

        # check interface is Router interface
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["adv_interval"],
                               ["Ethernet2", "8", "2"], obj=obj)
        print(result.exit_code, result.output)
        assert "Router Interface 'Ethernet2' not found" in result.output
        assert result.exit_code != 0

        # check the vrrp instance is valid
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["adv_interval"],
                               ["Ethernet64", "9", "2"], obj=obj)
        print(result.exit_code, result.output)
        assert "vrrp instance 9 not found on interface Ethernet64" in result.output
        assert result.exit_code != 0

        # config interface vrrp vrrp adv_interval Ethernet64 8 2
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["adv_interval"],
                               ["Ethernet64", "8", "2"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP')
        assert db.cfgdb.get_table('VRRP')['Ethernet64', '8']['adv_interval'] == '2'

        # config interface vrrp vrrp adv_interval Ethernet64 8 500
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["adv_interval"],
                               ["Ethernet64", "8", "500"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

        # config int vrrp remove Ethernet64 8
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["remove"],
                               ["Ethernet64", "8"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') not in db.cfgdb.get_table('VRRP')

        # config int ip remove Ethernet64 10.10.10.1/24
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet64", "10.10.10.1/24"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet64', '10.10.10.1/24') not in db.cfgdb.get_table('INTERFACE')

    def test_config_vrrp6_instance_adv_interval(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config int ip add Ethernet64 10::8/64
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet64", "10::8/64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '10::8/64') in db.cfgdb.get_table('INTERFACE')

        # config int vrrp6 ipv6 add Ethernet64 8 10::1/64
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["ipv6"].commands["add"],
                               ["Ethernet64", "8", "10::1/64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP6')
        assert db.cfgdb.get_table('VRRP6')['Ethernet64', '8']['vip'] == ['10::1/64']

        # check interface_name is valid
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["adv_interval"],
                               ["Ethernt64", "8", "2"], obj=obj)
        print(result.exit_code, result.output)
        assert "'interface_name' is not valid" in result.output
        assert result.exit_code != 0

        # check interface is Router interface
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["adv_interval"],
                               ["Ethernet2", "8", "2"], obj=obj)
        print(result.exit_code, result.output)
        assert "Router Interface 'Ethernet2' not found" in result.output
        assert result.exit_code != 0

        # check the vrrp instance is valid
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["adv_interval"],
                               ["Ethernet64", "9", "2"], obj=obj)
        print(result.exit_code, result.output)
        assert "Vrrpv6 instance 9 not found on interface Ethernet64" in result.output
        assert result.exit_code != 0

        # config interface vrrp6 adv_interval Ethernet64 8 2
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["adv_interval"],
                               ["Ethernet64", "8", "2"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP6')
        assert db.cfgdb.get_table('VRRP6')['Ethernet64', '8']['adv_interval'] == '2'

        # config interface vrrp6 adv_interval Ethernet64 8 500
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["adv_interval"],
                               ["Ethernet64", "8", "500"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

        # config int vrrp6 remove Ethernet64 8
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["remove"],
                               ["Ethernet64", "8"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') not in db.cfgdb.get_table('VRRP6')

        # config int ip remove Ethernet64 10::8/64
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet64", "10::8/64"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet64', '10::8/64') not in db.cfgdb.get_table('INTERFACE')

    def test_config_vrrp_instance_priority(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config int ip add Ethernet64 10.10.10.1/24
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet64", "10.10.10.1/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '10.10.10.1/24') in db.cfgdb.get_table('INTERFACE')

        # config int vrrp ip add Ethernet64 8 10.10.10.8/24
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["ip"].commands["add"],
                               ["Ethernet64", "8", "10.10.10.8/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP')
        assert db.cfgdb.get_table('VRRP')['Ethernet64', '8']['vip'] == ['10.10.10.8/24']

        # check interface_name is valid
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["priority"],
                               ["Ethernt64", "8", "150"], obj=obj)
        print(result.exit_code, result.output)
        assert "'interface_name' is not valid" in result.output
        assert result.exit_code != 0

        # check interface is Router interface
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["priority"],
                               ["Ethernet2", "8", "150"], obj=obj)
        print(result.exit_code, result.output)
        assert "Router Interface 'Ethernet2' not found" in result.output
        assert result.exit_code != 0

        # check the vrrp instance is valid
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["priority"],
                               ["Ethernet64", "9", "150"], obj=obj)
        print(result.exit_code, result.output)
        assert "vrrp instance 9 not found on interface Ethernet64" in result.output
        assert result.exit_code != 0

        # config interface vrrp priority Ethernet64 8 150
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["priority"],
                               ["Ethernet64", "8", "150"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP')
        assert db.cfgdb.get_table('VRRP')['Ethernet64', '8']['priority'] == '150'

        # config interface vrrp priority Ethernet64 8 256
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["priority"],
                               ["Ethernet64", "8", "256"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

        # config int vrrp remove Ethernet64 8
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["remove"],
                               ["Ethernet64", "8"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') not in db.cfgdb.get_table('VRRP')

        # config int ip remove Ethernet64 10.10.10.1/24
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet64", "10.10.10.1/24"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet64', '10.10.10.1/24') not in db.cfgdb.get_table('INTERFACE')

    def test_config_vrrp6_instance_priority(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config int ip add Ethernet64 10::8/64
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet64", "10::8/64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '10::8/64') in db.cfgdb.get_table('INTERFACE')

        # config int vrrp6 ipv6 add Ethernet64 8 10::1/64
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["ipv6"].commands["add"],
                               ["Ethernet64", "8", "10::1/64"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP6')
        assert db.cfgdb.get_table('VRRP6')['Ethernet64', '8']['vip'] == ['10::1/64']

        # check interface_name is valid
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["priority"],
                               ["Ethernt64", "8", "150"], obj=obj)
        print(result.exit_code, result.output)
        assert "'interface_name' is not valid" in result.output
        assert result.exit_code != 0

        # check interface is Router interface
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["priority"],
                               ["Ethernet2", "8", "150"], obj=obj)
        print(result.exit_code, result.output)
        assert "Router Interface 'Ethernet2' not found" in result.output
        assert result.exit_code != 0

        # check the vrrp instance is valid
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["priority"],
                               ["Ethernet64", "9", "150"], obj=obj)
        print(result.exit_code, result.output)
        assert "Vrrpv6 instance 9 not found on interface Ethernet64" in result.output
        assert result.exit_code != 0

        # config interface vrrp6 priority Ethernet64 8 150
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["priority"],
                               ["Ethernet64", "8", "150"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP6')
        assert db.cfgdb.get_table('VRRP6')['Ethernet64', '8']['priority'] == '150'

        # config interface vrrp priority Ethernet64 8 256
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["priority"],
                               ["Ethernet64", "8", "256"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

        # config int vrrp6 remove Ethernet64 8
        result = runner.invoke(config.config.commands["interface"].commands["vrrp6"].commands["remove"],
                               ["Ethernet64", "8"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') not in db.cfgdb.get_table('VRRP6')

        # config int ip remove Ethernet64 10::8/64
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet64", "10::8/64"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet64', '10::8/64') not in db.cfgdb.get_table('INTERFACE')

    def test_config_vrrp_instance_version(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config int ip add Ethernet64 10.10.10.1/24
        result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["add"],
                               ["Ethernet64", "10.10.10.1/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '10.10.10.1/24') in db.cfgdb.get_table('INTERFACE')

        # config int vrrp ip add Ethernet64 8 10.10.10.8/24
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["ip"].commands["add"],
                               ["Ethernet64", "8", "10.10.10.8/24"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP')
        assert db.cfgdb.get_table('VRRP')['Ethernet64', '8']['vip'] == ['10.10.10.8/24']

        # check interface_name is valid
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["version"],
                               ["Ethernt64", "8", "3"], obj=obj)
        print(result.exit_code, result.output)
        assert "'interface_name' is not valid" in result.output
        assert result.exit_code != 0

        # check interface is Router interface
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["version"],
                               ["Ethernet2", "8", "3"], obj=obj)
        print(result.exit_code, result.output)
        assert "Router Interface 'Ethernet2' not found" in result.output
        assert result.exit_code != 0

        # check the vrrp instance is valid
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["version"],
                               ["Ethernet64", "9", "3"], obj=obj)
        print(result.exit_code, result.output)
        assert "vrrp instance 9 not found on interface Ethernet64" in result.output
        assert result.exit_code != 0

        # config interface vrrp version Ethernet64 8 3
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["version"],
                               ["Ethernet64", "8", "3"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') in db.cfgdb.get_table('VRRP')
        assert db.cfgdb.get_table('VRRP')['Ethernet64', '8']['version'] == '3'

        # config interface vrrp version Ethernet64 8 1
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["version"],
                               ["Ethernet64", "8", "1"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

        # config int vrrp remove Ethernet64 8
        result = runner.invoke(config.config.commands["interface"].commands["vrrp"].commands["remove"],
                               ["Ethernet64", "8"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert ('Ethernet64', '8') not in db.cfgdb.get_table('VRRP')

        # config int ip remove Ethernet64 10.10.10.1/24
        with mock.patch('utilities_common.cli.run_command') as mock_run_command:
            result = runner.invoke(config.config.commands["interface"].commands["ip"].commands["remove"],
                                   ["Ethernet64", "10.10.10.1/24"], obj=obj)
            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert mock_run_command.call_count == 1
            assert ('Ethernet64', '10.10.10.1/24') not in db.cfgdb.get_table('INTERFACE')

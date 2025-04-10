import os
import traceback

from click.testing import CliRunner

import config.main as config
import show.main as show
from utilities_common.db import Db

ERROR_STR = '''
Error: argument is not in pattern prefix'''
ERROR_STR_INVALID_NEXTHOP_PATTERN = '''
Error: nexthop is not in pattern!
'''
ERROR_STR_MISS_PREFIX = '''
Error: argument is incomplete, prefix not found!
'''
ERROR_STR_MISS_NEXTHOP = '''
Error: argument is incomplete, nexthop not found!
'''
ERROR_STR_DEL_NONEXIST_KEY = '''
Error: Route {} doesnt exist
'''
ERROR_STR_DEL_NONEXIST_ENTRY = '''
Error: Not found {} in {}
'''
ERROR_STR_INVALID_IP = '''
Error: ip address is not valid.
'''
ERROR_STR_INVALID_PORTCHANNEL = '''
Error: portchannel does not exist.
'''
ERROR_STR_INVALID_VLAN = '''
Error: vlan interface does not exist.
'''
ERROR_STR_INVALID_NH_VRF = '''
Error: Nexthop VRF {} does not exist!
'''
ERROR_STR_INVALID_DEV = '''
Error: interface {} does not exist.
'''
ERROR_STR_NO_DEL_MULTI_NH = '''
Error: Only one nexthop can be deleted at a time
'''


class TestStaticRoutes(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

    def test_simple_static_route(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config route add prefix 1.2.3.4/32 nexthop 30.0.0.5
        result = runner.invoke(config.config.commands["route"].commands["add"],
        ["prefix", "1.2.3.4/32", "nexthop", "30.0.0.5"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '1.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|1.2.3.4/32') == {'nexthop': '30.0.0.5', 'blackhole': 'false', 'distance': '0', 'ifname': '', 'nexthop-vrf': ''}

        # config route del prefix 1.2.3.4/32 nexthop 30.0.0.5
        result = runner.invoke(config.config.commands["route"].commands["del"], \
        ["prefix", "1.2.3.4/32", "nexthop", "30.0.0.5"], obj=obj)
        print(result.exit_code, result.output)
        assert not '1.2.3.4/32' in db.cfgdb.get_table('STATIC_ROUTE')

    def test_invalid_portchannel_static_route(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config route add prefix 1.2.3.4/32 nexthop dev PortChannel0101
        result = runner.invoke(config.config.commands["route"].commands["add"],
                               ["prefix", "1.2.3.4/32", "nexthop", "dev", "PortChannel0101"], obj=obj)
        print(result.exit_code, result.output)
        assert ERROR_STR_INVALID_PORTCHANNEL in result.output

    def test_invalid_vlan_static_route(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config route add prefix 1.2.3.4/32 nexthop dev Vlan800
        result = runner.invoke(config.config.commands["route"].commands["add"],
                               ["prefix", "1.2.3.4/32", "nexthop", "dev", "Vlan800"], obj=obj)
        print(result.exit_code, result.output)
        assert ERROR_STR_INVALID_VLAN in result.output

    def test_static_route_invalid_prefix_ip(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config route add prefix 1.2.3/32 nexthop 30.0.0.5
        result = runner.invoke(config.config.commands["route"].commands["add"],
                               ["prefix", "1.2.3/32", "nexthop", "30.0.0.5"], obj=obj)
        print(result.exit_code, result.output)
        assert ERROR_STR_INVALID_IP in result.output

    def test_static_route_invalid_nexthop_ip(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config route add prefix 1.2.3.4/32 nexthop 30.0.5
        result = runner.invoke(config.config.commands["route"].commands["add"],
                               ["prefix", "1.2.3.4/32", "nexthop", "30.0.5"], obj=obj)
        print(result.exit_code, result.output)
        assert ERROR_STR_INVALID_IP in result.output

    def test_vrf_static_route(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config route add prefix vrf Vrf-BLUE 2.2.3.4/32 nexthop 30.0.0.6
        result = runner.invoke(config.config.commands["vrf"].commands["add"], ["Vrf-BLUE"], obj=obj)
        print(result.exit_code, result.output)
        result = runner.invoke(config.config.commands["route"].commands["add"],
                               ["prefix", "vrf", "Vrf-BLUE", "2.2.3.4/32", "nexthop", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert ('Vrf-BLUE', '2.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'Vrf-BLUE|2.2.3.4/32') == \
            {'nexthop': '30.0.0.6', 'blackhole': 'false',
             'distance': '0', 'ifname': '', 'nexthop-vrf': ''}

        # config route del prefix vrf Vrf-BLUE 2.2.3.4/32 nexthop 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["del"],
                               ["prefix", "vrf", "Vrf-BLUE", "2.2.3.4/32", "nexthop", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert not ('Vrf-BLUE', '2.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')

    def test_dest_vrf_static_route(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config route add prefix 3.2.3.4/32 nexthop vrf Vrf-RED 30.0.0.6
        result = runner.invoke(config.config.commands["vrf"].commands["add"], ["Vrf-RED"], obj=obj)
        print(result.exit_code, result.output)
        result = runner.invoke(config.config.commands["route"].commands["add"],
                               ["prefix", "3.2.3.4/32", "nexthop", "vrf", "Vrf-RED", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        print(db.cfgdb.get_table('STATIC_ROUTE'))
        assert ('default', '3.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|3.2.3.4/32') == \
            {'nexthop': '30.0.0.6', 'nexthop-vrf': 'Vrf-RED',
             'blackhole': 'false', 'distance': '0', 'ifname': ''}

        # config route del prefix 3.2.3.4/32 nexthop vrf Vrf-RED 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["del"],
                               ["prefix", "3.2.3.4/32", "nexthop", "vrf", "Vrf-RED", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert not ('3.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')

    def test_nonexistent_dest_vrf_static_route(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config route add prefix 3.2.3.4/32 nexthop vrf Vrf-RED 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["add"],
                               ["prefix", "3.2.3.4/32", "nexthop", "vrf", "Vrf-RED", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        print(db.cfgdb.get_table('STATIC_ROUTE'))
        assert ('default', '3.2.3.4/32') not in db.cfgdb.get_table('STATIC_ROUTE')
        assert ERROR_STR_INVALID_NH_VRF.format("Vrf-RED") in result.output

    def test_multiple_nexthops_with_vrf_static_route(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        ''' Add '''
        result = runner.invoke(config.config.commands["vrf"].commands["add"], ["Vrf-RED"], obj=obj)
        print(result.exit_code, result.output)
        # config route add prefix 6.2.3.4/32 nexthop vrf Vrf-RED "30.0.0.6,30.0.0.7"
        result = runner.invoke(config.config.commands["route"].commands["add"],
                               ["prefix", "6.2.3.4/32", "nexthop", "vrf", "Vrf-RED", "30.0.0.6,30.0.0.7"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '6.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|6.2.3.4/32') == \
            {'nexthop': '30.0.0.6,30.0.0.7', 'blackhole': 'false,false',
             'distance': '0,0', 'ifname': ',', 'nexthop-vrf': 'Vrf-RED,Vrf-RED'}

        ''' Del '''
        # config route del prefix 6.2.3.4/32 nexthop vrf Vrf-RED 30.0.0.7
        result = runner.invoke(config.config.commands["route"].commands["del"],
                               ["prefix", "6.2.3.4/32", "nexthop", "vrf", "Vrf-RED", "30.0.0.7"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '6.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|6.2.3.4/32') == \
            {'nexthop': '30.0.0.6', 'blackhole': 'false', 'distance': '0', 'ifname': '', 'nexthop-vrf': 'Vrf-RED'}

        # config route del prefix 6.2.3.4/32 nexthop vrf Vrf-RED 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["del"],
                               ["prefix", "6.2.3.4/32", "nexthop", "vrf", "Vrf-RED", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert not ('default', '6.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')

    def test_multiple_nexthops_static_route(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        ''' Add '''
        # config route add prefix 6.2.3.4/32 nexthop "30.0.0.6,30.0.0.7"
        result = runner.invoke(config.config.commands["route"].commands["add"],
                               ["prefix", "6.2.3.4/32", "nexthop", "30.0.0.6,30.0.0.7"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '6.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|6.2.3.4/32') == \
            {'nexthop': '30.0.0.6,30.0.0.7', 'blackhole': 'false,false',
             'distance': '0,0', 'ifname': ',', 'nexthop-vrf': ','}

        # config route add prefix 6.2.3.4/32 nexthop 30.0.0.8
        result = runner.invoke(config.config.commands["route"].commands["add"],
                               ["prefix", "6.2.3.4/32", "nexthop", "30.0.0.8"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '6.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|6.2.3.4/32') == \
            {'nexthop': '30.0.0.6,30.0.0.7,30.0.0.8', 'blackhole': 'false,false,false',
             'distance': '0,0,0', 'ifname': ',,', 'nexthop-vrf': ',,'}

        # config route add prefix 6.2.3.4/32 nexthop dev Ethernet0
        result = runner.invoke(config.config.commands["route"].commands["add"],
                               ["prefix", "6.2.3.4/32", "nexthop", "dev", "Ethernet0"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '6.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|6.2.3.4/32') == \
            {'nexthop': '30.0.0.6,30.0.0.7,30.0.0.8,', 'blackhole': 'false,false,false,false',
             'distance': '0,0,0,0', 'ifname': ',,,Ethernet0', 'nexthop-vrf': ',,,'}

        ''' Del '''
        # config route del prefix 6.2.3.4/32 nexthop dev Ethernet0
        result = runner.invoke(config.config.commands["route"].commands["del"],
                               ["prefix", "6.2.3.4/32", "nexthop", "dev", "Ethernet0"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '6.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|6.2.3.4/32') == \
            {"nexthop": '30.0.0.6,30.0.0.7,30.0.0.8', 'blackhole': 'false,false,false',
             'distance': '0,0,0', 'ifname': ',,', 'nexthop-vrf': ',,'}

        # config route del prefix 6.2.3.4/32 nexthop 30.0.0.8
        result = runner.invoke(config.config.commands["route"].commands["del"],
                               ["prefix", "6.2.3.4/32", "nexthop", "30.0.0.8"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '6.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|6.2.3.4/32') == \
            {"nexthop": '30.0.0.6,30.0.0.7', 'blackhole': 'false,false',
             'distance': '0,0', 'ifname': ',', 'nexthop-vrf': ','}

        # config route del prefix 6.2.3.4/32 nexthop 30.0.0.7
        result = runner.invoke(config.config.commands["route"].commands["del"],
                               ["prefix", "6.2.3.4/32", "nexthop", "30.0.0.7"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '6.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|6.2.3.4/32') == \
            {'nexthop': '30.0.0.6', 'blackhole': 'false',
             'distance': '0', 'ifname': '', 'nexthop-vrf': ''}

        # config route del prefix 6.2.3.4/32 nexthop 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["del"],
                               ["prefix", "6.2.3.4/32", "nexthop", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert not ('6.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')

    def test_static_route_miss_prefix(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config route add nexthop 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["add"], ["nexthop", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert ERROR_STR_MISS_PREFIX in result.output

    def test_static_route_miss_nexthop(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config route add prefix 7.2.3.4/32
        result = runner.invoke(config.config.commands["route"].commands["add"], ["prefix", "7.2.3.4/32"], obj=obj)
        print(result.exit_code, result.output)
        assert ERROR_STR_MISS_NEXTHOP in result.output

    def test_static_route_ECMP_nexthop(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        ''' Add '''
        # config route add prefix 10.2.3.4/32 nexthop 30.0.0.5
        result = runner.invoke(config.config.commands["route"].commands["add"],
                               ["prefix", "10.2.3.4/32", "nexthop", "30.0.0.5"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '10.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|10.2.3.4/32') == \
            {'nexthop': '30.0.0.5', 'blackhole': 'false',
             'distance': '0', 'ifname': '', 'nexthop-vrf': ''}

        # config route add prefix 10.2.3.4/32 nexthop 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["add"],
                               ["prefix", "10.2.3.4/32", "nexthop", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '10.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|10.2.3.4/32') == \
            {'nexthop': '30.0.0.5,30.0.0.6', 'blackhole': 'false,false',
             'distance': '0,0', 'ifname': ',', 'nexthop-vrf': ','}

        ''' Del '''
        # config route del prefix 10.2.3.4/32 nexthop 30.0.0.5,30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["del"],
                               ["prefix", "10.2.3.4/32", "nexthop", "30.0.0.5,30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '10.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert ERROR_STR_NO_DEL_MULTI_NH in result.output

        # config route del prefix 10.2.3.4/32 nexthop 30.0.0.5
        result = runner.invoke(config.config.commands["route"].commands["del"],
                               ["prefix", "10.2.3.4/32", "nexthop", "30.0.0.5"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '10.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|10.2.3.4/32') == {'nexthop': '30.0.0.6', 'blackhole': 'false', 'distance': '0', 'ifname': '', 'nexthop-vrf': ''}

        # config route del prefix 1.2.3.4/32 nexthop 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["del"],
                               ["prefix", "10.2.3.4/32", "nexthop", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert not ('10.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')

    def test_static_route_ECMP_nexthop_with_vrf(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        ''' Add '''
        result = runner.invoke(config.config.commands["vrf"].commands["add"], ["Vrf-RED"], obj=obj)
        print(result.exit_code, result.output)
        # config route add prefix 11.2.3.4/32 nexthop vrf Vrf-RED 30.0.0.5
        result = runner.invoke(config.config.commands["route"].commands["add"],
        ["prefix", "11.2.3.4/32", "nexthop", "vrf", "Vrf-RED", "30.0.0.5"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '11.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|11.2.3.4/32') == {'nexthop': '30.0.0.5', 'nexthop-vrf': 'Vrf-RED', 'blackhole': 'false', 'distance': '0', 'ifname': ''}

        result = runner.invoke(config.config.commands["vrf"].commands["add"], ["Vrf-BLUE"], obj=obj)
        print(result.exit_code, result.output)
        # config route add prefix 11.2.3.4/32 nexthop vrf Vrf-BLUE 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["add"],
        ["prefix", "11.2.3.4/32", "nexthop", "vrf", "Vrf-BLUE", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '11.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|11.2.3.4/32') == {"nexthop": "30.0.0.5,30.0.0.6", "nexthop-vrf": "Vrf-RED,Vrf-BLUE", 'blackhole': 'false,false', 'distance': '0,0', 'ifname': ','}

        ''' Del '''
        # config route del prefix 11.2.3.4/32 nexthop vrf Vrf-RED 30.0.0.5
        result = runner.invoke(config.config.commands["route"].commands["del"], \
        ["prefix", "11.2.3.4/32", "nexthop", "vrf", "Vrf-RED", "30.0.0.5"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '11.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|11.2.3.4/32') == {"nexthop": "30.0.0.6", "nexthop-vrf": "Vrf-BLUE", 'blackhole': 'false', 'distance': '0', 'ifname': ''}

        # config route del prefix 11.2.3.4/32 nexthop vrf Vrf-BLUE 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["del"], \
        ["prefix", "11.2.3.4/32", "nexthop", "vrf", "Vrf-BLUE", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert not ('default', '11.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')

    def test_static_route_ECMP_mixed_nextfop(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        ''' Add '''
        # config route add prefix 12.2.3.4/32 nexthop 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["add"],
        ["prefix", "12.2.3.4/32", "nexthop", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '12.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|12.2.3.4/32') == {'nexthop': '30.0.0.6', 'blackhole': 'false', 'distance': '0', 'ifname': '', 'nexthop-vrf': ''}

        result = runner.invoke(config.config.commands["vrf"].commands["add"], ["Vrf-RED"], obj=obj)
        print(result.exit_code, result.output)
        # config route add prefix 12.2.3.4/32 nexthop vrf Vrf-RED 30.0.0.7
        result = runner.invoke(config.config.commands["route"].commands["add"],
        ["prefix", "12.2.3.4/32", "nexthop", "vrf", "Vrf-RED", "30.0.0.7"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '12.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|12.2.3.4/32') == {'nexthop': '30.0.0.6,30.0.0.7', 'nexthop-vrf': ',Vrf-RED', 'blackhole': 'false,false', 'distance': '0,0', 'ifname': ','}

        ''' Del '''
        # config route del prefix 12.2.3.4/32 nexthop vrf Vrf-Red 30.0.0.7
        result = runner.invoke(config.config.commands["route"].commands["del"], \
        ["prefix", "12.2.3.4/32", "nexthop", "vrf", "Vrf-RED", "30.0.0.7"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '12.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|12.2.3.4/32') == {'nexthop': '30.0.0.6', 'nexthop-vrf': '', 'ifname': '', 'blackhole': 'false', 'distance': '0'}

        # config route del prefix 12.2.3.4/32 nexthop 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["del"], \
        ["prefix", "12.2.3.4/32", "nexthop", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert not ('default', '12.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')

    def test_del_nonexist_key_static_route(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config route del prefix 10.2.3.4/32 nexthop 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["del"],
                               ["prefix", "17.2.3.4/32", "nexthop", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert ERROR_STR_DEL_NONEXIST_KEY.format("default|17.2.3.4/32") in result.output

    def test_del_nonexist_entry_static_route(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config route add prefix 13.2.3.4/32 nexthop 30.0.0.5
        result = runner.invoke(config.config.commands["route"].commands["add"],
        ["prefix", "13.2.3.4/32", "nexthop", "30.0.0.5"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '13.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|13.2.3.4/32') == \
            {'nexthop': '30.0.0.5', 'blackhole': 'false', 'distance': '0', 'ifname': '', 'nexthop-vrf': ''}

        # config route del prefix 13.2.3.4/32 nexthop 30.0.0.6 <- nh ip that doesnt exist
        result = runner.invoke(config.config.commands["route"].commands["del"],
                               ["prefix", "13.2.3.4/32", "nexthop", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert ERROR_STR_DEL_NONEXIST_ENTRY.format(('30.0.0.6', '', ''), "default|13.2.3.4/32") in result.output

        # config route del prefix 13.2.3.4/32 nexthop 30.0.0.5
        result = runner.invoke(config.config.commands["route"].commands["del"],
                               ["prefix", "13.2.3.4/32", "nexthop", "30.0.0.5"], obj=obj)
        print(result.exit_code, result.output)
        assert not ('default', '13.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')

    def test_del_entire_ECMP_static_route(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config route add prefix 14.2.3.4/32 nexthop 30.0.0.5
        result = runner.invoke(config.config.commands["route"].commands["add"],
        ["prefix", "14.2.3.4/32", "nexthop", "30.0.0.5"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '14.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|14.2.3.4/32') == {'nexthop': '30.0.0.5', 'blackhole': 'false', 'distance': '0', 'ifname': '', 'nexthop-vrf': ''}

        # config route add prefix 14.2.3.4/32 nexthop 30.0.0.6
        result = runner.invoke(config.config.commands["route"].commands["add"],
        ["prefix", "14.2.3.4/32", "nexthop", "30.0.0.6"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '14.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|14.2.3.4/32') == {'nexthop': '30.0.0.5,30.0.0.6', 'nexthop-vrf': ',', 'ifname': ',', 'blackhole': 'false,false', 'distance': '0,0'}

        # config route del prefix 14.2.3.4/32
        result = runner.invoke(config.config.commands["route"].commands["del"], ["prefix", "14.2.3.4/32"], obj=obj)
        print(result.exit_code, result.output)
        assert not ('default', '14.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')

    def test_static_route_nexthop_subinterface(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config route add prefix 2.2.3.5/32 nexthop dev Ethernet0.10
        result = runner.invoke(config.config.commands["route"].commands["add"],
        ["prefix", "2.2.3.5/32", "nexthop", "dev", "Ethernet0.10"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '2.2.3.5/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|2.2.3.5/32') == {'nexthop': '', 'blackhole': 'false', 'distance': '0', 'ifname': 'Ethernet0.10', 'nexthop-vrf': ''}

        # config route del prefix 2.2.3.5/32 nexthop dev Ethernet0.10
        result = runner.invoke(config.config.commands["route"].commands["del"], \
        ["prefix", "2.2.3.5/32", "nexthop", "dev", "Ethernet0.10"], obj=obj)
        print(result.exit_code, result.output)
        assert not ('default', '2.2.3.5/32') in db.cfgdb.get_table('STATIC_ROUTE')

        # config route add prefix 2.2.3.5/32 nexthop dev Eth36.10
        result = runner.invoke(config.config.commands["route"].commands["add"],
        ["prefix", "2.2.3.5/32", "nexthop", "dev", "Eth36.10"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '2.2.3.5/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|2.2.3.5/32') == {'nexthop': '', 'blackhole': 'false', 'distance': '0', 'ifname': 'Eth36.10', 'nexthop-vrf': ''}

        # config route del prefix 2.2.3.5/32 nexthop dev Eth36.10
        result = runner.invoke(config.config.commands["route"].commands["del"], \
        ["prefix", "2.2.3.5/32", "nexthop", "dev", "Eth36.10"], obj=obj)
        print(result.exit_code, result.output)
        assert not ('default', '2.2.3.5/32') in db.cfgdb.get_table('STATIC_ROUTE')

    def test_static_route_both_nexthop_ip_and_dev(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config route add prefix 1.2.3.4/32 nexthop 30.0.0.5 dev Ethernet0
        result = runner.invoke(config.config.commands["route"].commands["add"],
                               ["prefix", "1.2.3.4/32", "nexthop", "30.0.0.5", "dev", "Ethernet0"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '1.2.3.4/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|1.2.3.4/32') ==\
            {'nexthop': '30.0.0.5', 'blackhole': 'false',
             'distance': '0', 'ifname': 'Ethernet0', 'nexthop-vrf': ''}

        # config route del prefix 1.2.3.4/32 nexthop 30.0.0.5 dev Ethernet0
        result = runner.invoke(config.config.commands["route"].commands["del"],
                               ["prefix", "1.2.3.4/32", "nexthop", "30.0.0.5", "dev", "Ethernet0"], obj=obj)
        print(result.exit_code, result.output)
        assert '1.2.3.4/32' not in db.cfgdb.get_table('STATIC_ROUTE')

        # config route add prefix 1.2.3.4/32 nexthop 30.0.0.5 dev Ethernet1000
        result = runner.invoke(config.config.commands["route"].commands["add"],
                               ["prefix", "1.2.3.4/32", "nexthop", "30.0.0.5", "dev", "Ethernet1000"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '1.2.3.4/32') not in db.cfgdb.get_table('STATIC_ROUTE')
        assert ERROR_STR_INVALID_DEV.format("Ethernet1000") in result.output

    def test_out_of_pattern_static_route(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config route add prefix vrf Vrf1 2.2.3.5/32 nexthop vrf Vrf2 10.0.0.1 dev Ethernet0.10 xxx
        result = runner.invoke(config.config.commands["route"].commands["add"],
                               ["prefix", "vrf", "Vrf1", "2.2.3.5/32", "nexthop", "vrf",
                                "Vrf2", "10.0.0.1", "dev", "Ethernet0.10", "xxx"], obj=obj)
        print(result.exit_code, result.output)
        assert not ('Vrf1', '2.2.3.5/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert ERROR_STR in result.output

        # config route add prefix vrf Vrf1 2.2.3.5/32 nexthop 10.0.0.1 dev
        result = runner.invoke(config.config.commands["route"].commands["add"],
                               ["prefix", "vrf", "Vrf1", "2.2.3.5/32", "nexthop", "10.0.0.1", "dev"], obj=obj)
        print(result.exit_code, result.output)
        assert not ('Vrf1', '2.2.3.5/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert ERROR_STR_INVALID_NEXTHOP_PATTERN in result.output

    def test_static_route_blackhole(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb}

        # config route add prefix 2.2.3.5/32 nexthop dev Ethernet0,null
        result = runner.invoke(config.config.commands["route"].commands["add"],
                               ["prefix", "2.2.3.5/32", "nexthop", "dev", "Ethernet0,null"], obj=obj)
        print(result.exit_code, result.output)
        assert ('default', '2.2.3.5/32') in db.cfgdb.get_table('STATIC_ROUTE')
        assert db.cfgdb.get_entry('STATIC_ROUTE', 'default|2.2.3.5/32') == \
            {'nexthop': ',', 'blackhole': 'false,true', 'distance': '0,0',
             'ifname': 'Ethernet0,null', 'nexthop-vrf': ','}

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")


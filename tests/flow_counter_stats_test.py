import importlib
import os
import sys

from click.testing import CliRunner
from unittest import mock

import show.main as show
import clear.main as clear
import config.main as config

from .utils import get_result_and_return_code
from flow_counter_util.route import FLOW_COUNTER_ROUTE_PATTERN_TABLE, FLOW_COUNTER_ROUTE_MAX_MATCH_FIELD
from utilities_common.db import Db
from utilities_common.general import load_module_from_source

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, scripts_path)

flow_counters_stat_path = os.path.join(scripts_path, 'flow_counters_stat')
flow_counters_stat = load_module_from_source('flow_counters_stat', flow_counters_stat_path)

expect_show_output = """\
  Trap Name    Packets    Bytes      PPS
-----------  ---------  -------  -------
       dhcp        100    2,000  50.25/s
"""

expect_show_output_json = """\
{
    "dhcp": {
        "Bytes": "2,000",
        "PPS": "50.25/s",
        "Packets": "100"
    }
}
"""

expect_show_output_after_clear = """\
  Trap Name    Packets    Bytes      PPS
-----------  ---------  -------  -------
       dhcp          0        0  50.25/s
"""

expect_show_output_multi_asic = """\
  ASIC ID    Trap Name    Packets    Bytes      PPS
---------  -----------  ---------  -------  -------
    asic0         dhcp        100    2,000  50.25/s
    asic1         dhcp        200    3,000  45.25/s
"""

expect_show_output_json_multi_asic = """\
{
    "asic0": {
        "Bytes": "2,000",
        "PPS": "50.25/s",
        "Packets": "100",
        "Trap Name": "dhcp"
    },
    "asic1": {
        "Bytes": "3,000",
        "PPS": "45.25/s",
        "Packets": "200",
        "Trap Name": "dhcp"
    }
}
"""

expect_show_output_multi_asic_after_clear = """\
  ASIC ID    Trap Name    Packets    Bytes      PPS
---------  -----------  ---------  -------  -------
    asic0         dhcp          0        0  50.25/s
    asic1         dhcp          0        0  45.25/s
"""

expect_show_route_pattern = """\
Route pattern    VRF        Max
---------------  -------  -----
1.1.0.0/24       Vrf1        30
2000::1/64       default     30
"""

expect_show_all_route_stats = """\
  Route pattern      VRF    Matched routes    Packets    Bytes
---------------  -------  ----------------  ---------  -------
     1.1.1.0/24  default        1.1.1.1/31        100    2,000
                                1.1.1.2/31      1,000    2,000
      2001::/64  default        2001::1/64         50    1,000
      2001::/64    Vrf_1        2001::1/64      1,000   25,000
"""

expect_show_route_stats_by_pattern_v4 = """\
  Route pattern      VRF    Matched routes    Packets    Bytes
---------------  -------  ----------------  ---------  -------
     1.1.1.0/24  default        1.1.1.1/31        100    2,000
                                1.1.1.2/31      1,000    2,000
"""

expect_show_route_stats_by_pattern_v6 = """\
  Route pattern      VRF    Matched routes    Packets    Bytes
---------------  -------  ----------------  ---------  -------
      2001::/64  default        2001::1/64         50    1,000
"""

expect_show_route_stats_by_pattern_and_vrf_v6 = """\
  Route pattern    VRF    Matched routes    Packets    Bytes
---------------  -----  ----------------  ---------  -------
      2001::/64  Vrf_1        2001::1/64      1,000   25,000
"""

expect_show_route_stats_by_pattern_empty = """\
  Route pattern    VRF    Matched routes    Packets    Bytes
---------------  -----  ----------------  ---------  -------
"""

expect_show_route_stats_by_route_v4 = """\
     Route      VRF    Route pattern    Packets    Bytes
----------  -------  ---------------  ---------  -------
1.1.1.1/31  default       1.1.1.0/24        100    2,000
"""

expect_show_route_stats_by_route_v6 = """\
     Route      VRF    Route pattern    Packets    Bytes
----------  -------  ---------------  ---------  -------
2001::1/64  default        2001::/64         50    1,000
"""

expect_show_route_stats_by_route_and_vrf_v6 = """\
     Route    VRF    Route pattern    Packets    Bytes
----------  -----  ---------------  ---------  -------
2001::1/64  Vrf_1        2001::/64      1,000   25,000
"""

expect_after_clear_route_stats_all = """\
  Route pattern      VRF    Matched routes    Packets    Bytes
---------------  -------  ----------------  ---------  -------
     1.1.1.0/24  default        1.1.1.1/31          0        0
                                1.1.1.2/31          0        0
      2001::/64  default        2001::1/64          0        0
      2001::/64    Vrf_1        2001::1/64          0        0
"""

expect_after_clear_route_stats_by_pattern_v4 = """\
  Route pattern      VRF    Matched routes    Packets    Bytes
---------------  -------  ----------------  ---------  -------
     1.1.1.0/24  default        1.1.1.1/31          0        0
                                1.1.1.2/31          0        0
      2001::/64  default        2001::1/64         50    1,000
      2001::/64    Vrf_1        2001::1/64      1,000   25,000
"""

expect_after_clear_route_stats_by_pattern_v6 = """\
  Route pattern      VRF    Matched routes    Packets    Bytes
---------------  -------  ----------------  ---------  -------
     1.1.1.0/24  default        1.1.1.1/31          0        0
                                1.1.1.2/31          0        0
      2001::/64  default        2001::1/64          0        0
      2001::/64    Vrf_1        2001::1/64      1,000   25,000
"""

expect_show_route_stats_all_json = """\
{
    "0": {
        "Bytes": "2,000",
        "Matched routes": "1.1.1.1/31",
        "Packets": "100",
        "Route pattern": "1.1.1.0/24",
        "VRF": "default"
    },
    "1": {
        "Bytes": "2,000",
        "Matched routes": "1.1.1.2/31",
        "Packets": "1,000",
        "Route pattern": "1.1.1.0/24",
        "VRF": "default"
    },
    "2": {
        "Bytes": "1,000",
        "Matched routes": "2001::1/64",
        "Packets": "50",
        "Route pattern": "2001::/64",
        "VRF": "default"
    },
    "3": {
        "Bytes": "25,000",
        "Matched routes": "2001::1/64",
        "Packets": "1,000",
        "Route pattern": "2001::/64",
        "VRF": "Vrf_1"
    }
}
"""

expect_show_route_stats_by_pattern_v4_json = """\
{
    "0": {
        "Bytes": "2,000",
        "Matched routes": "1.1.1.1/31",
        "Packets": "100",
        "Route pattern": "1.1.1.0/24",
        "VRF": "default"
    },
    "1": {
        "Bytes": "2,000",
        "Matched routes": "1.1.1.2/31",
        "Packets": "1,000",
        "Route pattern": "1.1.1.0/24",
        "VRF": "default"
    }
}
"""

expect_show_route_stats_by_pattern_and_vrf_v6_json = """\
{
    "0": {
        "Bytes": "25,000",
        "Packets": "1,000",
        "Route": "2001::1/64",
        "Route pattern": "2001::/64",
        "VRF": "Vrf_1"
    }
}
"""

expect_show_route_stats_all_multi_asic = """\
  ASIC ID    Route pattern      VRF    Matched routes    Packets    Bytes
---------  ---------------  -------  ----------------  ---------  -------
    asic0       1.1.1.0/24  default        1.1.1.1/31        100    2,000
                                           1.1.1.3/31        200    4,000
    asic1       1.1.1.0/24  default        1.1.1.2/31      1,000    2,000
"""

expect_show_route_stats_all_json_multi_asic = """\
{
    "0": {
        "ASIC ID": "asic0",
        "Bytes": "2,000",
        "Matched routes": "1.1.1.1/31",
        "Packets": "100",
        "Route pattern": "1.1.1.0/24",
        "VRF": "default"
    },
    "1": {
        "ASIC ID": "asic0",
        "Bytes": "4,000",
        "Matched routes": "1.1.1.3/31",
        "Packets": "200",
        "Route pattern": "1.1.1.0/24",
        "VRF": "default"
    },
    "2": {
        "ASIC ID": "asic1",
        "Bytes": "2,000",
        "Matched routes": "1.1.1.2/31",
        "Packets": "1,000",
        "Route pattern": "1.1.1.0/24",
        "VRF": "default"
    }
}
"""

expect_after_clear_route_stats_all_multi_asic = """\
  ASIC ID    Route pattern      VRF    Matched routes    Packets    Bytes
---------  ---------------  -------  ----------------  ---------  -------
    asic0       1.1.1.0/24  default        1.1.1.1/31          0        0
                                           1.1.1.3/31          0        0
    asic1       1.1.1.0/24  default        1.1.1.2/31          0        0
"""

def delete_cache(stat_type='trap'):
    cmd = ['flow_counters_stat', '-t', stat_type, '-d']
    get_result_and_return_code(cmd)


class TestTrapStat:
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        delete_cache()

    def test_show(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["flowcnt-trap"].commands["stats"],
            []
        )
        print(result.output)

        assert result.exit_code == 0
        assert result.output == expect_show_output

    def test_show_json(self):
        cmd = ['flow_counters_stat', '-t', 'trap', '-j']
        return_code, result = get_result_and_return_code(cmd)
        assert return_code == 0
        assert result == expect_show_output_json

    def test_clear(self):
        runner = CliRunner()
        result = runner.invoke(
            clear.cli.commands["flowcnt-trap"],
            []
        )
        print(result.output)

        assert result.exit_code == 0

        result = runner.invoke(
            show.cli.commands["flowcnt-trap"].commands["stats"],
            []
        )
        print(result.output)

        assert result.exit_code == 0
        assert result.output == expect_show_output_after_clear

    def test_diff(self):
        args = mock.MagicMock()
        args.type = 'trap'
        args.delete = False
        args.namespace = None
        args.json = False
        stats = flow_counters_stat.FlowCounterStats(args)
        stats._collect = mock.MagicMock()
        old_data = {
            '': {
                'bgp': ['100', '200', '50.0', '1'],
                'bgpv6': ['100', '200', '50.0', '2'],
                'lldp': ['100', '200', '50.0', '3'],
            }
        }
        stats._save(old_data)
        stats.data = {
            '': {
                'bgp': ['100', '200', '50.0', '4'],
                'bgpv6': ['100', '100', '50.0', '2'],
                'lldp': ['200', '300', '50.0', '3'],
            }
        }

        stats._collect_and_diff()
        cached_data = stats._load()
        assert cached_data['']['bgp'] == ['0', '0', '50.0', '4']
        assert cached_data['']['bgpv6'] == ['0', '0', '50.0', '2']
        assert cached_data['']['lldp'] == ['100', '200', '50.0', '3']


class TestTrapStatsMultiAsic:
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        delete_cache()

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        delete_cache()
        os.environ["PATH"] = os.pathsep.join(
            os.environ["PATH"].split(os.pathsep)[:-1]
        )
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)

    def test_show(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["flowcnt-trap"].commands["stats"],
            []
        )
        print(result.output)

        assert result.exit_code == 0
        assert result.output == expect_show_output_multi_asic

    def test_show_json(self):
        cmd = ['flow_counters_stat', '-t', 'trap', '-j']
        return_code, result = get_result_and_return_code(cmd)
        assert return_code == 0
        assert result == expect_show_output_json_multi_asic

    def test_clear(self):
        runner = CliRunner()
        result = runner.invoke(
            clear.cli.commands["flowcnt-trap"],
            []
        )
        print(result.output)

        result = runner.invoke(
            show.cli.commands["flowcnt-trap"].commands["stats"],
            []
        )
        print(result.output)

        assert result.exit_code == 0
        assert result.output == expect_show_output_multi_asic_after_clear


class TestConfigRoutePattern:
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(
            os.environ["PATH"].split(os.pathsep)[:-1]
        )
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""

    @mock.patch('utilities_common.cli.query_yes_no')
    def test_add_remove_pattern(self, mock_input):
        runner = CliRunner()
        db = Db()
        prefix = '1.1.1.1/24'
        result = runner.invoke(
            config.config.commands["flowcnt-route"].commands["pattern"].commands["add"],
            [prefix], obj=db
        )

        assert result.exit_code == 0
        table = db.cfgdb.get_table(FLOW_COUNTER_ROUTE_PATTERN_TABLE)
        assert prefix in table
        assert '30' == table[prefix][FLOW_COUNTER_ROUTE_MAX_MATCH_FIELD]

        result = runner.invoke(
            config.config.commands["flowcnt-route"].commands["pattern"].commands["add"],
            ['--max', '50', prefix], obj=db
        )

        assert result.exit_code == 0
        table = db.cfgdb.get_table(FLOW_COUNTER_ROUTE_PATTERN_TABLE)
        assert '50' == table[prefix][FLOW_COUNTER_ROUTE_MAX_MATCH_FIELD]

        mock_input.return_value = False
        vrf = 'Vrf1'
        result = runner.invoke(
            config.config.commands["flowcnt-route"].commands["pattern"].commands["add"],
            ['--max', '50', '--vrf', vrf, prefix], obj=db
        )

        assert result.exit_code == 0
        table = db.cfgdb.get_table(FLOW_COUNTER_ROUTE_PATTERN_TABLE)
        assert prefix in table

        prefix_v6 = '2000::/64'
        result = runner.invoke(
            config.config.commands["flowcnt-route"].commands["pattern"].commands["add"],
            ['--max', '50', prefix_v6], obj=db
        )

        assert result.exit_code == 0
        table = db.cfgdb.get_table(FLOW_COUNTER_ROUTE_PATTERN_TABLE)
        assert prefix_v6 in table

        mock_input.return_value = True
        result = runner.invoke(
            config.config.commands["flowcnt-route"].commands["pattern"].commands["add"],
            ['--max', '50', '--vrf', vrf, prefix], obj=db
        )

        assert result.exit_code == 0
        table = db.cfgdb.get_table(FLOW_COUNTER_ROUTE_PATTERN_TABLE)

        assert (vrf, prefix) in table
        assert '50' == table[(vrf, prefix)][FLOW_COUNTER_ROUTE_MAX_MATCH_FIELD]

        result = runner.invoke(
            config.config.commands["flowcnt-route"].commands["pattern"].commands["remove"],
            ['--vrf', vrf, prefix], obj=db
        )

        assert result.exit_code == 0
        table = db.cfgdb.get_table(FLOW_COUNTER_ROUTE_PATTERN_TABLE)
        assert (vrf, prefix) not in table

        result = runner.invoke(
            config.config.commands["flowcnt-route"].commands["pattern"].commands["remove"],
            [prefix_v6], obj=db
        )

        assert result.exit_code == 0
        table = db.cfgdb.get_table(FLOW_COUNTER_ROUTE_PATTERN_TABLE)
        assert prefix_v6 not in table

    @mock.patch('utilities_common.cli.query_yes_no', mock.MagicMock(return_value=True))
    def test_replace_invalid_pattern(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.mod_entry(FLOW_COUNTER_ROUTE_PATTERN_TABLE,
                           'vrf1|',
                           {FLOW_COUNTER_ROUTE_MAX_MATCH_FIELD: '30'})
        prefix = '1.1.1.0/24'
        result = runner.invoke(
            config.config.commands["flowcnt-route"].commands["pattern"].commands["add"],
            [prefix], obj=db
        )

        assert result.exit_code == 0
        table = db.cfgdb.get_table(FLOW_COUNTER_ROUTE_PATTERN_TABLE)
        assert prefix in table

        db.cfgdb.set_entry(FLOW_COUNTER_ROUTE_PATTERN_TABLE, prefix, None)
        db.cfgdb.mod_entry(FLOW_COUNTER_ROUTE_PATTERN_TABLE,
                           'vrf1|invalid',
                           {FLOW_COUNTER_ROUTE_MAX_MATCH_FIELD: '30'})
        result = runner.invoke(
            config.config.commands["flowcnt-route"].commands["pattern"].commands["add"],
            [prefix], obj=db
        )
        assert result.exit_code == 0
        table = db.cfgdb.get_table(FLOW_COUNTER_ROUTE_PATTERN_TABLE)
        assert prefix in table

    def test_add_invalid_pattern(self):
        runner = CliRunner()
        prefix = 'invalid'
        result = runner.invoke(
            config.config.commands["flowcnt-route"].commands["pattern"].commands["add"],
            [prefix]
        )

        print(result.output)
        assert result.exit_code == 1

    def test_remove_non_exist_pattern(self):
        runner = CliRunner()
        prefix = '1.1.1.1/24'
        result = runner.invoke(
            config.config.commands["flowcnt-route"].commands["pattern"].commands["remove"],
            [prefix]
        )

        assert result.exit_code == 1
        assert 'Failed to remove route pattern: {} does not exist'.format(prefix) in result.output

        result = runner.invoke(
            config.config.commands["flowcnt-route"].commands["pattern"].commands["remove"],
            ['invalid']
        )
        assert result.exit_code == 1
        assert 'Failed to remove route pattern: {} does not exist'.format('invalid') in result.output

    def test_add_pattern_repeatly(self):
        runner = CliRunner()
        db = Db()
        prefix = '1.1.1.1/24'
        result = runner.invoke(
            config.config.commands["flowcnt-route"].commands["pattern"].commands["add"],
            [prefix], obj=db
        )

        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["flowcnt-route"].commands["pattern"].commands["add"],
            [prefix], obj=db
        )

        print(result.output)
        assert result.exit_code == 1
        assert 'already exists' in result.output

        result = runner.invoke(
            config.config.commands["flowcnt-route"].commands["pattern"].commands["add"],
            ['--vrf', 'vnet1', '-y', prefix], obj=db
        )

        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["flowcnt-route"].commands["pattern"].commands["add"],
            ['--vrf', 'vnet1', '-y', prefix], obj=db
        )

        assert result.exit_code == 1
        assert 'already exists' in result.output

        prefix_v6 = '2000::/64'
        result = runner.invoke(
            config.config.commands["flowcnt-route"].commands["pattern"].commands["add"],
            ['--max', '50', prefix_v6], obj=db
        )

        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["flowcnt-route"].commands["pattern"].commands["add"],
            ['--max', '50', prefix_v6], obj=db
        )

        assert result.exit_code == 1
        assert 'already exists' in result.output

        result = runner.invoke(
            config.config.commands["flowcnt-route"].commands["pattern"].commands["add"],
            ['--max', '50', '--vrf', 'vrf1', '-y', prefix_v6], obj=db
        )

        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["flowcnt-route"].commands["pattern"].commands["add"],
            ['--max', '50', '--vrf', 'vrf1', '-y', prefix_v6], obj=db
        )

        assert result.exit_code == 1
        assert 'already exists' in result.output


    def test_add_pattern_without_prefix_length(self):
        runner = CliRunner()
        db = Db()
        prefix = '1.1.0.0'
        result = runner.invoke(
            config.config.commands["flowcnt-route"].commands["pattern"].commands["add"],
            [prefix], obj=db
        )

        assert result.exit_code == 0
        table = db.cfgdb.get_table(FLOW_COUNTER_ROUTE_PATTERN_TABLE)
        assert (prefix + '/32') in table

        prefix_v6 = '2000::1'
        result = runner.invoke(
            config.config.commands["flowcnt-route"].commands["pattern"].commands["add"],
            [prefix_v6], obj=db
        )

        assert result.exit_code == 0
        table = db.cfgdb.get_table(FLOW_COUNTER_ROUTE_PATTERN_TABLE)
        assert (prefix_v6 + '/128') in table

    def test_show_config(self):
        runner = CliRunner()
        db = Db()
        prefix = '1.1.0.0/24'
        result = runner.invoke(
            config.config.commands["flowcnt-route"].commands["pattern"].commands["add"],
            ['--vrf', 'Vrf1', prefix], obj=db
        )

        prefix_v6 = '2000::1/64'
        result = runner.invoke(
            config.config.commands["flowcnt-route"].commands["pattern"].commands["add"],
            [prefix_v6], obj=db
        )

        result = runner.invoke(
            show.cli.commands["flowcnt-route"].commands["config"],
            [], obj=db, catch_exceptions=False
        )

        assert result.exit_code == 0
        print(result.output)
        assert result.output == expect_show_route_pattern


class TestRouteStats:
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        delete_cache(stat_type='route')

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(
            os.environ["PATH"].split(os.pathsep)[:-1]
        )
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""

    def test_show_all_stats(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["flowcnt-route"].commands["stats"],
            []
        )

        assert result.exit_code == 0
        assert expect_show_all_route_stats == result.output

    def test_show_by_pattern(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["flowcnt-route"].commands["stats"].commands["pattern"],
            ['1.1.1.0/24']
        )

        assert result.exit_code == 0
        assert result.output == expect_show_route_stats_by_pattern_v4
        print(result.output)

        result = runner.invoke(
            show.cli.commands["flowcnt-route"].commands["stats"].commands["pattern"],
            ['2001::/64']
        )

        assert result.exit_code == 0
        assert result.output == expect_show_route_stats_by_pattern_v6
        print(result.output)

        result = runner.invoke(
            show.cli.commands["flowcnt-route"].commands["stats"].commands["pattern"],
            ['--vrf', 'Vrf_1', '2001::/64']
        )

        assert result.exit_code == 0
        assert result.output == expect_show_route_stats_by_pattern_and_vrf_v6
        print(result.output)

        result = runner.invoke(
            show.cli.commands["flowcnt-route"].commands["stats"].commands["pattern"],
            ['invalid']
        )

        assert result.exit_code == 0
        assert result.output == expect_show_route_stats_by_pattern_empty
        print(result.output)

    def test_show_by_route(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["flowcnt-route"].commands["stats"].commands["route"],
            ['1.1.1.1/31']
        )

        assert result.exit_code == 0
        assert result.output == expect_show_route_stats_by_route_v4
        print(result.output)

        result = runner.invoke(
            show.cli.commands["flowcnt-route"].commands["stats"].commands["route"],
            ['2001::1/64']
        )

        assert result.exit_code == 0
        assert result.output == expect_show_route_stats_by_route_v6
        print(result.output)

        result = runner.invoke(
            show.cli.commands["flowcnt-route"].commands["stats"].commands["route"],
            ['--vrf', 'Vrf_1', '2001::1/64']
        )

        assert result.exit_code == 0
        assert result.output == expect_show_route_stats_by_route_and_vrf_v6
        print(result.output)

    def test_show_json(self):
        cmd = ['flow_counters_stat', '-t', 'route', '-j']
        return_code, result = get_result_and_return_code(cmd)
        assert return_code == 0
        assert result == expect_show_route_stats_all_json

        cmd = ['flow_counters_stat', '-t', 'route', '-j', '--prefix_pattern', '1.1.1.0/24']
        return_code, result = get_result_and_return_code(cmd)
        assert return_code == 0
        assert result == expect_show_route_stats_by_pattern_v4_json

        cmd = ['flow_counters_stat', '-t', 'route', '-j', '--prefix', '2001::1/64', '--vrf', 'Vrf_1']
        return_code, result = get_result_and_return_code(cmd)
        assert return_code == 0
        assert result == expect_show_route_stats_by_pattern_and_vrf_v6_json

    def test_clear_all(self):
        delete_cache(stat_type='route')
        runner = CliRunner()
        result = runner.invoke(
            clear.cli.commands["flowcnt-route"], []
        )

        assert result.exit_code == 0

        result = runner.invoke(
            show.cli.commands["flowcnt-route"].commands["stats"],
            []
        )

        assert result.exit_code == 0
        assert expect_after_clear_route_stats_all == result.output
        print(result.output)

    def test_clear_by_pattern(self):
        delete_cache(stat_type='route')
        runner = CliRunner()
        result = runner.invoke(
            clear.cli.commands["flowcnt-route"].commands['pattern'],
            ['1.1.1.0/24']
        )

        assert result.exit_code == 0

        result = runner.invoke(
            show.cli.commands["flowcnt-route"].commands["stats"],
            []
        )

        assert result.exit_code == 0
        assert expect_after_clear_route_stats_by_pattern_v4 == result.output
        print(result.output)

        result = runner.invoke(
            clear.cli.commands["flowcnt-route"].commands['pattern'],
            ['2001::/64']
        )

        assert result.exit_code == 0

        result = runner.invoke(
            show.cli.commands["flowcnt-route"].commands["stats"],
            []
        )

        assert result.exit_code == 0
        assert expect_after_clear_route_stats_by_pattern_v6 == result.output
        print(result.output)

        result = runner.invoke(
            clear.cli.commands["flowcnt-route"].commands['pattern'],
            ['--vrf', 'Vrf_1', '2001::/64']
        )

        assert result.exit_code == 0

        result = runner.invoke(
            show.cli.commands["flowcnt-route"].commands["stats"],
            []
        )

        assert result.exit_code == 0
        assert expect_after_clear_route_stats_all == result.output
        print(result.output)

    def test_diff(self):
        args = mock.MagicMock()
        args.type = 'route'
        args.delete = False
        args.namespace = None
        args.json = False
        stats = flow_counters_stat.RouteFlowCounterStats(args)
        stats._collect = mock.MagicMock()
        old_data = {
            '': {
                '1.1.1.0/24': {
                    '1.1.1.1/24': ['100', '200', '1'],
                    '1.1.1.2/24': ['100', '100', '2'],
                    '1.1.1.3/24': ['100', '200', '3']
                }
            }
        }
        stats._save(old_data)
        stats.data = {
            '': {
                '1.1.1.0/24': {
                    '1.1.1.1/24': ['200', '300', '4'],
                    '1.1.1.2/24': ['100', '50', '2'],
                    '1.1.1.3/24': ['200', '300', '3']
                }
            }
        }

        stats._collect_and_diff()
        cached_data = stats._load()
        assert cached_data['']['1.1.1.0/24']['1.1.1.1/24'] == ['0', '0', '4']
        assert cached_data['']['1.1.1.0/24']['1.1.1.2/24'] == ['0', '0', '2']
        assert cached_data['']['1.1.1.0/24']['1.1.1.3/24'] == ['100', '200', '3']


class TestRouteStatsMultiAsic:
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        delete_cache(stat_type='route')

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        delete_cache(stat_type='route')
        os.environ["PATH"] = os.pathsep.join(
            os.environ["PATH"].split(os.pathsep)[:-1]
        )
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)

    def test_show_all_stats(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["flowcnt-route"].commands["stats"],
            []
        )

        assert result.exit_code == 0
        print(result.output)
        assert expect_show_route_stats_all_multi_asic == result.output

    def test_show_json(self):
        cmd = ['flow_counters_stat', '-t', 'route', '-j']
        return_code, result = get_result_and_return_code(cmd)
        assert return_code == 0
        assert result == expect_show_route_stats_all_json_multi_asic

    def test_clear_all(self):
        delete_cache(stat_type='route')
        runner = CliRunner()
        result = runner.invoke(
            clear.cli.commands["flowcnt-route"], []
        )

        assert result.exit_code == 0

        result = runner.invoke(
            show.cli.commands["flowcnt-route"].commands["stats"],
            []
        )

        assert result.exit_code == 0
        assert expect_after_clear_route_stats_all_multi_asic == result.output
        print(result.output)

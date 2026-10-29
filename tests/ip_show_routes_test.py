import copy
import io
import json
import os
import pytest

from . import show_ip_route_common
from click.testing import CliRunner
import mock
import sys

from show import bgp_common

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")

sys.path.insert(0, test_path)


class TestShowIpRouteCommands(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        import mock_tables.dbconnector

    def test_show_ip_route_err(
            self,
            setup_ip_route_commands):
        show = setup_ip_route_commands

        def mock_run_bgp_command(*args, **kwargs):
            command = args[0]
            return "% Unknown command: show ip route unknown", 1

        with mock.patch('utilities_common.cli.run_command', mock.MagicMock(side_effect=mock_run_bgp_command)) as mock_run_command:
            runner = CliRunner()
            result = runner.invoke(
                show.cli.commands["ip"].commands["route"], ["unknown"])
            print("{}".format(result.output))
            print(result.exit_code)
            assert result.exit_code == 1
            assert result.output == "% Unknown command: show ip route unknown" + "\n"

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['ip_route'], indirect=['setup_single_bgp_instance'])
    def test_show_ip_route(
            self,
            setup_ip_route_commands,
            setup_single_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], [])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_ip_route_expected_output

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['ip_specific_route'], indirect=['setup_single_bgp_instance'])
    def test_show_specific_ip_route(
            self,
            setup_ip_route_commands,
            setup_single_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["192.168.0.1"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_specific_ip_route_expected_output

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['ip_special_route'], indirect=['setup_single_bgp_instance'])
    def test_show_special_ip_route(
            self,
            setup_ip_route_commands,
            setup_single_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], [])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_special_ip_route_expected_output

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['ipv6_specific_route'], indirect=['setup_single_bgp_instance'])
    def test_show_specific_ipv6_route_json(
            self,
            setup_ip_route_commands,
            setup_single_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["20c0:a8c7:0:81::", "json"])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_ipv6_route_single_json_expected_output

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['ipv6_route'], indirect=['setup_single_bgp_instance'])
    def test_show_ipv6_route(
            self,
            setup_ip_route_commands,
            setup_single_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ipv6"].commands["route"], [])
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_ipv6_route_expected_output

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['ipv6_route'], indirect=['setup_single_bgp_instance'])
    def test_show_ipv6_route_alias(
            self,
            setup_ip_route_commands,
            setup_single_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(
            show.cli.commands["ipv6"].commands["route"], [])
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        print("{}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_ip_route_common.show_ipv6_route_alias_expected_output

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['ipv6_route_err'], indirect=['setup_single_bgp_instance'])
    def test_show_ipv6_route_err(
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

    @pytest.mark.parametrize('setup_single_bgp_instance',
                             ['ip_route'], indirect=['setup_single_bgp_instance'])
    def test_show_ip_route_bgp_json(
            self,
            setup_ip_route_commands,
            setup_single_bgp_instance):
        show = setup_ip_route_commands
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["ip"].commands["route"], ["bgp", "json"])
        print("{}".format(result.output))
        assert result.exit_code == 0

        try:
            parsed = json.loads(result.output)
            assert isinstance(parsed, dict)
        except json.JSONDecodeError as e:
            pytest.fail(f"Output is not valid JSON: {e}")

        bgp_routes_found = False
        for route_data in parsed.values():
            if isinstance(route_data, list):
                for entry in route_data:
                    if entry.get("protocol") == "bgp":
                        bgp_routes_found = True
                        break
        assert bgp_routes_found, "BGP routes should be present in filtered output"


def _legacy_merge_to_combined_route(combined_route, route, new_info_l):
    """Pre-refactor merge_to_combined_route (master) for parity checks."""
    single_nh_proto = ["connected"]
    if route in combined_route:
        while len(new_info_l):
            new_info = new_info_l.pop()
            proto_matched = False
            skip_this_new_info = False
            for j in range(0, len(combined_route[route])):
                if new_info['protocol'] == combined_route[route][j]['protocol']:
                    proto_matched = True
                    if new_info['protocol'] in single_nh_proto:
                        if (combined_route[route][j]['nexthops'][0]['interfaceName'] ==
                                new_info['nexthops'][0]['interfaceName']):
                            skip_this_new_info = True
                            break
                    else:
                        additional_nh_l = []
                        while len(new_info['nexthops']):
                            nh = new_info['nexthops'].pop()
                            found = False
                            for y in range(0, len(combined_route[route][j]['nexthops'])):
                                ex = combined_route[route][j]['nexthops'][y]
                                if "interfaceName" in nh and "interfaceName" in ex:
                                    if nh['interfaceName'] == ex['interfaceName']:
                                        found = True
                                        break
                                if bgp_common.device_info.is_voq_chassis():
                                    if nh['ip'] == ex['ip']:
                                        if 'interfaceName' not in ex:
                                            combined_route[route][j]['nexthops'][y] = nh
                                        found = True
                                        break
                                elif "active" not in nh and "active" not in ex:
                                    if nh['ip'] == ex['ip']:
                                        found = True
                                        break
                            if not found:
                                additional_nh_l.append(copy.deepcopy(nh))
                        if len(additional_nh_l) > 0:
                            combined_route[route][j]['internalNextHopNum'] + len(additional_nh_l)
                            if (combined_route[route][j]['internalNextHopActiveNum'] > 0 and
                                    new_info['internalNextHopActiveNum'] > 0):
                                combined_route[route][j]['internalNextHopActiveNum'] + len(additional_nh_l)
                            combined_route[route][j]['nexthops'] += additional_nh_l
                        skip_this_new_info = True
                        break
            if not proto_matched or not skip_this_new_info:
                combined_route[route].append(new_info)
    else:
        combined_route[route] = new_info_l


def _merge_snapshot(combined):
    """Compare merge results by route/nexthop shape (ignore FRR counter fields)."""
    snap = {}
    for route, entries in combined.items():
        snap[route] = []
        for entry in entries:
            snap[route].append({
                'protocol': entry['protocol'],
                'nexthops': sorted(
                    copy.deepcopy(entry['nexthops']),
                    key=lambda nh: (nh.get('interfaceName', ''), nh.get('ip', '')),
                ),
            })
    return snap


def _bgp_route_entry(prefix, nh_ip, nh_iface):
    nexthops = [{'ip': nh_ip, 'interfaceName': nh_iface, 'flags': 0, 'active': True}]
    return {
        'protocol': 'bgp', 'distance': 20, 'metric': 0, 'selected': True,
        'prefix': prefix, 'uptime': '01:00:00', 'installed': True,
        'internalNextHopNum': len(nexthops), 'internalNextHopActiveNum': len(nexthops),
        'nexthops': nexthops,
    }


def _merge(combined, route, entry, is_voq=False):
    bgp_common.merge_to_combined_route(
        combined, route, [copy.deepcopy(entry)], is_voq_chassis=is_voq)


class TestBgpCommonHelpers(object):
    """Focused tests for show/bgp_common.py merge/print helpers."""

    @pytest.mark.parametrize('is_voq,needle,forbidden', [
        (True, 'recursive via iBGP', None),
        (False, '(recursive)', 'recursive via iBGP'),
    ])
    def test_get_nexthop_recursive(self, is_voq, needle, forbidden):
        nh = {'ip': '10.0.0.1', 'recursive': True}
        out = bgp_common.get_nexthop_info_str(nh, False, is_voq_chassis=is_voq)
        assert needle in out
        if forbidden:
            assert forbidden not in out

    @mock.patch('show.bgp_common.device_info.is_voq_chassis', return_value=True)
    def test_get_nexthop_recursive_device_lookup(self, _mock_voq):
        nh = {'ip': '10.0.0.1', 'recursive': True}
        assert 'recursive via iBGP' in bgp_common.get_nexthop_info_str(nh, False)

    def test_merge_adds_new_prefix(self):
        combined = {}
        entry = _bgp_route_entry('10.0.0.0/24', '10.0.0.1', 'Ethernet0')
        _merge(combined, '10.1.0.0/24', entry)
        assert combined['10.1.0.0/24'] == [entry]

    def test_merge_bgp_nexthops_by_interface(self):
        combined = {}
        prefix = '10.0.0.0/24'
        _merge(combined, prefix, _bgp_route_entry(prefix, '10.0.0.1', 'Ethernet0'))
        _merge(combined, prefix, _bgp_route_entry(prefix, '10.0.0.2', 'Ethernet4'))
        assert {nh['interfaceName'] for nh in combined[prefix][0]['nexthops']} == {
            'Ethernet0', 'Ethernet4'}
        _merge(combined, prefix, _bgp_route_entry(prefix, '10.0.0.9', 'Ethernet0'))
        assert len(combined[prefix][0]['nexthops']) == 2
        assert combined[prefix][0]['internalNextHopNum'] == 2
        assert combined[prefix][0]['internalNextHopActiveNum'] == 2

    def test_merge_active_nexthop_count_excludes_inactive_added(self):
        prefix = '10.0.0.0/24'
        combined = {}
        _merge(combined, prefix, _bgp_route_entry(prefix, '10.0.0.1', 'Ethernet0'))
        second = _bgp_route_entry(prefix, '10.0.0.2', 'Ethernet4')
        second['nexthops'].append(
            {'ip': '10.0.0.3', 'interfaceName': 'Ethernet8', 'flags': 0})
        second['internalNextHopNum'] = 2
        second['internalNextHopActiveNum'] = 1
        _merge(combined, prefix, second)
        assert len(combined[prefix][0]['nexthops']) == 3
        assert combined[prefix][0]['internalNextHopNum'] == 3
        assert combined[prefix][0]['internalNextHopActiveNum'] == 2

    def test_merge_skips_duplicate_inactive_nexthop_ip(self):
        prefix = '10.0.0.0/24'
        with_inactive = _bgp_route_entry(prefix, '10.0.0.1', 'Ethernet20')
        with_inactive['nexthops'].append(
            {'ip': '10.0.0.5', 'interfaceName': 'Ethernet8', 'flags': 0})
        with_inactive['internalNextHopNum'] = 2
        dupe_inactive = _bgp_route_entry(prefix, '10.0.0.9', 'Ethernet16')
        dupe_inactive['nexthops'] = [
            {'ip': '10.0.0.5', 'interfaceName': 'Ethernet24', 'flags': 0}]
        combined = {}
        _merge(combined, prefix, with_inactive)
        _merge(combined, prefix, dupe_inactive)
        assert [nh['ip'] for nh in combined[prefix][0]['nexthops']].count('10.0.0.5') == 1

    def test_merge_voq_fills_missing_nexthop_interface(self):
        prefix = '10.0.0.0/24'
        combined = {}
        first = _bgp_route_entry(prefix, '10.0.0.1', 'Ethernet0')
        first['nexthops'] = [{'ip': '10.0.0.1', 'flags': 0}]
        _merge(combined, prefix, first, is_voq=True)
        _merge(combined, prefix, _bgp_route_entry(prefix, '10.0.0.1', 'Ethernet4'), is_voq=True)
        assert len(combined[prefix][0]['nexthops']) == 1
        assert combined[prefix][0]['nexthops'][0]['interfaceName'] == 'Ethernet4'

    def test_merge_connected_entries(self):
        prefix = '10.0.0.0/24'
        combined = {}

        def connected(iface):
            return {
                'protocol': 'connected', 'distance': 0, 'metric': 0, 'selected': True,
                'prefix': prefix, 'uptime': '00:10:00', 'installed': True,
                'internalNextHopNum': 1, 'internalNextHopActiveNum': 1,
                'nexthops': [{'directlyConnected': True, 'interfaceName': iface, 'flags': 0}],
            }

        _merge(combined, prefix, connected('Ethernet0'))
        _merge(combined, prefix, connected('Ethernet0'))
        assert len(combined[prefix]) == 1
        _merge(combined, prefix, connected('Ethernet4'))
        assert len(combined[prefix]) == 2

    def test_merge_distinct_protocols_same_prefix(self):
        combined = {}
        _merge(combined, '0.0.0.0/0', _bgp_route_entry('0.0.0.0/0', '10.0.0.1', 'PortChannel0002'))
        static = _bgp_route_entry('0.0.0.0/0', '10.3.146.1', 'eth0')
        static['protocol'] = 'static'
        static['distance'] = 200
        _merge(combined, '0.0.0.0/0', static)
        assert {e['protocol'] for e in combined['0.0.0.0/0']} == {'bgp', 'static'}

    @mock.patch('show.bgp_common.device_info.is_voq_chassis', return_value=False)
    def test_print_ip_routes(self, mock_voq):
        one_route = {'10.0.0.0/24': [_bgp_route_entry('10.0.0.0/24', '10.0.0.1', 'Ethernet0')]}
        buf = io.StringIO()
        with mock.patch('sys.stdout.write', buf.write):
            bgp_common.print_ip_routes(one_route, filter_by_ip=False)
        summary = buf.getvalue()
        assert 'B>' in summary and 'Ethernet0' in summary

        detail_route = {
            '192.168.0.1/32': [_bgp_route_entry('192.168.0.1/32', '10.0.0.1', 'PortChannel0002')],
        }
        buf = io.StringIO()
        with mock.patch('sys.stdout.write', buf.write):
            bgp_common.print_ip_routes(detail_route, filter_by_ip=True)
        nh = {'ip': '10.0.0.1', 'interfaceName': 'PortChannel0002', 'flags': 0, 'active': True}
        nh_line = bgp_common.get_nexthop_info_str(nh, True, is_voq_chassis=False)
        assert buf.getvalue() == (
            "Routing entry for 192.168.0.1/32\n"
            '  Known via "bgp", distance 20, metric 0, best\n'
            "  Last update 01:00:00 ago\n"
            "{}\n"
            "\n"
        ).format(nh_line)

        mock_voq.reset_mock()
        many = {
            '10.{}.0.0/24'.format(i): [_bgp_route_entry('10.{}.0.0/24'.format(i), '10.0.0.1', 'Ethernet0')]
            for i in range(10)
        }
        with mock.patch('sys.stdout.write', lambda _s: None):
            bgp_common.print_ip_routes(many, filter_by_ip=False)
        assert mock_voq.call_count == 1

        huge = {
            '10.{0}.{1}.0/24'.format(i // 256, i % 256): [
                _bgp_route_entry(
                    '10.{0}.{1}.0/24'.format(i // 256, i % 256),
                    '10.0.0.1', 'Ethernet0')]
            for i in range(2100)
        }
        writes = []
        with mock.patch('sys.stdout.write', writes.append):
            bgp_common.print_ip_routes(huge, filter_by_ip=False)
        assert len(writes) >= 2

    @mock.patch('show.bgp_common.device_info.is_voq_chassis', return_value=False)
    def test_process_route_info(self, _mock_voq):
        front = _bgp_route_entry('10.0.0.0/24', '10.0.0.1', 'Ethernet0')
        ib = _bgp_route_entry('10.1.0.0/24', '10.0.0.2', 'Ethernet-IB0')
        multi = {}
        bgp_common.process_route_info(
            {'10.0.0.0/24': [copy.deepcopy(front)], '10.1.0.0/24': [copy.deepcopy(ib)]},
            device=None, filter_back_end=True, print_ns_str=False,
            asic_cnt=2, ns_str='', combined_route=multi, back_end_intf_set={'Ethernet-IB0'},
        )
        assert '10.0.0.0/24' in multi and '10.1.0.0/24' not in multi

        single = {}
        bgp_common.process_route_info(
            {'10.0.0.0/24': [copy.deepcopy(front)]},
            device=None, filter_back_end=False, print_ns_str=False,
            asic_cnt=1, ns_str='', combined_route=single, back_end_intf_set=None,
        )
        assert single['10.0.0.0/24'][0]['nexthops'][0]['interfaceName'] == 'Ethernet0'


class TestBgpCommonMergeParity(object):
    """New merge_to_combined_route must match master nexthop merge semantics."""

    @staticmethod
    def _run_parity(is_voq, steps):
        legacy = {}
        current = {}
        for route, entry in steps:
            legacy_batch = [copy.deepcopy(entry)]
            current_batch = [copy.deepcopy(entry)]
            with mock.patch('show.bgp_common.device_info.is_voq_chassis', return_value=is_voq):
                _legacy_merge_to_combined_route(legacy, route, legacy_batch)
            bgp_common.merge_to_combined_route(
                current, route, current_batch, is_voq_chassis=is_voq)
        assert _merge_snapshot(legacy) == _merge_snapshot(current)

    def test_parity_bgp_multipath(self):
        p = '10.0.0.0/24'
        self._run_parity(False, [
            (p, _bgp_route_entry(p, '10.0.0.1', 'Ethernet0')),
            (p, _bgp_route_entry(p, '10.0.0.2', 'Ethernet4')),
            (p, _bgp_route_entry(p, '10.0.0.9', 'Ethernet0')),
        ])

    def test_parity_inactive_nexthop_dedup(self):
        p = '10.0.0.0/24'
        with_inactive = _bgp_route_entry(p, '10.0.0.1', 'Ethernet20')
        with_inactive['nexthops'].append(
            {'ip': '10.0.0.5', 'interfaceName': 'Ethernet8', 'flags': 0})
        dupe = _bgp_route_entry(p, '10.0.0.9', 'Ethernet16')
        dupe['nexthops'] = [{'ip': '10.0.0.5', 'interfaceName': 'Ethernet24', 'flags': 0}]
        self._run_parity(False, [(p, with_inactive), (p, dupe)])

    def test_parity_voq_interface_fill(self):
        p = '10.0.0.0/24'
        first = _bgp_route_entry(p, '10.0.0.1', 'Ethernet0')
        first['nexthops'] = [{'ip': '10.0.0.1', 'flags': 0}]
        self._run_parity(True, [
            (p, first),
            (p, _bgp_route_entry(p, '10.0.0.1', 'Ethernet4')),
        ])

    def test_parity_connected_and_multiprotocol(self):
        p = '10.0.0.0/24'

        def connected(iface):
            return {
                'protocol': 'connected', 'distance': 0, 'metric': 0, 'selected': True,
                'prefix': p, 'uptime': '00:10:00', 'installed': True,
                'internalNextHopNum': 1, 'internalNextHopActiveNum': 1,
                'nexthops': [{'directlyConnected': True, 'interfaceName': iface, 'flags': 0}],
            }

        static = _bgp_route_entry('0.0.0.0/0', '10.3.146.1', 'eth0')
        static['protocol'] = 'static'
        static['distance'] = 200
        self._run_parity(False, [
            (p, connected('Ethernet0')),
            (p, connected('Ethernet0')),
            (p, connected('Ethernet4')),
            ('0.0.0.0/0', _bgp_route_entry('0.0.0.0/0', '10.0.0.1', 'PortChannel0002')),
            ('0.0.0.0/0', static),
        ])

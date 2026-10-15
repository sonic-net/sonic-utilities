import json
import os
import sys
from click.testing import CliRunner
from unittest import TestCase, mock
from swsscommon.swsscommon import ConfigDBConnector

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

from .mock_tables import dbconnector

import show.main as show

# Expected output for 'show breakout current-mode'
current_mode_all_output = ''+ \
"""+-------------+-------------------------+
| Interface   | Current Breakout Mode   |
+=============+=========================+
| Ethernet0   | 4x25G[10G]              |
+-------------+-------------------------+
| Ethernet4   | 2x50G                   |
+-------------+-------------------------+
| Ethernet8   | 1x100G[40G]             |
+-------------+-------------------------+
"""

# Expected output for 'show breakout current-mode Ethernet0'
current_mode_intf_output = ''+ \
"""+-------------+-------------------------+
| Interface   | Current Breakout Mode   |
+=============+=========================+
| Ethernet0   | 4x25G[10G]              |
+-------------+-------------------------+
"""

# Negetive Test
# Expected output for 'show breakout current-mode Ethernet60'
current_mode_intf_output_Ethernet60 = ''+ \
"""+-------------+-------------------------+
| Interface   | Current Breakout Mode   |
+=============+=========================+
| Ethernet60  | Not Available           |
+-------------+-------------------------+
"""

class TestBreakout(TestCase):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def setUp(self):
        self.runner = CliRunner()
        self.config_db = ConfigDBConnector()
        self.config_db.connect()
        self.obj = {'db': self.config_db}

    def _invoke_breakout_details(self, args=None, breakout_cfg=None):
        platform_data = {
            'interfaces': {
                'Ethernet0': {
                    'index': '1,1,1,1',
                    'lanes': '1,2,3,4',
                    'breakout_modes': {'1x100G': ['etp1']}
                },
                'Ethernet4': {
                    'index': '2,2',
                    'lanes': '5,6,7,8',
                    'breakout_modes': {'2x50G': ['etp2a', 'etp2b']}
                }
            }
        }
        hwsku_data = {
            'interfaces': {
                'Ethernet0': {'default_brkout_mode': '1x100G'},
                'Ethernet4': {'default_brkout_mode': '2x50G'}
            }
        }
        if breakout_cfg is None:
            breakout_cfg = {
                'Ethernet0': {'brkout_mode': '1x100G'},
                'Ethernet4': {'brkout_mode': '2x50G'}
            }
        child_ports = {
            'Ethernet0': {'Ethernet0': {}},
            'Ethernet4': {'Ethernet4': {}, 'Ethernet6': {}}
        }
        speeds = {
            'Ethernet0': '100000',
            'Ethernet4': '50000',
            'Ethernet6': '50000'
        }

        config_db = mock.Mock()
        config_db.get_table.return_value = breakout_cfg
        config_db.get_entry.side_effect = lambda table, port: {'speed': speeds[port]}
        command = show.cli.commands["interfaces"].commands["breakout"]

        with mock.patch("show.interfaces.ConfigDBConnector", return_value=config_db), \
             mock.patch("show.interfaces.device_info.get_path_to_port_config_file",
                        return_value='platform.json'), \
             mock.patch("show.interfaces.device_info.get_path_to_hwsku_dir",
                        return_value='/mock/hwsku'), \
             mock.patch("show.interfaces.readJsonFile",
                        side_effect=[platform_data, hwsku_data]), \
             mock.patch("show.interfaces.get_child_ports",
                        side_effect=lambda port, mode, path: child_ports[port]) as get_child_ports_mock:
            result = self.runner.invoke(command, args or [], obj={})

        return result, get_child_ports_mock

    def test_all_intf_breakout_details(self):
        result, get_child_ports_mock = self._invoke_breakout_details()

        assert result.exit_code == 0, result.output
        assert list(json.loads(result.output)) == ['Ethernet0', 'Ethernet4']
        assert get_child_ports_mock.call_count == 2

    def test_single_intf_breakout_details(self):
        for option in ('-i', '--interface'):
            with self.subTest(option=option):
                result, get_child_ports_mock = self._invoke_breakout_details(
                    [option, 'Ethernet0'])

                assert result.exit_code == 0, result.output
                output = json.loads(result.output)
                assert list(output) == ['Ethernet0']
                assert output['Ethernet0']['breakout_modes'] == {
                    '1x100G': ['etp1']
                }
                assert output['Ethernet0']['Current Breakout Mode'] == '1x100G'
                assert output['Ethernet0']['child ports'] == 'Ethernet0'
                assert output['Ethernet0']['child port speeds'] == '100G'
                get_child_ports_mock.assert_called_once_with(
                    'Ethernet0', '1x100G', 'platform.json')

    def test_single_intf_breakout_details_with_alias(self):
        alias_converter = mock.Mock()
        alias_converter.alias_to_name.return_value = 'Ethernet0'

        with mock.patch("show.interfaces.clicommon.get_interface_naming_mode",
                        return_value='alias'), \
             mock.patch("show.interfaces.clicommon.InterfaceAliasConverter",
                        return_value=alias_converter):
            result, get_child_ports_mock = self._invoke_breakout_details(
                ['-i', 'etp1'])

        assert result.exit_code == 0, result.output
        assert list(json.loads(result.output)) == ['Ethernet0']
        alias_converter.alias_to_name.assert_called_once_with('etp1')
        get_child_ports_mock.assert_called_once_with(
            'Ethernet0', '1x100G', 'platform.json')

    def test_unknown_intf_breakout_details(self):
        result, get_child_ports_mock = self._invoke_breakout_details(
            ['-i', 'Ethernet60'])

        assert result.exit_code == 2
        assert "Invalid interface name Ethernet60" in result.output
        get_child_ports_mock.assert_not_called()

    def test_single_intf_breakout_details_without_breakout_cfg(self):
        result, get_child_ports_mock = self._invoke_breakout_details(
            ['-i', 'Ethernet0'], breakout_cfg={})

        assert result.exit_code == 2
        assert "Breakout information is not available for interface Ethernet0" in result.output
        get_child_ports_mock.assert_not_called()

    def test_breakout_interface_option_with_subcommand(self):
        command = show.cli.commands["interfaces"].commands["breakout"]
        result = self.runner.invoke(
            command, ['-i', 'Ethernet0', 'current-mode'], obj={})

        assert result.exit_code == 2
        assert "--interface is only valid without a breakout subcommand" in result.output

    def test_current_mode_through_breakout_group(self):
        config_db = mock.Mock()
        config_db.get_table.return_value = {
            'Ethernet0': {'brkout_mode': '4x25G[10G]'}
        }
        command = show.cli.commands["interfaces"].commands["breakout"]

        with mock.patch("show.interfaces.ConfigDBConnector", return_value=config_db):
            result = self.runner.invoke(
                command, ['current-mode', 'Ethernet0'], obj={})

        assert result.exit_code == 0, result.output
        assert result.output == current_mode_intf_output

    # Test 'show interfaces  breakout current-mode'
    def test_all_intf_current_mode(self):
        result = self.runner.invoke(show.cli.commands["interfaces"].commands["breakout"].commands["current-mode"], [], obj=self.obj)
        print(sys.stderr, result.output)
        assert result.output == current_mode_all_output

    # Test 'show interfaces  breakout current-mode Ethernet0'
    def test_single_intf_current_mode(self):
        result = self.runner.invoke(show.cli.commands["interfaces"].commands["breakout"].commands["current-mode"], ["Ethernet0"], obj=self.obj)
        print(sys.stderr, result.output)
        assert result.output == current_mode_intf_output

    # Negetive Test 'show interfaces  breakout current-mode Ethernet60'
    def test_single_intf_current_mode(self):
        result = self.runner.invoke(show.cli.commands["interfaces"].commands["breakout"].commands["current-mode"], ["Ethernet60"], obj=self.obj)
        print(sys.stderr, result.output)
        assert result.output == current_mode_intf_output_Ethernet60

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")

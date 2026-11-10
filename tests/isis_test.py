import os
import copy
from unittest import mock
import pytest
from click.testing import CliRunner

import config.main as config
import show.main as show
from utilities_common.db import Db
from sonic_py_common import multi_asic


@pytest.fixture
def isis_af_db():
    db = Db()
    config_db = db.cfgdb
    rows = [('PORT', 'Ethernet0'), ('INTERFACE', 'Ethernet0'),
            ('VRF', 'VrfIsis'), ('ISIS_GLOBALS', 'default'), ('ISIS_GLOBALS', 'VrfIsis'),
            ('ISIS_INTERFACE', 'Ethernet0'),
            ('PORTCHANNEL_MEMBER', ('PortChannel999', 'Ethernet0')),
            ('VLAN_MEMBER', ('Vlan999', 'Ethernet0'))]
    saved = {(table, key): copy.deepcopy(db.cfgdb.get_entry(table, key)) for table, key in rows}
    for table, key in rows:
        db.cfgdb.set_entry(table, key, None)
    db.cfgdb.set_entry('PORT', 'Ethernet0', {'alias': 'etp1', 'admin_status': 'up'})
    db.cfgdb.set_entry('ISIS_GLOBALS', 'default',
                       {'enabled': 'true', 'net_title': '49.0001.1921.6800.0001.00', 'level': 'level-2'})
    db.cfgdb.set_entry('ISIS_INTERFACE', 'Ethernet0',
                       {'enabled': 'true', 'metric': '30', 'passive': 'true', 'circuit_type': 'p2p'})
    yield db
    db.cfgdb = config_db
    for (table, key), data in saved.items():
        db.cfgdb.set_entry(table, key, data or None)


class TestIsis(object):
    config_isis_enable = config.config.commands["isis"].commands["enable"]
    config_isis_disable = config.config.commands["isis"].commands["disable"]
    config_isis_net = config.config.commands["isis"].commands["net"]
    config_isis_level = config.config.commands["isis"].commands["level"]
    config_isis_hostname = config.config.commands["isis"].commands["hostname"]

    config_isis_timer_lsp_mtu = config.config.commands["isis"].commands["timer"].commands["lsp-mtu"]
    config_isis_timer_lsp_refresh = config.config.commands["isis"].commands["timer"].commands["lsp-refresh"]
    config_isis_timer_lsp_lifetime = config.config.commands["isis"].commands["timer"].commands["lsp-lifetime"]

    config_interface_isis_enable = config.config.commands["interface"].commands["isis"].commands["enable"]
    config_interface_isis_disable = config.config.commands["interface"].commands["isis"].commands["disable"]
    config_interface_isis_metric = config.config.commands["interface"].commands["isis"].commands["metric"]
    config_interface_isis_circuit_type = config.config.commands["interface"].commands["isis"].commands["circuit-type"]
    config_interface_isis_passive = config.config.commands["interface"].commands["isis"].commands["passive"]

    show_isis_summary = show.cli.commands["isis"].commands["summary"]
    show_isis_neighbor = show.cli.commands["isis"].commands["neighbor"]
    show_isis_database = show.cli.commands["isis"].commands["database"]

    @classmethod
    def setup_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    @classmethod
    def teardown_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

    def test_isis_enable_disable(self):
        db = Db()
        runner = CliRunner()
        obj = db

        # Enable IS-IS default VRF
        result = runner.invoke(self.config_isis_enable, [], obj=obj)
        assert result.exit_code == 0
        assert "default" in db.cfgdb.get_table("ISIS_GLOBALS")
        assert db.cfgdb.get_table("ISIS_GLOBALS")["default"]["enabled"] == "true"

        # Reject absent VRFs before writing anything.
        result = runner.invoke(self.config_isis_enable, ["Vrf2"], obj=obj)
        assert result.exit_code != 0
        db.cfgdb.set_entry("VRF", "Vrf2", {"NULL": "NULL"})
        # Enable IS-IS for non-default VRF Vrf2
        result = runner.invoke(self.config_isis_enable, ["Vrf2"], obj=obj)
        assert result.exit_code == 0
        assert "Vrf2" in db.cfgdb.get_table("ISIS_GLOBALS")
        assert db.cfgdb.get_table("ISIS_GLOBALS")["Vrf2"]["enabled"] == "true"

        # Disable IS-IS for Vrf2
        result = runner.invoke(self.config_isis_disable, ["Vrf2"], obj=obj)
        assert result.exit_code == 0
        assert db.cfgdb.get_entry("ISIS_GLOBALS", "Vrf2")["enabled"] == "false"

        # Disable IS-IS default VRF
        result = runner.invoke(self.config_isis_disable, [], obj=obj)
        assert result.exit_code == 0
        assert db.cfgdb.get_entry("ISIS_GLOBALS", "default")["enabled"] == "false"

    def test_isis_net_level_hostname(self):
        db = Db()
        runner = CliRunner()
        obj = db

        # Try configuring without enabling first (should fail)
        result = runner.invoke(self.config_isis_net, ["49.0001.1921.6800.0001.00"], obj=obj)
        assert result.exit_code != 0

        # Enable first
        runner.invoke(self.config_isis_enable, [], obj=obj)

        # Set valid NET
        result = runner.invoke(self.config_isis_net, ["49.0001.1921.6800.0001.00"], obj=obj)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("ISIS_GLOBALS")["default"]["net_title"] == "49.0001.1921.6800.0001.00"

        # Set invalid NET (should fail)
        result = runner.invoke(self.config_isis_net, ["invalid-net"], obj=obj)
        assert result.exit_code != 0

        # Set level
        result = runner.invoke(self.config_isis_level, ["level-1"], obj=obj)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("ISIS_GLOBALS")["default"]["level"] == "level-1"

        # Set hostname
        result = runner.invoke(self.config_isis_hostname, ["enable"], obj=obj)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("ISIS_GLOBALS")["default"]["dynamic_hostname"] == "true"

    def test_isis_timers(self):
        db = Db()
        runner = CliRunner()
        obj = db

        # Enable first
        runner.invoke(self.config_isis_enable, [], obj=obj)

        # Set lsp-mtu
        result = runner.invoke(self.config_isis_timer_lsp_mtu, ["1400"], obj=obj)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("ISIS_GLOBALS_TIMERS")["default"]["lsp_mtu"] == "1400"

        # Set out-of-range lsp-mtu (should fail)
        result = runner.invoke(self.config_isis_timer_lsp_mtu, ["9999"], obj=obj)
        assert result.exit_code != 0

        # Set lsp-refresh
        result = runner.invoke(self.config_isis_timer_lsp_refresh, ["900"], obj=obj)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("ISIS_GLOBALS_TIMERS")["default"]["lsp_refresh_interval"] == "900"

        # Set lsp-lifetime
        result = runner.invoke(self.config_isis_timer_lsp_lifetime, ["1500"], obj=obj)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("ISIS_GLOBALS_TIMERS")["default"]["lsp_lifetime"] == "1500"

    def test_isis_interface(self):
        db = Db()
        runner = CliRunner()

        # Let's mock a port in CONFIG_DB so validation passes
        db.cfgdb.set_entry("PORT", "Ethernet0", {"admin_status": "up"})

        obj = {'config_db': db.cfgdb, 'namespace': 'default'}

        runner.invoke(self.config_isis_enable, [], obj=db)

        # Enable ISIS on Ethernet0
        result = runner.invoke(self.config_interface_isis_enable, ["Ethernet0"], obj=obj)
        assert result.exit_code == 0
        assert "Ethernet0" in db.cfgdb.get_table("ISIS_INTERFACE")

        # Configure Metric
        result = runner.invoke(self.config_interface_isis_metric, ["Ethernet0", "20"], obj=obj)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("ISIS_INTERFACE")["Ethernet0"]["metric"] == "20"

        # Configure Circuit Type
        result = runner.invoke(self.config_interface_isis_circuit_type, ["Ethernet0", "p2p"], obj=obj)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("ISIS_INTERFACE")["Ethernet0"]["circuit_type"] == "p2p"

        # Configure Passive Mode
        result = runner.invoke(self.config_interface_isis_passive, ["Ethernet0", "enable"], obj=obj)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("ISIS_INTERFACE")["Ethernet0"]["passive"] == "true"

        # Disable ISIS on Ethernet0
        result = runner.invoke(self.config_interface_isis_disable, ["Ethernet0"], obj=obj)
        assert result.exit_code == 0
        assert db.cfgdb.get_entry("ISIS_INTERFACE", "Ethernet0")["enabled"] == "false"

    @mock.patch('utilities_common.bgp_util.get_vtysh_shell_cmd', return_value='vtysh')
    @mock.patch('utilities_common.cli.run_command')
    def test_show_isis(self, mock_run_command, mock_shell):
        mock_run_command.return_value = ("IS-IS output summary mock", 0)
        runner = CliRunner()

        # show isis summary
        result = runner.invoke(self.show_isis_summary, [])
        assert result.exit_code == 0
        assert "IS-IS output summary mock" in result.output
        mock_run_command.assert_called_with(['sudo', 'vtysh', '-c', 'show isis summary'], return_cmd=True)

        # show isis neighbor --json
        mock_run_command.return_value = ("[]", 0)
        result = runner.invoke(self.show_isis_neighbor, ["--json"])
        assert result.exit_code == 0
        mock_run_command.assert_called_with(['sudo', 'vtysh', '-c', 'show isis neighbor json'], return_cmd=True)

        # show isis database
        mock_run_command.return_value = ("IS-IS database mock", 0)
        result = runner.invoke(self.show_isis_database, [])
        assert result.exit_code == 0
        assert "IS-IS database mock" in result.output
        mock_run_command.assert_called_with(['sudo', 'vtysh', '-c', 'show isis database'], return_cmd=True)

        # vtysh errors must be reported to the CLI caller
        mock_run_command.return_value = ("", 1)
        result = runner.invoke(self.show_isis_database, [])
        assert result.exit_code != 0
        assert result.exit_code == 1

    def test_isis_validation_and_preserved_fields(self):
        db = Db()
        runner = CliRunner()
        db.cfgdb.set_entry('ISIS_GLOBALS', 'default', {'enabled': 'false', 'level': 'level-2'})
        result = runner.invoke(self.config_isis_enable, [], obj=db)
        assert result.exit_code == 0
        assert db.cfgdb.get_entry('ISIS_GLOBALS', 'default')['level'] == 'level-2'
        for net in ('49.0001.00', '49.0001.0000.0000.0001.01'):
            assert runner.invoke(self.config_isis_net, [net], obj=db).exit_code != 0
        db.cfgdb.set_entry('ISIS_GLOBALS_TIMERS', 'default', None)
        for value in ('0', '65236', '1000'):
            assert runner.invoke(self.config_isis_timer_lsp_refresh, [value], obj=db).exit_code != 0
        assert runner.invoke(self.config_isis_timer_lsp_lifetime, ['1199'], obj=db).exit_code != 0
        assert runner.invoke(self.config_isis_timer_lsp_mtu, ['4000'], obj=db).exit_code == 0
        assert runner.invoke(self.config_isis_timer_lsp_lifetime, ['1500'], obj=db).exit_code == 0
        assert runner.invoke(self.config_isis_timer_lsp_refresh, ['1000'], obj=db).exit_code == 0
        reset = config.config.commands['isis'].commands['reset']
        assert runner.invoke(reset, ['lsp-lifetime'], obj=db).exit_code != 0
        assert runner.invoke(reset, ['lsp-refresh'], obj=db).exit_code == 0
        assert db.cfgdb.get_entry('ISIS_GLOBALS_TIMERS', 'default') == {
            'lsp_mtu': '4000', 'lsp_lifetime': '1500'}
        assert runner.invoke(reset, ['lsp-lifetime'], obj=db).exit_code == 0
        assert db.cfgdb.get_entry('ISIS_GLOBALS_TIMERS', 'default') == {'lsp_mtu': '4000'}
        assert runner.invoke(reset, ['lsp-mtu'], obj=db).exit_code == 0
        assert not db.cfgdb.get_entry('ISIS_GLOBALS_TIMERS', 'default')
        db.cfgdb.set_entry('ISIS_GLOBALS_TIMERS', 'default', None)
        db.cfgdb.set_entry('ISIS_GLOBALS', 'default', None)

    def test_isis_interface_negative_paths(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb, 'namespace': ''}
        db.cfgdb.set_entry('PORT', 'Ethernet0', {'alias': 'etp1', 'admin_status': 'up'})
        db.cfgdb.set_entry('ISIS_INTERFACE', 'Ethernet0', None)
        db.cfgdb.set_entry('ISIS_GLOBALS', 'default', None)
        assert runner.invoke(self.config_interface_isis_enable, ['Ethernet0'], obj=obj).exit_code != 0
        runner.invoke(self.config_isis_enable, [], obj=db)
        assert runner.invoke(self.config_interface_isis_enable, ['EthernetMissing'], obj=obj).exit_code != 0
        for command, args in ((self.config_interface_isis_metric, ['Ethernet0', '20']),
                              (self.config_interface_isis_circuit_type, ['Ethernet0', 'p2p']),
                              (self.config_interface_isis_passive, ['Ethernet0', 'enable'])):
            assert runner.invoke(command, args, obj=obj).exit_code != 0
        db.cfgdb.set_entry('PORTCHANNEL_MEMBER', ('PortChannel999', 'Ethernet0'), {'NULL': 'NULL'})
        assert runner.invoke(self.config_interface_isis_enable, ['Ethernet0'], obj=obj).exit_code != 0
        db.cfgdb.set_entry('PORTCHANNEL_MEMBER', ('PortChannel999', 'Ethernet0'), None)
        db.cfgdb.set_entry('VLAN_MEMBER', ('Vlan999', 'Ethernet0'), {'tagging_mode': 'untagged'})
        assert runner.invoke(self.config_interface_isis_enable, ['Ethernet0'], obj=obj).exit_code != 0
        db.cfgdb.set_entry('VLAN_MEMBER', ('Vlan999', 'Ethernet0'), None)
        with mock.patch('utilities_common.cli.get_interface_naming_mode', return_value='alias'):
            result = runner.invoke(self.config_interface_isis_enable, ['etp1'], obj=obj)
        assert result.exit_code == 0, result.output
        assert db.cfgdb.get_entry('ISIS_INTERFACE', 'Ethernet0')['enabled'] == 'true'
        delete = config.config.commands['isis'].commands['del']
        assert runner.invoke(delete, [], obj=db).exit_code != 0
        assert runner.invoke(self.config_interface_isis_disable, ['Ethernet0'], obj=obj).exit_code == 0
        assert runner.invoke(self.config_isis_disable, [], obj=db).exit_code == 0

    @mock.patch('utilities_common.bgp_util.get_vtysh_shell_cmd', return_value='rvtysh')
    @mock.patch('utilities_common.bgp_util.run_bgp_command', return_value='state\n')
    def test_show_isis_detail_interface(self, run_command, shell):
        runner = CliRunner()
        result = runner.invoke(self.show_isis_database, ['detail', '--json'])
        assert result.exit_code == 0
        run_command.assert_called_with('show isis database detail json', multi_asic.DEFAULT_NAMESPACE, 'rvtysh')
        result = runner.invoke(show.cli.commands['isis'].commands['interface'], [])
        assert result.exit_code == 0
        run_command.assert_called_with('show isis interface', multi_asic.DEFAULT_NAMESPACE, 'rvtysh')

    def test_isis_namespace(self):
        runner = CliRunner()
        db = Db()
        group = config.config.commands['isis']
        namespace_option = next(param for param in group.params if param.name == 'namespace')
        with mock.patch.object(namespace_option.type, 'choices', ['asic0']), \
                mock.patch('config.isis.ConfigDBConnector') as connector:
            selected = connector.return_value
            selected.get_entry.return_value = {}
            result = runner.invoke(group, ['-n', 'asic0', 'enable'], obj=db)
        assert result.exit_code == 0, result.output
        connector.assert_called_once_with(use_unix_socket_path=True, namespace='asic0')
        selected.mod_entry.assert_called_once_with('ISIS_GLOBALS', 'default', {'enabled': 'true'})

    def test_isis_cleanup_retained_rows(self):
        db = Db()
        runner = CliRunner()
        obj = {'config_db': db.cfgdb, 'namespace': ''}
        for name, enabled in (('EthernetMissing', 'true'), ('Ethernet0', 'false')):
            db.cfgdb.set_entry('ISIS_INTERFACE', name, {'enabled': enabled, 'metric': '30'})
            db.cfgdb.set_entry('PORTCHANNEL_MEMBER', ('PortChannel999', name), {'NULL': 'NULL'})
            delete = config.config.commands['interface'].commands['isis'].commands['del']
            result = runner.invoke(delete, [name], obj=obj)
            assert result.exit_code == 0, result.output
            assert not db.cfgdb.get_entry('ISIS_INTERFACE', name)
            db.cfgdb.set_entry('PORTCHANNEL_MEMBER', ('PortChannel999', name), None)

    def test_isis_reset_removes_fields_and_preserves_siblings(self):
        db = Db()
        runner = CliRunner()
        reset = config.config.commands['isis'].commands['reset']
        db.cfgdb.set_entry('ISIS_GLOBALS', 'default', {
            'enabled': 'true', 'net_title': '49.0001.0000.0000.0001.00',
            'level': 'level-2', 'dynamic_hostname': 'false'})
        remaining = db.cfgdb.get_entry('ISIS_GLOBALS', 'default').copy()
        for option, field in (('net', 'net_title'), ('level', 'level'), ('hostname', 'dynamic_hostname')):
            assert runner.invoke(reset, [option], obj=db).exit_code == 0
            remaining.pop(field)
            assert db.cfgdb.get_entry('ISIS_GLOBALS', 'default') == remaining
        db.cfgdb.set_entry('PORT', 'Ethernet0', {'alias': 'etp1'})
        db.cfgdb.set_entry('ISIS_INTERFACE', 'Ethernet0', {
            'enabled': 'true', 'metric': '30', 'circuit_type': 'p2p', 'passive': 'true'})
        interface_reset = config.config.commands['interface'].commands['isis'].commands['reset']
        obj = {'config_db': db.cfgdb, 'namespace': multi_asic.DEFAULT_NAMESPACE}
        remaining = db.cfgdb.get_entry('ISIS_INTERFACE', 'Ethernet0').copy()
        for option in ('metric', 'circuit-type', 'passive'):
            result = runner.invoke(interface_reset, ['Ethernet0', option], obj=obj)
            assert result.exit_code == 0, result.output
            remaining.pop(option.replace('-', '_'))
            assert db.cfgdb.get_entry('ISIS_INTERFACE', 'Ethernet0') == remaining
        db.cfgdb.set_entry('ISIS_INTERFACE', 'Ethernet0', None)
        db.cfgdb.set_entry('ISIS_GLOBALS', 'default', None)

    def test_isis_interface_address_families(self, isis_af_db):
        db = isis_af_db.cfgdb
        runner = CliRunner()
        group = config.config.commands['interface'].commands['isis']
        obj = {'config_db': db, 'namespace': 'asic0'}
        original = db.get_entry('ISIS_INTERFACE', 'Ethernet0')

        result = runner.invoke(group, ['ipv4', 'Ethernet0', 'disable'], obj=obj)
        assert result.exit_code == 0, result.output
        assert db.get_entry('ISIS_INTERFACE', 'Ethernet0') == dict(original, ipv4_enabled='false')
        result = runner.invoke(group, ['ipv6', 'Ethernet0', 'disable'], obj=obj)
        assert result.exit_code == 0, result.output
        assert db.get_entry('ISIS_INTERFACE', 'Ethernet0') == dict(
            original, ipv4_enabled='false', ipv6_enabled='false')

        result = runner.invoke(group, ['ipv6', 'Ethernet0', 'enable'], obj=obj)
        assert result.exit_code == 0, result.output
        assert db.get_entry('ISIS_INTERFACE', 'Ethernet0') == dict(
            original, ipv4_enabled='false', ipv6_enabled='true')
        for family in ('ipv4', 'ipv6'):
            result = runner.invoke(group, ['reset', 'Ethernet0', family], obj=obj)
            assert result.exit_code == 0, result.output
        # Reset removes only the selected leaves; their effective default is true.
        assert db.get_entry('ISIS_INTERFACE', 'Ethernet0') == original

    @pytest.mark.parametrize('family', ['ipv4', 'ipv6'])
    def test_isis_af_rejects_invalid_input(self, isis_af_db, family):
        db = isis_af_db.cfgdb
        runner = CliRunner()
        group = config.config.commands['interface'].commands['isis']
        obj = {'config_db': db, 'namespace': ''}
        original = db.get_entry('ISIS_INTERFACE', 'Ethernet0')
        for state in ('true', 'false', 'invalid'):
            result = runner.invoke(group, [family, 'Ethernet0', state], obj=obj)
            assert result.exit_code == 2, result.output
            assert db.get_entry('ISIS_INTERFACE', 'Ethernet0') == original
        result = runner.invoke(group, [family, 'EthernetMissing', 'disable'], obj=obj)
        assert result.exit_code != 0
        assert not db.get_entry('ISIS_INTERFACE', 'EthernetMissing')
        db.set_entry('PORTCHANNEL_MEMBER', ('PortChannel999', 'Ethernet0'), {'NULL': 'NULL'})
        assert runner.invoke(group, [family, 'Ethernet0', 'disable'], obj=obj).exit_code != 0
        db.set_entry('PORTCHANNEL_MEMBER', ('PortChannel999', 'Ethernet0'), None)
        db.set_entry('VLAN_MEMBER', ('Vlan999', 'Ethernet0'), {'tagging_mode': 'untagged'})
        assert runner.invoke(group, [family, 'Ethernet0', 'disable'], obj=obj).exit_code != 0
        assert db.get_entry('ISIS_INTERFACE', 'Ethernet0') == original

    @pytest.mark.parametrize('family', ['ipv4', 'ipv6'])
    def test_isis_af_allows_disabled_interface_and_requires_parent(self, isis_af_db, family):
        db = isis_af_db.cfgdb
        runner = CliRunner()
        group = config.config.commands['interface'].commands['isis']
        obj = {'config_db': db, 'namespace': ''}
        original = db.get_entry('ISIS_INTERFACE', 'Ethernet0')
        db.set_entry('ISIS_INTERFACE', 'Ethernet0', dict(original, enabled='false'))
        assert runner.invoke(group, [family, 'Ethernet0', 'disable'], obj=obj).exit_code == 0
        assert db.get_entry('ISIS_INTERFACE', 'Ethernet0') == dict(
            original, enabled='false', **{family + '_enabled': 'false'})
        db.set_entry('ISIS_INTERFACE', 'Ethernet0', original)
        db.set_entry('INTERFACE', 'Ethernet0', {'vrf_name': 'VrfIsis'})
        # An enabled default process does not satisfy this interface's VRF.
        for args in ([family, 'Ethernet0', 'disable'], ['reset', 'Ethernet0', family]):
            assert runner.invoke(group, args, obj=obj).exit_code != 0
            assert db.get_entry('ISIS_INTERFACE', 'Ethernet0') == original
        db.set_entry('VRF', 'VrfIsis', {'NULL': 'NULL'})
        db.set_entry('ISIS_GLOBALS', 'VrfIsis', {'enabled': 'true'})
        with mock.patch('utilities_common.cli.get_interface_naming_mode', return_value='alias'):
            result = runner.invoke(group, [family, 'etp1', 'disable'], obj=obj)
        assert result.exit_code == 0, result.output
        assert db.get_entry('ISIS_INTERFACE', 'Ethernet0') == dict(original, **{family + '_enabled': 'false'})

    @pytest.mark.parametrize('family', ['ipv4', 'ipv6'])
    def test_isis_af_selected_namespace(self, isis_af_db, family):
        runner = CliRunner()
        group = config.config.commands['interface']
        option = next(param for param in group.params if param.name == 'namespace')
        selected = mock.MagicMock()
        selected.get_table.side_effect = lambda table: {'Ethernet0': {'alias': 'etp1'}} if table == 'PORT' else {}
        selected.get_entry.side_effect = lambda table, key: (
            {'enabled': 'true'} if table in ('ISIS_GLOBALS', 'ISIS_INTERFACE') else {})
        with mock.patch.object(option.type, 'choices', ['asic0']), \
                mock.patch('config.main.ConfigDBConnector', return_value=selected) as connector:
            result = runner.invoke(group, ['-n', 'asic0', 'isis', family, 'Ethernet0', 'disable'], obj=isis_af_db)
        assert result.exit_code == 0, result.output
        connector.assert_called_once_with(use_unix_socket_path=True, namespace='asic0')
        selected.mod_entry.assert_called_once_with('ISIS_INTERFACE', 'Ethernet0', {family + '_enabled': 'false'})

    def test_isis_af_database_write_error(self, isis_af_db):
        runner = CliRunner()
        command = config.config.commands['interface'].commands['isis']
        obj = {'config_db': isis_af_db.cfgdb, 'namespace': ''}
        original = isis_af_db.cfgdb.get_entry('ISIS_INTERFACE', 'Ethernet0')
        with mock.patch.object(isis_af_db.cfgdb, 'mod_entry', side_effect=RuntimeError('write failed')):
            result = runner.invoke(command, ['ipv4', 'Ethernet0', 'disable'], obj=obj)
        assert result.exit_code != 0
        assert 'write failed' in result.output
        assert isis_af_db.cfgdb.get_entry('ISIS_INTERFACE', 'Ethernet0') == original

    def test_isis_ipv6_multi_topology(self, isis_af_db):
        db = isis_af_db
        runner = CliRunner()
        group = config.config.commands['isis']
        original = db.cfgdb.get_entry('ISIS_GLOBALS', 'default')
        for state, value in (('disable', 'false'), ('enable', 'true')):
            result = runner.invoke(group, ['ipv6-multi-topology', state], obj=db)
            assert result.exit_code == 0, result.output
            assert db.cfgdb.get_entry('ISIS_GLOBALS', 'default') == dict(
                original, ipv6_multi_topology=value)
        result = runner.invoke(group, ['reset', 'ipv6-multi-topology'], obj=db)
        assert result.exit_code == 0, result.output
        assert db.cfgdb.get_entry('ISIS_GLOBALS', 'default') == original

        named = {'enabled': 'true', 'level': 'level-1'}
        db.cfgdb.set_entry('VRF', 'VrfIsis', {'NULL': 'NULL'})
        db.cfgdb.set_entry('ISIS_GLOBALS', 'VrfIsis', named)
        result = runner.invoke(group, ['ipv6-multi-topology', 'disable', 'VrfIsis'], obj=db)
        assert result.exit_code == 0, result.output
        assert db.cfgdb.get_entry('ISIS_GLOBALS', 'VrfIsis') == dict(named, ipv6_multi_topology='false')
        result = runner.invoke(group, ['reset', 'ipv6-multi-topology', 'VrfIsis'], obj=db)
        assert result.exit_code == 0, result.output
        assert db.cfgdb.get_entry('ISIS_GLOBALS', 'VrfIsis') == named
        assert db.cfgdb.get_entry('ISIS_GLOBALS', 'default') == original

    def test_isis_topology_rejects_invalid_state_and_allows_disabled_process(self, isis_af_db):
        db = isis_af_db
        runner = CliRunner()
        group = config.config.commands['isis']
        original = db.cfgdb.get_entry('ISIS_GLOBALS', 'default')
        for args in (['ipv6-multi-topology', 'invalid'], ['ipv6-multi-topology', 'disable', 'VrfMissing']):
            assert runner.invoke(group, args, obj=db).exit_code != 0
            assert db.cfgdb.get_entry('ISIS_GLOBALS', 'default') == original
        db.cfgdb.set_entry('ISIS_GLOBALS', 'default', dict(original, enabled='false'))
        for args in (['ipv6-multi-topology', 'disable'], ['reset', 'ipv6-multi-topology']):
            assert runner.invoke(group, args, obj=db).exit_code == 0
            assert db.cfgdb.get_entry('ISIS_GLOBALS', 'default')['enabled'] == 'false'
        assert db.cfgdb.get_entry('ISIS_GLOBALS', 'default') == dict(original, enabled='false')

    def test_isis_topology_selected_namespace(self, isis_af_db):
        runner = CliRunner()
        group = config.config.commands['isis']
        option = next(param for param in group.params if param.name == 'namespace')
        with mock.patch.object(option.type, 'choices', ['asic0']), \
                mock.patch('config.isis.ConfigDBConnector') as connector:
            selected = connector.return_value
            selected.get_entry.return_value = {'enabled': 'true'}
            result = runner.invoke(group, ['-n', 'asic0', 'ipv6-multi-topology', 'disable'], obj=isis_af_db)
        assert result.exit_code == 0, result.output
        connector.assert_called_once_with(use_unix_socket_path=True, namespace='asic0')
        selected.mod_entry.assert_called_once_with('ISIS_GLOBALS', 'default', {'ipv6_multi_topology': 'false'})

    def test_isis_topology_database_write_error(self, isis_af_db):
        runner = CliRunner()
        command = config.config.commands['isis']
        original = isis_af_db.cfgdb.get_entry('ISIS_GLOBALS', 'default')
        with mock.patch.object(isis_af_db.cfgdb, 'mod_entry', side_effect=RuntimeError('write failed')):
            result = runner.invoke(command, ['ipv6-multi-topology', 'disable'], obj=isis_af_db)
        assert result.exit_code != 0
        assert 'write failed' in result.output
        assert isis_af_db.cfgdb.get_entry('ISIS_GLOBALS', 'default') == original

    def test_isis_disabled_configuration_lifecycle(self, isis_af_db):
        db = isis_af_db
        runner = CliRunner()
        global_group = config.config.commands['isis']
        interface_group = config.config.commands['interface'].commands['isis']
        obj = {'config_db': db.cfgdb, 'namespace': ''}
        original = db.cfgdb.get_entry('ISIS_INTERFACE', 'Ethernet0')
        db.cfgdb.set_entry('ISIS_GLOBALS_TIMERS', 'default', {'lsp_mtu': '1400'})
        try:
            assert runner.invoke(global_group, ['disable'], obj=db).exit_code == 0
            assert db.cfgdb.get_entry('ISIS_INTERFACE', 'Ethernet0') == original
            assert db.cfgdb.get_entry('ISIS_GLOBALS_TIMERS', 'default') == {'lsp_mtu': '1400'}
            for args in (['net', '49.0001.0000.0000.0002.00'], ['level', 'level-1'],
                         ['hostname', 'disable'], ['timer', 'lsp-mtu', '1492']):
                result = runner.invoke(global_group, args, obj=db)
                assert result.exit_code == 0, result.output
                assert db.cfgdb.get_entry('ISIS_GLOBALS', 'default')['enabled'] == 'false'
            assert runner.invoke(interface_group, ['disable', 'Ethernet0'], obj=obj).exit_code == 0
            for args in (['metric', 'Ethernet0', '40'], ['passive', 'Ethernet0', 'disable'],
                         ['ipv4', 'Ethernet0', 'disable'], ['reset', 'Ethernet0', 'ipv6']):
                result = runner.invoke(interface_group, args, obj=obj)
                assert result.exit_code == 0, result.output
                assert db.cfgdb.get_entry('ISIS_INTERFACE', 'Ethernet0')['enabled'] == 'false'
            with mock.patch('config.isis.log.log_error') as error:
                result = runner.invoke(global_group, ['del'], obj=db)
                assert result.exit_code != 0
                error.assert_not_called()
            assert db.cfgdb.get_entry('ISIS_GLOBALS_TIMERS', 'default') == {'lsp_mtu': '1492'}
            assert runner.invoke(interface_group, ['enable', 'Ethernet0'], obj=obj).exit_code == 0
            assert runner.invoke(global_group, ['enable'], obj=db).exit_code == 0
            assert db.cfgdb.get_entry('ISIS_INTERFACE', 'Ethernet0')['metric'] == '40'
            assert db.cfgdb.get_entry('ISIS_INTERFACE', 'Ethernet0')['circuit_type'] == 'p2p'
            assert runner.invoke(interface_group, ['del', 'Ethernet0'], obj=obj).exit_code == 0
            assert runner.invoke(global_group, ['del'], obj=db).exit_code == 0
            assert not db.cfgdb.get_entry('ISIS_GLOBALS', 'default')
            assert not db.cfgdb.get_entry('ISIS_GLOBALS_TIMERS', 'default')
            # Create/edit before first activation; repeated add preserves values.
            assert runner.invoke(global_group, ['add'], obj=db).exit_code == 0
            assert runner.invoke(global_group, ['level', 'level-2'], obj=db).exit_code == 0
            assert runner.invoke(global_group, ['add'], obj=db).exit_code == 0
            assert db.cfgdb.get_entry('ISIS_GLOBALS', 'default') == {'enabled': 'false', 'level': 'level-2'}
            assert runner.invoke(interface_group, ['add', 'Ethernet0'], obj=obj).exit_code == 0
            assert runner.invoke(interface_group, ['metric', 'Ethernet0', '50'], obj=obj).exit_code == 0
            assert runner.invoke(interface_group, ['add', 'Ethernet0'], obj=obj).exit_code == 0
            assert db.cfgdb.get_entry('ISIS_INTERFACE', 'Ethernet0') == {'enabled': 'false', 'metric': '50'}
        finally:
            db.cfgdb.set_entry('ISIS_GLOBALS_TIMERS', 'default', None)

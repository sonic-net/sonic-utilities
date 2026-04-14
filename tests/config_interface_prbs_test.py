import pytest
import config.main as config
from click.testing import CliRunner
from unittest.mock import patch, MagicMock, call


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

class MockConfigDB:
    """In-memory ConfigDBConnector mock with get_table / mod_entry."""

    def __init__(self, port_table=None):
        self._tables = {
            'PORT': port_table or {
                'Ethernet0': {'speed': '100000'},
                'Ethernet4': {'speed': '100000'},
            }
        }
        self.mod_entry_calls = []

    def get_table(self, table):
        return dict(self._tables.get(table, {}))

    def mod_entry(self, table, key, value):
        self.mod_entry_calls.append((table, key, value))
        self._tables.setdefault(table, {}). \
            setdefault(key, {}).update(value)


class MockStateDB:
    """Minimal SonicV2Connector mock for platform-supported patterns."""
    STATE_DB = "STATE_DB"

    def __init__(self, state_data=None):
        self._store = state_data or {}

    def connect(self, db):
        pass

    def get(self, db, key, field):
        return self._store.get(key, {}).get(field)


def _obj(config_db):
    return {'config_db': config_db, 'namespace': ''}


def _prbs_cmd():
    return config.config.commands['interface'].commands['prbs']


# ---------------------------------------------------------------------------
# Enable command
# ---------------------------------------------------------------------------

class TestPrbsEnable:

    def _invoke(self, args, config_db=None, state_db=None):
        config_db = config_db or MockConfigDB()
        state_db = state_db or MockStateDB()
        runner = CliRunner()
        with patch('config.interface_prbs.SonicV2Connector',
                   return_value=state_db), \
             patch('utilities_common.cli.get_interface_naming_mode',
                   return_value='default'):
            result = runner.invoke(
                _prbs_cmd().commands['enable'],
                args,
                obj=_obj(config_db),
            )
        return result, config_db

    # -- happy paths --

    def test_enable_default_mode(self):
        result, db = self._invoke(['Ethernet0'])
        assert result.exit_code == 0
        assert "PRBS enabled on Ethernet0 (mode=rx, pattern=none)" in result.output
        assert db.mod_entry_calls[0][2] == {'prbs_mode': 'rx'}

    def test_enable_tx_mode(self):
        result, db = self._invoke(['Ethernet0', '-m', 'tx'])
        assert result.exit_code == 0
        assert "mode=tx" in result.output
        assert db.mod_entry_calls[0][2] == {'prbs_mode': 'tx'}

    def test_enable_both_mode(self):
        result, _ = self._invoke(['Ethernet0', '-m', 'both'])
        assert result.exit_code == 0
        assert "mode=both" in result.output

    def test_enable_with_pattern(self):
        result, db = self._invoke(['Ethernet0', '-p', 'PRBS31'])
        assert result.exit_code == 0
        assert "pattern=PRBS31" in result.output
        assert db.mod_entry_calls[0][2]['prbs_pattern'] == 'PRBS31'

    def test_enable_mode_and_pattern(self):
        result, db = self._invoke(['Ethernet0', '-m', 'both', '-p', 'PRBS7'])
        assert result.exit_code == 0
        assert "mode=both" in result.output
        assert "pattern=PRBS7" in result.output

    def test_enable_shows_running_note(self):
        result, _ = self._invoke(['Ethernet0'])
        assert result.exit_code == 0
        assert "PRBS test is now running" in result.output

    # -- failure paths --

    def test_enable_nonexistent_interface(self):
        result, _ = self._invoke(['Ethernet999'])
        assert result.exit_code != 0
        assert "does not exist" in result.output

    def test_enable_already_enabled(self):
        db = MockConfigDB(port_table={
            'Ethernet0': {'speed': '100000', 'prbs_mode': 'rx'},
        })
        result, _ = self._invoke(['Ethernet0'], config_db=db)
        assert result.exit_code != 0
        assert "already enabled" in result.output

    def test_enable_already_enabled_both(self):
        db = MockConfigDB(port_table={
            'Ethernet0': {'speed': '100000', 'prbs_mode': 'both'},
        })
        result, _ = self._invoke(['Ethernet0', '-m', 'tx'], config_db=db)
        assert result.exit_code != 0
        assert "already enabled" in result.output
        assert "disable first" in result.output

    def test_enable_invalid_pattern_rejected_by_click(self):
        """Click.Choice rejects patterns not in the allowed list."""
        result, _ = self._invoke(['Ethernet0', '-p', 'PRBS99'])
        assert result.exit_code != 0
        assert "Invalid value" in result.output or "invalid choice" in result.output.lower()

    def test_enable_invalid_mode_rejected_by_click(self):
        result, _ = self._invoke(['Ethernet0', '-m', 'duplex'])
        assert result.exit_code != 0

    def test_enable_missing_interface_arg(self):
        result, _ = self._invoke([])
        assert result.exit_code != 0

    # -- platform-supported pattern validation --

    def test_enable_pattern_unsupported_by_platform(self):
        state = MockStateDB({
            'PORT_TABLE|Ethernet0': {
                'supported_prbs_patterns': 'PRBS7,PRBS31'
            }
        })
        result, _ = self._invoke(
            ['Ethernet0', '-p', 'PRBS9'],
            state_db=state,
        )
        assert result.exit_code != 0
        assert "not supported" in result.output
        assert "PRBS7" in result.output
        assert "PRBS31" in result.output

    def test_enable_pattern_supported_by_platform(self):
        state = MockStateDB({
            'PORT_TABLE|Ethernet0': {
                'supported_prbs_patterns': 'PRBS7,PRBS31,PRBS9'
            }
        })
        result, db = self._invoke(
            ['Ethernet0', '-p', 'PRBS31'],
            state_db=state,
        )
        assert result.exit_code == 0
        assert "pattern=PRBS31" in result.output

    def test_enable_no_platform_data_skips_check(self):
        """When STATE_DB has no supported_prbs_patterns, any valid pattern is accepted."""
        state = MockStateDB({})
        result, _ = self._invoke(
            ['Ethernet0', '-p', 'SSPRQ'],
            state_db=state,
        )
        assert result.exit_code == 0
        assert "pattern=SSPRQ" in result.output

    # -- case insensitivity --

    def test_enable_mode_case_insensitive(self):
        result, db = self._invoke(['Ethernet0', '-m', 'TX'])
        assert result.exit_code == 0
        assert db.mod_entry_calls[0][2]['prbs_mode'] == 'tx'

    # -- alias handling --

    def test_enable_alias_mode(self):
        mock_converter = MagicMock()
        mock_converter.alias_to_name.return_value = 'Ethernet0'
        db = MockConfigDB()
        state = MockStateDB()
        runner = CliRunner()

        with patch('config.interface_prbs.SonicV2Connector',
                   return_value=state), \
             patch('utilities_common.cli.get_interface_naming_mode',
                   return_value='alias'), \
             patch('utilities_common.cli.iface_alias_converter',
                   mock_converter):
            result = runner.invoke(
                _prbs_cmd().commands['enable'],
                ['etp1'],
                obj=_obj(db),
            )

        assert result.exit_code == 0
        mock_converter.alias_to_name.assert_called_once_with('etp1')
        assert db.mod_entry_calls[0][1] == 'Ethernet0'

    def test_enable_alias_invalid(self):
        mock_converter = MagicMock()
        mock_converter.alias_to_name.return_value = None
        runner = CliRunner()

        with patch('config.interface_prbs.SonicV2Connector',
                   return_value=MockStateDB()), \
             patch('utilities_common.cli.get_interface_naming_mode',
                   return_value='alias'), \
             patch('utilities_common.cli.iface_alias_converter',
                   mock_converter):
            result = runner.invoke(
                _prbs_cmd().commands['enable'],
                ['bad_alias'],
                obj=_obj(MockConfigDB()),
            )

        assert result.exit_code != 0
        assert "Invalid interface name" in result.output

    # -- does not mutate DB on failure --

    def test_enable_no_db_write_on_nonexistent(self):
        db = MockConfigDB()
        self._invoke(['EthernetXYZ'], config_db=db)
        assert db.mod_entry_calls == []

    def test_enable_no_db_write_when_already_enabled(self):
        db = MockConfigDB(port_table={
            'Ethernet0': {'speed': '100000', 'prbs_mode': 'tx'},
        })
        self._invoke(['Ethernet0'], config_db=db)
        assert db.mod_entry_calls == []


# ---------------------------------------------------------------------------
# Disable command
# ---------------------------------------------------------------------------

class TestPrbsDisable:

    def _invoke(self, args, config_db=None):
        config_db = config_db or MockConfigDB()
        runner = CliRunner()
        with patch('utilities_common.cli.get_interface_naming_mode',
                   return_value='default'):
            result = runner.invoke(
                _prbs_cmd().commands['disable'],
                args,
                obj=_obj(config_db),
            )
        return result, config_db

    # -- happy paths --

    def test_disable_rx(self):
        db = MockConfigDB(port_table={
            'Ethernet0': {'speed': '100000', 'prbs_mode': 'rx'},
        })
        result, _ = self._invoke(['Ethernet0'], config_db=db)
        assert result.exit_code == 0
        assert "PRBS disabled on Ethernet0" in result.output
        assert "Results captured" in result.output
        assert db.mod_entry_calls == [('PORT', 'Ethernet0', {'prbs_mode': 'disabled'})]

    def test_disable_both(self):
        db = MockConfigDB(port_table={
            'Ethernet0': {'speed': '100000', 'prbs_mode': 'both'},
        })
        result, _ = self._invoke(['Ethernet0'], config_db=db)
        assert result.exit_code == 0
        assert "PRBS disabled" in result.output

    def test_disable_tx(self):
        db = MockConfigDB(port_table={
            'Ethernet0': {'speed': '100000', 'prbs_mode': 'tx'},
        })
        result, _ = self._invoke(['Ethernet0'], config_db=db)
        assert result.exit_code == 0

    # -- not enabled --

    def test_disable_when_not_enabled(self):
        db = MockConfigDB(port_table={
            'Ethernet0': {'speed': '100000'},
        })
        result, _ = self._invoke(['Ethernet0'], config_db=db)
        assert result.exit_code == 0
        assert "not enabled" in result.output
        assert db.mod_entry_calls == []

    def test_disable_when_already_disabled(self):
        db = MockConfigDB(port_table={
            'Ethernet0': {'speed': '100000', 'prbs_mode': 'disabled'},
        })
        result, _ = self._invoke(['Ethernet0'], config_db=db)
        assert result.exit_code == 0
        assert "not enabled" in result.output

    # -- failure paths --

    def test_disable_nonexistent_interface(self):
        result, _ = self._invoke(['Ethernet999'])
        assert result.exit_code != 0
        assert "does not exist" in result.output

    def test_disable_missing_interface_arg(self):
        result, _ = self._invoke([])
        assert result.exit_code != 0

    # -- alias handling --

    def test_disable_alias_mode(self):
        mock_converter = MagicMock()
        mock_converter.alias_to_name.return_value = 'Ethernet4'
        db = MockConfigDB(port_table={
            'Ethernet4': {'speed': '100000', 'prbs_mode': 'rx'},
        })
        runner = CliRunner()

        with patch('utilities_common.cli.get_interface_naming_mode',
                   return_value='alias'), \
             patch('utilities_common.cli.iface_alias_converter',
                   mock_converter):
            result = runner.invoke(
                _prbs_cmd().commands['disable'],
                ['etp2'],
                obj=_obj(db),
            )

        assert result.exit_code == 0
        mock_converter.alias_to_name.assert_called_once_with('etp2')
        assert db.mod_entry_calls[0][1] == 'Ethernet4'

    def test_disable_alias_invalid(self):
        mock_converter = MagicMock()
        mock_converter.alias_to_name.return_value = None
        runner = CliRunner()

        with patch('utilities_common.cli.get_interface_naming_mode',
                   return_value='alias'), \
             patch('utilities_common.cli.iface_alias_converter',
                   mock_converter):
            result = runner.invoke(
                _prbs_cmd().commands['disable'],
                ['bad_alias'],
                obj=_obj(MockConfigDB()),
            )

        assert result.exit_code != 0
        assert "Invalid interface name" in result.output

    # -- no DB mutation on failure --

    def test_disable_no_db_write_on_nonexistent(self):
        db = MockConfigDB()
        self._invoke(['EthernetXYZ'], config_db=db)
        assert db.mod_entry_calls == []

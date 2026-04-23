import pytest
import diag.main as diag
from click.testing import CliRunner
from unittest.mock import patch, MagicMock, call


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

class MockConfigDB:
    """In-memory ConfigDBConnector mock with get_table / connect."""

    def __init__(self, port_table=None):
        self._tables = {
            'PORT': port_table or {
                'Ethernet0': {'speed': '100000'},
                'Ethernet4': {'speed': '100000'},
            }
        }

    def connect(self):
        pass

    def get_table(self, table):
        return dict(self._tables.get(table, {}))


class MockSonicV2Connector:
    """SonicV2Connector mock supporting STATE_DB and APPL_DB reads."""
    STATE_DB = "STATE_DB"
    APPL_DB = "APPL_DB"

    def __init__(self, *args, **kwargs):
        self._store = {}

    def connect(self, db):
        pass

    def get(self, db, key, field):
        return self._store.get(db, {}).get(key, {}).get(field)

    def seed(self, db, entries):
        """Populate mock: entries = {key: {field: value}}."""
        self._store.setdefault(db, {}).update(entries)


class MockProducerStateTable:
    """Track ProducerStateTable.set calls."""

    def __init__(self, *args, **kwargs):
        self.set_calls = []

    def set(self, key, fvs):
        self.set_calls.append((key, list(fvs)))


def _prbs_cmd():
    return diag.cli.commands['interface'].commands['prbs']


# ---------------------------------------------------------------------------
# Enable command
# ---------------------------------------------------------------------------

class TestPrbsEnable:

    def _invoke(self, args, config_db=None, sv2=None, pst=None):
        config_db = config_db or MockConfigDB()
        sv2 = sv2 or MockSonicV2Connector()
        pst = pst or MockProducerStateTable()
        runner = CliRunner()
        with patch('diag.main.ConfigDBConnector', return_value=config_db), \
             patch('diag.main.SonicV2Connector', return_value=sv2), \
             patch('diag.main.DBConnector'), \
             patch('diag.main.ProducerStateTable', return_value=pst), \
             patch('diag.main.FieldValuePairs', side_effect=lambda x: x), \
             patch('utilities_common.cli.get_interface_naming_mode',
                   return_value='default'):
            result = runner.invoke(
                _prbs_cmd().commands['enable'],
                args,
            )
        return result, pst

    # -- happy paths --

    def test_enable_default_mode(self):
        result, pst = self._invoke(['Ethernet0'])
        assert result.exit_code == 0
        assert "PRBS enabled on Ethernet0 (mode=rx, pattern=none)" in result.output
        assert pst.set_calls[0] == ('Ethernet0', [('prbs_mode', 'rx')])

    def test_enable_tx_mode(self):
        result, pst = self._invoke(['Ethernet0', '-m', 'tx'])
        assert result.exit_code == 0
        assert "mode=tx" in result.output
        assert pst.set_calls[0] == ('Ethernet0', [('prbs_mode', 'tx')])

    def test_enable_both_mode(self):
        result, _ = self._invoke(['Ethernet0', '-m', 'both'])
        assert result.exit_code == 0
        assert "mode=both" in result.output

    def test_enable_with_pattern(self):
        result, pst = self._invoke(['Ethernet0', '-p', 'PRBS31'])
        assert result.exit_code == 0
        assert "pattern=PRBS31" in result.output
        fvs_dict = dict(pst.set_calls[0][1])
        assert fvs_dict['prbs_pattern'] == 'PRBS31'

    def test_enable_mode_and_pattern(self):
        result, pst = self._invoke(['Ethernet0', '-m', 'both', '-p', 'PRBS7'])
        assert result.exit_code == 0
        assert "mode=both" in result.output
        assert "pattern=PRBS7" in result.output

    def test_enable_shows_running_note(self):
        result, _ = self._invoke(['Ethernet0'])
        assert result.exit_code == 0
        assert "PRBS test is now running" in result.output
        assert "diag interface prbs disable" in result.output

    # -- failure paths --

    def test_enable_nonexistent_interface(self):
        result, _ = self._invoke(['Ethernet999'])
        assert result.exit_code != 0
        assert "does not exist" in result.output

    def test_enable_already_enabled(self):
        sv2 = MockSonicV2Connector()
        sv2.seed('APPL_DB', {
            'DIAG_PORT_TABLE:Ethernet0': {'prbs_mode': 'rx'}
        })
        result, pst = self._invoke(['Ethernet0'], sv2=sv2)
        assert result.exit_code != 0
        assert "already enabled" in result.output
        assert pst.set_calls == []

    def test_enable_already_enabled_both(self):
        sv2 = MockSonicV2Connector()
        sv2.seed('APPL_DB', {
            'DIAG_PORT_TABLE:Ethernet0': {'prbs_mode': 'both'}
        })
        result, pst = self._invoke(['Ethernet0', '-m', 'tx'], sv2=sv2)
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
        sv2 = MockSonicV2Connector()
        sv2.seed('STATE_DB', {
            'PORT_TABLE|Ethernet0': {
                'supported_prbs_patterns': 'PRBS7,PRBS31'
            }
        })
        result, _ = self._invoke(
            ['Ethernet0', '-p', 'PRBS9'],
            sv2=sv2,
        )
        assert result.exit_code != 0
        assert "not supported" in result.output
        assert "PRBS7" in result.output
        assert "PRBS31" in result.output

    def test_enable_pattern_supported_by_platform(self):
        sv2 = MockSonicV2Connector()
        sv2.seed('STATE_DB', {
            'PORT_TABLE|Ethernet0': {
                'supported_prbs_patterns': 'PRBS7,PRBS31,PRBS9'
            }
        })
        result, pst = self._invoke(
            ['Ethernet0', '-p', 'PRBS31'],
            sv2=sv2,
        )
        assert result.exit_code == 0
        assert "pattern=PRBS31" in result.output

    def test_enable_no_platform_data_skips_check(self):
        """When STATE_DB has no supported_prbs_patterns, any valid pattern is accepted."""
        sv2 = MockSonicV2Connector()
        result, _ = self._invoke(
            ['Ethernet0', '-p', 'SSPRQ'],
            sv2=sv2,
        )
        assert result.exit_code == 0
        assert "pattern=SSPRQ" in result.output

    # -- case insensitivity --

    def test_enable_mode_case_insensitive(self):
        result, pst = self._invoke(['Ethernet0', '-m', 'TX'])
        assert result.exit_code == 0
        fvs_dict = dict(pst.set_calls[0][1])
        assert fvs_dict['prbs_mode'] == 'tx'

    # -- alias handling --

    def test_enable_alias_mode(self):
        mock_converter = MagicMock()
        mock_converter.alias_to_name.return_value = 'Ethernet0'
        sv2 = MockSonicV2Connector()
        pst = MockProducerStateTable()
        runner = CliRunner()

        with patch('diag.main.ConfigDBConnector', return_value=MockConfigDB()), \
             patch('diag.main.SonicV2Connector', return_value=sv2), \
             patch('diag.main.DBConnector'), \
             patch('diag.main.ProducerStateTable', return_value=pst), \
             patch('diag.main.FieldValuePairs', side_effect=lambda x: x), \
             patch('utilities_common.cli.get_interface_naming_mode',
                   return_value='alias'), \
             patch('utilities_common.cli.iface_alias_converter',
                   mock_converter):
            result = runner.invoke(
                _prbs_cmd().commands['enable'],
                ['etp1'],
            )

        assert result.exit_code == 0
        mock_converter.alias_to_name.assert_called_once_with('etp1')
        assert pst.set_calls[0][0] == 'Ethernet0'

    def test_enable_alias_invalid(self):
        mock_converter = MagicMock()
        mock_converter.alias_to_name.return_value = None
        runner = CliRunner()

        with patch('diag.main.ConfigDBConnector', return_value=MockConfigDB()), \
             patch('diag.main.SonicV2Connector', return_value=MockSonicV2Connector()), \
             patch('diag.main.DBConnector'), \
             patch('diag.main.ProducerStateTable', return_value=MockProducerStateTable()), \
             patch('diag.main.FieldValuePairs', side_effect=lambda x: x), \
             patch('utilities_common.cli.get_interface_naming_mode',
                   return_value='alias'), \
             patch('utilities_common.cli.iface_alias_converter',
                   mock_converter):
            result = runner.invoke(
                _prbs_cmd().commands['enable'],
                ['bad_alias'],
            )

        assert result.exit_code != 0
        assert "Invalid interface name" in result.output

    # -- does not write to DB on failure --

    def test_enable_no_db_write_on_nonexistent(self):
        _, pst = self._invoke(['EthernetXYZ'])
        assert pst.set_calls == []

    def test_enable_no_db_write_when_already_enabled(self):
        sv2 = MockSonicV2Connector()
        sv2.seed('APPL_DB', {
            'DIAG_PORT_TABLE:Ethernet0': {'prbs_mode': 'tx'}
        })
        _, pst = self._invoke(['Ethernet0'], sv2=sv2)
        assert pst.set_calls == []


# ---------------------------------------------------------------------------
# Disable command
# ---------------------------------------------------------------------------

class TestPrbsDisable:

    def _invoke(self, args, config_db=None, sv2=None, pst=None):
        config_db = config_db or MockConfigDB()
        sv2 = sv2 or MockSonicV2Connector()
        pst = pst or MockProducerStateTable()
        runner = CliRunner()
        with patch('diag.main.ConfigDBConnector', return_value=config_db), \
             patch('diag.main.SonicV2Connector', return_value=sv2), \
             patch('diag.main.DBConnector'), \
             patch('diag.main.ProducerStateTable', return_value=pst), \
             patch('diag.main.FieldValuePairs', side_effect=lambda x: x), \
             patch('utilities_common.cli.get_interface_naming_mode',
                   return_value='default'):
            result = runner.invoke(
                _prbs_cmd().commands['disable'],
                args,
            )
        return result, pst

    # -- happy paths --

    def test_disable_rx(self):
        sv2 = MockSonicV2Connector()
        sv2.seed('APPL_DB', {
            'DIAG_PORT_TABLE:Ethernet0': {'prbs_mode': 'rx'}
        })
        result, pst = self._invoke(['Ethernet0'], sv2=sv2)
        assert result.exit_code == 0
        assert "PRBS disabled on Ethernet0" in result.output
        assert "Results captured" in result.output
        assert pst.set_calls == [('Ethernet0', [('prbs_mode', 'disabled')])]

    def test_disable_both(self):
        sv2 = MockSonicV2Connector()
        sv2.seed('APPL_DB', {
            'DIAG_PORT_TABLE:Ethernet0': {'prbs_mode': 'both'}
        })
        result, _ = self._invoke(['Ethernet0'], sv2=sv2)
        assert result.exit_code == 0
        assert "PRBS disabled" in result.output

    def test_disable_tx(self):
        sv2 = MockSonicV2Connector()
        sv2.seed('APPL_DB', {
            'DIAG_PORT_TABLE:Ethernet0': {'prbs_mode': 'tx'}
        })
        result, _ = self._invoke(['Ethernet0'], sv2=sv2)
        assert result.exit_code == 0

    # -- not enabled --

    def test_disable_when_not_enabled(self):
        result, pst = self._invoke(['Ethernet0'])
        assert result.exit_code == 0
        assert "not enabled" in result.output
        assert pst.set_calls == []

    def test_disable_when_already_disabled(self):
        sv2 = MockSonicV2Connector()
        sv2.seed('APPL_DB', {
            'DIAG_PORT_TABLE:Ethernet0': {'prbs_mode': 'disabled'}
        })
        result, pst = self._invoke(['Ethernet0'], sv2=sv2)
        assert result.exit_code == 0
        assert "not enabled" in result.output
        assert pst.set_calls == []

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
        sv2 = MockSonicV2Connector()
        sv2.seed('APPL_DB', {
            'DIAG_PORT_TABLE:Ethernet4': {'prbs_mode': 'rx'}
        })
        config_db = MockConfigDB(port_table={
            'Ethernet4': {'speed': '100000'},
        })
        pst = MockProducerStateTable()
        runner = CliRunner()

        with patch('diag.main.ConfigDBConnector', return_value=config_db), \
             patch('diag.main.SonicV2Connector', return_value=sv2), \
             patch('diag.main.DBConnector'), \
             patch('diag.main.ProducerStateTable', return_value=pst), \
             patch('diag.main.FieldValuePairs', side_effect=lambda x: x), \
             patch('utilities_common.cli.get_interface_naming_mode',
                   return_value='alias'), \
             patch('utilities_common.cli.iface_alias_converter',
                   mock_converter):
            result = runner.invoke(
                _prbs_cmd().commands['disable'],
                ['etp2'],
            )

        assert result.exit_code == 0
        mock_converter.alias_to_name.assert_called_once_with('etp2')
        assert pst.set_calls[0][0] == 'Ethernet4'

    def test_disable_alias_invalid(self):
        mock_converter = MagicMock()
        mock_converter.alias_to_name.return_value = None
        runner = CliRunner()

        with patch('diag.main.ConfigDBConnector', return_value=MockConfigDB()), \
             patch('diag.main.SonicV2Connector', return_value=MockSonicV2Connector()), \
             patch('diag.main.DBConnector'), \
             patch('diag.main.ProducerStateTable', return_value=MockProducerStateTable()), \
             patch('diag.main.FieldValuePairs', side_effect=lambda x: x), \
             patch('utilities_common.cli.get_interface_naming_mode',
                   return_value='alias'), \
             patch('utilities_common.cli.iface_alias_converter',
                   mock_converter):
            result = runner.invoke(
                _prbs_cmd().commands['disable'],
                ['bad_alias'],
            )

        assert result.exit_code != 0
        assert "Invalid interface name" in result.output

    # -- no DB mutation on failure --

    def test_disable_no_db_write_on_nonexistent(self):
        _, pst = self._invoke(['EthernetXYZ'])
        assert pst.set_calls == []

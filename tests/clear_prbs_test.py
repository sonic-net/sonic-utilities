import fnmatch

import clear.main as clear
from click.testing import CliRunner
from unittest.mock import patch


class MockStateDB:
    """In-memory STATE_DB mock that supports keys/get_all/exists/delete."""
    STATE_DB = "STATE_DB"

    def __init__(self, *args, **kwargs):
        self._store = {}

    def connect(self, db):
        pass

    def keys(self, db, pattern):
        matched = [k for k in self._store if fnmatch.fnmatch(k, pattern)]
        return matched if matched else None

    def get_all(self, db, key):
        return self._store.get(key)

    def get(self, db, key, field):
        entry = self._store.get(key, {})
        return entry.get(field)

    def exists(self, db, key):
        return key in self._store

    def delete(self, db, key):
        self._store.pop(key, None)

    def seed(self, entries):
        """Populate the mock with {key: {field: value, ...}, ...}."""
        self._store.update(entries)


class MockConfigDB:
    """Minimal ConfigDBConnector mock with a PORT table."""

    def __init__(self, *args, **kwargs):
        self._tables = {
            'PORT': {
                'Ethernet0': {'speed': '100000'},
                'Ethernet4': {'speed': '100000'},
            }
        }

    def connect(self):
        pass

    def get_table(self, table):
        return self._tables.get(table, {})


def _invoke_clear_prbs(state_db_instance, args=None):
    """Helper: patch DB classes, invoke 'sonic-clear prbs results', return result."""
    runner = CliRunner()
    cmd = clear.cli.commands['prbs'].commands['results']

    with patch('swsscommon.swsscommon.SonicV2Connector', return_value=state_db_instance), \
         patch('swsscommon.swsscommon.ConfigDBConnector', return_value=MockConfigDB()), \
         patch('utilities_common.cli.get_interface_naming_mode', return_value='default'):
        return runner.invoke(cmd, args or [])


class TestClearPrbsAll:
    """Tests for 'sonic-clear prbs results' (all interfaces)."""

    def test_clear_all_no_results(self):
        state_db = MockStateDB()
        result = _invoke_clear_prbs(state_db)
        assert result.exit_code == 0
        assert "No PRBS results found." in result.output

    def test_clear_all_success(self):
        state_db = MockStateDB()
        state_db.seed({
            'PORT_PRBS_TEST|Ethernet0': {'status': 'completed', 'mode': 'rx'},
            'PORT_PRBS_RESULTS|Ethernet0': {'ber': '1e-10'},
            'PORT_PRBS_LANE_RESULT|Ethernet0|0': {'ber': '1e-10'},
            'PORT_PRBS_LANE_RESULT|Ethernet0|1': {'ber': '1e-11'},
            'PORT_PRBS_TEST|Ethernet4': {'status': 'completed', 'mode': 'tx'},
            'PORT_PRBS_RESULTS|Ethernet4': {'ber': '1e-9'},
        })
        result = _invoke_clear_prbs(state_db)
        assert result.exit_code == 0
        assert "Cleared PRBS results for all interfaces (6 records deleted)" in result.output
        assert len(state_db._store) == 0

    def test_clear_all_blocked_while_running(self):
        state_db = MockStateDB()
        state_db.seed({
            'PORT_PRBS_TEST|Ethernet0': {'status': 'running', 'mode': 'rx'},
            'PORT_PRBS_RESULTS|Ethernet4': {'ber': '1e-9'},
        })
        result = _invoke_clear_prbs(state_db)
        assert result.exit_code != 0
        assert "Cannot clear PRBS results while PRBS is running" in result.output

    def test_clear_all_blocked_while_running_preserves_data(self):
        """Guard must NOT delete anything when it fires."""
        state_db = MockStateDB()
        state_db.seed({
            'PORT_PRBS_TEST|Ethernet0': {'status': 'running', 'mode': 'rx'},
            'PORT_PRBS_RESULTS|Ethernet0': {'ber': '1e-10'},
        })
        _invoke_clear_prbs(state_db)
        assert 'PORT_PRBS_TEST|Ethernet0' in state_db._store
        assert 'PORT_PRBS_RESULTS|Ethernet0' in state_db._store

    def test_clear_all_mixed_completed_only(self):
        """Multiple interfaces, all completed — all should be cleared."""
        state_db = MockStateDB()
        state_db.seed({
            'PORT_PRBS_TEST|Ethernet0': {'status': 'completed'},
            'PORT_PRBS_TEST|Ethernet4': {'status': 'completed'},
            'PORT_PRBS_RESULTS|Ethernet0': {'ber': '0'},
            'PORT_PRBS_RESULTS|Ethernet4': {'ber': '0'},
        })
        result = _invoke_clear_prbs(state_db)
        assert result.exit_code == 0
        assert "4 records deleted" in result.output
        assert len(state_db._store) == 0


class TestClearPrbsInterface:
    """Tests for 'sonic-clear prbs results -i <interface>'."""

    def test_clear_interface_success(self):
        state_db = MockStateDB()
        state_db.seed({
            'PORT_PRBS_TEST|Ethernet0': {'status': 'completed', 'mode': 'rx'},
            'PORT_PRBS_RESULTS|Ethernet0': {'ber': '1e-10'},
            'PORT_PRBS_LANE_RESULT|Ethernet0|0': {'ber': '1e-10'},
            'PORT_PRBS_LANE_RESULT|Ethernet0|1': {'ber': '1e-11'},
        })
        result = _invoke_clear_prbs(state_db, ['-i', 'Ethernet0'])
        assert result.exit_code == 0
        assert "Cleared PRBS test results for Ethernet0 (4 records deleted)" in result.output
        assert len(state_db._store) == 0

    def test_clear_interface_blocked_while_running(self):
        state_db = MockStateDB()
        state_db.seed({
            'PORT_PRBS_TEST|Ethernet0': {'status': 'running', 'mode': 'rx'},
        })
        result = _invoke_clear_prbs(state_db, ['-i', 'Ethernet0'])
        assert result.exit_code != 0
        assert "Cannot clear PRBS results while PRBS is running on Ethernet0" in result.output

    def test_clear_interface_blocked_preserves_data(self):
        state_db = MockStateDB()
        state_db.seed({
            'PORT_PRBS_TEST|Ethernet0': {'status': 'running'},
            'PORT_PRBS_RESULTS|Ethernet0': {'ber': '1e-10'},
        })
        _invoke_clear_prbs(state_db, ['-i', 'Ethernet0'])
        assert 'PORT_PRBS_TEST|Ethernet0' in state_db._store
        assert 'PORT_PRBS_RESULTS|Ethernet0' in state_db._store

    def test_clear_interface_no_results(self):
        state_db = MockStateDB()
        result = _invoke_clear_prbs(state_db, ['-i', 'Ethernet0'])
        assert result.exit_code == 0
        assert "No PRBS test results found for Ethernet0" in result.output

    def test_clear_interface_does_not_exist(self):
        state_db = MockStateDB()
        result = _invoke_clear_prbs(state_db, ['-i', 'Ethernet999'])
        assert result.exit_code != 0
        assert "does not exist" in result.output

    def test_clear_interface_leaves_other_interfaces(self):
        """Clearing Ethernet0 must not touch Ethernet4 records."""
        state_db = MockStateDB()
        state_db.seed({
            'PORT_PRBS_TEST|Ethernet0': {'status': 'completed'},
            'PORT_PRBS_RESULTS|Ethernet0': {'ber': '1e-10'},
            'PORT_PRBS_TEST|Ethernet4': {'status': 'completed'},
            'PORT_PRBS_RESULTS|Ethernet4': {'ber': '1e-9'},
        })
        result = _invoke_clear_prbs(state_db, ['-i', 'Ethernet0'])
        assert result.exit_code == 0
        assert "Ethernet0" in result.output
        assert 'PORT_PRBS_TEST|Ethernet0' not in state_db._store
        assert 'PORT_PRBS_RESULTS|Ethernet0' not in state_db._store
        assert 'PORT_PRBS_TEST|Ethernet4' in state_db._store
        assert 'PORT_PRBS_RESULTS|Ethernet4' in state_db._store

    def test_clear_interface_allows_when_other_interface_running(self):
        """Running PRBS on Ethernet4 should NOT block clearing Ethernet0."""
        state_db = MockStateDB()
        state_db.seed({
            'PORT_PRBS_TEST|Ethernet0': {'status': 'completed'},
            'PORT_PRBS_RESULTS|Ethernet0': {'ber': '1e-10'},
            'PORT_PRBS_TEST|Ethernet4': {'status': 'running'},
        })
        result = _invoke_clear_prbs(state_db, ['-i', 'Ethernet0'])
        assert result.exit_code == 0
        assert "Cleared PRBS test results for Ethernet0" in result.output
        assert 'PORT_PRBS_TEST|Ethernet4' in state_db._store


class TestClearPrbsAlias:
    """Tests for alias mode in 'sonic-clear prbs results -i'."""

    def _invoke_alias(self, state_db, args, alias_return):
        from unittest.mock import MagicMock
        mock_converter = MagicMock()
        mock_converter.alias_to_name.return_value = alias_return
        runner = CliRunner()
        cmd = clear.cli.commands['prbs'].commands['results']
        with patch('swsscommon.swsscommon.SonicV2Connector', return_value=state_db), \
             patch('swsscommon.swsscommon.ConfigDBConnector', return_value=MockConfigDB()), \
             patch('utilities_common.cli.get_interface_naming_mode', return_value='alias'), \
             patch('utilities_common.cli.iface_alias_converter', mock_converter):
            return runner.invoke(cmd, args)

    def test_valid_alias_resolves_and_clears(self):
        state_db = MockStateDB()
        state_db.seed({
            'PORT_PRBS_TEST|Ethernet0': {'status': 'completed'},
        })
        result = self._invoke_alias(state_db, ['-i', 'etp1'], 'Ethernet0')
        assert result.exit_code == 0
        assert 'Ethernet0' in result.output

    def test_invalid_alias_fails(self):
        state_db = MockStateDB()
        result = self._invoke_alias(state_db, ['-i', 'bad_alias'], None)
        assert result.exit_code != 0
        assert 'Invalid interface name' in result.output

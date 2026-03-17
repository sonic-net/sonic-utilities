import os
import sys
import pytest
from click.testing import CliRunner
from unittest import mock
from unittest.mock import patch, MagicMock

import config.main as config
import show.main as show
import clear.main as clear
from utilities_common.db import Db


class TestConfigInterfaceDampening(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"

    def test_enable_dampening_defaults(self):
        """Test enabling dampening with default parameters"""
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(
            config.config.commands["interface"].commands["dampening"].commands["enable"],
            ["Ethernet0"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert "enabled" in result.output

    def test_enable_dampening_custom_params(self):
        """Test enabling dampening with custom parameters"""
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(
            config.config.commands["interface"].commands["dampening"].commands["enable"],
            ["Ethernet0", "--half-life", "10", "--reuse", "500",
             "--suppress", "3000", "--max-suppress-time", "40",
             "--flap-penalty", "2000"],
            obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert "enabled" in result.output

    def test_enable_dampening_monitor_mode(self):
        """Test enabling dampening in monitor-only mode"""
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(
            config.config.commands["interface"].commands["dampening"].commands["enable"],
            ["Ethernet0", "--monitor"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert "monitor" in result.output.lower()

    def test_enable_dampening_invalid_interface(self):
        """Test enabling dampening on non-existent interface"""
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(
            config.config.commands["interface"].commands["dampening"].commands["enable"],
            ["EthernetINVALID"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert "does not exist" in result.output

    def test_enable_dampening_reuse_ge_suppress(self):
        """Test that reuse >= suppress is rejected"""
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(
            config.config.commands["interface"].commands["dampening"].commands["enable"],
            ["Ethernet0", "--reuse", "3000", "--suppress", "2000"],
            obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert "Reuse threshold" in result.output

    def test_enable_dampening_halflife_gt_maxsuppress(self):
        """Test that half-life > max-suppress-time is rejected"""
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(
            config.config.commands["interface"].commands["dampening"].commands["enable"],
            ["Ethernet0", "--half-life", "30", "--max-suppress-time", "20"],
            obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert "Half-life" in result.output

    def test_enable_dampening_invalid_halflife(self):
        """Test that out-of-range half-life is rejected by click.IntRange"""
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(
            config.config.commands["interface"].commands["dampening"].commands["enable"],
            ["Ethernet0", "--half-life", "0"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert "Invalid value" in result.output

    def test_enable_dampening_overflow_warning(self):
        """Test warning for extremely high ceiling exponent"""
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(
            config.config.commands["interface"].commands["dampening"].commands["enable"],
            ["Ethernet0", "--half-life", "1", "--max-suppress-time", "3600",
             "--reuse", "100", "--suppress", "200"],
            obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert "Warning" in result.output

    def test_disable_dampening(self):
        """Test disabling dampening"""
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(
            config.config.commands["interface"].commands["dampening"].commands["disable"],
            ["Ethernet0"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert "disabled" in result.output

    def test_disable_dampening_invalid_interface(self):
        """Test disabling dampening on non-existent interface"""
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(
            config.config.commands["interface"].commands["dampening"].commands["disable"],
            ["EthernetINVALID"], obj=obj)
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert "does not exist" in result.output


class TestShowInterfacesDampening(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"

    def test_show_dampening_no_config(self):
        """Test show when no dampening is configured"""
        runner = CliRunner()
        db = Db()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["dampening"],
            [], obj=db)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert "not configured on any interface" in result.output

    def test_show_dampening_specific_disabled(self):
        """Test show for a specific interface with no dampening"""
        runner = CliRunner()
        db = Db()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["dampening"],
            ["Ethernet0"], obj=db)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert "disabled" in result.output

    def test_show_dampening_invalid_interface(self):
        """Test show for non-existent interface"""
        runner = CliRunner()
        db = Db()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["dampening"],
            ["EthernetINVALID"], obj=db)
        print(result.exit_code, result.output)
        assert result.exit_code != 0

    def test_show_dampening_configured(self):
        """Test show when dampening is configured on an interface"""
        runner = CliRunner()
        db = Db()

        # Set up dampening config via the config command first
        config_obj = {'config_db': db.cfgdb}
        runner.invoke(
            config.config.commands["interface"].commands["dampening"].commands["enable"],
            ["Ethernet0"], obj=config_obj)

        result = runner.invoke(
            show.cli.commands["interfaces"].commands["dampening"],
            ["Ethernet0"], obj=db)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert "aied" in result.output
        assert "Ethernet0" in result.output

    def test_show_dampening_monitor_mode(self):
        """Test show displays monitor mode correctly"""
        runner = CliRunner()
        db = Db()

        config_obj = {'config_db': db.cfgdb}
        runner.invoke(
            config.config.commands["interface"].commands["dampening"].commands["enable"],
            ["Ethernet0", "--monitor"], obj=config_obj)

        result = runner.invoke(
            show.cli.commands["interfaces"].commands["dampening"],
            ["Ethernet0"], obj=db)
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert "aied-monitor" in result.output


class TestClearInterfacesDampening(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"

    @patch('clear.main.ConfigDBConnector')
    @patch('clear.main.SonicV2Connector')
    def test_clear_dampening_specific_interface(self, mock_sv2, mock_cfgdb):
        """Test clearing dampening on a specific interface"""
        mock_db_instance = MagicMock()
        mock_cfgdb.return_value = mock_db_instance
        mock_db_instance.get_table.return_value = {
            "Ethernet0": {
                "link_event_damping_algorithm": "aied",
                "alias": "etp1",
            }
        }

        mock_state = MagicMock()
        mock_sv2.return_value = mock_state

        runner = CliRunner()
        result = runner.invoke(
            clear.cli.commands["interfaces"].commands["dampening"],
            ["Ethernet0"])
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert "Cleared dampening on Ethernet0" in result.output
        mock_state.set.assert_called_once()

    @patch('clear.main.ConfigDBConnector')
    @patch('clear.main.SonicV2Connector')
    def test_clear_dampening_all(self, mock_sv2, mock_cfgdb):
        """Test clearing dampening on all interfaces"""
        mock_db_instance = MagicMock()
        mock_cfgdb.return_value = mock_db_instance
        mock_db_instance.get_table.return_value = {
            "Ethernet0": {
                "link_event_damping_algorithm": "aied",
            },
            "Ethernet4": {
                "link_event_damping_algorithm": "aied-monitor",
            },
            "Ethernet8": {
                "link_event_damping_algorithm": "disabled",
            }
        }

        mock_state = MagicMock()
        mock_sv2.return_value = mock_state

        runner = CliRunner()
        result = runner.invoke(
            clear.cli.commands["interfaces"].commands["dampening"],
            [])
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert "Cleared dampening on Ethernet0" in result.output
        assert "Cleared dampening on Ethernet4" in result.output
        assert "Ethernet8" not in result.output
        assert "2 interface(s)" in result.output

    @patch('clear.main.ConfigDBConnector')
    def test_clear_dampening_no_config(self, mock_cfgdb):
        """Test clearing when no dampening is configured"""
        mock_db_instance = MagicMock()
        mock_cfgdb.return_value = mock_db_instance
        mock_db_instance.get_table.return_value = {
            "Ethernet0": {
                "link_event_damping_algorithm": "disabled",
            }
        }

        runner = CliRunner()
        result = runner.invoke(
            clear.cli.commands["interfaces"].commands["dampening"],
            [])
        print(result.exit_code, result.output)
        assert result.exit_code == 0
        assert "No interfaces have dampening configured" in result.output

    @patch('clear.main.ConfigDBConnector')
    def test_clear_dampening_invalid_interface(self, mock_cfgdb):
        """Test clearing dampening on non-existent interface"""
        mock_db_instance = MagicMock()
        mock_cfgdb.return_value = mock_db_instance
        mock_db_instance.get_table.return_value = {
            "Ethernet0": {"link_event_damping_algorithm": "aied"}
        }

        runner = CliRunner()
        result = runner.invoke(
            clear.cli.commands["interfaces"].commands["dampening"],
            ["EthernetINVALID"])
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert "does not exist" in result.output

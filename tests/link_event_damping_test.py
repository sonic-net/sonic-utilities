import os
from click.testing import CliRunner

import config.main as config
from utilities_common.db import Db


class TestConfigInterfaceDamping(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"

    def test_set_algo_aied(self):
        """Test setting damping algorithm to AIED"""
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(
            config.config.commands["interface"].commands["damping"].commands["algo"],
            ["Ethernet0", "aied"],
            obj=obj
        )
        print(result.exit_code, result.output)
        assert result.exit_code == 0

    def test_set_algo_disabled(self):
        """Test disabling damping"""
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(
            config.config.commands["interface"].commands["damping"].commands["algo"],
            ["Ethernet0", "disabled"],
            obj=obj
        )
        print(result.exit_code, result.output)
        assert result.exit_code == 0

    def test_set_algo_invalid_interface(self):
        """Test invalid interface for algo"""
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(
            config.config.commands["interface"].commands["damping"].commands["algo"],
            ["EthernetINVALID", "aied"],
            obj=obj
        )
        print(result.exit_code, result.output)
        assert result.exit_code != 0

    def test_set_aied_params_valid(self):
        """Test setting valid AIED parameters"""
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(
            config.config.commands["interface"].commands["damping"].commands["aied-param"],
            [
                "Ethernet0",
                "--suppress-threshold", "1400",
                "--decay-half-life", "20000",
                "--max-suppress-time", "40000",
                "--flap-penalty", "1000",
                "--reuse-threshold", "1100"
            ],
            obj=obj
        )
        print(result.exit_code, result.output)
        assert result.exit_code == 0

    def test_set_aied_params_single_param(self):
        """Test setting only one parameter"""
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(
            config.config.commands["interface"].commands["damping"].commands["aied-param"],
            ["Ethernet0", "--decay-half-life", "20000"],
            obj=obj
        )
        print(result.exit_code, result.output)
        assert result.exit_code == 0

    def test_aied_params_no_args(self):
        """Test failure if no params provided"""
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(
            config.config.commands["interface"].commands["damping"].commands["aied-param"],
            ["Ethernet0"],
            obj=obj
        )
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert "Expected at least one valid AIED config parameter" in result.output

    def test_aied_negative_value(self):
        """Test invalid negative values"""
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(
            config.config.commands["interface"].commands["damping"].commands["aied-param"],
            ["Ethernet0", "--flap-penalty", "-1"],
            obj=obj
        )
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert "Invalid flap_penalty" in result.output


def test_aied_reuse_ge_suppress(self):
        """Test that reuse_threshold >= suppress_threshold is rejected"""
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(
            config.config.commands["interface"].commands["damping"].commands["aied-param"],
            [
                "Ethernet0",
                "--reuse-threshold", "3000",
                "--suppress-threshold", "2000"
            ],
            obj=obj
        )
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert "reuse_threshold" in result.output.lower() or "Reuse threshold" in result.output


    def test_aied_halflife_gt_maxsuppress(self):
        """Test that decay_half_life > max_suppress_time is rejected"""
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(
            config.config.commands["interface"].commands["damping"].commands["aied-param"],
            [
                "Ethernet0",
                "--decay-half-life", "30000",
                "--max-suppress-time", "20000"
            ],
            obj=obj
        )
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert "decay_half_life" in result.output.lower() or "Half-life" in result.output


    def test_aied_invalid_halflife(self):
        """Test invalid (negative) decay_half_life"""
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(
            config.config.commands["interface"].commands["damping"].commands["aied-param"],
            [
                "Ethernet0",
                "--decay-half-life", "-1"
            ],
            obj=obj
        )
        print(result.exit_code, result.output)
        assert result.exit_code != 0
        assert "Invalid decay_half_life" in result.output or "Invalid value" in result.output

    def test_aied_invalid_interface(self):
        """Test invalid interface for aied-param"""
        runner = CliRunner()
        db = Db()
        obj = {'config_db': db.cfgdb}

        result = runner.invoke(
            config.config.commands["interface"].commands["damping"].commands["aied-param"],
            ["EthernetINVALID", "--decay-half-life", "1000"],
            obj=obj
        )
        print(result.exit_code, result.output)
        assert result.exit_code != 0

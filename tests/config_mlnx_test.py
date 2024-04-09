import sys
import click
import pytest
import config.plugins.mlnx as config
from unittest.mock import patch, Mock
from click.testing import CliRunner
from utilities_common.db import Db


@patch('config.plugins.mlnx.sniffer_env_variable_set', Mock(return_value=False))
@patch('config.plugins.mlnx.sniffer_filename_generate', Mock(return_value="sdk_file_name"))
class TestConfigMlnx(object):
    def setup(self):
        print('SETUP')


    @patch('config.plugins.mlnx.restart_swss', Mock(return_value=0))
    def test_config_sniffer_enable(self):
        db = Db()
        runner = CliRunner()
        result = runner.invoke(config.mlnx.commands["sniffer"].commands["sdk"].commands["enable"],["-y"])
        assert "SDK sniffer is Enabled, recording file is sdk_file_name." in result.output

    @patch('config.plugins.mlnx.restart_swss', Mock(return_value=0))
    def test_config_sniffer_disble(self):
        db = Db()
        runner = CliRunner()
        result = runner.invoke(config.mlnx.commands["sniffer"].commands["sdk"].commands["disable"],["-y"])
        assert "SDK sniffer is Disabled." in result.output

    @patch('config.plugins.mlnx.restart_swss', Mock(return_value=1))
    def test_config_sniffer_enable_fail(self):
        db = Db()
        runner = CliRunner()
        result = runner.invoke(config.mlnx.commands["sniffer"].commands["sdk"].commands["enable"],["-y"])
        assert "SDK sniffer is Enabled, recording file is sdk_file_name." not in result.output

    @patch('config.plugins.mlnx.restart_swss', Mock(return_value=1))
    def test_config_sniffer_disble_fail(self):
        db = Db()
        runner = CliRunner()
        result = runner.invoke(config.mlnx.commands["sniffer"].commands["sdk"].commands["disable"],["-y"])
        assert "SDK sniffer is Disabled." not in result.output

    def teardown(self):
        print('TEARDOWN')


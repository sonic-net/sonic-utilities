import os
import logging
import pytest

import show.plugins as show_plugins
import show.main as show_main
import config.plugins as config_plugins
import config.main as config_main
from .cli_autogen_input.autogen_test import show_cmd_output
from .cli_autogen_input.cli_autogen_common import backup_yang_models, restore_backup_yang_models, move_yang_models, remove_yang_models

from utilities_common import util_base
from sonic_cli_gen.generator import CliGenerator
from .mock_tables import dbconnector
from utilities_common.db import Db
from click.testing import CliRunner

logger = logging.getLogger(__name__)
gen = CliGenerator(logger)

test_path = os.path.dirname(os.path.abspath(__file__))
mock_db_path = os.path.join(test_path, 'cli_autogen_input', 'config_db')
config_db_path = os.path.join(test_path, 'cli_autogen_input', 'config_db.json')
templates_path = os.path.join(test_path, '../', 'sonic-utilities-data', 'templates', 'sonic-cli-gen')

SUCCESS = 0
ERROR = 1
INVALID_VALUE = 'INVALID'

test_yang_models = [
    'sonic-device_metadata.yang',
    'sonic-device_neighbor.yang',
]


class TestCliAutogen:
    @classmethod
    def setup_class(cls):
        logger.info('SETUP')
        os.environ['UTILITIES_UNIT_TESTING'] = '2'

        backup_yang_models()
        move_yang_models(test_path, 'autogen_test', test_yang_models)

        for yang_model in test_yang_models:
            gen.generate_cli_plugin(
                cli_group='show',
                plugin_name=yang_model.split('.')[0],
                config_db_path=config_db_path,
                templates_path=templates_path
            )
            gen.generate_cli_plugin(
                cli_group='config',
                plugin_name=yang_model.split('.')[0],
                config_db_path=config_db_path,
                templates_path=templates_path
            )

        helper = util_base.UtilHelper()
        helper.load_and_register_plugins(show_plugins, show_main.cli)
        helper.load_and_register_plugins(config_plugins, config_main.config)


    @classmethod
    def teardown_class(cls):
        logger.info('TEARDOWN')

        for yang_model in test_yang_models:
            gen.remove_cli_plugin('show', yang_model.split('.')[0])
            gen.remove_cli_plugin('config', yang_model.split('.')[0])

        restore_backup_yang_models()

        dbconnector.dedicated_dbs['CONFIG_DB'] = None

        os.environ['UTILITIES_UNIT_TESTING'] = '0'


    def test_show_device_metadata(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = mock_db_path
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show_main.cli.commands['device-metadata'].commands['localhost'], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        assert result.output == show_cmd_output.show_device_metadata_localhost


    def test_config_device_metadata(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = mock_db_path
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config_main.config.commands['device-metadata'].commands['localhost'].commands['buffer-model'], ['dynamic'], obj=db
        )

        result = runner.invoke(
            show_main.cli.commands['device-metadata'].commands['localhost'], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        assert result.output == show_cmd_output.show_device_metadata_localhost_changed_buffer_model

    def test_config_device_metadata_non_existing_field(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = mock_db_path
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config_main.config.commands['device-metadata'].commands['localhost'].commands['non-existing-field'], ['12'], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS

    @pytest.mark.parametrize("parameter,value", [
        ('default-bgp-status', INVALID_VALUE),
        ('docker-routing-config-mode', INVALID_VALUE),
        ('mac', INVALID_VALUE),
        ('default-pfcwd-status', INVALID_VALUE),
        ('bgp-asn', INVALID_VALUE),
        ('type', INVALID_VALUE),
        ('buffer-model', INVALID_VALUE),
        ('frr-mgmt-framework-config', INVALID_VALUE)
    ])
    def test_config_device_metadata_invalid(self, parameter, value):
        dbconnector.dedicated_dbs['CONFIG_DB'] = mock_db_path
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config_main.config.commands['device-metadata'].commands['localhost'].commands[parameter], [value], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR


    def test_show_device_neighbor(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = mock_db_path
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show_main.cli.commands['device-neighbor'], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert show_cmd_output.show_device_neighbor
        assert result.exit_code == SUCCESS


    def test_config_device_neighbor_add(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = mock_db_path
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config_main.config.commands['device-neighbor'].commands['add'],
                ['Ethernet8', '--name', 'Servers1', '--mgmt-addr', '10.217.0.3',
                 '--local-port', 'Ethernet8', '--port', 'eth2', '--type', 'type'],
                obj=db
        )
        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        result = runner.invoke(
            show_main.cli.commands['device-neighbor'], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        assert result.output == show_cmd_output.show_device_neighbor_added


    def test_config_device_neighbor_delete(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = mock_db_path
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config_main.config.commands['device-neighbor'].commands['delete'],
                ['Ethernet0'], obj=db
        )
        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        result = runner.invoke(
            show_main.cli.commands['device-neighbor'], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        assert result.output == show_cmd_output.show_device_neighbor_deleted


    @pytest.mark.parametrize("parameter,value,output", [
        ('--mgmt-addr', '10.217.0.5', show_cmd_output.show_device_neighbor_updated_mgmt_addr),
        ('--name', 'Servers1', show_cmd_output.show_device_neighbor_updated_name),
        ('--local-port', 'Ethernet12', show_cmd_output.show_device_neighbor_updated_local_port),
        ('--port', 'eth2', show_cmd_output.show_device_neighbor_updated_port),
        ('--type', 'type2', show_cmd_output.show_device_neighbor_updated_type),
    ])
    def test_config_device_neighbor_update(self, parameter, value, output):
        dbconnector.dedicated_dbs['CONFIG_DB'] = mock_db_path
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config_main.config.commands['device-neighbor'].commands['update'],
                ['Ethernet0', parameter, value], obj=db
        )
        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        result = runner.invoke(
            show_main.cli.commands['device-neighbor'], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == SUCCESS
        assert result.output == output


    @pytest.mark.parametrize("parameter,value", [
        ('--mgmt-addr', INVALID_VALUE),
        ('--local-port', INVALID_VALUE)
    ])
    def test_config_device_neighbor_update_invalid(self, parameter, value):
        dbconnector.dedicated_dbs['CONFIG_DB'] = mock_db_path
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config_main.config.commands['device-neighbor'].commands['update'],
                ['Ethernet0', parameter, value], obj=db
        )
        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)
        assert result.exit_code == ERROR


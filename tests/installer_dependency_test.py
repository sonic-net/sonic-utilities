import pytest
import sonic_installer.main as sonic_installer
import utilities_common.cli as clicommon

from click.testing import CliRunner
from unittest import mock

# mock load_db_config to throw exception
class MockSonicDBConfig:
    def load_sonic_db_config():
        raise RuntimeError("sonic installer 'list' command should not depends on database")

    def load_sonic_global_db_config():
        raise RuntimeError("sonic installer 'list' command should not depends on database")

    def isInit():
        return False

    def isGlobalInit():
        return False

@mock.patch("swsscommon.swsscommon.SonicDBConfig", MockSonicDBConfig)
def test_sonic_installer_not_depends_on_database_container():
    runner = CliRunner()
    result = runner.invoke(
            sonic_installer.sonic_installer.commands['list']
        )
    assert result.exit_code == 1

    # check InterfaceAliasConverter will break by the mock method, sonic installer use it to load db config.
    exception_happen = False
    try:
        clicommon.InterfaceAliasConverter()
    except RuntimeError:
        exception_happen = True

    assert exception_happen == True

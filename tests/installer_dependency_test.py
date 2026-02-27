import pytest
import click
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


# --- AliasedGroup bash completion context tests ---

@click.group(cls=clicommon.AliasedGroup)
def sample_cli():
    """Sample CLI for testing AliasedGroup completion"""
    pass


@sample_cli.command()
def remotemac():
    """show vxlan remotemac"""
    click.echo("remotemac")


@sample_cli.command()
def remotevni():
    """show vxlan remotevni"""
    click.echo("remotevni")


def test_ambiguous_command_returns_none_with_resilient_parsing():
    """In completion mode (resilient_parsing=True), ambiguous commands return None"""
    ctx = click.Context(sample_cli, resilient_parsing=True)
    # 'remote' matches both 'remotemac' and 'remotevni'
    result = sample_cli.get_command(ctx, 'remote')
    assert result is None


def test_ambiguous_command_raises_usageerror_without_resilient_parsing():
    """Without completion context, ambiguous commands should raise UsageError"""
    ctx = click.Context(sample_cli, resilient_parsing=False)
    with pytest.raises(click.UsageError):
        sample_cli.get_command(ctx, 'remote')

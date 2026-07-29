import click
import pytest

from utilities_common.cli import AbbreviationGroup


@click.group(cls=AbbreviationGroup)
def cli():
    pass


@cli.command(name="switch-hash")
def switch_hash():
    pass


@cli.command(name="switchport")
def switchport():
    pass


class TestAbbreviationGroup:
    def test_ambiguous_prefix_returns_none_during_completion(self):
        # During shell completion Click sets ctx.resilient_parsing and does not
        # catch exceptions from get_command, so an ambiguous prefix must return
        # None instead of raising (which would dump a traceback to the terminal).
        ctx = click.Context(cli, resilient_parsing=True)
        assert cli.get_command(ctx, "switch") is None

    def test_ambiguous_prefix_fails_on_invocation(self):
        # On a real invocation the ambiguous prefix must still fail with the
        # "Too many matches" usage error.
        ctx = click.Context(cli)
        with pytest.raises(click.exceptions.UsageError) as exc_info:
            cli.get_command(ctx, "switch")
        assert "Too many matches" in str(exc_info.value)

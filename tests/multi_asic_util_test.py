import click
import mock

from click.testing import CliRunner

import utilities_common.multi_asic as multi_asic_util


def _make_cmd():
    """Build a throwaway command wired to the namespace validation callback."""
    @click.command()
    @click.option('-n', '--namespace', 'namespace', default=None,
                  callback=multi_asic_util.multi_asic_namespace_validation_callback)
    def cmd(namespace):
        click.echo("ran namespace={}".format(namespace))
    return cmd


class TestMultiAsicNamespaceValidationCallback:
    @mock.patch("utilities_common.multi_asic.multi_asic.is_multi_asic",
                mock.Mock(return_value=False))
    def test_single_asic_without_namespace_is_allowed(self):
        # Click runs the callback even when -n is not supplied; the command
        # must still run on single-asic instead of aborting.
        result = CliRunner().invoke(_make_cmd(), [])
        assert result.exit_code == 0
        assert "ran namespace=None" in result.output

    @mock.patch("utilities_common.multi_asic.multi_asic.is_multi_asic",
                mock.Mock(return_value=False))
    def test_single_asic_with_namespace_is_rejected(self):
        result = CliRunner().invoke(_make_cmd(), ["-n", "asic0"])
        assert result.exit_code != 0
        assert "not available for single asic" in result.output

    @mock.patch("utilities_common.multi_asic.multi_asic.is_multi_asic",
                mock.Mock(return_value=True))
    def test_multi_asic_with_namespace_is_allowed(self):
        result = CliRunner().invoke(_make_cmd(), ["-n", "asic0"])
        assert result.exit_code == 0
        assert "ran namespace=asic0" in result.output

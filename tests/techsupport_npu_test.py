import pytest
import sys
import show.main
from unittest.mock import patch
import click
from click.testing import CliRunner
import importlib
from typing import Callable, TypeVar


T = TypeVar("T")

platform_clis = []
vendor_clis = {}


def register(func: Callable[..., T]) -> Callable[..., T]:
    platform_clis.append(func)
    vendor_clis['techsupport'] = [func]
    return func


@register
@click.command('npu')
def npu():
    click.echo('techsupport npu output')


def test_techsupport_npu():
    with patch("sonic_py_common.device_info.get_sonic_version_info",
            return_value={'asic_type': 'cisco-8000'}):
        cisco_8000 = importlib.import_module('show.plugins.cisco-8000')
        cisco_8000.PLATFORM_CLIS = platform_clis
        cisco_8000.VENDOR_CLIS = vendor_clis
        assert 'techsupport' in cisco_8000.VENDOR_CLIS
        cisco_8000.register(show.main.cli)

        expected_output = 'techsupport npu output'
        runner = click.testing.CliRunner()
        result = runner.invoke(show.main.cli.commands['techsupport'].commands['npu'], [])
        assert result.exit_code == 0
        assert result.output.strip() == expected_output

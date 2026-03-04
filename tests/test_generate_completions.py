"""Tests for sonic-utilities-data/generate_completions.py (Click 8 bash completion)."""
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

# Add sonic-utilities-data to path so we can import generate_completions
test_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(os.path.dirname(test_dir), "sonic-utilities-data")
if data_dir not in sys.path:
    sys.path.insert(0, data_dir)

import generate_completions as gc  # noqa: E402


def _mock_entry_point(name="show", value="show.main:cli"):
    ep = MagicMock()
    ep.name = name
    ep.value = value
    return ep


@patch("generate_completions.import_module")
@patch("generate_completions.importlib.metadata.distribution")
def test_generate_completions_produces_both_show_and_config(mock_dist, mock_import):
    """Generator produces correct scripts for show and config: bash_complete, stderr redirect, type,value parsing."""
    from click import Group
    mock_dist.return_value.entry_points = [
        _mock_entry_point("show", "show.main:cli"),
        _mock_entry_point("config", "config.main:cli"),
    ]

    def get_cmd(name):
        return Group(name)

    mock_import.return_value.get.side_effect = get_cmd

    with tempfile.TemporaryDirectory() as out_dir:
        gc.generate_completions(out_dir)
        for prog, var, func in [
            ("show", "_SHOW_COMPLETE", "_show_completion"),
            ("config", "_CONFIG_COMPLETE", "_config_completion"),
        ]:
            path = os.path.join(out_dir, prog)
            assert os.path.isfile(path), "Should generate %s" % prog
            content = open(path).read()
            assert var in content and func in content
            assert "complete -F %s" % func in content and "default %s" % prog in content
            assert "bash_complete" in content
            assert "2>/dev/null" in content
            assert '[[ "$line" == *,* ]]' in content and '${line##*,}' in content


def test_click8_completion_output_format_via_mock():
    """
    Simulate autocompletion: use Click's bash_complete with a minimal CLI
    and assert output is type,value per line so our generated script's parsing works.
    """
    import click
    from click.shell_completion import get_completion_class

    @click.group()
    def cli():
        pass

    @cli.command()
    def platform():
        pass

    @cli.command()
    def bgp():
        pass

    comp_cls = get_completion_class("bash")
    shell_comp = comp_cls(cli, {}, "show", "_SHOW_COMPLETE")

    env = {
        "COMP_WORDS": "show b",
        "COMP_CWORD": "1",
    }
    with patch.dict(os.environ, env, clear=False):
        output = shell_comp.complete()

    assert output, "Completion should return something for 'show b'"
    lines = [ln.strip() for ln in output.strip().split("\n") if ln.strip()]
    assert lines, "At least one completion line"
    for line in lines:
        assert "," in line, "Click 8 format is type,value per line; got %r" % line
        typ, value = line.split(",", 1)
        assert typ == "plain" or typ, "Expected type (e.g. plain)"
        assert value.startswith("b"), "Completions for 'b' should start with b (e.g. bgp)"
    values = [ln.split(",", 1)[1] for ln in lines]
    assert "bgp" in values, "Subcommand 'bgp' should be in completions"

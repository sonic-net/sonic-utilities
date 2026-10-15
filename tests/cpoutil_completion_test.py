"""Check the packaged Click entry point and hardware-free Bash completion."""
import ast
import importlib.metadata
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
from click.testing import CliRunner

from cpoutil import main as cpoutil


def test_packaged_entry_point_generates_bash_completion(monkeypatch, tmp_path):
    repo = Path(cpoutil.__file__).resolve().parents[1]
    setup = ast.parse((repo / "setup.py").read_text(encoding="utf-8"))
    setup_call = next(
        node for node in ast.walk(setup)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "setup"
    )
    entry_points = ast.literal_eval(next(
        keyword.value for keyword in setup_call.keywords
        if keyword.arg == "entry_points"
    ))
    entry = next(
        value for value in entry_points["console_scripts"]
        if value.split("=", 1)[0].strip() == "cpoutil"
    )
    name, target = (part.strip() for part in entry.split("=", 1))
    distribution = SimpleNamespace(entry_points=[
        importlib.metadata.EntryPoint(name=name, value=target, group="console_scripts"),
    ])
    monkeypatch.setattr(importlib.metadata, "distribution", lambda name: distribution)
    initialize = mock.Mock(side_effect=AssertionError("completion accessed hardware"))
    monkeypatch.setattr(cpoutil, "initialize_platform", initialize)
    spec = importlib.util.spec_from_file_location(
        "cpoutil_completion_generator", repo / "sonic-utilities-data" / "generate_completions.py"
    )
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)

    generator.generate_completions(str(tmp_path))

    source = (tmp_path / "cpoutil").read_text(encoding="utf-8")
    assert "_CPOUTIL_COMPLETE=bash_complete" in source
    assert "_cpoutil_completion" in source
    assert "complete -o nosort -F _cpoutil_completion cpoutil" in source
    initialize.assert_not_called()


@pytest.mark.parametrize("words,index,expected", [
    ("cpoutil sh", 1, "plain,show"),
    ("cpoutil show ", 2, "plain,interface"),
    ("cpoutil show oe t", 3, "plain,temperature"),
    ("cpoutil show oe temperature --j", 4, "plain,--json"),
    ("cpoutil config interface lpmode Ethernet0 l", 5, "plain,low"),
    ("cpoutil config interface tx-disable Ethernet0 t", 5, "plain,true"),
])
def test_bash_completion_does_not_initialize_platform(monkeypatch, words, index, expected):
    initialize = mock.Mock(side_effect=AssertionError("completion accessed hardware"))
    monkeypatch.setattr(cpoutil, "initialize_platform", initialize)

    result = CliRunner().invoke(cpoutil.cli, [], prog_name="cpoutil", env={
        "_CPOUTIL_COMPLETE": "bash_complete",
        "COMP_WORDS": words,
        "COMP_CWORD": str(index),
    })

    assert result.exit_code == 0, result.output
    assert expected in result.output.splitlines()
    initialize.assert_not_called()

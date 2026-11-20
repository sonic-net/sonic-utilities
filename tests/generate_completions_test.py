"""Tests for the build-time bash completion generator (sonic-utilities-data)."""

import importlib.util
import os
import tempfile
import types
import unittest
from unittest import mock

import click
from importlib.metadata import EntryPoint

GENERATE_COMPLETIONS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "sonic-utilities-data", "generate_completions.py"
)


def _load_generate_completions():
    spec = importlib.util.spec_from_file_location("generate_completions", GENERATE_COMPLETIONS_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@click.group()
def cli():
    """Fake CLI group used to exercise completion generation."""


@cli.command()
def counters():
    """Clear counters."""


class TestGenerateCompletions(unittest.TestCase):
    """The generated scripts must trigger the env var names Click looks up at runtime."""

    def _generate(self, prog_names):
        """
        Run the generator for fake entry points named prog_names and return
        {prog: generated completion script content}.
        """
        generate_completions = _load_generate_completions()
        fake_module = types.ModuleType("fake_module")
        fake_module.cli = cli
        entry_points = [
            EntryPoint(name=prog, value="fake_module:cli", group="console_scripts")
            for prog in prog_names
        ]
        with tempfile.TemporaryDirectory() as output_dir:
            with mock.patch("importlib.metadata.distribution") as distribution:
                distribution.return_value.entry_points = entry_points
                with mock.patch.object(
                    generate_completions, "import_module", return_value=fake_module
                ):
                    generate_completions.generate_completions(output_dir)
            return {
                prog: open(os.path.join(output_dir, prog)).read()
                for prog in os.listdir(output_dir)
            }

    def test_hyphenated_prog_name_uses_underscores_in_complete_var(self):
        # Click 8 replaces '-' (and '.') with '_' before upper-casing when it
        # derives the completion env var at runtime (click/core.py,
        # BaseCommand._main_shell_completion). The generator must derive the
        # same name, otherwise the installed script never triggers completion.
        content = self._generate(["sonic-clear"])["sonic-clear"]
        self.assertIn("_SONIC_CLEAR_COMPLETE", content)
        self.assertNotIn("_SONIC-CLEAR_COMPLETE", content)

    def test_plain_prog_name_complete_var_is_unchanged(self):
        # Names without separators must keep deriving exactly as before.
        content = self._generate(["show"])["show"]
        self.assertIn("_SHOW_COMPLETE", content)

    def test_dotted_prog_name_uses_underscores_in_complete_var(self):
        # Click also replaces '.' with '_' when deriving the var at runtime.
        content = self._generate(["sonic.cli"])["sonic.cli"]
        self.assertIn("_SONIC_CLI_COMPLETE", content)
        self.assertNotIn("_SONIC.CLI_COMPLETE", content)

import json
import unittest
from pathlib import Path
from unittest.mock import Mock

import click
from click.testing import CliRunner

from sonic_installer.patch_cli import register_patch_commands
from sonic_installer.patch_manager import PatchError


class PatchCliTest(unittest.TestCase):
    def setUp(self):
        self.manager = Mock()
        self.group = click.Group()

        def abort_if_false(ctx, param, value):
            if not value:
                ctx.abort()
            return value

        register_patch_commands(
            self.group,
            abort_if_false=abort_if_false,
            manager_factory=lambda: self.manager,
        )
        self.runner = CliRunner()

    def test_patch_install_calls_manager(self):
        self.manager.install.return_value = ["sub-Hotfix1.tar.gz"]
        with self.runner.isolated_filesystem():
            Path("Hotfix1.tar.gz").write_bytes(b"archive")
            result = self.runner.invoke(
                self.group,
                ["patch-install", "-y", "Hotfix1.tar.gz"],
            )
        self.assertEqual(result.exit_code, 0, result.output)
        self.manager.install.assert_called_once()
        self.assertIn("sub-Hotfix1.tar.gz", result.output)

    def test_hotpatch_install_single_calls_reapply(self):
        with self.runner.isolated_filesystem():
            Path("sub-Hotfix1.tar.gz").write_bytes(b"archive")
            result = self.runner.invoke(
                self.group,
                ["hotpatch-install-single", "sub-Hotfix1.tar.gz", "-y"],
            )
        self.assertEqual(result.exit_code, 0, result.output)
        self.manager.reapply_hotpatch.assert_called_once()

    def test_patch_list_json(self):
        self.manager.list_patches.return_value = [
            {"name": "sub-Hotfix1.tar.gz"}]
        result = self.runner.invoke(self.group, ["patch-list", "--json"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.output), [
                         {"name": "sub-Hotfix1.tar.gz"}])

    def test_patch_status_section(self):
        self.manager.status.return_value = {"live": [{"active": True}]}
        result = self.runner.invoke(
            self.group, ["patch-status", "--section", "live"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.manager.status.assert_called_once_with("live")
        self.assertEqual(json.loads(result.output), {
                         "live": [{"active": True}]})

    def test_patch_error_returns_nonzero(self):
        self.manager.install.side_effect = PatchError("invalid Hotfix")
        with self.runner.isolated_filesystem():
            Path("Hotfix1.tar.gz").write_bytes(b"archive")
            result = self.runner.invoke(
                self.group,
                ["patch-install", "-y", "Hotfix1.tar.gz"],
            )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("invalid Hotfix", result.output)


if __name__ == "__main__":
    unittest.main()

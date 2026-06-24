#!/usr/bin/env python3

import argparse
import contextlib
import pathlib
import re
import tempfile
import unittest
from unittest import mock

from sonic_sdboot_utils import boot_control_main
from sonic_sdboot_utils import sdboot_config

_DEV_NULL = pathlib.Path("/dev/null")


class BootAssessmentTest(unittest.TestCase):

    @contextlib.contextmanager
    def tempdir(self):
        try:
            tempdir = tempfile.TemporaryDirectory()
            yield pathlib.Path(tempdir.name)
        finally:
            tempdir.cleanup()

    def make_sdboot_conf(self, sort_key) -> sdboot_config.SdbootConfig:
        """Create a dummy sd-boot config with the given sort key."""
        return sdboot_config.SdbootConfig(
                title="dummy",
                version="DummyVersion",
                sort_key=sort_key,
                linux=pathlib.Path("dev/null"),
                initrd=pathlib.Path("dev/null"),
                options=["rw"],
                image_dir=pathlib.Path("dummy"),
        )

    @mock.patch("sonic_sdboot_utils.sdboot_config.get_cur_boot")
    @mock.patch("sonic_sdboot_utils.sdboot_config.reset_bootcount")
    def test_main_reset_bootcount_happy_path_one_blessed_config(
            self,
            rb: mock.MagicMock,
            gcb: mock.MagicMock,
    ):
        gcb.side_effect = [sdboot_config.SdbootEntry("sonic_a", None)]
        with self.tempdir() as td:
            self.make_sdboot_conf((1 << 64) - 1).write_file(td / "sonic_a.conf")
            boot_control_main.main(
                    argparse.Namespace(
                            action="reset-bootcount",
                            include_bootcount_in_oneshot=True,
                            efivars_path=_DEV_NULL,
                            boot_loader_entries_dir=td,
                            dry_run=False,
                    )
            )
            rb.assert_called_once_with(td / "sonic_a.conf", dry_run=False)

    @mock.patch("sonic_sdboot_utils.sdboot_config.get_cur_boot")
    @mock.patch("sonic_sdboot_utils.sdboot_config.reset_bootcount")
    def test_main_reset_bootcount_happy_path_one_counted_config(
            self,
            rb: mock.MagicMock,
            gcb: mock.MagicMock,
    ):
        # Get current boot should return 'sonic_a'; there will only exist a
        # bootcounted version. It should be reset.
        gcb.side_effect = [sdboot_config.SdbootEntry("sonic_a", None)]
        with self.tempdir() as td:
            self.make_sdboot_conf((1 << 64) - 1).write_file(td / "sonic_a+0-1.conf")
            boot_control_main.main(
                    argparse.Namespace(
                            include_bootcount_in_oneshot=True,
                            efivars_path=_DEV_NULL,
                            action="reset-bootcount",
                            boot_loader_entries_dir=td,
                            dry_run=False,
                    )
            )
            rb.assert_called_once_with(td / "sonic_a+0-1.conf", dry_run=False)

    @mock.patch("sonic_sdboot_utils.sdboot_config.get_cur_boot")
    @mock.patch("sonic_sdboot_utils.sdboot_config.reset_bootcount")
    def test_main_reset_bootcount_one_missing_config(
            self,
            rb: mock.MagicMock,
            gcb: mock.MagicMock,
    ):
        # Get current boot should return 'sonic_b'; there will only exist a sonic_a.
        # it should crash.
        gcb.side_effect = [sdboot_config.SdbootEntry("sonic_b", None)]
        with self.tempdir() as td:
            self.make_sdboot_conf((1 << 64) - 1).write_file(td / "sonic_a+0-1.conf")
            with self.assertRaisesRegex(
                    SystemExit, re.escape("Found no matching confs for sonic_b.conf")
            ):
                boot_control_main.main(
                        argparse.Namespace(
                                include_bootcount_in_oneshot=True,
                                efivars_path=_DEV_NULL,
                                action="reset-bootcount",
                                boot_loader_entries_dir=td,
                                dry_run=False,
                        )
                )
            rb.assert_not_called()

    @mock.patch("sonic_sdboot_utils.sdboot_config.get_cur_boot")
    @mock.patch("sonic_sdboot_utils.sdboot_config.reset_bootcount")
    def test_main_reset_bootcount_two_matching_configs(
            self,
            rb: mock.MagicMock,
            gcb: mock.MagicMock,
    ):
        # Get current boot should return 'sonic_a'; there should only exist a
        # bootcounted version. It should be reset.
        gcb.side_effect = [sdboot_config.SdbootEntry("sonic_a", None)]
        with self.tempdir() as td:
            self.make_sdboot_conf((1 << 64) - 1).write_file(td / "sonic_a.conf")
            self.make_sdboot_conf((1 << 64) - 1).write_file(td / "sonic_a+0-1.conf")
            with self.assertRaisesRegex(
                    SystemExit,
                    re.escape(
                            "Found 2 matching confs for sonic_a: sonic_a.conf,"
                            " sonic_a+0-1.conf"
                    ),
            ):
                boot_control_main.main(
                        argparse.Namespace(
                                include_bootcount_in_oneshot=True,
                                efivars_path=_DEV_NULL,
                                action="reset-bootcount",
                                boot_loader_entries_dir=td,
                                dry_run=False,
                        )
                )
            rb.assert_not_called()

    @mock.patch("sonic_sdboot_utils.boot_control_main.set_next_boot")
    def test_main_set_next_boot_happy_path_blessed(self, snb):
        with self.tempdir() as td:
            self.make_sdboot_conf((1 << 64) - 1).write_file(td / "sonic_a.conf")
            boot_control_main.main(
                    argparse.Namespace(
                            action="set-next-boot",
                            additional_arg="sonic_a",
                            boot_loader_entries_dir=td,
                            include_bootcount_in_oneshot=True,
                            next_boot_flagfile_path=_DEV_NULL,
                    )
            )
            snb.assert_called_once_with(
                    sdboot_config.SdbootEntry("sonic_a", None),
                    True,
                    _DEV_NULL,
            )

    @mock.patch("sonic_sdboot_utils.boot_control_main.set_next_boot")
    def test_main_set_next_boot_happy_path_bootcounted(self, snb):
        with self.tempdir() as td:
            self.make_sdboot_conf((1 << 64) - 1).write_file(td / "sonic_a+1-0.conf")
            boot_control_main.main(
                    argparse.Namespace(
                            action="set-next-boot",
                            additional_arg="sonic_a",
                            boot_loader_entries_dir=td,
                            include_bootcount_in_oneshot=True,
                            next_boot_flagfile_path=_DEV_NULL,
                    )
            )
            snb.assert_called_once_with(
                    sdboot_config.SdbootEntry("sonic_a", (1, 0)),
                    True,
                    _DEV_NULL,
            )

    @mock.patch("sonic_sdboot_utils.boot_control_main.set_next_boot")
    def test_main_set_next_boot_missing_conf(self, snb):
        with self.tempdir() as td:
            with self.assertRaisesRegex(
                    SystemExit, re.compile("Found no matching confs for sonic_a.conf")
            ):
                boot_control_main.main(
                        argparse.Namespace(
                                action="set-next-boot",
                                additional_arg="sonic_a",
                                boot_loader_entries_dir=td,
                                include_bootcount_in_oneshot=True,
                                next_boot_flagfile_path=_DEV_NULL,
                        )
                )
            snb.assert_not_called()

    @mock.patch("sonic_sdboot_utils.boot_control_main.set_next_boot")
    def test_main_set_next_boot_multiple_confs(self, snb):
        with self.tempdir() as td:
            self.make_sdboot_conf((1 << 64) - 1).write_file(td / "sonic_a.conf")
            self.make_sdboot_conf((1 << 64) - 1).write_file(td / "sonic_a+1-0.conf")
            with self.assertRaisesRegex(
                    SystemExit,
                    re.escape(
                            "Found 2 matching confs for sonic_a: sonic_a.conf,"
                            " sonic_a+1-0.conf"
                    ),
            ):
                boot_control_main.main(
                        argparse.Namespace(
                                action="set-next-boot",
                                additional_arg="sonic_a",
                                boot_loader_entries_dir=td,
                                include_bootcount_in_oneshot=True,
                                next_boot_flagfile_path=_DEV_NULL,
                        )
                )
            snb.assert_not_called()

    def test_set_get_next_boot_happy_path_blessed_include(self):
        with self.tempdir() as td:
            boot_control_main.set_next_boot(
                    sdboot_config.SdbootEntry("sonic_a", None), True, td / "flagfile"
            )
            with open(td / "flagfile", "r") as f:
                self.assertEqual(f.read(), "sonic_a.conf")
            self.assertEqual(
                    boot_control_main.get_next_boot(td / "flagfile"),
                    sdboot_config.SdbootEntry("sonic_a", None),
            )

    def test_set_get_next_boot_happy_path_counted_include(self):
        with self.tempdir() as td:
            boot_control_main.set_next_boot(
                    sdboot_config.SdbootEntry("sonic_a", (1, 0)), True, td / "flagfile"
            )
            with open(td / "flagfile", "r") as f:
                self.assertEqual(f.read(), "sonic_a+1-0.conf")
            self.assertEqual(
                    boot_control_main.get_next_boot(td / "flagfile"),
                    sdboot_config.SdbootEntry("sonic_a", (1, 0)),
            )

    def test_set_get_next_boot_happy_path_blessed_noinclude(self):
        with self.tempdir() as td:
            boot_control_main.set_next_boot(
                    sdboot_config.SdbootEntry("sonic_a", None), False, td / "flagfile"
            )
            with open(td / "flagfile", "r") as f:
                self.assertEqual(f.read(), "sonic_a.conf")
            self.assertEqual(
                    boot_control_main.get_next_boot(td / "flagfile"),
                    sdboot_config.SdbootEntry("sonic_a", None),
            )

    def test_set_get_next_boot_happy_path_counted_noinclude(self):
        with self.tempdir() as td:
            boot_control_main.set_next_boot(
                    sdboot_config.SdbootEntry("sonic_a", (1, 0)), False, td / "flagfile"
            )
            with open(td / "flagfile", "r") as f:
                self.assertEqual(f.read(), "sonic_a.conf")
            self.assertEqual(
                    boot_control_main.get_next_boot(td / "flagfile"),
                    sdboot_config.SdbootEntry("sonic_a", None),
            )

    def test_set_get_next_boot_noflagfile(self):
        with self.tempdir() as td:
            self.assertIsNone(boot_control_main.get_next_boot(td / "flagfile"))

    def test_set_get_next_boot_remove(self):
        with self.tempdir() as td:
            # make the flagfile exist...
            with open(td / "flagfile", "w"):
                pass

            boot_control_main.set_next_boot(None, True, td / "flagfile")

            # Assert that the flagfile got deleted.
            self.assertFalse((td / "flagfile").exists())

    def test_find_default_sonic_one_entry_blessed(self):
        with self.tempdir() as td:
            self.make_sdboot_conf((1 << 64) - 1).write_file(td / "sonic_a.conf")
            self.assertEqual(
                    boot_control_main.find_default_sonic(td),
                    sdboot_config.SdbootEntry("sonic_a", None),
            )

    def test_find_default_sonic_ignores_non_sonic(self):
        with self.tempdir() as td:
            self.make_sdboot_conf(0).write_file(td / "sonie.conf")
            self.make_sdboot_conf(1).write_file(td / "garbage.conf")
            self.make_sdboot_conf((1 << 64) - 1).write_file(td / "sonic_a.conf")
            self.assertEqual(
                    boot_control_main.find_default_sonic(td),
                    sdboot_config.SdbootEntry("sonic_a", None),
            )

    def test_find_default_sonic_picks_lowest_sonic(self):
        with self.tempdir() as td:
            self.make_sdboot_conf((1 << 64) - 1).write_file(td / "sonic_a.conf")
            self.make_sdboot_conf((1 << 64) - 2).write_file(td / "sonic_b.conf")
            self.assertEqual(
                    boot_control_main.find_default_sonic(td),
                    sdboot_config.SdbootEntry("sonic_b", None),
            )

    def test_find_default_sonic_one_entry_boot_counted(self):
        with self.tempdir() as td:
            self.make_sdboot_conf((1 << 64) - 1).write_file(td / "sonic_a+1-0.conf")
            self.assertEqual(
                    boot_control_main.find_default_sonic(td),
                    sdboot_config.SdbootEntry("sonic_a", (1, 0)),
            )

    @mock.patch("sonic_sdboot_utils.boot_control_main.get_next_boot")
    @mock.patch("sonic_sdboot_utils.boot_control_main.find_default_sonic")
    @mock.patch("sonic_sdboot_utils.sdboot_config.set_oneshot")
    def test_main_prepare_reboot_happy_path_next_boot_set(self, so, fds, gnb):
        with self.tempdir() as td:
            gnb.side_effect = [sdboot_config.SdbootEntry("sonic_b", (1, 0))]
            boot_control_main.main(
                    argparse.Namespace(
                            action="prepare-reboot",
                            next_boot_flagfile_path=_DEV_NULL,
                            boot_loader_entries_dir=td,
                            include_bootcount_in_oneshot=True,
                            dry_run=True,
                    )
            )
            gnb.expect_called_once_with(_DEV_NULL)
            fds.expect_not_called()
            so.expect_called_once_with(
                    sdboot_config.SdbootEntry("sonic_b", (1, 0)), True, True
            )

    @mock.patch("sonic_sdboot_utils.boot_control_main.get_next_boot")
    @mock.patch("sonic_sdboot_utils.boot_control_main.find_default_sonic")
    @mock.patch("sonic_sdboot_utils.sdboot_config.set_oneshot")
    def test_main_prepare_reboot_happy_path_next_boot_not_set(self, so, fds, gnb):
        fds.side_effect = [sdboot_config.SdbootEntry("sonic_b", (1, 0))]
        with self.tempdir() as td:
            boot_control_main.main(
                    argparse.Namespace(
                            action="prepare-reboot",
                            next_boot_flagfile_path=_DEV_NULL,
                            boot_loader_entries_dir=td,
                            include_bootcount_in_oneshot=True,
                            dry_run=True,
                    )
            )
            gnb.expect_called_once_with(_DEV_NULL)
            fds.expect_called_once_with(td)
            so.expect_called_once_with(
                    sdboot_config.SdbootEntry("sonic_b", (1, 0)), True, True
            )

    def test_find_matching_conf_none(self):
        with self.tempdir() as td:
            with self.assertRaises(SystemExit):
                boot_control_main.find_matching_conf_or_die(
                    sdboot_config.SdbootEntry("sonic_a", (1, 0)), td
                )

    def test_parse_args(self):
        with mock.patch("sys.argv", ["prog", "--dry-run", "--no-include-bootcount-in-oneshot", "prepare-reboot"]):
            res = boot_control_main._parse_args()
            self.assertTrue(res.dry_run)
            self.assertFalse(res.include_bootcount_in_oneshot)
            self.assertEqual(res.action, "prepare-reboot")

    def test_main_set_next_boot_missing_arg(self):
        with self.assertRaises(SystemExit):
            boot_control_main.main(argparse.Namespace(action="set-next-boot", additional_arg=None))

    def test_main_prepare_reboot_no_default(self):
        with mock.patch("sonic_sdboot_utils.boot_control_main.get_next_boot", return_value=None):
            with mock.patch("sonic_sdboot_utils.boot_control_main.find_default_sonic", return_value=None):
                with self.assertRaises(SystemExit):
                    boot_control_main.main(
                        argparse.Namespace(
                            action="prepare-reboot",
                            next_boot_flagfile_path=_DEV_NULL,
                            boot_loader_entries_dir=pathlib.Path("/mock"),
                            include_bootcount_in_oneshot=True,
                            dry_run=True,
                        )
                    )

    def test_main_unsupported_action(self):
        with self.assertRaises(SystemExit):
            boot_control_main.main(argparse.Namespace(action="invalid-action"))


if __name__ == "__main__":
    unittest.main()

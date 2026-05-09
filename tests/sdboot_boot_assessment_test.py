#!/usr/bin/env python3

import argparse
import contextlib
import pathlib
import tempfile
import unittest
from unittest import mock

from sonic_sdboot_utils import boot_assessment
from sonic_sdboot_utils import sdboot_config


class BootAssessmentTest(unittest.TestCase):

    @contextlib.contextmanager
    def make_namespace(self, *, dry_run: bool = False, reboot: bool = True):
        try:
            td = tempfile.TemporaryDirectory()
            tdpath = pathlib.Path(td.name)
            entries = tdpath / "loader/entries"
            entries.mkdir(parents=True)
            yield entries, argparse.Namespace(
                    boot_mountpoint=tdpath,
                    dry_run=dry_run,
                    include_bootcount_in_oneshot=True,
                    reboot=reboot,
            )
        finally:
            td.cleanup()

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
                version="dummy-ver",
                sort_key=sort_key,
                linux=pathlib.Path("dev/null"),
                initrd=pathlib.Path("dev/null"),
                options=["rw"],
                image_dir=pathlib.Path("image-A"),
        )

    def test_find_sonics_filters_and_orders_no_boot_loader_entries_dir(self):
        self.maxDiff = None
        with self.tempdir() as epath:
            confs = boot_assessment._find_sonics(epath / "dir/that/doesn't/exist")
            self.assertEqual(confs, [])

    def test_find_sonics_filters_and_orders_ba(self):
        self.maxDiff = None
        with self.tempdir() as epath:
            self.make_sdboot_conf(0x1001).write_file(epath / "sonic_x+1-1.conf")
            self.make_sdboot_conf(0x1000).write_file(epath / "sonic_a+1-1.conf")
            self.make_sdboot_conf(0x0FFF).write_file(epath / "sonic_b+1-1.conf")
            self.make_sdboot_conf(0x0FFE).write_file(epath / "sonic_c+1-1.conf")

            confs = boot_assessment._find_sonics(epath)
            self.assertListEqual(
                    confs,
                    [
                            (
                                    "sonic_b+1-1.conf",
                                    self.make_sdboot_conf(0x0FFF),
                            ),
                            (
                                    "sonic_a+1-1.conf",
                                    self.make_sdboot_conf(0x1000),
                            ),
                    ],
            )

    def test_find_sonics_filters_and_orders_ab(self):
        self.maxDiff = None
        with self.tempdir() as epath:
            self.make_sdboot_conf(0x1001).write_file(epath / "sonic_x+1-1.conf")
            self.make_sdboot_conf(0x1000).write_file(epath / "sonic_b+1-1.conf")
            self.make_sdboot_conf(0x0FFF).write_file(epath / "sonic_a+1-1.conf")
            self.make_sdboot_conf(0x0FFE).write_file(epath / "sonic_c+1-1.conf")

            confs = boot_assessment._find_sonics(epath)
            self.assertListEqual(
                    confs,
                    [
                            (
                                    "sonic_a+1-1.conf",
                                    self.make_sdboot_conf(0x0FFF),
                            ),
                            (
                                    "sonic_b+1-1.conf",
                                    self.make_sdboot_conf(0x1000),
                            ),
                    ],
            )

    @mock.patch("sonic_sdboot_utils.sdboot_config.set_oneshot")
    @mock.patch("sonic_sdboot_utils.boot_assessment.attempt_dhcp")
    @mock.patch("sonic_sdboot_utils.boot_assessment.reboot")
    def test_main_empty_boot(self, reboot, attempt_dhcp, set_os):
        with self.make_namespace() as (boot, ns):
            boot_assessment.main(ns)
        reboot.assert_called_once_with(dry_run=False)
        set_os.assert_not_called()
        attempt_dhcp.assert_called_with(
                boot_assessment.DHCPLength.LONG,
                dry_run=False,
        )

    @mock.patch("sonic_sdboot_utils.sdboot_config.set_oneshot")
    @mock.patch("sonic_sdboot_utils.boot_assessment.attempt_dhcp")
    @mock.patch("sonic_sdboot_utils.boot_assessment.reboot")
    def test_main_one_good(self, reboot, attempt_dhcp, set_os):
        with self.make_namespace() as (entries, ns):
            self.make_sdboot_conf(0x1000).write_file(entries / "sonic_a+1-0.conf")
            boot_assessment.main(ns)
        reboot.assert_called_once_with(dry_run=False)
        set_os.assert_called_once_with(
                sdboot_config.SdbootEntry("sonic_a", (1, 0)),
                include_bootcount=True,
                dry_run=False,
        )
        attempt_dhcp.assert_not_called()

    @mock.patch("sonic_sdboot_utils.sdboot_config.set_oneshot")
    @mock.patch("sonic_sdboot_utils.boot_assessment.attempt_dhcp")
    @mock.patch("sonic_sdboot_utils.boot_assessment.reboot")
    def test_main_one_bad(self, reboot, attempt_dhcp, set_os):
        with self.make_namespace() as (entries, ns):
            self.make_sdboot_conf(0x1000).write_file(entries / "sonic_a+0-1.conf")
            boot_assessment.main(ns)
        reboot.assert_called_once_with(dry_run=False)
        set_os.assert_not_called()
        attempt_dhcp.assert_called_with(
                boot_assessment.DHCPLength.SHORT, dry_run=False
        )

    @mock.patch("sonic_sdboot_utils.sdboot_config.set_oneshot")
    @mock.patch("sonic_sdboot_utils.boot_assessment.attempt_dhcp")
    @mock.patch("sonic_sdboot_utils.boot_assessment.reboot")
    def test_main_two_confs_none_bad(self, reboot, attempt_dhcp, set_os):
        with self.make_namespace() as (entries, ns):
            # sonic_b is 'primary' since it has the lower sort key.
            self.make_sdboot_conf(0x1000).write_file(entries / "sonic_a+1-0.conf")
            self.make_sdboot_conf(0x0FFF).write_file(entries / "sonic_b+1-0.conf")
            boot_assessment.main(ns)
        reboot.assert_called_once_with(dry_run=False)
        set_os.assert_called_once_with(
                sdboot_config.SdbootEntry("sonic_b", (1, 0)),
                include_bootcount=True,
                dry_run=False,
        )
        attempt_dhcp.assert_not_called()

    @mock.patch("sonic_sdboot_utils.sdboot_config.set_oneshot")
    @mock.patch("sonic_sdboot_utils.boot_assessment.attempt_dhcp")
    @mock.patch("sonic_sdboot_utils.boot_assessment.reboot")
    def test_main_two_confs_pri_bad(self, reboot, attempt_dhcp, set_os):
        with self.make_namespace() as (entries, ns):
            # sonic_b is 'primary' since it has the lower sort key.
            self.make_sdboot_conf(0x1000).write_file(entries / "sonic_a+1-0.conf")
            self.make_sdboot_conf(0x0FFF).write_file(entries / "sonic_b+0-1.conf")
            boot_assessment.main(ns)
        reboot.assert_called_once_with(dry_run=False)
        set_os.assert_called_once_with(
                sdboot_config.SdbootEntry("sonic_a", (1, 0)),
                include_bootcount=True,
                dry_run=False,
        )
        attempt_dhcp.assert_not_called()

    @mock.patch("sonic_sdboot_utils.sdboot_config.set_oneshot")
    @mock.patch("sonic_sdboot_utils.boot_assessment.attempt_dhcp")
    @mock.patch("sonic_sdboot_utils.boot_assessment.reboot")
    def test_main_two_confs_alt_bad(self, reboot, attempt_dhcp, set_os):
        with self.make_namespace() as (entries, ns):
            # sonic_b is 'primary' since it has the lower sort key.
            self.make_sdboot_conf(0x1000).write_file(entries / "sonic_a+0-1.conf")
            self.make_sdboot_conf(0x0FFF).write_file(entries / "sonic_b+1-0.conf")
            boot_assessment.main(ns)
        reboot.assert_called_once_with(dry_run=False)
        set_os.assert_not_called()
        attempt_dhcp.assert_called_with(
                boot_assessment.DHCPLength.SHORT, dry_run=False
        )

    @mock.patch("sonic_sdboot_utils.sdboot_config.set_oneshot")
    @mock.patch("sonic_sdboot_utils.boot_assessment.attempt_dhcp")
    @mock.patch("sonic_sdboot_utils.boot_assessment.reboot")
    def test_main_two_confs_both_bad(self, reboot, attempt_dhcp, set_os):
        with self.make_namespace() as (entries, ns):
            # sonic_b is 'primary' since it has the lower sort key.
            self.make_sdboot_conf(0x1000).write_file(entries / "sonic_a+0-1.conf")
            self.make_sdboot_conf(0x0FFF).write_file(entries / "sonic_b+0-1.conf")
            boot_assessment.main(ns)
        reboot.assert_called_once_with(dry_run=False)
        set_os.assert_not_called()
        attempt_dhcp.assert_called_with(
                boot_assessment.DHCPLength.SHORT, dry_run=False
        )

    def test_attempt_dhcp(self):
        with mock.patch("sonic_sdboot_utils.utils.run_cmd", return_value=0) as m:
            boot_assessment.attempt_dhcp(boot_assessment.DHCPLength.SHORT, dry_run=True)
            m.assert_called_once()

    def test_reboot(self):
        with mock.patch("sonic_sdboot_utils.utils.run_cmd", return_value=0) as m:
            boot_assessment.reboot(dry_run=True)
            m.assert_called_once_with(["reboot"], dry_run=True)

    def test_parse_args(self):
        with mock.patch("sys.argv", ["prog", "--dry-run", "--no-reboot", "--no-include-bootcount-in-oneshot"]):
            res = boot_assessment._parse_args()
            self.assertTrue(res.dry_run)
            self.assertFalse(res.reboot)
            self.assertFalse(res.include_bootcount_in_oneshot)


if __name__ == "__main__":
    unittest.main()

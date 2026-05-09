#!/usr/bin/env python3

import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock
import uuid

from sonic_sdboot_utils import utils

_DEV_NULL = pathlib.Path("/dev/null")
_TMP_MOUNT = pathlib.Path("/tmp/mountpoint")


class UtilsTest(unittest.TestCase):
  """Unit tests for utils.py"""

  def test_detect_install_env(self):
    cases = {
        "onie": utils.InstallEnvironment.ONIE,
        "sonic": utils.InstallEnvironment.SONIC,
        "sonie": utils.InstallEnvironment.SONIE,
        "build": utils.InstallEnvironment.BUILD,
    }

    for key, val in cases.items():
      with mock.patch("os.getenv") as oge:
        oge.return_value = key

        ret = utils.detect_install_environment()

        self.assertEqual(ret, val)

  @mock.patch("os.getenv")
  def test_empty_install_env(self, osge):
    osge.return_value = ""

    with self.assertRaises(ValueError):
      utils.detect_install_environment()

  @mock.patch("os.getenv")
  def test_invalid_install_env(self, osge):
    osge.return_value = "fake"

    with self.assertRaises(ValueError):
      utils.detect_install_environment()

  def check_run(self, run_cmd: mock.MagicMock, args: list[str]):
    """Asserts that run_cmd has been run with the specified arguments."""
    run_cmd.assert_has_calls([mock.call(args)])

  @mock.patch("subprocess.call")
  def test_run_cmd_simple(self, spcall):
    spcall.return_value = 42

    with mock.patch("builtins.print") as print_:
      ret = utils.run_cmd(["echo", "hello", "there"])
      print_.assert_has_calls(
          [mock.call("$ echo hello there", file=sys.stderr)]
      )

    self.assertEqual(ret, 42)
    spcall.assert_has_calls([mock.call(["echo", "hello", "there"])])

  @mock.patch("subprocess.call")
  def test_run_cmd_stringify(self, spcall):
    spcall.return_value = 42

    with mock.patch("builtins.print") as print_:
      ret = utils.run_cmd(["echo", 1, _DEV_NULL])
      print_.assert_has_calls(
          [mock.call("$ echo 1 /dev/null", file=sys.stderr)]
      )

    self.assertEqual(ret, 42)
    spcall.assert_has_calls([mock.call(["echo", "1", str(_DEV_NULL)])])

  @mock.patch("subprocess.call")
  def test_run_cmd_dryrun(self, spcall):
    spcall.return_value = 42

    with mock.patch("builtins.print") as print_:
      ret = utils.run_cmd(["echo", "hello there"], dry_run=True)
      print_.assert_has_calls(
          [mock.call("$ echo 'hello there'", file=sys.stderr)]
      )

    self.assertEqual(ret, 0)
    spcall.assert_not_called()

  @mock.patch("sonic_sdboot_utils.utils.run_cmd")
  def test_umount_failure(self, run_cmd):
    run_cmd.return_value = 42

    with self.assertRaises(utils.UnmountError):
      utils.umount(_TMP_MOUNT)

    self.check_run(run_cmd, ["umount", _TMP_MOUNT])

  @mock.patch("sonic_sdboot_utils.utils.run_cmd")
  def test_umount_success(self, run_cmd):
    run_cmd.return_value = 0

    utils.umount(_TMP_MOUNT)

    self.check_run(run_cmd, ["umount", _TMP_MOUNT])

  @mock.patch("sonic_sdboot_utils.utils.run_cmd")
  def test_simple_mount_success(self, run_cmd):
    run_cmd.return_value = 0

    ret = utils.mount(_DEV_NULL, _TMP_MOUNT)

    self.assertIsNone(ret)
    self.check_run(run_cmd, ["mount", _DEV_NULL, _TMP_MOUNT])

  @mock.patch("sonic_sdboot_utils.utils.run_cmd")
  def test_simple_mount_failure(self, run_cmd):
    run_cmd.return_value = 1

    with self.assertRaises(utils.MountError):
      ret = utils.mount(_DEV_NULL, _TMP_MOUNT)

    self.check_run(run_cmd, ["mount", _DEV_NULL, _TMP_MOUNT])

  @mock.patch("sonic_sdboot_utils.utils.run_cmd")
  def test_options_mount_success(self, run_cmd):
    run_cmd.return_value = 0

    ret = utils.mount(
        _DEV_NULL, _TMP_MOUNT, options=["bind", "noexec", "nosuid"]
    )

    self.assertIsNone(ret)
    self.check_run(
        run_cmd, ["mount", _DEV_NULL, _TMP_MOUNT, "-o", "bind,noexec,nosuid"]
    )

  @mock.patch("sonic_sdboot_utils.utils.run_cmd")
  def test_fstype_mount_success(self, run_cmd):
    run_cmd.return_value = 0

    ret = utils.mount(_DEV_NULL, _TMP_MOUNT, fstype="btrfs")

    self.assertIsNone(ret)
    self.check_run(run_cmd, ["mount", _DEV_NULL, _TMP_MOUNT, "-t", "btrfs"])

  def test_find_mountpoints_below(self):
    with tempfile.NamedTemporaryFile("w+t") as pm:
      pm.write("/dev/sda3 /                       ext4  rw 0 0\n")
      pm.write("/dev/sda1 /efi                    vfat  rw 0 0\n")
      pm.write("/dev/sda2 /boot                   vfat  rw 0 0\n")
      pm.write("none      /tmp                    tmpfs rw 0 0\n")
      pm.write("none      /tmp/mountpoint         tmpfs rw 0 0\n")
      pm.write("none      /tmp/mountpoint/one     tmpfs rw 0 0\n")
      pm.write("none      /tmp/mountpoint/one/two tmpfs rw 0 0\n")
      pm.write("none      /tmp/mountpoint/three   tmpfs rw 0 0\n")
      pm.flush()

      with mock.patch("sonic_sdboot_utils.utils._PROC_MOUNTS", pm.name):
        ret = utils.find_mountpoints_below(_TMP_MOUNT)
      self.assertEqual(
          ret,
          [
              _TMP_MOUNT / "three",
              _TMP_MOUNT / "one/two",
              _TMP_MOUNT / "one",
              _TMP_MOUNT,
          ],
      )

  @mock.patch("sonic_sdboot_utils.utils.find_mountpoints_below")
  @mock.patch("sonic_sdboot_utils.utils.umount")
  def test_unmount_tree_happy_path(self, umount, fmb):
    mps = [
        _TMP_MOUNT / "three",
        _TMP_MOUNT / "one/two",
        _TMP_MOUNT / "one",
        _TMP_MOUNT,
    ]
    fmb.return_value = mps

    utils.unmount_tree(_TMP_MOUNT)

    umount.assert_has_calls([mock.call(mp) for mp in mps])

  @mock.patch("sonic_sdboot_utils.utils.find_mountpoints_below")
  @mock.patch("sonic_sdboot_utils.utils.umount")
  def test_unmount_tree_error(self, umount, fmb):
    mps = [
        _TMP_MOUNT / "three",
        _TMP_MOUNT / "one/two",
        _TMP_MOUNT / "one",
        _TMP_MOUNT,
    ]
    fmb.return_value = mps
    # Succeed once, then throw an error.
    umount.side_effect = [None, utils.UnmountError("")]

    with self.assertRaises(utils.UnmountError):
      utils.unmount_tree(_TMP_MOUNT)

    umount.assert_has_calls([mock.call(mps[0]), mock.call(mps[1])])

  def test_get_dev_by_uuid_simple(self):
    target_dev = pathlib.Path("/dev/cooldev")
    with tempfile.TemporaryDirectory() as td:
      tdpath = pathlib.Path(td)
      gooduuid = str(uuid.uuid4())
      (tdpath / gooduuid).symlink_to(target_dev)

      # bunch of extra garbage
      (tdpath / str(uuid.uuid4())).symlink_to("/dev/notevenarealdev1")
      (tdpath / str(uuid.uuid4())).symlink_to("/dev/notevenarealdev2")
      (tdpath / str(uuid.uuid4())).symlink_to("/dev/notevenarealdev3")

      self.assertEqual(
          utils.get_dev_uuid(target_dev, dev_by_uuid=tdpath), gooduuid
      )

  def test_get_dev_by_uuid_missing(self):
    target_dev = pathlib.Path("/dev/cooldev")
    with tempfile.TemporaryDirectory() as td:
      tdpath = pathlib.Path(td)

      # bunch of extra garbage
      (tdpath / str(uuid.uuid4())).symlink_to("/dev/notevenarealdev1")
      (tdpath / str(uuid.uuid4())).symlink_to("/dev/notevenarealdev2")
      (tdpath / str(uuid.uuid4())).symlink_to("/dev/notevenarealdev3")

      with self.assertRaisesRegex(
          FileNotFoundError,
          f"Could not find a link for {target_dev} in {tdpath}",
      ):
        utils.get_dev_uuid(target_dev, dev_by_uuid=tdpath)


if __name__ == "__main__":
  unittest.main()

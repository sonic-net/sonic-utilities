#!/usr/bin/env python3

import argparse
import pathlib
import re
import tempfile
import unittest
from unittest import mock

from sonic_sdboot_utils import install_main
from sonic_sdboot_utils import sdboot_config
from sonic_sdboot_utils import utils

_UINT64_MAX = (1 << 64) - 1


def _is_mount_override(mounts):
    """Returns an is_mount that returns true only for the paths in mounts"""
    paths = set(pathlib.Path(path) for path in mounts)
    return lambda path: path in paths


def _mount_override(valids):
    """Returns an "is_mount" override that just checks for specific arguments."""

    def inner(*args, **kwargs):
        if (args, kwargs) in valids:
            return
        raise utils.MountError()

    return inner


class MainTest(unittest.TestCase):
    """Unit tests for the install functions."""

    def make_sdboot_conf(self, sort_key):
        """Create a dummy sd-boot config with the given sort key."""
        return sdboot_config.SdbootConfig(
                title="dummy",
                version="DummyVersion",
                sort_key=sort_key,
                linux=pathlib.Path("dev/null"),
                initrd=pathlib.Path("dev/null"),
                options=["rw"],
                image_dir=pathlib.Path("DummyImageName"),
        )

    @mock.patch("sonic_sdboot_utils.utils.detect_install_environment")
    @mock.patch("sonic_sdboot_utils.install_main._is_mount")
    def test_ensure_mountpoints_sonie_unmounted_boot(self, is_mount, udie):
        is_mount.side_effect = _is_mount_override([])
        udie.return_value = utils.InstallEnvironment.SONIE

        with self.assertRaisesRegex(
                install_main.InstallError, "/boot is not mounted"
        ):
            install_main.ensure_mountpoints_sonie(pathlib.Path("/tmp/something"))

    @mock.patch("sonic_sdboot_utils.utils.mount")
    @mock.patch("sonic_sdboot_utils.utils.run_cmd")
    @mock.patch("sonic_sdboot_utils.utils.unmount_tree")
    @mock.patch("sonic_sdboot_utils.utils.detect_install_environment")
    @mock.patch("sonic_sdboot_utils.install_main._is_mount")
    def test_ensure_mountpoints_sonie_unmounted_success(
            self, is_mount, udie, uumt, run_cmd, mount
    ):
        uumt.return_value = None
        udie.return_value = utils.InstallEnvironment.SONIE

        with (
                tempfile.TemporaryDirectory() as demo,
                tempfile.TemporaryDirectory() as boot,
                tempfile.TemporaryDirectory() as host,
        ):
            dpath = pathlib.Path(demo)
            bpath = pathlib.Path(boot)
            hpath = pathlib.Path(host)
            is_mount.side_effect = _is_mount_override([bpath])

            def mock_run_cmd(args):
                valids = {
                        ("mount", "--move", dpath, hpath),
                        ("mount", "--make-rprivate", "/"),
                }
                return 0 if tuple(args) in valids else 1

            run_cmd.side_effect = mock_run_cmd
            mount.return_value = None

            install_main.ensure_mountpoints_sonie(
                    pathlib.Path(demo), pathlib.Path(boot), pathlib.Path(host)
            )

            mount.assert_has_calls(
                    [mock.call(bpath, hpath / "boot", options=["bind"])]
            )

    @mock.patch("sonic_sdboot_utils.utils.mount")
    @mock.patch("sonic_sdboot_utils.utils.run_cmd")
    @mock.patch("sonic_sdboot_utils.utils.unmount_tree")
    @mock.patch("sonic_sdboot_utils.utils.detect_install_environment")
    @mock.patch("sonic_sdboot_utils.install_main._is_mount")
    def test_ensure_mountpoints_sonie_unmounted_move_fails(
            self, is_mount, udie, uumt, run_cmd, mount
    ):
        uumt.return_value = None
        udie.return_value = utils.InstallEnvironment.SONIE

        with (
                tempfile.TemporaryDirectory() as demo,
                tempfile.TemporaryDirectory() as boot,
                tempfile.TemporaryDirectory() as host,
        ):
            bpath = pathlib.Path(boot)
            is_mount.side_effect = _is_mount_override([bpath])

            def mock_run_cmd(args):
                valids = {
                        ("mount", "--make-rprivate", "/"),
                }
                return 0 if tuple(args) in valids else 1

            run_cmd.side_effect = mock_run_cmd
            mount.return_value = None

            with self.assertRaisesRegex(install_main.InstallError, ""):
                install_main.ensure_mountpoints_sonie(
                        pathlib.Path(demo), pathlib.Path(boot), pathlib.Path(host)
                )

    @mock.patch("sonic_sdboot_utils.utils.mount")
    @mock.patch("sonic_sdboot_utils.utils.run_cmd")
    @mock.patch("sonic_sdboot_utils.utils.unmount_tree")
    @mock.patch("sonic_sdboot_utils.utils.detect_install_environment")
    @mock.patch("sonic_sdboot_utils.install_main._is_mount")
    def test_ensure_mountpoints_sonie_bind_fails(
            self, is_mount, udie, uumt, run_cmd, mount
    ):
        uumt.return_value = None
        udie.return_value = utils.InstallEnvironment.SONIE

        with (
                tempfile.TemporaryDirectory() as demo,
                tempfile.TemporaryDirectory() as boot,
                tempfile.TemporaryDirectory() as host,
        ):
            dpath = pathlib.Path(demo)
            bpath = pathlib.Path(boot)
            hpath = pathlib.Path(host)
            is_mount.side_effect = _is_mount_override([bpath])
            mount.side_effect = _mount_override(
                    [((bpath, hpath / "boot"), {"options": ["bind"]})]
            )

            def mock_run_cmd(args):
                valids = {
                        ("mount", "--move", dpath, hpath),
                        ("mount", "--make-rprivate", "/"),
                }
                return 0 if tuple(args) in valids else 1

            run_cmd.side_effect = mock_run_cmd
            mount.return_value = None

            install_main.ensure_mountpoints_sonie(dpath, bpath, hpath)

            mount.assert_has_calls(
                    [mock.call(bpath, hpath / "boot", options=["bind"])]
            )

    @mock.patch("sonic_sdboot_utils.utils.umount")
    @mock.patch("sonic_sdboot_utils.utils.mount")
    @mock.patch("sonic_sdboot_utils.install_main._is_mount")
    def test_ensure_mountpoints_sonic_happy_path(self, is_mount, mount, umount):
        with (
                tempfile.TemporaryDirectory() as demo,
                tempfile.TemporaryDirectory() as boot,
                tempfile.TemporaryDirectory() as host,
        ):
            dpath = pathlib.Path(demo)
            bpath = pathlib.Path(boot)
            hpath = pathlib.Path(host)
            is_mount.side_effect = _is_mount_override([bpath, hpath])
            mount.side_effect = _mount_override(
                    [((bpath, hpath / "boot"), {"options": ["bind"]})]
            )

            install_main.ensure_mountpoints_sonic(dpath, bpath, hpath)

            umount.assert_not_called()
            mount.assert_called_once()

    @mock.patch("sonic_sdboot_utils.utils.umount")
    @mock.patch("sonic_sdboot_utils.utils.mount")
    @mock.patch("sonic_sdboot_utils.install_main._is_mount")
    def test_ensure_mountpoints_sonic_happy_path_host_boot_mounted(
            self, is_mount, mount, umount
    ):
        with (
                tempfile.TemporaryDirectory() as demo,
                tempfile.TemporaryDirectory() as boot,
                tempfile.TemporaryDirectory() as host,
        ):
            dpath = pathlib.Path(demo)
            bpath = pathlib.Path(boot)
            hpath = pathlib.Path(host)
            is_mount.side_effect = _is_mount_override([bpath, hpath, hpath / "boot"])
            mount.side_effect = _mount_override(
                    [((bpath, hpath / "boot"), {"options": ["bind"]})]
            )

            install_main.ensure_mountpoints_sonic(dpath, bpath, hpath)

            umount.assert_called_once_with(hpath / "boot")
            mount.assert_called_once()

    @mock.patch("sonic_sdboot_utils.utils.umount")
    @mock.patch("sonic_sdboot_utils.utils.mount")
    @mock.patch("sonic_sdboot_utils.install_main._is_mount")
    def test_ensure_mountpoints_sonic_missing_boot_mount(
            self, is_mount, mount, umount
    ):
        with (
                tempfile.TemporaryDirectory() as demo,
                tempfile.TemporaryDirectory() as boot,
                tempfile.TemporaryDirectory() as host,
        ):
            dpath = pathlib.Path(demo)
            bpath = pathlib.Path(boot)
            hpath = pathlib.Path(host)
            is_mount.side_effect = _is_mount_override([hpath])
            mount.side_effect = _mount_override(
                    [((bpath, hpath / "boot"), {"options": ["bind"]})]
            )

            with self.assertRaisesRegex(
                    install_main.InstallError,
                    re.escape(f"Missing mountpoints: {[bpath]}"),
            ):
                install_main.ensure_mountpoints_sonic(dpath, bpath, hpath)

            umount.assert_not_called()
            mount.assert_not_called()

    @mock.patch("sonic_sdboot_utils.utils.umount")
    @mock.patch("sonic_sdboot_utils.utils.mount")
    @mock.patch("sonic_sdboot_utils.install_main._is_mount")
    def test_ensure_mountpoints_sonic_missing_host_mount(
            self, is_mount, mount, umount
    ):
        with (
                tempfile.TemporaryDirectory() as demo,
                tempfile.TemporaryDirectory() as boot,
                tempfile.TemporaryDirectory() as host,
        ):
            dpath = pathlib.Path(demo)
            bpath = pathlib.Path(boot)
            hpath = pathlib.Path(host)
            is_mount.side_effect = _is_mount_override([bpath])
            mount.side_effect = _mount_override(
                    [((bpath, hpath / "boot"), {"options": ["bind"]})]
            )

            with self.assertRaisesRegex(
                    install_main.InstallError,
                    re.escape(f"Missing mountpoints: {[hpath]}"),
            ):
                install_main.ensure_mountpoints_sonic(dpath, bpath, hpath)

            umount.assert_not_called()
            mount.assert_not_called()

    @mock.patch("sonic_sdboot_utils.utils.umount")
    @mock.patch("sonic_sdboot_utils.utils.mount")
    @mock.patch("sonic_sdboot_utils.install_main._is_mount")
    def test_ensure_mountpoints_sonic_missing_all_mounts(
            self, is_mount, mount, umount
    ):
        with (
                tempfile.TemporaryDirectory() as demo,
                tempfile.TemporaryDirectory() as boot,
                tempfile.TemporaryDirectory() as host,
        ):
            dpath = pathlib.Path(demo)
            bpath = pathlib.Path(boot)
            hpath = pathlib.Path(host)
            is_mount.side_effect = _is_mount_override([])
            mount.side_effect = _mount_override(
                    [((bpath, hpath / "boot"), {"options": ["bind"]})]
            )

            with self.assertRaisesRegex(
                    install_main.InstallError,
                    re.escape(f"Missing mountpoints: {sorted([hpath, bpath])}"),
            ):
                install_main.ensure_mountpoints_sonic(dpath, bpath, hpath)

            umount.assert_not_called()
            mount.assert_not_called()

    def test_get_new_id_empty_dir(self):
        with tempfile.TemporaryDirectory() as entries:
            self.assertEqual(
                    install_main._get_new_id(pathlib.Path(entries)),
                    ("sonic_a", _UINT64_MAX),
            )

    def test_get_new_id_one_conf_returns_other(self):
        with tempfile.TemporaryDirectory() as entries:
            epath = pathlib.Path(entries)
            self.make_sdboot_conf(_UINT64_MAX).write_file(epath / "sonic_a.conf")
            self.assertEqual(
                    install_main._get_new_id(epath), ("sonic_b", _UINT64_MAX - 1)
            )

        with tempfile.TemporaryDirectory() as entries:
            epath = pathlib.Path(entries)
            self.make_sdboot_conf(0xFFFF).write_file(epath / "sonic_b.conf")
            self.assertEqual(install_main._get_new_id(epath), ("sonic_a", 0xFFFE))

    def test_get_new_id_irrelevant_ignored(self):
        with tempfile.TemporaryDirectory() as entries:
            epath = pathlib.Path(entries)
            self.make_sdboot_conf(0).write_file(epath / "sonic_c.conf")
            self.make_sdboot_conf(1).write_file(epath / "sonic_d.conf")
            self.make_sdboot_conf(2).write_file(epath / "sonic_e.conf")
            self.make_sdboot_conf(3).write_file(epath / "Garbage.conf")
            self.assertEqual(
                    install_main._get_new_id(epath), ("sonic_a", _UINT64_MAX)
            )

    def test_get_new_id_return_highest_if_two(self):
        with tempfile.TemporaryDirectory() as entries:
            epath = pathlib.Path(entries)
            self.make_sdboot_conf(0x1000).write_file(epath / "sonic_a.conf")
            self.make_sdboot_conf(0x2000).write_file(epath / "sonic_b.conf")
            self.assertEqual(
                    install_main._get_new_id(epath),
                    ("sonic_b", 0xFFF),
            )

        with tempfile.TemporaryDirectory() as entries:
            epath = pathlib.Path(entries)
            self.make_sdboot_conf(0x2000).write_file(epath / "sonic_a.conf")
            self.make_sdboot_conf(0x1000).write_file(epath / "sonic_b.conf")
            self.assertEqual(
                    install_main._get_new_id(epath),
                    ("sonic_a", 0xFFF),
            )

    @mock.patch("os.getenv")
    def test_bootloader_menu_config_happy_path(self, getenv):
        env = {}
        # Override new id finder to return an otherwise impossible ID.
        getenv.side_effect = env.get

        uuid = "011e416c-2289-4e4e-ac7e-a9ad5766edb9"

        with tempfile.TemporaryDirectory() as boot:
            bootpath = pathlib.Path(boot)
            ble = bootpath / "loader/entries"
            ble.mkdir(parents=True)

            sonie = bootpath / "SONIE"
            sonie.mkdir()

            linux = sonie / "linux-1.2.3"
            initrd = sonie / "initrd-1.2.3"

            for artifact in [linux, initrd]:
                with open(artifact, "w"):
                    pass

            install_main.bootloader_menu_config(
                    linux=linux.relative_to(bootpath),
                    version="DummyVersion",
                    initrd=initrd.relative_to(bootpath),
                    root_arg=f"UUID={uuid}",
                    fs_squashfs="image-A/fs.squashfs",
                    boot_path=bootpath,
                    conf_id="sonic_x",
                    sort_key=42,
                    extra_kernel_args=[],
                    image_name="DummyImageName",
            )

            conf = sdboot_config.SdbootConfig.from_file(
                    ble / "sonic_x+1-0.conf"
            ).to_dict()

            self.assertDictEqual(
                    conf,
                    {
                            "initrd": initrd.relative_to(bootpath),
                            "linux": linux.relative_to(bootpath),
                            "options": [
                                    f"root=UUID={uuid}",
                                    "rw",
                                    "net.ifnames=0",
                                    "biosdevname=0",
                                    "loop=/image-A/fs.squashfs",
                                    "loopfstype=squashfs",
                                    "systemd.unified_cgroup_hierarchy=0",
                                    "apparmor=1",
                                    "security=apparmor",
                                    "varlog_size=4096",
                                    "usbcore.autosuspend=-1",
                            ],
                            "sort-key": "0x000000000000002a",
                            "title": "sonic_x",
                            "version": "DummyVersion",
                            "image-dir": pathlib.Path("DummyImageName"),
                    },
            )

    @mock.patch("os.getenv")
    def test_bootloader_menu_config_happy_path_with_envs(self, getenv):
        env = {"VAR_LOG_SIZE": "1024"}
        # Override new id finder to return an otherwise impossible ID.
        getenv.side_effect = env.get

        uuid = "011e416c-2289-4e4e-ac7e-a9ad5766edb9"

        with tempfile.TemporaryDirectory() as boot:
            bootpath = pathlib.Path(boot)
            ble = bootpath / "loader/entries"
            ble.mkdir(parents=True)

            sonie = bootpath / "SONIE"
            sonie.mkdir()

            linux = sonie / "linux-1.2.3"
            initrd = sonie / "initrd-1.2.3"

            for artifact in [linux, initrd]:
                with open(artifact, "w"):
                    pass

            install_main.bootloader_menu_config(
                    linux=linux.relative_to(bootpath),
                    version="DummyVersion",
                    initrd=initrd.relative_to(bootpath),
                    root_arg=f"UUID={uuid}",
                    fs_squashfs="image-A/fs.squashfs",
                    boot_path=bootpath,
                    conf_id="sonic_x",
                    sort_key=42,
                    extra_kernel_args=["here", "is", "some", "more", "stuff"],
                    image_name="DummyImageName",
            )

            conf = sdboot_config.SdbootConfig.from_file(
                    ble / "sonic_x+1-0.conf"
            ).to_dict()

            self.assertDictEqual(
                    conf,
                    {
                            "initrd": initrd.relative_to(bootpath),
                            "linux": linux.relative_to(bootpath),
                            "options": [
                                    f"root=UUID={uuid}",
                                    "rw",
                                    "net.ifnames=0",
                                    "biosdevname=0",
                                    "loop=/image-A/fs.squashfs",
                                    "loopfstype=squashfs",
                                    "systemd.unified_cgroup_hierarchy=0",
                                    "apparmor=1",
                                    "security=apparmor",
                                    "varlog_size=1024",
                                    "usbcore.autosuspend=-1",
                                    "here",
                                    "is",
                                    "some",
                                    "more",
                                    "stuff",
                            ],
                            "sort-key": "0x000000000000002a",
                            "title": "sonic_x",
                            "version": "DummyVersion",
                            "image-dir": pathlib.Path("DummyImageName"),
                    },
            )

    def test_bootloader_menu_config_missing_linux(self):
        uuid = "011e416c-2289-4e4e-ac7e-a9ad5766edb9"

        with tempfile.TemporaryDirectory() as boot:
            bootpath = pathlib.Path(boot)
            ble = bootpath / "loader/entries"
            ble.mkdir(parents=True)

            sonie = bootpath / "SONIE"
            sonie.mkdir()

            linux = sonie / "linux-1.2.3"
            initrd = sonie / "initrd-1.2.3"

            with open(initrd, "w"):
                pass

            with self.assertRaisesRegex(
                    FileNotFoundError,
                    "Could not find linux artifact SONIE/linux-1.2.3 within .*",
            ):
                install_main.bootloader_menu_config(
                        linux=linux.relative_to(bootpath),
                        initrd=initrd.relative_to(bootpath),
                        version="DummyVersion",
                        root_arg=f"UUID={uuid}",
                        fs_squashfs="image-A/fs.squashfs",
                        boot_path=bootpath,
                        conf_id="sonic_x",
                        sort_key=42,
                        extra_kernel_args=[],
                        image_name="DummyImage",
                )

    def test_bootloader_menu_config_missing_initrd(self):
        uuid = "011e416c-2289-4e4e-ac7e-a9ad5766edb9"

        with tempfile.TemporaryDirectory() as boot:
            bootpath = pathlib.Path(boot)
            ble = bootpath / "loader/entries"
            ble.mkdir(parents=True)

            sonie = bootpath / "SONIE"
            sonie.mkdir()

            linux = sonie / "linux-1.2.3"
            initrd = sonie / "initrd-1.2.3"

            with open(linux, "w"):
                pass

            with self.assertRaisesRegex(
                    FileNotFoundError,
                    "Could not find initrd artifact SONIE/initrd-1.2.3 within .*",
            ):
                install_main.bootloader_menu_config(
                        linux=linux.relative_to(bootpath),
                        initrd=initrd.relative_to(bootpath),
                        version="DummyVersion",
                        root_arg=f"UUID={uuid}",
                        fs_squashfs="image-A/fs.squashfs",
                        boot_path=bootpath,
                        conf_id="sonic_x",
                        sort_key=42,
                        extra_kernel_args=[],
                        image_name="DummyImageName",
                )

    def test_install_boot_artifacts_success(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dest:
            spath = pathlib.Path(src)
            dpath = pathlib.Path(dest)
            with open(spath / "vmlinuz-1.2.3", "w"):
                pass
            with open(spath / "initrd.1.2.3", "w"):
                pass
            res_l, res_i = install_main._install_boot_artifacts(dpath, spath)
            self.assertEqual(res_l.name, "vmlinuz-1.2.3")
            self.assertEqual(res_i.name, "initrd.1.2.3")

    def test_install_boot_artifacts_failures(self):
        with tempfile.TemporaryDirectory() as src:
            spath = pathlib.Path(src)
            # Dest not dir
            with self.assertRaises(install_main.InstallError):
                install_main._install_boot_artifacts(spath / "non_existent", spath)

            # Ambiguous glob
            with self.assertRaises(ValueError):
                install_main._install_boot_artifacts(spath, spath)

    def test_parse_args(self):
        res = install_main._parse_args([
            "-d", "/mnt/demo", "-i", "image-A", "-I", "1.0", "-L", "fs.squashfs", "-D", "/dev/sda"
        ])
        self.assertEqual(res.image_name, "image-A")
        self.assertEqual(res.image_version, "1.0")

    def test_main_execution_sonie(self):
        with tempfile.TemporaryDirectory() as host:
            hpath = pathlib.Path(host)
            with mock.patch(
                "sonic_sdboot_utils.utils.detect_install_environment",
                return_value=install_main.utils.InstallEnvironment.SONIE,
            ):
                with mock.patch("sonic_sdboot_utils.utils.get_dev_uuid", return_value="mock-uuid"):
                    with mock.patch("sonic_sdboot_utils.install_main.ensure_mountpoints_sonie") as m_sonie:
                        with mock.patch("sonic_sdboot_utils.install_main._get_new_id", return_value=("sonic_a", 100)):
                            with mock.patch(
                                "sonic_sdboot_utils.install_main._install_boot_artifacts",
                                return_value=(hpath / "boot/vmlinuz", hpath / "boot/initrd"),
                            ):
                                with mock.patch("sonic_sdboot_utils.install_main.bootloader_menu_config") as m_cfg:
                                    (hpath / "boot/SONIC/sonic_a").mkdir(parents=True, exist_ok=True)
                                    install_main.main(
                                        argparse.Namespace(
                                            demo_dev=pathlib.Path("/dev/sda"),
                                            demo_dir=pathlib.Path("/mnt/demo"),
                                            boot_dir=pathlib.Path("/boot"),
                                            host_dir=hpath,
                                            image_name="image-A",
                                            image_version="1.0",
                                            loop_squash_file=pathlib.Path("fs.squashfs"),
                                            extra_kernel_args="console=ttyS0",
                                        )
                                    )
                                    m_sonie.assert_called_once()
                                    m_cfg.assert_called_once()

    def test_main_execution_sonic(self):
        with tempfile.TemporaryDirectory() as host:
            hpath = pathlib.Path(host)
            with mock.patch(
                "sonic_sdboot_utils.utils.detect_install_environment",
                return_value=install_main.utils.InstallEnvironment.SONIC,
            ):
                with mock.patch("sonic_sdboot_utils.utils.get_dev_uuid", return_value="mock-uuid"):
                    with mock.patch("sonic_sdboot_utils.install_main.ensure_mountpoints_sonic") as m_sonic:
                        with mock.patch("sonic_sdboot_utils.install_main._get_new_id", return_value=("sonic_a", 100)):
                            with mock.patch(
                                "sonic_sdboot_utils.install_main._install_boot_artifacts",
                                return_value=(hpath / "boot/vmlinuz", hpath / "boot/initrd"),
                            ):
                                with mock.patch("sonic_sdboot_utils.install_main.bootloader_menu_config") as m_cfg:
                                    install_main.main(
                                        argparse.Namespace(
                                            demo_dev=pathlib.Path("/dev/sda"),
                                            demo_dir=pathlib.Path("/mnt/demo"),
                                            boot_dir=pathlib.Path("/boot"),
                                            host_dir=hpath,
                                            image_name="image-A",
                                            image_version="1.0",
                                            loop_squash_file=pathlib.Path("fs.squashfs"),
                                            extra_kernel_args="console=ttyS0",
                                        )
                                    )
                                    m_sonic.assert_called_once()
                                    m_cfg.assert_called_once()

    def test_main_unsupported_env(self):
        with mock.patch(
            "sonic_sdboot_utils.utils.detect_install_environment",
            return_value=install_main.utils.InstallEnvironment.ONIE,
        ):
            with self.assertRaises(SystemExit):
                install_main.main(argparse.Namespace())


if __name__ == "__main__":
    unittest.main()

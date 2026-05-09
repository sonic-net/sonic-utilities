"""Abstract Bootloader class"""

from contextlib import contextmanager
import logging
from os import path
import pathlib
import re
import shutil

from sonic_sdboot_utils import sdboot_config
from sonic_sdboot_utils import boot_control_main

from .bootloader import Bootloader
from ..common import (
    HOST_PATH,
    IMAGE_PREFIX,
    ROOTFS_NAME,
    run_command,
)

logger = logging.getLogger(__name__)


class SystemdBootBootloader(Bootloader):

    NAME = None
    DEFAULT_IMAGE_PATH = "/tmp/sonic-image.bin"
    BOOT_LOADER_ENTRIES = pathlib.Path("/boot/loader/entries")

    def _parse_conf(self, conf: str) -> sdboot_config.SdbootEntry:
        return sdboot_config.SdbootEntry.from_filename(pathlib.Path(conf).stem)

    def _entries_exist(self) -> bool:
        return self.BOOT_LOADER_ENTRIES.is_dir()

    def _lookup_conf_by_id(
            self, conf_id: str
    ) -> tuple[sdboot_config.SdbootEntry | None, sdboot_config.SdbootConfig | None]:
        """Given a conf ID, find the conf's SdbootEntry and the parsed Config for it.

        If it can't be found, return None, None instead.
        """
        confs = sdboot_config.find_configs(self.BOOT_LOADER_ENTRIES)
        for key, val in confs.items():
            parsed = sdboot_config.SdbootEntry.from_filename(key)
            if parsed.identifier == conf_id:
                return parsed, val

        return None, None

    def _image_from_conf_id(self, conf_id: str) -> str | None:
        """Given a 'conf_id' (eg, sonic_a from sonic_a.conf), find the image str.

        Image str consistes of the title, a colon, and the version from the
        associated config.
        """
        confs = sdboot_config.find_configs(self.BOOT_LOADER_ENTRIES)
        for key, val in confs.items():
            parsed = sdboot_config.SdbootEntry.from_filename(key)
            if parsed.identifier == conf_id:
                return f"{val.title}:{val.version}"
        return None

    def _conf_from_image(self, image_str: str) -> str | None:
        """Given an 'image' string return which conf it's from.

        The inverse of _image_from_conf_id.
        """
        confs = sdboot_config.find_configs(self.BOOT_LOADER_ENTRIES)
        for key, val in confs.items():
            if f"{val.title}:{val.version}" == image_str:
                return sdboot_config.SdbootEntry.from_filename(key).identifier

    def get_current_image(self):
        """returns name of the current image"""
        cur_boot = sdboot_config.get_cur_boot()
        if cur_boot is None:
            return None
        return self._image_from_conf_id(cur_boot.identifier)

    def get_next_image(self):
        """returns name of the next image"""
        if not self.BOOT_LOADER_ENTRIES.is_dir():
            return None

        # Look at the efivar first.
        if (efivar := sdboot_config.get_oneshot()) is not None:
            return self._image_from_conf_id(efivar.identifier)

        # Next check if there's a next-boot set.
        if (flagfile := boot_control_main.get_next_boot()) is not None:
            return self._image_from_conf_id(flagfile.identifier)

        # If those both failed, try returning the default from sort-keys.
        default = boot_control_main.find_default_sonic(self.BOOT_LOADER_ENTRIES)
        if default is not None:
            return self._image_from_conf_id(default.identifier)

        return self.get_current_image()

    def get_installed_images(self) -> list[str]:
        """Returns list of installed images."""
        if not self.BOOT_LOADER_ENTRIES.is_dir():
            return []
        sonics = {"sonic_a", "sonic_b"}
        ret = []
        for key in sdboot_config.find_configs(self.BOOT_LOADER_ENTRIES):
            parsed = self._parse_conf(key)
            if parsed.identifier in sonics:
                ret.append(self._image_from_conf_id(parsed.identifier))
        return ret

    def set_default_image(self, image):
        """set default image to boot from"""
        if not self._entries_exist():
            return

        installed = self.get_installed_images()
        if image not in installed:
            return

        def get_config(identifier: str) -> sdboot_config.SdbootConfig:
            entry, conf = self._lookup_conf_by_id(identifier)
            return conf

        wanted_confname = self._conf_from_image(image)
        other_confnames = [
                self._conf_from_image(i) for i in installed if i != image
        ]

        new_key = min(
                (get_config(confname).sort_key - 1 for confname in other_confnames),
                default=(1 << 64) - 1,
        )

        new_conf = get_config(wanted_confname)
        new_conf.sort_key = new_key

        new_conf_entry = sdboot_config.SdbootEntry(wanted_confname, (1, 0))

        temp = self.BOOT_LOADER_ENTRIES / f"{new_conf_entry.to_stem()}.temp"
        live = self.BOOT_LOADER_ENTRIES / f"{new_conf_entry.to_stem()}.conf"

        new_conf.write_file(temp)
        temp.rename(live)

    def set_next_image(self, image):
        """set next image to boot from"""
        if not self._entries_exist():
            return

        want_conf_id = self._conf_from_image(image)
        if not want_conf_id:
            return

        parsed_entry, parsed_config = self._lookup_conf_by_id(want_conf_id)
        boot_control_main.set_next_boot(parsed_entry, True)

    def install_image(self, image_path):
        """install new image"""
        run_command(["bash", image_path])

    def remove_image(self, image):
        """remove existing image"""
        if not self.BOOT_LOADER_ENTRIES.exists():
            return

        conf = self._conf_from_image(image)
        parsed_entry, parsed_config = self._lookup_conf_by_id(conf)
        parsed_config: sdboot_config.SdbootConfig = parsed_config

        config_path = self.BOOT_LOADER_ENTRIES / f"{parsed_entry.to_stem()}.conf"
        print(f"Removing boot loader config {config_path}...")
        config_path.unlink()

        image_path = HOST_PATH / parsed_config.image_dir
        if image_path.is_dir():
            print(f"Removing image directory from filesystem ({image_path})...")
            shutil.rmtree(image_path)
        else:
            print(f"Not removing image directory {image_path}: It doesn't exist.")

    def get_binary_image_version(self, image_path):
        """Returns the version of the binary image."""
        if not path.isfile(image_path):
            return None

        version_re = re.compile(b'^image_version="(.*)"$')
        with open(image_path, "rb") as f:
            # Break out of looping upon the first decode or re error.
            try:
                for line in f:
                    match = version_re.match(line)
                    if match:
                        return IMAGE_PREFIX + match.group(1).rstrip().decode("utf-8")
            except (UnicodeDecodeError, TypeError):
                # Ignore errors since the image contains binary data.
                pass

        return None

    def verify_image_platform(self, image_path):
        """Verify image is of the same platform as the running platform"""
        return True

    def verify_secureboot_image(self, image_path):
        """verify that the image is secure running image"""
        # TODO(b/483382803): For now, return true. We're not using secure-boot yet,
        # so it's "verified" to the extent that anything is fine. Without this,
        # install will fail.
        return True

    def set_fips(self, image, enable):
        """set fips"""
        raise NotImplementedError

    def get_fips(self, image):
        """returns true if fips set"""
        raise NotImplementedError

    def verify_next_image(self):
        """verify the next image for reboot"""
        image = self.get_next_image()
        image_path = self.get_image_path(image)
        return path.exists(image_path)

    def supports_package_migration(self, image):
        """tells if the image supports package migration"""
        return False

    def verify_image_sign(self, image_path):
        """verify image signature is valid"""
        return True

    def is_secure_upgrade_image_verification_supported(self):
        return False

    @classmethod
    def detect(cls):
        """returns True if the bootloader is in use"""
        return path.isfile("/efi/EFI/systemd/systemd-bootx64.efi")

    @classmethod
    def get_image_path(cls, image):
        """Returns the image path."""
        conf = cls()._conf_from_image(image)
        return HOST_PATH / conf.image_dir

    @contextmanager
    def get_rootfs_path(self, image_path):
        """returns the path to the squashfs"""
        yield path.join(image_path, ROOTFS_NAME)

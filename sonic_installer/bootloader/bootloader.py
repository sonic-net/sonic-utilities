"""
Abstract Bootloader class
"""

from contextlib import contextmanager
from os import path
import yaml
import logging

logger = logging.getLogger(__name__)

from ..common import (
    HOST_PATH,
    IMAGE_DIR_PREFIX,
    IMAGE_PREFIX,
    ROOTFS_NAME,
)

class Bootloader(object):

    NAME = None
    DEFAULT_IMAGE_PATH = None

    def get_current_image(self):
        """returns name of the current image"""
        raise NotImplementedError

    def get_next_image(self):
        """returns name of the next image"""
        raise NotImplementedError

    def get_installed_images(self):
        """returns list of installed images"""
        raise NotImplementedError

    def set_default_image(self, image):
        """set default image to boot from"""
        raise NotImplementedError

    def set_next_image(self, image):
        """set next image to boot from"""
        raise NotImplementedError

    def install_image(self, image_path):
        """install new image"""
        raise NotImplementedError

    def remove_image(self, image):
        """remove existing image"""
        raise NotImplementedError

    def get_binary_image_version(self, image_path):
        """returns the version of the image"""
        raise NotImplementedError

    def verify_image_platform(self, image_path):
        """Verify image is of the same platform as the running platform"""
        raise NotImplementedError

    def verify_secureboot_image(self, image_path):
        """verify that the image is secure running image"""
        raise NotImplementedError

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
        return True

    def verify_image_sign(self, image_path):
        """verify image signature is valid"""
        raise NotImplementedError

    def is_secure_upgrade_image_verification_supported(self):
        return False

    @classmethod
    def detect(cls):
        """returns True if the bootloader is in use"""
        return False

    @classmethod
    def get_image_path(cls, image):
        """Returns the image path."""
        # 1. Try to find the image by version in SONiC A/B slots
        slot_names = ["image-A", "image-B"]
        paths = [path.join(HOST_PATH, s) for s in slot_names]
        candidates = [p for p in paths if path.exists(p)]

        clean_version = image
        if clean_version.startswith(IMAGE_PREFIX):
            clean_version = clean_version.replace(IMAGE_PREFIX, "", 1)

        fallback_slot_path = None
        for cand in candidates:
            config_path = path.join(cand, "sonic-config")
            if path.isfile(config_path):
                try:
                    with open(config_path, "r") as f:
                        data = yaml.safe_load(f)
                        if data and data.get("build_version") == clean_version:
                            return cand
                except AttributeError:
                    logger.error(f"Failed to get build version from {config_path}")
                except (OSError, yaml.YAMLError):
                    pass

            # Track a slot with a valid SONiC ROOTFS as a potential fallback
            if not fallback_slot_path and path.isfile(path.join(cand, ROOTFS_NAME)):
                fallback_slot_path = cand

        # 2. If it's a direct version directory check, e.g. /host/image-A/SONiC-OS-20260311.0
        # NOTE: This provides backwards compatibility for the non A/B slot SONiC distributions.
        prefix = path.join(HOST_PATH, IMAGE_DIR_PREFIX)
        default_path = image.replace(IMAGE_PREFIX, prefix, 1)
        if path.exists(default_path) and path.isfile(path.join(default_path, ROOTFS_NAME)):
            return default_path

        # 3. Use the fallback slot if found during search
        if fallback_slot_path:
            return fallback_slot_path

        # 4. Fallback: If the version is not found, it might be an installation
        # onto the "other" slot based on current running environment.
        try:
            # Detect which slot we should be targeting based on current running slot in cmdline.
            # Running in A targets B, otherwise default to A.
            with open('/proc/cmdline', 'r') as f:
                cmdline = f.read()

            slot = 'B' if 'image-A' in cmdline else 'A'
            target = path.join(HOST_PATH, f'image-{slot}')

            if path.isdir(target):
                return target
        except OSError:
            pass

        return default_path

    @contextmanager
    def get_rootfs_path(self, image_path):
        """returns the path to the squashfs"""
        yield path.join(image_path, ROOTFS_NAME)

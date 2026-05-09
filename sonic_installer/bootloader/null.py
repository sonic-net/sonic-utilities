"""
Null bootloader implementation when no bootloader is found on disk
"""

import os
import re

import click
import yaml

from ..common import (
    HOST_PATH,
    IMAGE_DIR_PREFIX,
    IMAGE_PREFIX,
    ROOTFS_NAME,
    run_command,
)
from .bootloader import Bootloader


class NullBootloader(Bootloader):
    """
    Null Bootloader that assumes we booted from RAM and there is no bootloader on disk.
    Used as a fallback when no other bootloader is detected.
    """

    NAME = 'null'

    def get_current_image(self):
        """Returns the name of the current image."""
        try:
            with open('/etc/sonic/sonic_version.yml', 'r') as f:
                data = yaml.safe_load(f)
                return IMAGE_PREFIX + data.get('build_version', 'Unknown')
        except (OSError, yaml.YAMLError, AttributeError):
            return "Unknown"

    def get_next_image(self):
        """Returns the name of the next image."""
        return "Unknown"

    def get_installed_images(self):
        """Returns a list of installed images."""
        return []

    def set_default_image(self, image):
        """Sets the default image to boot from."""
        return True

    def set_next_image(self, image):
        """Sets the next image to boot."""
        return True

    def install_image(self, image_path):
        """Installs the image."""
        click.echo("Null bootloader: installing image via bash...")
        run_command(["bash", image_path])

    def remove_image(self, image):
        """Removes the image."""
        pass

    def get_binary_image_version(self, image_path):
        """Returns the version of the binary image."""
        if not os.path.isfile(image_path):
            return None

        version_re = re.compile(b'image_version="(.*)"')
        with open(image_path, "rb") as f:
            # Break out of looping upon the first decode or re error.
            try:
                for line in f:
                    match = version_re.match(line)
                    if match:
                        return IMAGE_PREFIX + match.group(1).rstrip().decode('utf-8')
            except (UnicodeDecodeError, TypeError):
                # Ignore errors since the image contains binary data.
                pass

        return None

    def verify_image_platform(self, image_path):
        """Verifies the image platform."""
        return True

    def verify_secureboot_image(self, image_path):
        """Verifies the secure boot image."""
        return True

    def set_fips(self, image, enable):
        """Sets FIPS mode."""
        return True

    def get_fips(self, image):
        """Returns the FIPS status."""
        return False

    def verify_image_sign(self, image_path):
        """Verifies the image signature."""
        return True

    def supports_package_migration(self, image):
        """Returns true if the image supports package migration."""
        return False

    @classmethod
    def detect(cls):
        """Detects if the bootloader is in use."""
        # We only use this when everything else fails
        return False

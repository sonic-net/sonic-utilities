"""
Abstract Bootloader class
"""

from contextlib import contextmanager
from os import path

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
        """verify that the image is of the same platform than running platform"""
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
        """returns the image path"""
        prefix = path.join(HOST_PATH, IMAGE_DIR_PREFIX)
        return image.replace(IMAGE_PREFIX, prefix, 1)

    @contextmanager
    def get_rootfs_path(self, image_path):
        """returns the path to the squashfs"""
        yield path.join(image_path, ROOTFS_NAME)

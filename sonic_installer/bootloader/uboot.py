"""
Bootloader implementation for uboot based platforms
"""

import platform
import subprocess
import os
import re
from shlex import split
import click

from ..common import (
   HOST_PATH,
   IMAGE_DIR_PREFIX,
   IMAGE_PREFIX,
   run_command,
)
from .onie import OnieInstallerBootloader

class UbootBootloader(OnieInstallerBootloader):

    NAME = 'uboot'

    def get_installed_images(self):
        images = []
        proc = subprocess.Popen(["/usr/bin/fw_printenv", "-n", "sonic_version_1"], text=True, stdout=subprocess.PIPE)
        (out, _) = proc.communicate()
        image = out.rstrip()
        if IMAGE_PREFIX in image:
            images.append(image)
        proc = subprocess.Popen(["/usr/bin/fw_printenv", "-n", "sonic_version_2"], text=True, stdout=subprocess.PIPE)
        (out, _) = proc.communicate()
        image = out.rstrip()
        if IMAGE_PREFIX in image:
            images.append(image)
        return images

    def get_next_image(self):
        images = self.get_installed_images()
        proc = subprocess.Popen(["/usr/bin/fw_printenv", "-n", "boot_next"], text=True, stdout=subprocess.PIPE)
        (out, _) = proc.communicate()
        image = out.rstrip()
        if "sonic_image_2" in image and len(images) == 2:
            next_image_index = 1
        else:
            next_image_index = 0
        return images[next_image_index]

    def set_default_image(self, image):
        images = self.get_installed_images()
        if image in images[0]:
            run_command(['/usr/bin/fw_setenv', 'boot_next', "run sonic_image_1"])
        elif image in images[1]:
            run_command(['/usr/bin/fw_setenv', 'boot_next', "run sonic_image_2"])
        return True

    def set_next_image(self, image):
        images = self.get_installed_images()
        if image in images[0]:
            run_command(['/usr/bin/fw_setenv', 'boot_once', "run sonic_image_1"])
        elif image in images[1]:
            run_command(['/usr/bin/fw_setenv', 'boot_once', "run sonic_image_2"])
        return True

    def install_image(self, image_path):
        run_command(["bash", image_path])

    def remove_image(self, image):
        click.echo('Updating next boot ...')
        images = self.get_installed_images()
        if image in images[0]:
            run_command(['/usr/bin/fw_setenv', 'boot_next', "run sonic_image_2"])
            run_command(['/usr/bin/fw_setenv', 'sonic_version_1', "NONE"])
        elif image in images[1]:
            run_command(['/usr/bin/fw_setenv', 'boot_next', "run sonic_image_1"])
            run_command(['/usr/bin/fw_setenv', 'sonic_version_2', "NONE"])
        image_dir = image.replace(IMAGE_PREFIX, IMAGE_DIR_PREFIX, 1)
        click.echo('Removing image root filesystem...')
        subprocess.call(['rm','-rf', HOST_PATH + '/' + image_dir])
        click.echo('Done')

    def verify_image_platform(self, image_path):
        return os.path.isfile(image_path)

    def set_fips(self, image, enable):
        fips = "1" if enable else "0"
        proc = subprocess.Popen(["/usr/bin/fw_printenv", "linuxargs"], text=True, stdout=subprocess.PIPE)
        (out, _) = proc.communicate()
        cmdline = out.strip()
        cmdline = re.sub('^linuxargs=', '', cmdline)
        cmdline = re.sub(r' sonic_fips=[^\s]', '', cmdline) + " sonic_fips=" + fips
        run_command(['/usr/bin/fw_setenv', 'linuxargs', cmdline])
        click.echo('Done')

    def get_fips(self, image):
        proc = subprocess.Popen(["/usr/bin/fw_printenv", "linuxargs"], text=True, stdout=subprocess.PIPE)
        (out, _) = proc.communicate()
        return 'sonic_fips=1' in out

    @classmethod
    def detect(cls):
        arch = platform.machine()
        return ("arm" in arch) or ("aarch64" in arch)

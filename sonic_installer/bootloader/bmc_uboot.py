"""
Bootloader for BMC platforms (ASPEED U-Boot, two-slot environment).
"""

import os
import subprocess
import sys

import click
from sonic_py_common import device_info
from utilities_common.chassis import is_bmc

from ..common import (
   HOST_PATH,
   IMAGE_DIR_PREFIX,
   IMAGE_PREFIX,
   default_sigpipe,
   run_command,
)
from .onie import OnieInstallerBootloader

PLATFORMS_ASIC = "installer/platforms_asic"


class BmcUbootBootloader(OnieInstallerBootloader):

    NAME = 'bmc-uboot'

    SLOT_VERSION_VAR = {
        1: 'sonic_version_1',
        2: 'sonic_version_2',
    }
    SLOT_IMAGE_CMD = {
        1: 'run sonic_image_1',
        2: 'run sonic_image_2',
    }
    SLOT_LINUXARGS_VAR = {
        1: 'linuxargs',
        2: 'linuxargs_old',
    }
    SLOT_AUX_VARS = {
        1: ['image_dir', 'fit_name', 'linuxargs', 'sonic_bootargs', 'sonic_boot_load'],
        2: ['image_dir_old', 'fit_name_old', 'linuxargs_old', 'sonic_bootargs_old', 'sonic_boot_load_old'],
    }
    EMPTY_WRITE = 'None'

    def _fw_printenv(self, var):
        proc = subprocess.Popen(
            ['/usr/bin/fw_printenv', '-n', var],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, _ = proc.communicate()
        if proc.returncode != 0:
            return None
        return out.rstrip('\n')

    def _fw_setenv(self, var, value):
        run_command(['/usr/bin/fw_setenv', var, value])

    def _get_slot_image(self, slot):
        """Image name in `slot` (from sonic_version_N), or None if empty."""
        value = self._fw_printenv(self.SLOT_VERSION_VAR[slot])
        # Empty markers: '', 'None', 'NONE' (case-insensitive).
        if value is None or value.strip().lower() in ('', 'none'):
            return None
        if not value.startswith(IMAGE_PREFIX):
            return None
        return value

    def _get_image_slot(self, image):
        for slot in (1, 2):
            if self._get_slot_image(slot) == image:
                return slot
        return None

    def _boot_slot(self, var):
        """Slot that boot variable `var` ('boot_once'/'boot_next') selects, or None."""
        selector = (self._fw_printenv(var) or '').strip()
        for slot, command in self.SLOT_IMAGE_CMD.items():
            if selector == command:
                return slot
        return None

    # get_current_image is inherited from OnieInstallerBootloader: it parses
    # loop=<dir>/fs.squashfs from the cmdline, the format the BMC uses.

    def get_installed_images(self):
        images = []
        for slot in (1, 2):
            image = self._get_slot_image(slot)
            if image:
                images.append(image)
        return images

    def get_next_image(self):
        # boot_once (one-shot) wins over boot_next, matching U-Boot's bootcmd.
        for var in ('boot_once', 'boot_next'):
            slot = self._boot_slot(var)
            if slot:
                # Populated slot -> its image; empty slot -> raw marker, so state stays visible.
                return self._get_slot_image(slot) or self._fw_printenv(self.SLOT_VERSION_VAR[slot]) or self.SLOT_IMAGE_CMD[slot]
            selector = (self._fw_printenv(var) or '').strip()
            if selector:
                return selector  # set but unrecognized selector -> surface it
        return ''

    def set_default_image(self, image):
        slot = self._get_image_slot(image)
        if slot is None:
            return False
        self._fw_setenv('boot_next', self.SLOT_IMAGE_CMD[slot])
        self._fw_setenv('boot_once', '')
        return True

    def set_next_image(self, image):
        slot = self._get_image_slot(image)
        if slot is None:
            return False
        self._fw_setenv('boot_once', self.SLOT_IMAGE_CMD[slot])
        return True

    def install_image(self, image_path):
        run_command(['bash', image_path])
        # Installer set boot_next to slot 1; clear any stale boot_once that would shadow it.
        self._fw_setenv('boot_once', '')

    def remove_image(self, image):
        click.echo('Updating next boot ...')
        slot = self._get_image_slot(image)
        if slot is None:
            sys.exit('Image does not map to a BMC U-Boot slot')

        survivor = 2 if slot == 1 else 1
        if self._get_slot_image(survivor) is None:
            sys.exit('Cannot remove the only populated BMC image slot')

        if self._boot_slot('boot_once') == slot:
            self._fw_setenv('boot_once', '')

        if self._boot_slot('boot_next') == slot:
            self._fw_setenv('boot_next', self.SLOT_IMAGE_CMD[survivor])

        self._fw_setenv(self.SLOT_VERSION_VAR[slot], self.EMPTY_WRITE)
        for var in self.SLOT_AUX_VARS[slot]:
            self._fw_setenv(var, '')

        image_dir = image.replace(IMAGE_PREFIX, IMAGE_DIR_PREFIX, 1)
        click.echo('Removing image root filesystem...')
        subprocess.call(['rm', '-rf', os.path.join(HOST_PATH, image_dir)])
        click.echo('Done')

    def verify_image_platform(self, image_path):
        if not os.path.isfile(image_path):
            return False

        platform = device_info.get_platform()
        with open(os.devnull, 'w') as fnull:
            p1 = subprocess.Popen(
                ['sed', '-e', '1,/^exit_marker$/d', image_path],
                stdout=subprocess.PIPE,
                preexec_fn=default_sigpipe)
            p2 = subprocess.Popen(
                ['tar', 'xf', '-', PLATFORMS_ASIC, '-O'],
                stdin=p1.stdout,
                stdout=subprocess.PIPE,
                stderr=fnull,
                preexec_fn=default_sigpipe)
            p3 = subprocess.Popen(
                ['grep', '-Fxq', '-m', '1', platform],
                stdin=p2.stdout,
                preexec_fn=default_sigpipe)

            p2.wait()
            if p2.returncode != 0:
                return True

            p3.wait()
            return p3.returncode == 0

    def set_fips(self, image, enable):
        slot = self._get_image_slot(image)
        if slot is None:
            return False

        value = self._fw_printenv(self.SLOT_LINUXARGS_VAR[slot]) or ''
        tokens = [token for token in value.split() if not token.startswith('sonic_fips=')]
        tokens.append('sonic_fips={}'.format('1' if enable else '0'))
        self._fw_setenv(self.SLOT_LINUXARGS_VAR[slot], ' '.join(tokens))
        # CLI prints the success message; don't duplicate it here.
        return True

    def get_fips(self, image):
        slot = self._get_image_slot(image)
        if slot is None:
            return False

        value = self._fw_printenv(self.SLOT_LINUXARGS_VAR[slot]) or ''
        return any(token == 'sonic_fips=1' for token in value.split())

    @classmethod
    def detect(cls):
        return is_bmc()

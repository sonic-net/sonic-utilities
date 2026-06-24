"""
Common logic for bootloaders using an ONIE installer image
"""

import os
import re
import subprocess

from ..common import (
   IMAGE_DIR_PREFIX,
   IMAGE_PREFIX,
   default_sigpipe,
)
from .bootloader import Bootloader

class OnieInstallerBootloader(Bootloader): # pylint: disable=abstract-method

    DEFAULT_IMAGE_PATH = '/tmp/sonic_image'

    def get_current_image(self):
        try:
            with open('/proc/cmdline', 'r') as cmdline:
                match = re.search(r"loop=(\S+)/fs.squashfs", cmdline.read())
                if match:
                    current = match.group(1)
                    return current.replace(IMAGE_DIR_PREFIX, IMAGE_PREFIX, 1)
        except OSError:
            pass
        return None

    def get_binary_image_version(self, image_path):
        """returns the version of the image"""
        p1 = subprocess.Popen(["cat", "-v", image_path], stdout=subprocess.PIPE, preexec_fn=default_sigpipe)
        p2 = subprocess.Popen(["grep", "-m 1", "^image_version"], stdin=p1.stdout, stdout=subprocess.PIPE, preexec_fn=default_sigpipe)
        p3 = subprocess.Popen(["sed", "-n", r"s/^image_version=\"\(.*\)\"$/\1/p"], stdin=p2.stdout, stdout=subprocess.PIPE, preexec_fn=default_sigpipe, text=True)

        stdout = p3.communicate()[0]
        p3.wait()
        version_num = stdout.rstrip('\n')

        # If we didn't read a version number, this doesn't appear to be a valid SONiC image file
        if not version_num:
            return None

        return IMAGE_PREFIX + version_num

    def verify_secureboot_image(self, image_path):
        return os.path.isfile(image_path)

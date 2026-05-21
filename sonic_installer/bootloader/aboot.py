"""
Bootloader implementation for Aboot used on Arista devices
"""

import base64
import collections
import os
import re
import subprocess
import sys
import zipfile
from contextlib import contextmanager

import click

from M2Crypto import X509

from sonic_py_common import device_info
from ..common import (
   HOST_PATH,
   IMAGE_DIR_PREFIX,
   IMAGE_PREFIX,
   ROOTFS_NAME,
   run_command,
   run_command_or_raise,
   default_sigpipe,
)
from .bootloader import Bootloader

_secureboot = None
DEFAULT_SWI_IMAGE = 'sonic.swi'
KERNEL_CMDLINE_NAME = 'kernel-cmdline'

UNZIP_MISSING_FILE = 11

# For the signature format, see: https://github.com/aristanetworks/swi-tools/tree/master/switools
SWI_SIG_FILE_NAME = 'swi-signature'
SWIX_SIG_FILE_NAME = 'swix-signature'
ISSUERCERT = 'IssuerCert'

def parse_cmdline(cmdline=None):
    if cmdline is None:
        with open('/proc/cmdline') as f:
            cmdline = f.read()

    data = {}
    for entry in cmdline.split():
        idx = entry.find('=')
        if idx == -1:
            data[entry] = None
        else:
            data[entry[:idx]] = entry[idx+1:]
    return data

def docker_inram(cmdline=None):
    cmdline = parse_cmdline(cmdline)
    return cmdline.get('docker_inram') == 'on'

def is_secureboot():
    global _secureboot
    if _secureboot is None:
        cmdline = parse_cmdline()
        _secureboot = cmdline.get('secure_boot_enable') in ['y', '1']
    return _secureboot

class AbootBootloader(Bootloader):

    NAME = 'aboot'
    BOOT_CONFIG_PATH = os.path.join(HOST_PATH, 'boot-config')
    DEFAULT_IMAGE_PATH = '/tmp/sonic_image.swi'

    def _boot_config_read(self, path=BOOT_CONFIG_PATH):
        config = collections.OrderedDict()
        if not os.path.exists(path):
            return config
        with open(path) as f:
            for line in f.readlines():
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                config[key] = value
        return config

    def _boot_config_write(self, config, path=BOOT_CONFIG_PATH):
        with open(path, 'w') as f:
            f.write(''.join('%s=%s\n' % (k, v) for k, v in config.items()))

    def _boot_config_set(self, **kwargs):
        path = kwargs.pop('path', self.BOOT_CONFIG_PATH)
        config = self._boot_config_read(path=path)
        for key, value in kwargs.items():
            config[key] = value
        self._boot_config_write(config, path=path)

    def _swi_image_path(self, image):
        image_dir = image.replace(IMAGE_PREFIX, IMAGE_DIR_PREFIX, 1)
        if is_secureboot():
           return 'flash:%s/sonic.swi' % image_dir
        return 'flash:%s/.sonic-boot.swi' % image_dir

    def get_current_image(self):
        with open('/proc/cmdline') as f:
            current = re.search(r"loop=/*(\S+)/", f.read()).group(1)
        return current.replace(IMAGE_DIR_PREFIX, IMAGE_PREFIX, 1)

    def get_installed_images(self):
        images = []
        for filename in os.listdir(HOST_PATH):
            if filename.startswith(IMAGE_DIR_PREFIX):
                images.append(filename.replace(IMAGE_DIR_PREFIX,
                                               IMAGE_PREFIX, 1))
        return images

    def get_next_image(self):
        config = self._boot_config_read()
        swi = config.get('SWI', '')
        match = re.search(r"flash:/*(\S+)/", swi)
        if not match:
            return swi.split(':', 1)[-1]
        return match.group(1).replace(IMAGE_DIR_PREFIX, IMAGE_PREFIX, 1)

    def set_default_image(self, image):
        image_path = self._swi_image_path(image)
        self._boot_config_set(SWI=image_path, SWI_DEFAULT=image_path)
        return True

    def set_next_image(self, image):
        image_path = self._swi_image_path(image)
        self._boot_config_set(SWI=image_path)
        return True

    def install_image(self, image_path):
        run_command(["/usr/bin/unzip", "-od", "/tmp", image_path, "boot0"])
        env = os.environ.copy()
        env.update({
            'swipath': image_path,
            'target_path': '/host',
            'sonic_upgrade': '1'
        })
        run_command(["/bin/sh", "/tmp/boot0"], env=env)

    def remove_image(self, image):
        nextimage = self.get_next_image()
        current = self.get_current_image()
        if image == nextimage:
            image_path = self._swi_image_path(current)
            self._boot_config_set(SWI=image_path, SWI_DEFAULT=image_path)
            click.echo("Set next and default boot to current image %s" % current)

        image_path = self.get_image_path(image)
        click.echo('Removing image root filesystem...')
        subprocess.call(['rm','-rf', image_path])
        click.echo('Image removed')

    def _get_image_cmdline(self, image):
        image_path = self.get_image_path(image)
        with open(os.path.join(image_path, KERNEL_CMDLINE_NAME)) as f:
            return f.read()

    def _set_image_cmdline(self, image, cmdline):
        image_path = self.get_image_path(image)
        with open(os.path.join(image_path, KERNEL_CMDLINE_NAME), 'w') as f:
            return f.write(cmdline)

    def supports_package_migration(self, image):
        if is_secureboot():
            # NOTE: unsafe until migration can guarantee migration safety
            #       packages need to be signed and verified at boot time.
            return False
        cmdline = self._get_image_cmdline(image)
        if docker_inram(cmdline):
            # NOTE: the docker_inram feature extracts builtin containers at boot
            #       time in memory. the use of package manager under these
            #       circumpstances is not possible without a boot time package
            #       installation mechanism.
            return False
        return True

    def get_binary_image_version(self, image_path):
        try:
            version = subprocess.check_output(['/usr/bin/unzip', '-qop', image_path, '.imagehash'], text=True)
        except subprocess.CalledProcessError:
            return None
        return IMAGE_PREFIX + version.strip()

    def verify_image_platform(self, image_path):
        if not os.path.isfile(image_path):
            return False

        # Get running platform
        platform = device_info.get_platform()

        # If .platforms_asic is not existed, unzip will return code 11.
        # Return True for backward compatibility.
        # Otherwise, we grep to see if current platform is inside the
        # supported target platforms list.
        with open(os.devnull, 'w') as fnull:
            p1 = subprocess.Popen(['/usr/bin/unzip', '-qop', image_path, '.platforms_asic'], stdout=subprocess.PIPE, stderr=fnull, preexec_fn=default_sigpipe)
            p2 = subprocess.Popen(['grep', '-Fxq', '-m 1', platform], stdin=p1.stdout, preexec_fn=default_sigpipe)

            p1.wait()
            if p1.returncode == UNZIP_MISSING_FILE:
                return True

            # Code 0 is returned by grep as a result of found
            p2.wait()
            return p2.returncode == 0

    def verify_secureboot_image(self, image_path):
        try:
            subprocess.check_call(['/usr/bin/unzip', '-tq', image_path])
            return self._verify_secureboot_image(image_path)
        except subprocess.CalledProcessError:
            return False

    def verify_next_image(self):
        if not super(AbootBootloader, self).verify_next_image():
            return False
        image = self.get_next_image()
        image_path = os.path.join(self.get_image_path(image), DEFAULT_SWI_IMAGE)
        return self._verify_secureboot_image(image_path)

    def set_fips(self, image, enable):
        fips = "1" if enable else "0"
        cmdline = self._get_image_cmdline(image)
        cmdline = re.sub(r' sonic_fips=[^\s]', '', cmdline) + " sonic_fips=" + fips
        self._set_image_cmdline(image, cmdline)
        click.echo('Done')

    def get_fips(self, image):
        cmdline = self._get_image_cmdline(image)
        return 'sonic_fips=1' in cmdline

    def _verify_secureboot_image(self, image_path):
        if is_secureboot():
            cert = self.getCert(image_path)
            return cert is not None
        return True

    @classmethod
    def getCert(cls, swiFile):
        with zipfile.ZipFile(swiFile, 'r') as swi:
            try:
                sigInfo = swi.getinfo(cls.getSigFileName(swiFile))
            except KeyError:
                # Occurs if SIG_FILE_NAME is not in the swi (the SWI is not signed properly)
                return None
            with swi.open(sigInfo, 'r') as sigFile:
                for line in sigFile:
                    data = line.decode('utf8').split(':')
                    if len(data) == 2:
                        if data[0] == ISSUERCERT:
                            try:
                                base64_cert = cls.base64Decode(data[1].strip())
                                return X509.load_cert_string(base64_cert)
                            except TypeError:
                                return None
                    else:
                        sys.stderr.write('Unexpected format for line in swi[x]-signature file: %s\n' % line)
            return None

    @classmethod
    def getSigFileName(cls, swiFile):
        if swiFile.lower().endswith(".swix"):
            return SWIX_SIG_FILE_NAME
        return SWI_SIG_FILE_NAME

    @classmethod
    def base64Decode(cls, text):
        return base64.standard_b64decode(text)

    @classmethod
    def detect(cls):
        with open('/proc/cmdline') as f:
            return 'Aboot=' in f.read()

    def _get_swi_file_offset(self, swipath, filename):
        with zipfile.ZipFile(swipath) as swi:
            with swi.open(filename) as f:
                return f._fileobj.tell() # pylint: disable=protected-access

    @contextmanager
    def get_rootfs_path(self, image_path):
        path = os.path.join(image_path, ROOTFS_NAME)
        if os.path.exists(path) and not is_secureboot():
            yield path
            return

        swipath = os.path.join(image_path, DEFAULT_SWI_IMAGE)
        offset = self._get_swi_file_offset(swipath, ROOTFS_NAME)
        loopdev = subprocess.check_output(['losetup', '-f']).decode('utf8').rstrip()

        try:
            run_command_or_raise(['losetup', '-o', str(offset), loopdev, swipath])
            yield loopdev
        finally:
            run_command_or_raise(['losetup', '-d', loopdev])

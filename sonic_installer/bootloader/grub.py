"""
Bootloader implementation for grub based platforms
"""

import os
import re
import subprocess

import click

from sonic_py_common import device_info
from ..common import (
   HOST_PATH,
   IMAGE_DIR_PREFIX,
   IMAGE_PREFIX,
   run_command,
   default_sigpipe,
)
from .onie import OnieInstallerBootloader

PLATFORMS_ASIC = "installer/platforms_asic"

class GrubBootloader(OnieInstallerBootloader):

    NAME = 'grub'

    def get_installed_images(self):
        images = []
        config = open(HOST_PATH + '/grub/grub.cfg', 'r')
        for line in config:
            if line.startswith('menuentry'):
                image = line.split()[1].strip("'")
                if IMAGE_PREFIX in image:
                    images.append(image)
        config.close()
        return images

    def get_next_image(self):
        images = self.get_installed_images()
        grubenv = subprocess.check_output(["/usr/bin/grub-editenv", HOST_PATH + "/grub/grubenv", "list"], text=True)
        m = re.search(r"next_entry=(\d+)", grubenv)
        if m:
            next_image_index = int(m.group(1))
        else:
            m = re.search(r"saved_entry=(\d+)", grubenv)
            if m:
                next_image_index = int(m.group(1))
            else:
                next_image_index = 0
        return images[next_image_index]

    def set_default_image(self, image):
        images = self.get_installed_images()
        command = ['grub-set-default', '--boot-directory=' + HOST_PATH, str(images.index(image))]
        run_command(command)
        return True

    def set_next_image(self, image):
        images = self.get_installed_images()
        command = ['grub-reboot', '--boot-directory=' + HOST_PATH, str(images.index(image))]
        run_command(command)
        return True

    def install_image(self, image_path):
        run_command(["bash", image_path])
        run_command(['grub-set-default', '--boot-directory=' + HOST_PATH, '0'])

    def remove_image(self, image):
        click.echo('Updating GRUB...')
        config = open(HOST_PATH + '/grub/grub.cfg', 'r')
        old_config = config.read()
        menuentry = re.search("menuentry '" + image + "[^}]*}", old_config).group()
        config.close()
        config = open(HOST_PATH + '/grub/grub.cfg', 'w')
        # remove menuentry of the image in grub.cfg
        config.write(old_config.replace(menuentry, ""))
        config.close()
        click.echo('Done')

        image_dir = image.replace(IMAGE_PREFIX, IMAGE_DIR_PREFIX, 1)
        click.echo('Removing image root filesystem...')
        subprocess.call(['rm','-rf', HOST_PATH + '/' + image_dir])
        click.echo('Done')

        run_command(['grub-set-default', '--boot-directory=' + HOST_PATH, '0'])
        click.echo('Image removed')

    def get_linux_cmdline(self, image):
        cmdline = None
        config = open(HOST_PATH + '/grub/grub.cfg', 'r')
        old_config = config.read()
        menuentry = re.search("menuentry '" + image + "[^}]*}", old_config).group()
        config.close()
        for line in menuentry.split('\n'):
            line = line.strip()
            if line.startswith('linux '):
                cmdline = line[6:].strip()
                break
        return cmdline

    def set_linux_cmdline(self, image, cmdline):
        config = open(HOST_PATH + '/grub/grub.cfg', 'r')
        old_config = config.read()
        old_menuentry = re.search("menuentry '" + image + "[^}]*}", old_config).group()
        config.close()
        new_menuentry = old_menuentry
        for line in old_menuentry.split('\n'):
            line = line.strip()
            if line.startswith('linux '):
                new_menuentry = old_menuentry.replace(line, "linux " + cmdline)
                break
        config = open(HOST_PATH + '/grub/grub.cfg', 'w')
        config.write(old_config.replace(old_menuentry, new_menuentry))
        config.close()

    def set_fips(self, image, enable):
        fips = "1" if enable else "0"
        cmdline = self.get_linux_cmdline(image)
        cmdline = re.sub(r' sonic_fips=[^\s]', '', cmdline) + " sonic_fips=" + fips
        self.set_linux_cmdline(image, cmdline)
        click.echo('Done')

    def get_fips(self, image):
        cmdline = self.get_linux_cmdline(image)
        return 'sonic_fips=1' in cmdline

    def platform_in_platforms_asic(self, platform, image_path):
        """
        For those images that don't have devices list builtin, 'tar' will have non-zero returncode.
        In this case, we simply return True to make it worked compatible as before.
        Otherwise, we can grep to check if platform is inside the supported target platforms list.
        """
        with open(os.devnull, 'w') as fnull:
            p1 = subprocess.Popen(["sed", "-e", "1,/^exit_marker$/d", image_path], stdout=subprocess.PIPE, preexec_fn=default_sigpipe)
            p2 = subprocess.Popen(["tar", "xf", "-", PLATFORMS_ASIC, "-O"], stdin=p1.stdout, stdout=subprocess.PIPE, stderr=fnull, preexec_fn=default_sigpipe)
            p3 = subprocess.Popen(["grep", "-Fxq", "-m 1", platform], stdin=p2.stdout, preexec_fn=default_sigpipe)

            p2.wait()
            if p2.returncode != 0:
                return True

            # Code 0 is returned by grep as a result of found
            p3.wait()
            return p3.returncode ==0

    def verify_image_platform(self, image_path):
        if not os.path.isfile(image_path):
            return False

        # Get running platform
        platform = device_info.get_platform()

        # Check if platform is inside image's target platforms
        return self.platform_in_platforms_asic(platform, image_path)

    def is_secure_upgrade_image_verification_supported(self):

        check_if_verification_is_enabled_and_supported_code = '''
        SECURE_UPGRADE_ENABLED=0
        #Disabling the check for cisco-8000 platforms as platform-side support is not ready yet. This will be removed once platform
        #support is added.
        ASIC_TYPE=$(sonic-cfggen -y /etc/sonic/sonic_version.yml -v asic_type)
        if [ -d "/sys/firmware/efi/efivars" ] && [[ ${ASIC_TYPE} != *"cisco-8000"* ]]; then
            if ! [ -n "$(ls -A /sys/firmware/efi/efivars 2>/dev/null)" ]; then
                mount -t efivarfs none /sys/firmware/efi/efivars 2>/dev/null
            fi
            SECURE_UPGRADE_ENABLED=$(bootctl status 2>/dev/null | grep -c "Secure Boot: enabled")
        else
            echo "efi not supported - exiting without verification"
            exit 1
        fi

        if [ ${SECURE_UPGRADE_ENABLED} -eq 0 ]; then
            echo "secure boot not enabled - exiting without image verification"
            exit 1
        fi
        exit 0
        '''
        verification_result = subprocess.run(['bash', '-c', check_if_verification_is_enabled_and_supported_code], capture_output=True)
        click.echo(verification_result.stdout.decode())
        return verification_result.returncode == 0

    def verify_image_sign(self, image_path):
        click.echo('Verifying image signature')
        verification_script_name = 'verify_image_sign.sh'
        script_path = os.path.join('/usr', 'local', 'bin', verification_script_name)
        if not os.path.exists(script_path):
            click.echo("Unable to find verification script in path " + script_path)
            return False
        verification_result = subprocess.run([script_path, image_path], capture_output=True)
        click.echo(verification_result.stdout.decode())
        return verification_result.returncode == 0

    @classmethod
    def detect(cls):
        return os.path.isfile(os.path.join(HOST_PATH, 'grub/grub.cfg'))

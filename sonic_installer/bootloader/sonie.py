"""Bootloader implementation for Sonie based platforms."""

import os

import subprocess
import syslog
import sys
from typing import Optional
from ..common import (
    run_command,
)
from ..exception import SonicRuntimeException
from .grub import GrubBootloader


class SonieGrubBootloader(GrubBootloader):
    """Bootloader implementation for Sonie based platforms."""
    NAME = 'sonie'

    # Location of the sonie environment file
    ENV_FILE = '/efi/sonie_env'

    def _get_grub_env_var(self, variable: str) -> Optional[int]:
        """Returns the value of the Grub environment variable.

        Args:
          variable: Grub environment variable to retrieve value for.

        Returns:
          The value of the Grub environment variable, or None if the variable is not set.

        Raises:
          SonicRuntimeException: If the Grub environment variable could not be retrieved.
        """
        try:
            env_content = subprocess.check_output(
                ['/usr/bin/grub-editenv', self.ENV_FILE, 'list'], text=True
            )
        except subprocess.CalledProcessError as e:
            # If the file doesn't exist or we can't read it, it might not be initialized.
            raise SonicRuntimeException(
                'Failed to get environment variable %s: %s' % (variable, e.output)
            ) from e

        for line in env_content.splitlines():
            # Lines are formatted as key=value
            key, sep, value = line.partition('=')
            if sep == '=' and key == variable and value.isdigit():
                return int(value)

        return None

    def _set_grub_env_var(self, variable: str, value: str) -> bool:
        """Sets the value of the Grub environment variable.

        Args:
          variable: Name of Grub environment variable to set.
          value: Value to set the Grub environment variable to.

        Returns:
          True if the variable was set, False otherwise.
        """
        try:
            command = ['grub-editenv', self.ENV_FILE, 'set', f'{variable}={value}']
            run_command(command)
        except subprocess.CalledProcessError as e:
            raise SonicRuntimeException(
                'Failed to set environment variable %s: %s' % (variable, e.output)
            ) from e
        return True

    def _set_image_to_boot(self, image: str, persist: bool) -> bool:
        """Sets the next image to boot and whether to persist the setting.

        Args:
          image: Name of the next image to boot.
          persist: Whether to persist the setting.

        Returns:
          True if the image was set, False otherwise.
        """
        images = self.get_installed_images()
        try:
            # rollback: 0 for A (index 0), 1 for B (index 1)
            # bootcount: 2 (try 1), 1 (try 2), 0 (fallback)
            # If persist=True (default), we want to change rollback preference.
            target_index = images.index(image)

            # If persist, we update rollback to match target_index (0 -> 0, 1 -> 1)
            # And reset bootcount to 2.
            if persist:
                self._set_grub_env_var('rollback_env', str(target_index & 1))
                self._set_grub_env_var('bootcount_env', '2')
                self._set_grub_env_var('install_env', '0')
                self._set_grub_env_var('warmboot_env', '0')
                return True
            else:
                # If current preference is A (rollback=0):
                #   bootcount=2 -> A
                #   bootcount=1 -> B
                # So if we want to force B once, we set bootcount=1 (if rollback=0).
                # If rollback=1 (prefer B):
                #   bootcount=2 -> B
                #   bootcount=1 -> A
                # So if we want to force A once, we set bootcount=1 (if rollback=1).
                current_rollback = self._get_grub_env_var('rollback_env') or 0

                if current_rollback == target_index:
                    # Already preferred, just ensure bootcount=2
                    self._set_grub_env_var('bootcount_env', '2')
                else:
                    # target is opposite of preference. Set bootcount=1 to try secondary once.
                    self._set_grub_env_var('bootcount_env', '1')

                self._set_grub_env_var('install_env', '0')
                self._set_grub_env_var('warmboot_env', '0')
                return True

        except ValueError:
            syslog.syslog(syslog.LOG_ERR, f'Failed to find image: {image}')
        except SonicRuntimeException:
            syslog.syslog(syslog.LOG_ERR, 'Failed to set environment variables')
        return False

    def get_next_image(self):
        """Gets the next image to boot based on the environment variables.

        Returns:
          The next image to boot or None if the env vars are corrupted.
        """
        images = self.get_installed_images()
        try:
            bootcount = self._get_grub_env_var('bootcount_env')
            rollback = self._get_grub_env_var('rollback_env')
            install = self._get_grub_env_var('install_env')
        except SonicRuntimeException:
            syslog.syslog(syslog.LOG_ERR, 'Failed to get environment variables')
            return None

        if bootcount is None:
            # Return None, unitialized bootcount means we don't know what to do?
            return None

        # Determine defaults
        if rollback is None:
            rollback = 0

        if install == 1 or bootcount == 0:
            return 'SONIE'

        # Logic: index = (2 - bootcount) ^ rollback
        # b=2, r=0 -> 0 (A)
        # b=1, r=0 -> 1 (B)
        # b=2, r=1 -> 1 (B)
        # b=1, r=1 -> 0 (A)

        default_index = (2 - bootcount) ^ rollback

        if default_index >= len(images):
            return 'SONIE'

        return images[default_index]

    def set_default_image(self, image):
        """Sets the default image to boot from."""
        return self._set_image_to_boot(image, True)

    def set_next_image(self, image):
        """Sets the next image to boot."""
        return self._set_image_to_boot(image, False)

    def install_image(self, image_path):
        """Install new image."""
        run_command(['bash', image_path])

        try:
            self._set_grub_env_var('bootcount_env', '2')
            self._set_grub_env_var('install_env', '0')
            self._set_grub_env_var('warmboot_env', '0')
            self._set_grub_env_var('rollback_env', '0')
        except SonicRuntimeException as e:
            syslog.syslog(syslog.LOG_ERR, f'Failed to set environment variables: {str(e)}')

        except Exception as e:
            syslog.syslog(syslog.LOG_ERR, f'Failed to update bootloader environment variables: {str(e)}')
            # Also print to stderr
            sys.stderr.write(f'Failed to update bootloader environment variables: {str(e)}\n')

    def remove_image(self, image):
        """Removes image."""
        super().remove_image(image)
        # Reset state
        try:
            self._set_grub_env_var('bootcount_env', '2')
            self._set_grub_env_var('install_env', '0')
            self._set_grub_env_var('warmboot_env', '0')
        except SonicRuntimeException as e:
            syslog.syslog(syslog.LOG_ERR, f'Failed to set environment variables: {str(e)}')

    @classmethod
    def detect(cls):
        """Detects if the bootloader is in use.

        Returns:
            True if the bootloader is in use, False otherwise.
        """
        file_found = False
        try:
            if os.path.exists(cls.ENV_FILE):
                file_found = True
        except OSError:
            syslog.syslog(syslog.LOG_ERR, 'Failed to detect Sonie bootloader.')

        # Simple file existence check on the formatted partition
        return file_found

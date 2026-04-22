"""
Bootloader implementation for uboot based platforms
"""

import platform
import subprocess
import os
import re
from shlex import split
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

class UbootBootloader(OnieInstallerBootloader):

    NAME = 'uboot'

    # Marker for an emptied slot. Spelling ("NONE" vs "None") varies
    # between platform installers; read-side filtering uses IMAGE_PREFIX
    # so either is fine.
    EMPTY_SLOT_MARKER = "NONE"

    # Paired per-slot aux env vars (slot-1 name, slot-2 name).
    # When a slot is removed, remove_image() clears the var only if
    # BOTH names in the pair exist -- proving the platform actually
    # uses this name pair per-slot. Otherwise the var is treated as
    # globally shared and left alone (some platforms use a single
    # `linuxargs` referenced by both sonic_image_1 and sonic_image_2).
    SLOT_AUX_VAR_PAIRS = (
        # `_old` convention
        ("image_dir", "image_dir_old"),
        ("image_name", "image_name_old"),
        ("initrd_name", "initrd_name_old"),
        ("fdt_name", "fdt_name_old"),
        ("fit_name", "fit_name_old"),
        ("linuxargs", "linuxargs_old"),
        ("sonic_bootargs", "sonic_bootargs_old"),
        ("sonic_boot_load", "sonic_boot_load_old"),
        ("ubi_sonic_boot_bootargs", "ubi_sonic_boot_bootargs_old"),
        ("ubi_sonic_boot_load", "ubi_sonic_boot_load_old"),
        # `_1`/`_2` convention
        ("sonic_dir_1", "sonic_dir_2"),
    )

    def _fw_printenv(self, var):
        """Return stripped value of U-Boot env ``var``, or None on error."""
        proc = subprocess.Popen(
            ["/usr/bin/fw_printenv", "-n", var],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out, _) = proc.communicate()
        if proc.returncode != 0:
            return None
        return out.rstrip()

    def _fw_setenv(self, var, value):
        run_command(['/usr/bin/fw_setenv', var, value])

    def _read_slots(self):
        """Return ``{slot: version}`` for populated slots (1 and/or 2)."""
        slots = {}
        for slot in (1, 2):
            ver = self._fw_printenv("sonic_version_{}".format(slot))
            if ver is not None and IMAGE_PREFIX in ver:
                slots[slot] = ver
        return slots

    def get_installed_images(self):
        slots = self._read_slots()
        return [slots[s] for s in sorted(slots)]

    def _get_image_slot(self, image):
        """Return 1 or 2 — the slot that holds ``image`` — or None.

        Exact-equality match against sonic_version_<N>: avoids the
        substring + list-index bugs that bit the original
        ``if image in images[N]`` callers.
        """
        for slot, ver in self._read_slots().items():
            if ver == image:
                return slot
        return None

    def get_next_image(self):
        """Return the image U-Boot will boot next.

        SONiC bootcmd consumes ``boot_once`` (one-shot) before
        ``boot_next``; both name a slot via ``run sonic_image_<N>``.
        If the selected slot is empty, return that slot's raw
        sonic_version_<N> literal rather than silently substituting
        the current image -- otherwise list / verify-next-image
        would disagree with the actual boot config.
        """
        slots = self._read_slots()

        for var in ("boot_once", "boot_next"):
            cmd = self._fw_printenv(var) or ""
            if not cmd:
                continue
            for slot in (1, 2):
                if "sonic_image_{}".format(slot) in cmd:
                    if slot in slots:
                        return slots[slot]
                    # Selected slot is empty -- surface the literal,
                    # don't fall back (would mask broken state).
                    return self._fw_printenv(
                        "sonic_version_{}".format(slot)) or ""
            # Non-empty selector that doesn't name sonic_image_<1|2>.
            # U-Boot will execute it first, so reporting boot_next
            # instead would lie. Return the raw value.
            return cmd

        # No explicit selector -- fall back to current image
        # (mirrors grub.py when next_entry/saved_entry are absent).
        try:
            return self.get_current_image()
        except Exception:
            if slots:
                return slots[min(slots)]
            return ""

    def set_default_image(self, image):
        slot = self._get_image_slot(image)
        if slot is None:
            return False
        self._fw_setenv('boot_next', 'run sonic_image_{}'.format(slot))
        # Clear any prior set-next-boot so the new default isn't
        # shadowed by an older one-shot selection.
        self._fw_setenv('boot_once', '')
        return True

    def set_next_image(self, image):
        slot = self._get_image_slot(image)
        if slot is None:
            return False
        self._fw_setenv('boot_once', 'run sonic_image_{}'.format(slot))
        return True

    def install_image(self, image_path):
        run_command(["bash", image_path])
        # Clear any prior set-next-boot so a stale one-shot doesn't
        # shadow the freshly-installed image at next boot.
        self._fw_setenv('boot_once', '')

    def remove_image(self, image):
        click.echo('Updating next boot ...')
        slot = self._get_image_slot(image)
        if slot is not None:
            other = 2 if slot == 1 else 1
            self._fw_setenv('boot_next',
                            'run sonic_image_{}'.format(other))
            # Clear boot_once if it still points at the slot we're
            # removing -- otherwise next reboot runs a stale script.
            boot_once = self._fw_printenv("boot_once") or ""
            if "sonic_image_{}".format(slot) in boot_once:
                self._fw_setenv('boot_once', '')
            self._fw_setenv('sonic_version_{}'.format(slot),
                            self.EMPTY_SLOT_MARKER)
            # Pair-check before clearing each aux var: only clear if
            # BOTH names in the pair exist (platform uses per-slot
            # _old convention). Skip otherwise -- the var is likely
            # globally shared across slots.
            for pair in self.SLOT_AUX_VAR_PAIRS:
                target = pair[slot - 1]
                sibling = pair[2 - slot]
                if (self._fw_printenv(target) is not None
                        and self._fw_printenv(sibling) is not None):
                    self._fw_setenv(target, '')
        image_dir = image.replace(IMAGE_PREFIX, IMAGE_DIR_PREFIX, 1)
        click.echo('Removing image root filesystem...')
        subprocess.call(['rm', '-rf', HOST_PATH + '/' + image_dir])
        click.echo('Done')

    def platform_in_platforms_asic(self, platform, image_path):
        """Return True iff ``platform`` appears in the SONiC image's
        ``installer/platforms_asic`` manifest. Direct port of the
        grub.py helper: extracts the manifest via the standard
        sed-strip-+-tar pipeline and greps for an exact match.

        For older images that don't ship ``installer/platforms_asic``,
        tar exits non-zero and we return True (backward compatible
        with grub.py).
        """
        with open(os.devnull, 'w') as fnull:
            p1 = subprocess.Popen(
                ["sed", "-e", "1,/^exit_marker$/d", image_path],
                stdout=subprocess.PIPE, preexec_fn=default_sigpipe)
            p2 = subprocess.Popen(
                ["tar", "xf", "-", PLATFORMS_ASIC, "-O"],
                stdin=p1.stdout, stdout=subprocess.PIPE,
                stderr=fnull, preexec_fn=default_sigpipe)
            p3 = subprocess.Popen(
                ["grep", "-Fxq", "-m", "1", platform],
                stdin=p2.stdout, preexec_fn=default_sigpipe)

            p2.wait()
            if p2.returncode != 0:
                # No platforms_asic in the archive -> assume any
                # platform is acceptable (matches grub.py).
                return True

            p3.wait()
            return p3.returncode == 0

    def verify_image_platform(self, image_path):
        if not os.path.isfile(image_path):
            return False
        platform = device_info.get_platform()
        return self.platform_in_platforms_asic(platform, image_path)

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

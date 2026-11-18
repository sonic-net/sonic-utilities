
from .bmc_uboot import BmcUbootBootloader
from .aboot import AbootBootloader
from .grub import GrubBootloader
from .uboot import UbootBootloader

# Probe BMC first so a stray /host/grub/grub.cfg can't preempt it; detect() is
# is_bmc(), which is False on non-BMC platforms, so this is safe elsewhere.
BOOTLOADERS = [
    BmcUbootBootloader,
    AbootBootloader,
    GrubBootloader,
    UbootBootloader,
]

def get_bootloader():
    for bootloaderCls in BOOTLOADERS:
        if bootloaderCls.detect():
            return bootloaderCls()
    raise RuntimeError('Bootloader could not be detected')

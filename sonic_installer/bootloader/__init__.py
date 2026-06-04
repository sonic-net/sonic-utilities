
from .aboot import AbootBootloader
from .grub import GrubBootloader
from .bmc_uboot import BmcUbootBootloader
from .uboot import UbootBootloader

BOOTLOADERS = [
    AbootBootloader,
    GrubBootloader,
    BmcUbootBootloader,
    UbootBootloader,
]

def get_bootloader():
    for bootloaderCls in BOOTLOADERS:
        if bootloaderCls.detect():
            return bootloaderCls()
    raise RuntimeError('Bootloader could not be detected')

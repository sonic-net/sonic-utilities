
from .aboot import AbootBootloader
from .grub import GrubBootloader
from .uboot import UbootBootloader
from .sonie import SonieGrubBootloader
from .systemd_boot import SystemdBootBootloader
from .null import NullBootloader

# Sonie should be checked first.
BOOTLOADERS = [
    SonieGrubBootloader,
    AbootBootloader,
    GrubBootloader,
    UbootBootloader,
    SystemdBootBootloader,
]

def get_bootloader():
    for bootloaderCls in BOOTLOADERS:
        if bootloaderCls.detect():
            return bootloaderCls()
    return NullBootloader()

import os
from unittest.mock import Mock, call, patch

import sonic_installer.bootloader.bmc_uboot as bmc
import sonic_installer.bootloader.uboot as generic_uboot


IMAGE1 = bmc.IMAGE_PREFIX + '202401.0'
IMAGE2 = bmc.IMAGE_PREFIX + '202402.0'
DIR1 = bmc.IMAGE_DIR_PREFIX + '202401.0'
DIR2 = bmc.IMAGE_DIR_PREFIX + '202402.0'


def base_env():
    return {
        'sonic_version_1': IMAGE1,
        'sonic_version_2': IMAGE2,
        'boot_next': 'run sonic_image_1',
        'boot_once': '',
        'image_dir': DIR1,
        'image_dir_old': DIR2,
        'fit_name': 'sonic-itb.bin',
        'fit_name_old': 'sonic-itb-old.bin',
        'linuxargs': 'console=ttyS0',
        'linuxargs_old': 'console=ttyS1 sonic_fips=1 rootwait',
        'sonic_bootargs': 'console=${baudrate} ${linuxargs}',
        'sonic_bootargs_old': 'console=${baudrate} ${linuxargs_old}',
        'sonic_boot_load': 'load slot1',
        'sonic_boot_load_old': 'load slot2',
    }


def fake_popen(env):
    def _popen(cmd, *args, **kwargs):
        proc = Mock()
        assert cmd[:2] == ['/usr/bin/fw_printenv', '-n']
        value = env.get(cmd[2])
        if value is None:
            proc.returncode = 1
            proc.communicate.return_value = ('', '')
        else:
            proc.returncode = 0
            proc.communicate.return_value = (value + '\n', '')
        return proc

    return _popen


def fake_run_command(env):
    def _run_command(cmd, *args, **kwargs):
        if cmd[0] == 'bash':
            return None
        assert cmd[0] == '/usr/bin/fw_setenv'
        env[cmd[1]] = cmd[2] if len(cmd) > 2 else ''
        return None

    return _run_command


def test_set_default_slot2_updates_default_and_clears_boot_once():
    env = base_env()
    env['boot_once'] = 'run sonic_image_1'

    with patch('sonic_installer.bootloader.bmc_uboot.subprocess.Popen', side_effect=fake_popen(env)), \
         patch('sonic_installer.bootloader.bmc_uboot.run_command', side_effect=fake_run_command(env)):
        assert bmc.BmcUbootBootloader().set_default_image(IMAGE2)

    assert env['boot_next'] == 'run sonic_image_2'
    assert env['boot_once'] == ''


def test_set_next_image_sets_boot_once_without_changing_default():
    env = base_env()

    with patch('sonic_installer.bootloader.bmc_uboot.subprocess.Popen', side_effect=fake_popen(env)), \
         patch('sonic_installer.bootloader.bmc_uboot.run_command', side_effect=fake_run_command(env)):
        assert bmc.BmcUbootBootloader().set_next_image(IMAGE2)

    assert env['boot_once'] == 'run sonic_image_2'
    assert env['boot_next'] == 'run sonic_image_1'


def test_get_next_image_prefers_boot_once_and_returns_unknown_selector_raw():
    env = base_env()
    env['boot_once'] = 'run sonic_image_2'
    bootloader = bmc.BmcUbootBootloader()

    with patch('sonic_installer.bootloader.bmc_uboot.subprocess.Popen', side_effect=fake_popen(env)):
        assert bootloader.get_next_image() == IMAGE2

        env['boot_once'] = 'run unexpected_selector'
        assert bootloader.get_next_image() == 'run unexpected_selector'

        env['boot_once'] = ''
        assert bootloader.get_next_image() == IMAGE1


def test_install_image_runs_installer_and_clears_boot_once():
    env = base_env()
    env['boot_once'] = 'run sonic_image_2'

    with patch('sonic_installer.bootloader.bmc_uboot.run_command', side_effect=fake_run_command(env)) as run_command:
        bmc.BmcUbootBootloader().install_image('/tmp/sonic-bmc.bin')

    assert call(['bash', '/tmp/sonic-bmc.bin']) in run_command.call_args_list
    # Installer owns boot_next; we only drop the stale one-shot.
    assert env['boot_next'] == 'run sonic_image_1'
    assert env['boot_once'] == ''


def test_remove_image_repoints_selectors_clears_slot_and_removes_rootfs():
    env = base_env()
    env['boot_next'] = 'run sonic_image_2'
    env['boot_once'] = 'run sonic_image_2'

    with patch('sonic_installer.bootloader.bmc_uboot.subprocess.Popen', side_effect=fake_popen(env)), \
         patch('sonic_installer.bootloader.bmc_uboot.run_command', side_effect=fake_run_command(env)), \
         patch('sonic_installer.bootloader.bmc_uboot.subprocess.call') as subprocess_call:
        bmc.BmcUbootBootloader().remove_image(IMAGE2)

    assert env['boot_next'] == 'run sonic_image_1'
    assert env['boot_once'] == ''
    assert env['sonic_version_2'] == 'None'
    for var in bmc.BmcUbootBootloader.SLOT_AUX_VARS[2]:
        assert env[var] == ''
    subprocess_call.assert_called_once_with(['rm', '-rf', os.path.join(bmc.HOST_PATH, DIR2)])


def test_set_fips_updates_only_target_slot_linuxargs_token():
    env = base_env()

    with patch('sonic_installer.bootloader.bmc_uboot.subprocess.Popen', side_effect=fake_popen(env)), \
         patch('sonic_installer.bootloader.bmc_uboot.run_command', side_effect=fake_run_command(env)):
        bootloader = bmc.BmcUbootBootloader()
        assert bootloader.get_fips(IMAGE2)
        assert bootloader.set_fips(IMAGE2, False)
        assert not bootloader.get_fips(IMAGE2)

    # Only slot 2's linuxargs_old is rewritten; slot 1's linuxargs is untouched.
    assert env['linuxargs'] == 'console=ttyS0'
    assert env['linuxargs_old'] == 'console=ttyS1 rootwait sonic_fips=0'


def test_detect_uses_bmc_and_generic_uboot_excludes_bmc():
    with patch('sonic_installer.bootloader.bmc_uboot.is_bmc', return_value=True):
        assert bmc.BmcUbootBootloader.detect()

    with patch('sonic_installer.bootloader.uboot.is_bmc', return_value=True):
        assert not generic_uboot.UbootBootloader.detect()

    with patch('sonic_installer.bootloader.uboot.is_bmc', return_value=False), \
         patch('sonic_installer.bootloader.uboot.platform.machine', return_value='aarch64'):
        assert generic_uboot.UbootBootloader.detect()


def test_get_bootloader_prefers_bmc_over_grub_when_both_detect():
    # On a BMC with a stale/accidental /host/grub/grub.cfg present, both the BMC
    # and GRUB detectors would return True. BmcUbootBootloader must win because
    # it is probed first in BOOTLOADERS.
    import sonic_installer.bootloader as loader
    with patch('sonic_installer.bootloader.bmc_uboot.is_bmc', return_value=True), \
         patch('sonic_installer.bootloader.grub.os.path.isfile', return_value=True):
        assert isinstance(loader.get_bootloader(), bmc.BmcUbootBootloader)

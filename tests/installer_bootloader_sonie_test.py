import subprocess
from syslog import LOG_ERR as syslog_err
from unittest.mock import Mock, patch, call

import pytest
from pytest import mark
from sonic_installer.bootloader import sonie
from sonic_installer.common import IMAGE_PREFIX
from sonic_installer.exception import SonicRuntimeException

installed_images = [
    f'{IMAGE_PREFIX}A',
    f'{IMAGE_PREFIX}B',
    'SONIE',
]


@mark.parametrize('var, expected_value',
                  [('bootcount_env', 1), ('bootcount_env', None)])
def test_get_grub_env_var(var, expected_value):
    bootloader = sonie.SonieGrubBootloader()

    with patch('sonic_installer.bootloader.sonie.subprocess.check_output') as mock_cmd:
        mock_cmd.return_value = f'{var}={expected_value}'
        assert bootloader._get_grub_env_var(f'{var}') == expected_value


def test_get_grub_env_var_raises():
    bootloader = sonie.SonieGrubBootloader()

    with patch('sonic_installer.bootloader.sonie.subprocess.check_output') as mock_cmd:
        mock_cmd.side_effect = subprocess.CalledProcessError(1, 'cmd', output='error')
        with pytest.raises(SonicRuntimeException):
            bootloader._get_grub_env_var('exceptional_var')


def test_set_grub_env_var_raises():
    bootloader = sonie.SonieGrubBootloader()

    with patch('sonic_installer.bootloader.sonie.run_command') as mock_cmd:
        mock_cmd.side_effect = subprocess.CalledProcessError(1, 'cmd', output='error')
        with pytest.raises(SonicRuntimeException):
            bootloader._set_grub_env_var('var', 'value')


@patch('sonic_installer.bootloader.sonie.subprocess.check_output')
def test_set_default_image(mock_check_output):
    image = installed_images[0]  # Index 0
    # set_default_image(persist=True)
    # rollback should become 0 (matches index 0)
    # bootcount should become 2
    expected_calls = [
        call(['grub-editenv', '/efi/sonie_env', 'set', 'rollback_env=0']),
        call(['grub-editenv', '/efi/sonie_env', 'set', 'bootcount_env=2']),
        call(['grub-editenv', '/efi/sonie_env', 'set', 'install_env=0']),
        call(['grub-editenv', '/efi/sonie_env', 'set', 'warmboot_env=0'])
    ]
    mock_check_output.return_value = ''

    with patch('sonic_installer.bootloader.sonie.run_command') as mock_cmd:
        bootloader = sonie.SonieGrubBootloader()
        bootloader.get_installed_images = Mock(return_value=installed_images)
        bootloader.set_default_image(image)
        mock_cmd.assert_has_calls(expected_calls)


@patch('sonic_installer.bootloader.sonie.subprocess.check_output')
def test_set_next_image_same_preference(mock_check_output):
    # Current preference A (rollback=0)
    # Target image A (index 0)
    # Should stay rollback=0, bootcount=2
    def _get_grub_env_var(var):
        if var == 'rollback_env':
            return 0
        return 0

    with patch('sonic_installer.bootloader.sonie.run_command') as mock_cmd:
        bootloader = sonie.SonieGrubBootloader()
        bootloader.get_installed_images = Mock(return_value=installed_images)
        bootloader._get_grub_env_var = Mock(side_effect=_get_grub_env_var)

        bootloader.set_next_image(installed_images[0])

        # bootcount=2, no rollback change
        expected_calls = [
             call(['grub-editenv', '/efi/sonie_env', 'set', 'bootcount_env=2']),
             call(['grub-editenv', '/efi/sonie_env', 'set', 'install_env=0']),
             call(['grub-editenv', '/efi/sonie_env', 'set', 'warmboot_env=0'])
        ]
        mock_cmd.assert_has_calls(expected_calls)

        # Verify rollback NOT set
        for c in mock_cmd.call_args_list:
            assert 'rollback_env' not in str(c)


@patch('sonic_installer.bootloader.sonie.subprocess.check_output')
def test_set_next_image_diff_preference(mock_check_output):
    # Current preference A (rollback=0)
    # Target image B (index 1)
    # Should stay rollback=0, bootcount=1 (try secondary once)
    def _get_grub_env_var(var):
        if var == 'rollback_env':
            return 0
        return 0

    with patch('sonic_installer.bootloader.sonie.run_command') as mock_cmd:
        bootloader = sonie.SonieGrubBootloader()
        bootloader.get_installed_images = Mock(return_value=installed_images)
        bootloader._get_grub_env_var = Mock(side_effect=_get_grub_env_var)

        bootloader.set_next_image(installed_images[1])

        # bootcount=1
        expected_calls = [
             call(['grub-editenv', '/efi/sonie_env', 'set', 'bootcount_env=1']),
             call(['grub-editenv', '/efi/sonie_env', 'set', 'install_env=0']),
             call(['grub-editenv', '/efi/sonie_env', 'set', 'warmboot_env=0'])
        ]
        mock_cmd.assert_has_calls(expected_calls)


@mark.parametrize('bootcount, rollback, install, expected_image',
                  [
                   # rollback=0 (Prefer A)
                   (2, 0, 0, installed_images[0]),  # A
                   (1, 0, 0, installed_images[1]),  # B
                   (0, 0, 0, 'SONIE'),

                   # rollback=1 (Prefer B)
                   (2, 1, 0, installed_images[1]),  # B
                   (1, 1, 0, installed_images[0]),  # A
                   (0, 1, 0, 'SONIE'),

                   # Install mode
                   (2, 0, 1, 'SONIE'),
                   (1, 1, 1, 'SONIE'),

                   # None values
                   (None, 0, 0, None),
                  ])
def test_get_next_image_logic(bootcount, rollback, install, expected_image):
    def _get_grub_env_var(var):
        vals = {
            'bootcount_env': bootcount,
            'rollback_env': rollback,
            'install_env': install,
        }
        return vals.get(var)

    bootloader = sonie.SonieGrubBootloader()
    bootloader.get_installed_images = Mock(return_value=installed_images)
    bootloader._get_grub_env_var = Mock(side_effect=_get_grub_env_var)

    assert bootloader.get_next_image() == expected_image


def test_install_image():
    image_path = 'sonic_image.bin'

    with patch('sonic_installer.bootloader.sonie.run_command') as mock_cmd:
        bootloader = sonie.SonieGrubBootloader()
        bootloader._set_grub_env_var = Mock()

        bootloader.install_image(image_path)

        mock_cmd.assert_called_with(['bash', image_path])

        # Updates state
        bootloader._set_grub_env_var.assert_has_calls([
            call('bootcount_env', '2'),
            call('install_env', '0'),
            call('warmboot_env', '0'),
            call('rollback_env', '0')
        ], any_order=True)


def test_detect_true():
    with patch('os.path.exists', return_value=True):
        assert sonie.SonieGrubBootloader.detect() is True


def test_detect_false():
    with patch('os.path.exists', return_value=False):
        assert sonie.SonieGrubBootloader.detect() is False


def test_set_image_to_boot_value_error():
    # Attempting to set an image that is not installed
    bootloader = sonie.SonieGrubBootloader()
    bootloader.get_installed_images = Mock(return_value=installed_images)
    assert bootloader._set_image_to_boot('NON_EXISTENT', True) is False


def test_set_image_to_boot_runtime_error():
    # _set_grub_env_var raises SonicRuntimeException
    bootloader = sonie.SonieGrubBootloader()
    bootloader.get_installed_images = Mock(return_value=installed_images)
    bootloader._set_grub_env_var = Mock(side_effect=SonicRuntimeException)
    assert bootloader._set_image_to_boot(installed_images[0], True) is False


def test_get_next_image_runtime_error():
    bootloader = sonie.SonieGrubBootloader()
    bootloader.get_installed_images = Mock(return_value=installed_images)
    bootloader._get_grub_env_var = Mock(side_effect=SonicRuntimeException)
    assert bootloader.get_next_image() is None


def test_install_image_runtime_error():
    bootloader = sonie.SonieGrubBootloader()
    bootloader._set_grub_env_var = Mock(side_effect=SonicRuntimeException("Test error"))
    with patch('sonic_installer.bootloader.sonie.run_command'):
        with patch('sonic_installer.bootloader.sonie.syslog.syslog') as mock_syslog:
            bootloader.install_image('dummy.bin')
            mock_syslog.assert_called_with(syslog_err, 'Failed to set environment variables: Test error')


def test_install_image_exception():
    bootloader = sonie.SonieGrubBootloader()
    bootloader._set_grub_env_var = Mock(side_effect=Exception("Unknown error"))
    with patch('sonic_installer.bootloader.sonie.run_command'):
        with patch('sonic_installer.bootloader.sonie.syslog.syslog') as mock_syslog:
            bootloader.install_image('dummy.bin')
            mock_syslog.assert_called_with(
                syslog_err,
                'Failed to update bootloader environment variables: Unknown error'
            )


def test_remove_image():
    bootloader = sonie.SonieGrubBootloader()
    bootloader._set_grub_env_var = Mock()
    with patch('sonic_installer.bootloader.grub.GrubBootloader.remove_image') as mock_super_remove:
        bootloader.remove_image('dummy.bin')
        mock_super_remove.assert_called_once_with('dummy.bin')
        bootloader._set_grub_env_var.assert_has_calls([
            call('bootcount_env', '2'),
            call('install_env', '0'),
            call('warmboot_env', '0')
        ], any_order=True)


def test_remove_image_runtime_error():
    bootloader = sonie.SonieGrubBootloader()
    bootloader._set_grub_env_var = Mock(side_effect=SonicRuntimeException("Test error"))
    with patch('sonic_installer.bootloader.grub.GrubBootloader.remove_image'):
        with patch('sonic_installer.bootloader.sonie.syslog.syslog') as mock_syslog:
            bootloader.remove_image('dummy.bin')
            mock_syslog.assert_called_with(syslog_err, 'Failed to set environment variables: Test error')

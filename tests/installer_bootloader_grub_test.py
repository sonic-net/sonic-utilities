import os
import shutil
from unittest.mock import Mock, patch, call

import pytest

# Import test module
import sonic_installer.bootloader.grub as grub

installed_images = [
    f'{grub.IMAGE_PREFIX}expeliarmus-{grub.IMAGE_PREFIX}abcde',
    f'{grub.IMAGE_PREFIX}expeliarmus-abcde',
]


def test_pruning_discovers_installed_images_through_grub(tmp_path, monkeypatch):
    from sonic_installer import bootloader, secure_boot_db

    config_dir = tmp_path / "grub"
    config_dir.mkdir()
    (config_dir / "grub.cfg").write_text("".join(f"menuentry '{image}' {{\n}}\n" for image in installed_images))
    monkeypatch.setattr(grub, "HOST_PATH", str(tmp_path))
    monkeypatch.setattr(bootloader, "BOOTLOADERS", [grub.GrubBootloader])
    monkeypatch.setattr(secure_boot_db, "run", Mock(side_effect=AssertionError("unexpected subprocess")))
    assert secure_boot_db.installed_images() == installed_images


def test_set_default_image():
    image = installed_images[0]
    expected_call = [call(['grub-set-default', '--boot-directory=' + grub.HOST_PATH, str(installed_images.index(image))])]

    with patch("sonic_installer.bootloader.grub.run_command") as mock_cmd:
        bootloader = grub.GrubBootloader()
        bootloader.get_installed_images = Mock(return_value=installed_images)
        bootloader.set_default_image(image)
        mock_cmd.assert_has_calls(expected_call)

def test_set_next_image():
    image = installed_images[0]
    expected_call = [call(['grub-reboot', '--boot-directory=' + grub.HOST_PATH, str(installed_images.index(image))])]

    with patch("sonic_installer.bootloader.grub.run_command") as mock_cmd:
        bootloader = grub.GrubBootloader()
        bootloader.get_installed_images = Mock(return_value=installed_images)
        bootloader.set_next_image(image)
        mock_cmd.assert_has_calls(expected_call)

def test_install_image():
    image_path = 'sonic'
    expected_calls = [
        call(["bash", image_path]),
        call(['grub-set-default', '--boot-directory=' + grub.HOST_PATH, '0'])
    ]
    with patch('sonic_installer.bootloader.grub.run_command') as mock_cmd:
        bootloader = grub.GrubBootloader()
        bootloader.install_image(image_path)
        mock_cmd.assert_has_calls(expected_calls)

@patch("sonic_installer.bootloader.grub.subprocess.call", Mock())
@patch("sonic_installer.bootloader.grub.open")
@patch("sonic_installer.bootloader.grub.run_command")
@patch("sonic_installer.bootloader.grub.re.search")
def test_remove_image(open_patch, run_command_patch, re_search_patch):
    # Constants
    image_path_prefix = os.path.join(grub.HOST_PATH, grub.IMAGE_DIR_PREFIX)
    exp_image_path = f'{image_path_prefix}expeliarmus-{grub.IMAGE_PREFIX}abcde'
    image = f'{grub.IMAGE_PREFIX}expeliarmus-{grub.IMAGE_PREFIX}abcde'

    bootloader = grub.GrubBootloader()

    # Verify rm command was executed with image path
    bootloader.remove_image(image)
    args_list = grub.subprocess.call.call_args_list
    assert len(args_list) > 0

    args, _ = args_list[0]
    assert exp_image_path in args[0]

@patch("sonic_installer.bootloader.grub.HOST_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), 'installer_bootloader_input/_tmp_host'))
def test_set_fips_grub():
    # Prepare the grub.cfg in the _tmp_host folder
    current_path = os.path.dirname(os.path.abspath(__file__))
    grub_config = os.path.join(current_path, 'installer_bootloader_input/host/grub/grub.cfg')
    tmp_host_path = os.path.join(current_path, 'installer_bootloader_input/_tmp_host')
    tmp_grub_path = os.path.join(tmp_host_path, 'grub')
    os.makedirs(tmp_grub_path, exist_ok=True)
    shutil.copy(grub_config, tmp_grub_path)

    image = 'SONiC-OS-internal-202205.57377412-84a9a7f11b'
    bootloader = grub.GrubBootloader()

    # The the default setting
    assert not bootloader.get_fips(image)

    # Test fips enabled
    bootloader.set_fips(image, True)
    assert bootloader.get_fips(image)

    # Test fips disabled
    bootloader.set_fips(image, False)
    assert not bootloader.get_fips(image)

    # Cleanup the _tmp_host folder
    shutil.rmtree(tmp_host_path)


@patch(
    "sonic_installer.bootloader.grub.HOST_PATH",
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'installer_bootloader_input/_tmp_host_efi'
    )
)
def test_set_fips_grub_efi():
    # Prepare the grub.cfg in the _tmp_host folder
    current_path = os.path.dirname(os.path.abspath(__file__))
    grub_config = os.path.join(current_path, 'installer_bootloader_input/host/grub/grub_efi.cfg')
    tmp_host_path = os.path.join(current_path, 'installer_bootloader_input/_tmp_host_efi')
    tmp_grub_path = os.path.join(tmp_host_path, 'grub')
    os.makedirs(tmp_grub_path, exist_ok=True)
    tmp_grub_config = os.path.join(tmp_grub_path, 'grub.cfg')
    shutil.copy(grub_config, tmp_grub_config)

    image = 'SONiC-OS-internal-202205.57377412-84a9a7f11b'
    bootloader = grub.GrubBootloader()

    # The the default setting
    assert not bootloader.get_fips(image)

    # Test fips enabled
    bootloader.set_fips(image, True)
    assert bootloader.get_fips(image)

    # Test fips disabled
    bootloader.set_fips(image, False)
    assert not bootloader.get_fips(image)

    # Cleanup the _tmp_host folder
    shutil.rmtree(tmp_host_path)

def test_verify_image():

    bootloader = grub.GrubBootloader()
    image = f'{grub.IMAGE_PREFIX}expeliarmus-{grub.IMAGE_PREFIX}abcde'
    assert not bootloader.is_secure_upgrade_image_verification_supported()
    # command should fail
    assert not bootloader.verify_image_sign(image)


@pytest.mark.parametrize("success", [False, True])
def test_enroll_image_secure_boot_keys_calls_module(success):
    bootloader = grub.GrubBootloader()
    image = f'{grub.IMAGE_PREFIX}expeliarmus-{grub.IMAGE_PREFIX}abcde'
    with patch.object(grub.secure_boot_enroll_db, "enroll_db_certificate", return_value=success) as enroll, \
            patch.object(grub.subprocess, "run") as subprocess_run:
        assert bootloader.enroll_image_secure_boot_keys(image) is success
        enroll.assert_called_once_with(image)
        subprocess_run.assert_not_called()


@pytest.mark.parametrize("method", ["enroll_image_secure_boot_keys", "image_has_secure_boot_db_auth"])
@pytest.mark.parametrize("error", [
    grub.secure_boot_db.ScriptError("firmware rejected update"),
    OSError("cannot read image"),
    grub.subprocess.SubprocessError("command failed"),
])
def test_secure_boot_enrollment_errors_are_reported(method, error):
    bootloader = grub.GrubBootloader()
    with patch.object(grub.secure_boot_enroll_db, "enroll_db_certificate", side_effect=error), \
            patch("sonic_installer.bootloader.grub.click.echo") as mock_echo:
        assert not getattr(bootloader, method)("sonic.bin")
        mock_echo.assert_called_once_with(f"secure_boot_enroll_db: ERROR: {error}", err=True)


@pytest.mark.parametrize("present", [False, True])
def test_image_has_secure_boot_db_auth_calls_module(present):
    bootloader = grub.GrubBootloader()
    image = f'{grub.IMAGE_PREFIX}expeliarmus-{grub.IMAGE_PREFIX}abcde'
    with patch.object(grub.secure_boot_enroll_db, "enroll_db_certificate", return_value=present) as enroll, \
            patch.object(grub.subprocess, "run") as subprocess_run:
        assert bootloader.image_has_secure_boot_db_auth(image) is present
        enroll.assert_called_once_with(image, check_only=True)
        subprocess_run.assert_not_called()

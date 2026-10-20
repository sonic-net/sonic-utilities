import os
import shlex
import shutil
import sys
from unittest.mock import Mock, patch, call

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


def test_install_image_passes_lock_only_to_installer(tmp_path, monkeypatch):
    from sonic_installer import secure_boot_lock

    monkeypatch.setattr(secure_boot_lock, "LOCK_FILE", tmp_path / "installer.lock")
    with secure_boot_lock.installer_lock() as fd:
        with patch.object(grub, "run_command") as command:
            grub.GrubBootloader().install_image("sonic.bin")
        installer, update_default = command.call_args_list
        assert installer.args == (["bash", "sonic.bin"],)
        assert installer.kwargs["pass_fds"] == (fd,)
        assert installer.kwargs["env"][secure_boot_lock.LOCK_FD_ENV] == str(fd)
        assert update_default == call(["grub-set-default", "--boot-directory=" + grub.HOST_PATH, "0"])


def test_installer_child_pruning_reuses_shared_lock(tmp_path, monkeypatch):
    from sonic_installer import common, secure_boot_lock

    lock_path = tmp_path / "installer.lock"
    marker = tmp_path / "pruned"
    child = """
import fcntl
import sys
from pathlib import Path
from sonic_installer import secure_boot_lock as lock
lock.LOCK_FILE = Path(sys.argv[1])
flock = fcntl.flock
def no_wait(fd, flags):
    assert flags & fcntl.LOCK_NB, "installer child must reuse ownership without waiting"
    return flock(fd, flags)
lock.fcntl.flock = no_wait
with lock.installer_lock():
    Path(sys.argv[2]).write_text("pruned")
"""
    image = tmp_path / "image.sh"
    image.write_text("exec " + shlex.join([sys.executable, "-c", child, str(lock_path), str(marker)]) + "\n")
    monkeypatch.setattr(secure_boot_lock, "LOCK_FILE", lock_path)

    def run(command, **kwargs):
        if command[0] == "bash":
            common.run_command(command, **kwargs)

    monkeypatch.setattr(grub, "run_command", run)
    with secure_boot_lock.installer_lock():
        grub.GrubBootloader().install_image(str(image))
    assert marker.read_text() == "pruned"


def test_enrollment_passes_inherited_lock(tmp_path, monkeypatch):
    from sonic_installer import secure_boot_lock

    monkeypatch.setattr(secure_boot_lock, "LOCK_FILE", tmp_path / "installer.lock")
    with secure_boot_lock.installer_lock() as fd:
        with patch.object(grub.os.path, "exists", return_value=True):
            with patch.object(grub.subprocess, "run", return_value=Mock(returncode=0, stdout=b"", stderr=b"")) as run:
                assert grub.GrubBootloader().enroll_image_secure_boot_keys("sonic.bin")
        assert run.call_args.kwargs["pass_fds"] == (fd,)
        assert run.call_args.kwargs["env"][secure_boot_lock.LOCK_FD_ENV] == str(fd)


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


def test_enroll_image_secure_boot_keys_missing_script():

    bootloader = grub.GrubBootloader()
    image = f'{grub.IMAGE_PREFIX}expeliarmus-{grub.IMAGE_PREFIX}abcde'
    with patch("sonic_installer.bootloader.grub.os.path.exists", return_value=False):
        # When the enrollment script is absent, the method reports failure without raising.
        assert not bootloader.enroll_image_secure_boot_keys(image)


def test_enroll_image_secure_boot_keys_runs_script():

    bootloader = grub.GrubBootloader()
    image = f'{grub.IMAGE_PREFIX}expeliarmus-{grub.IMAGE_PREFIX}abcde'
    completed = Mock()
    completed.returncode = 0
    completed.stdout = b'db certificate enrolled\n'
    with patch("sonic_installer.bootloader.grub.os.path.exists", return_value=True), \
            patch("sonic_installer.bootloader.grub.subprocess.run", return_value=completed) as mock_run:
        assert bootloader.enroll_image_secure_boot_keys(image)
        mock_run.assert_called_once_with(
            ['/usr/local/bin/secure_boot_enroll_db.sh', image], capture_output=True)

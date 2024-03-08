import os
import sys
import pytest
from contextlib import contextmanager
from sonic_installer.main import sonic_installer
from click.testing import CliRunner
from unittest.mock import patch, Mock, call
import sonic_installer.common as sonic_installer_common


def test_run_command():
    with pytest.raises(SystemExit) as e:
        output = sonic_installer_common.run_command([sys.executable, "-c", "import sys; sys.exit(6)"])
    assert e.value.code == 6

@patch("sonic_installer.main.SWAPAllocator")
@patch("sonic_installer.main.get_bootloader")
@patch("sonic_installer.main.run_command_or_raise")
@patch("sonic_installer.main.run_command")
def test_install(run_command, run_command_or_raise, get_bootloader, swap, fs):
    """ This test covers the execution of "sonic-installer install" command. """

    sonic_image_filename = "sonic.bin"
    current_image_version = "image_1"
    new_image_version = "image_2"
    new_image_folder = f"/images/{new_image_version}"
    image_docker_folder = os.path.join(new_image_folder, "docker")
    mounted_image_folder = f"/tmp/image-{new_image_version}-fs"
    dockerd_opts = ["--iptables=false", "--bip=1.1.1.1/24"]

    # Setup mock files needed for our test scenario
    fs.create_file(sonic_image_filename)
    fs.create_dir(image_docker_folder)
    fs.create_dir(os.path.join(mounted_image_folder, "usr/lib/docker/docker.sh"))
    fs.create_file("/var/run/docker.pid", contents="15")
    fs.create_file("/proc/15/cmdline", contents="\x00".join(["dockerd"] + dockerd_opts))

    # Setup bootloader mock
    mock_bootloader = Mock()
    mock_bootloader.get_binary_image_version = Mock(return_value=new_image_version)
    mock_bootloader.get_installed_images = Mock(return_value=[current_image_version])
    mock_bootloader.get_image_path = Mock(return_value=new_image_folder)
    mock_bootloader.verify_image_sign = Mock(return_value=True)
    @contextmanager
    def rootfs_path_mock(path):
        yield mounted_image_folder

    mock_bootloader.get_rootfs_path = rootfs_path_mock
    get_bootloader.return_value=mock_bootloader

    # Invoke CLI command
    runner = CliRunner()
    result = runner.invoke(sonic_installer.commands["install"], [sonic_image_filename, "-y"])
    print(result.output)

    assert result.exit_code == 0
    mock_bootloader_verify_image_sign_fail = mock_bootloader
    mock_bootloader_verify_image_sign_fail.verify_image_sign = Mock(return_value=False)
    get_bootloader.return_value=mock_bootloader_verify_image_sign_fail
    result = runner.invoke(sonic_installer.commands["install"], [sonic_image_filename, "-y"])
    print(result.output)

    assert result.exit_code != 0
    # Assert bootloader install API was called
    mock_bootloader.install_image.assert_called_with(f"./{sonic_image_filename}")
    # Assert all below commands were called, so we ensure that
    #   1. update SONiC environment works
    #   2. package migration works
    expected_call_list = [
        call(["mkdir", "-p", mounted_image_folder]),
        call(["mount", "-t", "squashfs", mounted_image_folder, mounted_image_folder]),
        call(["sonic-cfggen", "-d", "-y", f"{mounted_image_folder}/etc/sonic/sonic_version.yml", "-t", f"{mounted_image_folder}/usr/share/sonic/templates/sonic-environment.j2"]),
        call(["umount", "-r", "-f", mounted_image_folder], raise_exception=True),
        call(["rm", "-rf", mounted_image_folder], raise_exception=True),
        call(["mkdir", "-p", mounted_image_folder]),
        call(["mount", "-t", "squashfs", mounted_image_folder, mounted_image_folder]),
        call(["mkdir", "-p", f"{new_image_folder}/rw"]),
        call(["mkdir", "-p", f"{new_image_folder}/work"]),
        call(["mkdir", "-p", mounted_image_folder]),
        call(["mount", "overlay", "-t", "overlay", "-o", f"rw,relatime,lowerdir={mounted_image_folder},upperdir={new_image_folder}/rw,workdir={new_image_folder}/work", mounted_image_folder]),
        call(["mkdir", "-p", f"{mounted_image_folder}/var/lib/docker"]),
        call(["mount", "--bind", f"{new_image_folder}/docker", f"{mounted_image_folder}/var/lib/docker"]),
        call(["chroot", mounted_image_folder, "mount", "proc", "/proc", "-t", "proc"]),
        call(["chroot", mounted_image_folder, "mount", "sysfs", "/sys", "-t", "sysfs"]),
        call(["cp", f"{mounted_image_folder}/etc/default/docker", f"{mounted_image_folder}/tmp/docker_config_backup"]),
        call(["sh", "-c", f"echo 'DOCKER_OPTS=\"$DOCKER_OPTS {' '.join(dockerd_opts)}\"' >> {mounted_image_folder}/etc/default/docker"]), # dockerd started with added options as host dockerd
        call(["chroot", mounted_image_folder, "/usr/lib/docker/docker.sh", "start"]),
        call(["cp", "/var/lib/sonic-package-manager/packages.json", f"{mounted_image_folder}/tmp/packages.json"]),
        call(["touch", f"{mounted_image_folder}/tmp/docker.sock"]),
        call(["mount", "--bind", "/var/run/docker.sock", f"{mounted_image_folder}/tmp/docker.sock"]),
        call(["cp", f"{mounted_image_folder}/etc/resolv.conf", "/tmp/resolv.conf.backup"]),
        call(["cp", "/etc/resolv.conf", f"{mounted_image_folder}/etc/resolv.conf"]),
        call(["chroot", mounted_image_folder, "sh", "-c", "command -v sonic-package-manager"]),
        call(["chroot", mounted_image_folder, "sonic-package-manager", "migrate", "/tmp/packages.json", "--dockerd-socket", "/tmp/docker.sock", "-y"], capture=False),
        call(["chroot", mounted_image_folder, "/usr/lib/docker/docker.sh", "stop"], raise_exception=False),
        call(["cp", "/tmp/resolv.conf.backup", f"{mounted_image_folder}/etc/resolv.conf"], raise_exception=False),
        call(["umount", "-f", "-R", mounted_image_folder], raise_exception=False),
        call(["umount", "-r", "-f", mounted_image_folder], raise_exception=False),
        call(["rm", "-rf", mounted_image_folder], raise_exception=False),
    ]
    assert run_command_or_raise.call_args_list == expected_call_list

@patch("sonic_installer.main.get_bootloader")
def test_set_fips(get_bootloader):
    """ This test covers the execution of "sonic-installer set-fips/get-fips" command. """

    image = "image_1"
    next_image = "image_2"

    # Setup bootloader mock
    mock_bootloader = Mock()
    mock_bootloader.get_next_image = Mock(return_value=next_image)
    mock_bootloader.get_installed_images = Mock(return_value=[image, next_image])
    mock_bootloader.set_fips = Mock()
    mock_bootloader.get_fips = Mock(return_value=False)
    get_bootloader.return_value=mock_bootloader

    runner = CliRunner()

    # Test set-fips command options: --enable-fips/--disable-fips
    result = runner.invoke(sonic_installer.commands["set-fips"], [next_image, '--enable-fips'])
    assert 'Set FIPS' in result.output
    result = runner.invoke(sonic_installer.commands["set-fips"], ['--disable-fips'])
    assert 'Set FIPS' in result.output

    # Test command get-fips options
    result = runner.invoke(sonic_installer.commands["get-fips"])
    assert "FIPS is disabled" in result.output
    mock_bootloader.get_fips = Mock(return_value=True)
    result = runner.invoke(sonic_installer.commands["get-fips"], [next_image])
    assert "FIPS is enabled" in result.output

@patch("sonic_installer.common.subprocess.Popen")
def test_runtime_exception(mock_popen):
    """ This test covers the "sonic-installer" exception handling. """

    mock_popen.return_value.returncode = 1
    mock_popen.return_value.communicate.return_value = ('Running', 'Failed')

    with pytest.raises(sonic_installer_common.SonicRuntimeException) as sre:
        sonic_installer_common.run_command_or_raise(["test.sh"])

    assert '\nSTDOUT:\nRunning' in sre.value.notes, "Invalid STDOUT"
    assert '\nSTDERR:\nFailed' in sre.value.notes, "Invalid STDERR"

    assert all(v in str(sre.value) for v in ['test.sh', 'Running', 'Failed']), "Invalid message"

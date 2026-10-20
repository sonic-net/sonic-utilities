import os
import subprocess
import sys
import pytest
from contextlib import contextmanager, nullcontext
from sonic_installer.main import sonic_installer
from click.testing import CliRunner
from unittest.mock import patch, Mock, call
import sonic_installer.common as sonic_installer_common
from sonic_installer import secure_boot_db
from sonic_installer import secure_boot_lock


@pytest.fixture(autouse=True)
def installer_lock_file(tmp_path, monkeypatch, request):
    monkeypatch.setattr(secure_boot_lock, "LOCK_FILE", tmp_path / "installer.lock")
    if "fs" in request.fixturenames:
        # fcntl requires real descriptors; filesystem-mocked cases test installer behavior only.
        monkeypatch.setattr(secure_boot_lock, "installer_lock", nullcontext)


@pytest.mark.parametrize("fail_install", [False, True])
def test_install_locks_discovery_enrollment_and_installation(monkeypatch, fail_install):
    import sonic_installer.main as installer

    bootloader = Mock()
    phases = []

    def checked(name, result=None):
        def operation(*args, **kwargs):
            assert secure_boot_lock.current_lock_fd() is not None
            phases.append(name)
            if name == "install" and fail_install:
                raise RuntimeError("installation failed")
            return result
        return operation

    bootloader.get_binary_image_version.return_value = "new-image"
    bootloader.get_installed_images.side_effect = checked("discovery", ["current-image"])
    bootloader.enroll_image_secure_boot_keys.side_effect = checked("enrollment", True)
    bootloader.verify_image_sign.side_effect = checked("verification", True)
    bootloader.install_image.side_effect = checked("install")
    monkeypatch.setattr(installer, "get_bootloader", lambda: bootloader)
    monkeypatch.setattr(installer, "is_secure_boot_pk_enrolled", lambda: False)
    monkeypatch.setattr(installer, "check_image_install_free_disk_space", lambda: True)
    monkeypatch.setattr(installer, "SWAPAllocator", lambda *args: nullcontext())
    monkeypatch.setattr(installer, "run_command", Mock())
    monkeypatch.setattr(installer, "update_sonic_environment", checked("environment"))
    result = CliRunner().invoke(sonic_installer.commands["install"], [
        "sonic.bin", "-y", "--skip_migration", "--skip-package-migration", "--skip-setup-swap",
    ])
    assert (result.exit_code != 0) == fail_install, (result.output, result.exception)
    assert phases == ["discovery", "enrollment", "verification", "install"] + (
        [] if fail_install else ["environment"]
    )
    assert secure_boot_lock.current_lock_fd() is None


def test_pruning_helper_locks_before_image_discovery(monkeypatch):
    import sonic_installer.main as installer

    def checked_images():
        assert secure_boot_lock.current_lock_fd() is not None
        return ["current-image"]

    def checked_prune(*args, **kwargs):
        assert secure_boot_lock.current_lock_fd() is not None
        assert kwargs["images"] == ["current-image"]

    bootloader = Mock()
    bootloader.get_installed_images.side_effect = checked_images
    monkeypatch.setattr(secure_boot_db, "prune_db_certificates", checked_prune)
    installer.prune_stale_db_certs(bootloader)
    bootloader.get_installed_images.assert_called_once()
    assert secure_boot_lock.current_lock_fd() is None


@pytest.mark.parametrize("supported", [False, True])
@patch("sonic_installer.main.os.geteuid", return_value=0)
@patch("sonic_installer.main.get_bootloader")
@patch("sonic_installer.main.secure_boot_db.prune_db_certificates")
def test_remove_calls_python_pruning_directly(prune, get_bootloader, geteuid, supported):
    bootloader = get_bootloader.return_value
    bootloader.get_installed_images.side_effect = [
        ["SONiC-OS-cur", "SONiC-OS-old"], ["SONiC-OS-cur"],
    ]
    bootloader.get_current_image.return_value = "SONiC-OS-cur"
    bootloader.is_secure_upgrade_image_verification_supported.return_value = supported

    def after_removal(*args, **kwargs):
        bootloader.remove_image.assert_called_once_with("SONiC-OS-old")

    prune.side_effect = after_removal
    result = CliRunner().invoke(sonic_installer, ["remove", "-y", "SONiC-OS-old"])
    assert result.exit_code == 0, (result.output, result.exception)
    if supported:
        prune.assert_called_once()
        assert isinstance(prune.call_args.args[0], secure_boot_db.Config)
        assert prune.call_args.kwargs == {"images": ["SONiC-OS-cur"], "auto": True}
    else:
        prune.assert_not_called()


@pytest.mark.parametrize("error", [
    secure_boot_db.ScriptError("invalid authenticated update"),
    OSError("missing utility"),
    subprocess.TimeoutExpired("openssl", 10),
])
@patch("sonic_installer.main.os.geteuid", return_value=0)
@patch("sonic_installer.main.get_bootloader")
@patch("sonic_installer.main.secure_boot_db.prune_db_certificates")
def test_remove_reports_pruning_errors_without_failing_removal(prune, get_bootloader, geteuid, error):
    bootloader = get_bootloader.return_value
    bootloader.get_installed_images.side_effect = [
        ["SONiC-OS-cur", "SONiC-OS-old"], ["SONiC-OS-cur"],
    ]
    bootloader.get_current_image.return_value = "SONiC-OS-cur"
    bootloader.is_secure_upgrade_image_verification_supported.return_value = True
    prune.side_effect = error
    result = CliRunner().invoke(sonic_installer, ["remove", "-y", "SONiC-OS-old"])
    assert result.exit_code == 0, (result.output, result.exception)
    bootloader.remove_image.assert_called_once_with("SONiC-OS-old")
    assert "Secure Boot db prune failed" in result.output
    assert "Verify db before rebooting" in result.output


@pytest.mark.parametrize("old_images", [[], ["SONiC-OS-old1", "SONiC-OS-old2"]])
@patch("sonic_installer.main.os.geteuid", return_value=0)
@patch("sonic_installer.main.get_bootloader")
@patch("sonic_installer.main.secure_boot_db.prune_db_certificates")
def test_cleanup_prunes_once_after_removing_old_images(prune, get_bootloader, geteuid, old_images):
    bootloader = get_bootloader.return_value
    remaining = ["SONiC-OS-cur", "SONiC-OS-next"]
    bootloader.get_installed_images.side_effect = [remaining + old_images, remaining]
    bootloader.get_current_image.return_value = remaining[0]
    bootloader.get_next_image.return_value = remaining[1]
    bootloader.is_secure_upgrade_image_verification_supported.return_value = True
    operations = []
    bootloader.remove_image.side_effect = operations.append
    prune.side_effect = lambda *args, **kwargs: operations.append("prune")
    result = CliRunner().invoke(sonic_installer, ["cleanup", "-y"])
    assert result.exit_code == 0, (result.output, result.exception)
    if old_images:
        assert operations == old_images + ["prune"]
        prune.assert_called_once()
        assert prune.call_args.kwargs == {"images": remaining, "auto": True}
    else:
        assert operations == []
        prune.assert_not_called()


@pytest.mark.parametrize("image", ["SONiC-OS-cur", "SONiC-OS-missing"])
@patch("sonic_installer.main.os.geteuid", return_value=0)
@patch("sonic_installer.main.get_bootloader")
@patch("sonic_installer.main.secure_boot_db.prune_db_certificates")
def test_rejected_removal_does_not_prune(prune, get_bootloader, geteuid, image):
    bootloader = get_bootloader.return_value
    bootloader.get_installed_images.return_value = ["SONiC-OS-cur", "SONiC-OS-old"]
    bootloader.get_current_image.return_value = "SONiC-OS-cur"
    result = CliRunner().invoke(sonic_installer, ["remove", "-y", image])
    assert result.exit_code != 0
    bootloader.remove_image.assert_not_called()
    prune.assert_not_called()


def test_run_command():
    with pytest.raises(SystemExit) as e:
        output = sonic_installer_common.run_command([sys.executable, "-c", "import sys; sys.exit(6)"])
    assert e.value.code == 6


@pytest.mark.parametrize("enrolled", [False, True])
@patch("sonic_installer.main.check_image_install_free_disk_space", return_value=True)
@patch("sonic_installer.main.is_secure_boot_pk_enrolled", return_value=False)
@patch("sonic_installer.main.get_bootloader")
def test_install_verifies_signature_after_enrollment(get_bootloader, pk_enrolled, free_space, enrolled):
    bootloader = get_bootloader.return_value
    bootloader.get_binary_image_version.return_value = "new-image"
    bootloader.get_installed_images.return_value = ["current-image"]
    bootloader.is_secure_upgrade_image_verification_supported.return_value = True
    bootloader.enroll_image_secure_boot_keys.return_value = enrolled
    bootloader.verify_image_sign.return_value = False

    result = CliRunner().invoke(sonic_installer.commands["install"], ["sonic.bin", "-y"])

    assert result.exit_code != 0
    assert "Failed verify image signature" in result.output
    assert ("continuing to signature verification" in result.output) is not enrolled
    bootloader.enroll_image_secure_boot_keys.assert_called_once_with("./sonic.bin")
    bootloader.verify_image_sign.assert_called_once_with("./sonic.bin")
    assert bootloader.method_calls.index(call.enroll_image_secure_boot_keys("./sonic.bin")) < \
        bootloader.method_calls.index(call.verify_image_sign("./sonic.bin"))
    bootloader.install_image.assert_not_called()


@pytest.mark.parametrize("force", [False, True])
@patch("sonic_installer.main.run_command")
@patch("sonic_installer.main.SWAPAllocator")
@patch("sonic_installer.main.is_secure_boot_pk_enrolled", return_value=False)
@patch("sonic_installer.main.get_bootloader")
@patch("sonic_installer.main.check_image_install_free_disk_space", return_value=False)
def test_install_refuses_insufficient_space_before_modifying_state(
        free_space, get_bootloader, pk_enrolled, swap, run_command, force):
    bootloader = get_bootloader.return_value
    bootloader.get_binary_image_version.return_value = "new-image"
    bootloader.get_installed_images.return_value = ["current-image"]
    options = ["sonic.bin", "-y"] + (["-f"] if force else [])
    result = CliRunner().invoke(sonic_installer.commands["install"], options)
    assert result.exit_code != 0
    assert "Insufficient free disk space" in result.output
    free_space.assert_called_once_with()
    bootloader.enroll_image_secure_boot_keys.assert_not_called()
    bootloader.install_image.assert_not_called()
    bootloader.set_default_image.assert_not_called()
    swap.assert_not_called()
    run_command.assert_not_called()


@patch("sonic_installer.main.check_image_install_free_disk_space", return_value=True)
@pytest.mark.parametrize("resolv_conf_symlink_target, expected_resolv_target", [
    ("/run/resolvconf/resolv.conf", "run/resolvconf/resolv.conf"),
    ("../run/resolvconf/resolv.conf", "run/resolvconf/resolv.conf"),
    ("../../run/resolvconf/resolv.conf", "run/resolvconf/resolv.conf"),
    ("resolvconf/resolv.conf", "etc/resolvconf/resolv.conf"),
    ("/../run/resolvconf/resolv.conf", "run/resolvconf/resolv.conf"),
    (None, "etc/resolv.conf"),
])
@patch("sonic_installer.main.SWAPAllocator")
@patch("sonic_installer.main.get_bootloader")
@patch("sonic_installer.main.run_command_or_raise")
@patch("sonic_installer.main.run_command")
def test_install(
    run_command,
    run_command_or_raise,
    get_bootloader,
    swap,
    _,
    fs,
    resolv_conf_symlink_target,
    expected_resolv_target,
):
    """ This test covers the execution of "sonic-installer install" command. """
    sonic_image_filename = "sonic.bin"
    current_image_version = "image_1"
    new_image_version = "image_2"
    new_image_folder = f"/images/{new_image_version}"
    image_docker_folder = os.path.join(new_image_folder, "docker")
    mounted_image_folder = f"/tmp/image-{new_image_version}-fs"
    dockerd_opts = ["--iptables=false", "--bip=1.1.1.1/24", "-H", "fd://"]

    # Setup mock files needed for our test scenario
    fs.create_file(sonic_image_filename)
    fs.create_dir(image_docker_folder)
    fs.create_dir(os.path.join(mounted_image_folder, "usr/lib/docker/docker.sh"))
    fs.create_file("/var/run/docker.pid", contents="15")
    fs.create_file("/proc/15/cmdline", contents="\x00".join(["dockerd"] + dockerd_opts))
    # New image /etc/resolv.conf: dangling symlink or regular file
    if resolv_conf_symlink_target:
        fs.create_symlink(f"{mounted_image_folder}/etc/resolv.conf", resolv_conf_symlink_target)
    else:
        fs.create_file(f"{mounted_image_folder}/etc/resolv.conf")

    # Expect fd:// to be replaced by unix://
    expected_dockerd_opts = [opt if opt != "fd://" else "unix://" for opt in dockerd_opts]

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
        # dockerd started with unix:// instead of fd://
        call([
            "sh", "-c",
            f"echo 'DOCKER_OPTS=\"$DOCKER_OPTS {' '.join(expected_dockerd_opts)}\"' "
            f">> {mounted_image_folder}/etc/default/docker"
        ]),
        call(["chroot", mounted_image_folder, "/usr/lib/docker/docker.sh", "start"]),
        call(["cp", "/var/lib/sonic-package-manager/packages.json", f"{mounted_image_folder}/tmp/packages.json"]),
        call(["mkdir", "-p", "/var/lib/sonic-package-manager/manifests"]),
        call(["cp", "-arf", "/var/lib/sonic-package-manager/manifests",
             f"{mounted_image_folder}/var/lib/sonic-package-manager"]),
        call(["touch", f"{mounted_image_folder}/tmp/docker.sock"]),
        call(["mount", "--bind", "/var/run/docker.sock", f"{mounted_image_folder}/tmp/docker.sock"]),
    ]
    if resolv_conf_symlink_target:
        expected_target = os.path.join(mounted_image_folder, expected_resolv_target)
        expected_call_list += [
            call(["mkdir", "-p", os.path.dirname(expected_target)]),
            call(["cp", "-L", "--remove-destination", "/etc/resolv.conf", expected_target]),
        ]
    else:
        # Regular file overwritten in place
        expected_call_list += [
            call(["cp", "/etc/resolv.conf", f"{mounted_image_folder}/etc/resolv.conf"]),
        ]
    expected_call_list += [
        call(["chroot", mounted_image_folder, "sh", "-c", "command -v sonic-package-manager"]),
        call(["chroot", mounted_image_folder, "sonic-package-manager", "migrate", "/tmp/packages.json", "--dockerd-socket", "/tmp/docker.sock", "-y"], capture=False),
        call(["chroot", mounted_image_folder, "/usr/lib/docker/docker.sh", "stop"], raise_exception=False),
        call(["umount", "-f", "-R", mounted_image_folder], raise_exception=False),
        call(["umount", "-r", "-f", mounted_image_folder], raise_exception=False),
        call(["rm", "-rf", mounted_image_folder], raise_exception=False),
    ]
    assert run_command_or_raise.call_args_list == expected_call_list


@patch("sonic_installer.main.get_bootloader")
@patch("sonic_installer.main.secure_boot_keys.update_secure_boot_key")
@patch("sonic_installer.main.run_command")
@patch("sonic_installer.main.is_secure_boot_pk_enrolled", return_value=True)
def test_install_remove_pk(pk_enrolled, run_command, update_key, get_bootloader, fs):
    sonic_image_filename = "sonic.bin"
    image_version = "image_1"
    auth_dir = "/secure-boot-empty-keys"
    kek_auth = os.path.join(auth_dir, "remove-all-kek.auth")
    pk_auth = os.path.join(auth_dir, "remove-all-pk.auth")

    fs.create_file(sonic_image_filename)
    fs.create_file(kek_auth)
    fs.create_file(pk_auth)

    mock_bootloader = Mock()
    mock_bootloader.get_binary_image_version.return_value = image_version
    mock_bootloader.get_installed_images.return_value = [image_version]
    mock_bootloader.set_default_image.return_value = True
    mock_bootloader.image_has_secure_boot_db_auth.return_value = False
    get_bootloader.return_value = mock_bootloader

    runner = CliRunner()
    result = runner.invoke(
        sonic_installer.commands["install"],
        [sonic_image_filename, "-y", f"--remove-pk={auth_dir}"],
    )

    assert result.exit_code == 0
    assert update_key.call_args_list == [
        call("KEK", kek_auth),
        call("PK", pk_auth),
    ]


@pytest.mark.parametrize("failed_key", ["KEK", "PK"])
@pytest.mark.parametrize("error", [
    secure_boot_db.ScriptError("firmware rejected update"),
    OSError("missing efi-updatevar"),
    subprocess.TimeoutExpired("efi-updatevar", 600),
])
@patch("sonic_installer.main.get_bootloader")
@patch("sonic_installer.main.run_command")
@patch("sonic_installer.main.is_secure_boot_pk_enrolled", return_value=True)
@patch("sonic_installer.main.secure_boot_keys.update_secure_boot_key")
def test_install_stops_when_key_removal_fails(
        update_key, pk_enrolled, run_command, get_bootloader, fs, failed_key, error):
    auth_dir = "/secure-boot-empty-keys"
    kek_auth = os.path.join(auth_dir, "remove-all-kek.auth")
    pk_auth = os.path.join(auth_dir, "remove-all-pk.auth")
    fs.create_file("sonic.bin")
    fs.create_file(kek_auth)
    fs.create_file(pk_auth)
    bootloader = get_bootloader.return_value
    bootloader.get_binary_image_version.return_value = "installed-image"
    bootloader.get_installed_images.return_value = ["installed-image"]
    bootloader.set_default_image.return_value = True
    update_key.side_effect = [error] if failed_key == "KEK" else [None, error]

    result = CliRunner().invoke(
        sonic_installer.commands["install"], ["sonic.bin", "-y", f"--remove-pk={auth_dir}"],
    )

    assert result.exit_code != 0
    assert isinstance(result.exception, sonic_installer_common.SonicRuntimeException)
    assert f"Failed to remove UEFI Secure Boot {failed_key}" in result.output
    assert "Done" not in result.output
    expected = [call("KEK", kek_auth)]
    if failed_key == "PK":
        expected.append(call("PK", pk_auth))
    assert update_key.call_args_list == expected
    run_command.assert_not_called()


@patch("sonic_installer.main.get_bootloader")
@patch("sonic_installer.main.is_secure_boot_pk_enrolled", return_value=True)
def test_install_rejects_image_without_db_auth_when_pk_enrolled(pk_enrolled, get_bootloader, fs):
    sonic_image_filename = "sonic.bin"
    image_version = "image_1"
    fs.create_file(sonic_image_filename)

    mock_bootloader = Mock()
    mock_bootloader.get_binary_image_version.return_value = image_version
    mock_bootloader.image_has_secure_boot_db_auth.return_value = False
    get_bootloader.return_value = mock_bootloader

    runner = CliRunner()
    result = runner.invoke(
        sonic_installer.commands["install"],
        [sonic_image_filename, "-y"],
    )

    assert result.exit_code != 0
    assert "device has an enrolled UEFI Secure Boot PK" in result.output
    assert "image does not contain boot/DB.auth" in result.output
    mock_bootloader.install_image.assert_not_called()


@patch("sonic_installer.main.run_command")
@patch("sonic_installer.main.get_bootloader")
@patch("sonic_installer.main.is_secure_boot_pk_enrolled", return_value=True)
@patch("sonic_installer.main.check_image_install_free_disk_space", return_value=False)
def test_install_accepts_image_with_db_auth_when_pk_enrolled(
        free_space, pk_enrolled, get_bootloader, run_command, fs):
    sonic_image_filename = "sonic.bin"
    image_version = "image_1"
    fs.create_file(sonic_image_filename)

    mock_bootloader = Mock()
    mock_bootloader.get_binary_image_version.return_value = image_version
    mock_bootloader.image_has_secure_boot_db_auth.return_value = True
    mock_bootloader.get_installed_images.return_value = [image_version]
    mock_bootloader.set_default_image.return_value = True
    get_bootloader.return_value = mock_bootloader

    runner = CliRunner()
    result = runner.invoke(
        sonic_installer.commands["install"],
        [sonic_image_filename, "-y"],
    )

    assert result.exit_code == 0
    mock_bootloader.set_default_image.assert_called_once_with(image_version)
    free_space.assert_not_called()


@patch("sonic_installer.main.get_bootloader")
def test_install_remove_pk_requires_both_auth_files(get_bootloader, fs):
    auth_dir = "/secure-boot-empty-keys"
    fs.create_dir(auth_dir)
    fs.create_file(os.path.join(auth_dir, "remove-all-kek.auth"))

    runner = CliRunner()
    result = runner.invoke(
        sonic_installer.commands["install"],
        ["sonic.bin", "-y", f"--remove-pk={auth_dir}"],
    )

    assert result.exit_code != 0
    assert "directory must contain remove-all-kek.auth and remove-all-pk.auth" in result.output
    get_bootloader.assert_not_called()


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


@patch("sonic_installer.main.check_image_install_free_disk_space", return_value=True)
@patch("sonic_installer.main.SWAPAllocator")
@patch("sonic_installer.main.get_bootloader")
@patch("sonic_installer.main.run_command_or_raise")
@patch("sonic_installer.main.run_command")
@patch('shutil.rmtree')
def test_install_failed(
    rmtree,
    run_command,
    run_command_or_raise,
    get_bootloader,
    swap,
    _,
    fs,
):
    """ This test covers the "sonic-installer" install image failed handling. """

    sonic_image_filename = "sonic.bin"
    current_image_version = "image_1"
    new_image_version = "image_2"
    new_image_folder = f"/images/{new_image_version}"
    image_docker_folder = os.path.join(new_image_folder, "docker")
    mounted_image_folder = f"/tmp/image-{new_image_version}-fs"
    dockerd_opts = ["--iptables=false", "--bip=1.1.1.1/24", "-H", "fd://"]

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

    def mock_install_image(arg):
        sys.exit(1)

    mock_bootloader.install_image = mock_install_image

    @contextmanager
    def rootfs_path_mock(path):
        yield mounted_image_folder

    mock_bootloader.get_rootfs_path = rootfs_path_mock

    get_bootloader.return_value = mock_bootloader

    # Invoke CLI command
    runner = CliRunner()
    result = runner.invoke(sonic_installer.commands["install"], [sonic_image_filename, "-y"])
    print(result.output)

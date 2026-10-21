import os
import subprocess
import sys
import pytest
from contextlib import contextmanager, nullcontext
from sonic_installer.main import (
    sonic_installer,
    SWAP_MEM_SIZE_DEFAULT,
    TOTAL_MEM_THRESHOLD_DEFAULT,
)
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


def test_pruning_helper_locks_before_image_discovery(monkeypatch, tmp_path):
    import sonic_installer.main as installer

    monkeypatch.setenv("SONIC_EFIVARS_DIR", str(tmp_path))
    (tmp_path / f"SecureBoot-{secure_boot_db.EFI_GLOBAL_VARIABLE_GUID}").write_bytes(
        b"\x06\x00\x00\x00\x01"
    )

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


def test_run_command():
    with pytest.raises(SystemExit) as e:
        output = sonic_installer_common.run_command([sys.executable, "-c", "import sys; sys.exit(6)"])
    assert e.value.code == 6


@patch("sonic_installer.main.check_image_install_free_disk_space", return_value=True)
@pytest.mark.parametrize("resolv_conf_symlink_target", [
    "/run/resolvconf/resolv.conf",       # absolute symlink
    "../run/resolvconf/resolv.conf",     # relative symlink (resolvconf package default)
    "../../run/resolvconf/resolv.conf",  # excess ".." clamps at the chroot root
    None,                                # regular file
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
        # Symlink target resolves to /run/resolvconf/resolv.conf inside the chroot
        expected_call_list += [
            call(["mkdir", "-p", f"{mounted_image_folder}/run/resolvconf"]),
            call(["cp", "-L", "--remove-destination", "/etc/resolv.conf",
                  f"{mounted_image_folder}/run/resolvconf/resolv.conf"]),
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


def setup_swap_install_mocks(fs, get_bootloader):
    """Set up the minimum mocks for an install to reach SWAPAllocator."""
    sonic_image_filename = "sonic.bin"
    new_image_version = "image_2"
    new_image_folder = f"/images/{new_image_version}"

    fs.create_file(sonic_image_filename)
    fs.create_dir(os.path.join(new_image_folder, "docker"))

    mock_bootloader = Mock()
    mock_bootloader.get_binary_image_version = Mock(return_value=new_image_version)
    mock_bootloader.get_installed_images = Mock(return_value=["image_1"])
    mock_bootloader.get_image_path = Mock(return_value=new_image_folder)
    mock_bootloader.verify_image_sign = Mock(return_value=True)
    mock_bootloader.install_image = Mock(side_effect=lambda arg: sys.exit(1))
    get_bootloader.return_value = mock_bootloader

    return sonic_image_filename


@patch("sonic_installer.main.check_image_install_free_disk_space", return_value=True)
@patch("sonic_installer.main.resolve_total_mem_threshold")
@patch("sonic_installer.main.resolve_swap_mem_size")
@patch("sonic_installer.main.SWAPAllocator")
@patch("sonic_installer.main.get_bootloader")
@patch("sonic_installer.main.run_command_or_raise")
@patch("sonic_installer.main.run_command")
@patch('shutil.rmtree')
def test_install_skip_setup_swap_does_not_resolve(
    rmtree,
    run_command,
    run_command_or_raise,
    get_bootloader,
    swap,
    resolve_swap_mem_size,
    resolve_total_mem_threshold,
    _,
    fs,
):
    """--skip-setup-swap must not read platform.json at all."""
    sonic_image_filename = setup_swap_install_mocks(fs, get_bootloader)

    runner = CliRunner()
    runner.invoke(
        sonic_installer.commands["install"],
        [sonic_image_filename, "-y", "--skip-setup-swap"],
    )

    resolve_swap_mem_size.assert_not_called()
    resolve_total_mem_threshold.assert_not_called()
    # The click defaults are passed through untouched, as before this change.
    swap.assert_called_with(False, SWAP_MEM_SIZE_DEFAULT, TOTAL_MEM_THRESHOLD_DEFAULT, 1200)


@patch("sonic_installer.main.check_image_install_free_disk_space", return_value=True)
@patch("sonic_installer.main.resolve_total_mem_threshold")
@patch("sonic_installer.main.resolve_swap_mem_size")
@patch("sonic_installer.main.SWAPAllocator")
@patch("sonic_installer.main.get_bootloader")
@patch("sonic_installer.main.run_command_or_raise")
@patch("sonic_installer.main.run_command")
@patch('shutil.rmtree')
def test_install_uses_resolved_swap_values(
    rmtree,
    run_command,
    run_command_or_raise,
    get_bootloader,
    swap,
    resolve_swap_mem_size,
    resolve_total_mem_threshold,
    _,
    fs,
):
    """The resolved values are what SWAPAllocator is given."""
    sonic_image_filename = setup_swap_install_mocks(fs, get_bootloader)
    resolve_swap_mem_size.return_value = 3072
    resolve_total_mem_threshold.return_value = 8192

    runner = CliRunner()
    runner.invoke(sonic_installer.commands["install"], [sonic_image_filename, "-y"])

    resolve_swap_mem_size.assert_called_once_with(
        SWAP_MEM_SIZE_DEFAULT, SWAP_MEM_SIZE_DEFAULT)
    resolve_total_mem_threshold.assert_called_once_with(
        TOTAL_MEM_THRESHOLD_DEFAULT, TOTAL_MEM_THRESHOLD_DEFAULT)
    swap.assert_called_with(True, 3072, 8192, 1200)


def _remove_with_prune(state="enabled", error=None, efivars_error=None):
    bootloader = Mock()
    bootloader.get_installed_images.side_effect = [["cur", "old"], ["cur"]]
    bootloader.get_current_image.return_value = "cur"

    def after_removal(*args, **kwargs):
        bootloader.remove_image.assert_called_once_with("old")
        if error is not None:
            raise error
        return 0

    with patch("sonic_installer.main.get_bootloader", return_value=bootloader), \
            patch("os.geteuid", return_value=0), \
            patch("sonic_installer.main.subprocess.run", side_effect=AssertionError("unexpected subprocess")), \
            patch("sonic_installer.main.secure_boot_db.ensure_efivars",
                  side_effect=efivars_error) as ensure_efivars, \
            patch("sonic_installer.main.secure_boot_db.secure_boot_state", return_value=state) as boot_state, \
            patch("sonic_installer.main.secure_boot_db.prune_db_certificates", side_effect=after_removal) as prune:
        result = CliRunner().invoke(sonic_installer, ["remove", "-y", "old"])
    assert result.exit_code == 0, (result.output, result.exception)
    bootloader.remove_image.assert_called_once_with("old")
    bootloader.is_secure_upgrade_image_verification_supported.assert_not_called()
    ensure_efivars.assert_called_once()
    if efivars_error is None:
        boot_state.assert_called_once_with(ensure_efivars.call_args.args[0])
    else:
        boot_state.assert_not_called()
    if prune.called:
        assert prune.call_args.args[0] is ensure_efivars.call_args.args[0]
    return result, prune


def test_remove_prunes_db_certs_without_flag():
    _, prune = _remove_with_prune()
    prune.assert_called_once()
    assert isinstance(prune.call_args.args[0], secure_boot_db.Config)
    assert prune.call_args.kwargs == {"images": ["cur"], "auto": True}


@pytest.mark.parametrize("error", [
    secure_boot_db.ScriptError("invalid authenticated update"),
    OSError("missing utility"),
    subprocess.TimeoutExpired("openssl", 600),
])
def test_remove_warns_when_prune_fails(error):
    result, prune = _remove_with_prune(error=error)
    prune.assert_called_once()
    assert "prune failed" in result.output
    assert str(error) in result.output
    assert "Verify db before rebooting" in result.output


@pytest.mark.parametrize("state", ["disabled", "unknown"])
def test_remove_skips_prune_when_secure_boot_not_enabled(state):
    result, prune = _remove_with_prune(state=state)
    prune.assert_not_called()
    if state == "unknown":
        assert "Secure Boot state is unknown" in result.output
    else:
        assert "Warning:" not in result.output


def test_remove_warns_when_efivars_unavailable():
    result, prune = _remove_with_prune(efivars_error=secure_boot_db.ScriptError("efivars unavailable"))
    prune.assert_not_called()
    assert "efivars unavailable" in result.output
    assert "prune failed" in result.output


@pytest.mark.parametrize("old_images", [[], ["old1", "old2"]])
def test_cleanup_prunes_only_when_images_were_removed(old_images):
    bootloader = Mock()
    bootloader.get_installed_images.side_effect = [["cur", "next"] + old_images, ["cur", "next"]]
    bootloader.get_current_image.return_value = "cur"
    bootloader.get_next_image.return_value = "next"
    operations = []
    bootloader.remove_image.side_effect = operations.append
    with patch("sonic_installer.main.get_bootloader", return_value=bootloader), \
            patch("os.geteuid", return_value=0), \
            patch("sonic_installer.main.secure_boot_db.ensure_efivars"), \
            patch("sonic_installer.main.secure_boot_db.secure_boot_state", return_value="enabled"), \
            patch("sonic_installer.main.secure_boot_db.prune_db_certificates",
                  side_effect=lambda *args, **kwargs: operations.append("prune")) as prune:
        result = CliRunner().invoke(sonic_installer, ["cleanup", "-y"])
    assert result.exit_code == 0, (result.output, result.exception)
    if old_images:
        assert operations == old_images + ["prune"]
        prune.assert_called_once()
        assert prune.call_args.kwargs == {"images": ["cur", "next"], "auto": True}
    else:
        assert operations == []
        prune.assert_not_called()


@pytest.mark.parametrize("image", ["cur", "missing"])
def test_rejected_removal_does_not_prune(image):
    bootloader = Mock()
    bootloader.get_installed_images.return_value = ["cur", "old"]
    bootloader.get_current_image.return_value = "cur"
    with patch("sonic_installer.main.get_bootloader", return_value=bootloader), \
            patch("os.geteuid", return_value=0), \
            patch("sonic_installer.main.secure_boot_db.prune_db_certificates") as prune:
        result = CliRunner().invoke(sonic_installer, ["remove", "-y", image])
    assert result.exit_code != 0
    bootloader.remove_image.assert_not_called()
    prune.assert_not_called()

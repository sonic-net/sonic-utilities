import os
from unittest.mock import Mock, patch, call

# Import test module
import sonic_installer.bootloader.uboot as uboot

# Constants
installed_images = [
    f'{uboot.IMAGE_PREFIX}expeliarmus-{uboot.IMAGE_PREFIX}abcde',
    f'{uboot.IMAGE_PREFIX}expeliarmus-abcde',
]

# Helper: map an image to the slot it lives in. By convention in these
# tests, installed_images[0] is slot 1 and installed_images[1] is slot 2.
_slot_of = {installed_images[0]: 1, installed_images[1]: 2}


class MockProc():
    commandline = "linuxargs="
    def communicate():
        return commandline, None

def mock_run_command(cmd):
    MockProc.commandline = cmd

@patch('sonic_installer.bootloader.uboot.run_command')
def test_set_default_image(mock_run_cmd):
    next_cmd = ['/usr/bin/fw_setenv', 'boot_next']
    clear_once = call(['/usr/bin/fw_setenv', 'boot_once', ''])
    image0, image1 = ['run sonic_image_1'], ['run sonic_image_2']
    expected_call0 = [call(next_cmd + image0), clear_once]
    expected_call1 = [call(next_cmd + image1), clear_once]

    bootloader = uboot.UbootBootloader()
    bootloader._get_image_slot = Mock(side_effect=_slot_of.get)
    bootloader.set_default_image(installed_images[0])
    assert mock_run_cmd.call_args_list == expected_call0

    mock_run_cmd.call_args_list = []
    bootloader.set_default_image(installed_images[1])
    assert mock_run_cmd.call_args_list == expected_call1


@patch('sonic_installer.bootloader.uboot.run_command')
def test_set_default_image_only_slot_2_populated(mock_run_cmd):
    """Regression for the substring + list-index bug. State: slot 1
    empty, sole image lives in slot 2 -> set_default_image must write
    ``run sonic_image_2`` (not ``sonic_image_1``, which would point
    boot_next at the empty slot and brick the box)."""
    bootloader = uboot.UbootBootloader()
    bootloader._get_image_slot = Mock(return_value=2)

    bootloader.set_default_image(installed_images[1])
    assert mock_run_cmd.call_args_list == [
        call(['/usr/bin/fw_setenv', 'boot_next', 'run sonic_image_2']),
        call(['/usr/bin/fw_setenv', 'boot_once', ''])]


@patch('sonic_installer.bootloader.uboot.run_command')
def test_set_next_image(mock_run_cmd):
    subcmd = ['/usr/bin/fw_setenv', 'boot_once']
    image0, image1 = ['run sonic_image_1'], ['run sonic_image_2']
    expected_call0, expected_call1 = [call(subcmd + image0)], [call(subcmd + image1)]

    bootloader = uboot.UbootBootloader()
    bootloader._get_image_slot = Mock(side_effect=_slot_of.get)
    bootloader.set_next_image(installed_images[0])
    assert mock_run_cmd.call_args_list == expected_call0

    mock_run_cmd.call_args_list = []
    bootloader.set_next_image(installed_images[1])
    assert mock_run_cmd.call_args_list == expected_call1


@patch('sonic_installer.bootloader.uboot.run_command')
def test_set_next_image_only_slot_2_populated(mock_run_cmd):
    """Same regression as set_default — slot 1 empty, image in slot 2
    must write ``run sonic_image_2`` into boot_once, not sonic_image_1."""
    bootloader = uboot.UbootBootloader()
    bootloader._get_image_slot = Mock(return_value=2)

    bootloader.set_next_image(installed_images[1])
    assert mock_run_cmd.call_args_list == [
        call(['/usr/bin/fw_setenv', 'boot_once', 'run sonic_image_2'])]


@patch('sonic_installer.bootloader.uboot.run_command')
def test_set_default_image_unknown_returns_false(mock_run_cmd):
    """Unknown image -> False, no fw_setenv call."""
    bootloader = uboot.UbootBootloader()
    bootloader._get_image_slot = Mock(return_value=None)

    assert bootloader.set_default_image('SONiC-OS-ghost') is False
    mock_run_cmd.assert_not_called()


@patch('sonic_installer.bootloader.uboot.run_command')
def test_set_next_image_unknown_returns_false(mock_run_cmd):
    """Unknown image -> False, no fw_setenv call."""
    bootloader = uboot.UbootBootloader()
    bootloader._get_image_slot = Mock(return_value=None)

    assert bootloader.set_next_image('SONiC-OS-ghost') is False
    mock_run_cmd.assert_not_called()


@patch("sonic_installer.bootloader.uboot.run_command")
def test_install_image(mock_run_cmd):
    image_path = 'sonic_image'
    expected_call = [
        call(['bash', image_path]),
        call(['/usr/bin/fw_setenv', 'boot_once', '']),
    ]

    bootloader = uboot.UbootBootloader()
    bootloader.install_image(image_path)
    assert mock_run_cmd.call_args_list == expected_call


def _mock_boot_once_popen(boot_once_value):
    """Return a Popen stub that replies to ``fw_printenv -n boot_once``
    with ``boot_once_value`` and returncode 0."""
    def factory(cmd, *args, **kwargs):
        proc = Mock()
        proc.communicate.return_value = (boot_once_value, None)
        proc.returncode = 0
        return proc
    return factory


@patch("sonic_installer.bootloader.uboot.subprocess.Popen")
@patch("sonic_installer.bootloader.uboot.subprocess.call", Mock())
@patch("sonic_installer.bootloader.uboot.run_command")
def test_remove_image(run_command_patch, popen_patch):
    # Constants
    image_path_prefix = os.path.join(uboot.HOST_PATH, uboot.IMAGE_DIR_PREFIX)
    exp_image_path = [
        f'{image_path_prefix}expeliarmus-{uboot.IMAGE_PREFIX}abcde',
        f'{image_path_prefix}expeliarmus-abcde'
    ]
    # boot_once empty -> conditional clear must NOT fire
    popen_patch.side_effect = _mock_boot_once_popen("")

    bootloader = uboot.UbootBootloader()
    bootloader._get_image_slot = Mock(side_effect=_slot_of.get)

    # Removing the slot-1 image: boot_next should flip to slot 2,
    # sonic_version_1 -> NONE, /host/image-<slot1>/ is rm -rf'd.
    bootloader.remove_image(installed_images[0])
    assert call(['/usr/bin/fw_setenv', 'boot_next', 'run sonic_image_2']) \
        in run_command_patch.call_args_list
    assert call(['/usr/bin/fw_setenv', 'sonic_version_1', 'NONE']) \
        in run_command_patch.call_args_list
    # boot_once was empty — it must NOT have been written
    assert call(['/usr/bin/fw_setenv', 'boot_once', '']) \
        not in run_command_patch.call_args_list

    args_list = uboot.subprocess.call.call_args_list
    assert len(args_list) > 0

    args, _ = args_list[0]
    assert exp_image_path[0] in args[0]

    uboot.subprocess.call.call_args_list = []
    run_command_patch.reset_mock()

    # Removing the slot-2 image: boot_next flips to slot 1, sonic_version_2 -> NONE.
    bootloader.remove_image(installed_images[1])
    assert call(['/usr/bin/fw_setenv', 'boot_next', 'run sonic_image_1']) \
        in run_command_patch.call_args_list
    assert call(['/usr/bin/fw_setenv', 'sonic_version_2', 'NONE']) \
        in run_command_patch.call_args_list

    args_list = uboot.subprocess.call.call_args_list
    assert len(args_list) > 0

    args, _ = args_list[0]
    assert exp_image_path[1] in args[0]


@patch("sonic_installer.bootloader.uboot.subprocess.Popen")
@patch("sonic_installer.bootloader.uboot.subprocess.call", Mock())
@patch("sonic_installer.bootloader.uboot.run_command")
def test_remove_image_clears_boot_once_pointing_at_removed_slot(
        run_command_patch, popen_patch):
    """Regression: if boot_once points at the slot being removed, remove_image
    must clear boot_once — otherwise the next reboot runs
    'run sonic_image_<removed>' into stale / empty pointers and can brick."""
    popen_patch.side_effect = _mock_boot_once_popen("run sonic_image_1")

    bootloader = uboot.UbootBootloader()
    bootloader._get_image_slot = Mock(return_value=1)

    bootloader.remove_image(installed_images[0])
    assert call(['/usr/bin/fw_setenv', 'boot_once', '']) \
        in run_command_patch.call_args_list


@patch("sonic_installer.bootloader.uboot.subprocess.Popen")
@patch("sonic_installer.bootloader.uboot.subprocess.call", Mock())
@patch("sonic_installer.bootloader.uboot.run_command")
def test_remove_image_preserves_boot_once_pointing_at_other_slot(
        run_command_patch, popen_patch):
    """Complementary: if boot_once points at the slot that is NOT being
    removed (i.e. will still be bootable), leave it alone."""
    popen_patch.side_effect = _mock_boot_once_popen("run sonic_image_2")

    bootloader = uboot.UbootBootloader()
    bootloader._get_image_slot = Mock(return_value=1)  # removing slot 1

    bootloader.remove_image(installed_images[0])
    assert call(['/usr/bin/fw_setenv', 'boot_once', '']) \
        not in run_command_patch.call_args_list


@patch("sonic_installer.bootloader.uboot.subprocess.Popen")
@patch("sonic_installer.bootloader.uboot.subprocess.call", Mock())
@patch("sonic_installer.bootloader.uboot.run_command")
def test_remove_image_clears_slot_aux_vars(run_command_patch, popen_patch):
    """Both sides of every pair exist -> every slot-1 var is cleared."""
    popen_patch.side_effect = _mock_boot_once_popen("present")

    bootloader = uboot.UbootBootloader()
    bootloader._get_image_slot = Mock(return_value=1)

    bootloader.remove_image(installed_images[0])

    for pair in uboot.UbootBootloader.SLOT_AUX_VAR_PAIRS:
        target = pair[0]  # slot-1 name
        assert call(['/usr/bin/fw_setenv', target, '']) \
            in run_command_patch.call_args_list, \
            f"slot-1 aux var {target!r} should have been cleared"


@patch("sonic_installer.bootloader.uboot.subprocess.Popen")
@patch("sonic_installer.bootloader.uboot.subprocess.call", Mock())
@patch("sonic_installer.bootloader.uboot.run_command")
def test_remove_image_preserves_linuxargs(run_command_patch, popen_patch):
    """Regression: set_fips()/get_fips() own `linuxargs` as a slot-agnostic
    kernel cmdline (they persist sonic_fips= into it regardless of slot).
    remove_image must NOT clear it even when both `linuxargs` and
    `linuxargs_old` are present -- doing so would wipe the surviving image's
    boot args / FIPS setting. Guarded by keeping linuxargs out of the table."""
    # Every fw_printenv var reads as present (rc 0), so the only thing
    # keeping linuxargs from being cleared is its absence from the table.
    popen_patch.side_effect = _mock_boot_once_popen("present")

    bootloader = uboot.UbootBootloader()
    bootloader._get_image_slot = Mock(return_value=1)

    bootloader.remove_image(installed_images[0])

    assert call(['/usr/bin/fw_setenv', 'linuxargs', '']) \
        not in run_command_patch.call_args_list, \
        "linuxargs must not be cleared on remove (owned by set_fips/get_fips)"


@patch("sonic_installer.bootloader.uboot.subprocess.Popen")
@patch("sonic_installer.bootloader.uboot.subprocess.call", Mock())
@patch("sonic_installer.bootloader.uboot.run_command")
def test_remove_image_skips_absent_aux_vars(run_command_patch, popen_patch):
    """Aux vars absent -> pair-check fails -> no clear."""
    def fake_popen(cmd, *args, **kwargs):
        proc = Mock()
        var = cmd[-1]
        if var == "boot_once":
            proc.communicate.return_value = ("", None)
            proc.returncode = 0
        else:
            proc.communicate.return_value = ("", None)
            proc.returncode = 1
        return proc
    popen_patch.side_effect = fake_popen

    bootloader = uboot.UbootBootloader()
    bootloader._get_image_slot = Mock(return_value=2)

    bootloader.remove_image(installed_images[1])

    for pair in uboot.UbootBootloader.SLOT_AUX_VAR_PAIRS:
        target = pair[1]  # slot-2 name
        assert call(['/usr/bin/fw_setenv', target, '']) \
            not in run_command_patch.call_args_list, \
            f"absent aux var {target!r} should not have been written"


def _fake_env_popen(env):
    """Build a subprocess.Popen side_effect that fakes
    ``fw_printenv -n <var>`` against the given env dict."""
    def factory(cmd, *args, **kwargs):
        var = cmd[-1]
        proc = Mock()
        proc.communicate.return_value = (env.get(var, ""), None)
        proc.returncode = 0 if var in env else 1
        return proc
    return factory


@patch("sonic_installer.bootloader.uboot.subprocess.Popen")
@patch("sonic_installer.bootloader.uboot.run_command")
def test_get_next_image(run_command_patch, popen_patch):
    """Round-trip: set_default_image writes boot_next; get_next_image
    reports that slot's image."""
    env = {
        "sonic_version_1": installed_images[0],
        "sonic_version_2": installed_images[1],
        "boot_once": "",
        "boot_next": "",
    }
    popen_patch.side_effect = _fake_env_popen(env)

    def mock_run_command(cmd):
        if len(cmd) >= 3 and cmd[0] == '/usr/bin/fw_setenv':
            env[cmd[1]] = cmd[2]
    run_command_patch.side_effect = mock_run_command

    bootloader = uboot.UbootBootloader()
    bootloader._get_image_slot = Mock(side_effect=_slot_of.get)

    bootloader.set_default_image(installed_images[1])
    assert env["boot_next"] == "run sonic_image_2"

    next_image = bootloader.get_next_image()
    assert next_image == installed_images[1]


@patch("sonic_installer.bootloader.uboot.subprocess.Popen")
def test_get_next_image_boot_once_overrides_boot_next(popen_patch):
    """boot_once wins over boot_next (matches bootcmd ordering)."""
    env = {
        "sonic_version_1": installed_images[0],
        "sonic_version_2": installed_images[1],
        "boot_once": "run sonic_image_2",
        "boot_next": "run sonic_image_1",
    }
    popen_patch.side_effect = _fake_env_popen(env)

    bootloader = uboot.UbootBootloader()
    assert bootloader.get_next_image() == installed_images[1]


@patch("sonic_installer.bootloader.uboot.subprocess.Popen")
def test_get_next_image_boot_once_empty_slot_returns_marker(popen_patch):
    """boot_once pointing at an empty slot returns the literal marker,
    not the current image -- surfaces broken state instead of hiding it."""
    env = {
        "sonic_version_1": installed_images[0],
        "sonic_version_2": "None",
        "boot_once": "run sonic_image_2",
        "boot_next": "run sonic_image_1",
    }
    popen_patch.side_effect = _fake_env_popen(env)

    bootloader = uboot.UbootBootloader()
    next_image = bootloader.get_next_image()
    assert next_image == "None"
    assert next_image != installed_images[0]


@patch("sonic_installer.bootloader.uboot.subprocess.Popen")
def test_get_next_image_unknown_boot_once_returns_raw(popen_patch):
    """Regression for codex review Finding 4: a non-empty ``boot_once``
    that doesn't name ``sonic_image_<N>`` is still what U-Boot will
    execute first. Return its raw value rather than falling through
    to ``boot_next`` (which would lie about ordering)."""
    env = {
        "sonic_version_1": installed_images[0],
        "sonic_version_2": installed_images[1],
        "boot_once": "run my_custom_script",
        "boot_next": "run sonic_image_1",
    }
    popen_patch.side_effect = _fake_env_popen(env)

    bootloader = uboot.UbootBootloader()
    assert bootloader.get_next_image() == "run my_custom_script"


@patch("sonic_installer.bootloader.uboot.subprocess.Popen")
def test_get_image_slot(popen_patch):
    """Direct coverage of the _get_image_slot helper."""
    env = {
        "sonic_version_1": installed_images[0],
        "sonic_version_2": installed_images[1],
    }

    def fake_popen(cmd, *args, **kwargs):
        var = cmd[-1]
        proc = Mock()
        value = env.get(var, "")
        proc.communicate.return_value = (value, None)
        proc.returncode = 0 if var in env else 1
        return proc
    popen_patch.side_effect = fake_popen

    bootloader = uboot.UbootBootloader()
    assert bootloader._get_image_slot(installed_images[0]) == 1
    assert bootloader._get_image_slot(installed_images[1]) == 2
    assert bootloader._get_image_slot("SONiC-OS-ghost.0") is None


@patch("sonic_installer.bootloader.uboot.subprocess.Popen")
def test_get_image_slot_substring_safe(popen_patch):
    """The helper must use ``==`` not ``in`` so that names which are
    substrings of each other don't mis-map."""
    shorter = f"{uboot.IMAGE_PREFIX}A"
    longer = f"{uboot.IMAGE_PREFIX}A-new"   # contains ``shorter`` as substring
    env = {"sonic_version_1": longer, "sonic_version_2": shorter}

    def fake_popen(cmd, *args, **kwargs):
        var = cmd[-1]
        proc = Mock()
        proc.communicate.return_value = (env.get(var, ""), None)
        proc.returncode = 0
        return proc
    popen_patch.side_effect = fake_popen

    bootloader = uboot.UbootBootloader()
    assert bootloader._get_image_slot(shorter) == 2
    assert bootloader._get_image_slot(longer) == 1

@patch("sonic_installer.bootloader.uboot.subprocess.Popen")
@patch("sonic_installer.bootloader.uboot.run_command")
def test_set_fips_uboot(run_command_patch, popen_patch):
    class MockProc():
        commandline = "linuxargs"
        def communicate(self):
            return MockProc.commandline, None

    def mock_run_command(cmd):
        # Remove leading string "/usr/bin/fw_setenv linuxargs " -- the 29 characters
        cmd = ' '.join(cmd)
        MockProc.commandline = 'linuxargs=' + cmd[29:]

    run_command_patch.side_effect = mock_run_command
    popen_patch.return_value = MockProc()

    image = 'test-image'
    bootloader = uboot.UbootBootloader()

    # The the default setting
    assert not bootloader.get_fips(image)

    # Test fips enabled
    bootloader.set_fips(image, True)
    assert bootloader.get_fips(image)

    # Test fips disabled
    bootloader.set_fips(image, False)
    assert not bootloader.get_fips(image)

def test_verify_image_sign():
    bootloader = uboot.UbootBootloader()
    image = 'test-image'
    return_value = None
    is_supported = bootloader.is_secure_upgrade_image_verification_supported()
    try:
        return_value = bootloader.verify_image_sign(image)
    except NotImplementedError:
        assert not is_supported
    else:
        assert False, "Wrong return value from verify_image_sign, returned" + str(return_value)


def _mock_verify_pipeline(p2_rc, p3_rc):
    """Popen side_effect returning a stub for each of sed/tar/grep
    (in call order). ``p2_rc`` is tar's rc (non-zero = manifest absent);
    ``p3_rc`` is grep's rc (0 = match)."""
    calls = []

    def factory(cmd, *args, **kwargs):
        proc = Mock()
        proc.stdout = Mock()
        idx = len(calls)
        calls.append(cmd)
        if idx == 0:
            proc.returncode = 0           # sed
        elif idx == 1:
            proc.returncode = p2_rc       # tar
        else:
            proc.returncode = p3_rc       # grep
        return proc
    return factory


@patch("sonic_installer.bootloader.uboot.device_info")
@patch("sonic_installer.bootloader.uboot.subprocess.Popen")
def test_verify_image_platform_matches(popen_patch, device_info_patch,
                                       tmp_path):
    """tar rc=0 + grep rc=0 -> True."""
    image = tmp_path / "sonic.bin"
    image.write_text("dummy")
    device_info_patch.get_platform = Mock(
        return_value="arm64-test-platform-r0")
    popen_patch.side_effect = _mock_verify_pipeline(p2_rc=0, p3_rc=0)

    bootloader = uboot.UbootBootloader()
    assert bootloader.verify_image_platform(str(image)) is True


@patch("sonic_installer.bootloader.uboot.device_info")
@patch("sonic_installer.bootloader.uboot.subprocess.Popen")
def test_verify_image_platform_mismatch(popen_patch, device_info_patch,
                                        tmp_path):
    """tar rc=0 + grep rc=1 -> False (platform not in manifest)."""
    image = tmp_path / "sonic.bin"
    image.write_text("dummy")
    device_info_patch.get_platform = Mock(return_value="x86_64-foo-r0")
    popen_patch.side_effect = _mock_verify_pipeline(p2_rc=0, p3_rc=1)

    bootloader = uboot.UbootBootloader()
    assert bootloader.verify_image_platform(str(image)) is False


@patch("sonic_installer.bootloader.uboot.device_info")
@patch("sonic_installer.bootloader.uboot.subprocess.Popen")
def test_verify_image_platform_no_manifest(popen_patch, device_info_patch,
                                           tmp_path):
    """tar rc!=0 (image ships no installer/platforms_asic) -> True, even
    when the running platform wouldn't match. Backward compatible with
    older images (matches grub.py); guards against tightening this."""
    image = tmp_path / "sonic.bin"
    image.write_text("dummy")
    device_info_patch.get_platform = Mock(return_value="x86_64-foo-r0")
    popen_patch.side_effect = _mock_verify_pipeline(p2_rc=2, p3_rc=1)

    bootloader = uboot.UbootBootloader()
    assert bootloader.verify_image_platform(str(image)) is True

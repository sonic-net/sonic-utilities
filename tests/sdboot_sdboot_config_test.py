#!/usr/bin/env python3

import contextlib
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

from sonic_sdboot_utils import sdboot_config
from sonic_sdboot_utils import utils

_TESTDATA_DIR = pathlib.Path(__file__).parent / "sdboot_utils_testdata"


class SdbootConfigTest(unittest.TestCase):

  def efivar_path(
      self,
      efivars_dir: pathlib.Path,
      entry_name: str,
  ) -> pathlib.Path:
    return efivars_dir / f"{entry_name}-{sdboot_config._SDBOOT_EFIVAR_UUID}"

  @contextlib.contextmanager
  def tempdir(self):
    try:
      tempdir = tempfile.TemporaryDirectory()
      yield pathlib.Path(tempdir.name)
    finally:
      tempdir.cleanup()

  def make_sdboot_conf(self, sort_key) -> sdboot_config.SdbootConfig:
    """Create a dummy sd-boot config with the given sort key."""
    return sdboot_config.SdbootConfig(
        title="dummy",
        version="dummy",
        sort_key=sort_key,
        linux=pathlib.Path("dev/null"),
        initrd=pathlib.Path("dev/null"),
        options=["rw"],
        image_dir=pathlib.Path("image-A"),
    )

  def test_sdboot_config_roundtrip(self):
    """Test that serialization and deserialization preserves content."""
    key = (1 << 64) - 1
    cfg = sdboot_config.SdbootConfig(
        title="Example",
        version="exemplar",
        sort_key=key,
        linux=pathlib.Path("sonic/a/vmlinuz-6.18.14"),
        initrd=pathlib.Path("sonic/a/initrd-6.18.14"),
        options=["rw", "nosplash"],
        image_dir=pathlib.Path("image-A"),
    )

    with tempfile.NamedTemporaryFile() as tf:
      tf_path = pathlib.Path(tf.name)
      cfg.write_file(tf_path)
      reread = cfg.from_file(tf_path)

    self.assertEqual(reread.title, cfg.title)
    self.assertEqual(reread.sort_key, cfg.sort_key)
    self.assertEqual(reread.key_str(), cfg.key_str())
    self.assertEqual(reread.linux, cfg.linux)
    self.assertEqual(reread.initrd, cfg.initrd)
    self.assertEqual(reread.options, cfg.options)
    self.assertEqual(reread.image_dir, cfg.image_dir)

  def test_sdboot_config_dict_roundtrip(self):
    key = (1 << 64) - 1
    cfg = sdboot_config.SdbootConfig(
        title="Example",
        version="example-version",
        sort_key=key,
        linux=pathlib.Path("sonic/a/vmlinuz-6.18.14"),
        initrd=pathlib.Path("sonic/a/initrd-6.18.14"),
        options=["rw", "nosplash"],
        image_dir="image-A",
    )

    reread = sdboot_config.SdbootConfig.from_dict(cfg.to_dict())

    self.assertEqual(reread.title, cfg.title)
    self.assertEqual(reread.sort_key, cfg.sort_key)
    self.assertEqual(reread.linux, cfg.linux)
    self.assertEqual(reread.key_str(), cfg.key_str())
    self.assertEqual(reread.initrd, cfg.initrd)
    self.assertEqual(reread.options, cfg.options)
    self.assertEqual(reread.image_dir, cfg.image_dir)

  def test_sdboot_config_good(self):
    """Test that a known-good config parses properly."""
    config = sdboot_config.SdbootConfig.from_file(
        _TESTDATA_DIR / "good_sdboot_config.conf"
    )

    self.assertEqual(config.sort_key, (1 << 64) - 1)

    sonic_a = pathlib.Path("sonic/a")
    self.assertEqual(
        config.to_dict(),
        {
            "title": "sonic_a",
            "version": "SONiC-OS-a",
            "sort-key": "0xffffffffffffffff",
            "linux": sonic_a / "vmlinuz-6.18.14-1rodete1-amd64",
            "initrd": sonic_a / "initrd.img-6.18.14-1rodete1-amd64",
            "options": [
                "console=ttyS0,115200n8",
                "console=hvc0",
                "console=tty0",
                "splash",
                "i915.enable_psr=0",
            ],
            "image-dir": pathlib.Path("image-A"),
        },
    )

  def test_find_configs_happypath(self):
    """Test that we can find all configs in a dir."""
    confs = sdboot_config.find_configs(_TESTDATA_DIR)
    self.assertEqual(len(confs), 1)
    self.assertIn("good_sdboot_config.conf", confs)

    conf = confs.get("good_sdboot_config.conf")
    self.assertIsNotNone(conf)

    sonic_a = pathlib.Path("sonic/a")
    self.assertEqual(
        conf.to_dict(),
        {
            "title": "sonic_a",
            "version": "SONiC-OS-a",
            "sort-key": "0xffffffffffffffff",
            "linux": sonic_a / "vmlinuz-6.18.14-1rodete1-amd64",
            "initrd": sonic_a / "initrd.img-6.18.14-1rodete1-amd64",
            "options": [
                "console=ttyS0,115200n8",
                "console=hvc0",
                "console=tty0",
                "splash",
                "i915.enable_psr=0",
            ],
            "image-dir": pathlib.Path("image-A"),
        },
    )

  def test_sdboot_config_key_format(self):
    conf = sdboot_config.SdbootConfig(
        title="example-os",
        version="example-os",
        sort_key=0,
        linux=pathlib.Path("dev/null"),
        initrd=pathlib.Path("dev/null"),
        options=[],
        image_dir="image-A",
    )

    self.assertEqual(conf.sort_key, 0)
    self.assertEqual(conf.key_str(), "0x0000000000000000")
    self.assertEqual(conf.to_dict()["sort-key"], "0x0000000000000000")

    conf.sort_key = 0xABCDEF
    self.assertEqual(conf.key_str(), "0x0000000000abcdef")
    self.assertEqual(conf.to_dict()["sort-key"], "0x0000000000abcdef")

  def test_bootcount_parse_and_roundtrip(self):
    cases = {
        "sonic_a": sdboot_config.SdbootEntry("sonic_a", None),
        "sonic_b": sdboot_config.SdbootEntry("sonic_b", None),
        "arch-linux": sdboot_config.SdbootEntry("arch-linux", None),
        "arch-linux+1-1": sdboot_config.SdbootEntry("arch-linux", (1, 1)),
        "arch-linux+0-1": sdboot_config.SdbootEntry("arch-linux", (0, 1)),
        "arch-linux+030-100": sdboot_config.SdbootEntry(
            "arch-linux", (30, 100)
        ),
    }
    for stem, expected in cases.items():
      parsed = sdboot_config.SdbootEntry.from_stem(stem)
      # Test parsing gets what we expect.
      self.assertEqual(parsed, expected)
      # Test that serializing returns to what we expect.
      self.assertEqual(parsed.to_stem(), stem)

  def test_bootcount_nodots(self):
    with self.assertRaisesRegex(ValueError, "ubuntu.conf contains a '.'"):
      sdboot_config.SdbootEntry.from_stem("ubuntu.conf")

  def test_bootcount_bad(self):
    with self.assertRaisesRegex(ValueError, "Invalid boot count 'bad'"):
      sdboot_config.SdbootEntry.from_stem("gentoo+bad")

    with self.assertRaisesRegex(
        ValueError, r"Invalid value for remaining: bad"
    ):
      sdboot_config.SdbootEntry.from_stem("gentoo+bad-horrible")

    with self.assertRaisesRegex(ValueError, r"Invalid value for total: \+10"):
      sdboot_config.SdbootEntry.from_stem("debian+10-+10")

    with self.assertRaisesRegex(
        ValueError, r"Invalid value for remaining: \+10"
    ):
      sdboot_config.SdbootEntry.from_stem("debian++10-100")

  def test_find_configs_new(self):
    confs = sdboot_config.find_configs(_TESTDATA_DIR / "configs_dir_all_valid")
    self.maxDiff = None
    asdict = {key: val.to_dict() for key, val in confs.items()}
    self.assertEqual(
        asdict,
        {
            "sonic_a+1-0.conf": {
                "initrd": pathlib.Path(
                    "sonic/a/initrd.img-6.18.14-1rodete1-amd64"
                ),
                "linux": pathlib.Path("sonic/a/vmlinuz-6.18.14-1rodete1-amd64"),
                "options": [
                    "console=ttyS0,115200n8",
                    "console=hvc0",
                    "console=tty0",
                    "splash",
                    "i915.enable_psr=0",
                ],
                "sort-key": "0xffffffffffffffff",
                "title": "sonic_a",
                "version": "SONiC-OS-a",
                "image-dir": pathlib.Path("image-A"),
            },
            "sonic_b+1-0.conf": {
                "initrd": pathlib.Path(
                    "sonic/a/initrd.img-6.18.14-1rodete1-amd64"
                ),
                "linux": pathlib.Path("sonic/a/vmlinuz-6.18.14-1rodete1-amd64"),
                "options": [
                    "console=ttyS0,115200n8",
                    "console=hvc0",
                    "console=tty0",
                    "splash",
                    "i915.enable_psr=0",
                ],
                "sort-key": "0xfffffffffffffffe",
                "title": "sonic_b",
                "version": "SONiC-OS-b",
                "image-dir": pathlib.Path("image-B"),
            },
        },
    )

  @mock.patch("builtins.print")
  def test_find_configs_new_badtitles(self, print_: mock.MagicMock):
    testdir = _TESTDATA_DIR / "configs_dir_with_invalid_title"
    confs = sdboot_config.find_configs(testdir)
    self.assertEqual(confs, {})

    print_.assert_has_calls(
        [
            mock.call(
                "Failed to parse boot entry metadata from"
                f" {testdir / 'sonic_a+bad.conf'}; skipping. error = Invalid"
                " boot count 'bad'",
                file=sys.stderr,
            ),
            mock.call(
                "Failed to parse boot entry metadata from"
                f" {testdir / 'sonic_b+one-ten.conf'}; skipping. error ="
                " Invalid value for remaining: one",
                file=sys.stderr,
            ),
        ],
        any_order=True,
    )

  @mock.patch("builtins.print")
  def test_find_configs_new_badcontents(self, print_: mock.MagicMock):
    testdir = _TESTDATA_DIR / "configs_dir_with_invalid_contents"
    confs = sdboot_config.find_configs(testdir)
    self.assertEqual(confs, {})

    print_.assert_has_calls(
        [
            mock.call(
                f"Failed to parse config file {testdir / 'sonic_a+1-0.conf'};"
                " skipping. error = Missing key linux",
                file=sys.stderr,
            ),
            mock.call(
                f"Failed to parse config file {testdir / 'sonic_b+1-0.conf'};"
                " skipping. error = Missing key initrd",
                file=sys.stderr,
            ),
        ],
        any_order=True,
    )

  def test_reset_bootcount_simple(self):
    with self.tempdir() as epath:
      conf_path = epath / "sonic_a+0-1.conf"
      self.make_sdboot_conf(0x1000).write_file(conf_path)

      with mock.patch.object(pathlib.Path, "rename") as ren:
        sdboot_config.reset_bootcount(
            conf_path,
            dry_run=False,
        )
        ren.assert_called_with(epath / "sonic_a+1-0.conf")

  def test_reset_bootcount_extra_attempts_done(self):
    with self.tempdir() as epath:
      self.make_sdboot_conf(0x1000).write_file(epath / "sonic_a+0-2.conf")

      with mock.patch.object(pathlib.Path, "rename") as ren:
        sdboot_config.reset_bootcount(
            epath / "sonic_a+0-2.conf",
            dry_run=False,
        )
        ren.assert_called_with(epath / "sonic_a+1-0.conf")

  def test_reset_bootcount_partial(self):
    with self.tempdir() as epath:
      self.make_sdboot_conf(0x1000).write_file(epath / "sonic_a+3-5.conf")

      with mock.patch.object(pathlib.Path, "rename") as ren:
        sdboot_config.reset_bootcount(
            epath / "sonic_a+3-5.conf",
            dry_run=False,
        )
        ren.assert_called_with(epath / "sonic_a+1-0.conf")

  def test_reset_bootcount_missing_conf(self):
    with self.tempdir() as epath:

      with self.assertRaises(FileNotFoundError):
        sdboot_config.reset_bootcount(
            epath / "sonic_a+0-1.conf",
            dry_run=False,
        )

  def test_reset_bootcount_no_change(self):
    with self.tempdir() as epath:
      self.make_sdboot_conf(0x1000).write_file(epath / "sonic_a+1-0.conf")

      with mock.patch.object(pathlib.Path, "rename") as ren:
        sdboot_config.reset_bootcount(
            epath / "sonic_a+1-0.conf",
            dry_run=False,
        )
        ren.assert_not_called()

  def test_reset_bootcount_blessed(self):
    with self.tempdir() as epath:
      path = epath / "sonic_a.conf"
      self.make_sdboot_conf(0x1000).write_file(path)

      with mock.patch.object(pathlib.Path, "rename") as ren:
        sdboot_config.reset_bootcount(
            path,
            dry_run=False,
        )
        ren.assert_not_called()

  @mock.patch("sonic_sdboot_utils.sdboot_config._read_efivar")
  def test_get_cur_boot_one_entry_a_selected(self, read_efi: mock.MagicMock):
    read_efi.side_effect = ["sonic_a.conf"]
    self.assertEqual(
        sdboot_config.get_cur_boot(), sdboot_config.SdbootEntry("sonic_a", None)
    )
    read_efi.assert_called_once()

  @mock.patch("sonic_sdboot_utils.sdboot_config._read_efivar")
  def test_get_cur_boot_one_entry_none_selected(self, read_efi: mock.MagicMock):
    read_efi.side_effect = [None]
    self.assertIsNone(sdboot_config.get_cur_boot())
    read_efi.assert_called_once()

  @mock.patch("sonic_sdboot_utils.utils.run_cmd")
  def test_set_oneshot_include_withbootcount(self, run_cmd):
    for dry_run in [True, False]:
      run_cmd.reset_mock()
      sdboot_config.set_oneshot(
          sdboot_config.SdbootEntry("sonic_a", (1, 0)),
          include_bootcount=True,
          dry_run=dry_run,
      )
      run_cmd.assert_called_once_with(
          ["bootctl", "set-oneshot", "sonic_a+1-0.conf"],
          dry_run=dry_run,
      )

  @mock.patch("sonic_sdboot_utils.utils.run_cmd")
  def test_set_oneshot_include_blessed(self, run_cmd):
    for dry_run in [True, False]:
      run_cmd.reset_mock()
      sdboot_config.set_oneshot(
          sdboot_config.SdbootEntry("sonic_a", None),
          include_bootcount=True,
          dry_run=dry_run,
      )
      run_cmd.assert_called_once_with(
          ["bootctl", "set-oneshot", "sonic_a.conf"],
          dry_run=dry_run,
      )

  @mock.patch("sonic_sdboot_utils.utils.run_cmd")
  def test_set_oneshot_noinclude_withbootcount(self, run_cmd):
    for dry_run in [True, False]:
      run_cmd.reset_mock()
      sdboot_config.set_oneshot(
          sdboot_config.SdbootEntry("sonic_a", (1, 0)),
          include_bootcount=False,
          dry_run=dry_run,
      )
      run_cmd.assert_called_once_with(
          ["bootctl", "set-oneshot", "sonic_a.conf"],
          dry_run=dry_run,
      )

  @mock.patch("sonic_sdboot_utils.utils.run_cmd")
  def test_set_oneshot_noinclude_blessed(self, run_cmd):
    for dry_run in [True, False]:
      run_cmd.reset_mock()
      sdboot_config.set_oneshot(
          sdboot_config.SdbootEntry("sonic_a", None),
          include_bootcount=False,
          dry_run=dry_run,
      )
      run_cmd.assert_called_once_with(
          ["bootctl", "set-oneshot", "sonic_a.conf"],
          dry_run=dry_run,
      )

  def test_read_efivar_happy_path(self):
    contents = "A lovely golden retriever"
    with self.tempdir() as efivars_dir:
      with open(self.efivar_path(efivars_dir, "LoaderEntryCuteDog"), "wb") as f:
        f.write(b"\x00" * 4)
        f.write(contents.encode("utf-16-le"))
        f.write("\x00".encode("utf-16-le"))

      self.assertEqual(
          sdboot_config._read_efivar(
              "LoaderEntryCuteDog",
              efivars_path=efivars_dir,
          ),
          contents,
      )

  def test_read_efivar_nonexistent(self):
    with self.tempdir() as efivars_dir:
      with self.assertRaises(FileNotFoundError):
        sdboot_config._read_efivar(
            "LoaderEntryCuteDog", efivars_path=efivars_dir
        )

  def test_read_efivar_too_short(self):
    with self.tempdir() as efivars_dir:
      with open(self.efivar_path(efivars_dir, "LoaderEntryCuteDog"), "wb") as f:
        f.write(b"\x00" * 3)
      with self.assertRaisesRegex(ValueError, "Too short!"):
        sdboot_config._read_efivar(
            "LoaderEntryCuteDog", efivars_path=efivars_dir
        )

  def test_read_efivar_bad_encoding(self):
    with self.tempdir() as efivars_dir:
      with open(self.efivar_path(efivars_dir, "LoaderEntryUglyDog"), "wb") as f:
        f.write(b"\x00" * 4)
        f.write(b"a mean chihuahua\x00")
      with self.assertRaises(UnicodeDecodeError):
        sdboot_config._read_efivar(
            "LoaderEntryUglyDog", efivars_path=efivars_dir
        )

  def test_read_efivar_not_null_terminated(self):
    with self.tempdir() as efivars_dir:
      with open(
          self.efivar_path(efivars_dir, "LoaderEntryFuzzyRabbit"), "wb"
      ) as f:
        f.write(b"\x00" * 4)
        f.write("French Lop".encode("utf-16-le"))
      with self.assertRaises(ValueError):
        sdboot_config._read_efivar(
            "LoaderEntryFuzzyRabbit", efivars_path=efivars_dir
        )

  @mock.patch("sonic_sdboot_utils.sdboot_config._read_efivar")
  def test_get_oneshot_happy_path(self, re: mock.MagicMock):
    with self.tempdir() as td:
      re.side_effect = ["sonic_a+1-0.conf"]
      self.assertEqual(
          sdboot_config.get_oneshot(td),
          sdboot_config.SdbootEntry("sonic_a", (1, 0)),
      )
      re.assert_called_with("LoaderEntryOneShot", efivars_path=td)

  @mock.patch("sonic_sdboot_utils.sdboot_config._read_efivar")
  def test_get_oneshot_parse_failure_ok(self, re: mock.MagicMock):
    with self.tempdir() as td:
      re.side_effect = [ValueError]
      self.assertIsNone(sdboot_config.get_oneshot(td))
      re.assert_called_with("LoaderEntryOneShot", efivars_path=td)

  @mock.patch("sonic_sdboot_utils.sdboot_config._read_efivar")
  def test_get_oneshot_efivar_missing_ok(self, re: mock.MagicMock):
    with self.tempdir() as td:
      re.side_effect = [FileNotFoundError]
      self.assertIsNone(sdboot_config.get_oneshot(td))
      re.assert_called_with("LoaderEntryOneShot", efivars_path=td)

  @mock.patch("sonic_sdboot_utils.sdboot_config._read_efivar")
  def test_get_selected_happy_path(self, re: mock.MagicMock):
    with self.tempdir() as td:
      re.side_effect = ["sonic_a+1-0.conf"]
      self.assertEqual(
          sdboot_config.get_cur_boot(td),
          sdboot_config.SdbootEntry("sonic_a", (1, 0)),
      )
      re.assert_called_with("LoaderEntrySelected", efivars_path=td)

  @mock.patch("sonic_sdboot_utils.sdboot_config._read_efivar")
  def test_get_selected_parse_failure_ok(self, re: mock.MagicMock):
    with self.tempdir() as td:
      re.side_effect = [ValueError]
      self.assertIsNone(sdboot_config.get_cur_boot(td))
      re.assert_called_with("LoaderEntrySelected", efivars_path=td)

  @mock.patch("sonic_sdboot_utils.sdboot_config._read_efivar")
  def test_get_selected_efivar_missing_ok(self, re: mock.MagicMock):
    with self.tempdir() as td:
      re.side_effect = [FileNotFoundError]
      self.assertIsNone(sdboot_config.get_cur_boot(td))
      re.assert_called_with("LoaderEntrySelected", efivars_path=td)


if __name__ == "__main__":
  unittest.main()

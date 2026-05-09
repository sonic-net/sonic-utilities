#!/usr/bin/env python3

import argparse
import json
import os
import pathlib
import shutil
import tempfile
import typing as t

# Try to load them from path, or try to load them locally if running in a test.
try:
  from sonic_sdboot_utils import sdboot_config
  from sonic_sdboot_utils import utils
except ModuleNotFoundError:
  import utils
  import sdboot_config

# Important paths...
_BOOT = pathlib.Path("/boot")
_HOST = pathlib.Path("/host")

_SONIC_IDS = {"sonic_a", "sonic_b"}
_UINT64_MAX = (1 << 64) - 1


class InstallError(RuntimeError):
  pass


def _is_mount(path: pathlib.Path) -> bool:
  """Mockable wrapper around pathlib.Path.is_mount."""
  return path.is_mount()


def ensure_mountpoints_sonie(
    demo_mnt: pathlib.Path,
    boot: pathlib.Path = _BOOT,
    host: pathlib.Path = _HOST,
):
  """Ensure requisite mountpoints to perform an install from SONIE."""
  install_env = utils.detect_install_environment()

  if not _is_mount(boot):
    raise InstallError(f"{boot} is not mounted!")

  try:
    utils.unmount_tree(host)
  except utils.UnmountError as x:
    print(f"ensure_mountpoints_sonie failed: {x}")
    raise InstallError(x)

  print("Running in SONIE, attempting to make / rprivate.")
  if ec := utils.run_cmd(["mount", "--make-rprivate", "/"]):
    print(f"Warning: Failed to make / rprivate (ec={ec})")

  if ec := utils.run_cmd(["mount", "--move", demo_mnt, host]):
    raise InstallError(f"Failed to move {demo_mnt} mount to {host}")

  # Ensure /host/boot mountpoint (or equivalent), and then bind mount /boot
  # thereto.
  host_boot = host / "boot"
  host_boot.mkdir(exist_ok=True)

  try:
    utils.mount(boot, host_boot, options=["bind"])
  except utils.MountError as x:
    print(f"Failed to bind mount {boot} onto {host_boot}: {x}")
    raise InstallError(x)

  # Ensure the systemd boot loader entries directory exists.
  entries = host_boot / "loader/entries"
  entries.mkdir(parents=True, exist_ok=True)


def ensure_mountpoints_sonic(
    demo_mnt: pathlib.Path,
    boot: pathlib.Path = _BOOT,
    host: pathlib.Path = _HOST,
):
  """Ensure requisite mountpoints to perform an install from SONIC."""
  missing = sorted(mp for mp in [boot, host] if not _is_mount(mp))
  if missing:
    raise InstallError(f"Missing mountpoints: {missing}")

  host_boot = host / "boot"
  host_boot.mkdir(exist_ok=True)

  if _is_mount(host_boot):
    utils.umount(host_boot)
  utils.mount(boot, host_boot, options=["bind"])
  (host_boot / "loader/entries").mkdir(parents=True, exist_ok=True)


def _get_new_id(loader_entries: pathlib.Path) -> tuple[str, int]:
  """Scan the entries directory and find the appropriate ID and next sort key.

  - Search for a config named 'sonic_a' and 'sonic_b'.
  - If neither exists, return 'sonic_a'.
  - If exactly one of the two exists, return the other.
  - If both exist, return whichever one currently has the higher sort-key.
  """

  confs = sdboot_config.find_configs(loader_entries)
  confs = {
      sdboot_config.SdbootEntry.from_filename(key).identifier: val
      for key, val in confs.items()
  }
  confs = {key: val for key, val in confs.items() if key in _SONIC_IDS}

  # If we have no existing sonics, return "sonic_a"
  if not confs:
    return "sonic_a", _UINT64_MAX

  # If we have one, return the other.
  if len(confs) == 1:
    key, val = confs.popitem()
    retset = _SONIC_IDS - {key}
    assert len(retset) == 1
    return retset.pop(), val.sort_key - 1

  # If we have two, find the highest sort key and return that one.
  allconfs = list(confs.items())
  allconfs.sort(key=lambda pair: pair[1].sort_key, reverse=True)
  return (
      allconfs[0][0],
      allconfs[1][1].sort_key - 1,
  )


def _install_boot_artifacts(
    dest: pathlib.Path,
    src: pathlib.Path,
) -> tuple[pathlib.Path, pathlib.Path]:
  """Copy boot artifacts from src and put them in dst."""

  if not dest.is_dir():
    raise InstallError(
        f"cannot install boot artifacts to {dest}: not a directory."
    )

  def find_one(glob: str) -> str:
    found = list(src.glob(glob))
    if len(found) == 1:
      return found[0]
    raise ValueError(f"Expected one file to match {glob} but got {found}.")

  def copy_verbose(src: pathlib.Path, dest: pathlib.Path):
    print(f"copying {src} to {dest}...")
    shutil.copy2(src, dest)

  # Find the items to copy.
  linux = find_one("vmlinuz-*")
  initrd = find_one("initrd.*")

  copy_verbose(linux, dest)
  copy_verbose(initrd, dest)

  return dest / linux.name, dest / initrd.name


def bootloader_menu_config(
    *,
    linux: pathlib.Path,
    initrd: pathlib.Path,
    version: str,
    root_arg: str,
    fs_squashfs: pathlib.Path,
    extra_kernel_args: list[str],
    conf_id: str,
    sort_key: int,
    boot_path: pathlib.Path = _BOOT,
    image_name: str,
):
  """Create a booloader entry for the newly installed SONIC.

  Args:
    linux: path to linux kernel, relative to |boot_path|.
    initrd: path to initrd, relative to |boot_path|.
    version: The version of the new OS veing installed.
    root_arg: Argument to identify the new filesystem's root device (eg.
      "UUID=$UUID" or LABEL=fslabel)
    fs_squashfs: Argument to pass to loop= to identify the loop dev to mount,
      relative to the root device's root filesystem.
    extra_kernel_args: Additional kernel args to apply in the config.
    boot_path: Path to /boot directory.
    image_name: Name of the image (eg, image-A/image-B. This is the directory on
      the sonic root partition where the install is located.
  """
  loader_entries = boot_path / "loader/entries"

  for name, item in {"linux": linux, "initrd": initrd}.items():
    if not (boot_path / item).is_file():
      raise FileNotFoundError(
          f"Could not find {name} artifact {item} within {boot_path}."
      )

  var_log_size = int(os.getenv("VAR_LOG_SIZE", "4096"))

  options = [
      f"root={root_arg}",
      "rw",
      "net.ifnames=0",
      "biosdevname=0",
      f"loop=/{fs_squashfs}",
      "loopfstype=squashfs",
      "systemd.unified_cgroup_hierarchy=0",
      "apparmor=1",
      "security=apparmor",
      f"varlog_size={var_log_size}",
      "usbcore.autosuspend=-1",
      *extra_kernel_args,
  ]

  conf = sdboot_config.SdbootConfig(
      title=conf_id,
      version=version,
      sort_key=sort_key,
      linux=linux,
      initrd=initrd,
      options=options,
      image_dir=pathlib.Path(image_name),
  )

  # write the config to a temp file, and then mv it into place, so that the new
  # config will come in to being fully formed, from the perspective of sdboot.
  new_stem = sdboot_config.SdbootEntry(identifier=conf_id, bootcount=(1, 0))
  new_temp = loader_entries / f"{new_stem.to_stem()}.temp"
  new_conf = loader_entries / f"{new_stem.to_stem()}.conf"

  conf.write_file(new_temp)
  new_temp.rename(new_conf)


def _parse_args(argv: list[str] | None = None) -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser()

  parser.add_argument(
      "-b",
      "--boot-dir",
      type=pathlib.Path,
      default=_BOOT,
      help="The boot directory as seen by the installation OS.",
  )
  parser.add_argument(
      "-o",
      "--host-dir",
      type=pathlib.Path,
      default=_HOST,
      help="The /host directory.",
  )
  parser.add_argument(
      "-d",
      "--demo-dir",
      type=pathlib.Path,
      required=True,
      help="Mountpoint of the new SONIC being installed.",
  )
  parser.add_argument(
      "-i",
      "--image-name",
      type=str,
      required=True,
      help=(
          "Name of the directory within the new SONIC corresponding to the new"
          " install."
      ),
  )
  parser.add_argument(
      "-I",
      "--image-version",
      type=str,
      required=True,
      help="Version of the image to be installed.",
  )
  parser.add_argument(
      "-L",
      "--loop-squash-file",
      type=pathlib.Path,
      required=True,
      help="Path to the loop squash device relative to the install device.",
  )
  parser.add_argument(
      "-D",
      "--demo-dev",
      type=pathlib.Path,
      required=True,
      help="Device path onto which SONIC is being installed.",
  )
  parser.add_argument(
      "-a",
      "--extra-kernel-args",
      type=str,
      default="",
      help="Extra arguments to be passed to the kernel.",
  )

  return parser.parse_args(argv)


def main(args: argparse.Namespace | None = None) -> None:
  args = args if args is not None else _parse_args()
  env = utils.detect_install_environment()
  if env not in {
      utils.InstallEnvironment.SONIC,
      utils.InstallEnvironment.SONIE,
  }:
    raise SystemExit(f"Unsupported install environment {env}")

  demo_uuid = utils.get_dev_uuid(args.demo_dev)

  match env:
    case utils.InstallEnvironment.SONIE:
      ensure_mountpoints_sonie(args.demo_dir, args.boot_dir, args.host_dir)
    case utils.InstallEnvironment.SONIC:
      ensure_mountpoints_sonic(args.demo_dir, args.boot_dir, args.host_dir)

  # TODO(scotthaiden): Implement separate dirs per install slot with cleanup.
  host_boot = args.host_dir / "boot"
  host_boot_sonic = host_boot / "SONIC"
  host_boot_sonic.mkdir(parents=True, exist_ok=True)

  new_id, sort_key = _get_new_id(host_boot / "loader/entries")

  artifacts_dir: pathlib.Path = host_boot_sonic / new_id
  if artifacts_dir.exists():
    shutil.rmtree(artifacts_dir)
  artifacts_dir.mkdir()

  linux, initrd = _install_boot_artifacts(
      artifacts_dir,
      args.host_dir / args.image_name / "boot",
  )

  bootloader_menu_config(
      linux=linux.relative_to(host_boot),
      version=args.image_version,
      initrd=initrd.relative_to(host_boot),
      root_arg=f"UUID={demo_uuid}",
      fs_squashfs=args.loop_squash_file,
      boot_path=host_boot,
      conf_id=new_id,
      sort_key=sort_key,
      extra_kernel_args=args.extra_kernel_args.split(),
      image_name=args.image_name,
  )


if __name__ == "__main__":
  main()

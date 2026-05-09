"""Utilities for the python systemd-boot installer."""

import enum
import os
import pathlib
import shlex
import subprocess
import sys
import typing as t


_INSTALL_ENV_ENVVAR_NAME = "install_env"

_PROC_MOUNTS = pathlib.Path("/proc/mounts")
_DEV_DISK_BY_UUID = pathlib.Path("/dev/disk/by-uuid")


class InstallEnvironment(enum.Enum):
  ONIE = "onie"
  SONIC = "sonic"
  SONIE = "sonie"
  BUILD = "build"


class UnmountError(RuntimeError):
  pass


class MountError(RuntimeError):
  pass


def detect_install_environment() -> InstallEnvironment:
  """Detect the current install environment or raise a ValueError."""
  val = os.getenv(_INSTALL_ENV_ENVVAR_NAME)
  if val is None:
    raise ValueError(
        f"Failed to detect environment: {_INSTALL_ENV_ENVVAR_NAME} unset."
    )
  return InstallEnvironment(val)


def run_cmd(argv: list[t.Any], *, dry_run: bool = False) -> int:
  """Run a command and return its exit code."""
  args = [str(arg) for arg in argv]
  print(f"$ {shlex.join(args)}", file=sys.stderr)
  return 0 if dry_run else subprocess.call(args)


def find_mountpoints_below(path: pathlib.Path) -> list[pathlib.Path]:
  with open(_PROC_MOUNTS, "rt") as mounts:
    lines = map(str.split, mounts)
    mps = (pathlib.Path(line[1]) for line in lines)
    subpaths = [mp for mp in mps if mp.is_relative_to(path)]

  subpaths.sort(reverse=True)
  return subpaths


def unmount_tree(path: pathlib.Path):
  """Unmount path, and any mountpoints below it.

  Args:
    path: Root of the tree to unmount below.

  Returns: None
  Raises:
    UnmountError: If any umount operation fails.
  """
  mps = find_mountpoints_below(path)

  for mp in mps:
    umount(mp)


def umount(mountpoint: pathlib.Path):
  """Wrap a call to umount. Mostly useful for test injection.

  Args:
    mountpoint: Path to unmount.

  Returns: None
  Raises:
    UnmountError: If the umount operation fails.
  """
  if ec := run_cmd(["umount", mountpoint]):
    raise UnmountError(f"Failed to unmount {mountpoint} (returned {ec})")


def mount(
    obj: pathlib.Path | str,
    mountpoint: pathlib.Path,
    *,
    fstype: str | None = None,
    options: list[str] | None = None,
) -> bool:
  """Perform a mount by shelling out to `mount`."""
  cmd = ["mount", obj, mountpoint]
  if fstype:
    cmd += ["-t", fstype]
  if options:
    cmd += ["-o", ",".join(options)]

  if ec := run_cmd(cmd):
    raise MountError(
        f"command failed ({shlex.join(map(str, cmd))}) returned {ec}"
    )


def get_dev_uuid(
    dev: pathlib.Path,
    *,
    dev_by_uuid: pathlib.Path = _DEV_DISK_BY_UUID,
):
  """Find the device UUID for dev, or raise FileNotFoundError."""
  for link in dev_by_uuid.glob("*"):
    if link.resolve() == dev:
      return link.name

  raise FileNotFoundError(f"Could not find a link for {dev} in {dev_by_uuid}")

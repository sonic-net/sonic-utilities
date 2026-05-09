#!/usr/bin/env python3

import argparse
import enum
import pathlib
import shlex
import sys

# Try to load them from path, or try to load them locally if running in a test.
try:
  from sonic_sdboot_utils import sdboot_config
  from sonic_sdboot_utils import utils
except ModuleNotFoundError:
  import sdboot_config
  import utils

_BOOT_MOUNTPOINT = pathlib.Path("/boot")
_WANTED_IDS = {"sonic_a", "sonic_b"}
_SONIE_DISCOVERY_SCRIPT = pathlib.Path("/usr/bin/sonie-discovery.sh")


class DHCPLength(enum.Enum):
  """Lenght of time in seconds for a DHCP attempt."""

  SHORT = 60
  LONG = 600


def _find_sonics(
    boot_loader_entries_dir: pathlib.Path,
) -> list[tuple[str, sdboot_config.SdbootConfig]]:
  if not boot_loader_entries_dir.is_dir():
    return []
  all_configs = sdboot_config.find_configs(boot_loader_entries_dir)

  def yield_entries():
    for name, val in all_configs.items():
      if (
          sdboot_config.SdbootEntry.from_filename(name).identifier
          not in _WANTED_IDS
      ):
        continue
      yield name, val

  def sort_key(kv) -> int:
    key, val = kv
    return val.sort_key

  return sorted(yield_entries(), key=sort_key)


def involuntary_reset():
  """Returns whether the reboot reason was involuntary_reset."""
  # TODO(b/502963587) -- implement this when we have the ability to detect
  # involuntary resets. We return true here by default to cause faster reboots.
  return True


def attempt_dhcp(attempt_type: DHCPLength, dry_run: bool):
  """Calls the DHCP discovery script with the specified length in seconds."""
  ec = utils.run_cmd(
      [_SONIE_DISCOVERY_SCRIPT, "-t", attempt_type.value], dry_run=dry_run
  )
  print(f"{attempt_type.name} DHCP attempt returned {ec}")


def reboot(dry_run: bool):
  """Reboots the system."""
  utils.run_cmd(["reboot"], dry_run=dry_run)


def _parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser()

  def add_bool(flag: str, default: bool, help: str):
    parser.add_argument(
        f"--{flag}",
        default=default,
        action="store_true",
        help=help,
    )
    parser.add_argument(
        f"--no-{flag}",
        action="store_false",
        dest=flag.replace("-", "_"),
    )

  parser.add_argument(
      "-b",
      "--boot-mountpoint",
      type=pathlib.Path,
      default=_BOOT_MOUNTPOINT,
  )
  add_bool("dry-run", False, "Print commands only, don't actually run them.")
  add_bool("reboot", True, "Reboot when assessment is done.")
  add_bool(
      "include-bootcount-in-oneshot",
      True,
      "If true, then when running bootctl set-oneshot, include the bootcount"
      " for compatability.",
  )

  return parser.parse_args()


def main(args: argparse.Namespace | None = None) -> None:
  args = args if args is not None else _parse_args()

  boot_loader_entries = args.boot_mountpoint / "loader/entries"
  all_sonics = _find_sonics(boot_loader_entries)
  match all_sonics:
    case []:
      # Long DHCP (10 minutes).
      attempt_dhcp(DHCPLength.LONG, dry_run=args.dry_run)
    case [primary]:
      name, config = primary
      entry = sdboot_config.SdbootEntry.from_filename(name)
      is_bad = entry.is_bad()
      sdboot_config.reset_bootcount(
          boot_loader_entries / name, dry_run=args.dry_run
      )

      if is_bad:
        attempt_dhcp(DHCPLength.SHORT, dry_run=args.dry_run)
      elif involuntary_reset():
        sdboot_config.set_oneshot(
            entry,
            include_bootcount=args.include_bootcount_in_oneshot,
            dry_run=args.dry_run,
        )
      else:
        attempt_dhcp(DHCPLength.SHORT, dry_run=args.dry_run)
    case [primary, alternate]:
      # Check the state of both.
      pri_name, pri_conf = primary
      alt_name, alt_conf = alternate
      pri_entry, alt_entry = map(
          sdboot_config.SdbootEntry.from_filename, [pri_name, alt_name]
      )
      pri_bad, alt_bad = pri_entry.is_bad(), alt_entry.is_bad()

      # Reset both.
      sdboot_config.reset_bootcount(
          boot_loader_entries / pri_name, dry_run=args.dry_run
      )
      sdboot_config.reset_bootcount(
          boot_loader_entries / alt_name, dry_run=args.dry_run
      )

      if alt_bad:
        attempt_dhcp(DHCPLength.SHORT, dry_run=args.dry_run)
      elif pri_bad:
        sdboot_config.set_oneshot(
            alt_entry,
            include_bootcount=args.include_bootcount_in_oneshot,
            dry_run=args.dry_run,
        )
      # If we get here, neither pri nor alt were bad.
      elif involuntary_reset():
        sdboot_config.set_oneshot(
            pri_entry,
            include_bootcount=args.include_bootcount_in_oneshot,
            dry_run=args.dry_run,
        )
      else:
        attempt_dhcp(DHCPLength.SHORT, dry_run=args.dry_run)

  if args.reboot:
    reboot(dry_run=args.dry_run)


if __name__ == "__main__":
  main()

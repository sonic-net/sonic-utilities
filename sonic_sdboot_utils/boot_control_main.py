#!/usr/bin/env python3

import argparse
import pathlib
import sys
import uuid

# Try to load them from path, or try to load them locally if running in a test.
try:
  from sonic_sdboot_utils import sdboot_config
  from sonic_sdboot_utils import utils
except ModuleNotFoundError:
  import utils
  import sdboot_config

_SYSTEMD_BOOT_EFIVAR_UUID = uuid.UUID("4a67b082-0a4c-41cf-b6c7-440b29bb8c4f")
_NEXT_BOOT_FLAGFILE_PATH = pathlib.Path("/run/sonic-boot-control/next-boot")


def set_next_boot(
    entry: sdboot_config.SdbootEntry | None,
    include_boot_count: bool,
    flagfile_path: pathlib.Path = _NEXT_BOOT_FLAGFILE_PATH,
):
  """Update the 'next-boot' flagfile which lives in /run (a tmpfs mount).

  This signals that on a clean shutdown, we should boot in to the given entry.
  """
  if entry is None:
    if flagfile_path.exists():
      flagfile_path.unlink()
    return

  stem = entry.to_stem() if include_boot_count else entry.identifier

  flagfile_path.parent.mkdir(parents=True, exist_ok=True)
  with open(flagfile_path, "w") as f:
    f.write(f"{stem}.conf")


def get_next_boot(
    flagfile_path: pathlib.Path = _NEXT_BOOT_FLAGFILE_PATH,
) -> sdboot_config.SdbootEntry | None:
  """Attempt to read the next-boot flagfile from /run.

  Returns:
    SdbootEntry from the file, if it exists.
    None, if it is not set.
  """
  if not flagfile_path.exists():
    return None

  with open(flagfile_path, "r") as f:
    return sdboot_config.SdbootEntry.from_filename(f.read())


def find_default_sonic(
    loader_entries_dir: pathlib.Path,
) -> sdboot_config.SdbootEntry | None:
  """Find the sonic entry with the lowest sort key."""
  all_entries = sdboot_config.find_configs(loader_entries_dir)
  parsed = {
      sdboot_config.SdbootEntry.from_filename(key): val
      for key, val in all_entries.items()
  }
  matching = [
      (key, val)
      for key, val in parsed.items()
      if key.identifier in {"sonic_a", "sonic_b"}
  ]
  matching.sort(key=lambda kv: kv[1].sort_key)

  if len(matching) > 0:
    return matching[0][0]

  return None


def _parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser()

  def add_bool(name: str, default: bool):
    parser.add_argument(f"--{name}", action="store_true", default=default)
    parser.add_argument(
        f"--no-{name}", action="store_false", dest=name.replace("-", "_")
    )

  add_bool("dry-run", True)
  add_bool("include-bootcount-in-oneshot", True)

  parser.add_argument(
      "--boot-loader-entries-dir",
      type=pathlib.Path,
      default=pathlib.Path("/boot/loader/entries"),
  )
  parser.add_argument(
      "--efivars-path",
      type=pathlib.Path,
      default=pathlib.Path("/sys/firmware/efi/efivars"),
  )
  parser.add_argument(
      "--next-boot-flagfile-path",
      type=pathlib.Path,
      default=_NEXT_BOOT_FLAGFILE_PATH,
  )

  parser.add_argument(
      "action",
      type=str,
      choices=["prepare-reboot", "reset-bootcount", "set-next-boot"],
      help="Desired action to perform.",
  )

  parser.add_argument("additional_arg", nargs="?")

  return parser.parse_args()


def find_matching_conf_or_die(
    conf: sdboot_config.SdbootEntry,
    entries_dir: pathlib.Path,
) -> sdboot_config.SdbootEntry:
  extant_confs = sdboot_config.find_configs(entries_dir)
  parsed = map(sdboot_config.SdbootEntry.from_filename, extant_confs)
  matching = filter(lambda c: c.identifier == conf.identifier, parsed)
  found = sorted(matching, key=sdboot_config.SdbootEntry.to_stem)

  if (l := len(found)) == 0:
    sys.exit(f"Found no matching confs for {conf.to_stem()}.conf")
  elif l > 1:
    imposters = ", ".join(f"{c.to_stem()}.conf" for c in found)
    sys.exit(f"Found {l} matching confs for {conf.to_stem()}: {imposters}")

  return found[0]


def main(args: argparse.Namespace | None = None) -> None:
  args = args if args is not None else _parse_args()

  match args.action:
    case "reset-bootcount":
      cur_boot = sdboot_config.get_cur_boot(args.efivars_path)
      matching_entry = find_matching_conf_or_die(
          cur_boot,
          args.boot_loader_entries_dir,
      )
      stem = (
          matching_entry.to_stem()
          if args.include_bootcount_in_oneshot
          else matching_entry.identifier
      )
      sdboot_config.reset_bootcount(
          args.boot_loader_entries_dir / f"{stem}.conf",
          dry_run=args.dry_run,
      )
    case "set-next-boot":
      if args.additional_arg is None:
        sys.exit("Missing argument: image")
      image = sdboot_config.SdbootEntry.from_filename(args.additional_arg)
      actual = find_matching_conf_or_die(image, args.boot_loader_entries_dir)
      set_next_boot(
          actual,
          args.include_bootcount_in_oneshot,
          args.next_boot_flagfile_path,
      )
    case "prepare-reboot":
      # get next_selected from flag file if possible.
      next_selected = get_next_boot(args.next_boot_flagfile_path)

      # If flag file doesn't work, find the config from configs on disk.
      if next_selected is None:
        next_selected = find_default_sonic(args.boot_loader_entries_dir)

      # If the configs on disk don't make it work, nothing to be done.
      if next_selected is None:
        sys.exit("Could not find config to set next boot.")

      sdboot_config.set_oneshot(
          next_selected, args.include_bootcount_in_oneshot, args.dry_run
      )

    case _:
      sys.exit(f"Unsupported action {args.action}")


if __name__ == "__main__":
  main()

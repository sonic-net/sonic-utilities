"""Apply signed PK and KEK updates; UEFI firmware enforces authorization."""

import argparse
import os
import subprocess
from pathlib import Path

from . import secure_boot_db
from .secure_boot_lock import locked


class PreconditionError(secure_boot_db.ScriptError):
    """Invalid arguments or unavailable efivars; the standalone command exits 2."""


def log(message):
    """Report key-update progress using the existing command's prefix."""
    print(f"secure_boot_enroll_key: {message}")


def ensure_efivars(config):
    """Mount efivarfs when necessary before accessing firmware variables."""
    if not config.efivars_dir.is_dir():
        raise PreconditionError(f"efivars not available at {config.efivars_dir}")
    if not os.path.ismount(config.efivars_dir):
        result = secure_boot_db.run(["mount", "-t", "efivarfs", "efivarfs", str(config.efivars_dir)])
        if result.returncode:
            raise secure_boot_db.ScriptError(
                f"failed to mount efivarfs at {config.efivars_dir}: {result.stderr.strip()}"
            )


@locked
def update_secure_boot_key(variable, auth_file, *, config=None):
    """Replace PK or KEK using a signed update; raise on failure, never append."""
    if variable not in ("KEK", "PK"):
        raise PreconditionError(f"unsupported variable '{variable}' (expected KEK or PK)")
    auth = Path(auth_file)
    if not auth.is_file():
        raise PreconditionError(f"auth file '{auth_file}' not found")
    config = config or secure_boot_db.Config.from_env()
    ensure_efivars(config)
    variable_path = config.efivars_dir / f"{variable}-{secure_boot_db.EFI_GLOBAL_VARIABLE_GUID}"
    if variable_path.exists():
        secure_boot_db.succeeds(["chattr", "-i", str(variable_path)])
    log(f"updating {variable} from {auth}")
    result = subprocess.run(
        ["efi-updatevar", "-f", str(auth), variable], timeout=secure_boot_db.COMMAND_TIMEOUT_SECS,
    )
    if result.returncode:
        raise secure_boot_db.ScriptError(
            f"failed to update {variable} (firmware rejected the update or the variable is not writable)"
        )
    log(f"{variable} updated")


def main(argv=None):
    """Run a standalone key update, retaining exit codes 0, 1 and 2."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("variable", choices=("KEK", "PK"), help="UEFI key variable to replace")
    parser.add_argument("auth_file", help="signed .auth update, possibly containing an empty key list")
    args = parser.parse_args(argv)
    try:
        update_secure_boot_key(args.variable, args.auth_file)
        return 0
    except PreconditionError as e:
        log(f"ERROR: {e}")
        return 2
    except (secure_boot_db.ScriptError, OSError, subprocess.SubprocessError) as e:
        log(f"ERROR: {e}")
        return 1

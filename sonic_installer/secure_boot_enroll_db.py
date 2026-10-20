"""Enroll an installer's bundled db update before verifying its image signature.

Enrollment accepts updates authorized by an enrolled PK or KEK. Pruning retains
its separate, KEK-only authorization policy.
"""

import argparse
import hashlib
import lzma
import os
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
import zlib
from pathlib import Path

from . import secure_boot_db
from .secure_boot_keys import ensure_efivars
from .secure_boot_lock import locked

ENROLLMENT_AUTHORITIES = ("PK", "KEK")


def log(message):
    """Report enrollment progress using the standalone command's existing prefix."""
    print(f"secure_boot_enroll_db: {message}")


def extract_db_auth(image_path, work):
    """Read only installer/fs.zip and boot/DB.auth, without extracting archive paths."""
    fs_zip = work / "fs.zip"
    with image_path.open("rb") as image:
        at_line_start = True
        while True:
            line = image.readline(8192)
            if not line:
                raise secure_boot_db.ScriptError("installer image has no exit_marker header")
            if at_line_start and line == b"exit_marker\n":
                break
            at_line_start = line.endswith(b"\n")
        try:
            with tarfile.open(fileobj=image, mode="r|*") as archive:
                for member in archive:
                    if member.name != "installer/fs.zip":
                        continue
                    if not member.isfile():
                        raise secure_boot_db.ScriptError("installer/fs.zip is not a regular file")
                    with archive.extractfile(member) as source, fs_zip.open("wb") as destination:
                        shutil.copyfileobj(source, destination)
                    break
                else:
                    log("image does not contain installer/fs.zip, no db certificate to enroll")
                    return None
        except tarfile.TarError as e:
            raise secure_boot_db.ScriptError(f"invalid installer archive: {e}") from e

    if fs_zip.stat().st_size == 0:
        log("image does not contain a nonempty installer/fs.zip, no db certificate to enroll")
        return None
    try:
        with zipfile.ZipFile(fs_zip) as archive:
            try:
                member = archive.getinfo("boot/DB.auth")
            except KeyError:
                member = None
            if member is None or member.file_size == 0:
                log("image does not bundle boot/DB.auth, no db certificate to enroll")
                return None
            if member.flag_bits & 1:
                raise secure_boot_db.ScriptError("boot/DB.auth must not be encrypted")
            auth = work / "DB.auth"
            with archive.open(member) as source, auth.open("wb") as destination:
                shutil.copyfileobj(source, destination)
            return auth
    except (zipfile.BadZipFile, EOFError, UnicodeDecodeError, NotImplementedError, zlib.error, lzma.LZMAError) as e:
        raise secure_boot_db.ScriptError(f"invalid installer/fs.zip: {e}") from e


def persist_auth(auth, auth_dir):
    """Keep authorized updates under content-addressed names without overwriting files."""
    data = auth.read_bytes()
    destination = auth_dir / f"DB-{hashlib.sha256(data).hexdigest()}.auth"
    auth_dir.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("xb") as output:
            output.write(data)
    except FileExistsError:
        if destination.read_bytes() != data:
            raise secure_boot_db.ScriptError(
                f"{destination} already exists with different content (sha256 collision)"
            )
        log(f"DB.auth already present at {destination}, not copying")
    else:
        log(f"copied DB.auth to {destination}")
    return destination


@locked
def enroll_db_certificate(image_file, *, check_only=False, config=None):
    """Inspect or enroll a bundled update; return False only when check mode finds none."""
    image_path = Path(image_file)
    if not image_path.is_file():
        raise secure_boot_db.ScriptError(f"image file '{image_file}' not found")
    if config is None:
        host_path = Path(os.environ.get("SONIC_HOST_PATH", "/host"))
        config = secure_boot_db.Config.from_env(
            auth_dir=os.environ.get("SONIC_DB_AUTH_DIR", host_path / "db-auth"),
        )
    with tempfile.TemporaryDirectory(prefix=".secure_boot_enroll_db.", dir=config.host_path) as directory:
        work = Path(directory)
        auth = extract_db_auth(image_path, work)
        if auth is None:
            return not check_only
        if check_only:
            log("image bundles boot/DB.auth")
            return True

        ensure_efivars(config)
        update = secure_boot_db.parse_auth(auth.read_bytes())
        trusted = secure_boot_db.build_trusted_pem(config, work, authorities=ENROLLMENT_AUTHORITIES)
        if not secure_boot_db.verify_db_auth(
            update, secure_boot_db.DB_ATTR_APPEND, True, trusted, work / "DB-auth",
        ):
            raise secure_boot_db.ScriptError(
                "failed to enroll db certificate: "
                "DB.auth is not a valid append update authorized by an enrolled PK or KEK"
            )
        persist_auth(auth, config.auth_dir)
        log("enrolling bundled db certificate into UEFI db")
        if not secure_boot_db.update_db(config, auth, append=True):
            raise secure_boot_db.ScriptError(
                "failed to enroll db certificate (db immutable, or its update is not authorized by an enrolled KEK)"
            )
        log("db certificate enrolled")
    return True


def main(argv=None):
    """Run the standalone enrollment command, reporting expected errors as exit status 1."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="only check whether the image bundles boot/DB.auth")
    parser.add_argument("image_file", help="SONiC installer image")
    args = parser.parse_args(argv)
    try:
        return 0 if enroll_db_certificate(args.image_file, check_only=args.check) else 1
    except (secure_boot_db.ScriptError, OSError, subprocess.SubprocessError) as e:
        log(f"ERROR: {e}")
        return 1

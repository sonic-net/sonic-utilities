import io
import os
import stat
import struct
import subprocess
import tarfile
import zipfile
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "secure_boot_enroll_db.sh"


def _write_executable(path, contents):
    path.write_text(contents)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _create_installer(path):
    auth = b"\0" * 16 + struct.pack("<I", 25) + b"\0" * 20 + b"\x30"
    fs_zip = io.BytesIO()
    with zipfile.ZipFile(fs_zip, "w") as archive:
        archive.writestr("boot/DB.auth", auth)

    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        info = tarfile.TarInfo("installer/fs.zip")
        info.size = len(fs_zip.getvalue())
        archive.addfile(info, io.BytesIO(fs_zip.getvalue()))

    path.write_bytes(b"#!/bin/sh\nexit_marker\n" + payload.getvalue())
    return auth


def _run_enrollment(tmp_path, authorized, check=False):
    fake_bin = tmp_path / "bin"
    host = tmp_path / "host"
    efivars = tmp_path / "efivars"
    auth_dir = tmp_path / "db-auth"
    update_marker = tmp_path / "efi-updatevar-called"
    image = tmp_path / "sonic-vs.bin"

    fake_bin.mkdir()
    host.mkdir()
    efivars.mkdir()
    expected_auth = _create_installer(image)

    _write_executable(fake_bin / "mountpoint", "#!/bin/sh\nexit 0\n")
    _write_executable(
        fake_bin / "efi-readvar",
        """#!/bin/sh
while [ "$#" -gt 0 ]; do
    if [ "$1" = "-o" ]; then
        shift
        printf authority > "$1"
        exit 0
    fi
    shift
done
exit 1
""",
    )
    _write_executable(
        fake_bin / "sig-list-to-certs",
        '#!/bin/sh\nprintf certificate > "$2-0.der"\n',
    )
    _write_executable(
        fake_bin / "openssl",
        """#!/bin/sh
case "$1" in
    x509) printf '%s\n' '-----BEGIN CERTIFICATE-----' trusted '-----END CERTIFICATE-----' ;;
    cms) [ "$DB_AUTH_AUTHORIZED" = "yes" ] ;;
    *) exit 1 ;;
esac
""",
    )
    _write_executable(
        fake_bin / "efi-updatevar",
        '#!/bin/sh\nprintf called > "$EFI_UPDATEVAR_MARKER"\n',
    )

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "SONIC_HOST_PATH": str(host),
            "SONIC_EFIVARS_DIR": str(efivars),
            "SONIC_DB_AUTH_DIR": str(auth_dir),
            "DB_AUTH_AUTHORIZED": "yes" if authorized else "no",
            "EFI_UPDATEVAR_MARKER": str(update_marker),
        }
    )
    result = subprocess.run(
        [str(SCRIPT), *(["--check"] if check else []), str(image)],
        capture_output=True,
        env=env,
        text=True,
        check=False,
    )
    return result, auth_dir, update_marker, expected_auth


def test_enrolls_db_auth_authorized_by_firmware_authority(tmp_path):
    result, auth_dir, update_marker, expected_auth = _run_enrollment(
        tmp_path, authorized=True
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert update_marker.exists()
    persisted = list(auth_dir.glob("DB-*.auth"))
    assert len(persisted) == 1
    assert persisted[0].read_bytes() == expected_auth


def test_rejects_unauthorized_db_auth_before_firmware_write(tmp_path):
    result, auth_dir, update_marker, _ = _run_enrollment(
        tmp_path, authorized=False
    )

    assert result.returncode == 1
    assert (
        "failed to enroll db certificate: "
        "DB.auth is not authorized by an enrolled PK or KEK"
    ) in result.stdout
    assert not update_marker.exists()
    assert not auth_dir.exists()


def test_check_only_reports_embedded_db_auth(tmp_path):
    result, auth_dir, update_marker, _ = _run_enrollment(
        tmp_path, authorized=False, check=True
    )

    assert result.returncode == 0
    assert "image bundles boot/DB.auth" in result.stdout
    assert not update_marker.exists()
    assert not auth_dir.exists()

import os
import stat
import struct
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "remove_stale_db_certs.sh"


def _write_executable(path, contents):
    path.write_text(contents)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_plan_marks_installed_kernel_and_fallback_loader_as_essential(tmp_path):
    fake_bin = tmp_path / "bin"
    host = tmp_path / "host"
    esp = tmp_path / "esp" / "EFI"
    efivars = tmp_path / "efivars"
    auth_dir = tmp_path / "db-auth"
    update_marker = tmp_path / "efi-updatevar-called"

    for directory in (
        fake_bin,
        host / "image-test" / "boot",
        esp / "SONiC-OS",
        esp / "BOOT",
        efivars,
        auth_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    (host / "image-test" / "boot" / "vmlinuz-test").write_text("kernel")
    (esp / "SONiC-OS" / "shimx64.efi").write_text("shim")
    (esp / "BOOT" / "BOOTX64.EFI").write_text("fallback")
    (efivars / "db-test").write_text("db")

    # A minimally shaped authenticated update carrying CERT0. CERT1 deliberately
    # has no matching .auth, so both the kernel and fallback loader are at risk.
    (auth_dir / "DB-cert0.auth").write_bytes(
        b"\0" * 16 + struct.pack("<I", 24) + b"\0" * 20 + b"ESL"
    )

    _write_executable(
        fake_bin / "id",
        """#!/bin/sh
if [ "$1" = "-u" ]; then echo 0; else /usr/bin/id "$@"; fi
""",
    )
    _write_executable(
        fake_bin / "sonic-installer",
        """#!/bin/sh
cat <<EOF
Current: SONiC-OS-test
Next: SONiC-OS-test
Available:
SONiC-OS-test
EOF
""",
    )
    _write_executable(
        fake_bin / "efi-readvar",
        """#!/bin/sh
while [ "$#" -gt 0 ]; do
    if [ "$1" = "-o" ]; then shift; printf db > "$1"; exit 0; fi
    shift
done
exit 1
""",
    )
    _write_executable(
        fake_bin / "sig-list-to-certs",
        """#!/bin/sh
case "$2" in
    */db)
        printf CERT0 > "$2-0.der"
        printf CERT1 > "$2-1.der"
        ;;
    */am_cert)
        printf CERT0 > "$2-0.der"
        ;;
esac
""",
    )
    _write_executable(
        fake_bin / "openssl",
        """#!/bin/sh
input=""
output=""
previous=""
for argument in "$@"; do
    [ "$previous" = "-in" ] && input="$argument"
    [ "$previous" = "-out" ] && output="$argument"
    previous="$argument"
done
if [ -n "$output" ]; then
    cp "$input" "$output"
    exit 0
fi
if grep -q CERT1 "$input"; then cert=1; else cert=0; fi
case " $* " in
    *" -subject "*) echo "subject=CN=CERT$cert" ;;
    *" -issuer "*) echo "issuer=CN=TEST" ;;
    *" -fingerprint "*) echo "SHA256 Fingerprint=FP$cert" ;;
    *" -enddate "*) echo "notAfter=Jan 1 00:00:00 2099 GMT" ;;
esac
""",
    )
    _write_executable(
        fake_bin / "sbverify",
        """#!/bin/sh
cert="$2"
binary="$3"
case "$(basename "$binary")" in
    shimx64.efi) grep -q CERT0 "$cert" ;;
    vmlinuz-test|BOOTX64.EFI) grep -q CERT1 "$cert" ;;
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
            "SONIC_ESP_PATH": str(esp),
            "SONIC_OS_DIR": str(esp / "SONiC-OS"),
            "SONIC_EFIVARS_DIR": str(efivars),
            "SONIC_DB_AUTH_DIR": str(auth_dir),
            "EFI_UPDATEVAR_MARKER": str(update_marker),
        }
    )

    result = subprocess.run(
        [str(SCRIPT), "--plan"],
        capture_output=True,
        env=env,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "essential_missing=2" in result.stdout
    assert "boot-chain binary would lose all db signers" in result.stderr
    assert "vmlinuz-test" in result.stderr
    assert "BOOTX64.EFI" in result.stderr

    commit_result = subprocess.run(
        [str(SCRIPT), "--commit"],
        capture_output=True,
        env=env,
        stdin=subprocess.DEVNULL,
        text=True,
        check=False,
    )

    assert commit_result.returncode == 2
    assert "Refusing to touch db" in commit_result.stderr
    assert not update_marker.exists()

#!/bin/bash
# Enroll the UEFI Secure Boot db certificate bundled inside a SONiC installer image
# (boot/DB.auth) into the running system's UEFI db variable.
#
# This must run BEFORE the image's CMS signature is verified (verify_image_sign.sh reads the
# verification certificate from the UEFI db via "efi-readvar -v db"). When an image is signed
# with a rotated db key, the new db certificate is not yet present in the firmware, so the
# verification would fail. Enrolling the bundled, pre-signed db update here lets the new image
# be verified and trusted without a manual key-enrollment step.
#
# Security: DB.auth is a TIME_BASED_AUTHENTICATED_WRITE update signed at build time. Before
# invoking firmware, this script verifies that the actual CMS signer chains to an enrolled PK or
# KEK certificate. This avoids relying on firmware error handling, which is not guaranteed to
# leave the variable intact after an unauthorized update attempt.
#
# Usage:
#   secure_boot_enroll_db.sh <image_file>
#   secure_boot_enroll_db.sh --check <image_file>
#
# Check mode only verifies that boot/DB.auth is present. Enrollment failures are
# returned to sonic-installer, which continues to image-signature verification.

set -euo pipefail

mode="enroll"
if [ "${1:-}" = "--check" ]; then
    mode="check"
    shift
fi
image_file="${1:-}"
DB_GUID="d719b2cb-3d3a-4596-a3bc-dad00e67656f"
EFIVARS_DIR="${SONIC_EFIVARS_DIR:-/sys/firmware/efi/efivars}"
DB_VAR="${EFIVARS_DIR}/db-${DB_GUID}"
HOST_PATH="${SONIC_HOST_PATH:-/host}"
DB_AUTH_DIR="${SONIC_DB_AUTH_DIR:-$HOST_PATH/db-auth}"

log() {
    echo "secure_boot_enroll_db: $*"
}

if [ -z "$image_file" ] || [ ! -f "$image_file" ]; then
    log "ERROR: image file '${image_file}' not found"
    exit 1
fi

TMP_DIR=$(mktemp -d "$HOST_PATH/.secure_boot_enroll_db.XXXXXX")
trap 'rm -rf "$TMP_DIR"' EXIT
FS_ZIP="${TMP_DIR}/fs.zip"
DB_AUTH="${TMP_DIR}/DB.auth"

# The .bin is a self-extracting archive: a shell header up to the "exit_marker" line, followed
# by a tar of the installer/ directory (which contains fs.zip), then an optional appended CMS
# signature. Strip the header, then pull installer/fs.zip out of the tar; --occurrence=1 makes
# tar stop after the first match so the trailing signature is ignored.
SHARCH_SIZE=$(sed '/^exit_marker$/q' "$image_file" | wc -c)
tail -c +$((SHARCH_SIZE + 1)) "$image_file" | tar --occurrence=1 -xO installer/fs.zip 2>/dev/null > "$FS_ZIP" || true
if [ ! -s "$FS_ZIP" ]; then
    log "image does not contain installer/fs.zip, no db certificate to enroll"
    [ "$mode" = "check" ] && exit 1
    exit 0
fi

unzip -p "$FS_ZIP" boot/DB.auth 2>/dev/null > "$DB_AUTH" || true
if [ ! -s "$DB_AUTH" ]; then
    log "image does not bundle boot/DB.auth, no db certificate to enroll"
    [ "$mode" = "check" ] && exit 1
    exit 0
fi

if [ "$mode" = "check" ]; then
    log "image bundles boot/DB.auth"
    exit 0
fi

if [ ! -d "$EFIVARS_DIR" ]; then
    log "ERROR: efivars not available at $EFIVARS_DIR, cannot enroll db certificate"
    exit 1
fi
if ! mountpoint -q "$EFIVARS_DIR" 2>/dev/null; then
    if ! mount -t efivarfs efivarfs "$EFIVARS_DIR" 2>/dev/null; then
        log "ERROR: failed to mount efivarfs at $EFIVARS_DIR, cannot enroll db certificate"
        exit 1
    fi
fi

for tool in efi-readvar sig-list-to-certs openssl python3; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        log "ERROR: $tool not found, cannot validate DB.auth authorization"
        exit 1
    fi
done

AUTH_PKCS7="${TMP_DIR}/DB-auth.p7b"
AUTH_SIGNED_CONTENT="${TMP_DIR}/DB-auth.signed-content"
TRUSTED_CERTS="${TMP_DIR}/firmware-authorities.pem"

# EFI_VARIABLE_AUTHENTICATION_2 stores a WIN_CERTIFICATE_UEFI_GUID after EFI_TIME.
# Its certificate data is usually bare SignedData, while OpenSSL expects a PKCS#7
# ContentInfo wrapper. Reconstruct the exact append-write content that firmware
# verifies so a replace-only DB.auth is rejected before it reaches OVMF.
if ! python3 - "$DB_AUTH" "$AUTH_PKCS7" "$AUTH_SIGNED_CONTENT" <<'PY'
import struct
import sys


def der_length(length):
    if length < 128:
        return bytes([length])
    encoded = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(encoded)]) + encoded


def der_value_offset(value):
    if len(value) < 2 or value[0] != 0x30:
        return None
    if value[1] < 0x80:
        return 2
    length_size = value[1] & 0x7f
    if not length_size or len(value) < 2 + length_size:
        return None
    return 2 + length_size


auth = open(sys.argv[1], "rb").read()
if len(auth) < 40:
    raise SystemExit("authenticated update header is truncated")

certificate_length = int.from_bytes(auth[16:20], "little")
certificate_end = 16 + certificate_length
if certificate_length < 24 or certificate_end > len(auth):
    raise SystemExit("authenticated update certificate length is invalid")

signed_data = auth[40:certificate_end]
if not signed_data:
    raise SystemExit("authenticated update has no PKCS#7 signed data")
payload = auth[certificate_end:]
if not payload:
    raise SystemExit("authenticated append update has no signature-list payload")

signed_data_oid = bytes.fromhex("06092a864886f70d010702")
value_offset = der_value_offset(signed_data)
if value_offset is not None and signed_data[value_offset:].startswith(signed_data_oid):
    content_info = signed_data
else:
    explicit_signed_data = b"\xa0" + der_length(len(signed_data)) + signed_data
    content = signed_data_oid + explicit_signed_data
    content_info = b"\x30" + der_length(len(content)) + content

open(sys.argv[2], "wb").write(content_info)

db_vendor_guid = bytes.fromhex("cbb219d73a3d9645a3bcdad00e67656f")
append_attributes = 0x00000067
signed_content = (
    "db".encode("utf-16-le")
    + db_vendor_guid
    + struct.pack("<I", append_attributes)
    + auth[:16]
    + payload
)
open(sys.argv[3], "wb").write(signed_content)
PY
then
    log "ERROR: failed to enroll db certificate: DB.auth authentication data is malformed"
    exit 1
fi

for variable in PK KEK; do
    authority_esl="${TMP_DIR}/${variable}.esl"
    authority_prefix="${TMP_DIR}/${variable}"
    if ! efi-readvar -v "$variable" -o "$authority_esl" >/dev/null 2>&1; then
        log "ERROR: failed to read enrolled UEFI $variable certificates"
        exit 1
    fi
    if ! sig-list-to-certs "$authority_esl" "$authority_prefix" >/dev/null 2>&1; then
        log "ERROR: failed to parse enrolled UEFI $variable certificates"
        exit 1
    fi
    for certificate in "${authority_prefix}"-*.der; do
        [ -e "$certificate" ] || continue
        if ! openssl x509 -inform DER -in "$certificate" >> "$TRUSTED_CERTS"; then
            log "ERROR: failed to convert an enrolled UEFI $variable certificate"
            exit 1
        fi
    done
done

if [ ! -s "$TRUSTED_CERTS" ]; then
    log "ERROR: failed to enroll db certificate: no enrolled PK or KEK certificates are available"
    exit 1
fi

# Verify both the signer chain and the detached firmware update content. The
# reconstructed content includes EFI_VARIABLE_APPEND_WRITE, matching the -a
# passed to efi-updatevar below.
if ! openssl cms -verify -binary -inform DER -in "$AUTH_PKCS7" \
        -content "$AUTH_SIGNED_CONTENT" -no_attr_verify -no_check_time \
        -purpose any -partial_chain -CAfile "$TRUSTED_CERTS" \
        -out /dev/null >/dev/null 2>&1; then
    log "ERROR: failed to enroll db certificate: DB.auth is not a valid append update authorized by an enrolled PK or KEK"
    exit 1
fi

# Persist the db certificate shipped with the image under /host/db-auth using a unique,
# content-based name, so certificates from successive installations accumulate instead of
# overwriting each other. The file name is the certificate's sha256, so a matching name implies
# identical content; a name clash with differing content would be a hash collision and is
# treated as an error rather than silently trusting the wrong certificate.
if ! mkdir -p "$DB_AUTH_DIR"; then
    log "ERROR: failed to create $DB_AUTH_DIR"
    exit 1
fi

db_hash=$(sha256sum "$DB_AUTH" | cut -d' ' -f1)
db_dest="$DB_AUTH_DIR/DB-${db_hash}.auth"

if [ -e "$db_dest" ]; then
    if cmp -s "$DB_AUTH" "$db_dest"; then
        log "DB.auth already present at $db_dest, not copying"
    else
        log "ERROR: $db_dest already exists with different content (sha256 collision)"
        exit 1
    fi
elif cp "$DB_AUTH" "$db_dest"; then
    log "copied DB.auth to $db_dest"
else
    log "ERROR: failed to copy DB.auth to $db_dest"
    exit 1
fi

# Clear the immutable (i) attribute the kernel sets on existing Secure Boot variables so the
# variable can be written. efi-updatevar does not clear this flag itself, so it is done here.
clear_db_immutable() {
    [ -e "$DB_VAR" ] || return 0
    chattr -i "$DB_VAR" 2>/dev/null || true
}

# Enroll via efi-updatevar (efitools); append (-a) so existing db entries are preserved.
# efitools is installed in the SONiC image; if it is absent there is no supported way to
# apply a signed authenticated variable update here, so enrollment fails.
if ! command -v efi-updatevar >/dev/null 2>&1; then
    log "ERROR: efi-updatevar not found, cannot enroll db certificate"
    exit 1
fi

log "enrolling bundled db certificate into UEFI db"
clear_db_immutable
if ! efi-updatevar -a -f "$DB_AUTH" db; then
    log "ERROR: failed to enroll db certificate (db immutable, or its update is not authorized by an enrolled KEK)"
    exit 1
fi
log "db certificate enrolled"
exit 0

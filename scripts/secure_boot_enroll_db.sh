#!/bin/sh
# Enroll the UEFI Secure Boot db certificate bundled inside a SONiC installer image
# (boot/DB.auth) into the running system's UEFI db variable.
#
# This must run BEFORE the image's CMS signature is verified (verify_image_sign.sh reads the
# verification certificate from the UEFI db via "efi-readvar -v db"). When an image is signed
# with a rotated db key, the new db certificate is not yet present in the firmware, so the
# verification would fail. Enrolling the bundled, pre-signed db update here lets the new image
# be verified and trusted without a manual key-enrollment step.
#
# Security: DB.auth is a TIME_BASED_AUTHENTICATED_WRITE update that was signed (by the KEK) at
# build time. UEFI firmware validates that signature against the already-enrolled KEK before
# applying the update, so a db certificate can only be added when it is authorized by a trusted
# KEK. An image carrying a db certificate signed by an untrusted KEK is rejected by firmware,
# the db is left unchanged, and the subsequent CMS verification still fails. This therefore
# does not bypass the secure-upgrade trust model; it implements KEK-authorized db key rotation.
#
# Best-effort: every failure is logged and the script exits 0 so it never blocks an install.

image_file="${1}"
DB_GUID="d719b2cb-3d3a-4596-a3bc-dad00e67656f"
EFIVARS_DIR="/sys/firmware/efi/efivars"
DB_VAR="${EFIVARS_DIR}/db-${DB_GUID}"

log() {
    echo "secure_boot_enroll_db: $*"
}

if [ -z "$image_file" ] || [ ! -f "$image_file" ]; then
    log "image file '${image_file}' not found, skipping db enrollment"
    exit 0
fi

if [ ! -d "$EFIVARS_DIR" ]; then
    log "efivars not available, skipping db enrollment"
    exit 0
fi
if ! mountpoint -q "$EFIVARS_DIR" 2>/dev/null; then
    mount -t efivarfs efivarfs "$EFIVARS_DIR" 2>/dev/null || true
fi

TMP_DIR=$(mktemp -d)
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
    log "image does not contain installer/fs.zip, skipping db enrollment"
    exit 0
fi

unzip -p "$FS_ZIP" boot/DB.auth 2>/dev/null > "$DB_AUTH" || true
if [ ! -s "$DB_AUTH" ]; then
    log "image does not bundle boot/DB.auth, skipping db enrollment"
    exit 0
fi

# Persist the db certificate shipped with the image under /host/db-auth using a unique,
# content-based name, so certificates from successive installations accumulate instead of
# overwriting each other. If a byte-identical DB.auth is already stored, it is not copied
# again. Best-effort.
DB_AUTH_DIR=/host/db-auth
if mkdir -p "$DB_AUTH_DIR" 2>/dev/null; then
    found_auth=""
    for existing_auth in "$DB_AUTH_DIR"/*.auth; do
        [ -e "$existing_auth" ] || continue
        if cmp -s "$DB_AUTH" "$existing_auth"; then
            found_auth="$existing_auth"
            break
        fi
    done
    if [ -n "$found_auth" ]; then
        log "DB.auth already present at $found_auth, not copying"
    else
        db_hash=$(sha256sum "$DB_AUTH" 2>/dev/null | cut -d' ' -f1)
        if [ -n "$db_hash" ]; then
            db_dest="$DB_AUTH_DIR/DB-${db_hash}.auth"
        else
            db_dest="$DB_AUTH_DIR/DB-$(date -u +%Y%m%d%H%M%S).auth"
        fi
        if cp "$DB_AUTH" "$db_dest" 2>/dev/null; then
            log "copied DB.auth to $db_dest"
        else
            log "WARNING: failed to copy DB.auth to $db_dest"
        fi
    fi
else
    log "WARNING: failed to create $DB_AUTH_DIR"
fi

# Clear the immutable (i) attribute the kernel sets on existing Secure Boot variables so the
# variable can be written. Best-effort; efi-updatevar also manages the flag itself.
clear_db_immutable() {
    [ -e "$DB_VAR" ] || return 0
    if command -v chattr >/dev/null 2>&1; then
        chattr -i "$DB_VAR" 2>/dev/null || true
    fi
}

# Enroll via efi-updatevar (efitools); append (-a) so existing db entries are preserved.
# efitools is installed in the SONiC image; if it is absent there is no supported way to
# apply a signed authenticated variable update here, so enrollment is skipped.
if ! command -v efi-updatevar >/dev/null 2>&1; then
    log "efi-updatevar not found, skipping db enrollment"
    exit 0
fi

log "enrolling bundled db certificate into UEFI db"
clear_db_immutable
if efi-updatevar -a -f "$DB_AUTH" db; then
    log "db certificate enrolled"
    exit 0
fi

log "WARNING: failed to enroll db certificate (db immutable, or its update is not authorized by an enrolled KEK)"
exit 0

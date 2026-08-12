#!/bin/sh
# Apply a signed .auth update to a UEFI Secure Boot key variable (KEK or PK) in
# the running firmware. The update may enroll a key or remove all keys.
#
# Usage: secure_boot_enroll_key.sh <KEK|PK> <auth_file>
#
# sonic-installer also uses this with signed empty updates to remove KEK first
# and PK last. Removing PK transitions the firmware to Setup Mode.
#
# Unlike secure_boot_enroll_db.sh (which is best-effort and always exits 0), this
# script's exit status reflects whether the firmware accepted the update. Every
# problem is logged.
#   exit 0 - the variable update was applied
#   exit 1 - efi-updatevar was run but the firmware rejected the update
#   exit 2 - a precondition was not met (bad args, no efivars, missing efitools)

var_name="${1}"
auth_file="${2}"
EFI_GLOBAL_GUID="8be4df61-93ca-11d2-aa0d-00e098032b8c"
EFIVARS_DIR="/sys/firmware/efi/efivars"

log() {
    echo "secure_boot_enroll_key: $*"
}

case "$var_name" in
    KEK|PK) ;;
    *)
        log "unsupported variable '${var_name}' (expected KEK or PK)"
        exit 2
        ;;
esac

if [ -z "$auth_file" ] || [ ! -f "$auth_file" ]; then
    log "auth file '${auth_file}' not found"
    exit 2
fi

if [ ! -d "$EFIVARS_DIR" ]; then
    log "efivars not available; cannot update ${var_name}"
    exit 2
fi
if ! mountpoint -q "$EFIVARS_DIR" 2>/dev/null; then
    mount -t efivarfs efivarfs "$EFIVARS_DIR" 2>/dev/null || true
fi

if ! command -v efi-updatevar >/dev/null 2>&1; then
    log "efi-updatevar not found; cannot update ${var_name}"
    exit 2
fi

# Clear the immutable (i) attribute the kernel sets on existing Secure Boot
# variables so the variable can be written. Best-effort; efi-updatevar also
# manages the flag itself.
var_path="${EFIVARS_DIR}/${var_name}-${EFI_GLOBAL_GUID}"
if [ -e "$var_path" ] && command -v chattr >/dev/null 2>&1; then
    chattr -i "$var_path" 2>/dev/null || true
fi

# Apply the update via efi-updatevar (efitools). No -a: a KEK/PK update replaces
# the variable rather than appending to it. The .auth payload is a signed,
# time-based authenticated update; in Setup Mode the firmware accepts it without
# verifying the signature, and in User Mode it must be authorized by the current
# PK.
log "updating ${var_name} from ${auth_file}"
if efi-updatevar -f "$auth_file" "$var_name"; then
    log "${var_name} updated"
    exit 0
fi

log "WARNING: failed to update ${var_name} (firmware rejected the update or the variable is not writable)"
exit 1

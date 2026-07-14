#!/bin/sh
#
# remove_stale_db_certs.sh
#
# Delete ALL UEFI Secure Boot "db" certificates and reinstall ONLY the ones that
# sign an installed SONiC image. Net effect: db is pruned down to exactly the
# certificates that actually verify a shim / grub / MokManager / kernel binary of
# an installed image, using pre-existing signed .auth files.
#
# Strategy
#   1. Read the current db and split it into individual X.509 certificates.
#   2. Determine which db certificates sign an installed image by verifying every
#      signed EFI binary (sbverify --cert) of every installed image AND of the
#      active ESP -- in particular EFI/SONiC-OS/{shimx64,grubx64,mmx64}.efi.
#   3. Map each "used" db certificate to a reinstall .auth file (assumed to exist)
#      by matching SHA-256 fingerprints of the certificate embedded in each .auth.
#   4. SAFETY GATE: refuse to proceed unless every boot-critical binary under
#      EFI/SONiC-OS keeps at least one db signer that we can reinstall. This
#      guarantees the db certificate signing shim/grub/MokManager is not lost.
#   5. Apply a single "remove-all" .auth (an empty-EFI-Signature-List replacement,
#      signed by KEK) to delete every db certificate, then append each selected
#      reinstall .auth to put the image-signing certificates back.
#
# This script is DRY-RUN by default (it only prints the plan). It modifies UEFI
# NVRAM only when given --commit.
#
# It is bundled into the SONiC image and invoked by "sonic-installer remove
# --prune-db-cert" (see sonic_installer/bootloader/grub.py). That caller first
# runs it with --plan to read the machine-readable "PRUNE_PLAN ..." summary line,
# decides whether operator confirmation is needed, then runs it with --commit
# (adding --allow-essential-missing only when the operator approved losing a
# boot-critical signer). It can also be run standalone.
#
# Requirements
#   Must run as root on a UEFI SONiC device with efi-readvar, sig-list-to-certs,
#   sbverify, openssl and efi-updatevar in PATH. mokutil is optional.
#
# Inputs (assumed to exist, per the task):
#   --auth-dir DIR     Directory holding one signed .auth file per db certificate
#                      (append-enrollment auths). Used to reinstall image signers.
#                      On a SONiC device this is /host/db-auth, populated by
#                      secure_boot_enroll_db.sh at each image install.
#   --remove-all FILE  A signed .auth that replaces db with an empty signature list
#                      (deletes every db certificate). Defaults to
#                      <auth-dir>/remove-all-db.auth (must already exist).
#
# Exit status: 0 success (or clean dry-run/plan), 2 on any error / aborted safety
# gate.
#

set -u

PROG="$(basename "$0")"

VERBOSE=0
COMMIT=0
PLAN=0
ASSUME_YES=0
ALLOW_ESSENTIAL_MISSING=0

# Paths may be overridden via environment (useful for chroot/mounted layouts and
# self-tests); they default to the standard on-device locations.
HOST_PATH="${SONIC_HOST_PATH:-/host}"
ESP_PATH="${SONIC_ESP_PATH:-/boot/efi/EFI}"
SONIC_OS_DIR="${SONIC_OS_DIR:-$ESP_PATH/SONiC-OS}"
IMAGE_PREFIX="SONiC-OS-"
IMAGE_DIR_PREFIX="image-"
EFIVARS_DIR="${SONIC_EFIVARS_DIR:-/sys/firmware/efi/efivars}"

AUTH_DIR="${SONIC_DB_AUTH_DIR:-/host/db-auth}"
REMOVE_ALL_AUTH=""           # resolved after arg parse (defaults into AUTH_DIR)

usage() {
    cat <<EOF
$PROG - delete all UEFI 'db' certificates and reinstall only those that sign an
        installed SONiC image, using pre-existing signed .auth files.

Usage: $PROG [options]

  --auth-dir DIR     Directory of per-certificate reinstall .auth files
                     (default: \$SONIC_DB_AUTH_DIR or /host/db-auth).
  --remove-all FILE  Signed .auth that empties db (deletes all certs)
                     (default: <auth-dir>/remove-all-db.auth).
      --commit       Actually modify UEFI db. Without this, the script is a
                     read-only dry-run that just prints the plan.
      --plan         Analyse only and print a machine-readable "PRUNE_PLAN ..."
                     summary line; never modifies db and never fails on a safety
                     condition (so a caller can inspect the plan and decide).
      --allow-essential-missing
                     Proceed with --commit even if a boot-critical (shim/grub/
                     MokManager) binary would lose every db signer because no
                     reinstall .auth is available. DANGEROUS: the system may fail
                     Secure Boot verification after reboot. Off by default.
      --yes          Skip the interactive confirmation when committing.
  -v, --verbose      Print the full per-binary -> db certificate mapping.
  -h, --help         Show this help and exit.

The script is DRY-RUN unless --commit is given. Run as root on a UEFI SONiC
device. Requires efi-readvar, sig-list-to-certs, sbverify, openssl, efi-updatevar.
EOF
}

die()  { echo "$PROG: error: $*" >&2; exit 2; }
warn() { echo "$PROG: warning: $*" >&2; }

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [ $# -gt 0 ]; do
    case "$1" in
        --auth-dir)    shift; [ $# -gt 0 ] || die "--auth-dir needs a value"; AUTH_DIR="$1" ;;
        --remove-all)  shift; [ $# -gt 0 ] || die "--remove-all needs a value"; REMOVE_ALL_AUTH="$1" ;;
        --commit)      COMMIT=1 ;;
        --plan)        PLAN=1 ;;
        --allow-essential-missing) ALLOW_ESSENTIAL_MISSING=1 ;;
        --yes)         ASSUME_YES=1 ;;
        -v|--verbose)  VERBOSE=1 ;;
        -h|--help)     usage; exit 0 ;;
        *)             die "unknown argument: $1 (see -h)" ;;
    esac
    shift
done

[ -n "$REMOVE_ALL_AUTH" ] || REMOVE_ALL_AUTH="$AUTH_DIR/remove-all-db.auth"

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------
[ "$(id -u)" -eq 0 ] || die "must be run as root (needs to read/write $EFIVARS_DIR and $HOST_PATH)"

for tool in efi-readvar sig-list-to-certs sbverify openssl efi-updatevar; do
    command -v "$tool" >/dev/null 2>&1 || die "required tool not found in PATH: $tool"
done

HAVE_MOKUTIL=0
command -v mokutil >/dev/null 2>&1 && HAVE_MOKUTIL=1
HAVE_CHATTR=0
command -v chattr >/dev/null 2>&1 && HAVE_CHATTR=1

if [ ! -d "$EFIVARS_DIR" ] || [ -z "$(ls -A "$EFIVARS_DIR" 2>/dev/null)" ]; then
    mount -t efivarfs efivarfs "$EFIVARS_DIR" 2>/dev/null || true
fi
{ [ -d "$EFIVARS_DIR" ] && [ -n "$(ls -A "$EFIVARS_DIR" 2>/dev/null)" ]; } \
    || die "UEFI efivars not available at $EFIVARS_DIR (not a UEFI system, or firmware access blocked)"

SB_STATE="unknown"
if [ "$HAVE_MOKUTIL" -eq 1 ]; then
    _sb="$(mokutil --sb-state 2>/dev/null)"
    case "$_sb" in
        *[Ee]nabled*)  SB_STATE="enabled" ;;
        *[Dd]isabled*) SB_STATE="disabled" ;;
    esac
fi

[ -d "$AUTH_DIR" ] || warn "auth directory not found: $AUTH_DIR (reinstall will find no .auth files)"

# ---------------------------------------------------------------------------
# Work area
# ---------------------------------------------------------------------------
WORK="$(mktemp -d)" || die "mktemp failed"
trap 'rm -rf "$WORK"' EXIT INT TERM

CERTS_DIR="$WORK/db_certs"
USED_FILE="$WORK/used_indices"
TARGETS="$WORK/targets.psv"        # label|tag|dir|crit
BINS="$WORK/bins.psv"              # binpath  (unique)
CRIT_BINS="$WORK/crit_bins.psv"    # binpath  (unique, boot-critical)
RECORDS="$WORK/records.psv"        # binpath|matched-idxs
AUTH_MAP="$WORK/auth_map.psv"      # fingerprint|authfile
SEL_AUTHS="$WORK/selected_auths"   # authfile (unique) to reinstall
REINSTALL_FPS="$WORK/reinstall_fps" # fingerprints that will be present afterwards
mkdir -p "$CERTS_DIR"
: > "$USED_FILE"; : > "$TARGETS"; : > "$BINS"; : > "$CRIT_BINS"
: > "$RECORDS"; : > "$AUTH_MAP"; : > "$SEL_AUTHS"; : > "$REINSTALL_FPS"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Echo the signed EFI binaries found in a directory, one per line.
discover_binaries() {
    _d="$1"
    [ -d "$_d" ] || return 0
    for _pat in 'shim*.efi' 'mm*.efi' 'grub*.efi' 'vmlinuz-*'; do
        for _f in "$_d"/$_pat; do
            [ -e "$_f" ] || continue
            # Ignore the network-boot GRUB variants (grubnetx64.efi, grubnetx64-installer.efi,
            # grubnetia32*.efi, ...). They are not used for normal disk boot, so they are neither
            # treated as boot-critical nor counted when deciding which db certificates are in use.
            case "$(basename "$_f")" in
                grubnet*) continue ;;
            esac
            printf '%s\n' "$_f"
        done
    done
}

# Read one field (1-based) from a db cert metadata file.
meta_field() {
    _idx="$1"; _n="$2"
    [ -f "$WORK/meta-$_idx.psv" ] || return 0
    cut -d'|' -f"$_n" "$WORK/meta-$_idx.psv"
}

print_cert() {
    _idx="$1"; _ind="$2"
    if [ -f "$WORK/meta-$_idx.psv" ]; then
        printf '%sdb[%s] %s\n'          "$_ind" "$_idx" "$(meta_field "$_idx" 2)"
        printf '%s      sha256 : %s\n'  "$_ind" "$(meta_field "$_idx" 4)"
        printf '%s      expires: %s\n'  "$_ind" "$(meta_field "$_idx" 5)"
    else
        printf '%sdb[%s] (certificate metadata unavailable)\n' "$_ind" "$_idx"
    fi
}

# Endian-safe read of a little-endian uint32 at byte <offset> of <file>.
read_u32le() {
    _f="$1"; _off="$2"
    set -- $(dd if="$_f" bs=1 skip="$_off" count=4 2>/dev/null | od -An -tu1 | tr -s ' ' '\n' | grep -v '^$')
    [ $# -eq 4 ] || return 1
    echo $(( $1 + ($2 * 256) + ($3 * 65536) + ($4 * 16777216) ))
}

# Extract the EFI Signature List payload carried by an EFI_VARIABLE_AUTHENTICATION_2
# .auth file into <out>. Layout: EFI_TIME(16) + WIN_CERTIFICATE_UEFI_GUID(dwLength)
# + Data(ESL). dwLength is a LE uint32 at offset 16.
auth_to_esl() {
    _auth="$1"; _out="$2"
    [ -s "$_auth" ] || return 1
    _dw="$(read_u32le "$_auth" 16)" || return 1
    { [ -n "$_dw" ] && [ "$_dw" -ge 24 ]; } || return 1
    _off=$((16 + _dw))
    dd if="$_auth" of="$_out" bs=1 skip="$_off" 2>/dev/null
    [ -s "$_out" ] || return 1
}

# ---------------------------------------------------------------------------
# Build the db certificate table
# ---------------------------------------------------------------------------
efi-readvar -v db -o "$WORK/db_efi" >/dev/null 2>&1 \
    || die "failed to read the UEFI db variable (efi-readvar -v db)"
sig-list-to-certs "$WORK/db_efi" "$CERTS_DIR/db" >/dev/null 2>&1 \
    || die "failed to convert the db signature list to certificates (sig-list-to-certs)"

for der in "$CERTS_DIR"/db-*.der; do
    [ -e "$der" ] || continue
    base="$(basename "$der" .der)"      # db-N
    idx="${base#db-}"
    pem="$CERTS_DIR/$base.pem"
    openssl x509 -inform der -in "$der" -out "$pem" 2>/dev/null || continue
    subj="$(openssl x509 -in "$pem" -noout -subject 2>/dev/null | sed 's/^subject= *//')"
    iss="$(openssl x509 -in "$pem" -noout -issuer  2>/dev/null | sed 's/^issuer= *//')"
    fp="$(openssl x509 -in "$pem" -noout -fingerprint -sha256 2>/dev/null | sed 's/^.*=//')"
    naft="$(openssl x509 -in "$pem" -noout -enddate 2>/dev/null | sed 's/^notAfter=//')"
    printf '%s|%s|%s|%s|%s\n' "$idx" "$subj" "$iss" "$fp" "$naft" > "$WORK/meta-$idx.psv"
    echo "$idx" >> "$WORK/db_idx_list"
done

[ -f "$WORK/db_idx_list" ] || die "no X.509 certificates found in the UEFI db variable"
DB_INDICES="$(sort -n "$WORK/db_idx_list" | tr '\n' ' ')"
DB_COUNT="$(sort -n -u "$WORK/db_idx_list" | grep -c .)"
[ "$DB_COUNT" -gt 0 ] || die "no X.509 certificates found in the UEFI db variable"

# ---------------------------------------------------------------------------
# Enumerate installed SONiC images (targets) and the boot-critical ESP dir
# ---------------------------------------------------------------------------
CURRENT_IMG=""
NEXT_IMG=""
IMAGES=""

if command -v sonic-installer >/dev/null 2>&1; then
    SI_OUT="$(sonic-installer list 2>/dev/null || true)"
    CURRENT_IMG="$(printf '%s\n' "$SI_OUT" | sed -n 's/^Current: *//p' | head -n1)"
    NEXT_IMG="$(printf '%s\n' "$SI_OUT" | sed -n 's/^Next: *//p' | head -n1)"
    IMAGES="$(printf '%s\n' "$SI_OUT" | grep -o "${IMAGE_PREFIX}[^ ]*" | sort -u)"
fi
if [ -z "$IMAGES" ] && [ -r "$HOST_PATH/grub/grub.cfg" ]; then
    IMAGES="$(grep '^menuentry' "$HOST_PATH/grub/grub.cfg" 2>/dev/null \
              | grep -o "${IMAGE_PREFIX}[^']*" | sort -u)"
fi
if [ -z "$CURRENT_IMG" ]; then
    _cur="$(sed -n 's:.*loop=/*image-\([^/ ]*\)/.*:\1:p' /proc/cmdline 2>/dev/null | head -n1)"
    [ -n "$_cur" ] && CURRENT_IMG="${IMAGE_PREFIX}${_cur}"
fi

# Non-critical image/ESP targets (used to decide which certs sign "an image").
if [ -n "$IMAGES" ]; then
    for img in $IMAGES; do
        ver="${img#"$IMAGE_PREFIX"}"
        bootdir="$HOST_PATH/$IMAGE_DIR_PREFIX$ver/boot"
        tag=""
        [ "$img" = "$CURRENT_IMG" ] && tag="current"
        [ "$img" = "$NEXT_IMG" ] && tag="${tag:+$tag,}next"
        if [ -z "$(discover_binaries "$bootdir")" ] && [ "$img" = "$CURRENT_IMG" ]; then
            for d in "$ESP_PATH"/*/; do
                [ -d "$d" ] || continue
                if [ -n "$(discover_binaries "${d%/}")" ]; then bootdir="${d%/}"; break; fi
            done
        fi
        printf '%s|%s|%s|0\n' "$img" "$tag" "$bootdir" >> "$TARGETS"
    done
else
    warn "no installed SONiC images found via sonic-installer or grub.cfg; relying on ESP contents"
fi
# Include every ESP loader directory as well.
for d in "$ESP_PATH"/*/; do
    [ -d "$d" ] || continue
    printf '%s|%s|%s|0\n' "ESP:$(basename "$d")" "active" "${d%/}" >> "$TARGETS"
done

# Boot-critical target: EFI/SONiC-OS holding shim/grub/MokManager. Fall back to any
# ESP subdirectory that actually contains a shim if SONiC-OS is absent.
CRIT_DIR=""
if [ -n "$(discover_binaries "$SONIC_OS_DIR")" ]; then
    CRIT_DIR="$SONIC_OS_DIR"
else
    for d in "$ESP_PATH"/*/; do
        [ -d "$d" ] || continue
        for s in "${d%/}"/shim*.efi; do
            [ -e "$s" ] && { CRIT_DIR="${d%/}"; break; }
        done
        [ -n "$CRIT_DIR" ] && break
    done
fi
if [ -n "$CRIT_DIR" ]; then
    printf '%s|%s|%s|1\n' "CRITICAL:$(basename "$CRIT_DIR")" "boot" "$CRIT_DIR" >> "$TARGETS"
else
    warn "boot-critical loader dir not found (looked for $SONIC_OS_DIR and ESP shim*.efi)"
fi

[ -s "$TARGETS" ] || die "no image/ESP directories with EFI binaries found under $HOST_PATH or $ESP_PATH"

# ---------------------------------------------------------------------------
# Expand targets into a de-duplicated set of binaries (+ the critical subset)
# ---------------------------------------------------------------------------
while IFS='|' read -r label tag bootdir crit; do
    for b in $(discover_binaries "$bootdir"); do
        grep -Fxq "$b" "$BINS" || printf '%s\n' "$b" >> "$BINS"
        if [ "$crit" = "1" ]; then
            grep -Fxq "$b" "$CRIT_BINS" || printf '%s\n' "$b" >> "$CRIT_BINS"
        fi
    done
done < "$TARGETS"

[ -s "$BINS" ] || die "no signed EFI binaries discovered in any target directory"

# ---------------------------------------------------------------------------
# Match every binary against every db certificate; record which certs are used
# ---------------------------------------------------------------------------
while IFS= read -r f; do
    [ -n "$f" ] || continue
    matched=""
    for idx in $DB_INDICES; do
        pem="$CERTS_DIR/db-$idx.pem"
        [ -f "$pem" ] || continue
        if sbverify --cert "$pem" "$f" >/dev/null 2>&1; then
            matched="$matched$idx "
            echo "$idx" >> "$USED_FILE"
        fi
    done
    printf '%s|%s\n' "$f" "$(printf '%s' "$matched" | sed 's/ *$//')" >> "$RECORDS"
done < "$BINS"

USED_SORTED="$(sort -n -u "$USED_FILE" 2>/dev/null | tr '\n' ' ')"

# ---------------------------------------------------------------------------
# Build the .auth fingerprint map from AUTH_DIR
# ---------------------------------------------------------------------------
_rm_all_base="$(basename "$REMOVE_ALL_AUTH")"
if [ -d "$AUTH_DIR" ]; then
    for a in "$AUTH_DIR"/*.auth; do
        [ -e "$a" ] || continue
        [ "$(basename "$a")" = "$_rm_all_base" ] && continue   # never treat remove-all as a signer
        esl="$WORK/am_esl"
        rm -f "$WORK"/am_cert-*.der 2>/dev/null
        if ! auth_to_esl "$a" "$esl"; then
            warn "could not parse an ESL from $a (skipping)"; continue
        fi
        if ! sig-list-to-certs "$esl" "$WORK/am_cert" >/dev/null 2>&1; then
            warn "no certificate found in $a (skipping)"; continue
        fi
        for d in "$WORK"/am_cert-*.der; do
            [ -e "$d" ] || continue
            fp="$(openssl x509 -inform der -in "$d" -noout -fingerprint -sha256 2>/dev/null | sed 's/^.*=//')"
            [ -n "$fp" ] && printf '%s|%s\n' "$fp" "$a" >> "$AUTH_MAP"
        done
    done
fi

# ---------------------------------------------------------------------------
# Select reinstall .auth files for the used certificates
# ---------------------------------------------------------------------------
: > "$WORK/reinstallable_idx"
: > "$WORK/missing_auth_idx"
for idx in $USED_SORTED; do
    fp="$(meta_field "$idx" 4)"
    a="$(awk -F'|' -v f="$fp" '$1==f{print $2; exit}' "$AUTH_MAP")"
    if [ -n "$a" ]; then
        echo "$a"   >> "$SEL_AUTHS"
        echo "$idx" >> "$WORK/reinstallable_idx"
    else
        echo "$idx" >> "$WORK/missing_auth_idx"
    fi
done
sort -u "$SEL_AUTHS" -o "$SEL_AUTHS" 2>/dev/null || true

# Fingerprints that will be present after reinstall = every cert carried by the
# selected .auth files (a multi-cert .auth reinstalls all of its certs).
while IFS= read -r a; do
    [ -n "$a" ] || continue
    awk -F'|' -v f="$a" '$2==f{print $1}' "$AUTH_MAP" >> "$REINSTALL_FPS"
done < "$SEL_AUTHS"
sort -u "$REINSTALL_FPS" -o "$REINSTALL_FPS" 2>/dev/null || true

# ---------------------------------------------------------------------------
# SAFETY GATE: every boot-critical binary must keep a reinstallable db signer
# ---------------------------------------------------------------------------
CRIT_FAIL=0
CRIT_AT_RISK=0
CRIT_TOTAL=0
if [ -s "$CRIT_BINS" ]; then
    while IFS= read -r cbin; do
        [ -n "$cbin" ] || continue
        CRIT_TOTAL=$((CRIT_TOTAL + 1))
        matched="$(awk -F'|' -v b="$cbin" '$1==b{print $2}' "$RECORDS")"
        if [ -z "$matched" ]; then
            warn "boot-critical binary has NO db signer at all: $cbin"
            warn "  (it must be validated outside db; deleting db will not restore it -- verify manually)"
            continue
        fi
        keep=0
        for idx in $matched; do
            fp="$(meta_field "$idx" 4)"
            if grep -Fxq "$fp" "$REINSTALL_FPS"; then keep=1; break; fi
        done
        if [ "$keep" -eq 0 ]; then
            echo "$PROG: SAFETY: boot-critical binary would lose all db signers: $cbin" >&2
            for idx in $matched; do
                echo "         signed by db[$idx] $(meta_field "$idx" 2) sha256 $(meta_field "$idx" 4)" >&2
                echo "         -> no matching .auth in $AUTH_DIR to reinstall it" >&2
            done
            CRIT_FAIL=1
            CRIT_AT_RISK=$((CRIT_AT_RISK + 1))
        fi
    done < "$CRIT_BINS"
else
    warn "no boot-critical binaries were identified under $SONIC_OS_DIR"
fi

# ---------------------------------------------------------------------------
# Compute reporting sets
# ---------------------------------------------------------------------------
REINSTALL_COUNT="$(awk 'END{print NR}' "$SEL_AUTHS")"
USED_COUNT="$(sort -nu "$USED_FILE" | awk 'END{print NR}')"
MISSING_COUNT="$(awk 'END{print NR}' "$WORK/missing_auth_idx")"

DROP_INDICES=""
for idx in $DB_INDICES; do
    case " $USED_SORTED " in
        *" $idx "*) : ;;
        *)          DROP_INDICES="$DROP_INDICES $idx" ;;
    esac
done
DROP_COUNT="$(echo "$DROP_INDICES" | wc -w | tr -d ' ')"

# ---------------------------------------------------------------------------
# Report the plan
# ---------------------------------------------------------------------------
echo "SONiC db certificate reset plan"
echo "==============================="
echo "Secure Boot state    : $SB_STATE"
echo "Mode                 : $([ "$COMMIT" -eq 1 ] && echo 'COMMIT (will modify UEFI db)' || echo 'dry-run (no changes)')"
echo "Enrolled db certs    : $DB_COUNT"
echo "Auth directory       : $AUTH_DIR"
echo "Remove-all .auth      : $REMOVE_ALL_AUTH"
[ -n "$CURRENT_IMG" ] && echo "Current image        : $CURRENT_IMG"
[ -n "$NEXT_IMG" ]    && echo "Next image           : $NEXT_IMG"
[ -n "$CRIT_DIR" ]    && echo "Boot-critical dir    : $CRIT_DIR ($CRIT_TOTAL binary/ies)"
echo

echo "db certificates that SIGN an installed image and will be REINSTALLED ($USED_COUNT):"
if [ "$USED_COUNT" -eq 0 ]; then
    echo "  (none matched - refusing to wipe db with nothing to reinstall)"
else
    for idx in $USED_SORTED; do
        fp="$(meta_field "$idx" 4)"
        a="$(awk -F'|' -v f="$fp" '$1==f{print $2; exit}' "$AUTH_MAP")"
        print_cert "$idx" "  "
        if [ -n "$a" ]; then
            echo "        via .auth : $a"
        else
            echo "        via .auth : *** MISSING *** (no matching file in $AUTH_DIR)"
        fi
        echo
    done
fi

echo "db certificates that sign NO installed image and will be DROPPED ($DROP_COUNT):"
if [ "$DROP_COUNT" -eq 0 ]; then
    echo "  (none)"
else
    for idx in $DROP_INDICES; do
        print_cert "$idx" "  "
        echo
    done
fi

if [ "$VERBOSE" -eq 1 ]; then
    echo "Per-binary -> db certificate mapping:"
    while IFS='|' read -r f matched; do
        _c=""
        [ -f "$CRIT_BINS" ] && grep -Fxq "$f" "$CRIT_BINS" && _c=" [boot-critical]"
        if [ -z "$matched" ]; then
            echo "  $f$_c -> (no db match)"
        else
            out=""
            for idx in $matched; do
                if [ -z "$out" ]; then out="db[$idx] $(meta_field "$idx" 2)"
                else out="$out; db[$idx] $(meta_field "$idx" 2)"; fi
            done
            echo "  $f$_c -> $out"
        fi
    done < "$RECORDS"
    echo
fi

# ---------------------------------------------------------------------------
# Gate checks before any modification
# ---------------------------------------------------------------------------
if [ "$MISSING_COUNT" -gt 0 ]; then
    warn "$MISSING_COUNT image-signing db cert(s) have NO matching .auth in $AUTH_DIR (see 'MISSING' above)"
fi

# Stable, machine-readable summary line for callers (e.g. sonic-installer). It is
# always printed; automation can grep for the "PRUNE_PLAN " prefix.
#   missing           = image-signing db certs with no reinstall .auth (dropped, lost)
#   essential_missing = boot-critical binaries that would lose every db signer
echo "PRUNE_PLAN missing=$MISSING_COUNT essential_missing=$CRIT_AT_RISK drop=$DROP_COUNT reinstall=$REINSTALL_COUNT used=$USED_COUNT db=$DB_COUNT"

# --plan: report only, never change anything and never fail on a safety condition.
if [ "$PLAN" -eq 1 ]; then
    echo "Plan only - no changes made."
    exit 0
fi

if [ "$CRIT_FAIL" -ne 0 ] && [ "$ALLOW_ESSENTIAL_MISSING" -ne 1 ]; then
    die "SAFETY GATE FAILED: a boot-critical (shim/grub/MokManager) binary would lose every db signer. Refusing to touch db. Provide the missing .auth in $AUTH_DIR and retry (or pass --allow-essential-missing to override)."
fi
if [ "$CRIT_FAIL" -ne 0 ]; then
    warn "proceeding despite $CRIT_AT_RISK boot-critical binary/ies without a reinstall .auth (--allow-essential-missing); the system may fail Secure Boot verification after reboot"
fi

if [ "$USED_COUNT" -eq 0 ]; then
    die "no db certificate signs any installed image; refusing to delete db (nothing safe to reinstall)"
fi

if [ "$COMMIT" -ne 1 ]; then
    echo "Dry-run complete. Re-run with --commit to delete all db certs and reinstall the"
    echo "$REINSTALL_COUNT image-signing certificate(s) listed above."
    exit 0
fi

# ---------------------------------------------------------------------------
# Require the pre-existing remove-all .auth
# ---------------------------------------------------------------------------
[ -f "$REMOVE_ALL_AUTH" ] \
    || die "remove-all .auth not found: $REMOVE_ALL_AUTH (supply the signed empty-db .auth)"
[ -s "$REMOVE_ALL_AUTH" ] || die "remove-all .auth is empty: $REMOVE_ALL_AUTH"

# Verify each selected reinstall .auth actually exists on disk.
while IFS= read -r a; do
    [ -n "$a" ] || continue
    [ -s "$a" ] || die "selected reinstall .auth is missing or empty: $a"
done < "$SEL_AUTHS"

# ---------------------------------------------------------------------------
# Confirmation
# ---------------------------------------------------------------------------
echo
echo "About to DELETE all $DB_COUNT db certificate(s) and REINSTALL $REINSTALL_COUNT image-signing"
echo "certificate(s) via the .auth files above. This changes UEFI Secure Boot NVRAM."
if [ "$ASSUME_YES" -ne 1 ]; then
    if [ ! -t 0 ]; then
        die "refusing to modify db without a TTY; re-run with --yes to confirm non-interactively"
    fi
    printf 'Type exactly "reset-db" to proceed: '
    read -r _ans
    [ "$_ans" = "reset-db" ] || die "aborted by user"
fi

# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------
# Best-effort: clear the immutable flag on the db efivars file so writes succeed.
if [ "$HAVE_CHATTR" -eq 1 ]; then
    for v in "$EFIVARS_DIR"/db-*; do
        [ -e "$v" ] && chattr -i "$v" 2>/dev/null || true
    done
fi

echo "Deleting all db certificates (applying remove-all .auth) ..."
efi-updatevar -f "$REMOVE_ALL_AUTH" db \
    || die "failed to apply remove-all .auth ($REMOVE_ALL_AUTH); db unchanged or partially modified -- verify before rebooting"

# Confirm db is now empty of X.509 certs.
rm -rf "$CERTS_DIR"/db-*.der "$CERTS_DIR"/db-*.pem 2>/dev/null
if efi-readvar -v db -o "$WORK/db_after_del" >/dev/null 2>&1 \
   && sig-list-to-certs "$WORK/db_after_del" "$WORK/adel" >/dev/null 2>&1; then
    if ls "$WORK"/adel-*.der >/dev/null 2>&1; then
        warn "db still reports certificates after remove-all; continuing to reinstall anyway"
    fi
fi
echo "  db emptied."

echo "Reinstalling $REINSTALL_COUNT image-signing certificate(s) ..."
_fail=0
while IFS= read -r a; do
    [ -n "$a" ] || continue
    echo "  appending: $a"
    if [ "$HAVE_CHATTR" -eq 1 ]; then
        for v in "$EFIVARS_DIR"/db-*; do [ -e "$v" ] && chattr -i "$v" 2>/dev/null || true; done
    fi
    if ! efi-updatevar -a -f "$a" db; then
        warn "failed to append $a"
        _fail=1
    fi
done < "$SEL_AUTHS"

# ---------------------------------------------------------------------------
# Post-verification
# ---------------------------------------------------------------------------
echo
echo "Verifying db after reinstall ..."
efi-readvar -v db -o "$WORK/db_new" >/dev/null 2>&1 \
    || die "post-check failed: cannot read db after reinstall"
rm -rf "$WORK"/new-*.der "$WORK"/new-*.pem 2>/dev/null
sig-list-to-certs "$WORK/db_new" "$WORK/new" >/dev/null 2>&1 || true
NEW_PEMS=""
for der in "$WORK"/new-*.der; do
    [ -e "$der" ] || continue
    pem="${der%.der}.pem"
    openssl x509 -inform der -in "$der" -out "$pem" 2>/dev/null && NEW_PEMS="$NEW_PEMS $pem"
done
NEW_COUNT="$(echo "$NEW_PEMS" | wc -w | tr -d ' ')"
echo "  db now holds $NEW_COUNT certificate(s)."

# Re-verify each boot-critical binary against the new db.
CRIT_POST_FAIL=0
CRIT_POST_FAIL_COUNT=0
if [ -s "$CRIT_BINS" ]; then
    while IFS= read -r cbin; do
        [ -n "$cbin" ] || continue
        ok=0
        for pem in $NEW_PEMS; do
            if sbverify --cert "$pem" "$cbin" >/dev/null 2>&1; then ok=1; break; fi
        done
        if [ "$ok" -eq 1 ]; then
            echo "  OK  $cbin verifies against the new db"
        else
            echo "  ERR $cbin does NOT verify against the new db" >&2
            CRIT_POST_FAIL=1
            CRIT_POST_FAIL_COUNT=$((CRIT_POST_FAIL_COUNT + 1))
        fi
    done < "$CRIT_BINS"
fi

if [ "$CRIT_POST_FAIL" -ne 0 ]; then
    if [ "$ALLOW_ESSENTIAL_MISSING" -eq 1 ]; then
        warn "CRITICAL: a boot-critical binary no longer verifies against db (approved via --allow-essential-missing). DO NOT REBOOT with Secure Boot enforcing until a valid image-signing db certificate is enrolled."
    else
        die "CRITICAL: a boot-critical binary no longer verifies against db. DO NOT REBOOT with Secure Boot enforcing. Re-enroll a valid image-signing db certificate before rebooting."
    fi
fi
if [ "$_fail" -ne 0 ]; then
    die "one or more reinstall .auth files failed to apply; review the warnings above before rebooting"
fi

echo
if [ "$CRIT_POST_FAIL" -ne 0 ]; then
    echo "Done: db reset to $NEW_COUNT image-signing certificate(s); WARNING: $CRIT_POST_FAIL_COUNT boot-critical binary/ies do NOT verify against the new db (see above)."
else
    echo "Done: db reset to $NEW_COUNT image-signing certificate(s); all boot-critical binaries verify."
fi
exit 0

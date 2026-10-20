"""Prune UEFI Secure Boot db certificates using authenticated updates.

Dry-run is the default. Every installed boot-chain binary must retain a db signer,
and every authenticated update is verified against the enrolled KEK before db is
changed. Automatic pruning skips unsafe plans instead of modifying firmware.
"""

import argparse
import ctypes
import os
import signal
import subprocess
import sys
import tempfile
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from .secure_boot_lock import locked

PROG = Path(sys.argv[0]).name if sys.argv and sys.argv[0] else "remove_stale_db_certs.py"

IMAGE_PREFIX = "SONiC-OS-"
IMAGE_DIR_PREFIX = "image-"

EFI_GLOBAL_VARIABLE_GUID = uuid.UUID("8be4df61-93ca-11d2-aa0d-00e098032b8c")
EFI_IMAGE_SECURITY_DATABASE_GUID = uuid.UUID("d719b2cb-3d3a-4596-a3bc-dad00e67656f")
EFI_CERT_X509_GUID = uuid.UUID("a5c059a1-94e4-4aa7-87b5-ab155c2bf072")
EFI_CERT_TYPE_PKCS7_GUID = uuid.UUID("4aafd29d-68df-49ee-8aa9-347d375665a7")
WIN_CERT_REVISION_2_0 = 0x0200
WIN_CERT_TYPE_EFI_GUID = 0x0EF1
VARIABLE_GUIDS = {
    "db": EFI_IMAGE_SECURITY_DATABASE_GUID,
    "PK": EFI_GLOBAL_VARIABLE_GUID,
    "KEK": EFI_GLOBAL_VARIABLE_GUID,
    "SecureBoot": EFI_GLOBAL_VARIABLE_GUID,
}

EFIVAR_ATTR_SIZE = 4
DB_ATTR_REPLACE = 0x27
DB_ATTR_APPEND = 0x67

DER_SEQUENCE = 0x30
DER_EXPLICIT_TAG_0 = 0xA0
DER_LONG_FORM = 0x80
DER_SHORT_FORM_MAX = 0x7F
PKCS7_SIGNED_DATA_OID = bytes.fromhex("06092a864886f70d010702")

AUTHORITY_VARIABLES = ("KEK",)
COMMAND_TIMEOUT_SECS = 600
FALLBACK_ESP_DIRS = ("BOOT", "boot")
IGNORED_EFI_PREFIXES = ("grubnet", "mmx")


class EfiTime(ctypes.LittleEndianStructure):
    _fields_ = [("year", ctypes.c_uint16), ("month", ctypes.c_uint8), ("day", ctypes.c_uint8),
                ("hour", ctypes.c_uint8), ("minute", ctypes.c_uint8), ("second", ctypes.c_uint8),
                ("pad1", ctypes.c_uint8), ("nanosecond", ctypes.c_uint32), ("timezone", ctypes.c_int16),
                ("daylight", ctypes.c_uint8), ("pad2", ctypes.c_uint8)]


class WinCertificateUefiGuid(ctypes.LittleEndianStructure):
    """WIN_CERTIFICATE header, including the certificate type GUID."""
    _fields_ = [("length", ctypes.c_uint32), ("revision", ctypes.c_uint16), ("cert_type", ctypes.c_uint16),
                ("cert_type_guid", ctypes.c_uint8 * 16)]


class EfiAuthVariable2(ctypes.LittleEndianStructure):
    _fields_ = [("timestamp", EfiTime), ("auth_info", WinCertificateUefiGuid)]


class ScriptError(Exception):
    """A fatal condition: reported as an error and exit status 2."""


@dataclass
class Config:
    host_path: Path
    esp_path: Path
    sonic_os_dir: Path
    efivars_dir: Path
    auth_dir: Path
    remove_all_auth: Path

    @classmethod
    def from_env(cls, auth_dir=None, remove_all=None):
        """Resolve device paths and optional CLI overrides."""
        esp_path = Path(os.environ.get("SONIC_ESP_PATH", "/boot/efi/EFI"))
        auth_dir = Path(auth_dir or os.environ.get("SONIC_DB_AUTH_DIR", "/host/db-auth"))
        return cls(
            host_path=Path(os.environ.get("SONIC_HOST_PATH", "/host")),
            esp_path=esp_path,
            sonic_os_dir=Path(os.environ.get("SONIC_OS_DIR", esp_path / "SONiC-OS")),
            efivars_dir=Path(os.environ.get("SONIC_EFIVARS_DIR", "/sys/firmware/efi/efivars")),
            auth_dir=auth_dir,
            remove_all_auth=Path(remove_all) if remove_all else auth_dir / "remove-all-db.auth",
        )


@dataclass
class DbCert:
    index: int
    pem: Path
    fingerprint: str
    subject: str
    expires: str


@dataclass
class AuthUpdate:
    """An EFI_VARIABLE_AUTHENTICATION_2 update split into its parts."""
    timestamp: bytes
    signed_data: bytes
    payload: bytes


@dataclass
class Plan:
    """Selected certificates and the boot-chain safety checks for a db reset."""

    sb_state: str
    db_certs: List[DbCert]
    boot_critical_dir: Path
    records: Dict[Path, List[DbCert]]
    boot_critical_binaries: List[Path]
    used: List[DbCert]
    drop: List[DbCert]
    auth_map: Dict[str, Path]
    selected_auths: List[Path]
    missing: List[DbCert]
    boot_critical_binaries_at_risk: int

    @property
    def boot_chain_at_risk(self) -> bool:
        return self.boot_critical_binaries_at_risk > 0


def warn(message):
    print(f"{PROG}: warning: {message}", file=sys.stderr)


def run(cmd, **kwargs):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=COMMAND_TIMEOUT_SECS, **kwargs)


def succeeds(cmd):
    try:
        return run(cmd).returncode == 0
    except OSError:
        return False


def read_efi_variable(config, name):
    """Return the data of an EFI variable, without the efivarfs attribute word."""
    path = config.efivars_dir / f"{name}-{VARIABLE_GUIDS[name]}"
    try:
        return path.read_bytes()[EFIVAR_ATTR_SIZE:]
    except OSError as e:
        raise ScriptError(f"failed to read the UEFI {name} variable ({path}): {e.strerror}") from e


def load_certificates(esl, work, name):
    """Split EFI signature lists into PEM certificates using sig-list-to-certs and openssl."""
    if not esl:
        return []
    esl_file = work / f"{name}.esl"
    esl_file.write_bytes(esl)
    result = run(["sig-list-to-certs", str(esl_file), str(work / name)])
    if result.returncode:
        raise ScriptError(f"sig-list-to-certs failed on {name}: {result.stderr.strip()}")
    ders = sorted(work.glob(f"{name}-*.der"), key=lambda p: int(p.stem.rsplit("-", 1)[1]))
    certs = []
    for index, der_file in enumerate(ders):
        pem = der_file.with_suffix(".pem")
        info = run(["openssl", "x509", "-inform", "der", "-in", str(der_file), "-out", str(pem)])
        if info.returncode == 0:
            info = run(["openssl", "x509", "-in", str(pem), "-noout", "-nameopt", "RFC2253", "-subject",
                        "-enddate", "-sha256", "-fingerprint"])
        if info.returncode:
            raise ScriptError(f"openssl could not read a certificate from {name}: {info.stderr.strip()}")
        fields = dict(line.split("=", 1) for line in info.stdout.splitlines() if "=" in line)
        fingerprint = next(v for k, v in fields.items() if k.lower() == "sha256 fingerprint")
        certs.append(DbCert(index, pem, fingerprint, fields["subject"], fields["notAfter"]))
    return certs


def read_efi_certificates(config, work, name, label=None):
    return load_certificates(read_efi_variable(config, name), work, label or name)


def parse_auth(data):
    """Split an EFI_VARIABLE_AUTHENTICATION_2 file into timestamp, PKCS#7 signature and payload."""
    header_size = ctypes.sizeof(EfiAuthVariable2)
    if len(data) < header_size:
        raise ScriptError("authenticated update header is truncated")
    auth = EfiAuthVariable2.from_buffer_copy(data)
    cert_end = ctypes.sizeof(EfiTime) + auth.auth_info.length
    if auth.auth_info.length < ctypes.sizeof(WinCertificateUefiGuid) or cert_end > len(data):
        raise ScriptError("authenticated update certificate length is invalid")
    if auth.auth_info.revision != WIN_CERT_REVISION_2_0:
        raise ScriptError("authenticated update certificate revision is invalid")
    if auth.auth_info.cert_type != WIN_CERT_TYPE_EFI_GUID:
        raise ScriptError("authenticated update certificate type is invalid")
    if bytes(auth.auth_info.cert_type_guid) != EFI_CERT_TYPE_PKCS7_GUID.bytes_le:
        raise ScriptError("authenticated update certificate type GUID is not PKCS#7")
    if cert_end == header_size:
        raise ScriptError("authenticated update signature is empty")
    return AuthUpdate(data[:ctypes.sizeof(EfiTime)], data[header_size:cert_end], data[cert_end:])


def der(tag, content):
    """DER TLV encoding of content."""
    size = len(content)
    if size <= DER_SHORT_FORM_MAX:
        return bytes([tag, size]) + content
    encoded = size.to_bytes((size.bit_length() + 7) // 8, "big")
    return bytes([tag, DER_LONG_FORM | len(encoded)]) + encoded + content


def is_pkcs7_content_info(data):
    """Identify a ContentInfo wrapper rather than bare SignedData."""
    return data[:1] == bytes([DER_SEQUENCE]) and PKCS7_SIGNED_DATA_OID in data[:16]


def verify_db_auth(update, attributes, require_payload, trusted_pem, prefix):
    """Verify the exact name, GUID, attributes, timestamp and payload firmware authenticates."""
    if not update.signed_data or (require_payload and not update.payload):
        return False
    if is_pkcs7_content_info(update.signed_data):
        content_info = update.signed_data
    else:
        content_info = der(DER_SEQUENCE, PKCS7_SIGNED_DATA_OID + der(DER_EXPLICIT_TAG_0, update.signed_data))
    signed_content = (
        "db".encode("utf-16-le")
        + EFI_IMAGE_SECURITY_DATABASE_GUID.bytes_le
        + attributes.to_bytes(4, "little")
        + update.timestamp
        + update.payload
    )
    pkcs7, content = Path(f"{prefix}.p7b"), Path(f"{prefix}.content")
    pkcs7.write_bytes(content_info)
    content.write_bytes(signed_content)
    return succeeds([
        "openssl", "cms", "-verify", "-binary", "-inform", "DER", "-in", str(pkcs7), "-content", str(content),
        "-no_check_time", "-purpose", "any", "-partial_chain", "-CAfile", str(trusted_pem),
        "-out", "/dev/null",
    ])


def discover_binaries(directory):
    """Find disk boot-chain EFI binaries and kernels, excluding network GRUB and MokManager."""
    if not directory.is_dir():
        return []
    return sorted(
        p for p in directory.iterdir()
        if p.is_file() and not p.is_symlink()
        and (p.name.lower().endswith(".efi") or p.name.startswith("vmlinuz-"))
        and not p.name.lower().startswith(IGNORED_EFI_PREFIXES)
    )


def secure_boot_state(config):
    try:
        return "enabled" if read_efi_variable(config, "SecureBoot")[-1:] == b"\x01" else "disabled"
    except ScriptError:
        return "unknown"


def ensure_efivars(config):
    def populated():
        return config.efivars_dir.is_dir() and any(config.efivars_dir.iterdir())

    if not populated():
        succeeds(["mount", "-t", "efivarfs", "efivarfs", str(config.efivars_dir)])
    if not populated():
        raise ScriptError(f"UEFI efivars not available at {config.efivars_dir} "
                          "(not a UEFI system, or firmware access blocked)")


def load_db_certs(config, work):
    certs = read_efi_certificates(config, work, "db")
    if not certs:
        raise ScriptError("no X.509 certificates found in the UEFI db variable")
    return certs


def installed_images():
    """Discover installed images through the bootloader API for standalone use."""
    from .bootloader import get_bootloader

    try:
        images = get_bootloader().get_installed_images()
    except (OSError, RuntimeError) as e:
        raise ScriptError(f"failed to query installed images from bootloader: {e}; refusing to prune") from e
    if not images:
        raise ScriptError("bootloader returned no installed images, refusing to prune")
    return images


def collect_targets(config, images):
    """Return the installed boot directories and SONiC ESP directory."""
    targets = [config.host_path / f"{IMAGE_DIR_PREFIX}{image[len(IMAGE_PREFIX):]}" / "boot" for image in images]
    targets += [config.esp_path / name for name in FALLBACK_ESP_DIRS if (config.esp_path / name).is_dir()]
    if not discover_binaries(config.sonic_os_dir):
        raise ScriptError(f"no boot loader found in {config.sonic_os_dir}; refusing to prune")
    targets.append(config.sonic_os_dir)
    return targets, config.sonic_os_dir


def build_auth_map(config, work):
    """Map certificate fingerprints to reinstall updates and updates to their fingerprints."""
    auth_map, auth_fingerprints = {}, {}
    if not config.auth_dir.is_dir():
        return auth_map, auth_fingerprints
    for number, auth in enumerate(sorted(config.auth_dir.glob("*.auth"))):
        if auth.name == config.remove_all_auth.name:
            continue
        try:
            certs = load_certificates(parse_auth(auth.read_bytes()).payload, work, f"auth-{number}")
        except (OSError, ScriptError):
            warn(f"could not parse an ESL from {auth} (skipping)")
            continue
        if not certs:
            warn(f"no certificate found in {auth} (skipping)")
            continue
        auth_fingerprints[auth] = [c.fingerprint for c in certs]
        for fingerprint in auth_fingerprints[auth]:
            auth_map.setdefault(fingerprint, auth)
    return auth_map, auth_fingerprints


def check_boot_chain(boot_critical_binaries, records, reinstall_fps, auth_dir):
    """Count boot-chain binaries that would be left without a reinstallable db signer."""
    at_risk = 0
    for binary in boot_critical_binaries:
        matched = records[binary]
        if not matched:
            if succeeds(["sbverify", "--list", str(binary)]):
                print(f"{PROG}: SAFETY: boot-chain binary is not signed by any db certificate: {binary}",
                      file=sys.stderr)
            else:
                print(f"{PROG}: SAFETY: cannot inspect boot-chain binary (sbverify --list failed): {binary}",
                      file=sys.stderr)
            at_risk += 1
        elif not any(c.fingerprint in reinstall_fps for c in matched):
            print(f"{PROG}: SAFETY: boot-chain binary would lose all db signers: {binary}", file=sys.stderr)
            for c in matched:
                print(f"         signed by db[{c.index}] {c.subject} sha256 {c.fingerprint}", file=sys.stderr)
                print(f"         -> no matching .auth in {auth_dir} to reinstall it", file=sys.stderr)
            at_risk += 1
    if not boot_critical_binaries:
        warn("no boot-chain binaries were identified")
    return at_risk


def analyze(config, work, images=None) -> Plan:
    """Build a pruning plan for the supplied images, or query them for standalone use."""
    db_certs = load_db_certs(config, work)
    images = installed_images() if images is None else images
    if not images:
        raise ScriptError("sonic-installer returned no installed images, refusing to prune")
    targets, boot_critical_dir = collect_targets(config, images)

    binaries = []
    for directory in targets:
        for binary in discover_binaries(directory):
            if binary not in binaries:
                binaries.append(binary)
    if not binaries:
        raise ScriptError("no signed EFI binaries discovered in any target directory")

    records = {b: [c for c in db_certs if succeeds(["sbverify", "--cert", str(c.pem), str(b)])] for b in binaries}
    used = [c for c in db_certs if any(c in signers for signers in records.values())]
    auth_map, auth_fingerprints = build_auth_map(config, work)
    missing = [c for c in used if c.fingerprint not in auth_map]
    selected = sorted({auth_map[c.fingerprint] for c in used if c.fingerprint in auth_map})
    reinstall_fps = {fp for a in selected for fp in auth_fingerprints[a]}

    return Plan(
        sb_state=secure_boot_state(config), db_certs=db_certs,
        boot_critical_dir=boot_critical_dir, records=records, boot_critical_binaries=binaries, used=used,
        drop=[c for c in db_certs if c not in used and c.fingerprint not in reinstall_fps],
        auth_map=auth_map, selected_auths=selected,
        missing=missing,
        boot_critical_binaries_at_risk=check_boot_chain(binaries, records, reinstall_fps, config.auth_dir),
    )


def format_cert(cert, indent="  "):
    return [f"{indent}db[{cert.index}] {cert.subject}",
            f"{indent}      sha256 : {cert.fingerprint}",
            f"{indent}      expires: {cert.expires}"]


def print_plan(config, plan, commit, verbose):
    lines = [
        "SONiC db certificate reset plan",
        "===============================",
        f"Secure Boot state    : {plan.sb_state}",
        f"Mode                 : {'COMMIT (will modify UEFI db)' if commit else 'dry-run (no changes)'}",
        f"Enrolled db certs    : {len(plan.db_certs)}",
        f"Auth directory       : {config.auth_dir}",
        f"Remove-all .auth      : {config.remove_all_auth}",
    ]
    lines += [f"Boot-critical dir    : {plan.boot_critical_dir} ({len(plan.boot_critical_binaries)} binaries)", "",
              f"db certificates that SIGN an installed image and will be REINSTALLED ({len(plan.used)}):"]
    if not plan.used:
        lines.append("  (none matched - refusing to wipe db with nothing to reinstall)")
    for cert in plan.used:
        auth = plan.auth_map.get(cert.fingerprint)
        lines += format_cert(cert)
        lines += [f"        via .auth : {auth}" if auth
                  else f"        via .auth : *** MISSING *** (no matching file in {config.auth_dir})", ""]
    lines.append(f"db certificates that sign NO installed image and will be DROPPED ({len(plan.drop)}):")
    if not plan.drop:
        lines.append("  (none)")
    for cert in plan.drop:
        lines += format_cert(cert) + [""]
    if verbose:
        lines.append("Per-binary -> db certificate mapping:")
        for binary, signers in plan.records.items():
            names = "; ".join(f"db[{c.index}] {c.subject}" for c in signers) or "(no db match)"
            lines.append(f"  {binary} -> {names}")
        lines.append("")
    print("\n".join(lines))

    if plan.missing:
        warn(f"{len(plan.missing)} image-signing db cert(s) have NO matching .auth in {config.auth_dir} "
             "(see 'MISSING' above)")
    print(f"PRUNE_PLAN missing={len(plan.missing)} essential_missing={plan.boot_critical_binaries_at_risk} "
          f"drop={len(plan.drop)} "
          f"reinstall={len(plan.selected_auths)} used={len(plan.used)} db={len(plan.db_certs)}")


def build_trusted_pem(config, work, authorities=AUTHORITY_VARIABLES):
    """Build an enrolled-authority bundle; pruning trusts only KEK by default."""
    pem = b"".join(c.pem.read_bytes()
                   for variable in authorities for c in read_efi_certificates(config, work, variable))
    if not pem:
        raise ScriptError(f"no enrolled {' or '.join(authorities)} certificates are available")
    trusted = work / "firmware-authorities.pem"
    trusted.write_bytes(pem)
    return trusted


def validate_updates(config, plan, work):
    """Verify every authenticated update before db is touched."""
    remove_all = config.remove_all_auth
    if not remove_all.is_file():
        raise ScriptError(f"remove-all .auth not found: {remove_all} (supply the signed empty-db .auth)")
    try:
        update = parse_auth(remove_all.read_bytes())
    except ScriptError:
        update = None
    if update is None or update.payload:
        raise ScriptError(f"remove-all .auth must contain an empty signature-list payload: {remove_all}")

    trusted = build_trusted_pem(config, work)
    if not verify_db_auth(update, DB_ATTR_REPLACE, False, trusted, work / "remove-all"):
        raise ScriptError(f"remove-all .auth is not an authorized db replacement update: {remove_all}")
    for i, auth in enumerate(plan.selected_auths):
        if not verify_db_auth(parse_auth(auth.read_bytes()), DB_ATTR_APPEND, True, trusted, work / f"reinstall-{i}"):
            raise ScriptError(f"selected reinstall .auth is not an authorized db append update: {auth}")


def update_db(config, auth, append):
    """Apply an authenticated db update, clearing immutable flags best-effort."""
    for variable in config.efivars_dir.glob("db-*"):
        try:
            succeeds(["chattr", "-i", str(variable)])
        except subprocess.SubprocessError as e:
            warn(f"could not clear immutable flag on {variable}: {e}; attempting the firmware update")
    sys.stdout.flush()
    cmd = ["efi-updatevar"] + (["-a"] if append else []) + ["-f", str(auth), "db"]
    # A deadline must not kill a firmware write after db has been emptied.
    return subprocess.run(cmd).returncode == 0


def apply_plan(config, plan, work, verbose=True):
    """Replace db, reinstall selected signers and verify the resulting boot chain."""
    if verbose:
        print("Deleting all db certificates (applying remove-all .auth) ...")
    if not update_db(config, config.remove_all_auth, append=False):
        raise ScriptError(f"failed to apply remove-all .auth ({config.remove_all_auth}); "
                          "db unchanged or partially modified -- verify before rebooting")
    if verbose:
        print("  db emptied.")

        print(f"Reinstalling {len(plan.selected_auths)} image-signing certificate(s) ...")
    failed = []
    for auth in plan.selected_auths:
        if verbose:
            print(f"  appending: {auth}")
        failure = f"failed to append {auth}"
        try:
            if update_db(config, auth, append=True):
                continue
        except (OSError, subprocess.SubprocessError) as e:
            failure += f": {e}"
        warn(failure)
        failed.append(auth)

    if verbose:
        print("\nVerifying db after reinstall ...")
    new_pems = [c.pem for c in read_efi_certificates(config, work, "db", "new-db")]
    if verbose:
        print(f"  db now holds {len(new_pems)} certificate(s).")
    broken = [
        b for b in plan.boot_critical_binaries
        if not any(succeeds(["sbverify", "--cert", str(p), str(b)]) for p in new_pems)
    ]
    for binary in plan.boot_critical_binaries:
        if binary in broken:
            print(f"  ERR {binary} does NOT verify against the new db", file=sys.stderr)
        elif verbose:
            print(f"  OK  {binary} verifies against the new db")
    if broken:
        raise ScriptError("CRITICAL: a boot-chain binary no longer verifies against db. DO NOT REBOOT with "
                          "Secure Boot enforcing. Re-enroll a valid image-signing db certificate before rebooting.")
    if failed:
        raise ScriptError("one or more reinstall .auth files failed to apply; "
                          "review the warnings above before rebooting")
    print(f"\nDone: db reset to {len(new_pems)} image-signing certificate(s); all boot-chain binaries verify.")


@locked
def prune_db_certificates(config, *, images=None, commit=False, plan_only=False, auto=False, verbose=False):
    """Analyze or prune db; automatic mode modifies only safe plans with stale certificates."""
    if auto and plan_only:
        raise ScriptError("--auto cannot be combined with --plan")
    commit = commit or auto
    if os.geteuid() != 0:
        raise ScriptError(f"must be run as root (needs to read/write {config.efivars_dir} and {config.host_path})")
    ensure_efivars(config)
    if not config.auth_dir.is_dir():
        warn(f"auth directory not found: {config.auth_dir} (reinstall will find no .auth files)")

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        plan = analyze(config, work, images)
        if not auto or verbose:
            print_plan(config, plan, commit, verbose)
        if plan_only:
            print("Plan only - no changes made.")
            return 0
        if auto:
            if not plan.used or plan.missing or plan.boot_chain_at_risk:
                warn(f"Secure Boot db prune skipped (unsafe plan: used={len(plan.used)} "
                     f"missing={len(plan.missing)} essential_missing={plan.boot_critical_binaries_at_risk})")
                return 0
            if not plan.drop:
                print("No stale db certificates to prune.")
                return 0
            print(f"Pruning {len(plan.drop)} stale Secure Boot db certificate(s)...")
        if not plan.used:
            raise ScriptError("no db certificate signs any installed image; "
                              "refusing to delete db (nothing safe to reinstall)")
        if not commit:
            if plan.boot_chain_at_risk:
                warn(f"{plan.boot_critical_binaries_at_risk} boot-chain binaries would lose every db signer "
                     "(essential db certificate missing); --commit would refuse")
            print("Dry-run complete. Re-run with --commit to delete all db certs and reinstall the")
            print(f"{len(plan.selected_auths)} image-signing certificate(s) listed above.")
            return 0
        if plan.boot_chain_at_risk:
            raise ScriptError("a boot-chain binary would lose every db signer. "
                              f"Refusing to touch db. Provide the missing .auth in {config.auth_dir}.")
        validate_updates(config, plan, work)
        completed = False
        handle_sigterm = (threading.current_thread() is threading.main_thread()
                          and signal.getsignal(signal.SIGTERM) == signal.SIG_DFL)
        try:
            if handle_sigterm:
                signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(128 + signum))
            apply_plan(config, plan, work, verbose=not auto or verbose)
            completed = True
        finally:
            try:
                if not completed:
                    warn("Secure Boot db update did not complete. DO NOT REBOOT until db has been "
                         "verified and any missing image-signing certificates have been restored.")
            finally:
                if handle_sigterm:
                    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    return 0


def parse_args(argv):
    """Parse standalone pruning options."""
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Delete all UEFI 'db' certificates and reinstall only those that sign an installed "
                    "SONiC image, using pre-existing signed .auth files. Dry run unless --commit/--auto.",
    )
    parser.add_argument("--auth-dir", help="directory of per-certificate reinstall .auth files "
                                           "(default: $SONIC_DB_AUTH_DIR or /host/db-auth)")
    parser.add_argument("--remove-all", help="signed .auth that empties db (default: <auth-dir>/remove-all-db.auth)")
    parser.add_argument("--commit", action="store_true", help="actually modify the UEFI db")
    parser.add_argument("--plan", action="store_true",
                        help="analyse only and print a PRUNE_PLAN summary; never modifies db or fails on safety")
    parser.add_argument("--auto", action="store_true",
                        help="unattended mode: prune only safe plans with stale certificates")
    parser.add_argument("-v", "--verbose", action="store_true", help="print the per-binary -> db cert mapping")
    args = parser.parse_args(argv)
    if args.auto and args.plan:
        parser.error("--auto cannot be combined with --plan")
    return args


def main(argv=None):
    """Run the standalone CLI, reporting expected failures as exit status 2."""
    args = parse_args(argv)
    try:
        return prune_db_certificates(
            Config.from_env(args.auth_dir, args.remove_all),
            commit=args.commit, plan_only=args.plan, auto=args.auto, verbose=args.verbose,
        )
    except (ScriptError, OSError, subprocess.SubprocessError) as e:
        print(f"{PROG}: error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    sys.exit(main())

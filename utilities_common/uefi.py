"""Apply-only UEFI Secure Boot helpers for SONiC CLI.

Default backend is efitools + efivarfs (OVMF / Linux). A platform package
may replace it with sonic_platform.uefi.UefiBackend. The CLI never takes a
private key and never retries a firmware reject.
"""

from __future__ import print_function

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

EFI_GLOBAL = "8be4df61-93ca-11d2-aa0d-00e098032b8c"
EFI_IMAGE_SECURITY = "d719b2cb-3d3a-4596-a3bc-dad00e67656f"
EFIVARS = "/sys/firmware/efi/efivars"
NOT_AVAILABLE = "UEFI Secure Boot key management is not available on this platform"
EXPIRY_WARN_DAYS = 90

UEFI_VARS = {
    "pk": ("PK", EFI_GLOBAL),
    "kek": ("KEK", EFI_GLOBAL),
    "db": ("db", EFI_IMAGE_SECURITY),
    "dbx": ("dbx", EFI_IMAGE_SECURITY),
}

SETUP_MODE_PATH = os.path.join(EFIVARS, "SetupMode-{}".format(EFI_GLOBAL))
SECURE_BOOT_PATH = os.path.join(EFIVARS, "SecureBoot-{}".format(EFI_GLOBAL))


class UefiError(Exception):
    """User-visible UEFI CLI failure."""

    def __init__(self, message, returncode=1):
        super(UefiError, self).__init__(message)
        self.returncode = returncode


def normalize_var(name):
    if name is None:
        return None
    key = name.lower()
    if key not in UEFI_VARS:
        raise UefiError(
            "Unknown UEFI variable '{}'. Use pk, kek, db, or dbx.".format(name))
    return key


def uefi_name(var):
    return UEFI_VARS[normalize_var(var)][0]


def efivar_path(var):
    name, guid = UEFI_VARS[normalize_var(var)]
    return os.path.join(EFIVARS, "{}-{}".format(name, guid))


def format_status(setup, secure):
    setup_txt = "1 (Setup Mode)" if setup == 1 else "0 (User Mode)"
    secure_txt = "1 (enforcing)" if secure == 1 else "0 (not enforcing)"
    return "SetupMode: {}\nSecureBoot: {}\n".format(setup_txt, secure_txt)


def audit_notice(msg):
    _audit("notice", msg)


def audit_error(msg):
    _audit("error", msg)


def _audit(level, msg):
    try:
        from config.utils import log
        if level == "error":
            log.log_error(msg)
        else:
            log.log_notice(msg)
        return
    except Exception:
        pass
    try:
        import syslog
        syslog.openlog("config")
        prio = syslog.LOG_ERR if level == "error" else syslog.LOG_NOTICE
        syslog.syslog(prio, msg)
    except Exception:
        pass


def _run(cmd, capture=False):
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False)
    except OSError as exc:
        raise UefiError(
            "Cannot run '{}': {}. Install efitools.".format(cmd[0], exc))
    out = (proc.stdout or b"").decode("utf-8", "replace")
    err = (proc.stderr or b"").decode("utf-8", "replace").strip()
    if proc.returncode != 0:
        msg = err or out.strip() or "{} failed".format(cmd[0])
        raise UefiError(msg, returncode=proc.returncode)
    if capture:
        return out
    if out:
        sys.stdout.write(out)
    return out


def clear_immutable(path):
    if not os.path.exists(path):
        return
    try:
        subprocess.call(
            ["chattr", "-i", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
    except OSError:
        pass


class EfitoolsBackend(object):
    """Default Linux/OVMF backend: efivarfs flags, efitools for PK/KEK/db/dbx."""

    def available(self):
        return os.path.isdir("/sys/firmware/efi")

    def ensure(self):
        if not self.available():
            raise UefiError(NOT_AVAILABLE)
        if os.path.ismount(EFIVARS):
            return
        os.makedirs(EFIVARS, exist_ok=True)
        try:
            subprocess.check_call(
                ["mount", "-t", "efivarfs", "efivarfs", EFIVARS],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise UefiError("efivarfs is not mounted: {}".format(exc))

    def get_status(self):
        self.ensure()
        return _read_flag(SETUP_MODE_PATH, "SetupMode"), _read_flag(
            SECURE_BOOT_PATH, "SecureBoot")

    def show_variable(self, var=None):
        self.ensure()
        cmd = ["efi-readvar"]
        if var is not None:
            cmd.extend(["-v", uefi_name(var)])
        return _run(cmd, capture=True)

    def export_esl(self, var):
        """NVRAM ESL bytes (efivarfs payload, no 4-byte attributes)."""
        self.ensure()
        path = efivar_path(var)
        if not os.path.exists(path):
            return b""
        with open(path, "rb") as handle:
            data = handle.read()
        if len(data) <= 4:
            return b""
        return data[4:]

    def enroll(self, var, path):
        self.ensure()
        if not os.path.isfile(path):
            raise UefiError("File not found: {}".format(path))
        key = normalize_var(var)
        name = uefi_name(key)
        clear_immutable(efivar_path(key))
        if key == "pk":
            _run(["efi-updatevar", "-f", path, name])
        else:
            _run(["efi-updatevar", "-e", "-f", path, name])

    def append(self, var, path):
        self._apply_auth2(var, path, append=True)

    def update(self, var, path):
        self._apply_auth2(var, path, append=False)

    def unclaim(self, path):
        self.update("pk", path)

    def _apply_auth2(self, var, path, append):
        self.ensure()
        if not os.path.isfile(path):
            raise UefiError("File not found: {}".format(path))
        key = normalize_var(var)
        name = uefi_name(key)
        clear_immutable(efivar_path(key))
        cmd = ["efi-updatevar"]
        if append:
            cmd.append("-a")
        cmd.extend(["-f", path, name])
        _run(cmd)


def get_backend():
    try:
        from sonic_platform.uefi import UefiBackend
        backend = UefiBackend()
        if hasattr(backend, "available") and not backend.available():
            raise UefiError(NOT_AVAILABLE)
        return backend
    except UefiError:
        raise
    except Exception:
        pass
    backend = EfitoolsBackend()
    if not backend.available():
        raise UefiError(NOT_AVAILABLE)
    return backend


def _read_flag(path, label):
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        raise UefiError("Cannot read {}: {}".format(label, exc))
    if len(data) < 5:
        raise UefiError("{} is truncated".format(label))
    return data[4]


def read_status():
    return get_backend().get_status()


def read_variables(var=None):
    return get_backend().show_variable(var)


def enroll(var, path):
    get_backend().enroll(var, path)


def append(var, path):
    get_backend().append(var, path)


def update(var, path):
    get_backend().update(var, path)


def unclaim(path):
    get_backend().unclaim(path)


def _describe_entry(entry):
    return "{}  {}  {}".format(
        entry.get("type", "?"),
        entry.get("label", ""),
        entry.get("digest", "")[:16])


def format_compare(var, path):
    from utilities_common import uefi_parser as parser
    backend = get_backend()
    current = parser.entries_from_bytes(backend.export_esl(var))
    incoming = parser.entries_from_file(path)
    cur_map = {e["digest"]: e for e in current}
    new_map = {e["digest"]: e for e in incoming}
    both = sorted(set(cur_map) & set(new_map))
    only_new = sorted(set(new_map) - set(cur_map))
    only_cur = sorted(set(cur_map) - set(new_map))
    lines = [
        "Variable: {}".format(normalize_var(var)),
        "Current store: {} entries".format(len(current)),
        "AUTH2/ESL file: {} entries".format(len(incoming)),
        "",
        "In both (unchanged):",
    ]
    if both:
        lines.extend("  " + _describe_entry(cur_map[d]) for d in both)
    else:
        lines.append("  (none)")
    lines.extend(["", "In file, not in store (append would add; update would keep only these plus overlap):"])
    if only_new:
        lines.extend("  " + _describe_entry(new_map[d]) for d in only_new)
    else:
        lines.append("  (none)")
    lines.extend(["", "In store, not in file (append would keep; update would remove):"])
    if only_cur:
        lines.extend("  " + _describe_entry(cur_map[d]) for d in only_cur)
    else:
        lines.append("  (none)")
    if not incoming:
        lines.append("")
        lines.append("File ESL is empty. update/unclaim would clear this variable.")
    return "\n".join(lines) + "\n"


def format_health():
    from utilities_common import uefi_parser as parser
    backend = get_backend()
    setup, secure = backend.get_status()
    now = datetime.now(timezone.utc)
    warn_after = now + timedelta(days=EXPIRY_WARN_DAYS)
    lines = [format_status(setup, secure).rstrip(), ""]
    findings = []
    by_var = {}
    for var in ("pk", "kek", "db", "dbx"):
        entries = parser.entries_from_bytes(backend.export_esl(var))
        by_var[var] = entries
        lines.append("{}: {} entries".format(var.upper(), len(entries)))
        for entry in entries:
            extra = ""
            if entry["type"] == "X509":
                _nb, na = parser.x509_dates(entry["payload"])
                if na is None:
                    extra = " validity=unknown"
                elif na < now:
                    extra = " EXPIRED {}".format(na.date().isoformat())
                    findings.append("WARNING: {} {} expired {}".format(
                        var, entry["label"], na.date().isoformat()))
                elif na < warn_after:
                    extra = " expiring {}".format(na.date().isoformat())
                    findings.append("WARNING: {} {} expires {}".format(
                        var, entry["label"], na.date().isoformat()))
                else:
                    extra = " not_after={}".format(na.date().isoformat())
            lines.append("  {}{}".format(_describe_entry(entry), extra))
        lines.append("")

    if setup == 1:
        findings.append("INFO: Setup Mode (unclaimed or after unclaim)")
    if setup == 0 and not by_var["pk"]:
        findings.append("ERROR: User Mode but PK is empty")
    if setup == 0 and not by_var["db"]:
        findings.append("WARNING: User Mode but db is empty")
    db_ids = {e["digest"] for e in by_var["db"]}
    dbx_ids = {e["digest"] for e in by_var["dbx"]}
    both = db_ids & dbx_ids
    if both:
        findings.append(
            "WARNING: {} cert/hash entries are in both db and dbx".format(len(both)))

    lines.append("Findings:")
    if findings:
        lines.extend("  " + item for item in findings)
    else:
        lines.append("  none")
    return "\n".join(lines) + "\n"

"""Decode UEFI AUTH2 and ESL files for CLI inspect.

Algorithm-agnostic: RSA-2048/SHA-256 (OVMF), RSA-4096/SHA-384, and PQC
(ML-DSA / SLH-DSA) all use the same AUTH2/ESL layout. This dumper does
not assume a key size or digest. Unknown OIDs and ESL type GUIDs are
printed; inspect does not fail.

Does not take a private key, does not verify PKCS#7, and cannot see
EFI_VARIABLE_APPEND_WRITE (that bit is not in the AUTH2 header).
"""

from __future__ import print_function

import hashlib
import os
import struct
import subprocess
from datetime import datetime, timezone

from utilities_common.uefi import UefiError

EFI_SIGNATURE_LIST_SIZE = 28
WIN_CERT_TYPE_EFI_GUID = 0x0EF1

# openssl -text lines that name the algorithm without dumping the key.
_X509_ALGO_PREFIXES = (
    "Signature Algorithm:",
    "Public Key Algorithm:",
    "RSA Public-Key:",
    "Public-Key:",
    "ASN1 OID:",
    "NIST CURVE:",
)


def _guid_wire(canonical):
    parts = canonical.lower().split("-")
    return struct.pack(
        "<IHH", int(parts[0], 16), int(parts[1], 16), int(parts[2], 16)
    ) + bytes.fromhex(parts[3] + parts[4])


# UEFI spec signature types (not vendor SignatureOwner labels).
GUID_X509 = _guid_wire("a5c059a1-94e4-4aa7-87b5-ab155c2bf072")
GUID_RSA2048 = _guid_wire("3c5766e8-269c-4e34-aa14-ed776e85b3b6")
GUID_PKCS7 = _guid_wire("4aafd29d-68df-49ee-8aa9-347d375665a7")
GUID_SHA256 = _guid_wire("c1c41626-504c-4092-aca9-41f936934328")
GUID_SHA384 = _guid_wire("ffaf3279-4605-4d2e-bd9d-92c348a780ce")
GUID_SHA512 = _guid_wire("093e0e91-96d8-46b4-a43c-0251ead32a99")
GUID_X509_SHA256 = _guid_wire("3bd2a492-96c0-4079-b420-fcf98ef103ed")
GUID_X509_SHA384 = _guid_wire("7076876e-80c2-4ee6-aad2-28b349a6865b")
GUID_X509_SHA512 = _guid_wire("446dbf63-2502-4cda-bcfa-2465d2b0fe9d")

_SIG_TYPES = (
    (GUID_X509, "X509"),
    (GUID_RSA2048, "RSA2048"),
    (GUID_PKCS7, "PKCS7"),
    (GUID_SHA256, "SHA256"),
    (GUID_SHA384, "SHA384"),
    (GUID_SHA512, "SHA512"),
    (GUID_X509_SHA256, "X509_SHA256"),
    (GUID_X509_SHA384, "X509_SHA384"),
    (GUID_X509_SHA512, "X509_SHA512"),
)

# DER OID content (no 0x06 length prefix). Debug labels only.
_OID_NAMES = {
    bytes.fromhex("608648016503040201"): "SHA-256",
    bytes.fromhex("608648016503040202"): "SHA-384",
    bytes.fromhex("608648016503040203"): "SHA-512",
    bytes.fromhex("2a864886f70d010101"): "rsaEncryption",
    bytes.fromhex("2a864886f70d01010b"): "sha256WithRSAEncryption",
    bytes.fromhex("2a864886f70d01010c"): "sha384WithRSAEncryption",
    bytes.fromhex("2a864886f70d01010d"): "sha512WithRSAEncryption",
    bytes.fromhex("2a8648ce3d0201"): "id-ecPublicKey",
    bytes.fromhex("2b6570"): "Ed25519",
    bytes.fromhex("2b6571"): "Ed448",
    bytes.fromhex("608648016503040311"): "ML-DSA-44",
    bytes.fromhex("608648016503040312"): "ML-DSA-65",
    bytes.fromhex("608648016503040313"): "ML-DSA-87",
    bytes.fromhex("608648016503040314"): "SLH-DSA-SHA2-128s",
    bytes.fromhex("608648016503040315"): "SLH-DSA-SHA2-128f",
    bytes.fromhex("608648016503040316"): "SLH-DSA-SHA2-192s",
    bytes.fromhex("608648016503040317"): "SLH-DSA-SHA2-192f",
    bytes.fromhex("608648016503040318"): "SLH-DSA-SHA2-256s",
    bytes.fromhex("608648016503040319"): "SLH-DSA-SHA2-256f",
}


def guid_to_str(guid_bytes):
    if len(guid_bytes) != 16:
        return guid_bytes.hex()
    u1, u2, u3 = struct.unpack_from("<IHH", guid_bytes, 0)
    clock_seq = "".join("{:02x}".format(b) for b in guid_bytes[8:10])
    node = "".join("{:02x}".format(b) for b in guid_bytes[10:16])
    return "{:08x}-{:04x}-{:04x}-{}-{}".format(u1, u2, u3, clock_seq, node)


def guid_type_name(sig_type):
    for guid, name in _SIG_TYPES:
        if sig_type == guid:
            return name
    return "Unknown"


def looks_like_auth(data):
    if len(data) < 40:
        return False
    wtype = struct.unpack_from("<H", data, 22)[0]
    return wtype == WIN_CERT_TYPE_EFI_GUID and guid_type_name(data[24:40]) == "PKCS7"


def extract_esl(data):
    """Return the ESL bytes from an AUTH2 blob or a raw ESL."""
    if not looks_like_auth(data):
        return data
    dwlen = struct.unpack_from("<I", data, 16)[0]
    siglen = 16 + dwlen
    if dwlen < 24 or siglen > len(data):
        raise UefiError("AUTH2 WIN_CERTIFICATE.dwLength is invalid")
    return data[siglen:]


def iter_entries(esl_data):
    """Yield ESL entries: type, owner, payload, digest, label."""
    offset = 0
    size = len(esl_data or b"")
    while offset + EFI_SIGNATURE_LIST_SIZE <= size:
        sig_type = esl_data[offset:offset + 16]
        list_size, header_size, sig_size = struct.unpack_from(
            "<III", esl_data, offset + 16)
        if list_size < EFI_SIGNATURE_LIST_SIZE or offset + list_size > size:
            break
        esl_type = guid_type_name(sig_type)
        pos = offset + EFI_SIGNATURE_LIST_SIZE + header_size
        end = offset + list_size
        while pos + sig_size <= end and sig_size >= 16:
            owner = esl_data[pos:pos + 16]
            payload = esl_data[pos + 16:pos + sig_size]
            yield {
                "type": esl_type,
                "type_guid": guid_to_str(sig_type),
                "owner": guid_to_str(owner),
                "payload": payload,
                "digest": hashlib.sha256(payload).hexdigest(),
                "label": _entry_label(esl_type, payload, owner),
            }
            pos += sig_size
        offset += list_size


def entries_from_file(path):
    if not os.path.isfile(path):
        raise UefiError("File not found: {}".format(path))
    with open(path, "rb") as handle:
        data = handle.read()
    return list(iter_entries(extract_esl(data)))


def entries_from_bytes(data):
    return list(iter_entries(extract_esl(data or b"")))


def _entry_label(esl_type, payload, owner):
    if esl_type == "X509":
        subject = x509_field(payload, "-subject")
        if subject:
            return subject
    if esl_type.startswith("SHA") or esl_type.startswith("X509_SHA"):
        return "{} {}".format(esl_type, payload[:16].hex())
    return "{} owner={}".format(esl_type, guid_to_str(owner))


def x509_field(cert_data, flag):
    try:
        proc = subprocess.run(
            ["openssl", "x509", "-inform", "DER", "-noout", flag],
            input=cert_data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False)
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    text = (proc.stdout or b"").decode("utf-8", "replace").strip()
    return text or None


def x509_dates(cert_data):
    """Return (not_before, not_after) as aware UTC datetimes, or (None, None)."""
    raw = x509_field(cert_data, "-dates")
    if not raw:
        return None, None
    not_before = not_after = None
    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        try:
            parsed = datetime.strptime(value.strip(), "%b %d %H:%M:%S %Y %Z")
            parsed = parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if key == "notBefore":
            not_before = parsed
        elif key == "notAfter":
            not_after = parsed
    return not_before, not_after


def scan_oids(data):
    """Best-effort DER OID names. Unknown OIDs are skipped, not errors."""
    found = []
    seen = set()
    i = 0
    size = len(data)
    while i + 2 < size:
        if data[i] != 0x06:
            i += 1
            continue
        length = data[i + 1]
        if length == 0 or length >= 0x80 or i + 2 + length > size:
            i += 1
            continue
        content = data[i + 2:i + 2 + length]
        name = _OID_NAMES.get(content)
        if name and name not in seen:
            seen.add(name)
            found.append(name)
        i += 2 + length
    return found


def _oid_line(label, data):
    names = scan_oids(data)
    if not names:
        return "{}: (none recognized; layout still valid)".format(label)
    return "{}: {}".format(label, ", ".join(names))


def _efi_time(ts):
    if len(ts) < 8:
        return "Time Stamp: <short>"
    y, m, d, h, mi, s = struct.unpack_from("<HBBBBB", ts, 0)
    return "Time Stamp: {:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
        y, m, d, h, mi, s)


def _x509_summary(cert_data):
    lines = [_oid_line("        Algorithms", cert_data)]
    try:
        proc = subprocess.run(
            ["openssl", "x509", "-inform", "DER", "-noout", "-text"],
            input=cert_data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False)
    except OSError as exc:
        lines.append("        (openssl not available: {})".format(exc))
        return lines
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace").strip()
        lines.append(
            "        (openssl could not decode cert; "
            "PQC or old openssl is ok: {})".format(err or "openssl failed"))
        return lines
    lines.append("        Data:")
    for raw in (proc.stdout or b"").decode("utf-8", "replace").splitlines():
        text = raw.strip()
        if text.startswith(("Subject:", "Issuer:", "Not Before:", "Not After:")):
            lines.append("           {}".format(text))
            continue
        if any(text.startswith(prefix) for prefix in _X509_ALGO_PREFIXES):
            lines.append("           {}".format(text))
    return lines


def _hash_lines(esl_type, payload):
    if esl_type in ("SHA256", "X509_SHA256"):
        digest = payload[:32]
    elif esl_type in ("SHA384", "X509_SHA384"):
        digest = payload[:48]
    elif esl_type in ("SHA512", "X509_SHA512"):
        digest = payload[:64]
    else:
        digest = payload
    return ["        Hash: {}".format(digest.hex())]


def _esl_lines(esl_data):
    lines = []
    offset = 0
    size = len(esl_data)
    if size == 0:
        lines.append("ESL: empty")
        return lines
    index = 0
    while offset + EFI_SIGNATURE_LIST_SIZE <= size:
        sig_type = esl_data[offset:offset + 16]
        list_size, header_size, sig_size = struct.unpack_from(
            "<III", esl_data, offset + 16)
        if list_size < EFI_SIGNATURE_LIST_SIZE or offset + list_size > size:
            lines.append("ERROR: invalid ESL list at offset {}".format(offset))
            break
        esl_type = guid_type_name(sig_type)
        lines.append("Signature List {}: {}".format(index, esl_type))
        if esl_type == "Unknown":
            lines.append("   Type GUID: {}".format(guid_to_str(sig_type)))
        lines.append("   Signature List Size: {}".format(list_size))
        lines.append("   Signature Header Size: {}".format(header_size))
        lines.append("   Signature Size: {}".format(sig_size))
        pos = offset + EFI_SIGNATURE_LIST_SIZE + header_size
        end = offset + list_size
        entry = 0
        while pos + sig_size <= end and sig_size >= 16:
            owner = esl_data[pos:pos + 16]
            payload = esl_data[pos + 16:pos + sig_size]
            lines.append("        Entry # {}".format(entry))
            lines.append("        Owner GUID : {}".format(guid_to_str(owner)))
            lines.append("        Payload Size : {}".format(len(payload)))
            if esl_type == "X509":
                lines.extend(_x509_summary(payload))
            elif esl_type.startswith("SHA") or esl_type.startswith("X509_SHA"):
                lines.extend(_hash_lines(esl_type, payload))
            elif payload:
                lines.append(_oid_line("        Algorithms", payload))
            entry += 1
            pos += sig_size
        offset += list_size
        index += 1
    return lines


def format_payload(path):
    """Return a text dump of an AUTH2 or raw ESL file."""
    if not os.path.isfile(path):
        raise UefiError("File not found: {}".format(path))
    with open(path, "rb") as handle:
        data = handle.read()
    lines = ["File: {}".format(path), "Size: {} bytes".format(len(data))]
    if looks_like_auth(data):
        lines.append("Type: AUTH2")
        if len(data) < 40:
            raise UefiError("AUTH2 file too short")
        dwlen = struct.unpack_from("<I", data, 16)[0]
        wrev = struct.unpack_from("<H", data, 20)[0]
        wtype = struct.unpack_from("<H", data, 22)[0]
        lines.append(_efi_time(data[:16]))
        lines.append("WIN_CERTIFICATE:")
        lines.append("  Length: {}".format(dwlen))
        lines.append("  Revision: {}".format(wrev))
        lines.append("  Certificate Type: {}".format(wtype))
        lines.append("  CertType(GUID): {}".format(guid_to_str(data[24:40])))
        pkcs7_len = dwlen - 24
        if pkcs7_len < 0:
            raise UefiError("AUTH2 WIN_CERTIFICATE.dwLength is invalid")
        siglen = 40 + pkcs7_len
        if siglen > len(data):
            raise UefiError("PKCS#7 region extends past file end")
        pkcs7 = data[40:siglen]
        lines.append("  PKCS#7 size: {} bytes".format(pkcs7_len))
        if pkcs7_len == 0:
            lines.append("  PKCS#7: empty (unsigned AUTH2 header)")
        else:
            lines.append("  " + _oid_line("PKCS#7 algorithms", pkcs7))
        esl = data[siglen:]
        lines.extend(_esl_lines(esl))
        if not esl:
            lines.append("Note: empty ESL is the unclaim / remaining-list-empty payload")
    else:
        lines.append("Type: ESL (no AUTH2 header)")
        lines.extend(_esl_lines(data))
    return "\n".join(lines) + "\n"

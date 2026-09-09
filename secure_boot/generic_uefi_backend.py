#!/usr/bin/env python3

"""Generic SONiC Secure Boot backend using Linux UEFI variable services.

This backend is selected by ``secure_boot_backend.py`` when no platform
backend is registered and standard UEFI variable services are available. It
speaks the same stdout-JSON / stderr-diagnostics contract as any other
Secure Boot backend.

Standard UEFI has no vendor/customer split, so this backend exposes only the
effective ("unified") variables. The ``vendor`` and ``customer`` stores are
rejected.
"""

import argparse
import json
import os
import struct
import sys

EFIVARS_PATH = "/sys/firmware/efi/efivars"

EFI_GLOBAL_VARIABLE_GUID = "8be4df61-93ca-11d2-aa0d-00e098032b8c"
EFI_IMAGE_SECURITY_DATABASE_GUID = "d719b2cb-3d3a-4596-a3bc-dad00e67656f"

VARIABLES = {
    "PK": EFI_GLOBAL_VARIABLE_GUID,
    "KEK": EFI_GLOBAL_VARIABLE_GUID,
    "db": EFI_IMAGE_SECURITY_DATABASE_GUID,
    "dbx": EFI_IMAGE_SECURITY_DATABASE_GUID,
}

EFI_VARIABLE_NON_VOLATILE = 0x00000001
EFI_VARIABLE_BOOTSERVICE_ACCESS = 0x00000002
EFI_VARIABLE_RUNTIME_ACCESS = 0x00000004
EFI_VARIABLE_TIME_BASED_AUTHENTICATED_WRITE_ACCESS = 0x00000020
EFI_VARIABLE_APPEND_WRITE = 0x00000040

DEFAULT_ATTRIBUTES = (
    EFI_VARIABLE_NON_VOLATILE
    | EFI_VARIABLE_BOOTSERVICE_ACCESS
    | EFI_VARIABLE_RUNTIME_ACCESS
    | EFI_VARIABLE_TIME_BASED_AUTHENTICATED_WRITE_ACCESS
)


class BackendError(RuntimeError):
    pass


def json_error(message, rc=1):
    print(json.dumps({"error": message}))
    return rc


def json_output(data):
    print(json.dumps(data, separators=(",", ":")))
    return 0


def _require_root():
    if os.geteuid() != 0:
        raise BackendError("Secure Boot backend requires root privileges")


def _uefi_available():
    return os.path.isdir(EFIVARS_PATH)


def _variable_path(variable):
    try:
        guid = VARIABLES[variable]
    except KeyError:
        raise BackendError("unsupported Secure Boot variable: {}".format(variable))

    return os.path.join(EFIVARS_PATH, "{}-{}".format(variable, guid))


def _read_variable(variable):
    path = _variable_path(variable)

    if not os.path.exists(path):
        return {"state": "empty", "entry_count": 0, "data_length": 0}

    try:
        with open(path, "rb") as fp:
            raw = fp.read()
    except OSError as exc:
        raise BackendError("failed to read {}: {}".format(variable, exc))

    if len(raw) < 4:
        raise BackendError("invalid efivarfs data for {}".format(variable))

    # efivarfs prepends a 32-bit EFI attribute word.
    payload = raw[4:]

    if not payload:
        return {"state": "empty", "entry_count": 0, "data_length": 0}

    return {
        "state": "present",
        "entry_count": _count_signature_entries(payload),
        "data_length": len(payload),
    }


def _count_signature_entries(payload):
    """Count EFI_SIGNATURE_DATA entries across one or more EFI_SIGNATURE_LISTs.

    EFI_SIGNATURE_LIST layout::

        EFI_GUID SignatureType         16 bytes
        UINT32   SignatureListSize       4
        UINT32   SignatureHeaderSize     4
        UINT32   SignatureSize           4
        UINT8    SignatureHeader[]
        EFI_SIGNATURE_DATA Signatures[]

    This only counts entries; it does not interpret certificate contents.
    """

    offset = 0
    count = 0

    while offset < len(payload):
        if len(payload) - offset < 28:
            raise BackendError("malformed EFI signature list")

        signature_list_size, signature_header_size, signature_size = \
            struct.unpack_from("<III", payload, offset + 16)

        if signature_list_size < 28:
            raise BackendError("invalid EFI signature list size")

        if signature_size == 0:
            raise BackendError("invalid EFI signature size")

        end = offset + signature_list_size

        if end > len(payload):
            raise BackendError("truncated EFI signature list")

        entries_start = offset + 28 + signature_header_size

        if entries_start > end:
            raise BackendError("invalid EFI signature header size")

        entries_len = end - entries_start

        if entries_len % signature_size != 0:
            raise BackendError("malformed EFI signature entries")

        count += entries_len // signature_size
        offset = end

    return count


def _read_raw_byte_variable(name):
    path = os.path.join(EFIVARS_PATH, "{}-{}".format(name, EFI_GLOBAL_VARIABLE_GUID))

    if not os.path.exists(path):
        return None

    try:
        with open(path, "rb") as fp:
            raw = fp.read()
    except OSError as exc:
        raise BackendError("failed to read {}: {}".format(name, exc))

    if len(raw) < 5:
        raise BackendError("invalid UEFI variable data for {}".format(name))

    # First 4 bytes are the EFI attribute word; the value byte follows.
    return raw[4]


def _mode():
    """Report standard UEFI SecureBoot/SetupMode state.

    The generic backend cannot expose platform-specific mode numbers or
    vendor/customer policy, so all policy flags are reported as ``False``.
    """

    secure_boot = _read_raw_byte_variable("SecureBoot")
    setup_mode = _read_raw_byte_variable("SetupMode")

    if secure_boot is None and setup_mode is None:
        raise BackendError("standard UEFI Secure Boot mode variables are not available")

    name = "Unknown"

    if setup_mode == 1:
        name = "Setup Mode"
    elif secure_boot == 1:
        name = "Secure Boot Enabled"
    elif secure_boot == 0:
        name = "Secure Boot Disabled"

    return {
        "raw": secure_boot if secure_boot is not None else -1,
        "hex": "0x{:02x}".format(secure_boot) if secure_boot is not None else "unknown",
        "name": name,
        # Standard UEFI has no vendor/customer logical stores; these platform
        # policy flags are intentionally always False for the generic backend.
        "policy": {
            "vendor_store_write": False,
            "vendor_store_lock": False,
            "customer_store_write": False,
            "customer_store_lock": False,
        },
    }


def cmd_mode():
    return json_output(_mode())


def cmd_keys():
    result = {}
    for variable in ("PK", "KEK", "db", "dbx"):
        result["{}Unified".format(variable)] = _read_variable(variable)
    return json_output(result)


def cmd_key(variable, store):
    if store != "unified":
        raise BackendError(
            "{} store is not supported by the generic UEFI backend".format(store)
        )
    return json_output({"{}Unified".format(variable): _read_variable(variable)})


def cmd_status():
    keys = {}
    for variable in ("PK", "KEK", "db", "dbx"):
        keys["{}Unified".format(variable)] = _read_variable(variable)
    return json_output({"mode": _mode(), "keys": keys})


def _write_authenticated_variable(variable, auth_file, operation):
    _require_root()

    path = _variable_path(variable)

    try:
        with open(auth_file, "rb") as fp:
            payload = fp.read()
    except OSError as exc:
        raise BackendError("failed to read authenticated-variable file: {}".format(exc))

    if not payload:
        raise BackendError("authenticated-variable file is empty")

    # The payload is passed unchanged to the firmware UEFI variable service.
    # The firmware remains the cryptographic authorization boundary: it
    # validates the authenticated-variable signature, timestamp/replay
    # protection, and authorization chain. This backend deliberately does not
    # re-implement that verification in Python.
    #
    # Operation -> efivarfs attribute mapping:
    #   append -> DEFAULT_ATTRIBUTES | EFI_VARIABLE_APPEND_WRITE
    #   update -> DEFAULT_ATTRIBUTES (authenticated replacement semantics)
    #   remove -> DEFAULT_ATTRIBUTES (authenticated payload controls removal)
    attributes = DEFAULT_ATTRIBUTES

    if operation == "append":
        attributes |= EFI_VARIABLE_APPEND_WRITE
    elif operation not in ("update", "remove"):
        raise BackendError("unsupported Secure Boot update operation: {}".format(operation))

    # efivarfs write format:
    #
    #   UINT32 attributes
    #   variable payload
    #
    # For authenticated Secure Boot variables, the payload must already
    # contain the UEFI authenticated-variable structure expected by firmware.
    raw = struct.pack("<I", attributes) + payload

    try:
        with open(path, "wb") as fp:
            fp.write(raw)
    except OSError as exc:
        raise BackendError("Secure Boot update failed: {}".format(exc))

    return json_output({"result": "success", "variable": variable, "operation": operation})


def build_parser():
    parser = argparse.ArgumentParser(description="SONiC generic UEFI Secure Boot backend")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status")
    subparsers.add_parser("mode")
    subparsers.add_parser("keys")

    key_parser = subparsers.add_parser("key")
    key_parser.add_argument("variable", choices=["PK", "KEK", "db", "dbx"])
    key_parser.add_argument("--store", choices=["vendor", "customer", "unified"], default="unified")

    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("variable", choices=["PK", "KEK", "db", "dbx"])
    update_parser.add_argument("--file", required=True)
    update_parser.add_argument("--operation", choices=["append", "update", "remove"], default="update")

    return parser


def main():
    if not _uefi_available():
        return json_error("standard UEFI variable services are not available")

    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "status":
            return cmd_status()
        if args.command == "mode":
            return cmd_mode()
        if args.command == "keys":
            return cmd_keys()
        if args.command == "key":
            return cmd_key(args.variable, args.store)
        if args.command == "update":
            return _write_authenticated_variable(args.variable, args.file, args.operation)
        return json_error("missing Secure Boot backend operation")
    except BackendError as exc:
        return json_error(str(exc))


if __name__ == "__main__":
    sys.exit(main())

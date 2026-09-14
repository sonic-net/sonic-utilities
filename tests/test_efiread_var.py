#!/usr/bin/env python3

import importlib.util
import os


SCRIPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "scripts",
    "efiread-var",
)

spec = importlib.util.spec_from_file_location(
    "efiread_var",
    SCRIPT_PATH,
)

efiread_var = importlib.util.module_from_spec(spec)
spec.loader.exec_module(efiread_var)


def test_supported_variables():
    assert efi_readvar.SUPPORTED_VARIABLES == (
        "PK",
        "KEK",
        "db",
    )


def test_read_pk(monkeypatch):
    calls = []

    monkeypatch.setattr(
        efi_readvar.os.path,
        "exists",
        lambda path: True,
    )

    def mock_call(cmd):
        calls.append(cmd)
        return 0

    monkeypatch.setattr(
        efi_readvar.subprocess,
        "call",
        mock_call,
    )

    rc = efi_readvar.read_efi_variable("PK")

    assert rc == 0
    assert calls == [
        ["/usr/bin/efi-readvar", "-v", "PK"]
    ]


def test_read_kek(monkeypatch):
    calls = []

    monkeypatch.setattr(
        efi_readvar.os.path,
        "exists",
        lambda path: True,
    )

    def mock_call(cmd):
        calls.append(cmd)
        return 0

    monkeypatch.setattr(
        efi_readvar.subprocess,
        "call",
        mock_call,
    )

    rc = efi_readvar.read_efi_variable("KEK")

    assert rc == 0
    assert calls == [
        ["/usr/bin/efi-readvar", "-v", "KEK"]
    ]


def test_read_db(monkeypatch):
    calls = []

    monkeypatch.setattr(
        efi_readvar.os.path,
        "exists",
        lambda path: True,
    )

    def mock_call(cmd):
        calls.append(cmd)
        return 0

    monkeypatch.setattr(
        efi_readvar.subprocess,
        "call",
        mock_call,
    )

    rc = efi_readvar.read_efi_variable("db")

    assert rc == 0
    assert calls == [
        ["/usr/bin/efi-readvar", "-v", "db"]
    ]


def test_unsupported_variable(capsys):
    rc = efi_readvar.read_efi_variable("dbx")

    captured = capsys.readouterr()

    assert rc == 2
    assert "unsupported EFI variable" in captured.err


def test_efi_readvar_missing(monkeypatch, capsys):
    monkeypatch.setattr(
        efi_readvar.os.path,
        "exists",
        lambda path: False,
    )

    rc = efi_readvar.read_efi_variable("PK")

    captured = capsys.readouterr()

    assert rc == 1
    assert "/usr/bin/efi-readvar is not installed" in captured.err


def test_efi_readvar_failure_propagated(monkeypatch):
    monkeypatch.setattr(
        efi_readvar.os.path,
        "exists",
        lambda path: True,
    )

    monkeypatch.setattr(
        efi_readvar.subprocess,
        "call",
        lambda cmd: 1,
    )

    assert efi_readvar.read_efi_variable("PK") == 1


def test_exec_failure(monkeypatch, capsys):
    monkeypatch.setattr(
        efi_readvar.os.path,
        "exists",
        lambda path: True,
    )

    def mock_call(cmd):
        raise OSError("exec failed")

    monkeypatch.setattr(
        efi_readvar.subprocess,
        "call",
        mock_call,
    )

    rc = efi_readvar.read_efi_variable("PK")

    captured = capsys.readouterr()

    assert rc == 1
    assert "failed to execute" in captured.err

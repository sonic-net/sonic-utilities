import copy
import hashlib
import json
import os
import shutil
import subprocess

import pytest

import utilities_common.generation_transaction as generation_transaction
from utilities_common.generation_transaction import (
    DatabaseAdapter,
    DatabaseSnapshot,
    DatabaseTarget,
    GenerationCleanupError,
    GenerationCommandError,
    GenerationRecoveryError,
    GenerationRollbackError,
    GenerationSnapshotError,
    GenerationTransaction,
    GenerationTransactionError,
    GenerationVerificationError,
    compare_database_dumps,
    sanitize_database_dump,
)


requires_posix_transaction_fs = pytest.mark.skipif(
    os.name == "nt",
    reason=(
        "transaction evidence security and atomic rename semantics require "
        "a POSIX filesystem"
    ),
)


class FakeDatabaseRunner:
    def __init__(self, databases, now=1000):
        self.databases = copy.deepcopy(databases)
        self.now = now
        self.calls = []
        self.operation_counts = {}
        self.failures = {}
        self.ignore_flush = False

    def fail(self, operation, call_number=1):
        self.failures.setdefault(operation, set()).add(call_number)

    def __call__(self, command):
        command = list(command)
        self.calls.append(command)
        operation = self._operation(command)
        count = self.operation_counts.get(operation, 0) + 1
        self.operation_counts[operation] = count

        if count in self.failures.get(operation, set()):
            return subprocess.CompletedProcess(
                command,
                1,
                stdout="",
                stderr="{} failed".format(operation),
            )

        namespace, database = self._target(command)
        target = (namespace, database)

        if operation == "dump":
            output_path = command[command.index("-o") + 1]
            with open(output_path, "w") as output:
                json.dump(self.databases.get(target, {}), output)
        elif operation == "flush":
            if not self.ignore_flush:
                self.databases[target] = {}
        elif operation == "load":
            input_path = command[-1]
            with open(input_path) as source:
                restored = json.load(source)
            for key, record in restored.items():
                expireat = record.get("expireat")
                if expireat is not None and expireat <= self.now:
                    continue
                self.databases.setdefault(target, {})[key] = record

        return subprocess.CompletedProcess(
            command,
            0,
            stdout="",
            stderr="",
        )

    @staticmethod
    def _operation(command):
        executable = os.path.basename(command[0])
        if executable == "sonic-db-dump":
            return "dump"
        if executable == "sonic-db-load":
            return "load"
        if executable == "sonic-db-cli":
            return "flush"
        raise AssertionError("Unexpected command: {}".format(command))

    @staticmethod
    def _target(command):
        executable = os.path.basename(command[0])
        if executable in ("sonic-db-dump", "sonic-db-load"):
            namespace = ""
            if "--netns" in command:
                namespace = command[command.index("--netns") + 1]
            database = command[command.index("-n") + 1]
            return namespace, database

        namespace = ""
        offset = 1
        if command[1:2] == ["-n"]:
            namespace = command[2]
            offset = 3
        return namespace, command[offset]


class FakeTransactionDatabaseAdapter:
    def __init__(self, events=None):
        self.events = events if events is not None else []
        self.fail_snapshots = set()
        self.fail_restores = set()
        self.restored_transaction_ids = []

    def snapshot(self, target, evidence_directory):
        self.events.append(("snapshot", target.namespace, target.database))
        if target in self.fail_snapshots:
            raise GenerationSnapshotError(
                "snapshot failed for {}".format(target.display_name)
            )
        content = json.dumps(
            {
                target.display_name: {
                    "type": "string",
                    "value": target.display_name,
                },
            },
            sort_keys=True,
        ).encode("utf-8")
        path = os.path.join(
            evidence_directory,
            "{}.json".format(target.filename_component),
        )
        with open(path, "wb") as output:
            output.write(content)
        os.chmod(path, 0o600)
        return DatabaseSnapshot(
            target=target,
            path=path,
            sha256=hashlib.sha256(content).hexdigest(),
        )

    def restore(self, snapshot):
        target = snapshot.target
        self.events.append(("restore", target.namespace, target.database))
        self.restored_transaction_ids.append(os.path.basename(
            os.path.dirname(os.path.dirname(snapshot.path))
        ))
        if target in self.fail_restores:
            raise GenerationVerificationError(
                "restore failed for {}".format(target.display_name)
            )


def _record(value, redis_type="hash", ttl=None, expireat=None):
    record = {
        "type": redis_type,
        "value": value,
    }
    if ttl is not None:
        record["ttl"] = ttl
    if expireat is not None:
        record["expireat"] = expireat
    return record


def _set_transaction_manifest_state(
        transaction,
        status,
        created_at=None,
        touched_scopes=(),
        shared_databases_touched=False,
        touched_files=(),
        failures=()):
    transaction._manifest["status"] = status
    if created_at is not None:
        transaction._manifest["created_at"] = created_at
    transaction._manifest["touched_scopes"] = list(touched_scopes)
    transaction._manifest["shared_databases_touched"] = \
        shared_databases_touched
    transaction._manifest["touched_files"] = list(touched_files)
    transaction._manifest["failures"] = list(failures)
    transaction._write_manifest()


def _begin_transaction(
        tmp_path,
        transaction_id,
        adapter=None,
        namespaces=("",),
        persistent_files=()):
    return GenerationTransaction(
        namespaces,
        persistent_files=tuple(str(path) for path in persistent_files),
        evidence_parent=str(tmp_path / "transactions"),
        database_adapter=adapter or FakeTransactionDatabaseAdapter(),
        transaction_id=transaction_id,
    ).begin()


def _load_transaction_manifest(transaction):
    with open(transaction.manifest_path) as source:
        return json.load(source)


def _write_transaction_manifest(transaction, manifest):
    with open(transaction.manifest_path, "w") as output:
        json.dump(manifest, output, sort_keys=True)
    os.chmod(transaction.manifest_path, 0o600)


def _stage_stale_transaction(
        tmp_path,
        transaction_id,
        status,
        created_at=1000,
        touched=True):
    adapter = FakeTransactionDatabaseAdapter()
    persistent_file = tmp_path / "{}.json".format(transaction_id)
    persistent_file.write_bytes(b'{"state":"original"}')
    transaction = _begin_transaction(
        tmp_path,
        transaction_id,
        adapter=adapter,
        persistent_files=(persistent_file,),
    )
    touched_scopes = ()
    touched_files = ()
    failures = ()
    if touched:
        transaction.mark_scope_touched("")
        transaction.mark_persistent_file_touched(str(persistent_file))
        persistent_file.write_bytes(b'{"state":"mutated"}')
        touched_scopes = ("",)
        touched_files = (str(persistent_file),)
    if status in ("rollback_failed", "rollback_cleanup_failed"):
        failures = ("interrupted rollback",)
    _set_transaction_manifest_state(
        transaction,
        status,
        created_at=created_at,
        touched_scopes=touched_scopes,
        touched_files=touched_files,
        failures=failures,
    )
    return transaction, persistent_file


@pytest.mark.parametrize(
    "namespace, expected_dump, expected_flush, expected_load",
    [
        (
            "",
            ["sonic-db-dump", "-n", "CONFIG_DB", "-o", "snapshot.json", "-y"],
            ["sonic-db-cli", "CONFIG_DB", "FLUSHDB"],
            ["sonic-db-load", "-n", "CONFIG_DB", "-A", "snapshot.json"],
        ),
        (
            "asic0",
            [
                "sonic-db-dump",
                "--netns",
                "asic0",
                "-n",
                "CONFIG_DB",
                "-o",
                "snapshot.json",
                "-y",
            ],
            ["sonic-db-cli", "-n", "asic0", "CONFIG_DB", "FLUSHDB"],
            [
                "sonic-db-load",
                "--netns",
                "asic0",
                "-n",
                "CONFIG_DB",
                "-A",
                "snapshot.json",
            ],
        ),
    ],
)
def test_database_target_builds_namespace_safe_commands(
        namespace, expected_dump, expected_flush, expected_load):
    target = DatabaseTarget(namespace, "CONFIG_DB")

    assert target.dump_command("snapshot.json") == expected_dump
    assert target.flush_command() == expected_flush
    assert target.load_command("snapshot.json") == expected_load


def test_sanitize_database_dump_removes_negative_persistent_ttl():
    source = {
        "persistent": _record(
            {"field": "value"},
            ttl=-0.001,
            expireat=999,
        ),
        "expiring": _record(
            "value",
            redis_type="string",
            ttl=30,
            expireat=1030,
        ),
    }

    sanitized = sanitize_database_dump(source)

    assert sanitized["persistent"] == _record({"field": "value"})
    assert sanitized["expiring"] == source["expiring"]
    assert source["persistent"]["expireat"] == 999


def test_sanitize_database_dump_rejects_partial_positive_expiration():
    with pytest.raises(GenerationVerificationError, match="expireat"):
        sanitize_database_dump({
            "key": _record("value", redis_type="string", ttl=30),
        })


@pytest.mark.parametrize("field", ["ttl", "expireat"])
@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_sanitize_database_dump_rejects_non_finite_expiration(field, value):
    record = _record(
        "value",
        redis_type="string",
        ttl=30,
        expireat=1030,
    )
    record[field] = value

    with pytest.raises(GenerationVerificationError, match="finite"):
        sanitize_database_dump({"key": record})


def test_restore_flushes_before_absolute_expiration_load_and_verifies(tmp_path):
    target = DatabaseTarget("asic0", "CONFIG_DB")
    original = {
        "persistent": _record({"field": "original"}),
        "expiring": _record(
            "value",
            redis_type="string",
            ttl=30,
            expireat=1030,
        ),
    }
    runner = FakeDatabaseRunner({
        ("asic0", "CONFIG_DB"): original,
    })
    adapter = DatabaseAdapter(runner=runner, now=lambda: runner.now)
    snapshot = adapter.snapshot(target, str(tmp_path))

    runner.databases[("asic0", "CONFIG_DB")] = {
        "persistent": _record({"field": "changed"}),
        "destination-only": _record("stale", redis_type="string"),
    }

    adapter.restore(snapshot)

    assert runner.databases[("asic0", "CONFIG_DB")] == original
    assert [os.path.basename(call[0]) for call in runner.calls] == [
        "sonic-db-dump",
        "sonic-db-cli",
        "sonic-db-load",
        "sonic-db-dump",
    ]
    assert runner.calls[1] == [
        "sonic-db-cli",
        "-n",
        "asic0",
        "CONFIG_DB",
        "FLUSHDB",
    ]
    assert "-A" in runner.calls[2]


def test_restore_detects_destination_only_key_when_clear_is_ineffective(tmp_path):
    target = DatabaseTarget("", "CONFIG_DB")
    original = {"expected": _record("value", redis_type="string")}
    runner = FakeDatabaseRunner({
        ("", "CONFIG_DB"): original,
    })
    adapter = DatabaseAdapter(runner=runner, now=lambda: runner.now)
    snapshot = adapter.snapshot(target, str(tmp_path))

    runner.databases[("", "CONFIG_DB")]["destination-only"] = \
        _record("stale", redis_type="string")
    runner.ignore_flush = True

    with pytest.raises(
            GenerationVerificationError,
            match="destination-only"):
        adapter.restore(snapshot)


@pytest.mark.parametrize(
    "actual_record, expected_error",
    [
        (_record("value", redis_type="list"), "type"),
        (_record("different", redis_type="string"), "value"),
    ],
)
def test_compare_database_dumps_rejects_type_and_value_differences(
        actual_record, expected_error):
    expected = {"key": _record("value", redis_type="string")}
    actual = {"key": actual_record}

    with pytest.raises(GenerationVerificationError, match=expected_error):
        compare_database_dumps(expected, actual, now=1000)


def test_compare_database_dumps_allows_expiry_during_rollback():
    expected = {
        "already-expired": _record(
            "value",
            redis_type="string",
            ttl=5,
            expireat=1000,
        ),
        "still-live": _record(
            "value",
            redis_type="string",
            ttl=15,
            expireat=1010,
        ),
    }
    actual = {
        "still-live": _record(
            "value",
            redis_type="string",
            ttl=9,
            expireat=1011,
        ),
    }

    compare_database_dumps(
        expected,
        actual,
        now=1005,
        expiration_tolerance=1,
    )


def test_compare_database_dumps_requires_unexpired_key():
    expected = {
        "key": _record(
            "value",
            redis_type="string",
            ttl=30,
            expireat=1030,
        ),
    }

    with pytest.raises(GenerationVerificationError, match="missing"):
        compare_database_dumps(expected, {}, now=1005)


@pytest.mark.parametrize(
    "operation, failure_call",
    [
        ("dump", 1),
        ("flush", 1),
        ("load", 1),
        ("dump", 2),
    ],
)
def test_adapter_surfaces_dump_clear_load_and_redump_failures(
        tmp_path, operation, failure_call):
    target = DatabaseTarget("", "CONFIG_DB")
    original = {"key": _record("value", redis_type="string")}
    runner = FakeDatabaseRunner({
        ("", "CONFIG_DB"): original,
    })
    adapter = DatabaseAdapter(runner=runner, now=lambda: runner.now)

    if operation == "dump" and failure_call == 1:
        runner.fail(operation, failure_call)
        with pytest.raises(GenerationCommandError, match="dump"):
            adapter.snapshot(target, str(tmp_path))
        return

    snapshot = adapter.snapshot(target, str(tmp_path))
    runner.fail(operation, failure_call)

    with pytest.raises(GenerationCommandError, match=operation):
        adapter.restore(snapshot)


def test_restore_is_namespace_isolated(tmp_path):
    target = DatabaseTarget("asic0", "CONFIG_DB")
    asic_original = {"asic": _record("original", redis_type="string")}
    host_original = {"host": _record("untouched", redis_type="string")}
    runner = FakeDatabaseRunner({
        ("asic0", "CONFIG_DB"): asic_original,
        ("", "CONFIG_DB"): host_original,
    })
    adapter = DatabaseAdapter(runner=runner, now=lambda: runner.now)
    snapshot = adapter.snapshot(target, str(tmp_path))

    runner.databases[("asic0", "CONFIG_DB")] = {
        "asic": _record("changed", redis_type="string"),
    }
    adapter.restore(snapshot)

    assert runner.databases[("asic0", "CONFIG_DB")] == asic_original
    assert runner.databases[("", "CONFIG_DB")] == host_original
    assert all(
        "--netns" in call or call[1:3] == ["-n", "asic0"]
        for call in runner.calls
    )


@pytest.mark.parametrize("component", [".", ".."])
def test_database_target_rejects_path_components(component):
    with pytest.raises(ValueError, match="Invalid"):
        DatabaseTarget(component, "CONFIG_DB")

    with pytest.raises(ValueError, match="Invalid"):
        DatabaseTarget("", component)


def test_generation_transaction_requires_absolute_unique_persistent_paths(
        tmp_path):
    absolute_path = str(tmp_path / "config_db.json")

    with pytest.raises(ValueError, match="absolute"):
        GenerationTransaction(("",), persistent_files=("config_db.json",))

    with pytest.raises(ValueError, match="unique"):
        GenerationTransaction(
            ("",),
            persistent_files=(absolute_path, absolute_path),
        )


@pytest.mark.parametrize("transaction_id", [".", ".."])
def test_generation_transaction_rejects_path_component_ids(
        tmp_path, transaction_id):
    with pytest.raises(ValueError, match="Invalid transaction ID"):
        GenerationTransaction(
            ("",),
            evidence_parent=str(tmp_path / "transactions"),
            transaction_id=transaction_id,
        )


def test_generation_transaction_rejects_cleanup_transaction_id(tmp_path):
    with pytest.raises(ValueError, match="cleanup"):
        GenerationTransaction(
            ("",),
            evidence_parent=str(tmp_path / "transactions"),
            transaction_id="transaction.cleanup",
        )


@requires_posix_transaction_fs
def test_transaction_snapshots_every_target_before_mutation(tmp_path):
    adapter = FakeTransactionDatabaseAdapter()
    evidence_parent = str(tmp_path / "transactions")
    transaction = GenerationTransaction.for_golden_native_host(
        ("asic0", "asic1"),
        evidence_parent=evidence_parent,
        database_adapter=adapter,
        transaction_id="snapshot-order",
    )

    transaction.begin()

    assert adapter.events == [
        ("snapshot", "", "CONFIG_DB"),
        ("snapshot", "", "APPL_DB"),
        ("snapshot", "asic0", "CONFIG_DB"),
        ("snapshot", "asic0", "APPL_DB"),
        ("snapshot", "asic1", "CONFIG_DB"),
        ("snapshot", "asic1", "APPL_DB"),
        ("snapshot", "", "STATE_DB"),
        ("snapshot", "", "LOGLEVEL_DB"),
    ]
    with open(transaction.manifest_path) as source:
        manifest = json.load(source)
    assert manifest["status"] == "prepared"
    assert len(manifest["database_snapshots"]) == 8

    transaction.commit()
    assert not os.path.exists(transaction.evidence_directory)


@requires_posix_transaction_fs
def test_transaction_records_service_recovery_before_quiescing(tmp_path):
    events = []
    adapter = FakeTransactionDatabaseAdapter(events)
    transaction = GenerationTransaction(
        ("",),
        evidence_parent=str(tmp_path / "transactions"),
        database_adapter=adapter,
        transaction_id="durable-quiescence",
    )

    def quiesce_services():
        manifest = _load_transaction_manifest(transaction)
        assert manifest["status"] == "preparing"
        assert manifest["service_recovery_required"] is True
        events.append(("quiesce-services",))

    transaction.begin(
        service_quiescence=quiesce_services,
        service_recovery=lambda: events.append(("recover-services",)),
    )

    assert events[0] == ("quiesce-services",)
    assert events[1][0] == "snapshot"
    manifest = _load_transaction_manifest(transaction)
    assert manifest["status"] == "prepared"
    assert manifest["service_recovery_required"] is True

    with pytest.raises(
            GenerationTransactionError,
            match="service recovery"):
        transaction.commit()

    transaction.mark_service_recovery_complete()
    transaction.commit()


@requires_posix_transaction_fs
def test_transaction_atomically_publishes_initialized_evidence(
        tmp_path, monkeypatch):
    transaction = GenerationTransaction(
        ("",),
        evidence_parent=str(tmp_path / "transactions"),
        database_adapter=FakeTransactionDatabaseAdapter(),
        transaction_id="atomic-publish",
    )
    original_rename = generation_transaction.os.rename
    publications = []

    def inspect_publish(source, destination):
        if source == transaction.staging_directory:
            assert destination == transaction.evidence_directory
            assert not os.path.lexists(transaction.evidence_directory)
            assert os.path.isdir(os.path.join(source, "databases"))
            assert os.path.isdir(os.path.join(source, "files"))
            with open(os.path.join(source, "manifest.json")) as manifest_file:
                manifest = json.load(manifest_file)
            assert manifest["status"] == "preparing"
            publications.append((source, destination))
        return original_rename(source, destination)

    monkeypatch.setattr(
        generation_transaction.os,
        "rename",
        inspect_publish,
    )

    transaction.begin()

    assert publications == [(
        transaction.staging_directory,
        transaction.evidence_directory,
    )]
    assert not os.path.lexists(transaction.staging_directory)
    assert os.path.isfile(transaction.manifest_path)
    transaction.commit()


@requires_posix_transaction_fs
def test_recovery_removes_interrupted_unpublished_evidence(
        tmp_path, monkeypatch):
    transaction = GenerationTransaction(
        ("",),
        evidence_parent=str(tmp_path / "transactions"),
        database_adapter=FakeTransactionDatabaseAdapter(),
        transaction_id="interrupted-initialization",
    )
    original_atomic_write_json = generation_transaction._atomic_write_json

    def interrupt_after_manifest(path, value, mode=0o600):
        original_atomic_write_json(path, value, mode=mode)
        raise KeyboardInterrupt()

    monkeypatch.setattr(
        generation_transaction,
        "_atomic_write_json",
        interrupt_after_manifest,
    )

    with pytest.raises(KeyboardInterrupt):
        transaction.begin()

    assert not os.path.lexists(transaction.evidence_directory)
    assert os.path.isdir(transaction.staging_directory)

    monkeypatch.setattr(
        generation_transaction,
        "_atomic_write_json",
        original_atomic_write_json,
    )
    assert GenerationTransaction.recover_stale_transactions(
        evidence_parent=transaction.evidence_parent,
        database_adapter=FakeTransactionDatabaseAdapter(),
    ) == ()
    assert not os.path.lexists(transaction.staging_directory)


@requires_posix_transaction_fs
def test_initial_evidence_failure_removes_private_staging(
        tmp_path, monkeypatch):
    transaction = GenerationTransaction(
        ("",),
        evidence_parent=str(tmp_path / "transactions"),
        database_adapter=FakeTransactionDatabaseAdapter(),
        transaction_id="failed-initialization",
    )

    def fail_manifest(*args, **kwargs):
        raise OSError("manifest write failed")

    monkeypatch.setattr(
        generation_transaction,
        "_atomic_write_json",
        fail_manifest,
    )

    with pytest.raises(OSError, match="manifest write failed"):
        transaction.begin()

    assert not os.path.lexists(transaction.evidence_directory)
    assert not os.path.lexists(transaction.staging_directory)


@requires_posix_transaction_fs
def test_prepare_failure_removes_partial_evidence(tmp_path):
    adapter = FakeTransactionDatabaseAdapter()
    adapter.fail_snapshots.add(DatabaseTarget("asic0", "APPL_DB"))
    transaction = GenerationTransaction.for_golden_native_host(
        ("asic0",),
        evidence_parent=str(tmp_path / "transactions"),
        database_adapter=adapter,
        transaction_id="prepare-failure",
    )

    with pytest.raises(GenerationSnapshotError, match="snapshot failed"):
        transaction.begin()

    assert not os.path.exists(transaction.evidence_directory)


@requires_posix_transaction_fs
def test_prepare_failure_recovers_services_after_durable_quiescence(
        tmp_path):
    events = []
    adapter = FakeTransactionDatabaseAdapter(events)
    adapter.fail_snapshots.add(DatabaseTarget("", "CONFIG_DB"))
    transaction = GenerationTransaction(
        ("",),
        evidence_parent=str(tmp_path / "transactions"),
        database_adapter=adapter,
        transaction_id="prepare-service-recovery",
    )

    with pytest.raises(GenerationSnapshotError, match="snapshot failed"):
        transaction.begin(
            service_quiescence=lambda: events.append(("quiesce-services",)),
            service_recovery=lambda: events.append(("recover-services",)),
        )

    assert events == [
        ("quiesce-services",),
        ("snapshot", "", "CONFIG_DB"),
        ("recover-services",),
    ]
    assert not os.path.exists(transaction.evidence_directory)


@requires_posix_transaction_fs
def test_prepare_recovery_failure_preserves_durable_evidence(tmp_path):
    adapter = FakeTransactionDatabaseAdapter()
    adapter.fail_snapshots.add(DatabaseTarget("", "CONFIG_DB"))
    transaction = GenerationTransaction(
        ("",),
        evidence_parent=str(tmp_path / "transactions"),
        database_adapter=adapter,
        transaction_id="prepare-recovery-failure",
    )

    with pytest.raises(
            GenerationRollbackError,
            match="service restart failed"):
        transaction.begin(
            service_quiescence=lambda: None,
            service_recovery=lambda: (_ for _ in ()).throw(
                RuntimeError("service restart failed")
            ),
        )

    manifest = _load_transaction_manifest(transaction)
    assert manifest["status"] == "preparing"
    assert manifest["service_recovery_required"] is True
    assert os.path.isdir(transaction.evidence_directory)


@requires_posix_transaction_fs
def test_rollback_restores_reverse_scopes_shared_once_files_then_services(
        tmp_path):
    events = []
    adapter = FakeTransactionDatabaseAdapter(events)
    persistent_file = tmp_path / "etc" / "sonic" / "config_db.json"
    persistent_file.parent.mkdir(parents=True)
    persistent_file.write_bytes(b"original")
    transaction = GenerationTransaction.for_golden_native_host(
        ("asic0", "asic1"),
        persistent_files=(str(persistent_file),),
        evidence_parent=str(tmp_path / "transactions"),
        database_adapter=adapter,
        transaction_id="reverse-rollback",
    ).begin()

    original_restore_file = transaction._restore_file

    def restore_file(snapshot):
        events.append(("restore-file", snapshot.path))
        original_restore_file(snapshot)

    transaction._restore_file = restore_file
    transaction.mark_scope_touched("")
    transaction.mark_scope_touched("asic0")
    transaction.mark_scope_touched("asic1")
    transaction.mark_shared_databases_touched()
    transaction.mark_shared_databases_touched()
    transaction.mark_persistent_file_touched(str(persistent_file))
    persistent_file.write_bytes(b"changed")

    transaction.rollback(
        RuntimeError("later ASIC failed"),
        service_quiescence=lambda: events.append(("quiesce-services",)),
        service_recovery=lambda: events.append(("recover-services",)),
    )

    restore_events = [
        event for event in events if event[0] != "snapshot"
    ]
    assert restore_events == [
        ("quiesce-services",),
        ("restore", "asic1", "APPL_DB"),
        ("restore", "asic1", "CONFIG_DB"),
        ("restore", "asic0", "APPL_DB"),
        ("restore", "asic0", "CONFIG_DB"),
        ("restore", "", "APPL_DB"),
        ("restore", "", "CONFIG_DB"),
        ("restore", "", "LOGLEVEL_DB"),
        ("restore", "", "STATE_DB"),
        ("restore-file", str(persistent_file)),
        ("recover-services",),
    ]
    assert persistent_file.read_bytes() == b"original"
    assert not os.path.exists(transaction.evidence_directory)


@requires_posix_transaction_fs
def test_publish_persistent_files_installs_complete_generation(tmp_path):
    adapter = FakeTransactionDatabaseAdapter()
    config_root = tmp_path / "etc" / "sonic"
    config_root.mkdir(parents=True)
    host_file = config_root / "config_db.json"
    asic_file = config_root / "config_db0.json"
    host_file.write_bytes(b"old-host")
    asic_file.write_bytes(b"old-asic")
    transaction = GenerationTransaction.for_golden_native_host(
        ("asic0",),
        persistent_files=(str(host_file), str(asic_file)),
        evidence_parent=str(tmp_path / "transactions"),
        database_adapter=adapter,
        transaction_id="publish-generation",
    ).begin()
    prepared_host = config_root / ".host.prepared"
    prepared_asic = config_root / ".asic.prepared"
    prepared_host.write_bytes(b"new-host")
    prepared_asic.write_bytes(b"new-asic")

    transaction.publish_persistent_files([
        (str(host_file), str(prepared_host)),
        (str(asic_file), str(prepared_asic)),
    ])

    assert host_file.read_bytes() == b"new-host"
    assert asic_file.read_bytes() == b"new-asic"
    assert not prepared_host.exists()
    assert not prepared_asic.exists()
    transaction.commit()


@requires_posix_transaction_fs
def test_publish_failure_rolls_back_every_persistent_file(
        tmp_path, monkeypatch):
    adapter = FakeTransactionDatabaseAdapter()
    config_root = tmp_path / "etc" / "sonic"
    config_root.mkdir(parents=True)
    host_file = config_root / "config_db.json"
    asic_file = config_root / "config_db0.json"
    host_file.write_bytes(b"old-host")
    asic_file.write_bytes(b"old-asic")
    transaction = GenerationTransaction.for_golden_native_host(
        ("asic0",),
        persistent_files=(str(host_file), str(asic_file)),
        evidence_parent=str(tmp_path / "transactions"),
        database_adapter=adapter,
        transaction_id="publish-failure",
    ).begin()
    prepared_host = config_root / ".host.prepared"
    prepared_asic = config_root / ".asic.prepared"
    prepared_host.write_bytes(b"new-host")
    prepared_asic.write_bytes(b"new-asic")
    original_replace = generation_transaction.os.replace
    failed = {"value": False}

    def fail_second_publication(source, destination):
        if destination == str(asic_file) and not failed["value"]:
            failed["value"] = True
            raise OSError("injected publication failure")
        return original_replace(source, destination)

    monkeypatch.setattr(
        generation_transaction.os,
        "replace",
        fail_second_publication,
    )

    with pytest.raises(OSError, match="publication failure"):
        transaction.publish_persistent_files([
            (str(host_file), str(prepared_host)),
            (str(asic_file), str(prepared_asic)),
        ])

    transaction.rollback(RuntimeError("publication failed"))
    assert host_file.read_bytes() == b"old-host"
    assert asic_file.read_bytes() == b"old-asic"


@requires_posix_transaction_fs
def test_rollback_removes_file_that_did_not_exist_at_snapshot(tmp_path):
    adapter = FakeTransactionDatabaseAdapter()
    persistent_file = tmp_path / "etc" / "sonic" / "config_db1.json"
    persistent_file.parent.mkdir(parents=True)
    transaction = GenerationTransaction(
        ("",),
        persistent_files=(str(persistent_file),),
        evidence_parent=str(tmp_path / "transactions"),
        database_adapter=adapter,
        transaction_id="remove-new-file",
    ).begin()

    transaction.mark_persistent_file_touched(str(persistent_file))
    persistent_file.write_bytes(b"created during operation")
    transaction.rollback(RuntimeError("operation failed"))

    assert not persistent_file.exists()


@requires_posix_transaction_fs
def test_file_restore_does_not_resecure_target_parent(tmp_path, monkeypatch):
    adapter = FakeTransactionDatabaseAdapter()
    persistent_file = tmp_path / "etc" / "sonic" / "config_db.json"
    persistent_file.parent.mkdir(parents=True)
    persistent_file.write_bytes(b"original")
    transaction = GenerationTransaction(
        ("",),
        persistent_files=(str(persistent_file),),
        evidence_parent=str(tmp_path / "transactions"),
        database_adapter=adapter,
        transaction_id="parent-permissions",
    ).begin()
    transaction.mark_persistent_file_touched(str(persistent_file))
    persistent_file.write_bytes(b"changed")

    def reject_directory_resecurity(path):
        raise AssertionError(
            "restore must not chmod or recreate destination parents: {}".format(
                path)
        )

    monkeypatch.setattr(
        generation_transaction,
        "_ensure_private_directory",
        reject_directory_resecurity,
    )
    transaction.rollback(RuntimeError("operation failed"))

    assert persistent_file.read_bytes() == b"original"


@requires_posix_transaction_fs
def test_rollback_failure_retains_evidence_and_original_error(tmp_path):
    events = []
    adapter = FakeTransactionDatabaseAdapter(events)
    failed_target = DatabaseTarget("asic0", "APPL_DB")
    adapter.fail_restores.add(failed_target)
    transaction = GenerationTransaction.for_golden_native_host(
        ("asic0",),
        evidence_parent=str(tmp_path / "transactions"),
        database_adapter=adapter,
        transaction_id="rollback-failure",
    ).begin()
    transaction.mark_scope_touched("asic0")
    transaction.mark_shared_databases_touched()
    original_error = RuntimeError("later scope failed")

    def fail_service_recovery():
        events.append(("recover-services",))
        raise RuntimeError("service recovery failed")

    with pytest.raises(GenerationRollbackError) as failure:
        transaction.rollback(
            original_error,
            service_recovery=fail_service_recovery,
        )

    assert failure.value.original_error is original_error
    assert any(
        "restore asic0:APPL_DB" in item
        for item in failure.value.failures
    )
    assert any(
        "recover services" in item
        for item in failure.value.failures
    )
    assert os.path.isdir(transaction.evidence_directory)
    with open(transaction.manifest_path) as source:
        manifest = json.load(source)
    assert manifest["status"] == "rollback_failed"
    assert manifest["failures"] == list(failure.value.failures)


@requires_posix_transaction_fs
def test_rollback_restores_data_when_quiescence_fails(tmp_path):
    events = []
    adapter = FakeTransactionDatabaseAdapter(events)
    failed_target = DatabaseTarget("asic0", "APPL_DB")
    adapter.fail_restores.add(failed_target)
    persistent_file = tmp_path / "etc" / "sonic" / "config_db1.json"
    persistent_file.parent.mkdir(parents=True)
    persistent_file.write_bytes(b"original")
    transaction = GenerationTransaction.for_golden_native_host(
        ("asic0",),
        persistent_files=(str(persistent_file),),
        evidence_parent=str(tmp_path / "transactions"),
        database_adapter=adapter,
        transaction_id="quiescence-failure",
    ).begin()
    transaction.mark_scope_touched("asic0")
    transaction.mark_shared_databases_touched()
    transaction.mark_persistent_file_touched(str(persistent_file))
    persistent_file.write_bytes(b"changed")
    original_error = RuntimeError("operation failed")

    def fail_quiescence():
        events.append(("quiesce-services",))
        raise RuntimeError("stop failed")

    with pytest.raises(GenerationRollbackError) as failure:
        transaction.rollback(
            original_error,
            service_quiescence=fail_quiescence,
            service_recovery=lambda: events.append(("recover-services",)),
        )

    restored_targets = {
        DatabaseTarget(event[1], event[2])
        for event in events
        if event[0] == "restore"
    }
    assert restored_targets == {
        DatabaseTarget("asic0", "CONFIG_DB"),
        failed_target,
        DatabaseTarget("", "STATE_DB"),
        DatabaseTarget("", "LOGLEVEL_DB"),
    }
    assert persistent_file.read_bytes() == b"original"
    assert ("recover-services",) in events
    assert any(
        "quiesce services before rollback" in item
        for item in failure.value.failures
    )
    assert any(
        "restore asic0:APPL_DB" in item
        for item in failure.value.failures
    )


@requires_posix_transaction_fs
def test_commit_cleanup_failure_retains_committed_evidence(
        tmp_path, monkeypatch):
    transaction = GenerationTransaction(
        ("",),
        evidence_parent=str(tmp_path / "transactions"),
        database_adapter=FakeTransactionDatabaseAdapter(),
        transaction_id="commit-cleanup-failure",
    ).begin()

    def fail_cleanup(path):
        raise OSError("injected cleanup failure")

    with monkeypatch.context() as patch:
        patch.setattr(generation_transaction.shutil, "rmtree", fail_cleanup)
        with pytest.raises(
                GenerationCleanupError,
                match="injected cleanup failure"):
            transaction.commit()

    cleanup_directory = "{}.cleanup".format(transaction.evidence_directory)
    assert not os.path.exists(transaction.evidence_directory)
    assert os.path.isdir(cleanup_directory)
    with open(os.path.join(cleanup_directory, "manifest.json")) as source:
        manifest = json.load(source)
    assert manifest["status"] == "committed"
    shutil.rmtree(cleanup_directory)


@requires_posix_transaction_fs
def test_rollback_propagates_keyboard_interrupt_during_restore(tmp_path):
    adapter = FakeTransactionDatabaseAdapter()
    transaction = _begin_transaction(
        tmp_path,
        "keyboard-interrupt",
        adapter=adapter,
    )
    transaction.mark_scope_touched("")

    def interrupt_restore(snapshot):
        raise KeyboardInterrupt()

    adapter.restore = interrupt_restore

    with pytest.raises(KeyboardInterrupt):
        transaction.rollback(RuntimeError("operation failed"))

    assert _load_transaction_manifest(transaction)["status"] == \
        "rolling_back"
    shutil.rmtree(transaction.evidence_directory)


@requires_posix_transaction_fs
def test_rollback_propagates_system_exit_during_service_quiescence(tmp_path):
    adapter = FakeTransactionDatabaseAdapter()
    transaction = _begin_transaction(
        tmp_path,
        "system-exit",
        adapter=adapter,
    )
    transaction.mark_scope_touched("")

    def exit_during_quiescence():
        raise SystemExit(7)

    with pytest.raises(SystemExit) as failure:
        transaction.rollback(
            RuntimeError("operation failed"),
            service_quiescence=exit_during_quiescence,
        )

    assert failure.value.code == 7
    assert _load_transaction_manifest(transaction)["status"] == \
        "rolling_back"
    assert not [
        event for event in adapter.events
        if event[0] == "restore"
    ]
    shutil.rmtree(transaction.evidence_directory)


@requires_posix_transaction_fs
def test_recovery_removes_interrupted_preparing_transaction(tmp_path):
    class InterruptingSnapshotAdapter(FakeTransactionDatabaseAdapter):
        def snapshot(self, target, evidence_directory):
            raise KeyboardInterrupt()

    transaction = GenerationTransaction(
        ("",),
        evidence_parent=str(tmp_path / "transactions"),
        database_adapter=InterruptingSnapshotAdapter(),
        transaction_id="interrupted-prepare",
    )

    with pytest.raises(KeyboardInterrupt):
        transaction.begin()

    assert _load_transaction_manifest(transaction)["status"] == "preparing"
    assert GenerationTransaction.recover_stale_transactions(
        evidence_parent=transaction.evidence_parent,
        database_adapter=FakeTransactionDatabaseAdapter(),
    ) == ()
    assert not os.path.exists(transaction.evidence_directory)


@requires_posix_transaction_fs
@pytest.mark.parametrize("status", ["preparing", "prepared"])
def test_recovery_restarts_services_for_interrupted_pre_mutation_transaction(
        tmp_path, status):
    if status == "preparing":
        class InterruptingSnapshotAdapter(FakeTransactionDatabaseAdapter):
            def snapshot(self, target, evidence_directory):
                raise KeyboardInterrupt()

        transaction = GenerationTransaction(
            ("",),
            evidence_parent=str(tmp_path / "transactions"),
            database_adapter=InterruptingSnapshotAdapter(),
            transaction_id="pre-mutation-preparing",
        )
        with pytest.raises(KeyboardInterrupt):
            transaction.begin()
    else:
        transaction = _begin_transaction(
            tmp_path,
            "pre-mutation-prepared",
        )

    transaction._manifest["service_recovery_required"] = True
    transaction._write_manifest()
    events = []

    assert GenerationTransaction.recover_stale_transactions(
        evidence_parent=transaction.evidence_parent,
        database_adapter=FakeTransactionDatabaseAdapter(),
        service_recovery=lambda: events.append(("recover-services",)),
    ) == ()
    assert events == [("recover-services",)]
    assert not os.path.exists(transaction.evidence_directory)


@requires_posix_transaction_fs
def test_pre_mutation_recovery_failure_preserves_evidence(tmp_path):
    transaction = _begin_transaction(
        tmp_path,
        "pre-mutation-recovery-failure",
    )
    transaction._manifest["service_recovery_required"] = True
    transaction._write_manifest()

    with pytest.raises(
            GenerationRecoveryError,
            match="service restart failed"):
        GenerationTransaction.recover_stale_transactions(
            evidence_parent=transaction.evidence_parent,
            database_adapter=FakeTransactionDatabaseAdapter(),
            service_recovery=lambda: (_ for _ in ()).throw(
                RuntimeError("service restart failed")
            ),
        )

    manifest = _load_transaction_manifest(transaction)
    assert manifest["status"] == "prepared"
    assert manifest["service_recovery_required"] is True
    assert os.path.isdir(transaction.evidence_directory)


@requires_posix_transaction_fs
@pytest.mark.parametrize("status", ["committed", "rolled_back"])
def test_recovery_removes_cleanup_only_transaction(tmp_path, status):
    transaction, _ = _stage_stale_transaction(
        tmp_path,
        "cleanup-{}".format(status),
        status,
        touched=False,
    )
    recovery_adapter = FakeTransactionDatabaseAdapter()

    assert GenerationTransaction.recover_stale_transactions(
        evidence_parent=transaction.evidence_parent,
        database_adapter=recovery_adapter,
    ) == ()
    assert not os.path.exists(transaction.evidence_directory)
    assert not [
        event for event in recovery_adapter.events
        if event[0] == "restore"
    ]


@requires_posix_transaction_fs
def test_recovery_removes_existing_cleanup_tombstone(tmp_path):
    transaction, _ = _stage_stale_transaction(
        tmp_path,
        "existing-tombstone",
        "committed",
        touched=False,
    )
    cleanup_directory = "{}.cleanup".format(transaction.evidence_directory)
    os.replace(transaction.evidence_directory, cleanup_directory)

    assert GenerationTransaction.recover_stale_transactions(
        evidence_parent=transaction.evidence_parent,
        database_adapter=FakeTransactionDatabaseAdapter(),
    ) == ()
    assert not os.path.exists(cleanup_directory)


@requires_posix_transaction_fs
@pytest.mark.parametrize("status", ["rolling_back", "rollback_failed"])
def test_recovery_retries_restore_required_transaction(tmp_path, status):
    transaction, persistent_file = _stage_stale_transaction(
        tmp_path,
        "retry-{}".format(status),
        status,
    )
    recovery_adapter = FakeTransactionDatabaseAdapter()

    assert GenerationTransaction.recover_stale_transactions(
        evidence_parent=transaction.evidence_parent,
        database_adapter=recovery_adapter,
    ) == ()
    assert persistent_file.read_bytes() == b'{"state":"original"}'
    assert set(recovery_adapter.restored_transaction_ids) == {
        transaction.transaction_id,
    }
    assert not os.path.exists(transaction.evidence_directory)


@requires_posix_transaction_fs
def test_recovery_restores_newest_first_with_transaction_id_tiebreaker(
        tmp_path):
    transactions = [
        _stage_stale_transaction(
            tmp_path,
            "older",
            "rolling_back",
            created_at=100,
        )[0],
        _stage_stale_transaction(
            tmp_path,
            "tie-a",
            "rolling_back",
            created_at=200,
        )[0],
        _stage_stale_transaction(
            tmp_path,
            "tie-b",
            "rolling_back",
            created_at=200,
        )[0],
    ]
    recovery_adapter = FakeTransactionDatabaseAdapter()

    assert GenerationTransaction.recover_stale_transactions(
        evidence_parent=transactions[0].evidence_parent,
        database_adapter=recovery_adapter,
    ) == ()
    restored_transactions = []
    for transaction_id in recovery_adapter.restored_transaction_ids:
        if not restored_transactions or \
                restored_transactions[-1] != transaction_id:
            restored_transactions.append(transaction_id)
    assert restored_transactions == ["tie-b", "tie-a", "older"]


@requires_posix_transaction_fs
def test_recovery_retries_one_shot_tombstone_cleanup_failure(
        tmp_path, monkeypatch):
    transaction, persistent_file = _stage_stale_transaction(
        tmp_path,
        "cleanup-retry",
        "rolling_back",
    )
    original_rmtree = generation_transaction.shutil.rmtree
    cleanup_attempts = {"count": 0}

    def fail_first_cleanup(path):
        cleanup_attempts["count"] += 1
        if cleanup_attempts["count"] == 1:
            raise OSError("injected one-shot cleanup failure")
        return original_rmtree(path)

    monkeypatch.setattr(
        generation_transaction.shutil,
        "rmtree",
        fail_first_cleanup,
    )

    assert GenerationTransaction.recover_stale_transactions(
        evidence_parent=transaction.evidence_parent,
        database_adapter=FakeTransactionDatabaseAdapter(),
    ) == ()
    assert cleanup_attempts["count"] == 2
    assert persistent_file.read_bytes() == b'{"state":"original"}'
    assert not os.path.exists(transaction.evidence_directory)
    assert not os.path.exists(
        "{}.cleanup".format(transaction.evidence_directory)
    )


@requires_posix_transaction_fs
def test_recovery_rejects_malformed_manifest_json(tmp_path):
    transaction, _ = _stage_stale_transaction(
        tmp_path,
        "malformed-manifest",
        "rolling_back",
    )
    with open(transaction.manifest_path, "w") as output:
        output.write("{")
    os.chmod(transaction.manifest_path, 0o600)

    with pytest.raises(
            GenerationRecoveryError,
            match="Failed to read JSON snapshot"):
        GenerationTransaction.recover_stale_transactions(
            evidence_parent=transaction.evidence_parent,
            database_adapter=FakeTransactionDatabaseAdapter(),
        )


@requires_posix_transaction_fs
def test_recovery_rejects_unknown_status(tmp_path):
    transaction, _ = _stage_stale_transaction(
        tmp_path,
        "unknown-status",
        "committed",
        touched=False,
    )
    manifest = _load_transaction_manifest(transaction)
    manifest["status"] = "unknown"
    _write_transaction_manifest(transaction, manifest)

    with pytest.raises(GenerationRecoveryError, match="Unknown transaction"):
        GenerationTransaction.recover_stale_transactions(
            evidence_parent=transaction.evidence_parent,
            database_adapter=FakeTransactionDatabaseAdapter(),
        )


@requires_posix_transaction_fs
def test_recovery_rejects_prepared_transaction_with_touched_targets(tmp_path):
    transaction, persistent_file = _stage_stale_transaction(
        tmp_path,
        "prepared-touched",
        "prepared",
        touched=False,
    )
    _set_transaction_manifest_state(
        transaction,
        "prepared",
        touched_scopes=("",),
        touched_files=(str(persistent_file),),
    )

    with pytest.raises(
            GenerationRecoveryError,
            match="Pre-mutation transaction has touched targets"):
        GenerationTransaction.recover_stale_transactions(
            evidence_parent=transaction.evidence_parent,
            database_adapter=FakeTransactionDatabaseAdapter(),
        )


@requires_posix_transaction_fs
def test_recovery_rejects_insecure_evidence_permissions(tmp_path):
    transaction, _ = _stage_stale_transaction(
        tmp_path,
        "insecure-mode",
        "committed",
        touched=False,
    )
    os.chmod(transaction.evidence_directory, 0o755)

    with pytest.raises(
            GenerationRecoveryError,
            match="evidence directory is not private"):
        GenerationTransaction.recover_stale_transactions(
            evidence_parent=transaction.evidence_parent,
            database_adapter=FakeTransactionDatabaseAdapter(),
        )


@requires_posix_transaction_fs
def test_recovery_rejects_wrong_evidence_ownership(tmp_path, monkeypatch):
    transaction, _ = _stage_stale_transaction(
        tmp_path,
        "wrong-owner",
        "committed",
        touched=False,
    )
    original_lstat = generation_transaction.os.lstat
    evidence_directory = os.path.abspath(transaction.evidence_directory)

    def wrong_owner_lstat(path):
        metadata = original_lstat(path)
        if os.path.abspath(path) != evidence_directory:
            return metadata
        values = list(metadata)
        values[4] = metadata.st_uid + 1
        return os.stat_result(values)

    monkeypatch.setattr(
        generation_transaction.os,
        "lstat",
        wrong_owner_lstat,
    )

    with pytest.raises(GenerationRecoveryError, match="owned"):
        GenerationTransaction.recover_stale_transactions(
            evidence_parent=transaction.evidence_parent,
            database_adapter=FakeTransactionDatabaseAdapter(),
        )


@requires_posix_transaction_fs
def test_recovery_rejects_snapshot_symlink(tmp_path):
    transaction, _ = _stage_stale_transaction(
        tmp_path,
        "snapshot-symlink",
        "rolling_back",
    )
    manifest = _load_transaction_manifest(transaction)
    first_snapshot = os.path.join(
        transaction.evidence_directory,
        manifest["database_snapshots"][0]["path"],
    )
    second_snapshot = os.path.join(
        transaction.evidence_directory,
        manifest["database_snapshots"][1]["path"],
    )
    os.unlink(first_snapshot)
    os.symlink(second_snapshot, first_snapshot)

    with pytest.raises(GenerationRecoveryError, match="contains a symlink"):
        GenerationTransaction.recover_stale_transactions(
            evidence_parent=transaction.evidence_parent,
            database_adapter=FakeTransactionDatabaseAdapter(),
        )


@requires_posix_transaction_fs
def test_recovery_rejects_snapshot_path_escape(tmp_path):
    transaction, _ = _stage_stale_transaction(
        tmp_path,
        "snapshot-escape",
        "rolling_back",
    )
    manifest = _load_transaction_manifest(transaction)
    manifest["database_snapshots"][0]["path"] = "../escape.json"
    _write_transaction_manifest(transaction, manifest)

    with pytest.raises(
            GenerationRecoveryError,
            match="Invalid database snapshot path"):
        GenerationTransaction.recover_stale_transactions(
            evidence_parent=transaction.evidence_parent,
            database_adapter=FakeTransactionDatabaseAdapter(),
        )


@requires_posix_transaction_fs
def test_recovery_rejects_snapshot_hash_corruption(tmp_path):
    transaction, _ = _stage_stale_transaction(
        tmp_path,
        "snapshot-corruption",
        "rolling_back",
    )
    manifest = _load_transaction_manifest(transaction)
    snapshot_path = os.path.join(
        transaction.evidence_directory,
        manifest["database_snapshots"][0]["path"],
    )
    with open(snapshot_path, "w") as output:
        json.dump(
            {"corrupt": {"type": "string", "value": "corrupt"}},
            output,
        )
    os.chmod(snapshot_path, 0o600)

    with pytest.raises(
            GenerationRecoveryError,
            match="snapshot SHA-256 mismatch"):
        GenerationTransaction.recover_stale_transactions(
            evidence_parent=transaction.evidence_parent,
            database_adapter=FakeTransactionDatabaseAdapter(),
        )


@requires_posix_transaction_fs
def test_corrupt_evidence_prevents_all_other_recovery_mutation(tmp_path):
    valid_transaction, _ = _stage_stale_transaction(
        tmp_path,
        "valid-cleanup",
        "committed",
        touched=False,
    )
    corrupt_transaction, persistent_file = _stage_stale_transaction(
        tmp_path,
        "corrupt-restore",
        "rolling_back",
    )
    with open(corrupt_transaction.manifest_path, "w") as output:
        output.write("{")
    os.chmod(corrupt_transaction.manifest_path, 0o600)
    recovery_adapter = FakeTransactionDatabaseAdapter()

    with pytest.raises(GenerationRecoveryError):
        GenerationTransaction.recover_stale_transactions(
            evidence_parent=valid_transaction.evidence_parent,
            database_adapter=recovery_adapter,
        )

    assert os.path.isdir(valid_transaction.evidence_directory)
    assert os.path.isdir(corrupt_transaction.evidence_directory)
    assert persistent_file.read_bytes() == b'{"state":"mutated"}'
    assert not [
        event for event in recovery_adapter.events
        if event[0] == "restore"
    ]

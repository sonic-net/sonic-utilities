from __future__ import absolute_import

import base64
import copy
import hashlib
import json
import math
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
import uuid

from dataclasses import dataclass


DEFAULT_NAMESPACE = ""
DEFAULT_EVIDENCE_PARENT = "/host/generation-transactions"
DATABASES_PER_NAMESPACE = ("CONFIG_DB", "APPL_DB")
SHARED_DATABASES = ("STATE_DB", "LOGLEVEL_DB")
_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9_.-]+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _is_safe_component(value):
    return bool(
        value and
        value not in (".", "..") and
        _SAFE_COMPONENT.match(value)
    )


class GenerationTransactionError(RuntimeError):
    pass


class GenerationCommandError(GenerationTransactionError):
    def __init__(self, operation, target, command, return_code, stdout, stderr):
        self.operation = operation
        self.target = target
        self.command = tuple(command)
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(
            "{} failed for {} with exit code {}: {}".format(
                operation,
                target.display_name,
                return_code,
                stderr.strip() or stdout.strip() or "no command output",
            )
        )


class GenerationSnapshotError(GenerationTransactionError):
    pass


class GenerationVerificationError(GenerationTransactionError):
    pass


class GenerationCleanupError(GenerationTransactionError):
    pass


class GenerationRecoveryError(GenerationTransactionError):
    def __init__(self, failures):
        self.failures = tuple(failures)
        super().__init__(
            "Interrupted generation transaction recovery failed: {}".format(
                "; ".join(self.failures)
            )
        )


class GenerationRollbackError(GenerationTransactionError):
    def __init__(self, original_error, failures, evidence_directory):
        self.original_error = original_error
        self.failures = tuple(failures)
        self.evidence_directory = evidence_directory
        primary = "{}: {}".format(
            type(original_error).__name__,
            original_error,
        ) if original_error is not None else "unknown operation failure"
        super().__init__(
            "{}; rollback was incomplete: {}; evidence retained at {}".format(
                primary,
                "; ".join(self.failures),
                evidence_directory,
            )
        )


@dataclass(frozen=True)
class DatabaseTarget:
    namespace: str
    database: str

    def __post_init__(self):
        namespace = self.namespace or DEFAULT_NAMESPACE
        if namespace and not _is_safe_component(namespace):
            raise ValueError("Invalid database namespace: {!r}".format(namespace))
        if not _is_safe_component(self.database):
            raise ValueError("Invalid database name: {!r}".format(self.database))
        object.__setattr__(self, "namespace", namespace)

    @property
    def display_name(self):
        return "{}:{}".format(self.namespace or "host", self.database)

    @property
    def filename_component(self):
        return "{}-{}".format(self.namespace or "host", self.database)

    def dump_command(self, output_path):
        command = ["sonic-db-dump"]
        if self.namespace:
            command.extend(["--netns", self.namespace])
        command.extend(["-n", self.database, "-o", output_path, "-y"])
        return command

    def flush_command(self):
        command = ["sonic-db-cli"]
        if self.namespace:
            command.extend(["-n", self.namespace])
        command.extend([self.database, "FLUSHDB"])
        return command

    def load_command(self, input_path):
        command = ["sonic-db-load"]
        if self.namespace:
            command.extend(["--netns", self.namespace])
        command.extend(["-n", self.database, "-A", input_path])
        return command


@dataclass(frozen=True)
class DatabaseSnapshot:
    target: DatabaseTarget
    path: str
    sha256: str


@dataclass(frozen=True)
class PersistentFileSnapshot:
    path: str
    existed: bool
    snapshot_path: str
    sha256: str
    mode: int
    uid: int
    gid: int
    xattrs: tuple


def _decode_output(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _default_runner(command):
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def _duplicate_rejecting_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: {!r}".format(key))
        result[key] = value
    return result


def _load_json_file(path):
    try:
        with open(path, "r", encoding="utf-8") as source:
            return json.load(
                source,
                object_pairs_hook=_duplicate_rejecting_object,
            )
    except (OSError, ValueError, TypeError) as error:
        raise GenerationSnapshotError(
            "Failed to read JSON snapshot {}: {}".format(path, error)
        ) from error


def _validate_dump_record(key, record):
    if not isinstance(key, str):
        raise GenerationVerificationError("Redis dump key must be a string")
    if not isinstance(record, dict):
        raise GenerationVerificationError(
            "Redis dump record for {!r} must be an object".format(key)
        )
    if "type" not in record or "value" not in record:
        raise GenerationVerificationError(
            "Redis dump record for {!r} requires type and value".format(key)
        )
    if not isinstance(record["type"], str) or not record["type"]:
        raise GenerationVerificationError(
            "Redis dump type for {!r} must be a non-empty string".format(key)
        )

    has_ttl = "ttl" in record
    has_expireat = "expireat" in record
    if has_ttl != has_expireat:
        missing = "expireat" if has_ttl else "ttl"
        raise GenerationVerificationError(
            "Redis dump record for {!r} is missing {}".format(key, missing)
        )
    if has_ttl:
        ttl = record["ttl"]
        expireat = record["expireat"]
        if isinstance(ttl, bool) or not isinstance(ttl, (int, float)):
            raise GenerationVerificationError(
                "Redis dump ttl for {!r} must be numeric".format(key)
            )
        if not math.isfinite(ttl):
            raise GenerationVerificationError(
                "Redis dump ttl for {!r} must be finite".format(key)
            )
        if isinstance(expireat, bool) or not isinstance(
                expireat, (int, float)):
            raise GenerationVerificationError(
                "Redis dump expireat for {!r} must be numeric".format(key)
            )
        if not math.isfinite(expireat):
            raise GenerationVerificationError(
                "Redis dump expireat for {!r} must be finite".format(key)
            )


def sanitize_database_dump(database_dump):
    if not isinstance(database_dump, dict):
        raise GenerationVerificationError(
            "Redis database dump must be a JSON object"
        )

    sanitized = copy.deepcopy(database_dump)
    for key, record in sanitized.items():
        _validate_dump_record(key, record)
        if record.get("ttl", 0) < 0:
            record.pop("ttl", None)
            record.pop("expireat", None)
    return sanitized


def compare_database_dumps(
        expected,
        actual,
        now=None,
        expiration_tolerance=2):
    expected = sanitize_database_dump(expected)
    actual = sanitize_database_dump(actual)
    current_time = time.time() if now is None else now

    extra_keys = sorted(set(actual) - set(expected))
    if extra_keys:
        raise GenerationVerificationError(
            "Restored database contains destination-only keys: {}".format(
                ", ".join(repr(key) for key in extra_keys)
            )
        )

    for key in sorted(expected):
        expected_record = expected[key]
        actual_record = actual.get(key)
        expected_expireat = expected_record.get("expireat")

        if actual_record is None:
            if expected_expireat is not None and \
                    expected_expireat <= current_time + expiration_tolerance:
                continue
            raise GenerationVerificationError(
                "Restored database is missing key {!r}".format(key)
            )

        if expected_record["type"] != actual_record["type"]:
            raise GenerationVerificationError(
                "Redis type mismatch for {!r}: expected {!r}, got {!r}".format(
                    key,
                    expected_record["type"],
                    actual_record["type"],
                )
            )
        if expected_record["value"] != actual_record["value"]:
            raise GenerationVerificationError(
                "Redis value mismatch for {!r}".format(key)
            )

        actual_expireat = actual_record.get("expireat")
        if (expected_expireat is None) != (actual_expireat is None):
            raise GenerationVerificationError(
                "Redis expiration mismatch for {!r}".format(key)
            )
        if expected_expireat is not None and abs(
                expected_expireat - actual_expireat) > expiration_tolerance:
            raise GenerationVerificationError(
                "Redis absolute expiration mismatch for {!r}: "
                "expected {!r}, got {!r}".format(
                    key,
                    expected_expireat,
                    actual_expireat,
                )
            )


def _sha256_bytes(content):
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_directory(path):
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _require_current_owner(metadata, path):
    if hasattr(os, "geteuid") and metadata.st_uid != os.geteuid():
        raise GenerationSnapshotError(
            "Evidence path is not owned by the current user: {}".format(path)
        )


def _ensure_private_directory(path):
    if os.path.lexists(path):
        metadata = os.lstat(path)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise GenerationSnapshotError(
                "Evidence path is not a real directory: {}".format(path)
            )
        _require_current_owner(metadata, path)
        os.chmod(path, stat.S_IRWXU)
    else:
        os.makedirs(path, mode=0o700)
    _fsync_directory(os.path.dirname(path) or ".")


def _atomic_write_bytes(path, content, mode=0o600):
    parent = os.path.dirname(path) or "."
    if not os.path.lexists(parent):
        raise GenerationSnapshotError(
            "Destination directory does not exist: {}".format(parent)
        )
    parent_metadata = os.lstat(parent)
    if stat.S_ISLNK(parent_metadata.st_mode) or not stat.S_ISDIR(
            parent_metadata.st_mode):
        raise GenerationSnapshotError(
            "Destination parent is not a real directory: {}".format(parent)
        )
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=".{}.".format(os.path.basename(path)),
        dir=parent,
    )
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as output:
            descriptor = None
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, path)
        os.chmod(path, mode)
        _fsync_directory(parent)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if os.path.lexists(temporary_path):
            os.unlink(temporary_path)


def _atomic_write_json(path, value, mode=0o600):
    content = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    _atomic_write_bytes(path, content, mode=mode)


def _read_regular_file(path):
    metadata = os.lstat(path)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise GenerationSnapshotError(
            "Snapshot path is not a regular file: {}".format(path)
        )
    with open(path, "rb") as source:
        return source.read()


def _fsync_file(path):
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _list_xattrs(path):
    if not hasattr(os, "listxattr"):
        return ()
    try:
        return tuple(sorted(
            (
                name,
                base64.b64encode(os.getxattr(path, name)).decode("ascii"),
            )
            for name in os.listxattr(path)
        ))
    except OSError as error:
        raise GenerationSnapshotError(
            "Failed to read extended attributes for {}: {}".format(
                path, error)
        ) from error


def _restore_xattrs(path, expected_xattrs):
    if not hasattr(os, "listxattr"):
        if expected_xattrs:
            raise GenerationVerificationError(
                "Extended attributes are unsupported for {}".format(path)
            )
        return

    expected = dict(expected_xattrs)
    for name in os.listxattr(path):
        if name not in expected:
            os.removexattr(path, name)
    for name, encoded_value in expected.items():
        os.setxattr(path, name, base64.b64decode(encoded_value))


class DatabaseAdapter:
    def __init__(
            self,
            runner=None,
            now=None,
            expiration_tolerance=2):
        self._runner = runner or _default_runner
        self._now = now or time.time
        self._expiration_tolerance = expiration_tolerance

    def snapshot(self, target, evidence_directory):
        _ensure_private_directory(evidence_directory)
        unique = uuid.uuid4().hex
        raw_path = os.path.join(
            evidence_directory,
            ".raw-{}-{}.json".format(target.filename_component, unique),
        )
        snapshot_path = os.path.join(
            evidence_directory,
            "{}-{}.json".format(target.filename_component, unique),
        )

        try:
            self._run("dump", target, target.dump_command(raw_path))
            raw_dump = _load_json_file(raw_path)
            sanitized_dump = sanitize_database_dump(raw_dump)
            _atomic_write_json(snapshot_path, sanitized_dump, mode=0o600)
            return DatabaseSnapshot(
                target=target,
                path=snapshot_path,
                sha256=_sha256_file(snapshot_path),
            )
        finally:
            if os.path.lexists(raw_path):
                os.unlink(raw_path)

    def restore(self, snapshot):
        content = _read_regular_file(snapshot.path)
        actual_hash = _sha256_bytes(content)
        if actual_hash != snapshot.sha256:
            raise GenerationSnapshotError(
                "Database snapshot hash mismatch for {}".format(
                    snapshot.target.display_name)
            )

        expected_dump = sanitize_database_dump(_load_json_file(snapshot.path))
        self._run(
            "flush",
            snapshot.target,
            snapshot.target.flush_command(),
        )
        self._run(
            "load",
            snapshot.target,
            snapshot.target.load_command(snapshot.path),
        )

        verification_path = os.path.join(
            os.path.dirname(snapshot.path),
            ".verify-{}-{}.json".format(
                snapshot.target.filename_component,
                uuid.uuid4().hex,
            ),
        )
        try:
            self._run(
                "dump",
                snapshot.target,
                snapshot.target.dump_command(verification_path),
            )
            actual_dump = sanitize_database_dump(
                _load_json_file(verification_path)
            )
            compare_database_dumps(
                expected_dump,
                actual_dump,
                now=self._now(),
                expiration_tolerance=self._expiration_tolerance,
            )
        finally:
            if os.path.lexists(verification_path):
                os.unlink(verification_path)

    def _run(self, operation, target, command):
        try:
            result = self._runner(command)
        except Exception as error:
            raise GenerationCommandError(
                operation,
                target,
                command,
                -1,
                "",
                str(error),
            ) from error

        return_code = getattr(result, "returncode", None)
        if return_code is None:
            raise GenerationCommandError(
                operation,
                target,
                command,
                -1,
                "",
                "command runner returned no exit status",
            )
        if return_code != 0:
            raise GenerationCommandError(
                operation,
                target,
                command,
                return_code,
                _decode_output(getattr(result, "stdout", "")),
                _decode_output(getattr(result, "stderr", "")),
            )
        return result


class GenerationTransaction:
    _CLEANUP_SUFFIX = ".cleanup"
    _STAGING_SUFFIX = ".creating"
    _MANIFEST_KEYS = frozenset({
        "schema_version",
        "transaction_id",
        "created_at",
        "status",
        "namespaces",
        "persistent_files",
        "database_snapshots",
        "file_snapshots",
        "touched_scopes",
        "shared_databases_touched",
        "touched_files",
        "service_recovery_required",
        "failures",
    })
    _DATABASE_SNAPSHOT_KEYS = frozenset({
        "namespace",
        "database",
        "path",
        "sha256",
    })
    _FILE_SNAPSHOT_KEYS = frozenset({
        "path",
        "existed",
        "snapshot_path",
        "sha256",
        "mode",
        "uid",
        "gid",
        "xattrs",
    })
    _CLEANUP_ONLY_STATUSES = frozenset({
        "preparing",
        "prepared",
        "committed",
        "rolled_back",
        "rollback_cleanup_failed",
    })
    _RECOVERY_STATUSES = frozenset({
        "mutating",
        "rolling_back",
        "rollback_failed",
    })
    _KNOWN_STATUSES = _CLEANUP_ONLY_STATUSES | _RECOVERY_STATUSES

    def __init__(
            self,
            namespaces,
            persistent_files=(),
            evidence_parent=DEFAULT_EVIDENCE_PARENT,
            database_adapter=None,
            transaction_id=None):
        normalized_namespaces = tuple(
            namespace or DEFAULT_NAMESPACE for namespace in namespaces
        )
        persistent_files = tuple(persistent_files)
        if not normalized_namespaces:
            raise ValueError("At least one namespace is required")
        if len(set(normalized_namespaces)) != len(normalized_namespaces):
            raise ValueError("Database namespaces must be unique")
        for namespace in normalized_namespaces:
            if namespace and not _is_safe_component(namespace):
                raise ValueError(
                    "Invalid database namespace: {!r}".format(namespace)
                )
        if len(set(persistent_files)) != len(persistent_files):
            raise ValueError("Persistent file paths must be unique")
        for path in persistent_files:
            if not os.path.isabs(path):
                raise ValueError(
                    "Persistent file path must be absolute: {!r}".format(path)
                )
        if not os.path.isabs(evidence_parent):
            raise ValueError("Transaction evidence parent must be absolute")

        self.namespaces = normalized_namespaces
        self.persistent_files = persistent_files
        self.evidence_parent = evidence_parent
        self.database_adapter = database_adapter or DatabaseAdapter()
        self.transaction_id = transaction_id or "{}-{}".format(
            time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
            uuid.uuid4().hex,
        )
        if not _is_safe_component(self.transaction_id):
            raise ValueError("Invalid transaction ID")
        if self.transaction_id.endswith(self._CLEANUP_SUFFIX):
            raise ValueError(
                "Transaction ID conflicts with the cleanup evidence suffix"
            )
        if self.transaction_id.endswith(self._STAGING_SUFFIX):
            raise ValueError(
                "Transaction ID conflicts with the staging evidence suffix"
            )

        self.evidence_directory = os.path.join(
            evidence_parent,
            self.transaction_id,
        )
        self.staging_directory = \
            self.evidence_directory + self._STAGING_SUFFIX
        self.database_directory = os.path.join(
            self.evidence_directory,
            "databases",
        )
        self.file_directory = os.path.join(
            self.evidence_directory,
            "files",
        )
        self.manifest_path = os.path.join(
            self.evidence_directory,
            "manifest.json",
        )

        self._database_snapshots = {}
        self._file_snapshots = {}
        self._touched_scopes = []
        self._shared_databases_touched = False
        self._touched_files = []
        self._prepared = False
        self._closed = False
        self._manifest = {
            "schema_version": 1,
            "transaction_id": self.transaction_id,
            "created_at": int(time.time()),
            "status": "new",
            "namespaces": list(self.namespaces),
            "persistent_files": list(self.persistent_files),
            "database_snapshots": [],
            "file_snapshots": [],
            "touched_scopes": [],
            "shared_databases_touched": False,
            "touched_files": [],
            "service_recovery_required": False,
            "failures": [],
        }

    @classmethod
    def for_golden_native_host(
            cls,
            asic_namespaces,
            persistent_files=(),
            evidence_parent=DEFAULT_EVIDENCE_PARENT,
            database_adapter=None,
            transaction_id=None):
        return cls(
            (DEFAULT_NAMESPACE,) + tuple(asic_namespaces),
            persistent_files=persistent_files,
            evidence_parent=evidence_parent,
            database_adapter=database_adapter,
            transaction_id=transaction_id,
        )

    @classmethod
    def recover_stale_transactions(
            cls,
            evidence_parent=DEFAULT_EVIDENCE_PARENT,
            database_adapter=None,
            service_quiescence=None,
            service_recovery=None):
        if not os.path.lexists(evidence_parent):
            return ()

        parent_metadata = os.lstat(evidence_parent)
        if stat.S_ISLNK(parent_metadata.st_mode) or not stat.S_ISDIR(
                parent_metadata.st_mode):
            raise GenerationRecoveryError([
                "transaction evidence parent is not a real directory: "
                "{}".format(evidence_parent)
            ])
        if stat.S_IMODE(parent_metadata.st_mode) & 0o077:
            raise GenerationRecoveryError([
                "transaction evidence parent is not private: {}".format(
                    evidence_parent
                )
            ])
        try:
            _require_current_owner(parent_metadata, evidence_parent)
        except GenerationSnapshotError as error:
            raise GenerationRecoveryError([str(error)]) from error

        transactions = []
        cleanup_directories = []
        staging_directories = []
        validation_failures = []
        for entry_name in sorted(os.listdir(evidence_parent)):
            evidence_directory = os.path.join(evidence_parent, entry_name)
            try:
                if entry_name.endswith(cls._STAGING_SUFFIX):
                    transaction_id = entry_name[:-len(cls._STAGING_SUFFIX)]
                    if not _is_safe_component(transaction_id):
                        raise GenerationSnapshotError(
                            "Invalid staging evidence directory name: {!r}".
                            format(entry_name)
                        )
                    cls._validate_staging_directory(
                        evidence_directory,
                        evidence_parent,
                    )
                    staging_directories.append(evidence_directory)
                    continue
                if entry_name.endswith(cls._CLEANUP_SUFFIX):
                    transaction_id = entry_name[:-len(cls._CLEANUP_SUFFIX)]
                    if not _is_safe_component(transaction_id):
                        raise GenerationSnapshotError(
                            "Invalid cleanup evidence directory name: {!r}".
                            format(entry_name)
                        )
                    cls._validate_cleanup_directory(
                        evidence_directory,
                        evidence_parent,
                    )
                    cleanup_directories.append(evidence_directory)
                    continue
                transactions.append(cls._load_stale_transaction(
                    evidence_directory,
                    evidence_parent=evidence_parent,
                    database_adapter=database_adapter,
                ))
            except Exception as error:
                validation_failures.append(
                    "{}: {}: {}".format(
                        evidence_directory,
                        type(error).__name__,
                        error,
                    )
                )

        if validation_failures:
            raise GenerationRecoveryError(validation_failures)

        for transaction in transactions:
            if transaction._manifest["status"] in cls._RECOVERY_STATUSES:
                try:
                    transaction._validate_recovery_snapshots()
                except Exception as error:
                    validation_failures.append(
                        "{}: {}: {}".format(
                            transaction.evidence_directory,
                            type(error).__name__,
                            error,
                        )
                    )

        if validation_failures:
            raise GenerationRecoveryError(validation_failures)

        cleanup_warnings = []
        recovery_failures = []
        recovering = sorted(
            (
                transaction for transaction in transactions
                if transaction._manifest["status"] in cls._RECOVERY_STATUSES
            ),
            key=lambda transaction: (
                transaction._manifest["created_at"],
                transaction.transaction_id,
            ),
            reverse=True,
        )
        for transaction in recovering:
            try:
                transaction.rollback(
                    original_error=GenerationTransactionError(
                        "recovering interrupted generation transaction {}".format(
                            transaction.transaction_id
                        )
                    ),
                    service_quiescence=service_quiescence,
                    service_recovery=service_recovery,
                )
            except GenerationRollbackError as error:
                if transaction._manifest["status"] == \
                        "rollback_cleanup_failed":
                    try:
                        transaction._remove_evidence()
                    except GenerationCleanupError as cleanup_error:
                        cleanup_warnings.append(str(cleanup_error))
                    continue
                recovery_failures.append(str(error))
            except Exception as error:
                recovery_failures.append(
                    "{}: {}: {}".format(
                        transaction.evidence_directory,
                        type(error).__name__,
                        error,
                    )
                )

        if recovery_failures:
            raise GenerationRecoveryError(recovery_failures)

        cleanup_only = sorted(
            (
                transaction for transaction in transactions
                if transaction._manifest["status"] in
                cls._CLEANUP_ONLY_STATUSES
            ),
            key=lambda transaction: (
                transaction._manifest["created_at"],
                transaction.transaction_id,
            ),
        )

        pre_mutation_service_recovery = [
            transaction for transaction in cleanup_only
            if transaction._manifest["status"] in ("preparing", "prepared")
            and transaction.service_recovery_required
        ]
        if pre_mutation_service_recovery:
            try:
                if service_recovery is not None:
                    service_recovery()
                for transaction in pre_mutation_service_recovery:
                    transaction.mark_service_recovery_complete()
            except Exception as error:
                raise GenerationRecoveryError([
                    "recover services for interrupted pre-mutation "
                    "transactions: {}: {}".format(
                        type(error).__name__,
                        error,
                    )
                ]) from error

        for transaction in cleanup_only:
            try:
                transaction._remove_evidence()
            except GenerationCleanupError as error:
                cleanup_warnings.append(str(error))

        for cleanup_directory in cleanup_directories:
            try:
                cls._remove_cleanup_directory(
                    cleanup_directory,
                    evidence_parent,
                )
            except GenerationCleanupError as error:
                cleanup_warnings.append(str(error))

        for staging_directory in staging_directories:
            try:
                cls._remove_staging_directory(
                    staging_directory,
                    evidence_parent,
                )
            except GenerationCleanupError as error:
                cleanup_warnings.append(str(error))

        return tuple(cleanup_warnings)

    @classmethod
    def _load_stale_transaction(
            cls,
            evidence_directory,
            evidence_parent,
            database_adapter):
        directory_metadata = os.lstat(evidence_directory)
        if stat.S_ISLNK(directory_metadata.st_mode) or not stat.S_ISDIR(
                directory_metadata.st_mode):
            raise GenerationSnapshotError(
                "Transaction evidence entry is not a real directory"
            )
        if stat.S_IMODE(directory_metadata.st_mode) & 0o077:
            raise GenerationSnapshotError(
                "Transaction evidence directory is not private"
            )
        _require_current_owner(directory_metadata, evidence_directory)

        transaction_id = os.path.basename(evidence_directory)
        if not _is_safe_component(transaction_id):
            raise GenerationSnapshotError(
                "Invalid transaction evidence directory name: {!r}".format(
                    transaction_id
                )
            )

        manifest_path = os.path.join(evidence_directory, "manifest.json")
        manifest_metadata = os.lstat(manifest_path)
        if stat.S_ISLNK(manifest_metadata.st_mode) or not stat.S_ISREG(
                manifest_metadata.st_mode):
            raise GenerationSnapshotError(
                "Transaction manifest is not a regular file"
            )
        if stat.S_IMODE(manifest_metadata.st_mode) & 0o077:
            raise GenerationSnapshotError(
                "Transaction manifest is not private"
            )
        _require_current_owner(manifest_metadata, manifest_path)

        manifest = _load_json_file(manifest_path)
        if not isinstance(manifest, dict):
            raise GenerationSnapshotError(
                "Transaction manifest must be a JSON object"
            )
        if set(manifest) != cls._MANIFEST_KEYS:
            raise GenerationSnapshotError(
                "Transaction manifest has an unexpected schema"
            )
        if manifest["schema_version"] != 1:
            raise GenerationSnapshotError(
                "Unsupported transaction manifest schema version: {!r}".format(
                    manifest["schema_version"]
                )
            )
        if manifest["transaction_id"] != transaction_id:
            raise GenerationSnapshotError(
                "Transaction manifest identity does not match its directory"
            )
        if (
                isinstance(manifest["created_at"], bool) or
                not isinstance(manifest["created_at"], int) or
                manifest["created_at"] < 0):
            raise GenerationSnapshotError(
                "Transaction manifest created_at must be a non-negative integer"
            )
        if manifest["status"] not in cls._KNOWN_STATUSES:
            raise GenerationSnapshotError(
                "Unknown transaction status: {!r}".format(manifest["status"])
            )

        namespaces = cls._validate_manifest_string_list(
            manifest["namespaces"],
            "namespaces",
            allow_empty=True,
        )
        if not namespaces:
            raise GenerationSnapshotError(
                "Transaction manifest requires at least one namespace"
            )
        for namespace in namespaces:
            if namespace and not _is_safe_component(namespace):
                raise GenerationSnapshotError(
                    "Invalid transaction namespace: {!r}".format(namespace)
                )

        persistent_files = cls._validate_manifest_string_list(
            manifest["persistent_files"],
            "persistent_files",
            allow_empty=False,
        )
        for path in persistent_files:
            if not os.path.isabs(path):
                raise GenerationSnapshotError(
                    "Persistent file path must be absolute: {!r}".format(path)
                )

        transaction = cls(
            namespaces,
            persistent_files=persistent_files,
            evidence_parent=evidence_parent,
            database_adapter=database_adapter,
            transaction_id=transaction_id,
        )
        if os.path.realpath(transaction.evidence_directory) != \
                os.path.realpath(evidence_directory):
            raise GenerationSnapshotError(
                "Transaction evidence path does not match its manifest"
            )

        transaction._manifest = copy.deepcopy(manifest)
        transaction._validate_evidence_subdirectory(
            transaction.database_directory,
            "Database snapshot directory",
        )
        transaction._validate_evidence_subdirectory(
            transaction.file_directory,
            "File snapshot directory",
        )
        transaction._database_snapshots = \
            transaction._load_database_snapshot_records(
                manifest["database_snapshots"]
            )
        transaction._file_snapshots = transaction._load_file_snapshot_records(
            manifest["file_snapshots"]
        )
        transaction._touched_scopes = list(
            cls._validate_manifest_string_list(
                manifest["touched_scopes"],
                "touched_scopes",
                allow_empty=True,
            )
        )
        if any(
                namespace not in transaction.namespaces
                for namespace in transaction._touched_scopes):
            raise GenerationSnapshotError(
                "Transaction touched an unknown namespace"
            )
        if not isinstance(manifest["shared_databases_touched"], bool):
            raise GenerationSnapshotError(
                "shared_databases_touched must be boolean"
            )
        transaction._shared_databases_touched = \
            manifest["shared_databases_touched"]
        transaction._touched_files = list(
            cls._validate_manifest_string_list(
                manifest["touched_files"],
                "touched_files",
                allow_empty=False,
            )
        )
        if any(
                path not in transaction.persistent_files
                for path in transaction._touched_files):
            raise GenerationSnapshotError(
                "Transaction touched an unknown persistent file"
            )
        if (
                not isinstance(manifest["failures"], list) or
                any(
                    not isinstance(failure, str)
                    for failure in manifest["failures"]
                )):
            raise GenerationSnapshotError(
                "Transaction failures must be a list of strings"
            )
        if not isinstance(manifest["service_recovery_required"], bool):
            raise GenerationSnapshotError(
                "service_recovery_required must be boolean"
            )
        if manifest["status"] in (
                "preparing",
                "prepared",
                "mutating",
                "committed",
                "rolled_back",
        ) and manifest["failures"]:
            raise GenerationSnapshotError(
                "Transaction status {!r} cannot retain failures".format(
                    manifest["status"]
                )
            )
        if manifest["status"] in (
                "rollback_failed",
                "rollback_cleanup_failed",
        ) and not manifest["failures"]:
            raise GenerationSnapshotError(
                "Transaction status {!r} requires failure details".format(
                    manifest["status"]
                )
            )

        if manifest["status"] == "preparing":
            if (
                    transaction._database_snapshots or
                    transaction._file_snapshots):
                raise GenerationSnapshotError(
                    "Preparing transaction must not publish snapshot records"
                )
        else:
            expected_database_targets = set(transaction._all_database_targets())
            if set(transaction._database_snapshots) != \
                    expected_database_targets:
                raise GenerationSnapshotError(
                    "Transaction database snapshot set is incomplete"
                )
            if set(transaction._file_snapshots) != \
                    set(transaction.persistent_files):
                raise GenerationSnapshotError(
                    "Transaction file snapshot set is incomplete"
                )

        if manifest["status"] in ("preparing", "prepared") and (
                transaction._touched_scopes or
                transaction._shared_databases_touched or
                transaction._touched_files):
            raise GenerationSnapshotError(
                "Pre-mutation transaction has touched targets"
            )

        transaction._prepared = manifest["status"] != "preparing"
        transaction._closed = False
        return transaction

    def _validate_evidence_subdirectory(self, path, label):
        metadata = os.lstat(path)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise GenerationSnapshotError(
                "{} is not a real directory".format(label)
            )
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise GenerationSnapshotError(
                "{} is not private".format(label)
            )
        _require_current_owner(metadata, path)
        if os.path.dirname(os.path.abspath(path)) != \
                os.path.abspath(self.evidence_directory):
            raise GenerationSnapshotError(
                "{} is outside the transaction evidence directory".format(
                    label
                )
            )

    @staticmethod
    def _validate_manifest_string_list(value, label, allow_empty):
        if not isinstance(value, list):
            raise GenerationSnapshotError(
                "Transaction {} must be a list".format(label)
            )
        if any(not isinstance(item, str) for item in value):
            raise GenerationSnapshotError(
                "Transaction {} must contain only strings".format(label)
            )
        if not allow_empty and any(not item for item in value):
            raise GenerationSnapshotError(
                "Transaction {} must not contain empty strings".format(label)
            )
        if len(set(value)) != len(value):
            raise GenerationSnapshotError(
                "Transaction {} must contain unique values".format(label)
            )
        return tuple(value)

    def _load_database_snapshot_records(self, records):
        if not isinstance(records, list):
            raise GenerationSnapshotError(
                "database_snapshots must be a list"
            )
        snapshots = {}
        for record in records:
            if not isinstance(record, dict) or \
                    set(record) != self._DATABASE_SNAPSHOT_KEYS:
                raise GenerationSnapshotError(
                    "Database snapshot record has an unexpected schema"
                )
            target = DatabaseTarget(
                record["namespace"],
                record["database"],
            )
            if target in snapshots:
                raise GenerationSnapshotError(
                    "Duplicate database snapshot: {}".format(
                        target.display_name
                    )
                )
            if not isinstance(record["sha256"], str) or not _SHA256.match(
                    record["sha256"]):
                raise GenerationSnapshotError(
                    "Invalid database snapshot SHA-256 for {}".format(
                        target.display_name
                    )
                )
            path = self._resolve_snapshot_path(
                record["path"],
                self.database_directory,
                "database snapshot",
            )
            snapshots[target] = DatabaseSnapshot(
                target=target,
                path=path,
                sha256=record["sha256"],
            )
        return snapshots

    def _load_file_snapshot_records(self, records):
        if not isinstance(records, list):
            raise GenerationSnapshotError("file_snapshots must be a list")
        snapshots = {}
        for record in records:
            if not isinstance(record, dict) or \
                    set(record) != self._FILE_SNAPSHOT_KEYS:
                raise GenerationSnapshotError(
                    "File snapshot record has an unexpected schema"
                )
            path = record["path"]
            if not isinstance(path, str) or not os.path.isabs(path):
                raise GenerationSnapshotError(
                    "File snapshot path must be absolute"
                )
            if path in snapshots:
                raise GenerationSnapshotError(
                    "Duplicate persistent file snapshot: {}".format(path)
                )
            if not isinstance(record["existed"], bool):
                raise GenerationSnapshotError(
                    "File snapshot existed field must be boolean"
                )

            xattrs = self._validate_manifest_xattrs(record["xattrs"], path)
            if record["existed"]:
                if (
                        isinstance(record["mode"], bool) or
                        not isinstance(record["mode"], int) or
                        record["mode"] < 0 or
                        record["mode"] > 0o7777):
                    raise GenerationSnapshotError(
                        "Invalid file snapshot mode for {}".format(path)
                    )
                if (
                        isinstance(record["uid"], bool) or
                        not isinstance(record["uid"], int) or
                        record["uid"] < 0 or
                        isinstance(record["gid"], bool) or
                        not isinstance(record["gid"], int) or
                        record["gid"] < 0):
                    raise GenerationSnapshotError(
                        "Invalid file snapshot ownership for {}".format(path)
                    )
                if (
                        not isinstance(record["sha256"], str) or
                        not _SHA256.match(record["sha256"])):
                    raise GenerationSnapshotError(
                        "Invalid file snapshot SHA-256 for {}".format(path)
                    )
                snapshot_path = self._resolve_snapshot_path(
                    record["snapshot_path"],
                    self.file_directory,
                    "file snapshot",
                )
            else:
                if (
                        record["snapshot_path"] != "" or
                        record["sha256"] != "" or
                        record["mode"] != 0 or
                        record["uid"] != -1 or
                        record["gid"] != -1 or
                        xattrs):
                    raise GenerationSnapshotError(
                        "Nonexistent file snapshot has unexpected metadata: "
                        "{}".format(path)
                    )
                snapshot_path = ""

            snapshots[path] = PersistentFileSnapshot(
                path=path,
                existed=record["existed"],
                snapshot_path=snapshot_path,
                sha256=record["sha256"],
                mode=record["mode"],
                uid=record["uid"],
                gid=record["gid"],
                xattrs=xattrs,
            )
        return snapshots

    @staticmethod
    def _validate_manifest_xattrs(value, path):
        if not isinstance(value, list):
            raise GenerationSnapshotError(
                "File snapshot xattrs must be a list for {}".format(path)
            )
        xattrs = []
        names = set()
        for item in value:
            if (
                    not isinstance(item, (list, tuple)) or
                    len(item) != 2 or
                    not isinstance(item[0], str) or
                    not item[0] or
                    not isinstance(item[1], str)):
                raise GenerationSnapshotError(
                    "Invalid file snapshot xattr for {}".format(path)
                )
            if item[0] in names:
                raise GenerationSnapshotError(
                    "Duplicate file snapshot xattr for {}".format(path)
                )
            try:
                base64.b64decode(item[1], validate=True)
            except (ValueError, TypeError) as error:
                raise GenerationSnapshotError(
                    "Invalid file snapshot xattr value for {}".format(path)
                ) from error
            names.add(item[0])
            xattrs.append((item[0], item[1]))
        return tuple(sorted(xattrs))

    def _resolve_snapshot_path(self, relative_path, expected_parent, label):
        if (
                not isinstance(relative_path, str) or
                not relative_path or
                os.path.isabs(relative_path) or
                os.path.normpath(relative_path) != relative_path or
                relative_path == os.pardir or
                relative_path.startswith(os.pardir + os.sep)):
            raise GenerationSnapshotError(
                "Invalid {} path: {!r}".format(label, relative_path)
            )
        candidate = os.path.abspath(os.path.join(
            self.evidence_directory,
            relative_path,
        ))
        expected_parent_path = os.path.abspath(expected_parent)
        try:
            lexically_contained = os.path.commonpath(
                (candidate, expected_parent_path)
            ) == expected_parent_path
        except ValueError:
            lexically_contained = False
        if not lexically_contained:
            raise GenerationSnapshotError(
                "{} path escapes its evidence directory".format(label)
            )

        current_path = expected_parent_path
        relative_to_parent = os.path.relpath(
            candidate,
            expected_parent_path,
        )
        for component in relative_to_parent.split(os.sep):
            current_path = os.path.join(current_path, component)
            if stat.S_ISLNK(os.lstat(current_path).st_mode):
                raise GenerationSnapshotError(
                    "{} path contains a symlink".format(label)
                )

        resolved = os.path.realpath(candidate)
        expected_parent = os.path.realpath(expected_parent)
        try:
            contained = os.path.commonpath(
                (resolved, expected_parent)
            ) == expected_parent
        except ValueError:
            contained = False
        if not contained:
            raise GenerationSnapshotError(
                "{} path escapes its evidence directory".format(label)
            )
        return resolved

    def _validate_recovery_snapshots(self):
        for snapshot in self._database_snapshots.values():
            self._validate_regular_snapshot_file(
                snapshot.path,
                snapshot.sha256,
                snapshot.target.display_name,
            )
            sanitize_database_dump(_load_json_file(snapshot.path))

        for snapshot in self._file_snapshots.values():
            if not snapshot.existed:
                continue
            self._validate_regular_snapshot_file(
                snapshot.snapshot_path,
                snapshot.sha256,
                snapshot.path,
            )

    @staticmethod
    def _validate_regular_snapshot_file(path, expected_hash, label):
        metadata = os.lstat(path)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise GenerationSnapshotError(
                "Recovery snapshot is not a regular file for {}".format(label)
            )
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise GenerationSnapshotError(
                "Recovery snapshot is not private for {}".format(label)
            )
        _require_current_owner(metadata, path)
        if _sha256_file(path) != expected_hash:
            raise GenerationSnapshotError(
                "Recovery snapshot SHA-256 mismatch for {}".format(label)
            )

    def _remove_evidence(self):
        cleanup_directory = \
            self.evidence_directory + self._CLEANUP_SUFFIX
        if not os.path.lexists(self.evidence_directory):
            if os.path.lexists(cleanup_directory):
                self._remove_cleanup_directory(
                    cleanup_directory,
                    self.evidence_parent,
                )
                self._closed = True
            return
        metadata = os.lstat(self.evidence_directory)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise GenerationCleanupError(
                "Refusing to remove invalid transaction evidence path: "
                "{}".format(self.evidence_directory)
            )
        if os.path.lexists(cleanup_directory):
            raise GenerationCleanupError(
                "Refusing to replace existing cleanup evidence path: "
                "{}".format(cleanup_directory)
            )
        try:
            os.rename(self.evidence_directory, cleanup_directory)
            _fsync_directory(self.evidence_parent)
        except OSError as error:
            raise GenerationCleanupError(
                "Transaction evidence cleanup staging failed at {}: {}".format(
                    self.evidence_directory,
                    error,
                )
            ) from error
        self._remove_cleanup_directory(
            cleanup_directory,
            self.evidence_parent,
        )
        self._closed = True

    @classmethod
    def _validate_cleanup_directory(cls, cleanup_directory, evidence_parent):
        cls._validate_transient_directory(
            cleanup_directory,
            evidence_parent,
            cls._CLEANUP_SUFFIX,
            "Cleanup",
        )

    @classmethod
    def _validate_staging_directory(cls, staging_directory, evidence_parent):
        cls._validate_transient_directory(
            staging_directory,
            evidence_parent,
            cls._STAGING_SUFFIX,
            "Staging",
        )

    @classmethod
    def _validate_transient_directory(
            cls, directory, evidence_parent, suffix, label):
        directory = os.path.abspath(directory)
        evidence_parent = os.path.abspath(evidence_parent)
        if os.path.dirname(directory) != evidence_parent:
            raise GenerationSnapshotError(
                "{} evidence path is outside its evidence parent".format(label)
            )
        entry_name = os.path.basename(directory)
        transaction_id = entry_name[:-len(suffix)] \
            if entry_name.endswith(suffix) else ""
        if not _is_safe_component(transaction_id):
            raise GenerationSnapshotError(
                "Invalid {} evidence directory name: {!r}".format(
                    label.lower(), entry_name
                )
            )
        metadata = os.lstat(directory)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise GenerationSnapshotError(
                "{} evidence entry is not a real directory".format(label)
            )
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise GenerationSnapshotError(
                "{} evidence directory is not private".format(label)
            )
        _require_current_owner(metadata, directory)

    @classmethod
    def _remove_cleanup_directory(cls, cleanup_directory, evidence_parent):
        try:
            cls._validate_cleanup_directory(
                cleanup_directory,
                evidence_parent,
            )
            shutil.rmtree(cleanup_directory)
            _fsync_directory(evidence_parent)
        except (OSError, GenerationSnapshotError) as error:
            raise GenerationCleanupError(
                "Transaction cleanup evidence removal failed at {}: {}".format(
                    cleanup_directory,
                    error,
                )
            ) from error

    @classmethod
    def _remove_staging_directory(cls, staging_directory, evidence_parent):
        try:
            cls._validate_staging_directory(
                staging_directory,
                evidence_parent,
            )
            shutil.rmtree(staging_directory)
            _fsync_directory(evidence_parent)
        except (OSError, GenerationSnapshotError) as error:
            raise GenerationCleanupError(
                "Transaction staging evidence removal failed at {}: {}".format(
                    staging_directory,
                    error,
                )
            ) from error

    @property
    def service_recovery_required(self):
        return self._manifest["service_recovery_required"]

    def mark_service_recovery_complete(self):
        if self._closed:
            raise GenerationTransactionError(
                "Closed transaction cannot record service recovery"
            )
        if not self.service_recovery_required:
            return
        self._manifest["service_recovery_required"] = False
        self._write_manifest()

    def begin(self, service_quiescence=None, service_recovery=None):
        if self._prepared or self._closed:
            raise GenerationTransactionError(
                "Transaction cannot be prepared in its current state"
            )
        if (service_quiescence is None) != (service_recovery is None):
            raise ValueError(
                "Service quiescence and recovery callbacks must be paired"
            )

        _ensure_private_directory(self.evidence_parent)
        if os.path.lexists(self.evidence_directory):
            raise GenerationSnapshotError(
                "Transaction evidence path already exists: {}".format(
                    self.evidence_directory
                )
            )
        if os.path.lexists(self.staging_directory):
            raise GenerationSnapshotError(
                "Transaction staging path already exists: {}".format(
                    self.staging_directory
                )
            )

        quiescence_recorded = False
        try:
            staging_database_directory = os.path.join(
                self.staging_directory,
                "databases",
            )
            staging_file_directory = os.path.join(
                self.staging_directory,
                "files",
            )
            staging_manifest_path = os.path.join(
                self.staging_directory,
                "manifest.json",
            )
            _ensure_private_directory(self.staging_directory)
            _ensure_private_directory(staging_database_directory)
            _ensure_private_directory(staging_file_directory)
            self._manifest["status"] = "preparing"
            self._manifest["service_recovery_required"] = \
                service_quiescence is not None
            _atomic_write_json(
                staging_manifest_path,
                self._manifest,
                mode=0o600,
            )
            _fsync_directory(self.staging_directory)
            os.rename(self.staging_directory, self.evidence_directory)
            _fsync_directory(self.evidence_parent)
            quiescence_recorded = service_quiescence is not None

            if service_quiescence is not None:
                service_quiescence()

            for target in self._all_database_targets():
                snapshot = self.database_adapter.snapshot(
                    target,
                    self.database_directory,
                )
                self._database_snapshots[target] = snapshot
                self._manifest["database_snapshots"].append({
                    "namespace": target.namespace,
                    "database": target.database,
                    "path": os.path.relpath(
                        snapshot.path,
                        self.evidence_directory,
                    ),
                    "sha256": snapshot.sha256,
                })

            for index, path in enumerate(self.persistent_files):
                snapshot = self._snapshot_file(path, index)
                self._file_snapshots[path] = snapshot
                self._manifest["file_snapshots"].append({
                    "path": path,
                    "existed": snapshot.existed,
                    "snapshot_path": os.path.relpath(
                        snapshot.snapshot_path,
                        self.evidence_directory,
                    ) if snapshot.snapshot_path else "",
                    "sha256": snapshot.sha256,
                    "mode": snapshot.mode,
                    "uid": snapshot.uid,
                    "gid": snapshot.gid,
                    "xattrs": list(snapshot.xattrs),
                })

            self._manifest["status"] = "prepared"
            self._write_manifest()
            self._prepared = True
            return self
        except BaseException as error:
            if quiescence_recorded:
                failures = []
                try:
                    service_recovery()
                except BaseException as recovery_error:
                    failures.append(
                        "recover services after transaction preparation: "
                        "{}: {}".format(
                            type(recovery_error).__name__,
                            recovery_error,
                        )
                    )
                else:
                    try:
                        self.mark_service_recovery_complete()
                    except BaseException as recovery_record_error:
                        failures.append(
                            "record service recovery after transaction "
                            "preparation: {}: {}".format(
                                type(recovery_record_error).__name__,
                                recovery_record_error,
                            )
                        )

                if not failures:
                    try:
                        self._cleanup_after_prepare_failure()
                    except BaseException as cleanup_error:
                        failures.append(
                            "cleanup transaction preparation evidence: "
                            "{}: {}".format(
                                type(cleanup_error).__name__,
                                cleanup_error,
                            )
                        )

                if failures:
                    raise GenerationRollbackError(
                        error,
                        failures,
                        self.evidence_directory,
                    ) from error
                raise

            if not isinstance(error, Exception):
                raise
            try:
                self._cleanup_after_prepare_failure()
            except Exception as cleanup_error:
                raise GenerationTransactionError(
                    "Transaction preparation failed: {}; evidence cleanup "
                    "also failed: {}".format(error, cleanup_error)
                ) from error
            raise

    def mark_scope_touched(self, namespace):
        self._require_prepared()
        namespace = namespace or DEFAULT_NAMESPACE
        if namespace not in self.namespaces:
            raise GenerationTransactionError(
                "Unknown transaction namespace: {!r}".format(namespace)
            )
        if namespace not in self._touched_scopes:
            self._touched_scopes.append(namespace)
            self._manifest["touched_scopes"] = list(self._touched_scopes)
            self._manifest["status"] = "mutating"
            self._write_manifest()

    def mark_shared_databases_touched(self):
        self._require_prepared()
        if not self._shared_databases_touched:
            self._shared_databases_touched = True
            self._manifest["shared_databases_touched"] = True
            self._manifest["status"] = "mutating"
            self._write_manifest()

    def mark_persistent_file_touched(self, path):
        self._require_prepared()
        if path not in self._file_snapshots:
            raise GenerationTransactionError(
                "Persistent file was not snapshotted: {}".format(path)
            )
        if path not in self._touched_files:
            self._touched_files.append(path)
            self._manifest["touched_files"] = list(self._touched_files)
            self._manifest["status"] = "mutating"
            self._write_manifest()

    def publish_persistent_files(self, prepared_files):
        self._require_prepared()
        prepared_items = list(prepared_files)
        prepared_by_destination = {}
        for destination, prepared_path in prepared_items:
            if destination in prepared_by_destination:
                raise GenerationTransactionError(
                    "Persistent publication destinations must be unique"
                )
            prepared_by_destination[destination] = prepared_path

        if set(prepared_by_destination) != set(self.persistent_files):
            raise GenerationTransactionError(
                "Persistent publication must include the complete generation"
            )

        publications = []
        try:
            for destination in self.persistent_files:
                prepared_path = prepared_by_destination[destination]
                destination_parent = os.path.realpath(
                    os.path.dirname(destination) or "."
                )
                prepared_parent = os.path.realpath(
                    os.path.dirname(prepared_path) or "."
                )
                if prepared_parent != destination_parent:
                    raise GenerationTransactionError(
                        "Prepared persistent file must share the destination "
                        "directory: {}".format(destination)
                    )

                metadata = os.lstat(prepared_path)
                if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(
                        metadata.st_mode):
                    raise GenerationTransactionError(
                        "Prepared persistent path is not a regular file: "
                        "{}".format(prepared_path)
                    )

                snapshot = self._file_snapshots[destination]
                mode = snapshot.mode if snapshot.existed else 0o644
                os.chmod(prepared_path, mode)
                if snapshot.existed and hasattr(os, "chown"):
                    os.chown(prepared_path, snapshot.uid, snapshot.gid)
                _restore_xattrs(prepared_path, snapshot.xattrs)
                _fsync_file(prepared_path)
                publications.append((
                    destination,
                    prepared_path,
                    _sha256_file(prepared_path),
                    mode,
                    snapshot,
                ))

            for destination, _, _, _, _ in publications:
                self.mark_persistent_file_touched(destination)

            for destination, prepared_path, _, _, _ in publications:
                os.replace(prepared_path, destination)
                _fsync_directory(os.path.dirname(destination) or ".")

            for destination, _, expected_hash, mode, snapshot in publications:
                metadata = os.lstat(destination)
                if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(
                        metadata.st_mode):
                    raise GenerationVerificationError(
                        "Published path is not a regular file: {}".format(
                            destination)
                    )
                if _sha256_file(destination) != expected_hash:
                    raise GenerationVerificationError(
                        "Published file content mismatch for {}".format(
                            destination)
                    )
                if stat.S_IMODE(metadata.st_mode) != mode:
                    raise GenerationVerificationError(
                        "Published file mode mismatch for {}".format(
                            destination)
                    )
                if snapshot.existed and hasattr(os, "chown") and (
                        metadata.st_uid != snapshot.uid or
                        metadata.st_gid != snapshot.gid):
                    raise GenerationVerificationError(
                        "Published file ownership mismatch for {}".format(
                            destination)
                    )
                if _list_xattrs(destination) != snapshot.xattrs:
                    raise GenerationVerificationError(
                        "Published file xattr mismatch for {}".format(
                            destination)
                    )
        finally:
            for _, prepared_path in prepared_items:
                if os.path.lexists(prepared_path):
                    os.unlink(prepared_path)

    def commit(self):
        self._require_prepared()
        if self.service_recovery_required:
            raise GenerationTransactionError(
                "Cannot commit while service recovery is still required"
            )
        self._manifest["status"] = "committed"
        self._write_manifest()
        self._remove_evidence()

    def rollback(
            self,
            original_error=None,
            service_quiescence=None,
            service_recovery=None):
        self._require_prepared()
        failures = []
        self._manifest["status"] = "rolling_back"
        self._record_manifest_failure(self._write_manifest, failures)

        if service_quiescence is not None:
            try:
                service_quiescence()
            except Exception as error:
                failures.append(
                    "quiesce services before rollback: {}".format(error)
                )

        for namespace in reversed(self._touched_scopes):
            for database in reversed(DATABASES_PER_NAMESPACE):
                target = DatabaseTarget(namespace, database)
                self._record_rollback_failure(
                    "restore {}".format(target.display_name),
                    lambda current=target: self.database_adapter.restore(
                        self._database_snapshots[current]
                    ),
                    failures,
                )

        if self._shared_databases_touched:
            for database in reversed(SHARED_DATABASES):
                target = DatabaseTarget(DEFAULT_NAMESPACE, database)
                self._record_rollback_failure(
                    "restore {}".format(target.display_name),
                    lambda current=target: self.database_adapter.restore(
                        self._database_snapshots[current]
                    ),
                    failures,
                )

        for path in reversed(self._touched_files):
            self._record_rollback_failure(
                "restore file {}".format(path),
                lambda current=path: self._restore_file(
                    self._file_snapshots[current]
                ),
                failures,
            )

        service_recovery_failure_count = len(failures)
        if service_recovery is not None:
            self._record_rollback_failure(
                "recover services",
                service_recovery,
                failures,
            )
        if len(failures) == service_recovery_failure_count:
            self._manifest["service_recovery_required"] = False

        self._manifest["status"] = \
            "rollback_failed" if failures else "rolled_back"
        self._manifest["failures"] = list(failures)
        self._record_manifest_failure(self._write_manifest, failures)

        if not failures:
            try:
                self._remove_evidence()
                return
            except GenerationCleanupError as error:
                failures.append(
                    "cleanup rollback evidence: {}".format(error)
                )
                self._manifest["status"] = "rollback_cleanup_failed"
                self._manifest["failures"] = list(failures)
                self._record_manifest_failure(self._write_manifest, failures)

        raise GenerationRollbackError(
            original_error,
            failures,
            self.evidence_directory,
        )

    def _all_database_targets(self):
        targets = []
        for namespace in self.namespaces:
            for database in DATABASES_PER_NAMESPACE:
                targets.append(DatabaseTarget(namespace, database))
        for database in SHARED_DATABASES:
            targets.append(DatabaseTarget(DEFAULT_NAMESPACE, database))
        return tuple(targets)

    def _snapshot_file(self, path, index):
        if not os.path.lexists(path):
            return PersistentFileSnapshot(
                path=path,
                existed=False,
                snapshot_path="",
                sha256="",
                mode=0,
                uid=-1,
                gid=-1,
                xattrs=(),
            )

        metadata = os.lstat(path)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise GenerationSnapshotError(
                "Persistent path is not a regular file: {}".format(path)
            )
        content = _read_regular_file(path)
        snapshot_path = os.path.join(
            self.file_directory,
            "{:04d}-{}.snapshot".format(index, uuid.uuid4().hex),
        )
        _atomic_write_bytes(snapshot_path, content, mode=0o600)
        return PersistentFileSnapshot(
            path=path,
            existed=True,
            snapshot_path=snapshot_path,
            sha256=_sha256_bytes(content),
            mode=stat.S_IMODE(metadata.st_mode),
            uid=metadata.st_uid,
            gid=metadata.st_gid,
            xattrs=_list_xattrs(path),
        )

    def _restore_file(self, snapshot):
        if not snapshot.existed:
            if os.path.lexists(snapshot.path):
                metadata = os.lstat(snapshot.path)
                if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(
                        metadata.st_mode):
                    raise GenerationVerificationError(
                        "Refusing to remove non-regular rollback path: {}".format(
                            snapshot.path)
                    )
                os.unlink(snapshot.path)
                _fsync_directory(os.path.dirname(snapshot.path) or ".")
            return

        content = _read_regular_file(snapshot.snapshot_path)
        if _sha256_bytes(content) != snapshot.sha256:
            raise GenerationSnapshotError(
                "Persistent file snapshot hash mismatch for {}".format(
                    snapshot.path)
            )

        _atomic_write_bytes(snapshot.path, content, mode=snapshot.mode)
        if hasattr(os, "chown"):
            os.chown(snapshot.path, snapshot.uid, snapshot.gid)
        os.chmod(snapshot.path, snapshot.mode)
        _restore_xattrs(snapshot.path, snapshot.xattrs)
        _fsync_file(snapshot.path)
        _fsync_directory(os.path.dirname(snapshot.path) or ".")

        metadata = os.lstat(snapshot.path)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise GenerationVerificationError(
                "Restored path is not a regular file: {}".format(snapshot.path)
            )
        if _sha256_file(snapshot.path) != snapshot.sha256:
            raise GenerationVerificationError(
                "Restored file content mismatch for {}".format(snapshot.path)
            )
        if stat.S_IMODE(metadata.st_mode) != snapshot.mode:
            raise GenerationVerificationError(
                "Restored file mode mismatch for {}".format(snapshot.path)
            )
        if hasattr(os, "chown") and (
                metadata.st_uid != snapshot.uid or
                metadata.st_gid != snapshot.gid):
            raise GenerationVerificationError(
                "Restored file ownership mismatch for {}".format(snapshot.path)
            )
        if _list_xattrs(snapshot.path) != snapshot.xattrs:
            raise GenerationVerificationError(
                "Restored file xattr mismatch for {}".format(snapshot.path)
            )

    def _write_manifest(self):
        _atomic_write_json(self.manifest_path, self._manifest, mode=0o600)

    def _require_prepared(self):
        if not self._prepared or self._closed:
            raise GenerationTransactionError(
                "Transaction is not active"
            )

    def _cleanup_after_prepare_failure(self):
        if os.path.lexists(self.staging_directory):
            self._remove_staging_directory(
                self.staging_directory,
                self.evidence_parent,
            )
            self._closed = True
        if os.path.lexists(self.evidence_directory):
            self._remove_evidence()

    @staticmethod
    def _record_rollback_failure(label, operation, failures):
        try:
            operation()
        except Exception as error:
            failures.append("{}: {}".format(label, error))

    @staticmethod
    def _record_manifest_failure(operation, failures):
        try:
            operation()
        except Exception as error:
            failures.append("update transaction manifest: {}".format(error))

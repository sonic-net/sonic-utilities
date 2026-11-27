"""Opt-in reporting of the existing GCU command outcome, not application policy.

Reports use the shared SONiC error-reporting envelope. A new invocation UUID
is required for every precheck/application attempt. An absent final report is
not evidence that the command did not run.
"""

from contextlib import contextmanager
from contextvars import ContextVar
import json
import os
from pathlib import Path
import re
import stat
import sys
import threading
import time
import uuid


REPORT_DIRECTORY = "/host/sonic-upgrade-reports"
MAX_STAGES = 1024
MAX_ERRORS = 32
MAX_MESSAGE = 4096
MAX_REDACTION_BYTES = 1024 * 1024

_report = ContextVar("gcu_error_report", default=None)
_scope = ContextVar("gcu_error_report_scope", default="")


def enabled():
    """Return whether this invocation requested a report."""
    return _report.get() is not None


def _exit_code(error, default, interrupt_exit_code):
    if error is None:
        return 0
    if isinstance(error, KeyboardInterrupt):
        return interrupt_exit_code
    if isinstance(error, SystemExit):
        return (error.code & 255) if isinstance(error.code, int) else 1 if error.code else 0
    return default


def _package_version():
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:
        return "unknown"
    for package in ("sonic-gcu", "sonic-utilities"):
        try:
            return f"{package}:{version(package)}"
        except PackageNotFoundError:
            continue
    return "unknown"


class ErrorReport:
    """Collect bounded stage observations without recording configuration."""

    def __init__(self, report_id, phase, failure_exit_code, interrupt_exit_code=130):
        self.guid = str(uuid.UUID(str(report_id)))
        if phase not in ("precheck", "apply"):
            raise ValueError("Report phase must be precheck or apply")
        self.script_name = f"gcu-{phase}"
        self.failure_exit_code = failure_exit_code
        self.interrupt_exit_code = interrupt_exit_code
        self.started = time.monotonic()
        self.stages = []
        self.errors = []
        self._values = set()
        self._value_bytes = 0
        self._complete = True
        self._has_config = False
        self._truncated = False
        self._lock = threading.Lock()

        directory = Path(REPORT_DIRECTORY)
        directory.mkdir(mode=0o700, exist_ok=True)
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("Report directory must not be a symlink")
        if os.name == "posix" and (
            info.st_uid != os.geteuid() or info.st_mode & 0o022
        ):
            raise ValueError("Report directory must be owned and not group/world writable")
        self.path = directory / f"{self.script_name}.{self.guid}.json"
        if os.path.lexists(self.path):
            raise FileExistsError("Report ID has already been used; do not retry the patch")
        self.pending = self.path.with_suffix(".pending")
        # Exclusive reservation also prevents concurrent reuse before publication.
        fd = os.open(self.pending, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        # Publication releases the pending name, so recheck after acquiring it.
        if os.path.lexists(self.path):
            raise FileExistsError("Report ID has already been used; do not retry the patch")

    def remember(self, data, config=False):
        """Inventory scalar values for conservative diagnostic redaction."""
        with self._lock:
            if config:
                self._has_config = True
            stack = [data]
            while stack and self._complete:
                value = stack.pop()
                if isinstance(value, dict):
                    stack.extend(value.values())
                elif isinstance(value, list):
                    stack.extend(value)
                elif value is not None:
                    text = str(value)
                    for form in (text, json.dumps(value, ensure_ascii=True)[1:-1]
                                 if isinstance(value, str) else text,
                                 repr(value)[1:-1] if isinstance(value, str) else text):
                        if form and form not in self._values:
                            self._value_bytes += len(form.encode("utf-8"))
                            if self._value_bytes > MAX_REDACTION_BYTES:
                                self._complete = False
                                self._values.clear()
                                break
                            self._values.add(form)

    def _message(self, error):
        kind = type(error).__name__
        if not self._complete or not self._has_config:
            return f"{kind}: diagnostic omitted because redaction inputs are unavailable"
        text = str(error)
        if len(text) > MAX_REDACTION_BYTES:
            return f"{kind}: diagnostic omitted because it exceeds the report limit"
        if self._values:
            # One substitution pass prevents rewriting the redaction marker.
            pattern = "|".join(re.escape(v) for v in sorted(self._values, key=len, reverse=True))
            text = re.sub(pattern, "[redacted]", text)
        return f"{kind}: {text[:MAX_MESSAGE]}"

    def publish(self, error):
        """Atomically publish a complete report; leave failed attempts reserved."""
        code = _exit_code(error, self.failure_exit_code, self.interrupt_exit_code)
        errors = [
            {"name": name, "message": self._message(exc)}
            for name, exc in self.errors
        ]
        if error is not None and code and not errors:
            errors.append({"name": "command", "message": self._message(error)})
        if self._truncated:
            errors.append({"name": "report_limits", "message": "Stage/error observations were truncated"})
        report = {
            "sonic_upgrade_summary": {
                "script_name": self.script_name,
                "sonic_upgrade_package_version": _package_version(),
                "fault_code": str(code),
                "fault_reason": (
                    f'{errors[0]["name"]}: {errors[0]["message"]}' if code and errors else
                    "GCU command completed; service readiness and persistence are not verified"
                ),
                "guid": self.guid,
            },
            "sonic_upgrade_actions": {
                "reputation_impact": False,
                "retriable": False,
                "isolate_on_failure": False,
                "auto_triage": {
                    "status": False,
                    "triage_queue": "",
                    "triage_action": "",
                },
            },
            "sonic_upgrade_report": {
                "duration": f"{time.monotonic() - self.started:.6f}",
                "stages": self.stages,
                "health_checks": [],
                "errors": errors,
            },
        }
        with self.pending.open("w", encoding="utf-8") as output:
            json.dump(report, output, ensure_ascii=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(self.pending, self.path)


@contextmanager
def report_session(report_id=None, phase="apply", failure_exit_code=1, interrupt_exit_code=130):
    """Report one invocation, preserving an original execution exception."""
    if report_id is None:
        yield
        return
    report = ErrorReport(report_id, phase, failure_exit_code, interrupt_exit_code)
    token = _report.set(report)
    error = None
    try:
        yield
    except BaseException as exc:
        error = exc
        raise
    finally:
        _report.reset(token)
        try:
            report.publish(error)
        except Exception as exc:
            if error is None:
                raise RuntimeError(
                    "GCU completed but its report could not be published; "
                    "reconcile configuration before any retry"
                ) from exc
            try:
                print("Error: GCU report publication failed; original command failure retained", file=sys.stderr)
            except Exception:
                # A broken diagnostic stream must not replace the operation's exception.
                pass


@contextmanager
def scope(name):
    """Attribute observations to an ASIC or change without sharing thread state."""
    parent = _scope.get()
    token = _scope.set(f"{parent}.{name}" if parent else name)
    try:
        yield
    finally:
        _scope.reset(token)


@contextmanager
def stage(name):
    """Observe an existing stage; never suppress or translate its exception."""
    report = _report.get()
    if report is None:
        yield
        return
    prefix = _scope.get()
    name = f"{prefix}.{name}" if prefix else name
    entry = {"name": name, "rc": "0"}
    with report._lock:
        if len(report.stages) < MAX_STAGES:
            report.stages.append(entry)
        else:
            report._truncated = True
    try:
        yield
    except BaseException as exc:
        entry["rc"] = str(_exit_code(exc, report.failure_exit_code, report.interrupt_exit_code))
        with report._lock:
            if len(report.errors) < MAX_ERRORS:
                report.errors.append((name, exc))
            else:
                report._truncated = True
        raise


def remember_config(config):
    """Redact values from the actual snapshot, without fetching another one."""
    report = _report.get()
    if report is not None:
        report.remember(json.loads(config) if isinstance(config, str) else config, config=True)


def remember_patch(patch):
    """Redact incoming values while retaining useful patch-path diagnostics."""
    report = _report.get()
    if report is not None:
        if isinstance(patch, list):
            for change in patch:
                report.remember(change.get("value") if isinstance(change, dict) else change)
        else:
            report.remember(patch)

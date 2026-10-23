"""Core helpers for installing and managing SONiC Hotfix packages."""

import contextlib
import fcntl
import hashlib
import importlib.util
import os
import re
import shutil
import subprocess  # nosec B404 - all calls use argv with shell=False
import sys
import tarfile
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml


DEFAULT_VERSION_FILE = Path("/etc/sonic/sonic_version.yml")
DEFAULT_PATCH_ROOT = Path("/usr/share/sonic/patches")
DEFAULT_HOTPATCH_ROOT = Path("/usr/share/sonic/hotpatches")
DEFAULT_OPERATION_LOG = Path("/var/log/patch_operation.rec")
DEFAULT_LOCK_FILE = Path("/run/lock/sonic-installer-patch.lock")
PATCH_METADATA_FILE = "metadata.yml"
PATCH_SUMMARY_FILE = "summary.yml"


class PatchError(Exception):
    """Raised when a Hotfix package is invalid or cannot be processed."""


def md5sum(path):
    """Return the hexadecimal MD5 checksum of *path*."""
    try:
        digest = hashlib.md5(usedforsecurity=False)  # nosec B303
    except TypeError:
        digest = hashlib.md5()  # nosec B303 - Hotfix format requires MD5
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _version_key(value):
    """Create a deterministic comparison key for SONiC version strings."""
    return tuple(
        (0, int(token)) if token.isdigit() else (1, token.lower())
        for token in re.findall(r"\d+|[^\d]+", value.strip())
    )


def version_matches(current, constraint):
    """Return whether *current* satisfies a simple version constraint."""
    match = re.fullmatch(r"\s*(>=|<=|>|<|==|=)?\s*(\S+)\s*", constraint or "")
    if not match:
        raise PatchError("Invalid version constraint: {}".format(constraint))

    operator = match.group(1) or "="
    expected = match.group(2)
    current_key = _version_key(current)
    expected_key = _version_key(expected)
    operations = {
        "=": lambda: current_key == expected_key,
        "==": lambda: current_key == expected_key,
        ">=": lambda: current_key >= expected_key,
        ">": lambda: current_key > expected_key,
        "<=": lambda: current_key <= expected_key,
        "<": lambda: current_key < expected_key,
    }
    return operations[operator]()


def safe_extract(archive, destination):
    """Extract a tar archive without allowing path or link traversal."""
    archive = Path(archive)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    destination_real = destination.resolve()

    try:
        package = tarfile.open(str(archive), mode="r:*")
    except (OSError, tarfile.TarError) as error:
        raise PatchError(
            "Cannot open patch archive {}: {}".format(archive, error))

    with package:
        for member in package.getmembers():
            member_path = (destination / member.name).resolve()
            try:
                common = os.path.commonpath(
                    (str(destination_real), str(member_path)))
            except ValueError:
                common = ""
            if common != str(destination_real):
                raise PatchError(
                    "Unsafe path in patch archive: {}".format(member.name))
            if member.issym() or member.islnk():
                raise PatchError(
                    "Links are not allowed in patch archives: {}".format(
                        member.name))
            if not member.isfile() and not member.isdir():
                raise PatchError(
                    "Special files are not allowed in patch archives: "
                    "{}".format(member.name))
        for member in package.getmembers():
            member_path = destination / member.name
            if member.isdir():
                member_path.mkdir(parents=True, exist_ok=True)
                member_path.chmod(member.mode & 0o777)
                continue
            member_path.parent.mkdir(parents=True, exist_ok=True)
            source = package.extractfile(member)
            if source is None:
                raise PatchError(
                    "Cannot read archive member: {}".format(member.name))
            with source, open(member_path, "wb") as output:
                shutil.copyfileobj(source, output)
            member_path.chmod(member.mode & 0o777)


@contextlib.contextmanager
def _working_directory(path):
    old_directory = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(old_directory)


def load_patch_plugin(patch_directory):
    """Load and validate the install.py plugin from a sub-patch directory."""
    patch_directory = Path(patch_directory)
    install_path = patch_directory / "install.py"
    if not install_path.is_file():
        raise PatchError("Patch plugin is missing: {}".format(install_path))

    module_name = "sonic_hotpatch_{}".format(uuid.uuid4().hex)
    spec = importlib.util.spec_from_file_location(
        module_name, str(install_path))
    if spec is None or spec.loader is None:
        raise PatchError("Cannot load patch plugin: {}".format(install_path))

    module = importlib.util.module_from_spec(spec)
    try:
        with _working_directory(patch_directory):
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
    except Exception as error:
        raise PatchError(
            "Cannot load patch plugin {}: {}".format(install_path, error))
    finally:
        sys.modules.pop(module_name, None)

    required = (
        "SUCCESS",
        "FAIL",
        "get_patch_name",
        "get_patch_desc",
        "do_patch_install",
        "do_patch_uninstall",
    )
    for name in required:
        if not hasattr(module, name):
            raise PatchError(
                "Patch plugin is missing required export: {}".format(name))
    for name in required[2:]:
        if not callable(getattr(module, name)):
            raise PatchError(
                "Patch plugin export must be callable: {}".format(name))
    return module


def _validate_name(value, description):
    if not isinstance(value, str) or not value or value in (".", ".."):
        raise PatchError("Invalid {}: {}".format(description, value))
    if Path(value).name != value or "/" in value or "\\" in value:
        raise PatchError("Invalid {}: {}".format(description, value))
    return value


def _read_yaml(path):
    try:
        with open(path, "r", encoding="utf-8") as stream:
            value = yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as error:
        raise PatchError("Cannot read YAML file {}: {}".format(path, error))
    if not isinstance(value, dict):
        raise PatchError("YAML file must contain a mapping: {}".format(path))
    return value


def _atomic_write_yaml(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".{}-".format(path.name), dir=str(path.parent))
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            yaml.safe_dump(
                value, stream, default_flow_style=False, sort_keys=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, str(path))
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def _archive_root(extract_directory):
    candidates = sorted(
        path.parent for path in Path(extract_directory).rglob("install.py")
        if path.is_file()
    )
    if len(candidates) != 1:
        raise PatchError("A sub-patch must contain exactly one install.py")
    return candidates[0]


def _plugin_result(plugin, method):
    result = method()
    if not isinstance(result, tuple) or len(result) != 2:
        raise PatchError("Patch plugin returned an invalid result")
    status, output = result
    return status, output or ""


class PatchManager:
    """Install, reapply, and remove SONiC Hotfix sub-patches."""

    def __init__(self, version_file=DEFAULT_VERSION_FILE,
                 patch_root=DEFAULT_PATCH_ROOT,
                 hotpatch_root=DEFAULT_HOTPATCH_ROOT,
                 operation_log=DEFAULT_OPERATION_LOG,
                 lock_file=DEFAULT_LOCK_FILE, user=None, runner=None):
        self.version_file = Path(version_file)
        self.patch_root = Path(patch_root)
        self.hotpatch_root = Path(hotpatch_root)
        self.operation_log = Path(operation_log)
        self.lock_file = Path(lock_file)
        self.user = user or os.environ.get(
            "SUDO_USER") or os.environ.get("USER") or "unknown"
        self.runner = runner or subprocess.run

    @contextlib.contextmanager
    def _lock(self):
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.lock_file, "a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _state(self):
        state = _read_yaml(self.version_file)
        if not isinstance(state.get("patches", []), list):
            raise PatchError(
                "Invalid patches field in {}".format(self.version_file))
        return state

    def _save_state(self, state):
        _atomic_write_yaml(self.version_file, state)

    def _record(self, message):
        try:
            self.operation_log.parent.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(
                timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            with open(self.operation_log, "a", encoding="utf-8") as stream:
                stream.write(
                    "{} {}: {}\n".format(timestamp, self.user, message))
        except OSError:
            # Failure to write an audit record must not corrupt patch state.
            return

    @contextlib.contextmanager
    def _summary(self, source):
        source = Path(source)
        if not source.is_file():
            raise PatchError("Patch file does not exist: {}".format(source))
        if source.suffix in (".yml", ".yaml"):
            yield source, source.parent, None
            return
        with tempfile.TemporaryDirectory(prefix="sonic-hotfix-") as directory:
            safe_extract(source, directory)
            summary = Path(directory) / PATCH_SUMMARY_FILE
            if not summary.is_file():
                raise PatchError("Hotfix archive does not contain summary.yml")
            yield summary, Path(directory), source

    def _precheck_summary(self, summary_file, directory):
        summary = _read_yaml(summary_file)
        target_version = summary.get("os_version")
        current_version = self._state().get("build_version")
        if not target_version:
            raise PatchError("summary.yml is missing os_version")
        if not current_version:
            raise PatchError(
                "{} is missing build_version".format(self.version_file))
        if not version_matches(str(current_version), str(target_version)):
            raise PatchError(
                "Patch targets {}, current SONiC version is {}".format(
                    target_version, current_version
                )
            )

        patch_entries = summary.get("patches", [])
        if not isinstance(patch_entries, list):
            raise PatchError("summary.yml patches must be a list")
        installed_names = {item.get("name")
                           for item in self._state().get("patches", [])}
        installed = []
        to_install = []
        for entry in patch_entries:
            if not isinstance(entry, dict) or not entry.get(
                    "name") or not entry.get("md5sum"):
                raise PatchError("Each patch entry requires name and md5sum")
            name = _validate_name(entry["name"], "patch archive name")
            archive = directory / name
            if not archive.is_file():
                raise PatchError("Patch archive is missing: {}".format(name))
            if md5sum(archive) != str(entry["md5sum"]):
                raise PatchError(
                    "Patch archive checksum mismatch: {}".format(name))
            if name in installed_names:
                installed.append(entry)
            else:
                to_install.append(entry)
        return summary, installed, to_install

    def precheck(self, source):
        with self._summary(source) as (summary_file, directory, _):
            summary, installed, to_install = self._precheck_summary(
                summary_file, directory)
            return {
                "os_version": summary["os_version"],
                "installed": [entry["name"] for entry in installed],
                "to_install": [entry["name"] for entry in to_install],
            }

    def _execute_plugin(self, plugin, patch_directory, method_name):
        with _working_directory(patch_directory):
            status, output = _plugin_result(
                plugin, getattr(plugin, method_name))
        if status != plugin.SUCCESS:
            raise PatchError(
                "Failed to {} patch: {}".format(
                    (
                        "install"
                        if method_name == "do_patch_install"
                        else "uninstall"
                    ),
                    output,
                ))
        return output

    def _install_subpatch(self, archive, summary_file, installed_by_file):
        archive = Path(archive)
        with tempfile.TemporaryDirectory(
                prefix="sonic-sub-hotfix-") as directory:
            safe_extract(archive, directory)
            patch_directory = _archive_root(directory)
            plugin = load_patch_plugin(patch_directory)
            patch_name = _validate_name(
                str(plugin.get_patch_name()), "patch name")
            patch_desc = str(plugin.get_patch_desc())
            patch_type = str(plugin.get_patch_type()) if hasattr(
                plugin, "get_patch_type") else "normal"
            patch_extern_name = (
                str(plugin.get_patch_extern_name())
                if (
                    hasattr(plugin, "get_patch_extern_name")
                    and plugin.get_patch_extern_name()
                )
                else patch_name
            )
            if patch_name in {
                item.get("name") for item in self._state().get(
                    "patches",
                    [])}:
                return None

            try:
                self._execute_plugin(
                    plugin, patch_directory, "do_patch_install")
                destination = self.patch_root / patch_name
                if destination.exists():
                    raise PatchError(
                        "Patch storage already exists: {}".format(destination))
                self.patch_root.mkdir(parents=True, exist_ok=True)
                shutil.copytree(str(patch_directory), str(destination))
                shutil.copy2(str(summary_file), str(
                    destination / PATCH_SUMMARY_FILE))

                archive_name = None
                if patch_type.lower() == "hotpatch":
                    self.hotpatch_root.mkdir(parents=True, exist_ok=True)
                    archive_name = archive.name
                    shutil.copy2(str(archive), str(
                        self.hotpatch_root / archive_name))

                metadata = {
                    "installed_time": datetime.now(
                        timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                    "installed_by_user": self.user,
                    "patch_type": patch_type,
                    "archive_name": archive_name,
                    "summary_file": Path(summary_file).name,
                    "installed_by_file": (
                        Path(installed_by_file).name
                        if installed_by_file
                        else None
                    ),
                }
                _atomic_write_yaml(destination / PATCH_METADATA_FILE, metadata)

                state = self._state()
                patches = state.setdefault("patches", [])
                patches.append({
                    "name": patch_name,
                    "desc": patch_desc,
                    "extern_name": patch_extern_name,
                })
                self._save_state(state)
                self._record("Installed patch {} ({})".format(
                    patch_name, patch_desc))
                return patch_name
            except Exception:
                try:
                    with _working_directory(patch_directory):
                        _plugin_result(plugin, plugin.do_patch_uninstall)
                except Exception as rollback_error:
                    self._record(
                        "Failed to roll back {}: {}".format(
                            patch_name, rollback_error))
                shutil.rmtree(str(self.patch_root / patch_name),
                              ignore_errors=True)
                if patch_type.lower() == "hotpatch":
                    try:
                        (self.hotpatch_root / archive.name).unlink()
                    except OSError:
                        pass
                raise

    def install(self, source):
        installed_now = []
        with self._lock():
            with self._summary(source) as (
                    summary_file, directory, source_archive):
                _, _, to_install = self._precheck_summary(
                    summary_file, directory)
                try:
                    for entry in to_install:
                        patch_name = self._install_subpatch(
                            directory /
                            entry["name"], summary_file, source_archive
                        )
                        if patch_name:
                            installed_now.append(patch_name)
                except Exception:
                    for patch_name in reversed(installed_now):
                        try:
                            self._uninstall_one(
                                patch_name, require_latest=True)
                        except Exception as rollback_error:
                            self._record(
                                "Failed to roll back {}: {}".format(
                                    patch_name, rollback_error))
                    self._record(
                        "Failed to install patches from {}".format(source))
                    raise
        return installed_now

    def reapply_hotpatch(self, archive):
        archive = Path(archive)
        with self._lock():
            with tempfile.TemporaryDirectory(
                    prefix="sonic-sub-hotfix-") as directory:
                safe_extract(archive, directory)
                patch_directory = _archive_root(directory)
                plugin = load_patch_plugin(patch_directory)
                patch_name = _validate_name(
                    str(plugin.get_patch_name()), "patch name")
                patch_type = str(plugin.get_patch_type()) if hasattr(
                    plugin, "get_patch_type") else "normal"
                if patch_type.lower() != "hotpatch":
                    raise PatchError(
                        "Patch archive is not a function hotpatch: {}".format(
                            archive))
                if patch_name not in {
                    item.get("name") for item in self._state().get(
                        "patches",
                        [])}:
                    raise PatchError(
                        "Patch is not installed: {}".format(patch_name))
                self._execute_plugin(
                    plugin, patch_directory, "do_patch_install")
                metadata_path = (
                    self.patch_root / patch_name / PATCH_METADATA_FILE)
                metadata = _read_yaml(metadata_path)
                metadata["reapplied_time"] = datetime.now(
                    timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                _atomic_write_yaml(metadata_path, metadata)
                self._record("Reapplied hotpatch {}".format(patch_name))

    def _uninstall_one(self, patch_name, require_latest=True):
        state = self._state()
        patches = state.get("patches", [])
        names = [item.get("name") for item in patches]
        if patch_name not in names:
            raise PatchError("Patch is not installed: {}".format(patch_name))
        if require_latest and names[-1] != patch_name:
            raise PatchError(
                "Patch is not the latest installed patch: {}".format(
                    patch_name))

        patch_directory = self.patch_root / patch_name
        plugin = load_patch_plugin(patch_directory)
        self._execute_plugin(plugin, patch_directory, "do_patch_uninstall")
        metadata_path = patch_directory / PATCH_METADATA_FILE
        metadata = _read_yaml(metadata_path) if metadata_path.exists() else {}
        archive_name = metadata.get("archive_name")
        if archive_name:
            try:
                (self.hotpatch_root / archive_name).unlink()
            except FileNotFoundError:
                pass
        shutil.rmtree(str(patch_directory))
        state["patches"] = [
            item for item in patches if item.get("name") != patch_name]
        if not state["patches"]:
            state.pop("patches")
        self._save_state(state)
        self._record("Uninstalled patch {}".format(patch_name))

    def uninstall(self, patch_name, single=False):
        """Uninstall one patch or a trailing group installed by one Hotfix."""
        with self._lock():
            if single:
                self._uninstall_one(patch_name, require_latest=True)
                return [patch_name]

            state = self._state()
            names = [item.get("name") for item in state.get("patches", [])]
            grouped = []
            requested = Path(patch_name).name
            for name in reversed(names):
                metadata_path = self.patch_root / name / PATCH_METADATA_FILE
                metadata = _read_yaml(
                    metadata_path) if metadata_path.exists() else {}
                installed_by_file = metadata.get("installed_by_file")
                summary_file = metadata.get("summary_file")
                if installed_by_file == requested or summary_file == requested:
                    grouped.append(name)
                elif grouped:
                    break

            if not grouped:
                if patch_name not in names:
                    raise PatchError(
                        "No installed patches match: {}".format(patch_name))
                grouped = list(reversed(names[names.index(patch_name):]))

            for name in grouped:
                self._uninstall_one(name, require_latest=True)
            return grouped

    def list_patches(self):
        state = self._state()
        result = []
        for entry in state.get("patches", []):
            item = dict(entry)
            metadata_path = self.patch_root / \
                entry["name"] / PATCH_METADATA_FILE
            if metadata_path.exists():
                item["metadata"] = _read_yaml(metadata_path)
            result.append(item)
        return result

    def _live_status(self):
        live = []
        for patch in self.list_patches():
            metadata = patch.get("metadata", {})
            if str(metadata.get("patch_type", "")).lower() != "hotpatch":
                continue
            patch_info_path = self.patch_root / \
                patch["name"] / "patch_info.yml"
            if not patch_info_path.is_file():
                continue
            patch_info = _read_yaml(patch_info_path)
            for package in patch_info.get("Packages", []):
                if str(package.get("Type", "")).lower() != "func_hotpatch":
                    continue
                process = str(package.get("ProcessName", ""))
                patch_id = str(package.get("PatchId", "")).zfill(4)
                item = {
                    "patch": patch["name"],
                    "process": process,
                    "patch_id": patch_id,
                    "pids": [],
                    "active": False,
                }
                if not process:
                    live.append(item)
                    continue
                pid_result = self.runner(
                    ["pidof", process],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                if pid_result.returncode == 0:
                    for pid in pid_result.stdout.split():
                        info_result = self.runner(
                            ["libcare-ctl", "info", "-p", pid],
                            text=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                        )
                        info = (
                            info_result.stdout
                            if info_result.returncode == 0
                            else ""
                        )
                        active = bool(re.search(
                            r"Patch id:\s*{}(?:\s|$)".format(
                                re.escape(patch_id)),
                            info,
                        ))
                        item["pids"].append(
                            {"pid": pid, "active": active, "info": info})
                        item["active"] = item["active"] or active
                live.append(item)
        return live

    def _pending_status(self):
        pending = []
        for patch in self.list_patches():
            patch_info_path = self.patch_root / \
                patch["name"] / "patch_info.yml"
            if not patch_info_path.is_file():
                continue
            patch_info = _read_yaml(patch_info_path)
            marker = Path(
                "/tmp/.{}.flag".format(  # nosec B108 - plugin contract
                    patch_info.get("Patch name", patch["name"])))
            if not marker.exists():
                continue
            for package in patch_info.get("Packages", []):
                if package.get("RestartForActive") is True:
                    package_name = package.get("Name") or Path(
                        package.get("Package", "")).name
                    pending.append({
                        "patch": patch["name"],
                        "package": package_name,
                    })
        return pending

    def status(self, section=None):
        """Return operation, live-patch, and pending-activation status."""
        operations = []
        if self.operation_log.exists():
            operations = self.operation_log.read_text(
                encoding="utf-8").splitlines()
        status = {
            "operation": operations,
            "live": self._live_status(),
            "pending": self._pending_status(),
        }
        if section:
            if section not in status:
                raise PatchError("Unknown status section: {}".format(section))
            return {section: status[section]}
        return status

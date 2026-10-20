import fcntl
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from sonic_installer import secure_boot_lock as lock


@pytest.fixture(autouse=True)
def lock_file(tmp_path, monkeypatch):
    path = tmp_path / "installer.lock"
    monkeypatch.setattr(lock, "LOCK_FILE", path)
    monkeypatch.delenv(lock.LOCK_FD_ENV, raising=False)
    return path


def test_nested_calls_keep_the_same_exclusive_lock(lock_file):
    @lock.locked
    def nested():
        return lock.current_lock_fd()

    with lock.installer_lock() as fd:
        assert nested() == fd
        with lock_file.open("a") as contender:
            with pytest.raises(BlockingIOError):
                fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
    assert lock.current_lock_fd() is None
    with lock_file.open("a") as contender:
        fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)


@pytest.mark.parametrize("error", [RuntimeError("failed"), KeyboardInterrupt(), SystemExit(143)])
def test_errors_release_the_lock_without_unlinking_it(lock_file, error):
    with pytest.raises(type(error)):
        with lock.installer_lock():
            inode = lock_file.stat().st_ino
            raise error
    assert lock.current_lock_fd() is None
    assert lock_file.stat().st_ino == inode
    with lock_file.open("a") as contender:
        fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_other_process_waits_then_acquires_the_lock(lock_file):
    script = """
import sys
from pathlib import Path
from sonic_installer import secure_boot_lock as lock
lock.LOCK_FILE = Path(sys.argv[1])
print("ready", flush=True)
with lock.installer_lock():
    print("acquired", flush=True)
"""
    process = None
    try:
        with lock.installer_lock():
            process = subprocess.Popen(
                [sys.executable, "-c", script, str(lock_file)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            assert process.stdout.readline().strip() == "ready"
            with pytest.raises(subprocess.TimeoutExpired):
                process.communicate(timeout=0.2)
        out, err = process.communicate(timeout=10)
        assert process.returncode == 0, err
        assert out.strip() == "acquired"
        assert "Waiting for another" in err
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            process.communicate(timeout=10)


def test_other_thread_does_not_bypass_the_lock():
    started, acquired = threading.Event(), threading.Event()

    def contender():
        started.set()
        with lock.installer_lock():
            acquired.set()

    with lock.installer_lock():
        thread = threading.Thread(target=contender)
        thread.start()
        assert started.wait(timeout=5)
        assert not acquired.wait(timeout=0.2)
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert acquired.is_set()


def test_synchronous_installer_child_can_reuse_lock_without_releasing_parent(lock_file):
    script = """
import os
import sys
from pathlib import Path
from sonic_installer import secure_boot_lock as lock
lock.LOCK_FILE = Path(sys.argv[1])
with lock.installer_lock():
    inherited = int(os.environ[lock.LOCK_FD_ENV])
    pid = os.fork()
    if pid == 0:
        assert lock.current_lock_fd() is None
        assert lock.LOCK_FD_ENV not in os.environ
        try:
            os.fstat(inherited)
        except OSError:
            os._exit(0)
        os._exit(1)
    _, status = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(status) == 0
    print("acquired")
"""
    with lock.installer_lock():
        result = subprocess.run(
            ["bash", "-c", 'exec "$@"', "--", sys.executable, "-c", script, str(lock_file)],
            capture_output=True, text=True, timeout=10, **lock.subprocess_lock_options(),
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "acquired"
        with lock_file.open("a") as contender:
            with pytest.raises(BlockingIOError):
                fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)


@pytest.mark.parametrize("value", ["not-a-descriptor", "-1", "999999999999999999999999999999"])
def test_invalid_inherited_descriptor_is_rejected(monkeypatch, value):
    monkeypatch.setenv(lock.LOCK_FD_ENV, value)
    with pytest.raises(OSError, match="invalid inherited installer lock descriptor"):
        with lock.installer_lock():
            pytest.fail("invalid ownership must not bypass locking")


def test_inherited_descriptor_must_reference_shared_lock(tmp_path, lock_file, monkeypatch):
    lock_file.touch()
    with (tmp_path / "wrong-lock").open("a") as other:
        monkeypatch.setenv(lock.LOCK_FD_ENV, str(other.fileno()))
        with pytest.raises(OSError, match="invalid inherited installer lock descriptor"):
            with lock.installer_lock():
                pytest.fail("a different file must not bypass locking")


@pytest.fixture
def enrollment_script(tmp_path, lock_file):
    source = Path(__file__).resolve().parents[1] / "scripts" / "secure_boot_enroll_db.sh"
    script = tmp_path / "enroll.sh"
    script.write_text(source.read_text().replace(
        "LOCK_FILE=/run/lock/sonic-installer.lock", f"LOCK_FILE={lock_file}",
    ).replace('EFIVARS_DIR="/sys/firmware/efi/efivars"', f'EFIVARS_DIR="{tmp_path}/missing-efivars"'))
    image = tmp_path / "sonic.bin"
    image.touch()
    return ["bash", str(script), str(image)]


def test_shell_enrollment_reuses_inherited_lock(enrollment_script, lock_file):
    with lock.installer_lock():
        result = subprocess.run(
            enrollment_script, capture_output=True, text=True, timeout=10, **lock.subprocess_lock_options(),
        )
        assert result.returncode == 1
        assert "efivars not available" in result.stdout
        with lock_file.open("a") as contender:
            with pytest.raises(BlockingIOError):
                fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_standalone_shell_enrollment_waits_for_installer(enrollment_script):
    process = None
    try:
        with lock.installer_lock():
            process = subprocess.Popen(enrollment_script, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            with pytest.raises(subprocess.TimeoutExpired):
                process.communicate(timeout=0.2)
        out, err = process.communicate(timeout=10)
        assert process.returncode == 1, err
        assert "efivars not available" in out
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            process.communicate(timeout=10)


def test_shell_enrollment_rejects_wrong_inherited_descriptor(enrollment_script, tmp_path):
    with (tmp_path / "wrong-lock").open("a") as other:
        result = subprocess.run(
            enrollment_script, capture_output=True, text=True, timeout=10, pass_fds=(other.fileno(),),
            env=dict(os.environ, **{lock.LOCK_FD_ENV: str(other.fileno())}),
        )
    assert result.returncode == 1
    assert "invalid inherited installer lock descriptor" in result.stdout


def test_forked_child_cannot_reuse_parent_ownership(lock_file):
    with lock.installer_lock():
        pid = os.fork()
        if pid == 0:
            if lock.current_lock_fd() is not None:
                os._exit(1)
            with lock_file.open("a") as contender:
                try:
                    fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    os._exit(0)
            os._exit(1)
        _, status = os.waitpid(pid, 0)
        assert os.waitstatus_to_exitcode(status) == 0


def test_cannot_open_lock_fails_before_running_operation(tmp_path, monkeypatch):
    monkeypatch.setattr(lock, "LOCK_FILE", tmp_path / "missing" / "installer.lock")

    @lock.locked
    def operation():
        pytest.fail("operation must not run without the lock")

    with pytest.raises(FileNotFoundError):
        operation()
    assert lock.current_lock_fd() is None


def test_lock_file_symlink_is_rejected(tmp_path, lock_file):
    target = tmp_path / "other-file"
    target.write_text("unchanged")
    lock_file.symlink_to(target)
    with pytest.raises(OSError):
        with lock.installer_lock():
            pytest.fail("must not follow a lock-file symlink")
    assert target.read_text() == "unchanged"

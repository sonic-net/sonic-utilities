"""Serialize image installation and Secure Boot updates across processes."""

import fcntl
import os
import sys
import threading
from contextlib import contextmanager
from functools import wraps
from pathlib import Path

LOCK_FILE = Path("/run/lock/sonic-installer.lock")
LOCK_FD_ENV = "SONIC_INSTALLER_LOCK_FD"
_state = threading.local()
_active_fds = set()
_inherited_fds = set()
_thread_lock = threading.RLock()


def _reset_after_fork():
    global _thread_lock
    # A child must not inherit ownership or keep its parent's lock alive.
    for fd in _active_fds | _inherited_fds:
        os.close(fd)
    _active_fds.clear()
    _inherited_fds.clear()
    os.environ.pop(LOCK_FD_ENV, None)
    _state.fd = None
    _thread_lock = threading.RLock()


os.register_at_fork(after_in_child=_reset_after_fork)


def current_lock_fd():
    """Return this thread's held lock descriptor, or None."""
    return getattr(_state, "fd", None)


def subprocess_lock_options(env=None):
    """Pass lock ownership only to synchronous installer/enrollment children."""
    fd = current_lock_fd()
    if fd is None:
        return {}
    return {
        "pass_fds": (fd,),
        "env": dict(os.environ if env is None else env, **{LOCK_FD_ENV: str(fd)}),
    }


def _open_lock():
    inherited = os.environ.get(LOCK_FD_ENV)
    if inherited is None:
        return os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fd = int(inherited)
        if not os.path.samestat(os.fstat(fd), os.stat(LOCK_FILE, follow_symlinks=False)):
            raise OSError("descriptor does not refer to the shared lock file")
        duplicate = os.dup(fd)
        _inherited_fds.add(fd)
        return duplicate
    except (OSError, ValueError, OverflowError) as e:
        raise OSError(f"invalid inherited installer lock descriptor: {inherited}") from e


@contextmanager
def installer_lock():
    """Hold the shared lock, allowing nested calls in the owning thread."""
    with _thread_lock:
        inherited = current_lock_fd()
        if inherited is not None:
            yield inherited
            return

        fd = _open_lock()
        _active_fds.add(fd)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print("Waiting for another image installation or Secure Boot update to finish...", file=sys.stderr)
                fcntl.flock(fd, fcntl.LOCK_EX)
            _state.fd = fd
            try:
                yield fd
            finally:
                _state.fd = None
        finally:
            _active_fds.remove(fd)
            os.close(fd)


def locked(function):
    """Run an operation under the shared installer/Secure Boot lock."""
    @wraps(function)
    def wrapper(*args, **kwargs):
        with installer_lock():
            return function(*args, **kwargs)
    return wrapper

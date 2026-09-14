"""File lock utilities."""
import click
import fcntl
import functools
import inspect
import os
import sys
import time

from sonic_py_common import logger


log = logger.Logger()


def acquire_flock(fd, timeout=-1):
    """Acquire the flock."""
    flags = fcntl.LOCK_EX
    if timeout >= 0:
        flags |= fcntl.LOCK_NB
    else:
        timeout = 0

    start_time = current_time = time.time()
    ret = False
    while current_time - start_time <= timeout:
        try:
            fcntl.flock(fd, flags)
        except (IOError, OSError):
            ret = False
        else:
            ret = True
            break
        current_time = time.time()
        if timeout != 0:
            time.sleep(0.2)
    return ret


def release_flock(fd):
    """Release the flock."""
    fcntl.flock(fd, fcntl.LOCK_UN)


class FileLock(object):
    """An flock held across part of a command.

    try_lock() wraps a whole function, which is enough when the lock should
    cover a whole command. This form scopes the lock to a block instead, so a
    command can do its read-only and interactive work without holding it and
    take it only for the phase that writes.

    As with try_lock(), this is best-effort coordination between participating
    writers, not exclusion of every CONFIG_DB or ASIC_DB writer.

    Unlike try_lock(), taking and releasing is silent: a command scoping the
    lock to a block may take it more than once, and announcing each one buries
    the output the operator is actually reading. Failing to acquire is still
    reported, since that is why the command stopped.
    """

    def __init__(self, lock_file, owner, timeout=0):
        self.lock_file = lock_file
        self.owner = owner
        self.timeout = timeout
        self.fd = None

    def _record_owner(self):
        os.truncate(self.fd, 0)
        os.pwrite(self.fd, f"{self.owner}, pid {os.getpid()}\n".encode(), 0)

    def _acquire(self):
        if acquire_flock(self.fd, self.timeout):
            self._record_owner()
            return True

        click.echo(f"Failed to acquire lock on {self.lock_file}")
        lock_owner = os.pread(self.fd, 1024, 0).decode() or "unknown"
        log.log_notice(
            (f"{self.owner} failed to acquire lock on {self.lock_file},"
             f" which is taken by {lock_owner}")
        )
        return False

    def _close(self):
        os.close(self.fd)
        self.fd = None

    def __enter__(self):
        self.fd = os.open(self.lock_file, os.O_CREAT | os.O_RDWR)
        if not self._acquire():
            self._close()
            sys.exit(1)
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        if self.fd is None:
            return False
        release_flock(self.fd)
        os.truncate(self.fd, 0)
        self._close()
        return False


def try_lock(lock_file, timeout=-1):
    """Decorator to try lock file using fcntl.flock."""
    def _decorator(func):
        @functools.wraps(func)
        def _wrapper(*args, **kwargs):
            bypass_lock = False

            # Get the bypass_lock argument from the function signature
            func_signature = inspect.signature(func)
            has_bypass_lock = "bypass_lock" in func_signature.parameters
            if has_bypass_lock:
                func_ba = func_signature.bind(*args, **kwargs)
                func_ba.apply_defaults()
                bypass_lock = func_ba.arguments["bypass_lock"]

            if bypass_lock:
                click.echo(f"Bypass lock on {lock_file}")
                return func(*args, **kwargs)
            else:
                fd = os.open(lock_file, os.O_CREAT | os.O_RDWR)
                if acquire_flock(fd, timeout):
                    click.echo(f"Acquired lock on {lock_file}")
                    os.truncate(fd, 0)
                    # Write pid and the function name to the lock file as a record
                    os.write(fd, f"{func.__name__}, pid {os.getpid()}\n".encode())
                    try:
                        return func(*args, **kwargs)
                    finally:
                        release_flock(fd)
                        click.echo(f"Released lock on {lock_file}")
                        os.truncate(fd, 0)
                        os.close(fd)
                else:
                    click.echo(f"Failed to acquire lock on {lock_file}")
                    lock_owner = os.read(fd, 1024).decode()
                    if not lock_owner:
                        lock_owner = "unknown"
                    log.log_notice(
                        (f"{func.__name__} failed to acquire lock on {lock_file},"
                         f" which is taken by {lock_owner}")
                    )
                    os.close(fd)
                    sys.exit(1)
        return _wrapper
    return _decorator

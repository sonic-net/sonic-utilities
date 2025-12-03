import pytest
import tempfile
import threading
import time

from unittest import mock
from utilities_common import flock


f0_exit = threading.Event()
f1_exit = threading.Event()
f2_exit = threading.Event()


def dummy_f0():
    while not f0_exit.is_set():
        time.sleep(1)


def dummy_f1(bypass_lock=False):
    while not f1_exit.is_set():
        time.sleep(1)


def dummy_f2(bypass_lock=True):
    while not f2_exit.is_set():
        time.sleep(1)


class TestFLock:
    def setup(self):
        print("SETUP")
        f0_exit.clear()
        f1_exit.clear()
        f2_exit.clear()

    def test_flock_acquire_lock_non_blocking(self):
        """Test flock non-blocking acquire lock."""
        with tempfile.NamedTemporaryFile() as fd0:
            fd1 = open(fd0.name, "r")

            assert flock.acquire_flock(fd0.fileno(), 0)
            assert not flock.acquire_flock(fd1.fileno(), 0)

            flock.release_flock(fd0.fileno())

            assert flock.acquire_flock(fd1.fileno(), 0)
            flock.release_flock(fd1.fileno())

    def test_flock_acquire_lock_blocking(self):
        """Test flock blocking acquire."""
        with tempfile.NamedTemporaryFile() as fd0:
            fd1 = open(fd0.name, "r")
            res = []

            assert flock.acquire_flock(fd0.fileno(), 0)
            thrd = threading.Thread(target=lambda: res.append(flock.acquire_flock(fd1.fileno(), -1)))
            thrd.start()

            time.sleep(5)
            assert thrd.is_alive()

            flock.release_flock(fd0.fileno())
            thrd.join()
            assert len(res) == 1 and res[0]

            fd2 = open(fd0.name, "r")
            assert not flock.acquire_flock(fd2.fileno(), 0)

            flock.release_flock(fd1.fileno())
            assert flock.acquire_flock(fd2.fileno(), 0)
            flock.release_flock(fd2.fileno())

    def test_flock_acquire_lock_timeout(self):
        """Test flock timeout acquire."""
        with tempfile.NamedTemporaryFile() as fd0:
            def acquire_helper():
                nonlocal elapsed
                start = time.time()
                res.append(flock.acquire_flock(fd1.fileno(), 5))
                end = time.time()
                elapsed = end - start

            fd1 = open(fd0.name, "r")
            elapsed = 0
            res = []

            assert flock.acquire_flock(fd0.fileno(), 0)
            thrd = threading.Thread(target=acquire_helper)
            thrd.start()

            thrd.join()
            assert ((len(res) == 1) and (not res[0]))
            assert elapsed >= 5

            flock.release_flock(fd0.fileno())

    @mock.patch("click.echo")
    def test_try_lock(self, mock_echo):
        """Test try_lock decorator."""
        with tempfile.NamedTemporaryFile() as fd0:
            def get_file_content(fd):
                fd.seek(0)
                return fd.read()

            f0_with_try_lock = flock.try_lock(fd0.name, timeout=0)(dummy_f0)
            f1_with_try_lock = flock.try_lock(fd0.name, timeout=0)(dummy_f1)

            thrd = threading.Thread(target=f0_with_try_lock)
            thrd.start()
            time.sleep(2)

            try:
                assert mock_echo.call_args_list == [mock.call(f"Acquired lock on {fd0.name}")]
                assert b"dummy_f0" in get_file_content(fd0)

                with pytest.raises(SystemExit):
                    f1_with_try_lock()
                assert mock_echo.call_args_list == [mock.call(f"Acquired lock on {fd0.name}"),
                                                    mock.call(f"Failed to acquire lock on {fd0.name}")]
            finally:
                f0_exit.set()
                thrd.join()

            assert b"dummy_f0" not in get_file_content(fd0)

            thrd = threading.Thread(target=f1_with_try_lock)
            thrd.start()
            time.sleep(2)

            try:
                assert mock_echo.call_args_list == [mock.call(f"Acquired lock on {fd0.name}"),
                                                    mock.call(f"Failed to acquire lock on {fd0.name}"),
                                                    mock.call(f"Released lock on {fd0.name}"),
                                                    mock.call(f"Acquired lock on {fd0.name}")]
                assert b"dummy_f1" in get_file_content(fd0)
            finally:
                f1_exit.set()
                thrd.join()

            assert b"dummy_f1" not in get_file_content(fd0)

    @mock.patch("click.echo")
    def test_try_lock_with_bypass(self, mock_echo):
        with tempfile.NamedTemporaryFile() as fd0:
            def get_file_content(fd):
                fd.seek(0)
                return fd.read()

            f1_with_try_lock = flock.try_lock(fd0.name, timeout=0)(dummy_f1)

            thrd = threading.Thread(target=f1_with_try_lock, args=(True,))
            thrd.start()
            time.sleep(2)

            try:
                assert mock_echo.call_args_list == [mock.call(f"Bypass lock on {fd0.name}")]
                assert b"dummy_f1" not in get_file_content(fd0)
            finally:
                f1_exit.set()
                thrd.join()

    @mock.patch("click.echo")
    def test_try_lock_with_bypass_default(self, mock_echo):
        with tempfile.NamedTemporaryFile() as fd0:
            def get_file_content(fd):
                fd.seek(0)
                return fd.read()

            f2_with_try_lock = flock.try_lock(fd0.name, timeout=0)(dummy_f2)

            thrd = threading.Thread(target=f2_with_try_lock)
            thrd.start()
            time.sleep(2)

            try:
                assert mock_echo.call_args_list == [mock.call(f"Bypass lock on {fd0.name}")]
                assert b"dummy_f2" not in get_file_content(fd0)
            finally:
                f2_exit.set()
                thrd.join()

    def teardown(self):
        print("TEARDOWN")
        f0_exit.clear()
        f1_exit.clear()
        f2_exit.clear()

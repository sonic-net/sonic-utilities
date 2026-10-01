"""Tests for the cli_server fork-server (execution + completion daemon).

These deliberately avoid importing show.main / config.main: cli_server's
own logic (fork, SCM_RIGHTS, exit-code translation, privilege drop,
fallback, staleness) is independent of what CLI is actually loaded, and is
exercised here with a minimal fake "cli" object instead.
"""

import array
import json
import os
import signal
import socket
import struct
import sys
from unittest import mock

import pytest

from utilities_common import cli_server


class _FakeCli:
    """Stands in for click's Group.main(args=..., prog_name=...)."""

    def __init__(self, action):
        self._action = action

    def main(self, args, prog_name):
        self._action(args, prog_name)


@pytest.fixture
def sock_paths(tmp_path, monkeypatch):
    sock_path = str(tmp_path / "cli.sock")
    monkeypatch.setattr(cli_server, "SOCKET_PATH", sock_path)
    return sock_path


def _listen(sock_path):
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(sock_path)
    server.listen(1)
    return server


# --------------------------------------------------------------------------- #
# Fallback / never-re-run semantics
# --------------------------------------------------------------------------- #

def test_try_run_falls_back_when_socket_missing(sock_paths):
    assert cli_server.try_run("show") is None


def test_try_run_falls_back_when_disabled(sock_paths, monkeypatch):
    monkeypatch.setenv("SONIC_CLI_DAEMON", "0")
    assert cli_server.try_run("show") is None


def test_try_run_never_falls_back_after_daemon_dies_mid_command(sock_paths):
    """If the daemon accepted the request but closes without a result,
    the client must return 1, not None -- config is not idempotent and
    must never be silently re-run on the legacy cold path.
    """
    server = _listen(sock_paths)
    try:
        r, w = os.pipe()
        try:
            import threading

            # try_run() calls signal.signal(), which CPython only allows
            # from the main thread -- so the *server* side (which has no
            # such restriction) runs on the background thread instead,
            # and the client call stays on the main thread.
            def fake_daemon():
                conn, _ = server.accept()
                # Blocking recv() only returns once the client's
                # sendmsg() has actually completed -- this removes the
                # send/close race and proves we are simulating a crash
                # *after* the request was accepted, not a failed send.
                conn.recv(4)
                conn.close()  # die before ever sending a result

            t = threading.Thread(target=fake_daemon)
            t.start()
            rc = cli_server._try_run_with_fds("config", (r, w, w))
            t.join(timeout=5)
        finally:
            os.close(r)
            os.close(w)
    finally:
        server.close()

    assert rc == 1


# --------------------------------------------------------------------------- #
# Exit code translation (real fork, real wait status -- not hand-crafted bits)
# --------------------------------------------------------------------------- #

def test_exit_code_from_wait_status_normal_exit():
    pid = os.fork()
    if pid == 0:
        os._exit(7)
    _pid, status = os.waitpid(pid, 0)
    assert cli_server._exit_code_from_wait_status(status) == 7


def test_exit_code_from_wait_status_signal():
    pid = os.fork()
    if pid == 0:
        os.kill(os.getpid(), signal.SIGTERM)
        os._exit(1)  # not reached if the signal fires first
    _pid, status = os.waitpid(pid, 0)
    assert cli_server._exit_code_from_wait_status(status) == 128 + signal.SIGTERM


# --------------------------------------------------------------------------- #
# Privilege drop (pure function, no real root required)
# --------------------------------------------------------------------------- #

def test_drop_privileges_noop_when_daemon_not_root(monkeypatch):
    monkeypatch.setattr(os, "getuid", lambda: 1000)
    setuid = mock.Mock()
    monkeypatch.setattr(os, "setuid", setuid)
    cli_server._drop_privileges(uid=1000, gid=1000)
    setuid.assert_not_called()


def test_drop_privileges_noop_when_caller_is_root(monkeypatch):
    monkeypatch.setattr(os, "getuid", lambda: 0)
    setuid = mock.Mock()
    monkeypatch.setattr(os, "setuid", setuid)
    cli_server._drop_privileges(uid=0, gid=0)
    setuid.assert_not_called()


def test_drop_privileges_drops_for_non_root_caller(monkeypatch):
    monkeypatch.setattr(os, "getuid", lambda: 0)
    calls = []
    monkeypatch.setattr(os, "initgroups", lambda user, gid: calls.append(("initgroups", user, gid)))
    monkeypatch.setattr(os, "setgid", lambda gid: calls.append(("setgid", gid)))
    monkeypatch.setattr(os, "setuid", lambda uid: calls.append(("setuid", uid)))

    fake_pwrec = mock.Mock(pw_name="admin")
    with mock.patch("pwd.getpwuid", return_value=fake_pwrec) as getpwuid:
        cli_server._drop_privileges(uid=1001, gid=1001)
        getpwuid.assert_called_once_with(1001)

    assert calls == [
        ("initgroups", "admin", 1001),
        ("setgid", 1001),
        ("setuid", 1001),
    ]


# --------------------------------------------------------------------------- #
# Full round trip: argv / env / cwd propagation, completion via forwarded env
# --------------------------------------------------------------------------- #

def _run_round_trip(prog, cli_action, argv, env_extra=None, cwd=None):
    """Drives one real client<->supervisor<->child round trip over a real
    AF_UNIX socket, with real fds standing in for the client's stdio.
    Returns (exit_code, captured_stdout_bytes).
    """
    out_r, out_w = os.pipe()
    in_r, in_w = os.pipe()
    os.close(in_w)  # child never reads stdin in these tests

    cli_server._clis[prog] = _FakeCli(cli_action)
    try:
        import tempfile

        tmp_dir = tempfile.mkdtemp()
        sock_path = os.path.join(tmp_dir, "cli.sock")
        sock_dir_server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock_dir_server.bind(sock_path)
        sock_dir_server.listen(1)

        client_env = dict(os.environ)
        if env_extra:
            client_env.update(env_extra)

        req = json.dumps({
            "prog": prog,
            "argv": argv,
            "env": client_env,
            "cwd": cwd or os.getcwd(),
        }).encode("utf-8")

        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(sock_path)
        client.sendmsg(
            [struct.pack("!I", len(req)) + req],
            [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", [in_r, out_w, out_w]))],
        )

        conn, _ = sock_dir_server.accept()
        supervisor_pid = os.fork()
        if supervisor_pid == 0:
            sock_dir_server.close()
            client.close()
            os.close(out_w)
            os.close(in_r)
            cli_server._serve_request(conn)
            os._exit(0)

        conn.close()
        os.close(out_w)
        os.close(in_r)

        resp_buf = b""
        client.settimeout(10)
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            resp_buf += chunk
        resp = json.loads(resp_buf.decode().strip())

        captured = b""
        while True:
            chunk = os.read(out_r, 4096)
            if not chunk:
                break
            captured += chunk

        os.waitpid(supervisor_pid, 0)
        return resp.get("exit_code"), captured
    finally:
        cli_server._clis.pop(prog, None)
        try:
            os.close(out_r)
        except OSError:
            pass
        try:
            sock_dir_server.close()
        except Exception:
            pass


def test_argv_and_env_reach_the_command():
    # The action runs inside a forked child (via os.fork() in
    # _serve_request): mutating a closed-over dict is invisible to this
    # (parent) process once forked, so results must travel back through
    # the captured stdout pipe -- the same channel a real command uses.
    def action(args, prog_name):
        sys.stdout.write(json.dumps({
            "args": args,
            "prog_name": prog_name,
            "env_marker": os.environ.get("SONIC_TEST_MARKER"),
        }))
        sys.stdout.write("\n")
        sys.exit(0)

    code, out = _run_round_trip(
        "show", action, argv=["version"], env_extra={"SONIC_TEST_MARKER": "hello"}
    )
    assert code == 0
    seen = json.loads(out.decode().strip())
    assert seen["args"] == ["version"]
    assert seen["prog_name"] == "show"
    assert seen["env_marker"] == "hello"


def test_completion_env_forwarded_to_child():
    """No special-casing needed for Tab completion: the child just sees
    _SHOW_COMPLETE in the forwarded environment, same as a real command.
    """
    def action(args, prog_name):
        sys.stdout.write(json.dumps({
            "complete_env": os.environ.get("_SHOW_COMPLETE"),
        }))
        sys.stdout.write("\n")
        sys.exit(0)

    code, out = _run_round_trip(
        "show",
        action,
        argv=[],
        env_extra={"_SHOW_COMPLETE": "bash_complete", "COMP_WORDS": "show ", "COMP_CWORD": "1"},
    )
    assert code == 0
    seen = json.loads(out.decode().strip())
    assert seen["complete_env"] == "bash_complete"


def test_system_exit_with_int_code():
    def action(args, prog_name):
        sys.exit(42)

    code, _out = _run_round_trip("show", action, argv=[])
    assert code == 42


def test_system_exit_with_string_message_maps_to_one():
    def action(args, prog_name):
        sys.exit("Root privileges are required for this operation")

    code, _out = _run_round_trip("config", action, argv=[])
    assert code == 1


def test_keyboard_interrupt_maps_to_130():
    def action(args, prog_name):
        raise KeyboardInterrupt()

    code, _out = _run_round_trip("show", action, argv=[])
    assert code == 130


# --------------------------------------------------------------------------- #
# Socket permissions (defense-in-depth on top of SO_PEERCRED + setuid)
# --------------------------------------------------------------------------- #

def test_set_socket_permissions_is_group_restricted_not_world_writable(tmp_path):
    sock_path = tmp_path / "cli.sock"
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(str(sock_path))
        cli_server._set_socket_permissions(str(sock_path))
        mode = os.stat(sock_path).st_mode & 0o777
        assert mode == 0o660
    finally:
        server.close()


# --------------------------------------------------------------------------- #
# Staleness detection
# --------------------------------------------------------------------------- #

def test_watch_mtimes_changed_detects_edit(tmp_path, monkeypatch):
    fake_module = tmp_path / "fake_show_main.py"
    fake_module.write_text("x = 1\n")

    monkeypatch.setattr(cli_server, "_watch_mtimes", {str(fake_module): os.stat(fake_module).st_mtime})
    assert cli_server._watch_mtimes_changed() is False

    # Simulate a package upgrade touching the file.
    import time

    time.sleep(0.01)
    fake_module.write_text("x = 2\n")
    os.utime(fake_module, None)
    assert cli_server._watch_mtimes_changed() is True


def test_watch_mtimes_changed_true_when_file_removed(tmp_path, monkeypatch):
    fake_module = tmp_path / "fake_show_main.py"
    fake_module.write_text("x = 1\n")
    mtime = os.stat(fake_module).st_mtime
    monkeypatch.setattr(cli_server, "_watch_mtimes", {str(fake_module): mtime})
    os.remove(fake_module)
    assert cli_server._watch_mtimes_changed() is True

"""Tests for the cli_server fork-server (execution + completion daemon).

These deliberately avoid importing show.main / config.main: cli_server's
own logic (fork, SCM_RIGHTS, exit-code translation, privilege drop,
fallback, staleness) is independent of what CLI is actually loaded, and is
exercised here with a minimal fake "cli" object instead.
"""

import array
import ast
import inspect
import json
import os
import signal
import socket
import struct
import sys
import textwrap
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


def test_client_does_not_retry_on_post_connect_send_failure(sock_paths, monkeypatch):
    """An OSError from sendmsg() does not prove the daemon received zero
    bytes -- it may have already accepted a partial request and started
    executing. Once connect() has succeeded, a send failure must report
    failure (1), not fall back to the cold path and risk re-running a
    non-idempotent config command.
    """
    server = _listen(sock_paths)
    try:
        monkeypatch.setattr(
            socket.socket, "sendmsg",
            mock.Mock(side_effect=OSError("simulated send failure")),
        )
        rc = cli_server.try_run("config")
    finally:
        server.close()

    assert rc == 1


def test_client_completes_partial_sendmsg_write(sock_paths):
    """sendmsg() on a stream socket may write only part of the buffer;
    the client must send the remainder itself rather than assuming the
    daemon received a complete frame.
    """
    import threading

    server = _listen(sock_paths)
    received = bytearray()
    try:
        def fake_daemon():
            conn, _ = server.accept()
            while len(received) < 4 or len(received) < 4 + struct.unpack("!I", bytes(received[:4]))[0]:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                received.extend(chunk)
            conn.close()

        t = threading.Thread(target=fake_daemon)
        t.start()

        real_sendmsg = socket.socket.sendmsg

        def half_sendmsg(self, buffers, ancdata=(), *a, **kw):
            data = buffers[0]
            half = max(1, len(data) // 2)
            return real_sendmsg(self, [data[:half]], ancdata, *a, **kw)

        r, w = os.pipe()
        try:
            with mock.patch.object(socket.socket, "sendmsg", half_sendmsg):
                cli_server._try_run_with_fds("show", (r, w, w))
        finally:
            os.close(r)
            os.close(w)
        t.join(timeout=5)
    finally:
        server.close()

    assert len(received) >= 4
    (length,) = struct.unpack("!I", bytes(received[:4]))
    assert len(received) == 4 + length
    req = json.loads(bytes(received[4:4 + length]).decode("utf-8"))
    assert req["prog"] == "show"


def test_client_clears_connect_timeout_before_sending():
    """``settimeout()`` applies to every subsequent operation on the
    socket, not just ``connect()`` -- the short connect deadline must be
    cleared before ``sendmsg()``/``sendall()`` run, or it also limits
    those: a large forwarded environment, or a daemon that's briefly not
    reading, could time out mid-send and be treated the same as an
    outright failure.
    """
    source = inspect.getsource(cli_server._try_run_with_fds)
    clear_timeout = source.index("sock.settimeout(None)")
    first_send = source.index("sock.sendmsg(")
    assert clear_timeout < first_send


def test_client_waits_past_connect_timeout_for_a_slow_command(sock_paths, monkeypatch):
    """The connect timeout must not leak into how long the client waits
    for the daemon's response: commands (especially `config`) can
    legitimately run far longer than any reasonable connect deadline.
    """
    import threading
    import time

    monkeypatch.setattr(cli_server, "CONNECT_TIMEOUT_SEC", 0.05)
    server = _listen(sock_paths)
    try:
        def fake_daemon():
            conn, _ = server.accept()
            conn.recv(4)
            time.sleep(0.3)  # much longer than CONNECT_TIMEOUT_SEC above
            conn.sendall(json.dumps({"exit_code": 7}).encode("utf-8") + b"\n")
            conn.close()

        t = threading.Thread(target=fake_daemon)
        t.start()
        r, w = os.pipe()
        try:
            rc = cli_server._try_run_with_fds("show", (r, w, w))
        finally:
            os.close(r)
            os.close(w)
        t.join(timeout=5)
    finally:
        server.close()

    assert rc == 7


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


def test_chdir_failure_reports_error_instead_of_running_in_wrong_directory():
    """The cold path never hits this: a normal fork+exec just inherits
    the shell's real cwd. This warm child starts in the *daemon's*
    directory and must explicitly switch to the caller's -- silently
    continuing on failure would run the command against the wrong
    directory, and a relative file argument could then read or write a
    different path than the caller intended.
    """
    def action(args, prog_name):
        # Must never be reached: the chdir failure has to short-circuit
        # before the CLI action runs.
        sys.stdout.write("ran-anyway")
        sys.exit(0)

    code, out = _run_round_trip("show", action, argv=[], cwd="/no/such/directory")
    assert code == 1
    assert b"ran-anyway" not in out
    assert b"no/such/directory" in out


def test_child_resets_signal_dispositions_before_setup_work():
    """The forked command child inherits the *daemon's* SIGHUP (re-exec
    self) and SIGTERM/SIGINT (unlink the shared socket + exit) handlers
    via fork(). Those resets must be the first thing ``_run_child`` does
    -- before dup2/setsid/tty-claim/privilege-drop -- or a signal
    forwarded by the client early enough in that window runs daemon-level
    logic (re-exec, or unlinking the one shared socket every other
    connection depends on) inside what must behave as an isolated command
    process.

    A full fork+signal-delivery-race reproduction is inherently
    non-deterministic, so this pins the required source ordering instead.
    """
    source = inspect.getsource(cli_server._run_child)
    first_signal_reset = source.index("signal.signal(signal.SIGINT")
    first_setup_call = min(
        source.index(needle) for needle in ("os.dup2(", "os.setsid()", "_drop_privileges(")
    )
    assert first_signal_reset < first_setup_call

    tree = ast.parse(textwrap.dedent(source))
    func = tree.body[0]
    assert isinstance(func, ast.FunctionDef)
    body_stmts = func.body
    if isinstance(body_stmts[0], ast.Expr) and isinstance(body_stmts[0].value, ast.Constant):
        body_stmts = body_stmts[1:]  # skip the docstring

    resets = {"SIGINT", "SIGTERM", "SIGQUIT", "SIGHUP", "SIGCHLD"}
    for stmt in body_stmts:
        call = stmt.value if isinstance(stmt, ast.Expr) else None
        if not (isinstance(call, ast.Call) and getattr(call.func, "attr", None) == "signal"):
            break
        resets.discard(call.args[0].attr)
    assert not resets, "not reset before other setup work: %s" % resets


def test_sigchld_handler_installed_before_fork_in_serve_request():
    """If the SIGCHLD handler is installed *after* ``os.fork()``, a child
    that exits quickly (``show --help``) can deliver SIGCHLD into the gap
    between fork() and the handler install. With no handler registered
    yet, that delivery is simply discarded (SIGCHLD's default disposition
    is Ignore) and the later select() loop waits forever even though
    waitpid() could reap the already-dead child immediately.
    """
    source = inspect.getsource(cli_server._serve_request)
    handler_install = source.index("signal.signal(signal.SIGCHLD, _on_sigchld)")
    fork_call = source.index("os.fork()")
    assert handler_install < fork_call


# --------------------------------------------------------------------------- #
# Signal forwarding
# --------------------------------------------------------------------------- #

def test_relay_signals_targets_process_group_not_just_leader(monkeypatch):
    """``_run_child`` calls ``setsid()``, so the forked command is its own
    process-group leader. Signaling only the leader pid (``os.kill``)
    leaves any subprocess it spawns running after Ctrl-C/termination;
    signaling the group (``os.killpg``) reaches those descendants too.
    """
    calls = []
    monkeypatch.setattr(os, "killpg", lambda pgid, sig: calls.append((pgid, sig)))
    monkeypatch.setattr(os, "kill", mock.Mock(side_effect=AssertionError("must use killpg, not kill")))

    remaining = cli_server._relay_signals(
        b"", json.dumps({"signal": signal.SIGINT}).encode("utf-8") + b"\n", 4321,
    )

    assert calls == [(4321, signal.SIGINT)]
    assert remaining == b""


def test_relay_signals_buffers_partial_frame_across_reads(monkeypatch):
    """recv() may split a signal frame at any byte boundary; a frame
    delivered in two pieces must still be forwarded once complete, not
    silently dropped because neither individual chunk parses as JSON.
    """
    calls = []
    monkeypatch.setattr(os, "killpg", lambda pgid, sig: calls.append((pgid, sig)))

    frame = json.dumps({"signal": signal.SIGINT}).encode("utf-8") + b"\n"
    split_at = len(frame) - 3
    buf = cli_server._relay_signals(b"", frame[:split_at], 4321)
    assert calls == []  # incomplete frame -- must not be dropped or misparsed

    buf = cli_server._relay_signals(buf, frame[split_at:], 4321)
    assert calls == [(4321, signal.SIGINT)]
    assert buf == b""


@pytest.mark.parametrize("payload", [
    b"42",                                  # valid JSON, not a dict
    b"[1, 2, 3]",                           # valid JSON, not a dict
    b'{"signal": "SIGINT"}',                # dict, but non-integer signal
    b'{"signal": -5}',                      # dict, but non-positive signal
    b'{"signal": null}',                    # dict, but missing/null signal
])
def test_relay_signals_ignores_malformed_frames_without_crashing(monkeypatch, payload):
    """Signal frames are client-controlled after the request is accepted.
    A valid JSON scalar/list, or a dict with a non-integer/non-positive
    "signal", must be ignored rather than raising out of .get() or
    os.killpg() -- an uncaught exception here would kill the supervisor
    without ever sending a response, while the already-forked command
    child keeps running unwatched.
    """
    calls = []
    monkeypatch.setattr(os, "killpg", lambda pgid, sig: calls.append((pgid, sig)))

    buf = cli_server._relay_signals(b"", payload + b"\n", 4321)

    assert calls == []
    assert buf == b""


def test_recv_request_rejects_oversized_length_header(sock_paths):
    """A caller can send an arbitrary length prefix (e.g. 0xffffffff) with
    no body. Without an upper bound, the forked supervisor would block in
    recv() waiting for a body that may never arrive, tying up process
    resources indefinitely.
    """
    server = _listen(sock_paths)
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(sock_paths)
        client.sendall(struct.pack("!I", 0xFFFFFFFF))
        conn, _ = server.accept()
        try:
            with pytest.raises(ValueError):
                cli_server._recv_request(conn)
        finally:
            conn.close()
            client.close()
    finally:
        server.close()


def test_recv_request_separates_trailing_bytes_from_declared_body(sock_paths):
    """The initial recvmsg() can return the length-prefixed request and
    already-queued signal bytes together. `body` must be capped to the
    declared length; anything past it belongs to the caller as leftover,
    not to the JSON payload.
    """
    server = _listen(sock_paths)
    try:
        req = json.dumps({"prog": "show", "argv": [], "env": {}, "cwd": "/"}).encode("utf-8")
        trailing = json.dumps({"signal": signal.SIGINT}).encode("utf-8") + b"\n"

        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(sock_paths)
        client.sendmsg(
            [struct.pack("!I", len(req)) + req + trailing],
            [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", [0, 1, 2]))],
        )
        conn, _ = server.accept()
        try:
            parsed, fds, leftover = cli_server._recv_request(conn)
        finally:
            conn.close()
            client.close()
    finally:
        server.close()

    assert parsed == {"prog": "show", "argv": [], "env": {}, "cwd": "/"}
    assert len(fds) == 3
    assert leftover == trailing


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


def test_set_socket_permissions_logs_when_group_is_missing(tmp_path, monkeypatch):
    """If the configured group doesn't exist, the socket silently stays
    root-only (safe -- clients just fall back) but nothing would tell an
    operator why the daemon stopped accelerating anything for non-root
    users. This must be surfaced, not swallowed.
    """
    sock_path = tmp_path / "cli.sock"
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(str(sock_path))
        monkeypatch.setenv("SONIC_CLI_SOCKET_GROUP", "no-such-group")
        logged = []
        monkeypatch.setattr(
            cli_server.syslog, "syslog",
            lambda priority, message: logged.append((priority, message)),
        )
        cli_server._set_socket_permissions(str(sock_path))
    finally:
        server.close()

    assert len(logged) == 1
    priority, message = logged[0]
    assert priority == cli_server.syslog.LOG_WARNING
    assert "no-such-group" in message


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

"""Warm fork-server for ``show``/``config`` execution and Tab completion.

The daemon imports ``show.main:cli`` and ``config.main:config`` exactly once.
For each request it forks a per-connection *supervisor*, which itself forks
the actual command *child*. The child:

  * receives the client's stdin/stdout/stderr fds via ``SCM_RIGHTS`` so
    output streams to the real TTY (colors, ``isatty()``, prompts work),
  * reads the caller's uid/gid from ``SO_PEERCRED`` (kernel-verified, not
    client-supplied) and drops root privileges when the caller is non-root
    -- this reuses ``config.main``'s existing ``os.geteuid() != 0`` check,
    it does not add new trust logic,
  * applies the client's argv, full environment and cwd, then runs
    ``cli.main(args=argv, prog_name=prog)``.

Tab completion needs no special handling: the forked child sees
``_SHOW_COMPLETE`` / ``_CONFIG_COMPLETE`` in the forwarded environment and
writes completions to the forwarded stdout, exactly like a real command.

The client (``try_run``) imports only the standard library before deciding
whether to use the daemon -- this must stay true, or most of the startup
savings disappear.
"""

import array
import json
import os
import select
import signal
import socket
import struct
import sys

SOCKET_PATH = os.environ.get("SONIC_CLI_SOCKET", "/run/sonic/cli.sock")
PID_PATH = os.environ.get("SONIC_CLI_DAEMON_PID", "/run/sonic/cli-daemon.pid")
CLIENT_TIMEOUT_SEC = float(os.environ.get("SONIC_CLI_DAEMON_TIMEOUT", "60.0"))

PROG_LOADERS = {
    "show": ("show.main", "cli"),
    "config": ("config.main", "config"),
}

FORWARDED_SIGNALS = (
    signal.SIGINT,
    signal.SIGTERM,
    signal.SIGHUP,
    signal.SIGQUIT,
)

_clis = {}
_watch_mtimes = {}


# =============================================================== client side

def try_run(prog):
    """Run ``prog`` via the daemon. Return an exit code, or ``None`` to fall
    back to the legacy cold-start path (``show.main:cli`` / ``config.main:config``).
    """
    return _try_run_with_fds(prog, (0, 1, 2))


def _try_run_with_fds(prog, fds):
    if os.environ.get("SONIC_CLI_DAEMON", "1") == "0":
        return None

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(CLIENT_TIMEOUT_SEC)
        sock.connect(SOCKET_PATH)
    except OSError:
        # Daemon not running / socket missing -- nothing has executed yet,
        # safe to fall back to the cold path.
        return None

    req = json.dumps({
        "prog": prog,
        "argv": sys.argv[1:],
        "env": dict(os.environ),
        "cwd": os.getcwd(),
    }).encode("utf-8")

    try:
        sock.sendmsg(
            [struct.pack("!I", len(req)) + req],
            [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", fds))],
        )
    except OSError:
        # Request never reached the daemon -- safe to fall back.
        sock.close()
        return None

    prev_handlers = {}

    def _forward(signum, _frame):
        try:
            sock.sendall(json.dumps({"signal": signum}).encode("utf-8") + b"\n")
        except OSError:
            pass

    for sig in FORWARDED_SIGNALS:
        prev_handlers[sig] = signal.signal(sig, _forward)

    buf = b""
    try:
        while True:
            try:
                chunk = sock.recv(65536)
            except (OSError, socket.timeout):
                break
            if not chunk:
                break
            buf += chunk
    finally:
        for sig, handler in prev_handlers.items():
            signal.signal(sig, handler)
        sock.close()

    line = buf.decode("utf-8", "replace").strip()
    if not line:
        # The request was sent (the daemon may already be running the
        # command) but we got no confirmed result back. config is not
        # idempotent -- never silently re-run it on the legacy path.
        return 1

    try:
        resp = json.loads(line.splitlines()[-1])
    except ValueError:
        return 1

    if resp.get("fallback"):
        return None
    return int(resp.get("exit_code", 1))


# =============================================================== daemon side

def _recv_request(conn):
    """Receive a length-prefixed JSON request plus stdio fds via SCM_RIGHTS."""
    fds = array.array("i")
    cmsg_space = socket.CMSG_SPACE(3 * fds.itemsize)
    msg, anc, _flags, _addr = conn.recvmsg(65536, cmsg_space)
    for level, ctype, data in anc:
        if level == socket.SOL_SOCKET and ctype == socket.SCM_RIGHTS:
            fds.frombytes(data[: len(data) - (len(data) % fds.itemsize)])
    if len(msg) < 4:
        raise ValueError("short request header")
    (length,) = struct.unpack("!I", msg[:4])
    body = msg[4:]
    while len(body) < length:
        more = conn.recv(length - len(body))
        if not more:
            raise ValueError("client closed before sending full request")
        body += more
    return json.loads(body.decode("utf-8")), list(fds)


def _peer_creds(conn):
    fmt = "3i"
    creds = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize(fmt))
    _pid, uid, gid = struct.unpack(fmt, creds)
    return uid, gid


def _exit_code_from_wait_status(status):
    """Translate a raw ``os.waitpid()`` status into a shell-style exit code.

    Deliberately avoids ``os.waitstatus_to_exitcode`` (Python 3.9+) so this
    keeps working on 3.8 images.
    """
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    if os.WIFSIGNALED(status):
        return 128 + os.WTERMSIG(status)
    return 1


def _drop_privileges(uid, gid):
    """Drop from root to the caller's real uid/gid. No-op if the daemon
    isn't root or the caller already is (e.g. connected via ``sudo``).
    """
    if os.getuid() != 0 or uid == 0:
        return
    import pwd

    user = pwd.getpwuid(uid).pw_name
    os.initgroups(user, gid)
    os.setgid(gid)
    os.setuid(uid)


def _acquire_controlling_tty():
    """Best-effort: claim the inherited stdin as our controlling terminal so
    pagers/prompts that open ``/dev/tty`` directly (e.g. ``less``) work.
    No-op for non-interactive/piped invocations, matching normal shell
    behavior for those cases.
    """
    try:
        import fcntl
        import termios

        fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    except OSError:
        pass


def _run_child(req, fds, uid, gid):
    """Runs inside the forked command child. Never returns normally."""
    for target, fd in enumerate(fds[:3]):
        os.dup2(fd, target)
    for fd in fds:
        if fd > 2:
            os.close(fd)

    os.setsid()
    _acquire_controlling_tty()
    _drop_privileges(uid, gid)

    os.environ.clear()
    os.environ.update(req["env"])
    try:
        os.chdir(req["cwd"])
    except OSError:
        pass

    signal.signal(signal.SIGINT, signal.default_int_handler)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    signal.signal(signal.SIGQUIT, signal.SIG_DFL)
    signal.signal(signal.SIGHUP, signal.SIG_DFL)

    sys.stdin = open(0, "r", closefd=False)
    sys.stdout = open(1, "w", buffering=1, closefd=False)
    sys.stderr = open(2, "w", buffering=1, closefd=False)

    prog = req["prog"]
    argv = list(req.get("argv", []))
    sys.argv = [prog] + argv
    cli = _clis[prog]

    code = 0
    try:
        cli.main(args=argv, prog_name=prog)
    except SystemExit as exc:
        if exc.code is None:
            code = 0
        elif isinstance(exc.code, int):
            code = exc.code
        else:
            sys.stderr.write(str(exc.code) + "\n")
            code = 1
    except KeyboardInterrupt:
        code = 130
    except Exception:
        import traceback

        traceback.print_exc()
        code = 1
    finally:
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
    os._exit(code)


def _serve_request(conn):
    """Runs inside the per-request supervisor process."""
    try:
        req, fds = _recv_request(conn)
    except (ValueError, OSError, json.JSONDecodeError):
        _reply_fallback(conn)
        return

    prog = req.get("prog")
    if prog not in _clis or len(fds) != 3:
        for fd in fds:
            _safe_close(fd)
        _reply_fallback(conn)
        return

    uid, gid = _peer_creds(conn)
    pipe_r, pipe_w = os.pipe()

    def _on_sigchld(_signum, _frame):
        try:
            os.write(pipe_w, b"x")
        except OSError:
            pass

    child = os.fork()
    if child == 0:
        os.close(pipe_r)
        os.close(pipe_w)
        conn.close()
        _run_child(req, fds, uid, gid)
        os._exit(1)  # unreachable

    for fd in fds:
        _safe_close(fd)
    prev_sigchld = signal.signal(signal.SIGCHLD, _on_sigchld)

    exit_code = 1
    watch_conn = True
    try:
        while True:
            watch_fds = [pipe_r] + ([conn] if watch_conn else [])
            readable, _, _ = select.select(watch_fds, [], [])
            if pipe_r in readable:
                _pid, status = os.waitpid(child, 0)
                exit_code = _exit_code_from_wait_status(status)
                break
            if conn in readable:
                try:
                    data = conn.recv(4096)
                except OSError:
                    data = b""
                if not data:
                    # Client went away; keep the command running (it owns
                    # its own fds already) but stop selecting on a dead
                    # connection to avoid spinning on repeated EOF.
                    watch_conn = False
                    continue
                _relay_signals(data, child)
    finally:
        signal.signal(signal.SIGCHLD, prev_sigchld)
        os.close(pipe_r)
        os.close(pipe_w)

    try:
        conn.sendall(json.dumps({"exit_code": exit_code}).encode("utf-8") + b"\n")
    except OSError:
        pass
    conn.close()


def _relay_signals(data, child):
    for line in data.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            sig = json.loads(line).get("signal")
        except ValueError:
            continue
        if sig:
            try:
                os.kill(child, sig)
            except OSError:
                pass


def _reply_fallback(conn):
    try:
        conn.sendall(b'{"fallback": true}\n')
    except OSError:
        pass
    conn.close()


def _safe_close(fd):
    try:
        os.close(fd)
    except OSError:
        pass


# --------------------------------------------------------- staleness / re-exec

def _module_file(modname):
    mod = sys.modules.get(modname)
    return getattr(mod, "__file__", None) if mod else None


def _snapshot_watch_mtimes():
    mtimes = {}
    for modname, _attr in PROG_LOADERS.values():
        path = _module_file(modname)
        if path and os.path.exists(path):
            mtimes[path] = os.stat(path).st_mtime
    return mtimes


def _watch_mtimes_changed():
    for path, recorded in _watch_mtimes.items():
        try:
            if os.stat(path).st_mtime != recorded:
                return True
        except OSError:
            return True
    return False


def _reexec_self():
    """Re-exec the daemon process in place.

    Used both when ``show.main``/``config.main`` changed on disk (package
    upgrade) and on SIGHUP. SIGHUP is the intended manual fix for
    show/main.py's import-time BGP routing-stack probe: if the BGP
    container was still starting when the daemon booted, ``show ip bgp``
    is permanently unavailable until something re-triggers that probe.
    Sending SIGHUP (or restarting the service) re-imports show.main from
    scratch, which reruns the probe against current container state.
    In-flight commands are unaffected -- they already forked and hold
    their own copy of the previously loaded code.
    """
    os.execv(sys.argv[0], sys.argv)


# ==================================================================== daemon

def run_daemon_main():
    """Entry point for the ``sonic-cli-daemon`` console script."""
    for prog, (modname, attr) in PROG_LOADERS.items():
        mod = __import__(modname, fromlist=[attr])
        _clis[prog] = getattr(mod, attr)
    _watch_mtimes.update(_snapshot_watch_mtimes())

    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)
    os.makedirs(os.path.dirname(SOCKET_PATH), mode=0o755, exist_ok=True)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    # Authorization is enforced via SO_PEERCRED + setuid in the forked
    # child, not via filesystem permissions on the socket itself -- see
    # cli-daemon.md for the full rationale.
    os.chmod(SOCKET_PATH, 0o666)
    server.listen(64)

    with open(PID_PATH, "w") as pid_file:
        pid_file.write(str(os.getpid()))

    def _reap_supervisors(_signum, _frame):
        while True:
            try:
                pid, _status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                break
            if pid == 0:
                break

    def _handle_sighup(_signum, _frame):
        _reexec_self()

    def _shutdown(_signum, _frame):
        server.close()
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)
        sys.exit(0)

    signal.signal(signal.SIGCHLD, _reap_supervisors)
    signal.signal(signal.SIGHUP, _handle_sighup)
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    while True:
        try:
            conn, _addr = server.accept()
        except InterruptedError:
            continue
        except OSError:
            break

        if _watch_mtimes_changed():
            # Code changed on disk since we loaded it (upgrade). Refuse
            # this one connection with fallback and restart with fresh
            # code; the client falls back to its own cold-start path.
            _reply_fallback(conn)
            _reexec_self()
            continue  # unreachable after execv

        pid = os.fork()
        if pid == 0:
            server.close()
            _serve_request(conn)
            os._exit(0)
        conn.close()


if __name__ == "__main__":
    run_daemon_main()

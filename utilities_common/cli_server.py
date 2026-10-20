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
import grp
import json
import os
import select
import signal
import socket
import struct
import sys
import syslog

SOCKET_PATH = os.environ.get("SONIC_CLI_SOCKET", "/run/sonic/cli.sock")
PID_PATH = os.environ.get("SONIC_CLI_DAEMON_PID", "/run/sonic/cli-daemon.pid")

# Only bounds connecting to the (local, already-running) daemon socket --
# never how long a command is allowed to run. Some commands (e.g. `config`
# operations) legitimately take well past a minute; once the request has
# been handed to the daemon, the client blocks indefinitely for the real
# result instead of guessing a deadline and reporting a false failure
# while the daemon is still correctly executing the command.
CONNECT_TIMEOUT_SEC = float(os.environ.get("SONIC_CLI_DAEMON_CONNECT_TIMEOUT", "2.0"))

# Daemon side: bounds how large a single request may declare itself to be
# (generous headroom over a real argv/env/cwd payload) and how long the
# supervisor will wait for the rest of it to arrive. Neither applies once
# the request has been fully received -- forwarding signals to an
# in-flight command has no deadline, since the command may run
# indefinitely.
MAX_REQUEST_BYTES = 8 * 1024 * 1024
REQUEST_RECV_TIMEOUT_SEC = 5.0

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
        sock.settimeout(CONNECT_TIMEOUT_SEC)
        sock.connect(SOCKET_PATH)
    except OSError:
        # Daemon not running / socket missing -- nothing has executed yet,
        # safe to fall back to the cold path.
        return None

    # settimeout() applies to every subsequent operation on this socket,
    # not just connect() -- clear it immediately so the short connect
    # deadline doesn't also apply to sendmsg()/sendall() below (a large
    # forwarded environment, or a daemon that's briefly not reading,
    # could otherwise time out mid-send and be treated the same as an
    # outright failure) or to the response-wait loop further down.
    sock.settimeout(None)

    request = {
        "prog": prog,
        "argv": sys.argv[1:],
        "env": dict(os.environ),
        "cwd": os.getcwd(),
    }
    pty_spec = _client_pty_spec(fds)
    if pty_spec is not None:
        request["pty"] = pty_spec
    req = json.dumps(request).encode("utf-8")
    frame = struct.pack("!I", len(req)) + req

    try:
        # sendmsg() on a stream socket may write only part of the frame;
        # the ancillary (SCM_RIGHTS) data is delivered together with
        # whichever bytes this call actually sends, so any remainder is
        # just ordinary bytes that a plain send finishes.
        sent = sock.sendmsg(
            [frame],
            [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", fds))],
        )
        if sent < len(frame):
            sock.sendall(frame[sent:])
    except OSError:
        # An error here does not prove the daemon received zero bytes --
        # it may have already accepted a partial request and started
        # executing. config is not idempotent, so once we've attempted to
        # connect and send, falling back to re-run on the cold path is
        # not an option; report failure instead.
        sock.close()
        return 1

    # The request is now fully on the wire; there is nothing further to
    # time out into -- only the daemon knows how long this command may
    # legitimately take, and if the client's connection to it dies from
    # here on, returning 1 (not None) is the only safe behavior anyway
    # (see the empty-response handling below).

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
        if pty_spec is not None:
            buf = _client_pty_session(sock, pty_spec, fds)
        else:
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


# ----------------------------------------------------------- client pty mode
#
# When any of the caller's stdin/stdout/stderr is a terminal, the daemon gives the command
# child a *fresh pty* as its controlling terminal (setsid + TIOCSCTTY works on a new pty) and
# this client proxies bytes, window-size changes and raw mode between the caller's terminal
# and that pty, like ``docker exec -t`` or ssh. The forwarded fds alone cannot do this: after
# setsid() the child has no controlling terminal, so ``/dev/tty`` (sudo/getpass prompts, ssh),
# tty-generated signals (SIGWINCH) and job control would all be broken, and stealing the
# caller's terminal (TIOCSCTTY with arg 1) would evict the user's own login shell.

def _client_pty_spec(fds):
    """Describe the caller's terminal for the daemon, or ``None`` for the plain fd-passing mode."""
    if os.environ.get("SONIC_CLI_DAEMON_PTY", "1") == "0":
        return None
    try:
        mask = [os.isatty(fd) for fd in fds[:3]]
    except OSError:
        return None
    if len(fds) != 3 or not any(mask):
        return None
    import fcntl
    import termios

    tty_fd = fds[mask.index(True)]
    spec = {"mask": mask}
    try:
        attrs = termios.tcgetattr(tty_fd)
        spec["termios"] = attrs[:6] + [[c if isinstance(c, int) else c[0] for c in attrs[6]]]
    except (termios.error, OSError, IndexError):
        pass
    try:
        spec["winsize"] = list(struct.unpack("HHHH", fcntl.ioctl(tty_fd, termios.TIOCGWINSZ, b"\0" * 8)))
    except OSError:
        pass
    return spec


def _client_pty_session(sock, spec, fds):
    """Receive the pty master from the daemon and proxy the terminal until the result arrives.

    Returns the raw bytes received on the control socket after the pty hand-off (the final
    ``{"exit_code": n}`` line, or ``{"fallback": true}``).
    """
    import fcntl
    import select
    import termios
    import tty

    # First reply: either {"fallback": true} / a result (no pty), or {"pty": bool} plus the
    # master fd as SCM_RIGHTS ancillary data.
    master = None
    got = array.array("i")
    try:
        msg, anc, _flags, _addr = sock.recvmsg(65536, socket.CMSG_SPACE(got.itemsize))
    except OSError:
        return b""
    for level, ctype, data in anc:
        if level == socket.SOL_SOCKET and ctype == socket.SCM_RIGHTS:
            got.frombytes(data[: len(data) - (len(data) % got.itemsize)])
    if got:
        master = got[0]
    head, _, rest = msg.partition(b"\n")
    try:
        status = json.loads(head.decode("utf-8")) if head else {}
    except ValueError:
        status = {}
    if "pty" not in status:
        # Fallback or an immediate result -- no pty was set up.
        return msg
    if not status.get("pty") or master is None:
        # Daemon could not allocate a pty: behave like the plain mode (child uses our fds).
        return rest + _drain_socket(sock)

    mask = spec["mask"]
    in_fd = fds[0] if mask[0] else None
    out_fd = next((fds[i] for i in (1, 2) if mask[i]), None)
    close_extra = []
    if in_fd is None or out_fd is None:
        # A prompt (sudo, getpass) goes to /dev/tty even if our stdin/stdout are redirected, so
        # keep the real keyboard/screen wired to the child's pty.
        try:
            extra = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
            close_extra.append(extra)
            in_fd = extra if in_fd is None else in_fd
            out_fd = extra if out_fd is None else out_fd
        except OSError:
            pass
    size_fd = fds[mask.index(True)]
    saved = None
    raw_fd = in_fd
    if raw_fd is not None and os.isatty(raw_fd):
        try:
            saved = termios.tcgetattr(raw_fd)
            tty.setraw(raw_fd)
        except (termios.error, OSError):
            saved = None

    def _winch(_signum, _frame):
        try:
            fcntl.ioctl(master, termios.TIOCSWINSZ, fcntl.ioctl(size_fd, termios.TIOCGWINSZ, b"\0" * 8))
        except OSError:
            pass

    prev_winch = signal.signal(signal.SIGWINCH, _winch)
    result = bytearray(rest)
    master_open = True
    sock_open = True
    try:
        _winch(None, None)
        while sock_open or master_open:
            rlist = []
            if master_open:
                rlist.append(master)
            if sock_open:
                rlist.append(sock)
            if in_fd is not None and master_open:
                rlist.append(in_fd)
            try:
                readable, _, _ = select.select(rlist, [], [])
            except InterruptedError:
                continue
            if in_fd is not None and in_fd in readable:
                try:
                    data = os.read(in_fd, 4096)
                except OSError:
                    data = b""
                if data:
                    try:
                        os.write(master, data)
                    except OSError:
                        pass
                else:
                    in_fd = None
            if master in readable:
                try:
                    data = os.read(master, 65536)
                except OSError:  # EIO: every slave end is closed
                    data = b""
                if data:
                    _write_all(out_fd, data)
                else:
                    master_open = False
            if sock in readable:
                try:
                    chunk = sock.recv(65536)
                except OSError:
                    chunk = b""
                if chunk:
                    result += chunk
                    if b"\n" in result:
                        sock_open = False
                else:
                    sock_open = False
            if not sock_open and master_open:
                # Result is in; flush whatever the command wrote last, then stop. Descendants
                # that outlive the command and keep the pty open must not hold us here.
                while True:
                    ready, _, _ = select.select([master], [], [], 0.05)
                    if not ready:
                        break
                    try:
                        data = os.read(master, 65536)
                    except OSError:
                        data = b""
                    if not data:
                        break
                    _write_all(out_fd, data)
                master_open = False
    finally:
        signal.signal(signal.SIGWINCH, prev_winch)
        if saved is not None:
            try:
                termios.tcsetattr(raw_fd, termios.TCSADRAIN, saved)
            except (termios.error, OSError):
                pass
        _safe_close(master)
        for fd in close_extra:
            _safe_close(fd)
    return bytes(result)


def _write_all(fd, data):
    while data:
        try:
            n = os.write(fd, data)
        except InterruptedError:
            continue
        except OSError:
            return
        data = data[n:]


def _drain_socket(sock):
    buf = b""
    while True:
        try:
            chunk = sock.recv(65536)
        except OSError:
            break
        if not chunk:
            break
        buf += chunk
    return buf


# =============================================================== daemon side

def _recv_request(conn):
    """Receive a length-prefixed JSON request plus stdio fds via SCM_RIGHTS.

    Returns ``(request_dict, fds, leftover)``. ``leftover`` is any bytes
    the client had already queued past the declared request length (for
    example an early-forwarded signal frame) so the caller can feed it
    back into the signal-relay buffer instead of silently dropping it or
    letting it corrupt the JSON parse below.
    """
    conn.settimeout(REQUEST_RECV_TIMEOUT_SEC)
    fds = array.array("i")
    cmsg_space = socket.CMSG_SPACE(3 * fds.itemsize)
    msg, anc, _flags, _addr = conn.recvmsg(65536, cmsg_space)
    for level, ctype, data in anc:
        if level == socket.SOL_SOCKET and ctype == socket.SCM_RIGHTS:
            fds.frombytes(data[: len(data) - (len(data) % fds.itemsize)])
    if len(msg) < 4:
        raise ValueError("short request header")
    (length,) = struct.unpack("!I", msg[:4])
    if length > MAX_REQUEST_BYTES:
        # A caller can connect and send an arbitrary length prefix (e.g.
        # 0xffffffff) with no body. Without this bound the forked
        # supervisor blocks in recv() for a body that may never arrive,
        # tying up process resources indefinitely.
        raise ValueError("request too large (%d bytes)" % length)
    # `msg` can contain more than just the declared request: a client
    # that forwards a signal immediately after sending the request can
    # have both queued together in the same recvmsg() read. Cap `body` to
    # exactly `length` bytes so trailing signal-frame bytes don't get
    # parsed as (invalid) JSON, and return them as `leftover` instead.
    body = msg[4:4 + length]
    while len(body) < length:
        more = conn.recv(length - len(body))
        if not more:
            raise ValueError("client closed before sending full request")
        body += more
    leftover = msg[4 + length:]
    conn.settimeout(None)
    return json.loads(body.decode("utf-8")), list(fds), leftover


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
    """Best-effort only -- see the "Known limitations" note in
    cli-daemon.md. ``setsid()`` leaves this child with no controlling
    terminal of its own; ``TIOCSCTTY`` with arg ``0`` claims the inherited
    stdin as one, but *only* succeeds if that terminal isn't already the
    controlling terminal of another session. For a normal interactive
    SSH/console session it always already is -- the caller's own login
    shell -- so this reliably no-ops (``EPERM``, caught below) for the
    primary use case, not just for piped/non-interactive invocations.

    Passing arg ``1`` would force the steal and make it "work", but that
    forcibly evicts the *caller's own shell* as that terminal's
    controlling session -- actively breaking the user's own login
    session's job control just to make one warm command's pager slightly
    more correct. That tradeoff is not worth it, so this stays a
    best-effort no-op rather than "fixed" via a steal.
    """
    try:
        import fcntl
        import termios

        fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    except OSError:
        pass


def _open_pty(spec, uid):
    """Allocate a pty for the command child and mirror the caller's terminal settings onto it.
    Returns ``(master, slave)``; raises OSError if no pty can be allocated."""
    import fcntl
    import termios

    master, slave = os.openpty()
    try:
        attrs = spec.get("termios")
        if attrs:
            iflag, oflag, cflag, lflag, ispeed, ospeed, cc = attrs
            canon = bool(lflag & termios.ICANON)
            cc = [bytes([v]) if (canon or i not in (termios.VMIN, termios.VTIME)) else v
                  for i, v in enumerate(cc)]
            termios.tcsetattr(slave, termios.TCSANOW, [iflag, oflag, cflag, lflag, ispeed, ospeed, cc])
    except (termios.error, OSError, ValueError, TypeError):
        pass
    try:
        size = spec.get("winsize")
        if size:
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", *size))
    except (OSError, struct.error, TypeError):
        pass
    try:
        # What grantpt() does for a login: the caller owns the terminal it is typing into.
        os.fchown(slave, uid, -1)
    except OSError:
        pass
    return master, slave


def _send_pty_status(conn, master):
    """First reply of a pty-mode request: ``{"pty": true}`` + the master fd, or ``{"pty": false}``."""
    line = json.dumps({"pty": master is not None}).encode("utf-8") + b"\n"
    anc = []
    if master is not None:
        anc.append((socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", [master])))
    conn.sendmsg([line], anc)


def _adopt_pty(slave, mask):
    """Make the fresh pty the child's controlling terminal and its stdio for every caller fd
    that was a terminal. Must run after ``setsid()`` (a session leader without a controlling tty
    can claim an unowned pty with ``TIOCSCTTY``)."""
    import fcntl
    import termios

    for fd, is_tty in enumerate(mask[:3]):
        if is_tty:
            os.dup2(slave, fd)
    if slave > 2:
        os.close(slave)
    first = next((i for i, is_tty in enumerate(mask[:3]) if is_tty), 0)
    try:
        fcntl.ioctl(first, termios.TIOCSCTTY, 0)
    except OSError:
        pass


def _run_child(req, fds, uid, gid, slave=None):
    """Runs inside the forked command child. Never returns normally."""
    # Reset signal dispositions *first*, before any other setup. This
    # process inherited the daemon's SIGHUP (re-exec self) and
    # SIGTERM/SIGINT (unlink the shared socket + exit) handlers via
    # fork(). A signal forwarded by the client and delivered before these
    # are reset would run those daemon-level actions -- re-exec or
    # unlinking the one shared socket -- inside what must behave as an
    # ordinary command process.
    signal.signal(signal.SIGINT, signal.default_int_handler)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    signal.signal(signal.SIGQUIT, signal.SIG_DFL)
    signal.signal(signal.SIGHUP, signal.SIG_DFL)
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)

    for target, fd in enumerate(fds[:3]):
        os.dup2(fd, target)
    for fd in fds:
        if fd > 2:
            os.close(fd)

    os.setsid()
    if slave is not None:
        _adopt_pty(slave, (req.get("pty") or {}).get("mask") or [])
    else:
        _acquire_controlling_tty()
    _drop_privileges(uid, gid)

    os.environ.clear()
    os.environ.update(req["env"])
    try:
        os.chdir(req["cwd"])
    except OSError as exc:
        # Unlike the cold path (which just inherits the shell's real cwd
        # by virtue of a normal fork+exec and never hits this), this
        # warm child starts in the *daemon's* directory and must
        # explicitly switch. Continuing on failure would silently run
        # the command against the wrong directory -- any relative file
        # argument could then read or write a different path than the
        # caller intended. Fail loudly instead.
        os.write(
            2,
            ("cli daemon: cannot chdir to %r: %s\n" % (req["cwd"], exc)).encode("utf-8", "replace"),
        )
        os._exit(1)

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
        req, fds, sig_buf = _recv_request(conn)
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

    slave = None
    if req.get("pty"):
        # Pty mode: the child's terminal is a fresh pty, whose master goes back to the client
        # (it proxies the real terminal to it). Done before fork so a failure is still
        # reportable and before any command runs.
        try:
            master, slave = _open_pty(req["pty"], uid)
        except OSError:
            master = None
        try:
            _send_pty_status(conn, master)
        except OSError:
            _safe_close(master)
            _safe_close(slave)
            for fd in fds:
                _safe_close(fd)
            conn.close()
            return
        # The client owns the only master now: when it goes away the child sees a hangup,
        # exactly like a command whose ssh session dropped.
        _safe_close(master)

    pipe_r, pipe_w = os.pipe()

    def _on_sigchld(_signum, _frame):
        try:
            os.write(pipe_w, b"x")
        except OSError:
            pass

    # Install the handler *before* forking. A child that exits quickly
    # (e.g. `show --help`) can otherwise deliver SIGCHLD into the gap
    # between fork() and installing the handler; with no handler
    # registered yet, that delivery is lost (default disposition for
    # SIGCHLD is to discard it) and the select() loop below would wait
    # forever even though waitpid() could reap the already-dead child
    # right away.
    prev_sigchld = signal.signal(signal.SIGCHLD, _on_sigchld)

    child = os.fork()
    if child == 0:
        os.close(pipe_r)
        os.close(pipe_w)
        conn.close()
        _run_child(req, fds, uid, gid, slave)
        os._exit(1)  # unreachable

    _safe_close(slave)
    for fd in fds:
        _safe_close(fd)

    # Flush any signal frame the client had already queued right behind
    # the request itself (see `_recv_request`'s `leftover`) now that the
    # child exists to receive it -- otherwise it sits in the buffer
    # unprocessed until the connection eventually closes.
    sig_buf = _relay_signals(sig_buf, b"", child)

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
                sig_buf = _relay_signals(sig_buf, data, child)
    finally:
        signal.signal(signal.SIGCHLD, prev_sigchld)
        os.close(pipe_r)
        os.close(pipe_w)

    try:
        conn.sendall(json.dumps({"exit_code": exit_code}).encode("utf-8") + b"\n")
    except OSError:
        pass
    conn.close()


def _relay_signals(buf, data, child):
    """Parse complete newline-delimited signal frames out of ``buf + data``,
    forwarding each to the child. Returns the remaining buffer, which may
    hold a not-yet-complete trailing frame.

    ``recv()`` may split a frame at any byte boundary; parsing each
    received chunk independently (with no buffer carried across reads)
    and discarding whatever doesn't parse as complete JSON can silently
    drop a forwarded Ctrl-C, leaving the command running until the
    client's own timeout.
    """
    buf += data
    *complete, buf = buf.split(b"\n")
    for line in complete:
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except ValueError:
            continue
        # The client is untrusted after the request is accepted: a valid
        # JSON scalar/list (not a dict), or a non-integer "signal" value,
        # must not raise -- an uncaught AttributeError/TypeError here
        # would kill this supervisor without ever sending a response,
        # while the already-forked command child keeps running unwatched.
        sig = parsed.get("signal") if isinstance(parsed, dict) else None
        if isinstance(sig, int) and sig > 0:
            try:
                # _run_child calls setsid(), making the child its own
                # process-group leader -- signal the whole group so
                # subprocesses it spawns (e.g. commands it shells out to)
                # are terminated/interrupted too, not just the leader.
                os.killpg(child, sig)
            except OSError:
                pass
    return buf


def _reply_fallback(conn):
    """Tell the client to re-run on the cold path, then close cleanly.

    Closing a Unix socket that still holds *unread* data (the client's
    request, sent before we read it) resets the peer: its ``recv`` fails
    with ECONNRESET and the fallback line is lost -- the client would then
    see "no reply" and, for non-idempotent ``config``, report failure.
    So half-close our side (client reads the reply, then EOF) and swallow
    whatever the client had already queued before the final close().
    """
    try:
        conn.settimeout(0.5)
        conn.sendall(b'{"fallback": true}\n')
        conn.shutdown(socket.SHUT_WR)
        while conn.recv(65536):
            pass
    except OSError:
        pass
    try:
        conn.close()
    except OSError:
        pass


def _safe_close(fd):
    if fd is None:
        return
    try:
        os.close(fd)
    except OSError:
        pass


# --------------------------------------------------------- staleness / re-exec

def _module_file(modname):
    mod = sys.modules.get(modname)
    return getattr(mod, "__file__", None) if mod else None


def _plugin_dirs():
    """Directories the CLI trees discover plugins from at import time
    (``show/plugins``, ``config/plugins``): hand-installed files and the
    ones sonic-package-manager extracts for extensions end up here."""
    dirs = []
    for modname, _attr in PROG_LOADERS.values():
        pkg = sys.modules.get(modname.rsplit(".", 1)[0] + ".plugins")
        for path in getattr(pkg, "__path__", []) or []:
            if os.path.isdir(path):
                dirs.append(path)
    return dirs


def _snapshot_watch_mtimes():
    mtimes = {}
    for modname, _attr in PROG_LOADERS.values():
        path = _module_file(modname)
        if path and os.path.exists(path):
            mtimes[path] = os.stat(path).st_mtime
    # Plugins are discovered once at import, so installing/upgrading/removing
    # one (e.g. a sonic-package-manager extension) is invisible to the warm
    # daemon. A directory's mtime moves when entries are added or removed;
    # each plugin file's own mtime catches in-place upgrades.
    for pdir in _plugin_dirs():
        mtimes[pdir] = os.stat(pdir).st_mtime
        for entry in os.listdir(pdir):
            if entry.endswith(".py"):
                fpath = os.path.join(pdir, entry)
                try:
                    mtimes[fpath] = os.stat(fpath).st_mtime
                except OSError:
                    pass
    return mtimes


def _watch_mtimes_changed():
    for path, recorded in _watch_mtimes.items():
        try:
            if os.stat(path).st_mtime != recorded:
                return True
        except OSError:
            return True
    return False


def _set_socket_permissions(sock_path):
    """Group-restrict the socket as defense-in-depth on top of the real
    authorization mechanism (SO_PEERCRED + setuid in the child, see
    cli-daemon.md). 0660 + a group instead of 0666 also keeps a generic
    "insecure file permissions" scanner from treating this like a normal
    world-writable file it isn't -- Unix sockets need write access to
    connect() at all, so 0644 would break every non-root client outright.
    """
    # This is a Unix domain socket, not a regular file: connect() requires
    # write permission on the path, so any mode that lets non-root clients
    # reach the daemon at all necessarily sets a group/other write bit,
    # which this generic rule can't distinguish from an unsafe world-
    # writable data file. The real authorization check is SO_PEERCRED +
    # setuid in the forked child (see cli-daemon.md); this chmod is
    # defense-in-depth, not the security boundary.
    os.chmod(sock_path, 0o660)  # nosemgrep: python.lang.security.audit.insecure-file-permissions.insecure-file-permissions
    group = os.environ.get("SONIC_CLI_SOCKET_GROUP", "admin")
    try:
        gid = grp.getgrnam(group).gr_gid
        os.chown(sock_path, os.getuid(), gid)
    except (KeyError, OSError) as exc:
        # If the group doesn't exist on this image (or chown fails for
        # any other reason), the socket is left owned by root:root at
        # 0660 -- unreachable by any non-root caller. That's safe (a
        # client just sees connect() fail and falls back to the cold
        # path), but silently swallowing it here means the daemon stops
        # accelerating anything for regular users with zero diagnostic.
        syslog.syslog(
            syslog.LOG_WARNING,
            "sonic-cli-daemon: could not restrict socket %s to group %r (%s); "
            "non-root clients will be unable to reach the daemon and will "
            "always use the cold-start path" % (sock_path, group, exc),
        )


_server = None  # the listening socket, once bound (see _retire_listener)


def _retire_listener():
    """Stop accepting without resetting clients that are already queued.

    ``execv`` / process exit close the listening socket, and the kernel
    resets every connection still sitting in its accept backlog. A client
    that connected and sent its request in that window sees an empty reply
    and (because ``config`` is not idempotent) must report failure -- even
    though nothing ran. So: unlink the path first (new clients get ENOENT
    and take the cold path), then answer everything already queued with
    ``fallback`` (the client re-runs on the cold path), then close.
    """
    server = _server
    try:
        os.unlink(SOCKET_PATH)
    except OSError:
        pass
    if server is None:
        return
    try:
        server.setblocking(False)
        while True:
            conn, _addr = server.accept()
            conn.setblocking(True)
            conn.settimeout(1.0)
            _reply_fallback(conn)
    except (BlockingIOError, InterruptedError):
        pass
    except OSError:
        pass
    try:
        server.close()
    except OSError:
        pass


def _reexec_self(reason="reload"):
    """Re-exec the daemon process in place.

    Used both when ``show.main``/``config.main``/a plugin changed on disk
    (package upgrade, extension install) and on SIGHUP. SIGHUP is the
    trigger for show/main.py's import-time BGP routing-stack probe: if the
    BGP container was still starting when the daemon booted, ``show ip bgp``
    is unavailable until something re-triggers that probe. Re-importing
    show.main from scratch reruns the probe against current container state.

    In-flight commands are unaffected -- they already forked and hold
    their own copy of the previously loaded code.

    A caught signal reverts to its default disposition across ``execv``,
    and SIGHUP's default is "terminate" -- which systemd counts as a clean
    exit, so ``Restart=on-failure`` would NOT bring the daemon back. An
    *ignored* disposition survives exec, so ignore SIGHUP here; the new
    image installs its own handler first thing in ``run_daemon_main``.
    """
    syslog.syslog(syslog.LOG_INFO, "sonic-cli-daemon: re-exec (%s)" % reason)
    _retire_listener()
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    os.execv(sys.argv[0], sys.argv)


# ==================================================================== daemon

def run_daemon_main():
    """Entry point for the ``sonic-cli-daemon`` console script."""
    global _server

    # Signals only record what was asked (``actions``); the main loop acts on
    # it at a safe point, never while holding an accepted-but-unserved
    # connection. The SIGHUP handler is installed BEFORE the (multi-second on
    # this CPU) show/config imports: a reload requested while we are still
    # starting up (e.g. `systemctl reload` right after a restart, or the
    # bgp.service reload hook) used to hit the default disposition and kill
    # the daemon for good (systemd treats death-by-SIGHUP as a clean exit).
    actions = []
    signal.signal(signal.SIGHUP, lambda _s, _f: actions.append("reload"))

    for prog, (modname, attr) in PROG_LOADERS.items():
        mod = __import__(modname, fromlist=[attr])
        _clis[prog] = getattr(mod, attr)
    _watch_mtimes.update(_snapshot_watch_mtimes())

    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)
    os.makedirs(os.path.dirname(SOCKET_PATH), mode=0o755, exist_ok=True)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    _set_socket_permissions(SOCKET_PATH)
    server.listen(64)
    server.setblocking(False)
    _server = server

    with open(PID_PATH, "w") as pid_file:
        pid_file.write(str(os.getpid()))

    # Wake select() on any signal without polling.
    wake_r, wake_w = os.pipe()
    os.set_blocking(wake_r, False)
    os.set_blocking(wake_w, False)
    signal.set_wakeup_fd(wake_w)

    def _reap_supervisors(_signum, _frame):
        while True:
            try:
                pid, _status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                break
            if pid == 0:
                break

    signal.signal(signal.SIGCHLD, _reap_supervisors)
    signal.signal(signal.SIGTERM, lambda _s, _f: actions.append("shutdown"))
    signal.signal(signal.SIGINT, lambda _s, _f: actions.append("shutdown"))

    while True:
        if actions:
            action = actions[0]
            if action == "shutdown":
                _retire_listener()
                sys.exit(0)
            _reexec_self("SIGHUP")

        try:
            readable, _, _ = select.select([server, wake_r], [], [])
        except InterruptedError:
            continue
        if wake_r in readable:
            try:
                os.read(wake_r, 4096)
            except OSError:
                pass
        if server not in readable:
            continue

        try:
            conn, _addr = server.accept()
        except (BlockingIOError, InterruptedError):
            continue
        except OSError:
            break
        conn.setblocking(True)

        if _watch_mtimes_changed():
            # Code (or a plugin) changed on disk since we loaded it
            # (upgrade / extension install). Refuse this one connection with
            # fallback and restart with fresh code; the client falls back to
            # its own cold-start path.
            _reply_fallback(conn)
            _reexec_self("watched file changed")
            continue  # unreachable after execv

        pid = os.fork()
        if pid == 0:
            # Supervisor: drop the daemon's loop state. Its signal handlers
            # only append to the daemon's `actions` list and would otherwise
            # make SIGTERM/SIGHUP no-ops here; the wakeup pipe belongs to
            # the daemon.
            signal.set_wakeup_fd(-1)
            signal.signal(signal.SIGHUP, signal.SIG_DFL)
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
            signal.signal(signal.SIGINT, signal.default_int_handler)
            os.close(wake_r)
            os.close(wake_w)
            server.close()
            _serve_request(conn)
            os._exit(0)
        conn.close()


if __name__ == "__main__":
    run_daemon_main()

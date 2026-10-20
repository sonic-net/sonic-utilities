# SONiC CLI warm daemon

Optional `systemd` service that keeps `show` and `config` Click trees loaded
and accelerates **both** command execution and Tab completion:

- **Enable switch:** `OPTIMIZE_CLI` -- a sonic-buildimage build flag
  (`rules/config`, default `n`). It is read at **package build time**, not
  runtime: when not `y`, `setup.py` excludes `show/cli_entry.py`,
  `config/cli_entry.py`, `utilities_common/cli_server.py` and their test
  module from the build entirely, `show`/`config` console scripts point
  straight at `show.main:cli` / `config.main:config` as before this
  feature existed, and `sonic-utilities-data/debian/rules` drops the
  `sonic-cli-daemon.service` unit and this doc from the data package. A
  default build therefore ships none of this code. Set `OPTIMIZE_CLI = y`
  in a profile (e.g. `rules/config.EMBEDDED`) to build it in.
- **Service:** `sonic-cli-daemon.service` (enabled with `sonic.target`)
- **Socket:** `/run/sonic/cli.sock`
- **Disable client for one session:** `SONIC_CLI_DAEMON=0`, even when
  `OPTIMIZE_CLI` is on fleet-wide
- **Fallback:** only available if `connect()` itself fails (daemon
  stopped or socket missing) -- in that case the client uses the normal
  cold Python path. Any failure from that point on, including a
  connection drop *during* transmission, is fatal: it returns exit code
  `1` rather than falling back. A request that has started being sent is
  never re-run -- `config` commands are not idempotent and must never
  run twice.

## What actually gets faster

Unlike the earlier Tab-only completion daemon, **command execution itself**
is accelerated: `show version`, `config …`, etc. all run inside a forked
child of the already-warm daemon instead of cold-starting Python and
reimporting `click`/`swsscommon`/the ~100 `show`/`config` submodules on
every invocation.

## Security model

The daemon runs as root and forks a child per request. That child:

1. Receives the caller's real stdin/stdout/stderr file descriptors via
   `SCM_RIGHTS`, so output streams to the caller's actual terminal
   (colors, `isatty()`, and prompts that just read/write those fds all
   work as they do today). When any of them is a terminal, the child gets
   a fresh pty instead -- see "Terminal handling" below.
2. Reads the caller's real uid/gid from `SO_PEERCRED` -- this is filled in
   by the kernel from the actual connecting process's credentials and
   **cannot be spoofed** by anything in the request payload.
3. If the daemon is root and the caller is not, the child drops
   privileges (`initgroups` + `setgid` + `setuid`) to the caller's uid/gid
   **before** running the command.

This does not add new trust logic: `config.main`'s existing
`os.geteuid() != 0` check still runs inside the child exactly as it does
today. A non-root caller without `sudo` still gets rejected by that
existing check; `sudo config …` still works because the connecting
process already has uid 0 by the time it talks to the daemon, so no
privilege drop happens and the existing check passes.

The socket itself is `0660`, owned by group `admin` (override via
`SONIC_CLI_SOCKET_GROUP`). This is defense-in-depth on top of the real
authorization mechanism, which is `SO_PEERCRED` + `setuid` in the child,
not the socket's filesystem permissions -- a caller connecting at all
still gets checked and dropped to their real uid/gid before anything
runs.

## Terminal handling (pty mode)

The forked child calls `setsid()` (so the whole command can be signalled as
one process group), which leaves it without a controlling terminal, and the
caller's terminal cannot be adopted: it already belongs to the caller's
login session, and forcing `TIOCSCTTY` would evict the user's shell. Passing
only the stdio fds therefore broke everything that needs a *controlling*
terminal: `/dev/tty` (sudo/`getpass` password prompts, `ssh`), tty-generated
signals (`SIGWINCH`, Ctrl-Z) and job control -- a pager left behind by
Ctrl-Z kept reading the shell's keystrokes.

So when any of the caller's stdin/stdout/stderr is a terminal, the daemon
works like `docker exec -t` / `ssh -t`:

- the supervisor allocates a **new pty**, copies the caller's termios
  settings and window size onto it, and hands the master end to the client
  (`SCM_RIGHTS`);
- the command child `setsid()`s and claims the new pty as its controlling
  terminal (`TIOCSCTTY` works on an unowned pty); its stdio is that pty
  wherever the caller's was a terminal (redirected streams still use the
  caller's own fds);
- the client puts the real terminal in raw mode and proxies bytes both ways,
  propagates `SIGWINCH` (window size), and restores the terminal on exit;
- Ctrl-C reaches the command through the pty (`SIGINT` to its foreground
  group) exactly as in a login; Ctrl-Z is recognised by the client, which
  stops the command's group, restores the terminal and stops itself, so the
  shell shows `Stopped` and `fg`/`bg` work;
- if the client goes away (ssh drop) the pty hangs up and the command gets
  `SIGHUP`, like a command whose terminal closed.

Set `SONIC_CLI_DAEMON_PTY=0` to fall back to plain fd passing without the
pty. Non-terminal callers never use the pty path.

## Known limitations

- **Import-time state (BGP routing stack, plugins) and how it is refreshed.**
  `show/main.py` decides once, at import time, whether to wire up FRR or
  Quagga `show ip bgp` commands (`sudo docker ps` probe), and `show`/`config`
  discover their plugins (`show/plugins`, `config/plugins`, including the
  ones sonic-package-manager extracts for extensions) once at import. The
  daemon imports once, so anything derived then would otherwise be frozen.
  It is refreshed automatically:
  - **bgp container (re)appears:** the shipped `bgp.service` drop-in
    (`10-sonic-cli-daemon.conf`, `ExecStartPost`) asks the daemon to reload
    every time `bgp.service` starts -- boot, `config feature state bgp
    enabled`, `systemctl restart bgp`. The reload is a SIGHUP re-exec, so the
    probe re-runs against the container that now exists. (An
    `After=bgp.service` ordering on the daemon unit was tried and not kept:
    the hook already covers cold boot, and the ordering delays the warm CLI
    by about two minutes.)
  - **plugins installed/upgraded/removed:** the daemon also watches the
    plugin directories (directory mtime plus each plugin file's mtime), in
    addition to `show/main.py` and `config/main.py`. On the next request it
    answers that one request with "fallback" (cold path) and re-execs.
  - **manually:** `systemctl reload sonic-cli-daemon` (SIGHUP) at any time.
    A reload that arrives while the daemon is still importing at startup is
    remembered and applied once it is listening (it no longer kills it).
  While the daemon re-execs, new clients get a missing socket or an
  explicit "fallback" and run on the cold path; they never fail. Each
  re-exec is logged to syslog (`sonic-cli-daemon: re-exec (<reason>)`).
  Multi-asic `bgp@N.service` instances are not covered by the drop-in.
- **Zombie reaping** relies on a `SIGCHLD` handler in the top-level daemon
  process; if you extend this code, keep that handler in place.
- **sudo's credential cache is per terminal.** In pty mode the command
  runs on its own pty, so a `sudo -v` done earlier in the login shell does
  not carry over: a user whose sudoers entry is *not* `NOPASSWD` is asked
  for the password by each command that runs `sudo` internally (cold path:
  only the first time within the `sudo` timeout). The default `admin`
  account is `NOPASSWD: ALL` and is not affected.
- **After Ctrl-Z/`fg` a pager is not redrawn** until a key is pressed
  (the pager is stopped with `SIGSTOP`, so it does not see `SIGTSTP`).
- **Terminal-less callers keep the old behavior.** If none of stdin,
  stdout and stderr is a terminal (cron, scripts, `ssh host show ...`
  without `-t`), the child still has no controlling terminal -- there is
  no terminal for it to use.

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
   work as they do today). `less`/pagers that open `/dev/tty` directly
   for job control are a partial exception -- see "Known limitations"
   below.
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

## Known limitations

- **BGP routing-stack staleness.** `show/main.py` decides once, at import
  time, whether to wire up FRR or Quagga `show ip bgp` commands (`sudo
  docker ps` probe). The daemon imports `show.main` once at startup, so if
  the BGP container was still starting when the daemon booted, `show ip
  bgp` stays unavailable until the daemon re-imports. Send `SIGHUP` to
  the daemon (or `systemctl reload sonic-cli-daemon`) after BGP comes up
  to force a clean re-exec and re-run that probe. The daemon also
  re-execs automatically if it detects `show/main.py` or `config/main.py`
  changed on disk (package upgrade).
- **Plugins installed after the daemon started** are not picked up until
  the daemon restarts/reloads, for the same reason.
- **Zombie reaping** relies on a `SIGCHLD` handler in the top-level daemon
  process; if you extend this code, keep that handler in place.
- **Pagers/prompts that open `/dev/tty` directly** (e.g. `less`) don't
  reliably get real job control. After `setsid()`, the command child has
  no controlling terminal of its own, and claiming the inherited one
  (`TIOCSCTTY`) only succeeds if it isn't already the controlling
  terminal of another session -- for a normal interactive SSH/console
  invocation it always already is (the caller's own login shell), so
  this is a best-effort no-op for exactly the common case. Forcibly
  stealing it (`TIOCSCTTY` with a nonzero arg) would "fix" this by
  evicting the caller's own shell as that terminal's controlling
  session, breaking their login session's job control to make one
  command's pager slightly more correct -- not a trade worth making. If
  a pager's behavior matters for a given invocation, disable the daemon
  for it with `SONIC_CLI_DAEMON=0`.

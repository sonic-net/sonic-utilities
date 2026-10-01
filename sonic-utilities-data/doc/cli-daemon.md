# SONiC CLI warm daemon

Optional `systemd` service that keeps `show` and `config` Click trees loaded
and accelerates **both** command execution and Tab completion:

- **Service:** `sonic-cli-daemon.service` (enabled with `sonic.target`)
- **Socket:** `/run/sonic/cli.sock`
- **Disable client:** `SONIC_CLI_DAEMON=0` for a single shell session
- **Fallback:** if the daemon is stopped, unreachable, or dies mid-command
  before responding, the client uses the normal cold Python path. If the
  daemon *had already accepted* the request when it died, the client
  returns exit code `1` instead of silently falling back and re-running --
  `config` commands are not idempotent and must never run twice.

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
   (colors, `isatty()`, interactive prompts, `less`/pagers via
   `TIOCSCTTY` all work as they do today).
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

The socket itself is `0666` -- access control is enforced by
`SO_PEERCRED` + `setuid` in the child, not by filesystem permissions on
the socket.

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

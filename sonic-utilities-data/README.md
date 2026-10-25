# sonic-utilities-data
Data files required for SONiC command line utilities


## Optional normal-stop quiescence

A service manifest may set `quiescence.command` to a container command argv list
and `quiescence.timeout` to a positive number of seconds (default: 60):

```json
{"service": {"quiescence": {"command": ["/usr/bin/example-quiesce"], "timeout": 60}}}
```

An absent or empty command preserves the generated unit and wrapper. Opted-in
systemd services run the command against their current container before the
existing stop command. Failure or timeout does not prevent that stop command.
The host bounds the action. An in-container timeout also terminates a detached
Docker exec, escalating to KILL after one second if needed; the container must
provide `/usr/bin/timeout`. These timeouts do not stop the container.
Choose a bound shorter than the service's existing systemd stop timeout.
Warm/fast reboot skips the action. Interrupted activation and direct wrapper
`stop` calls retain their existing behavior; this is not a readiness gate.

## To build

```
dpkg-buildpackage -rfakeroot -b -us -uc
```

## To clean

```
dpkg-buildpackage -rfakeroot -Tclean
```

---

See the [SONiC Website](http://azure.github.io/SONiC/) for more information about the SONiC project.

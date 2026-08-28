import subprocess
import uuid

import click

SYNCD_CONTAINER = 'syncd'
BCM_TIMEOUT_SEC = 120


def ensure_broadcom():
    from sonic_py_common import device_info

    version_info = device_info.get_sonic_version_info()
    if not version_info or version_info.get('asic_type') != 'broadcom':
        raise click.ClickException('BCM PTP CLI commands are only supported on Broadcom platforms')


def _format_bcmcmd_output(stdout, stderr):
    combined = (stdout or '') + (stderr or '')
    lines = []
    for line in combined.splitlines():
        text = line.rstrip('\r')
        if text == 'drivshell>':
            continue
        lines.append(text)
    return '\n'.join(lines).rstrip()


def run_bcmcmd(command, timeout_sec=BCM_TIMEOUT_SEC):
    """Run a bcmcmd shell command in syncd and print output."""
    ensure_broadcom()
    proc = subprocess.run(
        [
            'docker', 'exec', SYNCD_CONTAINER,
            'bcmcmd', '-t', str(timeout_sec), command,
        ],
        capture_output=True,
        text=True,
    )
    output = _format_bcmcmd_output(proc.stdout, proc.stderr)
    if output:
        click.echo(output)
    if proc.returncode != 0:
        raise click.ClickException('bcmcmd exited with status {}'.format(proc.returncode))


def run_bcm_cint(statement):
    """Run a cint statement via bcmcmd and print BCM shell output.

    Functions from cint_1step.c are loaded at syncd init by start_ptp_cint.sh
    and persist in the BCM cint environment.
    """
    ensure_broadcom()
    remote_path = '/tmp/ptp_cli_{}.cint'.format(uuid.uuid4().hex[:8])
    cint_body = statement.strip()
    if not cint_body.endswith(';'):
        cint_body += ';'
    cint_body += '\nexit;\n'

    write_cmd = ['docker', 'exec', '-i', SYNCD_CONTAINER, 'bash', '-c', 'cat > {}'.format(remote_path)]
    write_proc = subprocess.run(write_cmd, input=cint_body.encode(), capture_output=True)
    if write_proc.returncode != 0:
        err = write_proc.stderr.decode(errors='replace')
        raise click.ClickException('Failed to write cint script in syncd: {}'.format(err))

    try:
        proc = subprocess.run(
            [
                'docker', 'exec', SYNCD_CONTAINER,
                'bcmcmd', '-t', str(BCM_TIMEOUT_SEC),
                'cint {}'.format(remote_path),
            ],
            capture_output=True,
            text=True,
        )
        output = _format_bcmcmd_output(proc.stdout, proc.stderr)
        if output:
            click.echo(output)
        if proc.returncode != 0:
            raise click.ClickException('bcmcmd exited with status {}'.format(proc.returncode))
    finally:
        subprocess.run(
            ['docker', 'exec', SYNCD_CONTAINER, 'rm', '-f', remote_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

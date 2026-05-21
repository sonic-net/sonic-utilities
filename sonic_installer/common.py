"""
Module holding common functions and constants used by sonic-installer and its
subpackages.
"""

import subprocess
import sys
import signal

import click
from shlex import join
from .exception import SonicRuntimeException

HOST_PATH = '/host'
IMAGE_PREFIX = 'SONiC-OS-'
IMAGE_DIR_PREFIX = 'image-'
ROOTFS_NAME = 'fs.squashfs'
UPPERDIR_NAME = 'rw'
WORKDIR_NAME = 'work'
DOCKERDIR_NAME = 'docker'

def is_list_of_strings(command):
    return isinstance(command, list) and all(isinstance(item, str) for item in command)

# Run bash command and print output to stdout
def run_command(command, stdout=subprocess.PIPE, env=None, shell=False):
    if not is_list_of_strings(command):
        sys.exit("Input command should be a list of strings")
    if not shell:
        command_str = join(command)
    else:
        command_str = command
    click.echo(click.style("Command: ", fg='cyan') + click.style(command_str, fg='green'))

    proc = subprocess.Popen(command, text=True, stdout=stdout, env=env, shell=shell)
    (out, _) = proc.communicate()

    click.echo(out)

    if proc.returncode != 0:
        sys.exit(proc.returncode)

# Run bash command and return output, raise if it fails
def run_command_or_raise(argv, raise_exception=True, capture=True):
    click.echo(click.style("Command: ", fg='cyan') + click.style(' '.join(argv), fg='green'))

    stdout = subprocess.PIPE if capture else None
    proc = subprocess.Popen(argv, text=True, stdout=stdout)
    out, err = proc.communicate()

    if proc.returncode != 0 and raise_exception:
        sre = SonicRuntimeException("Failed to run command '{0}'".format(argv))
        if out:
            sre.add_note("\nSTDOUT:\n{}".format(out.rstrip("\n")))
        if err:
            sre.add_note("\nSTDERR:\n{}".format(err.rstrip("\n")))
        raise sre

    if out is not None:
        out = out.rstrip("\n")

    return out

# Needed to prevent "broken pipe" error messages when piping
# output of multiple commands using subprocess.Popen()
def default_sigpipe():
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)


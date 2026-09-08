#!/usr/bin/env python3
#
# Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES.
# Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

#
# main.py
#
# Specific command-line utility for Nvidia-bluefield platform
#

try:
    import click
    import os
    import sys
    from pathlib import Path
    import datetime
    import syslog
    from sonic_py_common import device_info
    from utilities_common.auto_techsupport_helper import get_stats, pretty_size
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))

SYNCD_CONTAINER_NAME = 'syncd'
NASA_CLI = '/usr/sbin/cli/nasa_cli.py -u --exit_on_failure'
NASA_CLI_CMD_F = '/tmp/nasa_cli_cmd.txt'
CFG_REC_CMD_PREFIX = 'set_sai_debug_mode'
PKT_REC_CMD_PREFIX = 'set_packet_debug_mode'

SAI_PROFILE_FILE = '/tmp/sai.profile'
SAI_KEY_DUMP_STORE_PATH = 'SAI_DUMP_STORE_PATH'
SAI_KEY_DUMP_STORE_COUNT = 'SAI_DUMP_STORE_AMOUNT'
CFG_REC_DIR = "config-record"
PKT_REC_DIR = "packet-drop"

# SDK techsupport CT dump sentinel path. Keep in sync across:
#   sonic-utilities/config/plugins/nvidia_bluefield.py (SDK_TECHSUPPORT_CT_DUMP_SENTINEL)
#   sonic-utilities/scripts/generate_dump (sdk_techsupport_ct_dump_sentinel)
#   sonic-sairedis/syncd/scripts/syncd_init_common.sh (config_syncd_nvidia_bluefield)
SDK_TECHSUPPORT_CT_DUMP_RUN_DIR = '/var/run/sonic-platform-nvidia-bluefield'
SDK_TECHSUPPORT_CT_DUMP_SENTINEL = f'{SDK_TECHSUPPORT_CT_DUMP_RUN_DIR}/sdk-techsupport-ct-dump.enabled'


def is_sdk_techsupport_ct_dump_enabled(docker_client):
    """Probe whether SDK CT dumps are enabled for techsupport.

    The probe command succeeds (rc == 0) whenever it runs in syncd, and prints
    the current state, so a missing sentinel (disabled) is distinguished from a
    failed probe (syncd unreachable / exec error).

    Returns:
        tuple: (rc, enabled) where rc is the probe return code. ``enabled`` is a
        bool that is only meaningful when rc == 0; it is None on probe failure.
    """
    rc, stdout = run_in_syncd(
        f"sh -c 'if [ -f {SDK_TECHSUPPORT_CT_DUMP_SENTINEL} ]; then echo enabled; else echo disabled; fi'",
        docker_client)

    if rc != 0:
        return rc, None

    return rc, stdout.strip() == 'enabled'


def set_sdk_techsupport_ct_dump_state(state, docker_client):
    """Enable or disable SDK CT dumps in techsupport via sentinel file."""
    if state == 'enabled':
        cmd = (
            f"sh -c 'mkdir -p {SDK_TECHSUPPORT_CT_DUMP_RUN_DIR} && "
            f"touch {SDK_TECHSUPPORT_CT_DUMP_SENTINEL}'"
        )
    else:
        cmd = f"sh -c 'rm -f {SDK_TECHSUPPORT_CT_DUMP_SENTINEL}'"

    return run_in_syncd(cmd, docker_client)


def run_in_syncd(cmd, docker_client):
    """Run a command in the syncd container using Docker Python SDK.

    Args:
        cmd (str): Command to run in the container
        docker_client (docker.client.DockerClient): Docker client

    Returns:
        tuple: (return_code, stdout)
    """
    try:
        container = docker_client.containers.get(SYNCD_CONTAINER_NAME)
        exit_code, output = container.exec_run(cmd)
        return exit_code, output.decode('utf-8')
    except Exception as e:
        click.echo(f"Error executing command in syncd container: {str(e)}", err=True)
        return 1, str(e)


def run_nasa_cli(cmd, docker_client):
    """Run a command in the syncd container using NASA CLI

    Args:
        cmd (str): Command to run in the container
            Eg: set_packet_debug_mode on filepath /tmp/nasa_pkt_record.bin
            Eg: set_sai_debug_mode on filepath /tmp/nasa_cfg_record.bin
        docker_client (docker.client.DockerClient): Docker client

    Returns:
        tuple: (return_code, stdout)
    """
    # First create a temp file in the container

    lines = [cmd + '\n', 'quit\n']
    command = f"sh -c 'echo -n \"{''.join(lines)}\" > {NASA_CLI_CMD_F}'"
    rc, stdout = run_in_syncd(command, docker_client)

    if rc != 0:
        return rc, stdout

    cmd = f"{NASA_CLI} -l {NASA_CLI_CMD_F}"
    return run_in_syncd(cmd, docker_client)


def rotate_dump_files(path, max_count):
    """Rotate dump files in the given directory

    If the number of dump files in the directory is greater than the or equal to the count,
    the oldest file is deleted.

    Args:
        path (str): Directory to rotate dump files. Should be accessible from the host
        max_count (int): Max number of dump files to keep
        docker_client (docker.client.DockerClient): Docker client

    Returns:
        None
    """
    fs_stats, num_bytes = get_stats(os.path.join(path, "*"))
    syslog.syslog(syslog.LOG_INFO, f"Logrotate: Current size of the directory {path} : {pretty_size(num_bytes)}")

    # If number of files exceeds count, delete the oldest ones
    num_delete = len(fs_stats) - max_count
    while num_delete >= 0:
        stat = fs_stats.pop()
        os.remove(stat[2])
        num_delete -= 1
        syslog.syslog(syslog.LOG_INFO, f"Logrotate: Deleted {stat[2]}, size: {pretty_size(stat[1])}")

    return


def get_location_details(docker_client):
    """Get the dump details from the sai.profile file

    Args:
        docker_client (docker.client.DockerClient): Docker client

    Returns:
        tuple: (path, count)
    """
    path_root = get_sai_profile_value(SAI_KEY_DUMP_STORE_PATH, docker_client)
    count = get_sai_profile_value(SAI_KEY_DUMP_STORE_COUNT, docker_client)

    if not Path(path_root).exists():
        click.echo(f"Directory {path_root} does not exist", err=True)
        return (None, None)

    try:
        count = int(count)
    except ValueError as e:
        click.echo(f"Invalid count value: {count}, error: {e}", err=True)
        return (path_root, None)

    return path_root, count


def cleanup_dump_files(path_root, count, dir_name):
    """Cleanup dump files in the given directory"""
    if path_root is None or count is None:
        return
    path = os.path.join(path_root, dir_name)
    Path(path).mkdir(parents=True, exist_ok=True)
    rotate_dump_files(path, count)


def parse_nasa_output(output, mode_type):
    """Parse NASA CLI output to determine status and filename"""
    if not output:
        return "disabled", None

    lines = output.splitlines()
    filename = None

    for line in lines:
        line = line.strip()

        # Look for filename line (format: "filename: /path/to/file.bin")
        if line.startswith("filename:"):
            filename = line.split(":", 1)[1].strip()
            break

    return "enabled" if filename else "disabled", filename


def get_packet_debug_mode(docker_client):
    """Get packet debug mode status"""
    try:
        rc, output = run_nasa_cli("get_packet_debug_mode", docker_client)
        if rc != 0:
            print(f"Error querying packet debug mode: \n {output}", file=sys.stderr)
            return "disabled", None

        status, filename = parse_nasa_output(output, "packet")
        return status, filename

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return "disabled", None


def get_sai_debug_mode(docker_client):
    """Get SAI debug mode status"""
    try:
        rc, output = run_nasa_cli("get_sai_debug_mode", docker_client)
        if rc != 0:
            print(f"Error querying SAI debug mode: \n {output}", file=sys.stderr)
            return "disabled", None

        status, filename = parse_nasa_output(output, "sai")
        return status, filename

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return "disabled", None


def get_sai_profile_value(key, docker_client):
    """Get value for a given key from /tmp/sai.profile file in syncd container.

    Args:
        key (str): Key to look up in the profile file
        docker_client (docker.client.DockerClient): Docker client

    Returns:
        str: Value for the given key, or None if not found
    """
    cmd = f"cat {SAI_PROFILE_FILE}"
    rc, out = run_in_syncd(cmd, docker_client)

    if rc == 0 and out:
        for line in out.splitlines():
            if line.startswith(f"{key}="):
                return line.split('=', 1)[1]
    return ""


@click.group()
def nvidia_bluefield():
    """NVIDIA BlueField platform configuration tasks"""
    pass


@nvidia_bluefield.group('sdk')
def sdk():
    """SDK related configuration"""
    pass


@sdk.command('packet-drop')
@click.argument('state', type=click.Choice(['enabled', 'disabled']))
def packet_drop(state):
    """Enable or disable packet drop recording"""
    import docker
    docker_client = docker.from_env()
    # check if the packet drop recording is already enabled
    status, filename = get_packet_debug_mode(docker_client)
    if status == 'enabled' and state == 'enabled':
        click.echo(f"Packet drop recording is already enabled on {filename}")
        sys.exit(0)
    elif status == 'disabled' and state == 'disabled':
        click.echo("Packet drop recording is already disabled")
        sys.exit(0)

    if state == 'disabled':
        rc, _ = run_nasa_cli(PKT_REC_CMD_PREFIX, docker_client)
        if rc == 0:
            click.echo(f"Packet drop recording {state}.")
        return rc

    path_root, count = get_location_details(docker_client)

    if path_root is None or count is None:
        click.echo("Could not enable packet drop recording, dump directory not configured", err=True)
        sys.exit(-1)

    cleanup_dump_files(path_root, count, PKT_REC_DIR)
    path = os.path.join(path_root, PKT_REC_DIR)

    # create the bin file under the path path with timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bin_path = os.path.join(path, f"pkt_dump_record_{timestamp}.bin")
    os.mknod(bin_path)

    cmd = f"{PKT_REC_CMD_PREFIX} on filepath {bin_path}"
    rc, stdout = run_nasa_cli(cmd, docker_client)
    if rc != 0:
        click.echo(f"Could not enable packet drop recording: {stdout}", err=True)
    else:
        syslog.syslog(syslog.LOG_NOTICE, f"Packet drop recording enabled on {bin_path}")
        click.echo(f"Packet drop recording {state} on {bin_path}.")

    sys.exit(rc)


@sdk.command('config-record')
@click.argument('state', type=click.Choice(['enabled', 'disabled']))
def config_record(state):
    """Enable or disable configuration recording"""
    import docker
    docker_client = docker.from_env()
    # check if the packet drop recording is already enabled
    status, filename = get_sai_debug_mode(docker_client)
    if status == 'enabled' and state == 'enabled':
        click.echo(f"Packet drop recording is already enabled on {filename}")
        sys.exit(0)
    elif status == 'disabled' and state == 'disabled':
        click.echo("Packet drop recording is already disabled")
        sys.exit(0)

    if state == 'disabled':
        rc, _ = run_nasa_cli(CFG_REC_CMD_PREFIX, docker_client)
        if rc == 0:
            click.echo(f"Config recording {state}.")
        return rc

    path_root, count = get_location_details(docker_client)

    if path_root is None or count is None:
        click.echo("Could not enable config recording, dump directory/count not configured", err=True)
        sys.exit(-1)

    cleanup_dump_files(path_root, count, CFG_REC_DIR)
    path = os.path.join(path_root, CFG_REC_DIR)

    # create the bin file under the path path with timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bin_path = os.path.join(path, f"cfg_record_{timestamp}.bin")
    os.mknod(bin_path)

    cmd = f"{CFG_REC_CMD_PREFIX} on filepath {bin_path}"
    rc, stdout = run_nasa_cli(cmd, docker_client)
    if rc != 0:
        click.echo(f"Could not enable config recording: {stdout}", err=True)
    else:
        syslog.syslog(syslog.LOG_NOTICE, f"Config recording enabled on {bin_path}")
        click.echo(f"Config recording {state} on {bin_path}.")

    sys.exit(rc)


@sdk.command('techsupport-ct-dump')
@click.argument('state', type=click.Choice(['enabled', 'disabled']))
def techsupport_ct_dump(state):
    """Enable or disable SDK Connection Table dumps in techsupport"""
    import docker
    docker_client = docker.from_env()

    rc, ct_dump_enabled = is_sdk_techsupport_ct_dump_enabled(docker_client)
    if rc != 0:
        click.echo(
            "Could not probe SDK Connection Table dump state in techsupport "
            f"(syncd error, rc={rc})", err=True)
        sys.exit(rc)

    if ct_dump_enabled and state == 'enabled':
        click.echo("SDK Connection Table dump in techsupport is already enabled")
        sys.exit(0)
    elif not ct_dump_enabled and state == 'disabled':
        click.echo("SDK Connection Table dump in techsupport is already disabled")
        sys.exit(0)

    rc, stdout = set_sdk_techsupport_ct_dump_state(state, docker_client)
    if rc != 0:
        click.echo(f"Could not set SDK Connection Table dump in techsupport to {state}: {stdout}", err=True)
        sys.exit(rc)

    click.echo(f"SDK Connection Table dump in techsupport {state}.")


def register(cli):
    version_info = device_info.get_sonic_version_info()
    if (version_info and version_info.get('asic_type') == 'nvidia-bluefield'):
        cli.commands['platform'].add_command(nvidia_bluefield)

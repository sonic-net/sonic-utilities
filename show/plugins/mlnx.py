#!/usr/bin/env python3
#
# Copyright (c) 2017-2021 NVIDIA CORPORATION & AFFILIATES.
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
# Specific command-line utility for Mellanox platform
#

try:
    import sys
    import subprocess
    import click
    from shlex import join
    from lxml import etree as ET
    from sonic_py_common import device_info
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))

ENV_VARIABLE_SX_SNIFFER = 'SX_SNIFFER_ENABLE'
CONTAINER_NAME = 'syncd'
SNIFFER_CONF_FILE = '/etc/supervisor/conf.d/mlnx_sniffer.conf'
SNIFFER_CONF_FILE_IN_CONTAINER = CONTAINER_NAME + ':' + SNIFFER_CONF_FILE
TMP_SNIFFER_CONF_FILE = '/tmp/tmp.conf'

HWSKU_PATH = '/usr/share/sonic/hwsku/'

SAI_PROFILE_DELIMITER = '='

# run command
def run_command(command, display_cmd=False, ignore_error=False, print_to_console=True):
    """Run bash command and print output to stdout
    """
    if display_cmd == True:
        click.echo(click.style("Running command: ", fg='cyan') + click.style(join(command), fg='green'))

    proc = subprocess.Popen(command, text=True, stdout=subprocess.PIPE)
    (out, err) = proc.communicate()

    if len(out) > 0 and print_to_console:
        click.echo(out)

    if proc.returncode != 0 and not ignore_error:
        sys.exit(proc.returncode)

    return out, err


# 'mlnx' group
@click.group()
def mlnx():
    """ Show Mellanox platform information """
    pass


# get current status of sniffer from conf file
def sniffer_status_get(env_variable_name):
    enabled = False
    command = ["docker", "exec", CONTAINER_NAME, "bash", "-c", 'touch {}'.format(SNIFFER_CONF_FILE)]
    run_command(command)
    command = ['docker', 'cp', SNIFFER_CONF_FILE_IN_CONTAINER, TMP_SNIFFER_CONF_FILE]
    run_command(command)
    conf_file = open(TMP_SNIFFER_CONF_FILE, 'r')
    for env_variable_string in conf_file:
        if env_variable_string.find(env_variable_name) >= 0:
            enabled = True
            break
    conf_file.close()
    command = ['rm', '-rf', TMP_SNIFFER_CONF_FILE]
    run_command(command)
    return enabled


def is_issu_status_enabled():
    """ This function parses the SAI XML profile used for mlnx to
    get whether ISSU is enabled or disabled
    @return: True/False
    """

    # ISSU disabled if node in XML config wasn't found
    issu_enabled = False

    # Get the SAI XML path from sai.profile
    sai_profile_path = '/{}/sai.profile'.format(HWSKU_PATH)

    DOCKER_CAT_COMMAND = ['docker', 'exec', CONTAINER_NAME, 'cat', sai_profile_path]
    sai_profile_content, _ = run_command(DOCKER_CAT_COMMAND, print_to_console=False)

    sai_profile_kvs = {}

    for line in sai_profile_content.split('\n'):
        if not SAI_PROFILE_DELIMITER in line:
            continue
        key, value = line.split(SAI_PROFILE_DELIMITER)
        sai_profile_kvs[key] = value.strip()

    try:
        sai_xml_path = sai_profile_kvs['SAI_INIT_CONFIG_FILE']
    except KeyError:
        click.echo("Failed to get SAI XML from sai profile", err=True)
        sys.exit(1)

    # Get ISSU from SAI XML
    DOCKER_CAT_COMMAND = ['docker', 'exec', CONTAINER_NAME, 'cat', sai_xml_path]
    sai_xml_content, _ = run_command(DOCKER_CAT_COMMAND, print_to_console=False)

    try:
        root = ET.fromstring(sai_xml_content)
    except ET.ParseError:
        click.echo("Failed to parse SAI xml", err=True)
        sys.exit(1)

    el = root.find('platform_info').find('issu-enabled')

    if el is not None:
        issu_enabled = int(el.text) == 1

    return issu_enabled

@mlnx.command('issu')
def issu_status():
    """ Show ISSU status """

    res = is_issu_status_enabled()

    click.echo('ISSU is enabled' if res else 'ISSU is disabled')


def register(cli):
    version_info = device_info.get_sonic_version_info()
    if (version_info and version_info.get('asic_type') == 'mellanox'):
        cli.commands['platform'].add_command(mlnx)

#!/usr/bin/env python3
#
# Copyright (c) 2017-2024 NVIDIA CORPORATION & AFFILIATES.
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
    import os
    import time

    import click
    from sonic_py_common import logger
    from sonic_py_common import device_info
    import utilities_common.cli as clicommon
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))

VERSION = '1.0'

SNIFFER_SYSLOG_IDENTIFIER = "sniffer"

# SDK sniffer env variable
ENV_VARIABLE_SX_SNIFFER = 'SX_SNIFFER_ENABLE'
ENV_VARIABLE_SX_SNIFFER_TARGET = 'SX_SNIFFER_TARGET'

# SDK sniffer file path and name
SDK_SNIFFER_TARGET_PATH = '/var/log/sdk_dbg/'
SDK_SNIFFER_FILENAME_PREFIX = 'sx_sdk_sniffer_'
SDK_SNIFFER_FILENAME_EXT = '.pcap'

# Supervisor config file path
TMP_SNIFFER_CONF_FILE = '/tmp/tmp.conf'
CONTAINER_NAME = 'syncd'
SNIFFER_CONF_FILE = '/etc/supervisor/conf.d/mlnx_sniffer.conf'
SNIFFER_CONF_FILE_IN_CONTAINER = CONTAINER_NAME + ':' + SNIFFER_CONF_FILE
# Command to restart swss service
COMMAND_RESTART_SWSS = ['systemctl', 'restart', 'swss.service']


# Global logger instance
log = logger.Logger(SNIFFER_SYSLOG_IDENTIFIER)

# generate sniffer target file name include a time stamp.
def sniffer_filename_generate(path, filename_prefix, filename_ext):
    if not os.path.exists(path):
        os.makedirs(path)
    time_stamp = time.strftime("%Y%m%d%H%M%S")
    filename = path + filename_prefix + time_stamp + filename_ext
    return filename


# write environment variable in local tmp file for sniffer
def env_variable_write(env_variable_string):
    conf_file = open(TMP_SNIFFER_CONF_FILE, 'a')
    if os.path.getsize(TMP_SNIFFER_CONF_FILE) == 0:
        conf_file.write('[program:syncd]\n')
    conf_file.write(env_variable_string)
    conf_file.close()


def env_variable_read(env_variable_name):
    conf_file = open(TMP_SNIFFER_CONF_FILE, 'r')
    for env_variable_string in conf_file:
        if env_variable_string.find(env_variable_name) >= 0:
            break
    else:
        env_variable_string = ''
    conf_file.close()
    return env_variable_string


def env_variable_delete(delete_line):
    conf_file = open(TMP_SNIFFER_CONF_FILE, 'r+')
    all_lines = conf_file.readlines()
    conf_file.seek(0)
    for line in all_lines:
        if line != delete_line:
            conf_file.write(line)
    conf_file.truncate()
    conf_file.close()


def conf_file_copy(src, dest):
    command = ['docker', 'cp', str(src), str(dest)]
    clicommon.run_command(command)


def conf_file_receive():
    command = ['docker', 'exec', str(CONTAINER_NAME), 'bash', '-c', 'touch ' + str(SNIFFER_CONF_FILE)]
    clicommon.run_command(command)
    conf_file_copy(SNIFFER_CONF_FILE_IN_CONTAINER, TMP_SNIFFER_CONF_FILE)


def config_file_send():
    conf_file_copy(TMP_SNIFFER_CONF_FILE, SNIFFER_CONF_FILE_IN_CONTAINER)


# set supervisor conf file for sniffer enable
def sniffer_env_variable_set(enable, env_variable_name, env_variable_string=""):
    ignore = False
    conf_file_receive()
    env_variable_exist_string = env_variable_read(env_variable_name)
    if env_variable_exist_string:
        if enable is True:
            click.echo("sniffer is already enabled, do nothing")
            ignore = True
        else:
            env_variable_delete(env_variable_exist_string)
    else:
        if enable is True:
            env_variable_write(env_variable_string)
        else:
            click.echo("sniffer is already disabled, do nothing")
            ignore = True

    if not ignore:
        config_file_send()

    command = ['rm', '-rf', str(TMP_SNIFFER_CONF_FILE)]
    clicommon.run_command(command)

    return ignore


# restart the swss service with command 'service swss restart'
def restart_swss():
    try:
        clicommon.run_command(COMMAND_RESTART_SWSS)
    except OSError as e:
        log.log_error("Not able to restart swss service, %s" % str(e), True)
        return 1
    return 0


# ==================== CLI commands and groups ====================

# Callback for confirmation prompt. Aborts if user enters "n"
def _abort_if_false(ctx, param, value):
    if not value:
        ctx.abort()


# 'mlnx' group
@click.group()
def mlnx():
    """ Mellanox platform configuration tasks """
    pass

def sdk_sniffer_enable():
    """Enable SDK Sniffer"""
    sdk_sniffer_filename = sniffer_filename_generate(SDK_SNIFFER_TARGET_PATH,
                                                     SDK_SNIFFER_FILENAME_PREFIX,
                                                     SDK_SNIFFER_FILENAME_EXT)
    sdk_sniffer_env_variable_dict = {ENV_VARIABLE_SX_SNIFFER: "1" + ",",
                                     ENV_VARIABLE_SX_SNIFFER_TARGET: sdk_sniffer_filename}
    sdk_sniffer_env_variable_string = "environment="

    for env_variable_name, env_variable_value in sdk_sniffer_env_variable_dict.items():
        sdk_sniffer_env_variable_string += (env_variable_name + "=" + env_variable_value)

    sdk_sniffer_env_variable_string += "\n"

    ignore = sniffer_env_variable_set(enable=True, env_variable_name=ENV_VARIABLE_SX_SNIFFER,
                                      env_variable_string=sdk_sniffer_env_variable_string)
    if not ignore:
        err = restart_swss()
        if err != 0:
            return
        click.echo('SDK sniffer is Enabled, recording file is %s.' % sdk_sniffer_filename)
    else:
        pass


def sdk_sniffer_disable():
    """Disable SDK Sniffer"""

    ignore = sniffer_env_variable_set(enable=False, env_variable_name=ENV_VARIABLE_SX_SNIFFER)
    if not ignore:
        err = restart_swss()
        if err != 0:
            return
        click.echo("SDK sniffer is Disabled.")
    else:
        pass


# place holders for 'sniff prm enable/disable' and 'sniffer all enable/disable'
# @sniffer.command()
# @click.argument('option', type=click.Choice(["enable", "disable"]))
# def prf():
#     pass
#
#
# @sniffer.command()
# @click.argument('option', type=click.Choice(["enable", "disable"]))
# def all():
#     pass


def register(cli):
    version_info = device_info.get_sonic_version_info()
    if (version_info and version_info.get('asic_type') == 'mellanox'):
        cli.commands['platform'].add_command(mlnx)

if __name__ == '__main__':
    sniffer()

#!/usr/bin/env python

import click
import json
import subprocess
from sonic_py_common import device_info
from sonic_py_common.general import getstatusoutput_noshell_pipe

@click.group()
def barefoot():
    pass

@barefoot.command()
def profile():
    # Check if profile can be changed
    completed_process = subprocess.run(['docker', 'exec', '-it', 'syncd',
        'test', '-h', '/opt/bfn/install'])
    if completed_process.returncode != 0:
        click.echo('Current profile: default')
        return
    
    # Get chip family
    hwsku_dir = device_info.get_path_to_hwsku_dir()
    with open(hwsku_dir + '/switch-tna-sai.conf') as file:
        chip_family = json.load(file)['chip_list'][0]['chip_family'].lower()
    
    # Print current profile
    click.echo('Current profile: ', nl=False)
    cmd0 = ['docker', 'exec', '-it', 'syncd', 'readlink', '/opt/bfn/install']
    cmd1 = ['sed', r's/install_\\\(.\*\\\)_profile/\\1/']
    getstatusoutput_noshell_pipe(cmd0, cmd1)
    
    # Exclude current and unsupported profiles
    opts = ''
    if chip_family == 'tofino':
        opts = r'\! -name install_y\*_profile'
    elif chip_family == 'tofino2':
        opts = r'\! -name install_x\*_profile'
    
    # Print profile list
    click.echo('Available profile(s):')
    cmd0 = ['docker', 'exec', '-it', 'syncd', 'find', '/opt/bfn', '-mindepth', '1',\
            '-maxdepth', '1', '-type', 'd', '-name', r'install_\*_profile', opts]
    cmd1 = ["sed", r's%/opt/bfn/install_\\\(.\*\\\)_profile%\\1%']
    getstatusoutput_noshell_pipe(cmd0, cmd1)

def register(cli):
    version_info = device_info.get_sonic_version_info()
    if version_info and version_info.get('asic_type') == 'barefoot':
        cli.commands['platform'].add_command(barefoot)

#!/usr/bin/env python3
# cpoutil/main.py
# CLI only, platform API logic marked Todo, reuse sonic sfputil existing CMIS CDB api calls

import os
import sys
import time
import click
from sonic_py_common import logger
from sonic_platform import platform

VERSION = "1.0"
SYSLOG_IDENTIFIER = "cpoutil"
log = logger.Logger(SYSLOG_IDENTIFIER)

# Global config
EXIT_SUCCESS = 0
EXIT_FAIL = -1
ERROR_PERMISSIONS = 1
ERROR_INVALID_COMPONENT = 2
ERROR_MISSING_INDEX = 3
ERROR_INDEX_INVALID = 4

SUPPORTED_COMPONENTS = ["mcu", "oe", "els"]
CDB_DEFAULT_PASSWORD = 0x00001011

# Global platform handle
platform_chassis = None

def load_platform():
    global platform_chassis
    try:
        platform_chassis = platform.Platform().get_chassis()
        return True
    except Exception as e:
        log.log_error(f"Load chassis failed: {e}")
        return False

def get_physical_port_by_cpo_index(component: str, index: int):
    """
    Todo: Read cpo.json mapping, convert component + index to physical_port index
    :param component: mcu/oe/els
    :param index: cpo instance index start from 0
    :return: physical_port integer
    """
    # Todo: implement cpo.json parse & index mapping
    physical_port = 0
    click.echo(f"[Todo] Map {component}-n{index} to physical_port {physical_port} via cpo.json")
    return physical_port

def get_cpo_xcvr_api(component: str, index: int):
    """
    Get xcvr api handle by cpo component index
    """
    validate_input(component, index)
    phys_port = get_physical_port_by_cpo_index(component, index)
    sfp = platform_chassis.get_sfp(phys_port)
    api = sfp.get_xcvr_api()
    if not api:
        click.echo(f"Error: get xcvr api failed for {component}-{index} port {phys_port}", err=True)
        sys.exit(EXIT_FAIL)
    return api

def validate_input(component: str, index: int):
    if component not in SUPPORTED_COMPONENTS:
        click.echo(f"Error: component {component} invalid, support: {SUPPORTED_COMPONENTS}", err=True)
        sys.exit(ERROR_INVALID_COMPONENT)
    if index is None:
        click.echo(f"Error: mandatory -n <index> missing", err=True)
        sys.exit(ERROR_MISSING_INDEX)
    if index < 0:
        click.echo(f"Error: index {index} must >=0", err=True)
        sys.exit(ERROR_INDEX_INVALID)

# ---------------------- Core Firmware Action Wrappers (Only CLI, call existed api) ----------------------
def fw_unlock(component: str, index: int, password=None):
    api = get_cpo_xcvr_api(component, index)
    pwd = password if password is not None else CDB_DEFAULT_PASSWORD
    # reuse existed CDB password entry api same as sfputil
    ret = api.cdb_enter_host_password(pwd)
    if ret == 1:
        click.echo(f"Unlock {component}-{index} success, password accepted")
    else:
        click.echo(f"Unlock {component}-{index} failed, cdb password reject ret={ret}", err=True)
        sys.exit(EXIT_FAIL)

def fw_download(component: str, index: int, fw_path: str):
    if not os.path.isfile(fw_path):
        click.echo(f"Error: firmware file {fw_path} not exist", err=True)
        sys.exit(EXIT_FAIL)
    api = get_cpo_xcvr_api(component, index)
    file_size = os.path.getsize(fw_path)
    click.echo(f"Start download {fw_path}, size={file_size} bytes to {component}-{index}")

    # 0x0101 start_fw_download
    ret_start = api.start_fw_download(fw_path)
    if ret_start != 1:
        click.echo(f"start_fw_download(0x0101) failed ret={ret_start}", err=True)
        sys.exit(EXIT_FAIL)

    # Todo: block read & loop write_epl_block(0x0104)
    click.echo("[Todo] Loop read firmware binary, call api.write_epl_block(0x0104) per block")

    # 0x0107 complete_fw_download
    ret_complete = api.complete_fw_download()
    if ret_complete != 1:
        click.echo(f"complete_fw_download(0x0107) failed ret={ret_complete}", err=True)
        sys.exit(EXIT_FAIL)
    click.echo(f"{component}-{index} firmware download complete")

def fw_run(component: str, index: int, mode: int = 0):
    api = get_cpo_xcvr_api(component, index)
    # 0x0109 run_fw_image
    ret_run = api.run_fw_image(mode)
    if ret_run != 1:
        click.echo(f"run_fw_image(0x0109) failed ret={ret_run}", err=True)
        sys.exit(EXIT_FAIL)
    click.echo(f"{component}-{index} run inactive firmware image success, wait init...")
    time.sleep(5)

def fw_commit(component: str, index: int):
    api = get_cpo_xcvr_api(component, index)
    # 0x010A commit_fw_image
    ret_commit = api.commit_fw_image()
    if ret_commit != 1:
        click.echo(f"commit_fw_image(0x010A) failed ret={ret_commit}", err=True)
        sys.exit(EXIT_FAIL)
    click.echo(f"{component}-{index} firmware commit permanent success")

def fw_upgrade_one_step(component: str, index: int, fw_package: str):
    click.echo(f"==== One-step full upgrade {component}-{index} start ====")
    fw_unlock(component, index)
    fw_download(component, index, fw_package)
    fw_run(component, index)
    fw_commit(component, index)
    click.echo(f"==== One-step upgrade {component}-{index} finished ====")

def show_fw_version(component: str, index: int):
    api = get_cpo_xcvr_api(component, index)
    # 0x0100 get_fw_status
    fw_status = api.get_fw_status()
    # Todo: parse fw_status dict to print format match HLD document
    click.echo(f"{component.upper()}{index}:")
    click.echo(f"[Todo] Parse get_fw_status(0x0100) raw data -> Active/Inactive version")
    click.echo(f"Raw FW Status Data: {fw_status}")

# ---------------------- Click CLI Entry ----------------------
@click.group()
def cli():
    """cpoutil - SONiC CLI for Co-packaged Optics CPO firmware management"""
    if os.geteuid() != 0:
        click.echo("Error: run with root privilege", err=True)
        sys.exit(ERROR_PERMISSIONS)
    if not load_platform():
        click.echo("Error: load platform chassis failed", err=True)
        sys.exit(EXIT_FAIL)

# show subgroup
@cli.group(name="show")
def show():
    """Show CPO component info"""
    pass

@show.command(name="fwversion")
@click.argument("component", type=click.Choice(SUPPORTED_COMPONENTS))
@click.option("-n", "--index", type=int, required=True, help="CPO component instance index (start from 0)")
def cmd_show_fwversion(component, index):
    """Show firmware active/inactive version of target component index"""
    show_fw_version(component, index)

# firmware subgroup
@cli.group(name="firmware")
def firmware():
    """CPO firmware operation workflow"""
    pass

@firmware.command(name="unlock")
@click.argument("component", type=click.Choice(SUPPORTED_COMPONENTS))
@click.option("-n", "--index", type=int, required=True, help="CPO component index")
@click.option("--password", type=int, help="CMIS CDB host password, default 0x00001011")
def cmd_fw_unlock(component, index, password):
    """Unlock CDB firmware download channel"""
    fw_unlock(component, index, password)

@firmware.command(name="download")
@click.argument("component", type=click.Choice(SUPPORTED_COMPONENTS))
@click.option("-n", "--index", type=int, required=True)
@click.argument("fw_file", type=click.Path(exists=True))
def cmd_fw_download(component, index, fw_file):
    """Download firmware binary to target component"""
    fw_download(component, index, fw_file)

@firmware.command(name="run")
@click.argument("component", type=click.Choice(SUPPORTED_COMPONENTS))
@click.option("-n", "--index", type=int, required=True)
@click.option("--mode", default=0, type=int, help="run image reset mode 0~3")
def cmd_fw_run(component, index, mode):
    """Activate downloaded inactive firmware image"""
    fw_run(component, index, mode)

@firmware.command(name="commit")
@click.argument("component", type=click.Choice(SUPPORTED_COMPONENTS))
@click.option("-n", "--index", type=int, required=True)
def cmd_fw_commit(component, index):
    """Commit running firmware as permanent boot image"""
    fw_commit(component, index)

@firmware.command(name="upgrade")
@click.argument("component", type=click.Choice(SUPPORTED_COMPONENTS))
@click.option("-n", "--index", type=int, required=True)
@click.argument("fw_package", type=click.Path(exists=True))
def cmd_fw_upgrade(component, index, fw_package):
    """One step full upgrade: unlock -> download -> run -> commit"""
    fw_upgrade_one_step(component, index, fw_package)

# top version cmd
@cli.command(name="version")
def cmd_version():
    """Print cpoutil tool version"""
    click.echo(f"cpoutil version {VERSION}")

if __name__ == "__main__":
    cli()
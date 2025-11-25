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
    from sonic_py_common import device_info, multi_asic
    from tabulate import tabulate
    from utilities_common.db import Db
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))

ENV_VARIABLE_SX_SNIFFER = 'SX_SNIFFER_ENABLE'
CONTAINER_NAME = 'syncd'
SNIFFER_CONF_FILE = '/etc/supervisor/conf.d/mlnx_sniffer.conf'
SNIFFER_CONF_FILE_IN_CONTAINER = CONTAINER_NAME + ':' + SNIFFER_CONF_FILE
TMP_SNIFFER_CONF_FILE = '/tmp/tmp.conf'

HWSKU_PATH = '/usr/share/sonic/hwsku/'

SAI_PROFILE_DELIMITER = '='

UP_STATUS = 'UP'
DOWN_STATUS = 'DOWN'
ETHERNET_PREFIX = 'Ethernet'
PORT_TABLE = 'PORT'
PORT_TYPE_CPO = 'CPO'
MPO_LANES = 4

# ------------------------ MPO helpers ------------------------


def is_cpo_port(rdb, port):
    """
    Determine whether a given port is a CPO type port.
    Fetch 'type' from STATE_DB 'TRANSCEIVER_INFO|<port>' and match 'CPO'.
    """
    try:
        val = rdb.get(rdb.STATE_DB, f"TRANSCEIVER_INFO|{port}", "type")
        return val == PORT_TYPE_CPO
    except Exception:
        return False


def get_cpo_ports_sorted(port_tbl, ns=None):
    """
    Return Ethernet ports in this namespace which are CPO type, sorted by numeric index.
    """
    try:
        # Use Db helper to get per-namespace STATE_DB connector
        db = Db()
        rdb = db.db if ns is None else db.db_clients[ns]
        cpo_ports = [p for p in port_tbl if p.startswith(ETHERNET_PREFIX) and is_cpo_port(rdb, p)]
    except Exception as e:
        click.echo(f"Warning: failed to get CPO ports list: {e}", err=True)
        return []
    return sorted(cpo_ports, key=lambda p: int(p.replace(ETHERNET_PREFIX, '')))


def get_ports_oper_status(ports, ns=None):
    """
    Fetch oper_status for ports from APPL_DB and return mapping to 'UP'/'DOWN'.
    """
    status_map = {}
    try:
        db = Db()
        rdb = db.db if ns is None else db.db_clients[ns]
        for p in ports:
            v = rdb.get(rdb.APPL_DB, f"PORT_TABLE:{p}", "oper_status")
            status_map[p] = UP_STATUS if v and v.upper() == UP_STATUS else DOWN_STATUS
    except Exception:
        pass
    return status_map


def create_single_asic_mpo_rows():
    """
    Build rows for single-ASIC: MPO from CONFIG_DB PORT.lanes for CPO ports only.
    """
    try:
        db = Db()
        cfg_db = db.cfgdb
        port_tbl = cfg_db.get_table(PORT_TABLE)
    except Exception as e:
        raise click.ClickException(f"Failed to read {PORT_TABLE} from CONFIG_DB: {e}")
    # Pre-fetch status for all CPO ports
    cpo_ports = get_cpo_ports_sorted(port_tbl=port_tbl)
    if len(cpo_ports) == 0:
        raise click.ClickException("No CPO ports found")
    status_map = get_ports_oper_status(ports=cpo_ports)
    mpo_to_lanes = {}
    for port_name in cpo_ports:
        attrs = port_tbl[port_name]
        lanes_str = attrs.get('lanes')
        if not lanes_str:
            continue
        try:
            lane_nums = [int(x.strip()) for x in lanes_str.split(',') if x.strip() != '']
        except Exception:
            continue
        for ln in lane_nums:
            mpo_idx = (ln // MPO_LANES) + 1
            lane_pos = ln % MPO_LANES
            if mpo_idx not in mpo_to_lanes:
                mpo_to_lanes[mpo_idx] = ['-', '-', '-', '-']
            mpo_to_lanes[mpo_idx][lane_pos] = f"{port_name}({status_map.get(port_name, DOWN_STATUS)})"
    # Build final rows, ordered by MPO index
    rows = [[mpo] + mpo_to_lanes[mpo] for mpo in sorted(mpo_to_lanes.keys())]
    return rows


def create_multi_asic_mpo_rows():
    """
    Build rows for multi-ASIC: MPO m = m-th CPO port of each ASIC in order.
    """
    namespaces = multi_asic.get_namespace_list()
    per_ns_port_lists = []
    per_ns_status = {}
    try:
        db = Db()
        for ns in namespaces:
            cfg_ns = db.cfgdb_clients[ns]
            port_tbl = cfg_ns.get_table(PORT_TABLE)
            cpo_list = get_cpo_ports_sorted(port_tbl=port_tbl, ns=ns)
            if len(cpo_list) == 0:
                click.echo(f"Warning: no CPO ports found in namespace {ns}", err=True)
                continue
            per_ns_port_lists.append((ns, cpo_list))
            per_ns_status[ns] = get_ports_oper_status(ports=cpo_list, ns=ns)
    except Exception as e:
        raise click.ClickException(f"Failed to read DBs for namespaces: {e}")
    if len(per_ns_port_lists) == 0:
        raise click.ClickException("No CPO ports found across namespaces")
    ports_number = max(len(port_list) for _, port_list in per_ns_port_lists)
    # Build MPO data structure: mapping from mpo index to a list of interfaces per lane
    # For multi-asic, mpo index and lane are determined as instructed
    mpo_to_lanes = {}
    total_interfaces = []
    # Collect the (ns, port_name) pairs across all namespaces
    for ns, port_list in per_ns_port_lists:
        for port in port_list:
            total_interfaces.append((ns, port))
    total_interfaces.sort(key=lambda x: int(x[1].replace(ETHERNET_PREFIX, '')))
    # Now for each interface, calculate its MPO index and lane position
    for lane, (ns, port) in enumerate(total_interfaces):
        mpo_idx = (lane % ports_number) + 1
        lane_pos = (lane // ports_number)
        if mpo_idx not in mpo_to_lanes:
            mpo_to_lanes[mpo_idx] = ['-', '-', '-', '-']
        status = per_ns_status.get(ns, {}).get(port, DOWN_STATUS)
        name_with_ns = f"{port}/{ns}" if ns else port
        mpo_to_lanes[mpo_idx][lane_pos] = f"{name_with_ns}({status})"
    # Build final rows, ordered by MPO index
    rows = [[mpo] + mpo_to_lanes[mpo] for mpo in sorted(mpo_to_lanes.keys())]
    return rows

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


@mlnx.command('mpo-status')
def mpo_status():
    """Show MPO → interface mapping status (CPO ports only)."""
    headers = ['MPO', 'Lane 1', 'Lane 2', 'Lane 3', 'Lane 4']
    multi = multi_asic.is_multi_asic()
    if not multi:
        # Single-ASIC: derive mapping directly from lanes
        rows = create_single_asic_mpo_rows()
    else:
        # Multi-ASIC: MPO m is composed of the m-th port on each ASIC (namespace)
        rows = create_multi_asic_mpo_rows()
    click.echo(tabulate(rows, headers, tablefmt="outline"))

def register(cli):
    version_info = device_info.get_sonic_version_info()
    if (version_info and version_info.get('asic_type') == 'mellanox'):
        cli.commands['platform'].add_command(mlnx)

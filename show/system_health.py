import os
import sys
import re
import click
from tabulate import tabulate
import utilities_common.cli as clicommon
from swsscommon.swsscommon import SonicV2Connector
from natsort import natsorted
from utilities_common.chassis import is_smartswitch, get_all_dpus, get_all_dpu_options, is_midplane_reachable, get_dpu_ip_list
import subprocess
import paramiko
from concurrent.futures import ThreadPoolExecutor, as_completed

DPU_STATE = 'DPU_STATE'
CHASSIS_SERVER = 'redis_chassis.server'
CHASSIS_SERVER_PORT = 6380
CHASSIS_STATE_DB = 13

# Global toggle to allow or disable auto SSH key setup
AUTO_SSH_KEY_SETUP_ENABLED = True
# Default SSH public key path
DEFAULT_KEY_PATH = os.path.expanduser("~/.ssh/id_rsa")
DEFAULT_PUBLIC_KEY_PATH = f"{DEFAULT_KEY_PATH}.pub"
# Internal cache to avoid repeat setup attempts
_ssh_key_cache = set()

def get_system_health_status():
    if os.environ.get("UTILITIES_UNIT_TESTING") == "1":
        modules_path = os.path.join(os.path.dirname(__file__), "..")
        sys.path.insert(0, modules_path)
        from tests.system_health_test import MockerManager
        from tests.system_health_test import MockerChassis
        HealthCheckerManager = MockerManager
        Chassis = MockerChassis
    else:
        if os.geteuid():
            click.echo("Root privileges are required for this operation")
            exit(1)
        from health_checker.manager import HealthCheckerManager
        from sonic_platform.chassis import Chassis


    manager = HealthCheckerManager()
    if not manager.config.config_file_exists():
        click.echo("System health configuration file not found, exit...")
        exit(1)

    chassis = Chassis()
    stat = manager.check(chassis)
    chassis.initizalize_system_led()

    return manager, chassis, stat

def display_system_health_summary(stat, led):
    click.echo("System status summary\n\n  System status LED  " + led)
    services_list = []
    fs_list = []
    device_list =[]
    for category, elements in stat.items():
        for element in elements:
            if elements[element]['status'] != "OK":
                if category == 'Services':
                    if 'Accessible' in elements[element]['message']:
                        fs_list.append(element)
                    else:
                        services_list.append(element)
                else:
                    device_list.append(elements[element]['message'])
    if services_list or fs_list:
        click.echo("  Services:\n    Status: Not OK")
    else:
        click.echo("  Services:\n    Status: OK")
    if services_list:
        click.echo("    Not Running: " + ', '.join(services_list))
    if fs_list:
        click.echo("    Not Accessible: " + ', '.join(fs_list))
    if device_list:
        click.echo("  Hardware:\n    Status: Not OK")
        device_list.reverse()
        click.echo("    Reasons: " + device_list[0])
        if len(device_list) > 1:
            click.echo('\n'.join(("\t     " + x) for x in device_list[1:]))
    else:
        click.echo("  Hardware:\n    Status: OK")

def display_monitor_list(stat):
    click.echo('\nSystem services and devices monitor list\n')
    header = ['Name', 'Status', 'Type']
    table = []
    for elements in stat.values():
        for element in sorted(elements.items(), key=lambda x: x[1]['status']):
            entry = []
            entry.append(element[0])
            entry.append(element[1]['status'])
            entry.append(element[1]['type'])
            table.append(entry)
    click.echo(tabulate(table, header))


def display_ignore_list(manager):
    header = ['Name', 'Status', 'Type']
    click.echo('\nSystem services and devices ignore list\n')
    table = []
    if manager.config.ignore_services:
        for element in manager.config.ignore_services:
            entry = []
            entry.append(element)
            entry.append("Ignored")
            entry.append("Service")
            table.append(entry)
    if manager.config.ignore_devices:
        for element in manager.config.ignore_devices:
            entry = []
            entry.append(element)
            entry.append("Ignored")
            entry.append("Device")
            table.append(entry)
    click.echo(tabulate(table, header))

def ensure_ssh_key_exists():
    if not os.path.exists(DEFAULT_PUBLIC_KEY_PATH):
        click.echo("SSH key not found. Generating...")
        subprocess.run(["ssh-keygen", "-t", "rsa", "-b", "4096", "-N", "", "-f", key_path],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# define the function to set up SSH key for remote module
def setup_ssh_key_for_remote(module_host, username, password, public_key_path):
    """Automatically copies the public SSH key to the remote module"""
    # Read the public key
    with open(public_key_path, 'r') as f:
        public_key = f.read().strip()

    # Create the SSH client
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # Automatically accept unknown keys

    # Connect to the DPU using the password
    ssh.connect(module_host, username=username, password=password)

    # Create the .ssh directory if it doesn't exist
    stdin, stdout, stderr = ssh.exec_command('mkdir -p ~/.ssh')
    stdin.channel.recv_exit_status()  # Wait for the command to finish

    # Add the public key to authorized_keys
    stdin, stdout, stderr = ssh.exec_command(f'echo "{public_key}" >> ~/.ssh/authorized_keys')
    stdin.channel.recv_exit_status()

    # Set proper permissions for the authorized_keys file
    stdin, stdout, stderr = ssh.exec_command('chmod 600 ~/.ssh/authorized_keys')
    stdin.channel.recv_exit_status()

    # Close the SSH connection
    ssh.close()

def ensure_ssh_key_setup(ip, username="admin"):
    if not AUTO_SSH_KEY_SETUP_ENABLED or ip in _ssh_key_cache:
        return

    if not is_midplane_reachable(ip):
        return

    ensure_ssh_key_exists()

    try:
        ssh_test = subprocess.run([
            "ssh", "-i", DEFAULT_KEY_PATH,
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=5",
            f"{username}@{ip}", "echo OK"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if ssh_test.returncode != 0:
            click.echo(f"SSH key not set for {ip}. Attempting setup...")
            click.echo(f"Reason: {ssh_test.stderr.decode().strip()}")
            password = click.prompt(f"Password for {username}@{ip}", hide_input=True)
            setup_ssh_key_for_remote(ip, username, password, DEFAULT_PUBLIC_KEY_PATH)
    except Exception as e:
        click.echo(f"Auto SSH key setup failed for {ip}: {e}")

    _ssh_key_cache.add(ip)


def get_module_health(ip, command_type, timeout=60):
    module_host = f"admin@{ip}"
    remote_cmd = f"sudo -n bash -c 'show system-health {command_type}'"
    ssh_command = [
        "ssh",
        "-i", DEFAULT_KEY_PATH,
        "-T",
        "-o", "ConnectTimeout=10",
        "-o", "StrictHostKeyChecking=no",
        module_host,
        remote_cmd
    ]
    try:
        output = subprocess.check_output(
            ssh_command, stderr=subprocess.STDOUT, text=True, timeout=timeout
        )
        lines = output.strip().splitlines()
        lines = [line for line in lines if not re.match(r'(Debian|GNU/Linux|Welcome)', line)]
        return ip, "\n".join(lines)
    except subprocess.TimeoutExpired:
        return ip, f"Module: {ip} down (timeout)"
    except subprocess.CalledProcessError as e:
        err = e.output.strip()
        if "No route to host" in err:
            return ip, f"Module: {ip} down"
        if "Permission denied" in err or "Too many authentication failures" in err:
            return ip, f"Module: {ip} authentication failed"
        return ip, f"Module: {ip} error: {err}"

def display_module_health_summary(module_name, command_type, reachable_only=False):
    dpulist = []
    if module_name == "all":
        dpulist = "all"
    else:
        dpulist = [module_name.lower()]
    modules = get_dpu_ip_list(dpulist)
    if reachable_only:
        modules = [(name, ip) for name, ip in modules if is_midplane_reachable(ip)]
    if not modules:
        click.echo("No reachable DPU modules found.")
        return

    for _, ip in modules:
        ensure_ssh_key_setup(ip)

    with ThreadPoolExecutor(max_workers=len(modules)) as executor:
        future_to_module = {
            executor.submit(get_module_health, ip, command_type): name for name, ip in modules
        }
        for future in as_completed(future_to_module):
            module = future_to_module[future]
            try:
                _, health_status = future.result()
                click.echo(f"\nModule: {module}")
                click.echo(health_status)
            except Exception as e:
                click.echo(f"\nModule: {module}")
                click.echo(f"Module: {module} error: {e}")

#
# 'system-health' command ("show system-health")
#
@click.group(name='system-health', cls=clicommon.AliasedGroup)
def system_health():
    """Show system-health information"""
    return

@system_health.command()
@click.argument('module_name', required=False)
@click.option('--reachable-only', is_flag=True, help="Only include modules reachable via midplane.")
def summary(module_name, reachable_only):
    if not module_name or module_name == "all":
        if module_name == "all":
            print("SWITCH")
        _, chassis, stat = get_system_health_status()
        display_system_health_summary(stat, chassis.get_status_led())
    if module_name and module_name.startswith("DPU") or module_name == "all":
        display_module_health_summary(module_name, "summary", reachable_only)


@system_health.command()
@click.argument('module_name', required=False)
@click.option('--reachable-only', is_flag=True, help="Only include modules reachable via midplane.")
def detail(module_name, reachable_only):
    _, chassis, stat = get_system_health_status()
    display_system_health_summary(stat, chassis.get_status_led())
    display_monitor_list(stat)
    display_ignore_list(_)
    if module_name and module_name.startswith("DPU") or module_name == "all":
        display_module_health_summary(module_name, "detail", reachable_only)

@system_health.command()
@click.argument('module_name', required=False)
@click.option('--reachable-only', is_flag=True, help="Only include modules reachable via midplane.")
def monitor_list(module_name, reachable_only):
    _, _, stat = get_system_health_status()
    display_monitor_list(stat)
    if module_name and module_name.startswith("DPU") or module_name == "all":
        display_module_health_summary(module_name, "monitor-list", reachable_only)

@system_health.command()
@click.argument('module_host')
@click.argument('username')
@click.argument('password')
@click.argument('public_key_path', required=False)
def setup_ssh_key(module_host, username, password, public_key_path):
    """Manually set up SSH key authentication for the remote module"""
    click.echo(f"Setting up SSH key for module: {module_host}")
    if not public_key_path:
        public_key_path = DEFAULT_PUBLIC_KEY_PATH
    public_key_path = os.path.expanduser(public_key_path)

    if not os.path.exists(public_key_path):
        click.echo(f"Public key not found at {public_key_path}. Please generate it first.")
        return

    try:
        setup_ssh_key_for_remote(module_host, username, password, public_key_path)
        click.echo(f"SSH key setup completed for {module_host}")
    except Exception as e:
        click.echo(f"Failed to set up SSH key for {module_host}: {str(e)}")

@system_health.command()
def disable_auto_ssh_key():
    """Disable automatic SSH key setup for modules"""
    global AUTO_SSH_KEY_SETUP_ENABLED
    AUTO_SSH_KEY_SETUP_ENABLED = False
    click.echo("Auto SSH key setup has been disabled.")

@system_health.group('sysready-status',invoke_without_command=True)
@click.pass_context
def sysready_status(ctx):
    """Show system-health system ready status"""

    if ctx.invoked_subcommand is None:
        try:
            cmd = ["sysreadyshow"]
            clicommon.run_command(cmd, display_cmd=False)
        except Exception as e:
            click.echo("Exception: {}".format(str(e)))


@sysready_status.command('brief')
def sysready_status_brief():
    try:
        cmd = ["sysreadyshow", "--brief"]
        clicommon.run_command(cmd, display_cmd=False)
    except Exception as e:
        click.echo("Exception: {}".format(str(e)))


@sysready_status.command('detail')
def sysready_status_detail():
    try:
        cmd = ["sysreadyshow", "--detail"]
        clicommon.run_command(cmd, display_cmd=False)
    except Exception as e:
        click.echo("Exception: {}".format(str(e)))


def show_dpu_state(module_name):
    chassis_state_db = SonicV2Connector(host=CHASSIS_SERVER, port=CHASSIS_SERVER_PORT)
    chassis_state_db.connect(chassis_state_db.CHASSIS_STATE_DB)
    key = 'DPU_STATE|'
    suffix = '*' if not module_name or not module_name.startswith("DPU") else module_name
    key = key + suffix
    keys = chassis_state_db.keys(chassis_state_db.CHASSIS_STATE_DB, key)
    if not keys:
        click.echo("DPU_STATE table is not present for module:{} in DB".format(module_name))
        return

    table = []
    for dbkey in natsorted(keys):
        key_list = dbkey.split('|')
        if len(key_list) != 2:  # error data in DB, log it and ignore
            continue
        state_info = chassis_state_db.get_all(chassis_state_db.CHASSIS_STATE_DB, dbkey)
        # Determine operational status
        midplanedown = False
        up_cnt = 0
        for key, value in state_info.items():
            if key.endswith('_state'):
                if value.lower() == 'up':
                    up_cnt = up_cnt + 1
                if 'midplane' in key and value.lower() == 'down':
                    midplanedown = True

        if midplanedown:
            oper_status = "Offline"
        elif up_cnt == 3:
            oper_status = "Online"
        else:
            oper_status = "Partial Online"

        for dpustates in range(3):
            if dpustates == 0:
                row = [key_list[1], oper_status, "", "", "", ""]
            else:
                row = ["", "", "", "", "", ""]
            for key, value in state_info.items():
                if key == "id":
                    continue
                if dpustates == 0 and 'midplane' in key:
                    populate_row(row, key, value, table)
                elif dpustates == 1 and 'control' in key:
                    populate_row(row, key, value, table)
                elif dpustates == 2 and 'data' in key:
                    populate_row(row, key, value, table)

    headers = ["Name", "Oper-Status", "State-Detail", "State-Value", "Time", "Reason"]
    click.echo(tabulate(table, headers=headers))


def populate_row(row, key, value, table):
    if key.endswith('_state'):
        row[2] = key
        row[3] = value
        if "up" in row[3]:
            row[5] = ""
        table.append(row)
    elif key.endswith('_time'):
        row[4] = value
    elif key.endswith('_reason'):
        if "up" not in row[3]:
            row[5] = value


@system_health.command()
@click.argument('module_name',
                required=True,
                type=click.Choice(get_all_dpu_options(), case_sensitive=False) if is_smartswitch() else None
                )
def dpu(module_name):
    """Show system-health dpu information"""
    if not is_smartswitch():
        return
    show_dpu_state(module_name)

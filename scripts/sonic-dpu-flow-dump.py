#!/usr/bin/env python3
"""
SONiC DPU Flow Dump Utility

This script triggers a flow dump session, waits for completion, and extracts/prints the results.
It automatically creates the configuration file in /etc/sonic/ha/flow_dump.json.

Usage:
    sonic-dpu-flow-dump.py [-f FLOW_STATE] [-t TIMEOUT] [-m MAX_FLOWS] [-v]

Options:
    -f, --flow-state    Flow state (true/false), default: true
    -t, --timeout       Timeout in seconds, default: 60
    -m, --max-flows     Maximum number of flows to dump, default: 1000
    -v, --verbose       Enable verbose output
"""

import json
import sys
import subprocess
import os
import gzip
import time
import random
import string
import argparse
import signal
import netifaces
from swsscommon import swsscommon


STATE_TABLE_NAME = "DASH_FLOW_SYNC_SESSION_STATE_TABLE"
CONFIG_FILE_PATH = "/etc/sonic/ha/flow_dump.json"
CONFIG_DIR = "/etc/sonic/ha"
SWSS_CONTAINER = "swss"
SWSS_CONFIG_CMD = "swssconfig"
MIDPLANE_INTERFACE = "eth0-midplane"

_interrupted = False
_verbose = False


def signal_handler(signum, frame):
    """Handle SIGINT (Ctrl+C) signal."""
    global _interrupted
    _interrupted = True


def print_verbose(*args, **kwargs):
    """Print only if verbose is True."""
    if _verbose:
        print(*args, **kwargs)


def print_error(*args, **kwargs):
    """Print error message to stderr."""
    print(*args, file=sys.stderr, **kwargs)


def get_midplane_ip(interface=MIDPLANE_INTERFACE):
    """Get IPv4 address from the specified interface with 169.254.200 prefix."""
    try:
        addresses = netifaces.ifaddresses(interface)
        if netifaces.AF_INET in addresses:
            ipv4_addrs = addresses[netifaces.AF_INET]
            for addr_info in ipv4_addrs:
                ip = addr_info.get('addr')
                if ip and ip.startswith('169.254.200'):
                    return ip
    except (ValueError, KeyError, IndexError):
        pass
    return None


def get_swss_config_endpoint():
    """Get the swssconfig endpoint based on midplane IP."""
    midplane_ip = get_midplane_ip()
    if midplane_ip:
        return f"tcp://{midplane_ip}"
    return "tcp://169.254.200.1"


def generate_session_name():
    """Generate a random session name."""
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"flow_dump_session_{random_suffix}"


def ensure_config_directory(config_dir=CONFIG_DIR):
    """Ensure the configuration directory exists."""
    try:
        os.makedirs(config_dir, exist_ok=True)
        return True
    except Exception as e:
        print_error(f"Error creating config directory {config_dir}: {e}")
        return False


def create_config_file(config_path, session_name=None, max_flows=1000, timeout=60, flow_state=True):
    """Create the flow dump config file."""
    try:
        if session_name is None:
            session_name = generate_session_name()

        if not ensure_config_directory():
            return None

        config = [
            {
                f"DASH_FLOW_SYNC_SESSION_TABLE:{session_name}": {
                    "type": "flow_dump",
                    "flow_state": "true" if flow_state else "false",
                    "max_flows": str(max_flows),
                    "timeout": str(timeout)
                },
                "OP": "SET"
            }
        ]

        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)

        return session_name
    except Exception as e:
        print_error(f"Error creating config file: {e}")
        return None


def trigger_flow_dump(config_path):
    """Trigger the flow dump using docker exec swss swssconfig."""
    endpoint = get_swss_config_endpoint()
    cmd = ["docker", "exec", SWSS_CONTAINER, SWSS_CONFIG_CMD, "-e", endpoint, config_path]

    print_verbose(f"Triggering flow dump: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print_verbose("Flow dump triggered successfully")
        if result.stdout:
            print_verbose(f"Output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Error triggering flow dump: {e}")
        if e.stdout:
            print_verbose(f"stdout: {e.stdout}", file=sys.stderr)
        if e.stderr:
            print_verbose(f"stderr: {e.stderr}", file=sys.stderr)
        return False


def check_session_state(table, session_name):
    """Check current session state from the table."""
    exists, fvs = table.get(session_name)
    if not exists:
        return None, None

    state = None
    output_file = None
    for field, value in fvs:
        if field == "state":
            state = value
        elif field == "output_file":
            output_file = value

    return state, output_file


def process_notification(key, op, fvs, session_name, table):
    """Process a notification event and return updated state."""
    if key != session_name:
        return None, None

    print_verbose(f"[Notification] Received update for session '{session_name}': op={op}")
    for field, value in fvs:
        print_verbose(f"  {field} = {value}")

    db_state, db_output_file = check_session_state(table, session_name)
    if db_state:
        print_verbose(f"[Notification] Current DB state: {db_state}")
        return db_state, db_output_file

    return None, None


def wait_for_completion(session_name, timeout=60):
    """Wait for the flow dump session to complete using SubscriberStateTable."""
    global _interrupted
    _interrupted = False

    signal.signal(signal.SIGINT, signal_handler)

    # Add 5 second buffer to timeout to ensure we capture even the failed notification from orchagent
    timeout_with_buffer = timeout + 5

    print_verbose(f"Waiting for session '{session_name}' to complete (timeout: {timeout}s)...")

    db = swsscommon.DBConnector("DPU_STATE_DB", 0, True)
    subscriber_table = swsscommon.SubscriberStateTable(db, STATE_TABLE_NAME)
    select = swsscommon.Select()
    select.addSelectable(subscriber_table)

    start_time = time.time()
    state = None
    output_file = None
    table = swsscommon.Table(db, STATE_TABLE_NAME)

    while True:
        if _interrupted:
            print_error("\nInterrupted by user (Ctrl+C)")
            break

        if time.time() - start_time >= timeout_with_buffer:
            print_verbose(f"Timeout waiting for session completion (waited {timeout_with_buffer}s)", file=sys.stderr)
            print_verbose(f"Last known state: {state}")
            return state, output_file

        (status, selectable) = select.select(timeout=1000)

        if status == swsscommon.Select.TIMEOUT:
            continue
        elif status == swsscommon.Select.ERROR:
            print_verbose("Error in select", file=sys.stderr)
            break

        (key, op, fvs) = subscriber_table.pop()

        if key is None:
            continue

        # Skip if this notification is not for our session
        if key != session_name:
            continue

        new_state, new_output_file = process_notification(key, op, fvs, session_name, table)
        if new_state:
            state = new_state
            if new_output_file:
                output_file = new_output_file

            if state == "completed":
                return state, output_file
            elif state == "failed":
                print_error("Session failed!")
                return state, output_file

    return state, output_file


# Mapping from numeric attribute IDs to attribute names
FLOW_ENTRY_ATTR_MAP = {
    0: "SAI_FLOW_ENTRY_ATTR_ACTION",
    1: "SAI_FLOW_ENTRY_ATTR_VERSION",
    2: "SAI_FLOW_ENTRY_ATTR_DASH_DIRECTION",
    3: "SAI_FLOW_ENTRY_ATTR_DASH_FLOW_ACTION",
    4: "SAI_FLOW_ENTRY_ATTR_METER_CLASS",
    5: "SAI_FLOW_ENTRY_ATTR_IS_UNIDIRECTIONAL_FLOW",
    6: "SAI_FLOW_ENTRY_ATTR_REVERSE_FLOW_ENI_MAC",
    7: "SAI_FLOW_ENTRY_ATTR_REVERSE_FLOW_VNET_ID",
    8: "SAI_FLOW_ENTRY_ATTR_REVERSE_FLOW_IP_PROTO",
    9: "SAI_FLOW_ENTRY_ATTR_REVERSE_FLOW_SRC_IP",
    10: "SAI_FLOW_ENTRY_ATTR_REVERSE_FLOW_DST_IP",
    11: "SAI_FLOW_ENTRY_ATTR_REVERSE_FLOW_SRC_PORT",
    12: "SAI_FLOW_ENTRY_ATTR_REVERSE_FLOW_DST_PORT",
    13: "SAI_FLOW_ENTRY_ATTR_UNDERLAY0_VNET_ID",
    14: "SAI_FLOW_ENTRY_ATTR_UNDERLAY0_SIP",
    15: "SAI_FLOW_ENTRY_ATTR_UNDERLAY0_DIP",
    16: "SAI_FLOW_ENTRY_ATTR_UNDERLAY0_DASH_ENCAPSULATION",
    17: "SAI_FLOW_ENTRY_ATTR_UNDERLAY1_VNET_ID",
    18: "SAI_FLOW_ENTRY_ATTR_UNDERLAY1_SIP",
    19: "SAI_FLOW_ENTRY_ATTR_UNDERLAY1_DIP",
    20: "SAI_FLOW_ENTRY_ATTR_UNDERLAY1_SMAC",
    21: "SAI_FLOW_ENTRY_ATTR_UNDERLAY1_DMAC",
    22: "SAI_FLOW_ENTRY_ATTR_UNDERLAY1_DASH_ENCAPSULATION",
    23: "SAI_FLOW_ENTRY_ATTR_DST_MAC",
    24: "SAI_FLOW_ENTRY_ATTR_SIP",
    25: "SAI_FLOW_ENTRY_ATTR_DIP",
    26: "SAI_FLOW_ENTRY_ATTR_SIP_MASK",
    27: "SAI_FLOW_ENTRY_ATTR_DIP_MASK",
    28: "SAI_FLOW_ENTRY_ATTR_VENDOR_METADATA",
    29: "SAI_FLOW_ENTRY_ATTR_FLOW_DATA_PB",
    30: "SAI_FLOW_ENTRY_ATTR_IP_ADDR_FAMILY",
    31: "SAI_FLOW_ENTRY_ATTR_DASH_FLOW_SYNC_STATE",
    32: "SAI_FLOW_ENTRY_ATTR_UNDERLAY0_SMAC",
    33: "SAI_FLOW_ENTRY_ATTR_UNDERLAY0_DMAC",
}

# Mapping from key field abbreviations to full names
KEY_FIELD_MAP = {
    "em": "ENI_MAC",
    "vn": "VNET_ID",
    "pr": "IP_PROTO",
    "si": "SRC_IP",
    "di": "DST_IP",
    "sp": "SRC_PORT",
    "dp": "DST_PORT",
}


def convert_flow_attributes(flow_data):
    """Convert numeric attribute IDs and key field abbreviations to string names."""
    converted = {}
    for key, value in flow_data.items():
        if key in KEY_FIELD_MAP:
            converted[KEY_FIELD_MAP[key]] = value
        elif key == "switch_id":
            converted["SWITCH_ID"] = value
        else:
            try:
                attr_id = int(key)
                attr_name = FLOW_ENTRY_ATTR_MAP.get(attr_id, key)
                converted[attr_name] = value
            except (ValueError, TypeError):
                converted[key] = value
    return converted


def extract_flows_from_file(file_path):
    """Extract flows from gzipped JSONL file and return as list of JSON objects with converted attribute names."""
    if not file_path or not os.path.exists(file_path):
        return []

    flows = []
    try:
        with gzip.open(file_path, 'rt', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        flow_data = json.loads(line)
                        converted_flow = convert_flow_attributes(flow_data)
                        flows.append(converted_flow)
                    except json.JSONDecodeError:
                        continue
    except Exception:
        pass

    return flows


def print_flows(file_path, file_only=False):
    """Print the output file path and flows."""
    if not file_path:
        return

    if file_only:
        print(file_path)
        return

    if not os.path.exists(file_path):
        print_verbose(f"Output file does not exist: {file_path}", file=sys.stderr)
        print_verbose("This may indicate that no flows were dumped (empty result)", file=sys.stderr)
        return

    flows = extract_flows_from_file(file_path)
    if len(flows) == 0:
        print_verbose("No flows found in dump file", file=sys.stderr)
        print("[]")
        return

    print(json.dumps(flows, indent=2))


def is_dpu_type():
    """Check if switch type is DPU from CONFIG_DB."""
    try:
        config_db = swsscommon.DBConnector("CONFIG_DB", 0, True)
        table = swsscommon.Table(config_db, "DEVICE_METADATA")
        exists, switch_type = table.hget("localhost", "switch_type")

        if not exists:
            print_error("Error: switch_type not found in DEVICE_METADATA")
            return False

        if switch_type.upper() != "DPU":
            print_error(f"Error: This script is only for DPU switches. Current switch_type: {switch_type}")
            return False

        return True
    except Exception as e:
        print_error(f"Error checking switch type: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Trigger DPU flow dump session and dump the flows to stdout'
    )
    parser.add_argument(
        '--no-flow-state',
        action='store_false',
        dest='flow_state',
        default=True,
        help='Disable flow state (default: enabled)'
    )
    parser.add_argument(
        '-f', '--file-only',
        action='store_true',
        help='Print only the output file path'
    )
    parser.add_argument(
        '-t', '--timeout',
        type=int,
        default=60,
        help='Timeout in seconds (default: 60)'
    )
    parser.add_argument(
        '-m', '--max-flows',
        type=int,
        default=1000,
        help='Maximum number of flows to dump (default: 1000)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    global _verbose
    _verbose = args.verbose

    # Check switch type before proceeding
    if not is_dpu_type():
        sys.exit(1)

    session_name = create_config_file(
        CONFIG_FILE_PATH,
        max_flows=args.max_flows,
        timeout=args.timeout,
        flow_state=args.flow_state
    )

    if session_name is None:
        sys.exit(1)

    print_verbose(f"Using session name: {session_name}")

    if not trigger_flow_dump(CONFIG_FILE_PATH):
        sys.exit(1)

    state, output_file = wait_for_completion(session_name, args.timeout)

    if state == "completed":
        if output_file:
            print_flows(output_file, args.file_only)
        else:
            print_verbose("Session completed but no output file specified.")
            print_verbose("This may indicate that no flows matched the criteria or no flows exist.")
    elif state == "failed":
        print_error("Flow dump session failed. Check logs for details.")
        sys.exit(1)
    else:
        print_verbose(f"Flow dump session ended with state: {state}")
        if output_file:
            print_flows(output_file, args.file_only)
        elif state:
            print_verbose(f'Session state is "{state}" but no output file available.')


if __name__ == "__main__":
    main()

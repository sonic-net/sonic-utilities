#!/usr/bin/env python3
#
# Copyright (c) 2024 Cisco Systems, Inc.
#

import argparse
import json
import os
import subprocess
from sonic_py_common import device_info

UART_CON = '/usr/bin/picocom'


def get_dpu_tty(dpu, tty, baud):

    platform = device_info.get_platform()
    if not platform:
        print("No platform")
        return None

    # Get platform path.
    platform_path = device_info.get_path_to_platform_dir()

    if os.path.isfile(os.path.join(platform_path, device_info.PLATFORM_JSON_FILE)):
        json_file = os.path.join(platform_path, device_info.PLATFORM_JSON_FILE)

        try:
            with open(json_file, 'r') as file:
                platform_data = json.load(file)
        except (json.JSONDecodeError, IOError, TypeError, ValueError):
            print("No platform.json")
            return None

    dpus = platform_data.get('DPUS', None)
    if dpus is None:
        print("No DPUs in platform.json")
        return None

    if tty is None:
        dev = dpus[dpu]["serial-console"]["device"]
    else:
        # overwrite tty device in platform.json
        dev = tty

    if baud is None:
        baud = dpus[dpu]["serial-console"]["baud-rate"]

    post_cmds = dpus[dpu].get("tty-post-cmds")

    return dev, baud, post_cmds


def main():

    parser = argparse.ArgumentParser(description='DPU TTY Console Utility')
    parser.add_argument('-n', '--name', required=True)
    parser.add_argument('-t', '--tty')
    parser.add_argument('-b', '--baud')
    args = parser.parse_args()

    dpu_tty, dpu_baud, post_cmds = get_dpu_tty(args.name, args.tty, args.baud)
    # Use UART console utility for error checking of dpu_tty and dpu_baud.

    p = subprocess.run([UART_CON, '-b', dpu_baud, '/dev/%s' % dpu_tty])
    if p.returncode:
        print('{} failed'.format(p.args))
        if p.stdout:
            print(p.stdout)
        if p.stderr:
            print(p.stderr)
        return p.returncode

    # Execute tty-post-cmds only if it exists
    if post_cmds:
        print(f"Executing post commands: {post_cmds}")
        for cmd in post_cmds:
            if 'echo' in cmd:
                subprocess.run(['bash', '-c', cmd])
            else:
                subprocess.run(cmd.split())
    return 0

if __name__ == "__main__":
    exit(main())

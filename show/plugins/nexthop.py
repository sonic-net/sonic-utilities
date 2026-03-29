#!/usr/bin/env python
"""
Nexthop BMC CLI extensions
Adds Switch-Host Serial Number to 'show version' output

Only activates on Nexthop platforms with Aspeed BMC
Reference: device/nexthop/arm64-nexthop_b27-r0/
"""

import click
import sys
from io import StringIO
from sonic_py_common import device_info
from swsscommon.swsscommon import SonicV2Connector


def register(cli):
    """
    Register Nexthop-specific CLI enhancements.
    Only activates on Nexthop platforms with Aspeed ASIC/BMC.
    """
    # Check 1: Must be a Nexthop platform
    platform_info = device_info.get_platform_info()
    platform = platform_info.get('platform', '')

    if 'nexthop' not in platform.lower():
        return

    # Check 2: Must be Aspeed BMC (not x86 switch)
    version_info = device_info.get_sonic_version_info()
    asic_type = version_info.get('asic_type', '') if version_info else ''

    if asic_type != 'aspeed':
        return

    # Both checks passed - this is a Nexthop Aspeed BMC platform
    version_cmd = cli.commands.get('version')
    if not version_cmd or not version_cmd.callback:
        return

    original_callback = version_cmd.callback

    def nexthop_version_wrapper(verbose):
        """
        Enhanced version command that inserts Switch-Host Serial after Serial Number.
        """
        # Capture the original output
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            # Call original show version
            original_callback(verbose)

            # Get the captured output
            output = captured_output.getvalue()

            # Get switch-host serial from DB
            switch_host_serial = None
            try:
                db = SonicV2Connector()
                db.connect(db.STATE_DB)
                switch_host_serial = db.get(db.STATE_DB, 'CHASSIS_INFO|chassis 1', 'switch_host_serial')
                db.close()

                if switch_host_serial and isinstance(switch_host_serial, bytes):
                    switch_host_serial = switch_host_serial.decode('utf-8')
            except Exception:
                pass

            # Insert the switch-host serial after "Serial Number:" line
            if switch_host_serial:
                lines = output.split('\n')
                new_lines = []
                for line in lines:
                    new_lines.append(line)
                    if line.startswith('Serial Number:'):
                        new_lines.append(f'Switch-Host Serial Number: {switch_host_serial}')
                output = '\n'.join(new_lines)

        finally:
            # Restore stdout
            sys.stdout = old_stdout

        # Print the modified output
        click.echo(output, nl=False)

    version_cmd.callback = nexthop_version_wrapper


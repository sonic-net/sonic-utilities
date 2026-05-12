#!/usr/bin/env python3

import click
from tabulate import tabulate
from natsort import natsorted
import utilities_common.cli as clicommon


def get_monitor_link_member_info(state_db, interface_name):
    """Get monitor link member information from STATE_DB"""
    member_key = f"MONITOR_LINK_GROUP_MEMBER|{interface_name}"
    member_data = state_db.get_all(state_db.STATE_DB, member_key)

    if not member_data:
        return None

    return {
        'state': member_data.get('state', ''),
        'down_due_to': member_data.get('down_due_to', '')
    }


def get_monitor_link_groups(state_db):
    """Get all monitor link groups from STATE_DB"""
    groups = {}

    # Get all monitor link group states (which contain all the info we need)
    state_keys = state_db.keys(state_db.STATE_DB, 'MONITOR_LINK_GROUP_STATE|*')
    for key in state_keys or []:
        group_name = key.split('|', 1)[1] if '|' in key else key
        state_data = state_db.get_all(state_db.STATE_DB, key)
        if state_data:
            interfaces = []

            # Parse monitored-links from monitored-links field (comma-separated list)
            monitored_str = state_data.get('monitored-links', '')
            if monitored_str:
                for monitored in monitored_str.split(','):
                    monitored = monitored.strip()
                    if monitored:
                        interfaces.append({
                            'name': monitored,
                            'link_type': 'monitored'
                        })

            # Parse managed-links from managed-links field (comma-separated list)
            managed_str = state_data.get('managed-links', '')
            if managed_str:
                for managed in managed_str.split(','):
                    managed = managed.strip()
                    if managed:
                        interfaces.append({
                            'name': managed,
                            'link_type': 'managed'
                        })

            # Handle empty values by providing defaults
            description = state_data.get('description', '').strip()
            min_monitored_links = state_data.get('link_up_threshold', '').strip() or '1'
            linkup_delay = state_data.get('link_up_delay', '').strip() or '0'

            groups[group_name] = {
                'description': description or 'No description',
                'min_monitored_links': min_monitored_links,
                'linkup_delay': linkup_delay,
                'interfaces': interfaces,
                'state': state_data.get('state', 'unknown'),
            }

    return groups


def format_group_state(state):
    """Format group state with colors"""
    if state.lower() == 'up':
        return click.style("UP", fg='green', bold=True)
    elif state.lower() == 'down':
        return click.style("DOWN", fg='red', bold=True)
    else:
        return click.style(state.upper(), fg='yellow', bold=True)


@click.command(name='monitor-link-group')
@click.argument('group_name', required=False)
@clicommon.pass_db
def monitor_link(db, group_name):
    """Show monitor link information for all groups or a specific group"""

    # Get monitor link groups from STATE_DB (contains all needed info)
    groups = get_monitor_link_groups(db.db)

    if not groups:
        click.echo("No monitor link groups configured")
        return

    # Filter by specific group if provided
    if group_name:
        if group_name not in groups:
            click.echo(f"Monitor link group '{group_name}' not found")
            return
        groups = {group_name: groups[group_name]}

    # Display information for each group
    for name in natsorted(groups.keys()):
        group_data = groups[name]

        # Count monitored / managed interfaces
        monitored_count = len([intf for intf in group_data['interfaces']
                              if intf['link_type'] == 'monitored'])
        managed_count = len([intf for intf in group_data['interfaces']
                            if intf['link_type'] == 'managed'])

        # Always calculate monitored-links up for real-time accuracy
        actual_monitored_up = 0
        for intf in group_data['interfaces']:
            if intf['link_type'] == 'monitored':
                status = clicommon.get_interface_operational_status(db.db, intf['name'])
                if status == 'UP':
                    actual_monitored_up += 1
        monitored_up_count_display = str(actual_monitored_up)

        # Display group header
        click.echo(f"Monitor Link Group: {name}")
        click.echo("=" * (len(name) + 20))
        click.echo(f"Description:           {group_data['description']}")
        click.echo(f"State:                 {format_group_state(group_data.get('state', 'unknown'))}")
        click.echo(f"Monitored Up:          {monitored_up_count_display}/{monitored_count}")
        click.echo(f"Min-monitored-links:   {group_data['min_monitored_links']}")
        click.echo(f"Link-up-delay:         {group_data['linkup_delay']} seconds")
        click.echo(f"Total Interfaces:      {len(group_data['interfaces'])} "
                   f"({monitored_count} monitored, {managed_count} managed)")
        click.echo()

        # Display interfaces table
        if group_data['interfaces']:
            click.echo("Interfaces:")
            click.echo("-" * 50)

            # Sort interfaces by link type (monitored first, then managed) and then by name
            def sort_key(interface):
                link_type_priority = 0 if interface['link_type'] == 'monitored' else 1
                return (link_type_priority, interface['name'])

            sorted_interfaces = sorted(group_data['interfaces'], key=sort_key)

            table_data = []
            headers = ['Interface', 'Link Type', 'Status', 'Reason']

            for interface in sorted_interfaces:
                interface_status = clicommon.get_interface_operational_status(db.db, interface['name'])
                reason = ""

                # For managed interfaces that are DOWN, get the reason
                if interface['link_type'] == 'managed' and interface_status == 'DOWN':
                    member_info = get_monitor_link_member_info(db.db, interface['name'])
                    if member_info and member_info['down_due_to']:
                        reason = f"Down due to group {member_info['down_due_to']}"

                table_data.append([
                    interface['name'],
                    interface['link_type'],
                    interface_status,
                    reason
                ])

            click.echo(tabulate(table_data, headers=headers, tablefmt='simple'))
        else:
            click.echo("No interfaces configured")

        click.echo()  # Add spacing between groups

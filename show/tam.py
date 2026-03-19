#!/usr/bin/env python3
"""
CLI commands for displaying TAM (Telemetry and Monitoring) information.

Implements:
- show tam mod sessions: Display drop monitor session information
"""

import click
import json as json_module
import utilities_common.cli as clicommon

from swsscommon.swsscommon import SonicV2Connector
from tabulate import tabulate


# STATE_DB table name for drop monitor sessions
STATE_TAM_DROP_MONITOR_SESSION_TABLE = "TAM_DROP_MONITOR_SESSION_TABLE"


class TamModShow:
    """Class to handle TAM MOD (Mirror-on-Drop) show commands."""

    def __init__(self):
        self.state_db = SonicV2Connector(use_unix_socket_path=True)
        self.state_db.connect(self.state_db.STATE_DB)

    def get_session_keys(self):
        """Get all drop monitor session keys from STATE_DB."""
        pattern = f"{STATE_TAM_DROP_MONITOR_SESSION_TABLE}|*"
        keys = self.state_db.keys(self.state_db.STATE_DB, pattern)
        return keys if keys else []

    def get_session_entry(self, key):
        """Get a single drop monitor session entry from STATE_DB."""
        entry = self.state_db.get_all(self.state_db.STATE_DB, key)
        if entry:
            # Extract session name from key (format: TABLE_NAME|session_name)
            session_name = key.split("|", 1)[1] if "|" in key else key
            entry["session_name"] = session_name
        return entry

    def get_all_sessions(self):
        """Get all drop monitor sessions."""
        sessions = []
        keys = self.get_session_keys()
        for key in keys:
            entry = self.get_session_entry(key)
            if entry:
                sessions.append(entry)
        return sessions

    def format_table_output(self, sessions):
        """Format sessions as a table."""
        # Define table headers (in requested order)
        header = ["Session", "Status", "Event Type", "Drop Stages", "Collectors", "Flow Group", "Report Type"]

        body = []
        for session in sessions:
            # Get status and format it
            status = session.get("status", "")
            status = status.capitalize() if status else ""  # "inactive" -> "Inactive", "active" -> "Active"
            if status == "Inactive":
                status_detail = session.get("status_detail")
                if status_detail:
                    status = f"{status} ({status_detail})"

            row = [
                session.get("session_name", ""),
                status,
                session.get("event_type", ""),
                session.get("drop_stages", ""),
                session.get("collectors", ""),
                session.get("flow_group", ""),
                session.get("report_type", ""),
            ]
            body.append(row)

        return header, body

    def format_json_output(self, sessions):
        """Format sessions for JSON output."""
        # Keep only relevant fields in requested order
        output = []
        for session in sessions:
            filtered = {
                "session_name": session.get("session_name", ""),
                "status": session.get("status", ""),
                "event_type": session.get("event_type", ""),
                "drop_stages": session.get("drop_stages", ""),
                "collectors": session.get("collectors", ""),
                "flow_group": session.get("flow_group", ""),
                "report_type": session.get("report_type", ""),
                "status_detail": session.get("status_detail", "")
            }
            output.append(filtered)
        return output


@click.group(cls=clicommon.AliasedGroup)
def tam():
    """Show TAM (Telemetry and Monitoring) information"""
    pass


@tam.group(cls=clicommon.AliasedGroup)
def mod():
    """Show TAM MOD (Mirror-on-Drop) information"""
    pass


@mod.command('sessions')
@click.option('--json', '-j', 'json_output', is_flag=True, default=False,
              help="Display the output in JSON format")
def sessions(json_output):
    """Show TAM drop monitor sessions"""
    try:
        tam_show = TamModShow()
        session_list = tam_show.get_all_sessions()

        if json_output:
            output = tam_show.format_json_output(session_list)
            click.echo(json_module.dumps(output, indent=2))
        else:
            header, body = tam_show.format_table_output(session_list)
            click.echo(tabulate(body, header))

    except Exception as e:
        click.echo(f"Error retrieving TAM MOD sessions: {e}", err=True)
        raise click.Abort()

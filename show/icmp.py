#!/usr/bin/env python3

import click
import utilities_common.cli as clicommon
import socket

from swsscommon.swsscommon import SonicV2Connector
from sonic_py_common import multi_asic
from tabulate import tabulate


class IcmpShow:
    def __init__(self, click):
        self.click = click
        namespaces = multi_asic.get_front_end_namespaces()
        self.asic_ids = []
        self.per_npu_statedb = {}
        self.icmp_echo_table_keys = {}
        self.ctx = self.click.get_current_context()
        for namespace in namespaces:
            asic_id = multi_asic.get_asic_index_from_namespace(namespace)
            self.asic_ids.append(asic_id)
            self.per_npu_statedb[asic_id] = SonicV2Connector(use_unix_socket_path=False, namespace=namespace)
            try:
                self.per_npu_statedb[asic_id].connect(self.per_npu_statedb[asic_id].STATE_DB)
                self.icmp_echo_table_keys[asic_id] = sorted(
                        self.per_npu_statedb[asic_id].keys(self.per_npu_statedb[asic_id].STATE_DB,
                                                           'ICMP_ECHO_SESSION_TABLE|*'))
            except (socket.error, IOError) as e:
                self.ctx.fail("Socket error in connecting with ICMP_ECHO_SESSION_TABLE: {}".format(str(e)))
            except (KeyError, ValueError) as e:
                self.ctx.fail("Error getting keys from ICMP_ECHO_SESSION_TABLE: {}".format(str(e)))

    def get_icmp_echo_entry(self, asic_id, key):
        """Show icmp echo session entry from state db."""
        state_db = self.per_npu_statedb[asic_id]
        tbl_dict = state_db.get_all(state_db.STATE_DB, key)
        if tbl_dict:
            # Prepare data for tabulate
            fields = {
                "key": key.removeprefix("ICMP_ECHO_SESSION_TABLE|"),
                "state": None,
                "dst_ip": None,
                "tx_interval": None,
                "rx_interval": None,
                "hw_lookup": None,
                "session_cookie": None
            }
            for f in tbl_dict:
                if f in fields:
                    fields[f] = tbl_dict[f]
            return [fields["key"], fields["dst_ip"], fields["tx_interval"], fields["rx_interval"], fields["hw_lookup"],
                    fields["session_cookie"], fields["state"]]
        else:
            return None

    def show_icmp_sessions(self, key):
        table_data = []
        for asic_id in self.asic_ids:
            keys = []
            if key is None:
                keys = self.icmp_echo_table_keys[asic_id]
            else:
                keys.append("ICMP_ECHO_SESSION_TABLE|" + key.replace(":", "|"))

            for k in keys:
                entry = self.get_icmp_echo_entry(asic_id, k)
                if entry:
                    table_data.append(entry)

        if table_data:
            headers = ["Key", "Dst IP", "Tx Interval", "Rx Interval", "HW lookup", "Cookie", "State"]
            click.echo(tabulate(table_data, headers=headers))
        else:
            click.echo("Keys not found in ICMP_ECHO_SESSION_TABLE")

    def show_summary(self):
        total_sessions = 0
        total_up = 0
        total_rx = 0
        for asic_id in self.asic_ids:
            keys = self.icmp_echo_table_keys[asic_id]

            for k in keys:
                if 'RX' in k:
                    total_rx = total_rx + 1
                entry = self.get_icmp_echo_entry(asic_id, k)
                total_sessions = total_sessions + 1
                if entry and entry[6] == "Up":
                    total_up = total_up + 1

            self.click.echo("Total Sessions: {}".format(total_sessions))
            self.click.echo("Up sessions: {}".format(total_up))
            self.click.echo("RX sessions: {}".format(total_rx))


@click.group(cls=clicommon.AliasedGroup)
def icmp():
    """Show icmp-offload information"""
    pass


@icmp.command()
@click.argument('key', required=False)
def sessions(key):
    s_icmp = IcmpShow(click)
    s_icmp.show_icmp_sessions(key)


@icmp.command()
def summary():
    s_icmp = IcmpShow(click)
    s_icmp.show_summary()

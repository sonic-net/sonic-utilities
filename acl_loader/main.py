
#!/usr/bin/env python

import click
import sys
import os.path
import json
import argparse
import tabulate

import openconfig_acl
import pyangbind.lib.pybindJSON as pybindJSON
from swsssdk import ConfigDBConnector


def info(msg):
    click.echo(click.style("Info: ", fg='cyan') + click.style(str(msg), fg='green'))


def warning(msg):
    click.echo(click.style("Warning: ", fg='cyan') + click.style(str(msg), fg='yellow'))


def error(msg):
    click.echo(click.style("Error: ", fg='cyan') + click.style(str(msg), fg='red'))


def deep_update(dst, src):
    for key, value in src.iteritems():
        if isinstance(value, dict):
            node = dst.setdefault(key, {})
            deep_update(node, value)
        else:
            dst[key] = value
    return dst


class AclLoaderException(Exception):
    pass


class AclLoader(object):

    ACL_TABLE = "ACL_TABLE"
    ACL_RULE = "ACL_RULE"
    MIRROR_SESSION = "MIRROR_SESSION"
    SESSION_PREFIX = "everflow"

    min_priority = 1
    max_priority = 10000

    ethertype_map = {
        "ETHERTYPE_LLDP": 0x88CC,
        "ETHERTYPE_VLAN": 0x8100,
        "ETHERTYPE_ROCE": 0x8915,
        "ETHERTYPE_ARP": 0x0806,
        "ETHERTYPE_IPV4": 0x0800,
        "ETHERTYPE_IPV6": 0x86DD,
        "ETHERTYPE_MPLS": 0x8847
    }

    ip_protocol_map = {
        "IP_TCP": 6,
        "IP_ICMP": 1,
        "IP_UDP": 17,
        "IP_IGMP": 2,
        "IP_PIM": 103,
        "IP_RSVP": 46,
        "IP_GRE": 47,
        "IP_AUTH": 51,
        "IP_L2TP": 115
    }

    def __init__(self):
        self.yang_acl = None
        self.requested_session = None
        self.tables_db_info = {}
        self.rules_db_info = {}
        self.rules_info = {}
        self.sessions_db_info = {}
        self.configdb = ConfigDBConnector()
        self.configdb.connect()

        self.read_tables_info()
        self.read_rules_info()
        self.read_sessions_info()

    def read_tables_info(self):
        """
        Read ACL tables information from Config DB
        :return:
        """
        self.tables_db_info = self.configdb.get_table(self.ACL_TABLE)

    def get_tables_db_info(self):
        return self.tables_db_info

    def read_rules_info(self):
        """
        Read rules information from Config DB
        :return:
        """
        self.rules_db_info = self.configdb.get_table(self.ACL_RULE)

    def get_rules_db_info(self):
        return self.rules_db_info

    def read_sessions_info(self):
        """
        Read ACL tables information from Config DB
        :return:
        """
        self.sessions_db_info = self.configdb.get_table(self.MIRROR_SESSION)

    def get_sessions_db_info(self):
        """
        Read mirror session information from Config DB
        :return:
        """
        return self.sessions_db_info

    def get_session_name(self):
        """
        Read mirror session name from Config DB
        :return: Mirror session name
        """
        if self.requested_session:
            return self.requested_session

        for key in self.get_sessions_db_info():
            if key.startswith(self.SESSION_PREFIX):
                return key

        return None

    def set_session_name(self, session_name):
        """
        Set session name to se used in ACL rule action.
        :param session_name: Mirror session name
        """
        if session_name not in self.get_sessions_db_info():
            raise AclLoaderException("Session %s does not exist" % session_name)

        self.requested_session = session_name

    def is_table_valid(self, tname):
        return self.tables_db_info.get(tname)

    def is_table_mirror(self, tname):
        """
        Check if ACL table type is MIRROR
        :param tname: ACL table name
        :return: True if table type is MIRROR else False
        """
        return self.tables_db_info[tname]['type'].upper() == "MIRROR"

    def load_rules_from_file(self, filename):
        """
        Load file with ACL rules configuration in openconfig ACL format. Convert rules
        to Config DB schema.
        :param filename: File in openconfig ACL format
        :return:
        """
        self.yang_acl = pybindJSON.load(filename, openconfig_acl, "openconfig_acl")
        self.convert_rules()

    def convert_action(self, table_name, rule_idx, rule):
        rule_props = {}

        if rule.actions.config.forwarding_action == "ACCEPT":
            if self.is_table_mirror(table_name):
                session_name = self.get_session_name()
                if not session_name:
                    raise AclLoaderException("Mirroring session does not exist")

                rule_props["MIRROR_ACTION"] = session_name
            else:
                rule_props["PACKET_ACTION"] = "FORWARD"
        elif rule.actions.config.forwarding_action == "DROP":
            rule_props["PACKET_ACTION"] = "DROP"
        elif rule.actions.config.forwarding_action == "REJECT":
            rule_props["PACKET_ACTION"] = "DROP"
        else:
            raise AclLoaderException("Unknown rule action %s in table %s, rule %d" % (
                rule.actions.config.forwarding_action, table_name, rule_idx))

        return rule_props

    def convert_l2(self, table_name, rule_idx, rule):
        rule_props = {}

        if rule.l2.config.ethertype:
            if rule.l2.config.ethertype in self.ethertype_map:
                rule_props["ETHER_TYPE"] = self.ethertype_map[rule.l2.config.ethertype]
            else:
                try:
                    rule_props["ETHER_TYPE"] = int(rule.l2.config.ethertype)
                except:
                    raise AclLoaderException("Failed to convert ethertype %s table %s rule %s" % (
                        rule.l2.config.ethertype, table_name, rule_idx))

        return rule_props

    def convert_ipv4(self, table_name, rule_idx, rule):
        rule_props = {}

        if rule.ip.config.protocol:
            if self.ip_protocol_map.has_key(rule.ip.config.protocol):
                rule_props["IP_PROTOCOL"] = self.ip_protocol_map[rule.ip.config.protocol]
            else:
                try:
                    int(rule.ip.config.protocol)
                except:
                    raise AclLoaderException("Unknown rule protocol %s in table %s, rule %d!" % (
                        rule.ip.config.protocol, table_name, rule_idx))

                rule_props["IP_PROTOCOL"] = rule.ip.config.protocol

        if rule.ip.config.source_ip_address:
            rule_props["SRC_IP"] = rule.ip.config.source_ip_address

        if rule.ip.config.destination_ip_address:
            rule_props["DST_IP"] = rule.ip.config.destination_ip_address

        # NOTE: DSCP is available only for MIRROR table
        if self.is_table_mirror(table_name):
            if rule.ip.config.dscp:
                rule_props["DSCP"] = rule.ip.config.dscp

        return rule_props

    def convert_port(self, port):
        if ".." in port:
            return  port.replace("..", "-"), True
        else:
            return port, False

    def convert_transport(self,  table_name, rule_idx, rule):
        rule_props = {}

        if rule.transport.config.source_port:
            port, is_range = self.convert_port(str(rule.transport.config.source_port))
            rule_props["L4_SRC_PORT_RANGE" if is_range else "L4_SRC_PORT"] = port
        if rule.transport.config.destination_port:
            port, is_range = self.convert_port(str(rule.transport.config.destination_port))
            rule_props["L4_DST_PORT_RANGE" if is_range else "L4_DST_PORT"] = port

        tcp_flags = 0x00

        for flag in rule.transport.config.tcp_flags:
            if flag == "TCP_FIN":
                tcp_flags = tcp_flags | 0x01
            if flag == "TCP_SYN":
                tcp_flags = tcp_flags | 0x02
            if flag == "TCP_RST":
                tcp_flags = tcp_flags | 0x04
            if flag == "TCP_PSH":
                tcp_flags = tcp_flags | 0x08
            if flag == "TCP_ACK":
                tcp_flags = tcp_flags | 0x10
            if flag == "TCP_URG":
                tcp_flags = tcp_flags | 0x20
            if flag == "TCP_ECE":
                tcp_flags = tcp_flags | 0x40
            if flag == "TCP_CWR":
                tcp_flags = tcp_flags | 0x80

        if tcp_flags:
            rule_props["TCP_FLAGS"] = '0x{:02x}/0x{:02x}'.format(tcp_flags, tcp_flags)

        return rule_props

    def convert_rule_to_db_schema(self, table_name, rule):
        """
        Convert rules format from openconfig ACL to Config DB schema
        :param table_name: ACL table name to which rule belong
        :param rule: ACL rule in openconfig format
        :return: dict with Config DB schema
        """
        rule_idx = int(rule.config.sequence_id)
        rule_props = {}
        rule_data = {(table_name, "RULE_" + str(rule_idx)): rule_props}

        rule_props["PRIORITY"] = self.max_priority - rule_idx

        deep_update(rule_props, self.convert_action(table_name, rule_idx, rule))
        deep_update(rule_props, self.convert_l2(table_name, rule_idx, rule))
        deep_update(rule_props, self.convert_ipv4(table_name, rule_idx, rule))
        deep_update(rule_props, self.convert_transport(table_name, rule_idx, rule))

        return rule_data

    def deny_rule(self, table_name):
        """
        Create default deny rule in Config DB format
        :param table_name: ACL table name to which rule belong
        :return: dict with Config DB schema
        """
        rule_props = {}
        rule_data = {(table_name, "DEFAULT_RULE"): rule_props}
        rule_props["PRIORITY"] = self.min_priority
        rule_props["ETHER_TYPE"] = "0x0800"
        rule_props["PACKET_ACTION"] = "DROP"
        return rule_data

    def convert_rules(self):
        """
        Convert rules in openconfig ACL format to Config DB schema
        :return:
        """
        for acl_set_name in self.yang_acl.acl.acl_sets.acl_set:
            table_name = acl_set_name.replace(" ", "_").replace("-", "_").upper()
            acl_set = self.yang_acl.acl.acl_sets.acl_set[acl_set_name]

            if not self.is_table_valid(table_name):
                warning("%s table does not exist" % (table_name))
                continue

            for acl_entry_name in acl_set.acl_entries.acl_entry:
                acl_entry = acl_set.acl_entries.acl_entry[acl_entry_name]
                rule = self.convert_rule_to_db_schema(table_name, acl_entry)
                deep_update(self.rules_info, rule)

            if not self.is_table_mirror(table_name):
                deep_update(self.rules_info, self.deny_rule(table_name))

    def full_update(self):
        """
        Perform full update of ACL rules configuration. All existing rules
        will be removed. New rules loaded from file will be installed.
        :return:
        """
        for key in self.rules_db_info.keys():
            self.configdb.set_entry(self.ACL_RULE, key, None)

        self.configdb.set_config({self.ACL_RULE: self.rules_info})

    def incremental_update(self):
        """
        Perform incremental ACL rules configuration update. Get existing rules from
        Config DB. Compare with rules specified in file and perform corresponding
        modifications.
        :return:
        """
        new_rules = set(self.rules_info.iterkeys())
        current_rules = set(self.rules_db_info.iterkeys())

        added_rules = new_rules.difference(current_rules)
        removed_rules = current_rules.difference(new_rules)
        existing_rules = new_rules.intersection(current_rules)

        for key in removed_rules:
            self.configdb.set_entry(self.ACL_RULE, key, None)

        for key in added_rules:
            self.configdb.set_entry(self.ACL_RULE, key, self.rules_info[key])

        for key in existing_rules:
            if not cmp(self.rules_info[key], self.rules_db_info[key]):
                self.configdb.set_entry(self.ACL_RULE, key, None)
                self.configdb.set_entry(self.ACL_RULE, key, self.rules_info[key])

    def show_table(self, table_name):
        """
        Show ACL table configuration.
        :param table_name: Optional. ACL table name. Filter tables by specified name.
        :return:
        """
        header = ("Name", "Type", "Ports", "Description")

        data = []
        for key, val in self.get_tables_db_info().iteritems():
            if table_name and key != table_name:
                continue

            if not val["ports"]:
                data.append([key, val["type"], "", val["policy_desc"]])
            else:
                ports = sorted(val["ports"], )
                data.append([key, val["type"], ports[0], val["policy_desc"]])

                if len(ports) > 1:
                    for port in ports[1:]:
                        data.append(["", "", port, ""])

        print(tabulate.tabulate(data, headers=header, tablefmt="simple", missingval=""))

    def show_session(self, session_name):
        """
        Show mirror session configuration.
        :param session_name: Optional. Mirror session name. Filter sessions by specified name.
        :return:
        """
        header = ("Name", "SRC IP", "DST IP", "GRE", "DSCP", "TTL", "Queue", "TOS")

        data = []
        for key, val in self.get_sessions_db_info().iteritems():
            if session_name and key != session_name:
                continue

            data.append([key, val["src_ip"], val["dst_ip"],
                         val.get("gre_type", ""), val.get("dscp", ""),
                         val.get("ttl", ""), val.get("queue", ""), val.get("tos", "")])

        print(tabulate.tabulate(data, headers=header, tablefmt="simple", missingval=""))

    def show_rule(self, table_name, rule_id):
        """
        Show ACL rules configuration.
        :param table_name: Optional. ACL table name. Filter rules by specified table name.
        :param rule_id: Optional. ACL rule name. Filter rule by specified rule name.
        :return:
        """
        header = ("Rule ID", "Table Name", "Priority", "Action", "Match")

        ignore_list = ["PRIORITY", "PACKET_ACTION", "MIRROR_ACTION"]

        raw_data = []
        for (tname, rid), val in self.get_rules_db_info().iteritems():

            if table_name and table_name != tname:
                continue

            if rule_id and rule_id != rid:
                continue

            priority = val["PRIORITY"]

            action = ""
            if "PACKET_ACTION" in val:
                action = val["PACKET_ACTION"]
            elif "MIRROR_ACTION" in val:
                action = "MIRROR: %s" % val["MIRROR_ACTION"]
            else:
                continue

            matches = ["%s: %s" % (k, v) for k, v in val.iteritems() if k not in ignore_list]

            matches.sort()

            rule_data = [[tname, rid, priority, action, matches[0]]]
            if len(matches) > 1:
                for m in matches[1:]:
                    rule_data.append(["", "", "", "", m])

            raw_data.append([priority, rule_data])

        def cmp_rules(a, b):
            return cmp(a[0], b[0])

        raw_data.sort(cmp_rules)
        raw_data.reverse()

        data = []
        for _, d in raw_data:
            data += d

        print(tabulate.tabulate(data, headers=header, tablefmt="simple", missingval=""))


@click.group()
@click.pass_context
def cli(ctx):
    """
    Utility entry point.
    """
    context = {
        "acl_loader": AclLoader()
    }

    ctx.obj = context


@cli.group()
@click.pass_context
def show(ctx):
    """
    Show ACL configuration.
    """
    pass


@show.command()
@click.argument('table_name', type=click.STRING, required=False)
@click.pass_context
def table(ctx, table_name):
    """
    Show ACL tables configuration.
    :return:
    """
    acl_loader = ctx.obj["acl_loader"]
    acl_loader.show_table(table_name)


@show.command()
@click.argument('session_name', type=click.STRING, required=False)
@click.pass_context
def session(ctx, session_name):
    """
    Show mirror session configuration.
    :return:
    """
    acl_loader = ctx.obj["acl_loader"]
    acl_loader.show_session(session_name)


@show.command()
@click.argument('table_name', type=click.STRING, required=False)
@click.argument('rule_id', type=click.STRING, required=False)
@click.pass_context
def rule(ctx, table_name, rule_id):
    """
    Show ACL rule configuration.
    :return:
    """
    acl_loader = ctx.obj["acl_loader"]
    acl_loader.show_rule(table_name, rule_id)


@cli.group()
@click.pass_context
def update(ctx):
    """
    Update ACL rules configuration.
    """
    pass


@update.command()
@click.argument('filename', type=click.Path(exists=True))
@click.option('--session_name', type=click.STRING, required=False)
@click.pass_context
def full(ctx, filename, session_name):
    """
    Full update of ACL rules configuration.
    """
    acl_loader = ctx.obj["acl_loader"]

    if session_name:
        acl_loader.set_session_name(session_name)

    acl_loader.load_rules_from_file(filename)
    acl_loader.full_update()


@update.command()
@click.argument('filename', type=click.Path(exists=True))
@click.option('--session_name', type=click.STRING, required=False)
@click.pass_context
def incremental(ctx, filename, session_name):
    """
    Incremental update of ACL rule configuration.
    """
    acl_loader = ctx.obj["acl_loader"]

    if session_name:
        acl_loader.set_session_name(session_name)

    acl_loader.load_rules_from_file(filename)
    acl_loader.incremental_update()


if __name__ == "__main__":
    try:
        cli()
    except AclLoaderException as e:
        error(e)
    except Exception as e:
        error("Unknown error: %s" % repr(e))

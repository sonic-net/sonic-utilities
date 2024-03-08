#!/usr/bin/env python3

import click
import ipaddress
import json
import syslog
import operator

import openconfig_acl
import tabulate
import pyangbind.lib.pybindJSON as pybindJSON
from natsort import natsorted
from sonic_py_common import multi_asic
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector
from utilities_common.general import load_db_config

def info(msg):
    click.echo(click.style("Info: ", fg='cyan') + click.style(str(msg), fg='green'))
    syslog.syslog(syslog.LOG_INFO, msg)


def warning(msg):
    click.echo(click.style("Warning: ", fg='cyan') + click.style(str(msg), fg='yellow'))
    syslog.syslog(syslog.LOG_WARNING, msg)


def error(msg):
    click.echo(click.style("Error: ", fg='cyan') + click.style(str(msg), fg='red'))
    syslog.syslog(syslog.LOG_ERR, msg)


def deep_update(dst, src):
    for key, value in src.items():
        if isinstance(value, dict):
            node = dst.setdefault(key, {})
            deep_update(node, value)
        else:
            dst[key] = value
    return dst


class AclAction:
    """ namespace for ACL action keys """

    PACKET         = "PACKET_ACTION"
    REDIRECT       = "REDIRECT_ACTION"
    MIRROR         = "MIRROR_ACTION"
    MIRROR_INGRESS = "MIRROR_INGRESS_ACTION"
    MIRROR_EGRESS  = "MIRROR_EGRESS_ACTION"


class PacketAction:
    """ namespace for ACL packet actions """

    DROP    = "DROP"
    FORWARD = "FORWARD"
    ACCEPT  = "ACCEPT"


class Stage:
    """ namespace for ACL stages """

    INGRESS = "INGRESS"
    EGRESS  = "EGRESS"


class AclLoaderException(Exception):
    pass


class AclLoader(object):

    ACL_TABLE = "ACL_TABLE"
    ACL_RULE = "ACL_RULE"
    CFG_ACL_TABLE = "ACL_TABLE"
    STATE_ACL_TABLE = "ACL_TABLE_TABLE"
    CFG_ACL_RULE = "ACL_RULE"
    STATE_ACL_RULE = "ACL_RULE_TABLE"
    ACL_TABLE_TYPE_MIRROR = "MIRROR"
    ACL_TABLE_TYPE_CTRLPLANE = "CTRLPLANE"
    CFG_MIRROR_SESSION_TABLE = "MIRROR_SESSION"
    STATE_MIRROR_SESSION_TABLE = "MIRROR_SESSION_TABLE"
    POLICER = "POLICER"
    SESSION_PREFIX = "everflow"
    SWITCH_CAPABILITY_TABLE = "SWITCH_CAPABILITY"
    ACL_STAGE_CAPABILITY_TABLE = "ACL_STAGE_CAPABILITY_TABLE"
    ACL_ACTIONS_CAPABILITY_FIELD = "action_list"
    ACL_ACTION_CAPABILITY_FIELD = "ACL_ACTION"

    min_priority = 1
    max_priority = 10000

    ethertype_map = {
        "ETHERTYPE_LLDP": 0x88CC,
        "ETHERTYPE_VLAN": 0x8100,
        "ETHERTYPE_ROCE": 0x8915,
        "ETHERTYPE_ARP":  0x0806,
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
        "IP_ICMPV6": 58,
        "IP_L2TP": 115
    }

    def __init__(self):
        self.yang_acl = None
        self.requested_session = None
        self.mirror_stage = None
        self.current_table = None
        self.tables_db_info = {}
        self.rules_db_info = {}
        self.rules_info = {}
        self.tables_state_info = None
        self.rules_state_info = None

        # Load database config files
        load_db_config()

        self.sessions_db_info = {}
        self.acl_table_status = {}
        self.acl_rule_status = {}

        self.configdb = ConfigDBConnector()
        self.configdb.connect()
        self.statedb = SonicV2Connector(host="127.0.0.1")
        self.statedb.connect(self.statedb.STATE_DB)

        # For multi-npu architecture we will have both global and per front asic namespace.
        # Global namespace will be used for Control plane ACL which are via IPTables.
        # Per ASIC namespace will be used for Data and Everflow ACL's.
        # Global Configdb will have all ACL information for both Ctrl and Data/Evereflow ACL's
        # and will be used as souurce of truth for ACL modification to config DB which will be done to both Global DB and
        # front asic namespace

        self.per_npu_configdb = {}

        # State DB are used for to get mirror Session monitor port.
        # For multi-npu platforms each asic namespace can have different monitor port
        # dependinding on which route to session destination ip. So for multi-npu
        # platforms we get state db for all front asic namespace in addition to

        self.per_npu_statedb = {}

        # Getting all front asic namespace and correspding config and state DB connector

        namespaces = multi_asic.get_all_namespaces()
        for front_asic_namespaces in namespaces['front_ns']:
            self.per_npu_configdb[front_asic_namespaces] = ConfigDBConnector(namespace=front_asic_namespaces)
            self.per_npu_configdb[front_asic_namespaces].connect()
            self.per_npu_statedb[front_asic_namespaces] = SonicV2Connector(namespace=front_asic_namespaces)
            self.per_npu_statedb[front_asic_namespaces].connect(self.per_npu_statedb[front_asic_namespaces].STATE_DB)

        self.read_tables_info()
        self.read_rules_info()
        self.read_sessions_info()
        self.read_policers_info()
        self.acl_table_status = self.read_acl_object_status_info(self.CFG_ACL_TABLE, self.STATE_ACL_TABLE)
        self.acl_rule_status = self.read_acl_object_status_info(self.CFG_ACL_RULE, self.STATE_ACL_RULE)

    def read_tables_info(self):
        """
        Read ACL_TABLE table from configuration database
        :return:
        """
        # get the acl table info from host config_db
        host_acl_table = self.configdb.get_table(self.ACL_TABLE)
        # For multi asic get only the control plane acls from the host config_db
        if self.per_npu_configdb:
            for table, entry in host_acl_table.items():
                if entry.get('type', None) != self.ACL_TABLE_TYPE_CTRLPLANE:
                    continue

                self.tables_db_info[table] = entry
        else:
            self.tables_db_info.update(host_acl_table)

        # for DATAACL, EVERFLOW acls.
        # update the ports from all the namespaces
        if self.per_npu_configdb:
            for ns, config_db in self.per_npu_configdb.items():
                acl_table = config_db.get_table(self.ACL_TABLE)
                for table, entry in acl_table.items():
                    if entry.get('type', None) == self.ACL_TABLE_TYPE_CTRLPLANE:
                        continue
                    if table not in self.tables_db_info:
                        self.tables_db_info[table] = entry
                    else:
                        self.tables_db_info[table]['ports'] += entry.get(
                            'ports', [])

    def get_tables_db_info(self):
        return self.tables_db_info

    def read_rules_info(self):
        """
        Read ACL_RULE table from configuration database
        :return:
        """
        self.rules_db_info = self.configdb.get_table(self.ACL_RULE)

    def get_rules_db_info(self):
        return self.rules_db_info

    def read_policers_info(self):
        """
        Read POLICER table from configuration database
        :return:
        """

        # For multi-npu platforms we will read from any one of front asic namespace
        # config db as the information should be same across all config db
        if self.per_npu_configdb:
            namespace_configdb = list(self.per_npu_configdb.values())[0]
            self.policers_db_info = namespace_configdb.get_table(self.POLICER)
        else:
            self.policers_db_info = self.configdb.get_table(self.POLICER)

    def get_policers_db_info(self):
        return self.policers_db_info

    def read_sessions_info(self):
        """
        Read MIRROR_SESSION table from configuration database
        :return:
        """

        # For multi-npu platforms we will read from any one of front asic namespace
        # config db as the information should be same across all config db
        if self.per_npu_configdb:
            namespace_configdb = list(self.per_npu_configdb.values())[0]
            self.sessions_db_info = namespace_configdb.get_table(self.CFG_MIRROR_SESSION_TABLE)
        else:
            self.sessions_db_info = self.configdb.get_table(self.CFG_MIRROR_SESSION_TABLE)
        for key in self.sessions_db_info:
            if self.per_npu_statedb:
                # For multi-npu platforms we will read from all front asic name space
                # statedb as the monitor port will be different for each asic
                # and it's status also might be different (ideally should not happen)
                # We will store them as dict of 'asic' : value
                self.sessions_db_info[key]["status"] = {}
                self.sessions_db_info[key]["monitor_port"] = {}
                for namespace_key, namespace_statedb in self.per_npu_statedb.items():
                    state_db_info = namespace_statedb.get_all(self.statedb.STATE_DB, "{}|{}".format(self.STATE_MIRROR_SESSION_TABLE, key))
                    self.sessions_db_info[key]["status"][namespace_key] = state_db_info.get("status", "inactive") if state_db_info else "error"
                    self.sessions_db_info[key]["monitor_port"][namespace_key] = state_db_info.get("monitor_port", "") if state_db_info else ""
            else:
                state_db_info = self.statedb.get_all(self.statedb.STATE_DB, "{}|{}".format(self.STATE_MIRROR_SESSION_TABLE, key))
                self.sessions_db_info[key]["status"] = state_db_info.get("status", "inactive") if state_db_info else "error"
                self.sessions_db_info[key]["monitor_port"] = state_db_info.get("monitor_port", "") if state_db_info else ""

    def read_acl_object_status_info(self, cfg_db_table_name, state_db_table_name):
        """
        Read ACL_TABLE status or ACL_RULE status from STATE_DB
        """
        if self.per_npu_configdb:
            namespace_configdb = list(self.per_npu_configdb.values())[0]
            keys = namespace_configdb.get_table(cfg_db_table_name).keys()
        else:
            keys = self.configdb.get_table(cfg_db_table_name).keys()

        status = {}
        for key in keys:
            # For ACL_RULE, the key is (acl_table_name, acl_rule_name)
            if isinstance(key, tuple):
                state_db_key = key[0] + "|" + key[1]
            else:
                state_db_key = key
            status[key] = {}
            if self.per_npu_statedb:
                status[key]['status'] = {}
                for namespace_key, namespace_statedb in self.per_npu_statedb.items():
                    state_db_info = namespace_statedb.get_all(self.statedb.STATE_DB, "{}|{}".format(state_db_table_name, state_db_key))
                    status[key]['status'][namespace_key] = state_db_info.get("status", "N/A") if state_db_info else "N/A"
            else:
                state_db_info = self.statedb.get_all(self.statedb.STATE_DB, "{}|{}".format(state_db_table_name, state_db_key))
                status[key]['status'] = state_db_info.get("status", "N/A") if state_db_info else "N/A"

        return status

    def get_sessions_db_info(self):
        return self.sessions_db_info

    def get_session_name(self):
        """
        Get requested mirror session name or default session
        :return: Mirror session name
        """
        if self.requested_session:
            return self.requested_session

        for key in self.get_sessions_db_info():
            if key.startswith(self.SESSION_PREFIX):
                return key

        return None

    def set_table_name(self, table_name):
        """
        Set table name to restrict the table to be modified
        :param table_name: Table name
        :return:
        """
        if not self.is_table_valid(table_name):
            warning("Table \"%s\" not found" % table_name)

        self.current_table = table_name

    def set_session_name(self, session_name):
        """
        Set session name to be used in ACL rule action
        :param session_name: Mirror session name
        :return:
        """
        if session_name not in self.get_sessions_db_info():
            raise AclLoaderException("Session %s does not exist" % session_name)

        self.requested_session = session_name

    def set_mirror_stage(self, stage):
        """
        Set mirror stage to be used in ACL mirror rule action
        :param session_name: stage 'ingress'/'egress'
        :return:
        """
        self.mirror_stage = stage.upper()

    def set_max_priority(self, priority):
        """
        Set rules max priority
        :param priority: Rules max priority
        :return:
        """
        self.max_priority = int(priority)

    def is_table_valid(self, tname):
        return self.tables_db_info.get(tname)

    def is_table_egress(self, tname):
        """
        Check if ACL table stage is egress
        :param tname: ACL table name
        :return: True if table type is Egress
        """
        return self.tables_db_info[tname].get("stage", Stage.INGRESS).upper() == Stage.EGRESS

    def is_table_mirror(self, tname):
        """
        Check if ACL table type is ACL_TABLE_TYPE_MIRROR or ACL_TABLE_TYPE_MIRRORV6
        :param tname: ACL table name
        :return: True if table type is MIRROR or MIRRORV6 else False
        """
        return self.tables_db_info[tname]['type'].upper().startswith(self.ACL_TABLE_TYPE_MIRROR)

    def is_table_l3v6(self, tname):
        """
        Check if ACL table type is L3V6
        :param tname: ACL table name
        :return: True if table type is L3V6 else False
        """
        return self.tables_db_info[tname]["type"].upper() == "L3V6"

    def is_table_l3v4v6(self, tname):
        """
        Check if ACL table type is L3V4V6
        :param tname: ACL table name
        :return: True if table type is L3V4V6 else False
        """
        return self.tables_db_info[tname]["type"].upper() == "L3V4V6"

    def is_table_l3(self, tname):
        """
        Check if ACL table type is L3
        :param tname: ACL table name
        :return: True if table type is L3 else False
        """
        return self.tables_db_info[tname]["type"].upper() == "L3"

    def is_table_ipv6(self, tname):
        """
        Check if ACL table type is IPv6 (L3V6 or MIRRORV6)
        :param tname: ACL table name
        :return: True if table type is IPv6 else False
        """
        return self.tables_db_info[tname]["type"].upper() in ("L3V6", "MIRRORV6")

    def is_table_control_plane(self, tname):
        """
        Check if ACL table type is ACL_TABLE_TYPE_CTRLPLANE
        :param tname: ACL table name
        :return: True if table type is ACL_TABLE_TYPE_CTRLPLANE else False
        """
        return self.tables_db_info[tname]['type'].upper() == self.ACL_TABLE_TYPE_CTRLPLANE

    @staticmethod
    def parse_acl_json(filename):
        yang_acl = pybindJSON.load(filename, openconfig_acl, "openconfig_acl")
        # Check pybindJSON parsing
        # pybindJSON.load will silently return an empty json object if input invalid
        with open(filename, 'r') as f:
            plain_json = json.load(f)
            if len(plain_json['acl']['acl-sets']['acl-set']) != len(yang_acl.acl.acl_sets.acl_set):
                raise AclLoaderException("Invalid input file %s" % filename)
        return yang_acl

    def load_rules_from_file(self, filename):
        """
        Load file with ACL rules configuration in openconfig ACL format. Convert rules
        to Config DB schema.
        :param filename: File in openconfig ACL format
        :return:
        """
        self.yang_acl = AclLoader.parse_acl_json(filename)
        self.convert_rules()

    def convert_action(self, table_name, rule_idx, rule):
        rule_props = {}

        if rule.actions.config.forwarding_action == "ACCEPT":
            if self.is_table_control_plane(table_name):
                rule_props[AclAction.PACKET] = PacketAction.ACCEPT
            elif self.is_table_mirror(table_name):
                session_name = self.get_session_name()
                if not session_name:
                    raise AclLoaderException("Mirroring session does not exist")

                if self.mirror_stage == Stage.INGRESS:
                    mirror_action = AclAction.MIRROR_INGRESS
                elif self.mirror_stage == Stage.EGRESS:
                    mirror_action = AclAction.MIRROR_EGRESS
                else:
                    raise AclLoaderException("Invalid mirror stage passed {}".format(self.mirror_stage))

                rule_props[mirror_action] = session_name
            else:
                rule_props[AclAction.PACKET] = PacketAction.FORWARD
        elif rule.actions.config.forwarding_action == "DROP":
            rule_props[AclAction.PACKET] = PacketAction.DROP
        elif rule.actions.config.forwarding_action == "REJECT":
            rule_props[AclAction.PACKET] = PacketAction.DROP
        else:
            raise AclLoaderException("Unknown rule action {} in table {}, rule {}".format(
                rule.actions.config.forwarding_action, table_name, rule_idx))

        if not self.validate_actions(table_name, rule_props):
            raise AclLoaderException("Rule action {} is not supported in table {}, rule {}".format(
                rule.actions.config.forwarding_action, table_name, rule_idx))

        return rule_props

    def validate_actions(self, table_name, action_props):
        if self.is_table_control_plane(table_name):
            return True

        action_count = len(action_props)

        if table_name not in self.tables_db_info:
            raise AclLoaderException("Table {} does not exist".format(table_name))

        stage = self.tables_db_info[table_name].get("stage", Stage.INGRESS)

        # check if per npu state db is there then read using first state db
        # else read from global statedb
        if self.per_npu_statedb:
            # For multi-npu we will read using anyone statedb connector for front asic namespace.
            # Same information should be there in all state DB's
            # as it is static information about switch capability
            namespace_statedb = list(self.per_npu_statedb.values())[0]
            aclcapability = namespace_statedb.get_all(self.statedb.STATE_DB, "{}|{}".format(self.ACL_STAGE_CAPABILITY_TABLE, stage.upper()))
            switchcapability = namespace_statedb.get_all(self.statedb.STATE_DB, "{}|switch".format(self.SWITCH_CAPABILITY_TABLE))
        else:
            aclcapability = self.statedb.get_all(self.statedb.STATE_DB, "{}|{}".format(self.ACL_STAGE_CAPABILITY_TABLE, stage.upper()))
            switchcapability = self.statedb.get_all(self.statedb.STATE_DB, "{}|switch".format(self.SWITCH_CAPABILITY_TABLE))
        for action_key in dict(action_props):
            action_list_key = self.ACL_ACTIONS_CAPABILITY_FIELD
            if action_list_key not in aclcapability:
                del action_props[action_key]
                continue

            values = aclcapability[action_list_key].split(",")
            if action_key.upper() not in values:
                del action_props[action_key]
                continue

            if action_key == AclAction.PACKET:
                # Check if action_value is supported
                action_value = action_props[action_key]
                key = "{}|{}".format(self.ACL_ACTION_CAPABILITY_FIELD, action_key.upper())
                if key not in switchcapability:
                    del action_props[action_key]
                    continue

                if action_value not in switchcapability[key]:
                    del action_props[action_key]
                    continue

        return action_count == len(action_props)

    def convert_l2(self, table_name, rule_idx, rule):
        rule_props = {}

        if rule.l2.config.ethertype:
            if rule.l2.config.ethertype in self.ethertype_map:
                rule_props["ETHER_TYPE"] = self.ethertype_map[rule.l2.config.ethertype]
            else:
                try:
                    rule_props["ETHER_TYPE"] = int(rule.l2.config.ethertype)
                except Exception as e:
                    raise AclLoaderException(
                        "Failed to convert ethertype %s; table %s rule %s; exception=%s" %
                        (rule.l2.config.ethertype, table_name, rule_idx, str(e)))

        if rule.l2.config.vlan_id != "" and rule.l2.config.vlan_id != "null":
            vlan_id = rule.l2.config.vlan_id

            if vlan_id <= 0 or vlan_id >= 4096:
                raise AclLoaderException("VLAN ID %d is out of bounds (0, 4096)" % (vlan_id))

            rule_props["VLAN_ID"] = vlan_id

        return rule_props

    def convert_ip(self, table_name, rule_idx, rule):
        rule_props = {}

        # FIXME: 0 is a valid protocol number, but openconfig seems to use it as a default value,
        # so there isn't currently a good way to check if the user defined proto=0 or not.
        if rule.ip.config.protocol:
            if rule.ip.config.protocol in self.ip_protocol_map:
                # Special case: ICMP has different protocol numbers for IPv4 and IPv6, so if we receive
                # "IP_ICMP" we need to pick the correct protocol number for the IP version
                if rule.ip.config.protocol == "IP_ICMP" and self.is_table_ipv6(table_name):
                    rule_props["IP_PROTOCOL"] = self.ip_protocol_map["IP_ICMPV6"]
                elif rule.ip.config.protocol == "IP_ICMP" and  self.is_table_l3v4v6(table_name):
                    # For L3V4V6 tables, both ICMP and ICMPv6 are supported,
                    # so find the IP_PROTOCOL using the ether_type.
                    try:
                        ether_type = rule.l2.config.ethertype
                    except Exception as e:
                        ether_type = None
                    if rule.l2.config.ethertype == "ETHERTYPE_IPV6":
                        rule_props["IP_PROTOCOL"] = self.ip_protocol_map["IP_ICMPV6"]
                    else:
                        rule_props["IP_PROTOCOL"] = self.ip_protocol_map[rule.ip.config.protocol]
                else:
                    rule_props["IP_PROTOCOL"] = self.ip_protocol_map[rule.ip.config.protocol]
            else:
                try:
                    int(rule.ip.config.protocol)
                except:
                    raise AclLoaderException("Unknown rule protocol %s in table %s, rule %d!" % (
                        rule.ip.config.protocol, table_name, rule_idx))

                rule_props["IP_PROTOCOL"] = rule.ip.config.protocol

        if rule.ip.config.source_ip_address:
            source_ip_address = rule.ip.config.source_ip_address
            if ipaddress.ip_network(source_ip_address).version == 4:
                rule_props["SRC_IP"] = source_ip_address
            else:
                rule_props["SRC_IPV6"] = source_ip_address

        if rule.ip.config.destination_ip_address:
            destination_ip_address = rule.ip.config.destination_ip_address
            if ipaddress.ip_network(destination_ip_address).version == 4:
                rule_props["DST_IP"] = destination_ip_address
            else:
                rule_props["DST_IPV6"] = destination_ip_address

        # NOTE: DSCP is available only for MIRROR table
        if self.is_table_mirror(table_name):
            if rule.ip.config.dscp:
                rule_props["DSCP"] = rule.ip.config.dscp

        return rule_props

    def convert_icmp(self, table_name, rule_idx, rule):
        rule_props = {}

        is_rule_v6 = False
        if self.is_table_ipv6(table_name):
            is_rule_v6 = True
        elif self.is_table_l3v4v6(table_name):
            # get the IP version type using Ether-Type.
            try:
                ether_type = rule.l2.config.ethertype
                if ether_type == "ETHERTYPE_IPV6":
                    is_rule_v6 = True
            except Exception as e:
                pass
        else:
            # get the IP version type using IP_PROTOCOL.
            try:
                ip_protocol = rule.ip.config.protocol
                if ip_protocol == "IP_ICMPV6" or int(ip_protocol) == self.ip_protocol_map["IP_ICMPV6"]:
                    is_rule_v6 = True
            except Exception as e:
                pass

        type_key = "ICMPV6_TYPE" if is_rule_v6 else "ICMP_TYPE"
        code_key = "ICMPV6_CODE" if is_rule_v6 else "ICMP_CODE"

        if rule.icmp.config.type != "" and rule.icmp.config.type != "null":
            icmp_type = rule.icmp.config.type

            if icmp_type < 0 or icmp_type > 255:
                raise AclLoaderException("ICMP type %d is out of bounds [0, 255]" % (icmp_type))

            rule_props[type_key] = icmp_type

        if rule.icmp.config.code != "" and rule.icmp.config.code != "null":
            icmp_code = rule.icmp.config.code

            if icmp_code < 0 or icmp_code > 255:
                raise AclLoaderException("ICMP code %d is out of bounds [0, 255]" % (icmp_code))

            rule_props[code_key] = icmp_code

        return rule_props

    def convert_port(self, port):
        """
        Convert port field format from openconfig ACL to Config DB schema
        :param port: String, ACL port number or range in openconfig format
        :return: Tuple, first value is converted port string,
            second value is boolean, True if value is a port range, False
            if it is a single port value
        """
        # OpenConfig port range is of the format "####..####", whereas
        # Config DB format is "####-####"
        if ".." in port:
            return  port.replace("..", "-"), True
        else:
            return port, False

    def convert_transport(self, table_name, rule_idx, rule):
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
                tcp_flags |= 0x01
            if flag == "TCP_SYN":
                tcp_flags |= 0x02
            if flag == "TCP_RST":
                tcp_flags |= 0x04
            if flag == "TCP_PSH":
                tcp_flags |= 0x08
            if flag == "TCP_ACK":
                tcp_flags |= 0x10
            if flag == "TCP_URG":
                tcp_flags |= 0x20
            if flag == "TCP_ECE":
                tcp_flags |= 0x40
            if flag == "TCP_CWR":
                tcp_flags |= 0x80

        if tcp_flags:
            rule_props["TCP_FLAGS"] = '0x{:02x}/0x{:02x}'.format(tcp_flags, tcp_flags)

        return rule_props

    def convert_input_interface(self, table_name, rule_idx, rule):
        rule_props = {}

        if rule.input_interface.interface_ref.config.interface:
            rule_props["IN_PORTS"] = rule.input_interface.interface_ref.config.interface

        return rule_props

    def validate_rule_fields(self, rule_props):
        protocol = rule_props.get("IP_PROTOCOL")

        if protocol:
            if "TCP_FLAGS" in rule_props and protocol != 6:
                raise AclLoaderException("IP_PROTOCOL={} is not TCP, but TCP flags were provided".format(protocol))

            if ("ICMP_TYPE" in rule_props or "ICMP_CODE" in rule_props) and protocol != 1:
                raise AclLoaderException("IP_PROTOCOL={} is not ICMP, but ICMP fields were provided".format(protocol))

            if ("ICMPV6_TYPE" in rule_props or "ICMPV6_CODE" in rule_props) and protocol != 58:
                raise AclLoaderException("IP_PROTOCOL={} is not ICMPV6, but ICMPV6 fields were provided".format(protocol))

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

        rule_props["PRIORITY"] = str(self.max_priority - rule_idx)

        # setup default ip type match to dataplane acl (could be overriden by rule later)
        if self.is_table_l3v4v6(table_name):
            # ETHERTYPE must be passed and it should be one of IPv4 or IPv6
            try:
                ether_type =  rule.l2.config.ethertype
            except Exception as e:
                raise AclLoaderException("l2:ethertype must be provided for rule #{} in table:{} of type L3V4V6".format(rule_idx, table_name))
            if ether_type not in ["ETHERTYPE_IPV4", "ETHERTYPE_IPV6"]:
                # Ether type must be v4 or v6 to match IP fields, L4 (TCP/UDP) fields or ICMP fields
                if rule.ip or rule.transport:
                    raise AclLoaderException("ethertype={} is neither ETHERTYPE_IPV4 nor ETHERTYPE_IPV6 for IP rule #{} in table:{} type L3V4V6".format(rule.l2.config.ethertype, rule_idx, table_name))
            rule_props["ETHER_TYPE"] = str(self.ethertype_map[ether_type])
        elif self.is_table_l3v6(table_name):
            rule_props["IP_TYPE"] = "IPV6ANY"  # ETHERTYPE is not supported for DATAACLV6
        elif self.is_table_l3(table_name):
            rule_props["ETHER_TYPE"] = str(self.ethertype_map["ETHERTYPE_IPV4"])

        deep_update(rule_props, self.convert_action(table_name, rule_idx, rule))
        deep_update(rule_props, self.convert_l2(table_name, rule_idx, rule))
        deep_update(rule_props, self.convert_ip(table_name, rule_idx, rule))
        deep_update(rule_props, self.convert_icmp(table_name, rule_idx, rule))
        deep_update(rule_props, self.convert_transport(table_name, rule_idx, rule))
        deep_update(rule_props, self.convert_input_interface(table_name, rule_idx, rule))

        self.validate_rule_fields(rule_props)

        return rule_data

    def deny_rule(self, table_name):
        """
        Create default deny rule in Config DB format
        Only create default deny rule when table is [L3, L3V6]
        :param table_name: ACL table name to which rule belong
        :return: dict with Config DB schema
        """
        rule_props = {}
        rule_data = {(table_name, "DEFAULT_RULE"): rule_props}
        rule_props["PRIORITY"] = str(self.min_priority)
        rule_props["PACKET_ACTION"] = "DROP"
        if self.is_table_l3v6(table_name):
            rule_props["IP_TYPE"] = "IPV6ANY"  # ETHERTYPE is not supported for DATAACLV6
        elif self.is_table_l3(table_name):
            rule_props["ETHER_TYPE"] = str(self.ethertype_map["ETHERTYPE_IPV4"])
        elif self.is_table_l3v4v6(table_name):
            rule_props["IP_TYPE"] = "IP" # Drop both v4 and v6 packets
        else:
            return {}  # Don't add default deny rule if table is not [L3, L3V6]
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

            if self.current_table is not None and self.current_table != table_name:
                continue

            for acl_entry_name in acl_set.acl_entries.acl_entry:
                acl_entry = acl_set.acl_entries.acl_entry[acl_entry_name]
                try:
                    rule = self.convert_rule_to_db_schema(table_name, acl_entry)
                    deep_update(self.rules_info, rule)
                except AclLoaderException as ex:
                    error("Error processing rule %s: %s. Skipped." % (acl_entry_name, ex))

            if not self.is_table_egress(table_name):
                deep_update(self.rules_info, self.deny_rule(table_name))

    def full_update(self):
        """
        Perform full update of ACL rules configuration. All existing rules
        will be removed. New rules loaded from file will be installed. If
        the current_table is not empty, only rules within that table will
        be removed and new rules in that table will be installed.
        :return:
        """
        for key in self.rules_db_info:
            if self.current_table is None or self.current_table == key[0]:
                self.configdb.mod_entry(self.ACL_RULE, key, None)
                # Program for per front asic namespace also if present
                for namespace_configdb in self.per_npu_configdb.values():
                    namespace_configdb.mod_entry(self.ACL_RULE, key, None)


        self.configdb.mod_config({self.ACL_RULE: self.rules_info})
        # Program for per front asic namespace also if present
        for namespace_configdb in self.per_npu_configdb.values():
            namespace_configdb.mod_config({self.ACL_RULE: self.rules_info})

    def incremental_update(self):
        """
        Perform incremental ACL rules configuration update. Get existing rules from
        Config DB. Compare with rules specified in file and perform corresponding
        modifications.
        :return:
        """

        # TODO: Until we test ASIC behavior, we cannot assume that we can insert
        # dataplane ACLs and shift existing ACLs. Therefore, we perform a full
        # update on dataplane ACLs, and only perform an incremental update on
        # control plane ACLs.

        new_rules = set(self.rules_info.keys())
        new_dataplane_rules = set()
        new_controlplane_rules = set()
        current_rules = set(self.rules_db_info.keys())
        current_dataplane_rules = set()
        current_controlplane_rules = set()

        for key in new_rules:
            table_name = key[0]
            if self.tables_db_info[table_name]['type'].upper() == self.ACL_TABLE_TYPE_CTRLPLANE:
                new_controlplane_rules.add(key)
            else:
                new_dataplane_rules.add(key)

        for key in current_rules:
            table_name = key[0]
            if self.tables_db_info[table_name]['type'].upper() == self.ACL_TABLE_TYPE_CTRLPLANE:
                current_controlplane_rules.add(key)
            else:
                current_dataplane_rules.add(key)

        # Remove all existing dataplane rules
        for key in current_dataplane_rules:
            self.configdb.mod_entry(self.ACL_RULE, key, None)
            # Program for per-asic namespace also if present
            for namespace_configdb in self.per_npu_configdb.values():
                namespace_configdb.mod_entry(self.ACL_RULE, key, None)


        # Add all new dataplane rules
        for key in new_dataplane_rules:
            self.configdb.mod_entry(self.ACL_RULE, key, self.rules_info[key])
            # Program for per-asic namespace corresponding to front asic also if present.
            for namespace_configdb in self.per_npu_configdb.values():
                namespace_configdb.mod_entry(self.ACL_RULE, key, self.rules_info[key])

        added_controlplane_rules = new_controlplane_rules.difference(current_controlplane_rules)
        removed_controlplane_rules = current_controlplane_rules.difference(new_controlplane_rules)
        existing_controlplane_rules = new_rules.intersection(current_controlplane_rules)

        for key in added_controlplane_rules:
            self.configdb.mod_entry(self.ACL_RULE, key, self.rules_info[key])
            # Program for per-asic namespace corresponding to front asic also if present.
            # For control plane ACL it's not needed but to keep all db in sync program everywhere
            for namespace_configdb in self.per_npu_configdb.values():
                namespace_configdb.mod_entry(self.ACL_RULE, key, self.rules_info[key])

        for key in removed_controlplane_rules:
            self.configdb.mod_entry(self.ACL_RULE, key, None)
            # Program for per-asic namespace corresponding to front asic also if present.
            # For control plane ACL it's not needed but to keep all db in sync program everywhere
            for namespace_configdb in self.per_npu_configdb.values():
                namespace_configdb.mod_entry(self.ACL_RULE, key, None)

        for key in existing_controlplane_rules:
            if not operator.eq(self.rules_info[key], self.rules_db_info[key]):
                self.configdb.set_entry(self.ACL_RULE, key, self.rules_info[key])
                # Program for per-asic namespace corresponding to front asic also if present.
                # For control plane ACL it's not needed but to keep all db in sync program everywhere
                for namespace_configdb in self.per_npu_configdb.values():
                    namespace_configdb.set_entry(self.ACL_RULE, key, self.rules_info[key])

    def delete(self, table=None, rule=None):
        """
        :param table:
        :param rule:
        :return:
        """
        for key in self.rules_db_info:
            if not table or table == key[0]:
                if not rule or rule == key[1]:
                    self.configdb.set_entry(self.ACL_RULE, key, None)
                    # Program for per-asic namespace corresponding to front asic also if present.
                    for namespace_configdb in self.per_npu_configdb.values():
                        namespace_configdb.set_entry(self.ACL_RULE, key, None)

    def show_table(self, table_name):
        """
        Show ACL table configuration.
        :param table_name: Optional. ACL table name. Filter tables by specified name.
        :return:
        """
        header = ("Name", "Type", "Binding", "Description", "Stage", "Status")

        data = []
        for key, val in self.get_tables_db_info().items():
            if table_name and key != table_name:
                continue

            stage = val.get("stage", Stage.INGRESS).lower()
            # Get ACL table status from STATE_DB
            if key in self.acl_table_status:
                status = self.acl_table_status[key]['status']
            else:
                status = 'N/A'
            if val["type"] == AclLoader.ACL_TABLE_TYPE_CTRLPLANE:
                services = natsorted(val["services"])
                data.append([key, val["type"], services[0], val["policy_desc"], stage, status])

                if len(services) > 1:
                    for service in services[1:]:
                        data.append(["", "", service, "", "", ""])
            else:
                if not val["ports"]:
                    data.append([key, val["type"], "", val["policy_desc"], stage, status])
                else:
                    ports = natsorted(val["ports"])
                    data.append([key, val["type"], ports[0], val["policy_desc"], stage, status])

                    if len(ports) > 1:
                        for port in ports[1:]:
                            data.append(["", "", port, "", "", ""])

        print(tabulate.tabulate(data, headers=header, tablefmt="simple", missingval=""))

    def show_session(self, session_name):
        """
        Show mirror session configuration.
        :param session_name: Optional. Mirror session name. Filter sessions by specified name.
        :return:
        """
        erspan_header = ("Name", "Status", "SRC IP", "DST IP", "GRE", "DSCP", "TTL", "Queue",
                            "Policer", "Monitor Port", "SRC Port", "Direction")
        span_header = ("Name", "Status", "DST Port", "SRC Port", "Direction", "Queue", "Policer")

        erspan_data = []
        span_data = []
        for key, val in self.get_sessions_db_info().items():
            if session_name and key != session_name:
                continue

            if val.get("type") == "SPAN":
                span_data.append([key, val.get("status", ""), val.get("dst_port", ""),
                                       val.get("src_port", ""), val.get("direction", "").lower(),
                                       val.get("queue", ""), val.get("policer", "")])
            else:
                erspan_data.append([key, val.get("status", ""), val.get("src_ip", ""),
                                         val.get("dst_ip", ""), val.get("gre_type", ""), val.get("dscp", ""),
                                         val.get("ttl", ""), val.get("queue", ""), val.get("policer", ""),
                                         val.get("monitor_port", ""), val.get("src_port", ""), val.get("direction", "").lower()])

        print("ERSPAN Sessions")
        erspan_data = natsorted(erspan_data)
        print(tabulate.tabulate(erspan_data, headers=erspan_header, tablefmt="simple", missingval=""))
        print("\nSPAN Sessions")
        span_data = natsorted(span_data)
        print(tabulate.tabulate(span_data, headers=span_header, tablefmt="simple", missingval=""))

    def show_policer(self, policer_name):
        """
        Show policer configuration.
        :param policer_name: Optional. Policer name. Filter policers by specified name.
        :return:
        """
        header = ("Name", "Type", "Mode", "CIR", "CBS")

        data = []
        for key, val in self.get_policers_db_info().items():
            if policer_name and key != policer_name:
                continue

            data.append([key, val["meter_type"], val["mode"], val.get("cir", ""), val.get("cbs", "")])

        print(tabulate.tabulate(data, headers=header, tablefmt="simple", missingval=""))


    def show_rule(self, table_name, rule_id):
        """
        Show ACL rules configuration.
        :param table_name: Optional. ACL table name. Filter rules by specified table name.
        :param rule_id: Optional. ACL rule name. Filter rule by specified rule name.
        :return:
        """
        header = ("Table", "Rule", "Priority", "Action", "Match", "Status")

        def pop_priority(val):
            priority = "N/A"
            for key in dict(val):
                if (key.upper() == "PRIORITY"):
                    priority  = val.pop(key)
                    return priority
            return priority

        def pop_action(val):
            action = ""

            for key in dict(val):
                key = key.upper()
                if key == AclAction.PACKET:
                    action = val.pop(key)
                elif key == AclAction.REDIRECT:
                    action = "REDIRECT: {}".format(val.pop(key))
                elif key in (AclAction.MIRROR, AclAction.MIRROR_INGRESS):
                    action = "MIRROR INGRESS: {}".format(val.pop(key))
                elif key == AclAction.MIRROR_EGRESS:
                    action = "MIRROR EGRESS: {}".format(val.pop(key))
                else:
                    continue

            return action

        def pop_matches(val):
            matches = list(sorted(["%s: %s" % (k, val[k]) for k in val]))
            if len(matches) == 0:
                matches.append("N/A")
            return matches

        raw_data = []
        for (tname, rid), val in self.get_rules_db_info().items():

            if table_name and table_name != tname:
                continue

            if rule_id and rule_id != rid:
                continue

            priority = pop_priority(val)
            action = pop_action(val)
            matches = pop_matches(val)
            # Get ACL rule status from STATE_DB
            status_key = (tname, rid)
            if status_key in self.acl_rule_status:
                status = self.acl_rule_status[status_key]['status']
            else:
                status = "N/A"
            rule_data = [[tname, rid, priority, action, matches[0], status]]
            if len(matches) > 1:
                for m in matches[1:]:
                    rule_data.append(["", "", "", "", m, ""])

            raw_data.append([priority, rule_data])

        raw_data.sort(key=lambda x: x[0], reverse=True)

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
@click.argument('policer_name', type=click.STRING, required=False)
@click.pass_context
def policer(ctx, policer_name):
    """
    Show policer configuration.
    :return:
    """
    acl_loader = ctx.obj["acl_loader"]
    acl_loader.show_policer(policer_name)


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
@click.option('--table_name', type=click.STRING, required=False)
@click.option('--session_name', type=click.STRING, required=False)
@click.option('--mirror_stage', type=click.Choice(["ingress", "egress"]), default="ingress")
@click.option('--max_priority', type=click.INT, required=False)
@click.pass_context
def full(ctx, filename, table_name, session_name, mirror_stage, max_priority):
    """
    Full update of ACL rules configuration.
    If a table_name is provided, the operation will be restricted in the specified table.
    """
    acl_loader = ctx.obj["acl_loader"]

    if table_name:
        acl_loader.set_table_name(table_name)

    if session_name:
        acl_loader.set_session_name(session_name)

    acl_loader.set_mirror_stage(mirror_stage)

    if max_priority:
        acl_loader.set_max_priority(max_priority)

    acl_loader.load_rules_from_file(filename)
    acl_loader.full_update()


@update.command()
@click.argument('filename', type=click.Path(exists=True))
@click.option('--session_name', type=click.STRING, required=False)
@click.option('--mirror_stage', type=click.Choice(["ingress", "egress"]), default="ingress")
@click.option('--max_priority', type=click.INT, required=False)
@click.pass_context
def incremental(ctx, filename, session_name, mirror_stage, max_priority):
    """
    Incremental update of ACL rule configuration.
    """
    acl_loader = ctx.obj["acl_loader"]

    if session_name:
        acl_loader.set_session_name(session_name)

    acl_loader.set_mirror_stage(mirror_stage)

    if max_priority:
        acl_loader.set_max_priority(max_priority)

    acl_loader.load_rules_from_file(filename)
    acl_loader.incremental_update()


@cli.command()
@click.argument('table', required=False)
@click.argument('rule', required=False)
@click.pass_context
def delete(ctx, table, rule):
    """
    Delete ACL rules.
    """
    acl_loader = ctx.obj["acl_loader"]

    acl_loader.delete(table, rule)


if __name__ == "__main__":
    try:
        cli()
    except AclLoaderException as e:
        error(e)
    except Exception as e:
        error("Unknown error: %s" % repr(e))

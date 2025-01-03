#!/usr/bin/env python3

from scapy.config import conf
conf.ipv6_enabled = False
from scapy.layers.l2 import Ether  # noqa: E402
from scapy.sendrecv import sendp  # noqa: E402
import scapy.contrib.lacp  # noqa: E402
import subprocess  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402
import syslog  # noqa: E402
from swsscommon.swsscommon import ConfigDBConnector  # noqa: E402

SYSLOG_ID = 'lag_keepalive'
SLOW_PROTOCOL_MAC_ADDRESS = "01:80:c2:00:00:02"
LACP_ETHERTYPE = 0x8809


def log_info(msg):
    syslog.openlog(SYSLOG_ID)
    syslog.syslog(syslog.LOG_INFO, msg)
    syslog.closelog()


def log_error(msg):
    syslog.openlog(SYSLOG_ID)
    syslog.syslog(syslog.LOG_ERR, msg)
    syslog.closelog()


def getCmdOutput(cmd):
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    return proc.communicate()[0], proc.returncode


def get_port_channel_config(portChannelName):
    (processStdout, _) = getCmdOutput(["teamdctl", portChannelName, "state", "dump"])
    return json.loads(processStdout)


def craft_lacp_packet(portChannelConfig, portName):
    portConfig = portChannelConfig["ports"][portName]
    actorConfig = portConfig["runner"]["actor_lacpdu_info"]
    partnerConfig = portConfig["runner"]["partner_lacpdu_info"]
    l2 = Ether(dst=SLOW_PROTOCOL_MAC_ADDRESS, src=portConfig["ifinfo"]["dev_addr"], type=LACP_ETHERTYPE)
    l3 = scapy.contrib.lacp.SlowProtocol(subtype=0x01)
    l4 = scapy.contrib.lacp.LACP()
    l4.version = 0x1
    l4.actor_system_priority = actorConfig["system_priority"]
    l4.actor_system = actorConfig["system"]
    l4.actor_key = actorConfig["key"]
    l4.actor_port_priority = actorConfig["port_priority"]
    l4.actor_port_number = actorConfig["port"]
    l4.actor_state = actorConfig["state"]
    l4.partner_system_priority = partnerConfig["system_priority"]
    l4.partner_system = partnerConfig["system"]
    l4.partner_key = partnerConfig["key"]
    l4.partner_port_priority = partnerConfig["port_priority"]
    l4.partner_port_number = partnerConfig["port"]
    l4.partner_state = partnerConfig["state"]
    packet = l2 / l3 / l4
    return packet


def get_lacpdu_per_lag_member():
    appDB = ConfigDBConnector()
    appDB.db_connect('APPL_DB')
    appDB_lag_info = appDB.get_keys('LAG_MEMBER_TABLE')
    active_lag_members = list()
    lag_member_to_packet = dict()
    for lag_entry in appDB_lag_info:
        lag_name = str(lag_entry[0])
        oper_status = appDB.get(appDB.APPL_DB, "LAG_TABLE:{}".format(lag_name), "oper_status")
        if oper_status == "up":
            # only apply the workaround for active lags
            lag_member = str(lag_entry[1])
            active_lag_members.append(lag_member)
            # craft lacpdu packets for each lag member based on config
            port_channel_config = get_port_channel_config(lag_name)
            socket = conf.L2socket(iface=lag_member)
            lag_member_to_packet[lag_member] = (socket, craft_lacp_packet(port_channel_config, lag_member))

    return active_lag_members, lag_member_to_packet


def lag_keepalive(lag_member_to_packet):
    while True:
        for lag_member, (socket, packet) in lag_member_to_packet.items():
            try:
                sendp(packet, iface=lag_member, verbose=False)
            except Exception:
                # log failure and continue to send lacpdu
                traceback_msg = traceback.format_exc()
                log_error("Failed to send LACPDU packet from interface {} with error: {}".format(
                    lag_member, traceback_msg))
                continue
        log_info("sent LACPDU packets via {}".format(lag_member_to_packet.keys()))
        time.sleep(1)


def main():
    while True:
        try:
            active_lag_members, lag_member_to_packet = get_lacpdu_per_lag_member()
            if len(active_lag_members) != len(lag_member_to_packet.keys()):
                log_error("Failed to craft LACPDU packets for some lag members. " +
                          "Active lag members: {}. LACPDUs craft for: {}".format(
                              active_lag_members, lag_member_to_packet.keys()))

            log_info("ready to send LACPDU packets via {}".format(lag_member_to_packet.keys()))
        except Exception:
            traceback_msg = traceback.format_exc()
            log_error("Failed to get LAG members and LACPDUs with error: {}".format(
                traceback_msg))
            # keep attempting until sniffed packets are ready
            continue
        # if no exceptions are thrown, break from loop as LACPDUs are ready to be sent
        break

    if lag_member_to_packet:
        # start an infinite loop to keep sending lacpdus from lag member ports
        lag_keepalive(lag_member_to_packet)


if __name__ == "__main__":
    main()

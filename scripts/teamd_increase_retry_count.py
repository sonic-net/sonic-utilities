#!/usr/bin/python3

import subprocess
import json
from pyroute2 import netns
from scapy.config import conf
# Fixes delayed import when we have a lot of routes installed
conf.route_autoload = False
conf.route6_autoload = False
import os
import re
import sys
from threading import Thread, Event
import time
import argparse
import signal

from sonic_py_common import logger, multi_asic
from swsscommon.swsscommon import DBConnector, Table, SonicDBConfig, SonicDBKey

from scapy.fields import ByteField, ShortField, MACField, XStrFixedLenField, ConditionalField, MultipleTypeField
from scapy.layers.l2 import Ether  # noqa: E402
from scapy.sendrecv import sendp, sniff  # noqa: E402
from scapy.packet import Packet, split_layers, bind_layers  # noqa: E402
import scapy.contrib.lacp  # noqa: E402

conf.verb = False

log = None
revertTeamdRetryCountChanges = False
DEFAULT_RETRY_COUNT = 3
EXTENDED_RETRY_COUNT = 5
SLOW_PROTOCOL_MAC_ADDRESS = "01:80:c2:00:00:02"
LACP_ETHERTYPE = 0x8809

class LACPRetryCount(Packet):
    name = "LACPRetryCount"
    fields_desc = [
        ByteField("version", 0xf1),
        ByteField("actor_type", 1),
        ByteField("actor_length", 20),
        ShortField("actor_system_priority", 0),
        MACField("actor_system", None),
        ShortField("actor_key", 0),
        ShortField("actor_port_priority", 0),
        ShortField("actor_port_number", 0),
        ByteField("actor_state", 0),
        XStrFixedLenField("actor_reserved", "", 3),
        ByteField("partner_type", 2),
        ByteField("partner_length", 20),
        ShortField("partner_system_priority", 0),
        MACField("partner_system", None),
        ShortField("partner_key", 0),
        ShortField("partner_port_priority", 0),
        ShortField("partner_port_number", 0),
        ByteField("partner_state", 0),
        XStrFixedLenField("partner_reserved", "", 3),
        ByteField("collector_type", 3),
        ByteField("collector_length", 16),
        ShortField("collector_max_delay", 0),
        XStrFixedLenField("collector_reserved", "", 12),
        ConditionalField(ByteField("actor_retry_count_type", 0x80), lambda pkt:pkt.version == 0xf1),
        ConditionalField(ByteField("actor_retry_count_length", 4), lambda pkt:pkt.version == 0xf1),
        ConditionalField(ByteField("actor_retry_count", 0), lambda pkt:pkt.version == 0xf1),
        ConditionalField(XStrFixedLenField("actor_retry_count_reserved", "", 1), lambda pkt:pkt.version == 0xf1),
        ConditionalField(ByteField("partner_retry_count_type", 0x81), lambda pkt:pkt.version == 0xf1),
        ConditionalField(ByteField("partner_retry_count_length", 4), lambda pkt:pkt.version == 0xf1),
        ConditionalField(ByteField("partner_retry_count", 0), lambda pkt:pkt.version == 0xf1),
        ConditionalField(XStrFixedLenField("partner_retry_count_reserved", "", 1), lambda pkt:pkt.version == 0xf1),
        ByteField("terminator_type", 0),
        ByteField("terminator_length", 0),
        MultipleTypeField(
            [
                (XStrFixedLenField("reserved", "", 42), lambda pkt:pkt.version == 0xf1),
                (XStrFixedLenField("reserved", "", 50), lambda pkt:pkt.version != 0xf1),
            ],
            XStrFixedLenField("reserved", "", 50)
        ),
    ]

split_layers(scapy.contrib.lacp.SlowProtocol, scapy.contrib.lacp.LACP, subtype=1)
bind_layers(scapy.contrib.lacp.SlowProtocol, LACPRetryCount, subtype=1)

class LacpPacketListenThread(Thread):
    def __init__(self, port, targetMacAddress, sendReadyEvent):
        Thread.__init__(self)
        self.port = port
        self.targetMacAddress = targetMacAddress
        self.sendReadyEvent = sendReadyEvent
        self.detectedNewVersion = False
        self.error = None

    def lacpPacketCallback(self, pkt):
        if pkt["LACPRetryCount"].version == 0xf1:
            self.detectedNewVersion = True
        return self.detectedNewVersion

    def run(self):
        try:
            sniff(stop_filter=self.lacpPacketCallback, iface=self.port,
                  filter="ether proto {} and ether src {}".format(
                      LACP_ETHERTYPE, self.targetMacAddress),
                  store=0, timeout=30,
                  started_callback=self.sendReadyEvent.set)
        except Exception as error:
            self.error = error
        finally:
            # Unblock the sender when capture setup fails before Scapy invokes
            # started_callback. The probe worker records that failure.
            self.sendReadyEvent.set()


class PortChannelProbeThread(Thread):
    def __init__(self, portChannel, namespace, lldpInfo):
        Thread.__init__(self)
        self.portChannel = portChannel
        self.namespace = namespace
        self.lldpInfo = lldpInfo
        self.success = False
        self.error = None

    def run(self):
        try:
            self.success = probePortChannel(
                self.portChannel, self.namespace, self.lldpInfo
            )
        except Exception as error:
            self.error = error
            log.log_error(
                "ERROR: Failed to probe port channel {}: {}".format(
                    self.portChannel, error
                ),
                also_print_to_console=True,
            )


def getPortChannels(namespace=""):
    key = SonicDBKey(namespace)
    is_tcp_conn = False
    applDb = DBConnector("APPL_DB", 0, is_tcp_conn, key)
    configDb = DBConnector("CONFIG_DB", 0, is_tcp_conn, key)
    portChannelTable = Table(applDb, "LAG_TABLE")
    portChannels = portChannelTable.getKeys()
    activePortChannels = []
    for portChannel in portChannels:
        state = portChannelTable.get(portChannel)
        if not state or not state[0]:
            continue
        isAdminUp = False
        isOperUp = False
        for key, value in state[1]:
            if key == "admin_status":
                isAdminUp = value == "up"
            elif key == "oper_status":
                isOperUp = value == "up"
        if isAdminUp and isOperUp:
            activePortChannels.append(portChannel)

    # Now find out which BGP sessions on these port channels are admin up. This needs to go
    # through a circuitious sequence of steps.
    #
    # 1. Get the local IPv4/IPv6 address assigned to each port channel.
    # 2. Find out which BGP session (in CONFIG_DB) has a local_addr attribute of the local
    # IPv4/IPv6 address.
    # 3. Check the admin_status field of that table in CONFIG_DB.
    portChannelData = {}
    portChannelInterfaceTable = Table(configDb, "PORTCHANNEL_INTERFACE")
    portChannelInterfaces = portChannelInterfaceTable.getKeys()
    for portChannelInterface in portChannelInterfaces:
        if "|" not in portChannelInterface:
            continue
        portChannel = portChannelInterface.split("|")[0]
        ipAddress = portChannelInterface.split("|")[1].split("/")[0].lower()
        if portChannel not in activePortChannels:
            continue
        portChannelData[ipAddress] = {
                "portChannel": portChannel,
                "adminUp": False
                }

    deviceMetadataTable = Table(configDb, "DEVICE_METADATA")
    metadata = deviceMetadataTable.get("localhost")
    defaultBgpStatus = True
    for key, value in metadata[1]:
        if key == "default_bgp_status":
            defaultBgpStatus = value == "up"
            break

    bgpTable = Table(configDb, "BGP_NEIGHBOR")
    bgpNeighbors = bgpTable.getKeys()
    for bgpNeighbor in bgpNeighbors:
        neighborData = bgpTable.get(bgpNeighbor)
        if not neighborData[0]:
            continue
        localAddr = None
        isAdminUp = defaultBgpStatus
        for key, value in neighborData[1]:
            if key == "local_addr":
                if value not in portChannelData:
                    break
                localAddr = value.lower()
            elif key == "admin_status":
                isAdminUp = value == "up"
        if not localAddr:
            continue
        portChannelData[localAddr]["adminUp"] = isAdminUp

    return set([portChannelData[x]["portChannel"] for x in portChannelData.keys() if portChannelData[x]["adminUp"]])


def getPortChannelConfig(portChannelName, namespace=""):
    teamdctl_command = ["teamdctl"]
    if namespace:
        teamdctl_command += ["-n", namespace.removeprefix("asic")]
    (processStdout, _) = getCmdOutput(teamdctl_command + [portChannelName, "state", "dump"])
    return json.loads(processStdout)


def getLldpNeighbors(namespace=""):
    container = "lldp"
    if namespace:
        container += namespace.removeprefix("asic")
    try:
        (processStdout, _) = getCmdOutput(["docker", "exec", container, "lldpctl", "-f", "json"])
        return json.loads(processStdout)
    except json.JSONDecodeError:
        return None

def craftLacpPacket(portChannelConfig, portName, isResetPacket=False, newVersion=True):
    portConfig = portChannelConfig["ports"][portName]
    actorConfig = portConfig["runner"]["actor_lacpdu_info"]
    partnerConfig = portConfig["runner"]["partner_lacpdu_info"]
    l2 = Ether(dst=SLOW_PROTOCOL_MAC_ADDRESS, src=portConfig["ifinfo"]["dev_addr"], type=LACP_ETHERTYPE)
    l3 = scapy.contrib.lacp.SlowProtocol(subtype=0x01)
    l4 = LACPRetryCount()
    if newVersion:
        l4.version = 0xf1
    else:
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
    if newVersion:
        l4.actor_retry_count = EXTENDED_RETRY_COUNT if not isResetPacket else DEFAULT_RETRY_COUNT
        l4.partner_retry_count = DEFAULT_RETRY_COUNT
    packet = l2 / l3 / l4
    return packet

def sendLacpPackets(packets, revertPackets):
    global revertTeamdRetryCountChanges
    while not revertTeamdRetryCountChanges:
        for port, packet in packets:
            sendp(packet, iface=port)
        time.sleep(15)
    if revertTeamdRetryCountChanges:
        for port, packet in revertPackets:
            sendp(packet, iface=port)

def abortTeamdChanges(signum, frame):
    global revertTeamdRetryCountChanges
    log.log_info("Got signal {}, reverting teamd retry count change".format(signum))
    revertTeamdRetryCountChanges = True

def getCmdOutput(cmd):
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    return proc.communicate()[0], proc.returncode


def probePortChannel(portChannel, namespace, lldpInfo):
    config = getPortChannelConfig(portChannel, namespace)
    for portName in config["ports"].keys():
        if "runner" not in config["ports"][portName] or \
                "partner_lacpdu_info" not in config["ports"][portName]["runner"] or \
                "actor_lacpdu_info" not in config["ports"][portName]["runner"]:
            log.log_error("ERROR: Missing information from teamd about {}; skipping".format(portName))
            return False

        interfaceLldpInfo = [k for k in lldpInfo["lldp"]["interface"] if portName in k]
        if not interfaceLldpInfo:
            log.log_warning("WARNING: No LLDP info available for {}; skipping".format(portName))
            continue
        interfaceLldpInfo = interfaceLldpInfo[0][portName]
        peerName = list(interfaceLldpInfo["chassis"].keys())[0]
        peerInfo = interfaceLldpInfo["chassis"][peerName]
        if "descr" not in peerInfo:
            log.log_warning("WARNING: No peer description available via LLDP for {}; skipping".format(portName))
            continue
        if "sonic" not in peerInfo["descr"].lower():
            log.log_warning("WARNING: Peer device is not a SONiC device; skipping")
            return False

        sendReadyEvent = Event()
        lacpThread = LacpPacketListenThread(
            portName,
            config["ports"][portName]["runner"]["partner_lacpdu_info"]["system"],
            sendReadyEvent,
        )
        probePacket = craftLacpPacket(config, portName)
        resetProbePacket = craftLacpPacket(config, portName, newVersion=False)
        probeSent = False
        probeFailed = False
        resetSucceeded = True
        try:
            lacpThread.start()
            sendReadyEvent.wait()
            if lacpThread.error is not None:
                raise lacpThread.error

            # Mark the probe before sendp so that even a partial-send failure
            # is followed by a standard-version reset.
            probeSent = True
            sendp(probePacket, iface=portName)
            lacpThread.join()
            if lacpThread.error is not None:
                raise lacpThread.error
        except Exception as error:
            probeFailed = True
            log.log_error(
                "ERROR: Failed probing {} on {}: {}".format(
                    portName, portChannel, error
                )
            )
        finally:
            if lacpThread.is_alive():
                lacpThread.join()
            if probeSent:
                try:
                    # Allow the peer to process this PortChannel's probe, then
                    # restore standard LACP without waiting for slower peers.
                    time.sleep(2)
                    sendp(resetProbePacket, iface=portName, count=2, inter=0.5)
                except Exception as error:
                    resetSucceeded = False
                    log.log_error(
                        "ERROR: Failed resetting {} on {}: {}".format(
                            portName, portChannel, error
                        )
                    )

        if not probeFailed and lacpThread.detectedNewVersion and resetSucceeded:
            log.log_notice(
                "SUCCESS: Peer device {} is running version of SONiC with teamd retry count feature".format(
                    peerName
                ),
                also_print_to_console=True,
            )
            return True

        if not probeFailed and resetSucceeded:
            log.log_warning(
                "WARNING: Peer device {} is running version of SONiC without teamd retry count feature".format(
                    peerName
                ),
                also_print_to_console=True,
            )
        return False

    log.log_warning(
        "WARNING: No information available about peer device on port channel {}".format(
            portChannel
        ),
        also_print_to_console=True,
    )
    return False


def probePortChannels(portChannels, namespace=""):
    lldpInfo = getLldpNeighbors(namespace)
    if not lldpInfo:
        log.log_error(
            "ERROR: Failed to get LLDP neighbors; make sure lldp container is running",
            also_print_to_console=True,
        )
        return sorted(portChannels)

    # Probe every PortChannel independently and concurrently. Unsupported
    # peers can consume the full 30-second receive window, so serial probes
    # delay warm reboot by that amount once per active PortChannel.
    probes = [
        PortChannelProbeThread(portChannel, namespace, lldpInfo)
        for portChannel in sorted(portChannels)
    ]
    for probe in probes:
        probe.start()
    for probe in probes:
        probe.join()

    return sorted(
        probe.portChannel
        for probe in probes
        if probe.error is not None or not probe.success
    )

def main(probeOnly=False, namespace=""):
    if os.geteuid() != 0:
        log.log_error("Root privileges required for this operation", also_print_to_console=True)
        sys.exit(1)
    if namespace:
        netns.setns(namespace)
    if multi_asic.is_multi_asic():
        SonicDBConfig.initializeGlobalConfig()
    portChannels = getPortChannels(namespace)
    if not portChannels:
        log.log_info("No port channels retrieved; exiting")
        return
    if probeOnly:
        failedPortChannels = probePortChannels(portChannels, namespace)
        if failedPortChannels:
            # The default reboot path is best-effort: it skips retry-count
            # negotiation when any peer is unsupported and continues. Keep
            # this a warning; strict -N mode turns the non-zero result into a
            # fatal reboot error in fast-reboot.
            log.log_warning(
                "WARNING: There are port channels/peer devices that failed "
                "the probe: {}".format(failedPortChannels),
                also_print_to_console=True,
            )
            sys.exit(2)
    else:
        global revertTeamdRetryCountChanges
        signal.signal(signal.SIGUSR1, abortTeamdChanges)
        signal.signal(signal.SIGTERM, abortTeamdChanges)
        (_, rc) = getCmdOutput(["config", "portchannel", "-n", namespace, "retry-count", "get", list(portChannels)[0]])
        if rc == 0:
            # Currently running on SONiC version with teamd retry count feature
            for portChannel in portChannels:
                getCmdOutput(["config", "portchannel", "-n", namespace, "retry-count", "set",
                              portChannel, str(EXTENDED_RETRY_COUNT)])
            pid = os.fork()
            if pid == 0:
                # Running in a new process, detached from parent process
                while not revertTeamdRetryCountChanges:
                    time.sleep(15)
                if revertTeamdRetryCountChanges:
                    for portChannel in portChannels:
                        getCmdOutput(["config", "portchannel", "-n", namespace, "retry-count", "set",
                                      portChannel, str(DEFAULT_RETRY_COUNT)])
        else:
            lacpPackets = []
            revertLacpPackets = []
            for portChannel in portChannels:
                config = getPortChannelConfig(portChannel)
                for portName in config["ports"].keys():
                    if not "runner" in config["ports"][portName] or \
                            not "partner_lacpdu_info" in config["ports"][portName]["runner"] or \
                            not "actor_lacpdu_info" in config["ports"][portName]["runner"]:
                        log.log_error("ERROR: Missing information from teamd about {}; skipping".format(portName))
                        break

                    packet = craftLacpPacket(config, portName)
                    lacpPackets.append((portName, packet))
                    packet = craftLacpPacket(config, portName, isResetPacket=True)
                    revertLacpPackets.append((portName, packet))
            pid = os.fork()
            if pid == 0:
                # Running in a new process, detached from parent process
                sendLacpPackets(lacpPackets, revertLacpPackets)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Teamd retry count changer.')
    parser.add_argument('--probe-only', action='store_true',
            help='Probe the peer devices only, to verify that they support the teamd retry count feature')
    parser.add_argument('-n', '--namespace', default="", type=str, help='namespace to use')
    args = parser.parse_args()
    log_identifier = "teamd_increase_retry_count"
    if args.namespace:
        log_identifier += f"_{args.namespace}"
    log = logger.Logger(log_identifier=log_identifier)
    main(args.probe_only, args.namespace)

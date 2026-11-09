"""Shared LACP retry-count packet format and port-channel selection."""

from scapy.fields import ByteField, ShortField, MACField, XStrFixedLenField, ConditionalField, MultipleTypeField
from scapy.packet import Packet
from swsscommon.swsscommon import DBConnector, Table, SonicDBKey


class LACPRetryCount(Packet):
    """LACPDU with optional SONiC retry-count TLVs."""

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
        ConditionalField(ByteField("actor_retry_count_type", 0x80), lambda pkt: pkt.version == 0xf1),
        ConditionalField(ByteField("actor_retry_count_length", 4), lambda pkt: pkt.version == 0xf1),
        ConditionalField(ByteField("actor_retry_count", 0), lambda pkt: pkt.version == 0xf1),
        ConditionalField(XStrFixedLenField("actor_retry_count_reserved", "", 1), lambda pkt: pkt.version == 0xf1),
        ConditionalField(ByteField("partner_retry_count_type", 0x81), lambda pkt: pkt.version == 0xf1),
        ConditionalField(ByteField("partner_retry_count_length", 4), lambda pkt: pkt.version == 0xf1),
        ConditionalField(ByteField("partner_retry_count", 0), lambda pkt: pkt.version == 0xf1),
        ConditionalField(XStrFixedLenField("partner_retry_count_reserved", "", 1), lambda pkt: pkt.version == 0xf1),
        ByteField("terminator_type", 0),
        ByteField("terminator_length", 0),
        MultipleTypeField(
            [
                (XStrFixedLenField("reserved", "", 42), lambda pkt: pkt.version == 0xf1),
                (XStrFixedLenField("reserved", "", 50), lambda pkt: pkt.version != 0xf1),
            ],
            XStrFixedLenField("reserved", "", 50)
        ),
    ]


def get_retry_count_port_channels(namespace=""):
    """Return active port channels with an administratively enabled BGP peer."""
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
    # through a circuitous sequence of steps.
    #
    # 1. Get the local IPv4/IPv6 address assigned to each port channel.
    # 2. Find out which BGP session (in CONFIG_DB) has a local_addr attribute of the local
    # IPv4/IPv6 address.
    # 3. Check the admin_status field of that table in CONFIG_DB, falling back to
    # DEVICE_METADATA.default_bgp_status (defaulting to "up") if it is not set.
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

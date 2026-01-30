import json

import utilities_common.cli as clicommon
from sonic_py_common import multi_asic
from utilities_common import constants


def is_software_bfd_enabled(namespace=multi_asic.DEFAULT_NAMESPACE, config_db=None):
    """
    Check if software BFD is enabled in CONFIG_DB
    :param namespace: namespace name
    :param config_db: ConfigDBConnector instance (optional, will create if not provided)
    :return: True if software BFD is enabled, False otherwise
    """
    if config_db is None:
        config_db = multi_asic.connect_config_db_for_ns(namespace)
    sys_defaults = config_db.get_entry("SYSTEM_DEFAULTS", "software_bfd")
    if sys_defaults and "status" in sys_defaults:
        return sys_defaults["status"] == "enabled"
    return False


def get_bfd_peers_from_config(namespace=multi_asic.DEFAULT_NAMESPACE, config_db=None):
    """
    Get all BFD-enabled peers from CONFIG_DB (BGP neighbors and static routes)
    :param namespace: namespace name
    :param config_db: ConfigDBConnector instance (optional, will create if not provided)
    :return: set of peer IP addresses that have BFD configured
    """
    if config_db is None:
        config_db = multi_asic.connect_config_db_for_ns(namespace)
    bfd_peers = set()

    # First, find peer groups with BFD enabled
    bfd_peer_groups = set()
    peer_groups = config_db.get_table("BGP_PEER_GROUP")
    for key, data in peer_groups.items():
        if data.get("bfd") == "true":
            if isinstance(key, tuple):
                # Unified mode: key is (vrf, peer_group_name)
                peer_group_name = key[1] if len(key) > 1 else key[0]
            else:
                # Legacy mode: key is peer_group_name
                peer_group_name = key
            bfd_peer_groups.add(peer_group_name)

    # Get BFD-enabled BGP neighbors (either directly or via peer group)
    bgp_tables = [
        multi_asic.BGP_NEIGH_CFG_DB_TABLE,
        multi_asic.BGP_INTERNAL_NEIGH_CFG_DB_TABLE,
    ]

    for table in bgp_tables:
        neighbors = config_db.get_table(table)
        for key, data in neighbors.items():
            if isinstance(key, tuple):
                # Unified mode: key is (vrf, neighbor_ip)
                neighbor_ip = key[1] if len(key) > 1 else key[0]
            else:
                # Legacy mode: key is neighbor_ip
                neighbor_ip = key

            # Check if BFD is enabled directly on the neighbor
            if data.get("bfd") == "true":
                bfd_peers.add(neighbor_ip)
            # Or if the neighbor inherits BFD from its peer group
            elif data.get("peer_group") in bfd_peer_groups:
                bfd_peers.add(neighbor_ip)

    # Get BFD-enabled static routes
    static_routes = config_db.get_table("STATIC_ROUTE")
    for key, data in static_routes.items():
        if data.get("bfd") == "true":
            # Extract nexthop IPs from the static route
            nexthops = data.get("nexthop", "")
            if nexthops:
                for nh in nexthops.split(","):
                    nh = nh.strip()
                    if nh:
                        bfd_peers.add(nh)

    return bfd_peers


def run_bfd_command(vtysh_cmd, namespace=multi_asic.DEFAULT_NAMESPACE):
    """
    Run a BFD command via vtysh
    :param vtysh_cmd: vtysh command to run
    :param namespace: namespace name
    :return: command output (string), or None if command fails
    """
    bgp_instance_id = []
    if namespace != multi_asic.DEFAULT_NAMESPACE:
        bgp_instance_id = ['-n', str(multi_asic.get_asic_id_from_name(namespace))]

    cmd = ['sudo', constants.RVTYSH_COMMAND] + bgp_instance_id + ['-c', vtysh_cmd]
    output, ret = clicommon.run_command(cmd, return_cmd=True)

    if ret != 0:
        return None

    return output


def get_bfd_sessions_from_frr(namespace=multi_asic.DEFAULT_NAMESPACE):
    """
    Get BFD sessions from FRR via vtysh
    :param namespace: namespace name
    :return: dict of BFD sessions keyed by peer IP
    """
    vtysh_cmd = "show bfd peers json"
    output = run_bfd_command(vtysh_cmd, namespace)

    if not output:
        return {}

    try:
        bfd_sessions = json.loads(output)
        # FRR returns a list of sessions
        # Convert to dict keyed by peer IP for easier lookup
        sessions_by_peer = {}
        for session in bfd_sessions:
            peer = session.get("peer")
            if peer:
                sessions_by_peer[peer] = session
        return sessions_by_peer
    except (ValueError, json.JSONDecodeError):
        return {}


def filter_bfd_sessions_by_config(frr_sessions, configured_peers):
    """
    Filter FRR BFD sessions to only include those configured in CONFIG_DB
    :param frr_sessions: dict of BFD sessions from FRR (keyed by peer IP)
    :param configured_peers: set of peer IPs configured in CONFIG_DB
    :return: list of filtered BFD sessions
    """
    filtered_sessions = []
    for peer_ip, session in frr_sessions.items():
        if peer_ip in configured_peers:
            filtered_sessions.append(session)
    return filtered_sessions

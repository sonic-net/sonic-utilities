import click
import ipaddress

from sonic_py_common import multi_asic
from sonic_py_common.interface import get_interface_table_name
from swsscommon.swsscommon import ConfigDBConnector
import utilities_common.cli as clicommon

from .utils import log

DEFAULT_NAMESPACE = ""

BGP_NEIGHBOR_ALLOWAS_MIN = 1
BGP_NEIGHBOR_ALLOWAS_MAX = 10
BGP_ASN_MIN = 1
BGP_ASN_MAX = 4294967295
BGP_ASN_RANGE = click.IntRange(min=BGP_ASN_MIN, max=BGP_ASN_MAX)
BGP_LISTEN_LIMIT_RANGE = click.IntRange(min=1, max=65535)
BGP_GR_RESTART_TIME_RANGE = click.IntRange(min=0, max=4095)
BGP_GR_STALEPATH_TIME_RANGE = click.IntRange(min=1, max=4095)
BGP_NEIGHBOR_ADV_INTERVAL_RANGE = click.IntRange(min=0, max=600)
BGP_NEIGHBOR_TIMER_RANGE = click.IntRange(min=0, max=65535)
BGP_NEIGHBOR_MULTIHOP_RANGE = click.IntRange(min=1, max=255)
BGP_IPV4_UNICAST_MAX_PATHS_RANGE = click.IntRange(min=1, max=256)
BGP_IPV4_UNICAST_DISTANCE_RANGE = click.IntRange(min=1, max=255)


def _is_neighbor_ipaddress(config_db, ipaddress):
    """Returns True if a neighbor has the IP address <ipaddress>, False if not"""
    entry = config_db.get_entry("BGP_NEIGHBOR", ipaddress)
    return True if entry else False


def _get_all_neighbor_ipaddresses(config_db):
    """Returns list of strings containing IP addresses of all BGP neighbors"""
    addrs = []
    bgp_sessions = config_db.get_table("BGP_NEIGHBOR")
    for addr, session in bgp_sessions.items():
        addrs.append(addr)
    return addrs


def _get_neighbor_ipaddress_list_by_hostname(config_db, hostname):
    """Returns list of strings, each containing an IP address of neighbor with
    hostname <hostname>. Returns empty list if <hostname> not a neighbor
    """
    addrs = []
    bgp_sessions = config_db.get_table("BGP_NEIGHBOR")
    for addr, session in bgp_sessions.items():
        if "name" in session and session["name"] == hostname:
            addrs.append(addr)
    return addrs


def _change_bgp_session_status_by_addr(config_db, ipaddress, status, verbose):
    """Start up or shut down BGP session by IP address"""
    verb = "Starting" if status == "up" else "Shutting"
    click.echo("{} {} BGP session with neighbor {}...".format(verb, status, ipaddress))

    config_db.mod_entry("bgp_neighbor", ipaddress, {"admin_status": status})


def _change_bgp_session_status(config_db, ipaddr_or_hostname, status, verbose):
    """Start up or shut down BGP session by IP address or hostname"""
    ip_addrs = []

    # If we were passed an IP address, convert it to lowercase because IPv6 addresses were
    # stored in ConfigDB with all lowercase alphabet characters during minigraph parsing
    if _is_neighbor_ipaddress(config_db, ipaddr_or_hostname.lower()):
        ip_addrs.append(ipaddr_or_hostname.lower())
    else:
        # If <ipaddr_or_hostname> is not the IP address of a neighbor, check to see if it's a hostname
        ip_addrs = _get_neighbor_ipaddress_list_by_hostname(
            config_db, ipaddr_or_hostname
        )

    if not ip_addrs:
        return False

    for ip_addr in ip_addrs:
        _change_bgp_session_status_by_addr(config_db, ip_addr, status, verbose)

    return True


def _validate_bgp_neighbor(config_db, neighbor_ip_or_hostname):
    """validates whether the given ip or host name is a BGP neighbor"""
    ip_addrs = []
    if _is_neighbor_ipaddress(config_db, neighbor_ip_or_hostname.lower()):
        ip_addrs.append(neighbor_ip_or_hostname.lower())
    else:
        ip_addrs = _get_neighbor_ipaddress_list_by_hostname(
            config_db, neighbor_ip_or_hostname.upper()
        )

    return ip_addrs


def _remove_bgp_neighbor_config(config_db, neighbor_ip_or_hostname):
    """Removes BGP configuration of the given neighbor"""
    ip_addrs = _validate_bgp_neighbor(config_db, neighbor_ip_or_hostname)

    if not ip_addrs:
        return False

    for ip_addr in ip_addrs:
        config_db.mod_entry("bgp_neighbor", ip_addr, None)
        click.echo("Removed configuration of BGP neighbor {}".format(ip_addr))

    return True


#
# 'bgp' group ('config bgp ...')
#


@click.group(cls=clicommon.AbbreviationGroup, name="bgp")
def bgp():
    """BGP-related configuration tasks"""
    pass


#
# 'shutdown' subgroup ('config bgp shutdown ...')
#


@bgp.group(cls=clicommon.AbbreviationGroup)
def shutdown():
    """Shut down BGP session(s)"""
    pass


# 'all' subcommand
@shutdown.command()
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
def all(verbose):
    """Shut down all BGP sessions
    In the case of Multi-Asic platform, we shut only the EBGP sessions with external neighbors.
    """
    log.log_info("'bgp shutdown all' executing...")
    namespaces = [DEFAULT_NAMESPACE]

    if multi_asic.is_multi_asic():
        ns_list = multi_asic.get_all_namespaces()
        namespaces = ns_list["front_ns"]

    # Connect to CONFIG_DB in linux host (in case of single ASIC) or CONFIG_DB in all the
    # namespaces (in case of multi ASIC) and do the sepcified "action" on the BGP neighbor(s)
    for namespace in namespaces:
        config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
        config_db.connect()
        bgp_neighbor_ip_list = _get_all_neighbor_ipaddresses(config_db)
        for ipaddr in bgp_neighbor_ip_list:
            _change_bgp_session_status_by_addr(config_db, ipaddr, "down", verbose)


# 'neighbor' subcommand
@shutdown.command()
@click.argument("ipaddr_or_hostname", metavar="<ipaddr_or_hostname>", required=True)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
def neighbor(ipaddr_or_hostname, verbose):
    """Shut down BGP session by neighbor IP address or hostname.
    User can specify either internal or external BGP neighbor to shutdown
    """
    log.log_info("'bgp shutdown neighbor {}' executing...".format(ipaddr_or_hostname))
    namespaces = [DEFAULT_NAMESPACE]
    found_neighbor = False

    if multi_asic.is_multi_asic():
        ns_list = multi_asic.get_all_namespaces()
        namespaces = ns_list["front_ns"] + ns_list["back_ns"]

    # Connect to CONFIG_DB in linux host (in case of single ASIC) or CONFIG_DB in all the
    # namespaces (in case of multi ASIC) and do the sepcified "action" on the BGP neighbor(s)
    for namespace in namespaces:
        config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
        config_db.connect()
        if _change_bgp_session_status(config_db, ipaddr_or_hostname, "down", verbose):
            found_neighbor = True

    if not found_neighbor:
        click.get_current_context().fail(
            "Could not locate neighbor '{}'".format(ipaddr_or_hostname)
        )


@bgp.group(cls=clicommon.AbbreviationGroup)
def startup():
    """Start up BGP session(s)"""
    pass


# 'all' subcommand
@startup.command()
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
def all(verbose):  # noqa: F811
    """Start up all BGP sessions
    In the case of Multi-Asic platform, we startup only the EBGP sessions with external neighbors.
    """
    log.log_info("'bgp startup all' executing...")
    namespaces = [DEFAULT_NAMESPACE]

    if multi_asic.is_multi_asic():
        ns_list = multi_asic.get_all_namespaces()
        namespaces = ns_list["front_ns"]

    # Connect to CONFIG_DB in linux host (in case of single ASIC) or CONFIG_DB in all the
    # namespaces (in case of multi ASIC) and do the sepcified "action" on the BGP neighbor(s)
    for namespace in namespaces:
        config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
        config_db.connect()
        bgp_neighbor_ip_list = _get_all_neighbor_ipaddresses(config_db)
        for ipaddr in bgp_neighbor_ip_list:
            _change_bgp_session_status_by_addr(config_db, ipaddr, "up", verbose)


# 'neighbor' subcommand
@startup.command()
@click.argument("ipaddr_or_hostname", metavar="<ipaddr_or_hostname>", required=True)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
def neighbor(ipaddr_or_hostname, verbose):  # noqa: F811
    log.log_info("'bgp startup neighbor {}' executing...".format(ipaddr_or_hostname))
    """Start up BGP session by neighbor IP address or hostname.
       User can specify either internal or external BGP neighbor to startup
    """
    namespaces = [DEFAULT_NAMESPACE]
    found_neighbor = False

    if multi_asic.is_multi_asic():
        ns_list = multi_asic.get_all_namespaces()
        namespaces = ns_list["front_ns"] + ns_list["back_ns"]

    # Connect to CONFIG_DB in linux host (in case of single ASIC) or CONFIG_DB in all the
    # namespaces (in case of multi ASIC) and do the sepcified "action" on the BGP neighbor(s)
    for namespace in namespaces:
        config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
        config_db.connect()
        if _change_bgp_session_status(config_db, ipaddr_or_hostname, "up", verbose):
            found_neighbor = True

    if not found_neighbor:
        click.get_current_context().fail(
            "Could not locate neighbor '{}'".format(ipaddr_or_hostname)
        )


#
# 'remove' subgroup ('config bgp remove ...')
#


@bgp.group(cls=clicommon.AbbreviationGroup)
def remove():
    "Remove BGP neighbor configuration from the device"
    pass


@remove.command("neighbor")
@click.argument(
    "neighbor_ip_or_hostname", metavar="<neighbor_ip_or_hostname>", required=True
)
def remove_neighbor(neighbor_ip_or_hostname):
    """Deletes BGP neighbor configuration of given hostname or ip from devices
    User can specify either internal or external BGP neighbor to remove
    """
    namespaces = [DEFAULT_NAMESPACE]
    removed_neighbor = False

    if multi_asic.is_multi_asic():
        ns_list = multi_asic.get_all_namespaces()
        namespaces = ns_list["front_ns"] + ns_list["back_ns"]

    # Connect to CONFIG_DB in linux host (in case of single ASIC) or CONFIG_DB in all the
    # namespaces (in case of multi ASIC) and do the sepcified "action" on the BGP neighbor(s)
    for namespace in namespaces:
        config_db = ConfigDBConnector(use_unix_socket_path=True, namespace=namespace)
        config_db.connect()
        if _remove_bgp_neighbor_config(config_db, neighbor_ip_or_hostname):
            removed_neighbor = True

    if not removed_neighbor:
        click.get_current_context().fail(
            "Could not locate neighbor '{}'".format(neighbor_ip_or_hostname)
        )


#
# 'bgp autonomous-system' group
#
@bgp.group(cls=clicommon.AbbreviationGroup, name="autonomous-system")
def bgp_asn():
    """Specify autonomous system number"""
    pass


#
# 'bgp autonomous-system add' command
#
@bgp_asn.command("add")
@click.argument("as_num", metavar="<as_num>", required=True, type=BGP_ASN_RANGE)
@clicommon.pass_db
def asn_add(db, as_num):
    """Add autonomous system number"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if bgp_globals.get("local_asn"):
        ctx.fail("AS number is already specified")

    db.cfgdb.mod_entry("BGP_GLOBALS", "default", {"local_asn": as_num})


#
# 'bgp autonomous-system del' command
#
@bgp_asn.command("del")
@click.argument("as_num", metavar="<as_num>", required=True, type=BGP_ASN_RANGE)
@clicommon.pass_db
def asn_del(db, as_num):
    """Delete autonomous system number"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    local_asn = bgp_globals.get("local_asn")
    if local_asn:
        if local_asn != str(as_num):
            ctx.fail("Configured AS number is {}".format(local_asn))
    else:
        ctx.fail("AS number is not configured")

    db.cfgdb.delete_table("ROUTE_REDISTRIBUTE")
    db.cfgdb.delete_table("BGP_NEIGHBOR_AF")
    db.cfgdb.delete_table("BGP_NEIGHBOR")
    db.cfgdb.delete_table("BGP_GLOBALS_AF_NETWORK")
    db.cfgdb.delete_table("BGP_GLOBALS_AF")
    db.cfgdb.delete_table("BGP_GLOBALS")


#
# 'bgp router-id' group
#
@bgp.group(cls=clicommon.AbbreviationGroup, name="router-id")
def bgp_router_id():
    """Configure router identifier"""
    pass


#
# 'bgp router-id add' command
#
@bgp_router_id.command("add")
@click.argument("router_id", metavar="<router_id>", required=True)
@clicommon.pass_db
def router_id_add(db, router_id):
    """Add router identifier"""
    ctx = click.get_current_context()

    try:
        ipaddress.IPv4Address(router_id)
    except ValueError as err:
        ctx.fail("IP address is not valid: {}".format(err))

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    if bgp_globals.get("router_id"):
        ctx.fail("Router identifier is already specified")

    db.cfgdb.mod_entry("BGP_GLOBALS", "default", {"router_id": router_id})


#
# 'bgp router-id set' command
#
@bgp_router_id.command("set")
@click.argument("router_id", metavar="<router_id>", required=True)
@clicommon.pass_db
def router_id_set(db, router_id):
    """Set router identifier"""
    ctx = click.get_current_context()

    try:
        ipaddress.IPv4Address(router_id)
    except ValueError as err:
        ctx.fail("IP address is not valid: {}".format(err))

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    if not bgp_globals.get("router_id"):
        ctx.fail("Router ID is not configured")

    db.cfgdb.mod_entry("BGP_GLOBALS", "default", {"router_id": router_id})


#
# 'bgp router-id del' command
#
@bgp_router_id.command("del")
@click.argument("router_id", metavar="<router_id>", required=True)
@clicommon.pass_db
def router_id_del(db, router_id):
    """Delete router identifier"""
    ctx = click.get_current_context()

    try:
        ipaddress.IPv4Address(router_id)
    except ValueError as err:
        ctx.fail("IP address is not valid: {}".format(err))

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    r_id = bgp_globals.get("router_id")
    if r_id:
        if r_id != str(router_id):
            ctx.fail("Configured router ID is {}".format(r_id))
    else:
        ctx.fail("Router ID is not configured")

    if bgp_globals.get("router_id"):
        del bgp_globals["router_id"]
        db.cfgdb.set_entry("BGP_GLOBALS", "default", bgp_globals)


#
# 'bgp cluster-id' group
#
@bgp.group(cls=clicommon.AbbreviationGroup, name="cluster-id")
def bgp_cluster_id():
    """Configure cluster identifier"""
    pass


#
# 'bgp cluster-id add' command
#
@bgp_cluster_id.command("add")
@click.argument("cluster_id", metavar="<cluster_id>", required=True)
@clicommon.pass_db
def cluster_id_add(db, cluster_id):
    """Add cluster identifier"""
    ctx = click.get_current_context()

    try:
        ipaddress.IPv4Address(cluster_id)
    except ValueError as err:
        ctx.fail("IP address is not valid: {}".format(err))

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    if bgp_globals.get("rr_cluster_id"):
        ctx.fail("Cluster ID is already added")

    db.cfgdb.mod_entry("BGP_GLOBALS", "default", {"rr_cluster_id": cluster_id})


#
# 'bgp cluster-id set' command
#
@bgp_cluster_id.command("set")
@click.argument("cluster_id", metavar="<cluster_id>", required=True)
@clicommon.pass_db
def cluster_id_set(db, cluster_id):
    """Set cluster identifier"""
    ctx = click.get_current_context()

    try:
        ipaddress.IPv4Address(cluster_id)
    except ValueError as err:
        ctx.fail("IP address is not valid: {}".format(err))

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    if not bgp_globals.get("rr_cluster_id"):
        ctx.fail("Cluster ID is not configured")

    db.cfgdb.mod_entry("BGP_GLOBALS", "default", {"rr_cluster_id": cluster_id})


#
# 'bgp cluster-id del' command
#
@bgp_cluster_id.command("del")
@click.argument("cluster_id", metavar="<cluster_id>", required=True)
@clicommon.pass_db
def cluster_id_del(db, cluster_id):
    """Delete cluster identifier"""
    ctx = click.get_current_context()

    try:
        ipaddress.IPv4Address(cluster_id)
    except ValueError as err:
        ctx.fail("IP address is not valid: {}".format(err))

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    rr_cluster_id = bgp_globals.get("rr_cluster_id")
    if rr_cluster_id:
        if rr_cluster_id != str(cluster_id):
            ctx.fail("Configured cluster ID is {}".format(rr_cluster_id))
    else:
        ctx.fail("Cluster ID is not configured")

    if bgp_globals.get("rr_cluster_id"):
        del bgp_globals["rr_cluster_id"]
        db.cfgdb.set_entry("BGP_GLOBALS", "default", bgp_globals)


#
# 'bgp ebgp-requires-policy' command
#
@bgp.command("ebgp-requires-policy")
@click.argument(
    "mode", metavar="<mode>", required=True, type=click.Choice(["on", "off"])
)
@clicommon.pass_db
def ebgp_requires_policy(db, mode):
    """Require in and out policy for eBGP peers"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    db.cfgdb.mod_entry(
        "BGP_GLOBALS",
        "default",
        {"ebgp_requires_policy": "true" if mode == "on" else "false"},
    )


#
# 'bgp fast-external-failover' command
#
@bgp.command("fast-external-failover")
@click.argument(
    "mode", metavar="<mode>", required=True, type=click.Choice(["on", "off"])
)
@clicommon.pass_db
def fast_ext_failover(db, mode):
    """Immediately reset session if a link to a directly connected external peer goes down"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    db.cfgdb.mod_entry(
        "BGP_GLOBALS",
        "default",
        {"fast_external_failover": "true" if mode == "on" else "false"},
    )


#
# 'bgp default' group
#
@bgp.group(cls=clicommon.AbbreviationGroup, name="default")
def bgp_default():
    """Configure BGP defaults"""
    pass


#
# 'bgp default ipv4-unicast' command
#
@bgp_default.command("ipv4-unicast")
@click.argument(
    "mode", metavar="<mode>", required=True, type=click.Choice(["on", "off"])
)
@clicommon.pass_db
def default_ipv4_unicast(db, mode):
    """Configure ipv4-unicast for a peer by default"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    db.cfgdb.mod_entry(
        "BGP_GLOBALS",
        "default",
        {"default_ipv4_unicast": "true" if mode == "on" else "false"},
    )


#
# 'bgp client-to-client' group
#
@bgp.group(cls=clicommon.AbbreviationGroup, name="client-to-client")
def bgp_clnt_to_clnt():
    """Configure client to client route reflection"""
    pass


#
# 'bgp client-to-client reflection' command
#
@bgp_clnt_to_clnt.command("reflection")
@click.argument(
    "mode", metavar="<mode>", required=True, type=click.Choice(["on", "off"])
)
@clicommon.pass_db
def clnt_to_clnt_refl(db, mode):
    """Configure reflection of routes"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    db.cfgdb.mod_entry(
        "BGP_GLOBALS",
        "default",
        {"rr_clnt_to_clnt_reflection": "true" if mode == "on" else "false"},
    )


#
# 'bgp bestpath' group
#
@bgp.group(cls=clicommon.AbbreviationGroup, name="bestpath")
def bgp_bestpath():
    """Configure bestpath selection"""
    pass


#
# 'bgp bestpath compare-routerid' command
#
@bgp_bestpath.command("compare-routerid")
@click.argument(
    "mode", metavar="<mode>", required=True, type=click.Choice(["on", "off"])
)
@clicommon.pass_db
def bestpath_cmp_router_id(db, mode):
    """Compare router-id for identical EBGP paths"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    db.cfgdb.mod_entry(
        "BGP_GLOBALS",
        "default",
        {"external_compare_router_id": "true" if mode == "on" else "false"},
    )


#
# 'bgp bestpath as-path' group
#
@bgp_bestpath.group(cls=clicommon.AbbreviationGroup, name="as-path")
def bgp_bestpath_as_path():
    """Configure AS-path attribute"""
    pass


#
# 'bgp bestpath as-path multipath-relax' command
#
@bgp_bestpath_as_path.command("multipath-relax")
@click.argument(
    "mode", metavar="<mode>", required=True, type=click.Choice(["on", "off"])
)
@clicommon.pass_db
def as_path_multipath_relax(db, mode):
    """Allow load sharing across routes that have different AS paths (but same length)"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    db.cfgdb.mod_entry(
        "BGP_GLOBALS",
        "default",
        {"load_balance_mp_relax": "true" if mode == "on" else "false"},
    )


#
# 'bgp listen' group
#
@bgp.group(cls=clicommon.AbbreviationGroup, name="listen")
def bgp_listen():
    """BGP Dynamic Neighbors listen configuration"""
    pass


#
# 'bgp listen limit' group
#
@bgp_listen.group(cls=clicommon.AbbreviationGroup, name="limit")
def bgp_listen_limit():
    """Maximum number of BGP Dynamic Neighbors that can be created"""
    pass


#
# 'bgp listen limit add' command
#
@bgp_listen_limit.command("add")
@click.argument("limit", metavar="<limit>", required=True, type=BGP_LISTEN_LIMIT_RANGE)
@clicommon.pass_db
def listen_limit_add(db, limit):
    """Add Dynamic Neighbors listen limit value"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    if bgp_globals.get("max_dynamic_neighbors"):
        ctx.fail("Listen limit is already specified")

    db.cfgdb.mod_entry("BGP_GLOBALS", "default", {"max_dynamic_neighbors": limit})


#
# 'bgp listen limit set' command
#
@bgp_listen_limit.command("set")
@click.argument("limit", metavar="<limit>", required=True, type=BGP_LISTEN_LIMIT_RANGE)
@clicommon.pass_db
def listen_limit_set(db, limit):
    """Set Dynamic Neighbors listen limit value"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    if not bgp_globals.get("max_dynamic_neighbors"):
        ctx.fail("Listen limit is not configured")

    db.cfgdb.mod_entry("BGP_GLOBALS", "default", {"max_dynamic_neighbors": limit})


#
# 'bgp listen limit del' command
#
@bgp_listen_limit.command("del")
@click.argument("limit", metavar="<limit>", required=True, type=BGP_LISTEN_LIMIT_RANGE)
@clicommon.pass_db
def listen_limit_del(db, limit):
    """Delete Dynamic Neighbors listen limit value"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    max_dyn_neighbors = bgp_globals.get("max_dynamic_neighbors")
    if max_dyn_neighbors:
        if max_dyn_neighbors != str(limit):
            ctx.fail("Configured listen limit is {}".format(max_dyn_neighbors))
    else:
        ctx.fail("Listen limit is not configured")

    if bgp_globals.get("max_dynamic_neighbors"):
        del bgp_globals["max_dynamic_neighbors"]
        db.cfgdb.set_entry("BGP_GLOBALS", "default", bgp_globals)


#
# 'bgp graceful-restart' group
#
@bgp.group(cls=clicommon.AbbreviationGroup, name="graceful-restart")
def bgp_gr_restart():
    """Graceful restart capability parameters"""
    pass


#
# 'bgp graceful-restart mode' command
#
@bgp_gr_restart.command("mode")
@click.argument(
    "mode", metavar="<mode>", required=True, type=click.Choice(["on", "off"])
)
@clicommon.pass_db
def gr_restart_state(db, mode):
    """Configure graceful-restart state"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    db.cfgdb.mod_entry(
        "BGP_GLOBALS",
        "default",
        {"graceful_restart_enable": "true" if mode == "on" else "false"},
    )


#
# 'bgp graceful-restart preserve-fw-state' command
#
@bgp_gr_restart.command("preserve-fw-state")
@click.argument(
    "mode", metavar="<mode>", required=True, type=click.Choice(["on", "off"])
)
@clicommon.pass_db
def gr_restart_preserve_fw_state(db, mode):
    """Sets F-bit indication that fib is preserved while doing Graceful Restart"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    db.cfgdb.mod_entry(
        "BGP_GLOBALS",
        "default",
        {"gr_preserve_fw_state": "true" if mode == "on" else "false"},
    )


#
# 'bgp graceful-restart restart-time' group
#
@bgp_gr_restart.group(cls=clicommon.AbbreviationGroup, name="restart-time")
def bgp_gr_restart_time():
    """Time to wait to delete stale routes before a BGP open message is received"""
    pass


#
# 'bgp graceful-restart restart-time add' command
#
@bgp_gr_restart_time.command("add")
@click.argument("time", metavar="<time>", required=True, type=BGP_GR_RESTART_TIME_RANGE)
@clicommon.pass_db
def gr_restart_time_add(db, time):
    """Add the time to wait to delete stale routes before a BGP open message is received"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    if bgp_globals.get("gr_restart_time"):
        ctx.fail("Graceful restart time is already specified")

    db.cfgdb.mod_entry("BGP_GLOBALS", "default", {"gr_restart_time": time})


#
# 'bgp graceful-restart restart-time set' command
#
@bgp_gr_restart_time.command("set")
@click.argument("time", metavar="<time>", required=True, type=BGP_GR_RESTART_TIME_RANGE)
@clicommon.pass_db
def gr_restart_time_set(db, time):
    """Set the time to wait to delete stale routes before a BGP open message is received"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    if not bgp_globals.get("gr_restart_time"):
        ctx.fail("Graceful restart time is not configured")

    db.cfgdb.mod_entry("BGP_GLOBALS", "default", {"gr_restart_time": time})


#
# 'bgp graceful-restart restart-time del' command
#
@bgp_gr_restart_time.command("del")
@click.argument("time", metavar="<time>", required=True, type=BGP_GR_RESTART_TIME_RANGE)
@clicommon.pass_db
def gr_restart_time_del(db, time):
    """Delete the time to wait to delete stale routes before a BGP open message is received"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    gr_restart_time = bgp_globals.get("gr_restart_time")
    if gr_restart_time:
        if gr_restart_time != str(time):
            ctx.fail("Configured graceful restart time is {}".format(gr_restart_time))
    else:
        ctx.fail("Graceful restart time is not configured")

    if bgp_globals.get("gr_restart_time"):
        del bgp_globals["gr_restart_time"]
        db.cfgdb.set_entry("BGP_GLOBALS", "default", bgp_globals)


#
# 'bgp graceful-restart stalepath-time' group
#
@bgp_gr_restart.group(cls=clicommon.AbbreviationGroup, name="stalepath-time")
def bgp_gr_stalepath_time():
    """Max time to hold onto restarting peer's stale paths"""
    pass


#
# 'bgp graceful-restart stalepath-time add' command
#
@bgp_gr_stalepath_time.command("add")
@click.argument(
    "time", metavar="<time>", required=True, type=BGP_GR_STALEPATH_TIME_RANGE
)
@clicommon.pass_db
def gr_stalepath_time_add(db, time):
    """Add the max time to hold onto restarting peer's stale paths"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    if bgp_globals.get("gr_stale_routes_time"):
        ctx.fail("Graceful restart stalepath time is already specified")

    db.cfgdb.mod_entry("BGP_GLOBALS", "default", {"gr_stale_routes_time": time})


#
# 'bgp graceful-restart stalepath-time set' command
#
@bgp_gr_stalepath_time.command("set")
@click.argument(
    "time", metavar="<time>", required=True, type=BGP_GR_STALEPATH_TIME_RANGE
)
@clicommon.pass_db
def gr_stalepath_time_set(db, time):
    """Set the max time to hold onto restarting peer's stale paths"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    if not bgp_globals.get("gr_stale_routes_time"):
        ctx.fail("Graceful restart stalepath time is not configured")

    db.cfgdb.mod_entry("BGP_GLOBALS", "default", {"gr_stale_routes_time": time})


#
# 'bgp graceful-restart stalepath-time del' command
#
@bgp_gr_stalepath_time.command("del")
@click.argument(
    "time", metavar="<time>", required=True, type=BGP_GR_STALEPATH_TIME_RANGE
)
@clicommon.pass_db
def gr_stalepath_time_del(db, time):
    """Delete the max time to hold onto restarting peer's stale paths"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    gr_stale_routes_time = bgp_globals.get("gr_stale_routes_time")
    if gr_stale_routes_time:
        if gr_stale_routes_time != str(time):
            ctx.fail(
                "Configured graceful restart stalepath time is {}".format(
                    gr_stale_routes_time
                )
            )
    else:
        ctx.fail("Graceful restart stalepath time is not configured")

    if bgp_globals.get("gr_stale_routes_time"):
        del bgp_globals["gr_stale_routes_time"]
        db.cfgdb.set_entry("BGP_GLOBALS", "default", bgp_globals)


#
# 'bgp neighbor' group
#
@bgp.group(cls=clicommon.AbbreviationGroup, name="neighbor")
def bgp_neighbor():
    """Configure BGP neighbors"""
    pass


#
# 'bgp neighbor remote-as' group
#
@bgp_neighbor.group(cls=clicommon.AbbreviationGroup, name="remote-as")
def bgp_remote_as():
    """Configure BGP neighbor remote-as"""
    pass


#
# 'bgp neighbor remote-as add' command
#
@bgp_remote_as.command("add")
@click.argument("ip_intf", metavar="<ip_addr|interface_name>", required=True)
@click.argument("remote-as", metavar="<as_num|external|internal>", required=True)
@clicommon.pass_db
def neighbor_remote_as_add(db, ip_intf, remote_as):
    """Add BGP neighbor remote-as"""
    ctx = click.get_current_context()

    if not get_interface_table_name(ip_intf):
        try:
            ipaddress.ip_address(ip_intf)
        except ValueError:
            ctx.fail("Neighbor interface/IP address is not valid")

    if remote_as not in ["external", "internal"]:
        try:
            if int(remote_as) not in range(BGP_ASN_MIN, BGP_ASN_MAX):
                raise ValueError
        except ValueError:
            ctx.fail("Remote AS is not valid")

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_neighbor = db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", ip_intf))
    if bgp_neighbor.get("asn"):
        ctx.fail("BGP neighbor remote-as already exists")

    db.cfgdb.mod_entry("BGP_NEIGHBOR", ("default", ip_intf), {"asn": remote_as})


#
# 'bgp neighbor remote-as set' command
#
@bgp_remote_as.command("set")
@click.argument("ip_intf", metavar="<ip_addr|interface_name>", required=True)
@click.argument("remote-as", metavar="<as_num|external|internal>", required=True)
@clicommon.pass_db
def neighbor_remote_as_set(db, ip_intf, remote_as):
    """Set BGP neighbor remote-as"""
    ctx = click.get_current_context()

    if not get_interface_table_name(ip_intf):
        try:
            ipaddress.ip_address(ip_intf)
        except ValueError:
            ctx.fail("Neighbor interface/IP address is not valid")

    if remote_as not in ["external", "internal"]:
        try:
            if int(remote_as) not in range(BGP_ASN_MIN, BGP_ASN_MAX):
                raise ValueError
        except ValueError:
            ctx.fail("Remote AS is not valid")

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_neighbor = db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", ip_intf))
    if not bgp_neighbor.get("asn"):
        ctx.fail("BGP neighbor remote-as is not configured")

    db.cfgdb.mod_entry("BGP_NEIGHBOR", ("default", ip_intf), {"asn": remote_as})


#
# 'bgp neighbor remote-as del' command
#
@bgp_remote_as.command("del")
@click.argument("ip_intf", metavar="<ip_addr|interface_name>", required=True)
@click.argument("remote-as", metavar="<as_num|external|internal>", required=True)
@clicommon.pass_db
def neighbor_remote_as_del(db, ip_intf, remote_as):
    """Delete BGP neighbor remote-as"""
    ctx = click.get_current_context()

    if not get_interface_table_name(ip_intf):
        try:
            ipaddress.ip_address(ip_intf)
        except ValueError:
            ctx.fail("Neighbor interface/IP address is not valid")

    if remote_as not in ["external", "internal"]:
        try:
            if int(remote_as) not in range(BGP_ASN_MIN, BGP_ASN_MAX):
                raise ValueError
        except ValueError:
            ctx.fail("Remote AS is not valid")

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_neighbor = db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", ip_intf))
    if not bgp_neighbor:
        ctx.fail("BGP neighbor does not exist")

    asn = bgp_neighbor.get("asn")
    if asn:
        if asn != str(remote_as):
            ctx.fail("Configured BGP neighbor remote-as is {}".format(asn))
    else:
        ctx.fail("BGP neighbor remote-as is not configured")

    db.cfgdb.set_entry("BGP_NEIGHBOR_AF", ("default", ip_intf, "l2vpn_evpn"), None)
    db.cfgdb.set_entry("BGP_NEIGHBOR_AF", ("default", ip_intf, "ipv4_unicast"), None)
    db.cfgdb.set_entry("BGP_NEIGHBOR", ("default", ip_intf), None)


#
# 'bgp neighbor update-source' group
#
@bgp_neighbor.group(cls=clicommon.AbbreviationGroup, name="update-source")
def bgp_neighbor_upd_source():
    """Configure BGP neighbor update-source"""
    pass


#
# 'bgp neighbor update-source add' command
#
@bgp_neighbor_upd_source.command("add")
@click.argument("ip_intf", metavar="<ip_addr|interface_name>", required=True)
@click.argument("upd_source", metavar="<ip_addr|interface_name>", required=True)
@clicommon.pass_db
def neighbor_upd_source_add(db, ip_intf, upd_source):
    """Add BGP neighbor update-source"""
    ctx = click.get_current_context()

    if not get_interface_table_name(ip_intf):
        try:
            ipaddress.ip_address(ip_intf)
        except ValueError:
            ctx.fail("Neighbor interface/IP address is not valid")

    if not get_interface_table_name(upd_source):
        try:
            ipaddress.ip_address(upd_source)
        except ValueError:
            ctx.fail("Update source interface/IP address is not valid")

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_neighbor = db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", ip_intf))
    if not bgp_neighbor.get("asn"):
        ctx.fail("Specify BGP neighbor remote-as first")
    if bgp_neighbor.get("local_addr"):
        ctx.fail("BGP neighbor update source already exists")

    db.cfgdb.mod_entry("BGP_NEIGHBOR", ("default", ip_intf), {"local_addr": upd_source})


#
# 'bgp neighbor update-source set' command
#
@bgp_neighbor_upd_source.command("set")
@click.argument("ip_intf", metavar="<ip_addr|interface_name>", required=True)
@click.argument("upd_source", metavar="<ip_addr|interface_name>", required=True)
@clicommon.pass_db
def neighbor_upd_source_set(db, ip_intf, upd_source):
    """Set BGP neighbor update-source"""
    ctx = click.get_current_context()

    if not get_interface_table_name(ip_intf):
        try:
            ipaddress.ip_address(ip_intf)
        except ValueError:
            ctx.fail("Neighbor interface/IP address is not valid")

    if not get_interface_table_name(upd_source):
        try:
            ipaddress.ip_address(upd_source)
        except ValueError:
            ctx.fail("Update source interface/IP address is not valid")

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_neighbor = db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", ip_intf))
    if not bgp_neighbor.get("asn"):
        ctx.fail("Specify BGP neighbor remote-as first")
    if not bgp_neighbor.get("local_addr"):
        ctx.fail("BGP neighbor update source is not configured")

    db.cfgdb.mod_entry("BGP_NEIGHBOR", ("default", ip_intf), {"local_addr": upd_source})


#
# 'bgp neighbor update-source del' command
#
@bgp_neighbor_upd_source.command("del")
@click.argument("ip_intf", metavar="<ip_addr|interface_name>", required=True)
@click.argument("upd_source", metavar="<ip_addr|interface_name>", required=True)
@clicommon.pass_db
def neighbor_upd_source_del(db, ip_intf, upd_source):
    """Delete BGP neighbor update-source"""
    ctx = click.get_current_context()

    if not get_interface_table_name(ip_intf):
        try:
            ipaddress.ip_address(ip_intf)
        except ValueError:
            ctx.fail("Neighbor interface/IP address is not valid")

    if not get_interface_table_name(upd_source):
        try:
            ipaddress.ip_address(upd_source)
        except ValueError:
            ctx.fail("Update source interface/IP address is not valid")

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_neighbor = db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", ip_intf))
    if not bgp_neighbor:
        ctx.fail("BGP neighbor does not exist")

    local_addr = bgp_neighbor.get("local_addr")
    if local_addr:
        if upd_source != str(local_addr):
            ctx.fail("Configured BGP neighbor update source is {}".format(local_addr))
    else:
        ctx.fail("BGP neighbor update source is not configured")

    del bgp_neighbor["local_addr"]
    db.cfgdb.set_entry("BGP_NEIGHBOR", ("default", ip_intf), bgp_neighbor)


#
# 'bgp neighbor advertisement-interval' group
#
@bgp_neighbor.group(cls=clicommon.AbbreviationGroup, name="advertisement-interval")
def bgp_neighbor_adv_interval():
    """Minimum interval between sending BGP routing updates"""
    pass


#
# 'bgp neighbor advertisement-interval add' command
#
@bgp_neighbor_adv_interval.command("add")
@click.argument("ip_intf", metavar="<ip_addr|interface_name>", required=True)
@click.argument(
    "interval",
    metavar="<interval>",
    required=True,
    type=BGP_NEIGHBOR_ADV_INTERVAL_RANGE,
)
@clicommon.pass_db
def neighbor_adv_int_add(db, ip_intf, interval):
    """Add minimum interval between sending BGP routing updates"""
    ctx = click.get_current_context()

    if not get_interface_table_name(ip_intf):
        try:
            ipaddress.ip_address(ip_intf)
        except ValueError:
            ctx.fail("Neighbor interface/IP address is not valid")

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_neighbor = db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", ip_intf))
    if not bgp_neighbor.get("asn"):
        ctx.fail("Specify BGP neighbor remote-as first")
    if bgp_neighbor.get("min_adv_interval"):
        ctx.fail("BGP neighbor advertisement interval already exists")

    db.cfgdb.mod_entry(
        "BGP_NEIGHBOR", ("default", ip_intf), {"min_adv_interval": interval}
    )


#
# 'bgp neighbor advertisement-interval set' command
#
@bgp_neighbor_adv_interval.command("set")
@click.argument("ip_intf", metavar="<ip_addr|interface_name>", required=True)
@click.argument(
    "interval",
    metavar="<interval>",
    required=True,
    type=BGP_NEIGHBOR_ADV_INTERVAL_RANGE,
)
@clicommon.pass_db
def neighbor_adv_int_set(db, ip_intf, interval):
    """Set minimum interval between sending BGP routing updates"""
    ctx = click.get_current_context()

    if not get_interface_table_name(ip_intf):
        try:
            ipaddress.ip_address(ip_intf)
        except ValueError:
            ctx.fail("Neighbor interface/IP address is not valid")

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_neighbor = db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", ip_intf))
    if not bgp_neighbor.get("asn"):
        ctx.fail("Specify BGP neighbor remote-as first")
    if not bgp_neighbor.get("min_adv_interval"):
        ctx.fail("BGP neighbor advertisement interval is not configured")

    db.cfgdb.mod_entry(
        "BGP_NEIGHBOR", ("default", ip_intf), {"min_adv_interval": interval}
    )


#
# 'bgp neighbor advertisement-interval del' command
#
@bgp_neighbor_adv_interval.command("del")
@click.argument("ip_intf", metavar="<ip_addr|interface_name>", required=True)
@click.argument(
    "interval",
    metavar="<interval>",
    required=True,
    type=BGP_NEIGHBOR_ADV_INTERVAL_RANGE,
)
@clicommon.pass_db
def neighbor_adv_int_del(db, ip_intf, interval):
    """Delete minimum interval between sending BGP routing updates"""
    ctx = click.get_current_context()

    if not get_interface_table_name(ip_intf):
        try:
            ipaddress.ip_address(ip_intf)
        except ValueError:
            ctx.fail("Neighbor interface/IP address is not valid")

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_neighbor = db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", ip_intf))
    if not bgp_neighbor:
        ctx.fail("BGP neighbor does not exist")

    min_adv_interval = bgp_neighbor.get("min_adv_interval")
    if min_adv_interval:
        if min_adv_interval != str(interval):
            ctx.fail(
                "Configured BGP neighbor advertisement interval is {}".format(
                    min_adv_interval
                )
            )
    else:
        ctx.fail("BGP neighbor advertisement interval is not configured")

    del bgp_neighbor["min_adv_interval"]
    db.cfgdb.set_entry("BGP_NEIGHBOR", ("default", ip_intf), bgp_neighbor)


#
# 'bgp neighbor timers' group
#
@bgp_neighbor.group(cls=clicommon.AbbreviationGroup, name="timers")
def bgp_neighbor_timers():
    """Configure BGP neighbor timers"""
    pass


#
# 'bgp neighbor timers add' command
#
@bgp_neighbor_timers.command("add")
@click.argument("ip_intf", metavar="<ip_addr|interface_name>", required=True)
@click.argument(
    "keepalive", metavar="<keepalive>", required=True, type=BGP_NEIGHBOR_TIMER_RANGE
)
@click.argument(
    "holdtime", metavar="<holdtime>", required=True, type=BGP_NEIGHBOR_TIMER_RANGE
)
@clicommon.pass_db
def neighbor_timers_add(db, ip_intf, keepalive, holdtime):
    """Add BGP neighbor timers"""
    ctx = click.get_current_context()

    if not get_interface_table_name(ip_intf):
        try:
            ipaddress.ip_address(ip_intf)
        except ValueError:
            ctx.fail("Neighbor interface/IP address is not valid")

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_neighbor = db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", ip_intf))
    if not bgp_neighbor.get("asn"):
        ctx.fail("Specify BGP neighbor remote-as first")
    if bgp_neighbor.get("keepalive") and bgp_neighbor.get("holdtime"):
        ctx.fail("BGP neighbor timers are already configured")

    db.cfgdb.mod_entry(
        "BGP_NEIGHBOR",
        ("default", ip_intf),
        {"keepalive": keepalive, "holdtime": holdtime},
    )


#
# 'bgp neighbor timers set' command
#
@bgp_neighbor_timers.command("set")
@click.argument("ip_intf", metavar="<ip_addr|interface_name>", required=True)
@click.argument(
    "keepalive", metavar="<keepalive>", required=True, type=BGP_NEIGHBOR_TIMER_RANGE
)
@click.argument(
    "holdtime", metavar="<holdtime>", required=True, type=BGP_NEIGHBOR_TIMER_RANGE
)
@clicommon.pass_db
def neighbor_timers_set(db, ip_intf, keepalive, holdtime):
    """Set BGP neighbor timers"""
    ctx = click.get_current_context()

    if not get_interface_table_name(ip_intf):
        try:
            ipaddress.ip_address(ip_intf)
        except ValueError:
            ctx.fail("Neighbor interface/IP address is not valid")

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_neighbor = db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", ip_intf))
    if not bgp_neighbor.get("asn"):
        ctx.fail("Specify BGP neighbor remote-as first")
    if not bgp_neighbor.get("keepalive") or not bgp_neighbor.get("holdtime"):
        ctx.fail("BGP neighbor timers are not configured")

    db.cfgdb.mod_entry(
        "BGP_NEIGHBOR",
        ("default", ip_intf),
        {"keepalive": keepalive, "holdtime": holdtime},
    )


#
# 'bgp neighbor timers del' command
#
@bgp_neighbor_timers.command("del")
@click.argument("ip_intf", metavar="<ip_addr|interface_name>", required=True)
@click.argument(
    "keepalive", metavar="<keepalive>", required=True, type=BGP_NEIGHBOR_TIMER_RANGE
)
@click.argument(
    "holdtime", metavar="<holdtime>", required=True, type=BGP_NEIGHBOR_TIMER_RANGE
)
@clicommon.pass_db
def neighbor_timers_del(db, ip_intf, keepalive, holdtime):
    """Delete BGP neighbor timers"""
    ctx = click.get_current_context()

    if not get_interface_table_name(ip_intf):
        try:
            ipaddress.ip_address(ip_intf)
        except ValueError:
            ctx.fail("Neighbor interface/IP address is not valid")

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_neighbor = db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", ip_intf))
    if not bgp_neighbor:
        ctx.fail("BGP neighbor does not exist")

    keepalive_entry = bgp_neighbor.get("keepalive")
    holdtime_entry = bgp_neighbor.get("holdtime")
    if keepalive_entry and holdtime_entry:
        if keepalive_entry != str(keepalive) or holdtime_entry != str(holdtime):
            ctx.fail(
                "Configured BGP neighbor timers are {} {}".format(
                    keepalive_entry, holdtime_entry
                )
            )
    else:
        ctx.fail("BGP neighbor timers are not configured")

    if bgp_neighbor.get("keepalive"):
        del bgp_neighbor["keepalive"]
    if bgp_neighbor.get("holdtime"):
        del bgp_neighbor["holdtime"]
    db.cfgdb.set_entry("BGP_NEIGHBOR", ("default", ip_intf), bgp_neighbor)


#
# 'bgp neighbor local-as' group
#
@bgp_neighbor.group(cls=clicommon.AbbreviationGroup, name="local-as")
def bgp_neighbor_local_as():
    """Specify a local-as number"""
    pass


#
# 'bgp neighbor local-as add' command
#
@bgp_neighbor_local_as.command("add")
@click.argument("ip_intf", metavar="<ip_addr|interface_name>", required=True)
@click.argument("as_num", metavar="<as_num>", required=True, type=BGP_ASN_RANGE)
@click.option("--no-prepend", required=False, is_flag=True)
@click.option("--replace-as", required=False, is_flag=True)
@clicommon.pass_db
def neighbor_local_as_add(db, ip_intf, as_num, no_prepend, replace_as):
    """Add AS number used as local AS"""
    ctx = click.get_current_context()

    if not get_interface_table_name(ip_intf):
        try:
            ipaddress.ip_address(ip_intf)
        except ValueError:
            ctx.fail("Neighbor interface/IP address is not valid")

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_neighbor = db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", ip_intf))
    if not bgp_neighbor.get("asn"):
        ctx.fail("Specify BGP neighbor remote-as first")
    if bgp_neighbor.get("local_asn"):
        ctx.fail("BGP neighbor local AS is already specified")

    if str(as_num) == bgp_globals.get("local_asn"):
        ctx.fail("Cannot have local-as same as BGP AS number")

    if not no_prepend and replace_as:
        ctx.fail("--no-prepend flag must be used with --replace-as")

    bgp_neighbor["local_asn"] = as_num
    bgp_neighbor["local_as_no_prepend"] = "true" if no_prepend else "false"
    bgp_neighbor["local_as_replace_as"] = "true" if replace_as else "false"
    db.cfgdb.set_entry("BGP_NEIGHBOR", ("default", ip_intf), bgp_neighbor)


#
# 'bgp neighbor local-as set' command
#
@bgp_neighbor_local_as.command("set")
@click.argument("ip_intf", metavar="<ip_addr|interface_name>", required=True)
@click.argument("as_num", metavar="<as_num>", required=True, type=BGP_ASN_RANGE)
@click.option("--no-prepend", required=False, is_flag=True)
@click.option("--replace-as", required=False, is_flag=True)
@clicommon.pass_db
def neighbor_local_as_set(db, ip_intf, as_num, no_prepend, replace_as):
    """Set AS number used as local AS"""
    ctx = click.get_current_context()

    if not get_interface_table_name(ip_intf):
        try:
            ipaddress.ip_address(ip_intf)
        except ValueError:
            ctx.fail("Neighbor interface/IP address is not valid")

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_neighbor = db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", ip_intf))
    if not bgp_neighbor.get("asn"):
        ctx.fail("Specify BGP neighbor remote-as first")
    if not bgp_neighbor.get("local_asn"):
        ctx.fail("BGP neighbor local AS is not configured")

    if str(as_num) == bgp_globals.get("local_asn"):
        ctx.fail("Cannot have local-as same as BGP AS number")

    if not no_prepend and replace_as:
        ctx.fail("--no-prepend flag must be used with --replace-as")

    bgp_neighbor["local_asn"] = as_num
    bgp_neighbor["local_as_no_prepend"] = "true" if no_prepend else "false"
    bgp_neighbor["local_as_replace_as"] = "true" if replace_as else "false"
    db.cfgdb.set_entry("BGP_NEIGHBOR", ("default", ip_intf), bgp_neighbor)


#
# 'bgp neighbor local-as del' command
#
@bgp_neighbor_local_as.command("del")
@click.argument("ip_intf", metavar="<ip_addr|interface_name>", required=True)
@click.argument("as_num", metavar="<as_num>", required=True, type=BGP_ASN_RANGE)
@clicommon.pass_db
def neighbor_local_as_del(db, ip_intf, as_num):
    """Delete AS number used as local AS"""
    ctx = click.get_current_context()

    if not get_interface_table_name(ip_intf):
        try:
            ipaddress.ip_address(ip_intf)
        except ValueError:
            ctx.fail("Neighbor interface/IP address is not valid")

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_neighbor = db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", ip_intf))
    if not bgp_neighbor:
        ctx.fail("BGP neighbor does not exist")

    local_asn = bgp_neighbor.get("local_asn")
    if local_asn:
        if local_asn != str(as_num):
            ctx.fail("Configured BGP neighbor local AS is {}".format(local_asn))
    else:
        ctx.fail("BGP neighbor local AS is not configured")

    del bgp_neighbor["local_asn"]
    if bgp_neighbor.get("local_as_no_prepend"):
        del bgp_neighbor["local_as_no_prepend"]
    if bgp_neighbor.get("local_as_replace_as"):
        del bgp_neighbor["local_as_replace_as"]
    db.cfgdb.set_entry("BGP_NEIGHBOR", ("default", ip_intf), bgp_neighbor)


#
# 'bgp neighbor shutdown' command
#
@bgp_neighbor.command("shutdown")
@click.argument("ip_intf", metavar="<ip_addr|interface_name>", required=True)
@click.argument(
    "mode", metavar="<mode>", required=True, type=click.Choice(["on", "off"])
)
@clicommon.pass_db
def neighbor_shutdown(db, ip_intf, mode):
    """Administratively shut down BGP neighbor"""
    ctx = click.get_current_context()

    if not get_interface_table_name(ip_intf):
        try:
            ipaddress.ip_address(ip_intf)
        except ValueError:
            ctx.fail("Neighbor interface/IP address is not valid")

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_neighbor = db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", ip_intf))
    if not bgp_neighbor.get("asn"):
        ctx.fail("Specify BGP neighbor remote-as first")

    db.cfgdb.mod_entry(
        "BGP_NEIGHBOR",
        ("default", ip_intf),
        {"admin_status": "false" if mode == "on" else "true"},
    )


#
# 'bgp neighbor ebgp-multihop' command
#
@bgp_neighbor.command("ebgp-multihop")
@click.argument("ip_intf", metavar="<ip_addr|interface_name>", required=True)
@click.argument(
    "mode", metavar="<mode>", required=True, type=click.Choice(["on", "off"])
)
@click.option(
    "--max-hops", metavar="<max_hops>", required=False, type=BGP_NEIGHBOR_MULTIHOP_RANGE
)
@clicommon.pass_db
def neighbor_multihop(db, ip_intf, mode, max_hops):
    """Allow EBGP neighbors on not directly connected networks"""
    ctx = click.get_current_context()

    if not get_interface_table_name(ip_intf):
        try:
            ipaddress.ip_address(ip_intf)
        except ValueError:
            ctx.fail("Neighbor interface/IP address is not valid")

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_neighbor = db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", ip_intf))
    if not bgp_neighbor.get("asn"):
        ctx.fail("Specify BGP neighbor remote-as first")

    if bgp_neighbor.get("asn") != "internal" and bgp_neighbor.get(
        "asn"
    ) != bgp_globals.get("local_asn"):
        bgp_neighbor["ebgp_multihop"] = "true" if mode == "on" else "false"
        if max_hops:
            bgp_neighbor["ebgp_multihop_ttl"] = max_hops
        elif bgp_neighbor.get("ebgp_multihop_ttl"):
            del bgp_neighbor["ebgp_multihop_ttl"]
        db.cfgdb.set_entry("BGP_NEIGHBOR", ("default", ip_intf), bgp_neighbor)
    else:
        ctx.fail("Invalid command. Not an external neighbor")


#
# 'bgp address-family' group
#
@bgp.group(cls=clicommon.AbbreviationGroup, name="address-family")
def bgp_addr():
    """Address family configuration"""
    pass


#
# 'bgp address-family ipv4' group
#
@bgp_addr.group(cls=clicommon.AbbreviationGroup, name="ipv4")
def bgp_addr_ipv4():
    """IPv4 address family configuration"""
    pass


#
# 'bgp address-family ipv4 unicast' group
#
@bgp_addr_ipv4.group(cls=clicommon.AbbreviationGroup, name="unicast")
def bgp_addr_ipv4_unicast():
    """IPv4 unicast address family configuration"""
    pass


#
# 'bgp address-family ipv4 unicast neighbor' group
#
@bgp_addr_ipv4_unicast.group(cls=clicommon.AbbreviationGroup, name="neighbor")
def bgp_addr_ipv4_unicast_neighbor():
    """IPv4 unicast neighbor address family configuration"""
    pass


#
# 'bgp address-family ipv4 unicast neighbor activate' command
#
@bgp_addr_ipv4_unicast_neighbor.command("activate")
@click.argument("ip_intf", metavar="<ip_addr|interface_name>", required=True)
@click.argument(
    "mode", metavar="<mode>", required=True, type=click.Choice(["on", "off"])
)
@clicommon.pass_db
def ipv4_neighbor_activate(db, ip_intf, mode):
    """IPv4 neighbor activate"""
    ctx = click.get_current_context()

    if not get_interface_table_name(ip_intf):
        try:
            ipaddress.ip_address(ip_intf)
        except ValueError:
            ctx.fail("Neighbor interface/IP address is not valid")

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_neighbor = db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", ip_intf))
    if not bgp_neighbor.get("asn"):
        ctx.fail("Specify BGP neighbor remote-as first")

    db.cfgdb.mod_entry(
        "BGP_NEIGHBOR_AF",
        ("default", ip_intf, "ipv4_unicast"),
        {"admin_status": "true" if mode == "on" else "false"},
    )


#
# 'bgp address-family ipv4 unicast network' group
#
@bgp_addr_ipv4_unicast.group(cls=clicommon.AbbreviationGroup, name="network")
def bgp_addr_ipv4_unicast_network():
    """IPv4 unicast network address family configuration"""
    pass


#
# 'bgp address-family ipv4 unicast network add' command
#
@bgp_addr_ipv4_unicast_network.command("add")
@click.argument("network", metavar="<network>", required=True)
@clicommon.pass_db
def ipv4_unicast_network_add(db, network):
    """Add IPv4 unicast network"""
    ctx = click.get_current_context()

    try:
        network = ipaddress.IPv4Network(network, True)
    except ValueError as err:
        ctx.fail("Network address is not valid: {}".format(err))

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_globals_af_net = db.cfgdb.get_table("BGP_GLOBALS_AF_NETWORK").keys()
    if ("default", "ipv4_unicast", str(network)) in bgp_globals_af_net:
        ctx.fail("IPv4 unicast network already exists")

    db.cfgdb.set_entry(
        "BGP_GLOBALS_AF_NETWORK", ("default|ipv4_unicast", str(network)), {}
    )


#
# 'bgp address-family ipv4 unicast network del' command
#
@bgp_addr_ipv4_unicast_network.command("del")
@click.argument("network", metavar="<network>", required=True)
@clicommon.pass_db
def ipv4_unicast_network_del(db, network):
    """Delete IPv4 unicast network"""
    ctx = click.get_current_context()

    try:
        network = ipaddress.IPv4Network(network, True)
    except ValueError as err:
        ctx.fail("Network address is not valid: {}".format(err))

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_globals_af_net = db.cfgdb.get_table("BGP_GLOBALS_AF_NETWORK").keys()
    if ("default", "ipv4_unicast", str(network)) not in bgp_globals_af_net:
        ctx.fail("IPv4 unicast network does not exist")

    db.cfgdb.set_entry(
        "BGP_GLOBALS_AF_NETWORK", ("default|ipv4_unicast", str(network)), None
    )


#
# 'bgp address-family ipv4 unicast max-paths' group
#
@bgp_addr_ipv4_unicast.group(cls=clicommon.AbbreviationGroup, name="max-paths")
def bgp_addr_ipv4_unicast_max_paths():
    """IPv4 unicast max-paths address family configuration"""
    pass


#
# 'bgp address-family ipv4 unicast max-paths add' command
#
@bgp_addr_ipv4_unicast_max_paths.command("add")
@click.argument(
    "paths_num",
    metavar="<paths_num>",
    required=True,
    type=BGP_IPV4_UNICAST_MAX_PATHS_RANGE,
)
@clicommon.pass_db
def max_paths_add(db, paths_num):
    """Add IPv4 unicast max-paths"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_globals_af = db.cfgdb.get_entry("BGP_GLOBALS_AF", "default|ipv4_unicast")
    if bgp_globals_af.get("max_ebgp_paths"):
        ctx.fail("Max paths number is already specified")

    db.cfgdb.mod_entry(
        "BGP_GLOBALS_AF", "default|ipv4_unicast", {"max_ebgp_paths": paths_num}
    )


#
# 'bgp address-family ipv4 unicast max-paths set' command
#
@bgp_addr_ipv4_unicast_max_paths.command("set")
@click.argument(
    "paths_num",
    metavar="<paths_num>",
    required=True,
    type=BGP_IPV4_UNICAST_MAX_PATHS_RANGE,
)
@clicommon.pass_db
def max_paths_set(db, paths_num):
    """Set IPv4 unicast max-paths"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_globals_af = db.cfgdb.get_entry("BGP_GLOBALS_AF", "default|ipv4_unicast")
    if not bgp_globals_af.get("max_ebgp_paths"):
        ctx.fail("Max-paths number is not configured")

    db.cfgdb.mod_entry(
        "BGP_GLOBALS_AF", "default|ipv4_unicast", {"max_ebgp_paths": paths_num}
    )


#
# 'bgp address-family ipv4 unicast max-paths del' command
#
@bgp_addr_ipv4_unicast_max_paths.command("del")
@click.argument(
    "paths_num",
    metavar="<paths_num>",
    required=True,
    type=BGP_IPV4_UNICAST_MAX_PATHS_RANGE,
)
@clicommon.pass_db
def max_paths_del(db, paths_num):
    """Delete IPv4 unicast max-paths"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_globals_af = db.cfgdb.get_entry("BGP_GLOBALS_AF", "default|ipv4_unicast")
    max_ebgp_paths = bgp_globals_af.get("max_ebgp_paths")
    if max_ebgp_paths:
        if max_ebgp_paths != str(paths_num):
            ctx.fail("Configured max-paths number is {}".format(max_ebgp_paths))
    else:
        ctx.fail("Max-paths number is not configured")

    del bgp_globals_af["max_ebgp_paths"]
    db.cfgdb.set_entry("BGP_GLOBALS_AF", "default|ipv4_unicast", bgp_globals_af)


#
# 'bgp address-family ipv4 unicast max-paths ibgp' group
#
@bgp_addr_ipv4_unicast_max_paths.group(cls=clicommon.AbbreviationGroup, name="ibgp")
def bgp_addr_ipv4_unicast_max_paths_ibgp():
    """IPv4 unicast ibgp max-paths address family configuration"""
    pass


#
# 'bgp address-family ipv4 unicast max-paths ibgp add' command
#
@bgp_addr_ipv4_unicast_max_paths_ibgp.command("add")
@click.argument(
    "paths_num",
    metavar="<paths_num>",
    required=True,
    type=BGP_IPV4_UNICAST_MAX_PATHS_RANGE,
)
@click.option("--equal-cluster-length", required=False, is_flag=True)
@clicommon.pass_db
def max_paths_ibgp_add(db, paths_num, equal_cluster_length):
    """Add IPv4 unicast ibgp max-paths"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_globals_af = db.cfgdb.get_entry("BGP_GLOBALS_AF", "default|ipv4_unicast")
    if bgp_globals_af.get("max_ibgp_paths"):
        ctx.fail("Max ibgp paths number is already specified")

    bgp_globals_af["max_ibgp_paths"] = paths_num
    bgp_globals_af["ibgp_equal_cluster_length"] = (
        "true" if equal_cluster_length else "false"
    )
    db.cfgdb.set_entry("BGP_GLOBALS_AF", "default|ipv4_unicast", bgp_globals_af)


#
# 'bgp address-family ipv4 unicast max-paths ibgp set' command
#
@bgp_addr_ipv4_unicast_max_paths_ibgp.command("set")
@click.argument(
    "paths_num",
    metavar="<paths_num>",
    required=True,
    type=BGP_IPV4_UNICAST_MAX_PATHS_RANGE,
)
@click.option("--equal-cluster-length", required=False, is_flag=True)
@clicommon.pass_db
def max_paths_ibgp_set(db, paths_num, equal_cluster_length):
    """Set IPv4 unicast ibgp max-paths"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_globals_af = db.cfgdb.get_entry("BGP_GLOBALS_AF", "default|ipv4_unicast")
    if not bgp_globals_af.get("max_ibgp_paths"):
        ctx.fail("Max-paths ibgp number is not configured")

    bgp_globals_af["max_ibgp_paths"] = paths_num
    bgp_globals_af["ibgp_equal_cluster_length"] = (
        "true" if equal_cluster_length else "false"
    )
    db.cfgdb.set_entry("BGP_GLOBALS_AF", "default|ipv4_unicast", bgp_globals_af)


#
# 'bgp address-family ipv4 unicast max-paths ibgp del' command
#
@bgp_addr_ipv4_unicast_max_paths_ibgp.command("del")
@click.argument(
    "paths_num",
    metavar="<paths_num>",
    required=True,
    type=BGP_IPV4_UNICAST_MAX_PATHS_RANGE,
)
@clicommon.pass_db
def max_paths_ibgp_del(db, paths_num):
    """Delete IPv4 unicast ibgp max-paths"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_globals_af = db.cfgdb.get_entry("BGP_GLOBALS_AF", "default|ipv4_unicast")
    max_ibgp_paths = bgp_globals_af.get("max_ibgp_paths")
    if max_ibgp_paths:
        if max_ibgp_paths != str(paths_num):
            ctx.fail("Configured max-paths ibgp number is {}".format(max_ibgp_paths))
    else:
        ctx.fail("Max-paths ibgp number is not configured")

    del bgp_globals_af["max_ibgp_paths"]
    if bgp_globals_af.get("ibgp_equal_cluster_length"):
        del bgp_globals_af["ibgp_equal_cluster_length"]
    db.cfgdb.set_entry("BGP_GLOBALS_AF", "default|ipv4_unicast", bgp_globals_af)


#
# 'bgp address-family ipv4 unicast distance' group
#
@bgp_addr_ipv4_unicast.group(cls=clicommon.AbbreviationGroup, name="distance")
def bgp_addr_ipv4_unicast_dist():
    """Define an administrative distance"""
    pass


#
# 'bgp address-family ipv4 unicast distance bgp' group
#
@bgp_addr_ipv4_unicast_dist.group(cls=clicommon.AbbreviationGroup, name="bgp")
def bgp_addr_ipv4_unicast_dist_bgp():
    """BGP distance"""
    pass


#
# 'bgp address-family ipv4 unicast distance bgp add' command
#
@bgp_addr_ipv4_unicast_dist_bgp.command("add")
@click.argument(
    "ebgp_dist",
    metavar="<ebgp_dist>",
    required=True,
    type=BGP_IPV4_UNICAST_DISTANCE_RANGE,
)
@click.argument(
    "ibgp_dist",
    metavar="<ibgp_dist>",
    required=True,
    type=BGP_IPV4_UNICAST_DISTANCE_RANGE,
)
@click.argument(
    "local_dist",
    metavar="<local_dist>",
    required=True,
    type=BGP_IPV4_UNICAST_DISTANCE_RANGE,
)
@clicommon.pass_db
def distance_bgp_add(db, ebgp_dist, ibgp_dist, local_dist):
    """Add BGP distance"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_globals_af = db.cfgdb.get_entry("BGP_GLOBALS_AF", "default|ipv4_unicast")
    if (
        bgp_globals_af.get("ebgp_route_distance")
        and bgp_globals_af.get("ibgp_route_distance")
        and bgp_globals_af.get("local_route_distance")
    ):
        ctx.fail("BGP distance values are already configured")

    db.cfgdb.mod_entry(
        "BGP_GLOBALS_AF",
        "default|ipv4_unicast",
        {
            "ebgp_route_distance": ebgp_dist,
            "ibgp_route_distance": ibgp_dist,
            "local_route_distance": local_dist,
        },
    )


#
# 'bgp address-family ipv4 unicast distance bgp set' command
#
@bgp_addr_ipv4_unicast_dist_bgp.command("set")
@click.argument(
    "ebgp_dist",
    metavar="<ebgp_dist>",
    required=True,
    type=BGP_IPV4_UNICAST_DISTANCE_RANGE,
)
@click.argument(
    "ibgp_dist",
    metavar="<ibgp_dist>",
    required=True,
    type=BGP_IPV4_UNICAST_DISTANCE_RANGE,
)
@click.argument(
    "local_dist",
    metavar="<local_dist>",
    required=True,
    type=BGP_IPV4_UNICAST_DISTANCE_RANGE,
)
@clicommon.pass_db
def distance_bgp_set(db, ebgp_dist, ibgp_dist, local_dist):
    """Set BGP distance"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_globals_af = db.cfgdb.get_entry("BGP_GLOBALS_AF", "default|ipv4_unicast")
    if (
        not bgp_globals_af.get("ebgp_route_distance")
        or not bgp_globals_af.get("ibgp_route_distance")
        or not bgp_globals_af.get("local_route_distance")
    ):
        ctx.fail("Distance bgp values are not configured")

    db.cfgdb.mod_entry(
        "BGP_GLOBALS_AF",
        "default|ipv4_unicast",
        {
            "ebgp_route_distance": ebgp_dist,
            "ibgp_route_distance": ibgp_dist,
            "local_route_distance": local_dist,
        },
    )


#
# 'bgp address-family ipv4 unicast distance bgp del' command
#
@bgp_addr_ipv4_unicast_dist_bgp.command("del")
@click.argument(
    "ebgp_dist",
    metavar="<ebgp_dist>",
    required=True,
    type=BGP_IPV4_UNICAST_DISTANCE_RANGE,
)
@click.argument(
    "ibgp_dist",
    metavar="<ibgp_dist>",
    required=True,
    type=BGP_IPV4_UNICAST_DISTANCE_RANGE,
)
@click.argument(
    "local_dist",
    metavar="<local_dist>",
    required=True,
    type=BGP_IPV4_UNICAST_DISTANCE_RANGE,
)
@clicommon.pass_db
def distance_bgp_del(db, ebgp_dist, ibgp_dist, local_dist):
    """Delete BGP distance"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_globals_af = db.cfgdb.get_entry("BGP_GLOBALS_AF", "default|ipv4_unicast")
    ebgp_rt_dist = bgp_globals_af.get("ebgp_route_distance")
    ibgp_rt_dist = bgp_globals_af.get("ibgp_route_distance")
    local_rt_dist = bgp_globals_af.get("local_route_distance")

    if ebgp_rt_dist and ibgp_rt_dist and local_rt_dist:
        if (
            ebgp_rt_dist != str(ebgp_dist)
            or ibgp_rt_dist != str(ibgp_dist)
            or local_rt_dist != str(local_dist)
        ):
            ctx.fail(
                "Configured distance bgp values are {} {} {}".format(
                    ebgp_rt_dist, ibgp_rt_dist, local_rt_dist
                )
            )
    else:
        ctx.fail("Distance bgp values are not configured")

    if bgp_globals_af.get("ebgp_route_distance"):
        del bgp_globals_af["ebgp_route_distance"]
    if bgp_globals_af.get("ibgp_route_distance"):
        del bgp_globals_af["ibgp_route_distance"]
    if bgp_globals_af.get("local_route_distance"):
        del bgp_globals_af["local_route_distance"]
    db.cfgdb.set_entry("BGP_GLOBALS_AF", "default|ipv4_unicast", bgp_globals_af)


#
# 'bgp address-family ipv4 redistribute' group
#
@bgp_addr_ipv4_unicast.group(cls=clicommon.AbbreviationGroup, name="redistribute")
def bgp_addr_ipv4_unicast_redist():
    """Redistribute information from another routing protocol"""
    pass


#
# 'bgp address-family ipv4 redistribute connected' command
#
@bgp_addr_ipv4_unicast_redist.command("connected")
@click.argument(
    "mode", metavar="<mode>", required=True, type=click.Choice(["on", "off"])
)
@clicommon.pass_db
def redist_connected(db, mode):
    """Connected routes (directly attached subnet or host)"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    db.cfgdb.set_entry(
        "ROUTE_REDISTRIBUTE", "default|connected|bgp|ipv4", {} if mode == "on" else None
    )


#
# 'bgp address-family l2vpn' group
#
@bgp_addr.group(cls=clicommon.AbbreviationGroup, name="l2vpn")
def bgp_addr_l2vpn():
    """L2VPN address family configuration"""
    pass


#
# 'bgp address-family l2vpn evpn' group
#
@bgp_addr_l2vpn.group(cls=clicommon.AbbreviationGroup, name="evpn")
def bgp_addr_l2vpn_evpn():
    """L2VPN EVPN address family configuration"""
    pass


#
# 'bgp address-family l2vpn evpn advertise-all-vni' command
#
@bgp_addr_l2vpn_evpn.command("advertise-all-vni")
@click.argument(
    "mode", metavar="<mode>", required=True, type=click.Choice(["on", "off"])
)
@clicommon.pass_db
def advertise_all_vni(db, mode):
    """Advertise all local VNIs"""
    ctx = click.get_current_context()

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    db.cfgdb.mod_entry(
        "BGP_GLOBALS_AF",
        "default|l2vpn_evpn",
        {"advertise-all-vni": "true" if mode == "on" else "false"},
    )


#
# 'bgp address-family l2vpn evpn neighbor' group
#
@bgp_addr_l2vpn_evpn.group(cls=clicommon.AbbreviationGroup, name="neighbor")
def bgp_addr_l2vpn_evpn_neighbor():
    """L2VPN EVPN neighbor address family configuration"""
    pass


#
# 'bgp address-family l2vpn evpn neighbor activate' command
#
@bgp_addr_l2vpn_evpn_neighbor.command("activate")
@click.argument("ip_intf", metavar="<ip_addr|interface_name>", required=True)
@click.argument(
    "mode", metavar="<mode>", required=True, type=click.Choice(["on", "off"])
)
@clicommon.pass_db
def evpn_neighbor_activate(db, ip_intf, mode):
    """L2VPN EVPN neighbor activate"""
    ctx = click.get_current_context()

    if not get_interface_table_name(ip_intf):
        try:
            ipaddress.ip_address(ip_intf)
        except ValueError:
            ctx.fail("Neighbor interface/IP address is not valid")

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_neighbor = db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", ip_intf))
    if not bgp_neighbor.get("asn"):
        ctx.fail("Specify BGP neighbor remote-as first")

    db.cfgdb.mod_entry(
        "BGP_NEIGHBOR_AF",
        ("default", ip_intf, "l2vpn_evpn"),
        {"admin_status": "true" if mode == "on" else "false"},
    )


#
# 'bgp address-family l2vpn evpn neighbor route-reflector-client' command
#
@bgp_addr_l2vpn_evpn_neighbor.command("route-reflector-client")
@click.argument("ip_intf", metavar="<ip_addr|interface_name>", required=True)
@click.argument(
    "mode", metavar="<mode>", required=True, type=click.Choice(["on", "off"])
)
@clicommon.pass_db
def evpn_neighbor_rrc(db, ip_intf, mode):
    """L2VPN EVPN neighbor route-reflector-client"""
    ctx = click.get_current_context()

    if not get_interface_table_name(ip_intf):
        try:
            ipaddress.ip_address(ip_intf)
        except ValueError:
            ctx.fail("Neighbor interface/IP address is not valid")

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_neighbor = db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", ip_intf))
    if not bgp_neighbor.get("asn"):
        ctx.fail("Specify BGP neighbor remote-as first")

    if (
        bgp_neighbor.get("asn") == bgp_globals.get("local_asn")
        or bgp_neighbor.get("asn") == "internal"
    ):
        db.cfgdb.mod_entry(
            "BGP_NEIGHBOR_AF",
            ("default", ip_intf, "l2vpn_evpn"),
            {"rrclient": "true" if mode == "on" else "false"},
        )
    else:
        ctx.fail("Invalid command. Not an internal neighbor")


#
# 'bgp address-family l2vpn evpn neighbor soft-reconf' group
#
@bgp_addr_l2vpn_evpn_neighbor.group(cls=clicommon.AbbreviationGroup, name="soft-reconf")
def bgp_addr_l2vpn_evpn_neighbor_soft_reconf():
    """L2VPN EVPN neighbor soft reconfiguration"""
    pass


#
# 'bgp address-family l2vpn evpn neighbor soft-reconf inbound' command
#
@bgp_addr_l2vpn_evpn_neighbor_soft_reconf.command("inbound")
@click.argument("ip_intf", metavar="<ip_addr|interface_name>", required=True)
@click.argument(
    "mode", metavar="<mode>", required=True, type=click.Choice(["on", "off"])
)
@clicommon.pass_db
def evpn_neighbor_reconf_inbound(db, ip_intf, mode):
    """Allow neighbor inbound soft reconfiguration"""
    ctx = click.get_current_context()

    if not get_interface_table_name(ip_intf):
        try:
            ipaddress.ip_address(ip_intf)
        except ValueError:
            ctx.fail("Neighbor interface/IP address is not valid")

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_neighbor = db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", ip_intf))
    if not bgp_neighbor.get("asn"):
        ctx.fail("Specify BGP neighbor remote-as first")

    db.cfgdb.mod_entry(
        "BGP_NEIGHBOR_AF",
        ("default", ip_intf, "l2vpn_evpn"),
        {"soft_reconfiguration_in": "true" if mode == "on" else "false"},
    )


#
# 'bgp address-family l2vpn evpn neighbor allowas-in' command
#
@bgp_addr_l2vpn_evpn_neighbor.command("allowas-in")
@click.argument("ip_intf", metavar="<ip_addr|interface_name>", required=True)
@click.argument(
    "mode", metavar="<mode>", required=True, type=click.Choice(["on", "off"])
)
@click.option("--allowas", metavar="<1-10|origin>", required=False)
@clicommon.pass_db
def evpn_neighbor_allowas_in(db, ip_intf, mode, allowas):
    """Accept as-path with my AS present in it"""
    ctx = click.get_current_context()

    if not get_interface_table_name(ip_intf):
        try:
            ipaddress.ip_address(ip_intf)
        except ValueError:
            ctx.fail("Neighbor interface/IP address is not valid")

    if allowas:
        if allowas != "origin":
            try:
                if int(allowas) not in range(
                    BGP_NEIGHBOR_ALLOWAS_MIN, BGP_NEIGHBOR_ALLOWAS_MAX
                ):
                    raise ValueError
            except ValueError:
                ctx.fail("'--allowas' argument is not valid")

    bgp_globals = db.cfgdb.get_entry("BGP_GLOBALS", "default")
    if not bgp_globals.get("local_asn"):
        ctx.fail("AS number is not specified")

    bgp_neighbor = db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", ip_intf))
    if not bgp_neighbor.get("asn"):
        ctx.fail("Specify BGP neighbor remote-as first")

    bgp_neighbor_af = db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", ip_intf))
    bgp_neighbor_af["allow_as_in"] = "true" if mode == "on" else "false"
    if allowas:
        if allowas == "origin":
            bgp_neighbor_af["allow_as_origin"] = "true"
        else:
            bgp_neighbor_af["allow_as_count"] = allowas
    db.cfgdb.mod_entry(
        "BGP_NEIGHBOR_AF", ("default", ip_intf, "l2vpn_evpn"), bgp_neighbor_af
    )

import click
from natsort import natsorted
from tabulate import tabulate
from sonic_py_common import multi_asic
import utilities_common.multi_asic as multi_asic_util
import utilities_common.cli as clicommon


@click.group(cls=clicommon.AliasedGroup)
def vlan():
    """Show VLAN information"""
    pass


# Attribute name used to stash per-invocation indexes on the ``db``
# object so all built-in column getters (and the plugin-extension
# callers that share the same ``ctx``) can reuse them. ``brief()`` is
# responsible for clearing this attribute before and after each render
# so stale data from a previous invocation can never be observed when
# the same ``Db`` instance is shared (e.g. by CliRunner-based tests or
# by tools that invoke the command multiple times after mutating
# VLAN_MEMBER / VLAN_INTERFACE / SONIC_CLI_IFACE_MODE).
_BRIEF_CACHE_ATTR = '_vlan_brief_cache'


def _get_brief_cache(ctx):
    """Build (lazily, once per ``brief`` invocation) and return indexes
    used by the built-in "show vlan brief" column getters.

    Without this cache each getter rescans VLAN_INTERFACE / VLAN_MEMBER
    for every VLAN, and ``get_vlan_ports`` re-constructs an
    ``InterfaceAliasConverter`` (which reloads the PORT table) per VLAN.
    With ~800 VLANs that becomes O(V^2) plus 800 PORT-table reads.

    The cache is stashed on the ``db`` object purely as a convenient
    place that every getter can reach via ``ctx``. ``brief()`` clears
    the attribute before populating ``vlan_cfg`` and again after the
    render completes, so the lifetime of the cache is exactly one
    invocation -- it never carries indexes from an earlier ``brief()``
    call into a later one, even when callers share the same ``Db``.

    As a second line of defence (for external callers that invoke the
    getters directly on a reused ``Db`` without going through
    ``brief()``), the cache records the identity of the ``vlan_ip_data``
    and ``vlan_ports_data`` objects it was built from and is rebuilt
    automatically when a different ``vlan_cfg`` is observed. The source
    objects are kept referenced (rather than comparing raw ``id()``
    values) so their identity can never be recycled by a freed object.
    """
    cfg, db = ctx
    _, vlan_ip_data, vlan_ports_data = cfg

    cache = getattr(db, _BRIEF_CACHE_ATTR, None)
    if cache is not None and \
            cache['_source'][0] is vlan_ip_data and \
            cache['_source'][1] is vlan_ports_data:
        return cache

    # Index VLAN_INTERFACE once: (vlan, prefix) entries provide IP
    # addresses; (vlan,) entries carry per-VLAN attributes like
    # proxy_arp.
    ip_by_vlan = {}
    proxy_arp_by_vlan = {}
    for key, value in vlan_ip_data.items():
        if clicommon.is_ip_prefix_in_key(key):
            ifname, address = key
            ip_by_vlan.setdefault(ifname, []).append(address)
        else:
            proxy_arp_by_vlan[key] = value.get('proxy_arp', 'disabled')

    # Index VLAN_MEMBER once, in natsorted port order. Both the Ports
    # column and the Port Tagging column iterate in this single order so
    # the two columns line up row-for-row.
    ports_by_vlan = {}
    tagging_by_vlan = {}
    for key in natsorted(list(vlan_ports_data.keys())):
        vlan_key, port = key
        ports_by_vlan.setdefault(vlan_key, []).append(port)
        tagging_by_vlan.setdefault(vlan_key, []).append(
            vlan_ports_data[key].get('tagging_mode', ''))

    naming_mode = clicommon.get_interface_naming_mode()
    # Only build the alias converter (which reads the PORT table) when
    # we will actually use it.
    iface_alias_converter = (clicommon.InterfaceAliasConverter(db)
                             if naming_mode == 'alias' else None)

    cache = {
        # Identity guard: the exact (vlan_ip_data, vlan_ports_data)
        # objects this cache was built from. Retrieval compares against
        # these with ``is`` (an O(1) identity check) and rebuilds on any
        # mismatch, so a reused ``Db`` can never expose indexes from
        # stale config. Keeping the references here also prevents their
        # identity from being recycled by a later, freed object.
        '_source': (vlan_ip_data, vlan_ports_data),
        'ip_by_vlan': ip_by_vlan,
        'proxy_arp_by_vlan': proxy_arp_by_vlan,
        'ports_by_vlan': ports_by_vlan,
        'tagging_by_vlan': tagging_by_vlan,
        'naming_mode': naming_mode,
        'iface_alias_converter': iface_alias_converter,
    }
    setattr(db, _BRIEF_CACHE_ATTR, cache)
    return cache


def _clear_brief_cache(db):
    """Drop any per-invocation index cache attached to ``db``.

    Called by ``brief()`` to scope the cache to a single render.
    """
    try:
        delattr(db, _BRIEF_CACHE_ATTR)
    except AttributeError:
        pass


def get_vlan_id(ctx, vlan):
    vlan_prefix, vid = vlan.split('Vlan')
    return vid


def get_vlan_ip_address(ctx, vlan):
    cache = _get_brief_cache(ctx)
    addrs = cache['ip_by_vlan'].get(vlan)
    if not addrs:
        return ""
    # Preserve the original formatting (leading newline before the first
    # address) so existing output / tests are unchanged.
    return "".join("\n{}".format(a) for a in addrs)


def get_vlan_ports(ctx, vlan):
    cache = _get_brief_cache(ctx)
    ports = cache['ports_by_vlan'].get(vlan)
    if not ports:
        return ''

    if cache['naming_mode'] == "alias":
        iface_alias_converter = cache['iface_alias_converter']
        ports = [iface_alias_converter.name_to_alias(p) for p in ports]

    return '\n'.join(ports)


def get_vlan_ports_tagging(ctx, vlan):
    cache = _get_brief_cache(ctx)
    tagging = cache['tagging_by_vlan'].get(vlan)
    if not tagging:
        return ''
    return '\n'.join(tagging)


def get_proxy_arp(ctx, vlan):
    cache = _get_brief_cache(ctx)
    return cache['proxy_arp_by_vlan'].get(vlan, "disabled")


def get_static_anycast_gateway(ctx, vlan):
    cfg, _ = ctx
    _, vlan_ip_data, _ = cfg

    if vlan in vlan_ip_data:
        if vlan_ip_data[vlan].get("static_anycast_gateway") == "true":
            return "enabled"

    return "disabled"

class VlanBrief:
    """ This class is used as a namespace to
    define columns for "show vlan brief" command.
    The usage of this class is for external plugin
    (in this case dhcp-relay) to append new columns
    to this list.
    """

    COLUMNS = [
        ("VLAN ID", get_vlan_id),
        ("IP Address", get_vlan_ip_address),
        ("Ports", get_vlan_ports),
        ("Port Tagging", get_vlan_ports_tagging),
        ("Proxy ARP", get_proxy_arp),
        ("Static Anycast Gateway", get_static_anycast_gateway)
    ]

    @classmethod
    def register_column(cls, column_name, callback):
        """ Adds a new column to "vlan brief" output.
        Expected to be used from plugins code to extend
        this command with  additional VLAN fields. """

        cls.COLUMNS.append((column_name, callback))


@vlan.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@multi_asic_util.multi_asic_click_option_namespace
def brief(verbose, namespace):
    def _brief_helper(db):
        """Show all bridge information"""
        header = [colname for colname, getter in VlanBrief.COLUMNS]
        body = []

        # Fetching data from config db for VLAN, VLAN_INTERFACE and VLAN_MEMBER
        vlan_data = db.cfgdb.get_table('VLAN')
        vlan_ip_data = db.cfgdb.get_table('VLAN_INTERFACE')
        vlan_ports_data = db.cfgdb.get_table('VLAN_MEMBER')
        vlan_cfg = (vlan_data, vlan_ip_data, vlan_ports_data)

        # Force the per-invocation index cache to be rebuilt from the
        # freshly fetched ``vlan_cfg`` above, and make sure nothing leaks
        # out of this call. Without this, a caller that reuses the same
        # ``Db`` across multiple ``brief`` invocations (CliRunner-based
        # tests, dump tools, etc.) could see indexes built from VLAN data
        # that was current at the time of the first call.
        _clear_brief_cache(db)
        try:
            for vlan in natsorted(vlan_data):
                row = []
                for column in VlanBrief.COLUMNS:
                    column_name, getter = column
                    row.append(getter((vlan_cfg, db), vlan))
                body.append(row)
        finally:
            _clear_brief_cache(db)

        click.echo(tabulate(body, header, tablefmt="grid"))

    if multi_asic.is_multi_asic():
        ns_list = multi_asic.get_namespace_list()
        if namespace:
            ns_list = [namespace]
    else:
        ns_list = [multi_asic.DEFAULT_NAMESPACE]

    for ns in ns_list:
        if multi_asic.is_multi_asic() and len(ns_list) > 1:
            click.echo("\nNamespace: {}".format(ns))

        config_db = multi_asic.connect_config_db_for_ns(ns)
        ns_db = multi_asic.connect_to_all_dbs_for_ns(ns)

        # Create a db-like object for compatibility with getter functions
        class ConfigDbWrapper:
            def __init__(self, cfgdb, ns_db):
                self.cfgdb = cfgdb
                self.db = ns_db

        db = ConfigDbWrapper(config_db, ns_db)
        _brief_helper(db)


@vlan.command()
@multi_asic_util.multi_asic_click_option_namespace
def config(namespace):
    def _config_helper(db):
        data = db.cfgdb.get_table('VLAN')
        keys = list(data.keys())
        member_data = db.cfgdb.get_table('VLAN_MEMBER')
        interface_naming_mode = clicommon.get_interface_naming_mode()
        iface_alias_converter = clicommon.InterfaceAliasConverter(db)

        def get_iface_name_for_display(member):
            if interface_naming_mode == "alias":
                return iface_alias_converter.name_to_alias(member)
            return member

        def get_tagging_mode(vlan, member):
            if not member:
                return ''
            key = (vlan, member)
            if key in member_data:
                return member_data[key].get('tagging_mode', '')
            return ''

        def tablelize(keys, data):
            table = []

            for k in natsorted(keys):
                members = set([(vlan, member) for vlan, member in member_data if vlan == k] +
                              [(k, member) for member in set(data[k].get('members', []))])
                # vlan with no members
                if not members:
                    members = [(k, '')]

                for vlan, member in natsorted(members):
                    r = [vlan, data[vlan]['vlanid'], get_iface_name_for_display(member), get_tagging_mode(vlan, member)]
                    table.append(r)

            return table

        header = ['Name', 'VID', 'Member', 'Mode']
        click.echo(tabulate(tablelize(keys, data), header))

    if multi_asic.is_multi_asic():
        ns_list = multi_asic.get_namespace_list()
        if namespace:
            ns_list = [namespace]
    else:
        ns_list = [multi_asic.DEFAULT_NAMESPACE]

    for ns in ns_list:
        if multi_asic.is_multi_asic() and len(ns_list) > 1:
            click.echo("\nNamespace: {}".format(ns))

        config_db = multi_asic.connect_config_db_for_ns(ns)
        ns_db = multi_asic.connect_to_all_dbs_for_ns(ns)

        # Create a db-like object for compatibility with helper function
        class ConfigDbWrapper:
            def __init__(self, cfgdb, ns_db):
                self.cfgdb = cfgdb
                self.db = ns_db

        db = ConfigDbWrapper(config_db, ns_db)
        _config_helper(db)


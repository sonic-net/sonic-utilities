import click
import utilities_common.cli as clicommon

from .validated_config_db_connector import ValidatedConfigDBConnector

PTP_TABLE = "PTP"
PTP_PORT_TABLE = "PTP_PORT"
PTP_UNICAST_MASTER_TABLE = "PTP_UNICAST_MASTER_TABLE"
PTP_UNICAST_MASTER_TABLE_IP = "PTP_UNICAST_MASTER_TABLE_IP"

ADHOC_VALIDATION = True


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------

@click.group(cls=clicommon.AbbreviationGroup, name='ptp')
def ptp():
    """PTP (IEEE 1588) configuration"""
    pass


# ---------------------------------------------------------------------------
# config ptp domain-number <0-127>
# ---------------------------------------------------------------------------

@ptp.command('domain-number')
@click.argument('domain', metavar='<domain>', type=click.IntRange(0, 127))
@clicommon.pass_db
def domain_number(db, domain):
    """Set PTP domain number (0-127)"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    config_db.mod_entry(PTP_TABLE, 'global', {'domain_number': domain})
    click.echo(f"PTP domain number set to {domain}")


# ---------------------------------------------------------------------------
# config ptp sync-interval <-7..7>
# ---------------------------------------------------------------------------

@ptp.command('sync-interval')
@click.argument('interval', metavar='<interval>', type=click.IntRange(-7, 7))
@clicommon.pass_db
def sync_interval(db, interval):
    """Set PTP sync interval as log2 of seconds (-7..7)"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    config_db.mod_entry(PTP_TABLE, 'global', {'sync_interval': interval})
    click.echo(f"PTP sync interval set to {interval}")


# ---------------------------------------------------------------------------
# config ptp announce-interval <-3..4>
# ---------------------------------------------------------------------------

@ptp.command('announce-interval')
@click.argument('interval', metavar='<interval>', type=click.IntRange(-3, 4))
@clicommon.pass_db
def announce_interval(db, interval):
    """Set PTP announce interval as log2 of seconds (-3..4)"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    config_db.mod_entry(PTP_TABLE, 'global', {'announce_interval': interval})
    click.echo(f"PTP announce interval set to {interval}")


# ---------------------------------------------------------------------------
# config ptp unicast-master-table
# ---------------------------------------------------------------------------

@ptp.group(cls=clicommon.AbbreviationGroup, name='unicast-master-table')
def unicast_master_table():
    """PTP unicast master table configuration"""
    pass


@unicast_master_table.command('add')
@click.argument('table_id', metavar='<id>', type=click.INT)
@clicommon.pass_db
def unicast_master_table_add(db, table_id):
    """Add a PTP unicast master table entry"""
    ctx = click.get_current_context()

    if ADHOC_VALIDATION:
        if table_id < 0:
            ctx.fail(f"Table ID {table_id} is invalid: must be a non-negative integer")

    config_db = ValidatedConfigDBConnector(db.cfgdb)

    if ADHOC_VALIDATION:
        existing_keys = config_db.get_keys(PTP_UNICAST_MASTER_TABLE)
        if str(table_id) in [str(k) for k in existing_keys]:
            ctx.fail(f"PTP unicast master table {table_id} already exists")

    config_db.set_entry(PTP_UNICAST_MASTER_TABLE, str(table_id), {'NULL': 'NULL'})
    click.echo(f"PTP unicast master table {table_id} added")


@unicast_master_table.command('remove')
@click.argument('table_id', metavar='<id>', type=click.INT)
@clicommon.pass_db
def unicast_master_table_remove(db, table_id):
    """Remove a PTP unicast master table entry"""
    ctx = click.get_current_context()
    config_db = ValidatedConfigDBConnector(db.cfgdb)

    if ADHOC_VALIDATION:
        existing_keys = config_db.get_keys(PTP_UNICAST_MASTER_TABLE)
        if str(table_id) not in [str(k) for k in existing_keys]:
            ctx.fail(f"PTP unicast master table {table_id} does not exist")

    # Remove all IP entries that belong to this table first
    ip_entries = config_db.get_keys(PTP_UNICAST_MASTER_TABLE_IP)
    for key in ip_entries:
        # keys are stored as tuples (table_id, ip_address) by ConfigDB
        entry_id = key[0] if isinstance(key, tuple) else key.split('|')[0]
        if str(entry_id) == str(table_id):
            config_db.set_entry(PTP_UNICAST_MASTER_TABLE_IP, key, None)

    config_db.set_entry(PTP_UNICAST_MASTER_TABLE, str(table_id), None)
    click.echo(f"PTP unicast master table {table_id} removed")


# ---------------------------------------------------------------------------
# config ptp unicast-master-table ip
# ---------------------------------------------------------------------------

@unicast_master_table.group(cls=clicommon.AbbreviationGroup, name='ip')
def unicast_master_table_ip():
    """PTP unicast master IP address configuration"""
    pass


@unicast_master_table_ip.command('add')
@click.argument('table_id', metavar='<id>', type=click.INT)
@click.argument('ip_address', metavar='<ip_address>')
@clicommon.pass_db
def unicast_master_table_ip_add(db, table_id, ip_address):
    """Add an IP address to a PTP unicast master table"""
    ctx = click.get_current_context()

    if ADHOC_VALIDATION:
        if not clicommon.is_ipaddress(ip_address):
            ctx.fail(f"'{ip_address}' is not a valid IPv4 or IPv6 address")

    config_db = ValidatedConfigDBConnector(db.cfgdb)

    if ADHOC_VALIDATION:
        parent_keys = config_db.get_keys(PTP_UNICAST_MASTER_TABLE)
        if str(table_id) not in [str(k) for k in parent_keys]:
            ctx.fail(f"PTP unicast master table {table_id} does not exist")

    key = (str(table_id), ip_address)
    if ADHOC_VALIDATION:
        ip_keys = config_db.get_keys(PTP_UNICAST_MASTER_TABLE_IP)
        if key in ip_keys or (str(table_id), ip_address) in [(str(k[0]), k[1]) for k in ip_keys if isinstance(k, tuple)]:
            ctx.fail(f"IP {ip_address} already exists in PTP unicast master table {table_id}")

    config_db.set_entry(PTP_UNICAST_MASTER_TABLE_IP, key, {'NULL': 'NULL'})
    click.echo(f"IP {ip_address} added to PTP unicast master table {table_id}")


@unicast_master_table_ip.command('remove')
@click.argument('table_id', metavar='<id>', type=click.INT)
@click.argument('ip_address', metavar='<ip_address>')
@clicommon.pass_db
def unicast_master_table_ip_remove(db, table_id, ip_address):
    """Remove an IP address from a PTP unicast master table"""
    ctx = click.get_current_context()

    if ADHOC_VALIDATION:
        if not clicommon.is_ipaddress(ip_address):
            ctx.fail(f"'{ip_address}' is not a valid IPv4 or IPv6 address")

    config_db = ValidatedConfigDBConnector(db.cfgdb)
    key = (str(table_id), ip_address)

    if ADHOC_VALIDATION:
        ip_keys = config_db.get_keys(PTP_UNICAST_MASTER_TABLE_IP)
        if key not in ip_keys and (str(table_id), ip_address) not in [(str(k[0]), k[1]) for k in ip_keys if isinstance(k, tuple)]:
            ctx.fail(f"IP {ip_address} does not exist in PTP unicast master table {table_id}")

    config_db.set_entry(PTP_UNICAST_MASTER_TABLE_IP, key, None)
    click.echo(f"IP {ip_address} removed from PTP unicast master table {table_id}")


# ---------------------------------------------------------------------------
# config ptp interface
# ---------------------------------------------------------------------------

@ptp.group(cls=clicommon.AbbreviationGroup, name='interface')
def interface():
    """PTP interface (port) configuration"""
    pass


@interface.command('add')
@click.argument('interface_name', metavar='<interface_name>')
@click.argument('table_id', metavar='<id>', type=click.INT, required=False, default=None)
@click.option('--unicast-listen', is_flag=True, default=False,
              help='Accept unicast Delay_Req messages on this interface')
@clicommon.pass_db
def interface_add(db, interface_name, table_id, unicast_listen):
    """Add a PTP port entry for an interface"""
    ctx = click.get_current_context()
    config_db = ValidatedConfigDBConnector(db.cfgdb)

    if ADHOC_VALIDATION:
        if not clicommon.is_valid_port(config_db, interface_name):
            ctx.fail(f"Interface '{interface_name}' does not exist in the PORT table")

        if table_id is not None:
            umt_keys = config_db.get_keys(PTP_UNICAST_MASTER_TABLE)
            if str(table_id) not in [str(k) for k in umt_keys]:
                ctx.fail(f"PTP unicast master table {table_id} does not exist")

    if ADHOC_VALIDATION:
        port_keys = config_db.get_keys(PTP_PORT_TABLE)
        if interface_name in port_keys:
            ctx.fail(f"PTP port entry for '{interface_name}' already exists; use 'config ptp interface remove' first")

    fvs = {'unicast_listen': 'true' if unicast_listen else 'false'}
    if table_id is not None:
        fvs['unicast_table'] = str(table_id)

    config_db.set_entry(PTP_PORT_TABLE, interface_name, fvs)
    config_db.mod_entry('PORT', interface_name, {'ptp_mode': 'one-step'})
    click.echo(f"PTP port entry added for interface '{interface_name}'")


@interface.command('remove')
@click.argument('interface_name', metavar='<interface_name>')
@clicommon.pass_db
def interface_remove(db, interface_name):
    """Remove the PTP port entry for an interface"""
    ctx = click.get_current_context()
    config_db = ValidatedConfigDBConnector(db.cfgdb)

    if ADHOC_VALIDATION:
        port_keys = config_db.get_keys(PTP_PORT_TABLE)
        if interface_name not in port_keys:
            ctx.fail(f"PTP port entry for '{interface_name}' does not exist")

    config_db.set_entry(PTP_PORT_TABLE, interface_name, None)
    config_db.mod_entry('PORT', interface_name, {'ptp_mode': 'none'})
    click.echo(f"PTP port entry removed for interface '{interface_name}'")

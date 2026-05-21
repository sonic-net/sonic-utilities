import re
import click
import ipaddress
import utilities_common.cli as clicommon

from sonic_py_common import logger
from utilities_common.bgp import (
    CFG_BGP_DEVICE_GLOBAL,
    BGP_DEVICE_GLOBAL_KEY,
    CFG_BGP_AGGREGATE_ADDRESS,
    SYSLOG_IDENTIFIER,
    to_str,
)


log = logger.Logger(SYSLOG_IDENTIFIER)
log.set_min_log_priority_info()


#
# BGP DB interface ----------------------------------------------------------------------------------------------------
#


def update_entry_validated(db, table, key, data, create_if_not_exists=False):
    """ Update entry in table and validate configuration.
    If attribute value in data is None, the attribute is deleted.

    Args:
        db (swsscommon.ConfigDBConnector): Config DB connector object.
        table (str): Table name to add new entry to.
        key (Union[str, Tuple]): Key name in the table.
        data (Dict): Entry data.
        create_if_not_exists (bool):
            In case entry does not exists already a new entry
            is not created if this flag is set to False and
            creates a new entry if flag is set to True.
    Raises:
        Exception: when cfg does not satisfy YANG schema.
    """

    cfg = db.get_config()
    cfg.setdefault(table, {})

    if not data:
        raise click.ClickException(f"No field/values to update {key}")

    if create_if_not_exists:
        cfg[table].setdefault(key, {})

    if key not in cfg[table]:
        raise click.ClickException(f"{key} does not exist")

    entry_changed = False
    for attr, value in data.items():
        if value == cfg[table][key].get(attr):
            continue
        entry_changed = True
        if value is None:
            cfg[table][key].pop(attr, None)
        else:
            cfg[table][key][attr] = value

    if not entry_changed:
        return

    db.set_entry(table, key, cfg[table][key])


#
# BGP handlers --------------------------------------------------------------------------------------------------------
#


def tsa_handler(ctx, db, state):
    """ Handle config updates for Traffic-Shift-Away (TSA) feature """

    table = CFG_BGP_DEVICE_GLOBAL
    key = BGP_DEVICE_GLOBAL_KEY
    data = {
        "tsa_enabled": state,
    }

    try:
        update_entry_validated(db.cfgdb, table, key, data, create_if_not_exists=True)
        log.log_notice("Configured TSA state: {}".format(to_str(state)))
    except Exception as e:
        log.log_error("Failed to configure TSA state: {}".format(str(e)))
        ctx.fail(str(e))


def wcmp_handler(ctx, db, state):
    """ Handle config updates for Weighted-Cost Multi-Path (W-ECMP) feature """

    table = CFG_BGP_DEVICE_GLOBAL
    key = BGP_DEVICE_GLOBAL_KEY
    data = {
        "wcmp_enabled": state,
    }

    try:
        update_entry_validated(db.cfgdb, table, key, data, create_if_not_exists=True)
        log.log_notice("Configured W-ECMP state: {}".format(to_str(state)))
    except Exception as e:
        log.log_error("Failed to configure W-ECMP state: {}".format(str(e)))
        ctx.fail(str(e))


#
# BGP device-global ---------------------------------------------------------------------------------------------------
#


@click.group(
    name="device-global",
    cls=clicommon.AliasedGroup
)
def DEVICE_GLOBAL():
    """ Configure BGP device global state """

    pass


#
# BGP device-global tsa -----------------------------------------------------------------------------------------------
#


@DEVICE_GLOBAL.group(
    name="tsa",
    cls=clicommon.AliasedGroup
)
def DEVICE_GLOBAL_TSA():
    """ Configure Traffic-Shift-Away (TSA) feature """

    pass


@DEVICE_GLOBAL_TSA.command(
    name="enabled"
)
@clicommon.pass_db
@click.pass_context
def DEVICE_GLOBAL_TSA_ENABLED(ctx, db):
    """ Enable Traffic-Shift-Away (TSA) feature """

    tsa_handler(ctx, db, "true")


@DEVICE_GLOBAL_TSA.command(
    name="disabled"
)
@clicommon.pass_db
@click.pass_context
def DEVICE_GLOBAL_TSA_DISABLED(ctx, db):
    """ Disable Traffic-Shift-Away (TSA) feature """

    tsa_handler(ctx, db, "false")


#
# BGP device-global w-ecmp --------------------------------------------------------------------------------------------
#


@DEVICE_GLOBAL.group(
    name="w-ecmp",
    cls=clicommon.AliasedGroup
)
def DEVICE_GLOBAL_WCMP():
    """ Configure Weighted-Cost Multi-Path (W-ECMP) feature """

    pass


@DEVICE_GLOBAL_WCMP.command(
    name="enabled"
)
@clicommon.pass_db
@click.pass_context
def DEVICE_GLOBAL_WCMP_ENABLED(ctx, db):
    """ Enable Weighted-Cost Multi-Path (W-ECMP) feature """

    wcmp_handler(ctx, db, "true")


@DEVICE_GLOBAL_WCMP.command(
    name="disabled"
)
@clicommon.pass_db
@click.pass_context
def DEVICE_GLOBAL_WCMP_DISABLED(ctx, db):
    """ Disable Weighted-Cost Multi-Path (W-ECMP) feature """

    wcmp_handler(ctx, db, "false")


#
# BGP aggregate-address ------------------------------------------------------------------------------------------------
#


PREFIX_LIST_PATTERN = re.compile(r'^[0-9a-zA-Z_-]*$')
PREFIX_LIST_MAX_LEN = 128


def validate_ip_prefix(ctx, param, value):
    """ Validate that the argument is a valid IP prefix """
    try:
        return str(ipaddress.ip_network(value, strict=False))
    except ValueError:
        raise click.BadParameter("'{}' is not a valid IP prefix".format(value))


def validate_prefix_list_name(name, field_name):
    """ Validate prefix list name against YANG schema constraints.
    Pattern: [0-9a-zA-Z_-]*, max length: 128
    """
    if len(name) > PREFIX_LIST_MAX_LEN:
        raise click.ClickException(
            "'{}' is invalid for {}: length exceeds {}".format(
                name, field_name, PREFIX_LIST_MAX_LEN))
    if not PREFIX_LIST_PATTERN.match(name):
        raise click.ClickException(
            "'{}' is invalid for {}: only alphanumeric characters, "
            "underscores and hyphens are allowed".format(name, field_name))


@click.group(
    name="aggregate-address",
    cls=clicommon.AliasedGroup
)
def AGGREGATE_ADDRESS():
    """ Configure BGP aggregate addresses """

    pass


@AGGREGATE_ADDRESS.command(
    name="add"
)
@click.argument("address", callback=validate_ip_prefix)
@click.option("--bbr-required", is_flag=True, default=False,
              help="Set if BBR is required for generating aggregate address")
@click.option("--summary-only", is_flag=True, default=False,
              help="Only advertise the summary of aggregate address")
@click.option("--as-set", is_flag=True, default=False,
              help="Include the AS set when advertising the aggregated address")
@click.option("--aggregate-address-prefix-list", default="",
              help="Prefix list to append aggregated address to")
@click.option("--contributing-address-prefix-list", default="",
              help="Prefix list to append contributing address filter to")
@clicommon.pass_db
@click.pass_context
def AGGREGATE_ADDRESS_ADD(ctx, db, address, bbr_required, summary_only, as_set,
                          aggregate_address_prefix_list, contributing_address_prefix_list):
    """ Add a BGP aggregate address """

    table = CFG_BGP_AGGREGATE_ADDRESS
    key = address

    # Validate prefix list names against YANG schema
    validate_prefix_list_name(aggregate_address_prefix_list,
                              "aggregate-address-prefix-list")
    validate_prefix_list_name(contributing_address_prefix_list,
                              "contributing-address-prefix-list")

    # Check if entry already exists
    cfg = db.cfgdb.get_config()
    if table in cfg and key in cfg[table]:
        ctx.fail("Aggregate address '{}' already exists".format(key))

    data = {
        "bbr-required": "true" if bbr_required else "false",
        "summary-only": "true" if summary_only else "false",
        "as-set": "true" if as_set else "false",
        "aggregate-address-prefix-list": aggregate_address_prefix_list,
        "contributing-address-prefix-list": contributing_address_prefix_list,
    }

    try:
        db.cfgdb.set_entry(table, key, data)
        log.log_notice("Added BGP aggregate address: {}".format(key))
    except Exception as e:
        log.log_error("Failed to add BGP aggregate address '{}': {}".format(key, str(e)))
        ctx.fail(str(e))


@AGGREGATE_ADDRESS.command(
    name="remove"
)
@click.argument("address", callback=validate_ip_prefix)
@clicommon.pass_db
@click.pass_context
def AGGREGATE_ADDRESS_REMOVE(ctx, db, address):
    """ Remove a BGP aggregate address """

    table = CFG_BGP_AGGREGATE_ADDRESS
    key = address

    # Check if entry exists
    cfg = db.cfgdb.get_config()
    if table not in cfg or key not in cfg[table]:
        ctx.fail("Aggregate address '{}' does not exist".format(key))

    try:
        db.cfgdb.set_entry(table, key, None)
        log.log_notice("Removed BGP aggregate address: {}".format(key))
    except Exception as e:
        log.log_error("Failed to remove BGP aggregate address '{}': {}".format(key, str(e)))
        ctx.fail(str(e))

import click
import utilities_common.cli as clicommon

from sonic_py_common import logger
from utilities_common.bgp import (
    CFG_BGP_DEVICE_GLOBAL,
    BGP_DEVICE_GLOBAL_KEY,
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

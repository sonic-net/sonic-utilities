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
# BGP DB interface -------------------------------------------------------
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
# BGP handlers -----------------------------------------------------------
#


def tsa_handler(ctx, db, state):
    """ Handle config updates for Traffic-Shift-Away (TSA) feature """

    table = CFG_BGP_DEVICE_GLOBAL
    key = BGP_DEVICE_GLOBAL_KEY
    data = {
        "tsa_enabled": state,
    }

    try:
        update_entry_validated(
            db.cfgdb,
            table,
            key,
            data,
            create_if_not_exists=True)
        log.log_notice("Configured TSA state: {}".format(to_str(state)))
    except Exception as e:
        log.log_error("Failed to configure TSA state: {}".format(str(e)))
        ctx.fail(str(e))


def originate_bandwidth_handler(ctx, db, state):
    """ Handle config updates for originate_bandwidth for Weighted-Cost Multi-Path (W-ECMP) feature """

    table = CFG_BGP_DEVICE_GLOBAL
    key = BGP_DEVICE_GLOBAL_KEY
    data = {
        "originate_bandwidth": state,
    }

    try:
        update_entry_validated(
            db.cfgdb,
            table,
            key,
            data,
            create_if_not_exists=True)
        log.log_notice(
            "Configured originate_bandwidth state: {}".format(
                to_str(state)))
    except Exception as e:
        log.log_error(
            "Failed to configure originate_bandwidth state: {}".format(
                str(e)))
        ctx.fail(str(e))


def received_bandwidth_handler(ctx, db, state):

    table = CFG_BGP_DEVICE_GLOBAL
    key = BGP_DEVICE_GLOBAL_KEY
    data = {
        "received_bandwidth": state,
    }

    try:
        update_entry_validated(
            db.cfgdb,
            table,
            key,
            data,
            create_if_not_exists=True)
        log.log_notice(
            "Configured received_bandwidth state: {}".format(
                to_str(state)))
    except Exception as e:
        log.log_error(
            "Failed to configure received_bandwidth state: {}".format(
                str(e)))
        ctx.fail(str(e))


#
# BGP device-global ------------------------------------------------------
#


@click.group(
    name="device-global",
    cls=clicommon.AliasedGroup
)
def DEVICE_GLOBAL():
    """ Configure BGP device global state """

    pass


#
# BGP device-global tsa --------------------------------------------------
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
# BGP device-global w-ecmp ---------------------------
#


@DEVICE_GLOBAL.group(
    name="w-ecmp",
    cls=clicommon.AliasedGroup
)
def DEVICE_GLOBAL_WCMP():
    """Configure Weighted-Cost Multi-Path (W-ECMP) feature"""
    pass

#
# BGP device-global w-ecmp originate-bandwidth ---------------------------
#


@DEVICE_GLOBAL_WCMP.group(
    name="originate-bandwidth",
    cls=clicommon.AliasedGroup
)
def DEVICE_GLOBAL_WCMP_ORIGINATE_BANDWIDTH():
    """Configure Originate Bandwidth via (W-ECMP) feature"""
    pass


@DEVICE_GLOBAL_WCMP_ORIGINATE_BANDWIDTH.command(
    name="cumulative"
)
@clicommon.pass_db
@click.pass_context
def DEVICE_GLOBAL_WCMP_ORIGINATE_BANDWIDTH_CUMULATIVE(ctx, db):
    """Cumulative bandwidth of all multipaths"""
    originate_bandwidth_handler(ctx, db, "cumulative")


@DEVICE_GLOBAL_WCMP_ORIGINATE_BANDWIDTH.command(
    name="num-multipaths"
)
@clicommon.pass_db
@click.pass_context
def DEVICE_GLOBAL_WCMP_ORIGINATE_BANDWIDTH_NUM_MULTIPATHS(ctx, db):
    """Bandwidth based on number of multipaths"""
    originate_bandwidth_handler(ctx, db, "num_multipaths")


@DEVICE_GLOBAL_WCMP_ORIGINATE_BANDWIDTH.command(
    name="disabled"
)
@clicommon.pass_db
@click.pass_context
def DEVICE_GLOBAL_WCMP_ORIGINATE_BANDWIDTH_DISABLED(ctx, db):
    """Disable Weighted-Cost Multi-Path (W-ECMP) feature"""
    originate_bandwidth_handler(ctx, db, "disabled")


@DEVICE_GLOBAL_WCMP_ORIGINATE_BANDWIDTH.command(
    name="set-bandwidth"
)
@clicommon.pass_db
@click.pass_context
@click.argument("bandwidth", required=True, type=str)
def DEVICE_GLOBAL_WCMP_ORIGINATE_BANDWIDTH_SET_BANDWIDTH(ctx, db, bandwidth):
    """(1-25600 Mbps) Set bandwidth for W-ECMP"""
    try:
        bandwidth = int(bandwidth)
    except ValueError:
        raise click.BadParameter('Bandwidth must be an integer.')

    if not (1 <= bandwidth <= 25600):
        raise click.BadParameter('Bandwidth must be between 1 and 25600.')

    originate_bandwidth_handler(ctx, db, str(bandwidth))


#
# BGP device-global w-ecmp received-bandwidth ----------------------------
#


@DEVICE_GLOBAL_WCMP.group(
    name="received-bandwidth",
    cls=clicommon.AliasedGroup
)
def DEVICE_GLOBAL_WCMP_RECEIVED_BANDWIDTH():
    """ Configure Received Bandwidth via (W-ECMP) feature """
    pass


@DEVICE_GLOBAL_WCMP_RECEIVED_BANDWIDTH.command(
    name="ignore"
)
@clicommon.pass_db
@click.pass_context
def DEVICE_GLOBAL_WCMP_RECEIVED_BANDWIDTH_IGNORE(ctx, db):
    """ Ignore link bandwidth (i.e., do regular ECMP, not weighted) """

    received_bandwidth_handler(ctx, db, "ignore")


@DEVICE_GLOBAL_WCMP_RECEIVED_BANDWIDTH.command(
    name="allow"
)
@clicommon.pass_db
@click.pass_context
def DEVICE_GLOBAL_WCMP_RECEIVED_BANDWIDTH_ALLOW(ctx, db):
    """ Allow for normal behavior without bestpath for bandwidth """

    received_bandwidth_handler(ctx, db, "allow")


@DEVICE_GLOBAL_WCMP_RECEIVED_BANDWIDTH.command(
    name="skip-missing"
)
@clicommon.pass_db
@click.pass_context
def DEVICE_GLOBAL_WCMP_RECEIVED_BANDWIDTH_SKIP_MISSING(ctx, db):
    """ Ignore paths without link bandwidth for W-ECMP (if other paths have it) """

    received_bandwidth_handler(ctx, db, "skip_missing")


@DEVICE_GLOBAL_WCMP_RECEIVED_BANDWIDTH.command(
    name="default-weight-for-missing"
)
@clicommon.pass_db
@click.pass_context
def DEVICE_GLOBAL_WCMP_RECEIVED_BANDWIDTH_DEFAULT_WEIGHT(ctx, db):
    """ Assign value 1 to paths not having link bandwidth """

    received_bandwidth_handler(ctx, db, "default_weight_for_missing")

import copy
import click
import utilities_common.cli as clicommon
import utilities_common.general as general
from config import config_mgmt


# Load sonic-cfggen from source since /usr/local/bin/sonic-cfggen does not have .py extension.
sonic_cfggen = general.load_module_from_source('sonic_cfggen', '/usr/local/bin/sonic-cfggen')


def exit_with_error(*args, **kwargs):
    """ Print a message with click.secho and abort CLI.

    Args:
        args: Positional arguments to pass to click.secho
        kwargs: Keyword arguments to pass to click.secho
    """

    click.secho(*args, **kwargs)
    raise click.Abort()


def validate_config_or_raise(cfg):
    """ Validate config db data using ConfigMgmt.

    Args:
        cfg (Dict): Config DB data to validate.
    Raises:
        Exception: when cfg does not satisfy YANG schema.
    """

    try:
        cfg = sonic_cfggen.FormatConverter.to_serialized(copy.deepcopy(cfg))
        config_mgmt.ConfigMgmt().loadData(cfg)
    except Exception as err:
        raise Exception('Failed to validate configuration: {}'.format(err))


def update_entry_validated(db, table, key, data, create_if_not_exists=False):
    """ Update entry in table and validate configuration.
    If attribute value in data is None, the attribute is deleted.

    Args:
        db (swsscommon.ConfigDBConnector): Config DB connector obect.
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
        raise Exception(f"No field/values to update {key}")

    if create_if_not_exists:
        cfg[table].setdefault(key, {})

    if key not in cfg[table]:
        raise Exception(f"{key} does not exist")

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

    validate_config_or_raise(cfg)
    db.set_entry(table, key, cfg[table][key])


@click.group(name="passw-hardening",
             cls=clicommon.AliasedGroup)
def PASSW_HARDENING():
    """ PASSWORD HARDENING part of config_db.json """

    pass




@PASSW_HARDENING.group(name="policies",
                        cls=clicommon.AliasedGroup)
@clicommon.pass_db
def PASSW_HARDENING_POLICIES(db):
    """  """

    pass




@PASSW_HARDENING_POLICIES.command(name="state")

@click.argument(
    "state",
    nargs=1,
    required=True,
)
@clicommon.pass_db
def PASSW_HARDENING_POLICIES_state(db, state):
    """ state of the feature """

    table = "PASSW_HARDENING"
    key = "POLICIES"
    data = {
        "state": state,
    }
    try:
        update_entry_validated(db.cfgdb, table, key, data, create_if_not_exists=True)
    except Exception as err:
        exit_with_error(f"Error: {err}", fg="red")



@PASSW_HARDENING_POLICIES.command(name="expiration")

@click.argument(
    "expiration",
    nargs=1,
    required=True,
)
@clicommon.pass_db
def PASSW_HARDENING_POLICIES_expiration(db, expiration):
    """ expiration time (days unit) """

    table = "PASSW_HARDENING"
    key = "POLICIES"
    data = {
        "expiration": expiration,
    }
    try:
        update_entry_validated(db.cfgdb, table, key, data, create_if_not_exists=True)
    except Exception as err:
        exit_with_error(f"Error: {err}", fg="red")



@PASSW_HARDENING_POLICIES.command(name="expiration-warning")

@click.argument(
    "expiration-warning",
    nargs=1,
    required=True,
)
@clicommon.pass_db
def PASSW_HARDENING_POLICIES_expiration_warning(db, expiration_warning):
    """ expiration warning time (days unit) """

    table = "PASSW_HARDENING"
    key = "POLICIES"
    data = {
        "expiration_warning": expiration_warning,
    }
    try:
        update_entry_validated(db.cfgdb, table, key, data, create_if_not_exists=True)
    except Exception as err:
        exit_with_error(f"Error: {err}", fg="red")



@PASSW_HARDENING_POLICIES.command(name="history-cnt")

@click.argument(
    "history-cnt",
    nargs=1,
    required=True,
)
@clicommon.pass_db
def PASSW_HARDENING_POLICIES_history_cnt(db, history_cnt):
    """ num of old password that the system will recorded """

    table = "PASSW_HARDENING"
    key = "POLICIES"
    data = {
        "history_cnt": history_cnt,
    }
    try:
        update_entry_validated(db.cfgdb, table, key, data, create_if_not_exists=True)
    except Exception as err:
        exit_with_error(f"Error: {err}", fg="red")



@PASSW_HARDENING_POLICIES.command(name="len-min")

@click.argument(
    "len-min",
    nargs=1,
    required=True,
)
@clicommon.pass_db
def PASSW_HARDENING_POLICIES_len_min(db, len_min):
    """ password min length """

    table = "PASSW_HARDENING"
    key = "POLICIES"
    data = {
        "len_min": len_min,
    }
    try:
        update_entry_validated(db.cfgdb, table, key, data, create_if_not_exists=True)
    except Exception as err:
        exit_with_error(f"Error: {err}", fg="red")



@PASSW_HARDENING_POLICIES.command(name="reject-user-passw-match")

@click.argument(
    "reject-user-passw-match",
    nargs=1,
    required=True,
)
@clicommon.pass_db
def PASSW_HARDENING_POLICIES_reject_user_passw_match(db, reject_user_passw_match):
    """ username password match """

    table = "PASSW_HARDENING"
    key = "POLICIES"
    data = {
        "reject_user_passw_match": reject_user_passw_match,
    }
    try:
        update_entry_validated(db.cfgdb, table, key, data, create_if_not_exists=True)
    except Exception as err:
        exit_with_error(f"Error: {err}", fg="red")



@PASSW_HARDENING_POLICIES.command(name="lower-class")

@click.argument(
    "lower-class",
    nargs=1,
    required=True,
)
@clicommon.pass_db
def PASSW_HARDENING_POLICIES_lower_class(db, lower_class):
    """ password lower chars policy """

    table = "PASSW_HARDENING"
    key = "POLICIES"
    data = {
        "lower_class": lower_class,
    }
    try:
        update_entry_validated(db.cfgdb, table, key, data, create_if_not_exists=True)
    except Exception as err:
        exit_with_error(f"Error: {err}", fg="red")



@PASSW_HARDENING_POLICIES.command(name="upper-class")

@click.argument(
    "upper-class",
    nargs=1,
    required=True,
)
@clicommon.pass_db
def PASSW_HARDENING_POLICIES_upper_class(db, upper_class):
    """ password upper chars policy """

    table = "PASSW_HARDENING"
    key = "POLICIES"
    data = {
        "upper_class": upper_class,
    }
    try:
        update_entry_validated(db.cfgdb, table, key, data, create_if_not_exists=True)
    except Exception as err:
        exit_with_error(f"Error: {err}", fg="red")



@PASSW_HARDENING_POLICIES.command(name="digits-class")

@click.argument(
    "digits-class",
    nargs=1,
    required=True,
)
@clicommon.pass_db
def PASSW_HARDENING_POLICIES_digits_class(db, digits_class):
    """ password digits chars policy """

    table = "PASSW_HARDENING"
    key = "POLICIES"
    data = {
        "digits_class": digits_class,
    }
    try:
        update_entry_validated(db.cfgdb, table, key, data, create_if_not_exists=True)
    except Exception as err:
        exit_with_error(f"Error: {err}", fg="red")



@PASSW_HARDENING_POLICIES.command(name="special-class")

@click.argument(
    "special-class",
    nargs=1,
    required=True,
)
@clicommon.pass_db
def PASSW_HARDENING_POLICIES_special_class(db, special_class):
    """ password special chars policy """

    table = "PASSW_HARDENING"
    key = "POLICIES"
    data = {
        "special_class": special_class,
    }
    try:
        update_entry_validated(db.cfgdb, table, key, data, create_if_not_exists=True)
    except Exception as err:
        exit_with_error(f"Error: {err}", fg="red")


































def register(cli):
    """ Register new CLI nodes in root CLI.

    Args:
        cli: Root CLI node.
    Raises:
        Exception: when root CLI already has a command
                   we are trying to register.
    """
    cli_node = PASSW_HARDENING
    if cli_node.name in cli.commands:
        raise Exception(f"{cli_node.name} already exists in CLI")
    cli.add_command(PASSW_HARDENING)

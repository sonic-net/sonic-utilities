import sys

import click
from swsscommon import swsscommon
from utilities_common.cli import AbbreviationGroup, pass_db
from .validated_config_db_connector import ValidatedConfigDBConnector

SELECT_TIMEOUT = 1000  # ms


def set_feature_state(cfgdb_clients, name, state, block):
    """Enable/disable a feature"""
    entry_data_set = set()

    for ns, cfgdb in cfgdb_clients.items():
        entry_data = cfgdb.get_entry('FEATURE', name)
        if not entry_data:
            raise Exception("Feature '{}' doesn't exist".format(name))
        entry_data_set.add(entry_data['state'])

    if len(entry_data_set) > 1:
        raise Exception("Feature '{}' state is not consistent across namespaces".format(name))

    if entry_data['state'] == "always_enabled":
        raise Exception("Feature '{}' state is always enabled and can not be modified".format(name))

    for ns, cfgdb in cfgdb_clients.items():
        try:
            config_db = ValidatedConfigDBConnector(cfgdb)
            config_db.mod_entry('FEATURE', name, {'state': state})
        except ValueError as e:
            ctx = click.get_current_context()
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))

    if block:
        db = swsscommon.DBConnector('STATE_DB', 0)
        tbl = swsscommon.SubscriberStateTable(db, 'FEATURE')
        sel = swsscommon.Select()

        sel.addSelectable(tbl);

        while True:
            rc, _ = sel.select(SELECT_TIMEOUT)

            if rc == swsscommon.Select.TIMEOUT:
                continue
            elif rc == swsscommon.Select.ERROR:
                raise Exception('Failed to wait till feature reaches desired state: select() failed')
            else:
                feature, _, fvs = tbl.pop()
                if feature != name:
                    continue

                actual_state = dict(fvs).get('state')

                if actual_state == 'failed':
                    raise Exception('Feature failed to be {}'.format(state))
                elif actual_state == state:
                    break


#
# 'feature' group ('config feature ...')
#
@click.group(cls=AbbreviationGroup, name='feature', invoke_without_command=False)
def feature():
    """Configure features"""
    pass

def _update_field(db, name, fld, val):
    tbl = db.cfgdb.get_table('FEATURE')
    if tbl == None:
        sys.exit(1)
    if name not in tbl:
        click.echo("Unable to retrieve {} from FEATURE table".format(name))
        sys.exit(1)
    try:
        config_db = ValidatedConfigDBConnector(db.cfgdb)
        config_db.mod_entry('FEATURE', name, { fld: val })
    except ValueError as e:
        ctx = click.get_current_context()
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))


#
# 'owner' command ('config feature owner ...')
#
@feature.command('owner', short_help="set owner for a feature")
@click.argument('name', metavar='<feature-name>', required=True)
@click.argument('owner', metavar='<owner>', required=True, type=click.Choice(["local", "kube"]))
@pass_db
def feature_owner(db, name, owner):
    """Set owner for the feature"""
    _update_field(db, name, "set_owner", owner)


#
# 'fallback' command ('config feature fallback ...')
#
@feature.command('fallback', short_help="set fallback for a feature")
@click.argument('name', metavar='<feature-name>', required=True)
@click.argument('fallback', metavar='<fallback>', required=True, type=click.Choice(["on", "off"]))
@pass_db
def feature_fallback(db, name, fallback):
    """Set fallback for the feature"""
    _update_field(db, name, "no_fallback_to_local", "false" if fallback == "on" else "true")


#
# 'state' command ('config feature state ...')
#
@feature.command('state', short_help="Enable/disable a feature")
@click.argument('name', metavar='<feature-name>', required=True)
@click.argument('state', metavar='<state>', required=True, type=click.Choice(["enabled", "disabled"]))
@click.option('--block', is_flag=True, help='Wait till operation is finished')
@pass_db
def feature_state(db, name, state, block):
    """Enable/disable a feature"""

    try:
        set_feature_state(db.cfgdb_clients, name, state, block)
    except Exception as exception:
        click.echo("{}".format(exception))
        sys.exit(1)

#
# 'autorestart' command ('config feature autorestart ...')
#
@feature.command(name='autorestart', short_help="Enable/disable autosrestart of a feature")
@click.argument('name', metavar='<feature-name>', required=True)
@click.argument('autorestart', metavar='<autorestart>', required=True, type=click.Choice(["enabled", "disabled"]))
@pass_db
def feature_autorestart(db, name, autorestart):
    """Enable/disable autorestart of a feature"""
    entry_data_set = set()

    for ns, cfgdb in db.cfgdb_clients.items():
        entry_data = cfgdb.get_entry('FEATURE', name)
        if not entry_data:
            click.echo("Feature '{}' doesn't exist".format(name))
            sys.exit(1)
        entry_data_set.add(entry_data['auto_restart'])

    if len(entry_data_set) > 1:
        click.echo("Feature '{}' auto-restart is not consistent across namespaces".format(name))
        sys.exit(1)

    if entry_data['auto_restart'] == "always_enabled":
        click.echo("Feature '{}' auto-restart is always enabled and can not be modified".format(name))
        return

    for ns, cfgdb in db.cfgdb_clients.items():
        try:
            config_db = ValidatedConfigDBConnector(cfgdb)
            config_db.mod_entry('FEATURE', name, {'auto_restart': autorestart})
        except ValueError as e:
            ctx = click.get_current_context()
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))


import sys
import click
from natsort import natsorted
from tabulate import tabulate

from utilities_common.cli import AbbreviationGroup, pass_db

#
# 'feature' group (show feature ...)
#
@click.group(cls=AbbreviationGroup, name='feature', invoke_without_command=False)
def feature():
    """Show feature status"""
    pass


def make_header(fields_info, fields):
    header = ["Feature"]

    for (h, f, _) in fields_info:
        if f in fields:
            header.append(h)
    return header

def make_body(names, lst_data, fields, fields_info):
    # Make body
    body = []
    for name, data in zip(names, lst_data):
        entry = [name]
        for (_, f, d) in fields_info:
            if f in fields:
                entry.append(data[f] if f in data else d)
        body.append(entry)
    return body


#
# 'status' subcommand (show feature status)
#
@feature.command('status', short_help="Show feature state")
@click.argument('feature_name', required=False)
@pass_db
def feature_status(db, feature_name):
    fields_info = [
            ('State', 'state', ""),
            ('AutoRestart', 'auto_restart', ""),
            ('SystemState', 'system_state', ""),
            ('UpdateTime', 'update_time', ""),
            ('ContainerId', 'container_id', ""),
            ('Version', 'container_version', ""),
            ('SetOwner', 'set_owner', ""),
            ('CurrentOwner', 'current_owner', ""),
            ('RemoteState', "remote_state", "")
            ]

    cfg_table = db.cfgdb.get_table('FEATURE')
    dbconn = db.db
    keys = dbconn.keys(dbconn.STATE_DB, "FEATURE|*")
    ordered_data = []
    fields = set()
    names = []
    if feature_name:
        key = "FEATURE|{}".format(feature_name)
        if feature_name in cfg_table:
            data = {}
            if keys and (key in keys):
                data = dbconn.get_all(dbconn.STATE_DB, key)
            data.update(cfg_table[feature_name])
            ordered_data.append(data)
            fields = set(data.keys())
            names.append(feature_name)
        else:
            click.echo("Can not find feature {}".format(feature_name))
            sys.exit(1)
    else:
        for name in natsorted(cfg_table.keys()):
            data = {}
            key = "FEATURE|{}".format(name)
            if keys and (key in keys):
                data = dbconn.get_all(dbconn.STATE_DB, key)
            data.update(cfg_table[name])

            fields = fields | set(data.keys())
            ordered_data.append(data)
            names.append(name)

    header = make_header(fields_info, fields)
    body = make_body(names, ordered_data, fields, fields_info)
    click.echo(tabulate(body, header, disable_numparse=True))


def _negate_bool_str(d):
    d = d.lower()
    if d ==  "true":
        return "false"
    if d ==  "false":
        return "true"
    return d

def _update_data(upd_lst, data):
    for f in upd_lst:
        if f in data:
            data[f] = upd_lst[f](data[f])
    return data

#
# 'config' subcommand (show feature config)
#
@feature.command('config', short_help="Show feature config")
@click.argument('feature_name', required=False)
@pass_db
def feature_config(db, feature_name):
    fields_info = [
            ('State', 'state', ""),
            ('AutoRestart', 'auto_restart', ""),
            ('Owner', 'set_owner', "local"),
            ('fallback', 'no_fallback_to_local', "")
            ]

    update_list = { "no_fallback_to_local" : _negate_bool_str }

    cfg_table = db.cfgdb.get_table('FEATURE')
    ordered_data = []
    names = []
    fields = set()
    if feature_name:
        if feature_name in cfg_table:
            data = _update_data(update_list, cfg_table[feature_name])
            ordered_data.append(data)
            names.append(feature_name)
            fields = set(data.keys())
        else:
            click.echo("Can not find feature {}".format(feature_name))
            sys.exit(1)
    else:
        for key in natsorted(cfg_table.keys()):
            data = _update_data(update_list, cfg_table[key])

            fields = fields | set(data.keys())
            names.append(key)
            ordered_data.append(data)

    header = make_header(fields_info, fields)
    body = make_body(names, ordered_data, fields, fields_info)
    click.echo(tabulate(body, header, disable_numparse=True))

#
# 'autorestart' subcommand (show feature autorestart)
#
@feature.command('autorestart', short_help="Show auto-restart state for a feature")
@click.argument('feature_name', required=False)
@pass_db
def feature_autorestart(db, feature_name):
    header = ['Feature', 'AutoRestart']
    body = []
    feature_table = db.cfgdb.get_table('FEATURE')
    if feature_name:
        if feature_table and feature_name in feature_table:
            body.append([feature_name, feature_table[ feature_name ].get('auto_restart', 'unknown')])
        else:
            click.echo("Can not find feature {}".format(feature_name))
            sys.exit(1)
    else:
        for name in natsorted(list(feature_table.keys())):
            body.append([name, feature_table[ name ].get('auto_restart', 'unknown')])
    click.echo(tabulate(body, header))

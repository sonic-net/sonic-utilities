import click
from getpass import getpass
import os
import sys

from swsscommon.swsscommon import SonicV2Connector

CHASSIS_MODULE_INFO_TABLE = 'CHASSIS_MODULE_TABLE'
CHASSIS_MODULE_INFO_KEY_TEMPLATE = 'CHASSIS_MODULE {}'
CHASSIS_MODULE_INFO_DESC_FIELD = 'desc'
CHASSIS_MODULE_INFO_SLOT_FIELD = 'slot'
CHASSIS_MODULE_INFO_OPERSTATUS_FIELD = 'oper_status'
CHASSIS_MODULE_INFO_ADMINSTATUS_FIELD = 'admin_status'

CHASSIS_MIDPLANE_INFO_TABLE = 'CHASSIS_MIDPLANE_TABLE'
CHASSIS_MIDPLANE_INFO_IP_FIELD = 'ip_address'
CHASSIS_MIDPLANE_INFO_ACCESS_FIELD = 'access'

CHASSIS_MODULE_HOSTNAME_TABLE = 'CHASSIS_MODULE_HOSTNAME_TABLE'
CHASSIS_MODULE_HOSTNAME = 'module_hostname'

def connect_to_chassis_state_db():
    chassis_state_db = SonicV2Connector(host="127.0.0.1")
    chassis_state_db.connect(chassis_state_db.CHASSIS_STATE_DB)
    return chassis_state_db


def connect_state_db():
    state_db = SonicV2Connector(host="127.0.0.1")
    state_db.connect(state_db.STATE_DB)
    return state_db


def get_linecard_module_name_from_hostname(linecard_name: str):

    chassis_state_db = connect_to_chassis_state_db()
    keys = chassis_state_db.keys(chassis_state_db.CHASSIS_STATE_DB , '{}|{}'.format(CHASSIS_MODULE_HOSTNAME_TABLE, '*'))
    for key in keys:
        module_name = key.split('|')[1]
        hostname = chassis_state_db.get(chassis_state_db.CHASSIS_STATE_DB, key, CHASSIS_MODULE_HOSTNAME)
        if hostname.replace('-', '').lower() == linecard_name.replace('-', '').lower():
            return module_name

    return None


def get_linecard_hostname_from_module_name(linecard_name: str):

    chassis_state_db = connect_to_chassis_state_db()
    keys = chassis_state_db.keys(chassis_state_db.CHASSIS_STATE_DB, '{}|{}'.format(CHASSIS_MODULE_HOSTNAME_TABLE, '*'))
    for key in keys:
        module_name = key.split('|')[1]
        if module_name.replace('-', '').lower() == linecard_name.replace('-', '').lower():
            hostname = chassis_state_db.get(chassis_state_db.CHASSIS_STATE_DB, key, CHASSIS_MODULE_HOSTNAME)
            return hostname

    return None


def get_linecard_ip(linecard_name: str):
    """
    Given a linecard name, lookup its IP address in the midplane table
    :param linecard_name: The name of the linecard you want to connect to
    :type linecard_name: str
    :return: IP address of the linecard
    """
    # Adapted from `show chassis modules midplane-status` command logic:
    # https://github.com/sonic-net/sonic-utilities/blob/master/show/chassis_modules.py

    # if the user passes linecard hostname, then try to get the module name for that linecard
    module_name = get_linecard_module_name_from_hostname(linecard_name)
    # if the module name cannot be found from host, assume the user has passed module name
    if module_name is None:
        module_name = linecard_name
    module_ip, module_access = get_module_ip_and_access_from_state_db(module_name)

    if not module_ip:
        click.echo('Linecard {} not found'.format(linecard_name))
        return None

    if module_access != 'True':
        click.echo('Linecard {} not accessible'.format(linecard_name))
        return None
    return module_ip


def get_module_ip_and_access_from_state_db(module_name):
    state_db = connect_state_db()
    data_dict = state_db.get_all(
        state_db.STATE_DB, '{}|{}'.format(CHASSIS_MIDPLANE_INFO_TABLE,module_name ))
    if data_dict is None:
        return None, None

    linecard_ip = data_dict.get(CHASSIS_MIDPLANE_INFO_IP_FIELD, None)
    access = data_dict.get(CHASSIS_MIDPLANE_INFO_ACCESS_FIELD, None)

    return linecard_ip, access


def get_all_linecards(ctx, args, incomplete) -> list:
    """
    Return a list of all accessible linecard names. This function is used to 
    autocomplete linecard names in the CLI.

    :param ctx: The Click context object that is passed to the command function
    :param args: The arguments passed to the Click command
    :param incomplete: The string that the user has typed so far
    :return: A list of all accessible linecard names.
    """
    # Adapted from `show chassis modules midplane-status` command logic:
    # https://github.com/sonic-net/sonic-utilities/blob/master/show/chassis_modules.py

    chassis_state_db = connect_to_chassis_state_db()
    state_db = connect_state_db()

    linecards = []
    keys = state_db.keys(state_db.STATE_DB,'{}|*'.format(CHASSIS_MIDPLANE_INFO_TABLE))
    for key in keys:
        key_list = key.split('|')
        if len(key_list) != 2:  # error data in DB, log it and ignore
            click.echo('Warn: Invalid Key {} in {} table'.format(key, CHASSIS_MIDPLANE_INFO_TABLE ))
            continue
        module_name = key_list[1]
        linecard_ip, access = get_module_ip_and_access_from_state_db(module_name)
        if linecard_ip is None:
            continue

        if access != "True":
            continue

        # get the hostname for this module
        hostname = chassis_state_db.get(chassis_state_db.CHASSIS_STATE_DB, '{}|{}'.format(CHASSIS_MODULE_HOSTNAME_TABLE, module_name), CHASSIS_MODULE_HOSTNAME)
        if hostname:
            linecards.append(hostname)
        else:
            linecards.append(module_name)

    # Return a list of all matched linecards
    return [lc for lc in linecards if incomplete in lc]


def get_password(username=None):
    """
    Prompts the user for a password, and returns the password

    :param username: The username that we want to get the password for
    :type username: str
    :return: The password for the username.
    """

    if username is None:
        username = os.getlogin()

    return getpass(
        "Password for username '{}': ".format(username),
        # Pass in click stdout stream - this is similar to using click.echo
        stream=click.get_text_stream('stdout')
    )

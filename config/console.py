import click
import string
import utilities_common.cli as clicommon
from .validated_config_db_connector import ValidatedConfigDBConnector
from jsonpatch import JsonPatchConflict
#
# 'console' group ('config console ...')
#
@click.group('console')
def console():
    """Console-related configuration tasks"""
    pass

#
# 'console enable' group ('config console enable')
#
@console.command('enable')
@clicommon.pass_db
def enable_console_switch(db):
    """Enable console switch"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)

    table = "CONSOLE_SWITCH"
    dataKey1 = 'console_mgmt'
    dataKey2 = 'enabled'

    data = { dataKey2 : "yes" }
    try:
        config_db.mod_entry(table, dataKey1, data)
    except ValueError as e:
        ctx = click.get_current_context()
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))

#
# 'console disable' group ('config console disable')
#
@console.command('disable')
@clicommon.pass_db
def disable_console_switch(db):
    """Disable console switch"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)

    table = "CONSOLE_SWITCH"
    dataKey1 = 'console_mgmt'
    dataKey2 = 'enabled'

    data = { dataKey2 : "no" }
    try:
        config_db.mod_entry(table, dataKey1, data)
    except ValueError as e:
        ctx = click.get_current_context()
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))


#
# 'console escape' group ('config console escape A|B|...')
#
@console.command('escape')
@clicommon.pass_db
@click.argument('escape', metavar='<escape_char|clear>', required=True,
                type=click.Choice(list(string.ascii_letters) + ["clear"], case_sensitive=True))
def set_console_escape_char(db, escape):
    """Set console escape character or clear the existing one"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)

    table = "CONSOLE_SWITCH"
    dataKey1 = 'console_mgmt'
    dataKey2 = 'escape_char'

    existing_entry = config_db.get_entry(table, dataKey1) or {}
    if escape == "clear":
        # Remove the escape_char field while preserving other keys (e.g., 'enabled')
        if dataKey2 in existing_entry:
            del existing_entry[dataKey2]
        data = existing_entry
    else:
        existing_entry[dataKey2] = escape.lower()
        data = existing_entry

    try:
        config_db.set_entry(table, dataKey1, data)
    except ValueError as e:
        ctx = click.get_current_context()
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))


#
# 'console add' group ('config console add ...')
#
@console.command('add')
@clicommon.pass_db
@click.argument('linenum', metavar='<line_number>', required=True, type=click.IntRange(0, 65535))
@click.option('--baud', '-b', metavar='<baud>', required=True, type=click.INT)
@click.option('--flowcontrol', '-f', metavar='<flow_control>', required=False, is_flag=True)
@click.option('--devicename', '-d', metavar='<device_name>', required=False)
def add_console_setting(db, linenum, baud, flowcontrol, devicename):
    """Add Console-realted configuration tasks"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)

    table = "CONSOLE_PORT"
    dataKey1 = 'baud_rate'
    dataKey2 = 'flow_control'
    dataKey3 = 'remote_device'

    ctx = click.get_current_context()
    data = config_db.get_entry(table, linenum)
    if data:
        ctx.fail("Trying to add console port setting, which is already exists.")
    else:
        console_entry = { dataKey1: baud }
        console_entry[dataKey2] = "1" if flowcontrol else "0"

        if devicename:
            if isExistingSameDevice(config_db, devicename, table):
                ctx.fail("Given device name {} has been used. Please enter a valid device name or remove the existing one !!".format(devicename))
            console_entry[dataKey3] = devicename

        try:
            config_db.set_entry(table, linenum, console_entry)
        except ValueError as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))


#
# 'console del' group ('config console del ...')
#
@console.command('del')
@clicommon.pass_db
@click.argument('linenum', metavar='<line_number>', required=True, type=click.IntRange(0, 65535))
def remove_console_setting(db, linenum):
    """Remove Console-related configuration tasks"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    ctx = click.get_current_context()

    table = "CONSOLE_PORT"

    data = config_db.get_entry(table, linenum)
    if data:
        try:
            config_db.set_entry(table, linenum, None)
        except JsonPatchConflict as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))
    else:
        ctx.fail("Trying to delete console port setting, which is not present.")

#
# 'console remote_device' group ('config console remote_device ...')
#
@console.command('remote_device')
@clicommon.pass_db
@click.argument('linenum', metavar='<line_number>', required=True, type=click.IntRange(0, 65535))
@click.argument('devicename', metavar='<device_name>', required=False)
def upate_console_remote_device_name(db, linenum, devicename):
    """Update remote device name for a console line"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    ctx = click.get_current_context()

    table = "CONSOLE_PORT"
    dataKey = 'remote_device'

    data = config_db.get_entry(table, linenum)
    if data:
        if dataKey in data and devicename == data[dataKey]:
            # do nothing if the device name is same with existing configurtion
            return
        elif not devicename:
            # remove configuration key from console setting if user not give a remote device name
            data.pop(dataKey, None)
            try:
                config_db.mod_entry(table, linenum, data)
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))
        elif isExistingSameDevice(config_db, devicename, table):
            ctx.fail("Given device name {} has been used. Please enter a valid device name or remove the existing one !!".format(devicename))
        else:
            data[dataKey] = devicename
            try:
                config_db.mod_entry(table, linenum, data)
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))
    else:
        ctx.fail("Trying to update console port setting, which is not present.")

#
# 'console baud' group ('config console baud ...')
#
@console.command('baud')
@clicommon.pass_db
@click.argument('linenum', metavar='<line_number>', required=True, type=click.IntRange(0, 65535))
@click.argument('baud', metavar='<baud>', required=True, type=click.INT)
def update_console_baud(db, linenum, baud):
    """Update baud for a console line"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    ctx = click.get_current_context()

    table = "CONSOLE_PORT"
    dataKey = 'baud_rate'

    data = config_db.get_entry(table, linenum)
    if data:
        baud = str(baud)
        if dataKey in data and baud == data[dataKey]:
            # do nothing if the baud is same with existing configurtion
            return
        else:
            data[dataKey] = baud
            try:
                config_db.mod_entry(table, linenum, data)
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))
    else:
        ctx.fail("Trying to update console port setting, which is not present.")

#
# 'console flow_control' group ('config console flow_control ...')
#
@console.command('flow_control')
@clicommon.pass_db
@click.argument('mode', metavar='<mode>', required=True, type=click.Choice(["enable", "disable"]))
@click.argument('linenum', metavar='<line_number>', required=True, type=click.IntRange(0, 65535))
def update_console_flow_control(db, mode, linenum):
    """Update flow control setting for a console line"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    ctx = click.get_current_context()

    table = "CONSOLE_PORT"
    dataKey = 'flow_control'

    innerMode = "1" if mode == "enable" else "0"

    data = config_db.get_entry(table, linenum)
    if data:
        if dataKey in data and innerMode == data[dataKey]:
            # do nothing if the flow control setting is same with existing configurtion
            return
        else:
            data[dataKey] = innerMode
            try:
                config_db.mod_entry(table, linenum, data)
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))
    else:
        ctx.fail("Trying to update console port setting, which is not present.")

def isExistingSameDevice(config_db, deviceName, table):
    """Check if the given device name is conflict with existing device"""
    settings = config_db.get_table(table)
    for key,values in settings.items():
        if "remote_device" in values and deviceName == values["remote_device"]:
            return True

    return False

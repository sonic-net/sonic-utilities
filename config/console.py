import click
import string
import re
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
# 'console heartbeat' group ('config console heartbeat ...')
#
@console.command('heartbeat')
@clicommon.pass_db
@click.argument('mode', metavar='<mode>', required=True, type=click.Choice(["enable", "disable"]))
def update_console_heartbeat(db, mode):
    """Enable/Disable console heartbeat on controlled device (DTE side)"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)

    table = "CONSOLE_SWITCH"
    dataKey1 = 'controlled_device'
    dataKey2 = 'enabled'

    data = {dataKey2: "yes" if mode == "enable" else "no"}
    try:
        config_db.mod_entry(table, dataKey1, data)
    except ValueError as e:
        ctx = click.get_current_context()
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))


# 'console default_escape' group ('config console default_escape A|B|...')
#
@console.command('default_escape')
@clicommon.pass_db
@click.argument('escape', metavar='<escape_char|clear>', required=True,
                type=click.Choice(list(string.ascii_letters) + ["clear"], case_sensitive=True))
def set_console_default_escape_char(db, escape):
    """Set console escape character or clear the existing one"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)

    table = "CONSOLE_SWITCH"
    dataKey1 = 'console_mgmt'
    dataKey2 = 'default_escape_char'

    existing_entry = config_db.get_entry(table, dataKey1) or {}
    if escape == "clear":
        # Remove the default_escape_char field while preserving other keys (e.g., 'enabled')
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
@click.option('--escape', '-e', metavar='<escape_char>', required=False,
              type=click.Choice(list(string.ascii_letters), case_sensitive=True))
def add_console_setting(db, linenum, baud, flowcontrol, devicename, escape):
    """Add Console-realted configuration tasks"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)

    table = "CONSOLE_PORT"
    dataKey1 = 'baud_rate'
    dataKey2 = 'flow_control'
    dataKey3 = 'remote_device'
    dataKey4 = 'escape_char'

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

        if escape:
            console_entry[dataKey4] = escape.lower()

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
def update_console_remote_device_name(db, linenum, devicename):
    """Update remote device name for a console line"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    ctx = click.get_current_context()

    table = "CONSOLE_PORT"
    dataKey = 'remote_device'

    data = config_db.get_entry(table, linenum)
    if data:
        if dataKey in data and devicename == data[dataKey]:
            # do nothing if the device name is same with existing configuration
            return
        elif not devicename:
            # remove configuration key from console setting if user not give a remote device name
            if dataKey in data:
                del data[dataKey]
                try:
                    config_db.set_entry(table, linenum, data)
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
            # do nothing if the baud is same with existing configuration
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
            # do nothing if the flow control setting is same with existing configuration
            return
        else:
            data[dataKey] = innerMode
            try:
                config_db.mod_entry(table, linenum, data)
            except ValueError as e:
                ctx.fail("Invalid ConfigDB. Error: {}".format(e))
    else:
        ctx.fail("Trying to update console port setting, which is not present.")


#
# 'console escape' group ('config console escape ...')
#
@console.command('escape')
@clicommon.pass_db
@click.argument('linenum', metavar='<line_number>', required=True, type=click.IntRange(0, 65535))
@click.argument('escape', metavar='<escape_char|clear>', required=True,
                type=click.Choice(list(string.ascii_letters) + ["clear"], case_sensitive=True))
def update_console_escape_char(db, linenum, escape):
    """Update escape character for a console line"""
    config_db = ValidatedConfigDBConnector(db.cfgdb)
    ctx = click.get_current_context()

    table = "CONSOLE_PORT"
    dataKey = 'escape_char'

    data = config_db.get_entry(table, linenum)
    if data:
        if escape == "clear":
            if dataKey in data:
                del data[dataKey]
        else:
            data[dataKey] = escape.lower()

        try:
            config_db.set_entry(table, linenum, data)
        except ValueError as e:
            ctx.fail("Invalid ConfigDB. Error: {}".format(e))
    else:
        ctx.fail("Trying to update console port setting, which is not present.")


#
# 'console logging' group ('config console logging ...')
#
LOGROTATE_SIZE_PATTERN = re.compile(r'^[0-9]+[kKmMgG]?$')
DEFAULT_LOG_FILE_TEMPLATE = "/var/log/console-{}.log"
DEFAULT_LOGROTATE_SIZE = "1M"
DEFAULT_LOGROTATE_COUNT = "20"


def default_log_file(linenum):
    return DEFAULT_LOG_FILE_TEMPLATE.format(linenum)


def apply_default_logging_config(data, linenum):
    """Fill in default log file and logrotate settings when not configured."""
    if not data.get('log_file'):
        data['log_file'] = default_log_file(linenum)
    if not data.get('logrotate_size'):
        data['logrotate_size'] = DEFAULT_LOGROTATE_SIZE
    if not data.get('logrotate_count'):
        data['logrotate_count'] = DEFAULT_LOGROTATE_COUNT


def parse_logrotate_args(ctx, logrotate_keyword, size, count):
    """Resolve logrotate size/count from optional CLI arguments."""
    if logrotate_keyword is None:
        return DEFAULT_LOGROTATE_SIZE, DEFAULT_LOGROTATE_COUNT

    if logrotate_keyword != 'logrotate':
        ctx.fail("Expected 'logrotate' keyword.")

    if size is None or count is None:
        ctx.fail("Both <size> and <count> are required when 'logrotate' is specified.")

    if not LOGROTATE_SIZE_PATTERN.match(size):
        ctx.fail("Invalid logrotate size '{}'. Use a value like 10M or 100k.".format(size))

    return size, str(count)


@console.group('logging')
@click.argument('linenum', metavar='<line_number>', required=True, type=click.IntRange(0, 65535))
def console_logging(linenum):
    """Console I/O logging configuration"""
    pass


@console_logging.command('enable')
@clicommon.pass_db
def enable_console_logging(db):
    """Enable console I/O logging for a console line"""
    linenum = click.get_current_context().parent.params['linenum']
    _set_console_logging_state(linenum, db, "yes")


@console_logging.command('disable')
@clicommon.pass_db
def disable_console_logging(db):
    """Disable console I/O logging for a console line"""
    linenum = click.get_current_context().parent.params['linenum']
    _set_console_logging_state(linenum, db, "no")


@console_logging.command('filename')
@clicommon.pass_db
@click.argument('filename', metavar='<file_name>', required=True)
@click.argument('logrotate_keyword', metavar='logrotate', required=False)
@click.argument('size', metavar='<size>', required=False)
@click.argument('count', metavar='<count>', required=False, type=click.IntRange(1, 100))
def set_console_logging_filename(db, filename, logrotate_keyword, size, count):
    """Configure console log file and optional logrotate settings"""
    ctx = click.get_current_context()
    logrotate_size, logrotate_count = parse_logrotate_args(ctx, logrotate_keyword, size, count)

    linenum = ctx.parent.params['linenum']
    config_db = ValidatedConfigDBConnector(db.cfgdb)

    table = "CONSOLE_PORT"
    data = config_db.get_entry(table, linenum)
    if not data:
        ctx.fail("Trying to update console port setting, which is not present.")

    size_key = 'logrotate_size'
    count_key = 'logrotate_count'
    file_key = 'log_file'

    if (data.get(file_key) == filename and
            data.get(size_key) == logrotate_size and
            data.get(count_key) == logrotate_count):
        return

    data[file_key] = filename
    data[size_key] = logrotate_size
    data[count_key] = logrotate_count
    try:
        config_db.mod_entry(table, linenum, data)
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))


def _set_console_logging_state(linenum, db, enabled_value):
    ctx = click.get_current_context()
    config_db = ValidatedConfigDBConnector(db.cfgdb)

    table = "CONSOLE_PORT"
    enabled_key = 'logging_enabled'

    data = config_db.get_entry(table, linenum)
    if not data:
        ctx.fail("Trying to update console port setting, which is not present.")

    if enabled_value == "yes":
        old_log_file = data.get('log_file')
        old_size = data.get('logrotate_size')
        old_count = data.get('logrotate_count')
        apply_default_logging_config(data, linenum)
        defaults_changed = (
            data.get('log_file') != old_log_file or
            data.get('logrotate_size') != old_size or
            data.get('logrotate_count') != old_count
        )
    else:
        defaults_changed = False

    if data.get(enabled_key) == enabled_value and not defaults_changed:
        return

    data[enabled_key] = enabled_value
    try:
        config_db.mod_entry(table, linenum, data)
    except ValueError as e:
        ctx.fail("Invalid ConfigDB. Error: {}".format(e))


def isExistingSameDevice(config_db, deviceName, table):
    """Check if the given device name is conflict with existing device"""
    settings = config_db.get_table(table)
    for key,values in settings.items():
        if "remote_device" in values and deviceName == values["remote_device"]:
            return True

    return False

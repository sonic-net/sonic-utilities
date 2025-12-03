import configparser
import os
import pexpect
import sys

import click


# This is from the aliases example:
# https://github.com/pallets/click/blob/57c6f09611fc47ca80db0bd010f05998b3c0aa95/examples/aliases/aliases.py
class Config(object):
    """Object to hold CLI config"""

    def __init__(self):
        self.path = os.getcwd()
        self.aliases = {}

    def read_config(self, filename):
        parser = configparser.RawConfigParser()
        parser.read([filename])
        try:
            self.aliases.update(parser.items('aliases'))
        except configparser.NoSectionError:
            pass


# Global Config object
_config = None


class AliasedGroup(click.Group):
    """This subclass of click.Group supports abbreviations and
       looking up aliases in a config file with a bit of magic.
    """

    def get_command(self, ctx, cmd_name):
        global _config

        # If we haven't instantiated our global config, do it now and load current config
        if _config is None:
            _config = Config()

            # Load our config file
            cfg_file = os.path.join(os.path.dirname(__file__), 'aliases.ini')
            _config.read_config(cfg_file)

        # Try to get builtin commands as normal
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv

        # No builtin found. Look up an explicit command alias in the config
        if cmd_name in _config.aliases:
            actual_cmd = _config.aliases[cmd_name]
            return click.Group.get_command(self, ctx, actual_cmd)

        # Alternative option: if we did not find an explicit alias we
        # allow automatic abbreviation of the command.  "status" for
        # instance will match "st".  We only allow that however if
        # there is only one command.
        matches = [x for x in self.list_commands(ctx)
                   if x.lower().startswith(cmd_name.lower())]
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail('Too many matches: %s' % ', '.join(sorted(matches)))

def run_command(command, display_cmd=False):
    if display_cmd:
        click.echo(click.style("Command: ", fg='cyan') + click.style(command, fg='green'))

    proc = pexpect.spawn(command)
    proc.interact()
    proc.close()
    return proc.exitstatus

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help', '-?'])

#
# 'connect' group (root group)
#

# This is our entrypoint - the main "connect" command
@click.group(cls=AliasedGroup, context_settings=CONTEXT_SETTINGS)
def connect():
    """SONiC command line - 'connect' command"""
    pass

#
# 'line' command ("connect line")
#
@connect.command('line')
@click.argument('target')
@click.option('--devicename', '-d', is_flag=True, help="connect by name - if flag is set, interpret target as device name instead")
def line(target, devicename):
    """Connect to line LINENUM via serial connection"""
    cmd = "consutil connect {}".format("--devicename " if devicename else "") + str(target)
    sys.exit(run_command(cmd))

#
# 'device' command ("connect device")
#
@connect.command('device')
@click.argument('devicename')
def device(devicename):
    """Connect to device DEVICENAME via serial connection"""
    cmd = "consutil connect -d " + devicename
    sys.exit(run_command(cmd))

if __name__ == '__main__':
    connect()

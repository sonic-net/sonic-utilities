import click
import utilities_common.cli as clicommon

from .validated_config_db_connector import ValidatedConfigDBConnector

#
#EVPN MH commands
#
EVPN_MH_TABLE = 'EVPN_MH_GLOBAL'

#
# 'evpn-mh' group ('config evpn-mh ...')
#
@click.group(cls=clicommon.AbbreviationGroup, name='evpn-mh')
@click.pass_context
def evpn_mh(ctx):
    """Set EVPN MH attributes"""
    pass

#
# 'startup-delay' subcommand
#
EVPN_MH_STARTUP_DELAY_MIN = 0
EVPN_MH_STARTUP_DELAY_DEFAULT = 300
EVPN_MH_STARTUP_DELAY_MAX = 3600

def is_valid_startup_delay(startup_delay):
    is_valid = False

    if int(startup_delay) in range(EVPN_MH_STARTUP_DELAY_MIN, EVPN_MH_STARTUP_DELAY_MAX+1):
        is_valid = True

    return is_valid


@evpn_mh.command('startup-delay')
@click.argument('startup_delay', metavar='<startup_delay>', required=True)
@click.pass_context
def set_startup_delay(ctx, startup_delay=EVPN_MH_STARTUP_DELAY_DEFAULT):
    """Add EVPN MH"""
    config_db = ValidatedConfigDBConnector(ctx.obj['config_db'])
    if not is_valid_startup_delay(startup_delay):
        ctx.fail(f"EVPN MH Startup Delay {startup_delay} is not valid. " \
                 "Valid values are {EVPN_MH_STARTUP_DELAY_MIN}-{EVPN_MH_STARTUP_DELAY_MAX}.")

    try:
        config_db.set_entry(EVPN_MH_TABLE, 'default', {'startup_delay': int(startup_delay)})
    except ValueError as e:
        ctx.fail("Failed to save to ConfigDB. Error: {}".format(e))

#
# 'mac-holdtime' subcommand
#
EVPN_MH_MAC_HOLDTIME_MIN = 0
EVPN_MH_MAC_HOLDTIME_DEFAULT = 1080
EVPN_MH_MAC_HOLDTIME_MAX = 86400

def is_valid_mac_holdtime(mac_holdtime):
    is_valid = False

    if int(mac_holdtime) in range(EVPN_MH_MAC_HOLDTIME_MIN, EVPN_MH_MAC_HOLDTIME_MAX+1):
        is_valid = True

    return is_valid

@evpn_mh.command('mac-holdtime')
@click.argument('mac_holdtime', metavar='<mac_holdtime>', required=True)
@click.pass_context
def set_mac_holdtime(ctx, mac_holdtime=EVPN_MH_MAC_HOLDTIME_DEFAULT):
    """Add EVPN MH"""
    config_db = ValidatedConfigDBConnector(ctx.obj['config_db'])
    if not is_valid_mac_holdtime(mac_holdtime):
        ctx.fail(f"EVPN MH Startup Delay {mac_holdtime} is not valid. " \
                 "Valid values are {EVPN_MH_MAC_HOLDTIME_MIN}-{EVPN_MH_MAC_HOLDTIME_MAX}.")

    try:
        config_db.set_entry(EVPN_MH_TABLE, 'default', {'mac_holdtime': int(mac_holdtime)})
    except ValueError as e:
        ctx.fail("Failed to save to ConfigDB. Error: {}".format(e))

#
# 'neigh_holdtime' subcommand
#
EVPN_MH_NEIGH_HOLDTIME_MIN = 0
EVPN_MH_NEIGH_HOLDTIME_DEFAULT = 1080
EVPN_MH_NEIGH_HOLDTIME_MAX = 86400

def is_valid_neigh_holdtime(neigh_holdtime):
    is_valid = False

    if int(neigh_holdtime) in range(EVPN_MH_NEIGH_HOLDTIME_MIN, EVPN_MH_NEIGH_HOLDTIME_MAX+1):
        is_valid = True

    return is_valid

@evpn_mh.command('neigh-holdtime')
@click.argument('neigh_holdtime', metavar='<neigh_holdtime>', required=True)
@click.pass_context
def set_neigh_holdtime(ctx, neigh_holdtime=EVPN_MH_NEIGH_HOLDTIME_DEFAULT):
    """Add EVPN MH"""
    config_db = ValidatedConfigDBConnector(ctx.obj['config_db'])
    if not is_valid_neigh_holdtime(neigh_holdtime):
        ctx.fail(f"EVPN MH Startup Delay {neigh_holdtime} is not valid. " \
                 "Valid values are {EVPN_MH_NEIGH_HOLDTIME_MIN}-{EVPN_MH_NEIGH_HOLDTIME_MAX}.")

    try:
        config_db.set_entry(EVPN_MH_TABLE, 'default', {'neigh_holdtime': int(neigh_holdtime)})
    except ValueError as e:
        ctx.fail("Failed to save to ConfigDB. Error: {}".format(e))

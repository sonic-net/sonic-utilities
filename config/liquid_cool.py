import click
import utilities_common.cli as clicommon

LEAK_CONTROL_POLICY_TABLE = 'LEAK_CONTROL_POLICY'
LEAK_CONTROL_POLICY_KEY = 'policy'

VALID_POLICIES = ('system', 'rack_mgr')
VALID_SEVERITIES = ('critical', 'major', 'minor')
VALID_ACTIONS = ('syslog_only', 'graceful_shutdown', 'power_off')

# A single Minor leak is already MINOR_SYSTEM_LEAK, so the smallest MIN-N that can
# classify concurrent Minor leaks as MAJOR is 2 (matches thermalctld's
# MAJOR_LEAK_MIN_SENSORS_FLOOR).
MAJOR_LEAK_MIN_SENSORS_FLOOR = 2
MAJOR_LEAK_MIN_SENSORS_FIELD = 'system_major_leak_num_min_sensors'

POLICY_FIELD_MAP = {
    'system': 'system_leak_policy',
    'rack_mgr': 'rack_mgr_leak_policy',
}

ACTION_FIELD_MAP = {
    ('system', 'critical'): 'system_critical_leak_action',
    ('system', 'major'): 'system_major_leak_action',
    ('system', 'minor'): 'system_minor_leak_action',
    ('rack_mgr', 'critical'): 'rack_mgr_critical_alert_action',
    ('rack_mgr', 'major'): 'rack_mgr_major_alert_action',
    ('rack_mgr', 'minor'): 'rack_mgr_minor_alert_action',
}


@click.group('liquid-cool')
def liquid_cool():
    """Liquid cooling configuration commands"""
    pass


@liquid_cool.command('leak-control')
@clicommon.pass_db
@click.argument('policy_type', metavar='[system|rack_mgr]', type=click.Choice(VALID_POLICIES))
@click.argument('state', metavar='[enabled|disabled]', type=click.Choice(['enabled', 'disabled']))
def leak_control(db, policy_type, state):
    """Enable or disable system/rack-manager leak policy enforcement"""
    field = POLICY_FIELD_MAP[policy_type]
    db.cfgdb.mod_entry(LEAK_CONTROL_POLICY_TABLE, LEAK_CONTROL_POLICY_KEY, {field: state})
    click.echo(f"Leak control policy for '{policy_type}' set to '{state}'")


@liquid_cool.command('leak-action')
@clicommon.pass_db
@click.argument('policy_type', metavar='[system|rack_mgr]', type=click.Choice(VALID_POLICIES))
@click.argument('severity', metavar='[critical|major|minor]', type=click.Choice(VALID_SEVERITIES))
@click.argument('action', metavar='[syslog_only|graceful_shutdown|power_off]', type=click.Choice(VALID_ACTIONS))
def leak_action(db, policy_type, severity, action):
    """Configure the action taken when a critical/major/minor leak event is detected"""
    field = ACTION_FIELD_MAP[(policy_type, severity)]
    db.cfgdb.mod_entry(LEAK_CONTROL_POLICY_TABLE, LEAK_CONTROL_POLICY_KEY, {field: action})
    click.echo(f"Leak action for '{policy_type}' '{severity}' events set to '{action}'")


@liquid_cool.command('major-leak-threshold')
@clicommon.pass_db
@click.argument('num_sensors', metavar='<N>', type=click.IntRange(min=MAJOR_LEAK_MIN_SENSORS_FLOOR))
def major_leak_threshold(db, num_sensors):
    """Configure MIN-N: the number of concurrent Minor leaks at or above which the
    system is classified as MAJOR_SYSTEM_LEAK (must be >= 2)"""
    db.cfgdb.mod_entry(LEAK_CONTROL_POLICY_TABLE, LEAK_CONTROL_POLICY_KEY,
                       {MAJOR_LEAK_MIN_SENSORS_FIELD: str(num_sensors)})
    click.echo(f"Major leak threshold (MIN-N) set to '{num_sensors}'")

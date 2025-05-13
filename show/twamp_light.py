import click
import utilities_common.cli as clicommon


#
# 'twamp-light' group ("show twamp-light")
#
@click.group(cls=clicommon.AliasedGroup)
def twamp_light():
    """ Show TWAMP-Light related information """
    pass


#
# 'twamp-light session' subcommand ("show twamp-light session")
#
@twamp_light.command('session')
@click.argument('session_name', metavar='<session_name>', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@clicommon.pass_db
def twamp_light_session(db, session_name, verbose):
    """ Show TWAMP-Light session """
#    cmd = ['sudo', 'twamp-light']
    cmd = ['twamp-light']

    if session_name is not None:
        cmd += ['-n', session_name]

    clicommon.run_command(cmd, display_cmd=verbose)


#
# 'twamp-light statistics' subcommand ("show twamp-light statistics")
#
@twamp_light.command('statistics')
@click.argument('statistics_type', metavar='<statistics_type>', required=True,
                type=click.Choice(['twoway-delay', 'twoway-loss']))
@click.argument('session_name', metavar='<session_name>', required=False)
@click.option('--brief', '-b', is_flag=True, help="Enable brief output")
@click.option('--lastest_number', '-l', is_flag=False, type=click.INT,
              help="Enable lastest number set of statistics output")
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@clicommon.pass_db
def twamp_light_statistics(db, statistics_type, session_name, brief, lastest_number, verbose):
    """Show TWAMP-Light statistics"""
#    cmd = ['sudo', 'twamp-light']
    cmd = ['twamp-light']

    if statistics_type is not None:
        cmd += ['-t', statistics_type]

    if session_name is not None:
        cmd += ['-n', session_name]

    if brief is not False:
        cmd += ['-b']
    elif lastest_number is not None:
        cmd += ['-l', str(lastest_number)]

    clicommon.run_command(cmd, display_cmd=verbose)

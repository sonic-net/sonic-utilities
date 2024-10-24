import click
import utilities_common.cli as clicommon
from jsonpatch import JsonPatchConflict
from jsonpointer import JsonPointerException
from swsscommon.swsscommon import SonicV2Connector, ConfigDBConnector
from .validated_config_db_connector import ValidatedConfigDBConnector


############### PAC Configuration ##################
#
# 'dot1x' group ('config dot1x ...')
#
@click.group('dot1x')
def dot1x():
    """802.1x authentication-related configuration tasks"""
    pass

 
# 
# 'dot1x system-auth-control' command ('config dot1x system-auth-control  <status> ') 
# 
@dot1x.command('system-auth-control') 
@click.pass_context 
@click.argument('status', metavar='<status>', required=True, type=click.Choice(['enable', 'disable'])) 
def add_system_auth_control(ctx, status): 
    """Add dot1x system-auth-control related  configutation""" 
 
    config_db = ValidatedConfigDBConnector(ConfigDBConnector()) 
    config_db.connect() 
 
    try: 
        config_db.mod_entry('HOSTAPD_GLOBAL_CONFIG_TABLE', ('GLOBAL'), {'dot1x_system_auth_control': "true" if status == 'enable' else "false"}) 
 
    except ValueError as e: 
        ctx.fail("Invalid ConfigDB. Error: {}".format(e)) 



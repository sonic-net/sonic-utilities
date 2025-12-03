import click

def get_attr_full_name(ctx, threshold):
    attr = 'dash_'

    if ctx.obj["crm"].addr_family:
        attr += ctx.obj["crm"].addr_family + '_'

    if ctx.obj["crm"].direction:
        attr += ctx.obj["crm"].direction + '_'

    attr += ctx.obj["crm"].res_type + '_' + threshold
    return attr

@click.command('type')
@click.argument('value', type=click.Choice(['percentage', 'used', 'free']))
@click.pass_context
def config_dash_type(ctx, value):
    """CRM threshold type configuration"""
    ctx.obj["crm"].config(get_attr_full_name(ctx, 'threshold_type'), value)

@click.command('low')
@click.argument('value', type=click.INT)
@click.pass_context
def config_dash_low(ctx, value):
    """CRM low threshold configuration"""
    ctx.obj["crm"].config(get_attr_full_name(ctx, 'low_threshold'), value)

@click.command('high')
@click.argument('value', type=click.INT)
@click.pass_context
def config_dash_high(ctx, value):
    """CRM high threshold configuration"""
    ctx.obj["crm"].config(get_attr_full_name(ctx, 'high_threshold'), value)

def group_add_thresholds(group):
    group.add_command(config_dash_type)
    group.add_command(config_dash_low)
    group.add_command(config_dash_high)

@click.group('dash')
@click.pass_context
def config_dash(ctx):
    """CRM configuration for DASH resource"""
    pass

@config_dash.group('ipv4')
@click.pass_context
def config_dash_ipv4(ctx):
    """DASH CRM resource IPv4 address family"""
    ctx.obj["crm"].addr_family = 'ipv4'

@config_dash.group('ipv6')
@click.pass_context
def config_dash_ipv6(ctx):
    """DASH CRM resource IPv6 address family"""
    ctx.obj["crm"].addr_family = 'ipv6'

@click.group('inbound')
@click.pass_context
def config_dash_inbound(ctx):
    """DASH CRM inbound direction resource"""
    ctx.obj["crm"].direction = 'inbound'

config_dash_ipv4.add_command(config_dash_inbound)
config_dash_ipv6.add_command(config_dash_inbound)

@click.group('outbound')
@click.pass_context
def config_dash_outbound(ctx):
    """DASH CRM outbound direction resource"""
    ctx.obj["crm"].direction = 'outbound'

config_dash_ipv4.add_command(config_dash_outbound)
config_dash_ipv6.add_command(config_dash_outbound)

@config_dash.group('eni')
@click.pass_context
def config_dash_eni(ctx):
    """CRM configuration for DASH ENI resource"""
    ctx.obj["crm"].res_type = 'eni'

group_add_thresholds(config_dash_eni)

@config_dash.group('eni-ether-address')
@click.pass_context
def config_dash_eni_ether_address_map(ctx):
    """CRM configuration for DASH ENI ETHER address map entry"""
    ctx.obj["crm"].res_type = 'eni_ether_address_map'

group_add_thresholds(config_dash_eni_ether_address_map)

@config_dash.group('vnet')
@click.pass_context
def config_dash_vnet(ctx):
    """CRM configuration for DASH VNET resource"""
    ctx.obj["crm"].res_type = 'vnet'

group_add_thresholds(config_dash_vnet)

@click.group('routing')
@click.pass_context
def config_dash_routing(ctx):
    """CRM configuration for DASH inbound routes"""
    ctx.obj["crm"].res_type = 'routing'

group_add_thresholds(config_dash_routing)
config_dash_inbound.add_command(config_dash_routing)
config_dash_outbound.add_command(config_dash_routing)

@click.group('pa-validation')
@click.pass_context
def config_dash_pa_validation(ctx):
    """CRM configuration for DASH PA validation entries"""
    ctx.obj["crm"].res_type = 'pa_validation'

group_add_thresholds(config_dash_pa_validation)
config_dash_ipv4.add_command(config_dash_pa_validation)
config_dash_ipv6.add_command(config_dash_pa_validation)

@click.group('ca-to-pa')
@click.pass_context
def config_dash_ca_to_pa(ctx):
    """CRM configuration for DASH  CA to PA entries"""
    ctx.obj["crm"].res_type = 'ca_to_pa'

group_add_thresholds(config_dash_ca_to_pa)
config_dash_outbound.add_command(config_dash_ca_to_pa)

@click.group('acl')
@click.pass_context
def config_dash_acl(ctx):
    """DASH CRM ACL resource"""

config_dash_ipv4.add_command(config_dash_acl)
config_dash_ipv6.add_command(config_dash_acl)

@click.group('group')
@click.pass_context
def config_dash_acl_group(ctx):
    """CRM configuration for DASH ACL group entries"""
    ctx.obj["crm"].res_type = 'acl_group'

group_add_thresholds(config_dash_acl_group)
config_dash_acl.add_command(config_dash_acl_group)

@click.group('rule')
@click.pass_context
def config_dash_acl_rule(ctx):
    """CRM configuration for DASH ACL rule entries"""
    ctx.obj["crm"].res_type = 'acl_rule'

group_add_thresholds(config_dash_acl_rule)
config_dash_acl.add_command(config_dash_acl_rule)


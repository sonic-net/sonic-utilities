import click

def show_resource(ctx, resource):
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds(resource)
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_resources(resource)

@click.group('dash')
@click.pass_context
def show_dash(ctx):
    """Show CRM information for DASH"""
    pass

@show_dash.group('ipv4')
@click.pass_context
def show_dash_ipv4(ctx):
    """Show CRM information for IPv4 address family"""
    ctx.obj["crm"].addr_family = 'ipv4'

@show_dash.group('ipv6')
@click.pass_context
def show_dash_ipv6(ctx):
    """Show CRM information for IPv6 address family"""
    ctx.obj["crm"].addr_family = 'ipv6'

@click.group('inbound')
@click.pass_context
def show_dash_inbound(ctx):
    """Show CRM information for inbound direction"""
    ctx.obj["crm"].direction = 'inbound'

show_dash_ipv4.add_command(show_dash_inbound)
show_dash_ipv6.add_command(show_dash_inbound)

@click.group('outbound')
@click.pass_context
def show_dash_outbound(ctx):
    """Show CRM information for outbound direction"""
    ctx.obj["crm"].direction = 'outbound'

show_dash_ipv4.add_command(show_dash_outbound)
show_dash_ipv6.add_command(show_dash_outbound)

@show_dash.command('vnet')
@click.pass_context
def show_dash_vnet(ctx):
    """Show CRM information for VNETs"""
    show_resource(ctx, 'dash_vnet')

@show_dash.command('eni')
@click.pass_context
def show_dash_eni(ctx):
    """Show CRM information for ENIs"""
    show_resource(ctx, 'dash_eni')

@show_dash.command('eni-ether-address')
@click.pass_context
def show_dash_eni_ether_address_map(ctx):
    """Show CRM information for ENI ETHER address map entries"""
    show_resource(ctx, 'dash_eni_ether_address_map')

@click.command('routing')
@click.pass_context
def show_dash_routing(ctx):
    """Show CRM information for inbound routes"""
    resource = f'dash_{ctx.obj["crm"].addr_family}_{ctx.obj["crm"].direction}_routing'
    show_resource(ctx, resource)

show_dash_inbound.add_command(show_dash_routing)
show_dash_outbound.add_command(show_dash_routing)

@click.command('pa-validation')
@click.pass_context
def show_dash_pa_validation(ctx):
    """Show CRM information for PA validation entries"""
    resource = f'dash_{ctx.obj["crm"].addr_family}_pa_validation'
    show_resource(ctx, resource)

show_dash_ipv4.add_command(show_dash_pa_validation)
show_dash_ipv6.add_command(show_dash_pa_validation)

@click.command('ca-to-pa')
@click.pass_context
def show_dash_ca_to_pa(ctx):
    """Show CRM information for CA to PA entries"""
    resource = f'dash_{ctx.obj["crm"].addr_family}_{ctx.obj["crm"].direction}_ca_to_pa'
    show_resource(ctx, resource)

show_dash_outbound.add_command(show_dash_ca_to_pa)

@click.group('acl')
@click.pass_context
def show_dash_acl(ctx):
    """Show CRM information for ACL resources"""

show_dash_ipv4.add_command(show_dash_acl)
show_dash_ipv6.add_command(show_dash_acl)

@click.command('group')
@click.pass_context
def show_dash_acl_group(ctx):
    """Show CRM information for ACL group entries"""
    resource = f'dash_{ctx.obj["crm"].addr_family}_acl_group'
    show_resource(ctx, resource)

show_dash_acl.add_command(show_dash_acl_group)

@click.command('rule')
@click.pass_context
def show_dash_acl_rule(ctx):
    """Show CRM information for ACL rule entries"""
    resource = f'dash_{ctx.obj["crm"].addr_family}_acl_rule'
    if ctx.obj["crm"].cli_mode == 'thresholds':
        ctx.obj["crm"].show_thresholds(resource)
    elif ctx.obj["crm"].cli_mode == 'resources':
        ctx.obj["crm"].show_acl_group_resources(resource)

show_dash_acl.add_command(show_dash_acl_rule)

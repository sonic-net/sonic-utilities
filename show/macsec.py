import click
import utilities_common.cli as clicommon

#
# 'macsec' group ("show macsec ...")
#
@click.group(cls=clicommon.AliasedGroup)
def macsec():
    """Show MACsec information"""
    pass

@macsec.command()
@click.argument('interfacename', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def connections(interfacename, verbose):
    """Show MACsec connections"""

    cmd = "macsecshow connections"

    if interfacename is not None:
        if clicommon.get_interface_naming_mode() == "alias":
            iface_alias_converter = clicommon.InterfaceAliasConverter(db)
            interfacename = iface_alias_converter.alias_to_name(interfacename)

        cmd += " {}".format(interfacename)

    clicommon.run_command(cmd, display_cmd=verbose)

@macsec.command()
@click.argument('interfacename', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def statistics(interfacename, verbose):
    """Show MACsec statistics"""

    cmd = "macsecshow statistics"

    if interfacename is not None:
        if clicommon.get_interface_naming_mode() == "alias":
            iface_alias_converter = clicommon.InterfaceAliasConverter(db)
            interfacename = iface_alias_converter.alias_to_name(interfacename)

        cmd += " {}".format(interfacename)

    clicommon.run_command(cmd, display_cmd=verbose)

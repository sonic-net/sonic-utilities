#!/usr/bin/env python3
#
# main.py
#
# Command-line utility for interacting with platform components within SONiC
#

try:
    import os
    import click

    from .lib import PlatformDataProvider, ComponentStatusProvider, ComponentUpdateProvider
    from .lib import URL, SquashFs, FWPackage
    from .log import LogHelper
except ImportError as e:
    raise ImportError("Required module not found: {}".format(str(e)))

# ========================= Constants ==========================================

VERSION = '2.0.0.0'

CHASSIS_NAME_CTX_KEY = "chassis_name"
MODULE_NAME_CTX_KEY = "module_name"
COMPONENT_CTX_KEY = "component"
COMPONENT_PATH_CTX_KEY = "component_path"
URL_CTX_KEY = "url"

TAB = "    "
PATH_SEPARATOR = "/"
IMAGE_NEXT = "next"
HELP = "?"

EXIT_SUCCESS = 0
EXIT_FAILURE = 1

ROOT_UID = 0

# ========================= Variables ==========================================

pdp = PlatformDataProvider()
log_helper = LogHelper()

# ========================= Helper functions ===================================

def cli_show_help(ctx):
    click.echo(ctx.get_help())
    ctx.exit(EXIT_SUCCESS)


def cli_abort(ctx, msg):
    click.echo("Error: " + msg + ". Aborting...")
    ctx.abort()


def cli_exit(ctx, msg):
    log_helper.print_info(msg)
    ctx.exit(EXIT_SUCCESS)


def cli_init(ctx):
    if os.geteuid() != ROOT_UID:
        cli_abort(ctx, "Root privileges are required")

    ctx.ensure_object(dict)

# ========================= CLI commands and groups ============================

# 'fwutil' command main entrypoint
@click.group()
@click.pass_context
def cli(ctx):
    """fwutil - Command-line utility for interacting with platform components"""
    cli_init(ctx)


# 'install' group
@cli.group()
@click.pass_context
def install(ctx):
    """Install platform firmware"""
    ctx.obj[COMPONENT_PATH_CTX_KEY] = [ ]


# 'update' group
@cli.group()
@click.pass_context
def update(ctx):
    """Update platform firmware"""
    ctx.obj[COMPONENT_PATH_CTX_KEY] = [ ]


# 'all_update' group
@click.group()
@click.pass_context
def all_update(ctx):
    """Auto-update platform firmware"""
    pass


def chassis_handler(ctx):
    ctx.obj[CHASSIS_NAME_CTX_KEY] = pdp.chassis.get_name()
    ctx.obj[COMPONENT_PATH_CTX_KEY].append(pdp.chassis.get_name())


# 'chassis' subgroup
@click.group()
@click.pass_context
def chassis_install(ctx):
    """Install chassis firmware"""
    chassis_handler(ctx)


# 'chassis' subgroup
@click.group()
@click.pass_context
def chassis_update(ctx):
    """Update chassis firmware"""
    chassis_handler(ctx)


def module_handler(ctx, module_name):
    ctx.obj[MODULE_NAME_CTX_KEY] = module_name
    ctx.obj[COMPONENT_PATH_CTX_KEY].append(pdp.chassis.get_name())
    ctx.obj[COMPONENT_PATH_CTX_KEY].append(module_name)


def validate_module(ctx, param, value):
    if value == HELP:
        cli_show_help(ctx)

    if not pdp.is_modular_chassis():
        ctx.fail("Unsupported platform: non modular chassis.")

    if value not in pdp.module_component_map:
        ctx.fail("Invalid value for \"{}\": Module \"{}\" does not exist.".format(param.metavar, value))

    return value


# 'module' subgroup
@click.group()
@click.argument('module_name', metavar='<module_name>', callback=validate_module)
@click.pass_context
def module_install(ctx, module_name):
    """Install module firmware"""
    module_handler(ctx, module_name)


# 'module' subgroup
@click.group()
@click.argument('module_name', metavar='<module_name>', callback=validate_module)
@click.pass_context
def module_update(ctx, module_name):
    """Update module firmware"""
    module_handler(ctx, module_name)


def component_handler(ctx, component_name):
    ctx.obj[COMPONENT_PATH_CTX_KEY].append(component_name)


def validate_component(ctx, param, value):
    if value == HELP:
        cli_show_help(ctx)

    if CHASSIS_NAME_CTX_KEY in ctx.obj:
        chassis_name = ctx.obj[CHASSIS_NAME_CTX_KEY]
        if value in pdp.chassis_component_map[chassis_name]:
            ctx.obj[COMPONENT_CTX_KEY] = pdp.chassis_component_map[chassis_name][value]
            return value

    if MODULE_NAME_CTX_KEY in ctx.obj:
        module_name = ctx.obj[MODULE_NAME_CTX_KEY]
        if value in pdp.module_component_map[module_name]:
            ctx.obj[COMPONENT_CTX_KEY] = pdp.module_component_map[module_name][value]
            return value

    ctx.fail("Invalid value for \"{}\": Component \"{}\" does not exist.".format(param.metavar, value))


# 'component' subgroup
@click.group()
@click.argument('component_name', metavar='<component_name>', callback=validate_component)
@click.pass_context
def component_install(ctx, component_name):
    """Install component firmware"""
    component_handler(ctx, component_name)


# 'component' subgroup
@click.group()
@click.argument('component_name', metavar='<component_name>', callback=validate_component)
@click.pass_context
def component_update(ctx, component_name):
    """Update component firmware"""
    component_handler(ctx, component_name)


def install_fw(ctx, fw_path):
    component = ctx.obj[COMPONENT_CTX_KEY]
    component_path = PATH_SEPARATOR.join(ctx.obj[COMPONENT_PATH_CTX_KEY])

    status = False

    try:
        click.echo("Installing firmware:")
        click.echo(TAB + fw_path)
        log_helper.log_fw_install_start(component_path, fw_path)
        status = component.install_firmware(fw_path)
        log_helper.log_fw_install_end(component_path, fw_path, status)
    except KeyboardInterrupt:
        log_helper.log_fw_install_end(component_path, fw_path, False, "Keyboard interrupt")
        raise
    except Exception as e:
        log_helper.log_fw_install_end(component_path, fw_path, False, e)
        cli_abort(ctx, str(e))

    if not status:
        log_helper.print_error("Firmware install failed")
        ctx.exit(EXIT_FAILURE)


def download_fw(ctx, url):
    filename, headers = None, None

    component_path = PATH_SEPARATOR.join(ctx.obj[COMPONENT_PATH_CTX_KEY])

    try:
        click.echo("Downloading firmware:")
        log_helper.log_fw_download_start(component_path, str(url))
        filename, headers = url.retrieve()
        log_helper.log_fw_download_end(component_path, str(url), True)
    except KeyboardInterrupt:
        log_helper.log_fw_download_end(component_path, str(url), False, "Keyboard interrupt")
        raise
    except Exception as e:
        log_helper.log_fw_download_end(component_path, str(url), False, e)
        cli_abort(ctx, str(e))

    return filename


def validate_fw(ctx, param, value):
    if value == HELP:
        cli_show_help(ctx)

    url = URL(value)

    if not url.is_url():
        path = click.Path(exists=True)
        path.convert(value, param, ctx)
    else:
        ctx.obj[URL_CTX_KEY] = url

    return value


# 'fw' subcommand
@component_install.command(name='fw')
@click.option('-y', '--yes', 'yes', is_flag=True, show_default=True, help="Assume \"yes\" as answer to all prompts and run non-interactively")
@click.argument('fw_path', metavar='<fw_path>', callback=validate_fw)
@click.pass_context
def fw_install(ctx, yes, fw_path):
    """Install firmware from local path or URL"""
    url = None

    try:
        if URL_CTX_KEY in ctx.obj:
            url = ctx.obj[URL_CTX_KEY]
            fw_path = download_fw(ctx, url)

        component = ctx.obj[COMPONENT_CTX_KEY]

        notification = component.get_firmware_update_notification(fw_path)
        if notification:
            log_helper.print_warning(notification)

        if not yes:
            click.confirm("New firmware will be installed, continue?", abort=True)

        install_fw(ctx, fw_path)
    finally:
        if url is not None and os.path.exists(fw_path):
            os.remove(fw_path)


# 'fw' subcommand
@component_update.command(name='fw')
@click.option('-y', '--yes', 'yes', is_flag=True, show_default=True, help="Assume \"yes\" as answer to all prompts and run non-interactively")
@click.option('-f', '--force', 'force', is_flag=True, show_default=True, help="Update firmware regardless the current version")
@click.option('-i', '--image', 'image', type=click.Choice(["current", "next"]), default="current", show_default=True, help="Update firmware using current/next SONiC image")
@click.pass_context
def fw_update(ctx, yes, force, image):
    """Update firmware from SONiC image"""
    if CHASSIS_NAME_CTX_KEY in ctx.obj:
        chassis_name = ctx.obj[CHASSIS_NAME_CTX_KEY]
        module_name = None
    elif MODULE_NAME_CTX_KEY in ctx.obj:
        chassis_name = pdp.chassis.get_name()
        module_name = ctx.obj[MODULE_NAME_CTX_KEY]

    component_name = ctx.obj[COMPONENT_CTX_KEY].get_name()

    try:
        squashfs = None

        try:
            if image == IMAGE_NEXT:
                squashfs = SquashFs()

                if squashfs.is_next_boot_set():
                    fs_path = squashfs.mount_next_image_fs()
                    cup = ComponentUpdateProvider(fs_path)
                else:
                    log_helper.print_warning("Next boot is set to current: fallback to defaults")
                    cup = ComponentUpdateProvider()
            else:
                cup = ComponentUpdateProvider()

            if not cup.is_firmware_update_available(chassis_name, module_name, component_name):
                cli_exit(ctx, "Firmware update is not available")

            if not (cup.is_firmware_update_required(chassis_name, module_name, component_name) or force):
                cli_exit(ctx, "Firmware is up-to-date")

            notification = cup.get_notification(chassis_name, module_name, component_name)
            if notification:
                log_helper.print_warning(notification)

            if not yes:
                click.confirm("New firmware will be installed, continue?", abort=True)

            cup.update_firmware(chassis_name, module_name, component_name)
        finally:
            if squashfs is not None:
                squashfs.umount_next_image_fs()
    except click.exceptions.Abort:
        ctx.abort()
    except click.exceptions.Exit as e:
        ctx.exit(e.exit_code)
    except Exception as e:
        cli_abort(ctx, str(e))


# 'fw' subcommand
@all_update.command(name='fw')
@click.option('-i', '--image', 'image', type=click.Choice(["current", "next"]), default="current", show_default=True, help="Update firmware using current/next SONiC image")
@click.option('-f', '--fw_image', 'fw_image', help="Custom FW package path")
@click.option('-b', '--boot', 'boot', type=click.Choice(["any", "cold", "fast", "warm", "none"]), default="none", show_default=True, help="Necessary boot option after the firmware update")
@click.pass_context
def fw_auto_update(ctx, boot, image=None, fw_image=None):
    """Update firmware from SONiC image"""
    squashfs = None
    fwpackage = None
    cup = None

    try:

        if fw_image is not None:
            fwpackage = FWPackage(fw_image)

            if fwpackage.untar_fwpackage():
                fs_path = fwpackage.get_fw_package_path()
                cup = ComponentUpdateProvider(fs_path)
            else:
                log_helper.print_warning("Cannot open the firmware package")
        else:
            if image == IMAGE_NEXT:
                squashfs = SquashFs()

                if squashfs.is_next_boot_set():
                    fs_path = squashfs.mount_next_image_fs()
                    cup = ComponentUpdateProvider(fs_path)
                else:
                    log_helper.print_warning("Next boot is set to current: fallback to defaults")
                    cup = ComponentUpdateProvider()
            else:
                cup = ComponentUpdateProvider()

        if cup is not None:
            au_component_list = cup.get_update_available_components()
            if au_component_list:
                if cup.is_capable_auto_update(boot):
                    for au_component in au_component_list:
                        cup.auto_update_firmware(au_component, boot)
                    log_helper.print_warning("All firmware auto-update has been performed")
                    click.echo("All firmware auto-update has been performed")
            else:
                log_helper.print_warning("All components: {}".format(cup.FW_STATUS_UP_TO_DATE))
        else:
            log_helper.print_warning("compoenet update package is not available")
    finally:
        if squashfs is not None:
            squashfs.umount_next_image_fs()
        if fwpackage is not None:
            fwpackage.cleanup_tmp_fwpackage()


# 'show' subgroup
@cli.group()
def show():
    """Display platform info"""
    pass


# 'updates' subcommand
@show.command()
@click.option('-i', '--image', 'image', type=click.Choice(["current", "next"]), default="current", show_default=True, help="Show updates using current/next SONiC image")
@click.option('-f', '--fw_image', 'fw_image', help="Custom FW package path")
@click.pass_context
def updates(ctx, image=None, fw_image=None):
    """Show available updates"""
    try:
        squashfs = None
        fwpackage = None
        cup = None

        try:
            if fw_image is not None:
                fwpackage = FWPackage(fw_image)

                if fwpackage.untar_fwpackage():
                    fs_path = fwpackage.get_fw_package_path()
                    cup = ComponentUpdateProvider(fs_path)
                else:
                    log_helper.print_warning("Cannot open the firmware package")
            else:
                if image == IMAGE_NEXT:
                    squashfs = SquashFs()

                    if squashfs.is_next_boot_set():
                        fs_path = squashfs.mount_next_image_fs()
                        cup = ComponentUpdateProvider(fs_path)
                    else:
                        log_helper.print_warning("Next boot is set to current: fallback to defaults")
                        cup = ComponentUpdateProvider()
                else:
                    cup = ComponentUpdateProvider()

            status = cup.get_status()
            if status is not None:
                click.echo(status)
            else:
                log_helper.print_info("Firmware updates are not available")
        finally:
            if squashfs is not None:
                squashfs.umount_next_image_fs()
    except Exception as e:
        cli_abort(ctx, str(e))


# 'status' subcommand
@show.command()
@click.pass_context
def status(ctx):
    """Show platform components status"""
    try:
        csp = ComponentStatusProvider()
        click.echo(csp.get_status())
    except Exception as e:
        cli_abort(ctx, str(e))


# 'updates' subcommand
@show.command(name='update-all-status')
@click.pass_context
def update_all_status(ctx):
    """Show platform components update all status"""
    try:
        csp = ComponentStatusProvider()
        click.echo(csp.get_au_status())
    except Exception as e:
        cli_abort(ctx, str(e))


# 'version' subcommand
@show.command()
def version():
    """Show utility version"""
    click.echo("fwutil version {0}".format(VERSION))

install.add_command(chassis_install, name='chassis')
install.add_command(module_install, name='module')

update.add_command(chassis_update, name='chassis')
update.add_command(module_update, name='module')
update.add_command(all_update, name='all')

chassis_install.add_command(component_install, name='component')
module_install.add_command(component_install, name='component')

chassis_update.add_command(component_update, name='component')
module_update.add_command(component_update, name='component')

# ========================= CLI entrypoint =====================================

if __name__ == '__main__':
    cli()

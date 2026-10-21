#!/usr/bin/env python3
#
# main.py
#
# Command-line utility for interacting with PCIE in SONiC
#

try:
    import os
    import re
    import sys
    from collections import OrderedDict

    import click
    from sonic_py_common import device_info, logger
    from swsscommon.swsscommon import SonicV2Connector
    from tabulate import tabulate
    import utilities_common.cli as clicommon
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))

VERSION = '1.0'

SYSLOG_IDENTIFIER = "pcieutil"
PLATFORM_SPECIFIC_MODULE_NAME = "pcieutil"

# Global platform-specific psuutil class instance
platform_pcieutil = None
platform_path = None

log = logger.Logger(SYSLOG_IDENTIFIER)


def print_result(name, result):
    string = "PCI Device:  {} ".format(name)
    length = 105-len(string)
    sys.stdout.write(string)
    for i in range(int(length)):
        sys.stdout.write("-")
    click.echo(' [%s]' % result)

# ==================== Methods for initialization ====================

# Loads platform specific psuutil module from source


def load_platform_pcieutil():
    global platform_pcieutil
    global platform_path

    # Load platform module from source
    platform_path, _ = device_info.get_paths_to_platform_and_hwsku_dirs()
    try:
        from sonic_platform.pcie import Pcie
        platform_pcieutil = Pcie(platform_path)
    except ImportError as e:
        log.log_warning("Failed to load platform Pcie module. Warning : {}, fallback to load Pcie common utility.".format(str(e)))
        try:
            from sonic_platform_base.sonic_pcie.pcie_common import PcieUtil
            platform_pcieutil = PcieUtil(platform_path)
        except ImportError as e:
            log.log_error("Failed to load default PcieUtil module. Error : {}".format(str(e)), True)
            raise e


# ==================== CLI commands and groups ====================


# This is our main entrypoint - the main 'psuutil' command
@click.group()
def cli():
    """pcieutil - Command line utility for checking pci device"""
    if os.geteuid() != 0:
        click.echo("Root privileges are required for this operation")
        sys.exit(1)

    # Load platform-specific psuutil class
    load_platform_pcieutil()

# 'version' subcommand


@cli.command()
def version():
    """Display version info"""
    click.echo("pcieutil version {0}".format(VERSION))

# show the platform PCIE info


def print_test_title(testname):
    click.echo("{name:=^80s}".format(name=testname))

#  Show PCIE lnkSpeed


@cli.command()
def show():
    '''Display PCIe Device '''
    testname = "Display PCIe Device"
    print_test_title(testname)
    resultInfo = platform_pcieutil.get_pcie_device()
    for item in resultInfo:
        Bus = item["bus"]
        Dev = item["dev"]
        Fn = item["fn"]
        Name = item["name"]
        Id = item["id"]
        click.echo("bus:dev.fn %s:%s.%s - dev_id=0x%s, %s" % (Bus, Dev, Fn, Id, Name))


# PCIe AER stats helpers

aer_fields = {
    "correctable": ['RxErr', 'BadTLP', 'BadDLLP', 'Rollover', 'Timeout', 'NonFatalErr', 'CorrIntErr', 'HeaderOF', 'TOTAL_ERR_COR'],
    "fatal": ['Undefined', 'DLP', 'SDES', 'TLP', 'FCP', 'CmpltTO', 'CmpltAbrt', 'UnxCmplt', 'RxOF', 'MalfTLP', 'ECRC', 'UnsupReq',
              'ACSViol', 'UncorrIntErr', 'BlockedTLP', 'AtomicOpBlocked', 'TLPBlockedErr', 'TOTAL_ERR_FATAL'],
    "non_fatal": ['Undefined', 'DLP', 'SDES', 'TLP', 'FCP', 'CmpltTO', 'CmpltAbrt', 'UnxCmplt', 'RxOF', 'MalfTLP', 'ECRC', 'UnsupReq',
                  'ACSViol', 'UncorrIntErr', 'BlockedTLP', 'AtomicOpBlocked', 'TLPBlockedErr', 'TOTAL_ERR_NONFATAL']
}


class PcieDevice(click.ParamType):
    name = "<Bus>:<Dev>.<Fn>"

    def convert(self, value, param, ctx):
        match = re.match(r'([0-9A-Fa-f]{1,2}):([0-9A-Fa-f]{1,2})\.([0-9A-Fa-f])', value)

        if not match:
            self.fail('{} is not in <Bus>:<Dev>.<Fn> format'.format(value), param, ctx)

        Bus, Dev, Fn = [int(val, 16) for val in match.groups()]
        if Bus > 255:
            self.fail('Invalid Bus number', param, ctx)

        if Dev > 31:
            self.fail('Invalid Dev number', param, ctx)

        if Fn > 7:
            self.fail('Invalid Fn number', param, ctx)

        return "%02x:%02x.%d" % (Bus, Dev, Fn)


_pcie_aer_click_options = [
    click.Option(['-d', '--device', 'device_key'],
                 type=PcieDevice(),
                 help="Display stats only for the specified device"),
    click.Option(['-v', '--verbose'],
                 is_flag=True,
                 help="Display all stats")
]


class PcieAerCommand(click.Command):
    '''This subclass of click.Command provides common options, help
    and short help text for PCIe AER commands'''

    def __init__(self, *args, **kwargs):
        super(PcieAerCommand, self).__init__(*args, **kwargs)
        self.params = _pcie_aer_click_options

    def format_help_text(self, ctx, formatter):
        formatter.write_paragraph()
        with formatter.indentation():
            formatter.write_text("Show {} PCIe AER attributes".format(self.name.replace("_", "-")))
            formatter.write_text("(Default: Display only non-zero attributes)")

    def get_short_help_str(self, limit):
        return "Show {} PCIe AER attributes".format(self.name.replace("_", "-"))


def pcie_aer_display(ctx, severity):
    device_key = ctx.params['device_key']
    no_zero = not ctx.params['verbose']
    header = ["AER - " + severity.upper().replace("_", "")]
    fields = aer_fields[severity]
    pcie_dev_list = list()
    dev_found = False

    statedb = SonicV2Connector()
    statedb.connect(statedb.STATE_DB)

    table = OrderedDict()
    for field in fields:
        table[field] = [field]

    if device_key:
        pcie_dev_list = ["PCIE_DEVICE|%s" % device_key]
    else:
        keys = statedb.keys(statedb.STATE_DB, "PCIE_DEVICE|*")
        if keys:
            pcie_dev_list = sorted(keys)

    for pcie_dev_key in pcie_dev_list:
        aer_attribute = statedb.get_all(statedb.STATE_DB, pcie_dev_key)
        if not aer_attribute:
            continue

        if device_key:
            dev_found = True

        if no_zero and all(val == '0' for key, val in aer_attribute.items() if key.startswith(severity)):
            continue

        pcie_dev = pcie_dev_key.split("|")[1]
        Id = aer_attribute['id']

        # Tabulate Header
        device_name = "%s\n%s" % (pcie_dev, Id)
        header.append(device_name)

        # Tabulate Row
        for field in fields:
            key = severity + "|" + field
            table[field].append(aer_attribute.get(key, 'NA'))

    if device_key and not dev_found:
        ctx.exit("Device not found in DB")

    # Strip fields with no non-zero value
    if no_zero:
        for field in fields:
            if all(val == '0' for val in table[field][1:]):
                del table[field]

    if not (no_zero and (len(header) == 1)):
        if ctx.obj:
            click.echo("")

        click.echo(tabulate(list(table.values()), header, tablefmt="grid"))
        ctx.obj = True


# Show PCIe AER status
@cli.group(cls=clicommon.AliasedGroup)
@click.pass_context
def pcie_aer(ctx):
    '''Display PCIe AER status'''
    # Set True to insert a line between severities in 'all' context
    ctx.obj = False


@pcie_aer.command(cls=PcieAerCommand)
@click.pass_context
def correctable(ctx, device_key, verbose):
    '''Show correctable PCIe AER attributes'''
    pcie_aer_display(ctx, "correctable")


@pcie_aer.command(cls=PcieAerCommand)
@click.pass_context
def fatal(ctx, device_key, verbose):
    '''Show fatal PCIe AER attributes'''
    pcie_aer_display(ctx, "fatal")


@pcie_aer.command(cls=PcieAerCommand)
@click.pass_context
def non_fatal(ctx, device_key, verbose):
    '''Show non-fatal PCIe AER attributes'''
    pcie_aer_display(ctx, "non_fatal")


@pcie_aer.command(name='all', cls=PcieAerCommand)
@click.pass_context
def all_errors(ctx, device_key, verbose):
    '''Show all PCIe AER attributes'''
    pcie_aer_display(ctx, "correctable")
    pcie_aer_display(ctx, "fatal")
    pcie_aer_display(ctx, "non_fatal")


#  Show PCIE Vendor ID and Device ID
@cli.command()
def check():
    '''Check PCIe Device '''
    testname = "PCIe Device Check"
    err = 0
    print_test_title(testname)
    resultInfo = platform_pcieutil.get_pcie_check()
    for item in resultInfo:
        if item["result"] == "Passed":
            print_result(item["name"], "Passed")
        else:
            print_result(item["name"], "Failed")
            log.log_warning("PCIe Device: " + item["name"] + " Not Found")
            err += 1
    if err:
        click.echo("PCIe Device Checking All Test ----------->>> FAILED")
    else:
        click.echo("PCIe Device Checking All Test ----------->>> PASSED")


@cli.command()
@click.confirmation_option(prompt="Are you sure to overwrite config file pcie.yaml with current pcie device info?")
def generate():
    '''Generate config file with current pci device'''
    platform_pcieutil.dump_conf_yaml()
    click.echo("Generated config file '{}/pcie.yaml'".format(platform_path))


if __name__ == '__main__':
    cli()

import argparse
import functools

import click
import netifaces
from natsort import natsorted
from sonic_py_common import multi_asic, device_info
from utilities_common import constants
from utilities_common.general import load_db_config
import subprocess
import json


class MultiAsic(object):

    def __init__(
        self, display_option=constants.DISPLAY_ALL, namespace_option=None,
        db=None
    ):
        # Load database config files
        load_db_config()
        self.namespace_option = namespace_option
        self.display_option = display_option
        self.current_namespace = None
        self.is_multi_asic = multi_asic.is_multi_asic()
        self.db = db

    def get_display_option(self):
        return self.display_option

    def is_object_internal(self, object_type, cli_object):
        '''
        The function checks if a CLI object is internal and returns true or false.
        Internal objects are port or portchannel which are connected to other
        ports or portchannels within a multi ASIC device.

        For single asic, this function is not applicable
        '''
        if object_type == constants.PORT_OBJ:
            return multi_asic.is_port_internal(cli_object, self.current_namespace)
        elif object_type == constants.PORT_CHANNEL_OBJ:
            return multi_asic.is_port_channel_internal(cli_object, self.current_namespace)
        elif object_type == constants.BGP_NEIGH_OBJ:
            return multi_asic.is_bgp_session_internal(cli_object, self.current_namespace)

    def skip_display(self, object_type, cli_object):
        '''
        The function determines if the passed cli_object has to be displayed or not.
        returns true if the display_option is external and  the cli object is internal.
        returns false, if the cli option is all or if it the platform is single ASIC.

        '''
        if not self.is_multi_asic and not device_info.is_chassis():
            return False
        if self.get_display_option() == constants.DISPLAY_ALL:
            return False
        return self.is_object_internal(object_type, cli_object)

    def get_ns_list_based_on_options(self):
        ns_list = []
        if not self.is_multi_asic:
            return [constants.DEFAULT_NAMESPACE]
        else:
            namespaces = multi_asic.get_all_namespaces()
            if self.namespace_option is None:
                if self.get_display_option() == constants.DISPLAY_ALL:
                    ns_list = namespaces['front_ns'] + namespaces['back_ns'] + namespaces['fabric_ns']
                else:
                    ns_list = namespaces['front_ns']
            else:
                if self.namespace_option not in namespaces['front_ns'] and \
                        self.namespace_option not in namespaces['back_ns'] and \
                        self.namespace_option not in namespaces['fabric_ns']:
                    raise ValueError(
                        'Unknown Namespace {}'.format(self.namespace_option))
                ns_list = [self.namespace_option]
        return ns_list


def multi_asic_ns_choices():
    if not multi_asic.is_multi_asic():
        return [constants.DEFAULT_NAMESPACE]
    choices = multi_asic.get_namespace_list()
    return choices


def multi_asic_display_choices():
    return [constants.DISPLAY_ALL, constants.DISPLAY_EXTERNAL]


def multi_asic_display_default_option():
    if not multi_asic.is_multi_asic() and not device_info.is_chassis():
        return constants.DISPLAY_ALL
    else:
        return constants.DISPLAY_EXTERNAL


_multi_asic_click_option_display = click.option('--display',
                                                '-d', 'display',
                                                default=multi_asic_display_default_option(),
                                                show_default=True,
                                                type=click.Choice(multi_asic_display_choices()),
                                                help='Show internal interfaces')
_multi_asic_click_option_namespace = click.option('--namespace',
                                                  '-n', 'namespace',
                                                  default=None,
                                                  type=click.Choice(multi_asic_ns_choices()),
                                                  show_default=True,
                                                  help='Namespace name or all')
_multi_asic_click_options = [
      _multi_asic_click_option_display,
      _multi_asic_click_option_namespace,
]

def multi_asic_namespace_validation_callback(ctx, param, value):
    if not multi_asic.is_multi_asic:
        click.echo("-n/--namespace is not available for single asic")
        ctx.abort()
    return value

def multi_asic_click_options(func):
    for option in reversed(_multi_asic_click_options):
        func = option(func)
    return func

def multi_asic_click_option_namespace(func):
   func = _multi_asic_click_option_namespace(func)
   return func

def run_on_multi_asic(func):
    '''
    This decorator is used on the CLI functions which needs to be
    run on all the namespaces in the multi ASIC platform
    The decorator loops through all the required namespaces,
    for every iteration, it connects to all the DBs and provides an handle
    to the wrapped function.

    '''
    @functools.wraps(func)
    def wrapped_run_on_all_asics(self, *args, **kwargs):
        ns_list = self.multi_asic.get_ns_list_based_on_options()
        for ns in ns_list:
            self.multi_asic.current_namespace = ns
            # if object instance already has db connections, use them
            if self.multi_asic.db and self.multi_asic.db.cfgdb_clients.get(ns):
                self.config_db = self.multi_asic.db.cfgdb_clients[ns]
            else:
                self.config_db = multi_asic.connect_config_db_for_ns(ns)

            if self.multi_asic.db and self.multi_asic.db.db_clients.get(ns):
                self.db = self.multi_asic.db.db_clients[ns]
            else:
                self.db = multi_asic.connect_to_all_dbs_for_ns(ns)

            func(self,  *args, **kwargs)
    return wrapped_run_on_all_asics


def multi_asic_args(parser=None):
    if parser is None:
        parser = argparse.ArgumentParser(
            formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('-d', '--display', default=constants.DISPLAY_EXTERNAL,
                        help='Display all interfaces or only external interfaces')
    parser.add_argument('-n', '--namespace', default=None,
                        help='Display interfaces for specific namespace')
    return parser

### Function to get the address info for all interfaces in a namespace
def multi_asic_get_addr_info_from_ns(namespace):
    ip_addr_db_ns_cmd = f"ip netns exec {namespace} " if namespace != constants.DEFAULT_NAMESPACE else ""
    ip_addr_db_ns_cmd += " ip -json addr show"
    out = subprocess.check_output(ip_addr_db_ns_cmd, shell=True)
    data = json.loads(out)
    if_db = {}
    for item in data:
        if_db[item["ifname"]] = item
    return if_db 

def multi_asic_get_ip_intf_from_ns(namespace):
    import pyroute2
    if namespace != constants.DEFAULT_NAMESPACE:
        pyroute2.netns.pushns(namespace)
    interfaces = natsorted(netifaces.interfaces())

    if namespace != constants.DEFAULT_NAMESPACE:
        pyroute2.netns.popns()

    return interfaces


def multi_asic_get_ip_intf_addr_from_ns(namespace, iface):
    import pyroute2
    if namespace != constants.DEFAULT_NAMESPACE:
        pyroute2.netns.pushns(namespace)
    ipaddresses = netifaces.ifaddresses(iface)

    if namespace != constants.DEFAULT_NAMESPACE:
        pyroute2.netns.popns()

    return ipaddresses

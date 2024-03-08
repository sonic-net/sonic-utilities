#!/usr/bin/env python3

"""
use wol to generate and send Wake-On-LAN (WOL) "Magic Packet" to specific interface

Usage: wol_click [OPTIONS] INTERFACE TARGET_MAC

  Generate and send Wake-On-LAN (WOL) "Magic Packet" to specific interface

Options:
  -b           Use broadcast MAC address instead of target device's MAC
               address as Destination MAC Address in Ethernet Frame Header.
               [default: False]
  -p password  An optional 4 or 6 byte password, in ethernet hex format or
               quad-dotted decimal  [default: ]
  -c count     For each target MAC address, the count of magic packets to
               send. count must between 1 and 5. This param must use with -i.
               [default: 1]
  -i interval  Wait interval milliseconds between sending each magic packet.
               interval must between 0 and 2000. This param must use with -c.
               [default: 0]
  -v           Verbose output  [default: False]
  -h, --help   Show this message and exit.

Examples:
  wol Ethernet10 00:11:22:33:44:55
  wol Ethernet10 00:11:22:33:44:55 -b
  wol Vlan1000 00:11:22:33:44:55,11:33:55:77:99:bb -p 00:22:44:66:88:aa
  wol Vlan1000 00:11:22:33:44:55,11:33:55:77:99:bb -p 192.168.1.1 -c 3 -i 2000
"""

import binascii
import click
import copy
import netifaces
import os
import socket
import time

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
EPILOG = """\b
Examples:
  wol Ethernet10 00:11:22:33:44:55
  wol Ethernet10 00:11:22:33:44:55 -b
  wol Vlan1000 00:11:22:33:44:55,11:33:55:77:99:bb -p 00:22:44:66:88:aa
  wol Vlan1000 00:11:22:33:44:55,11:33:55:77:99:bb -p 192.168.1.1 -c 3 -i 2000
"""
ORDINAL_NUMBER = ["0", "1st", "2nd", "3rd", "4th", "5th"]
ETHER_TYPE_WOL = b'\x08\x42'


class MacAddress(object):
    """
    Class to handle MAC addresses and perform operations on them.

    Attributes:
    - address: bytes
    """

    def __init__(self, address: str):
        """
        Constructor to instantiate the MacAddress class.

        Parameters:
        - address: str
            The MAC address in the format '01:23:45:67:89:AB' or '01-23-45-67-89-AB'.

        Raises:
        - ValueError:
            Throws an error if the provided address is not in the correct format.
        """
        try:
            self.address = binascii.unhexlify(address.replace(':', '').replace('-', ''))
        except binascii.Error:
            raise ValueError("invalid MAC address")
        if len(self.address) != 6:
            raise ValueError("invalid MAC address")

    def __str__(self):
        return ":".join(["%02x" % v for v in self.address])

    def __eq__(self, other):
        return self.address == other.address

    def to_bytes(self):
        return copy.copy(self.address)


BROADCAST_MAC = MacAddress('ff:ff:ff:ff:ff:ff')


def is_root():
    return os.geteuid() == 0


def get_interface_operstate(interface):
    with open('/sys/class/net/{}/operstate'.format(interface), 'r') as f:
        return f.read().strip().lower()


def get_interface_mac(interface):
    return MacAddress(netifaces.ifaddresses(interface)[netifaces.AF_LINK][0].get('addr'))


def build_magic_packet(interface, target_mac, broadcast, password):
    dst_mac = BROADCAST_MAC if broadcast else target_mac
    src_mac = get_interface_mac(interface)
    return dst_mac.to_bytes() + src_mac.to_bytes() + ETHER_TYPE_WOL \
        + b'\xff' * 6 + target_mac.to_bytes() * 16 + password


def send_magic_packet(interface, target_mac, pkt, count, interval, verbose):
    if verbose:
        print("Sending {} magic packet to {} via interface {}".format(count, target_mac, interface))
    sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
    sock.bind((interface, 0))
    for i in range(count):
        sock.send(pkt)
        if verbose:
            print("{} magic packet sent to {}".format(ORDINAL_NUMBER[i + 1], target_mac))
        if i + 1 != count:
            time.sleep(interval / 1000)
    sock.close()


def validate_interface(ctx, param, value):
    if value not in netifaces.interfaces():
        raise click.BadParameter("invalid SONiC interface name {}".format(value))
    if get_interface_operstate(value) != 'up':
        raise click.BadParameter("interface {} is not up".format(value))
    return value


def parse_target_mac(ctx, param, value):
    mac_list = []
    for mac in value.split(','):
        try:
            mac_list.append(MacAddress(mac))
        except ValueError:
            raise click.BadParameter("invalid MAC address {}".format(mac))
    return mac_list


def parse_password(ctx, param, value):
    if len(value) == 0:
        return b''  # Empty password is valid.
    elif len(value) <= 15:  # The length of a valid IPv4 address is less or equal to 15.
        try:
            password = socket.inet_aton(value)
        except OSError:
            raise click.BadParameter("invalid password format")
    else:  # The length of a valid MAC address is 17.
        try:
            password = MacAddress(value).to_bytes()
        except ValueError:
            raise click.BadParameter("invalid password format")
    if len(password) not in [4, 6]:
        raise click.BadParameter("password must be 4 or 6 bytes or empty")
    return password


def validate_count_interval(count, interval):
    if count is None and interval is None:
        return 1, 0  # By default, count=1 and interval=0.
    if count is None or interval is None:
        raise click.BadParameter("count and interval must be used together")
    # The values are confirmed in valid range by click.IntRange().
    return count, interval


@click.command(context_settings=CONTEXT_SETTINGS, epilog=EPILOG)
@click.argument('interface', type=click.STRING, callback=validate_interface)
@click.argument('target_mac', type=click.STRING, callback=parse_target_mac)
@click.option('-b', 'broadcast', is_flag=True, show_default=True, default=False,
              help="Use broadcast MAC address instead of target device's MAC address as Destination MAC Address in Ethernet Frame Header.")
@click.option('-p', 'password', type=click.STRING, show_default=True, default='', callback=parse_password, metavar='password',
              help='An optional 4 or 6 byte password, in ethernet hex format or quad-dotted decimal')
@click.option('-c', 'count', type=click.IntRange(1, 5), metavar='count', show_default=True,  # default=1,
              help='For each target MAC address, the count of magic packets to send. count must between 1 and 5. This param must use with -i.')
@click.option('-i', 'interval', type=click.IntRange(0, 2000), metavar='interval',  # show_default=True, default=0,
              help="Wait interval milliseconds between sending each magic packet. interval must between 0 and 2000. This param must use with -c.")
@click.option('-v', 'verbose', is_flag=True, show_default=True, default=False,
              help='Verbose output')
def wol(interface, target_mac, broadcast, password, count, interval, verbose):
    """
    Generate and send Wake-On-LAN (WOL) "Magic Packet" to specific interface
    """
    count, interval = validate_count_interval(count, interval)

    if not is_root():
        raise click.ClickException("root priviledge is required to run this script")

    for mac in target_mac:
        pkt = build_magic_packet(interface, mac, broadcast, password)
        try:
            send_magic_packet(interface, mac, pkt, count, interval, verbose)
        except Exception as e:
            raise click.ClickException(f'Exception: {e}')


if __name__ == '__main__':
    wol()

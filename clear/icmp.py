import click
import utilities_common.cli as clicommon

# `sonic-clear icmp counters` snapshots current per-session counters as
# the new baseline; `show icmp stats` subtracts it. Implementation lives
# in the show module so read and clear share one definition of the
# baseline format / on-disk location (UserCache 'icmpstat').
from show.icmp import IcmpShow


@click.group(cls=clicommon.AliasedGroup)
def icmp():
    """Clear ICMP offload counters"""
    pass


@icmp.command()
def counters():
    """Clear ICMP echo session counter baseline.

    Snapshots per-session per-direction (IN/OUT) packet and byte counts;
    native sessions capture only packets (bytes render as 'N/A').
    `show icmp stats` then subtracts this baseline until the next clear.
    Hardware counters and COUNTERS_DB are untouched."""
    IcmpShow(click).clear_baseline()

from collections import namedtuple


def disk_partitions():
    sdiskpart = namedtuple('sdiskpart', ['mountpoint', 'device'])
    return [sdiskpart(mountpoint="/host", device="/dev/sdx1")]

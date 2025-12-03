#!/usr/bin/env python

import os


def in_chroot() -> bool:
    """ Verify if we are running in chroot or not
     by comparing root / mount point device id and inode
     with init process - /proc/1/root mount point device
     id and inode. If those match we are not chroot-ed
     otherwise we are. """

    root_stat = os.stat('/')
    init_root_stat = os.stat('/proc/1/root')

    return (root_stat.st_dev, root_stat.st_ino) != \
           (init_root_stat.st_dev, init_root_stat.st_ino)

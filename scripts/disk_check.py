#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
What:
    There have been cases, where disk turns Read-only due to kernel bug.
    In Read-only state, system blocks new remote user login via TACACS.
    This utility is to check & make transient recovery as needed.

How:
    check for Read-Write permission. If Read-only, create writable overlay using tmpfs.

    By default "/etc" & "/home" are checked and if in Read-only state, make them Read-Write
    using overlay on top of tmpfs.

    Making /etc & /home as writable lets successful new remote user login.

    If in Read-only state or in Read-Write state with the help of tmpfs overlay,
    syslog ERR messages are written, to help raise alerts.

    Monit may be used to invoke it periodically, to help scan & fix and
    report via syslog.

Tidbit:
    If you would like to test this script, you could simulate a RO disk
    with the following command. Reboot will revert the effect.
        sudo bash -c "echo u > /proc/sysrq-trigger"

"""

import argparse
import os
import shutil
import sys
import syslog
import subprocess
from swsscommon.swsscommon import events_init_publisher, events_deinit_publisher, event_publish
from swsscommon.swsscommon import FieldValueMap

UPPER_DIR = "/run/mount/upper"
WORK_DIR = "/run/mount/work"
MOUNTS_FILE = "/proc/mounts"

# Threshold of free block counts: On most file systems, the block size is 4096 bytes.
FREE_SPACE_THRESHOLD = 1024

EVENTS_PUBLISHER_SOURCE = "sonic-events-host"
EVENTS_PUBLISHER_TAG = "event-disk"
events_handle = None

DISK_RO_EVENT = "read_only"
DISK_FULL_EVENT = "disk_full"

chk_log_level = syslog.LOG_ERR

def _log_msg(lvl, pfx, msg):
    if lvl <= chk_log_level:
        print("{}: {}".format(pfx, msg))
        syslog.syslog(lvl, msg)


def log_err(m):
    _log_msg(syslog.LOG_ERR, "Err", m)


def log_info(m):
    _log_msg(syslog.LOG_INFO, "Info",  m)


def log_debug(m):
    _log_msg(syslog.LOG_DEBUG, "Debug", m)


def event_pub(event):
    param_dict = FieldValueMap()
    param_dict["fail_type"] = event
    event_publish(events_handle, EVENTS_PUBLISHER_TAG, param_dict)


def test_disk_full(dirs): 
    for d in dirs:
        space = os.statvfs(d)
        if space.f_bavail < FREE_SPACE_THRESHOLD:
            log_err("{} has no free disk space".format(d))
            event_pub(DISK_FULL_EVENT)
            return True
        else:
            log_debug("{} has enough disk space".format(d))

    return False


def test_writable(dirs): 
    for d in dirs:
        rw = os.access(d, os.W_OK)
        if not rw:
            log_err("{} is not read-write".format(d))
            event_pub(DISK_RO_EVENT)
            return False
        else:
            log_debug("{} is Read-Write".format(d))

    return True


def run_cmd(cmd):
    proc = subprocess.run(cmd, shell=False, stdout=subprocess.PIPE)
    ret = proc.returncode
    if ret:
        log_err("failed: ret={} cmd={}".format(ret, cmd))
    else:
        log_info("ret={} cmd: {}".format(ret, cmd))

    if proc.stdout:
        log_info("stdout: {}".format(proc.stdout.decode("utf-8")))
    if proc.stderr:
        log_info("stderr: {}".format(proc.stderr.decode("utf-8")))
    return ret


def get_dname(path_name):
    return os.path.basename(os.path.normpath(path_name))


def do_mnt(dirs, overlay_prefix):
    if os.path.exists(UPPER_DIR):
        log_err("Already mounted")
        return 1

    for i in (UPPER_DIR, WORK_DIR):
        try:
            os.mkdir(i)
        except OSError as error:
            log_err("Failed to create {}, error: {}".format(i, error))
            return 1

    for d in dirs:
        d_name = get_dname(d)
        d_upper = os.path.join(UPPER_DIR, d_name)
        d_work = os.path.join(WORK_DIR, d_name)
        os.mkdir(d_upper)
        os.mkdir(d_work)

        ret = run_cmd(["mount", "-t", "overlay", "{}_{}".format(overlay_prefix, d_name),\
                "-o", "lowerdir={},upperdir={},workdir={}".format(d, d_upper, d_work), d])
        if ret:
            break

    if ret:
        log_err("Failed to mount {} as Read-Write".format(dirs))
    else:
        log_info("{} are mounted as Read-Write".format(dirs))
    return ret

def do_unmnt(dirs, overlay_prefix):
    for d in dirs:
        d_name = get_dname(d)
        ret = run_cmd(["umount", "-l", "{}_{}".format(overlay_prefix, d_name)])
        if ret:
            break

    if ret:
        log_err("Failed to umount {}".format(dirs))
    else:
        log_info("{} are unmounted".format(dirs))

    for i in (UPPER_DIR, WORK_DIR):
        try:
            shutil.rmtree(i)
        except OSError as error:
            log_err("Failed to delete {}, error: {}".format(i, error))
            return 1

    return ret


def is_mounted(dirs, overlay_prefix):
    if not os.path.exists(UPPER_DIR):
        return False

    onames = set()
    for d in dirs:
        onames.add("{}_{}".format(overlay_prefix, get_dname(d)))

    with open(MOUNTS_FILE, "r") as s:
        for ln in s.readlines():
            n = ln.strip().split()[0]
            if n in onames:
                log_debug("Mount exists for {}".format(n))
                return True
    return False


def do_check(skip_mount, dirs):
    ret = 0
    if not test_writable(dirs):
        if not skip_mount:
            ret = do_mnt(dirs, "overlay")

    # Check if mounted
    if (not ret) and is_mounted(dirs, "overlay"):
        log_err("READ-ONLY: Mounted {} to make Read-Write".format(dirs))
        event_pub(DISK_RO_EVENT)

    if ret:
        # When disk mounted, disk no free space issue also been fixed.
        return ret

    # Handle disk no free space case
    if test_disk_full(dirs):
        if not skip_mount:
            ret = do_mnt(dirs, "overlay_disk_full")

    # Check if mounted
    if (not ret) and is_mounted(dirs, "overlay_disk_full"):
        log_err("DISK-FULL: Mounted {} to make Read-Write".format(dirs))
        event_pub(DISK_FULL_EVENT)

    # Unmount when disk space issue fixed
    if is_mounted(dirs, "overlay_disk_full") and not test_disk_full(["/"]):
        log_debug("umount for disk space issue fixed")
        do_unmnt(dirs, "overlay_disk_full")

    return ret


def main():
    global chk_log_level, events_handle

    parser=argparse.ArgumentParser(
            description="check disk for Read-Write and mount etc & home as Read-Write")
    parser.add_argument('-s', "--skip-mount", action='store_true', default=False,
            help="Skip mounting /etc & /home as Read-Write")
    parser.add_argument('-d', "--dirs", default="/etc,/home",
            help="dirs to mount")
    parser.add_argument('-l', "--loglvl", default=syslog.LOG_ERR, type=int,
            help="log level")
    args = parser.parse_args()

    chk_log_level = args.loglvl

    events_handle = events_init_publisher(EVENTS_PUBLISHER_SOURCE)

    ret = do_check(args.skip_mount, args.dirs.split(","))

    events_deinit_publisher(events_handle)
    return ret


if __name__ == "__main__":
    sys.exit(main())

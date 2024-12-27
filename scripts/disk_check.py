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
import sys
import syslog
import subprocess
from swsscommon.swsscommon import events_init_publisher, events_deinit_publisher, event_publish
from swsscommon.swsscommon import FieldValueMap

UPPER_DIR = "/run/mount/upper"
WORK_DIR = "/run/mount/work"
MOUNTS_FILE = "/proc/mounts"

FREE_SPACE_THRESHOLD = 1024

EVENTS_PUBLISHER_SOURCE = "sonic-events-host"
EVENTS_PUBLISHER_TAG = "event-disk"
events_handle = None

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


def event_pub():
    param_dict = FieldValueMap()
    param_dict["fail_type"] = "read_only"
    event_publish(events_handle, EVENTS_PUBLISHER_TAG, param_dict)


def test_writable(dirs): 
    for d in dirs:
        rw = os.access(d, os.W_OK)
        if not rw:
            log_err("{} is not read-write".format(d))
            event_pub()
            return False
        else:
            space = os.statvfs(d)
            if space.f_bavail < FREE_SPACE_THRESHOLD:
                log_err("{} is no free space".format(d))
                event_pub()
                return False

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


def do_mnt(dirs):
    if os.path.exists(UPPER_DIR):
        log_err("Already mounted")
        return 1

    for i in (UPPER_DIR, WORK_DIR):
        try:
            os.mkdir(i)
        except OSError as error:
            log_err("Failed to create {}".format(i))
            return 1

    for d in dirs:
        d_name = get_dname(d)
        d_upper = os.path.join(UPPER_DIR, d_name)
        d_work = os.path.join(WORK_DIR, d_name)
        os.mkdir(d_upper)
        os.mkdir(d_work)

        ret = run_cmd(["mount", "-t", "overlay", "overlay_{}".format(d_name),\
                "-o", "lowerdir={},upperdir={},workdir={}".format(d, d_upper, d_work), d])
        if ret:
            break

    if ret:
        log_err("Failed to mount {} as Read-Write".format(dirs))
    else:
        log_info("{} are mounted as Read-Write".format(dirs))
    return ret


def is_mounted(dirs):
    if not os.path.exists(UPPER_DIR):
        return False

    onames = set()
    for d in dirs:
        onames.add("overlay_{}".format(get_dname(d)))

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
            ret = do_mnt(dirs)

    # Check if mounted
    if (not ret) and is_mounted(dirs):
        log_err("READ-ONLY: Mounted {} to make Read-Write".format(dirs))
        event_pub()

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

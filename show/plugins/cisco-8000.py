#!/usr/bin/env python
#########################################################
# Copyright 2021-2022 Cisco Systems, Inc.
# All rights reserved.
#
# CLI Extensions for show command
#########################################################

try:
    from sonic_py_common import device_info
    import utilities_common.cli as clicommon
except ImportError as e:
    raise ImportError("%s - required module not found".format(str(e)))

try:
    from sonic_platform.cli import PLATFORM_CLIS
except ImportError:
    PLATFORM_CLIS = []


def register(cli):
    version_info = device_info.get_sonic_version_info()
    if version_info and version_info.get("asic_type") == "cisco-8000":
        for c in PLATFORM_CLIS:
            cli.commands["platform"].add_command(c)

#!/usr/bin/env python

""" Logger for sonic-package-manager. """

import logging
import click_log

from logging.handlers import SysLogHandler


class Formatter(click_log.ColorFormatter):
    """ Click logging formatter. """

    colors = {
        'error': dict(fg='red'),
        'exception': dict(fg='red'),
        'critical': dict(fg='red'),
        'debug': dict(fg='blue', bold=True),
        'warning': dict(fg='yellow'),
    }


log = logging.getLogger("sonic-package-manager")
log.setLevel(logging.INFO)

click_handler = click_log.ClickHandler()
click_handler.formatter = Formatter()

syslog_handler = SysLogHandler()
syslog_handler.setFormatter(logging.Formatter('%(name)s: %(message)s'))

log.addHandler(click_handler)
log.addHandler(syslog_handler)

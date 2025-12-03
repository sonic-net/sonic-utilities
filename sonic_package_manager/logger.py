#!/usr/bin/env python

""" Logger for sonic-package-manager. """

import logging.handlers

import click_log


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

log.addHandler(click_handler)
log.addHandler(logging.handlers.SysLogHandler())

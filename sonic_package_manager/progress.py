#!/usr/bin/env python

import enlighten

BAR_FMT = '{desc}{desc_pad}{percentage:3.0f}%|{bar}| {count:{len_total}.2f}/{total:.2f}{unit_pad}{unit} ' + \
          '[{elapsed}<{eta}, {rate:.2f}{unit_pad}{unit}/s]'

COUNTER_FMT = '{desc}{desc_pad}{count:.1f} {unit}{unit_pad}' + \
              '[{elapsed}, {rate:.2f}{unit_pad}{unit}/s]{fill}'


class ProgressManager:
    """ ProgressManager is used for creating multiple progress bars
    which nicely interact with logging and prints. """

    def __init__(self):
        self.manager = enlighten.get_manager()
        self.pbars = {}

    def __enter__(self):
        return self.manager.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.manager.__exit__(exc_type, exc_val, exc_tb)

    def new(self, id: str, *args, **kwargs):
        """ Creates new progress bar with id.
        Args:
            id: progress bar identifier
            *args: pass arguments for progress bar creation
            **kwargs: pass keyword arguments for progress bar creation.
        """

        if 'bar_format' not in kwargs:
            kwargs['bar_format'] = BAR_FMT
        if 'counter_format' not in kwargs:
            kwargs['counter_format'] = COUNTER_FMT

        self.pbars[id] = self.manager.counter(*args, **kwargs)

    def get(self, id: str):
        """ Returns progress bar by id.
        Args:
            id: progress bar identifier
        Returns:
            Progress bar.
        """

        return self.pbars[id]

    def __contains__(self, id):
        return id in self.pbars

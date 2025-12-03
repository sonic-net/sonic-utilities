#!/usr/bin/env python

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class PackageReference:
    """ PackageReference is a package version constraint. """

    name: str
    reference: Optional[str] = None

    def __str__(self):
        return f'{self.name} {self.reference}'

    @staticmethod
    def parse(expression: str) -> 'PackageReference':
        REQUIREMENT_SPECIFIER_RE = \
            r'(?P<name>[A-Za-z0-9_-]+)(?P<reference_format>@(?P<reference>.*))'

        match = re.match(REQUIREMENT_SPECIFIER_RE, expression)
        if match is None:
            raise ValueError(f'Invalid reference specifier {expression}')
        groupdict = match.groupdict()
        name = groupdict.get('name')
        reference = groupdict.get('reference')

        return PackageReference(name, reference)

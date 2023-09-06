#!/usr/bin/env python

""" Package version constraints module. """

import re
from dataclasses import dataclass, field
from typing import Dict, Union

import semantic_version

from sonic_package_manager.version import Version


class VersionConstraint:
    """ Version constraint representation. """

    def __init__(self, *args, **kwargs):
        self._constraint = semantic_version.SimpleSpec(*args, **kwargs)

    @property
    def expression(self):
        return self._constraint.expression

    @classmethod
    def parse(cls, constraint_expression: str) -> 'VersionConstraint':
        """ Parse version constraint.

        Args:
            constraint_expression: Expression syntax: "[[op][version]]+".
        Returns:
            The resulting VersionConstraint object.
        """

        return cls(constraint_expression)

    def allows(self, version: Version) -> bool:
        """ Checks if other version is allowed by this constraint

        Args:
            version: Version to check against this constraint.
        Returns:
            Boolean wether this constraint allows version.
        """

        return self._constraint.match(version._version)

    def is_exact(self) -> bool:
        """ Is the version constraint exact, meaning only one version is allowed.

        Returns:
            Boolean wether this constraint is exact.
        """

        clause = self._constraint.clause
        return hasattr(clause, 'target') and clause.operator == '=='

    def get_exact_version(self) -> Version:
        """ Returns an exact version for this constraint if it is exact constraint.

        Returns:
            Exact version in case this constraint is exact.
        Raises:
            AttributeError: when constraint is not exact
        """

        return self._constraint.clause.target

    def __str__(self):
        return self._constraint.__str__()

    def __repr__(self):
        return self._constraint.__repr__()

    def __eq__(self, other):
        return self._constraint.__eq__(other._constraint)


@dataclass
class ComponentConstraints:
    """ ComponentConstraints is a set of components version constraints. """

    components: Dict[str, VersionConstraint] = field(default_factory=dict)

    @staticmethod
    def parse(constraints: Dict) -> 'ComponentConstraints':
        """ Parse constraint from dictionary.

        Args:
            constraints: dictionary with component name
            as key and constraint expression as value

        Returns:
            ComponentConstraints object.

        """

        components = {component: VersionConstraint.parse(version)
                      for component, version in constraints.items()}
        return ComponentConstraints(components)

    def deparse(self) -> Dict[str, str]:
        """ Returns the manifest representation of components constraints.

        Returns:
            Dictionary of string keys and string values.

        """

        return {
            component: str(version) for component, version in self.components.items()
        }


@dataclass
class PackageConstraint:
    """ PackageConstraint is a package version constraint. """

    name: str
    constraint: VersionConstraint
    _components: ComponentConstraints = field(default_factory=ComponentConstraints)

    def __str__(self): return f'{self.name}{self.constraint}'

    @property
    def components(self): return self._components.components

    @staticmethod
    def from_string(constraint_expression: str) -> 'PackageConstraint':
        """ Parse package constraint string which contains a package
        name separated by a space with zero, one or more version constraint
        expressions. A variety of version matching operators are supported
        including >, <, ==, !=, ^, *. See Examples.

        Args:
            constraint_expression: Expression syntax "[package name] [[op][version]]+".

        Returns:
            PackageConstraint object.

        Examples:
            >>> PackageConstraint.parse('syncd^1.0.0').constraint
            <VersionRange (>=1.0.0,<2.0.0)>
            >>> PackageConstraint.parse('swss>1.3.2 <4.2.1').constraint
            <VersionRange (>1.3.2,<4.2.1)>
            >>> PackageConstraint.parse('swss').constraint
            <VersionRange (*)>
        """

        REQUIREMENT_SPECIFIER_RE = \
            r'(?P<name>[A-Za-z0-9_-]+)(?P<constraint>.*)'

        match = re.match(REQUIREMENT_SPECIFIER_RE, constraint_expression)
        if match is None:
            raise ValueError(f'Invalid constraint {constraint_expression}')
        groupdict = match.groupdict()
        name = groupdict.get('name')
        constraint = groupdict.get('constraint') or '*'
        return PackageConstraint(name, VersionConstraint.parse(constraint))

    @staticmethod
    def from_dict(constraint_dict: Dict) -> 'PackageConstraint':
        """ Parse package constraint information from dictionary. E.g:

        {
            "name": "swss",
            "version": "^1.0.0",
            "componenets": {
                "libswsscommon": "^1.0.0"
            }
        }

        Args:
            constraint_dict: Dictionary of constraint infromation.

        Returns:
            PackageConstraint object.
        """

        name = constraint_dict['name']
        version = VersionConstraint.parse(constraint_dict.get('version') or '*')
        components = ComponentConstraints.parse(constraint_dict.get('components', {}))
        return PackageConstraint(name, version, components)

    @staticmethod
    def parse(constraint: Union[str, Dict]) -> 'PackageConstraint':
        """ Parse constraint from string expression or dictionary.

        Args:
            constraint: string or dictionary. Check from_str() and from_dict() methods.

        Returns:
            PackageConstraint object.

        """

        if type(constraint) is str:
            return PackageConstraint.from_string(constraint)
        elif type(constraint) is dict:
            return PackageConstraint.from_dict(constraint)
        else:
            raise ValueError('Input argument should be either str or dict')

    def deparse(self) -> Dict:
        """ Returns the manifest representation of package constraint.

        Returns:
            Dictionary in manifest representation.

        """

        return {
            'name': self.name,
            'version': str(self.constraint),
            'components': self._components.deparse(),
        }

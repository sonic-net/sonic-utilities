#!/usr/bin/env python

""" Version and helpers routines. """

import semantic_version


class Version:
    """ Version class represents SemVer 2.0 compliant version """

    @classmethod
    def parse(cls, version_string: str) -> 'Version':
        """ Construct Version from version_string.

        Args:
            version_string: SemVer compatible version string.
        Returns:
            Version object.
        Raises:
            ValueError: when version_string does not follow SemVer.
        """

        return cls(version_string)

    def __init__(self, *args, **kwargs):
        self._version = semantic_version.Version(*args, **kwargs)

    @property
    def major(self):
        return self._version.major

    @property
    def minor(self):
        return self._version.minor

    @property
    def patch(self):
        return self._version.patch

    def __str__(self):
        return self._version.__str__()

    def __repr__(self):
        return self._version.__repr__()

    def __iter__(self):
        return self._version.__iter__()

    def __cmp__(self, other):
        return self._version.__cmp__(other._version)

    def __eq__(self, other):
        return self._version.__eq__(other._version)

    def __ne__(self, other):
        return self._version.__ne__(other._version)

    def __lt__(self, other):
        return self._version.__lt__(other._version)

    def __le__(self, other):
        return self._version.__le__(other._version)

    def __gt__(self, other):
        return self._version.__gt__(other._version)

    def __ge__(self, other):
        return self._version.__ge__(other._version)


def version_to_tag(ver: Version) -> str:
    """ Converts the version to Docker compliant tag string. """

    return str(ver).replace('+', '_')


def tag_to_version(tag: str) -> Version:
    """ Converts the version to Docker compliant tag string. """

    try:
        return Version.parse(tag.replace('_', '+'))
    except ValueError as err:
        raise ValueError(f'Failed to convert {tag} to version string: {err}')

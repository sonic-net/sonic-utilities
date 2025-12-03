#!/usr/bin/env python

import pytest

from sonic_package_manager import version
from sonic_package_manager.constraint import PackageConstraint, VersionConstraint
from sonic_package_manager.version import Version


@pytest.mark.parametrize('invalid_version', ['1.2.3-0123', '1.2', '1.0.0+artiary+version'])
def test_invalid_version(invalid_version):
    with pytest.raises(Exception):
        Version.parse(invalid_version)


@pytest.mark.parametrize(('newer', 'older'),
                         [('0.1.1', '0.1.1-alpha')])
def test_version_comparison(newer, older):
    assert Version.parse(newer) > Version.parse(older)


def test_constraint():
    package_constraint = PackageConstraint.parse('swss>1.0.0')
    assert package_constraint.name == 'swss'
    assert not package_constraint.constraint.allows(Version.parse('0.9.1'))
    assert package_constraint.constraint.allows(Version.parse('1.1.1'))


def test_constraint_range():
    package_constraint = PackageConstraint.parse('swss^1.2.0')
    assert package_constraint.name == 'swss'
    assert not package_constraint.constraint.allows(Version.parse('1.1.1'))
    assert package_constraint.constraint.allows(Version.parse('1.2.5'))
    assert not package_constraint.constraint.allows(Version.parse('2.0.1'))


def test_constraint_strict():
    package_constraint = PackageConstraint.parse('swss==1.2.0')
    assert package_constraint.name == 'swss'
    assert not package_constraint.constraint.allows(Version.parse('1.1.1'))
    assert package_constraint.constraint.allows(Version.parse('1.2.0'))


def test_constraint_match():
    package_constraint = PackageConstraint.parse('swss==1.2.*')
    assert package_constraint.name == 'swss'
    assert not package_constraint.constraint.allows(Version.parse('1.1.1'))
    assert package_constraint.constraint.allows(Version.parse('1.2.0'))


def test_constraint_multiple():
    package_constraint = PackageConstraint.parse('swss>1.2.0,<3.0.0,!=2.2.2')
    assert package_constraint.name == 'swss'
    assert not package_constraint.constraint.allows(Version.parse('2.2.2'))
    assert not package_constraint.constraint.allows(Version.parse('3.2.0'))
    assert not package_constraint.constraint.allows(Version.parse('0.2.0'))
    assert package_constraint.constraint.allows(Version.parse('2.2.3'))
    assert package_constraint.constraint.allows(Version.parse('1.2.3'))


def test_constraint_only_name():
    package_constraint = PackageConstraint.parse('swss')
    assert package_constraint.name == 'swss'
    assert package_constraint.constraint == VersionConstraint('*')


def test_constraint_from_dict():
    package_constraint = PackageConstraint.parse({
        'name': 'swss',
        'version': '^1.0.0',
        'components': {
            'libswsscommon': '^1.1.0',
        },
    })
    assert package_constraint.name == 'swss'
    assert package_constraint.constraint.allows(Version.parse('1.0.0'))
    assert not package_constraint.constraint.allows(Version.parse('2.0.0'))
    assert package_constraint.components['libswsscommon'].allows(Version.parse('1.2.0'))
    assert not package_constraint.components['libswsscommon'].allows(Version.parse('1.0.0'))
    assert not package_constraint.components['libswsscommon'].allows(Version.parse('2.0.0'))


def test_version_to_tag():
    assert version.version_to_tag(Version.parse('1.0.0-rc0')) == '1.0.0-rc0'
    assert version.version_to_tag(Version.parse('1.0.0-rc0+152')) == '1.0.0-rc0_152'


def test_tag_to_version():
    assert str(version.tag_to_version('1.0.0-rc0_152')) == '1.0.0-rc0+152'
    assert str(version.tag_to_version('1.0.0-rc0')) == '1.0.0-rc0'

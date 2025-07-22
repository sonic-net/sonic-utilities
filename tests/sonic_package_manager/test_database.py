#!/usr/bin/env python

import pytest

from sonic_package_manager.database import PackageEntry, package_from_dict
from sonic_package_manager.errors import (
    PackageNotFoundError,
    PackageAlreadyExistsError,
    PackageManagerError
)
from sonic_package_manager.version import Version


def test_database_get_package(fake_db):
    swss_package = fake_db.get_package('swss')
    assert swss_package.installed
    assert swss_package.built_in
    assert swss_package.repository == 'docker-orchagent'
    assert swss_package.default_reference == '1.0.0'
    assert swss_package.version == Version.parse('1.0.0')


def test_database_get_package_not_builtin(fake_db):
    test_package = fake_db.get_package('test-package')
    assert not test_package.installed
    assert not test_package.built_in
    assert test_package.repository == 'Azure/docker-test'
    assert test_package.default_reference == '1.6.0'
    assert test_package.version is None


def test_database_get_package_not_existing(fake_db):
    with pytest.raises(PackageNotFoundError):
        fake_db.get_package('abc')


def test_database_add_package(fake_db):
    fake_db.add_package('test-package-99', 'Azure/docker-test-99')
    test_package = fake_db.get_package('test-package-99')
    assert not test_package.installed
    assert not test_package.built_in
    assert test_package.repository == 'Azure/docker-test-99'
    assert test_package.default_reference is None
    assert test_package.version is None


def test_database_add_package_existing(fake_db):
    with pytest.raises(PackageAlreadyExistsError):
        fake_db.add_package('swss', 'Azure/docker-orchagent')


def test_database_update_package(fake_db):
    test_package = fake_db.get_package('test-package-2')
    test_package.installed = True
    test_package.version = Version.parse('1.2.3')
    fake_db.update_package(test_package)
    test_package = fake_db.get_package('test-package-2')
    assert test_package.installed
    assert test_package.version == Version.parse('1.2.3')


def test_database_update_package_non_existing(fake_db):
    test_package = PackageEntry('abc', 'abc')
    with pytest.raises(PackageNotFoundError):
        fake_db.update_package(test_package)


def test_database_remove_package(fake_db):
    fake_db.remove_package('test-package')
    assert not fake_db.has_package('test-package')


def test_database_remove_package_non_existing(fake_db):
    with pytest.raises(PackageNotFoundError):
        fake_db.remove_package('non-existing-package')


def test_database_remove_package_installed(fake_db):
    with pytest.raises(PackageManagerError,
                       match='Package test-package-3 is installed, '
                             'uninstall it first'):
        fake_db.remove_package('test-package-3')


def test_database_remove_package_built_in(fake_db):
    with pytest.raises(PackageManagerError,
                       match='Package swss is built-in, '
                             'cannot remove it'):
        fake_db.remove_package('swss')


def test_package_from_dict():
    """Test converting dictionary to PackageEntry object."""
    package_info = {
        'repository': 'test-repo',
        'description': 'Test package description',
        'default-reference': '1.0.0',
        'installed-version': '1.0.0',
        'installed': True,
        'built-in': False,
        'image-id': 'abc123',
        'tag': 'latest'
    }

    package = package_from_dict('test-package', package_info)

    assert package.name == 'test-package'
    assert package.repository == 'test-repo'
    assert package.description == 'Test package description'
    assert package.default_reference == '1.0.0'
    assert package.version == Version.parse('1.0.0')
    assert package.installed is True
    assert package.built_in is False
    assert package.image_id == 'abc123'
    assert package.tag == 'latest'


def test_package_from_dict_minimal():
    """Test converting minimal dictionary to PackageEntry object."""
    package_info = {
        'repository': 'test-repo'
    }

    package = package_from_dict('test-package', package_info)

    assert package.name == 'test-package'
    assert package.repository == 'test-repo'
    assert package.description is None
    assert package.default_reference is None
    assert package.version is None
    assert package.installed is False
    assert package.built_in is False
    assert package.image_id is None
    assert package.tag is None

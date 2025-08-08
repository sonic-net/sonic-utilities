#!/usr/bin/env python

""" Repository Database interface module. """
import json
import os
from dataclasses import dataclass, replace
from typing import Optional, Dict, Callable

from sonic_package_manager.errors import PackageManagerError, PackageNotFoundError, PackageAlreadyExistsError
from sonic_package_manager.version import Version

BASE_LIBRARY_PATH = '/var/lib/sonic-package-manager/'
PACKAGE_MANAGER_DB_FILE_PATH = os.path.join(BASE_LIBRARY_PATH, 'packages.json')
PACKAGE_MANAGER_LOCK_FILE = os.path.join(BASE_LIBRARY_PATH, '.lock')


@dataclass(order=True)
class PackageEntry:
    """ Package database single entry object.

    Attributes:
        name: Name of the package
        repository: Default repository to pull package from.
        description: Package description or None if package does not
                     provide a description.
        default_reference: Default reference (tag or digest) or None
                           if default reference is not provided.
        version: Installed version of the package or None if
                 package is not installed.
        installed: Boolean flag whether the package is installed.
        built_in: Boolean flag whether the package is built in.
        image_id: Image ID for this package or None if package
                  is not installed.
        tag: Tag for this package or None if package is not installed.
    """

    name: str
    repository: Optional[str]
    description: Optional[str] = None
    default_reference: Optional[str] = None
    version: Optional[Version] = None
    installed: bool = False
    built_in: bool = False
    image_id: Optional[str] = None
    tag: Optional[str] = None


def package_from_dict(name: str, package_info: Dict) -> PackageEntry:
    """ Parse dictionary into PackageEntry object."""

    repository = package_info.get('repository')
    description = package_info.get('description')
    default_reference = package_info.get('default-reference')
    version = package_info.get('installed-version')
    if version:
        version = Version.parse(version)
    installed = package_info.get('installed', False)
    built_in = package_info.get('built-in', False)
    image_id = package_info.get('image-id')
    tag = package_info.get('tag')
    return PackageEntry(name, repository, description,
                        default_reference, version, installed,
                        built_in, image_id, tag)


def package_to_dict(package: PackageEntry) -> Dict:
    """ Serialize package into dictionary. """

    return {
        'repository': package.repository,
        'description': package.description,
        'default-reference': package.default_reference,
        'installed-version': None if package.version is None else str(package.version),
        'installed': package.installed,
        'built-in': package.built_in,
        'image-id': package.image_id,
        'tag': package.tag,
    }


class PackageDatabase:
    """ An interface to SONiC repository database """

    def __init__(self,
                 database: Dict[str, PackageEntry],
                 on_save: Optional[Callable] = None):
        """ Initialize PackageDatabase.

        Args:
            database: Database dictionary
            on_save: Optional callback to execute on commit()
        """

        self._database = database
        self._on_save = on_save

    def add_package(self,
                    name: str,
                    repository: str,
                    description: Optional[str] = None,
                    default_reference: Optional[str] = None):
        """ Adds a new package entry in database.

        Args:
            name: Package name.
            repository: Repository URL.
            description: Description string.
            default_reference: Default version string.

        Raises:
            PackageAlreadyExistsError: if package already exists in database.
        """

        if self.has_package(name):
            raise PackageAlreadyExistsError(name)

        package = PackageEntry(name, repository, description, default_reference)
        self._database[name] = package

    def remove_package(self, name: str):
        """ Removes package entry from database.

        Args:
            name: repository name.
        Raises:
            PackageNotFoundError: Raises when package with the given name does not exist
                                  in the database.
        """

        pkg = self.get_package(name)

        if pkg.built_in:
            raise PackageManagerError(f'Package {name} is built-in, cannot remove it')

        if pkg.installed:
            raise PackageManagerError(f'Package {name} is installed, uninstall it first')

        self._database.pop(name)

    def update_package(self, pkg: PackageEntry):
        """ Modify repository in the database.

        Args:
            pkg: Repository object.
        Raises:
            PackageManagerError: Raises when repository with the given name does not exist
                                 in the database.
        """

        name = pkg.name

        if not self.has_package(name):
            raise PackageNotFoundError(name)

        self._database[name] = pkg

    def get_package(self, name: str) -> PackageEntry:
        """ Return a package referenced by name.
        If the package is not found PackageNotFoundError is thrown.

        Args:
            name: Package name.
        Returns:
            PackageInfo object.
        Raises:
            PackageNotFoundError: When package called name was not found.
        """

        try:
            pkg = self._database[name]
        except KeyError:
            raise PackageNotFoundError(name)

        return replace(pkg)

    def has_package(self, name: str) -> bool:
        """ Checks if the database contains an entry for a package.
        called name. Returns True if the package exists, otherwise False.

        Args:
            name: Package name.
        Returns:
            True if the package exists, otherwise False.
        """

        try:
            self.get_package(name)
            return True
        except PackageNotFoundError:
            return False

    def __iter__(self):
        """ Iterates over packages in the database.

        Yields:
            PackageInfo object.
        """

        for name, _ in self._database.items():
            yield self.get_package(name)

    @staticmethod
    def from_file(db_file=PACKAGE_MANAGER_DB_FILE_PATH) -> 'PackageDatabase':
        """ Read database content from file. """

        def on_save(database):
            with open(db_file, 'w') as db:
                db_content = {}
                for name, package in database.items():
                    db_content[name] = package_to_dict(package)
                json.dump(db_content, db, indent=4)

        database = {}
        with open(db_file) as db:
            db_content = json.load(db)
            for key in db_content:
                package = package_from_dict(key, db_content[key])
                database[key] = package
        return PackageDatabase(database, on_save)

    def commit(self):
        """ Save database content to file. """

        if self._on_save:
            self._on_save(self._database)

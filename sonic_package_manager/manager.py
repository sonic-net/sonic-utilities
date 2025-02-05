#!/usr/bin/env python

import contextlib
import functools
import os
import pkgutil
import tempfile
import yang as ly
from inspect import signature
from typing import Any, Iterable, List, Callable, Dict, Optional

import docker
import filelock
from config import config_mgmt
from sonic_py_common import device_info

from sonic_cli_gen.generator import CliGenerator

from sonic_package_manager import utils
from sonic_package_manager.constraint import (
    VersionConstraint,
    PackageConstraint
)
from sonic_package_manager.database import (
    PACKAGE_MANAGER_LOCK_FILE,
    PackageDatabase
)
from sonic_package_manager.dockerapi import DockerApi
from sonic_package_manager.errors import (
    PackageManagerError,
    PackageDependencyError,
    PackageComponentDependencyError,
    PackageConflictError,
    PackageComponentConflictError,
    PackageInstallationError,
    PackageSonicRequirementError,
    PackageUninstallationError,
    PackageUpgradeError
)
from sonic_package_manager.logger import log
from sonic_package_manager.metadata import MetadataResolver
from sonic_package_manager.package import Package
from sonic_package_manager.progress import ProgressManager
from sonic_package_manager.reference import PackageReference
from sonic_package_manager.registry import RegistryResolver
from sonic_package_manager.service_creator import SONIC_CLI_COMMANDS
from sonic_package_manager.service_creator.creator import (
    ServiceCreator,
    run_command
)
from sonic_package_manager.service_creator.feature import FeatureRegistry
from sonic_package_manager.service_creator.sonic_db import (
    INIT_CFG_JSON,
    SonicDB
)
from sonic_package_manager.service_creator.utils import in_chroot
from sonic_package_manager.source import (
    PackageSource,
    LocalSource,
    RegistrySource,
    TarballSource
)
from sonic_package_manager.version import (
    Version,
    version_to_tag,
    tag_to_version
)
import click
import json
import requests
import getpass
import paramiko
import urllib.parse
from scp import SCPClient
from sonic_package_manager.manifest import Manifest, MANIFESTS_LOCATION, DEFAULT_MANIFEST_FILE
LOCAL_JSON = "/tmp/local_json"

@contextlib.contextmanager
def failure_ignore(ignore: bool):
    """ Ignores failures based on parameter passed. """

    try:
        yield
    except Exception as err:
        if ignore:
            log.warning(f'ignoring error {err}')
        else:
            raise


def under_lock(func: Callable) -> Callable:
    """ Execute operations under lock. """

    @functools.wraps(func)
    def wrapped_function(*args, **kwargs):
        self = args[0]
        with self.lock:
            return func(*args, **kwargs)

    return wrapped_function


def opt_check(func: Callable) -> Callable:
    """ Check kwargs for function. """

    @functools.wraps(func)
    def wrapped_function(*args, **kwargs):
        sig = signature(func)
        unsupported_opts = [opt for opt in kwargs if opt not in sig.parameters]
        if unsupported_opts:
            raise PackageManagerError(
                f'Unsupported options {unsupported_opts} for {func.__name__}'
            )
        return func(*args, **kwargs)

    return wrapped_function


def rollback(func, *args, **kwargs) -> Callable:
    """ Used in rollback callbacks to ignore failure
    but proceed with rollback. Error will be printed
    but not fail the whole procedure of rollback. """

    @functools.wraps(func)
    def wrapper():
        try:
            func(*args, **kwargs)
        except Exception as err:
            log.error(f'failed in rollback: {err}')

    return wrapper


def package_constraint_to_reference(constraint: PackageConstraint) -> PackageReference:
    package_name, version_constraint = constraint.name, constraint.constraint
    # Allow only specific version for now.
    # Later we can improve package manager to support
    # installing packages using expressions like 'package>1.0.0'
    if version_constraint.expression == '*':
        return PackageReference(package_name, None)
    if not version_constraint.is_exact():
        raise PackageManagerError(f'Can only install specific version. '
                                  f'Use only following expression "{package_name}=<version>" '
                                  f'to install specific version')
    version = version_constraint.get_exact_version()
    return PackageReference(package_name, version_to_tag(version))


def parse_reference_expression(expression) -> PackageReference:
    try:
        return package_constraint_to_reference(PackageConstraint.parse(expression))
    except ValueError:
        # if we failed to parse the expression as constraint expression
        # we will try to parse it as reference
        return PackageReference.parse(expression)


def get_cli_plugin_directory(command: str) -> str:
    """ Returns a plugins package directory for command group.

    Args:
        command: SONiC command: "show"/"config"/"clear".
    Returns:
        Path to plugins package directory.
    """

    pkg_loader = pkgutil.get_loader(f'{command}.plugins')
    if pkg_loader is None:
        raise PackageManagerError(f'Failed to get plugins path for {command} CLI')
    plugins_pkg_path = os.path.dirname(pkg_loader.path)
    return plugins_pkg_path


def get_cli_plugin_path(package: Package, index: int, command: str) -> str:
    """ Returns a path where to put CLI plugin code.

    Args:
        package: Package to generate this path for.
        index: Index of a cli plugin
        command: SONiC command: "show"/"config"/"clear".
    Returns:
        Path generated for this package.
    """

    if index == 0:
        plugin_module_file = f'{package.name}.py'
    else:
        plugin_module_file = f'{package.name}_{index}.py'

    return os.path.join(get_cli_plugin_directory(command), plugin_module_file)


def validate_package_base_os_constraints(package: Package, sonic_version_info: Dict[str, str]):
    """ Verify that all dependencies on base OS components are met.
    Args:
        package: Package to check constraints for.
        sonic_version_info: SONiC components version information.
    Raises:
        PackageSonicRequirementError: in case dependency is not satisfied.
    """

    base_os_constraints = package.manifest['package']['base-os'].components
    for component, constraint in base_os_constraints.items():
        if component not in sonic_version_info:
            raise PackageSonicRequirementError(package.name, component, constraint)

        version = Version.parse(sonic_version_info[component])

        if not constraint.allows(version):
            raise PackageSonicRequirementError(package.name, component, constraint, version)


def validate_package_tree(packages: Dict[str, Package]):
    """ Verify that all dependencies are met in all packages passed to this function.
    Args:
        packages: list of packages to check
    Raises:
        PackageDependencyError: if dependency is missing
        PackageConflictError: if there is a conflict between packages
    """

    for name, package in packages.items():
        log.debug(f'checking dependencies for {name}')
        for dependency in package.manifest['package']['depends']:
            dependency_package = packages.get(dependency.name)
            if dependency_package is None:
                raise PackageDependencyError(package.name, dependency)

            installed_version = dependency_package.version
            log.debug(f'dependency package is installed {dependency.name}: {installed_version}')
            if not dependency.constraint.allows(installed_version):
                raise PackageDependencyError(package.name, dependency, installed_version)

            dependency_components = dependency.components
            if not dependency_components:
                dependency_components = {}
                for component, version in package.components.items():
                    implicit_constraint = VersionConstraint.parse(f'^{version.major}.{version.minor}.0')
                    dependency_components[component] = implicit_constraint

            for component, constraint in dependency_components.items():
                if component not in dependency_package.components:
                    raise PackageComponentDependencyError(package.name, dependency,
                                                          component, constraint)

                component_version = dependency_package.components[component]
                log.debug(f'dependency package {dependency.name}: '
                          f'component {component} version is {component_version}')

                if not constraint.allows(component_version):
                    raise PackageComponentDependencyError(package.name, dependency, component,
                                                          constraint, component_version)

        log.debug(f'checking conflicts for {name}')
        for conflict in package.manifest['package']['breaks']:
            conflicting_package = packages.get(conflict.name)
            if conflicting_package is None:
                continue

            installed_version = conflicting_package.version
            log.debug(f'conflicting package is installed {conflict.name}: {installed_version}')
            if conflict.constraint.allows(installed_version):
                raise PackageConflictError(package.name, conflict, installed_version)

            for component, constraint in conflicting_package.components.items():
                if component not in conflicting_package.components:
                    continue

                component_version = conflicting_package.components[component]
                log.debug(f'conflicting package {conflict.name}: '
                          f'component {component} version is {component_version}')

                if constraint.allows(component_version):
                    raise PackageComponentConflictError(package.name, dependency, component,
                                                        constraint, component_version)


def validate_package_cli_can_be_skipped(package: Package, skip: bool):
    """ Checks whether package CLI installation can be skipped.

    Args:
        package: Package to validate
        skip: Whether to skip installing CLI

    Raises:
        PackageManagerError

    """

    if package.manifest['cli']['mandatory'] and skip:
        raise PackageManagerError(f'CLI is mandatory for package {package.name} '
                                  f'but it was requested to be not installed')
    elif skip:
        log.warning(f'Package {package.name} CLI plugin will not be installed')


class PackageManager:
    """ SONiC Package Manager. This class provides public API
    for sonic_package_manager python library. It has functionality
    for installing, uninstalling, updating SONiC packages as well as
    retrieving information about the packages from different sources. """

    def __init__(self,
                 docker_api: DockerApi,
                 registry_resolver: RegistryResolver,
                 database: PackageDatabase,
                 metadata_resolver: MetadataResolver,
                 service_creator: ServiceCreator,
                 device_information: Any,
                 lock: filelock.FileLock):
        """ Initialize PackageManager. """

        self.lock = lock
        self.docker = docker_api
        self.registry_resolver = registry_resolver
        self.database = database
        self.metadata_resolver = metadata_resolver
        self.service_creator = service_creator
        self.sonic_db = service_creator.sonic_db
        self.feature_registry = service_creator.feature_registry
        self.is_multi_npu = device_information.is_multi_npu()
        self.num_npus = device_information.get_num_npus()
        self.version_info = device_information.get_sonic_version_info()

    @under_lock
    def add_repository(self, *args, **kwargs):
        """ Add repository to package database
        and commit database content.

        Args:
            args: Arguments to pass to PackageDatabase.add_package
            kwargs: Keyword arguments to pass to PackageDatabase.add_package
        """

        self.database.add_package(*args, **kwargs)
        self.database.commit()

    @under_lock
    def remove_repository(self, name: str):
        """ Remove repository from package database
        and commit database content.

        Args:
            name: package name
        """

        self.database.remove_package(name)
        self.database.commit()

    @under_lock
    def install(self,
                expression: Optional[str] = None,
                repotag: Optional[str] = None,
                tarball: Optional[str] = None,
                use_local_manifest: bool = False,
                name: Optional[str] = None,
                **kwargs):
        """ Install/Upgrade SONiC Package from either an expression
        representing the package and its version, repository and tag or
        digest in same format as "docker pulL" accepts or an image tarball path.

        Args:
            expression: SONiC Package reference expression
            repotag: Install/Upgrade from REPO[:TAG][@DIGEST]
            tarball: Install/Upgrade from tarball, path to tarball file
            kwargs: Install/Upgrade options for self.install_from_source
        Raises:
            PackageManagerError
        """

        source = self.get_package_source(expression, repotag, tarball, use_local_manifest=use_local_manifest, name=name)
        package = source.get_package()

        if self.is_installed(package.name):
            self.upgrade_from_source(source, **kwargs)
        else:
            self.install_from_source(source, **kwargs)

    @under_lock
    @opt_check
    def install_from_source(self,
                            source: PackageSource,
                            force=False,
                            enable=False,
                            default_owner='local',
                            skip_host_plugins=False):
        """ Install SONiC Package from source represented by PackageSource.
        This method contains the logic of package installation.

        Args:
            source: SONiC Package source.
            force: Force the installation.
            enable: If True the installed feature package will be enabled.
            default_owner: Owner of the installed package.
            skip_host_plugins: Skip CLI plugin installation.
        Raises:
            PackageManagerError
        """

        package = source.get_package()
        name = package.name

        with failure_ignore(force):
            if self.is_installed(name):
                raise PackageInstallationError(f'{name} is already installed')

        version = package.manifest['package']['version']
        feature_state = 'enabled' if enable else 'disabled'
        installed_packages = self._get_installed_packages_and(package)

        with failure_ignore(force):
            validate_package_base_os_constraints(package, self.version_info)
            validate_package_tree(installed_packages)
            validate_package_cli_can_be_skipped(package, skip_host_plugins)

        # After all checks are passed we proceed to actual installation

        # When installing package from a tarball or directly from registry
        # package name may not be in database.
        if not self.database.has_package(package.name):
            self.database.add_package(package.name, package.repository)

        service_create_opts = {
            'state': feature_state,
            'owner': default_owner,
        }

        try:
            with contextlib.ExitStack() as exits:
                source.install(package)
                exits.callback(rollback(source.uninstall, package))

                self.service_creator.create(package, **service_create_opts)
                exits.callback(rollback(self.service_creator.remove, package))

                self.service_creator.generate_shutdown_sequence_files(
                    self._get_installed_packages_and(package)
                )
                exits.callback(rollback(
                    self.service_creator.generate_shutdown_sequence_files,
                    self.get_installed_packages())
                )

                if not skip_host_plugins:
                    self._install_cli_plugins(package)
                    exits.callback(rollback(self._uninstall_cli_plugins, package))

                exits.pop_all()
        except Exception as err:
            raise PackageInstallationError(f'Failed to install {package.name}: {err}')
        except KeyboardInterrupt:
            raise

        package.entry.installed = True
        package.entry.version = version
        self.database.update_package(package.entry)
        self.database.commit()

    @under_lock
    def update(self,
               name: str,
               **kwargs):
        """ Update SONiC Package referenced by name. The update
        can be forced if force argument is True.

        Args:
            name: SONiC Package name.
        Raises:
            PackageManagerError
        """
        if self.is_installed(name):
            edit_name = name + '.edit'
            edit_file = os.path.join(MANIFESTS_LOCATION, edit_name)
            if os.path.exists(edit_file):
                self.upgrade_from_source(None, name=name, **kwargs)
            else:
                click.echo("Package manifest {}.edit file does not exists to update".format(name))
                return
        else:
            click.echo("Package {} is not installed".format(name))
            return

    def remove_unused_docker_image(self, package):
        image_id_used = any(entry.image_id == package.image_id for entry in self.database if entry.name != package.name)
        if not image_id_used:
            self.docker.rmi(package.image_id, force=True)
        else:
            log.info(f'Image with ID {package.image_id} is in use by other package(s). Skipping deletion')

    @under_lock
    @opt_check
    def uninstall(self, name: str,
                  force: bool = False,
                  keep_config: bool = False):
        """ Uninstall SONiC Package referenced by name. The uninstallation
        can be forced if force argument is True.

        Args:
            name: SONiC Package name.
            force: Force the installation.
            keep_config: Keep feature configuration in databases.
        Raises:
            PackageManagerError
        """

        with failure_ignore(force):
            if not self.is_installed(name):
                raise PackageUninstallationError(f'{name} is not installed')

        package = self.get_installed_package(name)
        service_name = package.manifest['service']['name']

        with failure_ignore(force):
            if self.feature_registry.is_feature_enabled(service_name):
                raise PackageUninstallationError(
                    f'{service_name} is enabled. Disable the feature first')

        if package.built_in:
            raise PackageUninstallationError(
                f'Cannot uninstall built-in package {package.name}')

        installed_packages = self._get_installed_packages_except(package)

        with failure_ignore(force):
            validate_package_tree(installed_packages)

        # After all checks are passed we proceed to actual uninstallation

        try:
            self._disable_feature(package)
            self._uninstall_cli_plugins(package)
            self.service_creator.remove(package, keep_config=keep_config)
            self.service_creator.generate_shutdown_sequence_files(
                self._get_installed_packages_except(package)
            )
            self.docker.rm_by_ancestor(package.image_id, force=True)
            # Delete image if it is not in use, otherwise skip deletion
            self.remove_unused_docker_image(package)
            package.entry.image_id = None
        except Exception as err:
            raise PackageUninstallationError(
                f'Failed to uninstall {package.name}: {err}'
            )

        package.entry.installed = False
        package.entry.version = None
        self.database.update_package(package.entry)
        self.database.commit()
        manifest_path = os.path.join(MANIFESTS_LOCATION, name)
        edit_path = os.path.join(MANIFESTS_LOCATION, name + ".edit")
        if os.path.exists(manifest_path):
            os.remove(manifest_path)
        if os.path.exists(edit_path):
            os.remove(edit_path)


    @under_lock
    @opt_check
    def upgrade_from_source(self,
                            source: PackageSource,
                            force=False,
                            skip_host_plugins=False,
                            allow_downgrade=False,
                            update_only: Optional[bool] = False,
                            name: Optional[str] = None):
        """ Upgrade SONiC Package to a version the package reference
        expression specifies. Can force the upgrade if force parameter
        is True. Force can allow a package downgrade.

        Args:
            source: SONiC Package source
            force: Force the upgrade.
            skip_host_plugins: Skip host OS plugins installation.
            allow_downgrade: Flag to allow package downgrade.
            update_only: Perform package update with new manifest.
            name: name of package.
        Raises:
            PackageManagerError
        """

        if update_only:
            new_package = self.get_installed_package(name, use_edit=True)
        else:
            new_package = source.get_package()
            name = new_package.name

        with failure_ignore(force):
            if not self.is_installed(name):
                raise PackageUpgradeError(f'{name} is not installed')

        old_package = self.get_installed_package(name)

        if old_package.built_in:
            raise PackageUpgradeError(
                f'Cannot upgrade built-in package {old_package.name}'
            )

        old_feature = old_package.manifest['service']['name']
        old_version = old_package.manifest['package']['version']
        new_version = new_package.manifest['package']['version']

        if not update_only:
            with failure_ignore(force):
                if old_version == new_version:
                    raise PackageUpgradeError(f'{new_version} is already installed')

                # TODO: Not all packages might support downgrade.
                # We put a check here but we understand that for some packages
                # the downgrade might be safe to do. There can be a variable in manifest
                # describing package downgrade ability or downgrade-able versions.
                if new_version < old_version and not allow_downgrade:
                    raise PackageUpgradeError(
                        f'Request to downgrade from {old_version} to {new_version}. '
                        f'Downgrade might be not supported by the package'
                    )

        # remove currently installed package from the list
        installed_packages = self._get_installed_packages_and(new_package)

        with failure_ignore(force):
            validate_package_base_os_constraints(new_package, self.version_info)
            validate_package_tree(installed_packages)
            validate_package_cli_can_be_skipped(new_package, skip_host_plugins)

        # After all checks are passed we proceed to actual upgrade

        service_create_opts = {
            'register_feature': False,
        }
        service_remove_opts = {
            'deregister_feature': False,
        }

        try:
            with contextlib.ExitStack() as exits:
                self._uninstall_cli_plugins(old_package)
                exits.callback(rollback(self._install_cli_plugins, old_package))

                if not update_only:
                    source.install(new_package)
                    exits.callback(rollback(source.uninstall, new_package))

                feature_enabled = self.feature_registry.is_feature_enabled(old_feature)

                if feature_enabled:
                    self._stop_feature(old_package)
                    exits.callback(rollback(self._start_feature, old_package))

                self.service_creator.remove(old_package, **service_remove_opts)
                exits.callback(rollback(self.service_creator.create, old_package,
                                        **service_create_opts))

                self.docker.rm_by_ancestor(old_package.image_id, force=True)

                self.service_creator.create(new_package, **service_create_opts)
                exits.callback(rollback(self.service_creator.remove, new_package,
                                        **service_remove_opts))

                self.service_creator.generate_shutdown_sequence_files(
                    self._get_installed_packages_and(new_package)
                )
                exits.callback(rollback(
                    self.service_creator.generate_shutdown_sequence_files,
                    self._get_installed_packages_and(old_package))
                )

                self.feature_registry.update(old_package.manifest, new_package.manifest)
                exits.callback(rollback(
                    self.feature_registry.update, new_package.manifest, old_package.manifest)
                )

                # If old feature was enabled, the user should have the new feature enabled as well.
                if feature_enabled:
                    self._start_feature(new_package)
                    exits.callback(rollback(self._stop_feature, new_package))

                if not skip_host_plugins:
                    self._install_cli_plugins(new_package)
                    exits.callback(rollback(self._uninstall_cli_plugin, new_package))

                if old_package.image_id != new_package.image_id:
                    self.remove_unused_docker_image(old_package)

                exits.pop_all()
        except Exception as err:
            raise PackageUpgradeError(f'Failed to upgrade {new_package.name}: {err}')
        except KeyboardInterrupt:
            raise

        new_package_entry = new_package.entry
        new_package_entry.installed = True
        new_package_entry.version = new_version
        self.database.update_package(new_package_entry)
        self.database.commit()
        if update_only:
            manifest_path = os.path.join(MANIFESTS_LOCATION, name)
            edit_path = os.path.join(MANIFESTS_LOCATION, name + ".edit")
            os.rename(edit_path, manifest_path)

    @under_lock
    @opt_check
    def reset(self, name: str, force: bool = False, skip_host_plugins: bool = False):
        """ Reset package to defaults version

        Args:
            name: SONiC Package name.
            force: Force the installation.
            skip_host_plugins: Skip host plugins installation.
        Raises:
            PackageManagerError
        """

        with failure_ignore(force):
            if not self.is_installed(name):
                raise PackageManagerError(f'{name} is not installed')

        package = self.get_installed_package(name)
        default_reference = package.entry.default_reference
        if default_reference is None:
            raise PackageManagerError(f'package {name} has no default reference')

        package_ref = PackageReference(name, default_reference)
        source = self.get_package_source(package_ref=package_ref)
        self.upgrade_from_source(source, force=force,
                                 allow_downgrade=True,
                                 skip_host_plugins=skip_host_plugins)

    @under_lock
    def get_docker_client(self, dockerd_sock:str):
        return docker.DockerClient(base_url=f'unix://{dockerd_sock}', timeout=120)

    @under_lock
    def migrate_packages(self,
                         old_package_database: PackageDatabase,
                         dockerd_sock: Optional[str] = None):
        """
        Migrate packages from old database. This function can do a comparison between
        current database and the database passed in as argument. If the package is
        missing in the current database it will be added. If the package is installed
        in the passed database and in the current it is not installed it will be
        installed with a passed database package version. If the package is installed
        in the passed database and it is installed in the current database but with
        older version the package will be upgraded to the never version. If the package
        is installed in the passed database and in the current it is installed but with
        never version - no actions are taken. If dockerd_sock parameter is passed, the
        migration process will use loaded images from docker library of the currently
        installed image.

        Args:
            old_package_database: SONiC Package Database to migrate packages from.
            dockerd_sock: Path to dockerd socket.
        Raises:
            PackageManagerError
        """

        self._migrate_package_database(old_package_database)

        def migrate_package(old_package_entry,
                            new_package_entry):
            """ Migrate package routine

            Args:
                old_package_entry: Entry in old package database.
                new_package_entry: Entry in new package database.
            """

            name = new_package_entry.name
            version = new_package_entry.version

            if dockerd_sock:
                # dockerd_sock is defined, so use docked_sock to connect to
                # dockerd and fetch package image from it.
                log.info(f'installing {name} from old docker library')
                docker_client = self.get_docker_client(dockerd_sock)
                docker_api = DockerApi(docker_client)

                image = docker_api.get_image(old_package_entry.image_id)

                with tempfile.NamedTemporaryFile('wb') as file:
                    for chunk in image.save(named=True):
                        file.write(chunk)
                    file.flush()

                    self.install(tarball=file.name, name=name)
            else:
                log.info(f'installing {name} version {version}')

                self.install(f'{name}={version}')

        # TODO: Topological sort packages by their dependencies first.
        for old_package in old_package_database:
            if not old_package.installed or old_package.built_in:
                continue

            log.info(f'migrating package {old_package.name}')

            new_package = self.database.get_package(old_package.name)

            if new_package.installed:
                if old_package.version > new_package.version:
                    log.info(f'{old_package.name} package version is greater '
                             f'then installed in new image: '
                             f'{old_package.version} > {new_package.version}')
                    log.info(f'upgrading {new_package.name} to {old_package.version}')
                    new_package.version = old_package.version
                    migrate_package(old_package, new_package)
                else:
                    log.info(f'skipping {new_package.name} as installed version is newer')
            elif new_package.default_reference is not None:
                new_package_ref = PackageReference(new_package.name, new_package.default_reference)
                package_source = self.get_package_source(package_ref=new_package_ref)
                package = package_source.get_package()
                new_package_default_version = package.manifest['package']['version']
                if old_package.version > new_package_default_version:
                    log.info(f'{old_package.name} package version is lower '
                             f'then the default in new image: '
                             f'{old_package.version} > {new_package_default_version}')
                    new_package.version = old_package.version
                    migrate_package(old_package, new_package)
                else:
                    # self.install(f'{new_package.name}={new_package_default_version}')
                    repo_tag_formed = "{}:{}".format(new_package.repository, new_package.default_reference)
                    self.install(None, repo_tag_formed, name=new_package.name)
            else:
                # No default version and package is not installed.
                # Migrate old package same version.
                new_package.version = old_package.version
                migrate_package(old_package, new_package)

            self.database.commit()

    def get_installed_package(self, name: str, use_local_manifest: bool = False, use_edit: bool = False) -> Package:
        """ Get installed package by name.

        Args:
            name: package name.
        Returns:
            Package object.
        """

        package_entry = self.database.get_package(name)
        source = LocalSource(package_entry,
                             self.database,
                             self.docker,
                             self.metadata_resolver,
                             use_local_manifest=use_local_manifest,
                             name=name,
                             use_edit=use_edit)
        return source.get_package()

    def get_package_source(self,
                           package_expression: Optional[str] = None,
                           repository_reference: Optional[str] = None,
                           tarboll_path: Optional[str] = None,
                           package_ref: Optional[PackageReference] = None,
                           use_local_manifest: bool = False,
                           name: Optional[str] = None):
        """ Returns PackageSource object based on input source.

        Args:
             package_expression: SONiC Package expression string
             repository_reference: Install from REPO[:TAG][@DIGEST]
             tarboll_path: Install from image tarball
             package_ref: Package reference object
        Returns:
            SONiC Package object.
         Raises:
             ValueError if no source specified.
        """

        if package_expression:
            ref = parse_reference_expression(package_expression)
            return self.get_package_source(package_ref=ref, name=name)
        elif repository_reference:
            repo_ref = utils.DockerReference.parse(repository_reference)
            repository = repo_ref['name']
            reference = repo_ref['tag'] or repo_ref['digest']
            reference = reference or 'latest'
            return RegistrySource(repository,
                                  reference,
                                  self.database,
                                  self.docker,
                                  self.metadata_resolver,
                                  use_local_manifest,
                                  name)
        elif tarboll_path:
            return TarballSource(tarboll_path,
                                 self.database,
                                 self.docker,
                                 self.metadata_resolver,
                                 use_local_manifest,
                                 name)
        elif package_ref:
            package_entry = self.database.get_package(package_ref.name)
            name = package_ref.name
            # Determine the reference if not specified.
            # If package is installed assume the installed
            # one is requested, otherwise look for default
            # reference defined for this package. In case package
            # does not have a default reference raise an error.
            if package_ref.reference is None:
                if package_entry.installed:
                    return LocalSource(package_entry,
                                       self.database,
                                       self.docker,
                                       self.metadata_resolver,
                                       use_local_manifest,
                                       name)
                if package_entry.default_reference is not None:
                    package_ref.reference = package_entry.default_reference
                else:
                    raise PackageManagerError('No default reference tag. '
                                              'Please specify the version or tag explicitly')

            return RegistrySource(package_entry.repository,
                                  package_ref.reference,
                                  self.database,
                                  self.docker,
                                  self.metadata_resolver,
                                  use_local_manifest,
                                  name)
        else:
            raise ValueError('No package source provided')

    def get_package_available_versions(self,
                                       name: str,
                                       all: bool = False) -> Iterable:
        """ Returns a list of available versions for package.

        Args:
            name: Package name.
            all: If set to True will return all tags including
                 those which do not follow semantic versioning.
        Returns:
            List of versions
        """
        package_info = self.database.get_package(name)
        registry = self.registry_resolver.get_registry_for(package_info.repository)
        available_tags = registry.tags(package_info.repository)

        def is_semantic_ver_tag(tag: str) -> bool:
            try:
                tag_to_version(tag)
                return True
            except ValueError:
                pass
            return False

        if all:
            return available_tags

        return map(tag_to_version, filter(is_semantic_ver_tag, available_tags))

    def is_installed(self, name: str) -> bool:
        """ Returns boolean whether a package called name is installed.

        Args:
            name: Package name.
        Returns:
            True if package is installed, False otherwise.
        """

        if not self.database.has_package(name):
            return False
        package_info = self.database.get_package(name)
        return package_info.installed

    def get_installed_packages(self) -> Dict[str, Package]:
        """ Returns a dictionary of installed packages where
        keys are package names and values are package objects.

        Returns:
            Installed packages dictionary.
        """

        return {
            entry.name: entry for entry in self.get_installed_packages_list()
        }

    def get_installed_packages_list(self) -> List[Package]:
        """ Returns a list of installed packages.

        Returns:
            Installed packages dictionary.
        """

        return [self.get_installed_package(entry.name)
                for entry in self.database if entry.installed]

    def _migrate_package_database(self, old_package_database: PackageDatabase):
        """ Performs part of package migration process.
        For every package in  old_package_database that is not listed in current
        database add a corresponding entry to current database. """

        for package in old_package_database:
            if not self.database.has_package(package.name):
                self.database.add_package(package.name,
                                          package.repository,
                                          package.description,
                                          package.default_reference)

    def _get_installed_packages_and(self, package: Package) -> Dict[str, Package]:
        """ Returns a dictionary of installed packages with their names as keys
        adding a package provided in the argument. """

        packages = self.get_installed_packages()
        packages[package.name] = package
        return packages

    def _get_installed_packages_except(self, package: Package) -> Dict[str, Package]:
        """ Returns a dictionary of installed packages with their names as keys
        removing a package provided in the argument. """

        packages = self.get_installed_packages()
        packages.pop(package.name)
        return packages

    def _stop_feature(self, package: Package):
        self._systemctl_action(package, 'stop')
        self._systemctl_action(package, 'disable')

    def _start_feature(self, package: Package):
        self._systemctl_action(package, 'enable')
        self._systemctl_action(package, 'start')

    def _systemctl_action(self, package: Package, action: str):
        """ Execute systemctl action for a service. """

        name = package.manifest['service']['name']
        log.info('Execute systemctl action {} on {} service'.format(action, name))

        host_service = package.manifest['service']['host-service']
        asic_service = package.manifest['service']['asic-service']
        single_instance = host_service or (asic_service and not self.is_multi_npu)
        multi_instance = asic_service and self.is_multi_npu
        if single_instance:
            run_command(['systemctl', action, name])
        if multi_instance:
            for npu in range(self.num_npus):
                run_command(['systemctl', action, f'{name}@{npu}'])

    def _disable_feature(self, package: Package, block: bool = True):
        """ Stops the feature and blocks till operation is finished if
        block argument is set to True.

        Args:
            package: Package object of the feature that will be stopped.
            block: Whether to block for operation completion.
        """

        self._set_feature_state(package, 'disabled', block)

    def _set_feature_state(self, package: Package, state: str, block: bool = True):
        """ Sets the feature state and blocks till operation is finished if
        block argument is set to True.

        Args:
            package: Package object of the feature that will be stopped.
            state: Feature state to set.
            block: Whether to block for operation completion.
        """

        if in_chroot():
            return

        # import from here otherwise this import will fail when executing
        # sonic-package-manager from chroot environment as "config" package
        # tries accessing database at import time.
        from config.feature import set_feature_state

        feature_name = package.manifest['service']['name']
        log.info('{} {}'.format(state.replace('ed', 'ing').capitalize(), feature_name))
        cfgdb_clients = {'': self.sonic_db.get_running_db_connector()}
        set_feature_state(cfgdb_clients, feature_name, state, block)

    def _install_cli_plugins(self, package: Package):
        for command in SONIC_CLI_COMMANDS:
            self._install_cli_plugin(package, command)

    def _uninstall_cli_plugins(self, package: Package):
        for command in SONIC_CLI_COMMANDS:
            self._uninstall_cli_plugin(package, command)

    def _install_cli_plugin(self, package: Package, command: str):
        image_plugins = package.manifest['cli'][command]
        if not image_plugins:
            return
        for index, image_plugin_path in enumerate(image_plugins):
            host_plugin_path = get_cli_plugin_path(package, index, command)
            self.docker.extract(package.entry.image_id, image_plugin_path, host_plugin_path)

    def _uninstall_cli_plugin(self, package: Package, command: str):
        image_plugins = package.manifest['cli'][command]
        if not image_plugins:
            return
        for index, _ in enumerate(image_plugins):
            host_plugin_path = get_cli_plugin_path(package, index, command)
            if os.path.exists(host_plugin_path):
                os.remove(host_plugin_path)

    def download_file(self, url, local_path):
        # Parse information from the URL
        parsed_url = urllib.parse.urlparse(url)
        protocol = parsed_url.scheme
        username = parsed_url.username
        password = parsed_url.password
        hostname = parsed_url.hostname
        remote_path = parsed_url.path
        supported_protocols = ['http', 'https', 'scp', 'sftp']

        # clear the temporary local file
        if os.path.exists(local_path):
            os.remove(local_path)

        if not protocol:
            # check for local file
            if os.path.exists(url):
                os.rename(url, local_path)
                return True
            else:
                click.echo("Local file not present")
                return False
        if protocol not in supported_protocols:
            click.echo("Protocol not supported")
            return False

        # If the protocol is HTTP and no username or password is provided, proceed with the download using requests
        if (protocol == 'http' or protocol == 'https') and not username and not password:
            try:
                with requests.get(url, stream=True) as response:
                    response.raise_for_status()
                    with open(local_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
            except requests.exceptions.RequestException as e:
                click.echo("Download error", e)
                return False
        else:
            # If password is not provided, prompt the user for it securely
            if password is None:
                password = getpass.getpass(prompt=f"Enter password for {username}@{hostname}: ")

            # Create an SSH client
            client = paramiko.SSHClient()
            # Automatically add the server's host key (this is insecure and should be handled differently in production)
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            try:
                # Connect to the SSH server
                client.connect(hostname, username=username, password=password)

                if protocol == 'scp':
                    # Create an SCP client
                    scp = SCPClient(client.get_transport())
                    # Download the file
                    scp.get(remote_path, local_path)
                elif protocol == 'sftp':
                    # Open an SFTP channel
                    with client.open_sftp() as sftp:
                        # Download the file
                        sftp.get(remote_path, local_path)
                elif protocol == 'http' or protocol == 'https':
                    # Download using HTTP for URLs without credentials
                    try:
                        with requests.get(url, auth=(username, password), stream=True) as response:
                            response.raise_for_status()  # Raise an exception if the request was not successful
                            with open(local_path, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=8192):
                                    if chunk:
                                        f.write(chunk)
                    except requests.exceptions.RequestException as e:
                        click.echo("Download error", e)
                        return False
                else:
                    click.echo(f"Error: Source file '{remote_path}' does not exist.")

            finally:
                # Close the SSH connection
                client.close()

    def create_package_manifest(self, name, from_json):
        if name == "default_manifest":
            click.echo("Default Manifest creation is not allowed by user")
            return
        if self.is_installed(name):
            click.echo("Error: A package with the same name {} is already installed".format(name))
            return
        mfile_name = os.path.join(MANIFESTS_LOCATION, name)
        if os.path.exists(mfile_name):
            click.echo("Error: Manifest file '{}' already exists.".format(name))
            return

        if from_json:
            ret = self.download_file(from_json, LOCAL_JSON)
            if ret is False:
                return
            from_json = LOCAL_JSON
        else:
            from_json = DEFAULT_MANIFEST_FILE
        data = {}
        with open(from_json, 'r') as file:
            data = json.load(file)
            # Validate with manifest scheme
            Manifest.marshal(data)

            # Make sure the 'name' is overwritten into the dict
            data['package']['name'] = name
            data['service']['name'] = name

            with open(mfile_name, 'w') as file:
                json.dump(data, file, indent=4)
        click.echo(f"Manifest '{name}' created successfully.")

    def update_package_manifest(self, name, from_json):
        if name == "default_manifest":
            click.echo("Default Manifest updation is not allowed")
            return

        original_file = os.path.join(MANIFESTS_LOCATION, name)
        if not os.path.exists(original_file):
            click.echo(f'Local Manifest file for {name} does not exists to update')
            return
        # download json file from remote/local path
        ret = self.download_file(from_json, LOCAL_JSON)
        if ret is False:
            return
        from_json = LOCAL_JSON

        with open(from_json, 'r') as file:
            data = json.load(file)

        # Validate with manifest scheme
        Manifest.marshal(data)

        # Make sure the 'name' is overwritten into the dict
        data['package']['name'] = name
        data['service']['name'] = name

        if self.is_installed(name):
            edit_name = name + '.edit'
            edit_file = os.path.join(MANIFESTS_LOCATION, edit_name)
            with open(edit_file, 'w') as edit_file:
                json.dump(data, edit_file, indent=4)
            click.echo(f"Manifest '{name}' updated successfully.")
        else:
            # If package is not installed,
            # update the name file directly
            with open(original_file, 'w') as orig_file:
                json.dump(data, orig_file, indent=4)
            click.echo(f"Manifest '{name}' updated successfully.")

    def delete_package_manifest(self, name):
        if name == "default_manifest":
            click.echo("Default Manifest deletion is not allowed")
            return
        # Check if the manifest file exists
        mfile_name = "{}/{}".format(MANIFESTS_LOCATION, name)
        if not os.path.exists(mfile_name):
            click.echo("Error: Manifest file '{}' not found.".format(name))
            return
        # Confirm deletion with user input
        confirm = click.prompt("Are you sure you want to delete the manifest file '{}'? (y/n)".format(name), type=str)
        if confirm.lower() == 'y':
            os.remove(mfile_name)
            click.echo("Manifest '{}' deleted successfully.".format(name))
        else:
            click.echo("Deletion cancelled.")
            return

    def show_package_manifest(self, name):
        mfile_name = "{}/{}".format(MANIFESTS_LOCATION, name)
        edit_file_name = "{}.edit".format(mfile_name)
        if os.path.exists(edit_file_name):
            mfile_name = edit_file_name
        with open(mfile_name, 'r') as file:
            data = json.load(file)
            click.echo("Manifest file: {}".format(name))
            click.echo(json.dumps(data, indent=4))

    def list_package_manifest(self):
        # Get all files in the manifest location
        manifest_files = os.listdir(MANIFESTS_LOCATION)
        if not manifest_files:
            click.echo("No custom local manifest files found.")
        else:
            click.echo("Custom Local Manifest files:")
            for file in manifest_files:
                click.echo("- {}".format(file))

    @staticmethod
    def get_manager() -> 'PackageManager':
        """ Creates and returns PackageManager instance.

        Returns:
            PackageManager
        """

        docker_api = DockerApi(docker.from_env(), ProgressManager())
        registry_resolver = RegistryResolver()
        metadata_resolver = MetadataResolver(docker_api, registry_resolver)
        cfg_mgmt = config_mgmt.ConfigMgmt(source=INIT_CFG_JSON, sonicYangOptions=ly.LY_CTX_DISABLE_SEARCHDIR_CWD)
        cli_generator = CliGenerator(log)
        feature_registry = FeatureRegistry(SonicDB)
        service_creator = ServiceCreator(feature_registry,
                                         SonicDB,
                                         cli_generator,
                                         cfg_mgmt)

        return PackageManager(docker_api,
                              registry_resolver,
                              PackageDatabase.from_file(),
                              metadata_resolver,
                              service_creator,
                              device_info,
                              filelock.FileLock(PACKAGE_MANAGER_LOCK_FILE, timeout=0))

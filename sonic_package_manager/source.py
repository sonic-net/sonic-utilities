#!/usr/bin/env python3

from sonic_package_manager.database import PackageDatabase, PackageEntry
from sonic_package_manager.dockerapi import DockerApi, get_repository_from_image
from sonic_package_manager.metadata import Metadata, MetadataResolver
from sonic_package_manager.package import Package
from typing import Optional

class PackageSource(object):
    """ PackageSource abstracts the way manifest is read
    and image is retrieved based on different image sources.
    (i.e from registry, from tarball or locally installed) """

    def __init__(self,
                 database: PackageDatabase,
                 docker: DockerApi,
                 metadata_resolver: MetadataResolver):
        self.database = database
        self.docker = docker
        self.metadata_resolver = metadata_resolver

    def get_metadata(self) -> Metadata:
        """ Returns package manifest.
        Child class has to implement this method.

        Returns:
            Metadata
        """

        raise NotImplementedError

    def install_image(self, package: Package):
        """ Install image based on package source.
        Child class has to implement this method.

        Args:
            package: SONiC Package
        Returns:
            Docker Image object.
        """

        raise NotImplementedError

    def install(self, package: Package):
        """ Install image based on package source,
        record installation information in PackageEntry..

        Args:
            package: SONiC Package
        """

        image = self.install_image(package)
        package.entry.image_id = image.id
        if hasattr(image, 'tags') and image.tags:
            package.entry.docker_image_reference = image.tags[0]
        else:
            package.entry.docker_image_reference = image.id

        # if no repository is defined for this package
        # get repository from image
        if not package.repository:
            package.entry.repository = get_repository_from_image(image)

    def uninstall(self, package: Package):
        """ Uninstall image.

        Args:
            package: SONiC Package
        """

        self.docker.rmi(package.image_id)
        package.entry.image_id = None

    def get_package(self) -> Package:
        """ Returns SONiC Package based on manifest.

        Returns:
              SONiC Package
        """

        metadata = self.get_metadata()
        manifest = metadata.manifest

        name = manifest['package']['name']
        description = manifest['package']['description']

        # Will be resolved in install() method.
        # When installing from tarball we don't know yet
        # the repository for this package.
        repository = None

        if self.database.has_package(name):
            # inherit package database info
            package_entry = self.database.get_package(name)
        else:
            package_entry = PackageEntry(name, repository,
                                         description=description)

        return Package(
            package_entry,
            metadata
        )


class TarballSource(PackageSource):
    """ TarballSource implements PackageSource
    for locally existing image saved as tarball. """

    def __init__(self,
                 tarball_path: str,
                 database: PackageDatabase,
                 docker: DockerApi,
                 metadata_resolver: MetadataResolver,
                 use_local_manifest: bool = False,
                 name: Optional[str] = None):
        super().__init__(database,
                         docker,
                         metadata_resolver)
        self.tarball_path = tarball_path
        self.use_local_manifest = use_local_manifest
        self.name = name

    def get_metadata(self) -> Metadata:
        """ Returns manifest read from tarball. """
        return self.metadata_resolver.from_tarball(self.tarball_path,
                                                   use_local_manifest=self.use_local_manifest,
                                                   name=self.name)

    def install_image(self, package: Package):
        """ Installs image from local tarball source. """
        return self.docker.load(self.tarball_path)


class RegistrySource(PackageSource):
    """ RegistrySource implements PackageSource
    for packages that are pulled from registry. """

    def __init__(self,
                 repository: str,
                 reference: str,
                 database: PackageDatabase,
                 docker: DockerApi,
                 metadata_resolver: MetadataResolver,
                 use_local_manifest: bool = False,
                 name: Optional[str] = None):
        super().__init__(database,
                         docker,
                         metadata_resolver)
        self.repository = repository
        self.reference = reference
        self.use_local_manifest = use_local_manifest
        self.name = name

    def get_metadata(self) -> Metadata:
        """ Returns manifest read from registry. """

        return self.metadata_resolver.from_registry(self.repository,
                                                    self.reference,
                                                    self.use_local_manifest,
                                                    self.name)

    def install_image(self, package: Package):
        """ Installs image from registry. """

        image_id = self.docker.pull(self.repository, self.reference)
        if not package.entry.default_reference:
            package.entry.default_reference = self.reference
        return image_id


class LocalSource(PackageSource):
    """ LocalSource accesses local docker library to retrieve manifest
    but does not implement installation of the image. """

    def __init__(self,
                 entry: PackageEntry,
                 database: PackageDatabase,
                 docker: DockerApi,
                 metadata_resolver: MetadataResolver,
                 use_local_manifest: bool = False,
                 name: Optional[str] = None,
                 use_edit: bool = False):
        super().__init__(database,
                         docker,
                         metadata_resolver)
        self.entry = entry
        self.use_local_manifest = use_local_manifest
        self.name = name
        self.use_edit = use_edit

    def get_metadata(self) -> Metadata:
        """ Returns manifest read from locally installed Docker. """

        image = self.entry.image_id

        if self.entry.built_in:
            # Built-in (installed not via sonic-package-manager)
            # won't have image_id in database. Using their
            # repository name as image.
            image = f'{self.entry.repository}:latest'
        return self.metadata_resolver.from_local(image, self.use_local_manifest, self.name, self.use_edit)

    def get_package(self) -> Package:
        return Package(self.entry, self.get_metadata())

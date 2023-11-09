#!/usr/bin/env python

from dataclasses import dataclass
from unittest import mock
from unittest.mock import Mock, MagicMock

import pytest
from docker_image.reference import Reference

from config.config_mgmt import ConfigMgmt

from sonic_package_manager.database import PackageDatabase, PackageEntry
from sonic_package_manager.manager import DockerApi, PackageManager
from sonic_package_manager.manifest import Manifest
from sonic_package_manager.metadata import Metadata, MetadataResolver
from sonic_package_manager.registry import RegistryResolver
from sonic_package_manager.version import Version
from sonic_package_manager.service_creator.creator import *


@pytest.fixture
def mock_docker_api():
    docker = MagicMock(DockerApi)

    @dataclass
    class Image:
        id: str

        @property
        def attrs(self):
            return {'RepoTags': [self.id]}

    def pull(repo, ref):
        return Image(f'{repo}:{ref}')

    def load(filename):
        return Image(filename)

    docker.pull = MagicMock(side_effect=pull)
    docker.load = MagicMock(side_effect=load)

    yield docker


@pytest.fixture
def mock_registry_resolver():
    yield Mock(RegistryResolver)


@pytest.fixture
def mock_metadata_resolver():
    yield Mock(MetadataResolver)


@pytest.fixture
def mock_feature_registry():
    yield MagicMock()


@pytest.fixture
def mock_service_creator():
    yield Mock()


@pytest.fixture
def mock_sonic_db():
    yield MagicMock()


@pytest.fixture
def mock_config_mgmt():
    yield MagicMock()


@pytest.fixture
def mock_cli_gen():
    yield MagicMock()


@pytest.fixture
def fake_metadata_resolver():
    class FakeMetadataResolver:
        def __init__(self):
            self.metadata_store = {}
            self.add('docker-database', 'latest', 'database', '1.0.0')
            self.add('docker-orchagent', 'latest', 'swss', '1.0.0',
                     components={
                         'libswsscommon': Version.parse('1.0.0'),
                         'libsairedis': Version.parse('1.0.0')
                     },
                     warm_shutdown={
                         'before': ['syncd'],
                     },
                     fast_shutdown={
                         'before': ['syncd'],
                     },
                     processes=[
                        {
                            'name': 'orchagent',
                            'reconciles': True,
                        },
                        {
                            'name': 'neighsyncd',
                            'reconciles': True,
                        }
                     ],
            )
            self.add('docker-syncd', 'latest', 'syncd', '1.0.0')
            self.add('docker-teamd', 'latest', 'teamd', '1.0.0',
                     components={
                         'libswsscommon': Version.parse('1.0.0'),
                         'libsairedis': Version.parse('1.0.0')
                     },
                     warm_shutdown={
                         'before': ['syncd'],
                         'after': ['swss'],
                     },
                     fast_shutdown={
                         'before': ['swss'],
                     }
            )
            self.add('Azure/docker-test', '1.6.0', 'test-package', '1.6.0', yang='TEST')
            self.add('Azure/docker-test-2', '1.5.0', 'test-package-2', '1.5.0')
            self.add('Azure/docker-test-2', '2.0.0', 'test-package-2', '2.0.0')
            self.add('Azure/docker-test-3', 'latest', 'test-package-3', '1.6.0')
            self.add('Azure/docker-test-3', '1.5.0', 'test-package-3', '1.5.0')
            self.add('Azure/docker-test-3', '1.6.0', 'test-package-3', '1.6.0')
            self.add('Azure/docker-test-4', '1.5.0', 'test-package-4', '1.5.0')
            self.add('Azure/docker-test-5', '1.5.0', 'test-package-5', '1.5.0')
            self.add('Azure/docker-test-5', '1.9.0', 'test-package-5', '1.9.0')
            self.add('Azure/docker-test-6', '1.5.0', 'test-package-6', '1.5.0')
            self.add('Azure/docker-test-6', '1.9.0', 'test-package-6', '1.9.0')
            self.add('Azure/docker-test-6', '2.0.0', 'test-package-6', '2.0.0')
            self.add('Azure/docker-test-6', 'latest', 'test-package-6', '1.5.0')

        def from_registry(self, repository: str, reference: str):
            manifest = Manifest.marshal(self.metadata_store[repository][reference]['manifest'])
            components = self.metadata_store[repository][reference]['components']
            yang = self.metadata_store[repository][reference]['yang']
            return Metadata(manifest, components, yang)

        def from_local(self, image: str):
            ref = Reference.parse(image)
            manifest = Manifest.marshal(self.metadata_store[ref['name']][ref['tag']]['manifest'])
            components = self.metadata_store[ref['name']][ref['tag']]['components']
            yang = self.metadata_store[ref['name']][ref['tag']]['yang']
            return Metadata(manifest, components, yang)

        def from_tarball(self, filepath: str) -> Manifest:
            path, ref = filepath.split(':')
            manifest = Manifest.marshal(self.metadata_store[path][ref]['manifest'])
            components = self.metadata_store[path][ref]['components']
            yang = self.metadata_store[path][ref]['yang']
            return Metadata(manifest, components, yang)

        def add(self, repo, reference, name, version, components=None,
                warm_shutdown=None, fast_shutdown=None,
                processes=None, yang=None):
            repo_dict = self.metadata_store.setdefault(repo, {})
            repo_dict[reference] = {
                'manifest': {
                    'package': {
                        'version': version,
                        'name': name,
                        'base-os': {},
                    },
                    'service': {
                        'name': name,
                        'warm-shutdown': warm_shutdown or {},
                        'fast-shutdown': fast_shutdown or {},
                    },
                    'processes': processes or [],
                },
                'components': components or {},
                'yang': yang,
            }

    yield FakeMetadataResolver()


@pytest.fixture
def fake_device_info():
    class FakeDeviceInfo:
        def __init__(self):
            self.multi_npu = True
            self.num_npus = 1
            self.version_info = {
                'libswsscommon': '1.0.0',
            }

        def is_multi_npu(self):
            return self.multi_npu

        def get_num_npus(self):
            return self.num_npus

        def get_sonic_version_info(self):
            return self.version_info

    yield FakeDeviceInfo()


def add_package(content, metadata_resolver, repository, reference, **kwargs):
    metadata = metadata_resolver.from_registry(repository, reference)
    name = metadata.manifest['package']['name']
    version = metadata.manifest['package']['version']
    installed = kwargs.get('installed', False)
    built_in = kwargs.get('built-in', False)

    if installed and not built_in and 'image_id' not in kwargs:
        kwargs['image_id'] = f'{repository}:{reference}'

    if installed and 'version' not in kwargs:
        kwargs['version'] = version

    content[name] = PackageEntry(name, repository, **kwargs)


@pytest.fixture
def fake_db(fake_metadata_resolver):
    content = {}

    add_package(
        content,
        fake_metadata_resolver,
        'docker-database',
        'latest',
        description='SONiC database service',
        default_reference='1.0.0',
        installed=True,
        built_in=True
    )
    add_package(
        content,
        fake_metadata_resolver,
        'docker-orchagent',
        'latest',
        description='SONiC switch state service',
        default_reference='1.0.0',
        installed=True,
        built_in=True
    )
    add_package(
        content,
        fake_metadata_resolver,
        'docker-syncd',
        'latest',
        description='SONiC syncd service',
        default_reference='1.0.0',
        installed=True,
        built_in=True
    )
    add_package(
        content,
        fake_metadata_resolver,
        'docker-teamd',
        'latest',
        description='SONiC teamd service',
        default_reference='1.0.0',
        installed=True,
        built_in=True
    )
    add_package(
        content,
        fake_metadata_resolver,
        'Azure/docker-test',
        '1.6.0',
        description='SONiC Package Manager Test Package',
        default_reference='1.6.0',
        installed=False,
        built_in=False,
    )
    add_package(
        content,
        fake_metadata_resolver,
        'Azure/docker-test-2',
        '1.5.0',
        description='SONiC Package Manager Test Package #2',
        default_reference='1.5.0',
        installed=False,
        built_in=False
    )
    add_package(
        content,
        fake_metadata_resolver,
        'Azure/docker-test-3',
        '1.5.0',
        description='SONiC Package Manager Test Package #3',
        default_reference='1.5.0',
        installed=True,
        built_in=False
    )
    add_package(
        content,
        fake_metadata_resolver,
        'Azure/docker-test-5',
        '1.9.0',
        description='SONiC Package Manager Test Package #5',
        default_reference='1.9.0',
        installed=False,
        built_in=False
    )
    add_package(
        content,
        fake_metadata_resolver,
        'Azure/docker-test-6',
        '1.5.0',
        description='SONiC Package Manager Test Package #6',
        default_reference='1.5.0',
        installed=False,
        built_in=False
    )

    yield PackageDatabase(content)


@pytest.fixture
def fake_db_for_migration(fake_metadata_resolver):
    content = {}
    add_package(
        content,
        fake_metadata_resolver,
        'docker-database',
        'latest',
        description='SONiC database service',
        default_reference='1.0.0',
        installed=True,
        built_in=True
    )
    add_package(
        content,
        fake_metadata_resolver,
        'docker-orchagent',
        'latest',
        description='SONiC switch state service',
        default_reference='1.0.0',
        installed=True,
        built_in=True
    )
    add_package(
        content,
        fake_metadata_resolver,
        'Azure/docker-test',
        '1.6.0',
        description='SONiC Package Manager Test Package',
        default_reference='1.6.0',
        installed=False,
        built_in=False
    )
    add_package(
        content,
        fake_metadata_resolver,
        'Azure/docker-test-2',
        '2.0.0',
        description='SONiC Package Manager Test Package #2',
        default_reference='2.0.0',
        installed=False,
        built_in=False
    )
    add_package(
        content,
        fake_metadata_resolver,
        'Azure/docker-test-3',
        '1.6.0',
        description='SONiC Package Manager Test Package #3',
        default_reference='1.6.0',
        installed=True,
        built_in=False
    )
    add_package(
        content,
        fake_metadata_resolver,
        'Azure/docker-test-4',
        '1.5.0',
        description='SONiC Package Manager Test Package #4',
        default_reference='1.5.0',
        installed=True,
        built_in=False
    )
    add_package(
        content,
        fake_metadata_resolver,
        'Azure/docker-test-5',
        '1.5.0',
        description='SONiC Package Manager Test Package #5',
        default_reference='1.5.0',
        installed=True,
        built_in=False
    )
    add_package(
        content,
        fake_metadata_resolver,
        'Azure/docker-test-6',
        '2.0.0',
        description='SONiC Package Manager Test Package #6',
        default_reference='2.0.0',
        installed=True,
        built_in=False
    )

    yield PackageDatabase(content)


@pytest.fixture()
def sonic_fs(fs):
    fs.create_file('/proc/1/root')
    fs.create_dir(ETC_SONIC_PATH)
    fs.create_dir(SYSTEMD_LOCATION)
    fs.create_dir(DOCKER_CTL_SCRIPT_LOCATION)
    fs.create_dir(SERVICE_MGMT_SCRIPT_LOCATION)
    fs.create_file(GENERATED_SERVICES_CONF_FILE)
    fs.create_file(os.path.join(TEMPLATES_PATH, SERVICE_FILE_TEMPLATE))
    fs.create_file(os.path.join(TEMPLATES_PATH, TIMER_UNIT_TEMPLATE))
    fs.create_file(os.path.join(TEMPLATES_PATH, SERVICE_MGMT_SCRIPT_TEMPLATE))
    fs.create_file(os.path.join(TEMPLATES_PATH, DOCKER_CTL_SCRIPT_TEMPLATE))
    fs.create_file(os.path.join(TEMPLATES_PATH, DEBUG_DUMP_SCRIPT_TEMPLATE))
    yield fs


@pytest.fixture(autouse=True)
def patch_pkgutil():
    with mock.patch('pkgutil.get_loader') as loader:
        yield loader


@pytest.fixture
def package_manager(mock_docker_api,
                    mock_registry_resolver,
                    mock_service_creator,
                    fake_metadata_resolver,
                    fake_db,
                    fake_device_info):
    yield PackageManager(mock_docker_api, mock_registry_resolver,
                         fake_db, fake_metadata_resolver,
                         mock_service_creator,
                         fake_device_info,
                         MagicMock())


@pytest.fixture
def anything():
    """ Fixture that returns Any object that can be used in
    assert_called_*_with to match any object passed. """

    class Any:
        def __eq__(self, other):
            return True

    yield Any()

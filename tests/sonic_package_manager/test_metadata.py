#!/usr/bin/env python

import json
import contextlib
from unittest.mock import Mock, MagicMock, patch
import tempfile
import os
import pytest

from sonic_package_manager.database import PackageEntry
from sonic_package_manager.errors import MetadataError
from sonic_package_manager.manifest import MANIFESTS_LOCATION, DEFAULT_MANIFEST_FILE
from sonic_package_manager.metadata import MetadataResolver
from sonic_package_manager.version import Version


@pytest.fixture
def manifest_str():
    return json.dumps({
        'package': {
            'name': 'test',
            'version': '1.0.0',
        },
        'service': {
            'name': 'test',
            'asic-service': False,
            'host-service': True,
        },
        'container': {
            'privileged': True,
        },
    })


def test_metadata_resolver_local(mock_registry_resolver, mock_docker_api):
    metadata_resolver = MetadataResolver(mock_docker_api, mock_registry_resolver)
    # it raises exception because mock manifest is not a valid manifest
    # but this is not a test objective, so just suppress the error.
    with contextlib.suppress(MetadataError):
        metadata_resolver.from_local('image')
    mock_docker_api.labels.assert_called_once()


def test_metadata_resolver_remote(mock_registry_resolver, mock_docker_api):
    metadata_resolver = MetadataResolver(mock_docker_api, mock_registry_resolver)
    mock_registry = MagicMock()
    mock_registry.manifest = MagicMock(return_value={'config': {'digest': 'some-digest'}})

    def return_mock_registry(repository):
        return mock_registry

    mock_registry_resolver.get_registry_for = Mock(side_effect=return_mock_registry)
    # it raises exception because mock manifest is not a valid manifest
    # but this is not a test objective, so just suppress the error.
    with contextlib.suppress(MetadataError):
        metadata_resolver.from_registry('test-repository', '1.2.0')
    mock_registry_resolver.get_registry_for.assert_called_once_with('test-repository')
    mock_registry.manifest.assert_called_once_with('test-repository', '1.2.0')
    mock_registry.blobs.assert_called_once_with('test-repository', 'some-digest')
    mock_docker_api.labels.assert_not_called()


def test_metadata_construction(manifest_str):
    metadata = MetadataResolver.from_labels({
        'com': {
            'azure': {
                'sonic': {
                    'manifest': manifest_str,
                    'yang-module': 'TEST'
                }
            }
        }
    })
    assert metadata.yang_modules == ['TEST']

    metadata = MetadataResolver.from_labels({
        'com': {
            'azure': {
                'sonic': {
                    'manifest': manifest_str,
                    'yang-module': {
                        'sonic-test': 'TEST',
                        'sonic-test-2': 'TEST 2',
                    },
                },
            },
        },
    })
    assert metadata.yang_modules == ['TEST', 'TEST 2']


@pytest.fixture
def temp_manifest_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def temp_tarball(temp_manifest_dir):
    tarball_path = os.path.join(temp_manifest_dir, 'image.tar')
    # Create an empty tarball file for testing
    open(tarball_path, 'w').close()
    yield tarball_path


def test_metadata_resolver_local_with_name_and_use_local_manifest(mock_registry_resolver,
                                                                  mock_docker_api,
                                                                  temp_manifest_dir):
    metadata_resolver = MetadataResolver(mock_docker_api, mock_registry_resolver)
    # Patching the get_manifest_from_local_file method to avoid FileNotFoundError
    with patch('sonic_package_manager.manifest.Manifest.get_manifest_from_local_file') as mock_get_manifest:
        # Setting the side_effect to None to simulate the absence of a manifest file
        mock_get_manifest.side_effect = None
        with contextlib.suppress(MetadataError):
            metadata_resolver.from_local('image', use_local_manifest=True, name='test_manifest', use_edit=False)


def test_metadata_resolver_local_manifest_file_not_exist(mock_registry_resolver, mock_docker_api, temp_manifest_dir):
    metadata_resolver = MetadataResolver(mock_docker_api, mock_registry_resolver)
    # Patching the get_manifest_from_local_file method to avoid FileNotFoundError
    with patch('sonic_package_manager.manifest.Manifest.get_manifest_from_local_file') as mock_get_manifest:
        # Setting the side_effect to None to simulate the absence of a manifest file
        mock_get_manifest.side_effect = None
        with pytest.raises(MetadataError):
            metadata_resolver.from_local('image', use_local_manifest=True, name='test_manifest', use_edit=False)


def test_metadata_resolver_tarball_with_use_local_manifest(mock_registry_resolver,
                                                           mock_docker_api,
                                                           temp_manifest_dir):
    metadata_resolver = MetadataResolver(mock_docker_api, mock_registry_resolver)
    # Patching the get_manifest_from_local_file method to avoid FileNotFoundError
    with patch('sonic_package_manager.manifest.Manifest.get_manifest_from_local_file') as mock_get_manifest:
        # Setting the side_effect to None to simulate the absence of a manifest file
        mock_get_manifest.side_effect = None
        with pytest.raises(MetadataError):
            metadata_resolver.from_tarball('image.tar', use_local_manifest=True, name='test_manifest')


def test_metadata_resolver_no_name_and_no_metadata_in_labels_for_remote(mock_registry_resolver, mock_docker_api):
    metadata_resolver = MetadataResolver(mock_docker_api, mock_registry_resolver)
    # Mocking the registry resolver's get_registry_for method to return a MagicMock
    mock_registry_resolver.get_registry_for = MagicMock(return_value=Mock())
    with pytest.raises(TypeError):
        metadata_resolver.from_registry('test-repository', '1.2.0')


def test_metadata_resolver_tarball_with_use_local_manifest_true(mock_registry_resolver,
                                                                mock_docker_api,
                                                                temp_manifest_dir):
    metadata_resolver = MetadataResolver(mock_docker_api, mock_registry_resolver)
    # Patching the get_manifest_from_local_file method to avoid FileNotFoundError
    with patch('sonic_package_manager.manifest.Manifest.get_manifest_from_local_file') as mock_get_manifest:
        # Setting the side_effect to None to simulate the absence of a manifest file
        mock_get_manifest.side_effect = None
        with pytest.raises(MetadataError):
            metadata_resolver.from_tarball('image.tar', use_local_manifest=True)


def test_metadata_resolver_no_metadata_in_labels_for_tarball(mock_registry_resolver, mock_docker_api):
    metadata_resolver = MetadataResolver(mock_docker_api, mock_registry_resolver)
    with pytest.raises(FileNotFoundError):
        metadata_resolver.from_tarball('image.tar')


def test_metadata_resolver_local_with_name_and_use_edit(mock_registry_resolver,
                                                        mock_docker_api,
                                                        temp_manifest_dir,
                                                        sonic_fs):
    with patch('builtins.open') as mock_open, \
         patch('json.loads') as mock_json_loads:
        sonic_fs.create_dir(MANIFESTS_LOCATION)  # Create the directory using sonic_fs fixture
        mock_open.side_effect = FileNotFoundError  # Simulate FileNotFoundError when opening the manifest file
        mock_json_loads.side_effect = ValueError  # Simulate ValueError when parsing JSON

        # Create the default manifest file
        sonic_fs.create_file(DEFAULT_MANIFEST_FILE)
        sonic_fs.create_file(os.path.join(MANIFESTS_LOCATION, "test_manifest.edit"))

        metadata_resolver = MetadataResolver(mock_docker_api, mock_registry_resolver)
        with pytest.raises(FileNotFoundError):
            metadata_resolver.from_local('image',
                                         use_local_manifest=True,
                                         name='test_manifest',
                                         use_edit=True)

    mock_open.assert_called_with(os.path.join(MANIFESTS_LOCATION, 'test_manifest.edit'), 'r')
    mock_json_loads.assert_not_called()  # Ensure json.loads is not called


def test_metadata_resolver_local_with_name_and_default_manifest(mock_registry_resolver,
                                                                mock_docker_api,
                                                                temp_manifest_dir,
                                                                sonic_fs):
    with patch('builtins.open') as mock_open, \
         patch('json.loads') as mock_json_loads:
        sonic_fs.create_dir(MANIFESTS_LOCATION)  # Create the directory using sonic_fs fixture
        mock_open.side_effect = FileNotFoundError  # Simulate FileNotFoundError when opening the manifest file
        mock_json_loads.side_effect = ValueError  # Simulate ValueError when parsing JSON

        # Create the default manifest file
        sonic_fs.create_file(DEFAULT_MANIFEST_FILE)

        metadata_resolver = MetadataResolver(mock_docker_api, mock_registry_resolver)
        with pytest.raises(FileNotFoundError):
            metadata_resolver.from_local('image',
                                         use_local_manifest=False,
                                         name='test_manifest',
                                         use_edit=True)

    mock_open.assert_called_with(DEFAULT_MANIFEST_FILE, 'r')
    mock_json_loads.assert_not_called()  # Ensure json.loads is not called

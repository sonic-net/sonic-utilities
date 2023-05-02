#!/usr/bin/env python

import json
import contextlib
from unittest.mock import Mock, MagicMock, patch, mock_open
import pytest

from sonic_package_manager.database import PackageEntry
from sonic_package_manager.errors import MetadataError
from sonic_package_manager.manifest import Manifest
from sonic_package_manager.metadata import MetadataResolver, Metadata
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


@patch("sonic_package_manager.metadata.os.path.exists", return_value=True)
@patch("sonic_package_manager.metadata.open", create=True)
def test_get_manifest_from_local_file(mock_open, mock_path_exists, mock_docker_api, mock_registry_resolver):
    # Setting up mock file content with required fields
    mock_file_content = {
        "package": {
            "name": "test-package",
            "version": "1.0.0",
        },
        "service": {
            "name": "test-package",
            "asic-service": False,
            "host-service": True,
        },
        "container": {
            "privileged": True,
        },
    }
    mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_file_content)

    # Creating a mock MetadataResolver
    metadata_resolver = MetadataResolver(mock_docker_api, mock_registry_resolver)

    # Mocking necessary dependencies in the MetadataResolver instance
    metadata_resolver.docker.labels = Mock(return_value={"com.azure.sonic.manifest": "mocked_manifest_labels"})

    # Testing with an existing local manifest
    metadata = metadata_resolver.from_local('test-image', use_local_manifest=True, name='test-package', use_edit=False)

    assert isinstance(metadata, Metadata)



def test_get_manifest_from_local_file2(capsys):
    metadata_resolver = MetadataResolver(None, None)  # Replace None with appropriate mocks

    with patch('os.path.exists', return_value=True), \
         patch('os.mkdir'), \
         patch('builtins.open', mock_open(read_data=json.dumps({"package": {"name": "test-package"}}))):
        # Test when manifest file exists
        manifest = metadata_resolver.get_manifest_from_local_file('test-package')
        assert manifest is not None

    with patch('os.path.exists', return_value=False), \
         patch('os.mkdir'), \
         patch('builtins.open', mock_open()):
        # Test when manifest file does not exist
        manifest = metadata_resolver.get_manifest_from_local_file('non-existent-package')
        captured = capsys.readouterr()
        assert captured.out.strip() == "Local Manifest file /var/lib/sonic-package-manager/manifests/non-existent-package does not exists"
        assert manifest is None

    manifest_data = {"package": {"name": "test-package"}, "service": {"name": "test-package"}}
    with patch('os.path.exists', return_value=True), \
         patch('os.mkdir'), \
         patch('builtins.open', mock_open(read_data=json.dumps(manifest_data))), \
         patch('json.load', return_value=manifest_data), \
         patch('json.dump') as mock_json_dump:
        # Test when custom_name is provided
        manifest = metadata_resolver.get_manifest_from_local_file('test-package', custom_name='custom-name')

    captured = capsys.readouterr()
    print("Captured Output:", captured.out)

    # Assert that the manifest is not None
    assert manifest is not None

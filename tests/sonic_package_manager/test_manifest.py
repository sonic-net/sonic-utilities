#!/usr/bin/env python

import pytest
import json
from unittest.mock import patch, mock_open

from sonic_package_manager.constraint import ComponentConstraints
from sonic_package_manager.manifest import Manifest, ManifestError, MANIFESTS_LOCATION


def test_manifest_v1_defaults():
    manifest = Manifest.marshal({'package': {'name': 'test',
                                             'version': '1.0.0'},
                                 'service': {'name': 'test'}})
    assert manifest['package']['depends'] == []
    assert manifest['package']['breaks'] == []
    assert manifest['package']['base-os'] == ComponentConstraints()
    assert not manifest['service']['asic-service']
    assert manifest['service']['host-service']


def test_manifest_v1_invalid_version():
    with pytest.raises(ManifestError):
        Manifest.marshal({'package': {'version': 'abc', 'name': 'test'},
                          'service': {'name': 'test'}})


def test_manifest_v1_invalid_package_constraint():
    with pytest.raises(ManifestError):
        Manifest.marshal({'package': {'name': 'test', 'version': '1.0.0',
                                      'depends': ['swss>a']},
                          'service': {'name': 'test'}})


def test_manifest_v1_service_spec():
    manifest = Manifest.marshal({'package': {'name': 'test',
                                             'version': '1.0.0'},
                                 'service': {'name': 'test', 'asic-service': True}})
    assert manifest['service']['asic-service']


def test_manifest_v1_mounts():
    manifest = Manifest.marshal({'version': '1.0.0', 'package': {'name': 'test',
                                                                 'version': '1.0.0'},
                                 'service': {'name': 'cpu-report'},
                                 'container': {'privileged': True,
                                               'mounts': [{'source': 'a', 'target': 'b', 'type': 'bind'}]}})
    assert manifest['container']['mounts'][0]['source'] == 'a'
    assert manifest['container']['mounts'][0]['target'] == 'b'
    assert manifest['container']['mounts'][0]['type'] == 'bind'


def test_manifest_v1_mounts_invalid():
    with pytest.raises(ManifestError):
        Manifest.marshal({'version': '1.0.0', 'package': {'name': 'test', 'version': '1.0.0'},
                          'service': {'name': 'cpu-report'},
                          'container': {'privileged': True,
                                        'mounts': [{'not-source': 'a', 'target': 'b', 'type': 'bind'}]}})


def test_manifest_invalid_root_type():
    manifest_json_input = {'package': { 'name': 'test', 'version': '1.0.0'},
                           'service': {'name': 'test'}, 'container': 'abc'}
    with pytest.raises(ManifestError):
        Manifest.marshal(manifest_json_input)


def test_manifest_invalid_array_type():
    manifest_json_input = {'package': { 'name': 'test', 'version': '1.0.0'},
                           'service': {'name': 'test', 'warm-shutdown': {'after': 'bgp'}}}
    with pytest.raises(ManifestError):
        Manifest.marshal(manifest_json_input)


def test_manifest_v1_unmarshal():
    manifest_json_input = {'package': {'name': 'test', 'version': '1.0.0',
                                       'depends': [
                                           {
                                               'name': 'swss',
                                               'version': '>1.0.0',
                                               'components': {},
                                           }
                                        ]},
                           'service': {'name': 'test'}}
    manifest = Manifest.marshal(manifest_json_input)
    manifest_json = manifest.unmarshal()
    for key, section in manifest_json_input.items():
        for field, value in section.items():
            assert manifest_json[key][field] == value


@patch("sonic_package_manager.manifest.open", new_callable=mock_open)
def test_get_manifest_from_local_file_existing_manifest(mock_open, sonic_fs):
    # Create a mock manifest file
    manifest_name = "test_manifest.json"
    manifest_content = {"package": {"name": "test_package", "version": "1.0.0"},
                        "service": {"name": "test_service"}}
    mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(manifest_content)
    sonic_fs.create_dir(MANIFESTS_LOCATION)

    # Call the function
    desired_dict = Manifest.get_manifest_from_local_file(manifest_name)

    exp_manifest_content = {"package": {"name": "test_manifest.json", "version": "1.0.0"},
                            "service": {"name": "test_manifest.json"}}
    manifest_string = json.dumps(exp_manifest_content, indent=4)
    desired_output = {
        'Tag': 'master',
        'com': {
            'azure': {
                'sonic': {
                    'manifest': manifest_string
                }
            }
        }
    }

    # Check if the returned dictionary matches the expected structure
    assert desired_dict == desired_output

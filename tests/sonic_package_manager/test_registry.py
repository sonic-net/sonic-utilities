#!/usr/bin/env python

import requests
import responses
from sonic_package_manager.registry import RegistryResolver


def test_get_registry_for():
    resolver = RegistryResolver()
    registry = resolver.get_registry_for('debian')
    assert registry is resolver.DockerHubRegistry
    registry = resolver.get_registry_for('Azure/sonic')
    assert registry is resolver.DockerHubRegistry
    registry = resolver.get_registry_for('azure/sonic')
    assert registry is resolver.DockerHubRegistry
    registry = resolver.get_registry_for('registry-server:5000/docker')
    assert registry.url == 'https://registry-server:5000'
    registry = resolver.get_registry_for('registry-server.com/docker')
    assert registry.url == 'https://registry-server.com'


def test_split_docker_domain_preserves_repository():
    from sonic_package_manager.registry import split_docker_domain
    # An uppercase first component (e.g. 'Azure/...') must stay part of the
    # repository path, not be interpreted as a registry domain.
    assert split_docker_domain('Azure/docker-test') == ('docker.io', 'Azure/docker-test')
    assert split_docker_domain('debian') == ('docker.io', 'library/debian')
    assert split_docker_domain('registry-server.com/docker') == ('registry-server.com', 'docker')



@responses.activate
def test_registry_auth():
    resolver = RegistryResolver()
    registry = resolver.get_registry_for('registry-server:5000/docker')
    responses.add(responses.GET, registry.url + '/v2/docker/tags/list',
                  headers={
                      'www-authenticate': 'Bearer realm="https://auth.docker.io/token",scope="repository:library/docker:pull,push"'
                  },
                  status=requests.codes.unauthorized)
    responses.add(responses.GET,
                  'https://auth.docker.io/token?scope=repository:library/docker:pull,push',
                  json={'token': 'a', 'expires_in': '100'},
                  status=requests.codes.ok)
    responses.add(responses.GET, registry.url + '/v2/docker/tags/list',
                  json={'tags': ['a', 'b']},
                  status=requests.codes.ok)
    assert registry.tags('registry-server:5000/docker') == ['a', 'b']

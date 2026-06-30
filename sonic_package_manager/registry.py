#!/usr/bin/env python

import json
from dataclasses import dataclass
from typing import List, Dict

import requests
import www_authenticate
from docker_image import reference
from prettyprinter import pformat

from sonic_package_manager.logger import log


def split_docker_domain(name: str):
    """ Split a docker reference into registry domain and remainder.

    Reimplements the pre-0.2.0 docker-image-py heuristic: the first path
    component is treated as a registry domain only if it contains '.' or ':'
    or equals 'localhost'. docker-image-py 0.2.0 additionally treats an
    uppercase first component as a domain (because repository names must be
    lowercase), which would break the 'Azure/...' repositories used by
    sonic-package-manager. Keeping the old behavior makes resolution
    independent of the installed docker-image-py version.
    """

    i = name.find('/')
    if i == -1 or not ('.' in name[:i] or ':' in name[:i] or name[:i] == 'localhost'):
        domain, remainder = reference.DEFAULT_DOMAIN, name
    else:
        domain, remainder = name[:i], name[i + 1:]
    if domain == reference.DEFAULT_DOMAIN and '/' not in remainder:
        remainder = reference.OFFICIAL_REPO_NAME + '/' + remainder
    return domain, remainder


class AuthenticationServiceError(Exception):
    """ Exception class for errors related to authentication. """

    pass


class AuthenticationService:
    """ AuthenticationService provides an authentication tokens. """

    @staticmethod
    def get_token(bearer: Dict) -> str:
        """ Retrieve an authentication token.

        Args:
            bearer: Bearer token.
        Returns:
            token value as a string.
        """

        log.debug(f'getting authentication token {bearer}')
        if 'realm' not in bearer:
            raise AuthenticationServiceError(f'Realm is required in bearer')

        url = bearer.pop('realm')
        response = requests.get(url, params=bearer)
        if response.status_code != requests.codes.ok:
            raise AuthenticationServiceError('Failed to retrieve token')

        content = json.loads(response.content)
        token = content['token']

        log.debug(f'authentication token for bearer={bearer}: '
                  f'token={token}')

        return token


@dataclass
class RegistryApiError(Exception):
    """ Class for registry related errors. """

    msg: str
    response: requests.Response

    def __str__(self):
        code = self.response.status_code
        content = self.response.content.decode()
        try:
            content = json.loads(content)
        except ValueError:
            pass
        return f'{self.msg}: code: {code} details: {pformat(content)}'


class Registry:
    """ Provides a Docker registry interface. """

    MIME_DOCKER_MANIFEST = 'application/vnd.docker.distribution.manifest.v2+json'

    def __init__(self, host: str):
        self.url = host

    @staticmethod
    def _execute_get_request(url, headers):
        response = requests.get(url, headers=headers)
        if response.status_code == requests.codes.unauthorized:
            # Get authentication details from headers
            # Registry should tell how to authenticate
            www_authenticate_details = response.headers['Www-Authenticate']
            log.debug(f'unauthorized: retrieving authentication details '
                      f'from response headers {www_authenticate_details}')
            bearer = www_authenticate.parse(www_authenticate_details)['bearer']
            token = AuthenticationService.get_token(bearer)
            headers['Authorization'] = f'Bearer {token}'
            # Repeat request
            response = requests.get(url, headers=headers)
        return response

    def _get_base_url(self, repository: str):
        return f'{self.url}/v2/{repository}'

    def tags(self, repository: str) -> List[str]:
        log.debug(f'getting tags for {repository}')

        _, repository = split_docker_domain(repository)
        headers = {'Accept': 'application/json'}
        url = f'{self._get_base_url(repository)}/tags/list'
        response = self._execute_get_request(url, headers)
        if response.status_code != requests.codes.ok:
            raise RegistryApiError(f'Failed to retrieve tags from {repository}', response)

        content = json.loads(response.content)
        log.debug(f'tags list api response: f{content}')

        return content['tags']

    def manifest(self, repository: str, ref: str) -> Dict:
        log.debug(f'getting manifest for {repository}:{ref}')

        _, repository = split_docker_domain(repository)
        headers = {'Accept': self.MIME_DOCKER_MANIFEST}
        url = f'{self._get_base_url(repository)}/manifests/{ref}'
        response = self._execute_get_request(url, headers)

        if response.status_code != requests.codes.ok:
            raise RegistryApiError(f'Failed to retrieve manifest for {repository}:{ref}', response)

        content = json.loads(response.content)
        log.debug(f'manifest content for {repository}:{ref}: {content}')

        return content

    def blobs(self, repository: str, digest: str):
        log.debug(f'retrieving blob for {repository}:{digest}')

        _, repository = split_docker_domain(repository)
        headers = {'Accept': self.MIME_DOCKER_MANIFEST}
        url = f'{self._get_base_url(repository)}/blobs/{digest}'
        response = self._execute_get_request(url, headers)
        if response.status_code != requests.codes.ok:
            raise RegistryApiError(f'Failed to retrieve blobs for {repository}:{digest}', response)
        content = json.loads(response.content)

        log.debug(f'retrieved blob for {repository}:{digest}: {content}')
        return content


class RegistryResolver:
    """ Returns a registry object based on the input repository reference
     string. """

    DockerHubRegistry = Registry('https://index.docker.io')

    def __init__(self):
        pass

    def get_registry_for(self, ref: str) -> Registry:
        domain, _ = split_docker_domain(ref)
        if domain == reference.DEFAULT_DOMAIN:
            return self.DockerHubRegistry
        # TODO: support insecure registries
        return Registry(f'https://{domain}')

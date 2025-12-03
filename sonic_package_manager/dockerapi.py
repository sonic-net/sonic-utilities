#!/usr/bin/evn python

""" Module provides Docker interface. """

import contextlib
import io
import tarfile
import re
from typing import Optional

from sonic_package_manager.logger import log
from sonic_package_manager.progress import ProgressManager


def is_digest(ref: str):
    return ref.startswith('sha256:')


def bytes_to_mb(bytes):
    return bytes / 1024 / 1024


def get_id(line):
    return line['id']


def get_status(line):
    return line['status']


def get_progress(line):
    progress = line['progressDetail']
    current = bytes_to_mb(progress['current'])
    total = bytes_to_mb(progress['total'])
    return current, total


def process_progress(progress_manager, line):
    try:
        status = get_status(line)
        id = get_id(line)
        current, total = get_progress(line)

        if id not in progress_manager:
            progress_manager.new(id,
                                 total=total,
                                 unit='Mb',
                                 desc=f'{status} {id}')
        pbar = progress_manager.get(id)

        # Complete status
        if 'complete' in status:
            pbar.desc = f'{status} {id}'
            pbar.update(pbar.total)
            return

        # Status changed
        if status not in pbar.desc:
            pbar.desc = f'{status} {id}'
            pbar.total = total
            pbar.count = 0

        pbar.update(current - pbar.count)
    except KeyError:
        # not a progress line
        return


def get_repository_from_image(image):
    """ Returns the first RepoTag repository
    found in image. """

    repotags = image.attrs['RepoTags']
    for repotag in repotags:
        repository, tag = repotag.split(':')
        return repository


class DockerApi:
    """ DockerApi provides a set of methods -
     wrappers around docker client methods """

    def __init__(self,
                 client,
                 progress_manager: Optional[ProgressManager] = None):
        self.client = client
        self.progress_manager = progress_manager

    def pull(self, repository: str,
             reference: Optional[str] = None):
        """ Docker 'pull' command.
        Args:
            repository: repository to pull
            reference: tag or digest
        """

        log.debug(f'pulling image from {repository} reference={reference}')

        api = self.client.api
        progress_manager = self.progress_manager

        digest = None

        with progress_manager or contextlib.nullcontext():
            for line in api.pull(repository,
                                 reference,
                                 stream=True,
                                 decode=True):
                log.debug(f'pull status: {line}')

                status = get_status(line)

                # Record pulled digest
                digest_match = re.match(r'Digest: (?P<sha>.*)', status)
                if digest_match:
                    digest = digest_match.groupdict()['sha']

                if progress_manager:
                    process_progress(progress_manager, line)

        log.debug(f'Digest: {digest}')
        log.debug(f'image from {repository} reference={reference} pulled successfully')

        return self.get_image(f'{repository}@{digest}')

    def load(self, imgpath: str):
        """ Docker 'load' command.
        Args:

        """

        log.debug(f'loading image from {imgpath}')

        api = self.client.api
        progress_manager = self.progress_manager

        imageid = None
        repotag = None

        with progress_manager or contextlib.nullcontext():
            with open(imgpath, 'rb') as imagefile:
                for line in api.load_image(imagefile, quiet=False):
                    log.debug(f'pull status: {line}')

                    if progress_manager:
                        process_progress(progress_manager, line)

                    if 'stream' not in line:
                        continue

                    stream = line['stream']
                    repotag_match = re.match(r'Loaded image: (?P<repotag>.*)\n', stream)
                    if repotag_match:
                        repotag = repotag_match.groupdict()['repotag']
                    imageid_match = re.match(r'Loaded image ID: sha256:(?P<id>.*)\n', stream)
                    if imageid_match:
                        imageid = imageid_match.groupdict()['id']

        imagename = repotag if repotag else imageid
        log.debug(f'Loaded image {imagename}')

        return self.get_image(imagename)

    def rmi(self, image: str, **kwargs):
        """ Docker 'rmi -f' command. """

        log.debug(f'removing image {image} kwargs={kwargs}')

        self.client.images.remove(image, **kwargs)

        log.debug(f'image {image} removed successfully')

    def tag(self, image: str, repotag: str, **kwargs):
        """ Docker 'tag' command """

        log.debug(f'tagging image {image} {repotag} kwargs={kwargs}')

        img = self.client.images.get(image)
        img.tag(repotag, **kwargs)

        log.debug(f'image {image} tagged {repotag} successfully')

    def rm(self, container: str, **kwargs):
        """ Docker 'rm' command. """

        self.client.containers.get(container).remove(**kwargs)
        log.debug(f'removed container {container}')

    def rm_by_ancestor(self, image_id: str, **kwargs):
        """ Docker 'rm' command for running containers instantiated
        from image passed to this function. """

        # Clean containers based on the old image
        containers = self.ps(filters={'ancestor': image_id}, all=True)
        for container in containers:
            self.rm(container.id, **kwargs)

    def ps(self, **kwargs):
        """ Docker 'ps' command. """

        return self.client.containers.list(**kwargs)

    def labels(self, image: str):
        """ Returns a list of labels associated with image. """

        log.debug(f'inspecting image labels {image}')

        labels = self.client.images.get(image).labels

        log.debug(f'image {image} labels successfully: {labels}')
        return labels

    def get_image(self, name: str):
        return self.client.images.get(name)

    def extract(self, image, src_path: str, dst_path: str):
        """ Copy src_path from the docker image to host dst_path. """

        buf = bytes()

        container = self.client.containers.create(image)
        try:
            bits, _ = container.get_archive(src_path)
            for chunk in bits:
                buf += chunk
        finally:
            container.remove(force=True)

        with tarfile.open(fileobj=io.BytesIO(buf)) as tar:
            for member in tar:
                if dst_path.endswith('/'):
                    tar.extract(member, dst_path)
                else:
                    member.name = dst_path
                    tar.extract(member, dst_path)

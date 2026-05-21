#!/usr/bin/env python

from typing import Dict

from docker_image.reference import Reference

DockerReference = Reference


def deep_update(dst: Dict, src: Dict) -> Dict:
    """ Deep update dst dictionary with src dictionary.

    Args:
        dst: Dictionary to update
        src: Dictionary to update with

    Returns:
        New merged dictionary.
    """

    for key, value in src.items():
        if isinstance(value, dict):
            node = dst.setdefault(key, {})
            deep_update(node, value)
        else:
            dst[key] = value
    return dst

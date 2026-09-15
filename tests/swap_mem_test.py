# tests/swap_mem_test.py

import json

import pytest

from utilities_common import swap_mem


DEFAULT_SWAP_MEM_SIZE = 1024
DEFAULT_TOTAL_MEM_THRESHOLD = 2048


def write_platform_json(tmp_path, data):
    """Write platform data to a temporary platform.json file."""
    path = tmp_path / "platform.json"
    path.write_text(json.dumps(data))
    return str(path)


def test_get_min_swap_mem_size_from_platform_json(tmp_path):
    path = write_platform_json(
        tmp_path, {swap_mem.MIN_SWAP_MEM_SIZE_KEY: 3072}
    )

    assert swap_mem.get_min_swap_mem_size_in_mb(platform_json_path=path) == 3072


def test_get_min_swap_mem_size_missing_key_returns_none(tmp_path):
    path = write_platform_json(tmp_path, {})

    assert swap_mem.get_min_swap_mem_size_in_mb(platform_json_path=path) is None


@pytest.mark.parametrize("value", [0, -1, "abc", None])
def test_get_min_swap_mem_size_invalid_value_returns_none(tmp_path, value):
    path = write_platform_json(
        tmp_path, {swap_mem.MIN_SWAP_MEM_SIZE_KEY: value}
    )

    assert swap_mem.get_min_swap_mem_size_in_mb(platform_json_path=path) is None


def test_get_min_swap_mem_size_missing_file_returns_none(tmp_path):
    path = str(tmp_path / "does_not_exist.json")

    assert swap_mem.get_min_swap_mem_size_in_mb(platform_json_path=path) is None


def test_resolve_uses_platform_size_when_largest(tmp_path):
    path = write_platform_json(
        tmp_path, {swap_mem.MIN_SWAP_MEM_SIZE_KEY: 3072}
    )

    assert (
        swap_mem.resolve_swap_mem_size(
            DEFAULT_SWAP_MEM_SIZE,
            DEFAULT_SWAP_MEM_SIZE,
            platform_json_path=path,
        )
        == 3072
    )


def test_resolve_uses_requested_size_when_largest(tmp_path):
    path = write_platform_json(
        tmp_path, {swap_mem.MIN_SWAP_MEM_SIZE_KEY: 3072}
    )

    assert (
        swap_mem.resolve_swap_mem_size(
            4096,
            DEFAULT_SWAP_MEM_SIZE,
            platform_json_path=path,
        )
        == 4096
    )


def test_resolve_never_goes_below_default(tmp_path):
    path = write_platform_json(
        tmp_path, {swap_mem.MIN_SWAP_MEM_SIZE_KEY: 512}
    )

    assert (
        swap_mem.resolve_swap_mem_size(
            512,
            DEFAULT_SWAP_MEM_SIZE,
            platform_json_path=path,
        )
        == DEFAULT_SWAP_MEM_SIZE
    )


def test_resolve_without_platform_key_preserves_requested(tmp_path):
    path = write_platform_json(tmp_path, {})

    assert (
        swap_mem.resolve_swap_mem_size(
            2048,
            DEFAULT_SWAP_MEM_SIZE,
            platform_json_path=path,
        )
        == 2048
    )


def test_resolve_with_no_requested_size(tmp_path):
    path = write_platform_json(
        tmp_path, {swap_mem.MIN_SWAP_MEM_SIZE_KEY: 3072}
    )

    assert (
        swap_mem.resolve_swap_mem_size(
            None,
            DEFAULT_SWAP_MEM_SIZE,
            platform_json_path=path,
        )
        == 3072
    )


def test_get_min_total_mem_threshold_from_platform_json(tmp_path):
    path = write_platform_json(
        tmp_path, {swap_mem.MIN_TOTAL_MEM_THRESHOLD_KEY: 8192}
    )

    assert (
        swap_mem.get_min_total_mem_threshold_in_mb(platform_json_path=path)
        == 8192
    )


def test_get_min_total_mem_threshold_missing_key_returns_none(tmp_path):
    path = write_platform_json(tmp_path, {})

    assert (
        swap_mem.get_min_total_mem_threshold_in_mb(platform_json_path=path)
        is None
    )


@pytest.mark.parametrize("value", [0, -1, "abc", None])
def test_get_min_total_mem_threshold_invalid_returns_none(tmp_path, value):
    path = write_platform_json(
        tmp_path, {swap_mem.MIN_TOTAL_MEM_THRESHOLD_KEY: value}
    )

    assert (
        swap_mem.get_min_total_mem_threshold_in_mb(platform_json_path=path)
        is None
    )


def test_resolve_total_mem_threshold_uses_platform_when_largest(tmp_path):
    path = write_platform_json(
        tmp_path, {swap_mem.MIN_TOTAL_MEM_THRESHOLD_KEY: 8192}
    )

    assert (
        swap_mem.resolve_total_mem_threshold(
            DEFAULT_TOTAL_MEM_THRESHOLD,
            DEFAULT_TOTAL_MEM_THRESHOLD,
            platform_json_path=path,
        )
        == 8192
    )


def test_resolve_total_mem_threshold_uses_requested_when_largest(tmp_path):
    path = write_platform_json(
        tmp_path, {swap_mem.MIN_TOTAL_MEM_THRESHOLD_KEY: 8192}
    )

    assert (
        swap_mem.resolve_total_mem_threshold(
            16384,
            DEFAULT_TOTAL_MEM_THRESHOLD,
            platform_json_path=path,
        )
        == 16384
    )


def test_resolve_total_mem_threshold_never_below_default(tmp_path):
    path = write_platform_json(
        tmp_path, {swap_mem.MIN_TOTAL_MEM_THRESHOLD_KEY: 1024}
    )

    assert (
        swap_mem.resolve_total_mem_threshold(
            1024,
            DEFAULT_TOTAL_MEM_THRESHOLD,
            platform_json_path=path,
        )
        == DEFAULT_TOTAL_MEM_THRESHOLD
    )


def test_resolve_total_mem_threshold_without_platform_key(tmp_path):
    path = write_platform_json(tmp_path, {})

    assert (
        swap_mem.resolve_total_mem_threshold(
            4096,
            DEFAULT_TOTAL_MEM_THRESHOLD,
            platform_json_path=path,
        )
        == 4096
    )


def test_the_two_keys_are_independent(tmp_path):
    """Swap size and total memory threshold must not read each other's key."""
    path = write_platform_json(
        tmp_path,
        {
            swap_mem.MIN_SWAP_MEM_SIZE_KEY: 3072,
            swap_mem.MIN_TOTAL_MEM_THRESHOLD_KEY: 8192,
        },
    )

    assert swap_mem.resolve_swap_mem_size(
        DEFAULT_SWAP_MEM_SIZE, DEFAULT_SWAP_MEM_SIZE, platform_json_path=path
    ) == 3072
    assert swap_mem.resolve_total_mem_threshold(
        DEFAULT_TOTAL_MEM_THRESHOLD,
        DEFAULT_TOTAL_MEM_THRESHOLD,
        platform_json_path=path,
    ) == 8192

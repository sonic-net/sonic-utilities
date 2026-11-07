"""Keep native transceiver imports separate from unit-test module-level mocks."""

import importlib
import os
import sys
from contextlib import contextmanager

import pytest


PLATFORM_MODULES = (
    "sonic_platform",
    "sonic_platform_base",
    "sfputil",
    "utilities_common.platform_sfputil_helper",
    "integration_tests.xcvr_emulator",
    "integration_tests.sonic_environment",
)


def is_platform_module(name):
    """Select only the module trees shared with hardware-mocking unit tests."""
    return any(name == prefix or name.startswith(f"{prefix}.") for prefix in PLATFORM_MODULES)


@contextmanager
def isolated_platform_imports():
    """Load clean native APIs for a test, then restore the unit worker's imports."""
    saved_modules = {name: module for name, module in sys.modules.items() if is_platform_module(name)}
    missing = object()
    parent_attributes = []
    for name in PLATFORM_MODULES:
        parent_name, separator, attribute = name.rpartition(".")
        if separator:
            parent = importlib.import_module(parent_name)
            parent_attributes.append((parent, attribute, getattr(parent, attribute, missing)))
            if hasattr(parent, attribute):
                delattr(parent, attribute)

    for name in saved_modules:
        del sys.modules[name]

    try:
        with pytest.MonkeyPatch.context() as patch:
            for name in list(os.environ):
                if name == "UTILITIES_UNIT_TESTING" or name.startswith("UTILITIES_UNIT_TESTING_"):
                    patch.delenv(name)
            yield
    finally:
        for name in list(sys.modules):
            if is_platform_module(name):
                del sys.modules[name]
        sys.modules.update(saved_modules)
        for parent, attribute, value in parent_attributes:
            if value is missing:
                if hasattr(parent, attribute):
                    delattr(parent, attribute)
            else:
                setattr(parent, attribute, value)

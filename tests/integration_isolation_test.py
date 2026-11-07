"""Regression checks for unit/integration tests reusing the same pytest worker."""

import importlib
import os
import sys
from types import ModuleType

import pytest

from integration_tests.isolation import is_platform_module, isolated_platform_imports


@pytest.mark.parametrize("fail_inside", [False, True], ids=["success", "exception"])
def test_native_imports_restore_unit_worker_state(monkeypatch, fail_inside):
    """Restore worker state without changing the installed SDK's import search path."""
    from utilities_common import platform_sfputil_helper as original_helper
    import integration_tests
    import utilities_common

    original_environment = ModuleType("integration_tests.sonic_environment")
    monkeypatch.setitem(sys.modules, original_environment.__name__, original_environment)
    monkeypatch.setattr(integration_tests, "sonic_environment", original_environment, raising=False)
    marker = ModuleType("sfputil.unit_test_marker")
    monkeypatch.setitem(sys.modules, marker.__name__, marker)
    monkeypatch.setenv("UTILITIES_UNIT_TESTING", "2")
    monkeypatch.setenv("UTILITIES_UNIT_TESTING_TOPOLOGY", "multi_asic")
    search_path = sys.path.copy()
    saved = {name: module for name, module in sys.modules.items() if is_platform_module(name)}

    def exercise_isolation():
        with isolated_platform_imports():
            assert sys.path == search_path
            assert marker.__name__ not in sys.modules
            assert "UTILITIES_UNIT_TESTING" not in os.environ
            assert "UTILITIES_UNIT_TESTING_TOPOLOGY" not in os.environ
            assert original_environment.__name__ not in sys.modules
            assert not hasattr(integration_tests, "sonic_environment")
            helper = importlib.import_module("utilities_common.platform_sfputil_helper")
            assert helper is not original_helper
            assert helper.get_first_subport.__module__ == "utilities_common.platform_sfputil_helper"
            assert utilities_common.platform_sfputil_helper is helper
            sys.modules["sfputil.integration_test_marker"] = ModuleType("sfputil.integration_test_marker")
            environment = ModuleType("integration_tests.sonic_environment")
            sys.modules[environment.__name__] = environment
            integration_tests.sonic_environment = environment
            if fail_inside:
                raise RuntimeError("integration test failed")

    if fail_inside:
        with pytest.raises(RuntimeError, match="integration test failed"):
            exercise_isolation()
    else:
        exercise_isolation()

    restored = {name: module for name, module in sys.modules.items() if is_platform_module(name)}
    assert restored.keys() == saved.keys()
    assert all(restored[name] is module for name, module in saved.items())
    assert sys.path == search_path
    assert utilities_common.platform_sfputil_helper is original_helper
    assert integration_tests.sonic_environment is original_environment
    assert os.environ["UTILITIES_UNIT_TESTING"] == "2"
    assert os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] == "multi_asic"

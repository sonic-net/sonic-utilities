"""Compose the emulator and SONiC test environment, with per-test cleanup."""

import importlib.util

import pytest

from integration_tests.isolation import isolated_platform_imports


@pytest.fixture(autouse=True)
def native_platform_imports():
    """Prevent unit-test collection/runtime mocks from replacing the native CMIS stack."""
    with isolated_platform_imports():
        yield


@pytest.fixture
def monkeypatch(native_platform_imports):
    """Undo per-test patches before restoring the worker's saved module dictionary."""
    with pytest.MonkeyPatch.context() as patch:
        yield patch


@pytest.fixture
def module_config(request):
    """Load the checked-in config.yaml, optionally overriding this test's defaults."""
    if importlib.util.find_spec("xcvr_emu") is None:
        pytest.fail('xcvr-emu is not installed; run pip install ".[testing]"')
    from integration_tests.xcvr_emulator import EmulatorProcess

    return EmulatorProcess.load_config(getattr(request, "param", None))


@pytest.fixture
def emulator(tmp_path, module_config):
    """Own a fresh daemon and gRPC client, including failure-path cleanup."""
    from integration_tests.xcvr_emulator import EmulatorProcess

    with EmulatorProcess(tmp_path, module_config) as daemon:
        yield daemon.client
    assert daemon.process.returncode == 0, daemon.log_path.read_text()


@pytest.fixture
def sfputil_environment(monkeypatch, emulator):
    """Mock supporting services, not native transceiver APIs or CLI command results."""
    from integration_tests.sonic_environment import SonicEnvironment

    return SonicEnvironment(monkeypatch, emulator)


@pytest.fixture
def transceiver_commands(monkeypatch, sfputil_environment):
    """Bind wrapper CLIs to the same emulated SFP and mock services as sfputil."""
    from integration_tests.sonic_environment import TransceiverCommands

    return TransceiverCommands(monkeypatch, sfputil_environment)

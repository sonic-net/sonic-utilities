"""Lifecycle checks against actual child processes, including failed tests."""

import os

import pytest


pytestmark = pytest.mark.xcvr_emu


class TestEmulatorProcess:
    """Check process ownership and isolation without mocking subprocess creation."""

    @staticmethod
    def assert_reaped(process):
        """Check both Popen state and the OS child table, not merely an open TCP port."""
        assert process.poll() is not None
        with pytest.raises(ChildProcessError):
            os.waitpid(process.pid, os.WNOHANG)

    def test_daemon_is_a_real_reaped_child(self, tmp_path, module_config):
        """The custom YAML alone supplies the identity, without fixture writes."""
        from integration_tests.xcvr_emulator import EmulatorProcess

        with EmulatorProcess(tmp_path, module_config) as daemon:
            assert daemon.process.pid != os.getpid()
            assert daemon.process.poll() is None
            assert daemon.client.present()
            assert daemon.client.read_page(0, 0, 1) == b"\x18"
            assert daemon.client.read_page(0, 148, 16) == b"EMU-CMIS-400G".ljust(16, b"\x00")
            assert daemon.client.read_page(1, 142, 1)[0] & 0x20
            assert not any(access.write for access in daemon.client.accesses)
        assert daemon.process.returncode == 0
        self.assert_reaped(daemon.process)

    def test_config_overrides_are_independent(self, module_config):
        """Nested overrides must not mutate the source profile or another test's input."""
        from integration_tests.xcvr_emulator import EmulatorProcess

        overrides = {"VendorPN": "CUSTOM-MODULE", "DateCode": {"Year": "26", "Month": "09", "DayOfMonth": "23"}}
        config = EmulatorProcess.load_config(overrides)
        defaults = config["transceivers"][0]["defaults"]
        assert defaults["VendorPN"] == "CUSTOM-MODULE"
        assert defaults["DateCode"] == overrides["DateCode"]
        defaults["DateCode"]["Year"] = "99"
        assert overrides["DateCode"]["Year"] == "26"
        assert module_config["transceivers"][0]["defaults"]["VendorPN"] == "EMU-CMIS-400G"
        assert module_config["transceivers"][0]["defaults"]["DateCode"]["Year"] == "24"
        assert EmulatorProcess.load_config() == module_config

    def test_assertion_failure_still_stops_daemon(self, tmp_path, module_config):
        """Ensure a test failure cannot leave its emulator running."""
        from integration_tests.xcvr_emulator import EmulatorProcess

        with pytest.raises(AssertionError, match="deliberate test failure"):
            with EmulatorProcess(tmp_path, module_config) as daemon:
                assert daemon.client.present()
                raise AssertionError("deliberate test failure")
        self.assert_reaped(daemon.process)

    @pytest.mark.parametrize("config, message, log_message", [
        ({"invalid": {}}, "transceivers", "KeyError"),
        ({"transceivers": {}}, "Unexpected emulator inventory", "Server started"),
    ], ids=["invalid-config", "invalid-inventory"])
    def test_startup_failure_is_reported_and_reaped(self, tmp_path, config, message, log_message):
        """Expose startup errors and reap even when context entry never completes."""
        from integration_tests.xcvr_emulator import EmulatorProcess

        daemon = EmulatorProcess(tmp_path, config)
        with pytest.raises(AssertionError, match=message):
            with daemon:
                pytest.fail("An invalid emulator configuration unexpectedly started")
        self.assert_reaped(daemon.process)
        assert log_message in daemon.log_path.read_text()

    def test_fresh_processes_do_not_share_eeprom(self, tmp_path, module_config):
        """Verify process-per-test isolation of memory not covered by YAML defaults."""
        from integration_tests.xcvr_emulator import EmulatorProcess

        with EmulatorProcess(tmp_path / "first", module_config) as first:
            first.client.write_page(3, 128, b"\xde\xad\xbe\xef")
            assert first.client.read_page(3, 128, 4) == b"\xde\xad\xbe\xef"
        with EmulatorProcess(tmp_path / "second", module_config) as second:
            assert second.client.read_page(3, 128, 4) == b"\x00" * 4
        self.assert_reaped(first.process)
        self.assert_reaped(second.process)

    def test_transport_failure_is_not_a_success_shaped_default(self, tmp_path, module_config):
        """A dead daemon must surface a transport error, never fabricated EEPROM data."""
        import grpc
        from integration_tests.xcvr_emulator import EmulatorProcess

        with EmulatorProcess(tmp_path, module_config) as daemon:
            daemon.process.terminate()
            daemon.process.wait(timeout=5)
            with pytest.raises(grpc.RpcError):
                daemon.client.read_page(0, 0, 1)
        self.assert_reaped(daemon.process)

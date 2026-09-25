import unittest
from unittest.mock import patch

from secure_boot import secure_boot_backend


class TestSelectBackend(unittest.TestCase):
    def test_platform_backend_preferred(self):
        with patch.object(
            secure_boot_backend,
            "_is_executable",
            lambda path: path == secure_boot_backend.PLATFORM_BACKEND,
        ), patch.object(
            secure_boot_backend, "_uefi_services_available", lambda: True
        ):
            self.assertEqual(
                secure_boot_backend._select_backend(),
                secure_boot_backend.PLATFORM_BACKEND,
            )

    def test_platform_backend_preferred_when_both_available(self):
        with patch.object(
            secure_boot_backend,
            "_is_executable",
            lambda path: path in (
                secure_boot_backend.PLATFORM_BACKEND,
                secure_boot_backend.GENERIC_UEFI_BACKEND,
            ),
        ), patch.object(
            secure_boot_backend, "_uefi_services_available", lambda: True
        ):
            self.assertEqual(
                secure_boot_backend._select_backend(),
                secure_boot_backend.PLATFORM_BACKEND,
            )

    def test_generic_backend_fallback(self):
        def executable(path):
            return path == secure_boot_backend.GENERIC_UEFI_BACKEND

        with patch.object(
            secure_boot_backend, "_is_executable", executable
        ), patch.object(
            secure_boot_backend, "_uefi_services_available", lambda: True
        ):
            self.assertEqual(
                secure_boot_backend._select_backend(),
                secure_boot_backend.GENERIC_UEFI_BACKEND,
            )

    def test_generic_backend_not_selected_without_uefi(self):
        # Generic backend present but UEFI services unavailable -> unsupported.
        def executable(path):
            return path == secure_boot_backend.GENERIC_UEFI_BACKEND

        with patch.object(
            secure_boot_backend, "_is_executable", executable
        ), patch.object(
            secure_boot_backend, "_uefi_services_available", lambda: False
        ):
            self.assertIsNone(secure_boot_backend._select_backend())

    def test_backend_unsupported(self):
        with patch.object(
            secure_boot_backend, "_is_executable", lambda path: False
        ), patch.object(
            secure_boot_backend, "_uefi_services_available", lambda: False
        ):
            self.assertIsNone(secure_boot_backend._select_backend())


class TestMain(unittest.TestCase):
    def test_main_unsupported_reports_error(self):
        with patch.object(secure_boot_backend, "_select_backend", lambda: None):
            with patch("builtins.print") as mock_print:
                rc = secure_boot_backend.main()
        self.assertEqual(rc, 1)
        printed = mock_print.call_args[0][0]
        self.assertIn("not supported", printed)

    def test_main_execs_selected_backend(self):
        with patch.object(
            secure_boot_backend,
            "_select_backend",
            lambda: secure_boot_backend.PLATFORM_BACKEND,
        ):
            with patch("secure_boot.secure_boot_backend.os.execv") as execv:
                with patch.object(secure_boot_backend.sys, "argv", ["x", "status"]):
                    secure_boot_backend.main()
        execv.assert_called_once_with(
            secure_boot_backend.PLATFORM_BACKEND,
            [secure_boot_backend.PLATFORM_BACKEND, "status"],
        )

    def test_main_exec_failure_reports_error(self):
        with patch.object(
            secure_boot_backend,
            "_select_backend",
            lambda: secure_boot_backend.PLATFORM_BACKEND,
        ):
            with patch(
                "secure_boot.secure_boot_backend.os.execv",
                side_effect=OSError("boom"),
            ):
                with patch("builtins.print") as mock_print:
                    rc = secure_boot_backend.main()
        self.assertEqual(rc, 1)
        printed = mock_print.call_args[0][0]
        self.assertIn("failed to execute", printed)


if __name__ == "__main__":
    unittest.main()

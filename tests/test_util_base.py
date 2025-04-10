from unittest.mock import patch, MagicMock
from utilities_common.util_base import UtilHelper


@patch("pkgutil.iter_modules")
@patch("utilities_common.util_base.log.log_error")
@patch("utilities_common.util_base.log.log_warning")
def test_load_plugins_exceptions_logs(mock_log_warning, mock_log_error, mock_iter_modules):
    NON_EXISTENT_MODULE_NAME = "non-existent-module"
    FAILED_TO_IMPORT_MESSAGE = f"failed to import plugin {NON_EXISTENT_MODULE_NAME}"
    COMMON_EXCEPTION_MESSAGE = "Common exception"

    mock_iter_modules.return_value = [(None, NON_EXISTENT_MODULE_NAME, False)]
    plugins_namespace = MagicMock()
    plugins_namespace.__path__ = "some_path"
    plugins_namespace.__name__ = "some_name"

    # Assetion for ModuleNotFoundError
    list(UtilHelper().load_plugins(plugins_namespace))
    mock_log_warning.assert_called_once_with(
        f"{FAILED_TO_IMPORT_MESSAGE}: No module named '{NON_EXISTENT_MODULE_NAME}'",
        also_print_to_console=True
    )

    # Assertion for Exception
    with patch("importlib.import_module", side_effect=Exception(COMMON_EXCEPTION_MESSAGE)):
        list(UtilHelper().load_plugins(plugins_namespace))
    mock_log_error.assert_called_once_with(
        f"{FAILED_TO_IMPORT_MESSAGE}: {COMMON_EXCEPTION_MESSAGE}",
        also_print_to_console=True
    )

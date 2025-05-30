import sys
import pytest
from unittest import mock
from utilities_common.util_base import UtilHelper
from utilities_common.module import ModuleHelper, INVALID_MODULE_INDEX

sys.modules['sonic_platform'] = mock.MagicMock()

util = UtilHelper()
module_helper = ModuleHelper()


class TestModuleHelper:
    @pytest.fixture
    def mock_load_platform_chassis(self):
        with mock.patch('utilities_common.module.util.load_platform_chassis') as mock_load_platform_chassis:
            yield mock_load_platform_chassis

    @pytest.fixture
    def mock_try_get(self):
        with mock.patch('utilities_common.module.util.try_get') as mock_try_get:
            yield mock_try_get

    @pytest.fixture
    def mock_try_get_args(self):
        with mock.patch.object(ModuleHelper, 'try_get_args') as mock_try_get_args:
            yield mock_try_get_args

    @pytest.fixture
    def mock_log_error(self):
        with mock.patch('utilities_common.module.log.log_error') as mock_log_error:
            yield mock_log_error

    def test_try_get_args_success(self):
        def mock_callback(arg):
            return arg

        result = module_helper.try_get_args(mock_callback, "test_arg")
        assert result == "test_arg"

    def test_try_get_args_none_return(self):
        def mock_callback(arg):
            return None

        result = module_helper.try_get_args(mock_callback, "test_arg", default="default_value")
        assert result == "default_value"

    def test_try_get_args_not_implemented_error(self):
        def mock_callback(arg):
            raise NotImplementedError

        result = module_helper.try_get_args(mock_callback, "test_arg", default="default_value")
        assert result == "default_value"

    def test_init_success(self, mock_load_platform_chassis):
        mock_load_platform_chassis.return_value = mock.MagicMock()
        module_helper = ModuleHelper()
        assert module_helper.platform_chassis is not None

    def test_init_failure(self, mock_load_platform_chassis, mock_log_error):
        mock_load_platform_chassis.return_value = None
        module_helper = ModuleHelper()
        mock_log_error.assert_called_once_with("Failed to load platform chassis")
        assert module_helper.platform_chassis is None

    def test_reboot_module_success(self, mock_load_platform_chassis, mock_try_get_args):
        mock_try_get_args.return_value = True
        mock_load_platform_chassis.return_value.get_module_index.return_value = 1
        mock_load_platform_chassis.return_value.get_module.return_value.reboot.return_value = True

        result = module_helper.reboot_module("DPU1", "cold")
        assert result is True

    def test_reboot_module_invalid_index(self, mock_load_platform_chassis, mock_try_get_args):
        mock_try_get_args.return_value = INVALID_MODULE_INDEX
        mock_load_platform_chassis.return_value.get_module_index.return_value = INVALID_MODULE_INDEX

        result = module_helper.reboot_module("DPU1", "cold")
        assert result is False

    def test_module_pre_shutdown_success(self, mock_load_platform_chassis, mock_try_get_args, mock_try_get):
        mock_try_get_args.return_value = True
        mock_try_get.return_value = True
        mock_load_platform_chassis.return_value.get_module_index.return_value = 1
        mock_load_platform_chassis.return_value.get_module.return_value.module_pre_shutdown.return_value = True

        result = module_helper.module_pre_shutdown("DPU1")
        assert result is True

    def test_module_pre_shutdown_invalid_index(self, mock_load_platform_chassis, mock_try_get_args):
        mock_try_get_args.return_value = INVALID_MODULE_INDEX
        mock_load_platform_chassis.return_value.get_module_index.return_value = INVALID_MODULE_INDEX

        result = module_helper.module_pre_shutdown("DPU1")
        assert result is False

    def test_pci_reattach_module_success(self, mock_load_platform_chassis, mock_try_get_args, mock_try_get):
        mock_try_get_args.return_value = True
        mock_try_get.return_value = True
        mock_load_platform_chassis.return_value.get_module_index.return_value = 1
        mock_load_platform_chassis.return_value.get_module.return_value.module_post_startup.return_value = True

        result = module_helper.module_post_startup("DPU1")
        assert result is True

    def test_pci_reattach_module_invalid_index(self, mock_load_platform_chassis, mock_try_get_args):
        mock_try_get_args.return_value = INVALID_MODULE_INDEX
        mock_load_platform_chassis.return_value.get_module_index.return_value = INVALID_MODULE_INDEX

        result = module_helper.module_post_startup("DPU1")
        assert result is False

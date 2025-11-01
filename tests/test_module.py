import sys
import pytest
from unittest import mock
from utilities_common.util_base import UtilHelper
from utilities_common.module import ModuleHelper, INVALID_MODULE_INDEX

sys.modules['sonic_platform'] = mock.MagicMock()

util = UtilHelper()
module_helper = ModuleHelper()


class TestModuleHelper:
    @pytest.fixture(scope="function")
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

    def test_module_post_startup_success(self, mock_load_platform_chassis, mock_try_get_args, mock_try_get):
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

    def test_module_pre_shutdown_method_not_found(self, mock_load_platform_chassis, mock_try_get_args, mock_log_error):
        mock_try_get_args.return_value = 1
        # Create a plain object without any methods
        mock_module = object()
        module_helper.platform_chassis.get_module.return_value = mock_module

        result = module_helper.module_pre_shutdown("DPU1")
        assert result is False
        mock_log_error.assert_called_once_with("Module pre-shutdown method not found in platform chassis")

    def test_module_pre_shutdown_operation_failed(self,
                                                  mock_load_platform_chassis,
                                                  mock_try_get_args,
                                                  mock_try_get, mock_log_error):
        mock_try_get_args.return_value = 1
        mock_try_get.return_value = False
        mock_module = mock.MagicMock()
        mock_module.module_pre_shutdown.return_value = False
        module_helper.platform_chassis.get_module.return_value = mock_module

        result = module_helper.module_pre_shutdown("DPU1")
        assert result is False
        mock_log_error.assert_called_once_with("Module pre-shutdown status for module DPU1: False")

    def test_module_post_startup_method_not_found(self,
                                                  mock_load_platform_chassis,
                                                  mock_try_get_args,
                                                  mock_log_error):
        mock_try_get_args.return_value = 1
        # Create a plain object without any methods
        mock_module = object()
        module_helper.platform_chassis.get_module.return_value = mock_module

        result = module_helper.module_post_startup("DPU1")
        assert result is False
        mock_log_error.assert_called_once_with("Module post-startup method not found in platform chassis")

    def test_module_post_startup_operation_failed(self,
                                                  mock_load_platform_chassis,
                                                  mock_try_get_args,
                                                  mock_try_get,
                                                  mock_log_error):
        mock_try_get_args.return_value = 1
        mock_try_get.return_value = False
        mock_module = mock.MagicMock()
        mock_module.module_post_startup.return_value = False
        module_helper.platform_chassis.get_module.return_value = mock_module

        result = module_helper.module_post_startup("DPU1")
        assert result is False
        mock_log_error.assert_called_once_with("Module post-startup status for module DPU1: False")

    def test_set_module_state_transition_success(self,
                                                 mock_load_platform_chassis,
                                                 mock_try_get_args,
                                                 mock_try_get):
        mock_try_get_args.return_value = 1
        mock_try_get.return_value = True
        mock_module = mock.MagicMock()
        mock_module.set_module_state_transition.return_value = True
        module_helper.platform_chassis.get_module.return_value = mock_module

        result = module_helper.set_module_state_transition("DPU1", True)
        assert result is True

    def test_set_module_state_transition_invalid_index(self,
                                                       mock_load_platform_chassis,
                                                       mock_try_get_args):
        mock_try_get_args.return_value = INVALID_MODULE_INDEX

        result = module_helper.set_module_state_transition("DPU1", True)
        assert result is False

    def test_set_module_state_transition_method_not_found(self,
                                                          mock_load_platform_chassis,
                                                          mock_try_get_args,
                                                          mock_log_error):
        mock_try_get_args.return_value = 1
        mock_module = object()
        module_helper.platform_chassis.get_module.return_value = mock_module

        result = module_helper.set_module_state_transition("DPU1", True)
        assert result is False
        mock_log_error.assert_called_once_with("Set module state transition method not found in platform chassis")

    def test_set_module_state_transition_operation_failed(self,
                                                          mock_load_platform_chassis,
                                                          mock_try_get_args,
                                                          mock_try_get,
                                                          mock_log_error):
        mock_try_get_args.return_value = 1
        mock_try_get.return_value = False
        mock_module = mock.MagicMock()
        mock_module.set_module_state_transition.return_value = False
        module_helper.platform_chassis.get_module.return_value = mock_module

        result = module_helper.set_module_state_transition("DPU1", True)
        assert result is False
        mock_log_error.assert_called_once_with("Set module state transition flag status for module DPU1: False")

    def test_clear_module_state_transition_success(self,
                                                   mock_load_platform_chassis,
                                                   mock_try_get_args,
                                                   mock_try_get):
        mock_try_get_args.return_value = 1
        mock_try_get.return_value = True
        mock_module = mock.MagicMock()
        mock_module.clear_module_state_transition.return_value = True
        module_helper.platform_chassis.get_module.return_value = mock_module

        result = module_helper.clear_module_state_transition("DPU1")
        assert result is True

    def test_clear_module_state_transition_invalid_index(self,
                                                         mock_load_platform_chassis,
                                                         mock_try_get_args):
        mock_try_get_args.return_value = INVALID_MODULE_INDEX

        result = module_helper.clear_module_state_transition("DPU1")
        assert result is False

    def test_clear_module_state_transition_method_not_found(self,
                                                            mock_load_platform_chassis,
                                                            mock_try_get_args,
                                                            mock_log_error):
        mock_try_get_args.return_value = 1
        mock_module = object()
        module_helper.platform_chassis.get_module.return_value = mock_module

        result = module_helper.clear_module_state_transition("DPU1")
        assert result is False
        mock_log_error.assert_called_once_with("Clear module state transition method not found in platform chassis")

    def test_clear_module_state_transition_operation_failed(self,
                                                            mock_load_platform_chassis,
                                                            mock_try_get_args,
                                                            mock_try_get,
                                                            mock_log_error):
        mock_try_get_args.return_value = 1
        mock_try_get.return_value = False
        mock_module = mock.MagicMock()
        mock_module.clear_module_state_transition.return_value = False
        module_helper.platform_chassis.get_module.return_value = mock_module

        result = module_helper.clear_module_state_transition("DPU1")
        assert result is False
        mock_log_error.assert_called_once_with("Clear module state transition flag status for module DPU1: False")

    def test_get_module_state_transition_success(self,
                                                 mock_load_platform_chassis,
                                                 mock_try_get_args,
                                                 mock_try_get):
        mock_try_get_args.return_value = 1
        mock_try_get.return_value = True
        mock_module = mock.MagicMock()
        mock_module.get_module_state_transition.return_value = True
        module_helper.platform_chassis.get_module.return_value = mock_module

        result = module_helper.get_module_state_transition("DPU1")
        assert result is True

    def test_get_module_state_transition_invalid_index(self,
                                                       mock_load_platform_chassis,
                                                       mock_try_get_args):
        mock_try_get_args.return_value = INVALID_MODULE_INDEX

        result = module_helper.get_module_state_transition("DPU1")
        assert result is False

    def test_get_module_state_transition_method_not_found(self,
                                                          mock_load_platform_chassis,
                                                          mock_try_get_args,
                                                          mock_log_error):
        mock_try_get_args.return_value = 1
        mock_module = object()
        module_helper.platform_chassis.get_module.return_value = mock_module

        result = module_helper.get_module_state_transition("DPU1")
        assert result is False
        mock_log_error.assert_called_once_with("Get module state transition method not found in platform chassis")

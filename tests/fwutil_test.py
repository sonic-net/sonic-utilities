import sys
import pytest
from unittest.mock import call, patch, MagicMock

sys.modules['sonic_platform.platform'] = MagicMock()
import fwutil.lib as fwutil_lib

class TestSquashFs(object):
    def setup(self):
        print('SETUP')

    @patch('fwutil.lib.check_output_pipe')
    def test_get_current_image(self, mock_check_output_pipe):
        sqfs = fwutil_lib.SquashFs()
        sqfs.get_current_image()
        mock_check_output_pipe.assert_called_with(['sonic-installer', 'list'], ['grep', 'Current: '], ['cut', '-f2', '-d '])

    @patch('fwutil.lib.check_output_pipe')
    def test_get_next_image(self, mock_check_output_pipe):
        sqfs = fwutil_lib.SquashFs()
        sqfs.get_next_image()
        mock_check_output_pipe.assert_called_with(['sonic-installer', 'list'], ['grep', 'Next: '], ['cut', '-f2', '-d '])

    @patch("os.mkdir")
    @patch("os.path.exists", return_value=True)
    @patch("subprocess.check_call")
    @patch("os.path.ismount", MagicMock(return_value=False))
    @patch("fwutil.lib.SquashFs.next_image", MagicMock(return_value="SONiC-OS-123456"))
    def test_mount_next_image_fs(self, mock_check_call, mock_exists, mock_mkdir):
        image_stem = fwutil_lib.SquashFs.next_image()
        sqfs = fwutil_lib.SquashFs()
        sqfs.fs_path = "/host/image-{}/fs.squashfs".format(image_stem)
        sqfs.fs_mountpoint = "/tmp/image-{}-fs".format(image_stem)
        sqfs.overlay_mountpoint = "/tmp/image-{}-overlay".format(image_stem)

        result = sqfs.mount_next_image_fs()

        assert mock_mkdir.call_args_list == [
            call(sqfs.fs_mountpoint),
            call(sqfs.overlay_mountpoint)
        ]

        assert mock_check_call.call_args_list == [
            call(["mount", "-t", "squashfs", sqfs.fs_path, sqfs.fs_mountpoint]),
            call(["mount", "-n", "-r", "-t", "overlay", "-o", "lowerdir={},upperdir={},workdir={}".format(sqfs.fs_mountpoint, sqfs.fs_rw, sqfs.fs_work), "overlay", sqfs.overlay_mountpoint])
        ]

        assert mock_exists.call_args_list == [
            call(sqfs.fs_rw),
            call(sqfs.fs_work)
        ]

        assert result == sqfs.overlay_mountpoint

    @patch("os.rmdir")
    @patch("os.path.exists", return_value=True)
    @patch("subprocess.check_call")
    @patch("os.path.ismount", MagicMock(return_value=True))
    @patch("fwutil.lib.SquashFs.next_image", MagicMock(return_value="SONiC-OS-123456"))
    def test_unmount_next_image_fs(self, mock_check_call, mock_exists, mock_rmdir):
        sqfs = fwutil_lib.SquashFs()
        sqfs.fs_mountpoint = "/tmp/image-{}-fs".format("SONiC-OS-123456")
        sqfs.overlay_mountpoint = "/tmp/image-{}-overlay".format("SONiC-OS-123456")

        sqfs.umount_next_image_fs()

        assert mock_check_call.call_args_list == [
            call(["umount", "-rf", sqfs.overlay_mountpoint]),
            call(["umount", "-rf", sqfs.fs_mountpoint])
        ]

        assert mock_rmdir.call_args_list == [
            call(sqfs.overlay_mountpoint),
            call(sqfs.fs_mountpoint)
        ]

    def teardown(self):
        print('TEARDOWN')


class TestComponentUpdateProvider(object):
    def setup(self):
        print('SETUP')

    @patch("glob.glob", MagicMock(side_effect=[[], ['abc'], [], ['abc']]))
    @patch("fwutil.lib.ComponentUpdateProvider.read_au_status_file_if_exists", MagicMock(return_value=['def']))
    @patch("fwutil.lib.ComponentUpdateProvider._ComponentUpdateProvider__validate_platform_schema", MagicMock())
    @patch("fwutil.lib.PlatformComponentsParser.parse_platform_components", MagicMock())
    @patch("os.mkdir", MagicMock())
    def test_is_capable_auto_update(self):
        CUProvider = fwutil_lib.ComponentUpdateProvider()
        assert CUProvider.is_capable_auto_update('none') == True
        assert CUProvider.is_capable_auto_update('def') == True

    @patch('fwutil.lib.Platform')
    @patch('fwutil.lib.PlatformComponentsParser')
    @patch('fwutil.lib.ComponentUpdateProvider._ComponentUpdateProvider__validate_platform_schema')
    @patch('os.path.isdir', return_value=True)
    def test_is_smart_switch_method(self, mock_isdir, mock_validate,
                                    mock_parser_class, mock_platform_class):
        """Test that the is_smart_switch method correctly returns True
        when the chassis.is_smartswitch() method returns True."""
        # Setup mock chassis
        mock_chassis = MagicMock()
        mock_chassis.is_smartswitch.return_value = True

        # Setup mock platform
        mock_platform = MagicMock()
        mock_platform.get_chassis.return_value = mock_chassis
        mock_platform_class.return_value = mock_platform

        # Create ComponentUpdateProvider instance
        cup = fwutil_lib.ComponentUpdateProvider()

        # Test is_smart_switch method
        assert cup.is_smart_switch()
        mock_chassis.is_smartswitch.assert_called_once()

    @patch('fwutil.lib.Platform')
    @patch('fwutil.lib.PlatformComponentsParser')
    @patch('fwutil.lib.ComponentUpdateProvider._ComponentUpdateProvider__validate_platform_schema')
    @patch('os.mkdir')
    def test_smartswitch_modular_chassis_parsing(self, mock_mkdir, mock_validate,
                                                 mock_parser_class, mock_platform_class):
        """Test that SmartSwitch devices with modules are passed as non-modular (False)
        to the PlatformComponentsParser constructor."""
        # Setup mock chassis that is SmartSwitch and has modules
        mock_chassis = MagicMock()
        mock_chassis.is_smartswitch.return_value = True
        mock_chassis.get_all_modules.return_value = [MagicMock(), MagicMock()]  # 2 modules

        # Setup mock platform
        mock_platform = MagicMock()
        mock_platform.get_chassis.return_value = mock_chassis
        mock_platform_class.return_value = mock_platform

        # Setup mock parser
        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser

        # Create ComponentUpdateProvider instance
        fwutil_lib.ComponentUpdateProvider()

        # Verify that PlatformComponentsParser was called with is_modular_chassis=False
        # because SmartSwitch should be treated as non-modular for parsing purposes
        mock_parser_class.assert_called_once_with(False)

    @patch('fwutil.lib.Platform')
    @patch('fwutil.lib.PlatformComponentsParser')
    @patch('fwutil.lib.ComponentUpdateProvider._ComponentUpdateProvider__validate_platform_schema')
    @patch('os.mkdir')
    def test_regular_modular_chassis_parsing(self, mock_mkdir, mock_validate, mock_parser_class, mock_platform_class):
        """Test that regular modular chassis is treated as modular for parsing"""
        # Setup mock chassis that is not SmartSwitch but has modules
        mock_chassis = MagicMock()
        mock_chassis.is_smartswitch.return_value = False
        mock_chassis.get_all_modules.return_value = [MagicMock(), MagicMock()]  # 2 modules

        # Setup mock platform
        mock_platform = MagicMock()
        mock_platform.get_chassis.return_value = mock_chassis
        mock_platform_class.return_value = mock_platform

        # Setup mock parser
        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser

        # Create ComponentUpdateProvider instance
        fwutil_lib.ComponentUpdateProvider()

        # Verify that PlatformComponentsParser was called with is_modular_chassis=True
        # because regular modular chassis should be treated as modular
        mock_parser_class.assert_called_once_with(True)

    @patch('fwutil.lib.Platform')
    @patch('fwutil.lib.PlatformComponentsParser')
    @patch('fwutil.lib.ComponentUpdateProvider._ComponentUpdateProvider__validate_platform_schema')
    @patch('os.mkdir')
    def test_smartswitch_module_validation_skip(self, mock_mkdir, mock_validate,
                                                mock_parser_class, mock_platform_class):
        """Test that module validation is skipped for SmartSwitch platforms"""
        # Setup mock chassis that is SmartSwitch
        mock_chassis = MagicMock()
        mock_chassis.is_smartswitch.return_value = True
        mock_chassis.get_all_modules.return_value = [MagicMock()]  # Has modules

        # Setup mock platform
        mock_platform = MagicMock()
        mock_platform.get_chassis.return_value = mock_chassis
        mock_platform_class.return_value = mock_platform

        # Setup mock parser
        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser

        # Create ComponentUpdateProvider instance
        cup = fwutil_lib.ComponentUpdateProvider()

        # Test that module validation is skipped for SmartSwitch
        # This should not raise an exception even if there are differences
        pdp_map = {'module1': {'comp1': MagicMock()}}
        pcp_map = {'module2': {'comp2': MagicMock()}}  # Different modules

        # Should not raise exception for SmartSwitch module validation
        cup._ComponentUpdateProvider__validate_component_map(
            cup.SECTION_MODULE, pdp_map, pcp_map
        )

    @patch('fwutil.lib.Platform')
    @patch('fwutil.lib.PlatformComponentsParser')
    @patch('fwutil.lib.ComponentUpdateProvider._ComponentUpdateProvider__validate_platform_schema')
    @patch('os.mkdir')
    def test_regular_chassis_module_validation_error(self, mock_mkdir, mock_validate,
                                                     mock_parser_class, mock_platform_class):
        """Test that module validation raises error for regular modular chassis"""
        # Setup mock chassis that is not SmartSwitch but has modules
        mock_chassis = MagicMock()
        mock_chassis.is_smartswitch.return_value = False
        mock_chassis.get_all_modules.return_value = [MagicMock()]  # Has modules

        # Setup mock platform
        mock_platform = MagicMock()
        mock_platform.get_chassis.return_value = mock_chassis
        mock_platform_class.return_value = mock_platform

        # Setup mock parser
        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser

        # Create ComponentUpdateProvider instance
        cup = fwutil_lib.ComponentUpdateProvider()

        # Test that module validation raises error for regular modular chassis
        pdp_map = {'module1': {'comp1': MagicMock()}}
        pcp_map = {'module2': {'comp2': MagicMock()}}  # Different modules

        # Should raise exception for regular modular chassis
        with pytest.raises(RuntimeError) as excinfo:
            cup._ComponentUpdateProvider__validate_component_map(
                cup.SECTION_MODULE, pdp_map, pcp_map
            )
        assert "Module names mismatch" in str(excinfo.value)

    def teardown(self):
        print('TEARDOWN')

import os
import tarfile
import importlib
import sys
import pytest
from unittest.mock import call, patch, MagicMock

# fwutil/__init__.py imports sonic_platform at module level;
# inject before importing fwutil.lib so collection succeeds.
sys.modules['sonic_platform'] = MagicMock()
sys.modules['sonic_platform.platform'] = MagicMock()
import fwutil.lib as fwutil_lib

class TestSquashFs(object):
    def setup_method(self):
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

    def teardown_method(self):
        print('TEARDOWN')


class TestComponentUpdateProvider(object):
    def setup_method(self):
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

    def teardown_method(self):
        print('TEARDOWN')


class TestFwutilMain(object):
    def test_main_import_does_not_init_platform_provider(self):
        import fwutil.lib as fwutil_lib
        sys.modules.pop('fwutil.main', None)
        with patch.object(fwutil_lib, "PlatformDataProvider") as pdp_cls:
            import fwutil.main as fw_main
            importlib.reload(fw_main)
            pdp_cls.assert_not_called()

    def test_get_pdp_is_singleton(self):
        import fwutil.main as fw_main
        with patch.object(fw_main, "PlatformDataProvider") as pdp_cls:
            pdp_instance = MagicMock()
            pdp_cls.return_value = pdp_instance
            fw_main._pdp = None

            first = fw_main.get_pdp()
            second = fw_main.get_pdp()

            assert first is pdp_instance
            assert second is pdp_instance
            pdp_cls.assert_called_once()

    def test_chassis_handler_populates_context(self):
        import fwutil.main as fw_main
        ctx = MagicMock()
        ctx.obj = {fw_main.COMPONENT_PATH_CTX_KEY: []}
        pdp = MagicMock()
        pdp.chassis.get_name.return_value = "ChassisA"

        with patch.object(fw_main, "get_pdp", return_value=pdp) as mock_get_pdp:
            fw_main.chassis_handler(ctx)

        mock_get_pdp.assert_called_once()
        assert ctx.obj[fw_main.CHASSIS_NAME_CTX_KEY] == "ChassisA"
        assert ctx.obj[fw_main.COMPONENT_PATH_CTX_KEY] == ["ChassisA"]

    def test_module_handler_populates_context(self):
        import fwutil.main as fw_main
        ctx = MagicMock()
        ctx.obj = {fw_main.COMPONENT_PATH_CTX_KEY: []}
        pdp = MagicMock()
        pdp.chassis.get_name.return_value = "ChassisA"

        with patch.object(fw_main, "get_pdp", return_value=pdp) as mock_get_pdp:
            fw_main.module_handler(ctx, "Module1")

        mock_get_pdp.assert_called_once()
        assert ctx.obj[fw_main.MODULE_NAME_CTX_KEY] == "Module1"
        assert ctx.obj[fw_main.COMPONENT_PATH_CTX_KEY] == ["ChassisA", "Module1"]

    def test_validate_module_success(self):
        import fwutil.main as fw_main
        ctx = MagicMock()
        param = MagicMock()
        param.metavar = "<module_name>"
        pdp = MagicMock()
        pdp.is_modular_chassis.return_value = True
        pdp.module_component_map = {"Module1": {}}

        with patch.object(fw_main, "get_pdp", return_value=pdp) as mock_get_pdp:
            result = fw_main.validate_module(ctx, param, "Module1")

        mock_get_pdp.assert_called_once()
        assert result == "Module1"

    def test_validate_component_with_chassis(self):
        import fwutil.main as fw_main
        ctx = MagicMock()
        ctx.obj = {fw_main.CHASSIS_NAME_CTX_KEY: "ChassisA"}
        param = MagicMock()
        param.metavar = "<component_name>"
        component = MagicMock()
        pdp = MagicMock()
        pdp.chassis_component_map = {"ChassisA": {"Comp1": component}}

        with patch.object(fw_main, "get_pdp", return_value=pdp) as mock_get_pdp:
            result = fw_main.validate_component(ctx, param, "Comp1")

        mock_get_pdp.assert_called_once()
        assert result == "Comp1"
        assert ctx.obj[fw_main.COMPONENT_CTX_KEY] is component


class TestFWPackageUntar(object):
    """Tests for FWPackage.untar_fwpackage() path traversal protection."""

    def _make_tar(self, members, tmp_path):
        """Helper to create a tar file with given regular file members."""
        import io
        tar_path = str(tmp_path / "test.tar")
        with tarfile.open(tar_path, 'w') as t:
            for name in members:
                info = tarfile.TarInfo(name=name)
                data = b"test content"
                info.size = len(data)
                t.addfile(info, io.BytesIO(data))
        return tar_path

    def _make_symlink_tar(self, tmp_path, link_name, link_target):
        """Helper to create a tar file with a symlink member."""
        tar_path = str(tmp_path / "symlink.tar")
        with tarfile.open(tar_path, 'w') as t:
            info = tarfile.TarInfo(name=link_name)
            info.type = tarfile.SYMTYPE
            info.linkname = link_target
            t.addfile(info)
        return tar_path

    def test_valid_tar_extracts_successfully(self, tmp_path):
        extract_dir = str(tmp_path / "extract")
        os.makedirs(extract_dir)
        tar_path = self._make_tar(['platform_components.json', 'bios.bin'], tmp_path)
        pkg = fwutil_lib.FWPackage.__new__(fwutil_lib.FWPackage)
        pkg.fwupdate_package_name = tar_path
        with patch('fwutil.lib.FWUPDATE_FWPACKAGE_DIR', extract_dir):
            result = pkg.untar_fwpackage()
        assert result is True

    def test_path_traversal_is_blocked(self, tmp_path):
        extract_dir = str(tmp_path / "extract")
        os.makedirs(extract_dir)
        tar_path = self._make_tar(['../../etc/cron.d/evil'], tmp_path)
        pkg = fwutil_lib.FWPackage.__new__(fwutil_lib.FWPackage)
        pkg.fwupdate_package_name = tar_path
        with patch('fwutil.lib.FWUPDATE_FWPACKAGE_DIR', extract_dir):
            with pytest.raises(ValueError, match="unsafe path"):
                pkg.untar_fwpackage()

    def test_absolute_path_in_tar_is_blocked(self, tmp_path):
        extract_dir = str(tmp_path / "extract")
        os.makedirs(extract_dir)
        tar_path = self._make_tar(['/etc/passwd'], tmp_path)
        pkg = fwutil_lib.FWPackage.__new__(fwutil_lib.FWPackage)
        pkg.fwupdate_package_name = tar_path
        with patch('fwutil.lib.FWUPDATE_FWPACKAGE_DIR', extract_dir):
            with pytest.raises(ValueError, match="unsafe path"):
                pkg.untar_fwpackage()

    def test_symlink_escaping_is_blocked(self, tmp_path):
        extract_dir = str(tmp_path / "extract")
        os.makedirs(extract_dir)
        tar_path = self._make_symlink_tar(tmp_path, 'evil_link', '/etc/passwd')
        pkg = fwutil_lib.FWPackage.__new__(fwutil_lib.FWPackage)
        pkg.fwupdate_package_name = tar_path
        with patch('fwutil.lib.FWUPDATE_FWPACKAGE_DIR', extract_dir):
            with pytest.raises(ValueError, match="unsafe link"):
                pkg.untar_fwpackage()

    def test_symlink_within_tarball_is_allowed(self, tmp_path):
        extract_dir = str(tmp_path / "extract")
        os.makedirs(extract_dir)
        # Symlink pointing to another file inside the tarball is safe
        tar_path = self._make_symlink_tar(tmp_path, 'link_to_config', './platform_components.json')
        pkg = fwutil_lib.FWPackage.__new__(fwutil_lib.FWPackage)
        pkg.fwupdate_package_name = tar_path
        with patch('fwutil.lib.FWUPDATE_FWPACKAGE_DIR', extract_dir):
            result = pkg.untar_fwpackage()
        assert result is True


class TestFirmwareVersionStatus(object):
    """Unit tests for the firmware up-to-date decision in ComponentUpdateProvider.

    Covers __compare_versions() and __get_update_status() -- the fix where a
    component whose running firmware is the same as (or newer than) the version
    shipped in the SONiC image is reported "up-to-date" instead of
    "update is required", while non-numeric vendor labels (e.g. SSD
    "SBR10021"/"0710-001" or hex CPLD/FPGA revisions like "0x13") fall back to
    the legacy strict-equality behavior.
    """

    UP_TO_DATE = fwutil_lib.ComponentUpdateProvider.FW_STATUS_UP_TO_DATE
    UPDATE_REQUIRED = fwutil_lib.ComponentUpdateProvider.FW_STATUS_UPDATE_REQUIRED

    @staticmethod
    def _compare(current, available):
        # Reach the name-mangled private static method.
        cls = fwutil_lib.ComponentUpdateProvider
        return cls._ComponentUpdateProvider__compare_versions(current, available)

    @staticmethod
    def _status(current, available):
        # __get_update_status only reads class constants and calls
        # __compare_versions, so an uninitialized instance is sufficient
        # (no Platform/parser construction required).
        cup = fwutil_lib.ComponentUpdateProvider.__new__(
            fwutil_lib.ComponentUpdateProvider)
        return cup._ComponentUpdateProvider__get_update_status(current, available)

    @pytest.mark.parametrize("current, available, expected", [
        ("0212.0216", "0212.0215", 1),      # motivating case: running newer
        ("0212.0215", "0212.0216", -1),     # running older
        ("1.2.3", "1.2.3", 0),              # equal
        ("4.8", "4.8.0", 0),                # zero-padding: 4.8 == 4.8.0
        ("4.8.1", "4.8", 1),                # zero-padding: 4.8.1 > 4.8
        ("29.10", "29.9", 1),               # numeric (10 > 9), not lexical
        ("3.30", "3.5", 1),                 # numeric (30 > 5)
        ("SBR10021", "0710-001", None),     # SSD vendor labels: not comparable
        ("0x13", "0x12", None),             # hex CPLD/FPGA revision: not comparable
        ("240622.1D", "240622.1C", None),   # mixed alnum token: not comparable
        (None, "1.0", None),                # guard: missing current
        ("1.0", None, None),                # guard: missing available
        ("", "1.0", None),                  # guard: empty string has no number
    ])
    def test_compare_versions(self, current, available, expected):
        assert self._compare(current, available) == expected

    @pytest.mark.parametrize("current, available, up_to_date", [
        ("1.0", "1.0", True),               # identical
        ("0212.0216", "0212.0216", True),   # equal numeric
        ("0212.0216", "0212.0215", True),   # running newer -> up-to-date (the fix)
        ("0212.0215", "0212.0216", False),  # running older -> update required
        ("4.8.1", "4.8", True),             # newer with zero-pad -> up-to-date
        ("SBR10021", "SBR10021", True),     # vendor label equal -> up-to-date
        ("0710-001", "SBR10021", False),    # vendor mismatch -> update required
        ("0x13", "0x13", True),             # hex equal -> up-to-date (early equality)
        ("0x13", "0x12", False),            # hex differ -> strict fallback -> required
    ])
    def test_get_update_status(self, current, available, up_to_date):
        expected = self.UP_TO_DATE if up_to_date else self.UPDATE_REQUIRED
        assert self._status(current, available) == expected

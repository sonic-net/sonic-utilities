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


def make_fw_double(method_name, *, supports_force, raises_type_error=False,
                   return_value=None):
    """Build a firmware component test double for install/update tests.

    Returns an object exposing a single ``method_name`` (``install_firmware`` or
    ``update_firmware``) that appends every call to ``.calls`` and then returns
    ``return_value`` (or raises ``TypeError`` when ``raises_type_error``).

    ``force_update`` support is expressed through the method's *real* signature so
    ``supports_force_update`` (which inspects the signature) sees it correctly:
    when ``supports_force`` the method takes ``force_update=False`` and records
    ``(path, force_update)``; otherwise it takes only ``path`` and records
    ``(path,)``. A ``**kwargs``-style shortcut is deliberately avoided because it
    would be misdetected as force-update-capable.
    """
    calls = []

    if supports_force:
        def method(self, path, force_update=False):
            calls.append((path, force_update))
            if raises_type_error:
                raise TypeError("backend boom")
            return return_value
    else:
        def method(self, path):
            calls.append((path,))
            if raises_type_error:
                raise TypeError("backend boom")
            return return_value

    double = type("_FwDouble", (), {method_name: method})()
    double.calls = calls
    return double


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
        """Test that a chassis with module firmware components is treated as modular"""
        # Setup mock chassis that is not SmartSwitch and has a module that
        # actually exposes firmware components (a genuine modular chassis).
        mock_chassis = MagicMock()
        mock_chassis.is_smartswitch.return_value = False
        mock_component = MagicMock()
        mock_component.get_name.return_value = "CPLD"
        mock_module = MagicMock()
        mock_module.get_name.return_value = "Module1"
        mock_module.get_all_components.return_value = [mock_component]
        mock_chassis.get_all_modules.return_value = [mock_module]

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
    @patch('fwutil.lib.ComponentUpdateProvider._ComponentUpdateProvider__validate_platform_schema', MagicMock())
    @patch('os.mkdir', MagicMock())
    def test_module_without_components_is_non_modular(self, mock_parser_class, mock_platform_class):
        """A chassis whose modules expose no firmware components is NOT modular.

        Mirrors the NVIDIA AST2700 BMC, which exposes a component-less
        SWITCH-HOST module. Such a module must not make fwutil treat the device
        as modular (which would wrongly require a "module" section in
        platform_components.json).
        """
        mock_chassis = MagicMock()
        mock_chassis.is_smartswitch.return_value = False
        mock_module = MagicMock()
        mock_module.get_name.return_value = "SWITCH-HOST"
        mock_module.get_all_components.return_value = []  # no firmware components
        mock_chassis.get_all_modules.return_value = [mock_module]

        mock_platform = MagicMock()
        mock_platform.get_chassis.return_value = mock_chassis
        mock_platform_class.return_value = mock_platform
        mock_parser_class.return_value = MagicMock()

        fwutil_lib.ComponentUpdateProvider()

        # A component-less module must be treated as non-modular.
        mock_parser_class.assert_called_once_with(False)

    @patch('fwutil.lib.Platform')
    @patch('fwutil.lib.PlatformComponentsParser')
    @patch('fwutil.lib.ComponentUpdateProvider._ComponentUpdateProvider__validate_platform_schema')
    @patch('os.mkdir')
    def test_any_module_with_components_is_modular(self, mock_mkdir, mock_validate,
                                                   mock_parser_class, mock_platform_class):
        """Covers the any-module-has-components contract.

        A chassis may mix a component-less module (e.g. the BMC's SWITCH-HOST)
        with a module that does expose firmware components. If *any* module has
        components the chassis must be treated as modular, so the component-less
        module alongside it must not suppress modularity.
        """
        mock_chassis = MagicMock()
        mock_chassis.is_smartswitch.return_value = False

        empty_module = MagicMock()
        empty_module.get_name.return_value = "SWITCH-HOST"
        empty_module.get_all_components.return_value = []  # no firmware components

        component = MagicMock()
        component.get_name.return_value = "CPLD"
        fw_module = MagicMock()
        fw_module.get_name.return_value = "Module1"
        fw_module.get_all_components.return_value = [component]

        mock_chassis.get_all_modules.return_value = [empty_module, fw_module]

        mock_platform = MagicMock()
        mock_platform.get_chassis.return_value = mock_chassis
        mock_platform_class.return_value = mock_platform
        mock_parser_class.return_value = MagicMock()

        fwutil_lib.ComponentUpdateProvider()

        # Any module with components makes the chassis modular.
        mock_parser_class.assert_called_once_with(True)

    def test_component_less_module_construction_succeeds(self, tmp_path):
        """Integration test with REAL schema parsing/validation.

        A chassis that exposes a component-less module (e.g. the NVIDIA AST2700
        BMC's SWITCH-HOST) together with a platform_components.json that has no
        'module' section must construct without error. This exercises the real
        PlatformComponentsParser and __validate_platform_schema (neither is
        mocked), guarding against the regression where the non-modular chassis
        still tripped a spurious 'module names mismatch'.
        """
        import json

        root = str(tmp_path)
        platform_components = {
            "chassis": {
                "BMC-CHASSIS": {
                    "component": {}
                }
            }
        }
        with open(os.path.join(root, "platform_components.json"), "w") as f:
            json.dump(platform_components, f)

        module = MagicMock()
        module.get_name.return_value = "SWITCH-HOST"
        module.get_all_components.return_value = []  # component-less module

        chassis = MagicMock()
        chassis.is_smartswitch.return_value = False
        chassis.get_name.return_value = "BMC-CHASSIS"
        chassis.get_all_components.return_value = []
        chassis.get_all_modules.return_value = [module]

        # Route the parser at our temp platform_components.json (the FWUPDATE
        # path branch just joins root + filename) and skip real dir creation.
        with patch('fwutil.lib.Platform') as platform_cls, \
             patch('fwutil.lib.FWUPDATE_FWPACKAGE_DIR', root), \
             patch('os.path.isdir', return_value=True):
            platform_cls.return_value.get_chassis.return_value = chassis
            cup = fwutil_lib.ComponentUpdateProvider(root)

        assert cup.is_modular_chassis() is False
        # The real parser must not have required/parsed a module section for a
        # non-modular chassis: the parsed schema's module map is empty.
        pcp = cup._ComponentUpdateProvider__pcp
        assert pcp.module_component_map == {}

    def test_modular_chassis_missing_module_section_fails(self, tmp_path):
        """Complement to test_component_less_module_construction_succeeds.

        A genuinely modular chassis (a module exposes firmware components) with
        the SAME missing 'module' section must FAIL, proving the module-section
        requirement is enforced conditionally on modularity - not skipped
        unconditionally. Exercises the real PlatformComponentsParser and
        __validate_platform_schema paths (neither is mocked).
        """
        import json

        root = str(tmp_path)
        # Identical to the non-modular case: chassis section only, no 'module'.
        platform_components = {
            "chassis": {
                "BMC-CHASSIS": {
                    "component": {}
                }
            }
        }
        with open(os.path.join(root, "platform_components.json"), "w") as f:
            json.dump(platform_components, f)

        component = MagicMock()
        component.get_name.return_value = "CPLD"
        module = MagicMock()
        module.get_name.return_value = "Module1"
        module.get_all_components.return_value = [component]  # modular chassis

        chassis = MagicMock()
        chassis.is_smartswitch.return_value = False
        chassis.get_name.return_value = "BMC-CHASSIS"
        chassis.get_all_components.return_value = []
        chassis.get_all_modules.return_value = [module]

        with patch('fwutil.lib.Platform') as platform_cls, \
             patch('fwutil.lib.FWUPDATE_FWPACKAGE_DIR', root), \
             patch('os.path.isdir', return_value=True):
            platform_cls.return_value.get_chassis.return_value = chassis
            with pytest.raises(RuntimeError, match="module"):
                fwutil_lib.ComponentUpdateProvider(root)

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

    def test_invoke_install_firmware_is_keyword_only(self):
        # force_update is keyword-only: a positional boolean must be rejected.
        import fwutil.main as fw_main
        component = MagicMock()
        with pytest.raises(TypeError):
            fw_main._invoke_install_firmware(component, "/tmp/fw.bin", True)
        component.install_firmware.assert_not_called()

    def test_invoke_install_firmware_uses_force_when_supported(self):
        import fwutil.main as fw_main
        component = make_fw_double(
            "install_firmware", supports_force=True, return_value=True
        )
        result = fw_main._invoke_install_firmware(
            component, "/tmp/fw.bin", force_update=True
        )
        assert result is True
        assert component.calls == [("/tmp/fw.bin", True)]

    def test_invoke_install_firmware_no_force(self):
        import fwutil.main as fw_main
        component = make_fw_double(
            "install_firmware", supports_force=True, return_value=True
        )
        result = fw_main._invoke_install_firmware(
            component, "/tmp/fw.bin", force_update=False
        )
        assert result is True
        assert component.calls == [("/tmp/fw.bin", False)]

    def test_invoke_install_firmware_falls_back_when_unsupported(self):
        # A component whose install_firmware lacks force_update is detected via
        # its signature (not by catching TypeError) and gets a plain install.
        import fwutil.main as fw_main
        component = make_fw_double(
            "install_firmware", supports_force=False, return_value=True
        )
        with patch.object(fw_main, "log_helper") as mock_log:
            result = fw_main._invoke_install_firmware(
                component, "/tmp/fw.bin", force_update=True
            )
        assert result is True
        assert component.calls == [("/tmp/fw.bin",)]
        mock_log.print_warning.assert_called_once()

    def test_invoke_install_firmware_backend_typeerror_propagates_without_retry(self):
        # A TypeError from a force-update-capable install_firmware must propagate
        # unchanged and must NOT trigger a second, force_update-less install.
        import fwutil.main as fw_main
        component = make_fw_double(
            "install_firmware", supports_force=True, raises_type_error=True,
            return_value=True,
        )
        with patch.object(fw_main, "log_helper") as mock_log:
            with pytest.raises(TypeError, match="backend boom"):
                fw_main._invoke_install_firmware(
                    component, "/tmp/fw.bin", force_update=True
                )
        assert component.calls == [("/tmp/fw.bin", True)]  # single call, no retry
        mock_log.print_warning.assert_not_called()


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


class TestForceUpdateSupport:
    """update_firmware() must decide --force-update support from the backend's
    signature (before invocation), not by catching a TypeError from the backend
    call. Catching a runtime TypeError could mask a real backend bug and, worse,
    silently re-run a firmware update that may have already started."""

    def _make_cup(self, component, firmware_path="/tmp/fw.bin"):
        cup = fwutil_lib.ComponentUpdateProvider.__new__(fwutil_lib.ComponentUpdateProvider)
        fw_key = fwutil_lib.PlatformComponentsParser.FIRMWARE_KEY
        cup.chassis_component_map = {"CHASSIS": {"COMP": component}}
        cup.module_component_map = {}
        pcp = MagicMock()
        pcp.FIRMWARE_KEY = fw_key
        pcp.chassis_component_map = {"CHASSIS": {"COMP": {fw_key: firmware_path}}}
        cup._ComponentUpdateProvider__pcp = pcp
        cup._ComponentUpdateProvider__root_path = None
        return cup

    @patch("fwutil.lib.log_helper")
    def test_force_update_used_when_supported(self, mock_log):
        comp = make_fw_double("update_firmware", supports_force=True)
        cup = self._make_cup(comp)
        cup.update_firmware("CHASSIS", None, "COMP", force_update=True)
        assert comp.calls == [("/tmp/fw.bin", True)]
        mock_log.print_warning.assert_not_called()

    @patch("fwutil.lib.log_helper")
    def test_falls_back_when_force_update_unsupported(self, mock_log):
        comp = make_fw_double("update_firmware", supports_force=False)
        cup = self._make_cup(comp)
        cup.update_firmware("CHASSIS", None, "COMP", force_update=True)
        assert comp.calls == [("/tmp/fw.bin",)]
        mock_log.print_warning.assert_called_once()

    @patch("fwutil.lib.log_helper")
    def test_backend_typeerror_propagates_without_retry(self, mock_log):
        # The regression this fix guards: a TypeError from a force-update-capable
        # backend must propagate unchanged and must NOT trigger a second,
        # force_update-less invocation.
        comp = make_fw_double(
            "update_firmware", supports_force=True, raises_type_error=True
        )
        cup = self._make_cup(comp)
        with pytest.raises(TypeError, match="backend boom"):
            cup.update_firmware("CHASSIS", None, "COMP", force_update=True)
        assert comp.calls == [("/tmp/fw.bin", True)]  # single call, no retry
        mock_log.print_warning.assert_not_called()

    @patch("fwutil.lib.log_helper")
    def test_no_force_update_calls_without_force(self, mock_log):
        comp = make_fw_double("update_firmware", supports_force=True)
        cup = self._make_cup(comp)
        cup.update_firmware("CHASSIS", None, "COMP", force_update=False)
        assert comp.calls == [("/tmp/fw.bin", False)]
        mock_log.print_warning.assert_not_called()

    def test_force_update_is_keyword_only(self):
        # force_update is keyword-only: passing it positionally must be rejected
        # so it can never be misbound to another positional argument.
        comp = make_fw_double("update_firmware", supports_force=True)
        cup = self._make_cup(comp)
        with pytest.raises(TypeError):
            cup.update_firmware("CHASSIS", None, "COMP", True)
        assert comp.calls == []

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

    def teardown(self):
        print('TEARDOWN')

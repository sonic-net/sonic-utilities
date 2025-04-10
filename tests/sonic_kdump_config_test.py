import logging
import os
import sys
import unittest
from unittest.mock import patch, mock_open, Mock
from utilities_common.general import load_module_from_source
from sonic_installer.common import IMAGE_PREFIX
import argparse

TESTS_DIR_PATH = os.path.dirname(os.path.abspath(__file__))
UTILITY_DIR_PATH = os.path.dirname(TESTS_DIR_PATH)
SCRIPTS_DIR_PATH = os.path.join(UTILITY_DIR_PATH, "scripts")
sys.path.append(SCRIPTS_DIR_PATH)

ABOOT_MACHINE_CFG_PLATFORM = "aboot_platform=x86_64-arista_7050cx3_32s"
ABOOT_MACHINE_CFG_ARCH = "aboot_arch=x86_64"
KERNEL_BOOTING_CFG_KDUMP_DISABLED = "loop=image-20201231.63/fs.squashfs loopfstype=squashfs"
KERNEL_BOOTING_CFG_KDUMP_ENABLED = "loop=image-20201231.63/fs.squashfs loopfstype=squashfs crashkernel=0M-2G:256MB"

logger = logging.getLogger(__name__)
# Load `sonic-kdump-config` module from source since `sonic-kdump-config` does not have .py extension.
sonic_kdump_config_path = os.path.join(SCRIPTS_DIR_PATH, "sonic-kdump-config")
sonic_kdump_config = load_module_from_source("sonic_kdump_config", sonic_kdump_config_path)


class TestSonicKdumpConfig(unittest.TestCase):
    @classmethod
    def setup_class(cls):
        print("SETUP")

    @patch("sonic_kdump_config.run_command")
    def test_read_num_kdumps(self, mock_run_cmd):
        """Tests the function `read_num_kdumps(...)` in script `sonic-kdump-config`.
        """
        mock_run_cmd.return_value = (0, ["0"], None)
        num_dumps = sonic_kdump_config.read_num_dumps()
        assert num_dumps == 0
        logger.info("Value of 'num_dumps' is: '{}'.".format(num_dumps))
        logger.info("Expected value of 'num_dumps' is: '0'.")

        mock_run_cmd.return_value = (0, ["NotInteger"], None)
        with self.assertRaises(SystemExit) as sys_exit:
            num_dumps = sonic_kdump_config.read_num_dumps()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.return_value = (0, (), None)
        with self.assertRaises(SystemExit) as sys_exit:
            num_dumps = sonic_kdump_config.read_num_dumps()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.return_value = (0, [], None)
        with self.assertRaises(SystemExit) as sys_exit:
            num_dumps = sonic_kdump_config.read_num_dumps()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.return_value = (1, [], None)
        with self.assertRaises(SystemExit) as sys_exit:
            num_dumps = sonic_kdump_config.read_num_dumps()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.return_value = (1, ["3"], None)
        with self.assertRaises(SystemExit) as sys_exit:
            num_dumps = sonic_kdump_config.read_num_dumps()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.return_value = (1, (), None)
        with self.assertRaises(SystemExit) as sys_exit:
            num_dumps = sonic_kdump_config.read_num_dumps()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.return_value = (1, ["NotInteger"], None)
        with self.assertRaises(SystemExit) as sys_exit:
            num_dumps = sonic_kdump_config.read_num_dumps()
        self.assertEqual(sys_exit.exception.code, 1)

    @patch("sonic_kdump_config.run_command")
    def test_read_use_kdump(self, mock_run_cmd):
        """Tests the function `read_use_kdump(...)` in script `sonic-kdump-config`.
        """
        mock_run_cmd.return_value = (0, ["0"], None)
        is_kdump_enabled = sonic_kdump_config.read_use_kdump()
        assert is_kdump_enabled == 0

        mock_run_cmd.return_value = (0, (), None)
        with self.assertRaises(SystemExit) as sys_exit:
            is_kdump_enabled = sonic_kdump_config.read_use_kdump()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.return_value = (0, [], None)
        with self.assertRaises(SystemExit) as sys_exit:
            is_kdump_enabled = sonic_kdump_config.read_use_kdump()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.return_value = (0, ["NotInteger"], None)
        with self.assertRaises(SystemExit) as sys_exit:
            is_kdump_enabled = sonic_kdump_config.read_use_kdump()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.return_value = (1, ["0"], None)
        with self.assertRaises(SystemExit) as sys_exit:
            is_kdump_enabled = sonic_kdump_config.read_use_kdump()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.return_value = (1, ["NotInteger"], None)
        with self.assertRaises(SystemExit) as sys_exit:
            is_kdump_enabled = sonic_kdump_config.read_use_kdump()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.return_value = (1, (), None)
        with self.assertRaises(SystemExit) as sys_exit:
            is_kdump_enabled = sonic_kdump_config.read_use_kdump()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.return_value = (1, [], None)
        with self.assertRaises(SystemExit) as sys_exit:
            is_kdump_enabled = sonic_kdump_config.read_use_kdump()
        self.assertEqual(sys_exit.exception.code, 1)

    @patch("sonic_kdump_config.read_use_kdump")
    @patch("sonic_kdump_config.run_command")
    def test_write_num_kdump(self, mock_run_cmd, mock_read_kdump):
        """Tests the function `write_use_kdump(...)` in script `sonic-kdump-config`.
        """
        mock_run_cmd.side_effect = [(0, [], None), (0, ["1"], None)]
        mock_read_kdump.return_value = 0
        sonic_kdump_config.write_use_kdump(0)

        mock_run_cmd.side_effect = [(0, (), None), (0, ["1"], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(0)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(0, ["NotInteger"], None), (0, ["1"], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(0)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(2, [], None), (0, ["1"], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(0)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(2, (), None), (0, ["1"], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(0)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(2, ["NotInteger"], None), (0, ["1"], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(0)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(0, (), None), (0, ["1"], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(1)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(0, ["NotInteger"], None), (0, ["1"], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(1)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(2, [], None), (0, ["1"], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(1)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(2, (), None), (0, ["1"], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(1)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(2, ["NotInteger"], None), (0, ["1"], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(1)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(0, [], None), (1, [""], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(1)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(0, [], None), (0, ["1"], None)]
        mock_read_kdump.return_value = 1
        sonic_kdump_config.write_use_kdump(1)

        mock_run_cmd.side_effect = [(0, [], None), (1, [""], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(1)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(0, [], None), (0, [""], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(1)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(0, [], None), (0, [""], None)]
        mock_read_kdump.return_value = 1
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(0)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(0, [], None), (1, [""], None)]
        mock_read_kdump.return_value = 1
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(0)
        self.assertEqual(sys_exit.exception.code, 1)

        mock_run_cmd.side_effect = [(0, [], None), (1, [""], None)]
        mock_read_kdump.return_value = 0
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_use_kdump(0)
        self.assertEqual(sys_exit.exception.code, 1)

    @patch('sonic_kdump_config.run_command')
    @patch('sonic_kdump_config.read_ssh_string')
    @patch('builtins.print')  # Mock print to capture printed output
    def test_cmd_kdump_ssh_string_none(self, mock_print, mock_read, mock_run):
        # Mock the output of run_command when ssh_string is None
        mock_run.return_value = (0, ['current_ssh_string'], '')  # Simulated output
        sonic_kdump_config.cmd_kdump_ssh_string(verbose=True, ssh_string=None)

        # Check that run_command was called with the correct command
        mock_run.assert_called_once_with("show kdump ssh_string", use_shell=False)

        # Verify that the printed output is correct
        mock_print.assert_called_once_with('current_ssh_string')

    @patch('sonic_kdump_config.run_command')
    @patch('sonic_kdump_config.read_ssh_string')
    @patch('sonic_kdump_config.write_ssh_string')
    @patch('builtins.print')  # Mock print to capture printed output
    def test_cmd_kdump_ssh_string_update(self, mock_print, mock_write, mock_read, mock_run):
        # Mock read_ssh_string to return the current SSH string
        mock_read.return_value = 'old_ssh_string'
        # Call the function with a new SSH string to configure
        sonic_kdump_config.cmd_kdump_ssh_string(verbose=True, ssh_string='new_ssh_string')

        # Check that write_ssh_string was called with the new SSH string
        mock_write.assert_called_once_with('new_ssh_string')

        # Verify that the correct message is printed
        mock_print.assert_called_once_with("SSH string updated. Changes will take effect after the next reboot.")

    @patch('sonic_kdump_config.run_command')
    @patch('sonic_kdump_config.read_ssh_string')
    @patch('sonic_kdump_config.write_ssh_string')
    @patch('builtins.print')  # Mock print to capture printed output
    def test_cmd_kdump_ssh_string_no_update(self, mock_print, mock_write, mock_read, mock_run):
        # Mock read_ssh_string to return the same SSH string provided
        mock_read.return_value = 'same_ssh_string'

        # Call the function with the same SSH string
        sonic_kdump_config.cmd_kdump_ssh_string(verbose=True, ssh_string='same_ssh_string')

        # Check that write_ssh_string was not called
        mock_write.assert_not_called()

        # Check that no message is printed for update
        mock_print.assert_not_called()

    @patch("sonic_kdump_config.kdump_disable")
    @patch("sonic_kdump_config.get_current_image")
    @patch("sonic_kdump_config.get_kdump_administrative_mode")
    @patch("sonic_kdump_config.get_kdump_memory")
    @patch("sonic_kdump_config.get_kdump_num_dumps")
    @patch("os.path.exists")
    def test_cmd_kdump_disable(self, mock_path_exist, mock_num_dumps, mock_memory,
                               mock_administrative_mode, mock_image, mock_kdump_disable):
        """Tests the function `cmd_kdump_disable(...)` in script `sonic-kdump-config.py`.
        """
        mock_path_exist.return_value = True
        mock_num_dumps.return_value = 3
        mock_memory.return_value = "0M-2G:256MB"
        mock_administrative_mode = "True"
        mock_image.return_value = "20201230.63"
        mock_kdump_disable.return_value = True

        return_result = sonic_kdump_config.cmd_kdump_disable(True)
        assert return_result == True

        mock_path_exist.return_value = False
        with patch("sonic_kdump_config.open", mock_open(read_data=ABOOT_MACHINE_CFG_PLATFORM)):
            return_result = sonic_kdump_config.cmd_kdump_disable(True)
            assert return_result == True

        mock_path_exist.return_value = False
        with patch("sonic_kdump_config.open", mock_open(read_data=ABOOT_MACHINE_CFG_ARCH)):
            return_result = sonic_kdump_config.cmd_kdump_disable(True)
            assert return_result == False

    @patch("sonic_kdump_config.read_num_dumps")
    @patch("sonic_kdump_config.run_command")
    def test_write_num_dumps(self, mock_run_cmd, mock_read_num_dumps):
        # Success case: correct write and verification
        mock_run_cmd.side_effect = [(0, [], None)]
        mock_read_num_dumps.return_value = 5
        sonic_kdump_config.write_num_dumps(5)

        # Case where run_command returns wrong type
        mock_run_cmd.side_effect = [(0, (), None)]
        mock_read_num_dumps.return_value = 5
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_num_dumps(5)
        self.assertEqual(sys_exit.exception.code, 1)

        # Case where line is non-empty
        mock_run_cmd.side_effect = [(0, ["Some output"], None)]
        mock_read_num_dumps.return_value = 5
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_num_dumps(5)
        self.assertEqual(sys_exit.exception.code, 1)

        # Case where read_num_dumps does not match input
        mock_run_cmd.side_effect = [(0, [], None)]
        mock_read_num_dumps.return_value = 4
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_num_dumps(5)
        self.assertEqual(sys_exit.exception.code, 1)

        # Case where run_command fails
        mock_run_cmd.side_effect = [(1, [], "Error")]
        mock_read_num_dumps.return_value = 5
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_num_dumps(5)
        self.assertEqual(sys_exit.exception.code, 1)

        # Case where lines contain non-integer
        mock_run_cmd.side_effect = [(0, ["NotInteger"], None)]
        mock_read_num_dumps.return_value = 5
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_num_dumps(5)
        self.assertEqual(sys_exit.exception.code, 1)

        # Edge case: empty string in output but matches value
        mock_run_cmd.side_effect = [(0, [""], None)]
        mock_read_num_dumps.return_value = 5
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_num_dumps(5)
        self.assertEqual(sys_exit.exception.code, 1)

        # Edge case: read_num_dumps returns matching value but run_command fails
        mock_run_cmd.side_effect = [(2, [], None)]
        mock_read_num_dumps.return_value = 5
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_num_dumps(5)
        self.assertEqual(sys_exit.exception.code, 1)

    @patch("sonic_kdump_config.get_bootloader")
    def test_get_image(self, mock_get_bootloader):
        """Tests the function `get_current_image() and get_next_image()` in script `sonic-kdump-config.py`.
        """
        # Setup bootloader mock
        mock_bootloader = Mock()
        mock_bootloader.get_current_image = Mock(return_value=IMAGE_PREFIX + "-20201230.62")
        mock_bootloader.get_next_image = Mock(return_value=IMAGE_PREFIX + "-20201230.63")
        mock_get_bootloader.return_value = mock_bootloader

        return_result = sonic_kdump_config.get_next_image()
        assert return_result == "-20201230.63"

        return_result = sonic_kdump_config.get_current_image()
        assert return_result == "-20201230.62"

        mock_bootloader.get_current_image.return_value = "-20201230.62"
        with self.assertRaises(SystemExit) as sys_exit:
            return_result = sonic_kdump_config.get_current_image()
        self.assertEqual(sys_exit.exception.code, 1)

        mock_bootloader.get_next_image.return_value = "-20201230.63"
        with self.assertRaises(SystemExit) as sys_exit:
            return_result = sonic_kdump_config.get_next_image()
        self.assertEqual(sys_exit.exception.code, 1)

    @patch("sonic_kdump_config.run_command")
    @patch("sonic_kdump_config.get_kdump_remote")
    def test_write_kdump_remote_true(self, mock_read_remote, mock_run_command):
        """Test when remote is true, SSH and SSH_KEY should be uncommented."""
        mock_read_remote.return_value = True  # Simulate that remote is true

        sonic_kdump_config.write_kdump_remote()  # Call the function

        # Ensure the correct commands were run to uncomment SSH and SSH_KEY
        mock_run_command.assert_any_call("/bin/sed -i 's/#SSH/SSH/' /etc/default/kdump-tools", use_shell=False)
        mock_run_command.assert_any_call("/bin/sed -i 's/#SSH_KEY/SSH_KEY/' /etc/default/kdump-tools", use_shell=False)
        self.assertEqual(mock_run_command.call_count, 2)  # Ensure both commands were called

    @patch("sonic_kdump_config.run_command")
    @patch("sonic_kdump_config.get_kdump_remote")
    def test_write_kdump_remote_false(self, mock_read_remote, mock_run_command):
        """Test when remote is false, SSH and SSH_KEY should be commented."""
        mock_read_remote.return_value = False  # Simulate that remote is false

        sonic_kdump_config.write_kdump_remote()  # Call the function

        # Ensure the correct commands were run to comment SSH and SSH_KEY
        mock_run_command.assert_any_call("/bin/sed -i 's/SSH/#SSH/' /etc/default/kdump-tools", use_shell=False)
        mock_run_command.assert_any_call("/bin/sed -i 's/SSH_KEY/#SSH_KEY/' /etc/default/kdump-tools", use_shell=False)
        self.assertEqual(mock_run_command.call_count, 2)

    @patch("sonic_kdump_config.kdump_enable")
    @patch("sonic_kdump_config.os.path.exists")
    @patch("sonic_kdump_config.get_kdump_ssh_path")
    @patch("sonic_kdump_config.get_kdump_ssh_string")
    @patch("sonic_kdump_config.get_kdump_remote")
    @patch("sonic_kdump_config.get_kdump_num_dumps")
    @patch("sonic_kdump_config.get_kdump_memory")
    @patch("sonic_kdump_config.get_kdump_administrative_mode")
    @patch("sonic_kdump_config.open", new_callable=mock_open, read_data='... aboot ...')
    def test_cmd_kdump_enable_aboot_platform(self,
            mock_open_file,
            mock_admin_mode,
            mock_memory,
            mock_num_dumps,
            mock_remote,
            mock_ssh_string,
            mock_ssh_path,
            mock_exists,
            mock_kdump_enable):

        # Setup mocks
        mock_admin_mode.return_value = True
        mock_memory.return_value = "512M"
        mock_num_dumps.return_value = 3
        mock_remote.return_value = True
        mock_ssh_string.return_value = "user@host"
        mock_ssh_path.return_value = "/path/to/key"
        mock_exists.return_value = False  # grub_cfg does not exist

        image = "test-image"
        mock_kdump_enable.return_value = True

        result = sonic_kdump_config.cmd_kdump_enable(verbose=True, image=image)
        self.assertTrue(result)

        # Extract aboot_cfg value from mock_open_file (the path should include 'aboot')
        # Let's assume `cmd_kdump_enable` internally constructs something like '/host/boot/aboot.cfg'
        expected_aboot_cfg = "/host/boot/aboot.cfg"

        # Validate that kdump_enable was called with correct arguments
        mock_kdump_enable.assert_called_once_with(
            True,                 # verbose
            "512M",               # memory
            3,                    # num_dumps
            "test-image",         # image
            expected_aboot_cfg,   # aboot_cfg path
            True,                 # remote
            "user@host",          # ssh_string
            "/path/to/key"        # ssh_path
        )

    @patch("sonic_kdump_config.kdump_enable")
    @patch("sonic_kdump_config.open", new_callable=mock_open, read_data='some config data')
    @patch("sonic_kdump_config.os.path.exists")
    @patch("sonic_kdump_config.get_kdump_ssh_path")
    @patch("sonic_kdump_config.get_kdump_ssh_string")
    @patch("sonic_kdump_config.get_kdump_remote")
    @patch("sonic_kdump_config.get_kdump_num_dumps")
    @patch("sonic_kdump_config.get_kdump_memory")
    @patch("sonic_kdump_config.get_kdump_administrative_mode")
    def test_cmd_kdump_enable_unsupported_platform(self,
            mock_admin_mode,
            mock_memory,
            mock_num_dumps,
            mock_remote,
            mock_ssh_string,
            mock_ssh_path,
            mock_exists,
            mock_open_file,
            mock_kdump_enable):

        # Setup: Not grub_cfg, no aboot_platform -> should print unsupported
        mock_exists.return_value = False
        mock_open_file.return_value.read.return_value = 'no aboot string'

        result = sonic_kdump_config.cmd_kdump_enable(verbose=True, image="img")
        self.assertFalse(result)
        mock_kdump_enable.assert_not_called()

    @patch("sonic_kdump_config.kdump_enable")
    @patch("sonic_kdump_config.open", new_callable=mock_open)
    @patch("sonic_kdump_config.os.path.exists")
    @patch("sonic_kdump_config.get_kdump_ssh_path")
    @patch("sonic_kdump_config.get_kdump_ssh_string")
    @patch("sonic_kdump_config.get_kdump_remote")
    @patch("sonic_kdump_config.get_kdump_num_dumps")
    @patch("sonic_kdump_config.get_kdump_memory")
    @patch("sonic_kdump_config.get_kdump_administrative_mode")
    def test_cmd_kdump_enable_grub_cfg_exists(self,
            mock_admin_mode,
            mock_memory,
            mock_num_dumps,
            mock_remote,
            mock_ssh_string,
            mock_ssh_path,
            mock_exists,
            mock_open_file,
            mock_kdump_enable):

        # Setup grub.cfg path exists
        mock_exists.return_value = True
        mock_kdump_enable.return_value = True
        result = sonic_kdump_config.cmd_kdump_enable(verbose=False, image="img")
        self.assertTrue(result)
        mock_kdump_enable.assert_called_once()

    @patch("sonic_kdump_config.get_kdump_remote")
    @patch("sonic_kdump_config.run_command")
    def test_cmd_kdump_remote(self, mock_run_command, mock_read_remote):
        """Tests the function `cmd_kdump_remote(...)` in script `sonic-kdump-config`."""

        # Test case: Remote is True
        mock_read_remote.return_value = True
        sonic_kdump_config.cmd_kdump_remote(verbose=True)

        # Ensure the correct commands are being run
        mock_run_command.assert_any_call("/bin/sed -i 's/#SSH/SSH/' /etc/default/kdump-tools", use_shell=False)
        mock_run_command.assert_any_call("/bin/sed -i 's/#SSH_KEY/SSH_KEY/' /etc/default/kdump-tools", use_shell=False)

        # Test case: Remote is False
        mock_read_remote.return_value = False
        sonic_kdump_config.cmd_kdump_remote(verbose=True)

        # Ensure the correct commands are being run
        mock_run_command.assert_any_call("/bin/sed -i 's/SSH/#SSH/' /etc/default/kdump-tools", use_shell=False)
        mock_run_command.assert_any_call("/bin/sed -i 's/SSH_KEY/#SSH_KEY/' /etc/default/kdump-tools", use_shell=False)

        # Test case: Checking output messages
        with patch("builtins.print") as mock_print:
            sonic_kdump_config.cmd_kdump_remote(verbose=True)
            mock_print.assert_called_with("SSH and SSH_KEY commented out for local configuration.")

            mock_read_remote.return_value = False
            sonic_kdump_config.cmd_kdump_remote(verbose=True)
            mock_print.assert_called_with("SSH and SSH_KEY commented out for local configuration.")

    @patch("sonic_kdump_config.run_command")
    def test_read_ssh_string(self, mock_run_cmd):
        """Tests the function `read_ssh_string(...)` in script `sonic-kdump-config`."""

        # Test case for successful read
        mock_run_cmd.return_value = (0, ['user@ip_address'], None)  # Simulate successful command execution
        ssh_string = sonic_kdump_config.read_ssh_string()
        self.assertEqual(ssh_string, 'user@ip_address')

        # Test case for non-integer output
        mock_run_cmd.return_value = (0, ['NotAString'], None)  # Simulate command execution returning a non-string
        ssh_string = sonic_kdump_config.read_ssh_string()
        self.assertEqual(ssh_string, 'NotAString')

        # Test case for empty output
        mock_run_cmd.return_value = (0, [], None)  # Simulate command execution with empty output
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.read_ssh_string()
        self.assertEqual(sys_exit.exception.code, 1)

        # Test case for command failure
        mock_run_cmd.return_value = (1, [], None)  # Simulate command failure
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.read_ssh_string()
        self.assertEqual(sys_exit.exception.code, 1)

    @patch("sonic_kdump_config.run_command")
    @patch("sonic_kdump_config.read_ssh_string")
    def test_write_ssh_string(self, mock_read_ssh_string, mock_run_cmd):
        """Tests the function `write_ssh_string(...)` in script `sonic-kdump-config`."""

        # Test successful case
        mock_run_cmd.return_value = (0, [], None)  # Simulate successful command execution
        mock_read_ssh_string.return_value = 'user@ip_address'  # Simulate reading existing SSH string

        # Call the function to test
        sonic_kdump_config.write_ssh_string('user@ip_address')

        # Verify that run_command was called with the correct command list
        expected_cmd = [
            "/bin/sed",
            "-i",
            "-e",
            's/#*SSH=.*/SSH="user@ip_address"/',
            sonic_kdump_config.kdump_cfg
        ]
        mock_run_cmd.assert_called_once_with(expected_cmd, use_shell=False)

        # Test case where write fails
        mock_run_cmd.reset_mock()  # Reset the mock for new test
        mock_run_cmd.return_value = (1, [], None)  # Simulate command failure
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_ssh_string('user@ip_address')
        self.assertEqual(sys_exit.exception.code, 1)

        # Test case where the written SSH string doesn't match the expected value
        mock_run_cmd.reset_mock()  # Reset the mock for new test
        mock_run_cmd.return_value = (0, [], None)
        mock_read_ssh_string.return_value = 'different_user@ip_address'  # Simulate reading a different SSH string
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_ssh_string('user@ip_address')
        self.assertEqual(sys_exit.exception.code, 1)

    @patch("sonic_kdump_config.run_command")
    def test_read_ssh_path(self, mock_run_cmd):
        """Tests the function `read_ssh_path(...)` in script `sonic-kdump-config`."""

        # Test successful case with valid SSH path
        mock_run_cmd.return_value = (0, ['/path/to/keys'], None)
        ssh_path = sonic_kdump_config.read_ssh_path()
        self.assertEqual(ssh_path, '/path/to/keys')

        # Test case where SSH path is invalid
        mock_run_cmd.return_value = (0, ['NotAPath'], None)
        with self.assertRaises(SystemExit) as sys_exit:
            ssh_path = sonic_kdump_config.read_ssh_path()
        self.assertEqual(sys_exit.exception.code, 1)

        # Test case where grep fails (no SSH path found)
        mock_run_cmd.return_value = (1, [], None)
        with self.assertRaises(SystemExit) as sys_exit:
            ssh_path = sonic_kdump_config.read_ssh_path()
        self.assertEqual(sys_exit.exception.code, 1)

    @patch("sonic_kdump_config.run_command")
    @patch("sonic_kdump_config.read_ssh_path")
    def test_write_ssh_path(self, mock_read_ssh_path, mock_run_cmd):
        """Tests the function `write_ssh_path(...)` in script `sonic-kdump-config`."""

        # Test case: Successfully write a valid SSH path
        mock_run_cmd.return_value = (0, [], None)  # Simulate successful sed command
        mock_read_ssh_path.return_value = '/path/to/keys'  # Simulate correct SSH path read

        sonic_kdump_config.write_ssh_path('/path/to/keys')  # Call function with valid path
        # Ensure the correct command is being run
        expected_cmd = (
            "/bin/sed -i -e 's/#*SSH_KEY=.*/SSH_KEY=\"/path/to/keys\"/' %s"
            % sonic_kdump_config.kdump_cfg
        )
        mock_run_cmd.assert_called_once_with(expected_cmd, use_shell=False)

        # Test case: SSH path in config doesn't match the provided one
        mock_read_ssh_path.return_value = '/wrong/path'
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_ssh_path('/path/to/keys')
        self.assertEqual(sys_exit.exception.code, 1)

        # Test case: Error during sed command execution
        mock_run_cmd.return_value = (1, [], "Error")
        with self.assertRaises(SystemExit) as sys_exit:
            sonic_kdump_config.write_ssh_path('/path/to/keys')
        self.assertEqual(sys_exit.exception.code, 1)

    @patch('sonic_kdump_config.run_command')
    @patch('sonic_kdump_config.read_ssh_path')
    @patch('builtins.print')  # Mock print to capture printed output
    def test_cmd_kdump_ssh_path_none(self, mock_print, mock_read, mock_run):
        # Mock the output of run_command when ssh_path is None
        mock_run.return_value = (0, ['current_ssh_path'], '')  # Simulated output
        sonic_kdump_config.cmd_kdump_ssh_path(verbose=True, ssh_path=None)

        # Check that run_command was called with the correct command
        mock_run.assert_called_once_with("show kdump ssh_path", use_shell=False)

        # Verify that the printed output is correct
        mock_print.assert_called_once_with('current_ssh_path')

    @patch('builtins.open', new_callable=mock_open, read_data='loop=image-myimage crashkernel=128M')
    @patch('sonic_kdump_config.run_command')
    @patch('sonic_kdump_config.write_use_kdump')
    @patch('sonic_kdump_config.rewrite_cfg')
    @patch('sonic_kdump_config.search_for_crash_kernel_in_cmdline')
    @patch('sonic_kdump_config.search_for_crash_kernel')
    @patch('sonic_kdump_config.locate_image')
    def test_kdump_enable_remote(
        self, mock_locate, mock_search_kernel, mock_search_cmdline,
        mock_rewrite, mock_write_kdump, mock_run, mock_open
    ):
        # Setup mocks
        mock_locate.return_value = 0  # Image found at index 0
        mock_search_cmdline.return_value = None  # No crashkernel set in cmdline
        mock_search_kernel.return_value = None  # No crashkernel set in image line
        mock_run.return_value = (0, [], '')  # Simulate successful remote configuration

        # Call the function with remote enabled
        changed = sonic_kdump_config.kdump_enable(
                    verbose=True, kdump_enabled=True, memory='128M', num_dumps=3,
                    image='myimage', cmdline_file='cmdline.txt',
                    remote=True, ssh_string='user@remote', ssh_path='/path/to/keys'
        )

        # Assertions
        self.assertTrue(changed)  # Expect some changes to be made
        mock_run.assert_called_once_with("/usr/sbin/kdump-config set-remote user@remote /path/to/keys", use_shell=False)

    @patch('builtins.open', new_callable=mock_open, read_data='loop=image-myimage crashkernel=128M')
    @patch('sonic_kdump_config.run_command')
    @patch('sonic_kdump_config.write_use_kdump')
    @patch('sonic_kdump_config.rewrite_cfg')
    @patch('sonic_kdump_config.search_for_crash_kernel_in_cmdline')
    @patch('sonic_kdump_config.search_for_crash_kernel')
    @patch('sonic_kdump_config.locate_image')
    def test_kdump_enable_remote_error(
            self, mock_locate, mock_search_kernel, mock_search_cmdline,
            mock_rewrite, mock_write_kdump, mock_run, mock_open
            ):
        # Setup mocks
        mock_locate.return_value = 0  # Image found at index 0
        mock_search_cmdline.return_value = None  # No crashkernel set in cmdline
        mock_search_kernel.return_value = None  # No crashkernel set in image line
        mock_run.return_value = (1, [], 'Error occurred')  # Simulate failure

        # Expecting sys.exit to be called on failure
        with self.assertRaises(SystemExit):
            sonic_kdump_config.kdump_enable(
                verbose=True, kdump_enabled=True, memory='128M', num_dumps=3,
                image='myimage', cmdline_file='cmdline.txt',
                remote=True, ssh_string='user@remote', ssh_path='/path/to/keys'
                )

        # Check that the error message was printed
        mock_run.assert_called_once_with("/usr/sbin/kdump-config set-remote user@remote /path/to/keys", use_shell=False)

    @patch('builtins.open', new_callable=mock_open, read_data='loop=image-myimage crashkernel=128M')
    @patch('sonic_kdump_config.run_command')
    @patch('sonic_kdump_config.write_use_kdump')
    @patch('sonic_kdump_config.rewrite_cfg')
    @patch('sonic_kdump_config.search_for_crash_kernel_in_cmdline')
    @patch('sonic_kdump_config.search_for_crash_kernel')
    @patch('sonic_kdump_config.locate_image')
    def test_kdump_enable_local(
            self, mock_locate, mock_search_kernel, mock_search_cmdline,
            mock_rewrite, mock_write_kdump, mock_run, mock_open
            ):
        # Setup mocks
        mock_locate.return_value = 0  # Image found at index 0
        mock_search_cmdline.return_value = None  # No crashkernel set in cmdline
        mock_search_kernel.return_value = None  # No crashkernel set in image line

        # Call the function with remote disabled
        changed = sonic_kdump_config.kdump_enable(
            verbose=True, kdump_enabled=True, memory='128M', num_dumps=3,
            image='myimage', cmdline_file='cmdline.txt',
            remote=False, ssh_string='user@remote', ssh_path='/path/to/keys'
            )

        # Assertions

        self.assertTrue(changed)  # Expect some changes to be made
        mock_run.assert_not_called()  # Ensure no remote commands were run

    @patch('sonic_kdump_config.run_command')
    @patch('sonic_kdump_config.read_ssh_path')
    @patch('sonic_kdump_config.write_ssh_path')
    @patch('builtins.print')  # Mock print to capture printed output
    def test_cmd_kdump_ssh_path_update(self, mock_print, mock_write, mock_read, mock_run):
        # Mock read_ssh_path to return the current SSH path
        mock_read.return_value = '/old/path/to/keys'

        # Call the function with a new SSH path
        sonic_kdump_config.cmd_kdump_ssh_path(verbose=True, ssh_path='/new/path/to/keys')

        # Check that write_ssh_path was called with the new SSH path
        mock_write.assert_called_once_with('/new/path/to/keys')

        # Verify that the correct message is printed
        mock_print.assert_called_once_with("SSH path updated. Changes will take effect after reboot.")

    @patch('sonic_kdump_config.run_command')
    @patch('sonic_kdump_config.read_ssh_path')
    @patch('sonic_kdump_config.write_ssh_path')
    @patch('builtins.print')  # Mock print to capture printed output
    def test_cmd_kdump_ssh_path_no_update(self, mock_print, mock_write, mock_read, mock_run):
        # Mock read_ssh_path to return the same SSH path provided
        mock_read.return_value = '/same/path/to/keys'

        # Call the function with the same SSH path
        sonic_kdump_config.cmd_kdump_ssh_path(verbose=True, ssh_path='/same/path/to/keys')

        # Check that write_ssh_path was not called
        mock_write.assert_not_called()

        # Check that no message is printed for update
        mock_print.assert_not_called()

    @patch("sonic_kdump_config.write_use_kdump")
    @patch("os.path.exists")
    def test_kdump_disable(self, mock_path_exist, mock_write_kdump):
        """Tests the function `kdump_disable(...)` in script `sonic-kdump-config.py`.
        """
        mock_path_exist.return_value = True
        mock_write_kdump.return_value = 0

        return_result = sonic_kdump_config.kdump_disable(True, "20201230.63", "/host/image-20201231.64/kernel-cmdline")
        assert return_result == False

        mock_open_func = mock_open(read_data=KERNEL_BOOTING_CFG_KDUMP_ENABLED)
        with patch("sonic_kdump_config.open", mock_open_func):
            return_result = sonic_kdump_config.kdump_disable(True, "20201230.63", "/host/grub/grub.cfg")
            assert return_result == True
            handle = mock_open_func()
            handle.writelines.assert_called_once()

        mock_open_func = mock_open(read_data=KERNEL_BOOTING_CFG_KDUMP_DISABLED)
        with patch("sonic_kdump_config.open", mock_open_func):
            return_result = sonic_kdump_config.kdump_disable(True, "20201230.63", "/host/grub/grub.cfg")
            assert return_result == False

        mock_path_exist.return_value = False
        mock_open_func = mock_open(read_data=KERNEL_BOOTING_CFG_KDUMP_ENABLED)
        with patch("sonic_kdump_config.open", mock_open_func):
            return_result = sonic_kdump_config.kdump_disable(True, "20201230.63", "/host/grub/grub.cfg")
            assert return_result == False
            handle = mock_open_func()
            handle.writelines.assert_called_once()

        mock_path_exist.return_value = False
        mock_open_func = mock_open(read_data=KERNEL_BOOTING_CFG_KDUMP_DISABLED)
        with patch("sonic_kdump_config.open", mock_open_func):
            return_result = sonic_kdump_config.kdump_disable(True, "20201230.63", "/host/grub/grub.cfg")
            assert return_result == False

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")

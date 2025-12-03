import click
import mock
import pytest
import pdb
import subprocess

from sonic_installer.main import SWAPAllocator


class TestSWAPAllocator(object):

    @classmethod
    def setup(cls):
        print("SETUP")

    def test_read_from_meminfo(self):
        proc_meminfo_lines = [
            "MemTotal:       32859496 kB",
            "MemFree:        16275512 kB",
            "SwapTotal:      2000000  kB",
            "SwapFree:       1000000  kB",
            "HugePages_Total:       0",
            "HugePages_Free:        0",
        ]

        read_meminfo_expected_return = {
            "MemTotal": 32859496,
            "MemFree": 16275512,
            "SwapTotal": 2000000,
            "SwapFree": 1000000,
            "HugePages_Total": 0,
            "HugePages_Free": 0
        }

        with mock.patch("builtins.open") as mock_open:
            pseudo_fd = mock.MagicMock()
            pseudo_fd.readlines = mock.MagicMock(return_value=proc_meminfo_lines)
            mock_open.return_value.__enter__.return_value = pseudo_fd
            read_meminfo_actual_return = SWAPAllocator.read_from_meminfo()
            assert read_meminfo_actual_return == read_meminfo_expected_return

    def test_setup_swapmem(self):
        with mock.patch("builtins.open") as mock_open, \
                mock.patch("os.posix_fallocate") as mock_fallocate, \
                mock.patch("os.chmod") as mock_chmod, \
                mock.patch("sonic_installer.main.run_command") as mock_run:
            pseudo_fd = mock.MagicMock()
            pseudo_fd_fileno = 10
            pseudo_fd.fileno.return_value = pseudo_fd_fileno
            mock_open.return_value.__enter__.return_value = pseudo_fd

            swap_mem_size_in_mib = 2048 * 1024
            expected_swap_mem_size_in_bytes = swap_mem_size_in_mib * 1024 * 1024
            expected_swapfile_location = SWAPAllocator.SWAP_FILE_PATH
            expected_swapfile_permission = 0o600
            swap_allocator = SWAPAllocator(allocate=True, swap_mem_size=swap_mem_size_in_mib)
            swap_allocator.setup_swapmem()

            mock_fallocate.assert_called_once_with(pseudo_fd_fileno, 0, expected_swap_mem_size_in_bytes)
            mock_chmod.assert_called_once_with(expected_swapfile_location, expected_swapfile_permission)
            mock_run.assert_has_calls([mock.call(['mkswap', expected_swapfile_location]), mock.call(['swapon', expected_swapfile_location])])

    def test_remove_swapmem(self):
        with mock.patch("subprocess.Popen") as mock_popen, \
                mock.patch("os.unlink") as mock_unlink:
            pseudo_subproc = mock.MagicMock()
            mock_popen.return_value = pseudo_subproc
            pseudo_subproc.communicate.return_value = ("swapoff: /home/swapfile: swapoff failed: No such file or directory", None)
            pseudo_subproc.returncode = 255

            swap_allocator = SWAPAllocator(allocate=True)
            try:
                swap_allocator.remove_swapmem()
            except Exception as detail:
                pytest.fail("SWAPAllocator.remove_swapmem should not raise exception %s" % repr(detail))

            expected_swapfile_location = SWAPAllocator.SWAP_FILE_PATH
            mock_popen.assert_called_once_with(['swapoff', expected_swapfile_location], stdout=subprocess.PIPE, text=True)
            mock_unlink.assert_called_once_with(SWAPAllocator.SWAP_FILE_PATH)

    def test_swap_allocator_initialization_default_args(self):
        expected_allocate = False
        expected_swap_mem_size = SWAPAllocator.SWAP_MEM_SIZE
        expected_total_mem_threshold = SWAPAllocator.TOTAL_MEM_THRESHOLD
        expected_available_mem_threshold = SWAPAllocator.AVAILABLE_MEM_THRESHOLD
        swap_allocator = SWAPAllocator(allocate=expected_allocate)
        assert swap_allocator.allocate is expected_allocate
        assert swap_allocator.swap_mem_size == expected_swap_mem_size
        assert swap_allocator.total_mem_threshold == expected_total_mem_threshold
        assert swap_allocator.available_mem_threshold == expected_available_mem_threshold
        assert swap_allocator.is_allocated is False

    def test_swap_allocator_initialization_custom_args(self):
        expected_allocate = True
        expected_swap_mem_size = 2048
        expected_total_mem_threshold = 4096
        expected_available_mem_threshold = 1024
        swap_allocator = SWAPAllocator(
            allocate=expected_allocate,
            swap_mem_size=expected_swap_mem_size,
            total_mem_threshold=expected_total_mem_threshold,
            available_mem_threshold=expected_available_mem_threshold
        )
        assert swap_allocator.allocate is expected_allocate
        assert swap_allocator.swap_mem_size == expected_swap_mem_size
        assert swap_allocator.total_mem_threshold == expected_total_mem_threshold
        assert swap_allocator.available_mem_threshold == expected_available_mem_threshold
        assert swap_allocator.is_allocated is False

    def test_swap_allocator_context_enter_allocate_true_insufficient_total_memory(self):
        with mock.patch("sonic_installer.main.SWAPAllocator.get_disk_freespace") as mock_disk_free, \
                mock.patch("sonic_installer.main.SWAPAllocator.read_from_meminfo") as mock_meminfo, \
                mock.patch("sonic_installer.main.SWAPAllocator.setup_swapmem") as mock_setup, \
                mock.patch("sonic_installer.main.SWAPAllocator.remove_swapmem") as mock_remove, \
                mock.patch("os.path.exists") as mock_exists:
            mock_disk_free.return_value = 10 * 1024 * 1024 * 1024
            mock_meminfo.return_value = {
                "MemTotal": 2000000,
                "MemAvailable": 1900000,
                "SwapTotal": 0,
                "SwapFree": 0,
            }
            mock_exists.return_value = False

            swap_allocator = SWAPAllocator(allocate=True)
            try:
                swap_allocator.__enter__()
            except Exception as detail:
                pytest.fail("SWAPAllocator context manager should not raise exception %s" % repr(detail))
            mock_setup.assert_called_once()
            mock_remove.assert_not_called()
            assert swap_allocator.is_allocated is True

    def test_swap_allocator_context_enter_allocate_true_insufficient_available_memory(self):
        with mock.patch("sonic_installer.main.SWAPAllocator.get_disk_freespace") as mock_disk_free, \
                mock.patch("sonic_installer.main.SWAPAllocator.read_from_meminfo") as mock_meminfo, \
                mock.patch("sonic_installer.main.SWAPAllocator.setup_swapmem") as mock_setup, \
                mock.patch("sonic_installer.main.SWAPAllocator.remove_swapmem") as mock_remove, \
                mock.patch("os.path.exists") as mock_exists:
            mock_disk_free.return_value = 10 * 1024 * 1024 * 1024
            mock_meminfo.return_value = {
                "MemTotal": 3000000,
                "MemAvailable": 1000000,
                "SwapTotal": 0,
                "SwapFree": 0,
            }
            mock_exists.return_value = False

            swap_allocator = SWAPAllocator(allocate=True)
            try:
                swap_allocator.__enter__()
            except Exception as detail:
                pytest.fail("SWAPAllocator context manager should not raise exception %s" % repr(detail))
            mock_setup.assert_called_once()
            mock_remove.assert_not_called()
            assert swap_allocator.is_allocated is True

    def test_swap_allocator_context_enter_allocate_true_insufficient_total_memory_plus_swap(self):
        with mock.patch("sonic_installer.main.SWAPAllocator.get_disk_freespace") as mock_disk_free, \
                mock.patch("sonic_installer.main.SWAPAllocator.read_from_meminfo") as mock_meminfo, \
                mock.patch("sonic_installer.main.SWAPAllocator.setup_swapmem") as mock_setup, \
                mock.patch("sonic_installer.main.SWAPAllocator.remove_swapmem") as mock_remove, \
                mock.patch("os.path.exists") as mock_exists:
            mock_disk_free.return_value = 10 * 1024 * 1024 * 1024
            mock_meminfo.return_value = {
                "MemTotal": 1000000,
                "MemAvailable": 900000,
                "SwapTotal": 1000000,
                "SwapFree": 1000000,
            }
            mock_exists.return_value = False

            swap_allocator = SWAPAllocator(allocate=True)
            try:
                swap_allocator.__enter__()
            except Exception as detail:
                pytest.fail("SWAPAllocator context manager should not raise exception %s" % repr(detail))
            mock_setup.assert_called_once()
            mock_remove.assert_not_called()
            assert swap_allocator.is_allocated is True

    def test_swap_allocator_context_enter_allocate_true_insufficient_available_memory_plus_swap(self):
        with mock.patch("sonic_installer.main.SWAPAllocator.get_disk_freespace") as mock_disk_free, \
                mock.patch("sonic_installer.main.SWAPAllocator.read_from_meminfo") as mock_meminfo, \
                mock.patch("sonic_installer.main.SWAPAllocator.setup_swapmem") as mock_setup, \
                mock.patch("sonic_installer.main.SWAPAllocator.remove_swapmem") as mock_remove, \
                mock.patch("os.path.exists") as mock_exists:
            mock_disk_free.return_value = 10 * 1024 * 1024 * 1024
            mock_meminfo.return_value = {
                "MemTotal": 2000000,
                "MemAvailable": 500000,
                "SwapTotal": 1000000,
                "SwapFree": 500000,
            }
            mock_exists.return_value = False

            swap_allocator = SWAPAllocator(allocate=True)
            try:
                swap_allocator.__enter__()
            except Exception as detail:
                pytest.fail("SWAPAllocator context manager should not raise exception %s" % repr(detail))
            mock_setup.assert_called_once()
            mock_remove.assert_not_called()
            assert swap_allocator.is_allocated is True

    def test_swap_allocator_context_enter_allocate_true_insufficient_disk_space(self):
        with mock.patch("sonic_installer.main.SWAPAllocator.get_disk_freespace") as mock_disk_free, \
                mock.patch("sonic_installer.main.SWAPAllocator.read_from_meminfo") as mock_meminfo, \
                mock.patch("sonic_installer.main.SWAPAllocator.setup_swapmem") as mock_setup, \
                mock.patch("sonic_installer.main.SWAPAllocator.remove_swapmem") as mock_remove, \
                mock.patch("os.path.exists") as mock_exists:
            mock_disk_free.return_value = 1 * 1024 * 1024 * 1024
            mock_meminfo.return_value = {
                "MemTotal": 32859496,
                "MemAvailable": 16275512,
                "SwapTotal": 0,
                "SwapFree": 0,
            }
            mock_exists.return_value = False

            swap_allocator = SWAPAllocator(allocate=True)
            try:
                swap_allocator.__enter__()
            except Exception as detail:
                pytest.fail("SWAPAllocator context manager should not raise exception %s" % repr(detail))
            mock_setup.assert_not_called()
            mock_remove.assert_not_called()
            assert swap_allocator.is_allocated is False

    def test_swap_allocator_context_enter_allocate_true_swapfile_present(self):
        with mock.patch("sonic_installer.main.SWAPAllocator.get_disk_freespace") as mock_disk_free, \
                mock.patch("sonic_installer.main.SWAPAllocator.read_from_meminfo") as mock_meminfo, \
                mock.patch("sonic_installer.main.SWAPAllocator.setup_swapmem") as mock_setup, \
                mock.patch("sonic_installer.main.SWAPAllocator.remove_swapmem") as mock_remove, \
                mock.patch("os.path.exists") as mock_exists:
            mock_disk_free.return_value = 10 * 1024 * 1024 * 1024
            mock_meminfo.return_value = {
                "MemTotal": 32859496,
                "MemAvailable": 1000000,
                "SwapTotal": 0,
                "SwapFree": 0,
            }
            mock_exists.return_value = True

            swap_allocator = SWAPAllocator(allocate=True)
            try:
                swap_allocator.__enter__()
            except Exception as detail:
                pytest.fail("SWAPAllocator context manager should not raise exception %s" % repr(detail))
            mock_setup.assert_called_once()
            mock_remove.assert_called_once()
            assert swap_allocator.is_allocated is True

    def test_swap_allocator_context_enter_setup_error(self):
        with mock.patch("sonic_installer.main.SWAPAllocator.get_disk_freespace") as mock_disk_free, \
                mock.patch("sonic_installer.main.SWAPAllocator.read_from_meminfo") as mock_meminfo, \
                mock.patch("sonic_installer.main.SWAPAllocator.setup_swapmem") as mock_setup, \
                mock.patch("sonic_installer.main.SWAPAllocator.remove_swapmem") as mock_remove, \
                mock.patch("os.path.exists") as mock_exists:
            mock_disk_free.return_value = 10 * 1024 * 1024 * 1024
            mock_meminfo.return_value = {
                "MemTotal": 32859496,
                "MemAvailable": 1000000,
                "SwapTotal": 0,
                "SwapFree": 0,
            }
            mock_exists.return_value = False
            expected_err_str = "Pseudo Error"
            mock_setup.side_effect = Exception(expected_err_str)

            swap_allocator = SWAPAllocator(allocate=True)
            try:
                swap_allocator.__enter__()
            except Exception as detail:
                assert expected_err_str in str(detail)
            mock_setup.assert_called_once()
            mock_remove.assert_called_once()
            assert swap_allocator.is_allocated is False

    def test_swap_allocator_context_enter_allocate_false(self):
        with mock.patch("sonic_installer.main.SWAPAllocator.get_disk_freespace") as mock_disk_free, \
                mock.patch("sonic_installer.main.SWAPAllocator.read_from_meminfo") as mock_meminfo, \
                mock.patch("sonic_installer.main.SWAPAllocator.setup_swapmem") as mock_setup, \
                mock.patch("sonic_installer.main.SWAPAllocator.remove_swapmem") as mock_remove, \
                mock.patch("os.path.exists") as mock_exists:
            mock_disk_free.return_value = 10 * 1024 * 1024 * 1024
            mock_meminfo.return_value = {
                "MemTotal": 32859496,
                "MemAvailable": 1000000,
                "SwapTotal": 0,
                "SwapFree": 0,
            }
            mock_exists.return_value = False

            swap_allocator = SWAPAllocator(allocate=False)
            try:
                swap_allocator.__enter__()
            except Exception as detail:
                pytest.fail("SWAPAllocator context manager should not raise exception %s" % repr(detail))
            mock_setup.assert_not_called()
            mock_remove.assert_not_called()
            assert swap_allocator.is_allocated is False

    def test_swap_allocator_context_exit_is_allocated_true(self):
        with mock.patch("sonic_installer.main.SWAPAllocator.remove_swapmem") as mock_remove:
            swap_allocator = SWAPAllocator(allocate=True)
            swap_allocator.is_allocated = True
            swap_allocator.__exit__(None, None, None)
            mock_remove.assert_called_once()

    def test_swap_allocator_context_exit_is_allocated_false(self):
        with mock.patch("sonic_installer.main.SWAPAllocator.remove_swapmem") as mock_remove:
            swap_allocator = SWAPAllocator(allocate=True)
            swap_allocator.is_allocated = False
            swap_allocator.__exit__(None, None, None)
            mock_remove.assert_not_called()

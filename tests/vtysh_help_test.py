import os
import sys
from click.testing import CliRunner
from unittest import mock

import show.main as show

from show.vtysh_helper import VtyshCommand

# Add test path
test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)


class TestVtyshHelpCommands:
    """Test VtyshCommand help functionality for vtysh-integrated commands.

       The test uses 'show ip route' as an example command, but all output is mocked
       and we're just testing internals. The coverage should apply to any command
       that uses the VtyshCommand class.
    """

    @classmethod
    def setup_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    @classmethod
    def teardown_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

    def teardown_method(self, method):
        VtyshCommand.get_vtysh_help.cache_clear()

    def test_vtysh_help_basic_functionality(self):
        """Test basic help output structure for VtyshCommand."""
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["ip"].commands["route"], ["--help"])

        assert result.exit_code == 0
        assert "Usage: show ip route" in result.output
        assert "Show IP (IPv4) routing table" in result.output
        assert "Options:" in result.output
        assert "--help" in result.output

    @mock.patch('show.vtysh_helper.subprocess.run')
    def test_vtysh_help_with_subcommands(self, mock_subprocess):
        """Test help output when vtysh subcommands exist."""
        mock_result = mock.Mock()
        mock_result.returncode = 0
        mock_result.stdout = """
  summary         Summary of all routes
  vrf             Specify the VRF
  A.B.C.D         Network in the IP routing table to display
"""
        mock_subprocess.return_value = mock_result

        runner = CliRunner()
        result = runner.invoke(show.cli.commands["ip"].commands["route"], ["--help"])

        assert result.exit_code == 0
        assert "Usage: show ip route [OPTIONS] COMMAND [ARGS]..." in result.output
        assert "Commands:" in result.output
        assert "summary" in result.output
        assert "Summary of all routes" in result.output
        assert "vrf" in result.output
        assert "Specify the VRF" in result.output
        assert "A.B.C.D" in result.output
        assert "Network in the IP routing table to display" in result.output

    @mock.patch('show.vtysh_helper.subprocess.run')
    def test_vtysh_help_without_subcommands(self, mock_subprocess):
        """Test help output when no vtysh subcommands exist."""
        mock_result = mock.Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""  # No subcommands available
        mock_subprocess.return_value = mock_result

        runner = CliRunner()
        result = runner.invoke(show.cli.commands["ip"].commands["route"], ["summary", "--help"])

        assert result.exit_code == 0
        assert "Usage: show ip route summary [OPTIONS]" in result.output
        assert "COMMAND [ARGS]" not in result.output
        assert "Commands:" not in result.output

    @mock.patch('show.vtysh_helper.subprocess.run')
    def test_nested_command_help(self, mock_subprocess):
        """Test help for nested commands shows correct usage and description."""
        # Mock vtysh response - need to handle multiple calls
        def subprocess_side_effect(*args, **kwargs):
            command = args[0]
            mock_result = mock.Mock()
            mock_result.returncode = 0

            if 'show ip route ?' in ' '.join(command):
                # Parent command help
                mock_result.stdout = """
  summary         Summary of all routes
  vrf             Specify the VRF
"""
            elif 'show ip route vrf ?' in ' '.join(command):
                # Nested command help
                mock_result.stdout = """
  NAME            VRF name
  all             All VRFs
"""
            else:
                mock_result.stdout = ""

            return mock_result

        mock_subprocess.side_effect = subprocess_side_effect

        runner = CliRunner()
        result = runner.invoke(show.cli.commands["ip"].commands["route"], ["vrf", "--help"])

        assert result.exit_code == 0
        assert "Usage: show ip route vrf" in result.output
        assert "Commands:" in result.output
        assert "NAME" in result.output
        assert "all" in result.output
        assert "Specify the VRF" in result.output  # Description from parent command
        assert "summary" not in result.output  # Not a subcommand of 'vrf'
        assert "Summary of all routes" not in result.output  # Not a subcommand of 'vrf'

    @mock.patch('show.vtysh_helper.subprocess.run')
    def test_basic_invalid_command_error_handling(self, mock_subprocess):
        """Test error handling for invalid commands."""
        def subprocess_side_effect(*args, **kwargs):
            command = args[0]
            mock_result = mock.Mock()
            mock_result.returncode = 0

            if 'invalid' in ' '.join(command):
                mock_result.stdout = "% There is no matched command."
            else:
                mock_result.stdout = """
  summary         Summary of all routes
  vrf             Specify the VRF
"""
            return mock_result

        mock_subprocess.side_effect = subprocess_side_effect

        runner = CliRunner()
        result = runner.invoke(show.cli.commands["ip"].commands["route"], ["invalid", "--help"])

        assert result.exit_code == 0
        assert "Usage: show ip route [OPTIONS] COMMAND [ARGS]..." in result.output
        assert "Error:" in result.output
        assert 'No such command "invalid"' in result.output
        assert 'Try "show ip route -h" for help' in result.output
        assert "Commands:" not in result.output
        assert "summary" not in result.output
        assert "vrf" not in result.output

    @mock.patch('show.vtysh_helper.subprocess.run')
    def test_nested_invalid_command_error_handling(self, mock_subprocess):
        """Test that error usage line shows the last valid command, not the failing one."""
        def subprocess_side_effect(*args, **kwargs):
            command = args[0]
            command_str = ' '.join(command)
            mock_result = mock.Mock()
            mock_result.returncode = 0

            if 'show ip route ?' in command_str:
                mock_result.stdout = """
  summary         Summary of all routes
  vrf             Specify the VRF
"""
            elif 'show ip route vrf ?' in command_str:
                mock_result.stdout = """
  NAME            VRF name
  all             All VRFs
"""
            elif 'invalid' in command_str:
                mock_result.stdout = "% There is no matched command."
            else:
                mock_result.stdout = ""

            return mock_result

        mock_subprocess.side_effect = subprocess_side_effect

        runner = CliRunner()
        result = runner.invoke(show.cli.commands["ip"].commands["route"], ["vrf", "invalid", "--help"])

        assert result.exit_code == 0
        assert "Usage: show ip route vrf [OPTIONS] COMMAND [ARGS]..." in result.output
        assert 'No such command "invalid"' in result.output
        assert 'Try "show ip route vrf -h" for help' in result.output
        assert "Commands:" not in result.output
        assert "summary" not in result.output
        assert "all" not in result.output

    @mock.patch('show.vtysh_helper.subprocess.run')
    def test_vtysh_caching_functionality(self, mock_subprocess):
        """Test that vtysh calls are cached to avoid repeated calls."""
        mock_result = mock.Mock()
        mock_result.returncode = 0
        mock_result.stdout = """
  summary         Summary of all routes
  vrf             Specify the VRF
"""
        mock_subprocess.return_value = mock_result

        runner = CliRunner()
        # First call
        result1 = runner.invoke(show.cli.commands["ip"].commands["route"], ["--help"])
        # Second call (should use cache)
        result2 = runner.invoke(show.cli.commands["ip"].commands["route"], ["--help"])

        assert result1.exit_code == 0
        assert result2.exit_code == 0
        # Should have been called only once due to caching
        assert mock_subprocess.call_count == 1


class TestVtyshCompletionCommands:
    """Test VtyshCommand completion functionality for vtysh-integrated commands."""

    @classmethod
    def setup_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    @classmethod
    def teardown_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

    def teardown_method(self, method):
        VtyshCommand.get_vtysh_help.cache_clear()

    @mock.patch('show.vtysh_helper.subprocess.run')
    def test_basic_completion_functionality(self, mock_subprocess):
        """Test basic completion returns available subcommands."""
        mock_result = mock.Mock()
        mock_result.returncode = 0
        mock_result.stdout = """
  summary         Summary of all routes
  vrf             Specify the VRF
  A.B.C.D         Network in the IP routing table to display
  json            JavaScript Object Notation
  (1-100)         Number of entries to display
"""
        mock_subprocess.return_value = mock_result

        route_cmd = show.cli.commands["ip"].commands["route"]
        completions = route_cmd.get_vtysh_completions("show ip route")

        assert "summary" in completions
        assert "vrf" in completions
        assert "json" in completions
        assert "A.B.C.D" not in completions
        assert "(1-100)" not in completions
        assert len(completions) == 3

    @mock.patch('show.vtysh_helper.subprocess.run')
    def test_nested_completion_functionality(self, mock_subprocess):
        """Test completion for nested commands."""
        mock_result = mock.Mock()
        mock_result.returncode = 0
        mock_result.stdout = """
  NAME            VRF name
  all             All VRFs
  default         Default VRF
"""
        mock_subprocess.return_value = mock_result

        route_cmd = show.cli.commands["ip"].commands["route"]
        completions = route_cmd.get_vtysh_completions("show ip route vrf")

        assert "NAME" not in completions
        assert "all" in completions
        assert "default" in completions
        assert len(completions) == 2

    @mock.patch('show.vtysh_helper.subprocess.run')
    def test_completion_with_no_results(self, mock_subprocess):
        """Test completion when no subcommands are available."""
        mock_result = mock.Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_subprocess.return_value = mock_result

        route_cmd = show.cli.commands["ip"].commands["route"]
        completions = route_cmd.get_vtysh_completions("show ip route summary")

        assert completions == []

    @mock.patch('show.vtysh_helper.subprocess.run')
    def test_completion_with_vtysh_error(self, mock_subprocess):
        """Test completion when vtysh returns an error."""
        mock_result = mock.Mock()
        mock_result.returncode = 1
        mock_result.stdout = "% There is no matched command."
        mock_result.stderr = "Error: command not found"
        mock_subprocess.return_value = mock_result

        route_cmd = show.cli.commands["ip"].commands["route"]
        completions = route_cmd.get_vtysh_completions("show ip route invalid")

        assert completions == []

    @mock.patch('show.vtysh_helper.subprocess.run')
    def test_completion_with_whitespace_handling(self, mock_subprocess):
        """Test completion parsing handles whitespace correctly."""
        mock_result = mock.Mock()
        mock_result.returncode = 0
        mock_result.stdout = """

  summary         Summary of all routes

  vrf             Specify the VRF
  json            JavaScript Object Notation

"""
        mock_subprocess.return_value = mock_result

        route_cmd = show.cli.commands["ip"].commands["route"]
        completions = route_cmd.get_vtysh_completions("show ip route")

        assert "summary" in completions
        assert "vrf" in completions
        assert "json" in completions
        assert len(completions) == 3
        # Should not include empty strings
        assert "" not in completions

    @mock.patch('show.vtysh_helper.subprocess.run')
    def test_nested_command_help_with_completion(self, mock_subprocess):
        """Test help for nested commands shows correct usage and description, with completion."""
        # Mock vtysh response - need to handle multiple calls
        def subprocess_side_effect(*args, **kwargs):
            command = args[0]
            mock_result = mock.Mock()
            mock_result.returncode = 0

            if 'show ip route summ?' in ' '.join(command) or 'show ip route ?' in ' '.join(command):
                # Completion command help
                mock_result.stdout = """
  summary         Summary of all routes
"""
            elif 'show ip route summary ?' in ' '.join(command):
                # Parent command help
                mock_result.stdout = """
  vrf             Specify the VRF
"""
            else:
                mock_result.stdout = ""

            return mock_result

        mock_subprocess.side_effect = subprocess_side_effect

        runner = CliRunner()
        result = runner.invoke(show.cli.commands["ip"].commands["route"], ["summ", "--help"])

        assert result.exit_code == 0
        assert "Usage: show ip route summary" in result.output
        assert "Summary of all routes" in result.output
        assert "Commands:" in result.output
        assert "vrf" in result.output
        assert "Specify the VRF" in result.output

    @mock.patch('show.vtysh_helper.subprocess.run')
    def test_nested_command_help_with_inline_completion(self, mock_subprocess):
        """Test help for nested commands shows correct usage and description, with inline completion."""
        # Mock vtysh response - need to handle multiple calls
        def subprocess_side_effect(*args, **kwargs):
            command = args[0]
            mock_result = mock.Mock()
            mock_result.returncode = 0

            if 'show ip route summ?' in ' '.join(command) or 'show ip route ?' in ' '.join(command):
                # Completion command help
                mock_result.stdout = """
  summary         Summary of all routes
"""
            elif 'show ip route summary ?' in ' '.join(command):
                # Parent command help
                mock_result.stdout = """
  vrf             Specify the VRF
"""
            elif 'show ip route summary vrf ?' in ' '.join(command):
                # Nested command help
                mock_result.stdout = """
  NAME            VRF name
  all             All VRFs
"""
            else:
                mock_result.stdout = ""

            return mock_result

        mock_subprocess.side_effect = subprocess_side_effect

        runner = CliRunner()
        result = runner.invoke(show.cli.commands["ip"].commands["route"], ["summ", "vrf", "--help"])

        assert result.exit_code == 0
        assert "Usage: show ip route summary vrf" in result.output
        assert "Commands:" in result.output
        assert "NAME" in result.output
        assert "Specify the VRF" in result.output
        assert "all" in result.output
        assert "All VRFs" in result.output
        assert "Summary of all routes" not in result.output

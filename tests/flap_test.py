import os
import importlib

from click.testing import CliRunner

import show.main as show

intf_flap_masic_expected_output_default = """\
Interface    Flap Count    Admin    Oper     Link Down TimeStamp(UTC)    Link Up TimeStamp(UTC)
-----------  ------------  -------  -------  --------------------------  ------------------------
Ethernet0    5             Up       Up       Sat Jan 17 00:04:42 2025    Sat Jan 18 00:08:42 2025
Ethernet4    Never         Up       Up       Never                       Never
Ethernet16   Never         Unknown  Unknown  Never                       Never
Ethernet20   Never         Unknown  Unknown  Never                       Never
"""

# Display all: all namespaces (asic0 + asic1) including backplane ports
intf_flap_masic_expected_output_display_all = """\
Interface       Flap Count    Admin    Oper     Link Down TimeStamp(UTC)    Link Up TimeStamp(UTC)
--------------  ------------  -------  -------  --------------------------  ------------------------
Ethernet0       5             Up       Up       Sat Jan 17 00:04:42 2025    Sat Jan 18 00:08:42 2025
Ethernet4       Never         Up       Up       Never                       Never
Ethernet16      Never         Unknown  Unknown  Never                       Never
Ethernet20      Never         Unknown  Unknown  Never                       Never
Ethernet64      2             Up       Up       Thu Feb 12 23:03:40 2026    Thu Feb 12 23:25:31 2026
Ethernet-BP0    Never         Up       Up       Never                       Never
Ethernet-BP4    Never         Up       Up       Never                       Never
Ethernet-BP256  Never         Up       Up       Never                       Never
Ethernet-BP260  Never         Up       Up       Never                       Never
"""

intf_flap_masic_expected_output_ethernet0 = """\
Interface      Flap Count  Admin    Oper    Link Down TimeStamp(UTC)    Link Up TimeStamp(UTC)
-----------  ------------  -------  ------  --------------------------  ------------------------
Ethernet0               5  Up       Up      Sat Jan 17 00:04:42 2025    Sat Jan 18 00:08:42 2025
"""

intf_flap_masic_expected_output_ethernet64 = """\
Interface      Flap Count  Admin    Oper    Link Down TimeStamp(UTC)    Link Up TimeStamp(UTC)
-----------  ------------  -------  ------  --------------------------  ------------------------
Ethernet64              2  Up       Up      Thu Feb 12 23:03:40 2026    Thu Feb 12 23:25:31 2026
"""


class TestInterfacesFlapMasic(object):
    """Test cases for 'show interfaces flap' on multi-ASIC platforms."""

    @classmethod
    def setup_class(cls):
        print("SETUP")
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        from .mock_tables import dbconnector
        dbconnector.load_namespace_config()

    def test_show_interfaces_flap_masic_default(self):
        """Test frontend display shows only front-panel namespace ports."""
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["flap"],
            ["-d", "frontend"])
        assert result.exit_code == 0
        assert result.output == intf_flap_masic_expected_output_default

    def test_show_interfaces_flap_masic_display_all(self):
        """Test -d all shows all namespaces including backplane ports."""
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["flap"],
            ["-d", "all"])
        assert result.exit_code == 0
        assert result.output == intf_flap_masic_expected_output_display_all

    def test_show_interfaces_flap_masic_ethernet0(self):
        """Test specific port lookup on asic0 returns correct flap data."""
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["flap"],
            ["Ethernet0"])
        assert result.exit_code == 0
        assert result.output == intf_flap_masic_expected_output_ethernet0

    def test_show_interfaces_flap_masic_ethernet64(self):
        """Test specific port lookup on asic1 returns correct flap data."""
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["flap"],
            ["Ethernet64"])
        assert result.exit_code == 0
        assert result.output == intf_flap_masic_expected_output_ethernet64

    def test_show_interfaces_flap_masic_invalid_interface(self):
        """Test invalid interface name fails."""
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["interfaces"].commands["flap"],
            ["Ethernet100"])
        assert result.exit_code != 0
        assert "Invalid interface name" in result.output

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        from .mock_tables import dbconnector
        dbconnector.load_database_config()

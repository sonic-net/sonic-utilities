import sys
import os
import traceback

from unittest import mock
from unittest.mock import patch
from click.testing import CliRunner

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

import clear.main as clear
import show.main as show
from .mock_tables import dbconnector

show_vxlan_counters_output = """\
  IFACE    RX_PKTS    RX_BYTES      RX_PPS    TX_PKTS    TX_BYTES    TX_PPS
-------  ---------  ----------  ----------  ---------  ----------  --------
  vtep1        452       81922  20523.00/s        154       23434  201.00/s
"""

show_vxlan_counters_clear_output = """\
  IFACE    RX_PKTS    RX_BYTES      RX_PPS    TX_PKTS    TX_BYTES    TX_PPS
-------  ---------  ----------  ----------  ---------  ----------  --------
  vtep1          0           0  20523.00/s          0           0  201.00/s
"""

show_vxlan_counters_interface_output = """\
vtep1
-----

        RX:
               452 packets
             81922 bytes
        TX:
               154 packets
             23434 bytes
"""

show_vxlan_counters_clear_interface_output = """\
vtep1
-----

        RX:
                 0 packets
                 0 bytes
        TX:
                 0 packets
                 0 bytes
"""


class TestTunnelstat(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")

    def test_no_param(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vxlan"].commands["counters"], [])
        print(result.exit_code)
        print(result.output)
        traceback.print_tb(result.exc_info[2])
        assert result.exit_code == 0
        assert result.output == show_vxlan_counters_output

    def test_single_tunnel(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vxlan"].commands["counters"], ["vtep1"])
        expected = show_vxlan_counters_interface_output
        assert result.output == expected

    def test_clear(self):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands["tunnelcounters"], [])
        print(result.stdout)
        assert result.exit_code == 0
        result = runner.invoke(show.cli.commands["vxlan"].commands["counters"], [])
        print(result.stdout)
        expected = show_vxlan_counters_clear_output

        # remove the counters snapshot
        show.run_command(['tunnelstat', '-D'])
        for line in expected:
            assert line in result.output

    def test_clear_interface(self):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands["tunnelcounters"], [])
        print(result.stdout)
        assert result.exit_code == 0
        result = runner.invoke(show.cli.commands["vxlan"].commands["counters"], ["vtep1"])
        print(result.stdout)
        expected = show_vxlan_counters_clear_interface_output

        # remove the counters snapshot
        show.run_command(['tunnelstat', '-D'])
        for line in expected:
            assert line in result.output

    def test_show_tunnel_counters(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["tunnel"].commands["counters"], [])
        print(result.output)
        assert result.exit_code == 0
        # the unfiltered view carries a TYPE column that labels each tunnel's type
        assert 'TYPE' in result.output
        # all tunnel types are listed: the vxlan tunnel and the ipinip decap tunnel
        assert 'vtep1' in result.output
        assert 'vxlan' in result.output
        assert 'IPINIP_TUNNEL' in result.output
        assert 'ipinip' in result.output

    def test_show_tunnel_counters_type_ipinip(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["tunnel"].commands["counters"], ["--type", "ipinip"])
        print(result.output)
        assert result.exit_code == 0
        # a type-filtered view is single-type, so no TYPE column is added
        assert 'TYPE' not in result.output
        # only the ipinip decap tunnel is shown; the vxlan tunnel is filtered out
        assert 'IPINIP_TUNNEL' in result.output
        assert 'vtep1' not in result.output

    def test_show_tunnel_counters_single(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["tunnel"].commands["counters"], ["IPINIP_TUNNEL"])
        print(result.output)
        assert result.exit_code == 0
        assert 'IPINIP_TUNNEL' in result.output
        assert '226 packets' in result.output

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")


class TestTunnelstatMultiAsic(object):
    """Multi-asic behavior of 'show tunnel counters': tunnelstat is run once per
    namespace (wrapped in 'ip netns exec'), and a named tunnel is restricted to
    the namespaces where it is present."""

    @staticmethod
    def _cmds(mock_run):
        return [call.args[0] for call in mock_run.call_args_list]

    @staticmethod
    def _conn_factory(tunnels_by_ns):
        def factory(*args, **kwargs):
            inst = mock.MagicMock()
            inst.COUNTERS_DB = "COUNTERS_DB"
            inst.get_all.return_value = tunnels_by_ns.get(kwargs.get("namespace"), {})
            return inst
        return factory

    @patch("show.tunnel.clicommon.run_command")
    @patch("show.tunnel.SonicV2Connector")
    @patch("show.tunnel.multi_asic_util.multi_asic_get_ns_list",
           mock.Mock(return_value=["asic0", "asic1"]))
    @patch("show.tunnel.multi_asic_util.get_namespace_from_ctx",
           mock.Mock(return_value=None))
    @patch("show.tunnel.multi_asic.is_multi_asic", mock.Mock(return_value=True))
    def test_multi_asic_counters_run_in_each_namespace(self, mock_conn, mock_run):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["tunnel"].commands["counters"], [])
        assert result.exit_code == 0
        cmds = self._cmds(mock_run)
        # tunnelstat is run once per namespace, wrapped in 'ip netns exec'
        assert ["sudo", "ip", "netns", "exec", "asic0", "tunnelstat"] in cmds
        assert ["sudo", "ip", "netns", "exec", "asic1", "tunnelstat"] in cmds
        assert len(cmds) == 2

    @patch("show.tunnel.clicommon.run_command")
    @patch("show.tunnel.SonicV2Connector")
    @patch("show.tunnel.multi_asic_util.multi_asic_get_ns_list",
           mock.Mock(return_value=["asic0", "asic1"]))
    @patch("show.tunnel.multi_asic_util.get_namespace_from_ctx",
           mock.Mock(return_value=None))
    @patch("show.tunnel.multi_asic.is_multi_asic", mock.Mock(return_value=True))
    def test_multi_asic_named_tunnel_restricted_to_its_namespace(self, mock_conn, mock_run):
        # IPINIP_TUNNEL is present only in asic1
        mock_conn.side_effect = self._conn_factory(
            {"asic0": {}, "asic1": {"IPINIP_TUNNEL": "oid:0x2a0000000035f"}})
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["tunnel"].commands["counters"],
                               ["IPINIP_TUNNEL"])
        assert result.exit_code == 0
        # only asic1 (which has the tunnel) is queried
        assert self._cmds(mock_run) == [["sudo", "ip", "netns", "exec", "asic1",
                                         "tunnelstat", "-i", "IPINIP_TUNNEL"]]

    @patch("show.tunnel.clicommon.run_command")
    @patch("show.tunnel.SonicV2Connector")
    @patch("show.tunnel.multi_asic_util.multi_asic_get_ns_list",
           mock.Mock(return_value=["asic0", "asic1"]))
    @patch("show.tunnel.multi_asic_util.get_namespace_from_ctx",
           mock.Mock(return_value=None))
    @patch("show.tunnel.multi_asic.is_multi_asic", mock.Mock(return_value=True))
    def test_multi_asic_named_tunnel_absent_everywhere(self, mock_conn, mock_run):
        mock_conn.side_effect = self._conn_factory(
            {"asic0": {}, "asic1": {"IPINIP_TUNNEL": "oid:0x2a0000000035f"}})
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["tunnel"].commands["counters"],
                               ["NONEXISTENT"])
        assert result.exit_code == 0
        assert "Tunnel NONEXISTENT not found" in result.output
        # no tunnelstat is run when the tunnel is in no namespace
        assert mock_run.call_count == 0

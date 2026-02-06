import os
import sys
from importlib import reload

from click.testing import CliRunner

import show.main
import show.vnet
import config.main
import utilities_common.multi_asic
from utilities_common.db import Db

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)


class TestMultiAsicVnet:
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"

        from mock_tables import mock_multi_asic
        reload(mock_multi_asic)
        from mock_tables import dbconnector
        dbconnector.load_namespace_config()

        reload(utilities_common.multi_asic)
        reload(show.vnet)
        reload(show.main)
        reload(config.main)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        from mock_tables import mock_single_asic
        reload(mock_single_asic)
        from mock_tables import dbconnector
        dbconnector.load_database_config()

        os.environ["PATH"] = os.pathsep.join(
            os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""

        reload(utilities_common.multi_asic)
        reload(show.vnet)
        reload(show.main)
        reload(config.main)

    # ----------------------------------------------------------------
    # show vnet brief
    # ----------------------------------------------------------------
    def test_show_vnet_brief_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["brief"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        # Should contain VNET entries from both asic0 and asic1
        assert "Vnet_2000" in result.output
        assert "Vnet_3000" in result.output
        assert "Vnet_4000" in result.output

    def test_show_vnet_brief_specific_namespace(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["-n", "asic0", "brief"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert "Vnet_2000" in result.output
        assert "Vnet_3000" in result.output
        # asic1's VNET should not appear
        assert "Vnet_4000" not in result.output

    # ----------------------------------------------------------------
    # show vnet name
    # ----------------------------------------------------------------
    def test_show_vnet_name_found_in_asic0(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["name", "Vnet_2000"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert "Vnet_2000" in result.output
        assert "vtep1" in result.output

    def test_show_vnet_name_found_in_asic1(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["name", "Vnet_4000"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert "Vnet_4000" in result.output

    def test_show_vnet_name_not_found(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["name", "Vnet_9999"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert "not found" in result.output

    def test_show_vnet_name_specific_namespace(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["-n", "asic0", "name", "Vnet_2000"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert "Vnet_2000" in result.output

    # ----------------------------------------------------------------
    # show vnet guid
    # ----------------------------------------------------------------
    def test_show_vnet_guid_found(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["guid", "guid-2000-asic0"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert "Vnet_2000" in result.output

    def test_show_vnet_guid_found_in_asic1(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["guid", "guid-4000-asic1"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert "Vnet_4000" in result.output

    def test_show_vnet_guid_not_found(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["guid", "nonexistent-guid"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert "No VNET found" in result.output

    # ----------------------------------------------------------------
    # show vnet alias
    # ----------------------------------------------------------------
    def test_show_vnet_alias_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["alias"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert "guid-2000-asic0" in result.output
        assert "guid-4000-asic1" in result.output

    def test_show_vnet_alias_specific(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["alias", "guid-2000-asic0"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert "Vnet_2000" in result.output

    # ----------------------------------------------------------------
    # show vnet interfaces
    # ----------------------------------------------------------------
    def test_show_vnet_interfaces_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["interfaces"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        # Vnet_2000 has Ethernet0 (asic0)
        assert "Vnet_2000" in result.output
        # Vnet_3000 has Ethernet4 (asic0)
        assert "Vnet_3000" in result.output
        # Vnet_4000 has Ethernet64 (asic1)
        assert "Vnet_4000" in result.output

    def test_show_vnet_interfaces_specific_namespace(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["-n", "asic1", "interfaces"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert "Vnet_4000" in result.output
        # asic0 VNETs should not appear
        assert "Vnet_2000" not in result.output
        assert "Vnet_3000" not in result.output

    # ----------------------------------------------------------------
    # show vnet neighbors
    # ----------------------------------------------------------------
    def test_show_vnet_neighbors_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["neighbors"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0

    def test_show_vnet_neighbors_specific_namespace(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["-n", "asic0", "neighbors"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0

    # ----------------------------------------------------------------
    # show vnet routes all
    # ----------------------------------------------------------------
    def test_show_vnet_routes_all_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["routes", "all"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        # Regular routes from both namespaces
        assert "Vnet_2000" in result.output
        assert "Vnet_4000" in result.output
        # Tunnel routes
        assert "192.168.1.200" in result.output
        assert "192.168.2.200" in result.output

    def test_show_vnet_routes_all_specific_namespace(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["-n", "asic0", "routes", "all"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert "Vnet_2000" in result.output
        # asic1 data should not appear
        assert "192.168.2.200" not in result.output

    # ----------------------------------------------------------------
    # show vnet routes tunnel
    # ----------------------------------------------------------------
    def test_show_vnet_routes_tunnel_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["routes", "tunnel"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        # Tunnel routes from asic0
        assert "Vnet_2000" in result.output
        assert "192.168.1.200" in result.output
        # Tunnel routes from asic1
        assert "Vnet_4000" in result.output
        assert "192.168.2.200" in result.output

    def test_show_vnet_routes_tunnel_specific_namespace(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["-n", "asic1", "routes", "tunnel"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert "Vnet_4000" in result.output
        assert "192.168.2.200" in result.output
        # asic0 data should not appear
        assert "192.168.1.200" not in result.output

    # ----------------------------------------------------------------
    # show vnet endpoint
    # ----------------------------------------------------------------
    def test_show_vnet_endpoint_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["endpoint"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0

    # ----------------------------------------------------------------
    # show vnet - invalid namespace
    # ----------------------------------------------------------------
    def test_show_vnet_brief_invalid_namespace(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["-n", "invalid_ns", "brief"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code != 0

    # ----------------------------------------------------------------
    # config vnet add/del - requires namespace in multi-ASIC
    # ----------------------------------------------------------------
    def test_config_vnet_add_requires_namespace(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(
            config.main.config.commands["vnet"],
            ["add", "Vnet_Test", "999", "vtep1"],
            obj=db
        )
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        # Should fail because --namespace is required in multi-ASIC
        assert result.exit_code != 0
        assert "namespace" in result.output.lower() or "required" in result.output.lower()

    def test_config_vnet_del_requires_namespace(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(
            config.main.config.commands["vnet"],
            ["del", "Vnet_Test"],
            obj=db
        )
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code != 0
        assert "namespace" in result.output.lower() or "required" in result.output.lower()

    def test_config_vnet_add_route_requires_namespace(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(
            config.main.config.commands["vnet"],
            ["add-route", "Vnet_Test", "10.0.0.0/24", "10.10.10.1"],
            obj=db
        )
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code != 0
        assert "namespace" in result.output.lower() or "required" in result.output.lower()

    def test_config_vnet_del_route_requires_namespace(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(
            config.main.config.commands["vnet"],
            ["del-route", "Vnet_Test", "10.0.0.0/24"],
            obj=db
        )
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code != 0
        assert "namespace" in result.output.lower() or "required" in result.output.lower()

    # ----------------------------------------------------------------
    # config vnet add/del with namespace
    # ----------------------------------------------------------------
    def test_config_vnet_add_del_with_namespace(self):
        runner = CliRunner()
        db = Db()

        # First set up a vxlan tunnel in asic0's config DB
        db.cfgdb_clients["asic0"].set_entry("VXLAN_TUNNEL", "vtep1", {"src_ip": "10.10.10.1"})

        # Add a VNET to asic0
        result = runner.invoke(
            config.main.config.commands["vnet"],
            ["-n", "asic0", "add", "Vnet_Test", "999", "vtep1"],
            obj=db
        )
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert "added/updated" in result.output
        assert "Vnet_Test" in db.cfgdb_clients["asic0"].get_table("VNET")

        # Delete the VNET from asic0
        result = runner.invoke(
            config.main.config.commands["vnet"],
            ["-n", "asic0", "del", "Vnet_Test"],
            obj=db
        )
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert "deleted" in result.output
        assert "Vnet_Test" not in db.cfgdb_clients["asic0"].get_table("VNET")

    def test_config_vnet_add_del_route_with_namespace(self):
        runner = CliRunner()
        db = Db()

        # Set up prerequisites in asic0
        db.cfgdb_clients["asic0"].set_entry("VXLAN_TUNNEL", "vtep1", {"src_ip": "10.10.10.1"})

        # Add a VNET
        result = runner.invoke(
            config.main.config.commands["vnet"],
            ["-n", "asic0", "add", "Vnet_RT", "800", "vtep1"],
            obj=db
        )
        assert result.exit_code == 0
        assert "Vnet_RT" in db.cfgdb_clients["asic0"].get_table("VNET")

        # Add a route
        result = runner.invoke(
            config.main.config.commands["vnet"],
            ["-n", "asic0", "add-route", "Vnet_RT", "10.10.10.0/24", "192.168.1.1"],
            obj=db
        )
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert "added/updated" in result.output

        # Verify route exists
        vnet_route_tunnel = db.cfgdb_clients["asic0"].get_table("VNET_ROUTE_TUNNEL")
        assert ("Vnet_RT", "10.10.10.0/24") in vnet_route_tunnel

        # Delete the specific route
        result = runner.invoke(
            config.main.config.commands["vnet"],
            ["-n", "asic0", "del-route", "Vnet_RT", "10.10.10.0/24"],
            obj=db
        )
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert "Specific route deleted" in result.output

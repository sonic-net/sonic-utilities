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

show_vnet_brief_multi_asic_output = """\

Namespace: asic0
vnet name    vxlan tunnel      vni  peer list    guid
-----------  --------------  -----  -----------  ---------------
Vnet_2000    vtep1            5000               guid-2000-asic0
Vnet_3000    vtep1            6000               guid-3000-asic0

Namespace: asic1
vnet name    vxlan tunnel      vni  peer list    guid
-----------  --------------  -----  -----------  ---------------
Vnet_4000    vtep1            4000               guid-4000-asic1
"""

show_vnet_brief_asic0_output = """\
vnet name    vxlan tunnel      vni  peer list    guid
-----------  --------------  -----  -----------  ---------------
Vnet_2000    vtep1            5000               guid-2000-asic0
Vnet_3000    vtep1            6000               guid-3000-asic0
"""

show_vnet_name_vnet2000_output = """\

Namespace: asic0
vnet name    vxlan tunnel      vni  peer list    guid             interfaces
-----------  --------------  -----  -----------  ---------------  ------------
Vnet_2000    vtep1            5000               guid-2000-asic0  Ethernet16
"""

show_vnet_name_vnet4000_output = """\

Namespace: asic1
vnet name    vxlan tunnel      vni  peer list    guid             interfaces
-----------  --------------  -----  -----------  ---------------  ------------
Vnet_4000    vtep1            4000               guid-4000-asic1  Ethernet64
"""

show_vnet_name_not_found_output = """\
VNET 'Vnet_9999' not found!
"""

show_vnet_name_vnet2000_specific_ns_output = """\
vnet name    vxlan tunnel      vni  peer list    guid             interfaces
-----------  --------------  -----  -----------  ---------------  ------------
Vnet_2000    vtep1            5000               guid-2000-asic0  Ethernet16
"""

show_vnet_guid_vnet2000_output = """\

Namespace: asic0
vnet name    vxlan tunnel      vni  peer list    guid             interfaces
-----------  --------------  -----  -----------  ---------------  ------------
Vnet_2000    vtep1            5000               guid-2000-asic0  Ethernet16
"""

show_vnet_guid_vnet4000_output = """\

Namespace: asic1
vnet name    vxlan tunnel      vni  peer list    guid             interfaces
-----------  --------------  -----  -----------  ---------------  ------------
Vnet_4000    vtep1            4000               guid-4000-asic1  Ethernet64
"""

show_vnet_guid_not_found_output = """\
No VNET found with GUID 'nonexistent-guid'
"""

show_vnet_alias_multi_asic_output = """\

Namespace: asic0
Alias            Name
---------------  ---------
guid-2000-asic0  Vnet_2000
guid-3000-asic0  Vnet_3000

Namespace: asic1
Alias            Name
---------------  ---------
guid-4000-asic1  Vnet_4000
"""

show_vnet_alias_specific_output = """\

Namespace: asic0
Alias            Name
---------------  ---------
guid-2000-asic0  Vnet_2000
"""

show_vnet_interfaces_multi_asic_output = """\

Namespace: asic0
vnet name    interfaces
-----------  ------------
Vnet_2000    Ethernet16
Vnet_3000    Ethernet20

Namespace: asic1
vnet name    interfaces
-----------  ------------
Vnet_4000    Ethernet64
"""

show_vnet_interfaces_asic1_output = """\
vnet name    interfaces
-----------  ------------
Vnet_4000    Ethernet64
"""

show_vnet_neighbors_multi_asic_output = """\

Namespace: asic0
Vnet_2000    neighbor    mac_address        interfaces
-----------  ----------  -----------------  ------------
             10.0.0.1    00:11:22:33:44:aa  Ethernet16

Vnet_3000    neighbor    mac_address        interfaces
-----------  ----------  -----------------  ------------
             10.0.1.1    00:11:22:33:44:bb  Ethernet20


Namespace: asic1
Vnet_4000    neighbor    mac_address        interfaces
-----------  ----------  -----------------  ------------
             10.0.2.1    00:11:22:33:44:cc  Ethernet64

"""

show_vnet_neighbors_asic0_output = """\
Vnet_2000    neighbor    mac_address        interfaces
-----------  ----------  -----------------  ------------
             10.0.0.1    00:11:22:33:44:aa  Ethernet16

Vnet_3000    neighbor    mac_address        interfaces
-----------  ----------  -----------------  ------------
             10.0.1.1    00:11:22:33:44:bb  Ethernet20

"""

show_vnet_routes_all_multi_asic_output = """\

Namespace: asic0
vnet name    prefix       nexthop       interface
-----------  -----------  ------------  -----------
Vnet_2000    10.0.0.0/24  10.10.10.100  Ethernet16

vnet name    prefix       endpoint       mac address          vni
-----------  -----------  -------------  -----------------  -----
Vnet_2000    20.0.0.0/24  192.168.1.200  00:aa:bb:cc:dd:01   5000
Vnet_3000    30.0.0.0/24  192.168.1.201                      6000

Namespace: asic1
vnet name    prefix       nexthop       interface
-----------  -----------  ------------  -----------
Vnet_4000    40.0.0.0/24  10.10.10.200  Ethernet64

vnet name    prefix       endpoint       mac address          vni
-----------  -----------  -------------  -----------------  -----
Vnet_4000    50.0.0.0/24  192.168.2.200  00:aa:bb:cc:dd:02   4000
"""

show_vnet_routes_all_asic0_output = """\
vnet name    prefix       nexthop       interface
-----------  -----------  ------------  -----------
Vnet_2000    10.0.0.0/24  10.10.10.100  Ethernet16

vnet name    prefix       endpoint       mac address          vni
-----------  -----------  -------------  -----------------  -----
Vnet_2000    20.0.0.0/24  192.168.1.200  00:aa:bb:cc:dd:01   5000
Vnet_3000    30.0.0.0/24  192.168.1.201                      6000
"""

show_vnet_routes_tunnel_multi_asic_output = """\

Namespace: asic0
vnet name    prefix       endpoint       mac address          vni
-----------  -----------  -------------  -----------------  -----
Vnet_2000    20.0.0.0/24  192.168.1.200  00:aa:bb:cc:dd:01   5000
Vnet_3000    30.0.0.0/24  192.168.1.201                      6000

Namespace: asic1
vnet name    prefix       endpoint       mac address          vni
-----------  -----------  -------------  -----------------  -----
Vnet_4000    50.0.0.0/24  192.168.2.200  00:aa:bb:cc:dd:02   4000
"""

show_vnet_routes_tunnel_asic1_output = """\
vnet name    prefix       endpoint       mac address          vni
-----------  -----------  -------------  -----------------  -----
Vnet_4000    50.0.0.0/24  192.168.2.200  00:aa:bb:cc:dd:02   4000
"""

show_vnet_endpoint_multi_asic_output = """\

Namespace: asic0
Endpoint       Endpoint Monitor      prefix count  status
-------------  ------------------  --------------  --------
192.168.1.201  192.168.1.201                    1  Unknown

Namespace: asic1
Endpoint    Endpoint Monitor    prefix count    status
----------  ------------------  --------------  --------
"""


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

    def test_show_vnet_brief_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["brief"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vnet_brief_multi_asic_output

    def test_show_vnet_brief_specific_namespace(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["-n", "asic0", "brief"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vnet_brief_asic0_output

    def test_show_vnet_name_found_in_asic0(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["name", "Vnet_2000"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vnet_name_vnet2000_output

    def test_show_vnet_name_found_in_asic1(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["name", "Vnet_4000"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vnet_name_vnet4000_output

    def test_show_vnet_name_not_found(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["name", "Vnet_9999"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vnet_name_not_found_output

    def test_show_vnet_name_specific_namespace(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["-n", "asic0", "name", "Vnet_2000"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vnet_name_vnet2000_specific_ns_output

    def test_show_vnet_guid_found(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["guid", "guid-2000-asic0"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vnet_guid_vnet2000_output

    def test_show_vnet_guid_found_in_asic1(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["guid", "guid-4000-asic1"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vnet_guid_vnet4000_output

    def test_show_vnet_guid_not_found(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["guid", "nonexistent-guid"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vnet_guid_not_found_output

    def test_show_vnet_alias_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["alias"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vnet_alias_multi_asic_output

    def test_show_vnet_alias_specific(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["alias", "guid-2000-asic0"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vnet_alias_specific_output

    def test_show_vnet_interfaces_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["interfaces"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vnet_interfaces_multi_asic_output

    def test_show_vnet_interfaces_specific_namespace(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["-n", "asic1", "interfaces"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vnet_interfaces_asic1_output

    def test_show_vnet_neighbors_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["neighbors"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vnet_neighbors_multi_asic_output

    def test_show_vnet_neighbors_specific_namespace(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["-n", "asic0", "neighbors"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vnet_neighbors_asic0_output

    def test_show_vnet_routes_all_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["routes", "all"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vnet_routes_all_multi_asic_output

    def test_show_vnet_routes_all_specific_namespace(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["-n", "asic0", "routes", "all"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vnet_routes_all_asic0_output

    def test_show_vnet_routes_tunnel_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["routes", "tunnel"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vnet_routes_tunnel_multi_asic_output

    def test_show_vnet_routes_tunnel_specific_namespace(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["-n", "asic1", "routes", "tunnel"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vnet_routes_tunnel_asic1_output

    def test_show_vnet_endpoint_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["endpoint"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vnet_endpoint_multi_asic_output

    def test_show_vnet_brief_invalid_namespace(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vnet"], ["-n", "invalid_ns", "brief"])
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code != 0

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

    def test_config_vnet_add_del_with_namespace(self):
        runner = CliRunner()
        db = Db()

        db.cfgdb_clients["asic0"].set_entry("VXLAN_TUNNEL", "vtep1", {"src_ip": "10.10.10.1"})

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

        db.cfgdb_clients["asic0"].set_entry("VXLAN_TUNNEL", "vtep1", {"src_ip": "10.10.10.1"})

        result = runner.invoke(
            config.main.config.commands["vnet"],
            ["-n", "asic0", "add", "Vnet_RT", "800", "vtep1"],
            obj=db
        )
        assert result.exit_code == 0
        assert "Vnet_RT" in db.cfgdb_clients["asic0"].get_table("VNET")
        assert "added/updated" in result.output

        result = runner.invoke(
            config.main.config.commands["vnet"],
            ["-n", "asic0", "add-route", "Vnet_RT", "10.10.10.0/24", "192.168.1.1"],
            obj=db
        )
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert "added/updated" in result.output

        vnet_route_tunnel = db.cfgdb_clients["asic0"].get_table("VNET_ROUTE_TUNNEL")
        assert ("Vnet_RT", "10.10.10.0/24") in vnet_route_tunnel
        assert vnet_route_tunnel[("Vnet_RT", "10.10.10.0/24")]["endpoint"] == "192.168.1.1"

        vnet_route_tunnel_asic1 = db.cfgdb_clients["asic1"].get_table("VNET_ROUTE_TUNNEL")
        assert ("Vnet_RT", "10.10.10.0/24") not in vnet_route_tunnel_asic1

        result = runner.invoke(
            config.main.config.commands["vnet"],
            ["-n", "asic0", "del-route", "Vnet_RT", "10.10.10.0/24"],
            obj=db
        )
        print("exit_code: {}".format(result.exit_code))
        print("output: {}".format(result.output))
        assert result.exit_code == 0
        assert "Specific route deleted" in result.output

        vnet_route_tunnel = db.cfgdb_clients["asic0"].get_table("VNET_ROUTE_TUNNEL")
        assert ("Vnet_RT", "10.10.10.0/24") not in vnet_route_tunnel

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

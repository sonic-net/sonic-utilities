import os
import sys
from importlib import reload

from click.testing import CliRunner

import show.main
import show.vxlan
import config.main
import config.vxlan
import utilities_common.multi_asic
from utilities_common.db import Db

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

show_vxlan_interface_multi_asic_output = """\
VTEP Information:


Namespace: asic0
\tVTEP Name : vtep1, SIP  : 10.10.10.1
\tNVO Name  : nvo1,  VTEP : vtep1
\tSource interface  : Loopback0

Namespace: asic1
\tVTEP Name : vtep1, SIP  : 10.10.10.2
\tNVO Name  : nvo1,  VTEP : vtep1
\tSource interface  : Loopback0
"""

show_vxlan_vlanvnimap_multi_asic_output = """\

Namespace: asic0
+---------+-------+
| VLAN    |   VNI |
+=========+=======+
| Vlan100 |  1000 |
+---------+-------+
| Vlan200 |  2000 |
+---------+-------+
Total count : 2


Namespace: asic1
+---------+-------+
| VLAN    |   VNI |
+=========+=======+
| Vlan100 |  1000 |
+---------+-------+
| Vlan200 |  2000 |
+---------+-------+
Total count : 2

"""

show_vxlan_vlanvnimap_count_multi_asic_output = """\

Namespace: asic0
Total count : 2


Namespace: asic1
Total count : 2

"""

show_vxlan_vrfvnimap_multi_asic_output = """\

Namespace: asic0
+-------+-------+
| VRF   |   VNI |
+=======+=======+
| Vrf1  |  3000 |
+-------+-------+
Total count : 1


Namespace: asic1
+-------+-------+
| VRF   |   VNI |
+=======+=======+
| Vrf1  |  3000 |
+-------+-------+
Total count : 1

"""

show_vxlan_tunnel_multi_asic_output = """\

Namespace: asic0
vxlan tunnel name    source ip    destination ip    tunnel map name    tunnel map mapping(vni -> vlan)
-------------------  -----------  ----------------  -----------------  ---------------------------------
vtep1                10.10.10.1                     map_1000_Vlan100   1000 -> Vlan100
                                                    map_2000_Vlan200   2000 -> Vlan200

Namespace: asic1
vxlan tunnel name    source ip    destination ip    tunnel map name    tunnel map mapping(vni -> vlan)
-------------------  -----------  ----------------  -----------------  ---------------------------------
vtep1                10.10.10.2                     map_1000_Vlan100   1000 -> Vlan100
                                                    map_2000_Vlan200   2000 -> Vlan200
"""

show_vxlan_name_multi_asic_output = """\

Namespace: asic0
vxlan tunnel name    source ip    destination ip    tunnel map name    tunnel map mapping(vni -> vlan)
-------------------  -----------  ----------------  -----------------  ---------------------------------
vtep1                10.10.10.1                     map_1000_Vlan100   1000 -> Vlan100
                                                    map_2000_Vlan200   2000 -> Vlan200

Namespace: asic1
vxlan tunnel name    source ip    destination ip    tunnel map name    tunnel map mapping(vni -> vlan)
-------------------  -----------  ----------------  -----------------  ---------------------------------
vtep1                10.10.10.2                     map_1000_Vlan100   1000 -> Vlan100
                                                    map_2000_Vlan200   2000 -> Vlan200
"""

show_vxlan_remotevtep_multi_asic_output = """\

Namespace: asic0
+------------+---------------+-------------------+--------------+
| SIP        | DIP           | Creation Source   | OperStatus   |
+============+===============+===================+==============+
| 10.10.10.1 | 192.168.1.100 | EVPN              | oper_up      |
+------------+---------------+-------------------+--------------+
| 10.10.10.1 | 192.168.1.101 | EVPN              | oper_up      |
+------------+---------------+-------------------+--------------+
Total count : 2


Namespace: asic1
+------------+---------------+-------------------+--------------+
| SIP        | DIP           | Creation Source   | OperStatus   |
+============+===============+===================+==============+
| 10.10.10.2 | 192.168.1.102 | EVPN              | oper_up      |
+------------+---------------+-------------------+--------------+
Total count : 1

"""

show_vxlan_remotevtep_count_multi_asic_output = """\

Namespace: asic0
Total count : 2


Namespace: asic1
Total count : 1

"""

show_vxlan_remotevni_all_multi_asic_output = """\

Namespace: asic0
+---------+---------------+-------+
| VLAN    | RemoteVTEP    |   VNI |
+=========+===============+=======+
| Vlan100 | 192.168.1.100 |  1000 |
+---------+---------------+-------+
| Vlan200 | 192.168.1.101 |  2000 |
+---------+---------------+-------+
Total count : 2


Namespace: asic1
+---------+---------------+-------+
| VLAN    | RemoteVTEP    |   VNI |
+=========+===============+=======+
| Vlan100 | 192.168.1.102 |  1000 |
+---------+---------------+-------+
Total count : 1

"""

show_vxlan_remotevni_count_multi_asic_output = """\

Namespace: asic0
Total count : 2


Namespace: asic1
Total count : 1

"""

show_vxlan_remotemac_all_multi_asic_output = """\

Namespace: asic0
+---------+-------------------+---------------+-------+---------+
| VLAN    | MAC               | RemoteVTEP    |   VNI | Type    |
+=========+===================+===============+=======+=========+
| Vlan100 | 00:11:22:33:44:55 | 192.168.1.100 |  1000 | dynamic |
+---------+-------------------+---------------+-------+---------+
| Vlan200 | 00:11:22:33:44:66 | 192.168.1.101 |  2000 | dynamic |
+---------+-------------------+---------------+-------+---------+
Total count : 2


Namespace: asic1
+---------+-------------------+---------------+-------+---------+
| VLAN    | MAC               | RemoteVTEP    |   VNI | Type    |
+=========+===================+===============+=======+=========+
| Vlan100 | 00:11:22:33:44:77 | 192.168.1.102 |  1000 | dynamic |
+---------+-------------------+---------------+-------+---------+
Total count : 1

"""

show_vxlan_remotemac_count_multi_asic_output = """\

Namespace: asic0
Total count : 2


Namespace: asic1
Total count : 1

"""

show_vxlan_interface_asic0_output = """\
VTEP Information:

\tVTEP Name : vtep1, SIP  : 10.10.10.1
\tNVO Name  : nvo1,  VTEP : vtep1
\tSource interface  : Loopback0
"""

show_vxlan_vlanvnimap_asic0_output = """\
+---------+-------+
| VLAN    |   VNI |
+=========+=======+
| Vlan100 |  1000 |
+---------+-------+
| Vlan200 |  2000 |
+---------+-------+
Total count : 2

"""


class TestMultiAsicVxlan:
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
        reload(show.vxlan)
        reload(show.main)
        reload(config.vxlan)
        reload(config.main)

    def test_show_vxlan_interface_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vxlan"], ["interface"])
        print("result.exit_code: {}".format(result.exit_code))
        print("result.output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vxlan_interface_multi_asic_output

    def test_show_vxlan_interface_specific_namespace(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vxlan"], ["-n", "asic0", "interface"])
        print("result.exit_code: {}".format(result.exit_code))
        print("result.output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vxlan_interface_asic0_output

    def test_show_vxlan_tunnel_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vxlan"], ["tunnel"])
        print("result.exit_code: {}".format(result.exit_code))
        print("result.output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vxlan_tunnel_multi_asic_output

    def test_show_vxlan_name_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vxlan"], ["name", "vtep1"])
        print("result.exit_code: {}".format(result.exit_code))
        print("result.output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vxlan_name_multi_asic_output

    def test_show_vxlan_vlanvnimap_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vxlan"], ["vlanvnimap"])
        print("result.exit_code: {}".format(result.exit_code))
        print("result.output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vxlan_vlanvnimap_multi_asic_output

    def test_show_vxlan_vlanvnimap_count_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vxlan"], ["vlanvnimap", "count"])
        print("result.exit_code: {}".format(result.exit_code))
        print("result.output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vxlan_vlanvnimap_count_multi_asic_output

    def test_show_vxlan_vlanvnimap_specific_namespace(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vxlan"], ["-n", "asic0", "vlanvnimap"])
        print("result.exit_code: {}".format(result.exit_code))
        print("result.output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vxlan_vlanvnimap_asic0_output

    def test_show_vxlan_vrfvnimap_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vxlan"], ["vrfvnimap"])
        print("result.exit_code: {}".format(result.exit_code))
        print("result.output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vxlan_vrfvnimap_multi_asic_output

    def test_show_vxlan_remotevtep_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vxlan"], ["remotevtep"])
        print("result.exit_code: {}".format(result.exit_code))
        print("result.output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vxlan_remotevtep_multi_asic_output

    def test_show_vxlan_remotevtep_count_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vxlan"], ["remotevtep", "count"])
        print("result.exit_code: {}".format(result.exit_code))
        print("result.output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vxlan_remotevtep_count_multi_asic_output

    def test_show_vxlan_remotevni_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vxlan"], ["remotevni", "all"])
        print("result.exit_code: {}".format(result.exit_code))
        print("result.output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vxlan_remotevni_all_multi_asic_output

    def test_show_vxlan_remotevni_count_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vxlan"], ["remotevni", "all", "count"])
        print("result.exit_code: {}".format(result.exit_code))
        print("result.output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vxlan_remotevni_count_multi_asic_output

    def test_show_vxlan_remotemac_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vxlan"], ["remotemac", "all"])
        print("result.exit_code: {}".format(result.exit_code))
        print("result.output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vxlan_remotemac_all_multi_asic_output

    def test_show_vxlan_remotemac_count_all_namespaces(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vxlan"], ["remotemac", "all", "count"])
        print("result.exit_code: {}".format(result.exit_code))
        print("result.output: {}".format(result.output))
        assert result.exit_code == 0
        assert result.output == show_vxlan_remotemac_count_multi_asic_output

    def test_config_vxlan_add_requires_namespace(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(
            config.main.config.commands["vxlan"],
            ["add", "vtep_test", "10.10.10.10"],
            obj=db
        )
        print("result.exit_code: {}".format(result.exit_code))
        print("result.output: {}".format(result.output))
        assert result.exit_code != 0 or "namespace" in result.output.lower() or "required" in result.output.lower()

    def test_config_vxlan_add_with_namespace(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.main.config.commands["vxlan"],
            ["-n", "asic0", "add", "vtep_test", "10.10.10.10"],
            obj=db
        )
        print("result.exit_code: {}".format(result.exit_code))
        print("result.output: {}".format(result.output))
        assert result.exit_code != 0
        assert "VTEP already configured" in result.output

    def test_config_vxlan_evpn_nvo_requires_namespace(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.main.config.commands["vxlan"],
            ["evpn_nvo", "add", "nvo_test", "vtep1"],
            obj=db
        )
        print("result.exit_code: {}".format(result.exit_code))
        print("result.output: {}".format(result.output))
        assert result.exit_code != 0 or "namespace" in result.output.lower() or "required" in result.output.lower()

    def test_config_vxlan_map_requires_namespace(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.main.config.commands["vxlan"],
            ["map", "add", "vtep1", "300", "3000"],
            obj=db
        )
        print("result.exit_code: {}".format(result.exit_code))
        print("result.output: {}".format(result.output))
        assert result.exit_code != 0 or "namespace" in result.output.lower() or "required" in result.output.lower()

    def test_config_vxlan_map_range_with_namespace(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(
            config.main.config.commands["vxlan"],
            ["-n", "asic0", "map_range", "add", "vtep1", "300", "310", "3000"],
            obj=db
        )
        print("result.exit_code: {}".format(result.exit_code))
        print("result.output: {}".format(result.output))
        assert "not configured" in result.output.lower() or result.exit_code != 0

    def test_show_vxlan_interface_invalid_namespace(self):
        runner = CliRunner()
        result = runner.invoke(show.main.cli.commands["vxlan"], ["-n", "invalid_ns", "interface"])
        print("result.exit_code: {}".format(result.exit_code))
        print("result.output: {}".format(result.output))
        assert result.exit_code != 0 or "invalid" in result.output.lower() or result.output == ""

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
        reload(show.vxlan)
        reload(show.main)
        reload(config.vxlan)
        reload(config.main)

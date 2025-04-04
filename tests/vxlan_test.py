import os
import traceback
from unittest import mock

from click.testing import CliRunner
from mock import patch
from jsonpatch import JsonPatchConflict

import config.main as config
import config.validated_config_db_connector as validated_config_db_connector
import show.main as show
from utilities_common.db import Db
from .mock_tables import dbconnector

test_path = os.path.dirname(os.path.abspath(__file__))
mock_db_path = os.path.join(test_path, "vnet_input")

show_vxlan_interface_output="""\
VTEP Information:

	VTEP Name : vtep1, SIP  : 1.1.1.1
	NVO Name  : nvo1,  VTEP : vtep1
"""

show_vxlan_vlanvnimap_output="""\
+---------+-------+
| VLAN    |   VNI |
+=========+=======+
| Vlan100 |   100 |
+---------+-------+
| Vlan101 |   101 |
+---------+-------+
| Vlan102 |   102 |
+---------+-------+
| Vlan200 |   200 |
+---------+-------+
Total count : 4

"""

show_vxlan_vrfvnimap_output="""\
+-------+-------+
| VRF   |   VNI |
+=======+=======+
| Vrf1  |  1000 |
+-------+-------+
Total count : 1

"""


show_vxlan_tunnel_output="""\
+---------+-------------+-------------------+--------------+
| SIP     | DIP         | Creation Source   | OperStatus   |
+=========+=============+===================+==============+
| 1.1.1.1 | 25.25.25.25 | EVPN              | oper_down    |
+---------+-------------+-------------------+--------------+
| 1.1.1.1 | 25.25.25.26 | EVPN              | oper_down    |
+---------+-------------+-------------------+--------------+
| 1.1.1.1 | 25.25.25.27 | EVPN              | oper_down    |
+---------+-------------+-------------------+--------------+
Total count : 3

"""

show_vxlan_name_output="""\
vxlan tunnel name    source ip    destination ip    tunnel map name    tunnel map mapping(vni -> vlan)
-------------------  -----------  ----------------  -----------------  ---------------------------------
vtep1                1.1.1.1                        map_100_Vlan100    100 -> Vlan100
                                                    map_101_Vlan101    101 -> Vlan101
                                                    map_102_Vlan102    102 -> Vlan102
                                                    map_200_Vlan200    200 -> Vlan200
"""

show_vxlan_remotevni_output="""\
+---------+--------------+-------+
| VLAN    | RemoteVTEP   |   VNI |
+=========+==============+=======+
| Vlan200 | 25.25.25.25  |   200 |
+---------+--------------+-------+
| Vlan200 | 25.25.25.26  |   200 |
+---------+--------------+-------+
| Vlan200 | 25.25.25.27  |   200 |
+---------+--------------+-------+
Total count : 3

"""

show_vxlan_remotevni_specific_output="""\
+---------+--------------+-------+
| VLAN    | RemoteVTEP   |   VNI |
+=========+==============+=======+
| Vlan200 | 25.25.25.27  |   200 |
+---------+--------------+-------+
Total count : 1

"""
show_vxlan_vlanvnimap_cnt_output="""\
Total count : 4

"""

show_vxlan_tunnel_cnt_output="""\
Total count : 3

"""

show_vxlan_remotevni_cnt_output="""\
Total count : 3

"""

show_vxlan_remotevni_specific_cnt_output="""\
Total count : 1

"""

show_vxlan_remotemac_all_output="""\
+---------+-------------------+--------------+-------+---------+
| VLAN    | MAC               | RemoteVTEP   |   VNI | Type    |
+=========+===================+==============+=======+=========+
| Vlan200 | 00:02:00:00:47:e2 | 2.2.2.2      |   200 | dynamic |
+---------+-------------------+--------------+-------+---------+
| Vlan200 | 00:02:00:00:47:e3 | 2.2.2.3      |   200 | dynamic |
+---------+-------------------+--------------+-------+---------+
Total count : 2

"""

show_vxlan_remotemac_specific_output="""\
+---------+-------------------+--------------+-------+---------+
| VLAN    | MAC               | RemoteVTEP   |   VNI | Type    |
+=========+===================+==============+=======+=========+
| Vlan200 | 00:02:00:00:47:e2 | 2.2.2.2      |   200 | dynamic |
+---------+-------------------+--------------+-------+---------+
Total count : 1

"""

show_vxlan_remotemac_cnt_output="""\
Total count : 2

"""

show_vxlan_remotemac_specific_cnt_output="""\
Total count : 1

"""

class TestVxlan(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

    def test_show_vxlan_interface(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vxlan"].commands["interface"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vxlan_interface_output

    def test_show_vxlan_vlanvnimap(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vxlan"].commands["vlanvnimap"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vxlan_vlanvnimap_output

    def test_show_vxlan_vrfvnimap(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vxlan"].commands["vrfvnimap"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vxlan_vrfvnimap_output

    def test_show_vxlan_tunnel(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vxlan"].commands["remotevtep"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vxlan_tunnel_output

    def test_show_vxlan_tunnel_output(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vxlan"].commands["tunnel"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vxlan_name_output

    def test_show_vxlan_name_vtep(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vxlan"].commands["name"],["vtep1"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vxlan_name_output

    def test_show_vxlan_remotevni(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vxlan"].commands["remotevni"], ["all"])
        #result = runner.invoke(show.cli.commands["vxlan"].commands["remotevni"].commands["all"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vxlan_remotevni_output

    def test_show_vxlan_remotevni_specific(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vxlan"].commands["remotevni"],["25.25.25.27"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vxlan_remotevni_specific_output

    def test_show_vxlan_vlanvnimap_cnt(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vxlan"].commands["vlanvnimap"],["count"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vxlan_vlanvnimap_cnt_output

    def test_show_vxlan_tunnel_cnt(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vxlan"].commands["remotevtep"], ["count"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vxlan_tunnel_cnt_output

    def test_show_vxlan_remotevni_cnt(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vxlan"].commands["remotevni"], ["all", "count"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vxlan_remotevni_cnt_output

    def test_show_vxlan_remotevni_specific_cnt(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vxlan"].commands["remotevni"], ["25.25.25.25", "count"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vxlan_remotevni_specific_cnt_output

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=ValueError))
    @patch("config.main.ConfigDBConnector.get_entry", mock.Mock(return_value="Vlan Data"))
    @patch("config.main.ConfigDBConnector.get_table", mock.Mock(return_value={'sample_key': 'sample_value'}))
    def test_config_vxlan_add_yang_validation(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["vxlan"].commands["map_range"].commands["del"], ["vtep1", "100", "102", "100"], obj=db)
        print(result.exit_code)
        assert result.exit_code != 0

        result = runner.invoke(config.config.commands["vxlan"].commands["map_range"].commands["add"], ["vtep1", "100", "102", "100"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=JsonPatchConflict))
    def test_config_vxlan_add_yang_validation_json_error(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["vxlan"].commands["map"].commands["del"], ["vtep1", "200", "200"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0

    def test_show_vxlan_remotemac(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vxlan"].commands["remotemac"], ["all"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vxlan_remotemac_all_output

    def test_show_vxlan_remotemac_specific(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vxlan"].commands["remotemac"], ["2.2.2.2"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vxlan_remotemac_specific_output

    def test_show_vxlan_remotemac_cnt(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vxlan"].commands["remotemac"], ["all", "count"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vxlan_remotemac_cnt_output

    def test_show_vxlan_remotemac_specific_cnt(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["vxlan"].commands["remotemac"], ["2.2.2.2", "count"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vxlan_remotemac_specific_cnt_output

    def test_config_vxlan_add(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["vxlan"].commands["map"].commands["del"], ["vtep1", "200", "200"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(config.config.commands["vxlan"].commands["map_range"].commands["del"], ["vtep1", "100", "102", "100"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(config.config.commands["vxlan"].commands["evpn_nvo"].commands["del"], ["nvo1"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(config.config.commands["vxlan"].commands["del"], ["vtep1"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(config.config.commands["vxlan"].commands["add"], ["vtep1", "1.1.1.1"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(config.config.commands["vxlan"].commands["evpn_nvo"].commands["add"], ["nvo1", "vtep1"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(show.cli.commands["vxlan"].commands["interface"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vxlan_interface_output

        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["100"], obj=db)
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["101"], obj=db)
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["102"], obj=db)
        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["200"], obj=db)

        result = runner.invoke(config.config.commands["vxlan"].commands["map"].commands["add"], ["vtep1", "200", "200"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(config.config.commands["vxlan"].commands["map_range"].commands["add"], ["vtep1", "100", "102", "100"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(show.cli.commands["vxlan"].commands["vlanvnimap"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_vxlan_vlanvnimap_output

    def test_config_vxlan_add_invalid_name(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["vxlan"].commands["add"], ["vtep111111111111", "1.1.1.1"], obj=db)
        print(result.exit_code)
        print(result.output)
        expected_output = """\
Error: 'vxlan_name' length should not exceed 15 characters
"""
        assert expected_output in result.output
        assert result.exit_code != 0

    def test_config_vxlan_del(self):
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'config_db')
        db = Db()
        runner = CliRunner()

        result = runner.invoke(config.config.commands["vxlan"].commands["del"], ["tunnel_invalid"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Vxlan tunnel tunnel_invalid does not exist" in result.output

        result = runner.invoke(config.config.commands["vxlan"].commands["del"], ["tunnel1"], obj=db)
        dbconnector.dedicated_dbs = {}
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Please delete all VNET configuration referencing the tunnel" in result.output

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")

class TestVxlan(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

    def test_show_vnet_brief(self):
        from .mock_tables import dbconnector
        jsonfile_config = os.path.join(mock_db_path, "config_db")
        dbconnector.dedicated_dbs['CONFIG_DB'] = jsonfile_config
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["vnet"].commands["brief"], [])
        assert result.exit_code != 0
        assert "Vnet_2000" in result.output
        assert "1234-56-7890-1234" in result.output
        assert "tunnel1" in result.output

    def test_show_vnet_name(self):
        from .mock_tables import dbconnector
        jsonfile_config = os.path.join(mock_db_path, "config_db")
        dbconnector.dedicated_dbs['CONFIG_DB'] = jsonfile_config
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["vnet"].commands["name"], ["Vnet_2000"])
        assert result.exit_code != 0
        assert "Vnet_2000" in result.output
        assert "1234-56-7890-1234" in result.output
    
    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")

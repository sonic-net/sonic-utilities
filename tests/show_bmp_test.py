import os
from click.testing import CliRunner
from utilities_common.db import Db

import show.main as show

test_path = os.path.dirname(os.path.abspath(__file__))
mock_db_path = os.path.join(test_path, "bmp_input")


class TestShowBmp(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def set_db_values(self, db, key, kvs):
        for field, value in kvs.items():
            db.set(db.BMP_STATE_DB, key, field, value)

    def test_show_bmp_neighbor_table(self):
        runner = CliRunner()
        db = Db()
        dbconnector = db.db
        self.set_db_values(dbconnector,
                           "BGP_NEIGHBOR_TABLE|10.0.1.1",
                           {"peer_addr": "10.0.0.61",
                            "peer_asn": "64915",
                            "peer_rd": "300",
                            "remote_port": "5000",
                            "local_ip": "10.1.0.32",
                            "local_asn": "65100",
                            "local_port": "6000",
                            "sent_cap": "supports-mpbgp,supports-graceful-restart",
                            "recv_cap": "supports-mpbgp,supports-graceful-restart"})
        self.set_db_values(dbconnector,
                           "BGP_NEIGHBOR_TABLE|10.0.1.2",
                           {"peer_addr": "10.0.0.62",
                            "peer_asn": "64915",
                            "peer_rd": "300",
                            "remote_port": "5000",
                            "local_ip": "10.1.0.32",
                            "local_asn": "65100",
                            "local_port": "6000",
                            "sent_cap": "supports-mpbgp,supports-graceful-restart",
                            "recv_cap": "supports-mpbgp,supports-graceful-restart"})

        expected_output = """\
Total number of bmp neighbors: 2
Neighbor_Address       Peer_Address  Peer_ASN Peer_RD  Peer_Port     Local_Address   Local_ASN      \
Local_Port     Advertised_Capabilities                      Received_Capabilities
------------------    --------------  ----------  ---------  -----------  ---------------  -----------  \
------------  ----------------------------------------  ----------------------------------------
10.0.0.61              10.0.0.61     64915    300      5000          10.1.0.32       65100          6000           \
supports-mpbgp,supports-graceful-restart   supports-mpbgp,supports-graceful-restart
10.0.0.62              10.0.0.62     64915    300      5000          10.1.0.32       65100          6000           \
supports-mpbgp,supports-graceful-restart   supports-mpbgp,supports-graceful-restart
"""
        result = runner.invoke(show.cli.commands['bmp'].commands['bgp-neighbor-table'], [], obj=db)
        assert result.exit_code == 0
        resultA = result.output.strip().replace(' ', '').replace('\n', '')
        resultB = expected_output.strip().replace(' ', '').replace('\n', '')
        assert resultA == resultB

    def test_show_bmp_rib_out_table(self):
        runner = CliRunner()
        db = Db()
        dbconnector = db.db
        self.set_db_values(dbconnector,
                           "BGP_RIB_OUT_TABLE|20c0:ef50::/64|10.0.0.57",
                           {"origin": "igp",
                            "as_path": "65100 64600",
                            "origin_as": "64915",
                            "next_hop": "fc00::7e",
                            "local_pref": "0",
                            "originator_id": "0",
                            "community_list": "residential",
                            "ext_community_list": "traffic_engineering"})
        self.set_db_values(dbconnector,
                           "BGP_RIB_OUT_TABLE|192.181.168.0/25|10.0.0.59",
                           {"origin": "igp",
                            "as_path": "65100 64600",
                            "origin_as": "64915",
                            "next_hop": "10.0.0.63",
                            "local_pref": "0",
                            "originator_id": "0",
                            "community_list": "business",
                            "ext_community_list": "preferential_transit"})

        expected_output = """\
Total number of bmp bgp-rib-out-table: 2
Neighbor_Address       NLRI             Origin   AS_Path     Origin_AS     Next_Hop        Local_Pref     \
Originator_ID  Community_List            Ext_Community_List
------------------    ----------------  --------  -----------  ----------- ----------      ------------  \
---------------  ----------------          --------------------
10.0.0.57              20c0:ef50::/64   igp      65100 64600 64915         fc00::7e        0              \
0              residential               traffic_engineering
10.0.0.59              192.181.168.0/25 igp      65100 64600 64915         10.0.0.63       0              \
0              business                  preferential_transit
"""
        result = runner.invoke(show.cli.commands['bmp'].commands['bgp-rib-out-table'], [], obj=db)
        assert result.exit_code == 0
        resultA = result.output.strip().replace(' ', '').replace('\n', '')
        resultB = expected_output.strip().replace(' ', '').replace('\n', '')
        assert resultA == resultB

    def test_show_bmp_rib_in_table(self):
        runner = CliRunner()
        db = Db()
        dbconnector = db.db
        self.set_db_values(dbconnector,
                           "BGP_RIB_IN_TABLE|20c0:ef50::/64|10.0.0.57",
                           {"origin": "igp",
                            "as_path": "65100 64600",
                            "origin_as": "64915",
                            "next_hop": "fc00::7e",
                            "local_pref": "0",
                            "originator_id": "0",
                            "community_list": "residential",
                            "ext_community_list": "traffic_engineering"})
        self.set_db_values(dbconnector,
                           "BGP_RIB_IN_TABLE|192.181.168.0/25|10.0.0.59",
                           {"origin": "igp",
                            "as_path": "65100 64600",
                            "origin_as": "64915",
                            "next_hop": "10.0.0.63",
                            "local_pref": "0",
                            "originator_id": "0",
                            "community_list": "business",
                            "ext_community_list": "preferential_transit"})

        expected_output = """\
Total number of bmp bgp-rib-in-table: 2
Neighbor_Address       NLRI             Origin   AS_Path     Origin_AS     Next_Hop        Local_Pref     \
Originator_ID  Community_List            Ext_Community_List
------------------  ----------------  --------  -----------  -----------   ----------     ------------  \
---------------  ----------------         --------------------
10.0.0.57              20c0:ef50::/64   igp      65100 64600 64915         fc00::7e        0              \
0              residential               traffic_engineering
10.0.0.59              192.181.168.0/25 igp      65100 64600 64915         10.0.0.63       0              \
0              business                  preferential_transit
"""
        result = runner.invoke(show.cli.commands['bmp'].commands['bgp-rib-in-table'], [], obj=db)
        assert result.exit_code == 0
        resultA = result.output.strip().replace(' ', '').replace('\n', '')
        resultB = expected_output.strip().replace(' ', '').replace('\n', '')
        assert resultA == resultB

    def test_tables(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.mod_entry("BMP", "table", {'bgp_neighbor_table': 'true'})
        db.cfgdb.mod_entry("BMP", "table", {'bgp_rib_in_table': 'false'})
        db.cfgdb.mod_entry("BMP", "table", {'bgp_rib_out_table': 'true'})

        assert db.cfgdb.get_entry('BMP', 'table')['bgp_neighbor_table'] == 'true'
        assert db.cfgdb.get_entry('BMP', 'table')['bgp_rib_in_table'] == 'false'
        assert db.cfgdb.get_entry('BMP', 'table')['bgp_rib_out_table'] == 'true'

        expected_output = """\
BMP tables:
Table_Name          Enabled
------------------  ---------
bgp_neighbor_table  true
bgp_rib_in_table    false
bgp_rib_out_table   true
"""
        result = runner.invoke(show.cli.commands['bmp'].commands['tables'], [], obj=db)
        assert result.exit_code == 0
        resultA = result.output.strip().replace(' ', '').replace('\n', '')
        resultB = expected_output.strip().replace(' ', '').replace('\n', '')
        assert resultA == resultB

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

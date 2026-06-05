# flake8: noqa: E501
import os
import pytest
from click.testing import CliRunner
from utilities_common.db import Db
import show.main as show
import show.vnet as vnet
from tests.mock_tables import dbconnector

class TestShowVnetRoutesAll(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_Preety_print(self):
        table =[]
        row = ["Vnet_v6_in_v6-0", "fddd:a156:a251::a6:1/128"]
        mac_addr = ""
        vni = ""
        metric = "0"
        state = "active"
        epval = "fddd:a100:a251::a10:1,fddd:a101:a251::a10:1"

        vnet.pretty_print(table, row, epval, mac_addr, vni, metric, state)
        expected_output = [['Vnet_v6_in_v6-0', 'fddd:a156:a251::a6:1/128', 'fddd:a100:a251::a10:1,fddd:a101:a251::a10:1', '', '', '0', 'active']]
        assert table == expected_output

        table =[]
        row = ["Vnet_v6_in_v6-0", "fddd:a156:a251::a6:1/128"]
        epval = "fddd:a100:a251::a10:1,fddd:a101:a251::a10:1,fddd:a100:a251::a11:1,fddd:a100:a251::a12:1,fddd:a100:a251::a13:1"
        vnet.pretty_print(table, row, epval, mac_addr, vni, metric, state)
        expected_output = [
            ['Vnet_v6_in_v6-0', 'fddd:a156:a251::a6:1/128', 'fddd:a100:a251::a10:1,fddd:a101:a251::a10:1', '', '', '0', 'active'],
            ['',                '',                         'fddd:a100:a251::a11:1,fddd:a100:a251::a12:1', '', '', '', ''],
            ['',                '',                         'fddd:a100:a251::a13:1',                       '', '', '', '']
        ]
        assert table == expected_output

        table =[]
        row = ["Vnet_v6_in_v6-0", "fddd:a156:a251::a6:1/128"]
        epval = "192.168.1.1,192.168.1.2,192.168.1.3,192.168.1.4,192.168.1.5,192.168.1.6,192.168.1.7,192.168.1.8,192.168.1.9,192.168.1.10,192.168.1.11,192.168.1.12,192.168.1.13,192.168.1.14,192.168.1.15"
        vnet.pretty_print(table, row, epval, mac_addr, vni, metric, state)
        expected_output =[
            ['Vnet_v6_in_v6-0', 'fddd:a156:a251::a6:1/128', '192.168.1.1,192.168.1.2,192.168.1.3',    '', '', '0', 'active'],
            ['',                '',                         '192.168.1.4,192.168.1.5,192.168.1.6',    '', '', '', ''],
            ['',                '',                         '192.168.1.7,192.168.1.8,192.168.1.9',    '', '', '', ''],
            ['',                '',                         '192.168.1.10,192.168.1.11,192.168.1.12', '', '', '', ''],
            ['',                '',                         '192.168.1.13,192.168.1.14,192.168.1.15', '', '', '', '']]
        assert table == expected_output

        table =[]
        row = ["Vnet_v6_in_v6-0", "fddd:a156:a251::a6:1/128"]
        epval = "192.168.1.1"
        vnet.pretty_print(table, row, epval, mac_addr, vni, metric, state)
        expected_output =[
            ['Vnet_v6_in_v6-0', 'fddd:a156:a251::a6:1/128', '192.168.1.1', '', '', '0', 'active']]
        assert table == expected_output

        # same endpoint, per-endpoint MACs and VNIs are wrapped in sync with endpoints
        table = []
        row = ["TestVnet", "10.0.0.1/32"]
        epval = "1.1.1.1,1.1.1.1,1.1.1.1,1.1.1.1"
        mac_addr = "aa:bb:cc:00:00:01,aa:bb:cc:00:00:02,aa:bb:cc:00:00:03,aa:bb:cc:00:00:04"
        vni = "100,200,300,400"
        metric = ""
        # MAC items are 17 chars > 15, so row_width=2
        vnet.pretty_print(table, row, epval, mac_addr, vni, metric, state)
        expected_output = [
            ["TestVnet", "10.0.0.1/32", "1.1.1.1,1.1.1.1", "aa:bb:cc:00:00:01,aa:bb:cc:00:00:02", "100,200", "", "active"],
            ["",         "",            "1.1.1.1,1.1.1.1", "aa:bb:cc:00:00:03,aa:bb:cc:00:00:04", "300,400", "", ""],
        ]
        assert table == expected_output

        # row_width decided by MAC item length, not just endpoint length
        table = []
        row = ["TestVnet", "10.0.0.1/32"]
        epval = "1.1.1.1,2.2.2.2,3.3.3.3"
        mac_addr = "aa:bb:cc:00:00:01,aa:bb:cc:00:00:02,aa:bb:cc:00:00:03"
        vni = "100,200,300"
        metric = "5"
        # All endpoints are <=7 chars, MAC items are 17 chars > 15 → row_width=2
        vnet.pretty_print(table, row, epval, mac_addr, vni, metric, state)
        expected_output = [
            ["TestVnet", "10.0.0.1/32", "1.1.1.1,2.2.2.2", "aa:bb:cc:00:00:01,aa:bb:cc:00:00:02", "100,200", "5",  "active"],
            ["",         "",            "3.3.3.3",          "aa:bb:cc:00:00:03",                   "300",     "",   ""],
        ]
        assert table == expected_output

    @pytest.mark.parametrize("N,vnet_name,prefix,metric", [
        (511,  "Vnet_scale_511",  "10.0.0.0/9", "5"),   # current production scale (odd → last row is a singleton)
        (2048, "Vnet_scale_2048", "10.0.0.0/8", "10"),  # target maximum scale (even → all rows are pairs)
    ])
    def test_pretty_print_scale(self, N, vnet_name, prefix, metric):
        """Scale test for pretty_print at 511 (current production) and 2048 (target max) endpoints.

        Endpoints are generated as 10.{i>>8}.{i&0xff}.1, MACs as aa:bb:cc:00:{i>>8}:{i&0xff},
        and VNIs as sequential integers — all unique, no DB required, runs in well under 1 ms.
        """
        endpoints_list = [f"10.{(i >> 8) & 0xff}.{i & 0xff}.1" for i in range(N)]
        macs_list      = [f"aa:bb:cc:{(i >> 16) & 0xff:02x}:{(i >> 8) & 0xff:02x}:{i & 0xff:02x}" for i in range(N)]
        vnis_list      = [str(i + 1) for i in range(N)]

        table = []
        row = [vnet_name, prefix]
        vnet.pretty_print(table, row,
                          ",".join(endpoints_list),
                          ",".join(macs_list),
                          ",".join(vnis_list),
                          metric, "active")

        expected_rows = (N + 1) // 2  # ceil(N/2) — works for both odd and even
        assert len(table) == expected_rows

        # First row carries vnet name, prefix, metric, and state
        assert table[0][0] == vnet_name
        assert table[0][1] == prefix
        assert table[0][2] == f"{endpoints_list[0]},{endpoints_list[1]}"
        assert table[0][3] == f"{macs_list[0]},{macs_list[1]}"
        assert table[0][4] == f"{vnis_list[0]},{vnis_list[1]}"
        assert table[0][5] == metric
        assert table[0][6] == "active"

        # All subsequent rows have empty name, prefix, metric, and state
        for r in table[1:]:
            assert r[0] == "" and r[1] == "" and r[5] == "" and r[6] == ""

        # Round-trip: no data loss and endpoints/MACs/VNIs stay aligned across all rows
        assert ",".join(r[2] for r in table) == ",".join(endpoints_list)
        assert ",".join(r[3] for r in table) == ",".join(macs_list)
        assert ",".join(r[4] for r in table) == ",".join(vnis_list)

    def test_show_vnet_routes_all_basic(self):
        runner = CliRunner()
        db = Db()
        
        result = runner.invoke(show.cli.commands['vnet'].commands['routes'].commands['all'], [], obj=db)
        assert result.exit_code == 0
        expected_output = """\
vnet name        prefix            nexthop                                interface
---------------  ----------------  -------------------------------------  -------------------------------
test_v4_in_v4-0  160.162.191.1/32  100.100.4.1                            Ethernet1
test_v4_in_v4-0  160.163.191.1/32  100.101.4.1, 100.101.4.2               Ethernet1, Ethernet2
test_v4_in_v4-0  160.164.191.1/32  100.102.4.1, 100.102.4.2, 100.102.4.3  Ethernet1, Ethernet2, Ethernet3
test_v4_in_v4-1  160.165.191.1/32  100.103.4.1, 100.103.4.2, 100.103.4.3  Ethernet1, Ethernet2, Ethernet3

vnet name           prefix                    endpoint                                     mac address                          vni              metric    status
------------------  ------------------------  -------------------------------------------  -----------------------------------  ---------------  --------  --------
Vnet_7127926        30.0.20.0/24              100.106.230.44,10.134.85.10                  00:22:48:03:8c:f8,60:45:bd:a3:8d:ab  7127926,7127926  5         active
                                              100.106.229.38,100.106.229.170               60:45:bd:a3:21:88,60:45:bd:a2:e4:39  7127926,7127926
                                              100.106.228.160,10.134.84.24                 7c:1e:52:06:89:0f,7c:1e:52:06:8b:cd  7127926,7127926
                                              100.106.230.168,10.90.92.16                  60:45:bd:a3:8f:ae,60:45:bd:a2:e8:f9  7127926,7127926
                                              10.224.116.42,100.106.228.134                60:45:bd:a2:e5:ee,60:45:bd:a4:be:3e  7127926,7127926
Vnet_7127926        30.0.21.0/24              100.106.230.44,10.134.85.10                  00:22:48:03:8c:f8,60:45:bd:a3:8d:ab  7127926,7127926  5         active
                                              100.106.229.38,100.106.229.170               60:45:bd:a3:21:88,60:45:bd:a2:e4:39  7127926,7127926
                                              100.106.228.160,10.134.84.24                 7c:1e:52:06:89:0f,7c:1e:52:06:8b:cd  7127926,7127926
                                              100.106.230.168,10.90.92.16                  60:45:bd:a3:8f:ae,60:45:bd:a2:e8:f9  7127926,7127926
                                              10.224.116.42,100.106.228.134                60:45:bd:a2:e5:ee,60:45:bd:a4:be:3e  7127926,7127926
                                              100.106.229.171,100.106.228.161              60:45:bd:a3:8d:ac,7c:1e:52:06:89:10  7127926,7127926
Vnet_mac_vni_scale  10.0.0.0/24               10.0.0.1,10.0.0.2                            aa:bb:cc:00:00:01,aa:bb:cc:00:00:02  100,200                    active
                                              10.0.0.3,10.0.0.4                            aa:bb:cc:00:00:03,aa:bb:cc:00:00:04  300,400
                                              10.0.0.5,10.0.0.6                            aa:bb:cc:00:00:05,aa:bb:cc:00:00:06  500,600
Vnet_v6_in_v6-0     fddd:a156:a251::a6:1/128  fddd:a100:a251::a10:1,fddd:a101:a251::a10:1                                                                  active
                                              fddd:a102:a251::a10:1,fddd:a103:a251::a10:1
test_v4_in_v4-0     160.162.191.1/32          100.251.7.1                                                                                                  active
test_v4_in_v4-0     160.163.191.1/32          100.251.7.1                                                                                        0         active
test_v4_in_v4-0     160.164.191.1/32          100.251.7.1
"""
        assert result.output == expected_output

    def test_show_vnet_routes_all_vnetname(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands['vnet'].commands['routes'].commands['all'],
                               ['test_v4_in_v4-0'], obj=db)
        assert result.exit_code == 0
        expected_output = """\
vnet name        prefix            nexthop                                interface
---------------  ----------------  -------------------------------------  -------------------------------
test_v4_in_v4-0  160.162.191.1/32  100.100.4.1                            Ethernet1
test_v4_in_v4-0  160.163.191.1/32  100.101.4.1, 100.101.4.2               Ethernet1, Ethernet2
test_v4_in_v4-0  160.164.191.1/32  100.102.4.1, 100.102.4.2, 100.102.4.3  Ethernet1, Ethernet2, Ethernet3

vnet name        prefix            endpoint     mac address    vni    metric    status
---------------  ----------------  -----------  -------------  -----  --------  --------
test_v4_in_v4-0  160.162.191.1/32  100.251.7.1                                  active
test_v4_in_v4-0  160.163.191.1/32  100.251.7.1                        0         active
test_v4_in_v4-0  160.164.191.1/32  100.251.7.1
"""
        assert result.output == expected_output

    def test_show_vnet_routes_tunnel_basic(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands['vnet'].commands['routes'].commands['tunnel'], [], obj=db)
        assert result.exit_code == 0
        expected_output = """\
vnet name           prefix                    endpoint                                     mac address                          vni              metric    status
------------------  ------------------------  -------------------------------------------  -----------------------------------  ---------------  --------  --------
Vnet_7127926        30.0.20.0/24              100.106.230.44,10.134.85.10                  00:22:48:03:8c:f8,60:45:bd:a3:8d:ab  7127926,7127926  5         active
                                              100.106.229.38,100.106.229.170               60:45:bd:a3:21:88,60:45:bd:a2:e4:39  7127926,7127926
                                              100.106.228.160,10.134.84.24                 7c:1e:52:06:89:0f,7c:1e:52:06:8b:cd  7127926,7127926
                                              100.106.230.168,10.90.92.16                  60:45:bd:a3:8f:ae,60:45:bd:a2:e8:f9  7127926,7127926
                                              10.224.116.42,100.106.228.134                60:45:bd:a2:e5:ee,60:45:bd:a4:be:3e  7127926,7127926
Vnet_7127926        30.0.21.0/24              100.106.230.44,10.134.85.10                  00:22:48:03:8c:f8,60:45:bd:a3:8d:ab  7127926,7127926  5         active
                                              100.106.229.38,100.106.229.170               60:45:bd:a3:21:88,60:45:bd:a2:e4:39  7127926,7127926
                                              100.106.228.160,10.134.84.24                 7c:1e:52:06:89:0f,7c:1e:52:06:8b:cd  7127926,7127926
                                              100.106.230.168,10.90.92.16                  60:45:bd:a3:8f:ae,60:45:bd:a2:e8:f9  7127926,7127926
                                              10.224.116.42,100.106.228.134                60:45:bd:a2:e5:ee,60:45:bd:a4:be:3e  7127926,7127926
                                              100.106.229.171,100.106.228.161              60:45:bd:a3:8d:ac,7c:1e:52:06:89:10  7127926,7127926
Vnet_mac_vni_scale  10.0.0.0/24               10.0.0.1,10.0.0.2                            aa:bb:cc:00:00:01,aa:bb:cc:00:00:02  100,200                    active
                                              10.0.0.3,10.0.0.4                            aa:bb:cc:00:00:03,aa:bb:cc:00:00:04  300,400
                                              10.0.0.5,10.0.0.6                            aa:bb:cc:00:00:05,aa:bb:cc:00:00:06  500,600
Vnet_v6_in_v6-0     fddd:a156:a251::a6:1/128  fddd:a100:a251::a10:1,fddd:a101:a251::a10:1                                                                  active
                                              fddd:a102:a251::a10:1,fddd:a103:a251::a10:1
test_v4_in_v4-0     160.162.191.1/32          100.251.7.1                                                                                                  active
test_v4_in_v4-0     160.163.191.1/32          100.251.7.1                                                                                        0         active
test_v4_in_v4-0     160.164.191.1/32          100.251.7.1
"""
        assert result.output == expected_output

    def test_show_vnet_routes_tunnel_vnetname(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands['vnet'].commands['routes'].commands['tunnel'],
                               ['test_v4_in_v4-0'], obj=db)
        assert result.exit_code == 0
        expected_output = """\
vnet name        prefix            endpoint     mac address    vni    metric    status
---------------  ----------------  -----------  -------------  -----  --------  --------
test_v4_in_v4-0  160.162.191.1/32  100.251.7.1                                  active
test_v4_in_v4-0  160.163.191.1/32  100.251.7.1                        0         active
test_v4_in_v4-0  160.164.191.1/32  100.251.7.1
"""
        assert result.output == expected_output

    def test_show_vnet_routes_local_basic(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands['vnet'].commands['routes'].commands['local'], [], obj=db)
        assert result.exit_code == 0
        expected_output = """\
vnet name        prefix            nexthop                                interface
---------------  ----------------  -------------------------------------  -------------------------------
test_v4_in_v4-0  160.162.191.1/32  100.100.4.1                            Ethernet1
test_v4_in_v4-0  160.163.191.1/32  100.101.4.1, 100.101.4.2               Ethernet1, Ethernet2
test_v4_in_v4-0  160.164.191.1/32  100.102.4.1, 100.102.4.2, 100.102.4.3  Ethernet1, Ethernet2, Ethernet3
test_v4_in_v4-1  160.165.191.1/32  100.103.4.1, 100.103.4.2, 100.103.4.3  Ethernet1, Ethernet2, Ethernet3
"""
        assert result.output == expected_output

    def test_show_vnet_routes_local_vnetname(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands['vnet'].commands['routes'].commands['local'],
                               ['test_v4_in_v4-0'], obj=db)
        assert result.exit_code == 0
        expected_output = """\
vnet name        prefix            nexthop                                interface
---------------  ----------------  -------------------------------------  -------------------------------
test_v4_in_v4-0  160.162.191.1/32  100.100.4.1                            Ethernet1
test_v4_in_v4-0  160.163.191.1/32  100.101.4.1, 100.101.4.2               Ethernet1, Ethernet2
test_v4_in_v4-0  160.164.191.1/32  100.102.4.1, 100.102.4.2, 100.102.4.3  Ethernet1, Ethernet2, Ethernet3
"""
        assert result.output == expected_output

    def test_show_vnet_routes_tunnel_mac_vni_list(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands['vnet'].commands['routes'].commands['tunnel'],
                               ['Vnet_mac_vni_scale'], obj=db)
        assert result.exit_code == 0
        expected_output = """\
vnet name           prefix       endpoint           mac address                          vni      metric    status
------------------  -----------  -----------------  -----------------------------------  -------  --------  --------
Vnet_mac_vni_scale  10.0.0.0/24  10.0.0.1,10.0.0.2  aa:bb:cc:00:00:01,aa:bb:cc:00:00:02  100,200            active
                                 10.0.0.3,10.0.0.4  aa:bb:cc:00:00:03,aa:bb:cc:00:00:04  300,400
                                 10.0.0.5,10.0.0.6  aa:bb:cc:00:00:05,aa:bb:cc:00:00:06  500,600
"""
        assert result.output == expected_output


class TestShowVnetRoutesECMP(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"
        dbconnector.topo = "vnet_ecmp"

    @classmethod
    def teardown_class(cls):
        dbconnector.topo = None

    def test_show_vnet_routes_tunnel_ecmp(self):
        """Test show vnet routes tunnel filtered for a real-world ECMP vnet with 10-12 endpoints."""
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands['vnet'].commands['routes'].commands['tunnel'],
                               ['Vnet_7127926'], obj=db)
        assert result.exit_code == 0
        expected_output = """\
vnet name     prefix        endpoint                         mac address                          vni              metric    status
------------  ------------  -------------------------------  -----------------------------------  ---------------  --------  --------
Vnet_7127926  30.0.20.0/24  100.106.230.44,10.134.85.10      00:22:48:03:8c:f8,60:45:bd:a3:8d:ab  7127926,7127926  5         active
                            100.106.229.38,100.106.229.170   60:45:bd:a3:21:88,60:45:bd:a2:e4:39  7127926,7127926
                            100.106.228.160,10.134.84.24     7c:1e:52:06:89:0f,7c:1e:52:06:8b:cd  7127926,7127926
                            100.106.230.168,10.90.92.16      60:45:bd:a3:8f:ae,60:45:bd:a2:e8:f9  7127926,7127926
                            10.224.116.42,100.106.228.134    60:45:bd:a2:e5:ee,60:45:bd:a4:be:3e  7127926,7127926
Vnet_7127926  30.0.21.0/24  100.106.230.44,10.134.85.10      00:22:48:03:8c:f8,60:45:bd:a3:8d:ab  7127926,7127926  5         active
                            100.106.229.38,100.106.229.170   60:45:bd:a3:21:88,60:45:bd:a2:e4:39  7127926,7127926
                            100.106.228.160,10.134.84.24     7c:1e:52:06:89:0f,7c:1e:52:06:8b:cd  7127926,7127926
                            100.106.230.168,10.90.92.16      60:45:bd:a3:8f:ae,60:45:bd:a2:e8:f9  7127926,7127926
                            10.224.116.42,100.106.228.134    60:45:bd:a2:e5:ee,60:45:bd:a4:be:3e  7127926,7127926
                            100.106.229.171,100.106.228.161  60:45:bd:a3:8d:ac,7c:1e:52:06:89:10  7127926,7127926
"""
        assert result.output == expected_output


class TestShowVnetAdvertisedRoutesIPX(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_show_vnet_adv_routes_ip_basic(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands['vnet'].commands['advertised-routes'], [], obj=db)
        assert result.exit_code == 0
        expected_output = """\
Prefix                    Profile              Community Id
------------------------  -------------------  --------------
160.62.191.1/32           FROM_SDN_SLB_ROUTES  1234:1235
160.63.191.1/32           FROM_SDN_SLB_ROUTES  1234:1235
160.64.191.1/32           FROM_SDN_SLB_ROUTES  1234:1235
fccc:a250:a251::a6:1/128
fddd:a150:a251::a6:1/128  FROM_SDN_SLB_ROUTES  1234:1235
"""
        assert result.output == expected_output

    def test_show_vnet_adv_routes_ip_string(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands['vnet'].commands['advertised-routes'], ['1234:1235'], obj=db)
        assert result.exit_code == 0
        expected_output = """\
Prefix                    Profile              Community Id
------------------------  -------------------  --------------
160.62.191.1/32           FROM_SDN_SLB_ROUTES  1234:1235
160.63.191.1/32           FROM_SDN_SLB_ROUTES  1234:1235
160.64.191.1/32           FROM_SDN_SLB_ROUTES  1234:1235
fddd:a150:a251::a6:1/128  FROM_SDN_SLB_ROUTES  1234:1235
"""
        assert result.output == expected_output

    def test_show_vnet_adv_routes_ipv6_Error(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands['vnet'].commands['advertised-routes'], ['1230:1235'], obj=db)
        assert result.exit_code == 0
        expected_output = """\
Prefix    Profile    Community Id
--------  ---------  --------------
"""
        assert result.output == expected_output

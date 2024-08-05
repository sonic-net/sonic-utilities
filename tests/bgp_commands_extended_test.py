import os
import pytest

from click.testing import CliRunner

import config.main as config
from utilities_common.db import Db

test_path = os.path.dirname(os.path.abspath(__file__))


class TestBgpExtendedCommandsAs(object):
    @classmethod
    def setup_class(cls):
        # print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    @classmethod
    def teardown_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        # print("TEARDOWN")

    # -----------------------------------------------------------------------------------------------------------------------------------
    # config bgp autonomous-system add <as_num>
    # config bgp autonomous-system del <as_num>

    @pytest.mark.parametrize(
        "asn",
        [
            "1",
            "65100",
            "1231231231",
            "4294967295",
        ],
    )
    def test_bgp_config_as_add_del_asn_valid(self, asn):
        db = Db()
        runner = CliRunner()

        # config bgp autonomous-system add <asn>
        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [asn],
            obj=db,
        )
        assert result.exit_code == 0
        assert db.cfgdb.get_table("BGP_GLOBALS")["default"]["local_asn"] == asn

        # config bgp autonomous-system del <asn>
        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["del"],
            [asn],
            obj=db,
        )
        assert result.exit_code == 0
        assert "default" not in db.cfgdb.get_table("BGP_GLOBALS")

    @pytest.mark.parametrize(
        "asn",
        ["0", "4294967296", "string", "32313553434394192138954869547869324129301"],
    )
    def test_bgp_config_as_add_del_asn_invalid(self, asn):
        db = Db()
        runner = CliRunner()

        # config bgp autonomous-system add <asn>
        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [asn],
            obj=db,
        )
        assert result.exit_code != 0
        assert 'Invalid value for "<as_num>"' in result.output

        # config bgp autonomous-system del <asn>
        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["del"],
            [asn],
            obj=db,
        )
        assert result.exit_code != 0
        assert 'Invalid value for "<as_num>"' in result.output

    def test_bgp_config_as_del_asn_nonexistent(self):
        db = Db()
        runner = CliRunner()

        asn = "100"
        # config bgp autonomous-system del <asn>
        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["del"],
            [asn],
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not configured" in result.output


class TestBgpExtentedCommands(object):
    @classmethod
    def setup_class(cls):
        # print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    @classmethod
    def teardown_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        # print("TEARDOWN")

    default_asn = "65100"

    # -----------------------------------------------------------------------------------------------------------------------------------
    # config bgp fast-external-failover <on|off>
    # config bgp default ipv4-unicast <on|off>
    # config bgp client-to-client reflection <on|off>
    # config bgp bestpath compare-routerid <on|off>
    # config bgp bestpath as-path multipath-relax <on|off>
    # config bgp graceful-restart mode <on|off>
    # config bgp graceful-restart preserve-fw-state <on|off>
    # config bgp address-family ipv4 unicast redistribute connected <on|off>
    # config bgp address-family l2vpn evpn advertise-all-vni <on|off>

    def test_bgp_config_fast_external_failover(self):
        db = Db()
        runner = CliRunner()
        cmd = config.config.commands["bgp"].commands["fast-external-failover"]

        # Invalid input
        result = runner.invoke(cmd, ["qwe123qwe"], obj=db)
        assert result.exit_code != 0
        assert 'Invalid value for "<mode>"' in result.output

        # Without configured AS

        # config bgp fast-external-failover on
        result = runner.invoke(cmd, ["on"], obj=db)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp fast-external-failover off
        result = runner.invoke(cmd, ["off"], obj=db)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # With configured AS
        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp fast-external-failover on
        result = runner.invoke(cmd, ["on"], obj=db)
        assert result.exit_code == 0
        assert (
            db.cfgdb.get_table("BGP_GLOBALS")["default"]["fast_external_failover"]
            == "true"
        )

        # config bgp fast-external-failover off
        result = runner.invoke(cmd, ["off"], obj=db)
        assert result.exit_code == 0
        assert (
            db.cfgdb.get_table("BGP_GLOBALS")["default"]["fast_external_failover"]
            == "false"
        )

    def test_bgp_config_default_ipv4_unicast(self):
        db = Db()
        runner = CliRunner()
        cmd = config.config.commands["bgp"].commands["default"].commands["ipv4-unicast"]

        # Invalid input
        result = runner.invoke(cmd, ["qwe123qwe"], obj=db)
        assert result.exit_code != 0
        assert 'Invalid value for "<mode>"' in result.output

        # Without configured AS

        # config bgp default ipv4-unicast on
        result = runner.invoke(cmd, ["on"], obj=db)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp default ipv4-unicast off
        result = runner.invoke(cmd, ["off"], obj=db)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # With configured AS
        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp default ipv4-unicast on
        result = runner.invoke(cmd, ["on"], obj=db)
        assert result.exit_code == 0
        assert (
            db.cfgdb.get_table("BGP_GLOBALS")["default"]["default_ipv4_unicast"]
            == "true"
        )

        # config bgp default ipv4-unicast off
        result = runner.invoke(cmd, ["off"], obj=db)
        assert result.exit_code == 0
        assert (
            db.cfgdb.get_table("BGP_GLOBALS")["default"]["default_ipv4_unicast"]
            == "false"
        )

    def test_bgp_config_client_to_client_reflection(self):
        db = Db()
        runner = CliRunner()
        cmd = (
            config.config.commands["bgp"]
            .commands["client-to-client"]
            .commands["reflection"]
        )

        # Invalid input
        result = runner.invoke(cmd, ["qwe123qwe"], obj=db)
        assert result.exit_code != 0
        assert 'Invalid value for "<mode>"' in result.output

        # Without configured AS

        # config bgp client-to-client reflection on
        result = runner.invoke(cmd, ["on"], obj=db)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp client-to-client reflection off
        result = runner.invoke(cmd, ["off"], obj=db)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # With configured AS
        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp client-to-client reflection on
        result = runner.invoke(cmd, ["on"], obj=db)
        assert result.exit_code == 0
        assert (
            db.cfgdb.get_table("BGP_GLOBALS")["default"]["rr_clnt_to_clnt_reflection"]
            == "true"
        )

        # config bgp client-to-client reflection off
        result = runner.invoke(cmd, ["off"], obj=db)
        assert result.exit_code == 0
        assert (
            db.cfgdb.get_table("BGP_GLOBALS")["default"]["rr_clnt_to_clnt_reflection"]
            == "false"
        )

    def test_bgp_config_bestpath_compare_routerid(self):
        db = Db()
        runner = CliRunner()
        cmd = (
            config.config.commands["bgp"]
            .commands["bestpath"]
            .commands["compare-routerid"]
        )

        # Invalid input
        result = runner.invoke(cmd, ["qwe123qwe"], obj=db)
        assert result.exit_code != 0
        assert 'Invalid value for "<mode>"' in result.output

        # Without configured AS

        # config bgp bestpath compare-routerid on
        result = runner.invoke(cmd, ["on"], obj=db)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp bestpath compare-routerid off
        result = runner.invoke(cmd, ["off"], obj=db)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # With configured AS
        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp bestpath compare-routerid on
        result = runner.invoke(cmd, ["on"], obj=db)
        assert result.exit_code == 0
        assert (
            db.cfgdb.get_table("BGP_GLOBALS")["default"]["external_compare_router_id"]
            == "true"
        )

        # config bgp bestpath compare-routerid off
        result = runner.invoke(cmd, ["off"], obj=db)
        assert result.exit_code == 0
        assert (
            db.cfgdb.get_table("BGP_GLOBALS")["default"]["external_compare_router_id"]
            == "false"
        )

    def test_bgp_config_bestpath_as_path_multipath_relax(self):
        db = Db()
        runner = CliRunner()
        cmd = (
            config.config.commands["bgp"]
            .commands["bestpath"]
            .commands["as-path"]
            .commands["multipath-relax"]
        )

        # Invalid input
        result = runner.invoke(cmd, ["qwe123qwe"], obj=db)
        assert result.exit_code != 0
        assert 'Invalid value for "<mode>"' in result.output

        # Without configured AS

        # config bgp bestpath as-path multipath-relax on
        result = runner.invoke(cmd, ["on"], obj=db)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp bestpath as-path multipath-relax off
        result = runner.invoke(cmd, ["off"], obj=db)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # With configured AS
        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp bestpath as-path multipath-relax on
        result = runner.invoke(cmd, ["on"], obj=db)
        assert result.exit_code == 0
        assert (
            db.cfgdb.get_table("BGP_GLOBALS")["default"]["load_balance_mp_relax"]
            == "true"
        )

        # config bgp bestpath as-path multipath-relax off
        result = runner.invoke(cmd, ["off"], obj=db)
        assert result.exit_code == 0
        assert (
            db.cfgdb.get_table("BGP_GLOBALS")["default"]["load_balance_mp_relax"]
            == "false"
        )

    def test_bgp_config_graceful_restart(self):
        db = Db()
        runner = CliRunner()
        cmd = (
            config.config.commands["bgp"].commands["graceful-restart"].commands["mode"]
        )

        # Invalid input
        result = runner.invoke(cmd, ["qwe123qwe"], obj=db)
        assert result.exit_code != 0
        assert 'Invalid value for "<mode>"' in result.output

        # Without configured AS

        # config bgp graceful-restart mode on
        result = runner.invoke(cmd, ["on"], obj=db)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp graceful-restart mode off
        result = runner.invoke(cmd, ["off"], obj=db)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # With configured AS
        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp graceful-restart mode on
        result = runner.invoke(cmd, ["on"], obj=db)
        assert result.exit_code == 0
        assert (
            db.cfgdb.get_table("BGP_GLOBALS")["default"]["graceful_restart_enable"]
            == "true"
        )

        # config bgp graceful-restart mode off
        result = runner.invoke(cmd, ["off"], obj=db)
        assert result.exit_code == 0
        assert (
            db.cfgdb.get_table("BGP_GLOBALS")["default"]["graceful_restart_enable"]
            == "false"
        )

    def test_bgp_config_graceful_restart_preserve_fw_state(self):
        db = Db()
        runner = CliRunner()
        cmd = (
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["preserve-fw-state"]
        )

        # Invalid input
        result = runner.invoke(cmd, ["qwe123qwe"], obj=db)
        assert result.exit_code != 0
        assert 'Invalid value for "<mode>"' in result.output

        # Without configured AS

        # config bgp graceful-restart preserve-fw-state on
        result = runner.invoke(cmd, ["on"], obj=db)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp graceful-restart preserve-fw-state off
        result = runner.invoke(cmd, ["off"], obj=db)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # With configured AS
        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp graceful-restart preserve-fw-state on
        result = runner.invoke(cmd, ["on"], obj=db)
        assert result.exit_code == 0
        assert (
            db.cfgdb.get_table("BGP_GLOBALS")["default"]["gr_preserve_fw_state"]
            == "true"
        )

        # config bgp graceful-restart preserve-fw-state off
        result = runner.invoke(cmd, ["off"], obj=db)
        assert result.exit_code == 0
        assert (
            db.cfgdb.get_table("BGP_GLOBALS")["default"]["gr_preserve_fw_state"]
            == "false"
        )

    def test_bgp_config_address_family_ipv4_unicast_redistribute_connected(self):
        db = Db()
        runner = CliRunner()
        cmd = (
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["redistribute"]
            .commands["connected"]
        )

        # Invalid input
        result = runner.invoke(cmd, ["qwe123qwe"], obj=db)
        assert result.exit_code != 0
        assert 'Invalid value for "<mode>"' in result.output

        # Without configured AS

        # config bgp address-family ipv4 unicast redistribute connected on
        result = runner.invoke(cmd, ["on"], obj=db)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp address-family ipv4 unicast redistribute connected off
        result = runner.invoke(cmd, ["off"], obj=db)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # With configured AS
        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp address-family ipv4 unicast redistribute connected on
        result = runner.invoke(cmd, ["on"], obj=db)
        assert result.exit_code == 0
        assert ("default", "connected", "bgp", "ipv4") in db.cfgdb.get_table(
            "ROUTE_REDISTRIBUTE"
        )

        # config bgp address-family ipv4 unicast redistribute connected off
        result = runner.invoke(cmd, ["off"], obj=db)
        assert result.exit_code == 0
        assert ("default", "connected", "bgp", "ipv4") not in db.cfgdb.get_table(
            "ROUTE_REDISTRIBUTE"
        )

    def test_bgp_config_address_family_l2vpn_evpn_advertise_all_vni(self):
        db = Db()
        runner = CliRunner()
        cmd = (
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["l2vpn"]
            .commands["evpn"]
            .commands["advertise-all-vni"]
        )

        # Invalid input
        result = runner.invoke(cmd, ["qwe123qwe"], obj=db)
        assert result.exit_code != 0
        assert 'Invalid value for "<mode>"' in result.output

        # Without configured AS

        # config bgp address-family l2vpn evpn advertise-all-vni on
        result = runner.invoke(cmd, ["on"], obj=db)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp address-family l2vpn evpn advertise-all-vni off
        result = runner.invoke(cmd, ["off"], obj=db)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # With configured AS
        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp address-family l2vpn evpn advertise-all-vni on
        result = runner.invoke(cmd, ["on"], obj=db)
        assert result.exit_code == 0
        assert (
            db.cfgdb.get_table("BGP_GLOBALS_AF")[("default", "l2vpn_evpn")][
                "advertise-all-vni"
            ]
            == "true"
        )

        # config bgp address-family l2vpn evpn advertise-all-vni off
        result = runner.invoke(cmd, ["off"], obj=db)
        assert result.exit_code == 0
        assert (
            db.cfgdb.get_table("BGP_GLOBALS_AF")[("default", "l2vpn_evpn")][
                "advertise-all-vni"
            ]
            == "false"
        )

    # -----------------------------------------------------------------------------------------------------------------------------------
    # config bgp router-id add <router_id>
    # config bgp router-id set <router_id>
    # config bgp router-id del <router_id>

    default_router_id = "10.0.0.1"
    router_ids_valid = [
        "127.0.0.1",
        "0.0.0.0",
        "255.255.255.255",
        "192.168.1.1",
        "10.10.0.1",
        "8.8.8.8",
    ]

    @pytest.mark.parametrize("router_id", router_ids_valid)
    def test_bgp_config_router_id_add_del_valid(self, router_id):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp router-id add <router_id>
        result = runner.invoke(
            config.config.commands["bgp"].commands["router-id"].commands["add"],
            [router_id],
            obj=db,
        )
        assert result.exit_code == 0
        assert db.cfgdb.get_table("BGP_GLOBALS")["default"]["router_id"] == router_id

        # config bgp router-id del <router_id>
        result = runner.invoke(
            config.config.commands["bgp"].commands["router-id"].commands["del"],
            [router_id],
            obj=db,
        )
        assert result.exit_code == 0
        assert "router_id" not in db.cfgdb.get_table("BGP_GLOBALS")["default"]

    @pytest.mark.parametrize(
        "router_ids",
        [
            ("192.168.1.1",),
            (
                "192.168.1.1",
                "192.168.1.2",
            ),
            (
                "192.168.1.1",
                "192.168.1.2",
                "192.168.1.3",
            ),
        ],
    )
    def test_bgp_config_router_id_set_valid(self, router_ids):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0
        result = runner.invoke(
            config.config.commands["bgp"].commands["router-id"].commands["add"],
            [self.default_router_id],
            obj=db,
        )
        assert result.exit_code == 0

        for router_id in router_ids:
            # config bgp router-id set <router_id>
            result = runner.invoke(
                config.config.commands["bgp"].commands["router-id"].commands["set"],
                [router_id],
                obj=db,
            )
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_table("BGP_GLOBALS")["default"]["router_id"] == router_id
            )

    @pytest.mark.parametrize(
        "router_id",
        ["192.168.1.1/32", "255.255.255.256", "255.255.255.2567" "0.0.0", "abc"],
    )
    def test_bgp_config_router_id_add_del_set_invalid(self, router_id):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp router-id add <router_id>
        result = runner.invoke(
            config.config.commands["bgp"].commands["router-id"].commands["add"],
            [router_id],
            obj=db,
        )
        assert result.exit_code != 0
        assert "IP address is not valid" in result.output

        # config bgp router-id del <router_id>
        result = runner.invoke(
            config.config.commands["bgp"].commands["router-id"].commands["del"],
            [router_id],
            obj=db,
        )
        assert result.exit_code != 0
        assert "IP address is not valid" in result.output

        result = runner.invoke(
            config.config.commands["bgp"].commands["router-id"].commands["add"],
            [self.default_router_id],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp router-id set <router_id>
        result = runner.invoke(
            config.config.commands["bgp"].commands["router-id"].commands["set"],
            [router_id],
            obj=db,
        )
        assert result.exit_code != 0
        assert "IP address is not valid" in result.output

    @pytest.mark.parametrize("router_id", router_ids_valid)
    def test_bgp_config_router_id_set_del_nonexistent(self, router_id):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp router-id set <router_id>
        result = runner.invoke(
            config.config.commands["bgp"].commands["router-id"].commands["set"],
            [router_id],
            obj=db,
        )
        assert result.exit_code != 0
        assert "Router ID is not configured" in result.output

        # config bgp router-id del <router_id>
        result = runner.invoke(
            config.config.commands["bgp"].commands["router-id"].commands["del"],
            [router_id],
            obj=db,
        )
        assert result.exit_code != 0
        assert "Router ID is not configured" in result.output

    @pytest.mark.parametrize("router_id", router_ids_valid)
    def test_bgp_config_router_id_add_with_existent(self, router_id):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"].commands["router-id"].commands["add"],
            [self.default_router_id],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp router-id add <router_id>
        result = runner.invoke(
            config.config.commands["bgp"].commands["router-id"].commands["add"],
            [router_id],
            obj=db,
        )
        assert result.exit_code != 0
        assert "Router identifier is already specified" in result.output

    @pytest.mark.parametrize("router_id", router_ids_valid)
    def test_bgp_config_router_id_del_wrong(self, router_id):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"].commands["router-id"].commands["add"],
            [self.default_router_id],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp router-id del <router_id>
        result = runner.invoke(
            config.config.commands["bgp"].commands["router-id"].commands["del"],
            [router_id],
            obj=db,
        )
        assert result.exit_code != 0
        assert f"Configured router ID is {self.default_router_id}" in result.output

    @pytest.mark.parametrize("router_id", router_ids_valid)
    def test_bgp_config_router_id_add_set_del_no_as(self, router_id):
        db = Db()
        runner = CliRunner()

        # config bgp router-id add <router_id>
        result = runner.invoke(
            config.config.commands["bgp"].commands["router-id"].commands["add"],
            [router_id],
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp router-id set <router_id>
        result = runner.invoke(
            config.config.commands["bgp"].commands["router-id"].commands["set"],
            [router_id],
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp router-id del <router_id>
        result = runner.invoke(
            config.config.commands["bgp"].commands["router-id"].commands["del"],
            [router_id],
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

    # -----------------------------------------------------------------------------------------------------------------------------------
    # config bgp cluster-id add <cluster_id>
    # config bgp cluster-id set <cluster_id>
    # config bgp cluster-id del <cluster_id>

    default_cluster_id = "10.0.0.1"
    cluster_ids_valid = [
        "127.0.0.1",
        "0.0.0.0",
        "255.255.255.255",
        "192.168.1.1",
        "10.10.0.1",
        "8.8.8.8",
    ]

    @pytest.mark.parametrize("cluster_id", cluster_ids_valid)
    def test_bgp_config_cluster_id_add_del_valid(self, cluster_id):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp cluster-id add <cluster_id>
        result = runner.invoke(
            config.config.commands["bgp"].commands["cluster-id"].commands["add"],
            [cluster_id],
            obj=db,
        )
        assert result.exit_code == 0
        assert (
            db.cfgdb.get_table("BGP_GLOBALS")["default"]["rr_cluster_id"] == cluster_id
        )

        # config bgp cluster-id del <cluster_id>
        result = runner.invoke(
            config.config.commands["bgp"].commands["cluster-id"].commands["del"],
            [cluster_id],
            obj=db,
        )
        assert result.exit_code == 0
        assert "rr_cluster_id" not in db.cfgdb.get_table("BGP_GLOBALS")["default"]

    @pytest.mark.parametrize(
        "cluster_ids",
        [
            ("192.168.1.1",),
            (
                "192.168.1.1",
                "192.168.1.2",
            ),
            (
                "192.168.1.1",
                "192.168.1.2",
                "192.168.1.3",
            ),
        ],
    )
    def test_bgp_config_cluster_id_set_valid(self, cluster_ids):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0
        result = runner.invoke(
            config.config.commands["bgp"].commands["cluster-id"].commands["add"],
            [self.default_cluster_id],
            obj=db,
        )
        assert result.exit_code == 0

        for cluster_id in cluster_ids:
            # config bgp cluster-id set <cluster_id>
            result = runner.invoke(
                config.config.commands["bgp"].commands["cluster-id"].commands["set"],
                [cluster_id],
                obj=db,
            )
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_table("BGP_GLOBALS")["default"]["rr_cluster_id"]
                == cluster_id
            )

    @pytest.mark.parametrize(
        "cluster_id",
        ["192.168.1.1/32", "255.255.255.256", "255.255.255.2567" "0.0.0", "abc"],
    )
    def test_bgp_config_cluster_id_add_del_set_invalid(self, cluster_id):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp cluster-id add <cluster_id>
        result = runner.invoke(
            config.config.commands["bgp"].commands["cluster-id"].commands["add"],
            [cluster_id],
            obj=db,
        )
        assert result.exit_code != 0
        assert "IP address is not valid" in result.output

        # config bgp cluster-id del <cluster_id>
        result = runner.invoke(
            config.config.commands["bgp"].commands["cluster-id"].commands["del"],
            [cluster_id],
            obj=db,
        )
        assert result.exit_code != 0
        assert "IP address is not valid" in result.output

        result = runner.invoke(
            config.config.commands["bgp"].commands["cluster-id"].commands["add"],
            [self.default_cluster_id],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp cluster-id set <cluster_id>
        result = runner.invoke(
            config.config.commands["bgp"].commands["cluster-id"].commands["set"],
            [cluster_id],
            obj=db,
        )
        assert result.exit_code != 0
        assert "IP address is not valid" in result.output

    @pytest.mark.parametrize("cluster_id", cluster_ids_valid)
    def test_bgp_config_cluster_id_set_del_nonexistent(self, cluster_id):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp cluster-id set <cluster_id>
        result = runner.invoke(
            config.config.commands["bgp"].commands["cluster-id"].commands["set"],
            [cluster_id],
            obj=db,
        )
        assert result.exit_code != 0
        assert "Cluster ID is not configured" in result.output

        # config bgp cluster-id del <cluster_id>
        result = runner.invoke(
            config.config.commands["bgp"].commands["cluster-id"].commands["del"],
            [cluster_id],
            obj=db,
        )
        assert result.exit_code != 0
        assert "Cluster ID is not configured" in result.output

    @pytest.mark.parametrize("cluster_id", cluster_ids_valid)
    def test_bgp_config_cluster_id_add_with_existent(self, cluster_id):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"].commands["cluster-id"].commands["add"],
            [self.default_cluster_id],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp cluster-id add <cluster_id>
        result = runner.invoke(
            config.config.commands["bgp"].commands["cluster-id"].commands["add"],
            [cluster_id],
            obj=db,
        )
        assert result.exit_code != 0
        assert "Cluster ID is already added" in result.output

    @pytest.mark.parametrize("cluster_id", cluster_ids_valid)
    def test_bgp_config_cluster_id_del_wrong(self, cluster_id):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"].commands["cluster-id"].commands["add"],
            [self.default_cluster_id],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp cluster-id del <cluster_id>
        result = runner.invoke(
            config.config.commands["bgp"].commands["cluster-id"].commands["del"],
            [cluster_id],
            obj=db,
        )
        assert result.exit_code != 0
        assert f"Configured cluster ID is {self.default_cluster_id}" in result.output

    @pytest.mark.parametrize("cluster_id", cluster_ids_valid)
    def test_bgp_config_cluster_id_add_set_del_no_as(self, cluster_id):
        db = Db()
        runner = CliRunner()

        # config bgp cluster-id add <cluster_id>
        result = runner.invoke(
            config.config.commands["bgp"].commands["cluster-id"].commands["add"],
            [cluster_id],
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp cluster-id set <cluster_id>
        result = runner.invoke(
            config.config.commands["bgp"].commands["cluster-id"].commands["set"],
            [cluster_id],
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp cluster-id del <cluster_id>
        result = runner.invoke(
            config.config.commands["bgp"].commands["cluster-id"].commands["del"],
            [cluster_id],
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

    # -----------------------------------------------------------------------------------------------------------------------------------
    # config bgp listen limit add <limit>
    # config bgp listen limit set <limit>
    # config bgp listen limit del <limit>

    default_listen_limit = "5"
    listen_limits_valid = ["1", "100", "65535"]

    @pytest.mark.parametrize("listen_limit", listen_limits_valid)
    def test_bgp_config_listen_limit_add_del_valid(self, listen_limit):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp listen limit add <listen_limit>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["listen"]
            .commands["limit"]
            .commands["add"],
            [listen_limit],
            obj=db,
        )
        assert result.exit_code == 0
        assert (
            db.cfgdb.get_table("BGP_GLOBALS")["default"]["max_dynamic_neighbors"]
            == listen_limit
        )

        # config bgp listen limit del <listen_limit>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["listen"]
            .commands["limit"]
            .commands["del"],
            [listen_limit],
            obj=db,
        )
        assert result.exit_code == 0
        assert (
            "max_dynamic_neighbors" not in db.cfgdb.get_table("BGP_GLOBALS")["default"]
        )

    @pytest.mark.parametrize(
        "listen_limits",
        [
            ("1",),
            (
                "1",
                "65535",
            ),
            (
                "1",
                "100",
                "65535",
            ),
        ],
    )
    def test_bgp_config_listen_limit_set_valid(self, listen_limits):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["listen"]
            .commands["limit"]
            .commands["add"],
            [self.default_listen_limit],
            obj=db,
        )
        assert result.exit_code == 0

        for listen_limit in listen_limits:
            # config bgp listen limit set <listen_limit>
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["listen"]
                .commands["limit"]
                .commands["set"],
                [listen_limit],
                obj=db,
            )
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_table("BGP_GLOBALS")["default"]["max_dynamic_neighbors"]
                == listen_limit
            )

    @pytest.mark.parametrize("listen_limit", ["0", "65536", "4444444444444444", "abc"])
    def test_bgp_config_listen_limit_add_del_set_invalid(self, listen_limit):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp listen limit add <listen_limit>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["listen"]
            .commands["limit"]
            .commands["add"],
            [listen_limit],
            obj=db,
        )
        assert result.exit_code != 0
        assert 'Invalid value for "<limit>"' in result.output

        # config bgp listen limit del <listen_limit>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["listen"]
            .commands["limit"]
            .commands["del"],
            [listen_limit],
            obj=db,
        )
        assert result.exit_code != 0
        assert 'Invalid value for "<limit>"' in result.output

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["listen"]
            .commands["limit"]
            .commands["add"],
            [self.default_listen_limit],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp listen limit set <listen_limit>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["listen"]
            .commands["limit"]
            .commands["set"],
            [listen_limit],
            obj=db,
        )
        assert result.exit_code != 0
        assert 'Invalid value for "<limit>"' in result.output

    @pytest.mark.parametrize("listen_limit", listen_limits_valid)
    def test_bgp_config_listen_limit_set_del_nonexistent(self, listen_limit):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp listen limit set <listen_limit>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["listen"]
            .commands["limit"]
            .commands["set"],
            [listen_limit],
            obj=db,
        )
        assert result.exit_code != 0
        assert "Listen limit is not configured" in result.output

        # config bgp listen limit del <listen_limit>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["listen"]
            .commands["limit"]
            .commands["del"],
            [listen_limit],
            obj=db,
        )
        assert result.exit_code != 0
        assert "Listen limit is not configured" in result.output

    @pytest.mark.parametrize("listen_limit", listen_limits_valid)
    def test_bgp_config_listen_limit_add_with_existent(self, listen_limit):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["listen"]
            .commands["limit"]
            .commands["add"],
            [self.default_listen_limit],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp listen limit add <listen_limit>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["listen"]
            .commands["limit"]
            .commands["add"],
            [listen_limit],
            obj=db,
        )
        assert result.exit_code != 0
        assert "Listen limit is already specified" in result.output

    @pytest.mark.parametrize("listen_limit", listen_limits_valid)
    def test_bgp_config_listen_limit_del_wrong(self, listen_limit):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["listen"]
            .commands["limit"]
            .commands["add"],
            [self.default_listen_limit],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp listen limit del <listen_limit>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["listen"]
            .commands["limit"]
            .commands["del"],
            [listen_limit],
            obj=db,
        )
        assert result.exit_code != 0
        assert (
            f"Configured listen limit is {self.default_listen_limit}" in result.output
        )

    @pytest.mark.parametrize("listen_limit", listen_limits_valid)
    def test_bgp_config_listen_limit_add_set_del_no_as(self, listen_limit):
        db = Db()
        runner = CliRunner()

        # config bgp listen limit add <listen_limit>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["listen"]
            .commands["limit"]
            .commands["add"],
            [listen_limit],
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp listen limit set <listen_limit>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["listen"]
            .commands["limit"]
            .commands["set"],
            [listen_limit],
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp listen limit del <listen_limit>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["listen"]
            .commands["limit"]
            .commands["del"],
            [listen_limit],
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

    # -----------------------------------------------------------------------------------------------------------------------------------
    # config bgp graceful-restart restart-time add <time>
    # config bgp graceful-restart restart-time set <time>
    # config bgp graceful-restart restart-time del <time>

    default_restart_time = "1"
    restart_times_valid = ["0", "100", "4095"]

    @pytest.mark.parametrize("restart_time", restart_times_valid)
    def test_bgp_config_graceful_restart_restart_time_add_del_valid(self, restart_time):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp graceful-restart restart-time add <time>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["restart-time"]
            .commands["add"],
            [restart_time],
            obj=db,
        )
        assert result.exit_code == 0
        assert (
            db.cfgdb.get_table("BGP_GLOBALS")["default"]["gr_restart_time"]
            == restart_time
        )

        # config bgp graceful-restart restart-time del <time>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["restart-time"]
            .commands["del"],
            [restart_time],
            obj=db,
        )
        assert result.exit_code == 0
        assert "gr_restart_time" not in db.cfgdb.get_table("BGP_GLOBALS")["default"]

    @pytest.mark.parametrize(
        "restart_times",
        [
            ("0",),
            (
                "0",
                "4095",
            ),
            (
                "0",
                "100",
                "4095",
            ),
        ],
    )
    def test_bgp_config_graceful_restart_restart_time_set_valid(self, restart_times):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["restart-time"]
            .commands["add"],
            [self.default_restart_time],
            obj=db,
        )
        assert result.exit_code == 0

        for restart_time in restart_times:
            # config bgp graceful-restart restart-time set <time>
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["graceful-restart"]
                .commands["restart-time"]
                .commands["set"],
                [restart_time],
                obj=db,
            )
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_table("BGP_GLOBALS")["default"]["gr_restart_time"]
                == restart_time
            )

    @pytest.mark.parametrize("restart_time", ["4096", "4444444444444444", "abc"])
    def test_bgp_config_graceful_restart_restart_time_add_del_set_invalid(
        self, restart_time
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp graceful-restart restart-time add <time>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["restart-time"]
            .commands["add"],
            [restart_time],
            obj=db,
        )
        assert result.exit_code != 0
        assert 'Invalid value for "<time>"' in result.output

        # config bgp graceful-restart restart-time del <time>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["restart-time"]
            .commands["del"],
            [restart_time],
            obj=db,
        )
        assert result.exit_code != 0
        assert 'Invalid value for "<time>"' in result.output

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["restart-time"]
            .commands["add"],
            [self.default_restart_time],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp graceful-restart restart-time set <time>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["restart-time"]
            .commands["set"],
            [restart_time],
            obj=db,
        )
        assert result.exit_code != 0
        assert 'Invalid value for "<time>"' in result.output

    @pytest.mark.parametrize("restart_time", restart_times_valid)
    def test_bgp_config_graceful_restart_restart_time_set_del_nonexistent(
        self, restart_time
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp graceful-restart restart-time set <time>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["restart-time"]
            .commands["set"],
            [restart_time],
            obj=db,
        )
        assert result.exit_code != 0
        assert "Graceful restart time is not configured" in result.output

        # config bgp graceful-restart restart-time del <time>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["restart-time"]
            .commands["del"],
            [restart_time],
            obj=db,
        )
        assert result.exit_code != 0
        assert "Graceful restart time is not configured" in result.output

    @pytest.mark.parametrize("restart_time", restart_times_valid)
    def test_bgp_config_graceful_restart_restart_time_add_with_existent(
        self, restart_time
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["restart-time"]
            .commands["add"],
            [self.default_restart_time],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp graceful-restart restart-time add <time>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["restart-time"]
            .commands["add"],
            [restart_time],
            obj=db,
        )
        assert result.exit_code != 0
        assert "Graceful restart time is already specified" in result.output

    @pytest.mark.parametrize("restart_time", restart_times_valid)
    def test_bgp_config_graceful_restart_restart_time_del_wrong(self, restart_time):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["restart-time"]
            .commands["add"],
            [self.default_restart_time],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp graceful-restart restart-time del <time>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["restart-time"]
            .commands["del"],
            [restart_time],
            obj=db,
        )
        assert result.exit_code != 0
        assert (
            f"Configured graceful restart time is {self.default_restart_time}"
            in result.output
        )

    @pytest.mark.parametrize("restart_time", restart_times_valid)
    def test_bgp_config_graceful_restart_restart_time_add_set_del_no_as(
        self, restart_time
    ):
        db = Db()
        runner = CliRunner()

        # config bgp graceful-restart restart-time add <time>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["restart-time"]
            .commands["add"],
            [restart_time],
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp graceful-restart restart-time set <time>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["restart-time"]
            .commands["set"],
            [restart_time],
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp graceful-restart restart-time del <time>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["restart-time"]
            .commands["del"],
            [restart_time],
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

    # -----------------------------------------------------------------------------------------------------------------------------------
    # config bgp graceful-restart stalepath-time add <time>
    # config bgp graceful-restart stalepath-time set <time>
    # config bgp graceful-restart stalepath-time del <time>

    default_stalepath_time = "5"
    stalepath_times_valid = ["1", "100", "4095"]

    @pytest.mark.parametrize("stalepath_time", stalepath_times_valid)
    def test_bgp_config_graceful_restart_stalepath_time_add_del_valid(
        self, stalepath_time
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp graceful-restart stalepath-time add <time>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["stalepath-time"]
            .commands["add"],
            [stalepath_time],
            obj=db,
        )
        assert result.exit_code == 0
        assert (
            db.cfgdb.get_table("BGP_GLOBALS")["default"]["gr_stale_routes_time"]
            == stalepath_time
        )

        # config bgp graceful-restart stalepath-time del <time>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["stalepath-time"]
            .commands["del"],
            [stalepath_time],
            obj=db,
        )
        assert result.exit_code == 0
        assert (
            "gr_stale_routes_time" not in db.cfgdb.get_table("BGP_GLOBALS")["default"]
        )

    @pytest.mark.parametrize(
        "stalepath_times",
        [
            ("1",),
            (
                "1",
                "4095",
            ),
            (
                "1",
                "100",
                "4095",
            ),
        ],
    )
    def test_bgp_config_graceful_restart_stalepath_time_set_valid(
        self, stalepath_times
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["stalepath-time"]
            .commands["add"],
            [self.default_stalepath_time],
            obj=db,
        )
        assert result.exit_code == 0

        for stalepath_time in stalepath_times:
            # config bgp graceful-restart stalepath-time set <time>
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["graceful-restart"]
                .commands["stalepath-time"]
                .commands["set"],
                [stalepath_time],
                obj=db,
            )
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_table("BGP_GLOBALS")["default"]["gr_stale_routes_time"]
                == stalepath_time
            )

    @pytest.mark.parametrize("stalepath_time", ["4096", "4444444444444444", "abc"])
    def test_bgp_config_graceful_restart_stalepath_time_add_del_set_invalid(
        self, stalepath_time
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp graceful-restart stalepath-time add <time>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["stalepath-time"]
            .commands["add"],
            [stalepath_time],
            obj=db,
        )
        assert result.exit_code != 0
        assert 'Invalid value for "<time>"' in result.output

        # config bgp graceful-restart stalepath-time del <time>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["stalepath-time"]
            .commands["del"],
            [stalepath_time],
            obj=db,
        )
        assert result.exit_code != 0
        assert 'Invalid value for "<time>"' in result.output

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["stalepath-time"]
            .commands["add"],
            [self.default_stalepath_time],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp graceful-restart stalepath-time set <time>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["stalepath-time"]
            .commands["set"],
            [stalepath_time],
            obj=db,
        )
        assert result.exit_code != 0
        assert 'Invalid value for "<time>"' in result.output

    @pytest.mark.parametrize("stalepath_time", stalepath_times_valid)
    def test_bgp_config_graceful_restart_stalepath_time_set_del_nonexistent(
        self, stalepath_time
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp graceful-restart stalepath-time set <time>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["stalepath-time"]
            .commands["set"],
            [stalepath_time],
            obj=db,
        )
        assert result.exit_code != 0
        assert "Graceful restart stalepath time is not configured" in result.output

        # config bgp graceful-restart stalepath-time del <time>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["stalepath-time"]
            .commands["del"],
            [stalepath_time],
            obj=db,
        )
        assert result.exit_code != 0
        assert "Graceful restart stalepath time is not configured" in result.output

    @pytest.mark.parametrize("stalepath_time", stalepath_times_valid)
    def test_bgp_config_graceful_restart_stalepath_time_add_with_existent(
        self, stalepath_time
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["stalepath-time"]
            .commands["add"],
            [self.default_stalepath_time],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp graceful-restart stalepath-time add <time>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["stalepath-time"]
            .commands["add"],
            [stalepath_time],
            obj=db,
        )
        assert result.exit_code != 0
        assert "Graceful restart stalepath time is already specified" in result.output

    @pytest.mark.parametrize("stalepath_time", stalepath_times_valid)
    def test_bgp_config_graceful_restart_stalepath_time_del_wrong(self, stalepath_time):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["stalepath-time"]
            .commands["add"],
            [self.default_stalepath_time],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp graceful-restart stalepath-time del <time>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["stalepath-time"]
            .commands["del"],
            [stalepath_time],
            obj=db,
        )
        assert result.exit_code != 0
        assert (
            f"Configured graceful restart stalepath time is {self.default_stalepath_time}"
            in result.output
        )

    @pytest.mark.parametrize("stalepath_time", stalepath_times_valid)
    def test_bgp_config_graceful_restart_stalepath_time_add_set_del_no_as(
        self, stalepath_time
    ):
        db = Db()
        runner = CliRunner()

        # config bgp graceful-restart stalepath-time add <time>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["stalepath-time"]
            .commands["add"],
            [stalepath_time],
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp graceful-restart stalepath-time set <time>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["stalepath-time"]
            .commands["set"],
            [stalepath_time],
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp graceful-restart stalepath-time del <time>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["graceful-restart"]
            .commands["stalepath-time"]
            .commands["del"],
            [stalepath_time],
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

    # -----------------------------------------------------------------------------------------------------------------------------------
    # config bgp address-family ipv4 unicast max-paths add <paths_num>
    # config bgp address-family ipv4 unicast max-paths set <paths_num>
    # config bgp address-family ipv4 unicast max-paths del <paths_num>

    default_paths_num = "5"
    paths_nums_valid = ["1", "100", "256"]

    @pytest.mark.parametrize("paths_num", paths_nums_valid)
    def test_bgp_config_address_family_ipv4_unicast_max_paths_add_del_valid(
        self, paths_num
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp address-family ipv4 unicast max-paths add <paths_num>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["add"],
            [paths_num],
            obj=db,
        )
        assert result.exit_code == 0
        assert (
            db.cfgdb.get_table("BGP_GLOBALS_AF")[("default", "ipv4_unicast")][
                "max_ebgp_paths"
            ]
            == paths_num
        )

        # config bgp address-family ipv4 unicast max-paths del <paths_num>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["del"],
            [paths_num],
            obj=db,
        )
        assert result.exit_code == 0
        assert (
            "max_ebgp_paths"
            not in db.cfgdb.get_table("BGP_GLOBALS_AF")[("default", "ipv4_unicast")]
        )

    @pytest.mark.parametrize(
        "paths_nums",
        [
            ("1",),
            (
                "1",
                "256",
            ),
            (
                "1",
                "100",
                "256",
            ),
        ],
    )
    def test_bgp_config_address_family_ipv4_unicast_max_paths_set_valid(
        self, paths_nums
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["add"],
            [self.default_paths_num],
            obj=db,
        )
        assert result.exit_code == 0

        for paths_num in paths_nums:
            # config bgp address-family ipv4 unicast max-paths set <paths_num>
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["address-family"]
                .commands["ipv4"]
                .commands["unicast"]
                .commands["max-paths"]
                .commands["set"],
                [paths_num],
                obj=db,
            )
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_table("BGP_GLOBALS_AF")[("default", "ipv4_unicast")][
                    "max_ebgp_paths"
                ]
                == paths_num
            )

    @pytest.mark.parametrize("paths_num", ["0", "257", "4444444444444444", "abc"])
    def test_bgp_config_address_family_ipv4_unicast_max_paths_add_del_set_invalid(
        self, paths_num
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp address-family ipv4 unicast max-paths add <paths_num>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["add"],
            [paths_num],
            obj=db,
        )
        assert result.exit_code != 0
        assert 'Invalid value for "<paths_num>"' in result.output

        # config bgp address-family ipv4 unicast max-paths del <paths_num>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["del"],
            [paths_num],
            obj=db,
        )
        assert result.exit_code != 0
        assert 'Invalid value for "<paths_num>"' in result.output

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["add"],
            [self.default_paths_num],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp address-family ipv4 unicast max-paths set <paths_num>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["set"],
            [paths_num],
            obj=db,
        )
        assert result.exit_code != 0
        assert 'Invalid value for "<paths_num>"' in result.output

    @pytest.mark.parametrize("paths_num", paths_nums_valid)
    def test_bgp_config_address_family_ipv4_unicast_max_paths_set_del_nonexistent(
        self, paths_num
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp address-family ipv4 unicast max-paths set <paths_num>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["set"],
            [paths_num],
            obj=db,
        )
        assert result.exit_code != 0
        assert "Max-paths number is not configured" in result.output

        # config bgp address-family ipv4 unicast max-paths del <paths_num>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["del"],
            [paths_num],
            obj=db,
        )
        assert result.exit_code != 0
        assert "Max-paths number is not configured" in result.output

    @pytest.mark.parametrize("paths_num", paths_nums_valid)
    def test_bgp_config_address_family_ipv4_unicast_max_paths_add_with_existent(
        self, paths_num
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["add"],
            [self.default_paths_num],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp address-family ipv4 unicast max-paths add <paths_num>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["add"],
            [paths_num],
            obj=db,
        )
        assert result.exit_code != 0
        assert "Max paths number is already specified" in result.output

    @pytest.mark.parametrize("paths_num", paths_nums_valid)
    def test_bgp_config_address_family_ipv4_unicast_max_paths_del_wrong(
        self, paths_num
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["add"],
            [self.default_paths_num],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp address-family ipv4 unicast max-paths del <paths_num>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["del"],
            [paths_num],
            obj=db,
        )
        assert result.exit_code != 0
        assert (
            f"Configured max-paths number is {self.default_paths_num}" in result.output
        )

    @pytest.mark.parametrize("paths_num", paths_nums_valid)
    def test_bgp_config_address_family_ipv4_unicast_max_paths_add_set_del_no_as(
        self, paths_num
    ):
        db = Db()
        runner = CliRunner()

        # config bgp address-family ipv4 unicast max-paths add <paths_num>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["add"],
            [paths_num],
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp address-family ipv4 unicast max-paths set <paths_num>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["set"],
            [paths_num],
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp address-family ipv4 unicast max-paths del <paths_num>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["del"],
            [paths_num],
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

    # -----------------------------------------------------------------------------------------------------------------------------------
    # config bgp address-family ipv4 unicast max-paths ibgp add <paths_num> [--equal-cluster-length]
    # config bgp address-family ipv4 unicast max-paths ibgp set <paths_num> [--equal-cluster-length]
    # config bgp address-family ipv4 unicast max-paths ibgp del <paths_num>

    default_paths_num = "5"
    paths_nums_valid = ["1", "100", "256"]

    @pytest.mark.parametrize("paths_num", paths_nums_valid)
    def test_bgp_config_address_family_ipv4_unicast_max_paths_ibgp_add_del_valid(
        self, paths_num
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp address-family ipv4 unicast max-paths add <paths_num>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["ibgp"]
            .commands["add"],
            [paths_num],
            obj=db,
        )
        assert result.exit_code == 0
        assert (
            db.cfgdb.get_table("BGP_GLOBALS_AF")[("default", "ipv4_unicast")][
                "max_ibgp_paths"
            ]
            == paths_num
        )

        # config bgp address-family ipv4 unicast max-paths del <paths_num>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["ibgp"]
            .commands["del"],
            [paths_num],
            obj=db,
        )
        assert result.exit_code == 0
        assert (
            "max_ibgp_paths"
            not in db.cfgdb.get_table("BGP_GLOBALS_AF")[("default", "ipv4_unicast")]
        )

    @pytest.mark.parametrize(
        "paths_nums",
        [
            ("1",),
            (
                "1",
                "256",
            ),
            (
                "1",
                "100",
                "256",
            ),
        ],
    )
    def test_bgp_config_address_family_ipv4_unicast_max_paths_ibgp_set_valid(
        self, paths_nums
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["ibgp"]
            .commands["add"],
            [self.default_paths_num],
            obj=db,
        )
        assert result.exit_code == 0

        for paths_num in paths_nums:
            # config bgp address-family ipv4 unicast max-paths set <paths_num>
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["address-family"]
                .commands["ipv4"]
                .commands["unicast"]
                .commands["max-paths"]
                .commands["ibgp"]
                .commands["set"],
                [paths_num],
                obj=db,
            )
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_table("BGP_GLOBALS_AF")[("default", "ipv4_unicast")][
                    "max_ibgp_paths"
                ]
                == paths_num
            )

    @pytest.mark.parametrize("paths_num", ["0", "257", "4444444444444444", "abc"])
    def test_bgp_config_address_family_ipv4_unicast_max_paths_ibgp_add_del_set_invalid(
        self, paths_num
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp address-family ipv4 unicast max-paths add <paths_num>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["ibgp"]
            .commands["add"],
            [paths_num],
            obj=db,
        )
        assert result.exit_code != 0
        assert 'Invalid value for "<paths_num>"' in result.output

        # config bgp address-family ipv4 unicast max-paths del <paths_num>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["ibgp"]
            .commands["del"],
            [paths_num],
            obj=db,
        )
        assert result.exit_code != 0
        assert 'Invalid value for "<paths_num>"' in result.output

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["ibgp"]
            .commands["add"],
            [self.default_paths_num],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp address-family ipv4 unicast max-paths set <paths_num>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["ibgp"]
            .commands["set"],
            [paths_num],
            obj=db,
        )
        assert result.exit_code != 0
        assert 'Invalid value for "<paths_num>"' in result.output

    @pytest.mark.parametrize("paths_num", paths_nums_valid)
    def test_bgp_config_address_family_ipv4_unicast_max_paths_ibgp_set_del_nonexistent(
        self, paths_num
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp address-family ipv4 unicast max-paths set <paths_num>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["ibgp"]
            .commands["set"],
            [paths_num],
            obj=db,
        )
        assert result.exit_code != 0
        assert "Max-paths ibgp number is not configured" in result.output

        # config bgp address-family ipv4 unicast max-paths del <paths_num>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["ibgp"]
            .commands["del"],
            [paths_num],
            obj=db,
        )
        assert result.exit_code != 0
        assert "Max-paths ibgp number is not configured" in result.output

    @pytest.mark.parametrize("paths_num", paths_nums_valid)
    def test_bgp_config_address_family_ipv4_unicast_max_paths_ibgp_add_with_existent(
        self, paths_num
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["ibgp"]
            .commands["add"],
            [self.default_paths_num],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp address-family ipv4 unicast max-paths add <paths_num>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["ibgp"]
            .commands["add"],
            [paths_num],
            obj=db,
        )
        assert result.exit_code != 0
        assert "Max ibgp paths number is already specified" in result.output

    @pytest.mark.parametrize("paths_num", paths_nums_valid)
    def test_bgp_config_address_family_ipv4_unicast_max_paths_ibgp_del_wrong(
        self, paths_num
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["ibgp"]
            .commands["add"],
            [self.default_paths_num],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp address-family ipv4 unicast max-paths del <paths_num>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["ibgp"]
            .commands["del"],
            [paths_num],
            obj=db,
        )
        assert result.exit_code != 0
        assert (
            f"Configured max-paths ibgp number is {self.default_paths_num}"
            in result.output
        )

    @pytest.mark.parametrize("paths_num", paths_nums_valid)
    def test_bgp_config_address_family_ipv4_unicast_max_paths_ibgp_add_set_del_no_as(
        self, paths_num
    ):
        db = Db()
        runner = CliRunner()

        # config bgp address-family ipv4 unicast max-paths add <paths_num>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["ibgp"]
            .commands["add"],
            [paths_num],
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp address-family ipv4 unicast max-paths set <paths_num>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["ibgp"]
            .commands["set"],
            [paths_num],
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp address-family ipv4 unicast max-paths del <paths_num>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["max-paths"]
            .commands["ibgp"]
            .commands["del"],
            [paths_num],
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

    # -----------------------------------------------------------------------------------------------------------------------------------
    # config bgp address-family ipv4 unicast distance bgp add <ebgp_dist> <ibgp_dist> <local_dist>
    # config bgp address-family ipv4 unicast distance bgp set <ebgp_dist> <ibgp_dist> <local_dist>
    # config bgp address-family ipv4 unicast distance bgp del <ebgp_dist> <ibgp_dist> <local_dist>

    default_distances = ["5", "5", "5"]
    distances_valid = [["1", "1", "1"], ["100", "100", "100"], ["255", "255", "255"]]

    @pytest.mark.parametrize("distances", distances_valid)
    def test_bgp_config_address_family_ipv4_unicast_distance_bgp_add_del_valid(
        self, distances
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp address-family ipv4 unicast distance bgp add <ebgp_dist> <ibgp_dist> <local_dist>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["distance"]
            .commands["bgp"]
            .commands["add"],
            distances,
            obj=db,
        )
        assert result.exit_code == 0
        assert (
            db.cfgdb.get_table("BGP_GLOBALS_AF")[("default", "ipv4_unicast")][
                "ebgp_route_distance"
            ]
            == distances[0]
            and db.cfgdb.get_table("BGP_GLOBALS_AF")[("default", "ipv4_unicast")][
                "ibgp_route_distance"
            ]
            == distances[1]
            and db.cfgdb.get_table("BGP_GLOBALS_AF")[("default", "ipv4_unicast")][
                "local_route_distance"
            ]
            == distances[2]
        )

        # config bgp address-family ipv4 unicast distance bgp del <ebgp_dist> <ibgp_dist> <local_dist>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["distance"]
            .commands["bgp"]
            .commands["del"],
            distances,
            obj=db,
        )
        assert result.exit_code == 0
        assert (
            "ebgp_route_distance"
            not in db.cfgdb.get_table("BGP_GLOBALS_AF")[("default", "ipv4_unicast")]
            and "ibgp_route_distance"
            not in db.cfgdb.get_table("BGP_GLOBALS_AF")[("default", "ipv4_unicast")]
            and "local_route_distance"
            not in db.cfgdb.get_table("BGP_GLOBALS_AF")[("default", "ipv4_unicast")]
        )

    @pytest.mark.parametrize(
        "distances_sets",
        [
            (["1", "1", "1"],),
            (
                ["1", "1", "1"],
                ["255", "255", "255"],
            ),
            (
                ["1", "1", "1"],
                ["100", "100", "100"],
                ["255", "255", "255"],
            ),
        ],
    )
    def test_bgp_config_address_family_ipv4_unicast_distance_bgp_set_valid(
        self, distances_sets
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["distance"]
            .commands["bgp"]
            .commands["add"],
            self.default_distances,
            obj=db,
        )
        assert result.exit_code == 0

        for distances in distances_sets:
            # config bgp address-family ipv4 unicast distance bgp set <ebgp_dist> <ibgp_dist> <local_dist>
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["address-family"]
                .commands["ipv4"]
                .commands["unicast"]
                .commands["distance"]
                .commands["bgp"]
                .commands["set"],
                distances,
                obj=db,
            )
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_table("BGP_GLOBALS_AF")[("default", "ipv4_unicast")][
                    "ebgp_route_distance"
                ]
                == distances[0]
                and db.cfgdb.get_table("BGP_GLOBALS_AF")[("default", "ipv4_unicast")][
                    "ibgp_route_distance"
                ]
                == distances[1]
                and db.cfgdb.get_table("BGP_GLOBALS_AF")[("default", "ipv4_unicast")][
                    "local_route_distance"
                ]
                == distances[2]
            )

    @pytest.mark.parametrize(
        "distances",
        [
            ["0", "0", "0"],
            ["256", "256", "256"],
            ["4444444444444444", "4444444444444444", "4444444444444444"],
            ["abc", "abc", "abc"],
        ],
    )
    def test_bgp_config_address_family_ipv4_unicast_distance_bgp_add_del_set_invalid(
        self, distances
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp address-family ipv4 unicast distance bgp add <ebgp_dist> <ibgp_dist> <local_dist>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["distance"]
            .commands["bgp"]
            .commands["add"],
            distances,
            obj=db,
        )
        assert result.exit_code != 0
        assert (
            'Invalid value for "<ebgp_dist>"' in result.output
            or 'Invalid value for "<ibgp_dist>"' in result.output
            or 'Invalid value for "<local_dist>"' in result.output
        )

        # config bgp address-family ipv4 unicast distance bgp del <ebgp_dist> <ibgp_dist> <local_dist>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["distance"]
            .commands["bgp"]
            .commands["del"],
            distances,
            obj=db,
        )
        assert result.exit_code != 0
        assert (
            'Invalid value for "<ebgp_dist>"' in result.output
            or 'Invalid value for "<ibgp_dist>"' in result.output
            or 'Invalid value for "<local_dist>"' in result.output
        )

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["distance"]
            .commands["bgp"]
            .commands["add"],
            self.default_distances,
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp address-family ipv4 unicast distance bgp set <ebgp_dist> <ibgp_dist> <local_dist>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["distance"]
            .commands["bgp"]
            .commands["set"],
            distances,
            obj=db,
        )
        assert result.exit_code != 0
        assert (
            'Invalid value for "<ebgp_dist>"' in result.output
            or 'Invalid value for "<ibgp_dist>"' in result.output
            or 'Invalid value for "<local_dist>"' in result.output
        )

    @pytest.mark.parametrize("distances", distances_valid)
    def test_bgp_config_address_family_ipv4_unicast_distance_bgp_set_del_nonexistent(
        self, distances
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp address-family ipv4 unicast distance bgp set <ebgp_dist> <ibgp_dist> <local_dist>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["distance"]
            .commands["bgp"]
            .commands["set"],
            distances,
            obj=db,
        )
        assert result.exit_code != 0
        assert "Distance bgp values are not configured" in result.output

        # config bgp address-family ipv4 unicast distance bgp del <ebgp_dist> <ibgp_dist> <local_dist>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["distance"]
            .commands["bgp"]
            .commands["del"],
            distances,
            obj=db,
        )
        assert result.exit_code != 0
        assert "Distance bgp values are not configured" in result.output

    @pytest.mark.parametrize("distances", distances_valid)
    def test_bgp_config_address_family_ipv4_unicast_distance_bgp_add_with_existent(
        self, distances
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["distance"]
            .commands["bgp"]
            .commands["add"],
            self.default_distances,
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp address-family ipv4 unicast distance bgp add <ebgp_dist> <ibgp_dist> <local_dist>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["distance"]
            .commands["bgp"]
            .commands["add"],
            distances,
            obj=db,
        )
        assert result.exit_code != 0
        assert "BGP distance values are already configured" in result.output

    @pytest.mark.parametrize("distances", distances_valid)
    def test_bgp_config_address_family_ipv4_unicast_distance_bgp_del_wrong(
        self, distances
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["distance"]
            .commands["bgp"]
            .commands["add"],
            self.default_distances,
            obj=db,
        )
        assert result.exit_code == 0

        # config bgp address-family ipv4 unicast distance bgp del <ebgp_dist> <ibgp_dist> <local_dist>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["distance"]
            .commands["bgp"]
            .commands["del"],
            distances,
            obj=db,
        )
        assert result.exit_code != 0
        assert (
            "Configured distance bgp values are " + " ".join(self.default_distances)
            in result.output
        )

    @pytest.mark.parametrize("distances", distances_valid)
    def test_bgp_config_address_family_ipv4_unicast_distance_bgp_add_set_del_no_as(
        self, distances
    ):
        db = Db()
        runner = CliRunner()

        # config bgp address-family ipv4 unicast distance bgp add <ebgp_dist> <ibgp_dist> <local_dist>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["distance"]
            .commands["bgp"]
            .commands["add"],
            distances,
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp address-family ipv4 unicast distance bgp set <ebgp_dist> <ibgp_dist> <local_dist>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["distance"]
            .commands["bgp"]
            .commands["set"],
            distances,
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp address-family ipv4 unicast distance bgp del <ebgp_dist> <ibgp_dist> <local_dist>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["distance"]
            .commands["bgp"]
            .commands["del"],
            distances,
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

    # -----------------------------------------------------------------------------------------------------------------------------------
    # config bgp address-family ipv4 unicast network add <network>
    # config bgp address-family ipv4 unicast network del <network>

    networks_valid = [
        ("127.0.0.1",),
        (
            "10.0.0.1",
            "10.0.0.2/32",
            "10.10.10.0/24",
        ),
        ("0.0.0.0", "255.255.255.255"),
        (
            "8.8.8.8",
            "8.8.4.4/32",
            "1.1.1.1",
        ),
    ]

    @pytest.mark.parametrize("networks", networks_valid)
    def test_bgp_config_address_family_ipv4_unicast_network_add_del_valid(
        self, networks
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        for network in networks:
            # config bgp address-family ipv4 unicast network add <network>
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["address-family"]
                .commands["ipv4"]
                .commands["unicast"]
                .commands["network"]
                .commands["add"],
                [network],
                obj=db,
            )
            assert result.exit_code == 0

            if "/" not in network:
                network = network + "/32"

            assert ("default", "ipv4_unicast", network) in db.cfgdb.get_table(
                "BGP_GLOBALS_AF_NETWORK"
            )

        for network in networks:
            # config bgp address-family ipv4 unicast network del <network>
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["address-family"]
                .commands["ipv4"]
                .commands["unicast"]
                .commands["network"]
                .commands["del"],
                [network],
                obj=db,
            )
            assert result.exit_code == 0

            if "/" not in network:
                network = network + "/32"

            assert ("default", "ipv4_unicast", network) not in db.cfgdb.get_table(
                "BGP_GLOBALS_AF_NETWORK"
            )

    @pytest.mark.parametrize(
        "networks",
        [
            ("256.0.0.0",),
            (
                "10.0.0.1/24",
                "10.0.0.2/0",
                "10.10.10.0/33",
            ),
            ("0.0.0.0.0", "0x0a0000a0"),
            (
                "8.8.8",
                "qweqweqwe",
                "0.0.0.0\\16",
            ),
        ],
    )
    def test_bgp_config_address_family_ipv4_unicast_network_add_del_invalid(
        self, networks
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        for network in networks:
            # config bgp address-family ipv4 unicast network add <network>
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["address-family"]
                .commands["ipv4"]
                .commands["unicast"]
                .commands["network"]
                .commands["add"],
                [network],
                obj=db,
            )
            assert result.exit_code != 0
            assert "Network address is not valid" in result.output

        for network in networks:
            # config bgp address-family ipv4 unicast network del <network>
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["address-family"]
                .commands["ipv4"]
                .commands["unicast"]
                .commands["network"]
                .commands["del"],
                [network],
                obj=db,
            )
            assert result.exit_code != 0
            assert "Network address is not valid" in result.output

    @pytest.mark.parametrize("networks", networks_valid)
    def test_bgp_config_address_family_ipv4_unicast_network_del_nonexistent(
        self, networks
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        for network in networks:
            # config bgp address-family ipv4 unicast network del <network>
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["address-family"]
                .commands["ipv4"]
                .commands["unicast"]
                .commands["network"]
                .commands["del"],
                [network],
                obj=db,
            )
            assert result.exit_code != 0
            assert "IPv4 unicast network does not exist" in result.output

    @pytest.mark.parametrize("networks", networks_valid)
    def test_bgp_config_address_family_ipv4_unicast_network_add_existent(
        self, networks
    ):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            [self.default_asn],
            obj=db,
        )
        assert result.exit_code == 0

        for network in networks:
            # config bgp address-family ipv4 unicast network add <network>
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["address-family"]
                .commands["ipv4"]
                .commands["unicast"]
                .commands["network"]
                .commands["add"],
                [network],
                obj=db,
            )
            assert result.exit_code == 0

            if "/" not in network:
                network = network + "/32"

            assert ("default", "ipv4_unicast", network) in db.cfgdb.get_table(
                "BGP_GLOBALS_AF_NETWORK"
            )

            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["address-family"]
                .commands["ipv4"]
                .commands["unicast"]
                .commands["network"]
                .commands["add"],
                [network],
                obj=db,
            )
            assert result.exit_code != 0
            assert "IPv4 unicast network already exists" in result.output

    def test_bgp_config_address_family_ipv4_unicast_network_add_del_no_as(self):
        db = Db()
        runner = CliRunner()

        network = "1.2.3.4"

        # config bgp address-family ipv4 unicast network add <network>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["network"]
            .commands["add"],
            [network],
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        # config bgp address-family ipv4 unicast network del <network>
        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["network"]
            .commands["del"],
            [network],
            obj=db,
        )
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

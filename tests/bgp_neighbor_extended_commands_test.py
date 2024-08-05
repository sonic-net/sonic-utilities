import os
import pytest

from click.testing import CliRunner

import config.main as config
from utilities_common.db import Db


class TestBgpNeighborExtendedCommands(object):

    valid_neighbors = (
        ("10.10.10.10",),
        ("0bd3:8339:7d3b:d3bb:dd39:c1c0:6e23:f517",),
        ("Ethernet4",),
    )

    invalid_neighbors = (
        ("10.10.10.358",),
        ("5efc:2mf5:6f16:acdn:e9c4:5747:fg6b:275d",),
        ("Ether_net4",),
    )

    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    @classmethod
    def teardown_class(cls):
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        print("TEARDOWN")

    def test_config_bgp_add_neighbor_remote_as_without_asn(self):
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["remote-as"]
            .commands["add"],
            ["10.10.10.10", "65535"],
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

    @pytest.mark.parametrize("valid_neighbors", valid_neighbors)
    def test_config_bgp_add_set_del_valid_neighbor_remote_as(self, valid_neighbors):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["remote-as"]
                .commands["add"],
                [neighbor, "65535"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", neighbor)).get("asn")
                == "65535"
            )

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["remote-as"]
                .commands["set"],
                [neighbor, "62000"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", neighbor)).get("asn")
                == "62000"
            )

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["remote-as"]
                .commands["del"],
                [neighbor, "62000"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", neighbor)).get("asn")
                is None
            )

    @pytest.mark.parametrize("invalid_neighbors", invalid_neighbors)
    def test_config_bgp_add_set_del_invalid_neighbor_remote_as(self, invalid_neighbors):
        runner = CliRunner()
        db = Db()

        for neighbor in invalid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["remote-as"]
                .commands["add"],
                [neighbor, "65535"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code != 0
            assert "Neighbor interface/IP address is not valid" in result.output

        for neighbor in invalid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["remote-as"]
                .commands["set"],
                [neighbor, "34000"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code != 0
            assert "Neighbor interface/IP address is not valid" in result.output

        for neighbor in invalid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["remote-as"]
                .commands["del"],
                [neighbor, "60000"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code != 0
            assert "Neighbor interface/IP address is not valid" in result.output

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["remote-as"]
            .commands["add"],
            ["192.168.0.100", "0"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["remote-as"]
            .commands["set"],
            ["192.168.0.100", "1a"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["remote-as"]
            .commands["del"],
            ["192.168.0.100", "4294967296"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0

    def test_config_bgp_add_existing_neighbor_remote_as(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["remote-as"]
            .commands["add"],
            ["10.10.10.10", "65535"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["remote-as"]
            .commands["add"],
            ["10.10.10.10", "65535"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "BGP neighbor remote-as already exists" in result.output

    def test_config_bgp_set_unexisting_neighbor_remote_as(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["remote-as"]
            .commands["set"],
            ["10.10.10.10", "65535"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "BGP neighbor remote-as is not configured" in result.output

    def test_config_bgp_del_unexisting_neighbor_remote_as(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["remote-as"]
            .commands["del"],
            ["10.10.10.10", "65535"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "BGP neighbor does not exist" in result.output

    def test_config_bgp_add_neighbor_upd_src_without_asn(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["update-source"]
            .commands["add"],
            ["10.10.10.10", "20.20.20.20"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["update-source"]
            .commands["add"],
            ["10.10.10.10", "20.20.20.20"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "Specify BGP neighbor remote-as first" in result.output

    @pytest.mark.parametrize("valid_neighbors", valid_neighbors)
    def test_config_bgp_add_set_del_valid_neighbor_upd_src(self, valid_neighbors):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["remote-as"]
                .commands["add"],
                [neighbor, "200"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["update-source"]
                .commands["add"],
                [neighbor, "178.50.20.10"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", neighbor)).get(
                    "local_addr"
                )
                == "178.50.20.10"
            )

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["update-source"]
                .commands["set"],
                [neighbor, "180.122.55.50"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", neighbor)).get(
                    "local_addr"
                )
                == "180.122.55.50"
            )

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["update-source"]
                .commands["del"],
                [neighbor, "180.122.55.50"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", neighbor)).get(
                    "local_addr"
                )
                is None
            )

    @pytest.mark.parametrize("invalid_neighbors", invalid_neighbors)
    def test_config_bgp_add_set_del_invalid_neighbor_upd_src(self, invalid_neighbors):
        runner = CliRunner()
        db = Db()

        for neighbor in invalid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["update-source"]
                .commands["add"],
                [neighbor, "178.50.20.10"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code != 0
            assert "Neighbor interface/IP address is not valid" in result.output

        for neighbor in invalid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["update-source"]
                .commands["set"],
                [neighbor, "180.122.55.50"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code != 0
            assert "Neighbor interface/IP address is not valid" in result.output

        for neighbor in invalid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["update-source"]
                .commands["del"],
                [neighbor, "180.122.55.50"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code != 0
            assert "Neighbor interface/IP address is not valid" in result.output

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["update-source"]
            .commands["add"],
            ["192.168.0.100", "0.1a.50.20"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["update-source"]
            .commands["set"],
            ["192.168.0.100", "4294967296"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["update-source"]
            .commands["del"],
            ["192.168.0.100", "500.20.50.11"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0

    def test_config_bgp_add_existing_neighbor_upd_src(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["remote-as"]
            .commands["add"],
            ["192.168.0.100", "200"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["update-source"]
            .commands["add"],
            ["192.168.0.100", "20.20.20.20"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["update-source"]
            .commands["add"],
            ["192.168.0.100", "20.20.20.20"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "BGP neighbor update source already exists" in result.output

    def test_config_bgp_set_unexisting_neighbor_upd_src(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["remote-as"]
            .commands["add"],
            ["192.168.0.100", "200"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["update-source"]
            .commands["set"],
            ["192.168.0.100", "20.20.20.20"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "BGP neighbor update source is not configured" in result.output

    def test_config_bgp_del_unexisting_neighbor_upd_src(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["remote-as"]
            .commands["add"],
            ["192.168.0.100", "200"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["update-source"]
            .commands["del"],
            ["192.168.0.100", "20.20.20.20"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "BGP neighbor update source is not configured" in result.output

    def test_config_bgp_add_neighbor_adv_interval_without_asn(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["advertisement-interval"]
            .commands["add"],
            ["10.10.10.10", "33"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["advertisement-interval"]
            .commands["add"],
            ["10.10.10.10", "33"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "Specify BGP neighbor remote-as first" in result.output

    @pytest.mark.parametrize("valid_neighbors", valid_neighbors)
    def test_config_bgp_add_set_del_valid_neighbor_adv_interval(self, valid_neighbors):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["remote-as"]
                .commands["add"],
                [neighbor, "200"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["advertisement-interval"]
                .commands["add"],
                [neighbor, "123"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", neighbor)).get(
                    "min_adv_interval"
                )
                == "123"
            )

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["advertisement-interval"]
                .commands["set"],
                [neighbor, "234"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", neighbor)).get(
                    "min_adv_interval"
                )
                == "234"
            )

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["advertisement-interval"]
                .commands["del"],
                [neighbor, "234"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", neighbor)).get(
                    "min_adv_interval"
                )
                is None
            )

    @pytest.mark.parametrize("invalid_neighbors", invalid_neighbors)
    def test_config_bgp_add_set_del_invalid_neighbor_adv_interval(
        self, invalid_neighbors
    ):
        runner = CliRunner()
        db = Db()

        for neighbor in invalid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["advertisement-interval"]
                .commands["add"],
                [neighbor, "123"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code != 0
            assert "Neighbor interface/IP address is not valid" in result.output

        for neighbor in invalid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["advertisement-interval"]
                .commands["set"],
                [neighbor, "234"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code != 0
            assert "Neighbor interface/IP address is not valid" in result.output

        for neighbor in invalid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["advertisement-interval"]
                .commands["del"],
                [neighbor, "234"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code != 0
            assert "Neighbor interface/IP address is not valid" in result.output

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["advertisement-interval"]
            .commands["add"],
            ["192.168.0.100", "0"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["advertisement-interval"]
            .commands["set"],
            ["192.168.0.100", "800"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["advertisement-interval"]
            .commands["del"],
            ["192.168.0.100", "-5"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0

    def test_config_bgp_add_existing_neighbor_adv_interval(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["remote-as"]
            .commands["add"],
            ["192.168.0.100", "200"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["advertisement-interval"]
            .commands["add"],
            ["192.168.0.100", "200"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["advertisement-interval"]
            .commands["add"],
            ["192.168.0.100", "200"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "BGP neighbor advertisement interval already exists" in result.output

    def test_config_bgp_set_unexisting_neighbor_adv_interval(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["remote-as"]
            .commands["add"],
            ["192.168.0.100", "200"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["advertisement-interval"]
            .commands["set"],
            ["192.168.0.100", "500"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "BGP neighbor advertisement interval is not configured" in result.output

    def test_config_bgp_del_unexisting_neighbor_adv_interval(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["remote-as"]
            .commands["add"],
            ["192.168.0.100", "200"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["advertisement-interval"]
            .commands["del"],
            ["192.168.0.100", "500"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "BGP neighbor advertisement interval is not configured" in result.output

    def test_config_bgp_add_neighbor_timers_without_asn(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["timers"]
            .commands["add"],
            ["10.10.10.10", "2", "6"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["timers"]
            .commands["add"],
            ["10.10.10.10", "2", "6"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "Specify BGP neighbor remote-as first" in result.output

    @pytest.mark.parametrize("valid_neighbors", valid_neighbors)
    def test_config_bgp_add_set_del_neighbor_valid_timers(self, valid_neighbors):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["remote-as"]
                .commands["add"],
                [neighbor, "200"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["timers"]
                .commands["add"],
                [neighbor, "2", "6"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", neighbor)).get(
                    "keepalive"
                )
                == "2"
            )
            assert (
                db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", neighbor)).get(
                    "holdtime"
                )
                == "6"
            )

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["timers"]
                .commands["set"],
                [neighbor, "20", "60"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", neighbor)).get(
                    "keepalive"
                )
                == "20"
            )
            assert (
                db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", neighbor)).get(
                    "holdtime"
                )
                == "60"
            )

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["timers"]
                .commands["del"],
                [neighbor, "20", "60"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", neighbor)).get(
                    "keepalive"
                )
                is None
            )
            assert (
                db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", neighbor)).get(
                    "holdtime"
                )
                is None
            )

    @pytest.mark.parametrize("invalid_neighbors", invalid_neighbors)
    def test_config_bgp_add_set_del_neighbor_invalid_timers(self, invalid_neighbors):
        runner = CliRunner()
        db = Db()

        for neighbor in invalid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["timers"]
                .commands["add"],
                [neighbor, "2", "6"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code != 0
            assert "Neighbor interface/IP address is not valid" in result.output

        for neighbor in invalid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["timers"]
                .commands["set"],
                [neighbor, "2", "6"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code != 0
            assert "Neighbor interface/IP address is not valid" in result.output

        for neighbor in invalid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["timers"]
                .commands["del"],
                [neighbor, "2", "6"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code != 0
            assert "Neighbor interface/IP address is not valid" in result.output

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["timers"]
            .commands["add"],
            ["192.168.0.100", "-5"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["timers"]
            .commands["set"],
            ["192.168.0.100", "70000"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["timers"]
            .commands["del"],
            ["192.168.0.100", "99999"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0

    def test_config_bgp_add_existing_neighbor_timers(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["remote-as"]
            .commands["add"],
            ["192.168.0.100", "200"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["timers"]
            .commands["add"],
            ["192.168.0.100", "2", "6"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["timers"]
            .commands["add"],
            ["192.168.0.100", "2", "6"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "BGP neighbor timers are already configured" in result.output

    def test_config_bgp_set_unexisting_neighbor_timers(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["remote-as"]
            .commands["add"],
            ["192.168.0.100", "200"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["timers"]
            .commands["set"],
            ["192.168.0.100", "2", "6"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "BGP neighbor timers are not configured" in result.output

    def test_config_bgp_del_unexisting_neighbor_timers(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["remote-as"]
            .commands["add"],
            ["192.168.0.100", "200"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["timers"]
            .commands["del"],
            ["192.168.0.100", "2", "6"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "BGP neighbor timers are not configured" in result.output

    def test_config_bgp_add_neighbor_local_as_without_asn(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["local-as"]
            .commands["add"],
            ["10.10.10.10", "65000"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["local-as"]
            .commands["add"],
            ["10.10.10.10", "65000"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "Specify BGP neighbor remote-as first" in result.output

    @pytest.mark.parametrize("valid_neighbors", valid_neighbors)
    def test_config_bgp_add_set_del_neighbor_valid_local_as(self, valid_neighbors):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["remote-as"]
                .commands["add"],
                [neighbor, "200"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["local-as"]
                .commands["add"],
                [neighbor, "65535"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", neighbor)).get(
                    "local_asn"
                )
                == "65535"
            )

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["local-as"]
                .commands["set"],
                [neighbor, "62000"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", neighbor)).get(
                    "local_asn"
                )
                == "62000"
            )

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["local-as"]
                .commands["del"],
                [neighbor, "62000"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", neighbor)).get(
                    "local_asn"
                )
                is None
            )

    @pytest.mark.parametrize("invalid_neighbors", invalid_neighbors)
    def test_config_bgp_add_set_del_neighbor_invalid_local_as(self, invalid_neighbors):
        runner = CliRunner()
        db = Db()

        for neighbor in invalid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["local-as"]
                .commands["add"],
                [neighbor, "65535"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code != 0
            assert "Neighbor interface/IP address is not valid" in result.output

        for neighbor in invalid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["local-as"]
                .commands["set"],
                [neighbor, "34000"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code != 0
            assert "Neighbor interface/IP address is not valid" in result.output

        for neighbor in invalid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["local-as"]
                .commands["del"],
                [neighbor, "60000"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code != 0
            assert "Neighbor interface/IP address is not valid" in result.output

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["local-as"]
            .commands["add"],
            ["192.168.0.100", "0"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["local-as"]
            .commands["set"],
            ["192.168.0.100", "1a"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["local-as"]
            .commands["del"],
            ["192.168.0.100", "4294967296"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0

    def test_config_bgp_add_existing_neighbor_local_as(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["remote-as"]
            .commands["add"],
            ["192.168.0.100", "200"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["local-as"]
            .commands["add"],
            ["192.168.0.100", "65535"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["local-as"]
            .commands["add"],
            ["192.168.0.100", "65535"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "BGP neighbor local AS is already specified" in result.output

    def test_config_bgp_set_unexisting_neighbor_local_as(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["remote-as"]
            .commands["add"],
            ["192.168.0.100", "200"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["local-as"]
            .commands["set"],
            ["192.168.0.100", "65535"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "BGP neighbor local AS is not configured" in result.output

    def test_config_bgp_del_unexisting_neighbor_local_as(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["remote-as"]
            .commands["add"],
            ["192.168.0.100", "200"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["local-as"]
            .commands["del"],
            ["192.168.0.100", "65535"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "BGP neighbor local AS is not configured" in result.output

    def test_config_bgp_neighbor_shutdown_without_asn(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["neighbor"].commands["shutdown"],
            ["10.10.10.10", "on"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"].commands["neighbor"].commands["shutdown"],
            ["10.10.10.10", "on"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "Specify BGP neighbor remote-as first" in result.output

    @pytest.mark.parametrize("valid_neighbors", valid_neighbors)
    def test_config_bgp_valid_neighbor_shutdown(self, valid_neighbors):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["remote-as"]
                .commands["add"],
                [neighbor, "200"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"].commands["neighbor"].commands["shutdown"],
                [neighbor, "on"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", neighbor)).get(
                    "admin_status"
                )
                == "false"
            )

    @pytest.mark.parametrize("invalid_neighbors", invalid_neighbors)
    def test_config_bgp_invalid_neighbor_shutdown(self, invalid_neighbors):
        runner = CliRunner()
        db = Db()

        for neighbor in invalid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"].commands["neighbor"].commands["shutdown"],
                [neighbor, "on"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code != 0

    def test_config_bgp_neighbor_ebgp_multihop_without_asn(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["ebgp-multihop"],
            ["10.10.10.10", "on"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["neighbor"]
            .commands["ebgp-multihop"],
            ["10.10.10.10", "on"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "Specify BGP neighbor remote-as first" in result.output

    @pytest.mark.parametrize("valid_neighbors", valid_neighbors)
    def test_config_bgp_valid_neighbor_ebgp_multihop(self, valid_neighbors):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["remote-as"]
                .commands["add"],
                [neighbor, "200"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["ebgp-multihop"],
                [neighbor, "on"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_entry("BGP_NEIGHBOR", ("default", neighbor)).get(
                    "ebgp_multihop"
                )
                == "true"
            )

    @pytest.mark.parametrize("invalid_neighbors", invalid_neighbors)
    def test_config_bgp_invalid_neighbor_ebgp_multihop(self, invalid_neighbors):
        runner = CliRunner()
        db = Db()

        for neighbor in invalid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["ebgp-multihop"],
                [neighbor, "on"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code != 0

    def test_config_bgp_addr_family_ipv4_unicast_neighbor_activate_without_asn(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["neighbor"]
            .commands["activate"],
            ["10.10.10.10", "on"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["ipv4"]
            .commands["unicast"]
            .commands["neighbor"]
            .commands["activate"],
            ["10.10.10.10", "on"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "Specify BGP neighbor remote-as first" in result.output

    @pytest.mark.parametrize("valid_neighbors", valid_neighbors)
    def test_config_bgp_addr_family_ipv4_unicast_valid_neighbor_activate(
        self, valid_neighbors
    ):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["remote-as"]
                .commands["add"],
                [neighbor, "200"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["address-family"]
                .commands["ipv4"]
                .commands["unicast"]
                .commands["neighbor"]
                .commands["activate"],
                [neighbor, "on"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_entry(
                    "BGP_NEIGHBOR_AF", ("default", neighbor, "ipv4_unicast")
                ).get("admin_status")
                == "true"
            )

    @pytest.mark.parametrize("invalid_neighbors", invalid_neighbors)
    def test_config_bgp_addr_family_ipv4_unicast_invalid_neighbor_activate(
        self, invalid_neighbors
    ):
        runner = CliRunner()
        db = Db()

        for neighbor in invalid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["address-family"]
                .commands["ipv4"]
                .commands["unicast"]
                .commands["neighbor"]
                .commands["activate"],
                [neighbor, "on"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code != 0

    def test_config_bgp_addr_family_l2vpn_evpn_neighbor_activate_without_asn(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["l2vpn"]
            .commands["evpn"]
            .commands["neighbor"]
            .commands["activate"],
            ["10.10.10.10", "on"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["l2vpn"]
            .commands["evpn"]
            .commands["neighbor"]
            .commands["activate"],
            ["10.10.10.10", "on"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "Specify BGP neighbor remote-as first" in result.output

    @pytest.mark.parametrize("valid_neighbors", valid_neighbors)
    def test_config_bgp_addr_family_l2vpn_evpn_neighbor_activate(self, valid_neighbors):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["remote-as"]
                .commands["add"],
                [neighbor, "200"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["address-family"]
                .commands["l2vpn"]
                .commands["evpn"]
                .commands["neighbor"]
                .commands["activate"],
                [neighbor, "on"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_entry(
                    "BGP_NEIGHBOR_AF", ("default", neighbor, "l2vpn_evpn")
                ).get("admin_status")
                == "true"
            )

    @pytest.mark.parametrize("invalid_neighbors", invalid_neighbors)
    def test_config_bgp_addr_family_l2vpn_evpn_neighbor_activate_neg(
        self, invalid_neighbors
    ):
        runner = CliRunner()
        db = Db()

        for neighbor in invalid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["address-family"]
                .commands["l2vpn"]
                .commands["evpn"]
                .commands["neighbor"]
                .commands["activate"],
                [neighbor, "on"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code != 0

    def test_config_bgp_addr_family_l2vpn_evpn_neighbor_rr_client_without_asn(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["l2vpn"]
            .commands["evpn"]
            .commands["neighbor"]
            .commands["route-reflector-client"],
            ["10.10.10.10", "on"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["l2vpn"]
            .commands["evpn"]
            .commands["neighbor"]
            .commands["route-reflector-client"],
            ["10.10.10.10", "on"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "Specify BGP neighbor remote-as first" in result.output

    @pytest.mark.parametrize("valid_neighbors", valid_neighbors)
    def test_config_bgp_addr_family_l2vpn_evpn_neighbor_rr_client(
        self, valid_neighbors
    ):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["remote-as"]
                .commands["add"],
                [neighbor, "100"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["address-family"]
                .commands["l2vpn"]
                .commands["evpn"]
                .commands["neighbor"]
                .commands["route-reflector-client"],
                [neighbor, "on"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_entry(
                    "BGP_NEIGHBOR_AF", ("default", neighbor, "l2vpn_evpn")
                ).get("rrclient")
                == "true"
            )

    @pytest.mark.parametrize("invalid_neighbors", invalid_neighbors)
    def test_config_bgp_addr_family_l2vpn_evpn_neighbor_rr_client_neg(
        self, invalid_neighbors
    ):
        runner = CliRunner()
        db = Db()

        for neighbor in invalid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["address-family"]
                .commands["l2vpn"]
                .commands["evpn"]
                .commands["neighbor"]
                .commands["route-reflector-client"],
                [neighbor, "on"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code != 0

    def test_config_bgp_addr_family_l2vpn_evpn_neighbor_soft_reconf_inbound_without_asn(
        self,
    ):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["l2vpn"]
            .commands["evpn"]
            .commands["neighbor"]
            .commands["soft-reconf"]
            .commands["inbound"],
            ["10.10.10.10", "on"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["l2vpn"]
            .commands["evpn"]
            .commands["neighbor"]
            .commands["soft-reconf"]
            .commands["inbound"],
            ["10.10.10.10", "on"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "Specify BGP neighbor remote-as first" in result.output

    @pytest.mark.parametrize("valid_neighbors", valid_neighbors)
    def test_config_bgp_addr_family_l2vpn_evpn_neighbor_soft_reconf_inbound(
        self, valid_neighbors
    ):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["remote-as"]
                .commands["add"],
                [neighbor, "200"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["address-family"]
                .commands["l2vpn"]
                .commands["evpn"]
                .commands["neighbor"]
                .commands["soft-reconf"]
                .commands["inbound"],
                [neighbor, "on"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_entry(
                    "BGP_NEIGHBOR_AF", ("default", neighbor, "l2vpn_evpn")
                ).get("soft_reconfiguration_in")
                == "true"
            )

    @pytest.mark.parametrize("invalid_neighbors", invalid_neighbors)
    def test_config_bgp_addr_family_l2vpn_evpn_neighbor_soft_reconf_inbound_neg(
        self, invalid_neighbors
    ):
        runner = CliRunner()
        db = Db()

        for neighbor in invalid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["address-family"]
                .commands["l2vpn"]
                .commands["evpn"]
                .commands["neighbor"]
                .commands["soft-reconf"]
                .commands["inbound"],
                [neighbor, "on"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code != 0

    def test_config_bgp_addr_family_l2vpn_evpn_neighbor_allowas_without_asn(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["l2vpn"]
            .commands["evpn"]
            .commands["neighbor"]
            .commands["allowas-in"],
            ["10.10.10.10", "on"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "AS number is not specified" in result.output

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["bgp"]
            .commands["address-family"]
            .commands["l2vpn"]
            .commands["evpn"]
            .commands["neighbor"]
            .commands["allowas-in"],
            ["10.10.10.10", "on"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code != 0
        assert "Specify BGP neighbor remote-as first" in result.output

    @pytest.mark.parametrize("valid_neighbors", valid_neighbors)
    def test_config_bgp_addr_family_l2vpn_evpn_neighbor_allowas(self, valid_neighbors):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(
            config.config.commands["bgp"].commands["autonomous-system"].commands["add"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        assert result.exit_code == 0

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["neighbor"]
                .commands["remote-as"]
                .commands["add"],
                [neighbor, "200"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0

        for neighbor in valid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["address-family"]
                .commands["l2vpn"]
                .commands["evpn"]
                .commands["neighbor"]
                .commands["allowas-in"],
                [neighbor, "on"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code == 0
            assert (
                db.cfgdb.get_entry(
                    "BGP_NEIGHBOR_AF", ("default", neighbor, "l2vpn_evpn")
                ).get("allow_as_in")
                == "true"
            )

    @pytest.mark.parametrize("invalid_neighbors", invalid_neighbors)
    def test_config_bgp_addr_family_l2vpn_evpn_neighbor_allowas_neg(
        self, invalid_neighbors
    ):
        runner = CliRunner()
        db = Db()

        for neighbor in invalid_neighbors:
            result = runner.invoke(
                config.config.commands["bgp"]
                .commands["address-family"]
                .commands["l2vpn"]
                .commands["evpn"]
                .commands["neighbor"]
                .commands["allowas-in"],
                [neighbor, "on"],
                obj=db,
            )
            print(result.exit_code)
            assert result.exit_code != 0

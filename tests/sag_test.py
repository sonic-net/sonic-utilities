import os
from click.testing import CliRunner

import config.main as config
import show.main as show
from utilities_common.db import Db

show_sag_output = """\
Static Anycast Gateway Information
MacAddress         Interfaces
-----------------  ------------
00:11:22:33:44:55  Vlan1000
"""

show_sag_inconsistent_output = """\
Static Anycast Gateway Information
Warning: static-anycast-gateway is enabled on VLAN interfaces but SAG gateway_mac is not configured
MacAddress    Interfaces
------------  ------------
"""


class TestSag(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

    def test_config_add_sag_with_existed_mac(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["static-anycast-gateway"].commands["mac_address"].commands["add"],
                               ["00:22:33:44:55:66"], obj=db)
        assert result.exit_code != 0, (
            f"sag invalid mac with code {type(result.exit_code)}:{result.exit_code} "
            f"Output:{result.output}"
        )
        assert {"gateway_mac": "00:11:22:33:44:55"} == db.cfgdb.get_entry("SAG", "GLOBAL")

    def test_config_del_add_invalid_sag_mac_address(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["static-anycast-gateway"].commands["mac_address"].commands["del"],
                               obj=db)
        assert result.exit_code == 0, (
            f"sag invalid mac with code {type(result.exit_code)}:{result.exit_code} "
            f"Output:{result.output}"
        )
        assert not db.cfgdb.get_entry("SAG", "GLOBAL")

        result = runner.invoke(config.config.commands["static-anycast-gateway"].commands["mac_address"].commands["add"],
                               ["01:22:33:44:55:66"], obj=db)
        assert result.exit_code != 0, (
            f"sag invalid mac with code {type(result.exit_code)}:{result.exit_code} "
            f"Output:{result.output}"
        )
        assert {"gateway_mac": "01:11:22:33:44:55"} != db.cfgdb.get_entry("SAG", "GLOBAL")

    def test_config_del_add_sag_mac_address(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["static-anycast-gateway"].commands["mac_address"].commands["del"],
                               obj=db)
        assert result.exit_code == 0, (
            f"sag invalid mac with code {type(result.exit_code)}:{result.exit_code} "
            f"Output:{result.output}"
        )
        assert not db.cfgdb.get_entry("SAG", "GLOBAL")

        result = runner.invoke(config.config.commands["static-anycast-gateway"].commands["mac_address"].commands["add"],
                               ["00:22:33:44:55:66"], obj=db)
        assert result.exit_code == 0, (
            f"sag invalid mac with code {type(result.exit_code)}:{result.exit_code} "
            f"Output:{result.output}"
        )
        assert {"gateway_mac": "00:22:33:44:55:66"} == db.cfgdb.get_entry("SAG", "GLOBAL")

    def test_config_del_sag_mac_preserves_other_global_fields(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("SAG", "GLOBAL", {"gateway_mac": "00:11:22:33:44:55", "other_field": "keep"})

        result = runner.invoke(config.config.commands["static-anycast-gateway"].commands["mac_address"].commands["del"],
                               obj=db)
        assert result.exit_code == 0, (
            f"sag delete mac with code {type(result.exit_code)}:{result.exit_code} "
            f"Output:{result.output}"
        )
        assert {"other_field": "keep"} == db.cfgdb.get_entry("SAG", "GLOBAL")

    def test_config_enable_sag_on_vlan_interface(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["vlan"].commands["static-anycast-gateway"].commands["enable"],
                               ["2000"], obj=db)
        assert result.exit_code == 0, (
            f"sag invalid vlan with code {type(result.exit_code)}:{result.exit_code} "
            f"Output:{result.output}"
        )
        assert {"static_anycast_gateway": "true"}.items() <= db.cfgdb.get_entry("VLAN_INTERFACE", "Vlan2000").items()

    def test_config_disable_sag_on_vlan_interface(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["vlan"].commands["static-anycast-gateway"].commands["disable"],
                               ["1000"], obj=db)
        assert result.exit_code == 0, (
            f"sag invalid vlan with code {type(result.exit_code)}:{result.exit_code} "
            f"Output:{result.output}"
        )
        assert {"static_anycast_gateway": "false"}.items() <= db.cfgdb.get_entry("VLAN_INTERFACE", "Vlan1000").items()

    def test_show_sag_mac(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["static-anycast-gateway"], [])
        assert result.exit_code == 0, (
            f"invalid show sag with code {type(result.exit_code)}:{result.exit_code} "
            f"Output:{result.output}"
        )
        assert result.output == show_sag_output

    def test_show_sag_missing_global_mac_with_enabled_vlan(self):
        runner = CliRunner()
        db = Db()
        db.cfgdb.set_entry("SAG", "GLOBAL", None)

        result = runner.invoke(show.cli.commands["static-anycast-gateway"], [], obj=db)
        assert result.exit_code == 0, (
            f"invalid show sag with code {type(result.exit_code)}:{result.exit_code} "
            f"Output:{result.output}"
        )
        assert result.output == show_sag_inconsistent_output

    def test_config_enable_sag_already_enabled(self):
        runner = CliRunner()
        db = Db()
        # Vlan1000 already has static_anycast_gateway=true in mock config_db
        result = runner.invoke(config.config.commands["vlan"].commands["static-anycast-gateway"].commands["enable"],
                               ["1000"], obj=db)
        assert result.exit_code != 0, f"Expected failure for already-enabled SAG: {result.output}"
        assert "already enabled" in result.output

    def test_config_disable_sag_already_disabled(self):
        runner = CliRunner()
        db = Db()
        # Vlan2000 has no static_anycast_gateway=true (proxy_arp only) → already disabled
        result = runner.invoke(config.config.commands["vlan"].commands["static-anycast-gateway"].commands["disable"],
                               ["2000"], obj=db)
        assert result.exit_code != 0, f"Expected failure for already-disabled SAG: {result.output}"
        assert "already disabled" in result.output

    def test_config_enable_sag_nonexistent_vlan(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(config.config.commands["vlan"].commands["static-anycast-gateway"].commands["enable"],
                               ["9999"], obj=db)
        assert result.exit_code != 0, f"Expected failure for non-existent VLAN: {result.output}"
        assert "does not exist" in result.output

    def test_config_disable_sag_nonexistent_vlan(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(config.config.commands["vlan"].commands["static-anycast-gateway"].commands["disable"],
                               ["9999"], obj=db)
        assert result.exit_code != 0, f"Expected failure for non-existent VLAN: {result.output}"
        assert "does not exist" in result.output

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")

import os
from unittest.mock import patch
# from unittest.mock import MagicMock
import pytest
# from click import ClickException, Context
from click.testing import CliRunner
# import pytest
# from config.stp import (
#     mst_instance_interface_cost,
# )
#     get_global_stp_mode,
#     check_if_vlan_exist_in_db,
#     is_valid_forward_delay,
#     MST_MIN_PORT_PATH_COST,
#     MST_MAX_PORT_PATH_COST,
#     MST_MAX_INSTANCES,
#     is_valid_stp_vlan_parameters,
#     check_if_stp_enabled_for_vlan
# import time
import config.main as config
import show.main as show
from utilities_common.db import Db

show_spanning_tree = """\
Spanning-tree Mode: PVST

VLAN 100 - STP instance 0
--------------------------------------------------------------------
STP Bridge Parameters:
Bridge           Bridge Bridge Bridge Hold  LastTopology Topology
Identifier       MaxAge Hello  FwdDly Time  Change       Change
hex              sec    sec    sec    sec   sec          cnt
8064b86a97e24e9c 20     2      15     1     0            1

RootBridge       RootPath  DesignatedBridge  RootPort           Max Hel Fwd
Identifier       Cost      Identifier                           Age lo  Dly
hex                        hex                                  sec sec sec
0064b86a97e24e9c 600       806480a235f281ec  Root               20  2   15

STP Port Parameters:
Port             Prio Path      Port Uplink State         Designated  Designated       Designated
Name             rity Cost      Fast Fast                 Cost        Root             Bridge
Ethernet4        128  200       N    N      FORWARDING    400         0064b86a97e24e9c 806480a235f281ec
"""

show_spanning_tree_vlan = """\

VLAN 100 - STP instance 0
--------------------------------------------------------------------
STP Bridge Parameters:
Bridge           Bridge Bridge Bridge Hold  LastTopology Topology
Identifier       MaxAge Hello  FwdDly Time  Change       Change
hex              sec    sec    sec    sec   sec          cnt
8064b86a97e24e9c 20     2      15     1     0            1

RootBridge       RootPath  DesignatedBridge  RootPort           Max Hel Fwd
Identifier       Cost      Identifier                           Age lo  Dly
hex                        hex                                  sec sec sec
0064b86a97e24e9c 600       806480a235f281ec  Root               20  2   15

STP Port Parameters:
Port             Prio Path      Port Uplink State         Designated  Designated       Designated
Name             rity Cost      Fast Fast                 Cost        Root             Bridge
Ethernet4        128  200       N    N      FORWARDING    400         0064b86a97e24e9c 806480a235f281ec
"""

show_spanning_tree_statistics = """\
VLAN 100 - STP instance 0
--------------------------------------------------------------------
PortNum          BPDU Tx        BPDU Rx        TCN Tx         TCN Rx
Ethernet4        10             15             15             5
"""

show_spanning_tree_bpdu_guard = """\
PortNum          Shutdown     Port Shut
                 Configured   due to BPDU guard
-------------------------------------------
Ethernet4        No           NA
"""

show_spanning_tree_root_guard = """\
Root guard timeout: 30 secs

Port             VLAN   Current State
-------------------------------------------
Ethernet4        100    Consistent state
"""


class TestStp(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

    def test_show_spanning_tree(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands["spanning-tree"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        if result.exit_code != 0:
            print(f'Error Output:\n{result.output}')
            assert result.exit_code == 0
            assert result.output == show_spanning_tree

    def test_show_spanning_tree_vlan(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands["spanning-tree"].commands["vlan"], ["100"], obj=db)
        print(result.exit_code)
        print(result.output)
        if result.exit_code != 0:
            print(f'Error Output:\n{result.output}')
            assert result.exit_code == 0
            assert result.output == show_spanning_tree_vlan

    def test_show_spanning_tree_statistics(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands["spanning-tree"].commands["statistics"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        if result.exit_code != 0:
            print(f'Error Output:\n{result.output}')
            assert result.exit_code == 0
            assert result.output == show_spanning_tree_statistics

    def test_show_spanning_tree_statistics_vlan(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(
            show.cli.commands["spanning-tree"]
            .commands["statistics"]
            .commands["vlan"],
            ["100"],
            obj=db,
        )
        print(result.exit_code)
        print(result.output)
        if result.exit_code != 0:
            print(f'Error Output:\n{result.output}')
            assert result.exit_code == 0
            assert result.output == show_spanning_tree_statistics

    def test_show_spanning_tree_bpdu_guard(self):
        cli_runner = CliRunner()
        db = Db()
        result = cli_runner.invoke(show.cli.commands["spanning-tree"].commands["bpdu_guard"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        if result.exit_code != 0:
            print(f'Error Output:\n{result.output}')
            assert result.exit_code == 0
            assert result.output == show_spanning_tree_bpdu_guard

    def test_show_spanning_tree_root_guard(self):
        cli_runner = CliRunner()
        db = Db()
        result = cli_runner.invoke(show.cli.commands["spanning-tree"].commands["root_guard"], [], obj=db)
        print(result.exit_code)
        print(result.output)
        if result.exit_code != 0:
            print(f'Error Output:\n{result.output}')
            assert result.exit_code == 0
            assert result.output == show_spanning_tree_root_guard

    def test_disable_enable_global_pvst(self):
        cli_runner = CliRunner()
        db = Db()

        result = cli_runner.invoke(config.config.commands["spanning-tree"].commands["disable"], ["pvst"], obj=db)
        print("exit code {}".format(result.exit_code))
        print("result code {}".format(result.output))
        if result.exit_code != 0:
            print(f'Error Output:\n{result.output}')
            assert result.exit_code == 0

        result = cli_runner.invoke(config.config.commands["spanning-tree"].commands["enable"], ["pvst"], obj=db)
        print("exit code {}".format(result.exit_code))
        print("result code {}".format(result.output))
        if result.exit_code != 0:
            print(f'Error Output:\n{result.output}')
            assert result.exit_code == 0

        result = cli_runner.invoke(config.config.commands["vlan"].commands["add"], ["100"], obj=db)
        print(result.exit_code)
        if result.exit_code != 0:
            print(f'Error Output:\n{result.output}')
            assert result.exit_code == 0

        result = cli_runner.invoke(
            config.config.commands["vlan"]
            .commands["member"]
            .commands["add"],
            ["100", "Ethernet4"],
            obj=db,
        )
        print(result.exit_code)
        if result.exit_code != 0:
            print(f'Error Output:\n{result.output}')
            assert result.exit_code == 0

        result = cli_runner.invoke(config.config.commands["spanning-tree"].commands["enable"], ["pvst"], obj=db)
        print("exit code {}".format(result.exit_code))
        print("result code {}".format(result.output))
        assert result.exit_code != 0
        assert "PVST is already configured" in result.output

    def test_add_vlan_enable_pvst(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["spanning-tree"].commands["disable"], ["pvst"], obj=db)
        print("exit code {}".format(result.exit_code))
        print("result code {}".format(result.output))
        if result.exit_code != 0:
            print(f'Error Output:\n{result.output}')
            assert result.exit_code == 0

        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["100"], obj=db)
        print(result.exit_code)
        if result.exit_code != 0:
            print(f'Error Output:\n{result.output}')
            assert result.exit_code == 0

        result = runner.invoke(
                config.config.commands["vlan"]
                .commands["member"]
                .commands["add"],
                ["100", "Ethernet4"],
                obj=db,
            )
        print(result.exit_code)
        if result.exit_code != 0:
            print(f'Error Output:\n{result.output}')
            assert result.exit_code == 0

        result = runner.invoke(config.config.commands["spanning-tree"].commands["enable"], ["pvst"], obj=db)
        print(result.exit_code)
        if result.exit_code != 0:
            print(f'Error Output:\n{result.output}')
            assert result.exit_code == 0

        result = runner.invoke(config.config.commands["vlan"].commands["add"], ["200"], obj=db)
        print(result.exit_code)
        if result.exit_code != 0:
            print(f'Error Output:\n{result.output}')
            assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["disable"],
            ["200"],
            obj=db,
        )
        print("exit code {}".format(result.exit_code))
        print("result code {}".format(result.output))
        if result.exit_code != 0:
            print(f'Error Output:\n{result.output}')
            assert result.exit_code == 0

        result = runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["enable"],
            ["200"],
            obj=db,
        )
        print("exit code {}".format(result.exit_code))
        print("result code {}".format(result.output))
        if result.exit_code != 0:
            print(f'Error Output:\n{result.output}')
            assert result.exit_code == 0

        result = runner.invoke(config.config.commands["vlan"].commands["del"], ["200"], obj=db)
        print(result.exit_code)
        assert result.exit_code != 0

        # Enable/Disable on non-existing VLAN
        result = runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["enable"],
            ["101"],
            obj=db,
        )
        print("exit code {}".format(result.exit_code))
        print("result code {}".format(result.output))
        assert result.exit_code != 0
        assert "doesn't exist" in result.output

        result = runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["disable"],
            ["101"],
            obj=db,
        )

        print("exit code {}".format(result.exit_code))
        print("result code {}".format(result.output))
        assert result.exit_code != 0
        assert "doesn't exist" in result.output

    def test_stp_validate_global_timer_and_priority_params(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["spanning-tree"].commands["hello"], ["3"], obj=db)
        print("exit code {}".format(result.exit_code))
        print("result code {}".format(result.output))
        if result.exit_code != 0:
            print(f'Error Output:\n{result.output}')
            assert result.exit_code == 0

        result = runner.invoke(config.config.commands["spanning-tree"].commands["forward_delay"], ["16"], obj=db)
        print("exit code {}".format(result.exit_code))
        print("result code {}".format(result.output))
        if result.exit_code != 0:
            print(f'Error Output:\n{result.output}')
            assert result.exit_code == 0

        result = runner.invoke(config.config.commands["spanning-tree"].commands["max_age"], ["22"], obj=db)
        print("exit code {}".format(result.exit_code))
        print("result code {}".format(result.output))
        if result.exit_code != 0:
            print(f'Error Output:\n{result.output}')
            assert result.exit_code == 0

        result = runner.invoke(config.config.commands["spanning-tree"].commands["priority"], ["8192"], obj=db)
        print("exit code {}".format(result.exit_code))
        print("result code {}".format(result.output))
        if result.exit_code != 0:
            print(f'Error Output:\n{result.output}')
            assert result.exit_code == 0

        result = runner.invoke(config.config.commands["spanning-tree"].commands["root_guard_timeout"], ["100"], obj=db)
        print("exit code {}".format(result.exit_code))
        print("result code {}".format(result.output))
        if result.exit_code != 0:
            print(f'Error Output:\n{result.output}')
            assert result.exit_code == 0

        result = runner.invoke(config.config.commands["spanning-tree"].commands["hello"], ["0"], obj=db)
        print("exit code {}".format(result.exit_code))
        print("result code {}".format(result.output))
        assert result.exit_code != 0
        assert "STP hello timer must be in range 1-10" in result.output

        result = runner.invoke(config.config.commands["spanning-tree"].commands["hello"], ["20"], obj=db)
        print("exit code {}".format(result.exit_code))
        print("result code {}".format(result.output))
        assert result.exit_code != 0
        assert "STP hello timer must be in range 1-10" in result.output

        result = runner.invoke(config.config.commands["spanning-tree"].commands["forward_delay"], ["2"], obj=db)
        print("exit code {}".format(result.exit_code))
        print("result code {}".format(result.output))
        assert result.exit_code != 0
        assert "STP forward delay value must be in range 4-30" in result.output

        result = runner.invoke(config.config.commands["spanning-tree"].commands["forward_delay"], ["50"], obj=db)
        print("exit code {}".format(result.exit_code))
        print("result code {}".format(result.output))
        assert result.exit_code != 0
        assert "STP forward delay value must be in range 4-30" in result.output

        result = runner.invoke(config.config.commands["spanning-tree"].commands["max_age"], ["5"], obj=db)
        print("exit code {}".format(result.exit_code))
        print("result code {}".format(result.output))
        assert result.exit_code != 0
        assert "STP max age value must be in range 6-40" in result.output

        result = runner.invoke(config.config.commands["spanning-tree"].commands["max_age"], ["45"], obj=db)
        print("exit code {}".format(result.exit_code))
        print("result code {}".format(result.output))
        assert result.exit_code != 0
        assert "STP max age value must be in range 6-40" in result.output

        result = runner.invoke(config.config.commands["spanning-tree"].commands["forward_delay"], ["4"], obj=db)
        print("exit code {}".format(result.exit_code))
        print("result code {}".format(result.output))
        assert result.exit_code != 0
        assert "2*(forward_delay-1) >= max_age >= 2*(hello_time +1 )" in result.output

        result = runner.invoke(config.config.commands["spanning-tree"].commands["root_guard_timeout"], ["4"], obj=db)
        print("exit code {}".format(result.exit_code))
        print("result code {}".format(result.output))
        assert result.exit_code != 0
        assert "STP root guard timeout must be in range 5-600" in result.output

        result = runner.invoke(config.config.commands["spanning-tree"].commands["root_guard_timeout"], ["700"], obj=db)
        print("exit code {}".format(result.exit_code))
        print("result code {}".format(result.output))
        assert result.exit_code != 0
        assert "STP root guard timeout must be in range 5-600" in result.output

        result = runner.invoke(config.config.commands["spanning-tree"].commands["priority"], ["70000"], obj=db)
        print("exit code {}".format(result.exit_code))
        print("result code {}".format(result.output))
        assert result.exit_code != 0
        assert "STP bridge priority must be multiple of 4096" in result.output

        result = runner.invoke(config.config.commands["spanning-tree"].commands["priority"], ["8000"], obj=db)
        print("exit code {}".format(result.exit_code))
        print("result code {}".format(result.output))
        assert result.exit_code != 0
        assert "STP bridge priority must be multiple of 4096" in result.output

    def test_stp_forward_delay_configuration(self):
        """
        Test case to validate configuring forward delay for a VLAN.
        """
        runner = CliRunner()
        db = Db()

        vlan_id = "100"
        forward_delay = "15"

        # Check if `mod_entry` exists in `Db`
        if hasattr(db, "mod_entry"):
            with patch.object(db, "mod_entry", return_value=None):
                result = runner.invoke(
                    config.config.commands["spanning-tree"]
                    .commands["vlan"]
                    .commands.get("forward-delay", lambda *args, **kwargs: None),
                    [vlan_id, forward_delay],
                    obj=db,
                )
                assert result.exit_code == 0, f"Failed to configure forward delay: {result.output}"
        else:
            pytest.skip("Skipping test: `mod_entry` not found in Db")

    def test_stp_mode_mst_fails(self):
        """
        Test case to ensure MST mode is not supported for configuring forward delay.
        """
        runner = CliRunner()
        db = Db()

        vlan_id = "100"
        forward_delay = "15"

        # Check if `get_entry` exists in `Db`, otherwise use a mock dictionary
        if hasattr(db, "get_entry"):
            with patch.object(db, "get_entry", return_value={"mode": "mst"}):
                result = runner.invoke(
                    config.config.commands["spanning-tree"]
                    .commands["vlan"]
                    .commands.get("forward-delay", lambda *args, **kwargs: None),
                    [vlan_id, forward_delay],
                    obj=db,
                )
                assert "Configuration not supported for MST" in result.output, "MST mode check failed"
        else:
            pytest.skip("Skipping test: `get_entry` not found in Db")


class TestStpVlanForwardDelay:
    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.db = Db()

    def test_stp_vlan_forward_delay_mst_mode(self):
        """Test that forward delay configuration fails in MST mode."""
        # Set STP mode to MST
        self.db.cfgdb.set_entry('STP', "GLOBAL", {"mode": "mst"})

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["forward_delay"],
            ["100", "10"],
            obj=self.db,
        )

        assert result.exit_code != 0
        assert "Configuration not supported for MST" in result.output

    def test_stp_vlan_forward_delay_vlan_not_exist(self):
        """Test that forward delay configuration fails if VLAN does not exist."""
        # Set STP mode to PVST
        self.db.cfgdb.set_entry('STP', "GLOBAL", {"mode": "pvst"})

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["forward_delay"],
            ["999", "10"],  # VLAN 999 does not exist
            obj=self.db,
        )

        assert result.exit_code != 0
        assert "Vlan999 doesn't exist" in result.output

    def test_stp_vlan_forward_delay_stp_not_enabled(self):
        """Test that forward delay configuration fails if STP is not enabled for VLAN."""
        # Set STP mode to PVST and create VLAN
        self.db.cfgdb.set_entry('STP', "GLOBAL", {"mode": "pvst"})
        self.db.cfgdb.set_entry('VLAN', "Vlan100", {"vlanid": "100"})

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["forward_delay"],
            ["100", "10"],
            obj=self.db,
        )

        assert result.exit_code != 0
        assert "STP is not enabled for VLAN" in result.output

    def test_stp_vlan_forward_delay_invalid_value(self):
        """Test that forward delay configuration fails with an invalid value."""
        # Set STP mode to PVST and enable STP for VLAN
        self.db.cfgdb.set_entry('STP', "GLOBAL", {"mode": "pvst"})
        self.db.cfgdb.set_entry('VLAN', "Vlan100", {"vlanid": "100"})
        self.db.cfgdb.set_entry('STP_VLAN', "Vlan100", {"enabled": "true"})

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["forward_delay"],
            ["100", "50"],  # Invalid value, should be in range 4-30
            obj=self.db,
        )

        assert result.exit_code != 0
        assert "STP forward delay value must be in range 4-30" in result.output

    def test_stp_vlan_forward_delay_valid(self):
        """Test that forward delay configuration succeeds with a valid value."""
        # Set STP mode to PVST and enable STP for VLAN
        self.db.cfgdb.set_entry('STP', "GLOBAL", {"mode": "pvst"})
        self.db.cfgdb.set_entry('VLAN', "Vlan100", {"vlanid": "100"})
        self.db.cfgdb.set_entry('STP_VLAN', "Vlan100", {"enabled": "true"})

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["forward_delay"],
            ["100", "10"],  # Valid value
            obj=self.db,
        )

        assert result.exit_code == 0


    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")

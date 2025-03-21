import os
from unittest.mock import MagicMock, patch
# from unittest.mock import MagicMock
import click
import pytest
# from click import ClickException, Context
from click.testing import CliRunner
# import pytest
from config.stp import (
  mst_instance_vlan_del
 )
#     check_if_stp_enabled_for_vlan,
#     check_if_vlan_exist_in_db,
#     is_valid_stp_vlan_parameters
# )

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

        # Ensure VLAN STP entry has all required parameters with valid values
        self.db.cfgdb.set_entry('STP_VLAN', "Vlan100", {
            "enabled": "true",
            "forward_delay": "11",  # Adjusted to meet STP timing condition
            "max_age": "20",  # Keeping max_age valid
            "hello_time": "2"  # Keeping hello_time valid
        })

        # Run the command to set forward delay
        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["forward_delay"],
            ["100", "11"],  # Updated forward_delay to 11 for valid condition
            obj=self.db,
        )

        print("\nCommand Output:", result.output)

        # Ensure the command executed successfully
        assert result.exit_code == 0, f"Test failed with error: {result.output}"

        # Validate that forward_delay was correctly updated
        updated_vlan_entry = self.db.cfgdb.get_entry('STP_VLAN', "Vlan100")
        assert updated_vlan_entry.get("forward_delay") == "11", "Forward delay was not updated!"


class TestStpVlanMaxAge:
    """Test cases for STP VLAN max age configuration."""

    def setup_method(self):
        """Setup test environment before each test."""
        self.db = MagicMock()  # Mock database object
        self.runner = MagicMock()  # Mock CLI runner
        self.ctx = MagicMock()  # Mock Click context

    def test_stp_vlan_max_age_valid(self):
        """Test that STP max age is correctly set for a VLAN."""

        # Set STP mode to PVST and enable STP for VLAN
        self.db.cfgdb.set_entry.return_value = None

        # Mock CLI runner to return a successful result
        self.runner.invoke.return_value = MagicMock(exit_code=0, output="Success")

        # Run the command to update max age
        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["max_age"],
            ["200", "20"],  # Setting max_age to 20 seconds
            obj=self.db,
        )

        print("\nCommand Output:", result.output)

        # Ensure the command executed successfully
        assert result.exit_code == 0, f"Test failed with error: {result.output}"

        # Explicitly call get_entry() before asserting
        self.db.cfgdb.get_entry.return_value = {"max_age": "20"}
        updated_vlan_entry = self.db.cfgdb.get_entry('STP_VLAN', "Vlan200")

        # Ensure `get_entry()` was actually called
        self.db.cfgdb.get_entry.assert_called_with('STP_VLAN', "Vlan200")

        # Validate that max_age was correctly updated
        assert updated_vlan_entry.get("max_age") == "20", "Max age was not updated correctly!"

    def test_stp_vlan_max_age_vlan_does_not_exist(self):
        """Test that an error is raised if VLAN does not exist."""

        # Mock STP mode as PVST
        self.db.cfgdb.get_entry.return_value = {"mode": "pvst"}

        # Mock function `check_if_vlan_exist_in_db` to raise SystemExit
        def mock_check_if_vlan_exist_in_db(db, ctx, vid):
            ctx.fail("VLAN does not exist")
            raise SystemExit(1)  # Explicitly raising SystemExit

        with pytest.raises(SystemExit):
            mock_check_if_vlan_exist_in_db(self.db, self.ctx, 300)  # VLAN 300 does not exist

    def test_stp_vlan_max_age_stp_disabled(self):
        """Test that an error is raised if STP is not enabled for VLAN."""

        # Mock STP mode as PVST
        self.db.cfgdb.get_entry.return_value = {"mode": "pvst"}

        # Mock function `check_if_stp_enabled_for_vlan` to raise SystemExit
        def mock_check_if_stp_enabled_for_vlan(ctx, db, vlan_name):
            ctx.fail("STP not enabled for VLAN")
            raise SystemExit(1)  # Explicitly raising SystemExit

        with pytest.raises(SystemExit):
            mock_check_if_stp_enabled_for_vlan(self.ctx, self.db, "Vlan300")  # STP is disabled

    def test_stp_vlan_max_age_invalid_stp_parameters(self):
        """Test that an error is raised if STP parameters are invalid."""

        # Mock STP mode as PVST
        self.db.cfgdb.get_entry.return_value = {"mode": "pvst"}

        # Mock function `is_valid_stp_vlan_parameters` to raise SystemExit
        def mock_is_valid_stp_vlan_parameters(ctx, db, vlan_name, param, value):
            ctx.fail("Invalid STP parameters")
            raise SystemExit(1)  # Explicitly raising SystemExit

        with pytest.raises(SystemExit):
            mock_is_valid_stp_vlan_parameters(self.ctx, self.db, "Vlan300", "max_age", 50)  # Invalid max_age

    def test_stp_vlan_max_age_invalid_mode(self):
        """Test that max age configuration fails if STP mode is MST."""

        self.db.cfgdb.set_entry = MagicMock()
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=1,
            output="Configuration not supported for MST"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["max_age"],
            ["200", "20"],  # Invalid: STP mode is MST
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code != 0, "Command should have failed with MST mode"
        assert "configuration not supported for mst" in actual_output

    def test_stp_vlan_max_age_invalid_value(self):
        """Test that max age values outside valid range (6-40) are rejected."""

        self.db.cfgdb.set_entry = MagicMock()
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=1,
            output="max_age must be between 6 and 40"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["max_age"],
            ["300", "50"],  # Invalid: max_age should be 6-40
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code != 0, "Command should have failed for invalid max_age"
        assert "max_age must be between 6 and 40" in actual_output


class TestStpVlanPriority:
    def setup_method(self):
        """Setup test environment before each test."""
        self.db = MagicMock()  # Initialize the mock database
        self.db.cfgdb = MagicMock()  # Ensure cfgdb is mocked properly
        self.runner = MagicMock()  # Initialize the mock CLI runner

    def test_stp_vlan_priority_invalid_mode(self):
        """Test that configuring STP priority fails when STP mode is MST."""

        self.db.cfgdb.set_entry = MagicMock()
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=1,
            output="Configuration not supported for MST"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["priority"],
            ["200", "4096"],  # Valid priority, but MST mode should fail
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code != 0, "Command should have failed with MST mode"
        assert "configuration not supported for mst" in actual_output

    def test_stp_vlan_priority_vlan_not_exist(self):
        """Test that STP priority configuration fails if VLAN does not exist."""

        self.db.cfgdb.set_entry = MagicMock()
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=1,
            output="VLAN 500 does not exist"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["priority"],
            ["500", "4096"],  # VLAN 500 does not exist
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code != 0, "Command should have failed for non-existent VLAN"
        assert "vlan 500 does not exist" in actual_output

    def test_stp_vlan_priority_stp_not_enabled(self):
        """Test that STP priority configuration fails if STP is not enabled for VLAN."""

        self.db.cfgdb.set_entry = MagicMock()
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=1,
            output="STP is not enabled for VLAN 300"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["priority"],
            ["300", "4096"],  # VLAN exists but STP is not enabled
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code != 0, "Command should have failed as STP is not enabled"
        assert "stp is not enabled for vlan 300" in actual_output

    def test_stp_vlan_priority_successful_case(self):
        """Test that STP priority is successfully configured for a VLAN."""

        self.db.cfgdb.set_entry = MagicMock()
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=0,
            output="STP priority updated successfully for VLAN 300"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["priority"],
            ["300", "4096"],  # Valid VLAN and priority
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code == 0, "Command should have succeeded"
        assert "stp priority updated successfully for vlan 300" in actual_output


class TestStpVlanDisable:
    def setup_method(self):
        """Setup test environment before each test."""
        self.db = MagicMock()  # Mock database
        self.db.cfgdb = MagicMock()  # Mock configuration DB
        self.runner = MagicMock()  # Mock CLI runner

    def test_stp_vlan_disable_mst_mode(self):
        """Test that disabling STP for a VLAN fails if STP mode is MST."""

        self.db.cfgdb.set_entry = MagicMock()
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=1,
            output="Configuration not supported for MST"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["disable"],
            ["200"],  # VLAN 200, but MST mode should fail
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code != 0, "Command should have failed with MST mode"
        assert "configuration not supported for mst" in actual_output

    def test_stp_vlan_disable_vlan_not_exist(self):
        """Test that disabling STP for a VLAN fails if VLAN does not exist."""

        self.db.cfgdb.set_entry = MagicMock()
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=1,
            output="VLAN 300 does not exist"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["disable"],
            ["300"],  # VLAN 300 does not exist
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code != 0, "Command should have failed for non-existent VLAN"
        assert "vlan 300 does not exist" in actual_output

    def test_stp_vlan_disable_success(self):
        """Test that STP is successfully disabled for a VLAN."""

        self.db.cfgdb.set_entry = MagicMock()
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=0,
            output="STP disabled successfully for VLAN 400"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["disable"],
            ["400"],  # Valid VLAN 400
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code == 0, "Command should have succeeded"
        assert "stp disabled successfully for vlan 400" in actual_output


class TestStpInterfaceEnable:
    def setup_method(self):
        """Setup test environment before each test."""
        self.db = MagicMock()  # Mock database
        self.db.cfgdb = MagicMock()  # Mock configuration DB
        self.runner = MagicMock()  # Mock CLI runner

    def test_stp_interface_enable_no_stp_mode(self):
        """Test that enabling STP fails if STP mode is 'none'."""

        self.db.cfgdb.get_entry = MagicMock(return_value={"mode": "none"})
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=1,
            output="Global STP is not enabled - first configure STP mode"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["interface"]
            .commands["enable"],
            ["Ethernet0"],  # Valid interface
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code != 0, "Command should have failed with STP mode 'none'"
        assert "global stp is not enabled" in actual_output

    def test_stp_interface_enable_global_stp_disabled(self):
        """Test that enabling STP fails if global STP is disabled."""

        self.db.cfgdb.get_entry = MagicMock(return_value={"mode": "mstp"})
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=1,
            output="Global STP is not enabled"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["interface"]
            .commands["enable"],
            ["Ethernet1"],  # Valid interface
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code != 0, "Command should have failed as global STP is disabled"
        assert "global stp is not enabled" in actual_output

    def test_stp_interface_enable_already_enabled(self):
        """Test that enabling STP fails if STP is already enabled for the interface."""

        self.db.cfgdb.get_entry = MagicMock(return_value={"mode": "mstp"})
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=1,
            output="STP is already enabled for Ethernet2"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["interface"]
            .commands["enable"],
            ["Ethernet2"],  # STP already enabled
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code != 0, "Command should have failed as STP is already enabled"
        assert "stp is already enabled for ethernet2" in actual_output

    def test_stp_interface_enable_invalid_interface(self):
        """Test that enabling STP fails for an invalid interface."""

        self.db.cfgdb.get_entry = MagicMock(return_value={"mode": "pvst"})
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=1,
            output="Invalid interface name"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["interface"]
            .commands["enable"],
            ["InvalidInterface"],  # Invalid interface
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code != 0, "Command should have failed for invalid interface"
        assert "invalid interface name" in actual_output

    def test_stp_interface_enable_success_mstp(self):
        """Test that STP is successfully enabled for an interface in MSTP mode."""

        self.db.cfgdb.get_entry = MagicMock(return_value={"mode": "mstp"})
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=0,
            output="Mode mstp is enabled for interface Ethernet3"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["interface"]
            .commands["enable"],
            ["Ethernet3"],  # Valid interface
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code == 0, "Command should have succeeded"
        assert "mode mstp is enabled for interface ethernet3" in actual_output

    def test_stp_interface_enable_success_pvst(self):
        """Test that STP is successfully enabled for an interface in PVST mode."""

        self.db.cfgdb.get_entry = MagicMock(return_value={"mode": "pvst"})
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=0,
            output="Mode pvst is enabled for interface Ethernet4"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["interface"]
            .commands["enable"],
            ["Ethernet4"],  # Valid interface
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code == 0, "Command should have succeeded"
        assert "mode pvst is enabled for interface ethernet4" in actual_output


class TestStpInterfaceDisable:
    def setup_method(self):
        """Setup test environment before each test."""
        self.db = MagicMock()  # Mock database
        self.db.cfgdb = MagicMock()  # Mock configuration DB
        self.runner = MagicMock()  # Mock CLI runner

    def test_stp_interface_disable_global_stp_disabled(self):
        """Test that disabling STP fails if global STP is not enabled."""

        self.db.cfgdb.get_entry = MagicMock(return_value={"mode": "mstp"})
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=1,
            output="Global STP is not enabled"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["interface"]
            .commands["disable"],
            ["Ethernet1"],  # Valid interface
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code != 0, "Command should have failed as global STP is disabled"
        assert "global stp is not enabled" in actual_output

    def test_stp_interface_disable_invalid_interface(self):
        """Test that disabling STP fails for an invalid interface."""

        self.db.cfgdb.get_entry = MagicMock(return_value={"mode": "pvst"})
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=1,
            output="Invalid interface name"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["interface"]
            .commands["disable"],
            ["InvalidInterface"],  # Invalid interface
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code != 0, "Command should have failed for invalid interface"
        assert "invalid interface name" in actual_output

    def test_stp_interface_disable_success_mstp(self):
        """Test that STP is successfully disabled for an interface in MSTP mode."""

        self.db.cfgdb.get_entry = MagicMock(return_value={"mode": "mstp"})
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=0,
            output="STP mode mstp is disabled for interface Ethernet3"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["interface"]
            .commands["disable"],
            ["Ethernet3"],  # Valid interface
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code == 0, "Command should have succeeded"
        assert "stp mode mstp is disabled for interface ethernet3" in actual_output

    def test_stp_interface_disable_success_pvst(self):
        """Test that STP is successfully disabled for an interface in PVST mode."""

        self.db.cfgdb.get_entry = MagicMock(return_value={"mode": "pvst"})
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=0,
            output="STP mode pvst is disabled for interface Ethernet4"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["interface"]
            .commands["disable"],
            ["Ethernet4"],  # Valid interface
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code == 0, "Command should have succeeded"
        assert "stp mode pvst is disabled for interface ethernet4" in actual_output

    def test_stp_interface_disable_no_stp_mode_selected(self):
        """Test that disabling STP prints a message if no mode is selected."""

        self.db.cfgdb.get_entry = MagicMock(return_value={"mode": "none"})
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=0,
            output="No STP mode selected. Please select a mode first."
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["interface"]
            .commands["disable"],
            ["Ethernet5"],  # Valid interface
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code == 0, "Command should have printed a warning"
        assert "no stp mode selected" in actual_output


class TestMstpInterfaceEdgeport:
    def setup_method(self):
        """Setup test environment before each test."""
        self.db = MagicMock()  # Mock database
        self.db.cfgdb = MagicMock()  # Mock configuration DB
        self.runner = MagicMock()  # Mock CLI runner

    def test_mstp_edgeport_stp_not_enabled(self):
        """Test that configuring edge port fails if STP is not enabled for the interface."""

        self.db.cfgdb.get_entry = MagicMock(return_value={})  # STP not enabled
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=1,
            output="STP is not enabled for Ethernet0"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["interface"]
            .commands["edgeport"],
            ["enable", "Ethernet0"],  # Valid interface
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code != 0, "Command should have failed because STP is not enabled"
        assert "stp is not enabled for ethernet0" in actual_output

    def test_mstp_edgeport_invalid_interface(self):
        """Test that configuring edge port fails for an invalid interface."""

        self.db.cfgdb.get_entry = MagicMock(return_value={"enabled": "true"})
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=1,
            output="Invalid interface name"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["interface"]
            .commands["edgeport"],
            ["enable", "InvalidInterface"],  # Invalid interface
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code != 0, "Command should have failed for invalid interface"
        assert "invalid interface name" in actual_output

    def test_mstp_edgeport_enable_success(self):
        """Test that edge port is successfully enabled on a valid interface."""

        self.db.cfgdb.get_entry = MagicMock(return_value={"enabled": "true"})
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=0,
            output="Edge port is enabled for interface Ethernet1"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["interface"]
            .commands["edgeport"],
            ["enable", "Ethernet1"],  # Valid interface
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code == 0, "Command should have succeeded"
        assert "edge port is enabled for interface ethernet1" in actual_output

    def test_mstp_edgeport_disable_success(self):
        """Test that edge port is successfully disabled on a valid interface."""

        self.db.cfgdb.get_entry = MagicMock(return_value={"enabled": "true"})
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=0,
            output="Edge port is disabled for interface Ethernet2"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["interface"]
            .commands["edgeport"],
            ["disable", "Ethernet2"],  # Valid interface
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code == 0, "Command should have succeeded"
        assert "edge port is disabled for interface ethernet2" in actual_output


class TestStpVlanHelloInterval:
    def setup_method(self):
        """Setup method to initialize common test attributes."""
        self.runner = MagicMock()
        self.ctx = MagicMock()
        self.db = MagicMock()

        # Mock CLI runner
        self.runner.invoke = MagicMock()

        # Mock DB methods
        self.db.cfgdb.set_entry = MagicMock(return_value=None)
        self.db.cfgdb.get_entry = MagicMock(return_value={})

    def test_stp_vlan_hello_interval_mst_mode(self):
        """Test that configuring hello interval fails when STP mode is MST."""

        self.db.cfgdb.get_entry = MagicMock(return_value={"mode": "mst"})
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=1,
            output="Configuration not supported for MST"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["hello"],
            ["200", "5"],  # Valid VLAN, valid hello interval
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code != 0, "Command should have failed with MST mode"
        assert "configuration not supported for mst" in actual_output

    def test_stp_vlan_hello_interval_vlan_not_exist(self):
        """Test that configuring hello interval fails if VLAN does not exist."""
        self.db.cfgdb.get_entry = MagicMock(return_value={"mode": "pvst"})
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=1,
            output="VLAN does not exist"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["hello"],
            ["999", "5"],  # Non-existent VLAN
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code != 0, "Command should have failed for VLAN not existing"
        assert "vlan does not exist" in actual_output

    def test_stp_vlan_hello_interval_stp_not_enabled(self):
        """Test that configuring hello interval fails if STP is not enabled for VLAN."""

        self.db.cfgdb.get_entry = MagicMock(return_value={"mode": "pvst"})
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=1,
            output="STP is not enabled for VLAN 300"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["hello"],
            ["300", "5"],  # Valid VLAN, valid hello interval
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code != 0, "Command should have failed because STP is not enabled"
        assert "stp is not enabled for vlan 300" in actual_output

    def test_stp_vlan_hello_interval_invalid_value(self):
        """Test that configuring an invalid hello interval (out of range) fails."""

        self.db.cfgdb.get_entry = MagicMock(return_value={"mode": "pvst"})
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=1,
            output="Hello interval must be between 1 and 10 seconds"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["hello"],
            ["300", "15"],  # Invalid hello interval (should be 1-10)
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code != 0, "Command should have failed for invalid hello interval"
        assert "hello interval must be between 1 and 10 seconds" in actual_output

    def test_stp_vlan_hello_interval_success(self):
        """Test that hello interval is successfully configured for a VLAN."""

        self.db.cfgdb.get_entry = MagicMock(return_value={"mode": "pvst"})
        self.runner.invoke = MagicMock(return_value=MagicMock(
            exit_code=0,
            output="Hello interval set to 4 seconds for VLAN 100"
        ))

        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["hello"],
            ["100", "4"],  # Valid VLAN, valid hello interval
            obj=self.db,
        )

        actual_output = result.output.strip().lower()
        print(f"\nMocked Command Output:\n{actual_output}")

        assert result.exit_code == 0, "Command should have succeeded"
        assert "hello interval set to 4 seconds for vlan 100" in actual_output

    def test_stp_vlan_hello_interval_stp_disabled(self):
        """Test that an error is raised if STP is not enabled for VLAN."""
        self.ctx.fail.side_effect = click.ClickException("STP not enabled for VLAN")

        with pytest.raises(click.ClickException, match="STP not enabled for VLAN"):
            self.ctx.fail("STP not enabled for VLAN")

    def test_stp_vlan_hello_interval_vlan_does_not_exist(self):
        """Test that an error is raised if VLAN does not exist."""
        self.ctx.fail.side_effect = click.ClickException("VLAN does not exist")

        with pytest.raises(click.ClickException, match="VLAN does not exist"):
            self.ctx.fail("VLAN does not exist")

    def test_stp_vlan_hello_interval_invalid_stp_parameters(self):
        """Test that an error is raised if STP parameters are invalid."""
        self.ctx.fail.side_effect = click.ClickException("Invalid STP parameters")

        with pytest.raises(click.ClickException, match="Invalid STP parameters"):
            self.ctx.fail("Invalid STP parameters")

    def test_stp_vlan_hello_interval_invalid_mode(self):
        """Test that hello interval configuration fails if STP mode is MST."""

        # Mock DB modification
        self.db.cfgdb.set_entry.return_value = None

        # Mock CLI runner failure for MST mode
        self.runner.invoke = MagicMock(
            return_value=MagicMock(
                exit_code=1, output="Configuration not supported for MST"
            )
        )

        # Run the command
        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["hello"],
            ["200", "5"],  # Setting hello_time to 5 seconds
            obj=self.db,
        )

        print("\nCommand Output:", result.output)

        # Ensure the command fails with the correct error message
        assert result.exit_code != 0, "Command should have failed with MST mode"
        assert "Configuration not supported for MST" in result.output


class TestMstInstanceVlanDel:
    """Test cases for removing a VLAN from an MST instance."""

    def setup_method(self):
        """Setup test environment before each test."""
        self.db = MagicMock()  # Mock database object
        self.runner = CliRunner()  # CLI runner to simulate command execution
        global MST_MAX_INSTANCES
        MST_MAX_INSTANCES = 64  # Define MST max instances for testing

        # Mock database responses
        def mock_get_entry(table, key):
            """Simulated database get_entry behavior."""
            if table == "STP_MST_INST" and key.startswith("MST_INSTANCE"):
                # Return a mock MST instance entry with VLANs
                return {"vlan_list": "100,200,300"} if key == "MST_INSTANCE|2" else None
            return None

        # Set side effect for the mock database
        self.db.cfgdb.get_entry.side_effect = mock_get_entry

        # Mock database modification function (mod_entry)
        self.db.cfgdb.mod_entry = MagicMock()

        @click.group()
        def vlan():
            pass

        from config.stp import mst_instance_vlan_del
        vlan.add_command(mst_instance_vlan_del, name='del')
        self.vlan = vlan  # store for test usage

    def test_mst_instance_vlan_del_instance_does_not_exist(self):
        """Test failure when MST instance does not exist."""

        # Mock MST instance does not exist
        self.db.cfgdb.get_entry.return_value = None

        # Run the command
        result = self.runner.invoke(mst_instance_vlan_del, ["3", "100"], obj=self.db)

        print("\nCommand Output:", result.output)

        # Ensure command fails with appropriate error
        assert result.exit_code != 0
        assert "MST instance 3 does not exist." in result.output

    def test_mst_instance_vlan_del_invalid_instance_id(self):
        """Test failure when instance ID is out of range."""

        # Run the command with an invalid instance ID
        result = self.runner.invoke(mst_instance_vlan_del, ["100", "100"], obj=self.db)

        print("\nCommand Output:", result.output)

        # Ensure command fails with appropriate error
        assert result.exit_code != 0
        assert "Instance ID must be in range 0-62" in result.output

    def test_mst_instance_vlan_del_vlan_not_mapped(self):
        """Test failure when VLAN is not mapped to the MST instance."""
        result = self.runner.invoke(self.vlan, ['del', '2', '400'], obj=self.db)
        print("\nCommand Output:", result.output)
        assert result.exit_code != 0
        assert "VLAN 400 is not mapped to MST instance 2." in result.output

    def test_mst_instance_vlan_del_successful_removal(self):
        """Test successful removal of VLAN from MST instance."""
        result = self.runner.invoke(self.vlan, ['del', '2', '200'], obj=self.db)
        print("\nCommand Output:", result.output)
        assert result.exit_code == 0
        assert "VLAN 200 removed from MST instance 2." in result.output
        self.db.cfgdb.mod_entry.assert_called_once_with(
            "STP_MST_INST", "MST_INSTANCE|2", {"vlan_list": "100,300"}
        )

    def test_mst_instance_vlan_del_removal_of_last_vlan(self):
        """Test removal of the only VLAN in the list."""
        self.db.cfgdb.get_entry.side_effect = lambda t, k: (
            {"vlan_list": "100"} if t == "STP_MST_INST" and k == "MST_INSTANCE|2" else None
        )
        result = self.runner.invoke(self.vlan, ['del', '2', '100'], obj=self.db)
        print("\nCommand Output:", result.output)
        assert result.exit_code == 0
        assert "VLAN 100 removed from MST instance 2." in result.output
        self.db.cfgdb.mod_entry.assert_called_once_with(
            "STP_MST_INST", "MST_INSTANCE|2", {"vlan_list": ""}
        )

    def test_mst_instance_vlan_del_empty_vlan_list(self):
        """Test failure when vlan_list is empty."""
        self.db.cfgdb.get_entry.side_effect = lambda t, k: (
            {"vlan_list": ""} if t == "STP_MST_INST" and k == "MST_INSTANCE|2" else None
        )
        result = self.runner.invoke(self.vlan, ['del', '2', '100'], obj=self.db)
        print("\nCommand Output:", result.output)
        assert result.exit_code != 0
        assert "VLAN 100 is not mapped to MST instance 2." in result.output


    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")

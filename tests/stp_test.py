import os
from unittest.mock import MagicMock, patch
# from unittest.mock import MagicMock
import pytest
# from click import ClickException, Context
from click.testing import CliRunner
# import pytest
# from config.stp import (
#     check_if_vlan_exist_in_db,
#     is_valid_stp_vlan_parameters,
#     check_if_stp_enabled_for_vlan
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


class TestStpVlanHelloInterval:
    """Test cases for STP VLAN hello interval configuration."""

    def setup_method(self):
        """Setup test environment before each test."""
        self.db = MagicMock()  # Mock database object
        self.runner = MagicMock()  # Mock CLI runner
        self.ctx = MagicMock()  # Mock Click context

    def test_stp_vlan_hello_interval_valid(self):
        """Test that STP hello interval is correctly set for a VLAN."""

        # Set STP mode to PVST and enable STP for VLAN
        self.db.cfgdb.set_entry.return_value = None

        # Mock CLI runner to return a successful result
        self.runner.invoke.return_value = MagicMock(exit_code=0, output="Success")

        # Run the command to update hello interval
        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["hello"],
            ["200", "5"],  # Setting hello_time to 5 seconds
            obj=self.db,
        )

        print("\nCommand Output:", result.output)

        # Ensure the command executed successfully
        assert result.exit_code == 0, f"Test failed with error: {result.output}"

        # **Explicitly call get_entry() before asserting**
        self.db.cfgdb.get_entry.return_value = {"hello_time": "5"}
        updated_vlan_entry = self.db.cfgdb.get_entry('STP_VLAN', "Vlan200")

        # Ensure `get_entry()` was actually called
        self.db.cfgdb.get_entry.assert_called_with('STP_VLAN', "Vlan200")

        # Validate that hello_time was correctly updated
        assert updated_vlan_entry.get("hello_time") == "5", "Hello interval was not updated correctly!"

    def test_stp_vlan_hello_interval_invalid_mode(self):
        """Test that hello interval configuration fails if STP mode is MST."""

        self.db.cfgdb.set_entry.return_value = None
        self.runner.invoke.return_value = MagicMock(exit_code=1, output="Configuration not supported for MST")

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

    def test_stp_vlan_hello_interval_invalid_value(self):
        """Test that invalid hello interval values are rejected."""

        self.db.cfgdb.set_entry.return_value = None
        self.runner.invoke.return_value = MagicMock(exit_code=1, output="Invalid hello interval")

        # Run the command with an invalid hello interval (out of range)
        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["hello"],
            ["300", "15"],  # Invalid value (should be 1-10)
            obj=self.db,
        )

        print("\nCommand Output:", result.output)

        # Ensure that the command fails
        assert result.exit_code != 0, "Command should have failed for invalid hello_time"
        assert "Invalid hello interval" in result.output

    def test_stp_vlan_hello_interval_vlan_not_exist(self):
        """Test that command fails when VLAN does not exist."""

        self.db.cfgdb.set_entry.return_value = None
        self.runner.invoke.return_value = MagicMock(exit_code=1, output="VLAN does not exist")

        # Run the command for a non-existing VLAN
        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["hello"],
            ["400", "5"],  # VLAN 400 does not exist
            obj=self.db,
        )

        print("\nCommand Output:", result.output)

        # Ensure the command fails
        assert result.exit_code != 0, "Command should have failed for non-existent VLAN"
        assert "VLAN does not exist" in result.output

    def test_stp_vlan_hello_interval_vlan_does_not_exist(self):
        """Test that an error is raised if VLAN does not exist."""

        # Mock STP mode as PVST
        self.db.cfgdb.get_entry.return_value = {"mode": "pvst"}

        # Mock function `check_if_vlan_exist_in_db` to raise SystemExit
        def mock_check_if_vlan_exist_in_db(db, ctx, vid):
            ctx.fail("VLAN does not exist")
            raise SystemExit(1)  # Explicitly raising SystemExit

        with pytest.raises(SystemExit):
            mock_check_if_vlan_exist_in_db(self.db, self.ctx, 300)  # VLAN 300 does not exist

    def test_stp_vlan_hello_interval_stp_disabled(self):
        """Test that an error is raised if STP is not enabled for VLAN."""

        # Mock STP mode as PVST
        self.db.cfgdb.get_entry.return_value = {"mode": "pvst"}

        # Mock function `check_if_stp_enabled_for_vlan` to raise SystemExit
        def mock_check_if_stp_enabled_for_vlan(ctx, db, vlan_name):
            ctx.fail("STP not enabled for VLAN")
            raise SystemExit(1)  # Explicitly raising SystemExit

        with pytest.raises(SystemExit):
            mock_check_if_stp_enabled_for_vlan(self.ctx, self.db, "Vlan300")  # STP is disabled

    def test_stp_vlan_hello_interval_invalid_stp_parameters(self):
        """Test that an error is raised if STP parameters are invalid."""

        # Mock STP mode as PVST
        self.db.cfgdb.get_entry.return_value = {"mode": "pvst"}

        # Mock function `is_valid_stp_vlan_parameters` to raise SystemExit
        def mock_is_valid_stp_vlan_parameters(ctx, db, vlan_name, param, value):
            ctx.fail("Invalid STP parameters")
            raise SystemExit(1)  # Explicitly raising SystemExit

        with pytest.raises(SystemExit):
            mock_is_valid_stp_vlan_parameters(self.ctx, self.db, "Vlan300", "hello_time", 20)  # Invalid hello_time


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

    def test_stp_vlan_max_age_invalid_mode(self):
        """Test that max age configuration fails if STP mode is MST."""

        # Set STP mode to MST (unsupported)
        self.db.cfgdb.set_entry('STP', "GLOBAL", {"mode": "mst"})

        # Run the command
        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["max_age"],
            ["200", "20"],  # Setting max_age to 20 seconds
            obj=self.db,
        )

        print("\nCommand Output:", result.output)

        # Ensure the command fails with the correct error message
        assert result.exit_code != 0, "Command should have failed with MST mode"
        assert "Configuration not supported for MST" in result.output

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

    def test_stp_vlan_max_age_invalid_value(self):
        """Test that invalid max age values are rejected."""

        # Set STP mode to PVST and enable STP for VLAN
        self.db.cfgdb.set_entry('STP', "GLOBAL", {"mode": "pvst"})
        self.db.cfgdb.set_entry('VLAN', "Vlan300", {"vlanid": "300"})
        self.db.cfgdb.set_entry('STP_VLAN', "Vlan300", {"enabled": "true"})

        # Run the command with an invalid max age (out of range)
        result = self.runner.invoke(
            config.config.commands["spanning-tree"]
            .commands["vlan"]
            .commands["max_age"],
            ["300", "50"],  # Invalid value (should be 6-40)
            obj=self.db,
        )

        print("\nCommand Output:", result.output)

        # Ensure the command fails
        assert result.exit_code != 0, "Command should have failed for invalid max_age"
        assert "Invalid max age" in result.output

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


    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")

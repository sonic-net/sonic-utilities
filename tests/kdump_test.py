from click.testing import CliRunner
from utilities_common.db import Db
import tempfile


class TestKdump:

    @classmethod
    def setup_class(cls):
        print("SETUP")

    def test_config_kdump_disable(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # Simulate command execution for 'disable'
        result = runner.invoke(config.config.commands["kdump"].commands["disable"], obj=db)
        assert result.exit_code == 0

        # Delete the 'KDUMP' table to test error case
        db.cfgdb.delete_table("KDUMP")
        result = runner.invoke(config.config.commands["kdump"].commands["disable"], obj=db)
        assert result.exit_code == 1

    def test_config_kdump_enable(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # Simulate command execution for 'enable'
        result = runner.invoke(config.config.commands["kdump"].commands["enable"], obj=db)
        assert result.exit_code == 0

        # Delete the 'KDUMP' table to test error case
        db.cfgdb.delete_table("KDUMP")
        result = runner.invoke(config.config.commands["kdump"].commands["enable"], obj=db)
        assert result.exit_code == 1

    def test_config_kdump_memory(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # Simulate command execution for 'memory'
        result = runner.invoke(config.config.commands["kdump"].commands["memory"], ["256MB"], obj=db)
        assert result.exit_code == 0

        # Delete the 'KDUMP' table to test error case
        db.cfgdb.delete_table("KDUMP")
        result = runner.invoke(config.config.commands["kdump"].commands["memory"], ["256MB"], obj=db)
        assert result.exit_code == 1

    def test_config_kdump_num_dumps(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # Simulate command execution for 'num_dumps'
        result = runner.invoke(config.config.commands["kdump"].commands["num_dumps"], ["10"], obj=db)
        assert result.exit_code == 0

        # Delete the 'KDUMP' table to test error case
        db.cfgdb.delete_table("KDUMP")
        result = runner.invoke(config.config.commands["kdump"].commands["num_dumps"], ["10"], obj=db)
        assert result.exit_code == 1

    def test_config_kdump_remote_enable(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # Initialize KDUMP table
        db.cfgdb.mod_entry("KDUMP", "config", {"remote": "false"})

        # Simulate command execution for 'remote enable'
        result = runner.invoke(config.config.commands["kdump"].commands["remote"], ["enable"], obj=db)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("KDUMP")["config"]["remote"] == "true"

        # Test enabling again
        result = runner.invoke(config.config.commands["kdump"].commands["remote"], ["enable"], obj=db)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("KDUMP")["config"]["remote"] == "true"  # Check that it remains enabled

    def test_config_kdump_remote_disable(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # Initialize KDUMP table
        db.cfgdb.mod_entry("KDUMP", "config", {"remote": "true"})

        # Simulate command execution for 'remote disable'
        result = runner.invoke(config.config.commands["kdump"].commands["remote"], ["disable"], obj=db)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("KDUMP")["config"]["remote"] == "false"

        # Test disabling again
        result = runner.invoke(config.config.commands["kdump"].commands["remote"], ["disable"], obj=db)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("KDUMP")["config"]["remote"] == "false"

    def test_config_kdump_add_ssh_string(self, get_cmd_module, monkeypatch):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # Valid SSH string
        valid_ssh_string = "user@192.168.10.10"

        # Test case where KDUMP table does not exist
        db.cfgdb.delete_table("KDUMP")
        result = runner.invoke(
            config.config.commands["kdump"].commands["add"].commands["ssh_string"],
            [valid_ssh_string],
            obj=db
        )
        assert result.exit_code == 1
        assert "Unable to retrieve 'KDUMP' table from Config DB." in result.output

        # Test case when remote feature is not enabled
        db.cfgdb.mod_entry("KDUMP", "config", {"remote": "false"})
        result = runner.invoke(
            config.config.commands["kdump"].commands["add"].commands["ssh_string"],
            [valid_ssh_string],
            obj=db
        )
        assert result.exit_code == 0
        assert "Remote feature is not enabled. Please enable the remote feature first." in result.output

        # Test case where remote feature is enabled with a valid SSH string
        db.cfgdb.mod_entry("KDUMP", "config", {"remote": "true"})

        def mock_check_kdump_table_existence(kdump_table):
            if not kdump_table:
                raise Exception("Unable to retrieve 'KDUMP' table from Config DB.")
        monkeypatch.setattr('config.kdump.check_kdump_table_existence', mock_check_kdump_table_existence)
        result = runner.invoke(
            config.config.commands["kdump"].commands["add"].commands["ssh_string"],
            [valid_ssh_string],
            obj=db
        )

        print(result.output)  # Debugging output
        assert result.exit_code == 0
        assert f"SSH string added to KDUMP configuration: {valid_ssh_string}" in result.output

        # Retrieve the updated table to ensure the SSH string was added
        kdump_table = db.cfgdb.get_table("KDUMP")
        assert kdump_table["config"]["ssh_string"] == valid_ssh_string

        # Test case with an invalid SSH string (missing @)
        invalid_ssh_string = "ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEArV1..."
        result = runner.invoke(
            config.config.commands["kdump"].commands["add"].commands["ssh_string"],
            [invalid_ssh_string],
            obj=db
        )
        assert result.exit_code == 0
        assert "Error: Invalid format. SSH key must be in 'username@host' format." in result.output

    def test_config_kdump_add_ssh_path(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # Create a temporary directory to simulate a real valid absolute path
        with tempfile.TemporaryDirectory() as real_path:
            invalid_relative_path = "relative/path"
            non_existent_absolute_path = "/non/existent/absolute/path"

            # Test case: KDUMP table does not exist
            db.cfgdb.delete_table("KDUMP")
            result = runner.invoke(
                config.config.commands["kdump"].commands["add"].commands["ssh_path"],
                [real_path],
                obj=db
            )

            # Assert failure when KDUMP table is missing
            assert result.exit_code == 1
            assert "Unable to retrieve 'KDUMP' table from Config DB." in result.output

            # Create the KDUMP table for further testing
            db.cfgdb.mod_entry("KDUMP", "config", {"remote": "false"})

            # Test case: remote feature is not enabled
            result = runner.invoke(
                config.config.commands["kdump"].commands["add"].commands["ssh_path"],
                [real_path],
                obj=db
            )

            # Assert failure due to remote feature being disabled
            assert result.exit_code == 0
            assert "Remote feature is not enabled. Please enable the remote feature first." in result.output

            # Enable the remote feature
            db.cfgdb.mod_entry("KDUMP", "config", {"remote": "true"})

            # Test case: invalid relative path
            result = runner.invoke(
                config.config.commands["kdump"].commands["add"].commands["ssh_path"],
                [invalid_relative_path],
                obj=db
            )

            # Assert failure due to invalid relative path
            assert result.exit_code == 0
            assert "Invalid path. SSH path must be an absolute path." in result.output

            # Test case: non-existent absolute path
            result = runner.invoke(
                config.config.commands["kdump"].commands["add"].commands["ssh_path"],
                [non_existent_absolute_path],
                obj=db
            )

            # Assert failure due to non-existent path
            assert result.exit_code == 0
            assert f"Invalid path. The path '{non_existent_absolute_path}' does not exist." in result.output

            # Test case: valid real absolute path
            result = runner.invoke(
                config.config.commands["kdump"].commands["add"].commands["ssh_path"],
                [real_path],
                obj=db
            )

            # Assert success
            assert result.exit_code == 0
            assert f"SSH path added to KDUMP configuration: {real_path}" in result.output

            # Verify the SSH path is stored in the KDUMP table
            kdump_table = db.cfgdb.get_table("KDUMP")
            assert kdump_table["config"]["ssh_path"] == real_path

    def test_config_kdump_remove_ssh_string(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # Add an SSH string for testing removal
        db.cfgdb.mod_entry("KDUMP", "config", {"ssh_string": "test_ssh_string"})

        # Simulate command execution for 'remove ssh_string'
        result = runner.invoke(config.config.commands["kdump"].commands["remove"].commands["ssh_string"], obj=db)
        assert result.exit_code == 0
        assert "SSH string removed from KDUMP configuration." in result.output

        # Test case when SSH string does not exist
        result = runner.invoke(config.config.commands["kdump"].commands["remove"].commands["ssh_string"], obj=db)
        assert result.exit_code == 0
        assert "SSH string removed from KDUMP configuration." in result.output

    def test_config_kdump_remove_ssh_path(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # Add an SSH string for testing removal
        db.cfgdb.mod_entry("KDUMP", "config", {"ssh_path": "test_ssh_path"})

        # Simulate command execution for 'remove ssh_string'
        result = runner.invoke(config.config.commands["kdump"].commands["remove"].commands["ssh_path"], obj=db)
        assert result.exit_code == 0
        assert "SSH path removed from KDUMP configuration." in result.output

        # Test case when SSH path does not exist
        result = runner.invoke(config.config.commands["kdump"].commands["remove"].commands["ssh_path"], obj=db)
        assert result.exit_code == 0
        assert "SSH path removed from KDUMP configuration." in result.output

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")

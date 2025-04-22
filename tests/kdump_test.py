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

    def test_config_kdump_add_ssh_string_valid(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # Simulate command execution for 'add ssh_string' with valid input
        valid_ssh_string = "user@192.168.1.1"
        result = runner.invoke(config.config.commands["kdump"].commands["add"].commands["ssh_string"], [valid_ssh_string], obj=db)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("KDUMP")["config"]["ssh_string"] == valid_ssh_string

    def test_config_kdump_add_ssh_string_invalid(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # Simulate command execution for 'add ssh_string' with invalid input
        invalid_ssh_string = "user@invalid_ip"
        result = runner.invoke(config.config.commands["kdump"].commands["add"].commands["ssh_string"], [invalid_ssh_string], obj=db)
        assert result.exit_code == 1  # Expect no change to the database
        assert "Invalid SSH string" in result.output

    def test_config_kdump_add_ssh_path_valid(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # Simulate command execution for 'add ssh_path' with valid input
        valid_ssh_path = "/absolute/path/to/ssh"
        result = runner.invoke(config.config.commands["kdump"].commands["add"].commands["ssh_path"], [valid_ssh_path], obj=db)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("KDUMP")["config"]["ssh_path"] == valid_ssh_path

    def test_config_kdump_add_ssh_path_valid(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # Simulate command execution for 'add ssh_path' with valid input
        valid_ssh_path = "/absolute/path/to/ssh"
        result = runner.invoke(config.config.commands["kdump"].commands["add"].commands["ssh_path"], [valid_ssh_path], obj=db)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("KDUMP")["config"]["ssh_path"] == valid_ssh_path

    def test_config_kdump_add_ssh_path_invalid(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # Simulate command execution for 'add ssh_path' with invalid input
        invalid_ssh_path = "relative/path/to/ssh"
        result = runner.invoke(config.config.commands["kdump"].commands["add"].commands["ssh_path"], [invalid_ssh_path], obj=db)
        assert result.exit_code == 1  # Expect no change to the database
        assert "Invalid path" in result.output

    def test_config_kdump_remove_ssh_string(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # Initialize KDUMP table with ssh_string
        db.cfgdb.mod_entry("KDUMP", "config", {"ssh_string": "user@192.168.1.1"})

        # Simulate command execution for 'remove ssh_string'
        result = runner.invoke(config.config.commands["kdump"].commands["remove"].commands["ssh_string"], obj=db)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("KDUMP")["config"].get("ssh_string") == ""

    def test_config_kdump_remove_ssh_path(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # Initialize KDUMP table with ssh_path
        db.cfgdb.mod_entry("KDUMP", "config", {"ssh_path": "/absolute/path/to/ssh"})

        # Simulate command execution for 'remove ssh_path'
        result = runner.invoke(config.config.commands["kdump"].commands["remove"].commands["ssh_path"], obj=db)
        assert result.exit_code == 0
        assert db.cfgdb.get_table("KDUMP")["config"].get("ssh_path") == ""

    def test_config_kdump_remove_ssh_path_nothing_to_remove(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # Simulate command execution for 'remove ssh_path' when nothing is set
        result = runner.invoke(config.config.commands["kdump"].commands["remove"].commands["ssh_path"], obj=db)
        assert result.exit_code == 1
        assert "No SSH path is currently set" in result.output

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")

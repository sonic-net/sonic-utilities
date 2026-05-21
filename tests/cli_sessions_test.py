from click.testing import CliRunner

import config.main as config
import show.main as show
from utilities_common.db import Db


class TestCliSessionsCommands:
    def test_config_command(self):
        runner = CliRunner()

        db = Db()

        result = runner.invoke(config.config.commands['serial_console'].commands['sysrq-capabilities'],
                               ['enabled'], obj=db)
        assert result.exit_code == 0

        result = runner.invoke(config.config.commands['serial_console'].commands['inactivity-timeout'],
                               ['180'], obj=db)
        assert result.exit_code == 0

        result = runner.invoke(show.cli.commands['serial_console'], obj=db)
        assert result.exit_code == 0

        result = runner.invoke(config.config.commands['ssh'].commands['inactivity-timeout'], ['190'], obj=db)
        assert result.exit_code == 0

        result = runner.invoke(config.config.commands['ssh'].commands['max-sessions'], ['60'], obj=db)
        assert result.exit_code == 0

        result = runner.invoke(show.cli.commands['ssh'], obj=db)
        assert result.exit_code == 0

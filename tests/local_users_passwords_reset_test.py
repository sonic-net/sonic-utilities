from click.testing import CliRunner

import config.main as config
import show.main as show
from utilities_common.db import Db


class TestLocalUsersPasswordsReset:
    def test_config_command(self):
        runner = CliRunner()

        db = Db()

        result = runner.invoke(config.config.commands['local-users-passwords-reset'], ['enabled'], obj=db)
        print(result.output)
        assert result.exit_code == 0
        assert db.cfgdb.get_entry('LOCAL_USERS_PASSWORDS_RESET', 'global')['state'] == 'enabled'

        result = runner.invoke(show.cli.commands['local-users-passwords-reset'], obj=db)
        assert result.exit_code == 0
        assert 'enabled' in result.output

        result = runner.invoke(config.config.commands['local-users-passwords-reset'], ['disabled'], obj=db)
        print(result.output)
        assert result.exit_code == 0
        assert db.cfgdb.get_entry('LOCAL_USERS_PASSWORDS_RESET', 'global')['state'] == 'disabled'

        result = runner.invoke(show.cli.commands['local-users-passwords-reset'], obj=db)
        assert result.exit_code == 0
        assert 'disabled' in result.output

        result = runner.invoke(config.config.commands['local-users-passwords-reset'], ['invalid-input'], obj=db)
        print(result.output)
        assert result.exit_code != 0

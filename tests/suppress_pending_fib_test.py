import os
import importlib
from click.testing import CliRunner

import config.main as config
import show.main as show
from utilities_common.db import Db


class TestSuppressFibPending:
    def test_synchronous_mode(self):
        runner = CliRunner()

        db = Db()

        result = runner.invoke(config.config.commands['suppress-fib-pending'], ['enabled'], obj=db)
        print(result.output)
        assert result.exit_code == 0
        assert db.cfgdb.get_entry('DEVICE_METADATA', 'localhost')['suppress-fib-pending'] == 'enabled'

        result = runner.invoke(show.cli.commands['suppress-fib-pending'], obj=db)
        assert result.exit_code == 0
        assert result.output == 'Enabled\n'

        result = runner.invoke(config.config.commands['suppress-fib-pending'], ['disabled'], obj=db)
        print(result.output)
        assert result.exit_code == 0
        assert db.cfgdb.get_entry('DEVICE_METADATA', 'localhost')['suppress-fib-pending'] == 'disabled'

        result = runner.invoke(show.cli.commands['suppress-fib-pending'], obj=db)
        assert result.exit_code == 0
        assert result.output == 'Disabled\n'

        result = runner.invoke(config.config.commands['suppress-fib-pending'], ['invalid-input'], obj=db)
        print(result.output)
        assert result.exit_code != 0


class TestSuppressFibPendingMultiAsic(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        import show.main
        importlib.reload(show.main)
        import config.main
        importlib.reload(config.main)
        from .mock_tables import dbconnector
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        dbconnector.load_namespace_config()

    def test_config_suppress_fib_pending_all_asics(self):
        runner = CliRunner()
        db = Db()
        cfgdb0 = db.cfgdb_clients['asic0']
        cfgdb1 = db.cfgdb_clients['asic1']

        # Test config = disable and db check for all asics (asic0 and asic1)
        result = runner.invoke(config.config.commands['suppress-fib-pending'], ['disabled'], obj=db)
        print(result.output)
        assert result.exit_code == 0
        assert cfgdb0.get_entry('DEVICE_METADATA', 'localhost')['suppress-fib-pending'] == 'disabled'
        assert cfgdb1.get_entry('DEVICE_METADATA', 'localhost')['suppress-fib-pending'] == 'disabled'

        # Show disable for all asics
        result = runner.invoke(show.cli.commands['suppress-fib-pending'], obj=db)
        assert result.exit_code == 0
        assert result.output == 'asic0: Disabled\nasic1: Disabled\n'

        # Test config = enable and db check for all asics (asic0 and asic1)
        result = runner.invoke(config.config.commands['suppress-fib-pending'], ['enabled'], obj=db)
        print(result.output)
        assert result.exit_code == 0
        assert cfgdb0.get_entry('DEVICE_METADATA', 'localhost')['suppress-fib-pending'] == 'enabled'
        assert cfgdb1.get_entry('DEVICE_METADATA', 'localhost')['suppress-fib-pending'] == 'enabled'

        # Show enable for all asics
        result = runner.invoke(show.cli.commands['suppress-fib-pending'], obj=db)
        assert result.exit_code == 0
        assert result.output == 'asic0: Enabled\nasic1: Enabled\n'

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        from .mock_tables import dbconnector
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        dbconnector.load_namespace_config()

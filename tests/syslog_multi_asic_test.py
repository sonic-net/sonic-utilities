import mock
import pytest
from click.testing import CliRunner
from importlib import reload
from utilities_common.db import Db

show_all_config = """SERVICE    INTERVAL    BURST
---------  ----------  -------
database   200         20000
pmon       100         10000


Namespace asic0:
SERVICE    INTERVAL    BURST
---------  ----------  -------
bgp        111         33333
database   222         22222


Namespace asic1:
SERVICE    INTERVAL    BURST
---------  ----------  -------
bgp        444         44444
database   555         55555
"""

show_global_ns_config = """SERVICE    INTERVAL    BURST
---------  ----------  -------
database   200         20000
pmon       100         10000
"""

show_asic0_ns_config = """Namespace asic0:
SERVICE    INTERVAL    BURST
---------  ----------  -------
bgp        111         33333
database   222         22222
"""

show_all_ns_database_config = """SERVICE    INTERVAL    BURST
---------  ----------  -------
database   200         20000


Namespace asic0:
SERVICE    INTERVAL    BURST
---------  ----------  -------
database   222         22222


Namespace asic1:
SERVICE    INTERVAL    BURST
---------  ----------  -------
database   555         55555
"""

show_global_ns_database_config = """SERVICE    INTERVAL    BURST
---------  ----------  -------
database   200         20000
"""

show_asic0_ns_database_config = """Namespace asic0:
SERVICE    INTERVAL    BURST
---------  ----------  -------
database   222         22222
"""


@pytest.fixture(scope='module')
def setup_cmd_module():
    # Mock to multi ASIC
    from .mock_tables import mock_multi_asic
    from .mock_tables import dbconnector
    reload(mock_multi_asic)
    dbconnector.load_namespace_config()
    
    import show.main as show
    import config.main as config
    
    # Refresh syslog module for show and config
    import show.syslog as show_syslog
    reload(show_syslog)
    show.cli.add_command(show_syslog.syslog)
    
    import config.syslog as config_syslog
    reload(config_syslog)
    config.config.add_command(config_syslog.syslog)
    
    yield show, config
    
    # Mock back to single ASIC
    from .mock_tables import mock_single_asic
    reload(mock_single_asic)
    
    # Refresh syslog module for show and config
    reload(show_syslog)
    show.cli.add_command(show_syslog.syslog)
    
    reload(config_syslog)
    config.config.add_command(config_syslog.syslog)


class TestSyslogRateLimitMultiAsic:
    def test_show_rate_limit_container(self, setup_cmd_module):
        show, _ = setup_cmd_module
        
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["syslog"].commands["rate-limit-container"],
            []
        )
        
        assert result.output == show_all_config
        assert result.exit_code == 0
        
        result = runner.invoke(
            show.cli.commands["syslog"].commands["rate-limit-container"], ["-n", "default"]
        )
        
        assert result.output == show_global_ns_config
        assert result.exit_code == 0
        
        result = runner.invoke(
            show.cli.commands["syslog"].commands["rate-limit-container"], ["-n", "asic0"]
        )
        
        assert result.output == show_asic0_ns_config
        assert result.exit_code == 0
        
        result = runner.invoke(
            show.cli.commands["syslog"].commands["rate-limit-container"], ["database"]
        )
        
        assert result.output == show_all_ns_database_config
        assert result.exit_code == 0
        
        result = runner.invoke(
            show.cli.commands["syslog"].commands["rate-limit-container"], ["database", "-n", "default"]
        )
        
        assert result.output == show_global_ns_database_config
        assert result.exit_code == 0
        
        result = runner.invoke(
            show.cli.commands["syslog"].commands["rate-limit-container"], ["database", "-n", "asic0"]
        )
        
        assert result.output == show_asic0_ns_database_config
        assert result.exit_code == 0

    def test_config_rate_limit_container(self, setup_cmd_module):
        _, config = setup_cmd_module
        
        runner = CliRunner()
        db = Db()
        result = runner.invoke(
            config.config.commands["syslog"].commands["rate-limit-container"],
            ["database", "--interval", 1, "--burst", 100], obj=db
        )
        assert result.exit_code == 0
        for cfg_db in db.cfgdb_clients.values():
            data = cfg_db.get_entry('SYSLOG_CONFIG_FEATURE', 'database')
            assert data['rate_limit_burst'] == '100'
            assert data['rate_limit_interval'] == '1'
        
        result = runner.invoke(
            config.config.commands["syslog"].commands["rate-limit-container"],
            ["bgp", "--interval", 1, "--burst", 100], obj=db
        )
        assert result.exit_code == 0
        for namespace, cfg_db in db.cfgdb_clients.items():
            if namespace != '':
                data = cfg_db.get_entry('SYSLOG_CONFIG_FEATURE', 'bgp')
                assert data['rate_limit_burst'] == '100'
                assert data['rate_limit_interval'] == '1'
            else:
                table = cfg_db.get_table('SYSLOG_CONFIG_FEATURE')
                assert 'bgp' not in table
                
        result = runner.invoke(
            config.config.commands["syslog"].commands["rate-limit-container"],
            ["pmon", "--interval", 1, "--burst", 100], obj=db
        )
        assert result.exit_code == 0
        for namespace, cfg_db in db.cfgdb_clients.items():
            if namespace == '':
                data = cfg_db.get_entry('SYSLOG_CONFIG_FEATURE', 'pmon')
                assert data['rate_limit_burst'] == '100'
                assert data['rate_limit_interval'] == '1'
            else:
                table = cfg_db.get_table('SYSLOG_CONFIG_FEATURE')
                assert 'pmon' not in table
                
        result = runner.invoke(
            config.config.commands["syslog"].commands["rate-limit-container"],
            ["pmon", "--interval", 2, "--burst", 200, "-n", "default"], obj=db
        )
        assert result.exit_code == 0
        cfg_db = db.cfgdb_clients['']
        data = cfg_db.get_entry('SYSLOG_CONFIG_FEATURE', 'pmon')
        assert data['rate_limit_burst'] == '200'
        assert data['rate_limit_interval'] == '2'
        
    @mock.patch('config.syslog.clicommon.run_command', mock.MagicMock(return_value=('', 0)))
    def test_enable_syslog_rate_limit_feature(self, setup_cmd_module):
        _, config = setup_cmd_module
        
        runner = CliRunner()
        result = runner.invoke(
            config.config.commands["syslog"].commands["rate-limit-feature"].commands['enable'], []
        )
        assert result.exit_code == 0
        
        result = runner.invoke(
            config.config.commands["syslog"].commands["rate-limit-feature"].commands['enable'],
            ['-n', 'default']
        )
        assert result.exit_code == 0
        
        result = runner.invoke(
            config.config.commands["syslog"].commands["rate-limit-feature"].commands['enable'],
            ['-n', 'asic0']
        )

        assert result.exit_code == 0
        
        result = runner.invoke(
            config.config.commands["syslog"].commands["rate-limit-feature"].commands['enable'], ['database']
        )
        assert result.exit_code == 0
        
        result = runner.invoke(
            config.config.commands["syslog"].commands["rate-limit-feature"].commands['enable'], 
            ['database', '-n', 'default']
        )
        assert result.exit_code == 0
        
        result = runner.invoke(
            config.config.commands["syslog"].commands["rate-limit-feature"].commands['enable'], 
            ['database', '-n', 'asic0']
        )
        assert result.exit_code == 0
    
    @mock.patch('config.syslog.clicommon.run_command', mock.MagicMock(return_value=('', 0)))
    def test_disable_syslog_rate_limit_feature(self, setup_cmd_module):
        _, config = setup_cmd_module
        
        runner = CliRunner()
        result = runner.invoke(
            config.config.commands["syslog"].commands["rate-limit-feature"].commands['disable'], []
        )
        assert result.exit_code == 0
        
        result = runner.invoke(
            config.config.commands["syslog"].commands["rate-limit-feature"].commands['disable'],
            ['-n', 'default']
        )
        assert result.exit_code == 0
        
        result = runner.invoke(
            config.config.commands["syslog"].commands["rate-limit-feature"].commands['disable'],
            ['-n', 'asic0']
        )
        assert result.exit_code == 0
        
        result = runner.invoke(
            config.config.commands["syslog"].commands["rate-limit-feature"].commands['disable'], ['database']
        )
        assert result.exit_code == 0
        
        result = runner.invoke(
            config.config.commands["syslog"].commands["rate-limit-feature"].commands['disable'], 
            ['database', '-n', 'default']
        )
        assert result.exit_code == 0
        
        result = runner.invoke(
            config.config.commands["syslog"].commands["rate-limit-feature"].commands['disable'], 
            ['database', '-n', 'asic0']
        )
        assert result.exit_code == 0

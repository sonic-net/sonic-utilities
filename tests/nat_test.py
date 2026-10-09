import mock

from click.testing import CliRunner
from utilities_common.db import Db
from mock import patch
from jsonpatch import JsonPatchConflict
import config.main as config
import config.nat as nat
import config.validated_config_db_connector as validated_config_db_connector

class TestNat(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")

    def test_add_basic_invalid(self):
        nat.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(config.config.commands["nat"].commands["add"].commands["static"], ["basic", "65.66.45.1", "12.12.12.14x", "-nat_type", "dnat"],  obj=obj)
        assert "Please enter a valid local ip address" in result.output
        
        result = runner.invoke(config.config.commands["nat"].commands["add"].commands["static"], ["basic", "65.66.45.1x", "12.12.12.14", "-nat_type", "dnat"],  obj=obj)
        assert "Please enter a valid global ip address" in result.output

    @patch("config.nat.SonicV2Connector.get_all", mock.Mock(return_value={"MAX_NAT_ENTRIES": "9999"}))
    @patch("config.nat.SonicV2Connector.exists", mock.Mock(return_value="True"))
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=ValueError))
    def test_add_basic_yang_validation(self):
        nat.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(config.config.commands["nat"].commands["add"].commands["static"], ["basic", "65.66.45.1", "12.12.12.14", "-nat_type", "dnat", "-twice_nat_id", "3"],  obj=obj)
        assert "Invalid ConfigDB. Error" in result.output

        result = runner.invoke(config.config.commands["nat"].commands["add"].commands["static"], ["basic", "65.66.45.1", "12.12.12.14", "-nat_type", "dnat"],  obj=obj)
        assert "Invalid ConfigDB. Error" in result.output


        result = runner.invoke(config.config.commands["nat"].commands["add"].commands["static"], ["basic", "65.66.45.1", "12.12.12.14", "-twice_nat_id", "3"],  obj=obj)
        assert "Invalid ConfigDB. Error" in result.output
        
        result = runner.invoke(config.config.commands["nat"].commands["add"].commands["static"], ["basic", "65.66.45.1", "12.12.12.14"],  obj=obj)
        assert "Invalid ConfigDB. Error" in result.output
    
    def test_add_tcp_invalid(self):
        nat.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(config.config.commands["nat"].commands["add"].commands["static"], ["tcp", "65.66.45.1", "100", "12.12.12.14x", "200", "-nat_type", "dnat"],  obj=obj)
        assert "Please enter a valid local ip address" in result.output
        
        result = runner.invoke(config.config.commands["nat"].commands["add"].commands["static"], ["tcp", "65.66.45.1x", "100", "12.12.12.14", "200", "-nat_type", "dnat"],  obj=obj)
        assert "Please enter a valid global ip address" in result.output

    @patch("config.nat.SonicV2Connector.get_all", mock.Mock(return_value={"MAX_NAT_ENTRIES": "9999"}))
    @patch("config.nat.SonicV2Connector.exists", mock.Mock(return_value="True"))
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=ValueError))
    def test_add_tcp_yang_validation(self):
        nat.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(config.config.commands["nat"].commands["add"].commands["static"], ["tcp", "65.66.45.1", "100", "12.12.12.14", "200", "-nat_type", "dnat", "-twice_nat_id", "3"],  obj=obj)
        assert "Invalid ConfigDB. Error" in result.output

        result = runner.invoke(config.config.commands["nat"].commands["add"].commands["static"], ["tcp", "65.66.45.1", "100", "12.12.12.14", "200", "-nat_type", "dnat"],  obj=obj)
        assert "Invalid ConfigDB. Error" in result.output


        result = runner.invoke(config.config.commands["nat"].commands["add"].commands["static"], ["tcp", "65.66.45.1", "100", "12.12.12.14", "200", "-twice_nat_id", "3"],  obj=obj)
        assert "Invalid ConfigDB. Error" in result.output
        
        result = runner.invoke(config.config.commands["nat"].commands["add"].commands["static"], ["tcp", "65.66.45.1", "100", "12.12.12.14", "200"],  obj=obj)
        assert "Invalid ConfigDB. Error" in result.output
    
    def test_add_udp_invalid(self):
        nat.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(config.config.commands["nat"].commands["add"].commands["static"], ["udp", "65.66.45.1", "100", "12.12.12.14x", "200", "-nat_type", "dnat"],  obj=obj)
        assert "Please enter a valid local ip address" in result.output
        
        result = runner.invoke(config.config.commands["nat"].commands["add"].commands["static"], ["udp", "65.66.45.1x", "100", "12.12.12.14", "200", "-nat_type", "dnat"],  obj=obj)
        assert "Please enter a valid global ip address" in result.output

    @patch("config.nat.SonicV2Connector.get_all", mock.Mock(return_value={"MAX_NAT_ENTRIES": "9999"}))
    @patch("config.nat.SonicV2Connector.exists", mock.Mock(return_value="True"))
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=ValueError))
    def test_add_udp_yang_validation(self):
        nat.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(config.config.commands["nat"].commands["add"].commands["static"], ["udp", "65.66.45.1", "100", "12.12.12.14", "200", "-nat_type", "dnat", "-twice_nat_id", "3"],  obj=obj)
        assert "Invalid ConfigDB. Error" in result.output

        result = runner.invoke(config.config.commands["nat"].commands["add"].commands["static"], ["udp", "65.66.45.1", "100", "12.12.12.14", "200", "-nat_type", "dnat"],  obj=obj)
        assert "Invalid ConfigDB. Error" in result.output


        result = runner.invoke(config.config.commands["nat"].commands["add"].commands["static"], ["udp", "65.66.45.1", "100", "12.12.12.14", "200", "-twice_nat_id", "3"],  obj=obj)
        assert "Invalid ConfigDB. Error" in result.output
        
        result = runner.invoke(config.config.commands["nat"].commands["add"].commands["static"], ["udp", "65.66.45.1", "100", "12.12.12.14", "200"],  obj=obj)
        assert "Invalid ConfigDB. Error" in result.output

    def test_remove_basic(self):
        nat.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(config.config.commands["nat"].commands["remove"].commands["static"].commands["basic"], ["65.66.45.1", "12.12.12.14x"],  obj=obj)
        assert "Please enter a valid local ip address" in result.output
        
        result = runner.invoke(config.config.commands["nat"].commands["remove"].commands["static"].commands["basic"], ["65.66.45.1x", "12.12.12.14"],  obj=obj)
        assert "Please enter a valid global ip address" in result.output

    @patch("config.nat.ConfigDBConnector.get_entry", mock.Mock(return_value={"local_ip": "12.12.12.14"}))
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=JsonPatchConflict))
    def test_remove_basic_yang_validation(self):
        nat.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(config.config.commands["nat"].commands["remove"].commands["static"].commands["basic"], ["65.66.45.1", "12.12.12.14"],  obj=obj)
        assert "Invalid ConfigDB. Error" in result.output

    def test_remove_udp(self):
        nat.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(config.config.commands["nat"].commands["remove"].commands["static"].commands["udp"], ["65.66.45.1", "100", "12.12.12.14x", "200"],  obj=obj)
        assert "Please enter a valid local ip address" in result.output
        
        result = runner.invoke(config.config.commands["nat"].commands["remove"].commands["static"].commands["udp"], ["65.66.45.1x", "100", "12.12.12.14", "200"],  obj=obj)
        assert "Please enter a valid global ip address" in result.output

    @patch("config.nat.ConfigDBConnector.get_entry", mock.Mock(return_value={"local_ip": "12.12.12.14", "local_port": "200"}))
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=JsonPatchConflict))
    def test_remove_udp_yang_validation(self):
        nat.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}
        
        result = runner.invoke(config.config.commands["nat"].commands["remove"].commands["static"].commands["udp"], ["65.66.45.1", "100", "12.12.12.14", "200"],  obj=obj)
        assert "Invalid ConfigDB. Error" in result.output

    @patch("config.nat.ConfigDBConnector.get_table", mock.Mock(return_value={"sample_table_key": "sample_table_value"}))
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=JsonPatchConflict))
    def test_remove_static_all_yang_validation(self):
        nat.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}
        
        result = runner.invoke(config.config.commands["nat"].commands["remove"].commands["static"].commands["all"], obj=obj)
        assert "Invalid ConfigDB. Error" in result.output

    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_enable_yang_validation(self):
        nat.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(config.config.commands["nat"].commands["feature"].commands["enable"], obj=obj)
        assert "Invalid ConfigDB. Error" in result.output
    
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_disable_yang_validation(self):
        nat.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(config.config.commands["nat"].commands["feature"].commands["disable"], obj=obj)
        assert "Invalid ConfigDB. Error" in result.output
    
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_timeout_yang_validation(self):
        nat.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(config.config.commands["nat"].commands["set"].commands["timeout"], ["301"], obj=obj)
        assert "Invalid ConfigDB. Error" in result.output
    
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_tcp_timeout_yang_validation(self):
        nat.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(config.config.commands["nat"].commands["set"].commands["tcp-timeout"], ["301"], obj=obj)
        assert "Invalid ConfigDB. Error" in result.output
    
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_udp_timeout_yang_validation(self):
        nat.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(config.config.commands["nat"].commands["set"].commands["udp-timeout"], ["301"], obj=obj)
        assert "Invalid ConfigDB. Error" in result.output
    
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_reset_timeout_yang_validation(self):
        nat.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(config.config.commands["nat"].commands["reset"].commands["timeout"], obj=obj)
        assert "Invalid ConfigDB. Error" in result.output
    
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_reset_tcp_timeout_yang_validation(self):
        nat.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(config.config.commands["nat"].commands["reset"].commands["tcp-timeout"], obj=obj)
        assert "Invalid ConfigDB. Error" in result.output
    
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_reset_udp_timeout_yang_validation(self):
        nat.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(config.config.commands["nat"].commands["reset"].commands["udp-timeout"], obj=obj)
        assert "Invalid ConfigDB. Error" in result.output

    def test_nat_commands_use_unix_socket_connectors(self):
        nat.ADHOC_VALIDATION = True
        runner = CliRunner()
        connector = mock.Mock()
        connector.get_entry.return_value = None
        connector.get_table.return_value = {}
        config_connector = mock.Mock(return_value=connector)
        validated_connector = mock.Mock(return_value=connector)
        obj = {'config_db': connector}

        with patch("config.nat.ConfigDBConnector", config_connector), \
                patch("config.nat.ValidatedConfigDBConnector", validated_connector), \
                patch("config.nat.getTwiceNatIdCountWithStaticEntries", return_value=0), \
                patch("config.nat.getTwiceNatIdCountWithDynamicBinding", return_value=0):
            commands = config.config.commands["nat"].commands
            runner.invoke(commands["remove"].commands["static"].commands["tcp"],
                          ["65.66.45.1", "100", "12.12.12.14", "200"], obj=obj)
            runner.invoke(commands["add"].commands["pool"], ["pool1", "65.66.45.1"], obj=obj)
            runner.invoke(commands["add"].commands["binding"], ["binding1", "pool1"], obj=obj)
            runner.invoke(commands["remove"].commands["pool"], ["pool1"], obj=obj)
            runner.invoke(commands["remove"].commands["pools"], obj=obj)
            runner.invoke(commands["remove"].commands["binding"], ["binding1"], obj=obj)
            runner.invoke(commands["remove"].commands["bindings"], obj=obj)
            runner.invoke(commands["add"].commands["interface"],
                          ["Ethernet0", "-nat_zone", "1"], obj=obj)
            runner.invoke(commands["remove"].commands["interface"], ["Ethernet0"], obj=obj)
            runner.invoke(commands["remove"].commands["interfaces"], obj=obj)

        assert config_connector.call_count == 12
        assert all(call.kwargs == {"use_unix_socket_path": True}
                   for call in config_connector.call_args_list)
        assert validated_connector.call_count == 10

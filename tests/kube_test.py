import mock

from click.testing import CliRunner
from utilities_common.db import Db
from mock import patch

show_no_server_output="""\
Kubernetes server is not configured
"""
show_server_output_0="""\
ip           port    insecure    disable
-----------  ------  ----------  ---------
10.3.157.24  6443    True        False
"""

show_server_output_1="""\
ip           port    insecure    disable
-----------  ------  ----------  ---------
10.10.10.11  6443    True        False
"""

show_server_output_2="""\
ip           port    insecure    disable
-----------  ------  ----------  ---------
10.3.157.24  6443    False       False
"""

show_server_output_3="""\
ip           port    insecure    disable
-----------  ------  ----------  ---------
10.3.157.24  6443    True        True
"""

show_server_output_4="""\
ip           port    insecure    disable
-----------  ------  ----------  ---------
10.3.157.24  7777    True        False
"""

show_server_output_5="""\
ip           port    insecure    disable
-----------  ------  ----------  ---------
10.10.10.11  6443    True        False
"""

show_server_output_6="""\
ip           port    insecure    disable
-----------  ------  ----------  ---------
10.3.157.24  6443    True        False
"""

empty_server_status="""\
Kubernetes server has no status info
"""

non_empty_server_status="""\
ip           port    connected    update-time
-----------  ------  -----------  -------------------
10.3.157.24  6443    false        2020-11-13 00:49:05
"""

empty_labels="""\
name    value
------  -------
"""

non_empty_labels="""\
name           value
-------------  -------------
hwsku          Force10-S6000
teamd_enabled  false
"""

class TestKube(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")


    def __check_res(self, result, info, op):
        print("Running test: {}".format(info))
        print(result.exit_code)
        assert result.exit_code == 0
        print(result.output)
        assert result.output == op


    def test_kube_server(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()

        # Check server not configured
        result = runner.invoke(show.cli.commands["kubernetes"].commands["server"].commands["config"])
        self.__check_res(result, "init server config test", show_server_output_0)

        result = runner.invoke(show.cli.commands["kubernetes"].commands["server"].commands["status"])
        self.__check_res(result, "init server status test", empty_server_status)

    def test_no_kube_server(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()

        db.cfgdb.delete_table("KUBERNETES_MASTER")

        # Check server not configured
        result = runner.invoke(show.cli.commands["kubernetes"].commands["server"].commands["config"], [], obj=db)
        self.__check_res(result, "null server config test", show_no_server_output)

        # Add IP when not configured
        result = runner.invoke(config.config.commands["kubernetes"].commands["server"], ["ip", "10.10.10.11"], obj=db)
        self.__check_res(result, "set server IP when none", "")

        result = runner.invoke(show.cli.commands["kubernetes"].commands["server"].commands["config"], [], obj=db)
        self.__check_res(result, "config command default value", show_server_output_5)
    
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_mod_entry", mock.Mock(side_effect=ValueError))
    def test_no_kube_server_yang_validation(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()

        db.cfgdb.delete_table("KUBERNETES_MASTER")

        # Check server not configured
        result = runner.invoke(show.cli.commands["kubernetes"].commands["server"].commands["config"], [], obj=db)
        self.__check_res(result, "null server config test", show_no_server_output)

        # Add IP when not configured
        result = runner.invoke(config.config.commands["kubernetes"].commands["server"], ["ip", "10.10.10.11"], obj=db)
        assert "Invalid ConfigDB. Error" in result.output
        
        db.cfgdb.mod_entry("KUBERNETES_MASTER", "SERVER", {"ip": "10.10.10.11"})
        # Add IP when already configured
        result = runner.invoke(config.config.commands["kubernetes"].commands["server"], ["ip", "10.10.10.12"], obj=db)
        assert "Invalid ConfigDB. Error" in result.output

    
    def test_only_kube_server(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()

        db.cfgdb.delete_table("KUBERNETES_MASTER")
        db.cfgdb.set_entry("KUBERNETES_MASTER", "SERVER", {"ip": "10.3.157.24"})

        result = runner.invoke(show.cli.commands["kubernetes"].commands["server"].commands["config"], [], obj=db)
        self.__check_res(result, "show command default value", show_server_output_6)


    def test_kube_server_status(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()
        db = Db()
        dbconn = db.db

        for (k, v) in [ ("ip", "10.3.157.24"), ("port", "6443"),
                ("connected", "false"), ("update_time", "2020-11-13 00:49:05")]:
            dbconn.set(dbconn.STATE_DB, "KUBERNETES_MASTER|SERVER", k, v)

        result = runner.invoke(show.cli.commands["kubernetes"].commands["server"].commands["status"], [], obj=db)
        self.__check_res(result, "init server status test", non_empty_server_status)


    def test_set_server_ip(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # Add IP & test show
        result = runner.invoke(config.config.commands["kubernetes"].commands["server"], ["ip", "10.10.10.11"], obj=db)
        self.__check_res(result, "set server IP", "")

        result = runner.invoke(show.cli.commands["kubernetes"].commands["server"].commands["config"], [], obj=db)
        self.__check_res(result, "check server IP", show_server_output_1)


    def test_set_server_invalid_port(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # test invalid port
        result = runner.invoke(config.config.commands["kubernetes"].commands["server"], ["port", "10101011"], obj=db)
        assert result.exit_code == 1



    def test_set_insecure(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # set insecure as True & test show
        result = runner.invoke(config.config.commands["kubernetes"].commands["server"], ["insecure", "off"], obj=db)
        self.__check_res(result, "set server insecure", "")

        result = runner.invoke(show.cli.commands["kubernetes"].commands["server"].commands["config"], [], obj=db)
        self.__check_res(result, "check server IP", show_server_output_2)


    def test_set_disable(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # set disable as True & test show
        result = runner.invoke(config.config.commands["kubernetes"].commands["server"], ["disable", "on"], obj=db)
        self.__check_res(result, "set server disable", "")

        result = runner.invoke(show.cli.commands["kubernetes"].commands["server"].commands["config"], [], obj=db)
        self.__check_res(result, "check server IP", show_server_output_3)


    def test_set_port(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # set port  to a different value & test show
        result = runner.invoke(config.config.commands["kubernetes"].commands["server"], ["port", "7777"], obj=db)
        self.__check_res(result, "set server port", "")

        result = runner.invoke(show.cli.commands["kubernetes"].commands["server"].commands["config"], [], obj=db)
        self.__check_res(result, "check server IP", show_server_output_4)


    def test_kube_labels(self, get_cmd_module):
        (config, show) = get_cmd_module
        runner = CliRunner()

        # Check for no labels
        result = runner.invoke(show.cli.commands["kubernetes"].commands["labels"])
        self.__check_res(result, "no labels", empty_labels)


    def test_set_kube_labels(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # Add a label
        result = runner.invoke(config.config.commands["kubernetes"].commands["label"].commands["add"], ["hwsku", "Force10-S6000"], obj=db)
        self.__check_res(result, "set add label", "")

        # Drop a label
        result = runner.invoke(config.config.commands["kubernetes"].commands["label"].commands["drop"], ["teamd_enabled"], obj=db)
        self.__check_res(result, "set drop label", "")

        result = runner.invoke(show.cli.commands["kubernetes"].commands["labels"], [], obj=db)
        self.__check_res(result, "Test labels", non_empty_labels)


    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")



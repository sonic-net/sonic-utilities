import pytest
import fnmatch
import textwrap

from unittest.mock import patch, MagicMock
from config.main import config as config_cli
from show.main import cli as show_cli
from click.testing import CliRunner


@pytest.fixture
def configdbconnector_mock():
    class DB(MagicMock):
        CONFIG_DB = "CONFIG_DB"
        DBs = {}

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            namespace = kwargs.get("namespace", "")
            self.dbs = self.DBs.setdefault(namespace, {"CONFIG_DB": {}})

        def mod_entry(self, table, key, value):
            value = {k: str(v) for k, v in value.items()}
            self.dbs[self.CONFIG_DB].setdefault(table, {})[key] = value

        def get_table(self, table):
            return self.dbs[self.CONFIG_DB].get(table, {})

    with patch("config.main.ConfigDBConnector", new=DB), \
         patch("show.warm_restart.ConfigDBConnector", new=DB):
        yield DB


@pytest.fixture
def sonicv2connector_mock():
    class DB(MagicMock):
        STATE_DB = "STATE_DB"
        DBs = {}

        def __init__(self, *args, **kwargs):
            namespace = kwargs.get("namespace", "")
            super().__init__(*args, **kwargs)
            self.dbs = self.DBs.setdefault(namespace, {"STATE_DB": {}})

        def keys(self, db, hash):
            return [key for key in self.dbs[db].keys() if fnmatch.fnmatch(key, hash)]

        def set(self, db, key, field, value):
            self.dbs[db].setdefault(key, {})[field] = value

        def get(self, db, key, field):
            return self.dbs[db].get(key, {}).get(field, None)

        def get_all(self, db, key):
            return self.dbs[db][key]

    with patch("config.main.SonicV2Connector", new=DB), \
         patch("show.warm_restart.SonicV2Connector", new=DB):
        yield DB


@pytest.fixture
def multi_asic():
    global_namespace = ""
    asic_namespaces = ["asic0", "asic1", "asic2", "asic3"]
    namespaces = [global_namespace] + asic_namespaces
    with patch("config.main.multi_asic.is_multi_asic", return_value=True), \
         patch("config.main.multi_asic.get_namespace_list", return_value=asic_namespaces), \
         patch("show.warm_restart.multi_asic.is_multi_asic", return_value=True), \
         patch("show.warm_restart.multi_asic.get_namespace_list", return_value=asic_namespaces):
        yield {
            "namespaces": namespaces,
            "asic_namespaces": asic_namespaces,
        }


def test_config_warm_restart_enable(sonicv2connector_mock, configdbconnector_mock):
    runner = CliRunner()
    result = runner.invoke(
        config_cli.commands["warm_restart"], ["enable"],
    )
    state_db = sonicv2connector_mock()
    assert result.exit_code == 0
    assert state_db.get(state_db.STATE_DB,
                        "WARM_RESTART_ENABLE_TABLE|system", "enable") == "true"


def test_config_warm_restart_disable(sonicv2connector_mock, configdbconnector_mock):
    runner = CliRunner()
    result = runner.invoke(
        config_cli.commands["warm_restart"], ["disable"],
    )
    state_db = sonicv2connector_mock()
    assert result.exit_code == 0
    assert state_db.get(
        state_db.STATE_DB, "WARM_RESTART_ENABLE_TABLE|system", "enable") == "false"


def test_config_warm_restart_enable_multi_asic(sonicv2connector_mock, configdbconnector_mock, multi_asic):
    runner = CliRunner()
    result = runner.invoke(
        config_cli.commands["warm_restart"], ["enable"],
    )
    assert result.exit_code == 0
    for namespace in multi_asic["namespaces"]:
        state_db = sonicv2connector_mock(namespace=namespace)
        assert state_db.get(
            state_db.STATE_DB, "WARM_RESTART_ENABLE_TABLE|system", "enable") == "true"


def test_config_warm_restart_disable_multi_asic(sonicv2connector_mock, configdbconnector_mock, multi_asic):
    runner = CliRunner()
    result = runner.invoke(
        config_cli.commands["warm_restart"], ["disable"],
    )
    assert result.exit_code == 0
    for namespace in multi_asic["namespaces"]:
        state_db = sonicv2connector_mock(namespace=namespace)
        assert state_db.get(
            state_db.STATE_DB, "WARM_RESTART_ENABLE_TABLE|system", "enable") == "false"


def test_config_warm_restart_disable_multi_asic_one_asic(sonicv2connector_mock, configdbconnector_mock, multi_asic):
    runner = CliRunner()
    result = runner.invoke(
        config_cli.commands["warm_restart"], ["enable"],
    )
    assert result.exit_code == 0
    result = runner.invoke(
        config_cli.commands["warm_restart"], ["disable", "-n", "asic1"],
    )
    assert result.exit_code == 0
    for namespace in multi_asic["asic_namespaces"]:
        expected_value = "false" if namespace == "asic1" else "true"
        state_db = sonicv2connector_mock(namespace=namespace)
        assert state_db.get(
            state_db.STATE_DB, "WARM_RESTART_ENABLE_TABLE|system", "enable") == expected_value


def test_config_warm_restart_neighsyncd_timer(configdbconnector_mock, sonicv2connector_mock):
    runner = CliRunner()
    result = runner.invoke(
        config_cli.commands["warm_restart"], ["neighsyncd_timer", "180"],
    )
    cfg_db = configdbconnector_mock()
    assert result.exit_code == 0
    assert cfg_db.get_table("WARM_RESTART")[
        "swss"]["neighsyncd_timer"] == "180"


def test_config_warm_restart_neighsyncd_timer_multi_asic(configdbconnector_mock, sonicv2connector_mock, multi_asic):
    runner = CliRunner()
    result = runner.invoke(
        config_cli.commands["warm_restart"], ["neighsyncd_timer", "180"],
    )
    assert result.exit_code == 0
    for namespace in multi_asic["asic_namespaces"]:
        cfg_db = configdbconnector_mock(namespace=namespace)
        assert cfg_db.get_table("WARM_RESTART")[
            "swss"]["neighsyncd_timer"] == "180"


def test_config_warm_restart_neighsyncd_timer_multi_asic_one_asic(configdbconnector_mock, sonicv2connector_mock, multi_asic):
    runner = CliRunner()
    result = runner.invoke(
        config_cli.commands["warm_restart"], ["neighsyncd_timer", "180"],
    )
    assert result.exit_code == 0
    result = runner.invoke(
        config_cli.commands["warm_restart"], [
            "neighsyncd_timer", "200", "-n", "asic1"],
    )
    assert result.exit_code == 0
    for namespace in multi_asic["asic_namespaces"]:
        expected_value = "200" if namespace == "asic1" else "180"
        cfg_db = configdbconnector_mock(namespace=namespace)
        assert cfg_db.get_table("WARM_RESTART")[
            "swss"]["neighsyncd_timer"] == expected_value


def test_config_warm_restart_bgp_timer(configdbconnector_mock, sonicv2connector_mock):
    runner = CliRunner()
    result = runner.invoke(
        config_cli.commands["warm_restart"], ["bgp_timer", "180"],
    )
    cfg_db = configdbconnector_mock()
    assert result.exit_code == 0
    assert cfg_db.get_table("WARM_RESTART")["bgp"]["bgp_timer"] == "180"


def test_config_warm_restart_bgp_timer_multi_asic(configdbconnector_mock, sonicv2connector_mock, multi_asic):
    runner = CliRunner()
    result = runner.invoke(
        config_cli.commands["warm_restart"], ["bgp_timer", "180"],
    )
    assert result.exit_code == 0
    for namespace in multi_asic["asic_namespaces"]:
        cfg_db = configdbconnector_mock(namespace=namespace)
        assert cfg_db.get_table("WARM_RESTART")["bgp"]["bgp_timer"] == "180"


def test_config_warm_restart_bgp_timer_multi_asic_one_asic(configdbconnector_mock, sonicv2connector_mock, multi_asic):
    runner = CliRunner()
    result = runner.invoke(
        config_cli.commands["warm_restart"], ["bgp_timer", "180"],
    )
    assert result.exit_code == 0
    result = runner.invoke(
        config_cli.commands["warm_restart"], [
            "bgp_timer", "200", "-n", "asic1"],
    )
    assert result.exit_code == 0
    for namespace in multi_asic["asic_namespaces"]:
        expected_value = "200" if namespace == "asic1" else "180"
        cfg_db = configdbconnector_mock(namespace=namespace)
        assert cfg_db.get_table("WARM_RESTART")[
            "bgp"]["bgp_timer"] == expected_value


def test_config_warm_restart_enable_bgp_eoiu(configdbconnector_mock, sonicv2connector_mock):
    runner = CliRunner()
    result = runner.invoke(
        config_cli.commands["warm_restart"], ["bgp_eoiu", "true"],
    )
    cfg_db = configdbconnector_mock()
    assert result.exit_code == 0
    assert cfg_db.get_table("WARM_RESTART")["bgp"]["bgp_eoiu"] == "true"


def test_config_warm_restart_disable_bgp_eoiu_multi_asic(configdbconnector_mock, sonicv2connector_mock, multi_asic):
    runner = CliRunner()
    result = runner.invoke(
        config_cli.commands["warm_restart"], ["bgp_eoiu", "true"],
    )
    assert result.exit_code == 0
    for namespace in multi_asic["asic_namespaces"]:
        cfg_db = configdbconnector_mock(namespace=namespace)
        assert cfg_db.get_table("WARM_RESTART")["bgp"]["bgp_eoiu"] == "true"


def test_config_warm_restart_disable_bgp_eoiu_multi_asic_one_asic(configdbconnector_mock, sonicv2connector_mock, multi_asic):
    runner = CliRunner()
    result = runner.invoke(
        config_cli.commands["warm_restart"], ["bgp_eoiu", "true"],
    )
    assert result.exit_code == 0
    result = runner.invoke(
        config_cli.commands["warm_restart"], [
            "bgp_eoiu", "false", "-n", "asic1"],
    )
    assert result.exit_code == 0
    for namespace in multi_asic["asic_namespaces"]:
        expected_value = "false" if namespace == "asic1" else "true"
        cfg_db = configdbconnector_mock(namespace=namespace)
        assert cfg_db.get_table("WARM_RESTART")[
            "bgp"]["bgp_eoiu"] == expected_value


@pytest.fixture
def setup_state_db(sonicv2connector_mock):
    state_db = sonicv2connector_mock()
    state_db.set(state_db.STATE_DB, "WARM_RESTART_ENABLE_TABLE|system", "enable", "true")
    state_db.set(state_db.STATE_DB, "WARM_RESTART_TABLE|orchagent", "state", "restored")
    state_db.set(state_db.STATE_DB, "WARM_RESTART_TABLE|syncd", "state", "reconciled")
    state_db.set(state_db.STATE_DB, "WARM_RESTART_TABLE|orchagent", "restore_count", "1")
    state_db.set(state_db.STATE_DB, "WARM_RESTART_TABLE|syncd", "restore_count", "1")


@pytest.fixture
def setup_state_db_multi_asic(sonicv2connector_mock, multi_asic):
    for namespace in multi_asic["asic_namespaces"]:
        state_db = sonicv2connector_mock(namespace=namespace)
        state_db.set(state_db.STATE_DB, "WARM_RESTART_TABLE|orchagent", "state", "restored")
        state_db.set(state_db.STATE_DB, "WARM_RESTART_TABLE|syncd", "state", "reconciled")
        state_db.set(state_db.STATE_DB, "WARM_RESTART_TABLE|orchagent", "restore_count", "1")
        state_db.set(state_db.STATE_DB, "WARM_RESTART_TABLE|syncd", "restore_count", "1")


@pytest.fixture
def setup_config_db(configdbconnector_mock):
    cfg_db = configdbconnector_mock()
    cfg_db.mod_entry("WARM_RESTART", "teamd", {"teamsyncd_timer": "120"})


@pytest.fixture
def setup_config_db_multi_asic(configdbconnector_mock, multi_asic):
    for namespace in multi_asic["asic_namespaces"]:
        cfg_db = configdbconnector_mock(namespace=namespace)
        cfg_db.mod_entry("WARM_RESTART", "teamd", {"teamsyncd_timer": "180"})


def test_show_warm_restart_state(setup_state_db):
    runner = CliRunner()
    result = runner.invoke(
        show_cli.commands["warm_restart"], ["state"]
    )
    assert result.exit_code == 0
    assert result.output == textwrap.dedent("""\
        name         restore_count  state
        ---------  ---------------  ----------
        orchagent                1  restored
        syncd                    1  reconciled
    """)


def test_show_warm_restart_state_multi_asic(setup_state_db_multi_asic):
    runner = CliRunner()
    result = runner.invoke(
        show_cli.commands["warm_restart"], ["state"]
    )
    assert result.exit_code == 0
    assert result.output == textwrap.dedent("""\

        For namespace global:

        name    restore_count    state
        ------  ---------------  -------

        For namespace asic0:

        name         restore_count  state
        ---------  ---------------  ----------
        orchagent                1  restored
        syncd                    1  reconciled

        For namespace asic1:

        name         restore_count  state
        ---------  ---------------  ----------
        orchagent                1  restored
        syncd                    1  reconciled

        For namespace asic2:

        name         restore_count  state
        ---------  ---------------  ----------
        orchagent                1  restored
        syncd                    1  reconciled

        For namespace asic3:

        name         restore_count  state
        ---------  ---------------  ----------
        orchagent                1  restored
        syncd                    1  reconciled
    """)


def test_show_warm_restart_state_multi_asic_show_namespace(setup_state_db_multi_asic):
    runner = CliRunner()
    arguments = ["-n", "asic1"]
    result = runner.invoke(
        show_cli.commands["warm_restart"], ["state"] + arguments
    )
    assert result.exit_code == 0
    assert result.output == textwrap.dedent("""\
        name         restore_count  state
        ---------  ---------------  ----------
        orchagent                1  restored
        syncd                    1  reconciled
    """)


def test_show_warm_restart_state_invalid_namespace(setup_state_db_multi_asic):
    runner = CliRunner()
    arguments = ["-n", "asicX"]
    result = runner.invoke(
        show_cli.commands["warm_restart"], ["state"] + arguments,
    )
    expected_output = textwrap.dedent("""\
        Usage: warm_restart state [OPTIONS]

        Error: Invalid namespace: asicX
    """)
    assert result.exit_code == 2
    assert result.output == expected_output



def test_show_warm_restart_state_unix_sock_usage(setup_state_db):
    runner = CliRunner()
    arguments = ["-s", "/var/run/redis/redis.sock"]
    result = runner.invoke(
        show_cli.commands["warm_restart"], ["state"] + arguments,
    )
    expected_output = textwrap.dedent("""\
        Warning: '-s|--redis-unix-socket-path' has no effect and is left for compatibility
        name         restore_count  state
        ---------  ---------------  ----------
        orchagent                1  restored
        syncd                    1  reconciled
    """)
    assert result.exit_code == 0
    assert result.output == expected_output


def test_show_warm_restart_config(setup_state_db, setup_config_db):
    runner = CliRunner()
    result = runner.invoke(
        show_cli.commands["warm_restart"], ["config"],
    )
    expected_output = textwrap.dedent("""\
        name    enable    timer_name       timer_duration    eoiu_enable
        ------  --------  ---------------  ----------------  -------------
        teamd   false     teamsyncd_timer  120               NULL
        system  true      NULL             NULL              NULL
    """)
    assert result.exit_code == 0
    assert result.output == expected_output


def test_show_warm_restart_config_multi_asic(setup_state_db_multi_asic,
                                             setup_config_db_multi_asic):
    runner = CliRunner()
    result = runner.invoke(
        show_cli.commands["warm_restart"], ["config"],
    )
    expected_output = textwrap.dedent("""\

        For namespace global:

        name    enable    timer_name    timer_duration    eoiu_enable
        ------  --------  ------------  ----------------  -------------

        For namespace asic0:

        name    enable    timer_name         timer_duration  eoiu_enable
        ------  --------  ---------------  ----------------  -------------
        teamd   false     teamsyncd_timer               180  NULL

        For namespace asic1:

        name    enable    timer_name         timer_duration  eoiu_enable
        ------  --------  ---------------  ----------------  -------------
        teamd   false     teamsyncd_timer               180  NULL

        For namespace asic2:

        name    enable    timer_name         timer_duration  eoiu_enable
        ------  --------  ---------------  ----------------  -------------
        teamd   false     teamsyncd_timer               180  NULL

        For namespace asic3:

        name    enable    timer_name         timer_duration  eoiu_enable
        ------  --------  ---------------  ----------------  -------------
        teamd   false     teamsyncd_timer               180  NULL
    """)
    assert result.exit_code == 0
    assert result.output == expected_output


def test_show_warm_restart_config_multi_asic_show_namespace(setup_state_db_multi_asic,
                                                            setup_config_db_multi_asic):
    runner = CliRunner()
    arguments = ["-n", "asic1"]
    result = runner.invoke(
        show_cli.commands["warm_restart"], ["config"] + arguments,
    )
    expected_output = textwrap.dedent("""\
        name    enable    timer_name         timer_duration  eoiu_enable
        ------  --------  ---------------  ----------------  -------------
        teamd   false     teamsyncd_timer               180  NULL
    """)
    assert result.exit_code == 0
    assert result.output == expected_output


def test_show_warm_restart_config_invalid_namespace(setup_state_db_multi_asic):
    runner = CliRunner()
    arguments = ["-n", "asicX"]
    result = runner.invoke(
        show_cli.commands["warm_restart"], ["config"] + arguments,
    )
    expected_output = textwrap.dedent("""\
        Usage: warm_restart config [OPTIONS]

        Error: Invalid namespace: asicX
    """)
    assert result.exit_code == 2
    assert result.output == expected_output


def test_show_warm_restart_config_unix_sock_usage_and_namespace(setup_state_db_multi_asic):
    runner = CliRunner()
    arguments = ["-s", "/var/run/redis/redis.sock", "-n", "asic1"]
    result = runner.invoke(
        show_cli.commands["warm_restart"], ["config"] + arguments,
    )
    expected_output = textwrap.dedent("""\
        Usage: warm_restart config [OPTIONS]

        Error: Cannot specify both namespace and redis unix socket path
    """)
    assert result.exit_code == 2
    assert result.output == expected_output

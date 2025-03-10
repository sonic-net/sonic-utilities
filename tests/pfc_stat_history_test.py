import importlib
import os

from click.testing import CliRunner
from utilities_common.db import Db

show_pfc_stat_history_disabled_partial_output = """\
Setting              Value
-------------------  -------
POLL_INTERVAL        1000
FLEX_COUNTER_STATUS  disable
"""

show_pfc_stat_history_enabled_partial_output = """\
Setting              Value
-------------------  -------
POLL_INTERVAL        1000
FLEX_COUNTER_STATUS  enable
"""

show_pfc_stat_history_500ms_partial_output = """\
Setting              Value
-------------------  -------
POLL_INTERVAL        500
FLEX_COUNTER_STATUS  disable
"""

show_pfc_stat_history_no_ports_enabled_partial_output = """\
PFC Stat History not enabled on any ports
"""

show_pfc_stat_history_single_port_enabled_partial_output = """\
PFC Stat History enabled on:
Ethernet0
"""


show_pfc_stat_history_disabled_partial_output_masic = """\
Namespace: ASIC_PLACEHOLDER
Setting              Value
-------------------  -------
POLL_INTERVAL        1000
FLEX_COUNTER_STATUS  disable
"""

show_pfc_stat_history_enabled_partial_output_masic = """\
Namespace: ASIC_PLACEHOLDER
Setting              Value
-------------------  -------
POLL_INTERVAL        1000
FLEX_COUNTER_STATUS  enable
"""

show_pfc_stat_history_500ms_partial_output_masic = """\
Namespace: ASIC_PLACEHOLDER
Setting              Value
-------------------  -------
POLL_INTERVAL        500
FLEX_COUNTER_STATUS  disable
"""

show_pfc_stat_history_single_port_enabled_partial_output_asic1 = """\
PFC Stat History enabled on:
Ethernet-BP256
"""

show_pfc_stat_history_no_ports_enabled_on_multi_asic =\
    show_pfc_stat_history_disabled_partial_output_masic.replace("ASIC_PLACEHOLDER", "asic0") + '\n' +\
    show_pfc_stat_history_no_ports_enabled_partial_output + '\n' +\
    show_pfc_stat_history_disabled_partial_output_masic.replace("ASIC_PLACEHOLDER", "asic1") + '\n' +\
    show_pfc_stat_history_no_ports_enabled_partial_output

show_pfc_stat_history_port_enabled_on_multi_asic =\
    show_pfc_stat_history_disabled_partial_output_masic.replace("ASIC_PLACEHOLDER", "asic0") + '\n' +\
    show_pfc_stat_history_single_port_enabled_partial_output + '\n' +\
    show_pfc_stat_history_disabled_partial_output_masic.replace("ASIC_PLACEHOLDER", "asic1") + '\n' +\
    show_pfc_stat_history_single_port_enabled_partial_output_asic1



def show_config_show(get_cmd_module, initial_output, config_command, arguments, exit_code, final_output, db = None):
    if not db:
        db = Db()

    (config, show) = get_cmd_module
    runner = CliRunner()

    result = runner.invoke(show.cli.commands["pfc-stat-history"].commands["config"], obj=db)
    print(result.output)
    assert result.exit_code == 0
    assert initial_output in result.output

    result = runner.invoke(config.config.commands["pfc-stat-history"].commands[config_command], arguments, obj=db)
    print("PBAILEY" + str(result.exit_code))
    print(result.output)
    assert result.exit_code == exit_code

    result = runner.invoke(show.cli.commands["pfc-stat-history"].commands["config"], obj=db)
    print(result.output)
    assert result.exit_code == 0
    assert final_output in result.output


# test both show and config
class TestPfcStatHistory(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "2"

    def test_set_status_valid(self, get_cmd_module):
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_disabled_partial_output,
            "status",
            ["enable"],
            0,
            show_pfc_stat_history_enabled_partial_output
            )

    def test_set_status_invalid(self, get_cmd_module):
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_disabled_partial_output,
            "status",
            ["up"],
            2,
            show_pfc_stat_history_disabled_partial_output
            )

    def test_set_interval_valid(self, get_cmd_module):
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_disabled_partial_output,
            "interval",
            ["500"],
            0,
            show_pfc_stat_history_500ms_partial_output
            )

    def test_set_interval_non_int(self, get_cmd_module):
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_disabled_partial_output,
            "interval",
            ["up"],
            2,
            show_pfc_stat_history_disabled_partial_output
            )

    def test_set_ports_start_valid(self, get_cmd_module):
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_no_ports_enabled_partial_output,
            "start",
            ["Ethernet0"],
            0,
            show_pfc_stat_history_single_port_enabled_partial_output
            )

    def test_set_ports_start_invalid(self, get_cmd_module):
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_no_ports_enabled_partial_output,
            "start",
            ["Ethernet1000"],
            1,
            show_pfc_stat_history_no_ports_enabled_partial_output
            )

    def test_set_ports_start_pfc_not_enabled(self, get_cmd_module):
        # the port gets skipped, no error
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_no_ports_enabled_partial_output,
            "start",
            ["Ethernet8"],
            0,
            show_pfc_stat_history_no_ports_enabled_partial_output
            )

    def test_set_ports_stop_started_valid(self, get_cmd_module):
        db = Db()
        # first start it
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_no_ports_enabled_partial_output,
            "start",
            ["Ethernet0"],
            0,
            show_pfc_stat_history_single_port_enabled_partial_output,
            db
            )

        # now stop it
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_single_port_enabled_partial_output,
            "stop",
            ["Ethernet0"],
            0,
            show_pfc_stat_history_no_ports_enabled_partial_output,
            db
            )

    def test_set_ports_start_not_started_invalid(self, get_cmd_module):
        db = Db()
        # first start it
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_no_ports_enabled_partial_output,
            "start",
            ["Ethernet0"],
            0,
            show_pfc_stat_history_single_port_enabled_partial_output,
            db
            )
        # stop a port that is not started
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_single_port_enabled_partial_output,
            "stop",
            ["Ethernet8"],
            1,
            show_pfc_stat_history_single_port_enabled_partial_output,
            db
            )

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

class TestPfcStatHistoryMultiAsic(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        # change to multi asic config
        # wait why is flex counter table not in the other config_dbs ???
        from .mock_tables import dbconnector
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        dbconnector.load_namespace_config()

    def test_set_status_valid(self, get_cmd_module):
        # the same command will operate on both asics
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_disabled_partial_output_masic.replace("ASIC_PLACEHOLDER", "asic0"),
            "status",
            ["enable"],
            0,
            show_pfc_stat_history_enabled_partial_output_masic.replace("ASIC_PLACEHOLDER", "asic0")
            )
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_disabled_partial_output_masic.replace("ASIC_PLACEHOLDER", "asic1"),
            "status",
            ["enable"],
            0,
            show_pfc_stat_history_enabled_partial_output_masic.replace("ASIC_PLACEHOLDER", "asic1")
            )


    def test_set_status_invalid(self, get_cmd_module):
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_disabled_partial_output_masic.replace("ASIC_PLACEHOLDER", "asic0"),
            "status",
            ["up"],
            2,
            show_pfc_stat_history_disabled_partial_output_masic.replace("ASIC_PLACEHOLDER", "asic0")
            )
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_disabled_partial_output_masic.replace("ASIC_PLACEHOLDER", "asic1"),
            "status",
            ["up"],
            2,
            show_pfc_stat_history_disabled_partial_output_masic.replace("ASIC_PLACEHOLDER", "asic1")
            )


    def test_set_interval_valid(self, get_cmd_module):
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_disabled_partial_output_masic.replace("ASIC_PLACEHOLDER", "asic0"),
            "interval",
            ["500"],
            0,
            show_pfc_stat_history_500ms_partial_output_masic.replace("ASIC_PLACEHOLDER", "asic0")
            )
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_disabled_partial_output_masic.replace("ASIC_PLACEHOLDER", "asic1"),
            "interval",
            ["500"],
            0,
            show_pfc_stat_history_500ms_partial_output_masic.replace("ASIC_PLACEHOLDER", "asic1")
            )

    def test_set_interval_non_int(self, get_cmd_module):
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_disabled_partial_output_masic.replace("ASIC_PLACEHOLDER", "asic0"),
            "interval",
            ["up"],
            2,
            show_pfc_stat_history_disabled_partial_output_masic.replace("ASIC_PLACEHOLDER", "asic0")
            )
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_disabled_partial_output_masic.replace("ASIC_PLACEHOLDER", "asic1"),
            "interval",
            ["up"],
            2,
            show_pfc_stat_history_disabled_partial_output_masic.replace("ASIC_PLACEHOLDER", "asic1")
            )

    def test_set_ports_start_valid_one_asic(self, get_cmd_module):
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_no_ports_enabled_on_multi_asic,
            "start",
            ["Ethernet0"],
            0,
            show_pfc_stat_history_single_port_enabled_partial_output
            )
        # we should also see the output for no ports enabled for asic 1
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_no_ports_enabled_on_multi_asic,
            "start",
            ["Ethernet0"],
            0,
            show_pfc_stat_history_no_ports_enabled_partial_output
            )

    def test_set_ports_start_valid_two_asic(self, get_cmd_module):
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_no_ports_enabled_partial_output,
            "start",
            ["Ethernet0", "Ethernet-BP256"],
            0,
            show_pfc_stat_history_port_enabled_on_multi_asic
            )

    def test_set_ports_start_invalid(self, get_cmd_module):
        # does not exist on any asic
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_no_ports_enabled_on_multi_asic,
            "start",
            ["Ethernet1000"],
            1,
            show_pfc_stat_history_no_ports_enabled_on_multi_asic
            )

    def test_set_ports_start_pfc_not_enabled(self, get_cmd_module):
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_no_ports_enabled_on_multi_asic,
            "start",
            ["Ethernet-BP260"],
            0,
            show_pfc_stat_history_no_ports_enabled_on_multi_asic
            )

    def test_set_ports_stop_started_valid(self, get_cmd_module):
        db = Db()
        # first start on each asic
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_no_ports_enabled_on_multi_asic,
            "start",
            ["Ethernet0", "Ethernet-BP256"],
            0,
            show_pfc_stat_history_port_enabled_on_multi_asic,
            db
            )
        # now stop them
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_port_enabled_on_multi_asic,
            "stop",
            ["Ethernet0", "Ethernet-BP256"],
            0,
            show_pfc_stat_history_no_ports_enabled_on_multi_asic,
            db
            )

    def test_set_ports_start_not_started_invalid(self, get_cmd_module):
        db = Db()
        # first start on each asic
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_no_ports_enabled_on_multi_asic,
            "start",
            ["Ethernet0", "Ethernet-BP256"],
            0,
            show_pfc_stat_history_port_enabled_on_multi_asic,
            db
            )
        # stop a port that is not started
        show_config_show(
            get_cmd_module,
            show_pfc_stat_history_port_enabled_on_multi_asic,
            "stop",
            ["Ethernet0", "Ethernet-BP260"],
            1,
            show_pfc_stat_history_port_enabled_on_multi_asic,
            db
            )

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        from .mock_tables import dbconnector
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        dbconnector.load_namespace_config()


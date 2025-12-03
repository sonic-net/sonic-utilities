import pytest
import os
import logging
import show.main as show
from utilities_common.db import Db
from .mock_tables import dbconnector
from unittest.mock import mock_open, patch

from click.testing import CliRunner

test_path = os.path.dirname(os.path.abspath(__file__))
input_path = os.path.join(test_path, "copp_input")
mock_config_path = os.path.join(input_path, "mock_config")

mock_db_path = os.path.join(test_path, "mock_tables")

logger = logging.getLogger(__name__)

# show copp configuration
show_copp_expected_output = """\
TrapId           Trap Group     Action      CBS    CIR  Meter Type    Mode    HW Status
---------------  -------------  --------  -----  -----  ------------  ------  -------------
arp_req          queue4_group2  copy        600    600  packets       sr_tcm  not-installed
arp_resp         queue4_group2  copy        600    600  packets       sr_tcm  not-installed
bgp              queue4_group1  trap       2000   2000  packets       sr_tcm  installed
bgpv6            queue4_group1  trap       2000   2000  packets       sr_tcm  not-installed
dest_nat_miss    queue1_group2  trap        600    600  packets       sr_tcm  not-installed
dhcp             queue4_group3  trap        100    100  packets       sr_tcm  not-installed
dhcpv6           queue4_group3  trap        100    100  packets       sr_tcm  not-installed
eapol            queue4_group1  trap       2000   2000  packets       sr_tcm  not-installed
ip2me            queue1_group1  trap       6000   6000  packets       sr_tcm  not-installed
lacp             queue4_group1  trap       2000   2000  packets       sr_tcm  not-installed
lldp             queue4_group3  trap        100    100  packets       sr_tcm  not-installed
neigh_discovery  queue4_group2  copy        600    600  packets       sr_tcm  not-installed
sample_packet    queue2_group1  trap       1000   1000  packets       sr_tcm  not-installed
src_nat_miss     queue1_group2  trap        600    600  packets       sr_tcm  not-installed
udld             queue4_group3  trap        100    100  packets       sr_tcm  not-installed
"""

# show copp configuration detailed --group queue4_group1
show_copp_detailed_queue4_group1_expected_output = """\
Trap Id(s).................. bgp,bgpv6,lacp,eapol
Trap Action................. trap
Trap Priority............... 4
Queue....................... 4
CBS......................... 2000
CIR......................... 2000
Meter Type.................. packets
Mode........................ sr_tcm
Yellow Action............... forward
Green Action................ forward
Red Action.................. drop
"""

# show copp configuration detailed --group queue1_group3
show_copp_detailed_queue1_group3_expected_output = ""

# show copp configuration detailed --trapid bgp
show_copp_detailed_bgp_trap_expected_output = """\
Trap Group.................. queue4_group1
Trap Action................. trap
Trap Priority............... 4
Queue....................... 4
CBS......................... 2000
CIR......................... 2000
Meter Type.................. packets
Mode........................ sr_tcm
Yellow Action............... forward
Green Action................ forward
Red Action.................. drop
HW Status................... installed
"""

# show copp configuration detailed --trapid neighbor_miss
show_copp_detailed_neighbor_miss_trap_expected_output = ""

# show copp configuration detailed --group queue1_group3 --trapid neighbor_miss
show_copp_detailed_invalid_both_options_expected_output = """\
Either trapid or group must be provided, but not both.
"""

# show copp configuration detailed
show_copp_detailed_invalid_no_option_output = """\
Either trapid or group must be provided.
"""


class TestCoPP:
    @classmethod
    def setup_class(cls):
        logger.info("Setup class: {}".format(cls.__name__))
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'config_db')
        dbconnector.dedicated_dbs['STATE_DB'] = os.path.join(mock_db_path, 'state_db')

        # Path to the mock copp_cfg.json file in the test directory
        cls.mock_copp_cfg_path = os.path.join(mock_config_path, 'mock_copp_cfg.json')

        real_open = open

        # Read the content of the mock copp_cfg.json file
        with open(cls.mock_copp_cfg_path, 'r') as f:
            cls.mock_file_content = f.read()

        # logger.debug("Mock CoPP configuration file content: \n{}".format(cls.mock_file_content))

        # Custom mock function to selectively mock file opens
        def custom_open(file, *args, **kwargs):
            if os.path.basename(file) == 'copp_cfg.json':
                return mock_open(read_data=cls.mock_file_content)(file, *args, **kwargs)
            else:
                return real_open(file, *args, **kwargs)

        # Mock the open function to simulate the file content
        cls.patcher = patch('builtins.open', custom_open)
        cls.patcher.start()

    @classmethod
    def teardown_class(cls):
        logger.info("Teardown class: {}".format(cls.__name__))
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        dbconnector.dedicated_dbs.clear()
        cls.patcher.stop()

    # ---------- SHOW CoPP ---------- #

    def test_show_copp_configuration(self):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["copp"].commands["configuration"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == 0
        assert result.output == show_copp_expected_output

    @pytest.mark.parametrize("trap_name", ["neighbor_miss", "bgp"])
    def test_show_copp_configuration_detailed_trap_id(self, trap_name):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["copp"].commands["configuration"].commands["detailed"],
            ["--trapid", trap_name], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == 0
        if trap_name == "bgp":
            assert result.output == show_copp_detailed_bgp_trap_expected_output
        elif trap_name == "neighbor_miss":
            assert result.output == show_copp_detailed_neighbor_miss_trap_expected_output

    @pytest.mark.parametrize("group_name", ["queue4_group1", "queue1_group3"])
    def test_show_copp_configuration_detailed_group(self, group_name):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["copp"].commands["configuration"].commands["detailed"],
            ["--group", group_name], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == 0
        if group_name == "queue4_group1":
            assert result.output == show_copp_detailed_queue4_group1_expected_output
        elif group_name == "queue1_group3":
            assert result.output == show_copp_detailed_queue1_group3_expected_output

    def test_show_copp_configuration_detailed_invalid(self):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["copp"].commands["configuration"].commands["detailed"],
            ["--group", "queue1_group3", "--trapid", "neighbor_miss"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == 0
        assert result.output == show_copp_detailed_invalid_both_options_expected_output

        result = runner.invoke(
            show.cli.commands["copp"].commands["configuration"].commands["detailed"], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == 0
        assert result.output == show_copp_detailed_invalid_no_option_output

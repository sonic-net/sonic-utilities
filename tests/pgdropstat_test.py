import os
import sys
import pytest

import show.main as show
import clear.main as clear
import config.main as config

from click.testing import CliRunner
from shutil import copyfile

from utilities_common.cli import UserCache

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)


show_pg_dropped_packet_stat="""\
Ingress PG dropped packets:
     Port    PG0    PG1    PG2    PG3    PG4    PG5    PG6    PG7
---------  -----  -----  -----  -----  -----  -----  -----  -----
Ethernet0    800    801    802    803    804    805    806    807
Ethernet4    400    401    402    403    404    405    406    407
Ethernet8    100    101    102    103    104    105    106    107
"""

show_cleared_pg_dropped_packet_stat="""\
Ingress PG dropped packets:
     Port    PG0    PG1    PG2    PG3    PG4    PG5    PG6    PG7
---------  -----  -----  -----  -----  -----  -----  -----  -----
Ethernet0      0      0      0      0      0      0      0      0
Ethernet4      0      0      0      0      0      0      0      0
Ethernet8      0      0      0      0      0      0      0      0
"""

class TestPgDropstat(object):
    @classmethod
    def setup_class(cls):
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        print("SETUP")

    def replace_file(self, file_name_src, file_name_dst):
        sample_config_db_file = os.path.join(test_path, file_name_src)
        mock_config_db_file = os.path.join(test_path, "mock_tables", file_name_dst)

        #Backup origin config_db and replace it with config_db file with disabled PG_DROP counters
        copyfile(mock_config_db_file, "/tmp/" + file_name_dst)
        copyfile(sample_config_db_file, mock_config_db_file)

        return mock_config_db_file

    @pytest.fixture(scope='function')
    def replace_counter_db_file(self):
        mock_file = self.replace_file("pgdrop_input/counters_db.json", "counters_db.json")

        yield

        copyfile("/tmp/counters_db.json", mock_file)

    @pytest.fixture(scope='function')
    def replace_config_db_file(self):
        mock_file = self.replace_file("pgdrop_input/config_db.json", "config_db.json")

        yield

        copyfile("/tmp/config_db.json", mock_file)

    @pytest.fixture(scope='function')
    def replace_counter_db2_file(self):
        mock_file = self.replace_file("pgdrop_input/counters_db2.json", "counters_db.json")

        yield

        copyfile("/tmp/counters_db.json", mock_file)

    @pytest.fixture(scope='function')
    def replace_counter_db3_file(self):
        mock_file = self.replace_file("pgdrop_input/counters_db3.json", "counters_db.json")

        yield

        copyfile("/tmp/counters_db.json", mock_file)

    @pytest.fixture(scope='function')
    def replace_counter_db4_file(self):
        mock_file = self.replace_file("pgdrop_input/counters_db4.json", "counters_db.json")

        yield

        copyfile("/tmp/counters_db.json", mock_file)

    def test_show_pg_drop_pg_port_map(self, replace_counter_db3_file):
        runner = CliRunner()

        result = runner.invoke(show.cli.commands["priority-group"].commands["drop"].commands["counters"])
        assert result.exit_code == 1
        print(result.exit_code)

        assert "Port is not available for oid" in result.output
        print(result.exit_code)

    def test_show_pg_drop_pg_index_map(self, replace_counter_db4_file):
        runner = CliRunner()

        result = runner.invoke(show.cli.commands["priority-group"].commands["drop"].commands["counters"])
        assert result.exit_code == 1
        print(result.exit_code)

        assert "Priority group index is not available for oid" in result.output
        print(result.output)

    def test_show_pg_drop_port_name_map(self, replace_counter_db_file):
        runner = CliRunner()

        result = runner.invoke(show.cli.commands["priority-group"].commands["drop"].commands["counters"])
        assert result.exit_code == 1
        print(result.exit_code)

        assert result.output == "COUNTERS_PORT_NAME_MAP is empty!\n"
        print(result.output)

    def test_show_pg_drop_pg_name_map(self, replace_counter_db2_file):
        runner = CliRunner()

        result = runner.invoke(show.cli.commands["priority-group"].commands["drop"].commands["counters"])
        assert result.exit_code == 1
        print(result.exit_code)

        assert result.output == "COUNTERS_PG_NAME_MAP is empty!\n"
        print(result.output)

    def test_show_pg_drop_disabled(self, replace_config_db_file):
        runner = CliRunner()

        result = runner.invoke(show.cli.commands["priority-group"].commands["drop"].commands["counters"])
        assert result.exit_code == 0
        print(result.exit_code)

        assert result.output == "Warning: PG counters are disabled. Use 'counterpoll pg-drop enable' to enable polling\n"
        print(result.output)

    def test_show_pg_drop_show(self):
        self.executor(clear_before_show = False)

    def test_show_pg_drop_clear(self):
        self.executor(clear_before_show = True)

    def executor(self, clear_before_show):
        runner = CliRunner()
        show_output = show_pg_dropped_packet_stat

        # Clear stats
        if clear_before_show:
            result = runner.invoke(clear.cli.commands["priority-group"].commands["drop"].commands["counters"], [])
            assert result.exit_code == 0
            show_output = show_cleared_pg_dropped_packet_stat

        result = runner.invoke(show.cli.commands["priority-group"].commands["drop"].commands["counters"], [])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        assert result.output == show_output

    @classmethod
    def teardown_class(cls):
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        UserCache('pg-drop').remove_all()
        print("TEARDOWN")

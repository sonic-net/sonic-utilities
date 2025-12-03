import os

import pytest

from click.testing import CliRunner

from utilities_common import multi_asic
from utilities_common import constants
from .utils import get_result_and_return_code
import show.main as show

from unittest.mock import patch

from sonic_py_common import device_info

show_ip_fib_v4 = """\
  No.  Vrf    Route               Nexthop                                  Ifname
-----  -----  ------------------  ---------------------------------------  -----------------------------------------------------------
    1         192.168.104.0/25    10.0.0.57,10.0.0.59,10.0.0.61,10.0.0.63  PortChannel101,PortChannel102,PortChannel103,PortChannel104
    2         192.168.104.128/25                                           PortChannel101,PortChannel102,PortChannel103,PortChannel104
    3         192.168.112.0/25    10.0.0.57,10.0.0.59,10.0.0.61,10.0.0.63
    4         192.168.120.0/25    10.0.0.57,10.0.0.59,10.0.0.61,10.0.0.63  PortChannel101,PortChannel102,PortChannel103,PortChannel104
    5  Red    192.168.112.128/25  10.0.0.57,10.0.0.59,10.0.0.61,10.0.0.63  PortChannel101,PortChannel102,PortChannel103,PortChannel104
Total number of entries 5
"""

show_ip_fib_v6 = """\
  No.  Vrf    Route                Nexthop                              Ifname
-----  -----  -------------------  -----------------------------------  -----------------------------------------------------------
    1         20c0:fe28:0:80::/64  fc00::72,fc00::76,fc00::7a,fc00::7e  PortChannel101,PortChannel102,PortChannel103,PortChannel104
    2         20c0:fe28::/64       fc00::72,fc00::76,fc00::7a,fc00::7e  PortChannel101,PortChannel102,PortChannel103,PortChannel104
    3         20c0:fe30:0:80::/64                                       PortChannel101,PortChannel102,PortChannel103,PortChannel104
Total number of entries 3
"""

root_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(root_path)
scripts_path = os.path.join(modules_path, "scripts")


class TestFibshow():
    @pytest.fixture(scope="class", autouse=True)
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "1"
        yield
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

    @pytest.fixture(scope="function", autouse=True)
    def setUp(self):
        self.runner = CliRunner()
        yield
        del os.environ["FIBSHOW_MOCK"]

    def set_mock_variant(self, variant: str):
        os.environ["FIBSHOW_MOCK"] = variant

    def test_show_ip_fib(self):
        self.set_mock_variant("1")
        from .mock_tables import dbconnector
        modules_path = os.path.join(os.path.dirname(__file__), "..")
        test_path = os.path.join(modules_path, "tests")
        mock_db_path = os.path.join(test_path, "fibshow_input")
        jsonfile_appl = os.path.join(mock_db_path, 'appl_db')
        dbconnector.dedicated_dbs['APPL_DB'] = jsonfile_appl
        print(dbconnector.load_database_config())
        result = self.runner.invoke(show.cli.commands["ip"].commands["fib"], [])
        dbconnector.dedicated_dbs['APPL_DB'] = None
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_ip_fib_v4

    def test_show_ipv6_fib(self):
        self.set_mock_variant("1")
        from .mock_tables import dbconnector
        modules_path = os.path.join(os.path.dirname(__file__), "..")
        test_path = os.path.join(modules_path, "tests")
        mock_db_path = os.path.join(test_path, "fibshow_input")
        jsonfile_appl = os.path.join(mock_db_path, 'appl_db')
        dbconnector.dedicated_dbs['APPL_DB'] = jsonfile_appl
        print(dbconnector.load_database_config())
        result = self.runner.invoke(show.cli.commands["ipv6"].commands["fib"], [])
        dbconnector.dedicated_dbs['APPL_DB'] = None
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_ip_fib_v6


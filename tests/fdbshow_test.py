import os
from click.testing import CliRunner
import pytest

import show.main as show
from .utils import get_result_and_return_code
import subprocess

root_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(root_path)
scripts_path = os.path.join(modules_path, "scripts")

show_mac_output_with_def_vlan = """\
  No.    Vlan  MacAddress         Port       Type
-----  ------  -----------------  ---------  -------
    1       2  11:22:33:44:55:66  Ethernet0  Dynamic
    2       3  11:22:33:66:55:44  Ethernet4  Static
Total number of entries 2
"""

show_mac_aging_time_output = """\
Aging time for switch is 600 seconds
"""

show_mac_aging_time_not_present_output = """\
Aging time not configured for the switch
"""

show_mac_output = """\
  No.    Vlan  MacAddress         Port           Type
-----  ------  -----------------  -------------  -------
    1       2  11:22:33:44:55:66  Ethernet0      Dynamic
    2       3  11:22:33:66:55:44  Ethernet4      Static
    3       4  66:55:44:33:22:11  Ethernet0      Dynamic
    4       4  77:66:44:33:22:11  1000000000fff  Dynamic
    5       5  77:66:55:44:22:11  Ethernet4      Dynamic
Total number of entries 5
"""

show_mac_count_output = """\
Total number of entries 5
"""

show_mac__port_vlan_output = """\
  No.    Vlan  MacAddress         Port       Type
-----  ------  -----------------  ---------  -------
    1       2  11:22:33:44:55:66  Ethernet0  Dynamic
Total number of entries 1
"""

show_mac__address_output = """\
  No.    Vlan  MacAddress         Port       Type
-----  ------  -----------------  ---------  ------
    1       3  11:22:33:66:55:44  Ethernet4  Static
Total number of entries 1
"""

show_mac__address_case_output = """\
  No.    Vlan  MacAddress         Port       Type
-----  ------  -----------------  ---------  -------
    1       2  34:5F:78:9A:BC:DE  Ethernet0  Dynamic
Total number of entries 1
"""

show_mac__port_address_output = """\
  No.    Vlan  MacAddress         Port       Type
-----  ------  -----------------  ---------  -------
    1       4  66:55:44:33:22:11  Ethernet0  Dynamic
Total number of entries 1
"""

show_mac__vlan_address_output = """\
  No.    Vlan  MacAddress         Port       Type
-----  ------  -----------------  ---------  -------
    1       4  66:55:44:33:22:11  Ethernet0  Dynamic
Total number of entries 1
"""

show_mac__type_output = """\
  No.    Vlan  MacAddress         Port       Type
-----  ------  -----------------  ---------  ------
    1       3  11:22:33:66:55:44  Ethernet4  Static
Total number of entries 1
"""

show_mac__type_case_output = """\
  No.    Vlan  MacAddress         Port           Type
-----  ------  -----------------  -------------  -------
    1       2  11:22:33:44:55:66  Ethernet0      Dynamic
    2       4  66:55:44:33:22:11  Ethernet0      Dynamic
    3       4  77:66:44:33:22:11  1000000000fff  Dynamic
    4       5  77:66:55:44:22:11  Ethernet4      Dynamic
Total number of entries 4
"""

show_mac__port_type_output = """\
  No.    Vlan  MacAddress         Port       Type
-----  ------  -----------------  ---------  ------
    1       3  11:22:33:66:55:44  Ethernet4  Static
Total number of entries 1
"""

show_mac__vlan_type_output = """\
  No.    Vlan  MacAddress         Port       Type
-----  ------  -----------------  ---------  ------
    1       3  11:22:33:66:55:44  Ethernet4  Static
Total number of entries 1
"""

show_mac__address_type_output = """\
  No.    Vlan  MacAddress         Port       Type
-----  ------  -----------------  ---------  ------
    1       3  11:22:33:66:55:44  Ethernet4  Static
Total number of entries 1
"""

show_mac__port_vlan_address_type_output = """\
  No.    Vlan  MacAddress         Port       Type
-----  ------  -----------------  ---------  ------
    1       3  11:22:33:66:55:44  Ethernet4  Static
Total number of entries 1
"""

show_mac_no_results_output = """\
No.    Vlan    MacAddress    Port    Type
-----  ------  ------------  ------  ------
Total number of entries 0
"""

show_mac_invalid_namespace = """\
Error: Namespace is not supported in single asic
"""

show_mac_invalid_port_output= """\
Error: Invalid port eth123
"""

show_mac_invalid_vlan_output= """\
Error: Invalid vlan id 10000
"""

show_mac_invalid_type_output= """\
Error: Invalid type both
"""
show_mac_invalid_address_output= """\
Error: Invalid mac address 12:345:67:a9:bc:d
"""

class TestFdbshow():
    @pytest.fixture(scope="class", autouse=True)
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "1"
        os.environ["FDBSHOW_UNIT_TESTING"] = "1"
        yield
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["FDBSHOW_UNIT_TESTING"] = "0"

    @pytest.fixture(scope="function", autouse=True)
    def setUp(self):
        self.runner = CliRunner()
        yield
        del os.environ["FDBSHOW_MOCK"]

    def set_mock_variant(self, variant: str):
        os.environ["FDBSHOW_MOCK"] = variant

    def test_show_mac_def_vlan(self):
        self.set_mock_variant("2")

        result = self.runner.invoke(show.cli.commands["mac"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac_output_with_def_vlan

        return_code, result = get_result_and_return_code(['fdbshow'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac_output_with_def_vlan

    def test_show_mac_aging_time(self):
        self.set_mock_variant("1")
        from .mock_tables import dbconnector
        modules_path = os.path.join(os.path.dirname(__file__), "..")
        test_path = os.path.join(modules_path, "tests")
        mock_db_path = os.path.join(test_path, "fdbshow_input")
        jsonfile_appl = os.path.join(mock_db_path, 'appl_db')
        dbconnector.dedicated_dbs['APPL_DB'] = jsonfile_appl
        result = self.runner.invoke(show.cli.commands["mac"].commands["aging-time"], [])
        dbconnector.dedicated_dbs['APPL_DB'] = None
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac_aging_time_output

    def test_show_mac_no_aging_time(self):
        self.set_mock_variant("1")
        from .mock_tables import dbconnector
        modules_path = os.path.join(os.path.dirname(__file__), "..")
        test_path = os.path.join(modules_path, "tests")
        mock_db_path = os.path.join(test_path, "fdbshow_input")
        jsonfile_appl = os.path.join(mock_db_path, 'appl_db_no_age')
        dbconnector.dedicated_dbs['APPL_DB'] = jsonfile_appl
        result = self.runner.invoke(show.cli.commands["mac"].commands["aging-time"], [])
        dbconnector.dedicated_dbs['APPL_DB'] = None
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac_aging_time_not_present_output

    def test_show_mac(self):
        self.set_mock_variant("1")

        result = self.runner.invoke(show.cli.commands["mac"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac_output

        return_code, result = get_result_and_return_code(['fdbshow'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac_output

    def test_show_mac_count(self):
        self.set_mock_variant("1")

        result = self.runner.invoke(show.cli.commands["mac"], ["-c"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac_count_output

        return_code, result = get_result_and_return_code(['fdbshow', '-c'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac_count_output

    def test_show_mac_port_vlan(self):
        self.set_mock_variant("1")

        result = self.runner.invoke(show.cli.commands["mac"], "-p Ethernet0 -v 2")
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac__port_vlan_output

        return_code, result = get_result_and_return_code(['fdbshow', '-p', 'Ethernet0', '-v', '2'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac__port_vlan_output

    def test_show_mac_address(self):
        self.set_mock_variant("1")

        result = self.runner.invoke(show.cli.commands["mac"], "-a 11:22:33:66:55:44")
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac__address_output

        return_code, result = get_result_and_return_code(['fdbshow', '-a', '11:22:33:66:55:44'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac__address_output

    def test_show_mac_address_case(self):
        self.set_mock_variant("7")

        result = self.runner.invoke(show.cli.commands["mac"], "-a 34:5f:78:9a:bc:de")
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac__address_case_output

        return_code, result = get_result_and_return_code(['fdbshow', '-a', '34:5f:78:9a:bc:de'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac__address_case_output

    def test_show_mac_type(self):
        self.set_mock_variant("1")

        result = self.runner.invoke(show.cli.commands["mac"], "-t Static")
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac__type_output

        return_code, result = get_result_and_return_code(['fdbshow', '-t', 'Static'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac__type_output

    def test_show_mac_type_case(self):
        self.set_mock_variant("1")

        result = self.runner.invoke(show.cli.commands["mac"], "-t dynamic")
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac__type_case_output

        return_code, result = get_result_and_return_code(['fdbshow', '-t', 'DYNAMIC'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac__type_case_output

    def test_show_mac_port_address(self):
        self.set_mock_variant("1")

        result = self.runner.invoke(show.cli.commands["mac"], "-a 66:55:44:33:22:11 -p Ethernet0")
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac__port_address_output

        return_code, result = get_result_and_return_code(['fdbshow', '-a', '66:55:44:33:22:11', '-p', 'Ethernet0'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac__port_address_output

    def test_show_mac_vlan_address(self):
        self.set_mock_variant("1")

        result = self.runner.invoke(show.cli.commands["mac"], "-a 66:55:44:33:22:11 -v 4")
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac__vlan_address_output

        return_code, result = get_result_and_return_code(['fdbshow', '-a', '66:55:44:33:22:11', '-v', '4'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac__vlan_address_output

    def test_show_mac_port_type(self):
        self.set_mock_variant("1")

        result = self.runner.invoke(show.cli.commands["mac"], "-p Ethernet4 -t Static")
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac__port_type_output

        return_code, result = get_result_and_return_code(['fdbshow', '-p', 'Ethernet4', '-t', 'Static'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac__port_type_output

    def test_show_mac_vlan_type(self):
        self.set_mock_variant("1")

        result = self.runner.invoke(show.cli.commands["mac"], "-v 3 -t Static")
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac__vlan_type_output

        return_code, result = get_result_and_return_code(['fdbshow', '-v', '3', '-t', 'Static'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac__vlan_type_output

    def test_show_mac_address_type(self):
        self.set_mock_variant("1")

        result = self.runner.invoke(show.cli.commands["mac"], "-a 11:22:33:66:55:44 -t Static")
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac__address_type_output

        return_code, result = get_result_and_return_code(['fdbshow', '-a', '11:22:33:66:55:44', '-t', 'Static'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac__address_type_output

    def test_show_mac_port_vlan_address_type(self):
        self.set_mock_variant("1")

        result = self.runner.invoke(show.cli.commands["mac"], "-v 3 -p Ethernet4 -a 11:22:33:66:55:44 -t Static")
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac__port_vlan_address_type_output

        return_code, result = get_result_and_return_code(['fdbshow', '-v', '3', '-p', 'Ethernet4', '-a', '11:22:33:66:55:44', '-t', 'Static'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac__port_vlan_address_type_output

    def test_show_mac_no_port(self):
        self.set_mock_variant("1")

        result = self.runner.invoke(show.cli.commands["mac"], "-p Ethernet8")
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac_no_results_output

        return_code, result = get_result_and_return_code(['fdbshow', '-p', 'Ethernet8'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac_no_results_output

    def test_show_mac_no_vlan(self):
        self.set_mock_variant("1")

        result = self.runner.invoke(show.cli.commands["mac"], "-v 123")
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac_no_results_output

        return_code, result = get_result_and_return_code(['fdbshow', '-v', '123'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac_no_results_output

    def test_show_mac_no_address(self):
        self.set_mock_variant("1")

        result = self.runner.invoke(show.cli.commands["mac"], "-a 12:34:56:78:9A:BC")
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac_no_results_output

        return_code, result = get_result_and_return_code(['fdbshow', '-a', '12:34:56:78:9A:BC'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac_no_results_output

    def test_show_mac_no_type(self):
        self.set_mock_variant("6")

        result = self.runner.invoke(show.cli.commands["mac"], ["-t", "Static"])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac_no_results_output

        return_code, result = get_result_and_return_code(['fdbshow', '-t', 'Static'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac_no_results_output

    def test_show_mac_no_fdb(self):
        self.set_mock_variant("3")

        result = self.runner.invoke(show.cli.commands["mac"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac_no_results_output

        return_code, result = get_result_and_return_code(['fdbshow'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac_no_results_output

    def test_show_mac_no_bridge(self):
        self.set_mock_variant("4")

        result = self.runner.invoke(show.cli.commands["mac"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_mac_no_results_output

        return_code, result = get_result_and_return_code(['fdbshow'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == show_mac_no_results_output

    def test_show_fetch_except(self):
        self.set_mock_variant("5")

        result = self.runner.invoke(show.cli.commands["mac"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 1
        assert "Failed to get Vlan id for bvid oid:0x260000000007c7" in result.output

        try:
            output = subprocess.check_output(
                'fdbshow', stderr=subprocess.STDOUT, shell=True, text=True)
        except subprocess.CalledProcessError as e:
            return_code = e.returncode
            output = e.output

        print("return_code: {}".format(return_code))
        print("result = {}".format(output))
        assert return_code == 1
        assert "Failed to get Vlan id for bvid oid:0x260000000007c7" in output

    def test_show_mac_invalid_namespace(self):
        self.set_mock_variant("1")

        result = self.runner.invoke(show.cli.commands["mac"], "-n asic0")
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 1
        assert result.output == show_mac_invalid_namespace

        return_code, result = get_result_and_return_code(['fdbshow', '-n', 'asic0'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 1
        assert result == show_mac_invalid_namespace.strip("\n")

    def test_show_mac_invalid_port(self):
        self.set_mock_variant("1")

        result = self.runner.invoke(show.cli.commands["mac"], "-p eth123")
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 1
        assert result.output == show_mac_invalid_port_output

        return_code, result = get_result_and_return_code(['fdbshow', '-p', 'eth123'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 1
        assert result == show_mac_invalid_port_output.strip("\n")

    def test_show_mac_invalid_vlan(self):
        self.set_mock_variant("1")

        result = self.runner.invoke(show.cli.commands["mac"], "-v 10000")
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 1
        assert result.output == show_mac_invalid_vlan_output

        return_code, result = get_result_and_return_code(['fdbshow', '-v', '10000'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 1
        assert result == show_mac_invalid_vlan_output.strip("\n")

    def test_show_mac_invalid_type(self):
        self.set_mock_variant("1")

        result = self.runner.invoke(show.cli.commands["mac"], "-t both")
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 1
        assert result.output == show_mac_invalid_type_output

        return_code, result = get_result_and_return_code(['fdbshow', '-t', 'both'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 1
        assert result == show_mac_invalid_type_output.strip("\n")

    def test_show_mac_invalid_address(self):
        self.set_mock_variant("1")

        result = self.runner.invoke(show.cli.commands["mac"], "-a 12:345:67:a9:bc:d")
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 1
        assert result.output == show_mac_invalid_address_output

        return_code, result = get_result_and_return_code(['fdbshow', '-a', '12:345:67:a9:bc:d'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 1
        assert result == show_mac_invalid_address_output.strip("\n")

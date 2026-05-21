import os
import sys
import traceback
import mock_tables.dbconnector
from click.testing import CliRunner
from unittest import mock
from utilities_common.db import Db
import show.main as show

#test_path = os.path.dirname(os.path.abspath(__file__))

class TestShowVnet(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_show_vnet_endpoint(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands['vnet'].commands['endpoint'], [], obj=db)
        assert result.exit_code == 0
        expected_output = """\
Endpoint               Endpoint Monitor         prefix count  status
---------------------  ---------------------  --------------  --------
fddd:a100:a251::a10:1  fddd:a100:a251::a10:1               1  Unknown
fddd:a101:a251::a10:1  fddd:a101:a251::a10:1               1  Down
fddd:a102:a251::a10:1  fddd:a102:a251::a10:1               1  Unknown
fddd:a103:a251::a10:1  fddd:a103:a251::a10:1               1  Unknown
100.251.7.1            100.251.7.1                         3  Up
"""
        assert result.output == expected_output

    def test_show_vnet_endpoint_ipv4(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands['vnet'].commands['endpoint'], ['100.251.7.1'], obj=db)
        assert result.exit_code == 0
        expected_output = """\
Endpoint     Endpoint Monitor    prefix                                                        status
-----------  ------------------  ------------------------------------------------------------  --------
100.251.7.1  ['100.251.7.1']     ['160.162.191.1/32', '160.163.191.1/32', '160.164.191.1/32']  Up
"""
        assert result.output == expected_output

    def test_show_vnet_endpoint_ipv6(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands['vnet'].commands['endpoint'], ['fddd:a101:a251::a10:1'], obj=db)
        assert result.exit_code == 0
        expected_output = """\
Endpoint               Endpoint Monitor           prefix                        status
---------------------  -------------------------  ----------------------------  --------
fddd:a101:a251::a10:1  ['fddd:a101:a251::a10:1']  ['fddd:a156:a251::a6:1/128']  Down
"""
        assert result.output == expected_output

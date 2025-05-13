import os
import pytest
from click.testing import CliRunner

import acl_loader.main as acl_loader_show
from acl_loader import *
from acl_loader.main import AclLoader
from importlib import reload

root_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(root_path)
scripts_path = os.path.join(modules_path, "scripts")

MASIC_SHOW_ACL_OUTPUT = """Name       Type    Binding      Description    Stage    Status
---------  ------  -----------  -------------  -------  --------------------------------------
DATAACL_5  L3      Ethernet20   DATAACL_5      ingress  {'asic0': 'Active', 'asic2': 'Active'}
                   Ethernet124
"""

APPL_DB_ACL_SHOW_TABLE = """\
Name    Type          Binding         Description                                   Stage    Status
------  ------------  --------------  --------------------------------------------  -------  --------
ENI     ENI_REDIRECT  Ethernet104     Contains Mock Rules for ENI Based Forwarding  ingress  Active
                      PortChannel108
"""

APPL_DB_ACL_SHOW_RULE = """\
Table    Rule                      Priority    Action               Match                             Status
-------  ------------------------  ----------  -------------------  --------------------------------  --------
ENI      Vnet100_F4939FEFC47E_OUT  9997        REDIRECT: 10.0.0.75  DST_IP: 10.2.0.1/32               Active
                                                                    INNER_SRC_MAC: f4:93:9f:ef:c4:7e
                                                                    TUNNEL_VNI: 4321
ENI      Vnet100_F4939FEFC47E_IN   9996        REDIRECT: 10.0.0.75  DST_IP: 10.2.0.1/32               N/A
                                                                    INNER_DST_MAC: f4:93:9f:ef:c4:7e
"""

@pytest.fixture()
def setup_teardown_single_asic():
    os.environ["PATH"] += os.pathsep + scripts_path
    os.environ["UTILITIES_UNIT_TESTING"] = "2"
    os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
    yield
    os.environ["UTILITIES_UNIT_TESTING"] = "0"


@pytest.fixture(scope="class")
def setup_teardown_multi_asic():
    os.environ["PATH"] += os.pathsep + scripts_path
    os.environ["UTILITIES_UNIT_TESTING"] = "2"
    os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
    from .mock_tables import mock_multi_asic_3_asics
    reload(mock_multi_asic_3_asics)
    from .mock_tables import dbconnector
    dbconnector.load_namespace_config()
    yield
    os.environ["UTILITIES_UNIT_TESTING"] = "0"
    os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
    from .mock_tables import mock_single_asic
    reload(mock_single_asic)


class TestShowACLSingleASIC(object):
    def test_show_acl_table(self, setup_teardown_single_asic):
        runner = CliRunner()
        aclloader = AclLoader()
        context = {
            "acl_loader": aclloader
        }
        result = runner.invoke(acl_loader_show.cli.commands['show'].commands['table'], ['DATAACL_5'], obj=context)
        assert result.exit_code == 0
        # We only care about the third line, which contains the 'Active'
        result_top = result.output.split('\n')[2]
        expected_output = "DATAACL_5  L3      Ethernet124  DATAACL_5      ingress  Active"
        assert result_top == expected_output

    def test_show_acl_rule(self, setup_teardown_single_asic):
        runner = CliRunner()
        aclloader = AclLoader()
        context = {
            "acl_loader": aclloader
        }
        result = runner.invoke(acl_loader_show.cli.commands['show'].commands['rule'], ['DATAACL_5'], obj=context)
        assert result.exit_code == 0
        # We only care about the third line, which contains the 'Active'
        result_top = result.output.split('\n')[2]
        expected_output = "DATAACL_5  RULE_1        9999  FORWARD   IP_PROTOCOL: 126  Active"
        assert result_top == expected_output


class TestShowACLMultiASIC(object):
    def test_show_acl_table(self, setup_teardown_multi_asic):
        runner = CliRunner()
        aclloader = AclLoader()
        context = {
            "acl_loader": aclloader
        }
        result = runner.invoke(acl_loader_show.cli.commands['show'].commands['table'], ['DATAACL_5'], obj=context)
        assert result.exit_code == 0
        assert result.output == MASIC_SHOW_ACL_OUTPUT

    def test_show_acl_rule(self, setup_teardown_multi_asic):
        runner = CliRunner()
        aclloader = AclLoader()
        context = {
            "acl_loader": aclloader
        }
        result = runner.invoke(acl_loader_show.cli.commands['show'].commands['rule'], ['DATAACL_5'], obj=context)
        assert result.exit_code == 0
        # We only care about the third line, which contains the 'Active'
        result_top = result.output.split('\n')[2]
        expected_output = "DATAACL_5  RULE_1        9999  FORWARD   IP_PROTOCOL: 126  {'asic0': 'Active', 'asic2': 'Active'}"
        assert result_top == expected_output


class TestShowACLApplDb(object):

    def test_show_acl_table(self, setup_teardown_single_asic):
        runner = CliRunner()
        aclloader = AclLoader()
        context = {
            "acl_loader": aclloader
        }
        result = runner.invoke(acl_loader_show.cli.commands['show'].commands['table'], ["ENI"], obj=context)
        assert result.exit_code == 0
        print(result.output)
        assert result.output == APPL_DB_ACL_SHOW_TABLE

    def test_show_acl_rule(self, setup_teardown_single_asic):
        runner = CliRunner()
        aclloader = AclLoader()
        context = {
            "acl_loader": aclloader
        }
        result = runner.invoke(acl_loader_show.cli.commands['show'].commands['rule'], ["ENI"], obj=context)
        assert result.exit_code == 0
        print(result.output)
        assert result.output == APPL_DB_ACL_SHOW_RULE

import os
import sys
import json
import pytest
import traceback
import dump.main as dump

from unittest import mock, TestCase
from importlib import reload
from click.testing import CliRunner
from utilities_common.db import Db
from dump.match_infra import ConnectionPool, MatchEngine, CONN
from dump.helper import populate_mock
from deepdiff import DeepDiff
from utilities_common.constants import DEFAULT_NAMESPACE
from pyfakefs.fake_filesystem_unittest import Patcher
from swsscommon.swsscommon import SonicV2Connector
from ..mock_tables import dbconnector

def compare_json_output(exp_json, rec, exclude_paths=None):
    print("EXPECTED: \n")
    print(json.dumps(exp_json, indent=4))
    try:
        rec_json = json.loads(rec)
        print("RECIEVED: \n")
        print(json.dumps(rec_json, indent=4))
    except Exception as e:
        print(rec)
        assert False, "CLI Output is not in JSON Format"
    return DeepDiff(exp_json, rec_json, exclude_paths=exclude_paths)


table_display_output = '''\
+-------------+-----------+----------------------------------------------------------------------------+
| port_name   | DB_NAME   | DUMP                                                                       |
+=============+===========+============================================================================+
| Ethernet0   | STATE_DB  | +----------------------+-------------------------------------------------+ |
|             |           | | Keys                 | field-value pairs                               | |
|             |           | +======================+=================================================+ |
|             |           | | PORT_TABLE|Ethernet0 | +------------------+--------------------------+ | |
|             |           | |                      | | field            | value                    | | |
|             |           | |                      | |------------------+--------------------------| | |
|             |           | |                      | | speed            | 100000                   | | |
|             |           | |                      | | supported_speeds | 10000,25000,40000,100000 | | |
|             |           | |                      | +------------------+--------------------------+ | |
|             |           | +----------------------+-------------------------------------------------+ |
+-------------+-----------+----------------------------------------------------------------------------+
'''


table_display_output_no_filtering = '''\
+-------------+-----------+-----------------------------------------------------------+
| port_name   | DB_NAME   | DUMP                                                      |
+=============+===========+===========================================================+
| Ethernet0   | CONFIG_DB | +------------------+                                      |
|             |           | | Keys Collected   |                                      |
|             |           | +==================+                                      |
|             |           | | PORT|Ethernet0   |                                      |
|             |           | +------------------+                                      |
+-------------+-----------+-----------------------------------------------------------+
| Ethernet0   | APPL_DB   | +----------------------+                                  |
|             |           | | Keys Collected       |                                  |
|             |           | +======================+                                  |
|             |           | | PORT_TABLE:Ethernet0 |                                  |
|             |           | +----------------------+                                  |
+-------------+-----------+-----------------------------------------------------------+
| Ethernet0   | ASIC_DB   | +-------------------------------------------------------+ |
|             |           | | Keys Collected                                        | |
|             |           | +=======================================================+ |
|             |           | | ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF:oid:0xd00000000056d | |
|             |           | +-------------------------------------------------------+ |
|             |           | | ASIC_STATE:SAI_OBJECT_TYPE_PORT:oid:0x10000000004a4   | |
|             |           | +-------------------------------------------------------+ |
|             |           | +---------------------+---------------------+             |
|             |           | | vid                 | rid                 |             |
|             |           | +=====================+=====================+             |
|             |           | | oid:0xd00000000056d | oid:0xd             |             |
|             |           | +---------------------+---------------------+             |
|             |           | | oid:0x10000000004a4 | oid:0x1690000000001 |             |
|             |           | +---------------------+---------------------+             |
+-------------+-----------+-----------------------------------------------------------+
| Ethernet0   | STATE_DB  | +----------------------+                                  |
|             |           | | Keys Collected       |                                  |
|             |           | +======================+                                  |
|             |           | | PORT_TABLE|Ethernet0 |                                  |
|             |           | +----------------------+                                  |
+-------------+-----------+-----------------------------------------------------------+
'''

table_config_file_copp='''\
+-----------+-------------+---------------------------------------------------------------+
| trap_id   | DB_NAME     | DUMP                                                          |
+===========+=============+===============================================================+
| bgp       | CONFIG_FILE | +--------------------------+--------------------------------+ |
|           |             | | Keys                     | field-value pairs              | |
|           |             | +==========================+================================+ |
|           |             | | COPP_TRAP|bgp            | +------------+---------------+ | |
|           |             | |                          | | field      | value         | | |
|           |             | |                          | |------------+---------------| | |
|           |             | |                          | | trap_ids   | bgp,bgpv6     | | |
|           |             | |                          | | trap_group | queue4_group1 | | |
|           |             | |                          | +------------+---------------+ | |
|           |             | +--------------------------+--------------------------------+ |
|           |             | | COPP_GROUP|queue4_group1 | +---------------+---------+    | |
|           |             | |                          | | field         | value   |    | |
|           |             | |                          | |---------------+---------|    | |
|           |             | |                          | | trap_action   | trap    |    | |
|           |             | |                          | | trap_priority | 4       |    | |
|           |             | |                          | | queue         | 4       |    | |
|           |             | |                          | +---------------+---------+    | |
|           |             | +--------------------------+--------------------------------+ |
+-----------+-------------+---------------------------------------------------------------+
'''

@pytest.fixture(scope="class")
def match_engine():
    print("SETUP")
    os.environ["VERBOSE"] = "1"

    dump_port_input = os.path.join(os.path.dirname(__file__), "../dump_input/dump/default")

    dedicated_dbs = {}
    dedicated_dbs['CONFIG_DB'] = os.path.join(dump_port_input, "config_db.json")
    dedicated_dbs['APPL_DB'] = os.path.join(dump_port_input, "appl_db.json")
    dedicated_dbs['STATE_DB'] = os.path.join(dump_port_input, "state_db.json")
    dedicated_dbs['ASIC_DB'] =  os.path.join(dump_port_input, "asic_db.json")
    
    conn = SonicV2Connector()
    # popualate the db ,with mock data
    db_names = list(dedicated_dbs.keys())
    try:
        populate_mock(conn, db_names, dedicated_dbs)
    except Exception as e:
        assert False, "Mock initialization failed: " + str(e)

    conn_pool = ConnectionPool()
    conn_pool.fill(DEFAULT_NAMESPACE, conn, db_names)
    match_engine = MatchEngine(conn_pool)

    yield match_engine
    print("TEARDOWN")


@pytest.mark.usefixtures("match_engine")
class TestDumpState:

    def test_identifier_single(self, match_engine):
        runner = CliRunner()
        result = runner.invoke(dump.state, ["port", "Ethernet0"], obj=match_engine)
        expected = {'Ethernet0': {'CONFIG_DB': {'keys': [{'PORT|Ethernet0': {'alias': 'etp1', 'description': 'etp1', 'index': '0', 'lanes': '25,26,27,28', 'mtu': '9100', 'pfc_asym': 'off', 'speed': '40000'}}], 'tables_not_found': []},
                                  'APPL_DB': {'keys': [{'PORT_TABLE:Ethernet0': {'index': '0', 'lanes': '0', 'alias': 'Ethernet0', 'description': 'ARISTA01T2:Ethernet1', 'speed': '25000', 'oper_status': 'down', 'pfc_asym': 'off', 'mtu': '9100', 'fec': 'rs'}}], 'tables_not_found': []},
                                  'ASIC_DB': {'keys': [{'ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF:oid:0xd00000000056d': {'SAI_HOSTIF_ATTR_NAME': 'Ethernet0', 'SAI_HOSTIF_ATTR_OBJ_ID': 'oid:0x10000000004a4', 'SAI_HOSTIF_ATTR_OPER_STATUS': 'true', 'SAI_HOSTIF_ATTR_TYPE': 'SAI_HOSTIF_TYPE_NETDEV', 'SAI_HOSTIF_ATTR_VLAN_TAG': 'SAI_HOSTIF_VLAN_TAG_STRIP'}}, {'ASIC_STATE:SAI_OBJECT_TYPE_PORT:oid:0x10000000004a4': {'NULL': 'NULL', 'SAI_PORT_ATTR_ADMIN_STATE': 'true', 'SAI_PORT_ATTR_MTU': '9122', 'SAI_PORT_ATTR_SPEED': '100000'}}], 'tables_not_found': [], 'vidtorid': {'oid:0xd00000000056d': 'oid:0xd', 'oid:0x10000000004a4': 'oid:0x1690000000001'}},
                                  'STATE_DB': {'keys': [{'PORT_TABLE|Ethernet0': {'speed': '100000', 'supported_speeds': '10000,25000,40000,100000'}}], 'tables_not_found': []}}}

        assert result.exit_code == 0, "exit code: {}, Exception: {}, Traceback: {}".format(result.exit_code, result.exception, result.exc_info)
        ddiff = compare_json_output(expected, result.output)
        assert not ddiff, ddiff

    def test_identifier_multiple(self, match_engine):
        runner = CliRunner()
        result = runner.invoke(dump.state, ["port", "Ethernet0,Ethernet4"], obj=match_engine)
        print(result.output)
        expected = {"Ethernet0":
                    {"CONFIG_DB": {"keys": [{"PORT|Ethernet0": {"alias": "etp1", "description": "etp1", "index": "0", "lanes": "25,26,27,28", "mtu": "9100", "pfc_asym": "off", "speed": "40000"}}], "tables_not_found": []},
                     "APPL_DB": {"keys": [{"PORT_TABLE:Ethernet0": {"index": "0", "lanes": "0", "alias": "Ethernet0", "description": "ARISTA01T2:Ethernet1", "speed": "25000", "oper_status": "down", "pfc_asym": "off", "mtu": "9100", "fec": "rs"}}], "tables_not_found": []},
                     "ASIC_DB": {"keys": [{"ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF:oid:0xd00000000056d": {"SAI_HOSTIF_ATTR_NAME": "Ethernet0", "SAI_HOSTIF_ATTR_OBJ_ID": "oid:0x10000000004a4", "SAI_HOSTIF_ATTR_OPER_STATUS": "true", "SAI_HOSTIF_ATTR_TYPE": "SAI_HOSTIF_TYPE_NETDEV", "SAI_HOSTIF_ATTR_VLAN_TAG": "SAI_HOSTIF_VLAN_TAG_STRIP"}}, {"ASIC_STATE:SAI_OBJECT_TYPE_PORT:oid:0x10000000004a4": {"NULL": "NULL", "SAI_PORT_ATTR_ADMIN_STATE": "true", "SAI_PORT_ATTR_MTU": "9122", "SAI_PORT_ATTR_SPEED": "100000"}}], "tables_not_found": [], "vidtorid": {"oid:0xd00000000056d": "oid:0xd", "oid:0x10000000004a4": "oid:0x1690000000001"}},
                     "STATE_DB": {"keys": [{"PORT_TABLE|Ethernet0": {"speed": "100000", "supported_speeds": "10000,25000,40000,100000"}}], "tables_not_found": []}},
                    "Ethernet4":
                    {"CONFIG_DB": {"keys": [{"PORT|Ethernet4": {"admin_status": "up", "alias": "etp2", "description": "Servers0:eth0", "index": "1", "lanes": "29,30,31,32", "mtu": "9100", "pfc_asym": "off", "speed": "40000"}}], "tables_not_found": []},
                        "APPL_DB": {"keys": [], "tables_not_found": ["PORT_TABLE"]},
                        "ASIC_DB": {"keys": [], "tables_not_found": ["ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF", "ASIC_STATE:SAI_OBJECT_TYPE_PORT"]},
                        "STATE_DB": {"keys": [], "tables_not_found": ["PORT_TABLE"]}}}
        assert result.exit_code == 0, "exit code: {}, Exception: {}, Traceback: {}".format(result.exit_code, result.exception, result.exc_info)
        ddiff = compare_json_output(expected, result.output)
        assert not ddiff, ddiff

    def test_option_key_map(self, match_engine):
        runner = CliRunner()
        result = runner.invoke(dump.state, ["port", "Ethernet0", "--key-map"], obj=match_engine)
        expected = {"Ethernet0": {"CONFIG_DB": {"keys": ["PORT|Ethernet0"], "tables_not_found": []},
                                  "APPL_DB": {"keys": ["PORT_TABLE:Ethernet0"], "tables_not_found": []},
                                  "ASIC_DB": {"keys": ["ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF:oid:0xd00000000056d", "ASIC_STATE:SAI_OBJECT_TYPE_PORT:oid:0x10000000004a4"], "tables_not_found": [], "vidtorid": {"oid:0xd00000000056d": "oid:0xd", "oid:0x10000000004a4": "oid:0x1690000000001"}},
                                  "STATE_DB": {"keys": ["PORT_TABLE|Ethernet0"], "tables_not_found": []}}}
        assert result.exit_code == 0, "exit code: {}, Exception: {}, Traceback: {}".format(result.exit_code, result.exception, result.exc_info)
        ddiff = compare_json_output(expected, result.output)
        assert not ddiff, ddiff

    def test_option_db_filtering(self, match_engine):
        runner = CliRunner()
        result = runner.invoke(dump.state, ["port", "Ethernet0", "--db", "ASIC_DB", "--db", "STATE_DB"], obj=match_engine)
        expected = {"Ethernet0": {"ASIC_DB": {"keys": [{"ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF:oid:0xd00000000056d": {"SAI_HOSTIF_ATTR_NAME": "Ethernet0", "SAI_HOSTIF_ATTR_OBJ_ID": "oid:0x10000000004a4", "SAI_HOSTIF_ATTR_OPER_STATUS": "true", "SAI_HOSTIF_ATTR_TYPE": "SAI_HOSTIF_TYPE_NETDEV", "SAI_HOSTIF_ATTR_VLAN_TAG": "SAI_HOSTIF_VLAN_TAG_STRIP"}}, {"ASIC_STATE:SAI_OBJECT_TYPE_PORT:oid:0x10000000004a4": {"NULL": "NULL", "SAI_PORT_ATTR_ADMIN_STATE": "true", "SAI_PORT_ATTR_MTU": "9122", "SAI_PORT_ATTR_SPEED": "100000"}}], "tables_not_found": [], "vidtorid": {"oid:0xd00000000056d": "oid:0xd", "oid:0x10000000004a4": "oid:0x1690000000001"}},
                                  "STATE_DB": {"keys": [{"PORT_TABLE|Ethernet0": {"speed": "100000", "supported_speeds": "10000,25000,40000,100000"}}], "tables_not_found": []}}}
        assert result.exit_code == 0, "exit code: {}, Exception: {}, Traceback: {}".format(result.exit_code, result.exception, result.exc_info)
        ddiff = compare_json_output(expected, result.output)
        assert not ddiff, ddiff

    def test_option_tabular_display(self, match_engine):
        runner = CliRunner()
        result = runner.invoke(dump.state, ["port", "Ethernet0", "--db", "STATE_DB", "--table"], obj=match_engine)
        assert result.exit_code == 0, "exit code: {}, Exception: {}, Traceback: {}".format(result.exit_code, result.exception, result.exc_info)
        assert table_display_output == result.output

    def test_option_tabular_display_no_db_filter(self, match_engine):
        runner = CliRunner()
        result = runner.invoke(dump.state, ["port", "Ethernet0", "--table", "--key-map"], obj=match_engine)
        assert result.exit_code == 0, "exit code: {}, Exception: {}, Traceback: {}".format(result.exit_code, result.exception, result.exc_info)
        assert table_display_output_no_filtering == result.output

    def test_identifier_all_with_filtering(self, match_engine):
        runner = CliRunner()
        expected_entries = ["Ethernet0", "Ethernet4", "Ethernet156", "Ethernet160", "Ethernet164", "Ethernet176", "Ethernet60"]
        result = runner.invoke(dump.state, ["port", "all", "--db", "CONFIG_DB", "--key-map"], obj=match_engine)
        print(result.output)
        try:
            rec_json = json.loads(result.output)
        except Exception as e:
            assert 0, "CLI Output is not in JSON Format"
        ddiff = DeepDiff(set(expected_entries), set(rec_json.keys()))
        assert not ddiff, "Expected Entries were not recieved when passing all keyword"

    def test_namespace_single_asic(self, match_engine):
        runner = CliRunner()
        result = runner.invoke(dump.state, ["port", "Ethernet0", "--table", "--key-map", "--namespace", "asic0"], obj=match_engine)
        print(result.output)
        assert result.output == "Namespace option is not valid for a single-ASIC device\n"
    
    def test_populate_fv_config_file(self, match_engine):
        test_data = {
            "COPP_TRAP": {
                "bgp": {
                    "trap_ids": "bgp,bgpv6",
                    "trap_group": "queue4_group1"
                }
            },
            "COPP_GROUP": {
                "queue4_group1": {
                    "trap_action":"trap",
                    "trap_priority":"4",
                    "queue": "4"
                }
            }
        }
        with Patcher() as patcher:
            patcher.fs.create_file("/etc/sonic/copp_cfg.json", contents=json.dumps(test_data))
            runner = CliRunner()
            result = runner.invoke(dump.state, ["copp", "bgp", "--table", "--db", "CONFIG_FILE"], obj=match_engine)
            print(result)
            print(result.output)
            assert result.output == table_config_file_copp

@pytest.fixture(scope="class")
def match_engine_masic():
    print("SETUP")
    os.environ["VERBOSE"] = "1"

    from ..mock_tables import mock_multi_asic
    reload(mock_multi_asic)
    from ..mock_tables import dbconnector
    dbconnector.load_namespace_config()

    dump_input = os.path.join(os.path.dirname(__file__), "../dump_input/")
    dedicated_dbs = {}

    conn = SonicV2Connector()
    # popualate the db ,with mock data
    db_names = list(dedicated_dbs.keys())
    try:
        populate_mock(conn, db_names, dedicated_dbs)
    except Exception as e:
        assert False, "Mock initialization failed: " + str(e)

    conn_pool = ConnectionPool()
    dedicated_dbs['CONFIG_DB'] = os.path.join(dump_input, "dump/default/config_db.json")
    dedicated_dbs['APPL_DB'] = os.path.join(dump_input, "dump/default/appl_db.json")
    dedicated_dbs['STATE_DB'] = os.path.join(dump_input, "dump/default/state_db.json")
    dedicated_dbs['ASIC_DB'] =  os.path.join(dump_input, "dump/default/asic_db.json")
    conn_pool.fill(DEFAULT_NAMESPACE, conn_pool.initialize_connector(DEFAULT_NAMESPACE), list(dedicated_dbs.keys()))
    populate_mock(conn_pool.cache[DEFAULT_NAMESPACE][CONN], list(dedicated_dbs.keys()), dedicated_dbs)

    dedicated_dbs['CONFIG_DB'] = os.path.join(dump_input, "dump/asic0/config_db.json")
    dedicated_dbs['APPL_DB'] = os.path.join(dump_input, "dump/asic0/appl_db.json")
    dedicated_dbs['STATE_DB'] = os.path.join(dump_input, "dump/asic0/state_db.json")
    dedicated_dbs['ASIC_DB'] =  os.path.join(dump_input, "dump/asic0/asic_db.json")
    conn_pool.fill("asic0", conn_pool.initialize_connector("asic0"), list(dedicated_dbs.keys()))
    populate_mock(conn_pool.cache["asic0"][CONN], list(dedicated_dbs.keys()), dedicated_dbs)

    dedicated_dbs['CONFIG_DB'] = os.path.join(dump_input, "dump/asic1/config_db.json")
    dedicated_dbs['APPL_DB'] = os.path.join(dump_input, "dump/asic1/appl_db.json")
    dedicated_dbs['STATE_DB'] = os.path.join(dump_input, "dump/asic1/state_db.json")
    dedicated_dbs['ASIC_DB'] =  os.path.join(dump_input, "dump/asic1/asic_db.json")
    conn_pool.fill("asic1", conn_pool.initialize_connector("asic1"), list(dedicated_dbs.keys()))
    populate_mock(conn_pool.cache["asic1"][CONN], list(dedicated_dbs.keys()), dedicated_dbs)

    match_engine = MatchEngine(conn_pool)
    yield match_engine
    print("TEARDOWN")

@pytest.mark.usefixtures("match_engine_masic")
class TestDumpStateMultiAsic(object):

    def test_default_namespace(self, match_engine_masic):
        runner = CliRunner()
        result = runner.invoke(dump.state, ["port", "Ethernet0", "--key-map"], obj=match_engine_masic)
        expected = {"Ethernet0": {"CONFIG_DB": {"keys": ["PORT|Ethernet0"], "tables_not_found": []},
                                  "APPL_DB": {"keys": ["PORT_TABLE:Ethernet0"], "tables_not_found": []},
                                  "ASIC_DB": {"keys": ["ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF:oid:0xd00000000056d", "ASIC_STATE:SAI_OBJECT_TYPE_PORT:oid:0x10000000004a4"], "tables_not_found": [], "vidtorid": {"oid:0xd00000000056d": "oid:0xd", "oid:0x10000000004a4": "oid:0x1690000000001"}},
                                  "STATE_DB": {"keys": ["PORT_TABLE|Ethernet0"], "tables_not_found": []}}}
        assert result.exit_code == 0, "exit code: {}, Exception: {}, Output: {}".format(result.exit_code, result.exception, result.output)
        ddiff = compare_json_output(expected, result.output)
        assert not ddiff, ddiff

    def test_namespace_asic0(self, match_engine_masic):
        runner = CliRunner()
        result = runner.invoke(dump.state, ["port", "Ethernet0", "--namespace", "asic0"], obj=match_engine_masic)
        expected = {"Ethernet0": {"CONFIG_DB": {"keys": [{"PORT|Ethernet0": {"admin_status": "up", "alias": "Ethernet1/1", "asic_port_name": "Eth0-ASIC0", "description": "ARISTA01T2:Ethernet3/1/1", "lanes": "33,34,35,36", "mtu": "9100", "pfc_asym": "off", "role": "Ext", "speed": "40000"}}], "tables_not_found": []},
                                  "APPL_DB": {"keys": [{"PORT_TABLE:Ethernet0": {"lanes": "33,34,35,36", "description": "ARISTA01T2:Ethernet3/1/1", "pfc_asym": "off", "mtu": "9100", "alias": "Ethernet1/1", "oper_status": "up", "admin_status": "up", "role": "Ext", "speed": "40000", "asic_port_name": "Eth0-ASIC0"}}], "tables_not_found": []},
                                  "ASIC_DB": {"keys": [], "tables_not_found": ["ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF", "ASIC_STATE:SAI_OBJECT_TYPE_PORT"]}, "STATE_DB": {"keys": [], "tables_not_found": ["PORT_TABLE"]}}}
        print(expected)
        assert result.exit_code == 0, "exit code: {}, Exception: {}, Output: {}".format(result.exit_code, result.exception, result.output)
        ddiff = compare_json_output(expected, result.output)
        assert not ddiff, ddiff

    def test_namespace_asic1(self, match_engine_masic):
        runner = CliRunner()
        result = runner.invoke(dump.state, ["port", "Ethernet-BP256", "--namespace", "asic1"], obj=match_engine_masic)
        expected = {"Ethernet-BP256":
                    {"CONFIG_DB": {"keys": [{"PORT|Ethernet-BP256": {"admin_status": "up", "alias": "Ethernet-BP256", "asic_port_name": "Eth0-ASIC1", "description": "ASIC0:Eth16-ASIC0", "lanes": "61,62,63,64", "mtu": "9100", "pfc_asym": "off", "role": "Int", "speed": "40000"}}], "tables_not_found": []},
                     "APPL_DB": {"keys": [{"PORT_TABLE:Ethernet-BP256": {"oper_status": "up", "lanes": "61,62,63,64", "description": "ASIC0:Eth16-ASIC0", "pfc_asym": "off", "mtu": "9100", "alias": "Ethernet-BP256", "admin_status": "up", "speed": "40000", "asic_port_name": "Eth0-ASIC1"}}], "tables_not_found": []},
                     "ASIC_DB": {"keys": [], "tables_not_found": ["ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF", "ASIC_STATE:SAI_OBJECT_TYPE_PORT"]},
                     "STATE_DB": {"keys": [], "tables_not_found": ["PORT_TABLE"]}}}
        assert result.exit_code == 0, "exit code: {}, Exception: {}, Output: {}".format(result.exit_code, result.exception, result.output)
        ddiff = compare_json_output(expected, result.output)
        assert not ddiff, ddiff

    def test_invalid_namespace(self, match_engine_masic):
        runner = CliRunner()
        result = runner.invoke(dump.state, ["port", "Ethernet0", "--namespace", "asic3"], obj=match_engine_masic)
        assert result.output == "Namespace option is not valid. Choose one of ['asic0', 'asic1']\n", result


class TestMultiAsicInit:
    """Test multi-asic initialization in dump command group"""

    @mock.patch('dump.plugins.dump_modules', {})
    @mock.patch('dump.main.SonicDBConfig')
    @mock.patch('dump.main.multi_asic')
    def test_multi_asic_global_config_init(self, mock_multi_asic, mock_sonic_db_config):
        """Test that SonicDBConfig.initializeGlobalConfig() is called when multi-asic and not initialized"""
        mock_multi_asic.is_multi_asic.return_value = True
        mock_sonic_db_config.isGlobalInit.return_value = False
        runner = CliRunner()
        runner.invoke(dump.state, ['port', 'Ethernet0'])
        mock_multi_asic.is_multi_asic.assert_called()
        mock_sonic_db_config.isGlobalInit.assert_called()
        mock_sonic_db_config.initializeGlobalConfig.assert_called_once()

    @mock.patch('dump.plugins.dump_modules', {})
    @mock.patch('dump.main.SonicDBConfig')
    @mock.patch('dump.main.multi_asic')
    def test_multi_asic_already_initialized(self, mock_multi_asic, mock_sonic_db_config):
        """Test that initializeGlobalConfig() is NOT called when already initialized"""
        mock_multi_asic.is_multi_asic.return_value = True
        mock_sonic_db_config.isGlobalInit.return_value = True
        runner = CliRunner()
        runner.invoke(dump.state, ['port', 'Ethernet0'])
        mock_multi_asic.is_multi_asic.assert_called()
        mock_sonic_db_config.isGlobalInit.assert_called()
        mock_sonic_db_config.initializeGlobalConfig.assert_not_called()

    @mock.patch('dump.plugins.dump_modules', {})
    @mock.patch('dump.main.SonicDBConfig')
    @mock.patch('dump.main.multi_asic')
    def test_single_asic_no_init(self, mock_multi_asic, mock_sonic_db_config):
        """Test that initializeGlobalConfig() is NOT called on single-asic systems"""
        mock_multi_asic.is_multi_asic.return_value = False
        runner = CliRunner()
        runner.invoke(dump.state, ['port', 'Ethernet0'])
        mock_multi_asic.is_multi_asic.assert_called()
        mock_sonic_db_config.isGlobalInit.assert_not_called()
        mock_sonic_db_config.initializeGlobalConfig.assert_not_called()


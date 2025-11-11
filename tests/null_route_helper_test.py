import pytest
import os
from .utils import load_source

from click.testing import CliRunner
from swsscommon.swsscommon import ConfigDBConnector


null_route_helper = load_source('null_route_helper', os.path.join(os.path.dirname(__file__), '..',
                                                                  'scripts', 'null_route_helper'))
null_route_helper.ConfigDBConnector = ConfigDBConnector

expected_stdout_v4 = "" + \
"""Table          Rule                      Priority  Action    Match
-------------  ----------------------  ----------  --------  -----------
NULL_ROUTE_V4  BLOCK_RULE_10.0.0.2/32        9999  DROP      10.0.0.2/32
NULL_ROUTE_V4  BLOCK_RULE_10.0.0.3/32        9999  FORWARD   10.0.0.3/32
"""

expected_stdout_v6 = "" + \
"""Table          Rule                                     Priority  Action    Match
-------------  -------------------------------------  ----------  --------  --------------------------
NULL_ROUTE_V6  BLOCK_RULE_1000:1000:1000:1000::2/128        9999  DROP      1000:1000:1000:1000::2/128
NULL_ROUTE_V6  BLOCK_RULE_1000:1000:1000:1000::3/128        9999  FORWARD   1000:1000:1000:1000::3/128
"""

def test_ip_validation():
    # Verify prefix len will be appended if not set
    assert(null_route_helper.validate_input("1.2.3.4") == "1.2.3.4/32")
    assert(null_route_helper.validate_input("::1") == "::1/128")

    assert(null_route_helper.validate_input("1.2.3.4/32") == "1.2.3.4/32")

    assert(null_route_helper.validate_input("1000:1000:1000:1000::1/128") == "1000:1000:1000:1000::1/128")

    with pytest.raises(SystemExit) as e:
        null_route_helper.validate_input("a.b.c.d")
    assert(e.value.code != 0)

    with pytest.raises(SystemExit) as e:
        null_route_helper.validate_input("1.2.3.4/21/32")
    assert(e.value.code != 0)

    # Verify only 32 prefix len is accepted for IPv4
    with pytest.raises(SystemExit) as e:
        null_route_helper.validate_input("1.2.3.4/21")
    assert(e.value.code != 0)

    # Verify only 128 prefix len is accepted for IPv6
    with pytest.raises(SystemExit) as e:
        null_route_helper.validate_input("1000:1000:1000:1000::1/120")
    assert(e.value.code != 0)


def test_confirm_required_table_existence():
    configdb = ConfigDBConnector()
    configdb.connect()

    assert(null_route_helper.confirm_required_table_existence(configdb, "NULL_ROUTE_V4"))
    assert(null_route_helper.confirm_required_table_existence(configdb, "NULL_ROUTE_V6"))

    with pytest.raises(SystemExit) as e:
        null_route_helper.confirm_required_table_existence(configdb, "NULL_ROUTE_FAKE")
    assert(e.value.code != 0)


def test_build_rule():
    expected_rule_v4 = {
        "PRIORITY": "9999",
        "PACKET_ACTION": "DROP",
        "ETHER_TYPE": "2048",
        "SRC_IP": "1.2.3.4/32"
    }
    expected_rule_v6 = {
        "PRIORITY": "9999",
        "PACKET_ACTION": "DROP",
        "IP_TYPE": "IPV6ANY",
        "SRC_IPV6": "1000:1000:1000:1000::1/128"
    }

    assert(null_route_helper.build_acl_rule(9999, "1.2.3.4/32") == expected_rule_v4)
    assert(null_route_helper.build_acl_rule(9999, "1000:1000:1000:1000::1/128") == expected_rule_v6)


def test_get_rule():
    configdb = ConfigDBConnector()
    configdb.connect()

    assert(null_route_helper.get_rule(configdb, "NULL_ROUTE_ABSENT", "10.0.0.1/32") == None)

    assert(null_route_helper.get_rule(configdb, "NULL_ROUTE_V4", "10.0.0.1/32") == None)
    assert(null_route_helper.get_rule(configdb, "NULL_ROUTE_V4", "10.0.0.2/32"))

    assert(null_route_helper.get_rule(configdb, "NULL_ROUTE_V6", "1000:1000:1000:1000::1/128") == None)
    assert(null_route_helper.get_rule(configdb, "NULL_ROUTE_V6", "1000:1000:1000:1000::2/128"))


def test_run_when_table_absent():
    runner = CliRunner()

    result = runner.invoke(null_route_helper.cli.commands['block'], ['TABLE_ABSENT', '1.2.3.4'])
    assert(result.exit_code != 0)
    assert("not found" in result.output)

    result = runner.invoke(null_route_helper.cli.commands['unblock'], ['TABLE_ABSENT', '1.2.3.4'])
    assert(result.exit_code != 0)
    assert("not found" in result.output)


def test_run_with_invalid_ip():
    runner = CliRunner()

    result = runner.invoke(null_route_helper.cli.commands['block'], ['NULL_ROUTE_V4', 'a.b.c.d'])
    assert(result.exit_code != 0)
    assert("as a valid IP address" in result.output)

    result = runner.invoke(null_route_helper.cli.commands['block'], ['NULL_ROUTE_V6', 'xx:xx:xx:xx'])
    assert(result.exit_code != 0)
    assert("as a valid IP address" in result.output)

    result = runner.invoke(null_route_helper.cli.commands['unblock'], ['NULL_ROUTE_V4', 'a.b.c.d'])
    assert(result.exit_code != 0)
    assert("as a valid IP address" in result.output)

    result = runner.invoke(null_route_helper.cli.commands['unblock'], ['NULL_ROUTE_V6', 'xx:xx:xx:xx'])
    assert(result.exit_code != 0)
    assert("as a valid IP address" in result.output)

    result = runner.invoke(null_route_helper.cli.commands['block'], ['NULL_ROUTE_V4', '1.2.3.4/21'])
    assert(result.exit_code != 0)
    assert("Prefix length must be" in result.output)

    result = runner.invoke(null_route_helper.cli.commands['block'], ['NULL_ROUTE_V6', '::1/120'])
    assert(result.exit_code != 0)
    assert("Prefix length must be" in result.output)
    

def test_block():
    runner = CliRunner()

    # Verify block ip that is already blocked
    result = runner.invoke(null_route_helper.cli.commands['block'], ['NULL_ROUTE_V4', '10.0.0.2/32'])
    assert(result.exit_code == 0)

    # Verify block ip that is marked as forward
    result = runner.invoke(null_route_helper.cli.commands['block'], ['NULL_ROUTE_V4', '10.0.0.3/32'])
    assert(result.exit_code == 0)

    # Verify unblock ip that is not present in any rule
    result = runner.invoke(null_route_helper.cli.commands['block'], ['NULL_ROUTE_V4', '10.0.0.4/32'])
    assert(result.exit_code == 0)

    # Verify block ipv6 that is already blocked
    result = runner.invoke(null_route_helper.cli.commands['block'], ['NULL_ROUTE_V6', '1000:1000:1000:1000::2/128'])
    assert(result.exit_code == 0)

    # Verify block ipv6 that is marked as forward
    result = runner.invoke(null_route_helper.cli.commands['block'], ['NULL_ROUTE_V6', '1000:1000:1000:1000::3/128'])
    assert(result.exit_code == 0)

    # Verify block ipv6 that is not present in any rule
    result = runner.invoke(null_route_helper.cli.commands['block'], ['NULL_ROUTE_V6', '1000:1000:1000:1000::4/128'])
    assert(result.exit_code == 0)


def test_unblock():
    runner = CliRunner()

    # Verify unblock ip that is blocked
    result = runner.invoke(null_route_helper.cli.commands['unblock'], ['NULL_ROUTE_V4', '10.0.0.2/32'])
    assert(result.exit_code == 0)

    # Verify unblock ip that is not blocked
    result = runner.invoke(null_route_helper.cli.commands['unblock'], ['NULL_ROUTE_V4', '10.0.0.3/32'])
    assert(result.exit_code == 0)

    # Verify unblock ip that is not present in any rule
    result = runner.invoke(null_route_helper.cli.commands['unblock'], ['NULL_ROUTE_V4', '10.0.0.4/32'])
    assert(result.exit_code == 0)

    # Verify unblock ipv6 that is blocked
    result = runner.invoke(null_route_helper.cli.commands['unblock'], ['NULL_ROUTE_V6', '1000:1000:1000:1000::2/128'])
    assert(result.exit_code == 0)

    # Verify unblock ipv6 that is marked as forward
    result = runner.invoke(null_route_helper.cli.commands['unblock'], ['NULL_ROUTE_V6', '1000:1000:1000:1000::3/128'])
    assert(result.exit_code == 0)

    # Verify unblock ipv6 that is not present in any rule
    result = runner.invoke(null_route_helper.cli.commands['unblock'], ['NULL_ROUTE_V6', '1000:1000:1000:1000::4/128'])
    assert(result.exit_code == 0)


def test_list():
    runner = CliRunner()

    # Verify list rules in non-existing table
    result = runner.invoke(null_route_helper.cli.commands['list'], ['FAKE_NULL_ROUTE_V4'])
    assert(result.exit_code != 0)

    # Verify show IPv4 rules
    result = runner.invoke(null_route_helper.cli.commands['list'], ['NULL_ROUTE_V4'])
    assert(result.stdout == expected_stdout_v4)

    # Verify show IPv6 rules
    result = runner.invoke(null_route_helper.cli.commands['list'], ['NULL_ROUTE_V6'])
    assert(result.stdout == expected_stdout_v6)


import os
import sys
import mock
import pytest
from importlib import reload
from tabulate import tabulate

from click.testing import CliRunner
from utilities_common.db import Db
from .mock_tables import dbconnector

import crm.main as crm


test_path = os.path.dirname(os.path.abspath(__file__))
mock_db_path = os.path.join(test_path, "crm_dash")


@mock.patch('sonic_py_common.device_info.get_platform_info', mock.MagicMock(return_value={"switch_type": "dpu"}))
class TestCrmDash(object):

    dash_thresholds = [
        ("dash_vnet", ('dash', 'vnet')),
        ("dash_eni", ('dash', 'eni')),
        ("dash_eni_ether_address_map", ('dash', 'eni-ether-address')),
        ("dash_ipv4_inbound_routing", ('dash', 'ipv4', 'inbound', 'routing')),
        ("dash_ipv6_inbound_routing", ('dash', 'ipv6', 'inbound', 'routing')),
        ("dash_ipv4_outbound_routing", ('dash', 'ipv4', 'outbound', 'routing')),
        ("dash_ipv6_outbound_routing", ('dash', 'ipv6', 'outbound', 'routing')),
        ("dash_ipv4_pa_validation", ('dash', 'ipv4', 'pa-validation')),
        ("dash_ipv6_pa_validation", ('dash', 'ipv6', 'pa-validation')),
        ("dash_ipv4_outbound_ca_to_pa", ('dash', 'ipv4', 'outbound', 'ca-to-pa')),
        ("dash_ipv6_outbound_ca_to_pa", ('dash', 'ipv6', 'outbound', 'ca-to-pa')),
        ("dash_ipv4_acl_group", ('dash', 'ipv4', 'acl', 'group')),
        ("dash_ipv6_acl_group", ('dash', 'ipv6', 'acl', 'group')),
        ("dash_ipv4_acl_rule", ('dash', 'ipv4', 'acl', 'rule')),
        ("dash_ipv6_acl_rule", ('dash', 'ipv6', 'acl', 'rule')),
    ]

    dash_resources = [
        ("dash_vnet", ('dash', 'vnet'), (2, 200000000)),
        ("dash_eni", ('dash', 'eni'), (9, 1000000)),
        ("dash_eni_ether_address_map", ('dash', 'eni-ether-address'), (9, 1000000)),
        ("dash_ipv4_inbound_routing", ('dash', 'ipv4', 'inbound', 'routing'), (9, 200000000)),
        ("dash_ipv4_outbound_routing", ('dash', 'ipv4', 'outbound', 'routing'), (9, 1000000)),
        ("dash_ipv6_inbound_routing", ('dash', 'ipv6', 'inbound', 'routing'), (0, 200000000)),
        ("dash_ipv6_outbound_routing", ('dash', 'ipv6', 'outbound', 'routing'), (0, 1000000)),
        ("dash_ipv4_pa_validation", ('dash', 'ipv4', 'pa-validation'), (0, 1000000)),
        ("dash_ipv6_pa_validation", ('dash', 'ipv6', 'pa-validation'), (0, 1000000)),
        ("dash_ipv4_outbound_ca_to_pa", ('dash', 'ipv4', 'outbound', 'ca-to-pa'), (0, 1000000)),
        ("dash_ipv6_outbound_ca_to_pa", ('dash', 'ipv6', 'outbound', 'ca-to-pa'), (0, 1000000)),
        ("dash_ipv4_acl_group", ('dash', 'ipv4', 'acl', 'group'), (27, 200000000)),
        ("dash_ipv6_acl_group", ('dash', 'ipv6', 'acl', 'group'), (0, 200000000)),
    ]

    dash_acl_group_resources = [
        ("dash_ipv4_acl_rule", ('dash', 'ipv4', 'acl', 'rule'), "0x6a00000000002d", (100, 200000000)),
        ("dash_ipv6_acl_rule", ('dash', 'ipv6', 'acl', 'rule'), "0x6a00000000009d", (1000, 200000000)),
    ]

    dash_thresholds_header = ("Resource Name", "Threshold Type", "Low Threshold", "High Threshold")
    dash_resources_header = ("Resource Name", "Used Count", "Available Count")
    dash_acl_group_resources_header = ("DASH ACL Group ID", "Resource Name", "Used Count", "Available Count")

    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"
        dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(mock_db_path, 'config_db')
        dbconnector.dedicated_dbs['COUNTERS_DB'] = os.path.join(mock_db_path, "counters_db")

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        dbconnector.dedicated_dbs['CONFIG_DB'] = None
        dbconnector.dedicated_dbs['COUNTERS_DB'] = None
        dbconnector.load_namespace_config()

    @pytest.mark.parametrize("obj, cmd", dash_thresholds)
    def test_crm_show_thresholds(self, obj, cmd):
        reload(crm)

        db = Db()
        runner = CliRunner()
        result = runner.invoke(crm.cli, ('show', 'thresholds') + cmd, obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

        expected_output = tabulate([(obj, "percentage", "70", "85")], headers=self.dash_thresholds_header, tablefmt="simple", missingval="")
        assert result.output == "\n" + expected_output + "\n\n"

        result = runner.invoke(crm.cli, ('config', 'thresholds') + cmd + ('high', '90'), obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

        result = runner.invoke(crm.cli, ('config', 'thresholds') + cmd + ('low', '60'), obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

        result = runner.invoke(crm.cli, ('show', 'thresholds') + cmd, obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

        expected_output = tabulate([(obj, "percentage", "60", "90")], headers=self.dash_thresholds_header, tablefmt="simple", missingval="")
        assert result.output == "\n" + expected_output + "\n\n"

    def test_crm_show_all_thresholds(self):
        reload(crm)

        db = Db()
        runner = CliRunner()
        result = runner.invoke(crm.cli, ('show', 'thresholds', 'all'), obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

        table = []
        for obj in self.dash_thresholds:
            table.append((obj[0], "percentage", "70", "85"))

        expected_output = tabulate(table, headers=self.dash_thresholds_header, tablefmt="simple", missingval="")
        assert result.output == "\n" + expected_output + "\n\n"

    @pytest.mark.parametrize("obj, cmd, cnt", dash_resources)
    def test_crm_show_resources(self, obj, cmd, cnt):
        reload(crm)

        db = Db()
        runner = CliRunner()
        result = runner.invoke(crm.cli, ('show', 'resources') + cmd, obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

        expected_output = tabulate([(obj,) + cnt], headers=self.dash_resources_header, tablefmt="simple", missingval="")
        assert result.output == "\n" + expected_output + "\n\n"

    @pytest.mark.parametrize("obj, cmd, obj_id, cnt", dash_acl_group_resources)
    def test_crm_show_acl_group_resources(self, obj, cmd, obj_id, cnt):
        reload(crm)

        db = Db()
        runner = CliRunner()
        result = runner.invoke(crm.cli, ('show', 'resources') + cmd, obj=db)
        print(sys.stderr, result.output)
        assert result.exit_code == 0

        expected_output = tabulate([(obj_id, obj) + cnt], headers=self.dash_acl_group_resources_header, tablefmt="simple", missingval="")
        assert result.output == "\n" + expected_output + "\n\n"


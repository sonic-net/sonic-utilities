import os
import unittest
import pytest
import json
from deepdiff import DeepDiff
from mock import patch
from dump.helper import create_template_dict, populate_mock
from dump.plugins.route import Route
from dump.match_infra import MatchEngine, ConnectionPool
from swsscommon.swsscommon import SonicV2Connector
from utilities_common.constants import DEFAULT_NAMESPACE

# Location for dedicated db's used for UT
module_tests_path = os.path.dirname(__file__)
dump_tests_path = os.path.join(module_tests_path, "../")
tests_path = os.path.join(dump_tests_path, "../")
dump_test_input = os.path.join(tests_path, "dump_input")
Route_files_path = os.path.join(dump_test_input, "route")

# Define the mock files to read from
dedicated_dbs = {}
dedicated_dbs['CONFIG_DB'] = os.path.join(Route_files_path, "config_db.json")
dedicated_dbs['APPL_DB'] = os.path.join(Route_files_path, "appl_db.json")
dedicated_dbs['ASIC_DB'] = os.path.join(Route_files_path, "asic_db.json")


@pytest.fixture(scope="class", autouse=True)
def match_engine():

    print("SETUP")
    os.environ["VERBOSE"] = "1"

    # Monkey Patch the SonicV2Connector Object
    from ...mock_tables import dbconnector
    db = SonicV2Connector()

    # popualate the db with mock data
    db_names = list(dedicated_dbs.keys())
    try:
        populate_mock(db, db_names, dedicated_dbs)
    except Exception as e:
        assert False, "Mock initialization failed: " + str(e)

    # Initialize connection pool
    conn_pool = ConnectionPool()
    conn_pool.fill(DEFAULT_NAMESPACE, db, db_names)

    # Initialize match_engine
    match_engine = MatchEngine(conn_pool)
    yield match_engine
    print("TEARDOWN")
    os.environ["VERBOSE"] = "0"


def get_asic_route_key(dest):
    return "ASIC_STATE:SAI_OBJECT_TYPE_ROUTE_ENTRY:{\"dest\":\"" + dest + \
        "\",\"switch_id\":\"oid:0x21000000000000\",\"vr\":\"oid:0x3000000000002\"}"


@pytest.mark.usefixtures("match_engine")
class TestRouteModule:
    def test_static_route(self, match_engine):
        """
        Scenario: Fetch the Keys related to a Static Route from CONF, APPL & ASIC DB's
                  1) CONF & APPL are straightforward
                  2) SAI_ROUTE_ENTRY_ATTR_NEXT_HOP_ID = SAI_OBJECT_TYPE_NEXT_HOP here
                  For More details about SAI_ROUTE_ENTRY_ATTR_NEXT_HOP_ID, check the SAI header in sairoute.h
        """
        params = {Route.ARG_NAME: "20.0.0.0/24", "namespace": ""}
        m_route = Route(match_engine)
        returned = m_route.execute(params)
        expect = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB"])
        expect["CONFIG_DB"]["keys"].append("STATIC_ROUTE|20.0.0.0/24")
        expect["APPL_DB"]["keys"].append("ROUTE_TABLE:20.0.0.0/24")
        expect["ASIC_DB"]["keys"].append(get_asic_route_key("20.0.0.0/24"))
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_NEXT_HOP:oid:0x40000000002e7")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_ROUTER_INTERFACE:oid:0x60000000002cd")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_VIRTUAL_ROUTER:oid:0x3000000000002")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_ip2me_route(self, match_engine):
        """
        Scenario: Fetch the keys related to a ip2me route from APPL & ASIC DB.
                  1) CONF DB doesn't have a ip2me route entry unlike a static route.
                  2) APPL is straightforward
                  3) SAI_ROUTE_ENTRY_ATTR_NEXT_HOP_ID = SAI_OBJECT_TYPE_PORT (CPU Port)
                  4) Thus, no SAI_OBJECT_TYPE_ROUTER_INTERFACE entry for this route
                  For More details about SAI_ROUTE_ENTRY_ATTR_NEXT_HOP_ID, check the SAI header in sairoute.h
        """
        params = {Route.ARG_NAME: "fe80::/64", "namespace": ""}
        m_route = Route(match_engine)
        returned = m_route.execute(params)
        expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB"])
        expect["APPL_DB"]["keys"].append("ROUTE_TABLE:fe80::/64")
        expect["ASIC_DB"]["keys"].append(get_asic_route_key("fe80::/64"))
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_PORT:oid:0x1000000000001")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_VIRTUAL_ROUTER:oid:0x3000000000002")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_directly_connected_route(self, match_engine):
        """
        Scenario: Fetch the keys related to a directly connected route from APPL & ASIC DB.
                  1) CONF DB doesn't have this route entry
                  2) APPL is straightforward
                  3) SAI_ROUTE_ENTRY_ATTR_NEXT_HOP_ID = SAI_OBJECT_TYPE_ROUTER_INTERFACE
                  For More details about SAI_ROUTE_ENTRY_ATTR_NEXT_HOP_ID, check the SAI header in sairoute.h
        """
        params = {Route.ARG_NAME: "1.1.1.0/24", "namespace": ""}
        m_route = Route(match_engine)
        returned = m_route.execute(params)
        expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB"])
        expect["APPL_DB"]["keys"].append("ROUTE_TABLE:1.1.1.0/24")
        expect["ASIC_DB"]["keys"].append(get_asic_route_key("1.1.1.0/24"))
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_ROUTER_INTERFACE:oid:0x60000000002cd")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_VIRTUAL_ROUTER:oid:0x3000000000002")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_route_with_next_hop(self, match_engine):
        """
        Scenario: Fetch the keys related to a route with next hop.
                  1) CONF DB doesn't have this route entry
                  2) APPL is straightforward
                  3) SAI_ROUTE_ENTRY_ATTR_NEXT_HOP_ID = SAI_OBJECT_TYPE_NEXT_HOP
                  For More details about SAI_ROUTE_ENTRY_ATTR_NEXT_HOP_ID, check the SAI header in sairoute.h
        """
        params = {Route.ARG_NAME: "10.212.0.0/16", "namespace": ""}
        m_route = Route(match_engine)
        returned = m_route.execute(params)
        expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB"])
        expect["APPL_DB"]["keys"].append("ROUTE_TABLE:10.212.0.0/16")
        expect["ASIC_DB"]["keys"].append(get_asic_route_key("10.212.0.0/16"))
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_NEXT_HOP:oid:0x40000000002e7")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_ROUTER_INTERFACE:oid:0x60000000002cd")
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_VIRTUAL_ROUTER:oid:0x3000000000002")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_no_next_hop_id(self, match_engine):
        """
        Scenario: Fetch the keys related to a route with no next hop id
                  1) CONF DB doesn't have this route entry
                  2) APPL is straightforward
                  3) SAI_ROUTE_ENTRY_ATTR_NEXT_HOP_ID = EMPTY
                  For More details about SAI_ROUTE_ENTRY_ATTR_NEXT_HOP_ID, check the SAI header in sairoute.h
        """
        params = {Route.ARG_NAME: "0.0.0.0/0", "namespace": ""}
        m_route = Route(match_engine)
        returned = m_route.execute(params)
        expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB"])
        expect["APPL_DB"]["tables_not_found"].append("ROUTE_TABLE")
        expect["ASIC_DB"]["keys"].append(get_asic_route_key("0.0.0.0/0"))
        expect["ASIC_DB"]["keys"].append("ASIC_STATE:SAI_OBJECT_TYPE_VIRTUAL_ROUTER:oid:0x3000000000002")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def get_asic_nh_group_expected(self, asic_route_key):
        expect = []
        expect.append(asic_route_key)
        exp_nh_group = "ASIC_STATE:SAI_OBJECT_TYPE_NEXT_HOP_GROUP:oid:0x5000000000689"
        exp_nh_group_mem = ["ASIC_STATE:SAI_OBJECT_TYPE_NEXT_HOP_GROUP_MEMBER:oid:0x2d00000000068a",
                            "ASIC_STATE:SAI_OBJECT_TYPE_NEXT_HOP_GROUP_MEMBER:oid:0x2d00000000068b",
                            "ASIC_STATE:SAI_OBJECT_TYPE_NEXT_HOP_GROUP_MEMBER:oid:0x2d00000000068c",
                            "ASIC_STATE:SAI_OBJECT_TYPE_NEXT_HOP_GROUP_MEMBER:oid:0x2d00000000068d"]
        exp_nh = ["ASIC_STATE:SAI_OBJECT_TYPE_NEXT_HOP:oid:0x400000000066f",
                  "ASIC_STATE:SAI_OBJECT_TYPE_NEXT_HOP:oid:0x400000000067f",
                  "ASIC_STATE:SAI_OBJECT_TYPE_NEXT_HOP:oid:0x4000000000665",
                  "ASIC_STATE:SAI_OBJECT_TYPE_NEXT_HOP:oid:0x4000000000667"]
        exp_rif = ["ASIC_STATE:SAI_OBJECT_TYPE_ROUTER_INTERFACE:oid:0x60000000005c6",
                   "ASIC_STATE:SAI_OBJECT_TYPE_ROUTER_INTERFACE:oid:0x60000000005c7",
                   "ASIC_STATE:SAI_OBJECT_TYPE_ROUTER_INTERFACE:oid:0x60000000005c8",
                   "ASIC_STATE:SAI_OBJECT_TYPE_ROUTER_INTERFACE:oid:0x60000000005c9"]
        expect.append(exp_nh_group)
        expect.extend(exp_nh_group_mem)
        expect.extend(exp_nh)
        expect.extend(exp_rif)
        expect.append("ASIC_STATE:SAI_OBJECT_TYPE_VIRTUAL_ROUTER:oid:0x3000000000002")
        return expect

    def test_route_with_next_hop_group(self, match_engine):
        """
        Scenario: Fetch the keys related to a route with multiple next hops.
                  1) CONF DB doesn't have this route entry
                  2) APPL is straightforward
                  3) SAI_ROUTE_ENTRY_ATTR_NEXT_HOP_ID = SAI_OBJECT_TYPE_NEXT_HOP_GROUP
                  For More details about SAI_ROUTE_ENTRY_ATTR_NEXT_HOP_ID, check the SAI header in sairoute.h
        """
        params = {Route.ARG_NAME: "20c0:e6e0:0:80::/64", "namespace": ""}
        m_route = Route(match_engine)
        returned = m_route.execute(params)
        expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB"])
        expect["APPL_DB"]["keys"].append("ROUTE_TABLE:20c0:e6e0:0:80::/64")
        expect["ASIC_DB"]["keys"].extend(self.get_asic_nh_group_expected(get_asic_route_key("20c0:e6e0:0:80::/64")))
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_caching_redis_keys(self, match_engine):
        """
        Scenario: Test the caching mechanism which reduces number of redis calls
        """
        global num_hits, num_miss, msgs
        num_hits, num_miss, msgs = 0, 0, []

        def verbose_print_mock(msg):
            global num_hits, num_miss, msgs
            if "Cache Hit for Key:" in msg:
                num_hits = num_hits + 1
            elif "Cache Miss for Key:" in msg:
                num_miss = num_miss + 1
            else:
                return
            msgs.append(msg)

        with patch("dump.match_infra.verbose_print", verbose_print_mock):
            m_route = Route(match_engine)
            params = {Route.ARG_NAME: "20c0:e6e0:0:80::/64", "namespace": ""}
            returned = m_route.execute(params)
            expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB"])
            expect["APPL_DB"]["keys"].append("ROUTE_TABLE:20c0:e6e0:0:80::/64")
            expect["ASIC_DB"]["keys"].extend(self.get_asic_nh_group_expected(get_asic_route_key("20c0:e6e0:0:80::/64")))
            ddiff = DeepDiff(returned, expect, ignore_order=True)
            assert not ddiff, ddiff
            print(msgs)
            assert num_hits == 0
            assert num_miss == 11
            num_hits, num_miss, msgs = 0, 0, []

            params = {Route.ARG_NAME: "192.168.0.4/24", "namespace": ""}
            returned = m_route.execute(params)
            expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB"])
            expect["APPL_DB"]["keys"].append("ROUTE_TABLE:192.168.0.4/24")
            expect["ASIC_DB"]["keys"].extend(self.get_asic_nh_group_expected(get_asic_route_key("192.168.0.4/24")))
            ddiff = DeepDiff(returned, expect, ignore_order=True)
            assert not ddiff, ddiff
            print(msgs)
            assert num_hits == 10
            assert num_miss == 1
            num_hits, num_miss, msgs = 0, 0, []

            params = {Route.ARG_NAME: "192.168.0.10/22", "namespace": ""}
            returned = m_route.execute(params)
            expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB"])
            expect["APPL_DB"]["keys"].append("ROUTE_TABLE:192.168.0.10/22")
            expect["ASIC_DB"]["keys"].extend(self.get_asic_nh_group_expected(get_asic_route_key("192.168.0.10/22")))
            ddiff = DeepDiff(returned, expect, ignore_order=True)
            assert not ddiff, ddiff
            print(msgs)
            assert num_hits == 10
            assert num_miss == 1

    def test_no_route_entry(self, match_engine):
        """
        Scenario: Fetch the keys related to a non-exitent route
        """
        params = {Route.ARG_NAME: "192.168.19.45/28", "namespace": ""}
        m_route = Route(match_engine)
        returned = m_route.execute(params)
        expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB"])
        expect["APPL_DB"]["tables_not_found"].append("ROUTE_TABLE")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_ROUTE_ENTRY")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_VIRTUAL_ROUTER")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        assert not ddiff, ddiff

    def test_route_with_nhgrp_appl_table(self, match_engine):
        """
        Scenario: Fetch the NEXTHOP_GROUP_TABLE keys, if the nexthop_group field has a NEXTHOP_GROUP_TABLE.key
        """
        params = {Route.ARG_NAME: "10.0.0.16/16", "namespace": ""}
        m_route = Route(match_engine)
        returned = m_route.execute(params)
        expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB"])
        expect["APPL_DB"]["keys"].append("ROUTE_TABLE:10.0.0.16/16")
        expect["APPL_DB"]["keys"].append("NEXTHOP_GROUP_TABLE:testnhg")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_ROUTE_ENTRY")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_VIRTUAL_ROUTER")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        print("Expected: {}".format(expect))
        print("Returned: {}".format(returned))
        assert not ddiff, ddiff

    def test_route_with_nhgrp_appl_table(self, match_engine):
        """
        Scenario: Fetch the NEXTHOP_GROUP_TABLE/CLASS_BASED_NEXT_HOP_GROUP_TABLE keys,
                  if the nexthop_group field has a CLASS_BASED_NEXT_HOP_GROUP_TABLE.key
        """
        params = {Route.ARG_NAME: "10.1.1.16/16", "namespace": ""}
        m_route = Route(match_engine)
        returned = m_route.execute(params)
        expect = create_template_dict(dbs=["APPL_DB", "ASIC_DB"])
        expect["APPL_DB"]["keys"].append("ROUTE_TABLE:10.1.1.16/16")
        expect["APPL_DB"]["keys"].append("NEXTHOP_GROUP_TABLE:testnhg")
        expect["APPL_DB"]["keys"].append("CLASS_BASED_NEXT_HOP_GROUP_TABLE:testcbfnhg")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_ROUTE_ENTRY")
        expect["ASIC_DB"]["tables_not_found"].append("ASIC_STATE:SAI_OBJECT_TYPE_VIRTUAL_ROUTER")
        ddiff = DeepDiff(returned, expect, ignore_order=True)
        print("Expected: {}".format(expect))
        print("Returned: {}".format(returned))
        assert not ddiff, ddiff

    def test_all_args(self, match_engine):
        """
        Scenario: Verify Whether the get_all_args method is working as expected
        """
        m_route = Route(match_engine)
        returned = m_route.get_all_args("")
        expect = ["1.1.1.0/24", "10.1.0.32", "10.212.0.0/16", "20.0.0.0/24", "192.168.0.10/22",
                  "fe80::/64", "20c0:e6e0:0:80::/64", "192.168.0.4/24", "10.1.1.16/16", "10.0.0.16/16"]
        ddiff = DeepDiff(expect, returned, ignore_order=True)
        assert not ddiff, ddiff

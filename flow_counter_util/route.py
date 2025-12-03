import os
import sys
from swsscommon.swsscommon import SonicV2Connector

try:
    if os.environ["UTILITIES_UNIT_TESTING"] == "1" or os.environ["UTILITIES_UNIT_TESTING"] == "2":
        modules_path = os.path.join(os.path.dirname(__file__), "..")
        test_path = os.path.join(modules_path, "tests")
        sys.path.insert(0, modules_path)
        sys.path.insert(0, test_path)
        import mock_tables.dbconnector  # lgtm[py/unused-import]
except KeyError:
    pass


COUNTERS_ROUTE_TO_PATTERN_MAP = 'COUNTERS_ROUTE_TO_PATTERN_MAP'
FLOW_COUNTER_CAPABILITY_TABLE = 'FLOW_COUNTER_CAPABILITY_TABLE'
FLOW_COUNTER_CAPABILITY_KEY = 'route'
FLOW_COUNTER_CAPABILITY_SUPPORT_FIELD = 'support'
FLOW_COUNTER_ROUTE_PATTERN_TABLE = 'FLOW_COUNTER_ROUTE_PATTERN'
FLOW_COUNTER_ROUTE_MAX_MATCH_FIELD = 'max_match_count'
FLOW_COUNTER_ROUTE_CONFIG_HEADER = ['Route pattern', 'VRF', 'Max']
DEFAULT_MAX_MATCH = 30
DEFAULT_VRF = 'default'
PATTERN_SEPARATOR = '|'


def extract_route_pattern(route_pattern):
    """Extract vrf and prefix from route pattern, route pattrn shall be formated like: "Vrf_1:1.1.1.1/24"
       or "1.1.1.1/24"

    Args:
        route_pattern (str): route pattern string
        sep (str, optional): Defaults to PATTERN_SEPARATOR.

    Returns:
        [tuple]: vrf and prefix
    """
    if isinstance(route_pattern, tuple):
        return route_pattern
    items = route_pattern.split(PATTERN_SEPARATOR)
    if len(items) == 1:
        return DEFAULT_VRF, items[0]
    elif len(items) == 2:
        return items[0], items[1]
    else:
        return None, None


def build_route_pattern(vrf, prefix):
    if vrf and vrf != 'default':
        return '{}{}{}'.format(vrf, PATTERN_SEPARATOR, prefix)
    else:
        return prefix


def get_route_flow_counter_capability():
    state_db = SonicV2Connector(host="127.0.0.1")
    state_db.connect(state_db.STATE_DB)

    return state_db.get_all(state_db.STATE_DB, '{}|{}'.format(FLOW_COUNTER_CAPABILITY_TABLE, FLOW_COUNTER_CAPABILITY_KEY))


def exit_if_route_flow_counter_not_support():
    capabilities = get_route_flow_counter_capability()
    if not capabilities:
        print('Waiting for swss to initialize route flow counter capability, please try again later')
        exit(1)

    support = capabilities.get(FLOW_COUNTER_CAPABILITY_SUPPORT_FIELD)
    if support is None:
        print('Waiting for swss to initialize route flow counter capability, please try again later')
        exit(1)

    if support != 'true':
        print('Route flow counter is not supported on this platform')
        exit(1)

    return

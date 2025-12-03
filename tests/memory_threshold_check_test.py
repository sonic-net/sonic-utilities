import os
import sys
import pytest
from unittest import mock
from .mock_tables import dbconnector
from utilities_common.general import load_module_from_source

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, 'scripts')
sys.path.insert(0, scripts_path)

memory_threshold_check_path = os.path.join(scripts_path, 'memory_threshold_check.py')
memory_threshold_check = load_module_from_source('memory_threshold_check.py', memory_threshold_check_path)

@pytest.fixture()
def setup_dbs_regular_mem_usage():
    cfg_db = dbconnector.dedicated_dbs.get('CONFIG_DB')
    state_db = dbconnector.dedicated_dbs.get('STATE_DB')
    dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(test_path, 'memory_threshold_check', 'config_db')
    dbconnector.dedicated_dbs['STATE_DB'] = os.path.join(test_path, 'memory_threshold_check', 'state_db')
    yield
    dbconnector.dedicated_dbs['CONFIG_DB'] = cfg_db
    dbconnector.dedicated_dbs['STATE_DB'] = state_db


@pytest.fixture()
def setup_dbs_telemetry_high_mem_usage():
    memory_threshold_check.MemoryStats.get_sys_memory_stats = mock.Mock(return_value={'MemAvailable': 10000000, 'MemTotal': 20000000})
    cfg_db = dbconnector.dedicated_dbs.get('CONFIG_DB')
    state_db = dbconnector.dedicated_dbs.get('STATE_DB')
    dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(test_path, 'memory_threshold_check', 'config_db')
    dbconnector.dedicated_dbs['STATE_DB'] = os.path.join(test_path, 'memory_threshold_check', 'state_db_2')
    yield
    dbconnector.dedicated_dbs['CONFIG_DB'] = cfg_db
    dbconnector.dedicated_dbs['STATE_DB'] = state_db


@pytest.fixture()
def setup_dbs_swss_high_mem_usage():
    memory_threshold_check.MemoryStats.get_sys_memory_stats = mock.Mock(return_value={'MemAvailable': 10000000, 'MemTotal': 20000000})
    cfg_db = dbconnector.dedicated_dbs.get('CONFIG_DB')
    state_db = dbconnector.dedicated_dbs.get('STATE_DB')
    dbconnector.dedicated_dbs['CONFIG_DB'] = os.path.join(test_path, 'memory_threshold_check', 'config_db')
    dbconnector.dedicated_dbs['STATE_DB'] = os.path.join(test_path, 'memory_threshold_check', 'state_db_3')
    yield
    dbconnector.dedicated_dbs['CONFIG_DB'] = cfg_db
    dbconnector.dedicated_dbs['STATE_DB'] = state_db


def test_memory_check_host_not_crossed(setup_dbs_regular_mem_usage):
    memory_threshold_check.MemoryStats.get_sys_memory_stats = mock.Mock(return_value={'MemAvailable': 1000000, 'MemTotal': 2000000})
    assert memory_threshold_check.main() == (memory_threshold_check.EXIT_SUCCESS, '')


def test_memory_check_host_less_then_min_required(setup_dbs_regular_mem_usage):
    memory_threshold_check.MemoryStats.get_sys_memory_stats = mock.Mock(return_value={'MemAvailable': 1000, 'MemTotal': 2000000})
    assert memory_threshold_check.main() == (memory_threshold_check.EXIT_THRESHOLD_CROSSED, '')


def test_memory_check_host_threshold_crossed(setup_dbs_regular_mem_usage):
    memory_threshold_check.MemoryStats.get_sys_memory_stats = mock.Mock(return_value={'MemAvailable': 2000000, 'MemTotal': 20000000})
    assert memory_threshold_check.main() == (memory_threshold_check.EXIT_THRESHOLD_CROSSED, '')


def test_memory_check_telemetry_threshold_crossed(setup_dbs_telemetry_high_mem_usage):
    assert memory_threshold_check.main() == (memory_threshold_check.EXIT_THRESHOLD_CROSSED, 'telemetry')


def test_memory_check_swss_threshold_crossed(setup_dbs_swss_high_mem_usage):
    assert memory_threshold_check.main() == (memory_threshold_check.EXIT_THRESHOLD_CROSSED, 'swss')

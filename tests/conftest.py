import importlib
import json
import os
import re
import shutil
import sys
import unittest
from unittest import mock

import pytest
from sonic_py_common import device_info, multi_asic
from swsscommon.swsscommon import ConfigDBConnector

from .mock_tables import dbconnector
from . import show_ip_route_common

from .bgp_commands_input.bgp_neighbor_test_vector import(
    mock_show_bgp_neighbor_single_asic,
    mock_show_bgp_neighbor_multi_asic,
    )
from .bgp_commands_input.bgp_network_test_vector import (
    mock_show_bgp_network_single_asic,
    mock_show_bgp_network_multi_asic
    )
from . import config_int_ip_common
import utilities_common.constants as constants
import config.main as config
import show.main  # noqa: F401, E402 — import early so mock tables load with UUT="2"

unittest.TestCase.maxDiff = None

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)

# ---------------------------------------------------------------------------
# pytest-xdist parallelization support
# ---------------------------------------------------------------------------
# Serial test file list and pytest_collection_modifyitems hook are in the
# root-level conftest.py (next to pytest.ini) to ensure they run before
# xdist schedules tests to workers.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True, scope='session')
def setup_db_config():
    """Initialize mock DB config once per xdist worker process."""
    from swsssdk import SonicDBConfig as _PyDBConfig
    from swsscommon.swsscommon import SonicDBConfig as _CppDBConfig

    from .mock_tables import mock_single_asic  # noqa: F401
    dbconnector.load_database_config()

    # Also load global DB config so that SonicDBConfig.namespace_validation()
    # does not raise "Load the global DB config first" when tests create
    # SonicV2Connector instances.
    mock_tables_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'mock_tables')
    _PyDBConfig.load_sonic_global_db_config(
        global_db_file_path=os.path.join(mock_tables_dir, 'database_global.json'))

    # Initialize the C++ swsscommon.SonicDBConfig as well.
    db_config_path = os.path.join(mock_tables_dir, 'database_config.json')
    global_db_config_path = os.path.join(mock_tables_dir, 'database_global.json')
    if not _CppDBConfig.isInit():
        _CppDBConfig.load_sonic_db_config(db_config_path)
    if not _CppDBConfig.isGlobalInit():
        _CppDBConfig.load_sonic_global_db_config(global_db_config_path)

    # Give each xdist worker its own directory tree to prevent
    # cross-worker contamination.  Everything worker-specific lives
    # under a single root: /tmp/worker-<id>/.
    worker_id = os.environ.get('PYTEST_XDIST_WORKER', 'master')
    worker_root = f'/tmp/worker-{worker_id}'
    if os.path.exists(worker_root):
        shutil.rmtree(worker_root)
    os.makedirs(worker_root)

    # Per-worker cache dir for stat script cache files (intfstat, etc.)
    worker_cache_dir = os.path.join(worker_root, 'cache')
    os.makedirs(worker_cache_dir)
    os.environ['SONIC_CLI_CACHE_DIR'] = worker_cache_dir

    # Per-worker copy of mock_tables so tests that overwrite shared
    # JSON files (e.g. portstat_test replaces counters_db.json) only
    # affect their own worker's sandbox.
    worker_mock_tables = os.path.join(worker_root, 'mock_tables')
    shutil.copytree(dbconnector.INPUT_DIR, worker_mock_tables)
    dbconnector.INPUT_DIR = worker_mock_tables
    os.environ['MOCK_TABLES_DIR'] = worker_mock_tables

    # Per-worker scratch dir for test scripts that write temp files
    # (e.g. mmuconfig).  Tests should use WORKER_TMP for any /tmp/
    # file that could race across workers.
    os.environ['WORKER_TMP'] = worker_root

    yield

    if os.path.exists(worker_root):
        shutil.rmtree(worker_root, ignore_errors=True)
    os.environ.pop('MOCK_TABLES_DIR', None)
    os.environ.pop('WORKER_TMP', None)


_last_seen_file = None
_original_path = None
_scripts_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """Reset global state when transitioning between test files.

    Ensures every test file starts from a clean single-asic baseline,
    regardless of what the previous file left behind.  This makes tests
    independent of execution order and safe under any xdist worker count
    (including -n 1).

    Only resets on FILE transitions, not class transitions within the same
    file.  Intra-file class setup (setup_class) is responsible for
    configuring its own state from the file-level baseline.  Module-scoped
    fixtures span the whole file and must not be disrupted mid-file.

    tryfirst=True ensures this runs BEFORE the default setup hook which
    triggers setup_class, so the reset happens before the next file's
    setup_class configures its own state.
    """
    global _last_seen_file
    current_file = str(item.fspath)

    if current_file != _last_seen_file:
        _reset_between_files()

    _last_seen_file = current_file


def _reset_between_files():
    """Reset global state to single-asic defaults between test files.

    This must undo ALL side-effects that any test file can leave behind,
    including module reloads, env var changes, and mock patches.
    """
    from sonic_py_common import multi_asic
    from utilities_common import multi_asic as multi_asic_util

    # Reset PATH to baseline + scripts directory
    global _original_path
    if _original_path is None:
        _original_path = os.environ.get("PATH", "")
    os.environ["PATH"] = _original_path + os.pathsep + _scripts_path

    # Reset mutable mock DB state
    dbconnector.dedicated_dbs.clear()
    dbconnector.topo = None

    # Reset environment variables that tests may have set
    os.environ['UTILITIES_UNIT_TESTING'] = "2"
    os.environ['UTILITIES_UNIT_TESTING_TOPOLOGY'] = ""
    os.environ.pop('UTILITIES_UNIT_TESTING_IS_SUP', None)
    os.environ.pop('SONIC_CLI_IFACE_MODE', None)
    os.environ.pop('FDBSHOW_UNIT_TESTING', None)
    os.environ.pop('WATERMARKSTAT_UNIT_TESTING', None)
    os.environ.pop('VOQ_DROP_COUNTER_TESTING', None)
    os.environ.pop('UTILITIES_UNIT_TESTING_VOQ', None)
    os.environ.pop('UTILITIES_UNIT_TESTING_DROPSTAT_CLEAN_CACHE', None)
    os.environ.pop('FIBSHOW_MOCK', None)

    # Clean up any dedicated_dbs env vars set for subprocess support
    for env_key in [k for k in os.environ if k.startswith('MOCK_DEDICATED_DB_')]:
        del os.environ[env_key]

    # Reset config.main module-level state that tests may mutate
    config.ADHOC_VALIDATION = True
    config.asic_type = None

    # Restore CliRunner.invoke if a test replaced it (e.g. vlan_test.py)
    from click.testing import CliRunner as _CliRunner
    import click.testing as _click_testing
    _orig_invoke = _click_testing.__dict__.get('_original_CliRunner_invoke')
    if _orig_invoke is None:
        # First call — save the real invoke for future resets
        _click_testing._original_CliRunner_invoke = _CliRunner.invoke
    elif _CliRunner.invoke is not _orig_invoke:
        _CliRunner.invoke = _orig_invoke

    # Clear per-worker cache files left by stat utilities (intfstat,
    # srv6stat, queuestat, etc.).  Without this, counter cache from one
    # test file leaks into the next file on the same worker.
    worker_cache_dir = os.environ.get('SONIC_CLI_CACHE_DIR', '')
    if worker_cache_dir and os.path.isdir(worker_cache_dir):
        for entry in os.listdir(worker_cache_dir):
            entry_path = os.path.join(worker_cache_dir, entry)
            if os.path.isdir(entry_path):
                shutil.rmtree(entry_path, ignore_errors=True)
            else:
                try:
                    os.remove(entry_path)
                except OSError:
                    pass

    # Restore single-asic mock patches (same as mock_single_asic.py)
    multi_asic.is_multi_asic = lambda: False
    multi_asic.get_num_asics = lambda: 1
    multi_asic.get_namespace_list = lambda namespace=None: ['']
    multi_asic.get_all_namespaces = lambda: {'front_ns': [], 'back_ns': [], 'fabric_ns': []}
    multi_asic_util.multi_asic_get_ip_intf_from_ns = lambda ns: []
    multi_asic_util.multi_asic_get_ip_intf_addr_from_ns = lambda ns, iface: []
    multi_asic.get_namespaces_from_linux = lambda namespace=None: ['']

    # Reload config.main so Click decorators re-evaluate
    # multi_asic.is_multi_asic() with restored single-asic state.
    # Without this, commands like 'config route' and 'config subinterface'
    # keep required=True on --namespace from a prior multi-asic file.
    importlib.reload(sys.modules['config.main'])

    # Restore DB config to single-asic
    dbconnector.load_database_config()

    # Restore global DB config flag that clean_up_config() clears
    from swsssdk import SonicDBConfig as _PyDBConfig
    mock_tables_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'mock_tables')
    if not _PyDBConfig._sonic_db_global_config_init:
        _PyDBConfig.load_sonic_global_db_config(
            global_db_file_path=os.path.join(mock_tables_dir, 'database_global.json'))

    # Restore C++ SonicDBConfig to single-asic mock paths.
    # Always reset and reload so that multi-asic C++ config from a
    # previous file is replaced with single-asic defaults.
    from swsscommon.swsscommon import SonicDBConfig as _CppDBConfig
    db_config_path = os.path.join(mock_tables_dir, 'database_config.json')
    global_db_config_path = os.path.join(mock_tables_dir, 'database_global.json')
    _CppDBConfig.reset()
    _CppDBConfig.load_sonic_db_config(db_config_path)
    _CppDBConfig.load_sonic_global_db_config(global_db_config_path)


generated_services_list = [
    'warmboot-finalizer.service',
    'watchdog-control.service',
    'rsyslog-config.service',
    'interfaces-config.service',
    'hostcfgd.service',
    'hostname-config.service',
    'topology.service',
    'updategraph.service',
    'config-setup.service',
    'caclmgrd.service',
    'procdockerstatsd.service',
    'pcie-check.service',
    'process-reboot-cause.service',
    'dhcp_relay.service',
    'snmp.service',
    'sflow.service',
    'bgp.service',
    'telemetry.service',
    'swss.service',
    'database.service',
    'database.service',
    'lldp.service',
    'lldp.service',
    'pmon.service',
    'radv.service',
    'mgmt-framework.service',
    'nat.service',
    'teamd.service',
    'syncd.service',
    'snmp.timer',
    'telemetry.timer']

@pytest.fixture(autouse=True)
def setup_env():
    # This is needed because we call scripts from this module as a separate
    # process when running tests, and so the PYTHONPATH needs to be set
    # correctly for those scripts to run.
    if "PYTHONPATH" not in os.environ:
        os.environ["PYTHONPATH"] = os.getcwd()

@pytest.fixture
def get_cmd_module():
    import config.main as config
    import show.main as show

    return (config, show)

def set_mock_apis():
    import config.main as config
    cwd = os.path.dirname(os.path.realpath(__file__))
    config.asic_type = mock.MagicMock(return_value="broadcom")
    config._get_device_type = mock.MagicMock(return_value="ToRRouter")

@pytest.fixture
def setup_cbf_mock_apis():
    cwd = os.path.dirname(os.path.realpath(__file__))
    device_info.get_paths_to_platform_and_hwsku_dirs = mock.MagicMock(
        return_value=(
            os.path.join(cwd, "."), os.path.join(cwd, "cbf_config_input")
        )
    )
    device_info.get_sonic_version_file = mock.MagicMock(
        return_value=os.path.join(cwd, "qos_config_input/sonic_version.yml")
    )

@pytest.fixture
def setup_qos_mock_apis():
    cwd = os.path.dirname(os.path.realpath(__file__))
    device_info.get_paths_to_platform_and_hwsku_dirs = mock.MagicMock(
        return_value=(
            os.path.join(cwd, "."), os.path.join(cwd, "qos_config_input")
        )
    )
    device_info.get_sonic_version_file = mock.MagicMock(
        return_value=os.path.join(cwd, "qos_config_input/sonic_version.yml")
    )

@pytest.fixture
def setup_single_broadcom_asic():
    import config.main as config
    import show.main as show

    set_mock_apis()
    device_info.get_num_npus = mock.MagicMock(return_value=1)
    config._get_sonic_generated_services = \
        mock.MagicMock(return_value=(generated_services_list, []))


@pytest.fixture
def setup_multi_broadcom_masic():
    import config.main as config
    import show.main as show

    set_mock_apis()
    device_info.get_num_npus = mock.MagicMock(return_value=2)
    multi_asic.get_num_asics = mock.MagicMock(return_value=2)
    multi_asic.is_multi_asic= mock.MagicMock(return_value=True)

    yield

    device_info.get_num_npus = mock.MagicMock(return_value=1)
    multi_asic.get_num_asics = mock.MagicMock(return_value=1)
    multi_asic.is_multi_asic= mock.MagicMock(return_value=False)


@pytest.fixture
def setup_single_bgp_instance_chassis(request):
    import utilities_common.bgp_util as bgp_util

    def mock_show_bgp_summary(
        vtysh_cmd, bgp_namespace, vtysh_shell_cmd=constants.RVTYSH_COMMAND
    ):
        if os.path.isfile(bgp_mocked_json):
            with open(bgp_mocked_json) as json_data:
                mock_frr_data = json_data.read()
            return mock_frr_data
        return ""

    if request.param == 'v4':
        bgp_mocked_json = os.path.join(
            test_path, 'mock_tables', 'ipv4_bgp_summary_chassis.json')
    elif request.param == 'v6':
        bgp_mocked_json = os.path.join(
            test_path, 'mock_tables', 'ipv6_bgp_summary_chassis.json')

    _old_run_bgp_command = bgp_util.run_bgp_command
    bgp_util.run_bgp_command = mock.MagicMock(
        return_value=mock_show_bgp_summary("", ""))

    yield
    bgp_util.run_bgp_command = _old_run_bgp_command


@pytest.fixture
def setup_t1_topo():
    dbconnector.topo = "t1"
    yield
    dbconnector.topo = None


@pytest.fixture
def setup_single_bgp_instance(request):
    import utilities_common.bgp_util as bgp_util
    if request.param == 'v4':
        bgp_mocked_json = os.path.join(
            test_path, 'mock_tables', 'ipv4_bgp_summary.json')
    elif request.param == 'v4_dynamic':
        bgp_mocked_json = os.path.join(
            test_path, 'mock_tables', 'ipv4_bgp_summary_dynamic.json')
    elif request.param == 'v6_dynamic':
        bgp_mocked_json = os.path.join(
            test_path, 'mock_tables', 'ipv6_bgp_summary_dynamic.json')
    elif request.param == 'v4_vrf':
        bgp_mocked_json = os.path.join(
            test_path, 'mock_tables', 'ipv4_bgp_summary_vrf.json')
    elif request.param == 'v6':
        bgp_mocked_json = os.path.join(
            test_path, 'mock_tables', 'ipv6_bgp_summary.json')
    elif request.param == 'v6_vrf':
        bgp_mocked_json = os.path.join(
            test_path, 'mock_tables', 'ipv6_bgp_summary_vrf.json')
    elif request.param == 'show_bgp_summary_no_neigh':
        bgp_neigh_mocked_json = os.path.join(
            test_path, 'mock_tables', 'no_bgp_neigh.json')
        bgp_mocked_json = os.path.join(
            test_path, 'mock_tables', 'device_bgp_info.json')
    elif request.param == 'show_run_bgp':
        bgp_mocked_json = os.path.join(
            test_path, 'mock_tables', 'show_run_bgp.txt')
    elif request.param == 'ip_route':
        bgp_mocked_json = 'ip_route.json'
    elif request.param == 'ip_specific_route': 
        bgp_mocked_json = 'ip_specific_route.json'    
    elif request.param == 'ipv6_specific_route':
        bgp_mocked_json = 'ipv6_specific_route.json'
    elif request.param == 'ipv6_route':
        bgp_mocked_json = 'ipv6_route.json'
    elif request.param == 'ip_special_route':
        bgp_mocked_json = 'ip_special_route.json'
    elif request.param == 'ip_route_lc':
        bgp_mocked_json = 'ip_route_lc.json'
    elif request.param == 'ip_route_remote_lc':
        bgp_mocked_json = 'ip_route_remote_lc.json'
    else:
        bgp_mocked_json = os.path.join(
            test_path, 'mock_tables', 'dummy.json')

    def mock_run_bgp_command(mock_bgp_file):
        if os.path.isfile(mock_bgp_file):
            with open(mock_bgp_file) as json_data:
                mock_frr_data = json_data.read()
            return mock_frr_data
        return ""

    def mock_show_run_bgp(request):
        if os.path.isfile(bgp_mocked_json):
            with open(bgp_mocked_json) as json_data:
                mock_frr_data = json_data.read()
            return mock_frr_data
        return ""

    def mock_run_bgp_command_for_static(vtysh_cmd, bgp_namespace=[], vtysh_shell_cmd=constants.RVTYSH_COMMAND):
        if vtysh_cmd == "show ip route vrf all static":
            return config_int_ip_common.show_ip_route_with_static_expected_output
        elif vtysh_cmd == "show ipv6 route vrf all static":
            return config_int_ip_common.show_ipv6_route_with_static_expected_output
        else:
            return ""

    def mock_run_show_ip_route_commands(request):
        if request.param == 'ipv6_route_err':
            return show_ip_route_common.show_ipv6_route_err_expected_output
        else:
            return ""

    def mock_run_bgp_route_command(vtysh_cmd, bgp_namespace, vtysh_shell_cmd=constants.RVTYSH_COMMAND):
        bgp_mocked_json_file = os.path.join(
            test_path, 'mock_tables', bgp_mocked_json)
        if os.path.isfile(bgp_mocked_json_file):
            with open(bgp_mocked_json_file) as json_data:
                mock_frr_data = json_data.read()
            return mock_frr_data
        else:
            return ""

    _old_run_bgp_command = bgp_util.run_bgp_command
    if any([request.param == 'ip_route',
            request.param == 'ip_specific_route', request.param == 'ip_special_route',
            request.param == 'ipv6_route', request.param == 'ipv6_specific_route',
            request.param == 'ip_route_lc', request.param == 'ip_route_remote_lc']):
        bgp_util.run_bgp_command = mock.MagicMock(
            return_value=mock_run_bgp_route_command("", ""))
    elif request.param.startswith('ipv6_route_err'):
        bgp_util.run_bgp_command = mock.MagicMock(
            return_value=mock_run_show_ip_route_commands(request))
    elif request.param.startswith('bgp_v4_neighbor') or \
            request.param.startswith('bgp_v6_neighbor'):
        bgp_util.run_bgp_command = mock.MagicMock(
            return_value=mock_show_bgp_neighbor_single_asic(request))
    elif request.param.startswith('bgp_v4_network') or \
            request.param.startswith('bgp_v6_network'):
        bgp_util.run_bgp_command = mock.MagicMock(
            return_value=mock_show_bgp_network_single_asic(request))
    elif request.param == 'ip_route_for_int_ip':
        bgp_util.run_bgp_command = mock_run_bgp_command_for_static
    elif request.param.startswith('show_run_bgp'):
        bgp_util.run_bgp_command = mock.MagicMock(
            return_value=mock_show_run_bgp(request))
    elif request.param == 'show_bgp_summary_no_neigh':
        functions_to_call = [mock_run_bgp_command(bgp_neigh_mocked_json), mock_run_bgp_command(bgp_mocked_json)]
        bgp_util.run_bgp_command = mock.MagicMock(
            side_effect=functions_to_call)
    else:
        bgp_util.run_bgp_command = mock.MagicMock(
            return_value=mock_run_bgp_command(bgp_mocked_json))

    yield

    bgp_util.run_bgp_command = _old_run_bgp_command


@pytest.fixture
def setup_multi_asic_bgp_instance(request):
    import utilities_common.bgp_util as bgp_util

    if request.param == 'ip_route':
        m_asic_json_file = 'ip_route.json'
    elif request.param == 'ip_specific_route':
        m_asic_json_file = 'ip_specific_route.json'
    elif request.param == 'ipv6_specific_route':
        m_asic_json_file = 'ipv6_specific_route.json'
    elif request.param == 'ipv6_route':
        m_asic_json_file = 'ipv6_route.json'
    elif request.param == 'ip_special_route':
        m_asic_json_file = 'ip_special_route.json'
    elif request.param == 'ip_empty_route':
        m_asic_json_file = 'ip_empty_route.json'
    elif request.param == 'ip_specific_route_on_1_asic':
        m_asic_json_file = 'ip_special_route_asic0_only.json'
    elif request.param == 'ip_specific_recursive_route':
        m_asic_json_file = 'ip_special_recursive_route.json'
    elif request.param == 'ip_route_summary':
        m_asic_json_file = 'ip_route_summary.txt'
    elif request.param == 'show_run_bgp':
        m_asic_json_file = 'show_run_bgp.txt'
    elif request.param == 'show_not_running_bgp':
        m_asic_json_file = 'show_not_running_bgp.txt'
    elif request.param.startswith('bgp_v4_network') or \
        request.param.startswith('bgp_v6_network') or \
        request.param.startswith('bgp_v4_neighbor') or \
        request.param.startswith('bgp_v6_neighbor'):
        m_asic_json_file = request.param
    elif request.param == 'ip_route_lc':
        m_asic_json_file = 'ip_route_lc.json'
    elif request.param == 'ip_route_remote_lc':
        m_asic_json_file = 'ip_route_remote_lc.json'
    elif request.param == 'ip_route_lc_2':
        m_asic_json_file = 'ip_route_lc_2.json'
    else:
        m_asic_json_file = os.path.join(
            test_path, 'mock_tables', 'dummy.json')

    def mock_run_bgp_command_for_static(vtysh_cmd, bgp_namespace="", vtysh_shell_cmd=constants.RVTYSH_COMMAND):
        if bgp_namespace != 'test_ns':
            return ""
        if vtysh_cmd == "show ip route vrf all static":
            return config_int_ip_common.show_ip_route_with_static_expected_output
        elif vtysh_cmd == "show ipv6 route vrf all static":
            return config_int_ip_common.show_ipv6_route_with_static_expected_output
        else:
            return ""

    def mock_run_bgp_command(vtysh_cmd, bgp_namespace, vtysh_shell_cmd=constants.RVTYSH_COMMAND, exit_on_fail=True):
        if m_asic_json_file.startswith('bgp_v4_network') or \
            m_asic_json_file.startswith('bgp_v6_network'):
            return mock_show_bgp_network_multi_asic(m_asic_json_file)

        if m_asic_json_file.startswith('bgp_v4_neighbor') or \
            m_asic_json_file.startswith('bgp_v6_neighbor'):
            return mock_show_bgp_neighbor_multi_asic(m_asic_json_file, bgp_namespace)

        bgp_mocked_json = os.path.join(
            test_path, 'mock_tables', bgp_namespace, m_asic_json_file)
        if os.path.isfile(bgp_mocked_json):
            with open(bgp_mocked_json) as json_data:
                mock_frr_data = json_data.read()
            return mock_frr_data
        else:
            return ""

    def mock_run_show_sum_bgp_command(
            vtysh_cmd, bgp_namespace, vtysh_shell_cmd=constants.VTYSH_COMMAND, exit_on_fail=True):
        if vtysh_cmd == "show ip bgp summary json":
            m_asic_json_file = 'no_bgp_neigh.json'
        else:
            m_asic_json_file = 'device_bgp_info.json'

        bgp_mocked_json = os.path.join(
            test_path, 'mock_tables', bgp_namespace, m_asic_json_file)
        if os.path.isfile(bgp_mocked_json):
            with open(bgp_mocked_json) as json_data:
                mock_frr_data = json_data.read()
            return mock_frr_data
        else:
            return ""

    def mock_run_show_summ_bgp_command_no_ext_neigh_on_all_asic(
            vtysh_cmd, bgp_namespace, vtysh_shell_cmd=constants.VTYSH_COMMAND, exit_on_fail=True):
        if vtysh_cmd == "show ip bgp summary json" or vtysh_cmd == "show ip bgp vrf default summary json":
            m_asic_json_file = 'no_ext_bgp_neigh.json'
        else:
            m_asic_json_file = 'device_bgp_info.json'
        
        bgp_mocked_json = os.path.join(
            test_path, 'mock_tables', bgp_namespace, m_asic_json_file)
        if os.path.isfile(bgp_mocked_json):
            with open(bgp_mocked_json) as json_data:
                mock_frr_data = json_data.read()
            return mock_frr_data
        else:
            return ""

    def mock_run_show_summ_bgp_command_no_ext_neigh_on_asic1(
            vtysh_cmd, bgp_namespace, vtysh_shell_cmd=constants.VTYSH_COMMAND, exit_on_fail=True):
        if vtysh_cmd == "show ip bgp summary json" or vtysh_cmd == "show ip bgp vrf default summary json":
            if bgp_namespace == "asic1":
                m_asic_json_file = 'no_ext_bgp_neigh.json'
            else:
                m_asic_json_file = 'show_ip_bgp_summary.json'
        else:
            m_asic_json_file = 'device_bgp_info.json'

        bgp_mocked_json = os.path.join(
            test_path, 'mock_tables', bgp_namespace, m_asic_json_file)
        if os.path.isfile(bgp_mocked_json):
            with open(bgp_mocked_json) as json_data:
                mock_frr_data = json_data.read()
            return mock_frr_data
        else:
            return ""

    def mock_multi_asic_list():
        return ["asic0", "asic1"]

    # mock multi-asic list
    if request.param == "bgp_v4_network_all_asic":
        multi_asic.get_namespace_list = mock_multi_asic_list

    _old_run_bgp_command = bgp_util.run_bgp_command
    if request.param == 'ip_route_for_int_ip':
        bgp_util.run_bgp_command = mock_run_bgp_command_for_static
    elif request.param == 'show_bgp_summary_no_neigh':
        bgp_util.run_bgp_command = mock_run_show_sum_bgp_command
    elif request.param == 'show_bgp_summary_no_ext_neigh_on_all_asic':
        bgp_util.run_bgp_command = mock_run_show_summ_bgp_command_no_ext_neigh_on_all_asic
    elif request.param == 'show_bgp_summary_no_ext_neigh_on_asic1':
        bgp_util.run_bgp_command = mock_run_show_summ_bgp_command_no_ext_neigh_on_asic1
    else:
        bgp_util.run_bgp_command = mock_run_bgp_command

    yield

    bgp_util.run_bgp_command = _old_run_bgp_command

@pytest.fixture
def setup_bgp_commands():
    import show.main as show
    from show.bgp_frr_v4 import bgp as bgpv4
    from show.bgp_frr_v6 import bgp as bgpv6

    show.ip.add_command(bgpv4)
    show.ipv6.add_command(bgpv6)
    return show


@pytest.fixture
def setup_ip_route_commands():
    import show.main as show
    return show


@pytest.fixture
def setup_fib_commands():
    import show.main as show
    return show


@pytest.fixture(scope='function')
def mock_restart_dhcp_relay_service():
    print("We are mocking restart dhcp_relay")
    origin_funcs = []
    origin_funcs.append(config.vlan.dhcp_relay_util.restart_dhcp_relay_service)
    origin_funcs.append(config.vlan.is_dhcp_relay_running)
    config.vlan.dhcp_relay_util.restart_dhcp_relay_service = mock.MagicMock(return_value=0)
    config.vlan.is_dhcp_relay_running = mock.MagicMock(return_value=True)

    yield

    config.vlan.dhcp_relay_util.restart_dhcp_relay_service = origin_funcs[0]
    config.vlan.is_dhcp_relay_running = origin_funcs[1]


@pytest.fixture(scope='class')
def setup_multi_asic_env():
    """Set up multi-asic environment for testing.

    This fixture:
    1. Sets environment variables for multi-asic mode
    2. Loads multi-asic mock patches via mock_multi_asic module
    3. Reloads dependent modules to pick up patched functions
    4. Restores single-asic state on teardown
    """
    # Set environment variables
    os.environ['UTILITIES_UNIT_TESTING'] = "2"
    os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"

    # Import and reload to apply multi-asic patches
    from .mock_tables import mock_multi_asic
    importlib.reload(mock_multi_asic)

    dbconnector.load_namespace_config()

    # Reload dependent modules to pick up patched functions
    importlib.reload(sys.modules['utilities_common.multi_asic'])
    importlib.reload(sys.modules['config.main'])

    yield

    # Restore single-asic state
    from .mock_tables import mock_single_asic
    importlib.reload(mock_single_asic)

    dbconnector.load_database_config()

    # Reload modules to pick up restored single-asic state
    importlib.reload(sys.modules['utilities_common.multi_asic'])
    importlib.reload(sys.modules['config.main'])

    # Reset environment
    os.environ['UTILITIES_UNIT_TESTING'] = "0"
    os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""


@pytest.fixture(scope='class')
def setup_env_paths(request):
    """Add directories to PATH environment variable for subprocess-based tests.

    This fixture reads 'env_paths' from the test class, which should be a list
    of paths to add to the PATH environment variable.

    Usage:
        @pytest.mark.usefixtures("setup_env_paths")
        class TestSomething:
            env_paths = [scripts_path, other_path]  # List of paths to add
    """
    paths_to_add = getattr(request.cls, 'env_paths', None)
    if paths_to_add is None:
        yield
        return

    # Ensure paths_to_add is a list
    if isinstance(paths_to_add, str):
        paths_to_add = [paths_to_add]

    original_path = os.environ.get("PATH", "")

    for path in paths_to_add:
        os.environ["PATH"] += os.pathsep + path

    yield

    os.environ["PATH"] = original_path

import sys
import os
import json
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest import mock

import click
from click.testing import CliRunner
from .mock_tables import dbconnector

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, modules_path)

class MockerConfig(object):
    ignore_devices = []
    ignore_services = []
    first_time = True

    def config_file_exists(self):
        if MockerConfig.first_time:
            MockerConfig.first_time = False
            return False
        else:
            return True

class MockerManager(object):
    counter = 0

    def __init__(self):
        self.config = MockerConfig()

    def check(self):
        if MockerManager.counter == 0:
            stats = {'Services': {'neighsyncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'vrfmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'telemetry': {'status': 'Not OK', 'message': 'telemetry is not Running', 'type': 'Process'}, 'dialout_client': {'status': 'OK', 'message': '', 'type': 'Process'}, 'zebra': {'status': 'OK', 'message': '', 'type': 'Process'}, 'rsyslog': {'status': 'OK', 'message': '', 'type': 'Process'}, 'snmpd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'redis_server': {'status': 'OK', 'message': '', 'type': 'Process'}, 'intfmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'orchagent': {'status': 'OK', 'message': '', 'type': 'Process'}, 'vxlanmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'lldpd_monitor': {'status': 'OK', 'message': '', 'type': 'Process'}, 'portsyncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'var-log': {'status': 'OK', 'message': '', 'type': 'Filesystem'}, 'lldpmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'syncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'sonic': {'status': 'OK', 'message': '', 'type': 'System'}, 'buffermgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'portmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'staticd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'bgpd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'lldp_syncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'bgpcfgd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'snmp_subagent': {'status': 'Not OK', 'message': 'snmp_subagent is not Running', 'type': 'Process'}, 'root-overlay': {'status': 'OK', 'message': '', 'type': 'Filesystem'}, 'fpmsyncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'sflowmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'vlanmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'nbrmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}}, 'Hardware': {'psu_1_fan_1': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'psu_2_fan_1': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'PSU 1': {'status': 'OK', 'message': '', 'type': 'PSU'}, 'fan10': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'PSU 2': {'status': 'OK', 'message': '', 'type': 'PSU'}, 'ASIC': {'status': 'OK', 'message': '', 'type': 'ASIC'}, 'fan1': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan3': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan2': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan5': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan4': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan7': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan6': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan9': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan8': {'status': 'OK', 'message': '', 'type': 'Fan'}}}
        elif MockerManager.counter == 1:
            stats = {'Services': {'neighsyncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'vrfmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'telemetry': {'status': 'OK', 'message': '', 'type': 'Process'}, 'dialout_client': {'status': 'OK', 'message': '', 'type': 'Process'}, 'zebra': {'status': 'OK', 'message': '', 'type': 'Process'}, 'rsyslog': {'status': 'OK', 'message': '', 'type': 'Process'}, 'snmpd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'redis_server': {'status': 'OK', 'message': '', 'type': 'Process'}, 'intfmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'orchagent': {'status': 'OK', 'message': '', 'type': 'Process'}, 'vxlanmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'lldpd_monitor': {'status': 'OK', 'message': '', 'type': 'Process'}, 'portsyncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'var-log': {'status': 'OK', 'message': '', 'type': 'Filesystem'}, 'lldpmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'syncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'sonic': {'status': 'OK', 'message': '', 'type': 'System'}, 'buffermgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'portmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'staticd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'bgpd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'lldp_syncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'bgpcfgd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'snmp_subagent': {'status': 'OK', 'message': '', 'type': 'Process'}, 'root-overlay': {'status': 'OK', 'message': '', 'type': 'Filesystem'}, 'fpmsyncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'sflowmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'vlanmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'nbrmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}}, 'Hardware': {'psu_1_fan_1': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'psu_2_fan_1': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'PSU 1': {'status': 'OK', 'message': '', 'type': 'PSU'}, 'fan10': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'PSU 2': {'status': 'OK', 'message': '', 'type': 'PSU'}, 'ASIC': {'status': 'OK', 'message': '', 'type': 'ASIC'}, 'fan1': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan3': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan2': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan5': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan4': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan7': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan6': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan9': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan8': {'status': 'OK', 'message': '', 'type': 'Fan'}}}
        elif MockerManager.counter == 2:
            stats = {'Services': {'neighsyncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'vrfmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'telemetry': {'status': 'Not OK', 'message': 'telemetry is not Running', 'type': 'Process'}, 'dialout_client': {'status': 'OK', 'message': '', 'type': 'Process'}, 'zebra': {'status': 'OK', 'message': '', 'type': 'Process'}, 'rsyslog': {'status': 'OK', 'message': '', 'type': 'Process'}, 'snmpd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'redis_server': {'status': 'OK', 'message': '', 'type': 'Process'}, 'intfmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'orchagent': {'status': 'OK', 'message': '', 'type': 'Process'}, 'vxlanmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'lldpd_monitor': {'status': 'OK', 'message': '', 'type': 'Process'}, 'portsyncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'var-log': {'status': 'OK', 'message': '', 'type': 'Filesystem'}, 'lldpmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'syncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'sonic': {'status': 'OK', 'message': '', 'type': 'System'}, 'buffermgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'portmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'staticd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'bgpd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'lldp_syncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'bgpcfgd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'snmp_subagent': {'status': 'OK', 'message': '', 'type': 'Process'}, 'root-overlay': {'status': 'OK', 'message': '', 'type': 'Filesystem'}, 'fpmsyncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'sflowmgrd': {'status': 'Not OK', 'message': 'sflowmgrd is not Running', 'type': 'Process'}, 'vlanmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'nbrmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}}, 'Hardware': {'PSU 2': {'status': 'OK', 'message': '', 'type': 'PSU'}, 'psu_1_fan_1': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'psu_2_fan_1': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan11': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan10': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan12': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'ASIC': {'status': 'OK', 'message': '', 'type': 'ASIC'}, 'fan1': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'PSU 1': {'status': 'OK', 'message': '', 'type': 'PSU'}, 'fan3': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan2': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan5': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan4': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan7': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan6': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan9': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan8': {'status': 'OK', 'message': '', 'type': 'Fan'}}}
        elif MockerManager.counter == 3:
            stats = {'Services': {'neighsyncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'vrfmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'telemetry': {'status': 'Not OK', 'message': 'telemetry is not Running', 'type': 'Process'}, 'dialout_client': {'status': 'OK', 'message': '', 'type': 'Process'}, 'zebra': {'status': 'OK', 'message': '', 'type': 'Process'}, 'rsyslog': {'status': 'OK', 'message': '', 'type': 'Process'}, 'snmpd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'redis_server': {'status': 'OK', 'message': '', 'type': 'Process'}, 'intfmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'orchagent': {'status': 'OK', 'message': '', 'type': 'Process'}, 'vxlanmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'lldpd_monitor': {'status': 'OK', 'message': '', 'type': 'Process'}, 'portsyncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'var-log': {'status': 'OK', 'message': '', 'type': 'Filesystem'}, 'lldpmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'syncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'sonic': {'status': 'OK', 'message': '', 'type': 'System'}, 'buffermgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'portmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'staticd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'bgpd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'lldp_syncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'bgpcfgd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'snmp_subagent': {'status': 'OK', 'message': '', 'type': 'Process'}, 'root-overlay': {'status': 'OK', 'message': '', 'type': 'Filesystem'}, 'fpmsyncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'sflowmgrd': {'status': 'Not OK', 'message': 'sflowmgrd is not Running', 'type': 'Process'}, 'vlanmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'nbrmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}}, 'Hardware': {'PSU 2': {'status': 'Not OK', 'message': 'Failed to get voltage minimum threshold data for PSU 2', 'type': 'PSU'}, 'psu_1_fan_1': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'psu_2_fan_1': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan11': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan10': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan12': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'ASIC': {'status': 'OK', 'message': '', 'type': 'ASIC'}, 'fan1': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'PSU 1': {'status': 'Not OK', 'message': 'Failed to get voltage minimum threshold data for PSU 1', 'type': 'PSU'}, 'fan3': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan2': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan5': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan4': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan7': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan6': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan9': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan8': {'status': 'OK', 'message': '', 'type': 'Fan'}}}
        elif MockerManager.counter == 4:
            stats = {'Services': {'neighsyncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'vrfmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'telemetry': {'status': 'Not OK', 'message': 'telemetry is not Running', 'type': 'Process'}, 'dialout_client': {'status': 'OK', 'message': '', 'type': 'Process'}, 'zebra': {'status': 'OK', 'message': '', 'type': 'Process'}, 'rsyslog': {'status': 'OK', 'message': '', 'type': 'Process'}, 'snmpd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'redis_server': {'status': 'OK', 'message': '', 'type': 'Process'}, 'intfmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'orchagent': {'status': 'OK', 'message': '', 'type': 'Process'}, 'vxlanmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'lldpd_monitor': {'status': 'OK', 'message': '', 'type': 'Process'}, 'portsyncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'var-log': {'status': 'OK', 'message': '', 'type': 'Filesystem'}, 'lldpmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'syncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'sonic': {'status': 'OK', 'message': '', 'type': 'System'}, 'buffermgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'portmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'staticd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'bgpd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'lldp_syncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'bgpcfgd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'snmp_subagent': {'status': 'OK', 'message': '', 'type': 'Process'}, 'root-overlay': {'status': 'OK', 'message': '', 'type': 'Filesystem'}, 'fpmsyncd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'sflowmgrd': {'status': 'Not OK', 'message': 'sflowmgrd is not Running', 'type': 'Process'}, 'vlanmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}, 'nbrmgrd': {'status': 'OK', 'message': '', 'type': 'Process'}}, 'Hardware': {'PSU 2': {'status': 'OK', 'message': '', 'type': 'PSU'}, 'psu_1_fan_1': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'psu_2_fan_1': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan11': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan10': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan12': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'ASIC': {'status': 'OK', 'message': '', 'type': 'ASIC'}, 'fan1': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'PSU 1': {'status': 'OK', 'message': '', 'type': 'PSU'}, 'fan3': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan2': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan5': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan4': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan7': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan6': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan9': {'status': 'OK', 'message': '', 'type': 'Fan'}, 'fan8': {'status': 'OK', 'message': '', 'type': 'Fan'}}}
        else:
            stats = {}
        MockerManager.counter += 1

        return stats

class MockerChassis(object):
    counter = 0

    def get_status_led(self):
        if MockerChassis.counter == 1:
            MockerChassis.counter += 1
            return "green"
        else:
            MockerChassis.counter += 1
            return "red"


def mock_healthcheck():
    """Runs the mocked checks and returns their JSON as the check binary prints it."""
    if not MockerConfig().config_file_exists():
        return 1, '', 'System health configuration file not found, exit...'
    manager = MockerManager()
    stat = manager.check()
    output = {
        'led': MockerChassis().get_status_led(),
        'stat': stat,
        'ignore': {'services': manager.config.ignore_services, 'devices': manager.config.ignore_devices},
    }
    return 0, json.dumps(output), ''


@contextmanager
def modules_replaced(modules):
    """Puts the given entries in sys.modules and afterwards restores exactly those. mock.patch.dict would clear and
    refill the whole dict, dropping the modules first imported inside the block."""
    saved = {name: sys.modules[name] for name in modules if name in sys.modules}
    sys.modules.update(modules)
    try:
        yield
    finally:
        for name in modules:
            if name in saved:
                sys.modules[name] = saved[name]
            else:
                sys.modules.pop(name, None)

import show.main as show
real_run_healthcheck = show.system_health.run_healthcheck
real_healthcheck_installed = show.system_health.healthcheck_installed

class TestHealth(object):
    original_cli = None

    @classmethod
    def setup_class(cls):
        print("SETUP")
        # pop_all() keeps the patches only when all of them started; closing them also restores the environment.
        with ExitStack() as stack:
            stack.enter_context(mock.patch.dict(os.environ, {"UTILITIES_UNIT_TESTING": "1"}))
            stack.enter_context(mock.patch('show.system_health.healthcheck_installed', return_value=True))
            stack.enter_context(mock.patch('show.system_health.run_healthcheck', side_effect=mock_healthcheck))
            stack.enter_context(mock.patch('show.system_health.os.geteuid', return_value=0))
            cls.patches = stack.pop_all()
        global original_cli
        original_cli = show.cli

    def test_health_summary(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["system-health"].commands["summary"])
        click.echo(result.output)
        expected = """\
System health configuration file not found, exit...
"""
        assert result.output == expected
        result = runner.invoke(show.cli.commands["system-health"].commands["summary"])
        expected = """\
System status summary

  System status LED  red
  Services:
    Status: Not OK
    Not Running: telemetry, snmp_subagent
  Hardware:
    Status: OK
"""
        click.echo(result.output)
        assert result.output == expected
        result = runner.invoke(show.cli.commands["system-health"].commands["summary"])
        click.echo(result.output)
        expected = """\
System status summary

  System status LED  green
  Services:
    Status: OK
  Hardware:
    Status: OK
"""
        assert result.output == expected

    def test_health_monitor(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["system-health"].commands["monitor-list"])
        click.echo(result.output)
        expected = """
System services and devices monitor list

Name            Status    Type
--------------  --------  ----------
telemetry       Not OK    Process
sflowmgrd       Not OK    Process
neighsyncd      OK        Process
vrfmgrd         OK        Process
dialout_client  OK        Process
zebra           OK        Process
rsyslog         OK        Process
snmpd           OK        Process
redis_server    OK        Process
intfmgrd        OK        Process
orchagent       OK        Process
vxlanmgrd       OK        Process
lldpd_monitor   OK        Process
portsyncd       OK        Process
var-log         OK        Filesystem
lldpmgrd        OK        Process
syncd           OK        Process
sonic           OK        System
buffermgrd      OK        Process
portmgrd        OK        Process
staticd         OK        Process
bgpd            OK        Process
lldp_syncd      OK        Process
bgpcfgd         OK        Process
snmp_subagent   OK        Process
root-overlay    OK        Filesystem
fpmsyncd        OK        Process
vlanmgrd        OK        Process
nbrmgrd         OK        Process
PSU 2           OK        PSU
psu_1_fan_1     OK        Fan
psu_2_fan_1     OK        Fan
fan11           OK        Fan
fan10           OK        Fan
fan12           OK        Fan
ASIC            OK        ASIC
fan1            OK        Fan
PSU 1           OK        PSU
fan3            OK        Fan
fan2            OK        Fan
fan5            OK        Fan
fan4            OK        Fan
fan7            OK        Fan
fan6            OK        Fan
fan9            OK        Fan
fan8            OK        Fan
"""
        assert result.output == expected

    def test_health_detail(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["system-health"].commands["detail"])
        click.echo(result.output)
        expected = """\
System status summary

  System status LED  red
  Services:
    Status: Not OK
    Not Running: telemetry, sflowmgrd
  Hardware:
    Status: Not OK
    Reasons: Failed to get voltage minimum threshold data for PSU 1
	     Failed to get voltage minimum threshold data for PSU 2

System services and devices monitor list

Name            Status    Type
--------------  --------  ----------
telemetry       Not OK    Process
sflowmgrd       Not OK    Process
neighsyncd      OK        Process
vrfmgrd         OK        Process
dialout_client  OK        Process
zebra           OK        Process
rsyslog         OK        Process
snmpd           OK        Process
redis_server    OK        Process
intfmgrd        OK        Process
orchagent       OK        Process
vxlanmgrd       OK        Process
lldpd_monitor   OK        Process
portsyncd       OK        Process
var-log         OK        Filesystem
lldpmgrd        OK        Process
syncd           OK        Process
sonic           OK        System
buffermgrd      OK        Process
portmgrd        OK        Process
staticd         OK        Process
bgpd            OK        Process
lldp_syncd      OK        Process
bgpcfgd         OK        Process
snmp_subagent   OK        Process
root-overlay    OK        Filesystem
fpmsyncd        OK        Process
vlanmgrd        OK        Process
nbrmgrd         OK        Process
PSU 2           Not OK    PSU
PSU 1           Not OK    PSU
psu_1_fan_1     OK        Fan
psu_2_fan_1     OK        Fan
fan11           OK        Fan
fan10           OK        Fan
fan12           OK        Fan
ASIC            OK        ASIC
fan1            OK        Fan
fan3            OK        Fan
fan2            OK        Fan
fan5            OK        Fan
fan4            OK        Fan
fan7            OK        Fan
fan6            OK        Fan
fan9            OK        Fan
fan8            OK        Fan

System services and devices ignore list

Name    Status    Type
------  --------  ------
"""
        assert result.output == expected
        MockerConfig.ignore_devices.insert(0, "psu.voltage")
        result = runner.invoke(show.cli.commands["system-health"].commands["detail"])
        click.echo(result.output)
        expected = """\
System status summary

  System status LED  red
  Services:
    Status: Not OK
    Not Running: telemetry, sflowmgrd
  Hardware:
    Status: OK

System services and devices monitor list

Name            Status    Type
--------------  --------  ----------
telemetry       Not OK    Process
sflowmgrd       Not OK    Process
neighsyncd      OK        Process
vrfmgrd         OK        Process
dialout_client  OK        Process
zebra           OK        Process
rsyslog         OK        Process
snmpd           OK        Process
redis_server    OK        Process
intfmgrd        OK        Process
orchagent       OK        Process
vxlanmgrd       OK        Process
lldpd_monitor   OK        Process
portsyncd       OK        Process
var-log         OK        Filesystem
lldpmgrd        OK        Process
syncd           OK        Process
sonic           OK        System
buffermgrd      OK        Process
portmgrd        OK        Process
staticd         OK        Process
bgpd            OK        Process
lldp_syncd      OK        Process
bgpcfgd         OK        Process
snmp_subagent   OK        Process
root-overlay    OK        Filesystem
fpmsyncd        OK        Process
vlanmgrd        OK        Process
nbrmgrd         OK        Process
PSU 2           OK        PSU
psu_1_fan_1     OK        Fan
psu_2_fan_1     OK        Fan
fan11           OK        Fan
fan10           OK        Fan
fan12           OK        Fan
ASIC            OK        ASIC
fan1            OK        Fan
PSU 1           OK        PSU
fan3            OK        Fan
fan2            OK        Fan
fan5            OK        Fan
fan4            OK        Fan
fan7            OK        Fan
fan6            OK        Fan
fan9            OK        Fan
fan8            OK        Fan

System services and devices ignore list

Name         Status    Type
-----------  --------  ------
psu.voltage  Ignored   Device
"""
        assert result.output == expected

    def test_health_check_failure(self):
        runner = CliRunner()
        with mock.patch('show.system_health.run_healthcheck', return_value=(2, '', 'cannot connect to redis\n')):
            result = runner.invoke(show.cli.commands["system-health"].commands["summary"])
        assert result.exit_code == 1
        assert result.output == "System health check failed: cannot connect to redis (exit code 2)\n"

    def test_health_check_exit_code_1(self):
        """Exit code 1 with a message is the missing configuration file: the binary's own message is shown, as Python
        printed it. Without a message it is a failure like any other."""
        runner = CliRunner()
        with mock.patch('show.system_health.run_healthcheck', return_value=(1, '', 'Another reason to stop\n')):
            result = runner.invoke(show.cli.commands["system-health"].commands["summary"])
        assert result.exit_code == 1
        assert result.output == "Another reason to stop\n"
        with mock.patch('show.system_health.run_healthcheck', return_value=(1, '', '')):
            result = runner.invoke(show.cli.commands["system-health"].commands["summary"])
        assert result.exit_code == 1
        assert result.output == "System health check failed: exit code 1\n"

    def test_health_check_failure_without_stderr(self):
        runner = CliRunner()
        with mock.patch('show.system_health.run_healthcheck', return_value=(101, '', '')):
            result = runner.invoke(show.cli.commands["system-health"].commands["summary"])
        assert result.exit_code == 1
        assert result.output == "System health check failed: exit code 101\n"

    def test_health_check_killed_by_signal(self):
        runner = CliRunner()
        with mock.patch('show.system_health.run_healthcheck', return_value=(-9, '', '')):
            result = runner.invoke(show.cli.commands["system-health"].commands["summary"])
        assert result.exit_code == 1
        assert result.output == "System health check failed: killed by signal 9\n"
        with mock.patch('show.system_health.run_healthcheck', return_value=(-11, '', 'Fatal Python error\n')):
            result = runner.invoke(show.cli.commands["system-health"].commands["summary"])
        assert result.exit_code == 1
        assert result.output == "System health check failed: Fatal Python error (killed by signal 11)\n"

    def test_health_check_prints_before_the_report(self):
        """What the checks printed (here the LED message of a platform without set_status_led) comes first."""
        stat = {'Hardware': {'fan1': {'status': 'OK', 'message': '', 'type': 'Fan'}}}
        output = json.dumps({'led': 'green', 'stat': stat, 'ignore': {'services': [], 'devices': []}})
        runner = CliRunner()
        with mock.patch('show.system_health.run_healthcheck',
                        return_value=(0, output, 'chassis.set_status_led is not implemented\n')):
            result = runner.invoke(show.cli.commands["system-health"].commands["summary"])
        assert result.exit_code == 0
        assert result.output == """\
chassis.set_status_led is not implemented
System status summary

  System status LED  green
  Services:
    Status: OK
  Hardware:
    Status: OK
"""

    def test_health_check_prints_without_trailing_newline(self):
        """The report starts on its own line even when what the checks printed does not end with a newline."""
        stat = {'Hardware': {'fan1': {'status': 'OK', 'message': '', 'type': 'Fan'}}}
        output = json.dumps({'led': 'green', 'stat': stat, 'ignore': {'services': [], 'devices': []}})
        runner = CliRunner()
        with mock.patch('show.system_health.run_healthcheck',
                        return_value=(0, output, 'chassis.set_status_led is not implemented')):
            result = runner.invoke(show.cli.commands["system-health"].commands["summary"])
        assert result.exit_code == 0
        assert result.output.startswith("chassis.set_status_led is not implemented\nSystem status summary\n")

    def test_health_check_os_error(self):
        runner = CliRunner()
        with mock.patch('show.system_health.run_healthcheck', side_effect=PermissionError(13, 'Permission denied')):
            result = runner.invoke(show.cli.commands["system-health"].commands["summary"])
        assert result.exit_code == 1
        assert result.output == "System health check failed: [Errno 13] Permission denied\n"

    def test_health_check_invalid_output(self):
        runner = CliRunner()
        expected = "System health check failed: invalid output from {}\n".format(show.system_health.HEALTHCHECK_PATH)
        for stdout in ['', 'not json', '[]', '{"led": "green"}', '{"led": null, "stat": {}}',
                       '{"led": "green", "stat": {}, "ignore": []}',
                       '{"led": "green", "stat": {}, "ignore": null}',
                       '{"led": "green", "stat": {"Hardware": []}}',
                       '{"led": "green", "stat": {"Hardware": {"fan1": "OK"}}}',
                       '{"led": "green", "stat": {"Hardware": {"fan1": {"status": "OK", "message": ""}}}}',
                       ('{"led": "green", "stat": {"Services": {"bgp": '
                        '{"status": "OK", "message": null, "type": "x"}}}}'),
                       '{"led": "green", "stat": {}, "ignore": {"services": "bgp"}}',
                       '{"led": "green", "stat": {}, "ignore": {"devices": [1]}}']:
            with mock.patch('show.system_health.run_healthcheck', return_value=(0, stdout, '')):
                result = runner.invoke(show.cli.commands["system-health"].commands["summary"])
            assert result.exit_code == 1, stdout
            assert result.output == expected, stdout
        # What the binary printed on stderr explains the output, so it is shown too.
        with mock.patch('show.system_health.run_healthcheck', return_value=(0, 'not json', 'Traceback: oops\n')):
            result = runner.invoke(show.cli.commands["system-health"].commands["summary"])
        assert result.exit_code == 1
        assert result.output == "System health check failed: Traceback: oops (invalid output from {})\n".format(
            show.system_health.HEALTHCHECK_PATH)

    def test_health_requires_root(self):
        runner = CliRunner()
        with mock.patch('show.system_health.os.geteuid', return_value=1000):
            result = runner.invoke(show.cli.commands["system-health"].commands["summary"])
        assert result.exit_code == 1
        assert result.output == "Root privileges are required for this operation\n"

    def test_run_healthcheck(self):
        with mock.patch('show.system_health.subprocess.run') as run, \
                mock.patch('show.system_health.HEALTHCHECK_PATH', '/opt/test/healthcheck'):
            run.return_value = mock.Mock(returncode=0, stdout='{}', stderr='')
            assert real_run_healthcheck() == (0, '{}', '')
        # No overall limit, as the in-process checks had none. The binary writes UTF-8 whatever the locale.
        run.assert_called_once_with(['/opt/test/healthcheck', '--json'], capture_output=True, text=True,
                                    encoding='utf-8', errors='replace')

    @staticmethod
    def write_binary(path, mode, stdout='', stderr=''):
        """A stand-in check binary: a shell script printing the given text."""
        path.write_text("#!/bin/sh\nprintf '%s' '{}'\nprintf '%s' '{}' >&2\n".format(stdout, stderr))
        path.chmod(mode)
        return str(path)

    def test_health_check_runs_the_binary(self, tmp_path):
        stat = {'Hardware': {'fan1': {'status': 'OK', 'message': '', 'type': 'Fan'}}}
        output = json.dumps({'led': 'green', 'stat': stat, 'ignore': {'services': [], 'devices': []}})
        path = self.write_binary(tmp_path / 'healthcheck', 0o755, output, 'vendor print\n')
        runner = CliRunner()
        with mock.patch('show.system_health.HEALTHCHECK_PATH', path), \
                mock.patch('show.system_health.healthcheck_installed', real_healthcheck_installed), \
                mock.patch('show.system_health.run_healthcheck', real_run_healthcheck):
            result = runner.invoke(show.cli.commands["system-health"].commands["summary"])
        assert result.exit_code == 0, result.output
        assert result.output.startswith("vendor print\nSystem status summary\n\n  System status LED  green\n")

    def test_health_check_binary_not_executable(self, tmp_path):
        """A binary that is present but cannot run is reported as such, not as missing."""
        path = self.write_binary(tmp_path / 'healthcheck', 0o644)
        runner = CliRunner()
        with mock.patch('show.system_health.HEALTHCHECK_PATH', path), \
                mock.patch('show.system_health.healthcheck_installed', real_healthcheck_installed), \
                mock.patch('show.system_health.run_healthcheck', real_run_healthcheck), \
                mock.patch('show.system_health.syslog.syslog') as log:
            result = runner.invoke(show.cli.commands["system-health"].commands["summary"])
        log.assert_not_called()
        assert result.exit_code == 1
        assert result.output == "System health check failed: [Errno 13] Permission denied: '{}'\n".format(path)

    def test_healthcheck_installed(self, tmp_path):
        path = tmp_path / 'healthcheck'
        with mock.patch('show.system_health.HEALTHCHECK_PATH', str(path)):
            assert not real_healthcheck_installed()
            self.write_binary(path, 0o755)
            assert real_healthcheck_installed()
            # Present but not executable: running it gives the error, rather than the fallback.
            path.chmod(0o644)
            assert real_healthcheck_installed()

    @staticmethod
    def health_checker_package(config_file_exists, calls):
        """Stand-ins for the Python health_checker package and the vendor's Chassis, recording what is called."""
        class Config:
            ignore_services = []
            ignore_devices = ['psu.voltage']

            def config_file_exists(self):
                calls.append('config_file_exists')
                return config_file_exists

        class Manager:
            def __init__(self):
                self.config = Config()

            def check(self, chassis):
                calls.append('check')
                return {'Hardware': {'fan1': {'status': 'OK', 'message': '', 'type': 'Fan'}}}

        class Chassis:
            def __init__(self):
                calls.append('Chassis')

            def initizalize_system_led(self):
                calls.append('initialize LED')

            def get_status_led(self):
                calls.append('get_status_led')
                return 'green'

        return {'health_checker.manager': SimpleNamespace(HealthCheckerManager=Manager),
                'sonic_platform.chassis': SimpleNamespace(Chassis=Chassis)}

    def test_modules_replaced(self):
        """Only the given entries of sys.modules are replaced and then restored; a module imported meanwhile stays."""
        original, stand_in, imported = SimpleNamespace(), SimpleNamespace(), SimpleNamespace()
        sys.modules['system_health_test_replaced'] = original
        try:
            with modules_replaced({'system_health_test_replaced': stand_in, 'system_health_test_added': None}):
                assert sys.modules['system_health_test_replaced'] is stand_in
                assert sys.modules['system_health_test_added'] is None
                sys.modules['system_health_test_imported'] = imported
            assert sys.modules['system_health_test_replaced'] is original
            assert 'system_health_test_added' not in sys.modules
            assert sys.modules['system_health_test_imported'] is imported
        finally:
            for name in ('system_health_test_replaced', 'system_health_test_added', 'system_health_test_imported'):
                sys.modules.pop(name, None)

    def test_health_without_healthcheck_binary(self):
        """Without the binary the checks run in process through the Python health_checker package."""
        calls = []
        runner = CliRunner()
        with mock.patch('show.system_health.healthcheck_installed', return_value=False), \
                modules_replaced(self.health_checker_package(True, calls)), \
                mock.patch('show.system_health.syslog.syslog') as log, \
                mock.patch('show.system_health.run_healthcheck') as run:
            result = runner.invoke(show.cli.commands["system-health"].commands["summary"])
        run.assert_not_called()
        log.assert_called_once_with(
            show.system_health.syslog.LOG_NOTICE,
            "show system-health: {} is not installed, running the Python health_checker package "
            "instead".format(show.system_health.HEALTHCHECK_PATH))
        assert result.output == """\
System status summary

  System status LED  green
  Services:
    Status: OK
  Hardware:
    Status: OK
"""
        # The LED is initialized after the checks, then read for the report.
        assert calls == ['config_file_exists', 'Chassis', 'check', 'initialize LED', 'get_status_led']

    def test_health_detail_without_healthcheck_binary(self):
        calls = []
        runner = CliRunner()
        with mock.patch('show.system_health.healthcheck_installed', return_value=False), \
                modules_replaced(self.health_checker_package(True, calls)), \
                mock.patch('show.system_health.syslog.syslog'), \
                mock.patch('show.system_health.run_healthcheck') as run:
            result = runner.invoke(show.cli.commands["system-health"].commands["detail"])
        run.assert_not_called()
        assert result.exit_code == 0
        assert result.output == """\
System status summary

  System status LED  green
  Services:
    Status: OK
  Hardware:
    Status: OK

System services and devices monitor list

Name    Status    Type
------  --------  ------
fan1    OK        Fan

System services and devices ignore list

Name         Status    Type
-----------  --------  ------
psu.voltage  Ignored   Device
"""
        assert calls == ['config_file_exists', 'Chassis', 'check', 'initialize LED', 'get_status_led']

    def test_health_monitor_list_without_healthcheck_binary(self):
        calls = []
        runner = CliRunner()
        with mock.patch('show.system_health.healthcheck_installed', return_value=False), \
                modules_replaced(self.health_checker_package(True, calls)), \
                mock.patch('show.system_health.syslog.syslog'), \
                mock.patch('show.system_health.run_healthcheck') as run:
            result = runner.invoke(show.cli.commands["system-health"].commands["monitor-list"])
        run.assert_not_called()
        assert result.exit_code == 0
        assert result.output == """
System services and devices monitor list

Name    Status    Type
------  --------  ------
fan1    OK        Fan
"""
        # The LED is initialized even though this report does not show it.
        assert calls == ['config_file_exists', 'Chassis', 'check', 'initialize LED']

    def test_health_without_healthcheck_binary_or_configuration_file(self):
        calls = []
        runner = CliRunner()
        with mock.patch('show.system_health.healthcheck_installed', return_value=False), \
                modules_replaced(self.health_checker_package(False, calls)), \
                mock.patch('show.system_health.syslog.syslog'), \
                mock.patch('show.system_health.run_healthcheck') as run:
            result = runner.invoke(show.cli.commands["system-health"].commands["summary"])
        run.assert_not_called()
        assert result.exit_code == 1
        assert result.output == "System health configuration file not found, exit...\n"
        assert calls == ['config_file_exists']

    def test_health_without_healthcheck_binary_or_package(self):
        runner = CliRunner()
        with mock.patch('show.system_health.healthcheck_installed', return_value=False), \
                modules_replaced({'health_checker.manager': None}), \
                mock.patch('show.system_health.syslog.syslog') as log:
            result = runner.invoke(show.cli.commands["system-health"].commands["summary"])
        assert result.exit_code == 1
        assert isinstance(result.exception, SystemExit)
        assert result.output.startswith("System health check failed: {} is not installed, and ".format(
            show.system_health.HEALTHCHECK_PATH))
        assert 'health_checker.manager' in result.output
        assert log.call_args.args[0] == show.system_health.syslog.LOG_NOTICE

    def test_health_systemready(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["system-health"].commands["sysready-status"])
        click.echo(result.output)
        print("myresult:{}".format(result.output))
        expected = """\
System is not ready - one or more services are not up

Service-Name    Service-Status    App-Ready-Status    Down-Reason
--------------  ----------------  ------------------  -------------
bgp             Down              Down                Inactive
mgmt-framework  OK                OK                  -
pmon            OK                OK                  -
swss            OK                OK                  -
"""
        assert result.output == expected
        result = runner.invoke(show.cli.commands["system-health"].commands["sysready-status"],["brief"])
        click.echo(result.output)
        print("myresult:{}".format(result.output))
        expected = """\
System is not ready - one or more services are not up
"""
        assert result.output == expected
        result = runner.invoke(show.cli.commands["system-health"].commands["sysready-status"],["detail"])
        click.echo(result.output)
        print("myresult:{}".format(result.output))
        expected = """\
System is not ready - one or more services are not up

Service-Name    Service-Status    App-Ready-Status    Down-Reason    AppStatus-UpdateTime
--------------  ----------------  ------------------  -------------  ----------------------
bgp             Down              Down                Inactive       -
mgmt-framework  OK                OK                  -              -
pmon            OK                OK                  -              -
swss            OK                OK                  -              -
"""

    def test_health_dpu(self):
        # Mock is_smartswitch to return True
        with mock.patch("sonic_py_common.device_info.is_smartswitch", return_value=True):

            # Check if 'dpu' command is available under system-health
            available_commands = show.cli.commands["system-health"].commands
            assert "dpu" in available_commands, f"'dpu' command not found: {available_commands}"

            conn = dbconnector.SonicV2Connector()
            conn.connect(conn.CHASSIS_STATE_DB)
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "id", "0")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_midplane_link_reason", "OK")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_midplane_link_state", "UP")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_data_plane_time", "20240607 15:08:51")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_control_plane_time", "20240608 09:11:13")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_data_plane_state", "UP")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_control_plane_reason", "Uplink is UP")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_control_plane_state", "UP")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_data_plane_reason", "Polaris is UP")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_midplane_link_time", "20240608 09:11:13")

            with mock.patch("show.system_health.SonicV2Connector", return_value=conn):
                runner = CliRunner()
                result = runner.invoke(show.cli.commands["system-health"].commands["dpu"], ["DPU0"])

                # Assert the output and exit code
                assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}. Output: {result.output}"
                assert "DPU0" in result.output, f"Expected 'DPU0' in output, got: {result.output}"

                # check -h option
                result = runner.invoke(show.cli.commands["system-health"].commands["dpu"], ["-h"])
                print(result.output)

    def test_health_dpu_non_smartswitch(self):
        # Mock is_smartswitch to return True
        with mock.patch("sonic_py_common.device_info.is_smartswitch", return_value=False):

            # Check if 'dpu' command is available under system-health
            available_commands = show.cli.commands["system-health"].commands
            assert "dpu" in available_commands, f"'dpu' command not found: {available_commands}"

            conn = dbconnector.SonicV2Connector()
            conn.connect(conn.CHASSIS_STATE_DB)
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "id", "0")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_midplane_link_reason", "OK")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_midplane_link_state", "UP")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_data_plane_time", "20240607 15:08:51")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_control_plane_time", "20240608 09:11:13")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_data_plane_state", "UP")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_control_plane_reason", "Uplink is UP")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_control_plane_state", "UP")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_data_plane_reason", "Polaris is UP")
            conn.set(conn.CHASSIS_STATE_DB, 'DPU_STATE|DPU0', "dpu_midplane_link_time", "20240608 09:11:13")

            with mock.patch("show.system_health.SonicV2Connector", return_value=conn):
                runner = CliRunner()
                result = runner.invoke(show.cli.commands["system-health"].commands["dpu"], ["DPU0"])

                # Assert the output and exit code
                assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}. Output: {result.output}"
                assert "DPU0" not in result.output, f"Output contained DPU0: {result.output}"

    # Test 'get_all_dpu_options' function
    def test_get_all_dpu_options(self):
        # Mock is_smartswitch to return True
        with mock.patch("sonic_py_common.device_info.is_smartswitch", return_value=True):

            # Mock platform info to simulate a valid platform returned from get_platform_info
            mock_platform_info = {'platform': 'mock_platform'}
            with mock.patch("sonic_py_common.device_info.get_platform_info", return_value=mock_platform_info):

                # Mock open to simulate reading a platform.json file
                mock_platform_data = '{"DPUS": {"dpu0": {}, "dpu1": {}}}'
                with mock.patch("builtins.open", mock.mock_open(read_data=mock_platform_data)):

                    # Mock json.load to return parsed JSON content from the mocked file
                    with mock.patch("json.load", return_value=json.loads(mock_platform_data)):

                        # Import the actual get_all_dpu_options function and invoke it
                        from show.system_health import get_all_dpu_options
                        dpu_list = get_all_dpu_options()
                        print(dpu_list)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        cls.patches.close()
        show.cli = original_cli

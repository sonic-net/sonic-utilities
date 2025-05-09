# https://github.com/ninjaaron/fast-entry_points
# workaround for slow 'pkg_resources' import
#
# NOTE: this only has effect on console_scripts and no speed-up for commands
# under scripts/. Consider stop using scripts and use console_scripts instead
#
# https://stackoverflow.com/questions/18787036/difference-between-entry-points-console-scripts-and-scripts-in-setup-py
from __future__ import print_function
import sys
import fastentrypoints

from setuptools import setup
import pkg_resources
from packaging import version

# sonic_dependencies, version requirement only supports '>='
sonic_dependencies = [
    'sonic-config-engine',
    'sonic-platform-common',
    'sonic-py-common',
    'sonic-yang-mgmt',
]

for package in sonic_dependencies:
    try:
        package_dist = pkg_resources.get_distribution(package.split(">=")[0])
    except pkg_resources.DistributionNotFound:
        print(package + " is not found!", file=sys.stderr)
        print("Please build and install SONiC python wheels dependencies from sonic-buildimage", file=sys.stderr)
        exit(1)
    if ">=" in package:
        if version.parse(package_dist.version) >= version.parse(package.split(">=")[1]):
            continue
        print(package + " version not match!", file=sys.stderr)
        exit(1)

setup(
    name='sonic-utilities',
    version='1.2',
    description='Command-line utilities for SONiC',
    license='Apache 2.0',
    author='SONiC Team',
    author_email='linuxnetdev@microsoft.com',
    url='https://github.com/Azure/sonic-utilities',
    maintainer='Joe LeVeque',
    maintainer_email='jolevequ@microsoft.com',
    packages=[
        'acl_loader',
        'clear',
        'clear.plugins',
        'clear.plugins.auto',
        'config',
        'config.plugins',
        'config.plugins.auto',
        'connect',
        'consutil',
        'counterpoll',
        'crm',
        'debug',
        'generic_config_updater',
        'dump',
        'dump.plugins',
        'pfcwd',
        'sfputil',
        'ssdutil',
        'pfc',
        'psuutil',
        'flow_counter_util',
        'fdbutil',
        'fwutil',
        'pcieutil',
        'pddf_fanutil',
        'pddf_psuutil',
        'pddf_thermalutil',
        'pddf_ledutil',
        'syslog_util',
        'rcli',
        'show',
        'show.interfaces',
        'show.plugins',
        'show.plugins.auto',
        'sonic_installer',
        'sonic_installer.bootloader',
        'sonic_package_manager',
        'sonic_package_manager.service_creator',
        'tests',
        'undebug',
        'utilities_common',
        'watchdogutil',
        'sonic_cli_gen',
    ],
    package_data={
        'generic_config_updater': ['gcu_services_validator.conf.json', 'gcu_field_operation_validators.conf.json'],
        'show': ['aliases.ini'],
        'sonic_installer': ['aliases.ini'],
        'tests': ['acl_input/*',
                  'db_migrator_input/*.json',
                  'db_migrator_input/config_db/*.json',
                  'db_migrator_input/appl_db/*.json',
                  'counterpoll_input/*',
                  'mock_tables/*.py',
                  'mock_tables/*.json',
                  'mock_tables/asic0/*.json',
                  'mock_tables/asic1/*.json',
                  'mock_tables/asic2/*.json',
                  'filter_fdb_input/*',
                  'pfcwd_input/*',
                  'wm_input/*',
                  'ecn_input/*',
                  'dump_input/*']
    },
    scripts=[
        'scripts/aclshow',
        'scripts/asic_config_check',
        'scripts/boot_part',
        'scripts/buffershow',
        'scripts/coredump-compress',
        'scripts/configlet',
        'scripts/db_migrator.py',
        'scripts/decode-syseeprom',
        'scripts/dropcheck',
        'scripts/disk_check.py',
        'scripts/dpu-tty.py',
        'scripts/dropconfig',
        'scripts/dropstat',
        'scripts/dualtor_neighbor_check.py',
        'scripts/dump_nat_entries.py',
        'scripts/debug_voq_chassis_packet_drops.sh',
        'scripts/ecnconfig',
        'scripts/express-reboot',
        'scripts/fabricstat',
        'scripts/fanshow',
        'scripts/fast-reboot',
        'scripts/fast-reboot-dump.py',
        'scripts/fast-reboot-filter-routes.py',
        'scripts/fdbclear',
        'scripts/fdbshow',
        'scripts/fibshow',
        'scripts/flow_counters_stat',
        'scripts/gearboxutil',
        'scripts/generate_dump',
        'scripts/generate_shutdown_order.py',
        'scripts/intfutil',
        'scripts/intfstat',
        'scripts/ipintutil',
        'scripts/lag_keepalive.py',
        'scripts/lldpshow',
        'scripts/log_ssd_health',
        'scripts/mellanox_buffer_migrator.py',
        'scripts/mmuconfig',
        'scripts/natclear',
        'scripts/natconfig',
        'scripts/natshow',
        'scripts/nbrshow',
        'scripts/neighbor_advertiser',
        'scripts/pcmping',
        'scripts/pg-drop',
        'scripts/port2alias',
        'scripts/portconfig',
        'scripts/portstat',
        'scripts/pfcstat',
        'scripts/psushow',
        'scripts/queuestat',
        'scripts/reboot',
        'scripts/reboot_smartswitch_helper',
        'scripts/route_check.py',
        'scripts/route_check_test.sh',
        'scripts/vnet_route_check.py',
        'scripts/sfpshow',
        'scripts/soft-reboot',
        'scripts/storyteller',
        'scripts/syseeprom-to-json',
        'scripts/srv6stat',
        'scripts/teamd_increase_retry_count.py',
        'scripts/tempershow',
        'scripts/tunnelstat',
        'scripts/update_json.py',
        'scripts/sensorshow',
        'scripts/voqutil',
        'scripts/warm-reboot',
        'scripts/watermarkstat',
        'scripts/watermarkcfg',
        'scripts/sonic-kdump-config',
        'scripts/sonic-bootchart',
        'scripts/centralize_database',
        'scripts/null_route_helper',
        'scripts/coredump_gen_handler.py',
        'scripts/memory_threshold_check.py',
        'scripts/memory_threshold_check_handler.py',
        'scripts/techsupport_cleanup.py',
        'scripts/storm_control.py',
        'scripts/verify_image_sign.sh',
        'scripts/verify_image_sign_common.sh',
        'scripts/check_db_integrity.py',
        'scripts/sysreadyshow',
        'scripts/wredstat'
    ],
    entry_points={
        'console_scripts': [
            'acl-loader = acl_loader.main:cli',
            'config = config.main:config',
            'connect = connect.main:connect',
            'consutil = consutil.main:consutil',
            'counterpoll = counterpoll.main:cli',
            'crm = crm.main:cli',
            'debug = debug.main:cli',
            'dump = dump.main:dump',
            'filter_fdb_entries = fdbutil.filter_fdb_entries:main',
            'pfcwd = pfcwd.main:cli',
            'sfputil = sfputil.main:cli',
            'ssdutil = ssdutil.main:ssdutil',
            'pfc = pfc.main:cli',
            'psuutil = psuutil.main:cli',
            'fwutil = fwutil.main:cli',
            'pcieutil = pcieutil.main:cli',
            'pddf_fanutil = pddf_fanutil.main:cli',
            'pddf_psuutil = pddf_psuutil.main:cli',
            'pddf_thermalutil = pddf_thermalutil.main:cli',
            'pddf_ledutil = pddf_ledutil.main:cli',
            'rexec = rcli.rexec:cli',
            'rshell = rcli.rshell:cli',
            'show = show.main:cli',
            'sonic-clear = clear.main:cli',
            'sonic-installer = sonic_installer.main:sonic_installer',
            'sonic_installer = sonic_installer.main:sonic_installer',  # Deprecated
            'sonic-package-manager = sonic_package_manager.main:cli',
            'spm = sonic_package_manager.main:cli',
            'undebug = undebug.main:cli',
            'watchdogutil = watchdogutil.main:watchdogutil',
            'sonic-cli-gen = sonic_cli_gen.main:cli',
        ]
    },
    install_requires=[
        'bcrypt==3.2.2',
        'click==7.0',
        'cryptography>=3.3.2',
        'urllib3>=2',
        'click-log>=0.3.2',
        'docker>=4.4.4',
        'docker-image-py>=0.1.10',
        'filelock>=3.0.12',
        'enlighten>=1.8.0',
        'ipaddress>=1.0.23',
        'protobuf',
        'jinja2>=2.11.3',
        'jsondiff>=1.2.0',
        'jsonpatch>=1.32.0',
        'jsonpointer>=1.9',
        'm2crypto>=0.31.0',
        'natsort>=6.2.1',  # 6.2.1 is the last version which supports Python 2. Can update once we no longer support Python 2
        'netaddr>=0.8.0',
        'netifaces>=0.10.7',
        'paramiko==2.11.0',
        'pexpect>=4.8.0',
        'semantic-version>=2.8.5',
        'prettyprinter>=0.18.0',
        'pyroute2==0.7.12',
        'requests>=2.25.0, <=2.31.0',
        'tabulate==0.9.0',
        'toposort==1.6',
        'www-authenticate==0.9.2',
        'xmltodict==0.12.0',
        'lazy-object-proxy',
        'six==1.16.0',
        'scp==0.14.5',
    ] + sonic_dependencies,
    setup_requires= [
        'pytest-runner',
        'wheel'
    ],
    tests_require = [
        'pyfakefs',
        'responses',
        'pytest',
        'mockredispy>=2.9.3',
        'deepdiff==6.2.2'
    ],
    extras_require = {
        'testing': [
            'pyfakefs',
            'responses',
            'pytest',
            'mockredispy>=2.9.3',
            'deepdiff==6.2.2'
        ],
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.7',
        'Topic :: Utilities',
    ],
    keywords='sonic SONiC utilities command line cli CLI',
    test_suite='setup.get_test_suite'
)

# https://github.com/ninjaaron/fast-entry_points
# workaround for slow 'pkg_resources' import
#
# NOTE: this only has effect on console_scripts and no speed-up for commands
# under scripts/. Consider stop using scripts and use console_scripts instead
#
# https://stackoverflow.com/questions/18787036/difference-between-entry-points-console-scripts-and-scripts-in-setup-py
from __future__ import print_function
import sys
import shutil
import os

from setuptools import setup
import pkg_resources
from packaging import version


# Copy necessary directories and files for python package
if not os.path.exists("./generic_config_updater"):
    shutil.copytree("../generic_config_updater", ".")
if not os.path.exists("./utilities_common"):
    shutil.copytree("../utilities_common", ".")
if not os.path.exists("./scripts/gcu.py"):
    if not os.path.exists("./scripts"):
        os.makedirs("./scripts")
    shutil.copy("../scripts/gcu.py", "./scripts/")

# sonic_dependencies, version requirement only supports '>='
sonic_dependencies = [
    'sonic-config-engine',
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
    name='sonic-gcu',
    version='1.0.0',
    description='GCU package for SONiC',
    license='Apache 2.0',
    author='SONiC Team',
    author_email='linuxnetdev@microsoft.com',
    url='https://github.com/Azure/sonic-utilities/gcu',
    maintainer='Gang Lv',
    maintainer_email='ganglv@microsoft.com',
    packages=[
        'generic_config_updater',
        'utilities_common',
    ],
    package_data={
        'generic_config_updater': ['gcu_services_validator.conf.json', 'gcu_field_operation_validators.conf.json']
    },
    scripts=[
        'scripts/gcu.py'
    ],
    entry_points={
        'console_scripts': [
        ]
    },
    install_requires=[
        'click==7.0',
        'jsondiff>=1.2.0',
        'jsonpatch>=1.32.0',
        'jsonpointer>=1.9',
        'netifaces>=0.10.7',
        'lazy-object-proxy',
    ] + sonic_dependencies,
    setup_requires=[
        'pytest-runner',
        'wheel'
    ],
    extras_require={
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
    keywords='SONiC GCU package'
)

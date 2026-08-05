# generic_config_updater/ — Standalone GCU wheel build context
#
# This setup.py builds the 'sonic-gcu' Python wheel, published independently
# from the main 'sonic-utilities' wheel.  The gcu-standalone binary installed
# from this wheel is placed at /opt/sonic/gcu/current/bin/gcu-standalone and
# allows the GCU container to deliver fixes to generic_config_updater without
# touching the host sonic-utilities package.
#
# pytest.ini and .coveragerc in this directory configure test runs scoped to
# GCU only (see azure-pipelines.yml 'Build Python 3 wheel for GCU' step).
#
# Dependencies are intentionally absent from install_requires: the GCU venv is
# created with --system-site-packages and the wheel is installed with --no-deps,
# so all runtime dependencies (SONiC packages and third-party libs) are
# inherited from the host SONiC environment.
from setuptools import setup


setup(
    name='sonic-gcu',
    version='1.0.0',
    description='GCU package for SONiC',
    license='Apache 2.0',
    author='SONiC Team',
    author_email='linuxnetdev@microsoft.com',
    url='https://github.com/Azure/sonic-utilities/generic_config_updater',
    maintainer='Xincun Li',
    maintainer_email='xincun.li@microsoft.com',
    package_dir={'generic_config_updater': '.'},
    packages=[
        'generic_config_updater',
    ],
    package_data={
        'generic_config_updater': ['gcu_services_validator.conf.json', 'gcu_field_operation_validators.conf.json']
    },
    entry_points={
        'console_scripts': [
            'gcu-standalone=generic_config_updater.main:main',
        ]
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

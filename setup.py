from setuptools import setup

setup(
    name='sonic-utilities',
    version='1.1',
    description='Command-line utilities for SONiC',
    license='Apache 2.0',
    author='SONiC Team',
    author_email='linuxnetdev@microsoft.com',
    url='https://github.com/Azure/sonic-utilities',
    maintainer='Joe LeVeque',
    maintainer_email='jolevequ@microsoft.com',
    packages=['config', 'sfputil', 'show', 'sonic_eeprom', 'sonic_sfp', "sonic_installer", 'acl_loader'],
    package_data={
        'show': ['aliases.ini']
    },
    scripts=[
        'scripts/aclshow',
        'scripts/boot_part',
        'scripts/coredump-compress',
        'scripts/decode-syseeprom',
        'scripts/dropcheck',
        'scripts/fast-reboot',
        'scripts/fast-reboot-dump.py',
        'scripts/generate_dump',
        'scripts/lldpshow',
        'scripts/portstat',
        'scripts/teamshow',
    ],
    data_files=[
        ('/etc/bash_completion.d', ['data/etc/bash_completion.d/config']),
        ('/etc/bash_completion.d', ['data/etc/bash_completion.d/sfputil']),
        ('/etc/bash_completion.d', ['data/etc/bash_completion.d/show']),
        ('/etc/bash_completion.d', ['data/etc/bash_completion.d/sonic_installer']),
        ('/etc/bash_completion.d', ['data/etc/bash_completion.d/acl-loader']),
    ],
    entry_points={
        'console_scripts': [
            'config = config.main:cli',
            'sfputil = sfputil.main:cli',
            'show = show.main:cli',
            'sonic_installer = sonic_installer.main:cli',
            'acl-loader = acl_loader.main:cli'
        ]
    },
    install_requires=[
        'click',
        'click-default-group',
        'natsort',
        'tabulate'
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2.7',
        'Topic :: Utilities',
    ],
    keywords='sonic SONiC utilities command line cli CLI',
)

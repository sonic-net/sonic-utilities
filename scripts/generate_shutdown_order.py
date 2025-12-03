#!/usr/bin/python3

''' This script is used to generate initial warm/fast shutdown order file '''

from sonic_package_manager import PackageManager

def main():
    manager = PackageManager.get_manager()
    installed_packages = manager.get_installed_packages()
    print('installed packages {}'.format(installed_packages))
    manager.service_creator.generate_shutdown_sequence_files(installed_packages)
    print('Done.')

if __name__ == '__main__':
    main()

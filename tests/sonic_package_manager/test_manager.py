#!/usr/bin/env python

import re
from unittest.mock import Mock, call, patch

import pytest

import sonic_package_manager
from sonic_package_manager.errors import *
from sonic_package_manager.version import Version

@pytest.fixture(autouse=True)
def mock_run_command():
    with patch('sonic_package_manager.manager.run_command') as run_command:
        yield run_command


def test_installation_not_installed(package_manager):
    package_manager.install('test-package')
    package = package_manager.get_installed_package('test-package')
    assert package.installed
    assert package.entry.default_reference == '1.6.0'


def test_installation_already_installed(package_manager):
    package_manager.install('test-package')
    with pytest.raises(PackageManagerError,
                       match='1.6.0 is already installed'):
        package_manager.install('test-package')


def test_installation_dependencies(package_manager, fake_metadata_resolver, mock_docker_api):
    manifest = fake_metadata_resolver.metadata_store['Azure/docker-test']['1.6.0']['manifest']
    manifest['package']['depends'] = ['swss^2.0.0']
    with pytest.raises(PackageInstallationError,
                       match=re.escape('Package test-package requires swss^2.0.0 '
                                       'but version 1.0.0 is installed')):
        package_manager.install('test-package')


def test_installation_dependencies_missing_package(package_manager, fake_metadata_resolver):
    manifest = fake_metadata_resolver.metadata_store['Azure/docker-test']['1.6.0']['manifest']
    manifest['package']['depends'] = ['missing-package>=1.0.0']
    with pytest.raises(PackageInstallationError,
                       match='Package test-package requires '
                             'missing-package>=1.0.0 but it is not installed'):
        package_manager.install('test-package')


def test_installation_dependencies_satisfied(package_manager, fake_metadata_resolver):
    manifest = fake_metadata_resolver.metadata_store['Azure/docker-test']['1.6.0']['manifest']
    manifest['package']['depends'] = ['database>=1.0.0', 'swss>=1.0.0']
    package_manager.install('test-package')


def test_installation_components_dependencies_satisfied(package_manager, fake_metadata_resolver):
    metadata = fake_metadata_resolver.metadata_store['Azure/docker-test']['1.6.0']
    manifest = metadata['manifest']
    metadata['components'] = {
        'libswsscommon': Version.parse('1.1.0')
    }
    manifest['package']['depends'] = [
        {
            'name': 'swss',
            'version': '>=1.0.0',
            'components': {
                'libswsscommon': '^1.0.0',
            },
        },
    ]
    package_manager.install('test-package')


def test_installation_components_dependencies_not_satisfied(package_manager, fake_metadata_resolver):
    metadata = fake_metadata_resolver.metadata_store['Azure/docker-test']['1.6.0']
    manifest = metadata['manifest']
    metadata['components'] = {
        'libswsscommon': Version.parse('1.1.0')
    }
    manifest['package']['depends'] = [
        {
            'name': 'swss',
            'version': '>=1.0.0',
            'components': {
                'libswsscommon': '^1.1.0',
            },
        },
    ]
    with pytest.raises(PackageInstallationError,
                       match=re.escape('Package test-package requires libswsscommon ^1.1.0 '
                                       'in package swss>=1.0.0 but version 1.0.0 is installed')):
        package_manager.install('test-package')


def test_installation_components_dependencies_implicit(package_manager, fake_metadata_resolver):
    metadata = fake_metadata_resolver.metadata_store['Azure/docker-test']['1.6.0']
    manifest = metadata['manifest']
    metadata['components'] = {
        'libswsscommon': Version.parse('2.1.0')
    }
    manifest['package']['depends'] = [
        {
            'name': 'swss',
            'version': '>=1.0.0',
        },
    ]
    with pytest.raises(PackageInstallationError,
                       match=re.escape('Package test-package requires libswsscommon ^2.1.0 '
                                       'in package swss>=1.0.0 but version 1.0.0 is installed')):
        package_manager.install('test-package')


def test_installation_components_dependencies_explicitely_allowed(package_manager, fake_metadata_resolver):
    metadata = fake_metadata_resolver.metadata_store['Azure/docker-test']['1.6.0']
    manifest = metadata['manifest']
    metadata['components'] = {
        'libswsscommon': Version.parse('2.1.0')
    }
    manifest['package']['depends'] = [
        {
            'name': 'swss',
            'version': '>=1.0.0',
            'components': {
                'libswsscommon': '>=1.0.0,<3.0.0'
            }
        },
    ]
    package_manager.install('test-package')


def test_installation_breaks(package_manager, fake_metadata_resolver):
    manifest = fake_metadata_resolver.metadata_store['Azure/docker-test']['1.6.0']['manifest']
    manifest['package']['breaks'] = ['swss^1.0.0']
    with pytest.raises(PackageInstallationError,
                       match=re.escape('Package test-package conflicts with '
                                       'swss^1.0.0 but version 1.0.0 is installed')):
        package_manager.install('test-package')


def test_installation_breaks_missing_package(package_manager, fake_metadata_resolver):
    manifest = fake_metadata_resolver.metadata_store['Azure/docker-test']['1.6.0']['manifest']
    manifest['package']['breaks'] = ['missing-package^1.0.0']
    package_manager.install('test-package')


def test_installation_breaks_not_installed_package(package_manager, fake_metadata_resolver):
    manifest = fake_metadata_resolver.metadata_store['Azure/docker-test']['1.6.0']['manifest']
    manifest['package']['breaks'] = ['test-package-2^1.0.0']
    package_manager.install('test-package')


def test_installation_base_os_constraint(package_manager, fake_metadata_resolver):
    manifest = fake_metadata_resolver.metadata_store['Azure/docker-test']['1.6.0']['manifest']
    manifest['package']['base-os']['libswsscommon'] = '>=2.0.0'
    with pytest.raises(PackageSonicRequirementError,
                       match='Package test-package requires base OS component libswsscommon '
                             'version >=2.0.0 while the installed version is 1.0.0'):
        package_manager.install('test-package')


def test_installation_base_os_constraint_satisfied(package_manager, fake_metadata_resolver):
    manifest = fake_metadata_resolver.metadata_store['Azure/docker-test']['1.6.0']['manifest']
    manifest['package']['base-os']['libswsscommon'] = '>=1.0.0'
    package_manager.install('test-package')


def test_installation_cli_plugin(package_manager, fake_metadata_resolver, anything):
    manifest = fake_metadata_resolver.metadata_store['Azure/docker-test']['1.6.0']['manifest']
    manifest['cli']= {'show': '/cli/plugin.py'}
    with patch('sonic_package_manager.manager.get_cli_plugin_directory') as get_dir_mock:
        get_dir_mock.return_value = '/'
        package_manager.install('test-package')
        package_manager.docker.extract.assert_called_once_with(anything, '/cli/plugin.py', '/test-package.py')


def test_installation_multiple_cli_plugin(package_manager, fake_metadata_resolver, mock_feature_registry, anything):
    manifest = fake_metadata_resolver.metadata_store['Azure/docker-test']['1.6.0']['manifest']
    manifest['cli']= {'show': ['/cli/plugin.py', '/cli/plugin2.py']}
    with patch('sonic_package_manager.manager.get_cli_plugin_directory') as get_dir_mock, \
         patch('os.remove') as remove_mock, \
         patch('os.path.exists') as path_exists_mock:
        get_dir_mock.return_value = '/'
        package_manager.install('test-package')
        package_manager.docker.extract.assert_has_calls(
            [
                call(anything, '/cli/plugin.py', '/test-package.py'),
                call(anything, '/cli/plugin2.py', '/test-package_1.py'),
            ],
            any_order=True,
        )

        package_manager._set_feature_state = Mock()
        package_manager.uninstall('test-package', force=True)
        remove_mock.assert_has_calls(
            [
                call('/test-package.py'),
                call('/test-package_1.py'),
            ],
            any_order=True,
        )


def test_installation_cli_plugin_skipped(package_manager, fake_metadata_resolver, anything):
    manifest = fake_metadata_resolver.metadata_store['Azure/docker-test']['1.6.0']['manifest']
    manifest['cli']= {'show': '/cli/plugin.py'}
    package_manager._install_cli_plugins = Mock()
    package_manager.install('test-package', skip_host_plugins=True)
    package_manager._install_cli_plugins.assert_not_called()


def test_installation_cli_plugin_is_mandatory_but_skipped(package_manager, fake_metadata_resolver):
    manifest = fake_metadata_resolver.metadata_store['Azure/docker-test']['1.6.0']['manifest']
    manifest['cli']= {'mandatory': True}
    with pytest.raises(PackageManagerError,
                       match='CLI is mandatory for package test-package but '
                             'it was requested to be not installed'):
        package_manager.install('test-package', skip_host_plugins=True)


def test_installation(package_manager, mock_docker_api, anything):
    package_manager.install('test-package')
    mock_docker_api.pull.assert_called_once_with('Azure/docker-test', '1.6.0')


def test_installation_using_reference(package_manager,
                                      fake_metadata_resolver,
                                      mock_docker_api,
                                      anything):
    ref = 'sha256:9780f6d83e45878749497a6297ed9906c19ee0cc48cc88dc63827564bb8768fd'
    metadata = fake_metadata_resolver.metadata_store['Azure/docker-test']['1.6.0']
    fake_metadata_resolver.metadata_store['Azure/docker-test'][ref] = metadata

    package_manager.install(f'test-package@{ref}')
    mock_docker_api.pull.assert_called_once_with('Azure/docker-test', f'{ref}')


def test_manager_installation_tag(package_manager,
                                  mock_docker_api,
                                  anything):
    package_manager.install(f'test-package=1.6.0')
    mock_docker_api.pull.assert_called_once_with('Azure/docker-test', '1.6.0')


def test_installation_from_file(package_manager, mock_docker_api, sonic_fs):
    sonic_fs.create_file('Azure/docker-test:1.6.0')
    package_manager.install(tarball='Azure/docker-test:1.6.0')
    mock_docker_api.load.assert_called_once_with('Azure/docker-test:1.6.0')


def test_installation_from_registry(package_manager, mock_docker_api):
    package_manager.install(repotag='Azure/docker-test:1.6.0')
    mock_docker_api.pull.assert_called_once_with('Azure/docker-test', '1.6.0')


def test_installation_from_registry_using_digest(package_manager, mock_docker_api, fake_metadata_resolver):
    ref = 'sha256:9780f6d83e45878749497a6297ed9906c19ee0cc48cc88dc63827564bb8768fd'
    metadata = fake_metadata_resolver.metadata_store['Azure/docker-test']['1.6.0']
    fake_metadata_resolver.metadata_store['Azure/docker-test'][ref] = metadata

    ref = 'sha256:9780f6d83e45878749497a6297ed9906c19ee0cc48cc88dc63827564bb8768fd'
    package_manager.install(repotag=f'Azure/docker-test@{ref}')
    mock_docker_api.pull.assert_called_once_with('Azure/docker-test', ref)


def test_installation_from_file_known_package(package_manager, fake_db, sonic_fs):
    repository = fake_db.get_package('test-package').repository
    sonic_fs.create_file('Azure/docker-test:1.6.0')
    package_manager.install(tarball='Azure/docker-test:1.6.0')
    # locally installed package does not override already known package repository
    assert repository == fake_db.get_package('test-package').repository


def test_installation_from_file_unknown_package(package_manager, fake_db, sonic_fs):
    assert not fake_db.has_package('test-package-4')
    sonic_fs.create_file('Azure/docker-test-4:1.5.0')
    package_manager.install(tarball='Azure/docker-test-4:1.5.0')
    assert fake_db.has_package('test-package-4')


def test_upgrade_from_file_known_package(package_manager, fake_db, sonic_fs):
    repository = fake_db.get_package('test-package-6').repository
    # install older version from repository
    package_manager.install('test-package-6=1.5.0')
    # upgrade from file
    sonic_fs.create_file('Azure/docker-test-6:2.0.0')
    package_manager.install(tarball='Azure/docker-test-6:2.0.0')
    # locally installed package does not override already known package repository
    assert repository == fake_db.get_package('test-package-6').repository


def test_installation_non_default_owner(package_manager, anything, mock_service_creator):
    package_manager.install('test-package', default_owner='kube')
    mock_service_creator.create.assert_called_once_with(anything, state='disabled', owner='kube')
    mock_service_creator.generate_shutdown_sequence_files.assert_called_once_with(
        package_manager.get_installed_packages()
    )


def test_installation_enabled(package_manager, anything, mock_service_creator):
    package_manager.install('test-package', enable=True)
    mock_service_creator.create.assert_called_once_with(anything, state='enabled', owner='local')
    mock_service_creator.generate_shutdown_sequence_files.assert_called_once_with(
        package_manager.get_installed_packages()
    )


def test_installation_fault(package_manager, mock_docker_api, mock_service_creator):
    # make 'tag' to fail
    mock_service_creator.create = Mock(side_effect=Exception('Failed to create service'))
    # 'rmi' is called on rollback
    mock_docker_api.rmi = Mock(side_effect=Exception('Failed to remove image'))
    # assert that the rollback does not hide the original failure.
    with pytest.raises(Exception, match='Failed to create service'):
        package_manager.install('test-package')
    mock_docker_api.rmi.assert_called_once()


def test_manager_installation_version_range(package_manager):
    with pytest.raises(PackageManagerError,
                       match='Can only install specific version. '
                             'Use only following expression "test-package=<version>" '
                             'to install specific version'):
        package_manager.install(f'test-package>=1.6.0')


def test_manager_upgrade(package_manager, sonic_fs):
    package_manager.install('test-package-6=1.5.0')
    package = package_manager.get_installed_package('test-package-6')

    package_manager.install('test-package-6=2.0.0')
    upgraded_package = package_manager.get_installed_package('test-package-6')
    assert upgraded_package.entry.version == Version.parse('2.0.0')
    assert upgraded_package.entry.default_reference == package.entry.default_reference


def test_manager_package_reset(package_manager, sonic_fs):
    package_manager.install('test-package-6=1.5.0')
    package_manager.install('test-package-6=2.0.0')

    package_manager.reset('test-package-6')
    upgraded_package = package_manager.get_installed_package('test-package-6')
    assert upgraded_package.entry.version == Version.parse('1.5.0')


def test_manager_migration(package_manager, fake_db_for_migration):
    package_manager.install = Mock()
    package_manager.migrate_packages(fake_db_for_migration)

    package_manager.install.assert_has_calls([
        # test-package-3 was installed but there is a newer version installed
        # in fake_db_for_migration, asserting for upgrade
        call('test-package-3=1.6.0'),
        # test-package-4 was not present in DB at all, but it is present and installed in
        # fake_db_for_migration, thus asserting that it is going to be installed.
        call('test-package-4=1.5.0'),
        # test-package-5 1.5.0 was installed in fake_db_for_migration but the default
        # in current db is 1.9.0, assert that migration will install the newer version.
        call('test-package-5=1.9.0'),
        # test-package-6 2.0.0 was installed in fake_db_for_migration but the default
        # in current db is 1.5.0, assert that migration will install the newer version.
        call('test-package-6=2.0.0')],
        any_order=True
    )


def mock_get_docker_client(dockerd_sock):
    class DockerClient:
        def __init__(self, dockerd_sock):
            class Image:
                def __init__(self, image_id):
                    self.image_id = image_id
                
                def save(self, named):
                    return ["named: {}".format(named).encode()]

            image = Image("dummy_id")
            self.images = {
                "Azure/docker-test-3:1.6.0": image,
                "Azure/docker-test-6:2.0.0": image
            }
            self.dockerd_sock = dockerd_sock

    return DockerClient(dockerd_sock)


def test_manager_migration_dockerd(package_manager, fake_db_for_migration, mock_docker_api):
    package_manager.install = Mock()
    package_manager.get_docker_client = Mock(side_effect=mock_get_docker_client)
    package_manager.migrate_packages(fake_db_for_migration, '/var/run/docker.sock')
    package_manager.get_docker_client.assert_has_calls([
        call('/var/run/docker.sock')], any_order=True)

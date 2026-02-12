#!/usr/bin/env python

import re
import unittest
from unittest.mock import Mock, call, patch, mock_open, MagicMock
import pytest

import sonic_package_manager
from sonic_package_manager.errors import *
from sonic_package_manager.version import Version
import json

@pytest.fixture(autouse=True)
def mock_run_command():
    with patch('sonic_package_manager.manager.run_command') as run_command:
        yield run_command


def test_installation_not_installed(package_manager):
    with patch('sonic_package_manager.manager.os.sync') as mock_sync:
        package_manager.install('test-package')
        package = package_manager.get_installed_package('test-package')
        assert package.installed
        assert package.entry.default_reference == '1.6.0'
        # Verify os.sync() is called after installation to ensure data persistence
        mock_sync.assert_called()


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
         patch('os.path.exists'), \
         patch('sonic_package_manager.manager.os.sync') as mock_sync:
        get_dir_mock.return_value = '/'
        package_manager.install('test-package')
        package_manager.docker.extract.assert_has_calls(
            [
                call(anything, '/cli/plugin.py', '/test-package.py'),
                call(anything, '/cli/plugin2.py', '/test-package_1.py'),
            ],
            any_order=True,
        )
        # Verify os.sync() is called after installation
        install_sync_count = mock_sync.call_count
        assert install_sync_count >= 1, "os.sync() should be called after installation"

        package_manager._set_feature_state = Mock()
        package_manager.uninstall('test-package', force=True)
        remove_mock.assert_has_calls(
            [
                call('/test-package.py'),
                call('/test-package_1.py'),
            ],
            any_order=True,
        )
        # Verify os.sync() is called after uninstallation
        uninstall_sync_count = mock_sync.call_count
        assert uninstall_sync_count > install_sync_count, "os.sync() should be called after uninstallation"


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


def test_manager_upgrade(package_manager, sonic_fs, mock_run_command):
    package_manager.install('test-package-6=1.5.0')
    package = package_manager.get_installed_package('test-package-6')

    with patch('sonic_package_manager.manager.os.sync') as mock_sync:
        package_manager.install('test-package-6=2.0.0')
        upgraded_package = package_manager.get_installed_package('test-package-6')
        assert upgraded_package.entry.version == Version.parse('2.0.0')
        assert upgraded_package.entry.default_reference == package.entry.default_reference
        # Verify os.sync() is called after upgrade to ensure data persistence
        mock_sync.assert_called()

    mock_run_command.assert_has_calls(
        [
            call(['systemctl', 'stop', 'test-package-6']),
            call(['systemctl', 'disable', 'test-package-6']),
            call(['systemctl', 'enable', 'test-package-6']),
            call(['systemctl', 'start', 'test-package-6']),
        ]
    )


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
        call(None, 'Azure/docker-test-4:1.5.0', name='test-package-4'),
        # test-package-5 1.5.0 was installed in fake_db_for_migration but the default
        # in current db is 1.9.0, assert that migration will install the newer version.
        call(None, 'Azure/docker-test-5:1.9.0', name='test-package-5'),
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


def test_create_package_manifest_default_manifest(package_manager):
    """Test case for creating a default manifest."""

    with patch('os.path.exists', return_value=False), \
         patch('os.mkdir'), \
         patch('builtins.open', new_callable=mock_open()), \
         patch('click.echo') as mock_echo:

        package_manager.create_package_manifest("default_manifest", from_json=None)

    mock_echo.assert_called_once_with("Default Manifest creation is not allowed by user")


def test_create_package_manifest_existing_package(package_manager):
    """Test case for creating a manifest with an existing package."""

    with patch('os.path.exists', side_effect=[False, True]), \
         patch('sonic_package_manager.main.PackageManager.is_installed', return_value=True), \
         patch('click.echo') as mock_echo:

        package_manager.create_package_manifest("test-package", from_json=None)

    mock_echo.assert_called_once_with("Error: A package with the same name test-package is already installed")


def test_create_package_manifest_existing_manifest(package_manager):
    """Test case for creating a manifest with an existing manifest file."""

    with patch('os.path.exists', return_value=True), \
         patch('click.echo') as mock_echo:

        package_manager.create_package_manifest("test-manifest", from_json=None)

    mock_echo.assert_called_once_with("Error: Manifest file 'test-manifest' already exists.")


def test_manifests_create_command(package_manager):
    with patch('click.echo') as mock_echo, \
         patch('os.path.exists') as mock_exists, \
         patch('os.mkdir'), \
         patch('builtins.open', new_callable=mock_open()), \
         patch('json.dump'), \
         patch('json.load') as mock_json_load, \
         patch('sonic_package_manager.manifest.Manifest.marshal') as mock_marshal, \
         patch('sonic_package_manager.manager.PackageManager.is_installed') as mock_is_installed, \
         patch('sonic_package_manager.manager.PackageManager.download_file') as mock_download_file:

        dummy_json = {"package": {"name": "test", "version": "1.0.0"}, "service": {"name": "test"}}
        # Setup mocks
        mock_exists.return_value = False
        mock_is_installed.return_value = False
        mock_download_file.return_value = True
        mock_marshal.return_value = None
        mock_json_load.return_value = dummy_json

        # Run the function
        package_manager.create_package_manifest("test_manifest", dummy_json)

        # Assertions
        mock_echo.assert_called_with("Manifest 'test_manifest' created successfully.")


def test_manifests_update_command(package_manager):
    with patch('click.echo') as mock_echo, \
         patch('os.path.exists') as mock_exists, \
         patch('os.mkdir'), \
         patch('builtins.open', new_callable=unittest.mock.mock_open), \
         patch('json.dump'), \
         patch('json.load') as mock_json_load, \
         patch('sonic_package_manager.manifest.Manifest.marshal') as mock_marshal, \
         patch('sonic_package_manager.manager.PackageManager.is_installed') as mock_is_installed, \
         patch('sonic_package_manager.manager.PackageManager.download_file') as mock_download_file:

        dummy_json = {"package": {"name": "test", "version": "2.0.0"}, "service": {"name": "test"}}
        # Setup mocks
        mock_exists.return_value = True
        mock_is_installed.return_value = True
        mock_download_file.return_value = True
        mock_marshal.return_value = None
        mock_json_load.return_value = dummy_json

        # Run the function
        package_manager.update_package_manifest("test_manifest", "dummy_json")

        # Assertions
        mock_echo.assert_called_with("Manifest 'test_manifest' updated successfully.")


def test_delete_package_manifest(package_manager):
    with patch('click.echo') as mock_echo, \
         patch('click.prompt') as mock_prompt, \
         patch('os.path.exists') as mock_exists, \
         patch('os.remove'):

        # Test case 1: deleting default manifest
        package_manager.delete_package_manifest("default_manifest")
        mock_echo.assert_called_with("Default Manifest deletion is not allowed")
        mock_echo.reset_mock()  # Reset the mock for the next test case

        # Test case 2: manifest file doesn't exist
        mock_exists.return_value = True
        mock_exists.side_effect = lambda x: False if x.endswith("test_manifest") else True
        package_manager.delete_package_manifest("test_manifest")
        mock_echo.assert_called_with("Error: Manifest file 'test_manifest' not found.")
        mock_echo.reset_mock()

        # Test case 3: user confirms deletion
        mock_exists.side_effect = lambda x: True if x.endswith("test_manifest") else False
        mock_prompt.return_value = "y"
        package_manager.delete_package_manifest("test_manifest")
        mock_echo.assert_called_with("Manifest 'test_manifest' deleted successfully.")
        mock_echo.reset_mock()

        # Test case 4: user cancels deletion
        mock_prompt.return_value = "n"
        package_manager.delete_package_manifest("test_manifest")
        mock_echo.assert_called_with("Deletion cancelled.")
        mock_echo.reset_mock()


def test_show_package_manifest(package_manager):
    with patch('click.echo') as mock_echo, \
         patch('os.path.exists') as mock_exists, \
         patch('builtins.open', unittest.mock.mock_open()), \
         patch('json.load') as mock_json_load:

        mock_exists.return_value = True
        mock_exists.side_effect = lambda x: True if x.endswith("test_manifest") else False

        dummy_json = {"package": {"name": "test", "version": "2.0.0"}, "service": {"name": "test"}}
        mock_json_load.return_value = dummy_json

        package_manager.show_package_manifest("test_manifest")
        mock_echo.assert_called_with(json.dumps(dummy_json, indent=4))


def test_list_package_manifest(package_manager):
    with patch('click.echo') as mock_echo, \
         patch('os.path.exists') as mock_exists, \
         patch('os.listdir') as mock_listdir:

        # Test case 1: no custom local manifest files found
        mock_exists.return_value = True
        mock_listdir.return_value = []
        package_manager.list_package_manifest()
        mock_echo.assert_called_with("No custom local manifest files found.")

        # Test case 2: custom local manifest files found
        mock_listdir.return_value = ["manifest1.json", "manifest2.json"]
        package_manager.list_package_manifest()
        mock_echo.assert_any_call("Custom Local Manifest files:")
        mock_echo.assert_any_call("- manifest1.json")
        mock_echo.assert_any_call("- manifest2.json")


def test_download_file_http(package_manager):
    fake_remote_url = "http://www.example.com/index.html"
    fake_local_path = "local_path"
    with patch("requests.get") as mock_requests_get:
        with patch("builtins.open", mock_open()) as mock_file:
            package_manager.download_file(fake_remote_url, fake_local_path)
    mock_requests_get.assert_called_once_with(fake_remote_url, stream=True)
    mock_file.assert_called_once_with("local_path", "wb")


def test_download_file_scp(package_manager):
    fake_remote_url = "scp://admin@10.x.x.x:/home/admin/sec_update.json"
    fake_local_path = "local_path"

    with patch("paramiko.SSHClient") as mock_ssh_client:
        with patch("scp.SCPClient"):
            with patch("getpass.getpass", return_value="test_password"):
                package_manager.download_file(fake_remote_url, fake_local_path)

    mock_ssh_client.assert_called_once()
    mock_ssh_client.return_value.set_missing_host_key_policy.assert_called_once()
    mock_ssh_client.return_value.connect.assert_called_once_with(
        "10.x.x.x",
        username="admin",
        password="test_password"
    )


def test_download_file_sftp(package_manager):
    fake_remote_url = "sftp://admin@10.x.x.x:/home/admin/sec_update.json"
    fake_local_path = "local_path"

    with patch("paramiko.SSHClient") as mock_ssh_client:
        with patch("paramiko.SFTPClient.from_transport"):
            with patch("getpass.getpass", return_value="test_password"):
                package_manager.download_file(fake_remote_url, fake_local_path)

    mock_ssh_client.assert_called_once()
    mock_ssh_client.return_value.set_missing_host_key_policy.assert_called_once()
    mock_ssh_client.return_value.connect.assert_called_once_with(
        "10.x.x.x",
        username="admin",
        password="test_password"
    )


def test_installation_from_file_no_tags(package_manager, mock_docker_api, sonic_fs):
    # Override the load function to return an image without tags
    def load_no_tags(filename):
        class Image:
            def __init__(self, id):
                self.id = id
                self.tags = []

            @property
            def attrs(self):
                return {'RepoTags': []}

        return Image(filename)

    mock_docker_api.load = MagicMock(side_effect=load_no_tags)

    sonic_fs.create_file('Azure/docker-test:1.6.0')
    package_manager.install(tarball='Azure/docker-test:1.6.0')

    # Verify the image was loaded
    mock_docker_api.load.assert_called_once_with('Azure/docker-test:1.6.0')

    # Get the package from the database and verify the tag was set to the image ID
    package = package_manager.database.get_package('test-package')
    assert package.docker_image_reference == 'Azure/docker-test:1.6.0'


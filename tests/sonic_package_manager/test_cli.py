#!/usr/bin/env python

from click.testing import CliRunner

from sonic_package_manager import main

from unittest.mock import patch, mock_open, MagicMock

MANIFEST_LOCATION = 'fake_manifest_location'
DMFILE_NAME = 'fake_dmfile_name'
DEFAUT_MANIFEST_NAME = 'fake_default_manifest_name'
LOCAL_JSON = 'fake_local_json'
sample_manifest_json = '{"package": {"name": "test", "version": "1.0.0"}, "service": {"name": "test"}}'
fake_manifest_name = 'test-manifest'
MANIFEST_CONTENT = '{"package": {"name": "test", "version": "1.0.0"}, "service": {"name": "test"}}'

def test_show_changelog(package_manager, fake_metadata_resolver):
    """ Test case for "sonic-package-manager package show changelog [NAME]" """

    runner = CliRunner()
    changelog = {
      "1.0.0": {
        "changes": ["Initial release"],
        "author": "Stepan Blyshchak",
        "email": "stepanb@nvidia.com",
        "date": "Mon, 25 May 2020 12:24:30 +0300"
      },
      "1.1.0": {
        "changes": [
          "Added functionality",
          "Bug fixes"
        ],
        "author": "Stepan Blyshchak",
        "email": "stepanb@nvidia.com",
        "date": "Fri, 23 Oct 2020 12:26:08 +0300"
      }
    }
    manifest = fake_metadata_resolver.metadata_store['Azure/docker-test']['1.6.0']['manifest']
    manifest['package']['changelog'] = changelog

    expected_output = """\
1.0.0:

    • Initial release

        Stepan Blyshchak (stepanb@nvidia.com) Mon, 25 May 2020 12:24:30 +0300

1.1.0:

    • Added functionality
    • Bug fixes

        Stepan Blyshchak (stepanb@nvidia.com) Fri, 23 Oct 2020 12:26:08 +0300

"""

    result = runner.invoke(main.show.commands['package'].commands['changelog'],
                           ['test-package'], obj=package_manager)

    assert result.exit_code == 0
    assert result.output == expected_output


def test_show_changelog_no_changelog(package_manager):
    """ Test case for "sonic-package-manager package show changelog [NAME]"
    when there is no changelog provided by package. """

    runner = CliRunner()
    result = runner.invoke(main.show.commands['package'].commands['changelog'], ['test-package'], obj=package_manager)

    assert result.exit_code == 1
    assert result.output == 'Failed to print package changelog: No changelog for package test-package\n'


def test_manifests_create_command_existing_manifest(package_manager):
    """ Test case for "sonic-package-manager manifests create" with an existing manifest file """

    runner = CliRunner()

    with patch('os.path.exists', side_effect=[True, False]), \
         patch('sonic_package_manager.main.PackageManager.is_installed', return_value=False), \
         patch('builtins.open', new_callable=mock_open()), \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.manifests.commands['create'],
                               ['test-manifest'],
                               input=sample_manifest_json,
                               obj=package_manager)

    assert 'Error: Manifest file \'test-manifest\' already exists.' in result.output
    assert result.exit_code == 0


def test_manifests_create_command_existing_package(package_manager):
    """ Test case for "sonic-package-manager manifests create" with an existing installed package """

    runner = CliRunner()

    with patch('os.path.exists', return_value=False), \
         patch('sonic_package_manager.main.PackageManager.is_installed', return_value=True), \
         patch('builtins.open', new_callable=mock_open()), \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.manifests.commands['create'],
                               ['test-manifest'],
                               input=sample_manifest_json,
                               obj=package_manager)

    assert 'Error: A package with the same name test-manifest is already installed' in result.output
    assert result.exit_code == 0


def test_manifests_update_command_error_handling(package_manager):

    runner = CliRunner()

    with patch('os.path.exists', return_value=False), \
         patch('builtins.open', new_callable=mock_open(read_data='{"key": "value"}')), \
         patch('json.load', side_effect=lambda x: MagicMock(return_value='{"key": "value"}')), \
         patch('json.dump'), \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.manifests.commands['update'],
                               ['non-existent-manifest', '--from-json', 'fake_json_path'],
                               obj=package_manager)
        assert 'Local Manifest file for non-existent-manifest does not exists to update\n' in result.output
        assert result.exit_code == 0


def test_manifests_delete_command_deletion_cancelled(package_manager):
    runner = CliRunner()

    with patch('os.path.exists', return_value=True), \
         patch('click.prompt', return_value='n'), \
         patch('os.remove') as mock_remove, \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.manifests.commands['delete'], ['test-manifest'], obj=package_manager)

        # Check if the cancellation message is present in the result output
        assert 'Deletion cancelled.' in result.output
        # Check if os.remove is not called when the deletion is cancelled
        assert not mock_remove.called


def test_manifests_list_command_no_manifests(package_manager):
    runner = CliRunner()

    with patch('os.listdir', return_value=[]), \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.manifests.commands['list'], [], obj=package_manager)

        # Check if the appropriate message is present in the result output
        assert 'No custom local manifest files found.\n' in result.output


def test_manifests_command():
    """ Test case for "sonic-package-manager manifests" """

    runner = CliRunner()
    result = runner.invoke(main.manifests)
    assert result.exit_code == 0


def test_manifests_create_command_exception(package_manager):
    """Test case for "sonic-package-manager manifests create" with an exception during manifest creation"""

    runner = CliRunner()

    with patch('sonic_package_manager.main.PackageManager.create_package_manifest',
               side_effect=Exception("Custom error")), \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.manifests.commands['create'], ['test-manifest'], obj=package_manager)

    assert 'Error: Manifest test-manifest creation failed - Custom error' in result.output
    assert result.exit_code == 0


def test_manifests_update_command_exception(package_manager):
    """Test case for 'sonic-package-manager manifests update' with an exception during manifest update"""

    runner = CliRunner()

    with patch('sonic_package_manager.main.PackageManager.update_package_manifest',
               side_effect=Exception("Custom error")), \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.manifests.commands['update'],
                               ['test-manifest', '--from-json', 'new_manifest.json'],
                               obj=package_manager)

    assert 'Error occurred while updating manifest \'test-manifest\': Custom error' in result.output
    assert result.exit_code == 0


def test_manifests_delete_command_exception(package_manager):
    """Test case for 'sonic-package-manager manifests delete' with an exception during manifest deletion"""

    runner = CliRunner()

    with patch('sonic_package_manager.main.PackageManager.delete_package_manifest',
               side_effect=Exception("Custom error")), \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.manifests.commands['delete'],
                               ['test-manifest'], obj=package_manager)

    assert "Error: Failed to delete manifest file 'test-manifest'. Custom error" in result.output
    assert result.exit_code == 0


def test_manifests_show_command_file_not_found(package_manager):
    """Test case for 'sonic-package-manager manifests show' with a non-existent manifest file"""

    runner = CliRunner()

    with patch('sonic_package_manager.main.PackageManager.show_package_manifest',
               side_effect=FileNotFoundError()), \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.manifests.commands['show'],
                               ['nonexistent_manifest.json'], obj=package_manager)

    assert "Manifest file 'nonexistent_manifest.json' not found." in result.output
    assert result.exit_code == 0


def test_install_with_local_manifest(package_manager):
    """Test case for 'install' command with use_local_manifest=True and name provided"""

    runner = CliRunner()

    with patch('os.path.exists', return_value=True), \
            patch('os.geteuid', return_value=0):
        result = runner.invoke(main.install,
                               ['package_name', '--use-local-manifest', '-y'],
                               obj=package_manager)

    assert 'name argument is not provided to use local manifest' in result.output
    assert result.exit_code == 0


def test_install_with_nonexistent_manifest(package_manager):
    """Test case for 'install' command with use_local_manifest=True and non-existent name provided"""

    runner = CliRunner()

    with patch('os.path.exists', return_value=False), \
            patch('os.geteuid', return_value=0):
        result = runner.invoke(
            main.install,
            ['package_name', '--use-local-manifest', '--name', 'nonexistent_manifest', '-y'],
            obj=package_manager)

    assert 'Local Manifest file for nonexistent_manifest does not exists to install' in result.output
    assert result.exit_code == 0


def test_update_command_exception(package_manager):
    """Test case for 'update' command with an exception during package update"""

    runner = CliRunner()

    with patch('sonic_package_manager.main.PackageManager.update',
               side_effect=Exception("Custom error")), \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.update, ['package_name'], obj=package_manager)

    assert 'Failed to update package package_name: Custom error' in result.output


def test_update_command_keyboard_interrupt(package_manager):
    """Test case for 'update' command with a keyboard interrupt"""

    runner = CliRunner()

    with patch('sonic_package_manager.main.PackageManager.update',
               side_effect=KeyboardInterrupt()), \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.update, ['package_name'], obj=package_manager)

    assert 'Operation canceled by user' in result.output

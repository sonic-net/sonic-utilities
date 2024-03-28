#!/usr/bin/env python

from click.testing import CliRunner

from sonic_package_manager import main

from unittest.mock import patch, Mock, mock_open, MagicMock
import os

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


def test_manifests_create_command(package_manager):

    runner = CliRunner()

    with patch('os.path.exists', return_value=False), \
         patch('os.mkdir'), \
         patch('os.path.isfile', return_value=False), \
         patch('shutil.copy'), \
         patch('sonic_package_manager.main.download_file') as mock_download_file, \
         patch('sonic_package_manager.main.Manifest.marshal'), \
         patch('builtins.open', new_callable=mock_open()) as mock_file, \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.manifests.commands['create'], ['test-manifest'], input=sample_manifest_json, obj=package_manager)

        assert 'Manifest \'test-manifest\' created successfully.' in result.output

def test_manifests_create_command_existing_manifest(package_manager):
    """ Test case for "sonic-package-manager manifests create" with an existing manifest file """

    runner = CliRunner()

    with patch('os.path.exists', side_effect=[True, False]), \
         patch('sonic_package_manager.main.PackageManager.is_installed', return_value=False), \
         patch('shutil.copy'), \
         patch('sonic_package_manager.main.download_file') as mock_download_file, \
         patch('sonic_package_manager.main.Manifest.marshal'), \
         patch('builtins.open', new_callable=mock_open()) as mock_file, \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.manifests.commands['create'], ['test-manifest'], input=sample_manifest_json, obj=package_manager)

    assert 'Error: Manifest file \'test-manifest\' already exists.' in result.output
    assert result.exit_code == 0

def test_manifests_create_command_existing_package(package_manager):
    """ Test case for "sonic-package-manager manifests create" with an existing installed package """

    runner = CliRunner()

    with patch('os.path.exists', return_value=False), \
         patch('sonic_package_manager.main.PackageManager.is_installed', return_value=True), \
         patch('shutil.copy'), \
         patch('sonic_package_manager.main.download_file') as mock_download_file, \
         patch('sonic_package_manager.main.Manifest.marshal'), \
         patch('builtins.open', new_callable=mock_open()) as mock_file, \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.manifests.commands['create'], ['test-manifest'], input=sample_manifest_json, obj=package_manager)

    assert 'Error: A package with the same name test-manifest is already installed' in result.output
    assert result.exit_code == 0



def test_manifests_update_command(package_manager):

    runner = CliRunner()

    with patch('os.path.exists', return_value=True), \
         patch('builtins.open', new_callable=mock_open(read_data='{"key": "value"}')), \
         patch('shutil.copy'), \
         patch('sonic_package_manager.main.download_file') as mock_download_file, \
         patch('sonic_package_manager.main.Manifest.marshal'), \
         patch('json.load', side_effect=lambda x: MagicMock(return_value='{"key": "value"}')), \
         patch('json.dump'), \
         patch('os.geteuid', return_value=0):
        
        result = runner.invoke(main.manifests.commands['update'], ['test-manifest', '--from-json', 'fake_json_path'], obj=package_manager)

        assert 'Manifest \'test-manifest\' updated successfully.' in result.output


def test_manifests_update_command_error_handling(package_manager):

    runner = CliRunner()

    with patch('os.path.exists', return_value=False), \
         patch('builtins.open', new_callable=mock_open(read_data='{"key": "value"}')), \
         patch('shutil.copy'), \
         patch('sonic_package_manager.main.download_file') as mock_download_file, \
         patch('sonic_package_manager.main.Manifest.marshal'), \
         patch('json.load', side_effect=lambda x: MagicMock(return_value='{"key": "value"}')), \
         patch('json.dump'), \
         patch('os.geteuid', return_value=0):
        
        result = runner.invoke(main.manifests.commands['update'], ['non-existent-manifest', '--from-json', 'fake_json_path'], obj=package_manager)
        assert 'Local Manifest file for non-existent-manifest does not exists to update' in result.output
        assert result.exit_code == 0

def test_manifests_update_command_download_failure(package_manager):
    """ Test case for "sonic-package-manager manifests update" with download failure """

    runner = CliRunner()

    with patch('os.path.exists', return_value=True), \
         patch('sonic_package_manager.main.PackageManager.is_installed', return_value=True), \
         patch('sonic_package_manager.main.download_file', side_effect=Exception('Download failed')), \
         patch('sonic_package_manager.main.Manifest.marshal'), \
         patch('builtins.open', new_callable=mock_open(read_data='{"key": "value"}')), \
         patch('shutil.copy'), \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.manifests.commands['update'], ['test-manifest', '--from-json', 'fake_json_path'], obj=package_manager)

    assert "Error occurred while updating manifest 'test-manifest': Download failed" in result.output


def test_manifests_update_nonexistent_file_command(package_manager):

    runner = CliRunner()

    # Test case: Updating a non-existent manifest file
    with patch('os.path.exists', return_value=False), \
         patch('sonic_package_manager.main.PackageManager.is_installed', return_value=False), \
         patch('shutil.copy'), \
         patch('sonic_package_manager.main.download_file') as mock_download_file, \
         patch('sonic_package_manager.main.Manifest.marshal'), \
         patch('json.load', side_effect=lambda x: MagicMock(return_value='{"key": "value"}')), \
         patch('json.dump'), \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.manifests.commands['update'], ['test-nonexistent-manifest', '--from-json', 'fake_json_path'], obj=package_manager)

        assert f"Local Manifest file for test-nonexistent-manifest does not exists to update" in result.output


def test_manifests_update_command_installed(package_manager):
    runner = CliRunner()

    with patch('os.path.exists', return_value=True), \
         patch('sonic_package_manager.main.PackageManager.is_installed', return_value=True), \
         patch('builtins.open', new_callable=mock_open(read_data='{"key": "value"}')), \
         patch('shutil.copy'), \
         patch('sonic_package_manager.main.download_file') as mock_download_file, \
         patch('sonic_package_manager.main.Manifest.marshal'), \
         patch('json.load', side_effect=lambda x: MagicMock(return_value='{"key": "value"}')), \
         patch('json.dump'), \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.manifests.commands['update'], ['test-manifest', '--from-json', 'fake_json_path'], obj=package_manager)

        assert 'Manifest \'test-manifest\' updated successfully.' in result.output

        # Assuming 'test-manifest' is the name and the package is already installed
        edit_name = 'test-manifest.edit'
        EDIT_FILE = os.path.join('/path/to/manifests', edit_name)

        # Check if the .edit file is created
        assert os.path.exists(EDIT_FILE)


def test_manifests_update_command_error(package_manager):
    runner = CliRunner()

    with patch('os.path.exists', return_value=True), \
         patch('sonic_package_manager.main.PackageManager.is_installed', return_value=False), \
         patch('builtins.open', new_callable=mock_open(read_data='{"key": "value"}')), \
         patch('shutil.copy'), \
         patch('sonic_package_manager.main.download_file', side_effect=Exception('Download failed')), \
         patch('sonic_package_manager.main.Manifest.marshal', side_effect=Exception('Validation failed')), \
         patch('json.load', side_effect=lambda x: MagicMock(return_value='{"key": "value"}')), \
         patch('json.dump'), \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.manifests.commands['update'], ['test-manifest', '--from-json', 'fake_json_path'], obj=package_manager)

        # Check if the error message is present in the result output
        assert 'Error occurred while updating manifest \'test-manifest\': Download failed' in result.output


def test_manifests_delete_command_not_found(package_manager):
    runner = CliRunner()

    with patch('os.path.exists', return_value=False), \
         patch('click.prompt', return_value='n'), \
         patch('os.remove') as mock_remove, \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.manifests.commands['delete'], ['test-manifest'], obj=package_manager)

        # Check if the error message is present in the result output
        assert 'Error: Manifest file \'test-manifest\' not found.' in result.output
        # Check if os.remove is not called when the manifest file is not found
        assert not mock_remove.called

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


def test_manifests_delete_command_failed_deletion(package_manager):
    runner = CliRunner()

    with patch('os.path.exists', return_value=True), \
         patch('click.prompt', return_value='y'), \
         patch('os.remove', side_effect=Exception('Deletion failed')), \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.manifests.commands['delete'], ['test-manifest'], obj=package_manager)

        # Check if the failed deletion error message is present in the result output
        assert 'Error: Failed to delete manifest file \'test-manifest\'. Deletion failed' in result.output


def test_manifests_delete_command(package_manager):

    runner = CliRunner()

    with patch('os.path.exists', return_value=True), \
         patch('os.remove'), \
         patch('os.path.join', return_value='fake_manifest_file_path'), \
         patch('click.prompt', return_value='y'), \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.manifests.commands['delete'], [fake_manifest_name], obj=package_manager)

        assert 'Manifest \'test-manifest\' deleted successfully.' in result.output


def test_manifests_list_command(package_manager):

    runner = CliRunner()

    with patch('os.listdir', return_value=['test-manifest1', 'test-manifest2']), \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.manifests.commands['list'], obj=package_manager)

        assert 'Custom Local Manifest files:' in result.output
        assert '- test-manifest1' in result.output
        assert '- test-manifest2' in result.output

def test_manifests_list_command_no_manifests(package_manager):
    runner = CliRunner()

    with patch('os.listdir', return_value=[]), \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.manifests.commands['list'], [], obj=package_manager)

        # Check if the appropriate message is present in the result output
        assert 'No custom local manifest files found.' in result.output


def test_manifests_show_command(package_manager):

    runner = CliRunner()

    with patch('builtins.open', mock_open(read_data=MANIFEST_CONTENT)), \
         patch('os.path.exists', return_value=True), \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.manifests.commands['show'], ['test-manifest'], obj=package_manager)

        assert 'Manifest file: test-manifest' in result.output
        assert '"package": {' in result.output
        assert '"name": "test"' in result.output
        assert '"version": "1.0.0"' in result.output
        assert '"service": {' in result.output
        assert '"name": "test"' in result.output

def test_manifests_show_command_file_not_found(package_manager):
    runner = CliRunner()

    with patch('os.path.exists', return_value=False), \
         patch('os.geteuid', return_value=0):

        result = runner.invoke(main.manifests.commands['show'], ['nonexistent-manifest'], obj=package_manager)

        # Check if the appropriate error message is present in the result output
        assert 'Manifest file \'nonexistent-manifest\' not found.' in result.output


def test_download_file():
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Set up a fake remote file and local path
        fake_remote_path = "remote_path"
        fake_local_path = "local_path"

        # Mock parse_url to return SCP information
        with patch("sonic_package_manager.main.parse_url", return_value=("test_user", None, "test_host", fake_remote_path)):
            # Mock SSHClient and SFTP
            with patch("paramiko.SSHClient") as mock_ssh_client, patch("paramiko.SFTP") as mock_sftp:
                # Mock getpass to return a test password
                with patch("getpass.getpass", return_value="test_password"):
                    # Mock os.path.exists to simulate the remote file existence
                    with patch("os.path.exists", return_value=True):
                        # Mock open to simulate writing to a local file
                        with patch("builtins.open", mock_open()) as mock_file:
                            main.download_file(f"scp://{fake_remote_path}", fake_local_path)

        # Assertions
        mock_ssh_client.assert_called_once()
        mock_ssh_client().set_missing_host_key_policy.assert_called_once()
        mock_ssh_client().connect.assert_called_once_with("test_host", username="test_user", password="test_password")
        mock_ssh_client().close.assert_called_once()

    # Additional assertions based on your specific logic...

    # Assertions for HTTP scenario
    with runner.isolated_filesystem():
        fake_remote_url = "http://example.com/remote_file"
        fake_local_path = "local_path"

        with patch("sonic_package_manager.main.parse_url", return_value=(None, None, "example.com", "/remote_file")):
            with patch("requests.get") as mock_requests_get:
                with patch("builtins.open", mock_open()) as mock_file:
                    main.download_file(fake_remote_url, fake_local_path)

        mock_requests_get.assert_called_once_with(fake_remote_url)
        mock_file.assert_called_once_with("local_path", "wb")

    # Assertions for local file scenario
    with runner.isolated_filesystem():
        fake_local_file = "local_file"
        fake_local_path = "local_path"

        with patch("sonic_package_manager.main.parse_url", return_value=(None, None, None, "/local_file")):
            with patch("os.path.exists", return_value=True):
                with patch("shutil.copy") as mock_shutil_copy:
                	main.download_file(fake_local_file, fake_local_path)

        mock_shutil_copy.assert_called_once_with("/local_file", "local_path")


def test_download_file_error(capsys):
    runner = CliRunner()

    # Mock requests.get to simulate an exception during HTTP download
    with runner.isolated_filesystem():
        fake_remote_url = "http://example.com/remote_file"
        fake_local_path = "local_path"

        with patch("sonic_package_manager.main.parse_url", return_value=(None, None, "example.com", "/remote_file")):
            with patch("requests.get", side_effect=requests.exceptions.RequestException("Download failed")) as mock_requests_get:
                with patch("builtins.open", mock_open()) as mock_file:
                    main.download_file(fake_remote_url, fake_local_path)

        mock_requests_get.assert_called_once_with(fake_remote_url)
        mock_file.assert_not_called()  # Ensure that file is not opened in case of exception
        #assert "Download error Download failed" in capsys.readouterr().err  # Adjust this line based on your output logic
        out, err = capsys.readouterr()
        assert "Image file not found on remote machine. Aborting..." in out
        assert "Download error Download failed" in out


def test_manifests_command():
    """ Test case for "sonic-package-manager manifests" """

    runner = CliRunner()
    result = runner.invoke(main.manifests)
    assert result.exit_code == 0


def test_show_package_manifest(package_manager):
    """ Test case for sonic-package-manager show package manifest """

    runner = CliRunner()
    result = runner.invoke(main.show.commands['package'].commands['manifest'], ['test-package'], obj=package_manager)

    print("result:===={}".format(result.output))
    assert result.exit_code == 0


def test_show_manifest_error_handling(package_manager):
    """ Test case for error handling for sonic-package-manager show package manifest """

    runner = CliRunner()
    result = runner.invoke(main.show.commands['package'].commands['manifest'], ['invalid-package'], obj=package_manager)

    print("result:===={}".format(result.output))
    assert result.exit_code != 0
    assert 'Failed to print manifest' in result.output

from sonic_package_manager.main import parse_url
def test_download_file_with_scp_url():
    url = "scp://user:pass@hostname:/path/to/file"

    with patch('sonic_package_manager.main.parse_url', return_value=('user', 'pass', 'hostname', '/path/to/file')):
        # Call the function that uses parse_url
        username, password, hostname, remote_path = parse_url(url)

    # Now, you can assert the values or perform other checks
    assert username == 'user'
    assert password == 'pass'
    assert hostname == 'hostname'
    assert remote_path == '/path/to/file'


def test_download_file_with_http_url():
    url = "http://example.com/path/to/file"

    with patch('sonic_package_manager.main.parse_url', return_value=(None, None, 'example.com', '/path/to/file')):
        # Call the function that uses parse_url
        username, password, hostname, remote_path = parse_url(url)

    # Now, you can assert the values or perform other checks
    assert username is None
    assert password is None
    assert hostname == 'example.com'
    assert remote_path == '/path/to/file'

def test_download_file_with_local_path():
    url = "/path/to/local/file"

    with patch('sonic_package_manager.main.parse_url', return_value=(None, None, None, '/path/to/local/file')):
        # Call the function that uses parse_url
        username, password, hostname, remote_path = parse_url(url)

    # Now, you can assert the values or perform other checks
    assert username is None
    assert password is None
    assert hostname is None
    assert remote_path == '/path/to/local/file'


from urllib.parse import urlparse

def test_parse_url_unsupported_scheme():
    url = "ftp://example.com/some/file"

    with patch('sonic_package_manager.main.urlparse', return_value=urlparse(url)):
        try:
            # Call the function that uses parse_url with an unsupported scheme
            parse_url(url)
        except ValueError as e:
            # Assert that the ValueError is raised with the expected message
            assert str(e) == "Unsupported URL scheme"
        else:
            # If no exception is raised, fail the test
            assert False, "Expected ValueError but no exception was raised"


from sonic_package_manager.main import validate_url_or_abort
import requests

def test_validate_url_or_abort_successful():
    url = "http://example.com/some/file"

    with patch('sonic_package_manager.main.requests.head') as mock_head:
        # Simulate a successful HTTP HEAD request
        mock_head.return_value.status_code = 200

        # Call the function with the URL
        validate_url_or_abort(url)

        # Assert that the print statements are not called
        mock_head.assert_called_once_with(url)

def test_validate_url_or_abort_request_exception():
    url = "http://example.com/some/file"

    with patch('sonic_package_manager.main.requests.head') as mock_head, \
         patch('builtins.print') as mock_print:
        # Simulate a requests exception
        mock_head.side_effect = requests.exceptions.RequestException()

        # Call the function with the URL
        validate_url_or_abort(url)

        # Assert that the appropriate print statement is called
        mock_head.assert_called_once_with(url)
        mock_print.assert_called_once_with("Did not receive a response from remote machine. Aborting...")

def test_validate_url_or_abort_4xx_response():
    url = "http://example.com/some/file"

    with patch('sonic_package_manager.main.requests.head') as mock_head, \
         patch('builtins.print') as mock_print:
        # Simulate a 4xx response code
        mock_head.return_value.status_code = 404

        # Call the function with the URL
        validate_url_or_abort(url)

        # Assert that the appropriate print statement is called
        mock_head.assert_called_once_with(url)
        mock_print.assert_called_once_with("Image file not found on remote machine. Aborting...")



def test_install_with_local_manifest(package_manager, monkeypatch):
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Create a fake local manifest file and set use_local_manifest to True
        fake_name = "fake_manifest"
        fake_repo = "fake_repo"
        fake_local_path = "local_path"
        fake_local_manifest_content = '{"package": {"name": "test_package"}}'

        with open(fake_local_path, 'w') as fake_manifest_file:
            fake_manifest_file.write(fake_local_manifest_content)

        monkeypatch.setattr('click.confirm', lambda *args, **kwargs: True)

        with patch('os.geteuid', return_value=0):
            # Run the install command with use_local_manifest and name arguments
            result = runner.invoke(main.install, ['--from-repository', fake_repo, '--use-local-manifest', '--name', fake_name], obj=package_manager)

        print("result:{}".format(result.output))
        # Assertions
        assert result.exit_code == 0
        assert f'Local Manifest file for {fake_name} does not exists to install' in result.output
        #assert f'name argument is not provided to use local manifest' in result.output

        with patch('os.geteuid', return_value=0):
            ## Run the install command with use_local_manifest, name, and non-existent local manifest
            result = runner.invoke(main.install, ['--from-repository', fake_name, '--use-local-manifest'])

        print("result:{}".format(result.output))
        ## Assertions
        assert result.exit_code == 0
        assert f'name argument is not provided to use local manifest' in result.output




def test_update(package_manager, monkeypatch):
    runner = CliRunner()

    with runner.isolated_filesystem():
        fake_package_name = "fake_package"
        fake_force = True
        fake_yes = False

        # Mock PackageManager.update method
        with patch.object(package_manager, 'update') as mock_update:
            # Use monkeypatch to bypass the click.confirm prompt
            monkeypatch.setattr('click.confirm', lambda *args, **kwargs: True)

            with patch('os.geteuid', return_value=0):
            # Run the update command with arguments
                result = runner.invoke(main.update, [fake_package_name, '--force', '--yes'], obj=package_manager)

        print("result:{}".format(result.output))
        ## Assertions
        mock_update.assert_called_once_with(fake_package_name, fake_force)
        assert result.exit_code == 0


class SomeUpdateError(Exception):
    pass

def test_update_error(package_manager, monkeypatch):
    runner = CliRunner()

    with runner.isolated_filesystem():
        fake_package_name = "fake_package"
        fake_force = True
        fake_yes = False

        # Mock PackageManager.update method to raise an exception
        with patch.object(package_manager, 'update', side_effect=SomeUpdateError("Update failed")) as mock_update:
            # Use monkeypatch to bypass the click.confirm prompt
            monkeypatch.setattr('click.confirm', lambda *args, **kwargs: True)

            with patch('os.geteuid', return_value=0):
                # Run the update command with arguments
                result = runner.invoke(main.update, [fake_package_name, '--force', '--yes'], obj=package_manager)

        # Assertions
        mock_update.assert_called_once_with(fake_package_name, fake_force)
        assert result.exit_code == 1
        assert "Failed to update package fake_package: Update failed" in result.output




#!/usr/bin/env python

import functools
import json
import os
import sys
import typing

import click
import click_log
import tabulate
from urllib.parse import urlparse
import paramiko
import requests
import getpass
import shutil
from natsort import natsorted

from sonic_package_manager.database import PackageEntry, PackageDatabase
from sonic_package_manager.errors import PackageManagerError
from sonic_package_manager.logger import log
from sonic_package_manager.manager import PackageManager
from sonic_package_manager.manifest import Manifest, DEFAULT_MANIFEST, MANIFEST_LOCATION, DEFAUT_MANIFEST_NAME, DMFILE_NAME
LOCAL_TARBALL_PATH="/tmp/local_tarball.gz"
LOCAL_JSON="/tmp/local_json"

BULLET_UC = '\u2022'


def exit_cli(*args, **kwargs):
    """ Print a message and exit with rc 1. """

    click.secho(*args, **kwargs)
    sys.exit(1)


def show_help(ctx):
    """ Show  help message and exit process successfully. """

    click.echo(ctx.get_help())
    ctx.exit(0)


def root_privileges_required(func: typing.Callable) -> typing.Callable:
    """ Decorates a function, so that the function is invoked
    only if the user is root. """

    @functools.wraps(func)
    def wrapped_function(*args, **kwargs):
        """ Wrapper around func. """

        if os.geteuid() != 0:
            exit_cli('Root privileges required for this operation', fg='red')

        return func(*args, **kwargs)

    wrapped_function.__doc__ += '\n\n NOTE: This command requires elevated (root) privileges to run.'

    return wrapped_function


def add_options(options):
    """ Decorator to append options from
    input list to command. """

    def _add_options(func):
        for option in reversed(options):
            func = option(func)
        return func

    return _add_options


class MutuallyExclusiveOption(click.Option):
    """ This options type is extended with 'mutually_exclusive'
    parameter which makes CLI to check if several options are now
    used together in single command. """

    def __init__(self, *args, **kwargs):
        self.mutually_exclusive = set(kwargs.pop('mutually_exclusive', []))
        help_string = kwargs.get('help', '')
        if self.mutually_exclusive:
            ex_str = ', '.join(self.mutually_exclusive)
            kwargs['help'] = f'{help_string} ' \
                             f'NOTE: This argument is mutually ' \
                             f'exclusive with arguments: [{ex_str}].'
        super().__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        if self.name in opts and opts[self.name] is not None:
            for opt_name in self.mutually_exclusive.intersection(opts):
                if opts[opt_name] is None:
                    continue

                raise click.UsageError(f'Illegal usage: {self.name} is mutually '
                                       f'exclusive with arguments '
                                       f'{", ".join(self.mutually_exclusive)}.')

        return super().handle_parse_result(ctx, opts, args)


PACKAGE_SOURCE_OPTIONS = [
    click.option('--from-repository',
                 help='Fetch package directly from image registry repository.',
                 cls=MutuallyExclusiveOption,
                 mutually_exclusive=['from_tarball', 'package_expr']),
    click.option('--from-tarball',
                 type=str,
                 help='Fetch package from saved image tarball from local/scp/sftp/http',
                 cls=MutuallyExclusiveOption,
                 mutually_exclusive=['from_repository', 'package_expr']),
    click.argument('package-expr',
                   type=str,
                   required=False)
]


PACKAGE_COMMON_INSTALL_OPTIONS = [
    click.option('--skip-host-plugins',
                 is_flag=True,
                 help='Do not install host OS plugins provided by the package (CLI, etc). '
                 'NOTE: In case when package host OS plugins are set as mandatory in '
                 'package manifest this option will fail the installation.')
]


PACKAGE_COMMON_OPERATION_OPTIONS = [
    click.option('-f', '--force',
                 is_flag=True,
                 help='Force operation by ignoring package dependency tree and package manifest validation failures.'),
    click.option('-y', '--yes',
                 is_flag=True,
                 help='Automatically answer yes on prompts.'),
    click_log.simple_verbosity_option(log, help='Either CRITICAL, ERROR, WARNING, INFO or DEBUG. Default is INFO.'),
]


def get_package_status(package: PackageEntry):
    """ Returns the installation status message for package. """

    if package.built_in:
        return 'Built-In'
    elif package.installed:
        return 'Installed'
    else:
        return 'Not Installed'


@click.group()
@click.pass_context
def cli(ctx):
    """ SONiC Package Manager """

    ctx.obj = PackageManager.get_manager()


@cli.group()
@click.pass_context
def repository(ctx):
    """ Repository management commands. """

    pass


@cli.group()
@click.pass_context
def manifests(ctx):
    """ Custom local Manifest management commands. """
    
    pass

@cli.group()
@click.pass_context
def show(ctx):
    """ Package manager show commands. """

    pass


@show.group()
@click.pass_context
def package(ctx):
    """ Package show commands. """

    pass


@cli.command()
@click.pass_context
def list(ctx):
    """ List available packages. """

    table_header = ['Name', 'Repository', 'Description', 'Version', 'Status']
    table_body = []

    manager: PackageManager = ctx.obj

    try:
        for package in natsorted(manager.database):
            repository = package.repository or 'N/A'
            version = package.version or 'N/A'
            description = package.description or 'N/A'
            status = get_package_status(package)

            table_body.append([
                package.name,
                repository,
                description,
                version,
                status
            ])

        click.echo(tabulate.tabulate(table_body, table_header))
    except PackageManagerError as err:
        exit_cli(f'Failed to list repositories: {err}', fg='red')


@package.command()
@add_options(PACKAGE_SOURCE_OPTIONS)
@click.pass_context
def manifest(ctx,
             package_expr,
             from_repository,
             from_tarball):
    """ Show package manifest. """

    manager: PackageManager = ctx.obj

    try:
        if from_tarball:
            #Download the tar file from local/scp/sftp/http
            download_file(from_tarball, LOCAL_TARBALL_PATH)
            from_tarball = LOCAL_TARBALL_PATH

        source = manager.get_package_source(package_expr,
                                            from_repository,
                                            from_tarball)
        package = source.get_package()
        click.echo(json.dumps(package.manifest.unmarshal(), indent=4))
    except Exception as err:
        exit_cli(f'Failed to print manifest: {err}', fg='red')


@package.command()
@click.argument('name')
@click.option('--all', is_flag=True, help='Show all available tags in repository.')
@click.option('--plain', is_flag=True, help='Plain output.')
@click.pass_context
def versions(ctx, name, all, plain):
    """ Show available versions. """

    try:
        manager: PackageManager = ctx.obj
        versions = manager.get_package_available_versions(name, all)
        for version in versions:
            if not plain:
                click.secho(f'{BULLET_UC} ', bold=True, fg='green', nl=False)
            click.secho(f'{version}')
    except Exception as err:
        exit_cli(f'Failed to get package versions for {name}: {err}', fg='red')


@package.command()
@add_options(PACKAGE_SOURCE_OPTIONS)
@click.pass_context
def changelog(ctx,
              package_expr,
              from_repository,
              from_tarball):
    """ Show package changelog. """

    manager: PackageManager = ctx.obj

    try:
        if from_tarball:
            #Download the tar file from local/scp/sftp/http
            download_file(from_tarball, LOCAL_TARBALL_PATH)
            from_tarball = LOCAL_TARBALL_PATH

        source = manager.get_package_source(package_expr,
                                            from_repository,
                                            from_tarball)
        package = source.get_package()
        changelog = package.manifest['package']['changelog']

        if not changelog:
            raise PackageManagerError(f'No changelog for package {package.name}')

        for version, entry in changelog.items():
            author = entry.get('author') or 'N/A'
            email = entry.get('email') or 'N/A'
            changes = entry.get('changes') or []
            date = entry.get('date') or 'N/A'
            click.secho(f'{version}:\n', fg='green', bold=True)
            for line in changes:
                click.secho(f'    {BULLET_UC} {line}', bold=True)
            click.secho(f'\n        {author} '
                        f'({email}) {date}', fg='green', bold=True)
            click.secho('')

    except Exception as err:
        exit_cli(f'Failed to print package changelog: {err}', fg='red')



@manifests.command('create')
@click.pass_context
@click.argument('name', type=click.Path())
@click.option('--from-json', type=str, help='specify manifest json file')
@root_privileges_required
def create(ctx, name, from_json):
    """Create a new custom local manifest file."""

    #Validation checks
    manager: PackageManager = ctx.obj
    if manager.is_installed(name):
        click.echo("Error: A package with the same name {} is already installed".format(name))
        return
    MFILE_NAME = os.path.join(MANIFEST_LOCATION, name)
    if os.path.exists(MFILE_NAME):
        click.echo("Error: Manifest file '{}' already exists.".format(name))
        return
    
    #Creation of default  manifest file in case the file does not exist
    if not os.path.exists(MANIFEST_LOCATION):
        os.mkdir(MANIFEST_LOCATION)
    if not os.path.exists(DMFILE_NAME):
        with open(DMFILE_NAME, 'w') as file:
            json.dump(DEFAULT_MANIFEST, file, indent=4)
        #click.echo(f"Manifest '{DEFAUT_MANIFEST_NAME}' created now.")

    
    #Create the manifest file in centralized location
    #Download the json file from scp/sftp/http to local_json_file
    try: 
        if from_json:
            download_file(from_json, LOCAL_JSON)
            from_json = LOCAL_JSON
            data = {}
            with open(from_json, 'r') as file:
                data = json.load(file)
            #Validate with manifest scheme
            Manifest.marshal(data)
            
            #Make sure the 'name' is overwritten into the dict
            data['package']['name'] = name
            data['service']['name'] = name

            with open(MFILE_NAME, 'w') as file:
                json.dump(data, file, indent=4)
        else:
            shutil.copy(DMFILE_NAME, MFILE_NAME)
        click.echo(f"Manifest '{name}' created successfully.")
    except Exception as e:
        click.echo("Error: Manifest {} creation failed - {}".format(name, str(e)))
        return
        


#At the end of sonic-package-manager install, a new manifest file is created with the name.
#At the end of sonic-package-manager uninstall name, this manifest file name and name.edit will be deleted.
#At the end of sonic-package-manager update, we need to mv maniests name.edit to name in case of success, else keep it as such.
#So during sonic-package-manager update, we could take old package from name and new package from edit and at the end, follow 3rd point
@manifests.command('update')
@click.pass_context
@click.argument('name', type=click.Path())
@click.option('--from-json', type=str, required=True)
#@click.argument('--from-json', type=str, help='Specify Manifest json file')
@root_privileges_required
def update(ctx, name, from_json):
    """Update an existing custom local manifest file with new one."""

    manager: PackageManager = ctx.obj
    ORG_FILE = os.path.join(MANIFEST_LOCATION, name)
    if not os.path.exists(ORG_FILE):
        click.echo(f'Local Manifest file for {name} does not exists to update')
        return
    try:
        #download json file from remote/local path
        download_file(from_json, LOCAL_JSON)
        from_json = LOCAL_JSON
        with open(from_json, 'r') as file:
            data = json.load(file)

        #Validate with manifest scheme
        Manifest.marshal(data)
        
        #Make sure the 'name' is overwritten into the dict
        data['package']['name'] = name
        data['service']['name'] = name

        if manager.is_installed(name):
            edit_name = name + '.edit'
            EDIT_FILE = os.path.join(MANIFEST_LOCATION, edit_name)
            with open(EDIT_FILE, 'w') as edit_file:
                json.dump(data, edit_file, indent=4)
            click.echo(f"Manifest '{name}' updated successfully.")
        else:
            #If package is not installed, 
            ## update the name file directly
            with open(ORG_FILE, 'w') as orig_file:
                json.dump(data, orig_file, indent=4)
            click.echo(f"Manifest '{name}' updated successfully.")
    except Exception as e:
        click.echo(f"Error occurred while updating manifest '{name}': {e}")
        return


@manifests.command('delete')
@click.pass_context
@click.argument('name', type=click.Path())
@root_privileges_required
def delete(ctx, name):
    """Delete a custom local manifest file."""
    # Check if the manifest file exists
    mfile_name = "{}{}".format(MANIFEST_LOCATION, name)
    if not os.path.exists(mfile_name):
        click.echo("Error: Manifest file '{}' not found.".format(name))
        return

    try:
        # Confirm deletion with user input
        confirm = click.prompt("Are you sure you want to delete the manifest file '{}'? (y/n)".format(name), type=str)
        if confirm.lower() == 'y':
            os.remove(mfile_name)
            click.echo("Manifest '{}' deleted successfully.".format(name))
        else:
            click.echo("Deletion cancelled.")
    except Exception as e:
        click.echo("Error: Failed to delete manifest file '{}'. {}".format(name, e))


@manifests.command('show')
@click.pass_context
@click.argument('name', type=click.Path())
@root_privileges_required
def show_manifest(ctx, name):
    """Show the contents of custom local manifest file."""
    mfile_name = "{}{}".format(MANIFEST_LOCATION, name)
    edit_file_name = "{}.edit".format(mfile_name)
    try:
        if os.path.exists(edit_file_name):
            mfile_name = edit_file_name
        with open(mfile_name, 'r') as file:
            data = json.load(file)
            click.echo("Manifest file: {}".format(name))
            click.echo(json.dumps(data, indent=4))
    except FileNotFoundError:
        click.echo("Manifest file '{}' not found.".format(name))

@manifests.command('list')
@click.pass_context
@root_privileges_required
def list_manifests(ctx):
    """List all custom local manifest files."""
    # Get all files in the manifest location
    manifest_files = os.listdir(MANIFEST_LOCATION)
    if not manifest_files:
        click.echo("No custom local manifest files found.")
    else:
        click.echo("Custom Local Manifest files:")
        for file in manifest_files:
            click.echo("- {}".format(file))


@repository.command()
@click.argument('name', type=str)
@click.argument('repository', type=str)
@click.option('--default-reference', type=str, help='Default installation reference. Can be a tag or sha256 digest in repository.')
@click.option('--description', type=str, help='Optional package entry description.')
@click.pass_context
@root_privileges_required
def add(ctx, name, repository, default_reference, description):
    """ Add a new repository to database. """

    manager: PackageManager = ctx.obj

    try:
        manager.add_repository(name,
                               repository,
                               description=description,
                               default_reference=default_reference)
    except Exception as err:
        exit_cli(f'Failed to add repository {name}: {err}', fg='red')


@repository.command()
@click.argument("name")
@click.pass_context
@root_privileges_required
def remove(ctx, name):
    """ Remove repository from database. """

    manager: PackageManager = ctx.obj

    try:
        manager.remove_repository(name)
    except Exception as err:
        exit_cli(f'Failed to remove repository {name}: {err}', fg='red')


def parse_url(url):
    # Parse information from URL
    parsed_url = urlparse(url)
    if parsed_url.scheme == "scp" or parsed_url.scheme == "sftp":
        return parsed_url.username, parsed_url.password, parsed_url.hostname, parsed_url.path
    elif parsed_url.scheme == "http":
        return None, None, parsed_url.netloc, parsed_url.path
    elif not parsed_url.scheme:  # No scheme indicates a local file path
        return None, None, None, parsed_url.path
    else:
        raise ValueError("Unsupported URL scheme")

def validate_url_or_abort(url):
    # Attempt to retrieve HTTP response code
    try:
        response = requests.head(url)
        response_code = response.status_code
    except requests.exceptions.RequestException as err:
        response_code = None

    if not response_code:
        print("Did not receive a response from remote machine. Aborting...")
        return
    else:
        # Check for a 4xx response code which indicates a nonexistent URL
        if str(response_code).startswith('4'):
            print("Image file not found on remote machine. Aborting...")
            return

def download_file(url, local_path):
    # Parse information from the URL
    username, password, hostname, remote_path = parse_url(url)

    if username is not None:
        # If password is not provided, prompt the user for it securely
        if password is None:
            password = getpass.getpass(prompt=f"Enter password for {username}@{hostname}: ")

        # Create an SSH client for SCP or SFTP
        client = paramiko.SSHClient()
        # Automatically add the server's host key (this is insecure and should be handled differently in production)
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # Connect to the SSH server
            client.connect(hostname, username=username, password=password)

            # Open an SCP channel for SCP or an SFTP channel for SFTP
            with client.open_sftp() as sftp:
                # Download the file
                sftp.get(remote_path, local_path)

        finally:
            # Close the SSH connection
            client.close()
    elif hostname:
        # Download using HTTP for URLs without credentials
        validate_url_or_abort(url)
        try:
            response = requests.get(url)
            with open(local_path, 'wb') as f:
                f.write(response.content)
        except requests.exceptions.RequestException as e:
            print("Download error", e)
            return
    else:
        if os.path.exists(remote_path):
            shutil.copy(remote_path, local_path)
        else:
            print(f"Error: Source file '{remote_path}' does not exist.")


@cli.command()
@click.option('--enable',
              is_flag=True,
              default=None,
              help='Set the default state of the feature to enabled '
                   'and enable feature right after installation. '
                   'NOTE: user needs to execute "config save -y" to make '
                   'this setting persistent.')
@click.option('--set-owner',
              type=click.Choice(['local', 'kube']),
              default=None,
              help='Default owner configuration setting for a feature.')
@click.option('--allow-downgrade',
              is_flag=True,
              default=None,
              help='Allow package downgrade. By default an attempt to downgrade the package '
              'will result in a failure since downgrade might not be supported by the package, '
              'thus requires explicit request from the user.')
@click.option('--use-local-manifest',
              is_flag=True,
              default=None,
              help='Use locally created custom manifest file ')
@click.option('--name',
                 type=str,
                 help='custom name for the package')
@add_options(PACKAGE_SOURCE_OPTIONS)
@add_options(PACKAGE_COMMON_OPERATION_OPTIONS)
@add_options(PACKAGE_COMMON_INSTALL_OPTIONS)
@click.pass_context
@root_privileges_required
def install(ctx,
            package_expr,
            from_repository,
            from_tarball,
            force,
            yes,
            enable,
            set_owner,
            skip_host_plugins,
            allow_downgrade,
            use_local_manifest,
            name):
    """ Install/Upgrade package using [PACKAGE_EXPR] in format "<name>[=<version>|@<reference>]".

    The repository to pull the package from is resolved by lookup in package database,
    thus the package has to be added via "sonic-package-manager repository add" command.

    In case when [PACKAGE_EXPR] is a package name "<name>" this command will install or upgrade
    to a version referenced by "default-reference" in package database. """

    manager: PackageManager = ctx.obj

    package_source = package_expr or from_repository or from_tarball
    if not package_source:
        exit_cli('Package source is not specified', fg='red')

    if not yes and not force:
        click.confirm(f'{package_source} is going to be installed, '
                      f'continue?', abort=True, show_default=True)

    install_opts = {
        'force': force,
        'skip_host_plugins': skip_host_plugins,
    }
    if enable is not None:
        install_opts['enable'] = enable
    if set_owner is not None:
        install_opts['default_owner'] = set_owner
    if allow_downgrade is not None:
        install_opts['allow_downgrade'] = allow_downgrade

    if use_local_manifest:
        if not name:
            click.echo(f'name argument is not provided to use local manifest')
            return
        ORG_FILE = os.path.join(MANIFEST_LOCATION, name)
        if not os.path.exists(ORG_FILE):
            click.echo(f'Local Manifest file for {name} does not exists to install')
            return
        
    if from_tarball:
        #Download the tar file from local/scp/sftp/http
        download_file(from_tarball, LOCAL_TARBALL_PATH)
        from_tarball = LOCAL_TARBALL_PATH

    try:
        manager.install(package_expr,
                        from_repository,
                        from_tarball,
                        use_local_manifest,
                        name,
                        **install_opts)
    except Exception as err:
        exit_cli(f'Failed to install {package_source}: {err}', fg='red')
    except KeyboardInterrupt:
        exit_cli('Operation canceled by user', fg='red')


@cli.command()
@add_options(PACKAGE_COMMON_OPERATION_OPTIONS)
@click.argument('name')
@click.pass_context
@root_privileges_required
def update(ctx, name, force, yes):
    """ Update package to the updated manifest file """

    manager: PackageManager = ctx.obj

    try:
        manager.update(name, force)
    except Exception as err:
        exit_cli(f'Failed to update package {name}: {err}', fg='red')
    except KeyboardInterrupt:
        exit_cli('Operation canceled by user', fg='red')

@cli.command()
@add_options(PACKAGE_COMMON_OPERATION_OPTIONS)
@add_options(PACKAGE_COMMON_INSTALL_OPTIONS)
@click.argument('name')
@click.pass_context
@root_privileges_required
def reset(ctx, name, force, yes, skip_host_plugins):
    """ Reset package to the default version. """

    manager: PackageManager = ctx.obj

    if not yes and not force:
        click.confirm(f'Package {name} is going to be reset to default version, '
                      f'continue?', abort=True, show_default=True)

    try:
        manager.reset(name, force, skip_host_plugins)
    except Exception as err:
        exit_cli(f'Failed to reset package {name}: {err}', fg='red')
    except KeyboardInterrupt:
        exit_cli('Operation canceled by user', fg='red')


@cli.command()
@add_options(PACKAGE_COMMON_OPERATION_OPTIONS)
@click.option('--keep-config', is_flag=True, help='Keep features configuration in CONFIG DB.')
@click.argument('name')
@click.pass_context
@root_privileges_required
def uninstall(ctx, name, force, yes, keep_config):
    """ Uninstall package. """

    manager: PackageManager = ctx.obj

    if not yes and not force:
        click.confirm(f'Package {name} is going to be uninstalled, '
                      f'continue?', abort=True, show_default=True)

    uninstall_opts = {
        'force': force,
        'keep_config': keep_config,
    }

    try:
        manager.uninstall(name, **uninstall_opts)
    except Exception as err:
        exit_cli(f'Failed to uninstall package {name}: {err}', fg='red')
    except KeyboardInterrupt:
        exit_cli('Operation canceled by user', fg='red')


@cli.command()
@add_options(PACKAGE_COMMON_OPERATION_OPTIONS)
@click.option('--dockerd-socket', type=click.Path())
@click.argument('database', type=click.Path())
@click.pass_context
@root_privileges_required
def migrate(ctx, database, force, yes, dockerd_socket):
    """ Migrate packages from the given database file. """

    manager: PackageManager = ctx.obj

    if not yes and not force:
        click.confirm('Continue with package migration?', abort=True, show_default=True)

    try:
        manager.migrate_packages(PackageDatabase.from_file(database), dockerd_socket)
    except Exception as err:
        exit_cli(f'Failed to migrate packages {err}', fg='red')
    except KeyboardInterrupt:
        exit_cli('Operation canceled by user', fg='red')


if __name__ == "__main__":
    cli()

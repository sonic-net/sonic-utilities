import configparser
import os
import re
import subprocess
import sys
import time
import utilities_common.cli as clicommon
from urllib.request import urlopen, urlretrieve

import click
from sonic_py_common import logger
from swsscommon.swsscommon import SonicV2Connector
from sonic_py_common.general import getstatusoutput_noshell_pipe
from .bootloader import get_bootloader
from .common import (
    run_command, run_command_or_raise,
    IMAGE_PREFIX,
    UPPERDIR_NAME,
    WORKDIR_NAME,
    DOCKERDIR_NAME,
)
from .exception import SonicRuntimeException

SYSLOG_IDENTIFIER = "sonic-installer"
LOG_ERR = logger.Logger.LOG_PRIORITY_ERROR
LOG_WARN = logger.Logger.LOG_PRIORITY_WARNING
LOG_NOTICE = logger.Logger.LOG_PRIORITY_NOTICE

# Global Config object
_config = None

# Global logger instance
log = logger.Logger(SYSLOG_IDENTIFIER)

# This is from the aliases example:
# https://github.com/pallets/click/blob/57c6f09611fc47ca80db0bd010f05998b3c0aa95/examples/aliases/aliases.py
class Config(object):
    """Object to hold CLI config"""

    def __init__(self):
        self.path = os.getcwd()
        self.aliases = {}

    def read_config(self, filename):
        parser = configparser.RawConfigParser()
        parser.read([filename])
        try:
            self.aliases.update(parser.items('aliases'))
        except configparser.NoSectionError:
            pass


class AliasedGroup(click.Group):
    """This subclass of click.Group supports abbreviations and
       looking up aliases in a config file with a bit of magic.
    """

    def get_command(self, ctx, cmd_name):
        global _config

        # If we haven't instantiated our global config, do it now and load current config
        if _config is None:
            _config = Config()

            # Load our config file
            cfg_file = os.path.join(os.path.dirname(__file__), 'aliases.ini')
            _config.read_config(cfg_file)

        # Try to get builtin commands as normal
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv

        # No builtin found. Look up an explicit command alias in the config
        if cmd_name in _config.aliases:
            actual_cmd = _config.aliases[cmd_name]
            return click.Group.get_command(self, ctx, actual_cmd)

        # Alternative option: if we did not find an explicit alias we
        # allow automatic abbreviation of the command.  "status" for
        # instance will match "st".  We only allow that however if
        # there is only one command.
        matches = [x for x in self.list_commands(ctx)
                   if x.lower().startswith(cmd_name.lower())]
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail('Too many matches: %s' % ', '.join(sorted(matches)))


#
# Helper functions
#

_start_time = None
_last_time = None
def reporthook(count, block_size, total_size):
    global _start_time, _last_time
    cur_time = int(time.time())
    if count == 0:
        _start_time = cur_time
        _last_time = cur_time
        return

    if cur_time == _last_time:
        return

    _last_time = cur_time

    duration = cur_time - _start_time
    progress_size = int(count * block_size)
    speed = int(progress_size / (1024 * duration))
    percent = int(count * block_size * 100 / total_size)
    time_left = (total_size - progress_size) / speed / 1024
    sys.stdout.write("\r...%d%%, %d MB, %d KB/s, %d seconds left...   " %
                     (percent, progress_size / (1024 * 1024), speed, time_left))
    sys.stdout.flush()


# TODO: Embed tag name info into docker image meta data at build time,
# and extract tag name from docker image file.
def get_docker_tag_name(image):
    # Try to get tag name from label metadata
    cmd = ["docker", "inspect", "--format", '{{.ContainerConfig.Labels.Tag}}', image]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
    (out, _) = proc.communicate()
    if proc.returncode != 0:
        return "unknown"
    tag = out.rstrip()
    if tag == "<no value>":
        return "unknown"
    return tag


def echo_and_log(msg, priority=LOG_NOTICE, fg=None):
    if priority == LOG_ERR:
        # Print to stderr if priority is error
        click.secho(msg, fg=fg, err=True)
    else:
        click.secho(msg, fg=fg)
    log.log(priority, msg, False)


# Function which validates whether a given URL specifies an existent file
# on a reachable remote machine. Will abort the current operation if not
def validate_url_or_abort(url):
    # Attempt to retrieve HTTP response code
    try:
        urlfile = urlopen(url)
        response_code = urlfile.getcode()
        urlfile.close()
    except IOError:
        response_code = None

    if not response_code:
        echo_and_log("Did not receive a response from remote machine. Aborting...", LOG_ERR)
        raise click.Abort()
    else:
        # Check for a 4xx response code which indicates a nonexistent URL
        if response_code / 100 == 4:
            echo_and_log("Image file not found on remote machine. Aborting...", LOG_ERR)
            raise click.Abort()


# Callback for confirmation prompt. Aborts if user enters "n"
def abort_if_false(ctx, param, value):
    if not value:
        ctx.abort()


def get_container_image_name(container_name):
    # example image: docker-lldp-sv2:latest
    cmd = ["docker", "inspect", "--format", '{{.Config.Image}}', container_name]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
    (out, _) = proc.communicate()
    if proc.returncode != 0:
        sys.exit(proc.returncode)
    image_latest = out.rstrip()

    # example image_name: docker-lldp-sv2
    _, stdout = getstatusoutput_noshell_pipe(["echo", image_latest], ["cut", "-d", ':', "-f", "1"])
    image_name = stdout.rstrip()
    return image_name


def get_container_image_id(image_tag):
    # TODO: extract commond docker info fetching functions
    # this is image_id for image with tag, like 'docker-teamd:latest'
    cmd = ["docker", "images", "--format", '{{.ID}}', image_tag]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
    image_id = proc.stdout.read().rstrip()
    return image_id


def get_container_image_id_all(image_name):
    # All images id under the image name like 'docker-teamd'
    cmd = ["docker", "images", "--format", '{{.ID}}', image_name]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
    image_id_all = proc.stdout.read()
    image_id_all = image_id_all.splitlines()
    image_id_all = set(image_id_all)
    return image_id_all


def hget_warm_restart_table(db_name, table_name, warm_app_name, key):
    db = SonicV2Connector()
    db.connect(db_name, False)
    _hash = table_name + db.get_db_separator(db_name) + warm_app_name
    client = db.get_redis_client(db_name)
    return client.hget(_hash, key)


def hdel_warm_restart_table(db_name, table_name, warm_app_name, key):
    db = SonicV2Connector()
    db.connect(db_name, False)
    _hash = table_name + db.get_db_separator(db_name) + warm_app_name
    client = db.get_redis_client(db_name)
    return client.hdel(_hash, key)


def print_deprecation_warning(deprecated_cmd_or_subcmd, new_cmd_or_subcmd):
    click.secho("Warning: '{}' {}command is deprecated and will be removed in the future"
                .format(deprecated_cmd_or_subcmd, "" if deprecated_cmd_or_subcmd == "sonic_installer" else "sub"),
                fg="red", err=True)
    click.secho("Please use '{}' instead".format(new_cmd_or_subcmd), fg="red", err=True)


def mount_squash_fs(squashfs_path, mount_point):
    run_command_or_raise(["mkdir", "-p", mount_point])
    run_command_or_raise(["mount", "-t", "squashfs", squashfs_path, mount_point])


def umount(mount_point, read_only=True, recursive=False, force=True, remove_dir=True, raise_exception=True):
    flags = []
    if read_only:
        flags.append("-r")
    if force:
        flags.append("-f")
    if recursive:
        flags.append("-R")
    run_command_or_raise(["umount", *flags, mount_point], raise_exception=raise_exception)
    if remove_dir:
        run_command_or_raise(["rm", "-rf", mount_point], raise_exception=raise_exception)


def mount_overlay_fs(lowerdir, upperdir, workdir, mount_point):
    run_command_or_raise(["mkdir", "-p", mount_point])
    overlay_options = "rw,relatime,lowerdir={},upperdir={},workdir={}".format(lowerdir, upperdir, workdir)
    run_command_or_raise(["mount", "overlay", "-t", "overlay", "-o", overlay_options, mount_point])


def mount_bind(source, mount_point):
    run_command_or_raise(["mkdir", "-p", mount_point])
    run_command_or_raise(["mount", "--bind", source, mount_point])


def mount_procfs_chroot(root):
    run_command_or_raise(["chroot", root, "mount", "proc", "/proc", "-t", "proc"])


def mount_sysfs_chroot(root):
    run_command_or_raise(["chroot", root, "mount", "sysfs", "/sys", "-t", "sysfs"])


def update_sonic_environment(bootloader, binary_image_version):
    """Prepare sonic environment variable using incoming image template file. If incoming image template does not exist
       use current image template file.
    """

    SONIC_ENV_TEMPLATE_FILE = os.path.join("usr", "share", "sonic", "templates", "sonic-environment.j2")
    SONIC_VERSION_YML_FILE = os.path.join("etc", "sonic", "sonic_version.yml")

    sonic_version = re.sub(IMAGE_PREFIX, '', binary_image_version, 1)
    new_image_dir = bootloader.get_image_path(binary_image_version)
    new_image_mount = os.path.join('/', "tmp", "image-{0}-fs".format(sonic_version))
    env_dir = os.path.join(new_image_dir, "sonic-config")
    env_file = os.path.join(env_dir, "sonic-environment")

    with bootloader.get_rootfs_path(new_image_dir) as new_image_squashfs_path:
        try:
            mount_squash_fs(new_image_squashfs_path, new_image_mount)

            next_sonic_env_template_file = os.path.join(new_image_mount, SONIC_ENV_TEMPLATE_FILE)
            next_sonic_version_yml_file = os.path.join(new_image_mount, SONIC_VERSION_YML_FILE)

            sonic_env = run_command_or_raise([
                    "sonic-cfggen",
                    "-d",
                    "-y",
                    next_sonic_version_yml_file,
                    "-t",
                    next_sonic_env_template_file,
            ])
            os.mkdir(env_dir, 0o755)
            with open(env_file, "w+") as ef:
                print(sonic_env, file=ef)
            os.chmod(env_file, 0o644)
        except SonicRuntimeException as ex:
            echo_and_log("Warning: SONiC environment variables are not supported for this image: {0}".format(str(ex)), LOG_ERR, fg="red")
            if os.path.exists(env_file):
                os.remove(env_file)
                os.rmdir(env_dir)
        finally:
            umount(new_image_mount)


def get_docker_opts():
    """ Get options dockerd is started with """
    with open("/var/run/docker.pid") as pid_file:
        pid = int(pid_file.read())

    with open("/proc/{}/cmdline".format(pid)) as cmdline_file:
        return cmdline_file.read().strip().split("\x00")[1:]


def migrate_sonic_packages(bootloader, binary_image_version):
    """ Migrate SONiC packages to new SONiC image. """

    TMP_DIR = "tmp"
    SONIC_PACKAGE_MANAGER = "sonic-package-manager"
    PACKAGE_MANAGER_DIR = "/var/lib/sonic-package-manager/"
    DOCKER_CTL_SCRIPT = "/usr/lib/docker/docker.sh"
    DOCKERD_SOCK = "docker.sock"
    VAR_RUN_PATH = "/var/run/"
    RESOLV_CONF_FILE = os.path.join("etc", "resolv.conf")
    RESOLV_CONF_BACKUP_FILE = os.path.join("/", TMP_DIR, "resolv.conf.backup")

    packages_file = "packages.json"
    packages_path = os.path.join(PACKAGE_MANAGER_DIR, packages_file)
    sonic_version = re.sub(IMAGE_PREFIX, '', binary_image_version, 1)
    new_image_dir = bootloader.get_image_path(binary_image_version)
    new_image_upper_dir = os.path.join(new_image_dir, UPPERDIR_NAME)
    new_image_work_dir = os.path.join(new_image_dir, WORKDIR_NAME)
    new_image_docker_dir = os.path.join(new_image_dir, DOCKERDIR_NAME)
    new_image_mount = os.path.join("/", TMP_DIR, "image-{0}-fs".format(sonic_version))
    new_image_docker_mount = os.path.join(new_image_mount, "var", "lib", "docker")
    docker_default_config = os.path.join(new_image_mount, "etc", "default", "docker")
    docker_default_config_backup = os.path.join(new_image_mount, TMP_DIR, "docker_config_backup")

    if not os.path.isdir(new_image_docker_dir):
        # NOTE: This codepath can be reached if the installation process did not
        #       extract the default dockerfs. This can happen with docker_inram
        #       though the bootloader class should have disabled the package
        #       migration which is why this message is a non fatal error message.
        echo_and_log("Error: SONiC package migration cannot proceed due to missing docker folder", LOG_ERR, fg="red")
        return

    docker_started = False
    with bootloader.get_rootfs_path(new_image_dir) as new_image_squashfs_path:
        try:
            mount_squash_fs(new_image_squashfs_path, new_image_mount)
            # make sure upper dir and work dir exist
            run_command_or_raise(["mkdir", "-p", new_image_upper_dir])
            run_command_or_raise(["mkdir", "-p", new_image_work_dir])
            mount_overlay_fs(new_image_mount, new_image_upper_dir, new_image_work_dir, new_image_mount)
            mount_bind(new_image_docker_dir, new_image_docker_mount)
            mount_procfs_chroot(new_image_mount)
            mount_sysfs_chroot(new_image_mount)
            # Assume if docker.sh script exists we are installing Application Extension compatible image.
            if not os.path.exists(os.path.join(new_image_mount, os.path.relpath(DOCKER_CTL_SCRIPT, os.path.abspath(os.sep)))):
                echo_and_log("Warning: SONiC Application Extension is not supported in this image", LOG_WARN, fg="yellow")
                return

            # Start dockerd with same docker bridge, iptables configuration as on the host to not override docker configurations on the host.
            # Dockerd has an option to start without creating a bridge, using --bridge=none option, however dockerd will remove the host docker0 in that case.
            # Also, it is not possible to configure dockerd to start using a different bridge as it will also override the ip of the default docker0.
            # Considering that, we start dockerd with same options the host dockerd is started.
            run_command_or_raise(["cp", docker_default_config, docker_default_config_backup])
            run_command_or_raise(["sh", "-c", "echo 'DOCKER_OPTS=\"$DOCKER_OPTS {}\"' >> {}".format(" ".join(get_docker_opts()), docker_default_config)])

            run_command_or_raise(["chroot", new_image_mount, DOCKER_CTL_SCRIPT, "start"])
            docker_started = True
            run_command_or_raise(["cp", packages_path, os.path.join(new_image_mount, TMP_DIR, packages_file)])
            run_command_or_raise(["touch", os.path.join(new_image_mount, "tmp", DOCKERD_SOCK)])
            run_command_or_raise(["mount", "--bind",
                                os.path.join(VAR_RUN_PATH, DOCKERD_SOCK),
                                os.path.join(new_image_mount, "tmp", DOCKERD_SOCK)])

            run_command_or_raise(["cp", os.path.join(new_image_mount, RESOLV_CONF_FILE), RESOLV_CONF_BACKUP_FILE])
            run_command_or_raise(["cp", os.path.join("/", RESOLV_CONF_FILE), os.path.join(new_image_mount, RESOLV_CONF_FILE)])

            run_command_or_raise(["chroot", new_image_mount, "sh", "-c", "command -v {}".format(SONIC_PACKAGE_MANAGER)])
            run_command_or_raise(["chroot", new_image_mount, SONIC_PACKAGE_MANAGER, "migrate",
                                os.path.join("/", TMP_DIR, packages_file),
                                "--dockerd-socket", os.path.join("/", TMP_DIR, DOCKERD_SOCK),
                                "-y"], capture=False)
        finally:
            if docker_started:
                run_command_or_raise(["chroot", new_image_mount, DOCKER_CTL_SCRIPT, "stop"], raise_exception=False)
            if os.path.exists(docker_default_config_backup):
                run_command_or_raise(["mv", docker_default_config_backup, docker_default_config], raise_exception=False);
            run_command_or_raise(["cp", RESOLV_CONF_BACKUP_FILE, os.path.join(new_image_mount, RESOLV_CONF_FILE)], raise_exception=False)
            umount(new_image_mount, recursive=True, read_only=False, remove_dir=False, raise_exception=False)
            umount(new_image_mount, raise_exception=False)


class SWAPAllocator(object):
    """Context class to allocate SWAP memory."""

    SWAP_MEM_SIZE = 1024
    DISK_FREESPACE_THRESHOLD = 4 * 1024
    TOTAL_MEM_THRESHOLD = 2048
    AVAILABLE_MEM_THRESHOLD = 1200
    SWAP_FILE_PATH = '/host/swapfile'
    KiB_TO_BYTES_FACTOR = 1024
    MiB_TO_BYTES_FACTOR = 1024 * 1024

    def __init__(self, allocate, swap_mem_size=None, total_mem_threshold=None, available_mem_threshold=None):
        """
        Initialize the SWAP memory allocator.
        The allocator will try to setup SWAP memory only if all the below conditions are met:
            - allocate evaluates to True
            - disk has enough space(> DISK_MEM_THRESHOLD)
            - either system total memory < total_mem_threshold or system available memory < available_mem_threshold

        @param allocate: True to allocate SWAP memory if necessarry
        @param swap_mem_size: the size of SWAP memory to allocate(in MiB)
        @param total_mem_threshold: the system totla memory threshold(in MiB)
        @param available_mem_threshold: the system available memory threshold(in MiB)
        """
        self.allocate = allocate
        self.swap_mem_size = SWAPAllocator.SWAP_MEM_SIZE if swap_mem_size is None else swap_mem_size
        self.total_mem_threshold = SWAPAllocator.TOTAL_MEM_THRESHOLD if total_mem_threshold is None else total_mem_threshold
        self.available_mem_threshold = SWAPAllocator.AVAILABLE_MEM_THRESHOLD if available_mem_threshold is None else available_mem_threshold
        self.is_allocated = False

    @staticmethod
    def get_disk_freespace(path):
        """Return free disk space in bytes."""
        fs_stats = os.statvfs(path)
        return fs_stats.f_bsize * fs_stats.f_bavail

    @staticmethod
    def read_from_meminfo():
        """Read information from /proc/meminfo."""
        meminfo = {}
        with open("/proc/meminfo") as fd:
            for line in fd.readlines():
                if line:
                    fields = line.split()
                    if len(fields) >= 2 and fields[1].isdigit():
                        meminfo[fields[0].rstrip(":")] = int(fields[1])
        return meminfo

    def setup_swapmem(self):
        swapfile = SWAPAllocator.SWAP_FILE_PATH
        with open(swapfile, 'wb') as fd:
            os.posix_fallocate(fd.fileno(), 0, self.swap_mem_size * SWAPAllocator.MiB_TO_BYTES_FACTOR)
        os.chmod(swapfile, 0o600)
        run_command(['mkswap', swapfile])
        run_command(['swapon', swapfile])

    def remove_swapmem(self):
        swapfile = SWAPAllocator.SWAP_FILE_PATH
        run_command_or_raise(['swapoff', swapfile], raise_exception=False)
        try:
            os.unlink(swapfile)
        finally:
            pass

    def __enter__(self):
        if self.allocate:
            if self.get_disk_freespace('/host') < max(SWAPAllocator.DISK_FREESPACE_THRESHOLD, self.swap_mem_size) * SWAPAllocator.MiB_TO_BYTES_FACTOR:
                echo_and_log("Failed to setup SWAP memory due to insufficient disk free space...", LOG_ERR)
                return
            meminfo = self.read_from_meminfo()
            mem_total_in_bytes = meminfo["MemTotal"] * SWAPAllocator.KiB_TO_BYTES_FACTOR
            mem_avail_in_bytes = meminfo["MemAvailable"] * SWAPAllocator.KiB_TO_BYTES_FACTOR
            swap_total_in_bytes = meminfo["SwapTotal"] * SWAPAllocator.KiB_TO_BYTES_FACTOR
            swap_free_in_bytes = meminfo["SwapFree"] * SWAPAllocator.KiB_TO_BYTES_FACTOR
            if (mem_total_in_bytes + swap_total_in_bytes < self.total_mem_threshold * SWAPAllocator.MiB_TO_BYTES_FACTOR
                    or mem_avail_in_bytes + swap_free_in_bytes < self.available_mem_threshold * SWAPAllocator.MiB_TO_BYTES_FACTOR):
                echo_and_log("Setup SWAP memory")
                swapfile = SWAPAllocator.SWAP_FILE_PATH
                if os.path.exists(swapfile):
                    self.remove_swapmem()
                try:
                    self.setup_swapmem()
                except Exception:
                    self.remove_swapmem()
                    raise
                self.is_allocated = True

    def __exit__(self, *exc_info):
        if self.is_allocated:
            self.remove_swapmem()


def validate_positive_int(ctx, param, value):
    """Callback to validate param passed is a positive integer."""
    if isinstance(value, int) and value > 0:
        return value
    raise click.BadParameter("Must be a positive integer")


# Main entrypoint
@click.group(cls=AliasedGroup)
def sonic_installer():
    """ SONiC image installation manager """
    if os.geteuid() != 0:
        sys.exit("Root privileges required for this operation")

    # Warn the user if they are calling the deprecated version of the command (with an underscore instead of a hyphen)
    if os.path.basename(sys.argv[0]) == "sonic_installer":
        print_deprecation_warning("sonic_installer", "sonic-installer")


# Install image
@sonic_installer.command('install')
@click.option('-y', '--yes', is_flag=True, callback=abort_if_false,
              expose_value=False, prompt='New image will be installed, continue?')
@click.option('-f', '--force', '--skip-secure-check', is_flag=True,
              help="Force installation of an image of a non-secure type than secure running " +
              " image, this flag does not affect secure upgrade image verification")
@click.option('--skip-platform-check', is_flag=True,
              help="Force installation of an image of a type which is not of the same platform")
@click.option('--skip_migration', is_flag=True,
              help="Do not migrate current configuration to the newly installed image")
@click.option('--skip-package-migration', is_flag=True,
              help="Do not migrate current packages to the newly installed image")
@click.option('--skip-setup-swap', is_flag=True,
              help='Skip setup temporary SWAP memory used for installation')
@click.option('--swap-mem-size', default=1024, type=int, show_default='1024 MiB',
              help='SWAP memory space size', callback=validate_positive_int,
              cls=clicommon.MutuallyExclusiveOption, mutually_exclusive=['skip_setup_swap'])
@click.option('--total-mem-threshold', default=2048, type=int, show_default='2048 MiB',
              help='If system total memory is lower than threshold, setup SWAP memory',
              cls=clicommon.MutuallyExclusiveOption, mutually_exclusive=['skip_setup_swap'],
              callback=validate_positive_int)
@click.option('--available-mem-threshold', default=1200, type=int, show_default='1200 MiB',
              help='If system available memory is lower than threhold, setup SWAP memory',
              cls=clicommon.MutuallyExclusiveOption, mutually_exclusive=['skip_setup_swap'],
              callback=validate_positive_int)
@click.argument('url')
def install(url, force, skip_platform_check=False, skip_migration=False, skip_package_migration=False,
            skip_setup_swap=False, swap_mem_size=None, total_mem_threshold=None, available_mem_threshold=None):
    """ Install image from local binary or URL"""
    bootloader = get_bootloader()

    if url.startswith('http://') or url.startswith('https://'):
        echo_and_log('Downloading image...')
        validate_url_or_abort(url)
        try:
            urlretrieve(url, bootloader.DEFAULT_IMAGE_PATH, reporthook)
            click.echo('')
        except Exception as e:
            echo_and_log("Download error", e)
            raise click.Abort()
        image_path = bootloader.DEFAULT_IMAGE_PATH
    else:
        image_path = os.path.join("./", url)

    binary_image_version = bootloader.get_binary_image_version(image_path)
    if not binary_image_version:
        echo_and_log("Image file does not exist or is not a valid SONiC image file", LOG_ERR)
        raise click.Abort()

    # Is this version already installed?
    if binary_image_version in bootloader.get_installed_images():
        echo_and_log("Image {} is already installed. Setting it as default...".format(binary_image_version))
        if not bootloader.set_default_image(binary_image_version):
            echo_and_log('Error: Failed to set image as default', LOG_ERR)
            raise click.Abort()
    else:
        # Verify not installing non-secure image in a secure running image
        if not force and not bootloader.verify_secureboot_image(image_path):
            echo_and_log("Image file '{}' is of a different type than running image.\n".format(url) +
                "If you are sure you want to install this image, use -f|--force|--skip-secure-check.\n" +
                "Aborting...", LOG_ERR)
            raise click.Abort()

        # Verify that the binary image is of the same platform type as running platform
        if not skip_platform_check and not bootloader.verify_image_platform(image_path):
            echo_and_log("Image file '{}' is of a different platform ASIC type than running platform's.\n".format(url) +
                "If you are sure you want to install this image, use --skip-platform-check.\n" +
                "Aborting...", LOG_ERR)
            raise click.Abort()

        if bootloader.is_secure_upgrade_image_verification_supported():
            echo_and_log("Verifing image {} signature...".format(binary_image_version))
            if not bootloader.verify_image_sign(image_path):
                echo_and_log('Error: Failed verify image signature', LOG_ERR)
                raise click.Abort()
            else:
                echo_and_log('Verification successful')

        echo_and_log("Installing image {} and setting it as default...".format(binary_image_version))
        with SWAPAllocator(not skip_setup_swap, swap_mem_size, total_mem_threshold, available_mem_threshold):
            bootloader.install_image(image_path)
        # Take a backup of current configuration
        if skip_migration:
            echo_and_log("Skipping configuration migration as requested in the command option.")
        else:
            run_command(['config-setup', 'backup'])

        update_sonic_environment(bootloader, binary_image_version)

        if not bootloader.supports_package_migration(binary_image_version) and not skip_package_migration:
            echo_and_log("Warning: SONiC package migration is not supported for this bootloader/image", fg="yellow")
            skip_package_migration = True

        if not skip_package_migration:
            migrate_sonic_packages(bootloader, binary_image_version)

    # Finally, sync filesystem
    run_command(["sync"])
    run_command(["sync"])
    run_command(["sync"])
    run_command(["sleep", "3"])  # wait 3 seconds after sync
    echo_and_log('Done')


# List installed images
@sonic_installer.command('list')
def list_command():
    """ Print installed images """
    bootloader = get_bootloader()
    images = bootloader.get_installed_images()
    curimage = bootloader.get_current_image()
    nextimage = bootloader.get_next_image()
    click.echo("Current: " + curimage)
    click.echo("Next: " + nextimage)
    click.echo("Available: ")
    for image in images:
        click.echo(image)


# Set default image for boot
@sonic_installer.command('set-default')
@click.argument('image')
def set_default(image):
    """ Choose image to boot from by default """
    # Warn the user if they are calling the deprecated version of the subcommand (with an underscore instead of a hyphen)
    if "set_default" in sys.argv:
        print_deprecation_warning("set_default", "set-default")

    bootloader = get_bootloader()
    if image not in bootloader.get_installed_images():
        echo_and_log('Error: Image does not exist', LOG_ERR)
        raise click.Abort()
    bootloader.set_default_image(image)


# Set image for next boot
@sonic_installer.command('set-next-boot')
@click.argument('image')
def set_next_boot(image):
    """ Choose image for next reboot (one time action) """
    # Warn the user if they are calling the deprecated version of the subcommand (with underscores instead of hyphens)
    if "set_next_boot" in sys.argv:
        print_deprecation_warning("set_next_boot", "set-next-boot")

    bootloader = get_bootloader()
    if image not in bootloader.get_installed_images():
        echo_and_log('Error: Image does not exist', LOG_ERR)
        sys.exit(1)
    bootloader.set_next_image(image)

# Set fips for image
@sonic_installer.command('set-fips')
@click.argument('image', required=False)
@click.option('--enable-fips/--disable-fips', is_flag=True, default=True,
              help="Enable or disable FIPS, the default value is to enable FIPS")
def set_fips(image, enable_fips):
    """ Set fips for the image """
    bootloader = get_bootloader()
    if not image:
        image =  bootloader.get_next_image()
    if image not in bootloader.get_installed_images():
        echo_and_log('Error: Image does not exist', LOG_ERR)
        sys.exit(1)
    bootloader.set_fips(image, enable=enable_fips)
    click.echo('Set FIPS for the image successfully')

# Get fips for image
@sonic_installer.command('get-fips')
@click.argument('image', required=False)
def get_fips(image):
    """ Get the fips enabled or disabled status for the image """
    bootloader = get_bootloader()
    if not image:
        image =  bootloader.get_next_image()
    if image not in bootloader.get_installed_images():
        echo_and_log('Error: Image does not exist', LOG_ERR)
        sys.exit(1)
    enable = bootloader.get_fips(image)
    if enable:
       click.echo("FIPS is enabled")
    else:
       click.echo("FIPS is disabled")

# Uninstall image
@sonic_installer.command('remove')
@click.option('-y', '--yes', is_flag=True, callback=abort_if_false,
              expose_value=False, prompt='Image will be removed, continue?')
@click.argument('image')
def remove(image):
    """ Uninstall image """
    bootloader = get_bootloader()
    images = bootloader.get_installed_images()
    current = bootloader.get_current_image()
    if image not in images:
        echo_and_log('Image does not exist', LOG_ERR)
        sys.exit(1)
    if image == current:
        echo_and_log('Cannot remove current image', LOG_ERR)
        sys.exit(1)
    # TODO: check if image is next boot or default boot and fix these
    bootloader.remove_image(image)


# Retrieve version from binary image file and print to screen
@sonic_installer.command('binary-version')
@click.argument('binary_image_path')
def binary_version(binary_image_path):
    """ Get version from local binary image file """
    # Warn the user if they are calling the deprecated version of the subcommand (with an underscore instead of a hyphen)
    if "binary_version" in sys.argv:
        print_deprecation_warning("binary_version", "binary-version")

    bootloader = get_bootloader()
    version = bootloader.get_binary_image_version(binary_image_path)
    if not version:
        click.echo("Image file does not exist or is not a valid SONiC image file")
        sys.exit(1)
    else:
        click.echo(version)


# Remove installed images which are not current and next
@sonic_installer.command('cleanup')
@click.option('-y', '--yes', is_flag=True, callback=abort_if_false,
              expose_value=False, prompt='Remove images which are not current and next, continue?')
def cleanup():
    """ Remove installed images which are not current and next """
    bootloader = get_bootloader()
    images = bootloader.get_installed_images()
    curimage = bootloader.get_current_image()
    nextimage = bootloader.get_next_image()
    image_removed = 0
    for image in images:
        if image != curimage and image != nextimage:
            echo_and_log("Removing image %s" % image)
            bootloader.remove_image(image)
            image_removed += 1

    if image_removed == 0:
        echo_and_log("No image(s) to remove")


DOCKER_CONTAINER_LIST = [
    "bgp",
    "dhcp_relay",
    "lldp",
    "macsec",
    "nat",
    "pmon",
    "radv",
    "restapi",
    "sflow",
    "snmp",
    "swss",
    "syncd",
    "teamd",
    "telemetry",
    "mgmt-framework"
]

# Upgrade docker image
@sonic_installer.command('upgrade-docker')
@click.option('-y', '--yes', is_flag=True, callback=abort_if_false,
              expose_value=False, prompt='New docker image will be installed, continue?')
@click.option('--cleanup_image', is_flag=True, help="Clean up old docker image")
@click.option('--skip_check', is_flag=True, help="Skip task check for docker upgrade")
@click.option('--tag', type=str, help="Tag for the new docker image")
@click.option('--warm', is_flag=True, help="Perform warm upgrade")
@click.argument('container_name', metavar='<container_name>', required=True,
                type=click.Choice(DOCKER_CONTAINER_LIST))
@click.argument('url')
def upgrade_docker(container_name, url, cleanup_image, skip_check, tag, warm):
    """ Upgrade docker image from local binary or URL"""
    # Warn the user if they are calling the deprecated version of the subcommand (with an underscore instead of a hyphen)
    if "upgrade_docker" in sys.argv:
        print_deprecation_warning("upgrade_docker", "upgrade-docker")

    image_name = get_container_image_name(container_name)
    image_latest = image_name + ":latest"
    image_id_previous = get_container_image_id(image_latest)

    DEFAULT_IMAGE_PATH = os.path.join("/tmp/", image_name)
    if url.startswith('http://') or url.startswith('https://'):
        echo_and_log('Downloading image...')
        validate_url_or_abort(url)
        try:
            urlretrieve(url, DEFAULT_IMAGE_PATH, reporthook)
        except Exception as e:
            echo_and_log("Download error: {}".format(e), LOG_ERR)
            raise click.Abort()
        image_path = DEFAULT_IMAGE_PATH
    else:
        image_path = os.path.join("./", url)

    # Verify that the local file exists and is a regular file
    # TODO: Verify the file is a *proper Docker image file*
    if not os.path.isfile(image_path):
        echo_and_log("Image file '{}' does not exist or is not a regular file. Aborting...".format(image_path), LOG_ERR)
        raise click.Abort()

    # warm restart enable/disable config is put in stateDB, not persistent across cold reboot, not saved to config_DB.json file
    warm_configured = hget_warm_restart_table('STATE_DB', 'WARM_RESTART_ENABLE_TABLE', container_name, 'enable') == "true"

    if container_name == "swss" or container_name == "bgp" or container_name == "teamd":
        if warm_configured is False and warm:
            run_command(["config", "warm_restart", "enable", "%s" % container_name])

    # Fetch tag of current running image
    tag_previous = get_docker_tag_name(image_latest)
    # Load the new image beforehand to shorten disruption time
    run_command(["docker", "load", "-i", "%s" % image_path])
    warm_app_names = []
    # warm restart specific procssing for swss, bgp and teamd dockers.
    if warm_configured is True or warm:
        # make sure orchagent is in clean state if swss is to be upgraded
        if container_name == "swss":
            skipPendingTaskCheck = ""
            if skip_check:
                skipPendingTaskCheck = " -s"

            cmd = ["docker", "exec", "-i", "swss", "orchagent_restart_check", "-w", "2000", "-r", "5", skipPendingTaskCheck]

            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
            (out, err) = proc.communicate()
            if proc.returncode != 0:
                if not skip_check:
                    echo_and_log("Orchagent is not in clean state, RESTARTCHECK failed", LOG_ERR)
                    # Restore orignal config before exit
                    if warm_configured is False and warm:
                        run_command(["config", "warm_restart", "disable", "%s" % container_name])
                    # Clean the image loaded earlier
                    image_id_latest = get_container_image_id(image_latest)
                    run_command(["docker", "rmi", "-f", "%s" % image_id_latest])
                    # Re-point latest tag to previous tag
                    run_command(["docker", "tag", "%s:%s" % (image_name, tag_previous), "%s" % image_latest])

                    sys.exit(proc.returncode)
                else:
                    echo_and_log("Orchagent is not in clean state, upgrading it anyway")
            else:
                echo_and_log("Orchagent is in clean state and frozen for warm upgrade")

            warm_app_names = ["orchagent", "neighsyncd"]

        elif container_name == "bgp":
            # Kill bgpd to restart the bgp graceful restart procedure
            echo_and_log("Stopping bgp ...")
            run_command(["docker", "exec", "-i", "bgp", "pkill", "-9", "zebra"])
            run_command(["docker", "exec", "-i", "bgp", "pkill", "-9", "bgpd"])
            warm_app_names = ["bgp"]
            echo_and_log("Stopped  bgp ...")

        elif container_name == "teamd":
            echo_and_log("Stopping teamd ...")
            # Send USR1 signal to all teamd instances to stop them
            # It will prepare teamd for warm-reboot
            run_command(["docker", "exec", "-i", "teamd", "pkill", "-USR1", "teamd"], stdout=subprocess.DEVNULL)
            warm_app_names = ["teamsyncd"]
            echo_and_log("Stopped  teamd ...")

        # clean app reconcilation state from last warm start if exists
        for warm_app_name in warm_app_names:
            hdel_warm_restart_table("STATE_DB", "WARM_RESTART_TABLE", warm_app_name, "state")

    run_command(["docker", "kill", "%s" % container_name], stdout=subprocess.DEVNULL)
    run_command(["docker", "rm", "%s" % container_name])
    if tag is None:
        # example image: docker-lldp-sv2:latest
        tag = get_docker_tag_name(image_latest)
    run_command(["docker", "tag", "%s:latest" % image_name, "%s:%s" % (image_name, tag)])
    run_command(["systemctl", "restart", "%s" % container_name])

    if cleanup_image:
        # All images id under the image name
        image_id_all = get_container_image_id_all(image_name)
        # Unless requested, the previoud docker image will be preserved
        for id in image_id_all:
            if id == image_id_previous:
                run_command(["docker", "rmi", "-f", "%s" % id])
                break

    exp_state = "reconciled"
    state = ""
    # post warm restart specific procssing for swss, bgp and teamd dockers, wait for reconciliation state.
    if warm_app_names and (warm_configured is True or warm):
        count = 0
        for warm_app_name in warm_app_names:
            state = ""
            # Wait up to 180 seconds for reconciled state
            while state != exp_state and count < 90:
                sys.stdout.write("\r  {}: ".format(warm_app_name))
                sys.stdout.write("[%-s" % ('='*count))
                sys.stdout.flush()
                count += 1
                time.sleep(2)
                state = hget_warm_restart_table("STATE_DB", "WARM_RESTART_TABLE", warm_app_name, "state")
                log.log_notice("%s reached %s state" % (warm_app_name, state))
            sys.stdout.write("]\n\r")
            if state != exp_state:
                echo_and_log("%s failed to reach %s state" % (warm_app_name, exp_state), LOG_ERR)
    else:
        exp_state = ""  # this is cold upgrade

    # Restore to previous cold restart setting
    if warm_configured is False and warm:
        if container_name == "swss" or container_name == "bgp" or container_name == "teamd":
            run_command(["config", "warm_restart", "disable", container_name])

    if state == exp_state:
        echo_and_log('Done')
    else:
        echo_and_log('Failed', LOG_ERR)
        sys.exit(1)


# rollback docker image
@sonic_installer.command('rollback-docker')
@click.option('-y', '--yes', is_flag=True, callback=abort_if_false,
              expose_value=False, prompt='Docker image will be rolled back, continue?')
@click.argument('container_name', metavar='<container_name>', required=True,
                type=click.Choice(DOCKER_CONTAINER_LIST))
def rollback_docker(container_name):
    """ Rollback docker image to previous version"""
    # Warn the user if they are calling the deprecated version of the subcommand (with an underscore instead of a hyphen)
    if "rollback_docker" in sys.argv:
        print_deprecation_warning("rollback_docker", "rollback-docker")

    image_name = get_container_image_name(container_name)
    # All images id under the image name
    image_id_all = get_container_image_id_all(image_name)
    if len(image_id_all) != 2:
        echo_and_log("Two images required, but there are '{}' images for '{}'. Aborting...".format(len(image_id_all), image_name), LOG_ERR)
        raise click.Abort()

    image_latest = image_name + ":latest"
    image_id_previous = get_container_image_id(image_latest)

    version_tag = ""
    for id in image_id_all:
        if id != image_id_previous:
            version_tag = get_docker_tag_name(id)
            break

    # make previous image as latest
    run_command(["docker", "tag", "%s:%s" % (image_name, version_tag), "%s:latest" % (image_name)])
    if container_name == "swss" or container_name == "bgp" or container_name == "teamd":
        echo_and_log("Cold reboot is required to restore system state after '{}' rollback !!".format(container_name), LOG_ERR)
    else:
        run_command(["systemctl", "restart", container_name])

    echo_and_log('Done')

# verify the next image
@sonic_installer.command('verify-next-image')
def verify_next_image():
    """ Verify the next image for reboot"""
    bootloader = get_bootloader()
    if not bootloader.verify_next_image():
        echo_and_log('Image verification failed', LOG_ERR)
        sys.exit(1)
    click.echo('Image successfully verified')

if __name__ == '__main__':
    sonic_installer()

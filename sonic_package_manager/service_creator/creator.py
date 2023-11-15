#!/usr/bin/env python

import contextlib
import os
import sys
import shutil
import stat
import subprocess
import tempfile
from collections import defaultdict
from typing import Dict, Type, List

import jinja2 as jinja2
from config.config_mgmt import ConfigMgmt
from prettyprinter import pformat
from toposort import toposort_flatten, CircularDependencyError

from config.config_mgmt import sonic_cfggen
from sonic_cli_gen.generator import CliGenerator
from sonic_package_manager import utils
from sonic_package_manager.logger import log
from sonic_package_manager.package import Package
from sonic_package_manager.service_creator import (
    ETC_SONIC_PATH,
    SONIC_CLI_COMMANDS,
)
from sonic_package_manager.service_creator.feature import FeatureRegistry
from sonic_package_manager.service_creator.sonic_db import SonicDB
from sonic_package_manager.service_creator.utils import in_chroot


SERVICE_FILE_TEMPLATE = 'sonic.service.j2'
TIMER_UNIT_TEMPLATE = 'timer.unit.j2'

SYSTEMD_LOCATION = '/usr/lib/systemd/system'

GENERATED_SERVICES_CONF_FILE = '/etc/sonic/generated_services.conf'

SERVICE_MGMT_SCRIPT_TEMPLATE = 'service_mgmt.sh.j2'
SERVICE_MGMT_SCRIPT_LOCATION = '/usr/local/bin'

DOCKER_CTL_SCRIPT_TEMPLATE = 'docker_image_ctl.j2'
DOCKER_CTL_SCRIPT_LOCATION = '/usr/bin'

DEBUG_DUMP_SCRIPT_TEMPLATE = 'dump.sh.j2'
DEBUG_DUMP_SCRIPT_LOCATION = '/usr/local/bin/debug-dump/'

TEMPLATES_PATH = '/usr/share/sonic/templates'


class ServiceCreatorError(Exception):
    pass


def render_template(in_template: str,
                    outfile: str,
                    render_ctx: Dict,
                    executable: bool = False):
    """ Template renderer helper routine.
    Args:
        in_template: Input file with template content
        outfile: Output file to render template to
        render_ctx: Dictionary used to generate jinja2 template
        executable: Set executable bit on rendered file
    """

    log.debug(f'Rendering {in_template} to {outfile} with {pformat(render_ctx)}')

    with open(in_template, 'r') as instream:
        template = jinja2.Template(instream.read())

    with open(outfile, 'w') as outstream:
        outstream.write(template.render(**render_ctx))

    if executable:
        set_executable_bit(outfile)


def get_tmpl_path(template_name: str) -> str:
    """ Returns a path to a template.
    Args:
        template_name: Template file name.
    """

    return os.path.join(TEMPLATES_PATH, template_name)


def set_executable_bit(filepath):
    """ Sets +x on filepath. """

    st = os.stat(filepath)
    os.chmod(filepath, st.st_mode | stat.S_IEXEC)


def remove_if_exists(path):
    """ Remove filepath if it exists """

    if not os.path.exists(path):
        return

    os.remove(path)
    log.info(f'removed {path}')

def is_list_of_strings(command):
    return isinstance(command, list) and all(isinstance(item, str) for item in command)

def run_command(command: List[str]):
    """ Run arbitrary bash command.
    Args:
        command: List of Strings command to execute as bash script
    Raises:
        ServiceCreatorError: Raised when the command return code
                             is not 0.
    """
    if not is_list_of_strings(command):
        sys.exit("Input command should be a list of strings")
    log.debug(f'running command: {command}')

    proc = subprocess.Popen(command, stdout=subprocess.PIPE)
    (_, _) = proc.communicate()
    if proc.returncode != 0:
        raise ServiceCreatorError(f'Failed to execute "{command}"')


class ServiceCreator:
    """ Creates and registers services in SONiC based on the package
     manifest. """

    def __init__(self,
                 feature_registry: FeatureRegistry,
                 sonic_db: Type[SonicDB],
                 cli_gen: CliGenerator,
                 cfg_mgmt: ConfigMgmt):
        """ Initialize ServiceCreator with:

        Args:
            feature_registry: FeatureRegistry object.
            sonic_db: SonicDB interface.
            cli_gen: CliGenerator instance.
            cfg_mgmt: ConfigMgmt instance.
         """

        self.feature_registry = feature_registry
        self.sonic_db = sonic_db
        self.cli_gen = cli_gen
        self.cfg_mgmt = cfg_mgmt

    def create(self,
               package: Package,
               register_feature: bool = True,
               state: str = 'enabled',
               owner: str = 'local'):
        """ Register package as SONiC service.

        Args:
            package: Package object to install.
            register_feature: Wether to register this package in FEATURE table.
            state: Default feature state.
            owner: Default feature owner.

        Returns:
            None
        """

        try:
            self.generate_container_mgmt(package)
            self.generate_service_mgmt(package)
            self.update_dependent_list_file(package)
            self.generate_systemd_service(package)
            self.update_generated_services_conf_file(package)
            self.generate_dump_script(package)
            self.generate_service_reconciliation_file(package)
            self.install_yang_module(package)
            self.set_initial_config(package)
            self.install_autogen_cli_all(package)
            self._post_operation_hook()

            if register_feature:
                self.feature_registry.register(package.manifest, state, owner)
        except (Exception, KeyboardInterrupt):
            self.remove(package, deregister_feature=register_feature)
            raise

    def remove(self,
               package: Package,
               deregister_feature: bool = True,
               keep_config: bool = False):
        """ Uninstall SONiC service provided by the package.

        Args:
            package: Package object to uninstall.
            deregister_feature: Wether to deregister this package from FEATURE table.
            keep_config: Whether to remove package configuration.

        Returns:
            None
        """

        name = package.manifest['service']['name']
        remove_if_exists(os.path.join(SYSTEMD_LOCATION, f'{name}.service'))
        remove_if_exists(os.path.join(SYSTEMD_LOCATION, f'{name}@.service'))
        remove_if_exists(os.path.join(SERVICE_MGMT_SCRIPT_LOCATION, f'{name}.sh'))
        remove_if_exists(os.path.join(DOCKER_CTL_SCRIPT_LOCATION, f'{name}.sh'))
        remove_if_exists(os.path.join(DEBUG_DUMP_SCRIPT_LOCATION, f'{name}'))
        remove_if_exists(os.path.join(ETC_SONIC_PATH, f'{name}_reconcile'))
        self.update_dependent_list_file(package, remove=True)
        self.update_generated_services_conf_file(package, remove=True)

        if deregister_feature and not keep_config:
            self.remove_config(package)

        self.uninstall_autogen_cli_all(package)
        self.uninstall_yang_module(package)
        self._post_operation_hook()

        if deregister_feature:
            self.feature_registry.deregister(package.manifest['service']['name'])

    def generate_container_mgmt(self, package: Package):
        """ Generates container management script under /usr/bin/<service>.sh for package.

        Args:
            package: Package object to generate script for.
        Returns:
            None
        """

        image_id = package.image_id
        name = package.manifest['service']['name']
        container_spec = package.manifest['container']
        script_path = os.path.join(DOCKER_CTL_SCRIPT_LOCATION, f'{name}.sh')
        script_template = get_tmpl_path(DOCKER_CTL_SCRIPT_TEMPLATE)
        run_opt = []

        if container_spec['privileged']:
            run_opt.append('--privileged')

        run_opt.append('-t')

        for volume in container_spec['volumes']:
            run_opt.append(f'-v {volume}')

        for mount in container_spec['mounts']:
            mount_type, source, target = mount['type'], mount['source'], mount['target']
            run_opt.append(f'--mount type={mount_type},source={source},target={target}')

        for tmpfs_mount in container_spec['tmpfs']:
            run_opt.append(f'--tmpfs {tmpfs_mount}')

        for env_name, value in container_spec['environment'].items():
            run_opt.append(f'-e {env_name}={value}')

        run_opt = ' '.join(run_opt)
        render_ctx = {
            'docker_container_name': name,
            'docker_image_id': image_id,
            'docker_image_run_opt': run_opt,
        }
        render_template(script_template, script_path, render_ctx, executable=True)
        log.info(f'generated {script_path}')

    def generate_service_mgmt(self, package: Package):
        """ Generates service management script under /usr/local/bin/<service>.sh for package.

        Args:
            package: Package object to generate script for.
        Returns:
            None
        """

        name = package.manifest['service']['name']
        multi_instance_services = self.feature_registry.get_multi_instance_features()
        script_path = os.path.join(SERVICE_MGMT_SCRIPT_LOCATION, f'{name}.sh')
        scrip_template = get_tmpl_path(SERVICE_MGMT_SCRIPT_TEMPLATE)
        render_ctx = {
            'source': get_tmpl_path(SERVICE_MGMT_SCRIPT_TEMPLATE),
            'manifest': package.manifest.unmarshal(),
            'multi_instance_services': multi_instance_services,
        }
        render_template(scrip_template, script_path, render_ctx, executable=True)
        log.info(f'generated {script_path}')

    def generate_systemd_service(self, package: Package):
        """ Generates systemd service(s) file and timer(s) (if needed) for package.

        Args:
            package: Package object to generate service for.
        Returns:
            None
        """

        name = package.manifest['service']['name']
        multi_instance_services = self.feature_registry.get_multi_instance_features()

        template = get_tmpl_path(SERVICE_FILE_TEMPLATE)
        template_vars = {
            'source': get_tmpl_path(SERVICE_FILE_TEMPLATE),
            'manifest': package.manifest.unmarshal(),
            'multi_instance': False,
            'multi_instance_services': multi_instance_services,
        }
        output_file = os.path.join(SYSTEMD_LOCATION, f'{name}.service')
        render_template(template, output_file, template_vars)
        log.info(f'generated {output_file}')

        if package.manifest['service']['asic-service']:
            output_file = os.path.join(SYSTEMD_LOCATION, f'{name}@.service')
            template_vars['multi_instance'] = True
            render_template(template, output_file, template_vars)
            log.info(f'generated {output_file}')

        if package.manifest['service']['delayed']:
            template_vars = {
                'source': get_tmpl_path(TIMER_UNIT_TEMPLATE),
                'manifest': package.manifest.unmarshal(),
                'multi_instance': False,
            }
            output_file = os.path.join(SYSTEMD_LOCATION, f'{name}.timer')
            template = os.path.join(TEMPLATES_PATH, TIMER_UNIT_TEMPLATE)
            render_template(template, output_file, template_vars)
            log.info(f'generated {output_file}')

            if package.manifest['service']['asic-service']:
                output_file = os.path.join(SYSTEMD_LOCATION, f'{name}@.timer')
                template_vars['multi_instance'] = True
                render_template(template, output_file, template_vars)
                log.info(f'generated {output_file}')

    def update_generated_services_conf_file(self, package: Package, remove=False):
        """ Updates generated_services.conf file.

        Args:
            package: Package to update generated_services.conf with.
            remove: True if update for removal process.
        Returns:
            None.
        """
        name = package.manifest['service']['name']
        asic_service= package.manifest['service']['asic-service']

        with open(GENERATED_SERVICES_CONF_FILE, 'r') as generated_services_conf_file:
            list_of_services = set(generated_services_conf_file.read().split())

        if not remove:
            list_of_services.add(f'{name}.service')
            if asic_service:
                list_of_services.add(f'{name}@.service')
        else:
            list_of_services.discard(f'{name}.service')
            list_of_services.discard(f'{name}@.service')

        # Write to tmp file and replace the original file with it
        with tempfile.NamedTemporaryFile('w', delete=False) as tmp:
            tmp.write('\n'.join(list_of_services))
            tmp.write('\n')
            tmp.flush()

            shutil.move(tmp.name, GENERATED_SERVICES_CONF_FILE)

    def update_dependent_list_file(self, package: Package, remove=False):
        """ This function updates dependent list file for packages listed in "dependent-of"
            (path: /etc/sonic/<service>_dependent file).

        Args:
            package: Package to update packages dependent of it.
            remove: True if update for removal process.
        Returns:
            None.
        """

        name = package.manifest['service']['name']
        dependent_of = package.manifest['service']['dependent-of']
        host_service = package.manifest['service']['host-service']
        asic_service = package.manifest['service']['asic-service']

        def update_dependent(service, name, multi_inst):
            if multi_inst:
                filename = f'{service}_multi_inst_dependent'
            else:
                filename = f'{service}_dependent'

            filepath = os.path.join(ETC_SONIC_PATH, filename)

            dependent_services = set()
            if os.path.exists(filepath):
                with open(filepath) as fp:
                    dependent_services.update({line.strip() for line in fp.readlines()})
            if remove:
                with contextlib.suppress(KeyError):
                    dependent_services.remove(name)
            else:
                dependent_services.add(name)
            with open(filepath, 'w') as fp:
                fp.write('\n'.join(dependent_services))

        for service in dependent_of:
            if host_service:
                update_dependent(service, name, multi_inst=False)
            if asic_service:
                update_dependent(service, name, multi_inst=True)

    def generate_dump_script(self, package):
        """ Generates dump plugin script for package.

        Args:
            package: Package object to generate dump plugin script for.
        Returns:
            None.
        """

        name = package.manifest['service']['name']

        if not package.manifest['package']['debug-dump']:
            return

        if not os.path.exists(DEBUG_DUMP_SCRIPT_LOCATION):
            os.mkdir(DEBUG_DUMP_SCRIPT_LOCATION)

        scrip_template = os.path.join(TEMPLATES_PATH, DEBUG_DUMP_SCRIPT_TEMPLATE)
        script_path = os.path.join(DEBUG_DUMP_SCRIPT_LOCATION, f'{name}')
        render_ctx = {
            'source': get_tmpl_path(SERVICE_MGMT_SCRIPT_TEMPLATE),
            'manifest': package.manifest.unmarshal(),
        }
        render_template(scrip_template, script_path, render_ctx, executable=True)
        log.info(f'generated {script_path}')

    def get_shutdown_sequence(self, reboot_type: str, packages: Dict[str, Package]):
        """ Returns shutdown sequence file for particular reboot type.

        Args:
            reboot_type: Reboot type to generated service shutdown sequence for.
            packages: Dict of installed packages.
        Returns:
            Ordered list of service names.
        """

        shutdown_graph = defaultdict(set)

        def service_exists(service):
            for package in packages.values():
                if package.manifest['service']['name'] == service:
                    return True
            log.info(f'Service {service} is not installed, it is skipped...')
            return False

        def filter_not_available(services):
            return set(filter(service_exists, services))

        for package in packages.values():
            service_props = package.manifest['service']
            after = filter_not_available(service_props[f'{reboot_type}-shutdown']['after'])
            before = filter_not_available(service_props[f'{reboot_type}-shutdown']['before'])

            if not after and not before:
                continue

            name = package.manifest['service']['name']
            shutdown_graph[name].update(after)

            for service in before:
                shutdown_graph[service].update({name})

        log.debug(f'shutdown graph {pformat(shutdown_graph)}')

        try:
            order = toposort_flatten(shutdown_graph)
        except CircularDependencyError as err:
            raise ServiceCreatorError(f'Circular dependency found in {reboot_type} error: {err}')

        log.debug(f'shutdown order {pformat(order)}')
        return order

    def generate_shutdown_sequence_file(self, reboot_type: str, packages: Dict[str, Package]):
        """ Generates shutdown sequence file for particular reboot type
            (path: /etc/sonic/<reboot-type>-reboot_order).

        Args:
            reboot_type: Reboot type to generated service shutdown sequence for.
            packages: Dict of installed packages.
        Returns:
            None.
        """

        order = self.get_shutdown_sequence(reboot_type, packages)
        with open(os.path.join(ETC_SONIC_PATH, f'{reboot_type}-reboot_order'), 'w') as file:
            file.write(' '.join(order))

    def generate_shutdown_sequence_files(self, packages: Dict[str, Package]):
        """ Generates shutdown sequence file for fast and warm reboot.
            (path: /etc/sonic/<reboot-type>-reboot_order).

        Args:
            packages: Dict of installed packages.
        Returns:
            None.
        """

        for reboot_type in ('fast', 'warm'):
            self.generate_shutdown_sequence_file(reboot_type, packages)

    def generate_service_reconciliation_file(self, package):
        """ Generates reconciliation file for package
            (path: /etc/sonic/<service>_reconcile).

        Args:
            package: Package object to generate service reconciliation file for.
        Returns:
            None
        """

        name = package.manifest['service']['name']
        all_processes = package.manifest['processes']
        processes = [process['name'] for process in all_processes if process['reconciles']]
        with open(os.path.join(ETC_SONIC_PATH, f'{name}_reconcile'), 'w') as file:
            file.write(' '.join(processes))

    def set_initial_config(self, package):
        """ Set initial package configuration from manifest.
        This method updates but does not override existing entries in tables.

        Args:
            package: Package object to set initial configuration for.
        Returns:
            None
        """

        init_cfg = package.manifest['package']['init-cfg']
        if not init_cfg:
            return

        def update_config_with_init_cfg(cfg, conn):
            for table, content in init_cfg.items():
                if not isinstance(content, dict):
                    continue

                for key, fvs in content.items():
                    key_cfg = cfg.get(table, {}).get(key, {})
                    key_cfg.update(fvs)
                    conn.mod_entry(table, key, key_cfg)

        for conn in self.sonic_db.get_connectors():
            cfg = conn.get_config()
            new_cfg = init_cfg.copy()
            utils.deep_update(new_cfg, cfg)
            self.validate_config(new_cfg)
            update_config_with_init_cfg(cfg, conn)

    def remove_config(self, package):
        """ Remove configuration based on package YANG module.

        Args:
            package: Package object remove initial configuration for.
        Returns:
            None
        """

        if not package.metadata.yang_modules:
            return

        for module in package.metadata.yang_modules:
            module_name = self.cfg_mgmt.get_module_name(module)
            for tablename, module in self.cfg_mgmt.sy.confDbYangMap.items():
                if module.get('module') != module_name:
                    continue

                for conn in self.sonic_db.get_connectors():
                    keys = conn.get_table(tablename).keys()
                    for key in keys:
                        conn.set_entry(tablename, key, None)

    def validate_config(self, config):
        """ Validate configuration through YANG.

        Args:
            config: Config DB data.
        Returns:
            None.
        Raises:
            Exception: if config does not pass YANG validation.
        """

        config = sonic_cfggen.FormatConverter.to_serialized(config)
        log.debug(f'validating configuration {pformat(config)}')
        # This will raise exception if configuration is not valid.
        # NOTE: loadData() modifies the state of ConfigMgmt instance.
        # This is not desired for configuration validation only purpose.
        # Although the config loaded into ConfigMgmt instance is not
        # interesting in this application so we don't care.
        self.cfg_mgmt.loadData(config)

    def install_yang_module(self, package: Package):
        """ Install package's yang module in the system.

        Args:
            package: Package object.
        Returns:
            None
        """

        if not package.metadata.yang_modules:
            return

        for module in package.metadata.yang_modules:
            self.cfg_mgmt.add_module(module)

    def uninstall_yang_module(self, package: Package):
        """ Uninstall package's yang module in the system.

        Args:
            package: Package object.
        Returns:
            None
        """

        if not package.metadata.yang_modules:
            return

        for module in package.metadata.yang_modules:
            module_name = self.cfg_mgmt.get_module_name(module)
            self.cfg_mgmt.remove_module(module_name)

    def install_autogen_cli_all(self, package: Package):
        """ Install autogenerated CLI plugins for package.

        Args:
            package: Package
        Returns:
            None
        """

        for command in SONIC_CLI_COMMANDS:
            self.install_autogen_cli(package, command)

    def uninstall_autogen_cli_all(self, package: Package):
        """ Remove autogenerated CLI plugins for package.

        Args:
            package: Package
        Returns:
            None
        """

        for command in SONIC_CLI_COMMANDS:
            self.uninstall_autogen_cli(package, command)

    def install_autogen_cli(self, package: Package, command: str):
        """ Install autogenerated CLI plugins for package for particular command.

        Args:
            package: Package.
            command: Name of command to generate CLI for.
        Returns:
            None
        """

        if not package.metadata.yang_modules:
            return
        if f'auto-generate-{command}' not in package.manifest['cli']:
            return
        if not package.manifest['cli'][f'auto-generate-{command}']:
            return

        for module_name in self._get_yang_modules_for_auto_gen(command, package):
            self.cli_gen.generate_cli_plugin(command, module_name)
            log.debug(f'{command} command line interface autogenerated for {module_name}')

    def uninstall_autogen_cli(self, package: Package, command: str):
        """ Uninstall autogenerated CLI plugins for package for particular command.

        Args:
            package: Package.
            command: Name of command to remove CLI.
        Returns:
            None
        """

        if not package.metadata.yang_modules:
            return
        if f'auto-generate-{command}' not in package.manifest['cli']:
            return
        if not package.manifest['cli'][f'auto-generate-{command}']:
            return

        for module_name in self._get_yang_modules_for_auto_gen(command, package):
            self.cli_gen.remove_cli_plugin(command, module_name)
            log.debug(f'{command} command line interface removed for {module_name}')

    def _post_operation_hook(self):
        """ Common operations executed after service is created/removed. """

        if not in_chroot():
            run_command(['systemctl', 'daemon-reload'])

    def _get_yang_modules_for_auto_gen(self, command: str, package: Package):
        source_yang_modules = package.manifest['cli'][f'auto-generate-{command}-source-yang-modules']

        def filter_yang_modules_for_auto_gen(module_name):
            if not source_yang_modules:
                return True
            if module_name in source_yang_modules:
                return True
            return False

        filtered_yang_modules = filter(filter_yang_modules_for_auto_gen,
                map(self.cfg_mgmt.get_module_name, package.metadata.yang_modules))
        return list(filtered_yang_modules)

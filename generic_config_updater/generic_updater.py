import json
import os
from enum import Enum
from .gu_common import GenericConfigUpdaterError, EmptyTableError, ConfigWrapper, \
                       DryRunConfigWrapper, PatchWrapper, genericUpdaterLogging
from .patch_sorter import StrictPatchSorter, NonStrictPatchSorter, ConfigSplitter, \
                          TablesWithoutYangConfigSplitter, IgnorePathsFromYangConfigSplitter
from .change_applier import ChangeApplier, DryRunChangeApplier

CHECKPOINTS_DIR = "/etc/sonic/checkpoints"
CHECKPOINT_EXT = ".cp.json"

class ConfigLock:
    def acquire_lock(self):
        # TODO: Implement ConfigLock
        pass

    def release_lock(self):
        # TODO: Implement ConfigLock
        pass


class ConfigFormat(Enum):
    CONFIGDB = 1
    SONICYANG = 2

class PatchApplier:
    def __init__(self,
                 patchsorter=None,
                 changeapplier=None,
                 config_wrapper=None,
                 patch_wrapper=None):
        self.logger = genericUpdaterLogging.get_logger(title="Patch Applier", print_all_to_console=True)
        self.config_wrapper = config_wrapper if config_wrapper is not None else ConfigWrapper()
        self.patch_wrapper = patch_wrapper if patch_wrapper is not None else PatchWrapper()
        self.patchsorter = patchsorter if patchsorter is not None else StrictPatchSorter(self.config_wrapper, self.patch_wrapper)
        self.changeapplier = changeapplier if changeapplier is not None else ChangeApplier()

    def apply(self, patch, sort=True):
        self.logger.log_notice("Patch application starting.")
        self.logger.log_notice(f"Patch: {patch}")

        # Get old config
        self.logger.log_notice("Getting current config db.")
        old_config = self.config_wrapper.get_config_db_as_json()

        # Generate target config
        self.logger.log_notice("Simulating the target full config after applying the patch.")
        target_config = self.patch_wrapper.simulate_patch(patch, old_config)
        
        # Validate all JsonPatch operations on specified fields
        self.logger.log_notice("Validating all JsonPatch operations are permitted on the specified fields")
        self.config_wrapper.validate_field_operation(old_config, target_config)

        # Validate target config does not have empty tables since they do not show up in ConfigDb
        self.logger.log_notice("Validating target config does not have empty tables, " \
                               "since they do not show up in ConfigDb.")
        empty_tables = self.config_wrapper.get_empty_tables(target_config)
        if empty_tables: # if there are empty tables
            empty_tables_txt = ", ".join(empty_tables)
            raise EmptyTableError("Given patch is not valid because it will result in empty tables " \
                             "which is not allowed in ConfigDb. " \
                            f"Table{'s' if len(empty_tables) != 1 else ''}: {empty_tables_txt}")

        # Generate list of changes to apply
        if sort:
            self.logger.log_notice("Sorting patch updates.")
            changes = self.patchsorter.sort(patch)
        else:
            self.logger.log_notice("Converting patch to JsonChange.")
            changes = [JsonChange(jsonpatch.JsonPatch([element])) for element in patch]
            
        changes_len = len(changes)
        self.logger.log_notice(f"The patch was converted into {changes_len} " \
                          f"change{'s' if changes_len != 1 else ''}{':' if changes_len > 0 else '.'}")

        for change in changes:
            self.logger.log_notice(f"  * {change}")

        # Apply changes in order
        self.logger.log_notice(f"Applying {changes_len} change{'s' if changes_len != 1 else ''} " \
                               f"in order{':' if changes_len > 0 else '.'}")
        for change in changes:
            self.logger.log_notice(f"  * {change}")
            self.changeapplier.apply(change)

        # Validate config updated successfully
        self.logger.log_notice("Verifying patch updates are reflected on ConfigDB.")
        new_config = self.config_wrapper.get_config_db_as_json()
        self.changeapplier.remove_backend_tables_from_config(target_config)
        self.changeapplier.remove_backend_tables_from_config(new_config)
        if not(self.patch_wrapper.verify_same_json(target_config, new_config)):
            raise GenericConfigUpdaterError(f"After applying patch to config, there are still some parts not updated")

        self.logger.log_notice("Patch application completed.")

class ConfigReplacer:
    def __init__(self, patch_applier=None, config_wrapper=None, patch_wrapper=None):
        self.logger = genericUpdaterLogging.get_logger(title="Config Replacer", print_all_to_console=True)
        self.patch_applier = patch_applier if patch_applier is not None else PatchApplier()
        self.config_wrapper = config_wrapper if config_wrapper is not None else ConfigWrapper()
        self.patch_wrapper = patch_wrapper if patch_wrapper is not None else PatchWrapper()

    def replace(self, target_config):
        self.logger.log_notice("Config replacement starting.")
        self.logger.log_notice(f"Target config length: {len(json.dumps(target_config))}.")

        self.logger.log_notice("Getting current config db.")
        old_config = self.config_wrapper.get_config_db_as_json()

        # mode from PORT table will be remove from both old_config & target_config to resolve rollback & replace issue
        old_config = self.switchport_mode_remove(old_config)
        target_config = self.switchport_mode_remove(target_config)
        
        self.logger.log_notice("Generating patch between target config and current config db.")
        patch = self.patch_wrapper.generate_patch(old_config, target_config)
        self.logger.log_debug(f"Generated patch: {patch}.") # debug since the patch will printed again in 'patch_applier.apply'

        self.logger.log_notice("Applying patch using 'Patch Applier'.")
        self.patch_applier.apply(patch)

        self.logger.log_notice("Verifying config replacement is reflected on ConfigDB.")
        new_config = self.config_wrapper.get_config_db_as_json()
        if not(self.patch_wrapper.verify_same_json(target_config, new_config)):
            raise GenericConfigUpdaterError(f"After replacing config, there is still some parts not updated")

        self.logger.log_notice("Config replacement completed.")

    @staticmethod
    def switchport_mode_remove(config):
        """ 
        This method will check & remove mode attribute in PORT table. 
        It is to resolve rollback check patch where it failed 
        due to missing "mode"  in patch applier. 
        """
        current_mode  = 'mode'
        exisitng_port = 'PORT'
        if exisitng_port in config:
            for port, port_data in config[exisitng_port].items():
                if current_mode in port_data:
                    del config[exisitng_port][port][current_mode]
        return config

class FileSystemConfigRollbacker:
    def __init__(self,
                 checkpoints_dir=CHECKPOINTS_DIR,
                 config_replacer=None,
                 config_wrapper=None):
        self.logger = genericUpdaterLogging.get_logger(title="Config Rollbacker", print_all_to_console=True)
        self.checkpoints_dir = checkpoints_dir
        self.config_replacer = config_replacer if config_replacer is not None else ConfigReplacer()
        self.config_wrapper = config_wrapper if config_wrapper is not None else ConfigWrapper()

    def rollback(self, checkpoint_name):
        self.logger.log_notice("Config rollbacking starting.")
        self.logger.log_notice(f"Checkpoint name: {checkpoint_name}.")

        self.logger.log_notice(f"Verifying '{checkpoint_name}' exists.")
        if not self._check_checkpoint_exists(checkpoint_name):
            raise ValueError(f"Checkpoint '{checkpoint_name}' does not exist")

        self.logger.log_notice(f"Loading checkpoint into memory.")
        target_config = self._get_checkpoint_content(checkpoint_name)

        self.logger.log_notice(f"Replacing config using 'Config Replacer'.")
        self.config_replacer.replace(target_config)

        self.logger.log_notice("Config rollbacking completed.")

    def checkpoint(self, checkpoint_name):
        self.logger.log_notice("Config checkpoint starting.")
        self.logger.log_notice(f"Checkpoint name: {checkpoint_name}.")

        self.logger.log_notice("Getting current config db.")
        json_content = self.config_wrapper.get_config_db_as_json()

        self.logger.log_notice("Getting checkpoint full-path.")
        path = self._get_checkpoint_full_path(checkpoint_name)

        self.logger.log_notice("Ensuring checkpoint directory exist.")
        self._ensure_checkpoints_dir_exists()

        self.logger.log_notice(f"Saving config db content to {path}.")
        self._save_json_file(path, json_content)

        self.logger.log_notice("Config checkpoint completed.")

    def list_checkpoints(self):
        self.logger.log_info("Listing checkpoints starting.")
        
        self.logger.log_info(f"Verifying checkpoints directory '{self.checkpoints_dir}' exists.")
        if not self._checkpoints_dir_exist():
            self.logger.log_info("Checkpoints directory is empty, returning empty checkpoints list.")
            return []

        self.logger.log_info("Getting checkpoints in checkpoints directory.")
        checkpoint_names = self._get_checkpoint_names()

        checkpoints_len = len(checkpoint_names)
        self.logger.log_info(f"Found {checkpoints_len} checkpoint{'s' if checkpoints_len != 1 else ''}{':' if checkpoints_len > 0 else '.'}")
        for checkpoint_name in checkpoint_names:
            self.logger.log_info(f"  * {checkpoint_name}")

        self.logger.log_info("Listing checkpoints completed.")

        return checkpoint_names

    def delete_checkpoint(self, checkpoint_name):
        self.logger.log_notice("Deleting checkpoint starting.")
        self.logger.log_notice(f"Checkpoint name: {checkpoint_name}.")

        self.logger.log_notice(f"Checking checkpoint exists.")
        if not self._check_checkpoint_exists(checkpoint_name):
            raise ValueError(f"Checkpoint '{checkpoint_name}' does not exist")

        self.logger.log_notice(f"Deleting checkpoint.")
        self._delete_checkpoint(checkpoint_name)

        self.logger.log_notice("Deleting checkpoint completed.")

    def _ensure_checkpoints_dir_exists(self):
        os.makedirs(self.checkpoints_dir, exist_ok=True)

    def _save_json_file(self, path, json_content):
        with open(path, "w") as fh:
            fh.write(json.dumps(json_content))

    def _get_checkpoint_content(self, checkpoint_name):
        path = self._get_checkpoint_full_path(checkpoint_name)
        with open(path) as fh:
            text = fh.read()
            return json.loads(text)

    def _get_checkpoint_full_path(self, name):
        return os.path.join(self.checkpoints_dir, f"{name}{CHECKPOINT_EXT}")

    def _get_checkpoint_names(self):
        file_names = []
        for file_name in os.listdir(self.checkpoints_dir):
            if file_name.endswith(CHECKPOINT_EXT):
                # Remove extension from file name.
                # Example assuming ext is '.cp.json', then 'checkpoint1.cp.json' becomes 'checkpoint1'
                file_names.append(file_name[:-len(CHECKPOINT_EXT)])

        return file_names

    def _checkpoints_dir_exist(self):
        return os.path.isdir(self.checkpoints_dir)

    def _check_checkpoint_exists(self, name):
        path = self._get_checkpoint_full_path(name)
        return os.path.isfile(path)

    def _delete_checkpoint(self, name):
        path = self._get_checkpoint_full_path(name)
        return os.remove(path)

class Decorator(PatchApplier, ConfigReplacer, FileSystemConfigRollbacker):
    def __init__(self, decorated_patch_applier=None, decorated_config_replacer=None, decorated_config_rollbacker=None):
        # initing base classes to make LGTM happy
        PatchApplier.__init__(self)
        ConfigReplacer.__init__(self)
        FileSystemConfigRollbacker.__init__(self)

        self.decorated_patch_applier = decorated_patch_applier
        self.decorated_config_replacer = decorated_config_replacer
        self.decorated_config_rollbacker = decorated_config_rollbacker

    def apply(self, patch):
        self.decorated_patch_applier.apply(patch)

    def replace(self, target_config):
        self.decorated_config_replacer.replace(target_config)

    def rollback(self, checkpoint_name):
        self.decorated_config_rollbacker.rollback(checkpoint_name)

    def checkpoint(self, checkpoint_name):
        self.decorated_config_rollbacker.checkpoint(checkpoint_name)

    def list_checkpoints(self):
        return self.decorated_config_rollbacker.list_checkpoints()

    def delete_checkpoint(self, checkpoint_name):
        self.decorated_config_rollbacker.delete_checkpoint(checkpoint_name)

class SonicYangDecorator(Decorator):
    def __init__(self, patch_wrapper, config_wrapper, decorated_patch_applier=None, decorated_config_replacer=None):
        Decorator.__init__(self, decorated_patch_applier, decorated_config_replacer)

        self.patch_wrapper = patch_wrapper
        self.config_wrapper = config_wrapper

    def apply(self, patch):
        config_db_patch = self.patch_wrapper.convert_sonic_yang_patch_to_config_db_patch(patch)
        Decorator.apply(self, config_db_patch)

    def replace(self, target_config):
        config_db_target_config = self.config_wrapper.convert_sonic_yang_to_config_db(target_config)
        Decorator.replace(self, config_db_target_config)

class ConfigLockDecorator(Decorator):
    def __init__(self,
                 decorated_patch_applier=None,
                 decorated_config_replacer=None,
                 decorated_config_rollbacker=None,
                 config_lock = ConfigLock()):
        Decorator.__init__(self, decorated_patch_applier, decorated_config_replacer, decorated_config_rollbacker)

        self.config_lock = config_lock

    def apply(self, patch, sort=True):
        self.execute_write_action(Decorator.apply, self, patch)

    def replace(self, target_config):
        self.execute_write_action(Decorator.replace, self, target_config)

    def rollback(self, checkpoint_name):
        self.execute_write_action(Decorator.rollback, self, checkpoint_name)

    def checkpoint(self, checkpoint_name):
        self.execute_write_action(Decorator.checkpoint, self, checkpoint_name)

    def execute_write_action(self, action, *args):
        self.config_lock.acquire_lock()
        action(*args)
        self.config_lock.release_lock()

class GenericUpdateFactory:
    def create_patch_applier(self, config_format, verbose, dry_run, ignore_non_yang_tables, ignore_paths):
        self.init_verbose_logging(verbose)
        config_wrapper = self.get_config_wrapper(dry_run)
        change_applier = self.get_change_applier(dry_run, config_wrapper)
        patch_wrapper = PatchWrapper(config_wrapper)
        patch_sorter = self.get_patch_sorter(ignore_non_yang_tables, ignore_paths, config_wrapper, patch_wrapper)
        patch_applier = PatchApplier(config_wrapper=config_wrapper,
                                     patchsorter=patch_sorter,
                                     patch_wrapper=patch_wrapper,
                                     changeapplier=change_applier)

        if config_format == ConfigFormat.CONFIGDB:
            pass
        elif config_format == ConfigFormat.SONICYANG:
            patch_applier = SonicYangDecorator(
                    decorated_patch_applier = patch_applier, patch_wrapper=patch_wrapper, config_wrapper=config_wrapper)
        else:
            raise ValueError(f"config-format '{config_format}' is not supported")

        if not dry_run:
            patch_applier = ConfigLockDecorator(decorated_patch_applier = patch_applier)

        return patch_applier

    def create_config_replacer(self, config_format, verbose, dry_run, ignore_non_yang_tables, ignore_paths):
        self.init_verbose_logging(verbose)

        config_wrapper = self.get_config_wrapper(dry_run)
        change_applier = self.get_change_applier(dry_run, config_wrapper)
        patch_wrapper = PatchWrapper(config_wrapper)
        patch_sorter = self.get_patch_sorter(ignore_non_yang_tables, ignore_paths, config_wrapper, patch_wrapper)
        patch_applier = PatchApplier(config_wrapper=config_wrapper,
                                     patchsorter=patch_sorter,
                                     patch_wrapper=patch_wrapper,
                                     changeapplier=change_applier)

        config_replacer = ConfigReplacer(patch_applier=patch_applier, config_wrapper=config_wrapper)
        if config_format == ConfigFormat.CONFIGDB:
            pass
        elif config_format == ConfigFormat.SONICYANG:
            config_replacer = SonicYangDecorator(
                    decorated_config_replacer = config_replacer, patch_wrapper=patch_wrapper, config_wrapper=config_wrapper)
        else:
            raise ValueError(f"config-format '{config_format}' is not supported")

        if not dry_run:
            config_replacer = ConfigLockDecorator(decorated_config_replacer = config_replacer)

        return config_replacer

    def create_config_rollbacker(self, verbose, dry_run=False, ignore_non_yang_tables=False, ignore_paths=[]):
        self.init_verbose_logging(verbose)

        config_wrapper = self.get_config_wrapper(dry_run)
        change_applier = self.get_change_applier(dry_run, config_wrapper)
        patch_wrapper = PatchWrapper(config_wrapper)
        patch_sorter = self.get_patch_sorter(ignore_non_yang_tables, ignore_paths, config_wrapper, patch_wrapper)
        patch_applier = PatchApplier(config_wrapper=config_wrapper,
                                     patchsorter=patch_sorter,
                                     patch_wrapper=patch_wrapper,
                                     changeapplier=change_applier)

        config_replacer = ConfigReplacer(config_wrapper=config_wrapper, patch_applier=patch_applier)
        config_rollbacker = FileSystemConfigRollbacker(config_wrapper = config_wrapper, config_replacer = config_replacer)

        if not dry_run:
            config_rollbacker = ConfigLockDecorator(decorated_config_rollbacker = config_rollbacker)

        return config_rollbacker

    def init_verbose_logging(self, verbose):
        genericUpdaterLogging.set_verbose(verbose)

    def get_config_wrapper(self, dry_run):
        if dry_run:
            return DryRunConfigWrapper()
        else:
            return ConfigWrapper()

    def get_change_applier(self, dry_run, config_wrapper):
        if dry_run:
            return DryRunChangeApplier(config_wrapper)
        else:
            return ChangeApplier()

    def get_patch_sorter(self, ignore_non_yang_tables, ignore_paths, config_wrapper, patch_wrapper):
        if not ignore_non_yang_tables and not ignore_paths:
            return StrictPatchSorter(config_wrapper, patch_wrapper)

        inner_config_splitters = []
        if ignore_non_yang_tables:
            inner_config_splitters.append(TablesWithoutYangConfigSplitter(config_wrapper))

        if ignore_paths:
            inner_config_splitters.append(IgnorePathsFromYangConfigSplitter(ignore_paths, config_wrapper))

        config_splitter = ConfigSplitter(config_wrapper, inner_config_splitters)

        return NonStrictPatchSorter(config_wrapper, patch_wrapper, config_splitter)

class GenericUpdater:
    def __init__(self, generic_update_factory=None):
        self.generic_update_factory = \
            generic_update_factory if generic_update_factory is not None else GenericUpdateFactory()

    def apply_patch(self, patch, config_format, verbose, dry_run, ignore_non_yang_tables, ignore_paths, sort=True):
        patch_applier = self.generic_update_factory.create_patch_applier(config_format, verbose, dry_run, ignore_non_yang_tables, ignore_paths)
        patch_applier.apply(patch, sort)

    def replace(self, target_config, config_format, verbose, dry_run, ignore_non_yang_tables, ignore_paths):
        config_replacer = self.generic_update_factory.create_config_replacer(config_format, verbose, dry_run, ignore_non_yang_tables, ignore_paths)
        config_replacer.replace(target_config)

    def rollback(self, checkpoint_name, verbose, dry_run, ignore_non_yang_tables, ignore_paths):
        config_rollbacker = self.generic_update_factory.create_config_rollbacker(verbose, dry_run, ignore_non_yang_tables, ignore_paths)
        config_rollbacker.rollback(checkpoint_name)

    def checkpoint(self, checkpoint_name, verbose):
        config_rollbacker = self.generic_update_factory.create_config_rollbacker(verbose)
        config_rollbacker.checkpoint(checkpoint_name)

    def delete_checkpoint(self, checkpoint_name, verbose):
        config_rollbacker = self.generic_update_factory.create_config_rollbacker(verbose)
        config_rollbacker.delete_checkpoint(checkpoint_name)

    def list_checkpoints(self, verbose):
        config_rollbacker = self.generic_update_factory.create_config_rollbacker(verbose)
        return config_rollbacker.list_checkpoints()

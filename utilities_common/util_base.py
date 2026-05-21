import os
import pkgutil
import importlib

from sonic_py_common import logger

# Constants ====================================================================
PDDF_SUPPORT_FILE = '/usr/share/sonic/platform/pddf_support'

# Helper class

log = logger.Logger()


class UtilHelper(object):
    def __init__(self):
        pass

    def load_plugins(self, plugins_namespace):
        """ Discover and load CLI plugins. Yield a plugin module. """

        def iter_namespace(ns_pkg):
            return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + ".")

        for _, module_name, ispkg in iter_namespace(plugins_namespace):
            if ispkg:
                yield from self.load_plugins(importlib.import_module(module_name))
                continue
            log.log_debug('importing plugin: {}'.format(module_name))
            try:
                module = importlib.import_module(module_name)

            except ModuleNotFoundError as err:
                log.log_warning('failed to import plugin {}: {}'.format(module_name, err),
                                also_print_to_console=True)
                continue

            except Exception as err:
                log.log_error('failed to import plugin {}: {}'.format(module_name, err),
                              also_print_to_console=True)
                continue

            yield module

    def register_plugin(self, plugin, root_command):
        """ Register plugin in top-level command root_command. """

        name = plugin.__name__
        log.log_debug('registering plugin: {}'.format(name))
        try:
            plugin.register(root_command)
        except Exception as err:
            log.log_error('failed to import plugin {}: {}'.format(name, err),
                          also_print_to_console=True)

    # try get information from platform API and return a default value if caught NotImplementedError
    def try_get(self, callback, default=None):
        """
        Handy function to invoke the callback, catch NotImplementedError and return a default value
        :param callback: Callback to be invoked
        :param default: Default return value if exception occur
        :return: Default return value if exception occur else return value of the callback
        """
        try:
            ret = callback()
            if ret is None:
                ret = default
        except NotImplementedError:
            ret = default

        return ret

    # Instantiate platform-specific Chassis class
    def load_platform_chassis(self):
        chassis = None

        # Load 2.0 platform API chassis class
        try:
            import sonic_platform
            chassis = sonic_platform.platform.Platform().get_chassis()
        except Exception as e:
            raise Exception("Failed to load chassis due to {}".format(repr(e)))

        return chassis

    # Check for PDDF mode enabled
    def check_pddf_mode(self):
        if os.path.exists(PDDF_SUPPORT_FILE):
            return True
        else:
            return False

    def load_and_register_plugins(self, plugins, cli):
        """ Load plugins and register them """

        for plugin in self.load_plugins(plugins):
            self.register_plugin(plugin, cli)
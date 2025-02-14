#!/usr/bin/env python3
#
# module.py
#
# Utility helper for modules within SONiC

from sonic_py_common import syslogger
from utilities_common.util_base import UtilHelper

SYSLOG_IDENTIFIER = "module"
NOT_AVAILABLE = 'N/A'
INVALID_MODULE_INDEX = -1

# Load the UtilHelper class
util = UtilHelper()

# Global logger instance
log = syslogger.SysLogger(SYSLOG_IDENTIFIER)


class ModuleHelper:
    def __init__(self):
        # Global variable for platform chassis
        self.platform_chassis = util.load_platform_chassis()
        if not self.platform_chassis:
            log.log_error("Failed to load platform chassis")

    def try_get_args(self, callback, *args, **kwargs):
        """
        Handy function to invoke the callback and catch NotImplementedError
        :param callback: Callback to be invoked
        :param args: Arguments to be passed to callback
        :param kwargs: Default return value if exception occur
        :return: Default return value if exception occur else return value of the callback
        """
        default = kwargs.get('default', NOT_AVAILABLE)
        try:
            ret = callback(*args)
            if ret is None:
                ret = default
        except NotImplementedError:
            ret = default

        return ret

    def reboot_module(self, module_name, reboot_type):
        """
        Reboot the specified module by invoking the platform API.

        Args:
            module_name (str): The name of the module to reboot.
            reboot_type (str): The type of reboot requested for the module.

        Returns:
            bool: True if the reboot command was successfully sent, False otherwise.
        """
        module_name = module_name.upper()
        module_index = self.try_get_args(self.platform_chassis.get_module_index, module_name,
                                         default=INVALID_MODULE_INDEX)
        if module_index < 0:
            log.log_error("Unable to get module-index for {}". format(module_name))
            return False

        if not hasattr(self.platform_chassis.get_module(module_index), 'reboot'):
            log.log_error("Reboot method not found in platform chassis")
            return False

        log.log_info("Rebooting module {} with reboot_type {}...".format(module_name, reboot_type))
        status = self.try_get_args(self.platform_chassis.get_module(module_index).reboot, reboot_type, default=False)
        if not status:
            log.log_error("Reboot status for module {}: {}".format(module_name, status))
            return False

        return True

    def pci_detach_module(self, module_name):
        """
        Detach the specified module by invoking the platform API.
        Note: Caller to make sure this method is not invoked concurrently with
        pci_reattach_module for the same module.

        Args:
            module_name (str): The name of the module to detach.

        Returns:
            bool: True if the detach command was successfully sent, False otherwise.
        """
        module_name = module_name.upper()
        module_index = self.try_get_args(self.platform_chassis.get_module_index, module_name,
                                         default=INVALID_MODULE_INDEX)
        if module_index < 0:
            log.log_error("Unable to get module-index for {}". format(module_name))
            return False

        if not hasattr(self.platform_chassis.get_module(module_index), 'pci_detach'):
            log.log_error("PCI detach method not found in platform chassis")
            return False

        log.log_info("Detaching module {}...".format(module_name))
        status = util.try_get(self.platform_chassis.get_module(module_index).pci_detach, default=False)
        if not status:
            log.log_error("PCI detach status for module {}: {}".format(module_name, status))
            return False

        return True

    def pci_reattach_module(self, module_name):
        """
        Rescan the specified module by invoking the platform API.
        Note: Caller to make sure this method is not invoked concurrently with
        pci_detach_module for the same module.

        Args:
            module_name (str): The name of the module to rescan.

        Returns:
            bool: True if the rescan command was successfully sent, False otherwise.
        """
        module_name = module_name.upper()
        module_index = self.try_get_args(self.platform_chassis.get_module_index, module_name,
                                         default=INVALID_MODULE_INDEX)
        if module_index < 0:
            log.log_error("Unable to get module-index for {}". format(module_name))
            return False

        if not hasattr(self.platform_chassis.get_module(module_index), 'pci_reattach'):
            log.log_error("PCI reattach method not found in platform chassis")
            return False

        log.log_info("Rescanning module {}...".format(module_name))
        status = util.try_get(self.platform_chassis.get_module(module_index).pci_reattach, default=False)
        if not status:
            log.log_error("PCI rescan status for module {}: {}".format(module_name, status))
            return False

        return True

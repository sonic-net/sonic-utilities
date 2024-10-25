#!/usr/bin/env python3
#
# reboot_helper.py
#
# Utility helper for reboot within SONiC

import sys
import syslog
import sonic_platform

chk_log_level = syslog.LOG_ERR


def _log_msg(lvl, pfx, msg):
    if lvl <= chk_log_level:
        print("{}: {}".format(pfx, msg))
        syslog.syslog(lvl, msg)


def log_err(m):
    _log_msg(syslog.LOG_ERR, "Err", m)


def log_info(m):
    _log_msg(syslog.LOG_INFO, "Info",  m)


def log_debug(m):
    _log_msg(syslog.LOG_DEBUG, "Debug", m)


# Global variable for platform chassis
platform_chassis = None


def load_platform_chassis():
    global platform_chassis

    # Load new platform API class
    try:
        platform_chassis = sonic_platform.platform.Platform().get_chassis()
    except Exception as e:
        log_err("Failed to instantiate Chassis due to {}".format(repr(e)))
        return False

    if not platform_chassis:
        log_err("Platform chassis is not loaded")
        return False

    return True


def reboot_module(module_name):
    """Reboot the specified module by invoking the platform API"""

    # Load the platform chassis if not already loaded
    if not load_platform_chassis():
        log_err("Failed to load platform chassis")
        return False

    if not platform_chassis.is_smartswitch():
        return False

    # Iterate over the modules to find the one with the specified name
    try:
        # Use get_all_modules to retrieve all modules on the chassis
        modules = platform_chassis.get_all_modules()

        # Iterate over the modules to find the one with the specified name
        for module in modules:
            # Check if the module name matches the provided module_name
            if module and module.get_name() == module_name:
                # Reboot the module
                log_info(f"Rebooting module {module_name}...")
                try:
                    module.reboot()
                    log_info("Reboot command sent for module {module_name}")
                    return True
                except NotImplementedError:
                    log_err("Reboot not implemented for module {module_name}.")
                    return False
                except Exception as e:  # noqa: F841
                    log_err("An error occurred while rebooting module {module_name}: {e}")
                    return False

        # If the module with the given name is not found
        log_err("Module {module_name} not found")
        return False

    except Exception as e:  # noqa: F841
        log_err("Error occurred while rebooting module {module_name}: {repr(e)}")
        return False


def is_dpu():
    """Check if script is running on DPU module"""

    # Load the platform chassis if not already loaded
    if not load_platform_chassis():
        log_err("Failed to load platform chassis")
        return False

    if not platform_chassis.is_smartswitch():
        return False

    # Iterate over the modules
    for module in platform_chassis.get_all_modules():
        if "DPU" in module.get_name():
            return True

    return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: reboot_helper.py <command> <module_name>")
        sys.exit(1)

    command = sys.argv[1]
    module_name = sys.argv[2]

    if command == "reboot":
        success = reboot_module(module_name)
        if not success:
            sys.exit(1)
        else:
            print("Reboot command sent for module {module_name}")
    elif command == "is_dpu":
        if is_dpu():
            print("Script is running on DPU module")
        else:
            sys.exit(1)
    else:
        print("Unknown command: {command}")
        sys.exit(1)

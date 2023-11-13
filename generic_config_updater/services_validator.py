import os
import time
from .gu_common import genericUpdaterLogging

logger = genericUpdaterLogging.get_logger(title="Service Validator")

print_to_console = False

def set_verbose(verbose=False):
    global print_to_console, logger

    print_to_console = verbose
    if verbose:
        logger.set_min_log_priority_debug()
    else:
        logger.set_min_log_priority_notice()


def _service_restart(svc_name):
    rc = os.system(f"systemctl restart {svc_name}")
    if rc != 0:
        # This failure is likely due to too many restarts
        #
        rc = os.system(f"systemctl reset-failed {svc_name}")
        logger.log(logger.LOG_PRIORITY_ERROR, 
                f"Service has been reset. rc={rc}; Try restart again...",
                print_to_console)

        rc = os.system(f"systemctl restart {svc_name}")
        if rc != 0:
            # Even with reset-failed, restart fails.
            # Give a pause before retry.
            #
            logger.log(logger.LOG_PRIORITY_ERROR,
                    f"Restart failed for {svc_name} rc={rc} after reset; Pause for 10s & retry",
                    print_to_console)
            time.sleep(10)
            rc = os.system(f"systemctl restart {svc_name}")

    if rc == 0:
        logger.log(logger.LOG_PRIORITY_NOTICE,
                f"Restart succeeded for {svc_name}",
                print_to_console)
    else:
        logger.log(logger.LOG_PRIORITY_ERROR,
                f"Restart failed for {svc_name} rc={rc}",
                print_to_console)
    return rc == 0


def rsyslog_validator(old_config, upd_config, keys):
    old_syslog = old_config.get("SYSLOG_SERVER", {})
    upd_syslog = upd_config.get("SYSLOG_SERVER", {})

    if old_syslog != upd_syslog:
        os.system("systemctl reset-failed rsyslog-config rsyslog")
        rc = os.system("systemctl restart rsyslog-config")
        if rc != 0:
            return False
    return True


def dhcp_validator(old_config, upd_config, keys):
    return _service_restart("dhcp_relay")


def vlan_validator(old_config, upd_config, keys):
    old_vlan = old_config.get("VLAN", {})
    upd_vlan = upd_config.get("VLAN", {})

    for key in set(old_vlan.keys()).union(set(upd_vlan.keys())):
        if (old_vlan.get(key, {}).get("dhcp_servers", []) != 
                upd_vlan.get(key, {}).get("dhcp_servers", [])):
            return _service_restart("dhcp_relay")
    # No update to DHCP servers.
    return True

def caclmgrd_validator(old_config, upd_config, keys):
    old_acltable = old_config.get("ACL_TABLE", {})
    upd_acltable = upd_config.get("ACL_TABLE", {})

    old_cacltable = [table for table, fields in old_acltable.items()
                     if fields.get("type", "") == "CTRLPLANE"]
    upd_cacltable = [table for table, fields in upd_acltable.items()
                     if fields.get("type", "") == "CTRLPLANE"]

    old_aclrule = old_config.get("ACL_RULE", {})
    upd_aclrule = upd_config.get("ACL_RULE", {})

    old_caclrule = [rule for rule in old_aclrule
                    if rule.split("|")[0] in old_cacltable]
    upd_caclrule = [rule for rule in upd_aclrule
                    if rule.split("|")[0] in upd_cacltable]

    # Only sleep when cacl rule is changed as this will update iptable.
    for key in set(old_caclrule).union(set(upd_caclrule)):
        if (old_aclrule.get(key, {}) != upd_aclrule.get(key, {})):
            # caclmgrd will update in 0.5 sec when configuration stops,
            # we sleep 1 sec to make sure it does update.
            time.sleep(1)
            return True
    # No update to ACL_RULE.
    return True


def ntp_validator(old_config, upd_config, keys):
    return _service_restart("ntp-config")

def vlanintf_validator(old_config, upd_config, keys):
    old_vlan_intf = old_config.get("VLAN_INTERFACE", {})
    upd_vlan_intf = upd_config.get("VLAN_INTERFACE", {})

    # Get the tuple with format (iface, iface_ip) then check deleted tuple
    # Example:
    # old_keys = [("Vlan1000", "192.168.0.1")]
    # upd_keys = [("Vlan1000", "192.168.0.2")]
    old_keys = [ tuple(key.split("|"))
            for key in old_vlan_intf if len(key.split("|")) == 2 ]
    upd_keys = [ tuple(key.split("|"))
            for key in upd_vlan_intf if len(key.split("|")) == 2 ]

    deleted_keys = list(set(old_keys) - set(upd_keys))
    for key in deleted_keys:
        iface, iface_ip = key
        rc = os.system(f"ip neigh flush dev {iface} {iface_ip}")
        if rc:
            return False
    return True

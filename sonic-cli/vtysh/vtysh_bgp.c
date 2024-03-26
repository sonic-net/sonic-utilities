#include <zebra.h>
#include "command.h"
#include "vtysh.h"
#include "if.h"

#define BGP_HELP_STR        "BGP Specific commands\n"
#define ADVERTISE_LOW_PRIORITY_STR  "Advertise routes with low priority\n"
#define BGP_NETWORK_STR     "Specify a network to announce via BGP\n"
#define IP_PREFIX_STR       "IP prefix <network>/<length>,  e.g.,  35.0.0.0/8"

DEFUN(no_bgp_advertise_low_priority_config,
      no_bgp_advertise_low_priority_config_cmd,
      "no bgp advertise-low-priority",
      NO_STR
      BGP_HELP_STR
      ADVERTISE_LOW_PRIORITY_STR)
{
    char cmdstr[128];
    snprintf(cmdstr, 128, "sudo config bgp delete advertise-low-priority");
    execute_linux_cmd_pipe(cmdstr);
    return CMD_SUCCESS;
}

DEFUN(bgp_advertise_low_priority_config,
      bgp_advertise_low_priority_config_cmd,
      "bgp advertise-low-priority",
      BGP_HELP_STR
      ADVERTISE_LOW_PRIORITY_STR)
{
    char cmdstr[128];
    snprintf(cmdstr, 128, "sudo config bgp add advertise-low-priority");
    execute_linux_cmd_pipe(cmdstr);
    return CMD_SUCCESS;
}

DEFUN(no_bgp_network_config,
      no_bgp_network_config_cmd,
      "no bgp network A.B.C.D/M",
      NO_STR
      BGP_HELP_STR
      BGP_NETWORK_STR
      IP_PREFIX_STR)
{
    char cmdstr[128];
    snprintf(cmdstr, 128, "sudo config bgp delete network %s", argv[0]);
    execute_linux_cmd_pipe(cmdstr);
    return CMD_SUCCESS;
}

DEFUN(bgp_network_config,
      bgp_network_config_cmd,
      "bgp network A.B.C.D/M",
      BGP_HELP_STR
      BGP_NETWORK_STR
      IP_PREFIX_STR)
{
    char cmdstr[128];
    snprintf(cmdstr, 128, "sudo config bgp add network %s", argv[0]);
    execute_linux_cmd_pipe(cmdstr);
    return CMD_SUCCESS;
}


void
vtysh_bgp_init (void)
{
    install_element (CONFIG_NODE, &no_bgp_advertise_low_priority_config_cmd);
    install_element (CONFIG_NODE, &bgp_advertise_low_priority_config_cmd);
    install_element (CONFIG_NODE, &no_bgp_network_config_cmd);
    install_element (CONFIG_NODE, &bgp_network_config_cmd);
}

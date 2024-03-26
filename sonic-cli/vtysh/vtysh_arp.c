#include <zebra.h>
#include "command.h"
#include "vtysh.h"
#include "if.h"

#define ARP_HELP_STR        "arp configuration\n"
#define ARP_AGINGTIME_HELP_STR      "Set arp aging time\n"
#define ARP_AGINGTIME_VAL_STR       "Aging time 0 to 3221225 seconds\n"
#define ARP2ROUTE_HELP_STR          "create 32 bit route for arp\n"

DEFUN(arp_aging_time_config,
      arp_aging_time_config_cmd,
      "arp agingtime <0-3221225>",
      ARP_HELP_STR
      ARP_AGINGTIME_HELP_STR
      ARP_AGINGTIME_VAL_STR)
{
    char cmdstr[128];
    snprintf(cmdstr, 128, "sudo sw config arp timeout %s",argv[0]);
    execute_linux_cmd_pipe(cmdstr);
    return CMD_SUCCESS;
}

DEFUN(arp2route_config,
      arp2route_config_cmd,
      "arp arp2route",
      ARP_HELP_STR
      ARP2ROUTE_HELP_STR)
{
    char cmdstr[128];
    snprintf(cmdstr, 128, "sudo sw config arp2route enable");
    execute_linux_cmd_pipe(cmdstr);
    return CMD_SUCCESS;
}

DEFUN(no_arp2route_config,
      no_arp2route_config_cmd,
      "no arp arp2route",
      NO_STR
      ARP_HELP_STR
      ARP2ROUTE_HELP_STR)
{
    char cmdstr[128];
    snprintf(cmdstr, 128, "sudo sw config arp2route disable");
    execute_linux_cmd_pipe(cmdstr);
    return CMD_SUCCESS;
}

void
vtysh_arp_init (void)
{
    install_element (CONFIG_NODE, &arp_aging_time_config_cmd);
    install_element (CONFIG_NODE, &arp2route_config_cmd);
    install_element (CONFIG_NODE, &no_arp2route_config_cmd);
}

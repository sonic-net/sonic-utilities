#include <zebra.h>
#include "command.h"
#include "vtysh.h"
#include "if.h"

#define CMDSZ          128
#define INTFNMSZ       32
#define DHCP_STR       "DHCP configuration\n"
#define DHCP_RELAY_STR "DHCP relay configuration\n"

/* dhcp relay server A.B.C.D */
DEFUN (dhcp_relay_server, dhcp_relay_server_cmd,
       "dhcp relay server A.B.C.D",
       DHCP_STR
       DHCP_RELAY_STR
       "DHCP relay server configuration\n"
       "DHCP relay server IP address\n")
{
  char cmdstr[CMDSZ];
  snprintf(cmdstr, CMDSZ, "dhcprelay -s %s", argv[0]);
  execute_linux_cmd_pipe(cmdstr);
  return CMD_SUCCESS;
}

/* no dhcp relay server A.B.C.D */
DEFUN (no_dhcp_relay_server, no_dhcp_relay_server_cmd,
       "no dhcp relay server A.B.C.D",
       NO_STR
       DHCP_STR
       DHCP_RELAY_STR
       "DHCP relay server configuration\n"
       "DHCP relay server IP address\n")
{
  char cmdstr[CMDSZ];
  snprintf(cmdstr, CMDSZ, "dhcprelay --no-s %s", argv[0]);
  execute_linux_cmd_pipe(cmdstr);
  return CMD_SUCCESS;
}

/* dhcp relay */
DEFUN (dhcp_relay, dhcp_relay_cmd,
       "dhcp relay",
       DHCP_STR
       "enable DHCP relay on this interface\n")
{
  char cmdstr[CMDSZ];
  const char* intf_name = ((struct interface*)(vty->index))->name;
  snprintf(cmdstr, CMDSZ, "dhcprelay -d %s", intf_name);
  execute_linux_cmd_pipe(cmdstr);
  return CMD_SUCCESS;
}

/* dhcp relay */
DEFUN (no_dhcp_relay, no_dhcp_relay_cmd,
       "no dhcp relay",
       NO_STR
       DHCP_STR
       "enable DHCP relay on this interface\n")
{
  char cmdstr[CMDSZ];
  const char* intf_name = ((struct interface*)(vty->index))->name;
  snprintf(cmdstr, CMDSZ, "dhcprelay --no-d %s --no-u %s", intf_name, intf_name);
  execute_linux_cmd_pipe(cmdstr);
  return CMD_SUCCESS;
}


void
vtysh_dhcp_init (void)
{
  install_element (CONFIG_NODE, &dhcp_relay_server_cmd);
  install_element (CONFIG_NODE, &no_dhcp_relay_server_cmd);
  install_element (INTERFACE_NODE, &dhcp_relay_cmd);
  install_element (INTERFACE_NODE, &no_dhcp_relay_cmd);
}


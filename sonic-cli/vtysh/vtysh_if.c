#include "command.h"
#include "vtysh.h"
#include "if.h"
#include "vty.h"
#include "memory.h"
#include <stdbool.h>

#define CMDSZ          128
#define INTFNMSZ       32

DEFUN (proxy_arp, proxy_arp_cmd,
       "proxy arp",
       "Enable Proxy\n"
       "ARP\n")
{
  char cmdstr[CMDSZ];
  const char* intf_name = ((struct interface*)(vty->index))->name;
  snprintf(cmdstr, CMDSZ, "sudo sw config proxy_arp -i %s", intf_name);
  execute_linux_cmd_pipe(cmdstr);

  return CMD_SUCCESS;
}

DEFUN (no_proxy_arp, no_proxy_arp_cmd,
       "no proxy arp",
       NO_STR
       "Enable Proxy\n"
       "ARP\n")
{
  char cmdstr[CMDSZ];
  const char* intf_name = ((struct interface*)(vty->index))->name;
  snprintf(cmdstr, CMDSZ, "sudo sw config proxy_arp -i %s --disable", intf_name);
  execute_linux_cmd_pipe(cmdstr);
  return CMD_SUCCESS;
}

DEFUN (interface,
       interface_cmd,
       "interface IFNAME",
       "Select an interface to configure\n"
       INTERFACE_NAME_RANGE_STR)
{
    struct interface *ifp;
    size_t sl;
    int index = 0;
    const char *if_name;

    //check if is a digit
    if (strmatch(argv[0],"^[0-9]+$"))
    {
        //printf("is digit\n");
        index = atoi(argv[0]);
        if ( (index > 0)
             && (index < 256)
             && (system_intfs[index] != NULL) )
        {
            if_name = system_intfs[index];
        }
        else
        {
            vty_out (vty, "%% Interface index %s is invalid.%s", argv[0], VTY_NEWLINE);
            return CMD_WARNING;
        }
    }
    else if(intf_range_match(argv[0]))
    {
        //printf("is range\n");
        vty->index = NULL;
        vty->node = INTERFACE_NODE;
        vty->intf_range = strndup(argv[0], strlen(argv[0]));
        vty->intf_type = INTFACE_TYPE_PORT;
        return CMD_SUCCESS;
    }
    else
    {
        if_name = argv[0];
    }

    if ((sl = strlen(if_name)) > INTERFACE_NAMSIZ)
    {
        vty_out (vty, "%% Interface name %s is invalid: length exceeds "
                         "%d characters%s",
                 if_name, INTERFACE_NAMSIZ, VTY_NEWLINE);
        return CMD_WARNING;
    }
    ifp = if_get_by_name_len(if_name, sl);

    vty->index = ifp;
    vty->node = INTERFACE_NODE;
    vty->intf_range = NULL;

    return CMD_SUCCESS;
}

bool is_vlan_exist(int vlan_id)
{
    FILE *fstream=NULL;
    bool exist = false;
    char cmdstr[CMDSZ];
    char output[512] = {0};

    snprintf(cmdstr, CMDSZ, "ip link show Vlan%d", vlan_id);
    if(!(fstream = popen(cmdstr, "r")))
    {
        return false;
    }

    snprintf(cmdstr, CMDSZ, "Vlan%d@Bridge", vlan_id);
    while(fgets(output, sizeof(output), fstream))
    {
        if(NULL != strstr(output, cmdstr))
        {
            exist = true;
        }
    }
    pclose(fstream);
    return exist;
}

DEFUN (port_vlan, port_vlan_cmd,
       "port vlan <1-4096> (tagged|untagged)",
       "Port vlan configuration\n"
       "VLAN ID configuration\n"
       "VLAN ID\n"
       "Tagged mode\n"
       "Untagged mode\n")
{
  char cmdstr[CMDSZ];
  const char* intf_name = ((struct interface*)(vty->index))->name;
  int index = 0;

  if (!strncmp(intf_name, "Vlan", strlen("Vlan")))
  {
      vty_out (vty, "%% port vlan configuration not supported on vlan  %s", VTY_NEWLINE);
      return CMD_WARNING;
  }

  //check if is a digit
  if (strmatch(argv[0],"^[0-9]+$"))
  {
      //printf("is digit\n");
      index = atoi(argv[0]);
      if ( (index < 0)
           && (index >= 4096))
      {
          vty_out (vty, "%% Vlan ID %s is invalid.%s", argv[0], VTY_NEWLINE);
          return CMD_WARNING;
      }
  }
  else
  {
      vty_out (vty, "%% Vlan ID %s is invalid.%s", argv[0], VTY_NEWLINE);
      return CMD_WARNING;
  }

  if (!is_vlan_exist(index))
  {
      vty_out (vty, "%% Vlan %s is not created.%s", argv[0], VTY_NEWLINE);
      return CMD_WARNING;
  }

  snprintf(cmdstr, CMDSZ, "cfgmgr vlan add vlan %d dev %s %s", index, intf_name, argv[1]);
  execute_linux_cmd_pipe(cmdstr);

  return CMD_SUCCESS;
}

DEFUN (no_port_vlan, no_port_vlan_cmd,
       "no port vlan <1-4096>",
       NO_STR
       "Port vlan configuration\n"
       "VLAN ID configuration\n"
       "VLAN ID\n")
{
  char cmdstr[CMDSZ];
  const char* intf_name = ((struct interface*)(vty->index))->name;
  int index = 0;

  if (!strncmp(intf_name, "Vlan", strlen("Vlan")))
  {
      vty_out (vty, "%% port vlan configuration not supported on vlan  %s", VTY_NEWLINE);
      return CMD_WARNING;
  }
  //check if is a digit
  if (strmatch(argv[0],"^[0-9]+$"))
  {
      //printf("is digit\n");
      index = atoi(argv[0]);
      if ( (index < 0)
           && (index >= 4096))
      {
          vty_out (vty, "%% Vlan ID %s is invalid.%s", argv[0], VTY_NEWLINE);
          return CMD_WARNING;
      }
  }
  else
  {
      vty_out (vty, "%% Vlan ID %s is invalid.%s", argv[0], VTY_NEWLINE);
      return CMD_WARNING;
  }

  if (!is_vlan_exist(index))
  {
      vty_out (vty, "%% Vlan %s is not created.%s", argv[0], VTY_NEWLINE);
      return CMD_WARNING;
  }

  snprintf(cmdstr, CMDSZ, "cfgmgr vlan del vlan %d dev %s", index, intf_name);
  execute_linux_cmd_pipe(cmdstr);

  return CMD_SUCCESS;
}


DEFUN (vlan_intf_description, vlan_intf_description_cmd,
       "description .LINE",
       "Interface specific description\n"
       "Characters describing this interface\n")
{
  char cmdstr[CMDSZ];
  char *desc;
  const char* intf_name = ((struct interface*)(vty->index))->name;
  int index = 0;

  if (strncmp(intf_name, "Vlan", strlen("Vlan")))
  {
      vty_out (vty, "%% description supported on vlan only %s", VTY_NEWLINE);
      return CMD_WARNING;
  }

  desc = argv_concat (argv, argc, 0);
  index = atoi(intf_name + strlen("Vlan"));

  if (!is_vlan_exist(index))
  {
      vty_out (vty, "%% Vlan %s is not created.%s", argv[0], VTY_NEWLINE);
      return CMD_WARNING;
  }

  snprintf(cmdstr, CMDSZ, "cfgmgr vlan add vlan %d desc %s", index, desc);
  execute_linux_cmd_pipe(cmdstr);
  XFREE (MTYPE_TMP, desc);
  return CMD_SUCCESS;
}

DEFUN (vlan_intf_address, vlan_intf_address_cmd,
       "ip address A.B.C.D/M",
       "IP address configuration\n"
       "Set the IP address of an interface\n"
       "IP address\n")
{
  char cmdstr[CMDSZ];
  const char* intf_name = ((struct interface*)(vty->index))->name;
  int index = atoi(intf_name + strlen("Vlan"));

  if (!is_vlan_exist(index))
  {
      vty_out (vty, "%% Vlan %s is not created.%s", argv[0], VTY_NEWLINE);
      return CMD_WARNING;
  }

  snprintf(cmdstr, CMDSZ, "cfgmgr intf add %s dev %s", argv[0], intf_name);
  execute_linux_cmd_pipe(cmdstr);
  return CMD_SUCCESS;
}

DEFUN (no_vlan_intf_address, no_vlan_intf_address_cmd,
       "no ip address A.B.C.D/M",
       NO_STR
       "IP address configuration\n"
       "Set the IP address of an interface\n"
       "IP address\n")
{
  char cmdstr[CMDSZ];
  const char* intf_name = ((struct interface*)(vty->index))->name;
  int index = atoi(intf_name + strlen("Vlan"));

  if (!is_vlan_exist(index))
  {
      vty_out (vty, "%% Vlan %s is not created.%s", argv[0], VTY_NEWLINE);
      return CMD_WARNING;
  }

  snprintf(cmdstr, CMDSZ, "cfgmgr intf del %s dev %s", argv[0], intf_name);
  execute_linux_cmd_pipe(cmdstr);
  return CMD_SUCCESS;
}

DEFUN (interface_vlan,
       interface_vlan_cmd,
       "interface vlan <1-4096>",
       "Select an interface to configure\n"
        INTERFACE_VLAN_STR
       "vlan ID\n")
{
    struct interface *ifp;
    size_t sl;
    int index = 0;
    char if_name[24];

    //check if is a digit
    if (strmatch(argv[0],"^[0-9]+$"))
    {
        //printf("is digit\n");
        index = atoi(argv[0]);
        if ( (index > 0)
             && (index < 4096))
        {
            sprintf(if_name,"Vlan%d", index);
        }
        else
        {
            vty_out (vty, "%% Vlan ID %s is invalid.%s", argv[0], VTY_NEWLINE);
            return CMD_WARNING;
        }
    }
    else
    {
        vty_out (vty, "%% Vlan ID %s is invalid.%s", argv[0], VTY_NEWLINE);
        return CMD_WARNING;
    }

    if ((sl = strlen(if_name)) > INTERFACE_NAMSIZ)
    {
        vty_out (vty, "%% Interface name %s is invalid: length exceeds "
                         "%d characters%s",
                 if_name, INTERFACE_NAMSIZ, VTY_NEWLINE);
        return CMD_WARNING;
    }
    ifp = if_get_by_name_len(if_name, sl);

    vty->index = ifp;
    vty->node = INTERFACE_NODE;
    vty->intf_range = NULL;

    return CMD_SUCCESS;
}

DEFUN (vtysh_vlan_add,
       vtysh_vlan_add_cmd,
       "vlan <1-4096>",
       "Creates a VLAN\n"
       "Vlan ID\n")
{
    char cmdstr[CMDSZ];
    snprintf(cmdstr, CMDSZ, "cfgmgr vlan add vlan %s up",
             argv[0]);
    execute_linux_cmd_pipe(cmdstr);
    return CMD_SUCCESS;
}

DEFUN (vtysh_vlan_del,
       vtysh_vlan_del_cmd,
       "no vlan <1-4096>",
       "NO_STR\n"
       "VLAN operation command\n"
       "Vlan ID\n")
{
    char cmdstr[CMDSZ];
    snprintf(cmdstr, CMDSZ, "cfgmgr vlan del vlan %s", argv[0]);
    execute_linux_cmd_pipe(cmdstr);
    return CMD_SUCCESS;
}

DEFUN (interface_portchannel,
       interface_portchannel_cmd,
       "interface port-channel RANGE",
       "Select an interface to configure\n"
       INTERFACE_PORT_CHANNEL_STR
       INTERFACE_RANGE_STR)
{
    struct interface *ifp;
    size_t sl;
    int index = 0;
    char if_name[24];

    //check if is a digit
    if (strmatch(argv[0],"^[0-9]+$"))
    {
        //printf("is digit\n");
        index = atoi(argv[0]);
        if ( (index > 0)
             && (index < 49) )
        {
            sprintf(if_name,"PortChannel%d", index);
        }
        else
        {
            vty_out (vty, "%% PortChannel index %s is invalid.%s", argv[0], VTY_NEWLINE);
            return CMD_WARNING;
        }
    }
    else if(intf_range_match(argv[0]))
    {
        //printf("is range\n");
        vty->index = NULL;
        vty->node = INTERFACE_NODE;
        vty->intf_range = strndup(argv[0], strlen(argv[0]));
        vty->intf_type = INTFACE_TYPE_LAG;
        return CMD_SUCCESS;
    }
    else
    {
        vty_out (vty, "%% Interface %s is invalid.%s", argv[0], VTY_NEWLINE);
        return CMD_WARNING;
    }

    if ((sl = strlen(if_name)) > INTERFACE_NAMSIZ)
    {
        vty_out (vty, "%% Interface name %s is invalid: length exceeds "
                         "%d characters%s",
                 if_name, INTERFACE_NAMSIZ, VTY_NEWLINE);
        return CMD_WARNING;
    }
    ifp = if_get_by_name_len(if_name, sl);

    vty->index = ifp;
    vty->node = INTERFACE_NODE;
    vty->intf_range = NULL;

    return CMD_SUCCESS;
}

DEFUN (shut_down, shut_down_cmd,
       "shutdown",
       "Shutdown the selected interface\n")
{
    char cmdstr[CMDSZ];
    const char* intf_name = ((struct interface*)(vty->index))->name;
    //snprintf(cmdstr, CMDSZ, "sudo sw config interfaces admin_status %s down", intf_name);
    snprintf(cmdstr, CMDSZ, "sudo ip link set %s down", intf_name);
    execute_linux_cmd_pipe(cmdstr);

    return CMD_SUCCESS;
}

DEFUN (no_shut_down, no_shut_down_cmd,
       "no shutdown",
       NO_STR
       "Shutdown the selected interface\n")
{
    char cmdstr[CMDSZ];
    const char* intf_name = ((struct interface*)(vty->index))->name;
    //snprintf(cmdstr, CMDSZ, "sudo sw config interfaces admin_status %s up", intf_name);
    snprintf(cmdstr, CMDSZ, "sudo ip link set %s up", intf_name);
    execute_linux_cmd_pipe(cmdstr);

    return CMD_SUCCESS;
}

DEFUN (bgp_isolate, bgp_isolate_cmd,
       "isolate",
       "isolate device\n")
{
    execute_linux_cmd_pipe("sudo sw config bgp isolate");
    return CMD_SUCCESS;
}

DEFUN (no_bgp_isolate, no_bgp_isolate_cmd,
       "no isolate",
        NO_STR
       "isolate device\n")
{
    execute_linux_cmd_pipe("sudo sw config bgp no isolate");
    return CMD_SUCCESS;
}
void
vtysh_if_init (void)
{
    install_element (INTERFACE_NODE, &proxy_arp_cmd);
    install_element (INTERFACE_NODE, &no_proxy_arp_cmd);
    install_element (INTERFACE_NODE, &shut_down_cmd);
    install_element (INTERFACE_NODE, &no_shut_down_cmd);
    install_element (INTERFACE_NODE, &port_vlan_cmd);
    install_element (INTERFACE_NODE, &no_port_vlan_cmd);
    install_element (INTERFACE_NODE, &vlan_intf_description_cmd);
    install_element (INTERFACE_NODE, &vlan_intf_address_cmd);
    install_element (INTERFACE_NODE, &no_vlan_intf_address_cmd);

    install_element (CONFIG_NODE, &vtysh_vlan_add_cmd);
    install_element (CONFIG_NODE, &vtysh_vlan_del_cmd);

    install_element (CONFIG_NODE, &interface_cmd);
    install_element (CONFIG_NODE, &interface_vlan_cmd);
    install_element (CONFIG_NODE, &interface_portchannel_cmd);
    install_element (CONFIG_NODE, &bgp_isolate_cmd);
    install_element (CONFIG_NODE, &no_bgp_isolate_cmd);
}


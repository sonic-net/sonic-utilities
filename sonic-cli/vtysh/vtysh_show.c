#include <zebra.h>
#include "command.h"
#include "vtysh.h"
#include "if.h"

#define CMDSZ          128

#define RUNNING_CFG_STR "Current operating configuration\n"
#define STARTUP_CFG_STR "Contentes of startup configuration\n"

/* show ip interfaces brief. */
DEFUN (show_ip_interfaces_brief, show_ip_interfaces_brief_cmd,
       "show ip interfaces brief",
       SHOW_STR
       IP_STR
       "IP interfaces status\n"
       "IP interfaces status brief\n")
{
  /* Specified interface print. */
  //execute_linux_cmd_pipe("sw show ip interfaces brief");
  execute_linux_cmd_pipe("sudo ip addr show | grep inet");
  return CMD_SUCCESS;
}
/* show ip interfaces brief. */
DEFUN (show_interface_counters, show_interface_counters_cmd,
       "show interface counters",
       SHOW_STR
       INTERFACE_STR
       "interfaces counters\n")
{
  /* Specified interface print. */
  execute_linux_cmd_pipe("show interface counters -a");
  return CMD_SUCCESS;
}
DEFUN (show_interface_counters_rate, show_interface_counters_rate_cmd,
       "show interface counters rate",
       SHOW_STR
       INTERFACE_STR
       "interfaces counters\n"
       "counters rate")
{
  /* Specified interface print. */
  execute_linux_cmd_pipe("show interface counters -a -p 1");
  return CMD_SUCCESS;
}
DEFUN (clear_interface_counters, clear_interface_counters_cmd,
       "clear interface counters",
       CLEAR_STR
       INTERFACE_STR
       "clear interfaces counters\n")
{
  /* Specified interface print. */
  execute_linux_cmd_pipe("show interface counters -c");
  return CMD_SUCCESS;
}
DEFUN (show_lldp_neighbors, show_lldp_neighbors_cmd,
       "show lldp neighbors",
       SHOW_STR
       "lldp neighbors information\n"
       "lldp neighbors information\n")
{
  /* Specified interface print. */
  execute_linux_cmd_pipe("lldpshow");
  return CMD_SUCCESS;
}

DEFUN (show_interfaces_status, show_interfaces_status_cmd,
       "show interface status",
       SHOW_STR
       INTERFACE_STR
       "IP interfaces status\n")
{
  /* Specified interface print. */
  execute_linux_cmd_pipe("show interfaces status");
  return CMD_SUCCESS;
}

DEFUN (show_vlan_state, show_vlan_state_cmd,
       "show vlan state {vlan <1-4095>}",
       SHOW_STR
       "vlan\n"
       "vlan status\n"
       "vlan name.eg Vlan10\n")
{
  char cmdstr[512];
  /* show vlan state. */
  if (argv[0] !=NULL)
  {
    snprintf(cmdstr, 512, "sudo docker exec -it swss cfgmgr vlan show state vlan %s" ,argv[0]);
    execute_linux_cmd_pipe(cmdstr);
  }
  else
  {
    execute_linux_cmd_pipe("sudo docker exec -it swss cfgmgr vlan show state");
  }
  return CMD_SUCCESS;
}

static int getsysloglinenumber(char *cmdline)
{
  FILE *fstream=NULL;
  char *cmdtmp;
  char output[1024];
  int linenumber=0;

  memset(output,0,sizeof(output));
  if(NULL==(fstream=popen(cmdline,"r")))
  {
    vty_out(vty,"execute command failed: %s", safe_strerror(errno));
    return 0;
  }

  if(NULL!=fgets(output, sizeof(output), fstream))
  {
    cmdtmp=output;
    while(*cmdtmp!='\0'){
      if(*cmdtmp==' '){
        *cmdtmp='\0';
        break;
      }
      cmdtmp++;
    }
    linenumber = atoi(output);
  }
  pclose(fstream);
  return linenumber;
}

static int showlog(int filenumber,int inputlinenumber)
{
  char filename[512];
  char gzfilename[512];
  char cmdstr[1024];
  int filelinenumber=0;
  int gzipflag=0;

  if(filenumber==0)
  {
    snprintf(filename, 512, "/var/log/syslog");
  }
  else
  {
    snprintf(filename, 512, "/var/log/syslog.%d",filenumber);
  }
  if(access(filename,F_OK)==-1)
  {
      snprintf(gzfilename, 512, "%s.gz",filename);
      if(access(gzfilename,F_OK)!=-1)
      {
          snprintf(cmdstr, 1024, "sudo sh -c 'gzip -dc %s > %s'",gzfilename,filename);
          execute_linux_cmd_pipe(cmdstr);
          gzipflag=1;
      }
      else
      {
        return -1;
      }
  }
  snprintf(cmdstr,1024,"sudo wc -l %s",filename);
  filelinenumber = getsysloglinenumber(cmdstr);
  if(inputlinenumber<=filelinenumber)
  {
    snprintf(cmdstr, 1024, "sudo cat %s | tail -%d",filename,inputlinenumber);
    execute_linux_cmd_pipe(cmdstr);
  }
  else
  {
    showlog(filenumber+1,inputlinenumber-filelinenumber);
    snprintf(cmdstr, 1024, "sudo cat %s | tail -%d",filename,filelinenumber);
    execute_linux_cmd_pipe(cmdstr);
  }
  if(gzipflag==1)
  {
    snprintf(cmdstr, 1024, "sudo rm -rf %s",filename);
    execute_linux_cmd_pipe(cmdstr);
  }
  return 0;
}

DEFUN (show_log, show_log_cmd,
       "show log",
       SHOW_STR
       "Show Syslog Information(last 500 lines)\n")
{
  showlog(0,500);
  return CMD_SUCCESS;
}

DEFUN (show_log_on, show_log_on_cmd,
       "show log on",
       SHOW_STR
       "Show Syslog Information(last 500 lines)\n"
       "Show ERROR syslog on\n")
{
    execute_linux_cmd_pipe("sudo tail -f /var/log/syslog | grep -E 'WARNING|ERR'");
    return CMD_SUCCESS;
}

DEFUN (show_log_tail, show_log_tail_cmd,
       "show log tail NUM",
       SHOW_STR
       "Show Syslog Information(last 500 lines)\n"
       "Last Syslog to Show\n"
       "Line Number \n")
{
  int inputlinenumber=atoi(argv[0]);
  showlog(0,inputlinenumber);
  return CMD_SUCCESS;
}

DEFUN (show_portchannel_summary, show_portchannel_summary_cmd,
       "show portchannel summary",
       SHOW_STR
       "portchannel info"
       "portchannel summary\n")
{
    execute_linux_cmd_pipe("teamshow");
    return CMD_SUCCESS;
}

DEFUN (show_portchannel_status, show_portchannel_status_cmd,
       "show portchannel RANGE status",
       SHOW_STR
       INTERFACE_PORT_CHANNEL_STR
       INTERFACE_RANGE_STR
       "portchannel status\n")
{
    int index = 0;
    char if_name[24];
    char cmdstr[CMDSZ];
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
        snprintf(cmdstr, CMDSZ, "teamdctl %s state dump", if_name);
        execute_linux_cmd_pipe(cmdstr);
    }
    else if(intf_range_match(argv[0]))
    {
        printf("is range\n");
#if 0
        vty->index = NULL;
        vty->node = INTERFACE_NODE;
        vty->intf_range = strndup(argv[0], strlen(argv[0]));
        vty->intf_type = INTFACE_TYPE_LAG;
#endif
        return CMD_SUCCESS;
    }
    else
    {
        vty_out (vty, "%% PortChannel %s is invalid.%s", argv[0], VTY_NEWLINE);
        return CMD_WARNING;
    }

    return CMD_SUCCESS;
}



DEFUN (show_platform, show_platform_cmd,
       "show platform",
       SHOW_STR
       "platform-specific hardware info\n")
{
    execute_linux_cmd_pipe("show platform summary");
    execute_linux_cmd_pipe("show platform syseeprom");
    return CMD_SUCCESS;
}

DEFUN (show_environment, show_environment_cmd,
       "show environment",
       SHOW_STR
       "Show environmentals (voltages, fans, temps)\n")
{
    execute_linux_cmd_pipe("show environment");
    execute_linux_cmd_pipe("sudo /usr/sbin/i2c_utils.sh i2c_psu_status");
    return CMD_SUCCESS;
}

DEFUN (show_ntp, show_ntp_cmd,
       "show ntp",
       SHOW_STR
       "Show ntpstatus\n")
{
    execute_linux_cmd_pipe("sudo ntpstat");
    return CMD_SUCCESS;
}


DEFUN (show_transceiver, show_transceiver_cmd,
       "show transceiver interface IFNAME",
       SHOW_STR
       "transceiver eeprom\n"
       "Select an interface to show\n"
       "Interface name or index \n")
{
    struct interface *ifp;
    size_t sl;
    char cmdstr[CMDSZ];
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

    snprintf(cmdstr, CMDSZ, "sudo sfputil show eeprom -d --port %s", ifp->name);

    execute_linux_cmd_pipe(cmdstr);

    return CMD_SUCCESS;
}


DEFUN (show_version, show_version_cmd,
       "show version",
       SHOW_STR
       "version information\n")
{
    execute_linux_cmd_pipe("show version");
    return CMD_SUCCESS;
}

DEFUN (show_arp, show_arp_cmd,
       "show arp",
       SHOW_STR
       "Address Resolution Protocol cache\n")
{
    //execute_linux_cmd_pipe("sw show arp");
    execute_linux_cmd_pipe("sudo ip neigh show");
    return CMD_SUCCESS;
}

DEFUN (show_arp_brief, show_arp_brief_cmd,
       "show arp brief",
       SHOW_STR
       "Address Resolution Protocol cache\n"
       "Brief Information\n")
{
    execute_linux_cmd_pipe("sw show arp brief");
    return CMD_SUCCESS;
}


DEFUN (show_mac, show_mac_cmd,
       "show mac",
       SHOW_STR
       "MAC Address Table information\n")
{
    execute_linux_cmd_pipe("show mac");
    return CMD_SUCCESS;
}

DEFUN (vtysh_show_running_config,
       vtysh_show_running_config_cmd,
       "show running-config",
       SHOW_STR
       RUNNING_CFG_STR)
{
    execute_linux_cmd_pipe("/usr/local/bin/sonic-cfggen -d --print-data");
    return CMD_SUCCESS;
}

DEFUN (vtysh_show_running_config_quagga,
       vtysh_show_running_config_quagga_cmd,
       "show running-config quagga",
       SHOW_STR
       RUNNING_CFG_STR)
{
    execute_linux_cmd_pipe("vtysh -c \"show running-config\"");
    return CMD_SUCCESS;
}
DEFUN (vtysh_show_startup_config,
       vtysh_show_startup_config_cmd,
       "show startup-config",
       SHOW_STR
       STARTUP_CFG_STR)
{
    execute_linux_cmd_pipe("/usr/local/bin/sonic-cfggen -j /etc/sonic/config_db.json --print-data");
    return CMD_SUCCESS;
}

DEFUN (vtysh_show_running_config_readable,
       vtysh_show_running_config_readable_cmd,
       "show running-config readable",
       SHOW_STR
       RUNNING_CFG_STR
       "Make it modularized and readable\n")
{
    execute_linux_cmd_pipe("/usr/local/bin/configshow --db --all");
    return CMD_SUCCESS;
}

DEFUN (vtysh_show_startup_config_readable,
       vtysh_show_startup_config_readable_cmd,
       "show startup-config readable",
       SHOW_STR
       STARTUP_CFG_STR
       "Make it modularized and readable\n")
{
    execute_linux_cmd_pipe("/usr/local/bin/configshow --all");
    return CMD_SUCCESS;
}


DEFUN (vtysh_show_system_cpu,
       vtysh_show_system_cpu_cmd,
       "show system cpu",
       SHOW_STR
       "System information\n"
       "Processes cpu detail information\n")
{
    execute_linux_cmd_pipe("top -bn 1 -o %CPU");
    return CMD_SUCCESS;
}

DEFUN (vtysh_show_system_mem,
       vtysh_show_system_mem_cmd,
       "show system memory",
       SHOW_STR
       "System information\n"
       "Memory detail usage\n")
{
    execute_linux_cmd_pipe("free -m");
    execute_linux_cmd_pipe("free -t | grep \"buffers/cache\" | awk '{ printf \"mem usage  : %.1f%%\\n\",$3/($3+$4) * 100}'");
    return CMD_SUCCESS;
}

DEFUN (vtysh_show_system_disk,
       vtysh_show_system_disk_cmd,
       "show system storage",
       SHOW_STR
       "System information\n"
       "File system storage information\n")
{
    execute_linux_cmd_pipe("df -h");
    return CMD_SUCCESS;
}

DEFUN (vtysh_snapaudit_sys_usage,
       vtysh_snapaudit_sys_usage_cmd,
       "snapaudit sys-usage",
       "Snapaudit information command\n"
       "Cpu, memory and disk usage\n")
{
    execute_linux_cmd_pipe("sys-usage");
    return CMD_SUCCESS;
}

DEFUN (vtysh_snapaudit_psu,
       vtysh_snapaudit_psu_cmd,
       "snapaudit psu",
       "Snapaudit information command\n"
       "Inspection information\n"
       "PSU status\n")
{
    execute_linux_cmd_pipe("/usr/bin/snapaudit --psu");
    return CMD_SUCCESS;
}

DEFUN (vtysh_snapaudit_temp,
       vtysh_snapaudit_temp_cmd,
       "snapaudit temperature",
       SHOW_STR
       "Inspection information\n"
       "Temperature sensor status\n")
{
    execute_linux_cmd_pipe("/usr/bin/snapaudit --temp");
    return CMD_SUCCESS;
}

DEFUN (vtysh_snapaudit_fan,
       vtysh_snapaudit_fan_cmd,
       "snapaudit fan",
       SHOW_STR
       "Inspection information\n"
       "FAN status\n")
{
    execute_linux_cmd_pipe("/usr/bin/snapaudit --fan");
    return CMD_SUCCESS;
}

DEFUN (vtysh_snapaudit_arp,
       vtysh_snapaudit_arp_cmd,
       "snapaudit arp",
       SHOW_STR
       "Inspection information\n"
       "ARP entry num\n")
{
    execute_linux_cmd_pipe("/usr/bin/snapaudit --arp");
    return CMD_SUCCESS;
}

DEFUN (vtysh_snapaudit_mac,
       vtysh_snapaudit_mac_cmd,
       "snapaudit mac",
       SHOW_STR
       "Inspection information\n"
       "MAC entry num\n")
{
    execute_linux_cmd_pipe("/usr/bin/snapaudit --mac");
    return CMD_SUCCESS;
}

DEFUN (vtysh_snapaudit_transceiver,
       vtysh_snapaudit_transceiver_cmd,
       "snapaudit transceiver",
       SHOW_STR
       "Inspection information\n"
       "Transceiver status\n")
{
    execute_linux_cmd_pipe("/usr/bin/snapaudit --sfp");
    return CMD_SUCCESS;
}

void
vtysh_show_ip_init (void)
{
  install_element (ENABLE_NODE, &show_ip_interfaces_brief_cmd);
  install_element (ENABLE_NODE, &show_interface_counters_cmd);
  install_element (ENABLE_NODE, &show_interface_counters_rate_cmd);
  install_element (ENABLE_NODE, &clear_interface_counters_cmd);
  install_element (ENABLE_NODE, &show_lldp_neighbors_cmd);
  install_element (ENABLE_NODE, &show_interfaces_status_cmd);
  install_element (ENABLE_NODE, &show_vlan_state_cmd);
  install_element (ENABLE_NODE, &show_log_cmd);
  install_element (ENABLE_NODE, &show_log_on_cmd);
  install_element (ENABLE_NODE, &show_log_tail_cmd);
  install_element (ENABLE_NODE, &show_portchannel_summary_cmd);
  install_element (ENABLE_NODE, &show_portchannel_status_cmd);
  install_element (ENABLE_NODE, &show_platform_cmd);
  install_element (ENABLE_NODE, &show_environment_cmd);
  install_element (ENABLE_NODE, &show_ntp_cmd);
  install_element (ENABLE_NODE, &show_transceiver_cmd);
  install_element (ENABLE_NODE, &show_version_cmd);
  install_element (ENABLE_NODE, &show_arp_cmd);
  install_element (ENABLE_NODE, &show_arp_brief_cmd);
  install_element (ENABLE_NODE, &show_mac_cmd);

  install_element (ENABLE_NODE, &vtysh_show_running_config_cmd);
  install_element (ENABLE_NODE, &vtysh_show_running_config_readable_cmd);
  install_element (ENABLE_NODE, &vtysh_show_running_config_quagga_cmd);
  install_element (ENABLE_NODE, &vtysh_show_startup_config_cmd);
  install_element (ENABLE_NODE, &vtysh_show_startup_config_readable_cmd);

  install_element (ENABLE_NODE, &vtysh_show_system_cpu_cmd);
  install_element (ENABLE_NODE, &vtysh_show_system_mem_cmd);
  install_element (ENABLE_NODE, &vtysh_show_system_disk_cmd);

  install_element (ENABLE_NODE, &vtysh_snapaudit_sys_usage_cmd);
  install_element (ENABLE_NODE, &vtysh_snapaudit_psu_cmd);
  install_element (ENABLE_NODE, &vtysh_snapaudit_fan_cmd);
  install_element (ENABLE_NODE, &vtysh_snapaudit_temp_cmd);
  install_element (ENABLE_NODE, &vtysh_snapaudit_arp_cmd);
  install_element (ENABLE_NODE, &vtysh_snapaudit_mac_cmd);
  install_element (ENABLE_NODE, &vtysh_snapaudit_transceiver_cmd);
}


#include <zebra.h>
#include "command.h"
#include "vtysh.h"
#include <string.h>

#define USERDIRECTORY "/usr/share/sonic/operator"
char curDirectory[1024]=USERDIRECTORY;

extern int pipeflag;
extern char ppipecmd[512];

DEFUN (scp, scp_cmd,
       "scp .LINE",
       "scp command\n"
       "scp parameters\n")
{
  execute_command ("scp", argc, argv);
  return CMD_SUCCESS;
}

DEFUN (ls_file, ls_file_cmd,
       "ls",
       "ls command\n")
{
  char cmdstr[1024];
  snprintf(cmdstr, 1024, "ls %s -l --color=auto",curDirectory);

  FILE *fstream=NULL;
  char output[1024];
  char cmdline[1024];
  char *cmdtmp;

  if(pipeflag==1){
    sprintf(cmdline,"%s |%s",cmdstr,ppipecmd);
  }
  else{
    sprintf(cmdline,"%s",cmdstr);
  }

  memset(output,0,sizeof(output));
  if(NULL==(fstream=popen(cmdline,"r")))
  {
    vty_out(vty,"execute command failed: %s", safe_strerror(errno));
    return CMD_WARNING;
  }

  fgets(output, sizeof(output), fstream);
  memset(output,0,sizeof(output));

  while(NULL!=fgets(output, sizeof(output), fstream))
  {
    int count=0;
    cmdtmp=output;
    while(*cmdtmp!='\0'){
      if(*cmdtmp==' '){
        count++;
      }
      if(count==4){
        break;
      }
      cmdtmp++;
    }
    vty_out (vty, "%s", cmdtmp);
    memset(output,0,sizeof(output));
    if (feof(fstream))
      break;
  }
  pclose(fstream);
  return CMD_SUCCESS;
}

DEFUN (pwd_show, pwd_show_cmd,
       "pwd",
       "pwd command\n")
{
  char* pos = strstr(curDirectory, USERDIRECTORY);
  if (NULL != pos)
  {
      char* pos2 = pos + strlen(USERDIRECTORY);
      vty_out (vty, "%s/%s",pos2,VTY_NEWLINE);
  }
  else
  {
     vty_out (vty, "%%invalid directory.%s",VTY_NEWLINE);
  }
  return CMD_SUCCESS;
}

DEFUN (mkdir_dir, mkdir_dir_cmd,
       "mkdir DIRECTORY",
       "mkdir command\n"
       "directory name\n")
{
  char* pos1 = strstr(argv[0], "/");
  char* pos2 = strstr(argv[0], "..");
  if((pos1!=NULL)||(pos2!=NULL))
  {
    vty_out (vty, "%%invalid input.%s",VTY_NEWLINE);
  }
  else
  {
    char cmdstr[1024];
    snprintf(cmdstr, 1024, "sudo mkdir %s/%s",curDirectory,argv[0]);
    execute_linux_cmd_pipe (cmdstr);
  }
  return CMD_SUCCESS;
}

DEFUN (rm_dir, rm_dir_cmd,
       "rm NAME",
       "rm command\n"
       "directory name or file name(only in current directory)\n")
{
  char* pos1 = strstr(argv[0], "/");
  char* pos2 = strstr(argv[0], "..");
  if((pos1!=NULL)||(pos2!=NULL))
  {
    vty_out (vty, "%%invalid input.%s",VTY_NEWLINE);
  }
  else{
    char cmdstr[1024];
    snprintf(cmdstr, 1024, "sudo rm -rf %s/%s",curDirectory,argv[0]);
    execute_linux_cmd_pipe (cmdstr);
  }
  return CMD_SUCCESS;
}

DEFUN (cd_dir, cd_dir_cmd,
       "cd NAME",
       "cd command\n"
       "directory name\n")
{

  char* pos1 = strstr(argv[0], "/");
  if(pos1!=NULL)
  {
    vty_out (vty, "%%invalid input.%s",VTY_NEWLINE);
  }
  else
  {
    char curdirectorytmp[1024];
    strcpy(curdirectorytmp,curDirectory);

    if(0==strcmp(argv[0],"..")){
      if(0!=strcmp(curdirectorytmp,USERDIRECTORY)){
        char *ptr =strrchr(curdirectorytmp, '/');
        *ptr='\0';
      }
    }
    else
    {
      strcat (curdirectorytmp,"/");
      strcat (curdirectorytmp,argv[0]);
    }

    char cmdstr[128];
    int status;
    snprintf(cmdstr, 128, "sudo ls %s",curdirectorytmp);
    status = system(cmdstr);
    if(0!=status)
    {
        return CMD_WARNING;
    }
    strcpy(curDirectory,curdirectorytmp);
  }
  return CMD_SUCCESS;
}
DEFUN (mv_file, mv_file_cmd,
       "mv FILE DIRECTORY",
       "mv command\n"
       "file name\n"
       "directory name\n")
{
  char* pos1 = strstr(argv[0], "/");
  char* pos2 = strstr(argv[0], "..");
  char* pos3 = strstr(argv[1], "..");
  if((pos1!=NULL)||(pos2!=NULL)||(pos3!=NULL))
  {
    vty_out (vty, "%%invalid input.%s",VTY_NEWLINE);
  }
  else
  {
    char cmdstr[1024];
    snprintf(cmdstr, 1024, "sudo mv %s/%s %s/%s",curDirectory,argv[0],USERDIRECTORY,argv[1]);
    execute_linux_cmd_pipe (cmdstr);
  }
  return CMD_SUCCESS;
}
DEFUN (vi_file, vi_file_cmd,
       "vi FILE",
       "vi command\n"
       "file name\n")
{
  char* pos1 = strstr(argv[0], "/");
  char* pos2 = strstr(argv[0], "..");
  if((pos1!=NULL)||(pos2!=NULL))
  {
    vty_out (vty, "%%invalid input.%s",VTY_NEWLINE);
  }
  else
  {
    char cmdstr[1024];
    snprintf(cmdstr, 1024, "sudo vi %s/%s",curDirectory,argv[0]);
    execute_linux_cmd_pipe (cmdstr);
  }
  return CMD_SUCCESS;
}

DEFUN (cat_file, cat_file_cmd,
       "cat FILE",
       "cat command\n"
       "file name\n")
{
  char* pos1 = strstr(argv[0], "/");
  char* pos2 = strstr(argv[0], "..");
  if((pos1!=NULL)||(pos2!=NULL))
  {
    vty_out (vty, "%%invalid input.%s",VTY_NEWLINE);
  }
  else
  {
    char cmdstr[1024];
    snprintf(cmdstr, 1024, "sudo cat %s/%s",curDirectory,argv[0]);
    execute_linux_cmd_pipe (cmdstr);
  }
  return CMD_SUCCESS;
}

DEFUN (drop_service_sip, drop_service_sip_cmd,
       "(add|delete) drop (ssh|snmp) sip IP ",
       "add\n"
       "delete\n"
       "drop packet\n"
       "ssh protocol\n"
       "snmp protocol\n"
       "source ip\n"
       "ip address(ip/mask)\n")
{
  char cmdstr[128];
  snprintf(cmdstr, 128, "sw config service_acl %s --service %s --sip %s --action DROP",argv[0],argv[1],argv[2]);
  execute_linux_cmd_pipe (cmdstr);
  return CMD_SUCCESS;
}
DEFUN (accpet_service_sip, accept_service_sip_cmd,
       "(add|delete) accept (ssh|snmp) sip IP ",
       "add\n"
       "delete\n"
       "accept packet\n"
       "ssh protocol\n"
       "snmp protocol\n"
       "source ip\n"
       "ip address(ip/mask)\n")
{
  char cmdstr[128];
  snprintf(cmdstr, 128, "sw config service_acl %s --service %s --sip %s --action ACCEPT",argv[0],argv[1],argv[2]);
  execute_linux_cmd_pipe (cmdstr);
  return CMD_SUCCESS;
}

DEFUN (show_input_iptables, show_input_iptables_cmd,
       "show input iptables",
       SHOW_STR
       "input\n"
       "iptables\n")
{
  char cmdstr[128];
  snprintf(cmdstr, 128, "sudo iptables -L INPUT -n --line-number -v");
  execute_linux_cmd_pipe (cmdstr);
  return CMD_SUCCESS;
}

DEFUN (show_service_acl_iptables, show_service_acl_iptables_cmd,
       "show service_acl iptables",
       SHOW_STR
       "service_acl\n"
       "iptables\n")
{
  char cmdstr[128];
  snprintf(cmdstr, 128, "sw show service_acl_state");
  execute_linux_cmd_pipe (cmdstr);
  return CMD_SUCCESS;
}

DEFUN (del_input_iptables, del_input_iptables_cmd,
       "del input iptables NUM",
       "delete"
       "input\n"
       "iptables\n"
       "iptables number\n")
{
  char cmdstr[128];
  snprintf(cmdstr, 128, "sudo iptables -D INPUT %s",argv[0]);
  execute_linux_cmd_pipe (cmdstr);
  return CMD_SUCCESS;
}

DEFUN (show_netstat_udp,
       show_netstat_udp_cmd,
       "show netstat udp",
       SHOW_STR
       "Show netstat information\n"
       "UDP service\n")
{
  execute_linux_cmd_pipe("netstat -upln");
  return CMD_SUCCESS;
}

DEFUN (show_netstat_tcp,
       show_netstat_tcp_cmd,
       "show netstat tcp",
       SHOW_STR
       "Show netstat information\n"
       "TCP service\n")
{
  execute_linux_cmd_pipe("netstat -tpln");
  return CMD_SUCCESS;
}

DEFUN (config_timezone,
       config_timezone_cmd,
       "timezone ZONENAME",
       "timezone\n"
       "ZONENAME eg.Asia/Shanghai\n")
{
  char cmdstr[128];
  snprintf(cmdstr, 128, "sw config timezone %s",argv[0]);
  execute_linux_cmd_pipe(cmdstr);
  return CMD_SUCCESS;
}

DEFUN (show_timezone,
       show_timezone_cmd,
       "show timezone",
       SHOW_STR
       "timezone\n")
{
  execute_linux_cmd_pipe("timedatectl status");
  return CMD_SUCCESS;
}
extern int IDLE_TIME_OUT;
DEFUN (idle_timeout,
       idle_timeout_cmd,
       "idle-timeout <0-36000>",
       "Set connection IDLE timeout\n"
       "seconds between 0-36000")
{
    IDLE_TIME_OUT = atoi(argv[0]);
    char cmdstr[128];
    snprintf(cmdstr, 128, "sudo sed -i 's/^TMOUT=[0-9]\\{1,\\}/TMOUT=%d/g' /etc/bash.bashrc\n",
             IDLE_TIME_OUT);
    execute_linux_cmd_pipe (cmdstr);
    snprintf(cmdstr,128, "TMOUT=%d", IDLE_TIME_OUT);
    putenv(cmdstr);

    return CMD_SUCCESS;
}

void
vtysh_linux_cmd_init (void)
{
  install_element (ENABLE_NODE, &scp_cmd);
  install_element (VTY_NODE, &idle_timeout_cmd);
  install_element (CONFIG_NODE, &ls_file_cmd);
  install_element (CONFIG_NODE, &pwd_show_cmd);
  install_element (CONFIG_NODE, &mkdir_dir_cmd);
  install_element (CONFIG_NODE, &rm_dir_cmd);
  install_element (CONFIG_NODE, &cd_dir_cmd);
  install_element (CONFIG_NODE, &mv_file_cmd);
  install_element (CONFIG_NODE, &vi_file_cmd);
  install_element (CONFIG_NODE, &cat_file_cmd);
  install_element (CONFIG_NODE, &drop_service_sip_cmd);
  install_element (CONFIG_NODE, &accept_service_sip_cmd);
  install_element (CONFIG_NODE, &show_input_iptables_cmd);
  install_element (CONFIG_NODE, &del_input_iptables_cmd);
  install_element (CONFIG_NODE, &config_timezone_cmd);
  install_element (ENABLE_NODE, &show_service_acl_iptables_cmd);

  install_element (ENABLE_NODE, &show_timezone_cmd);
  install_element (ENABLE_NODE, &show_netstat_udp_cmd);
  install_element (ENABLE_NODE, &show_netstat_tcp_cmd);
}



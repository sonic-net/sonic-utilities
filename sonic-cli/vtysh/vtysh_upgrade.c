#include "command.h"
#include "vtysh.h"
#include <unistd.h>

#define IMAGE_CFG "Image configuration\n"
const char image_dir[] = "/usr/share/sonic/operator";

DEFUN (vtysh_image_install,
       vtysh_image_install_cmd,
       "image install WORD",
       IMAGE_CFG
       "Install image from local binary\n"
       "Image from local binary")
{
    char cmdstr[256];
    char image[128];

    snprintf(image, 128, "%s/%s", image_dir, argv[0]);
    if (access(image, F_OK))
    {
        vty_out(vty, "%s is not exist, please check it by command \"show image list\"\n", argv[0]);
        return CMD_SUCCESS;
    }
    snprintf(cmdstr, 256, "sudo sonic_installer install %s -y", image);
    execute_linux_cmd_pipe(cmdstr);
    return CMD_SUCCESS;
}

DEFUN (vtysh_image_boot_next,
       vtysh_image_boot_next_cmd,
       "image boot-next <0-1>",
       IMAGE_CFG
       "Set the next image to boot\n"
       "Installed image number\n")
{
    char cmdstr[128];
    snprintf(cmdstr, 128, "sudo grub-set-default --boot-directory=/host %s", argv[0]);
    execute_linux_cmd_pipe(cmdstr);
    return CMD_SUCCESS;
}

DEFUN (vtysh_image_cleanup,
       vtysh_image_cleanup_cmd,
       "image cleanup",
       IMAGE_CFG
       "Remove installed image which is not current\n")
{
    execute_linux_cmd_pipe("sudo sonic_installer cleanup -y");
    return CMD_SUCCESS;
}

DEFUN (vtysh_show_image_installed,
       vtysh_show_image_installed_cmd,
       "show image installed",
       SHOW_STR
       "Show image information\n"
       "Installed image information\n")
{
    execute_linux_cmd_pipe("sudo sonic_installer list | sed -e 's/SONiC-OS-//g'");
    return CMD_SUCCESS;
}

DEFUN (vtysh_show_image_list,
       vtysh_show_image_list_cmd,
       "show image list",
       SHOW_STR
       "Show image information\n"
       "Local image binary list\n")
{
    char cmdstr[256];

    snprintf(cmdstr, 256, "ls -gGh %s", image_dir);
    execute_linux_cmd_pipe(cmdstr);
    vty_out(vty, "\n");
    snprintf(cmdstr, 256, "if [ `ls -1 %s/*.bin 2>/dev/null | wc -l ` -gt 0 ];then cd %s && ls *.bin | xargs -n 1 sudo sonic_installer binary_version | sed -e 's/SONiC-OS-//g'; fi", image_dir, image_dir);
    execute_linux_cmd_pipe(cmdstr);
    return CMD_SUCCESS;
}

DEFUN (vtysh_copy_runningcfg_startupcfg,
       vtysh_copy_runningcfg_startupcfg_cmd,
       "copy running-config startup-config",
       "Copy from one file to another\n"
       "Copy from current system configuration\n"
       "Copy to startup configuration\n")
{
    execute_linux_cmd_pipe("/usr/local/bin/sonic-cfggen -d --print-data > /etc/sonic/config_db.json");
    return CMD_SUCCESS;
}

DEFUN (vtysh_copy_file_startupcfg,
       vtysh_copy_file_startupcfg_cmd,
       "copy WORD startup-config",
       "Copy from one file to another\n"
       "Copy from specific file\n"
       "Copy to startup configuration\n")
{
    char new_cfg[128];
    char cmdstr[256];

    snprintf(new_cfg, 128, "%s/%s", image_dir, argv[0]);
    if (access(new_cfg, F_OK))
    {
        vty_out(vty, "%s is not exist, please check it\n", argv[0]);
        return CMD_SUCCESS;
    }
    snprintf(cmdstr, 256, "cp %s /etc/sonic/config_db.json", new_cfg);
    execute_linux_cmd_pipe(cmdstr);
    return CMD_SUCCESS;
}

DEFUN (vtysh_copy_runningcfg_file,
       vtysh_copy_runningcfg_file_cmd,
       "copy running-config WORD",
       "Copy from one file to another\n"
       "Copy from current system configuration\n"
       "Copy to specific file\n")
{
    char cmdstr[256];

    snprintf(cmdstr, 256, "/usr/local/bin/sonic-cfggen -d --print-data > %s/%s", image_dir, argv[0]);
    execute_linux_cmd_pipe(cmdstr);
    return CMD_SUCCESS;
}

DEFUN (vtysh_copy_startupcfg_file,
       vtysh_copy_startupcfg_file_cmd,
       "copy startup-config WORD",
       "Copy from one file to another\n"
       "Copy from startup configuration\n"
       "Copy to specific file\n")
{
    char cmdstr[256];

    snprintf(cmdstr, 256, "cp /etc/sonic/config_db.json %s/%s", image_dir, argv[0]);
    execute_linux_cmd_pipe(cmdstr);
    return CMD_SUCCESS;
}


void
vtysh_upgrade_init (void)
{
  install_element (CONFIG_NODE, &vtysh_image_install_cmd);
  install_element (CONFIG_NODE, &vtysh_image_boot_next_cmd);
  install_element (CONFIG_NODE, &vtysh_image_cleanup_cmd);
  install_element (CONFIG_NODE, &vtysh_show_image_installed_cmd);
  install_element (CONFIG_NODE, &vtysh_show_image_list_cmd);
  install_element (CONFIG_NODE, &vtysh_copy_runningcfg_startupcfg_cmd);
  install_element (CONFIG_NODE, &vtysh_copy_startupcfg_file_cmd);
  install_element (CONFIG_NODE, &vtysh_copy_runningcfg_file_cmd);
  install_element (CONFIG_NODE, &vtysh_copy_file_startupcfg_cmd);

  install_element (ENABLE_NODE, &vtysh_show_image_installed_cmd);
  install_element (ENABLE_NODE, &vtysh_show_image_list_cmd);
}


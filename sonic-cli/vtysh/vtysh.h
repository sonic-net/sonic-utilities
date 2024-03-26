/* Virtual terminal interface shell.
 * Copyright (C) 2000 Kunihiro Ishiguro
 *
 * This file is part of GNU Zebra.
 *
 * GNU Zebra is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by the
 * Free Software Foundation; either version 2, or (at your option) any
 * later version.
 *
 * GNU Zebra is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with GNU Zebra; see the file COPYING.  If not, write to the Free
 * Software Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
 * 02111-1307, USA.
 */

#ifndef VTYSH_H
#define VTYSH_H

#define VTYSH_ZEBRA  0x01
#define VTYSH_RIPD   0x02
#define VTYSH_RIPNGD 0x04
#define VTYSH_OSPFD  0x08
#define VTYSH_OSPF6D 0x10
#define VTYSH_BGPD   0x20
#define VTYSH_ISISD  0x40
#define VTYSH_BABELD  0x80
#define VTYSH_PIMD   0x100
#define VTYSH_ALL	  VTYSH_ZEBRA|VTYSH_RIPD|VTYSH_RIPNGD|VTYSH_OSPFD|VTYSH_OSPF6D|VTYSH_BGPD|VTYSH_ISISD|VTYSH_BABELD|VTYSH_PIMD
#define VTYSH_RMAP	  VTYSH_ZEBRA|VTYSH_RIPD|VTYSH_RIPNGD|VTYSH_OSPFD|VTYSH_OSPF6D|VTYSH_BGPD|VTYSH_BABELD
#define VTYSH_INTERFACE	  VTYSH_ZEBRA|VTYSH_RIPD|VTYSH_RIPNGD|VTYSH_OSPFD|VTYSH_OSPF6D|VTYSH_ISISD|VTYSH_BABELD|VTYSH_PIMD

/* vtysh local configuration file. */
#define VTYSH_DEFAULT_CONFIG "vtysh.conf"
#define CMD_AS_RANGE "<1-4294967295>"

void vtysh_init_vty (void);
void vtysh_init_cmd (void);
extern int vtysh_connect_all (const char *optional_daemon_name);
void vtysh_readline_init (void);
void vtysh_user_init (void);

int vtysh_execute (const char *);
int vtysh_execute_no_pager (const char *);

char *vtysh_prompt (void);

void vtysh_config_write (void);

int vtysh_config_from_file (struct vty *, FILE *);

int vtysh_read_config (char *);

void vtysh_config_parse (char *);

void vtysh_config_dump (FILE *);

void vtysh_config_init (void);

void vtysh_pager_init (void);

extern void vtysh_show_ip_init (void);

extern void vtysh_linux_cmd_init (void);

extern void vtysh_dhcp_init (void);

extern void vtysh_if_init (void);

extern void vtysh_link_monitor_init (void);

extern void vtysh_rdma_init(void);

extern void vtysh_upgrade_init (void);

extern void vtysh_acl_init (void);

extern int execute_linux_cmd_pipe(char* cmd);

extern void vtysh_poap_init(void);

extern void vtysh_arp_init(void);
extern void vtysh_bgp_init(void);


int execute_command (const char *command, int argc, const char *arg[]);

/* Child process execution flag. */
extern int execute_flag;

extern struct vty *vty;

extern char *system_intfs[];

#define EXEC_CMD_WITH_PARAM(format, ...) \
    do { \
        char cmdstr[128]; \
        snprintf(cmdstr, 128, format, __VA_ARGS__); \
        execute_linux_cmd_pipe(cmdstr); \
    } while(0)


#endif /* VTYSH_H */

/* User authentication for vtysh.
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

#include <zebra.h>
#include <lib/version.h>

#include <pwd.h>
#include <string.h>

#ifdef USE_PAM
#include <security/pam_appl.h>
#ifdef HAVE_PAM_MISC_H
#include <security/pam_misc.h>
#endif
#ifdef HAVE_OPENPAM_H
#include <security/openpam.h>
#endif
#endif /* USE_PAM */

#include "memory.h"
#include "linklist.h"
#include "command.h"
#include "vtysh.h"
#include "authorization.h"
#include "rbac.h"

#define AAA_HELP_STR                     "Authentication, Authorization and Accounting\n"
#define TACACS_HELP_STR                  "TACACS+ server\n"
#define AAA_AUTHENTICATION_HELP_STR      "User authentication\n"
#define AAA_AUTHORIZATION_HELP_STR       "User authorization\n"

#define AAA_LOGIN_HELP_STR               "Switch login\n"
#define AAA_ALLOW_FAIL_THROUGH_HELP_STR  "Allow AAA fail-through\n"
#define AAA_COMMAND_AUZ_STR              "Command authorization\n"
#define TACACS_ENABLE_AUZ_STR            "Enable TACACS+ authorization\n"
#define AAA_NONE_AUTHOR_HELP_STR         "No authorization\n"


#define AUTH_PORT_HELP_STR            "Set authentication port\n"
#define AUTH_PORT_RANGE_HELP_STR      "TCP port range is 1 to 65535. (Default: 49)\n"
#define TIMEOUT_HELP_STR              "Set the transmission timeout interval\n"
#define TIMEOUT_RANGE_HELP_STR        "Timeout interval 1 to 60 seconds. (Override default)\n"
#define SHARED_KEY_HELP_STR           "Set shared secret\n"
#define SHARED_KEY_VAL_HELP_STR       "TACACS+ shared secret. (Override default)\n"
#define AAA_AUTH_TYPE_HELP_STR        "Set authentication type. (Override default)\n"
#define AUTH_TYPE_PAP_HELP_STR        "Set PAP authentication\n"
#define AUTH_TYPE_CHAP_HELP_STR       "Set CHAP authentication\n"
#define TACACS_SERVER_HELP_STR        "TACACS+ server configuration\n"
#define TACACS_SERVER_HOST_HELP_STR   "Specify a TACACS+ server\n"
#define TACACS_SERVER_NAME_HELP_STR   "TACACS+ server IP address or hostname\n"

#define TACACS_EXEC_CMD_WITH_PARAM(format, ...) \
    do { \
        char cmdstr[128]; \
        snprintf(cmdstr, 128, format, __VA_ARGS__); \
        execute_linux_cmd_pipe(cmdstr); \
    } while(0)


#define TACACS_STR_EQ(s1, s2) \
    ((strlen((s1)) == strlen((s2))) && (!strncmp((s1), (s2), strlen((s2)))))

#ifdef USE_PAM
static struct pam_conv conv =
{
  PAM_CONV_FUNC,
  NULL
};

int
vtysh_pam (const char *user)
{
  int ret;
  pam_handle_t *pamh = NULL;

  /* Start PAM. */
  ret = pam_start(QUAGGA_PROGNAME, user, &conv, &pamh);
  /* printf ("ret %d\n", ret); */

  /* Is user really user? */
  if (ret == PAM_SUCCESS)
    ret = pam_authenticate (pamh, 0);
    if (ret != PAM_SUCCESS)
      printf("Not authenticated. Check /etc/pam.d/quagga.\n");
  /* printf ("ret %d\n", ret); */

#if 0
  /* Permitted access? */
  if (ret == PAM_SUCCESS)
    ret = pam_acct_mgmt (pamh, 0);
  printf ("ret %d\n", ret);

  if (ret == PAM_AUTHINFO_UNAVAIL)
    ret = PAM_SUCCESS;
#endif /* 0 */

  /* This is where we have been authorized or not. */
#ifdef DEBUG
  if (ret == PAM_SUCCESS)
    printf("Authenticated\n");
  else
    printf("Not Authenticated\n");
#endif /* DEBUG */

  /* close Linux-PAM */
  if (pam_end (pamh, ret) != PAM_SUCCESS)
    {
      pamh = NULL;
      fprintf(stderr, "vtysh_pam: failed to release authenticator\n");
      exit(1);
    }

  return ret == PAM_SUCCESS ? 0 : 1;
}
#endif /* USE_PAM */

struct vtysh_user
{
  char *name;
  u_char nopassword;
};

struct list *userlist;

struct vtysh_user *
user_new ()
{
  return XCALLOC (0, sizeof (struct vtysh_user));
}

void
user_free (struct vtysh_user *user)
{
  XFREE (0, user);
}

struct vtysh_user *
user_lookup (const char *name)
{
  struct listnode *node, *nnode;
  struct vtysh_user *user;

  for (ALL_LIST_ELEMENTS (userlist, node, nnode, user))
    {
      if (strcmp (user->name, name) == 0)
	return user;
    }
  return NULL;
}

void
user_config_write ()
{
  struct listnode *node, *nnode;
  struct vtysh_user *user;

  for (ALL_LIST_ELEMENTS (userlist, node, nnode, user))
    {
      if (user->nopassword)
	printf (" username %s nopassword\n", user->name);
    }
}

struct vtysh_user *
user_get (const char *name)
{
  struct vtysh_user *user;
  user = user_lookup (name);
  if (user)
    return user;

  user = user_new ();
  user->name = strdup (name);
  listnode_add (userlist, user);

  return user;
}

DEFUN (username_nopassword,
       username_nopassword_cmd,
       "username WORD nopassword",
       "\n"
       "\n"
       "\n")
{
  struct vtysh_user *user;
  user = user_get (argv[0]);
  user->nopassword = 1;
  return CMD_SUCCESS;
}

int
vtysh_auth ()
{
#if 0
  struct vtysh_user *user;
  struct passwd *passwd;

  passwd = getpwuid (geteuid ());

  user = user_lookup (passwd->pw_name);
  if (user && user->nopassword)
    /* Pass through */;
  else
    {
#ifdef USE_PAM
      if (vtysh_pam (passwd->pw_name))
	exit (0);
#endif /* USE_PAM */
    }
#endif

    /* Not need PAM authentication. Update TACACS+ configuration and
     * obtain RBAC and TACACS+ privilege level */
    if(author_update_config())
        fprintf(stderr, "**WARNING**: failed to read tacacs configuration.\n");

    rbac_set_access(author_get_privilege());

    /* To mask the syslog debug message in libtac, close syslog debug
     * when initial */
    author_set_debug(false);

    return 0;
}

static char *strupper(char *str)
{
    char *orign = str;
    while(*str != '\0')
    {
        *str = toupper(*str);
        ++str;
    }
    return orign;
}

static int cli_create_user_password(struct vty* vty, const char *name,
    const char *encrypt, const char *secret, const char *role)
{
    char role_type[16] = {0};

    strncpy(role_type, role, 16);
    strupper(role_type);

    TACACS_EXEC_CMD_WITH_PARAM(
        "sudo sw config useradd %s %s -e %s -r %s -g sudo,docker -s /usr/bin/cli",
        name, secret, encrypt, role_type);

    return CMD_SUCCESS;
}

DEFUN (username_role_password,
       username_role_password_cmd,
       "username WORD secret (md5|sha256|sha512) LINE role (read|write|admin)",
       "Set up a user account\n"
       "User name\n"
       "Configure login secret for the account\n"
       "Specifies an ENCRYPTED MD5 password will follow\n"
       "Specifies an ENCRYPTED SHA256 password will follow\n"
       "Specifies an ENCRYPTED SHA512 password will follow\n"
       "The ENCRYPTED user account password\n"
       "Configure a role for the user\n"
       "Specifies a READ-ACCESS role\n"
       "Specifies a WRITE-ACCESS role\n"
       "Specifies a ADMIN-ACCESS role\n")
{
    return cli_create_user_password(vty, argv[0], argv[1], argv[2], argv[3]);
}

DEFUN (username_password,
       username_password_cmd,
       "username WORD secret (md5|sha256|sha512) LINE",
       "Set up a user account\n"
       "User name\n"
       "Configure login secret for the account\n"
       "Specifies an ENCRYPTED MD5 password will follow\n"
       "Specifies an ENCRYPTED SHA256 password will follow\n"
       "Specifies an ENCRYPTED SHA512 password will follow\n"
       "The ENCRYPTED user account password\n")
{
    return cli_create_user_password(vty, argv[0], argv[1], argv[2], "READ");
}

DEFUN (no_username_password,
       no_username_password_cmd,
       "no username WORD",
       NO_STR
       "Set up a user account\n"
       "User name\n")
{
    TACACS_EXEC_CMD_WITH_PARAM("sudo sw config userdel %s", argv[0]);
    return CMD_SUCCESS;
}

DEFUN (show_user_account,
       show_user_account_cmd,
       "show user-account",
       SHOW_STR
       "Show user information\n")
{
    execute_linux_cmd_pipe("sudo sw show user_account");

    return CMD_SUCCESS;
}

DEFUN (show_users,
       show_users_cmd,
       "show users",
       SHOW_STR
       "Display the usernames which currently logged into the switch\n")
{
    execute_linux_cmd_pipe("pinky");
    return CMD_SUCCESS;
}

DEFUN (cli_aaa_auth_login_one,
       aaa_auth_login_one_cmd,
       "aaa authentication login (local|tacacs+)",
       AAA_HELP_STR
       AAA_AUTHENTICATION_HELP_STR
       AAA_LOGIN_HELP_STR
       "Local authentication\n"
       "TACACS+ authentication\n")
{
    TACACS_EXEC_CMD_WITH_PARAM("sudo config aaa authentication login %s",
            argv[0]);

    if(author_update_config())
        vty_out(vty, "Update TACACS+ configuration fail\n");

    return CMD_SUCCESS;
}

DEFUN (cli_aaa_auth_login_local_tacacs,
       aaa_auth_login_local_tacacs_cmd,
       "aaa authentication login local tacacs+",
       AAA_HELP_STR
       AAA_AUTHENTICATION_HELP_STR
       AAA_LOGIN_HELP_STR
       "Local authentication\n"
       "TACACS+ authentication\n")
{
    execute_linux_cmd_pipe("sudo config aaa authentication login local tacacs+");
    if(author_update_config())
        vty_out(vty, "Update TACACS+ configuration fail\n");

    return CMD_SUCCESS;
}

DEFUN (cli_aaa_auth_login_tacacs_local,
       aaa_auth_login_tacacs_local_cmd,
       "aaa authentication login tacacs+ local",
       AAA_HELP_STR
       AAA_AUTHENTICATION_HELP_STR
       AAA_LOGIN_HELP_STR
       "TACACS+ authentication\n"
       "Local authentication\n")
{
    execute_linux_cmd_pipe("sudo config aaa authentication login tacacs+ local");
    if(author_update_config())
        vty_out(vty, "Update TACACS+ configuration fail\n");

    return CMD_SUCCESS;
}


DEFUN (cli_no_aaa_auth_login,
       no_aaa_auth_login_cmd,
       "no aaa authentication login",
       NO_STR
       AAA_HELP_STR
       AAA_AUTHENTICATION_HELP_STR
       AAA_LOGIN_HELP_STR)
{
    execute_linux_cmd_pipe("sudo config aaa authentication login default");
    if(author_update_config())
        vty_out(vty, "Update TACACS+ configuration fail\n");
    return CMD_SUCCESS;
}

DEFUN(cli_aaa_allow_fail_through,
      aaa_allow_fail_through_cmd,
      "aaa authentication allow-fail-through",
      AAA_HELP_STR
      AAA_AUTHENTICATION_HELP_STR
      AAA_ALLOW_FAIL_THROUGH_HELP_STR)
{
    execute_linux_cmd_pipe("sudo config aaa authentication failthrough enable");
    if(author_update_config())
        vty_out(vty, "Update TACACS+ configuration fail\n");
    return CMD_SUCCESS;
}

DEFUN(cli_no_aaa_allow_fail_through,
      no_aaa_allow_fail_through_cmd,
      "no aaa authentication allow-fail-through",
      NO_STR
      AAA_HELP_STR
      AAA_AUTHENTICATION_HELP_STR
      AAA_ALLOW_FAIL_THROUGH_HELP_STR)
{
    execute_linux_cmd_pipe("sudo config aaa authentication failthrough default");
    if(author_update_config())
        vty_out(vty, "Update TACACS+ configuration fail\n");

    return CMD_SUCCESS;
}

DEFUN(cli_tacacs_server_set_passkey,
      tacacs_server_set_passkey_cmd,
      "tacacs-server key WORD",
      TACACS_SERVER_HELP_STR
      SHARED_KEY_HELP_STR
      SHARED_KEY_VAL_HELP_STR)
{
    TACACS_EXEC_CMD_WITH_PARAM("sudo config tacacs passkey %s", argv[0]);
    if(author_update_config())
        vty_out(vty, "Update TACACS+ configuration fail\n");

    return CMD_SUCCESS;
}

DEFUN(cli_no_tacacs_server_set_passkey,
      no_tacacs_server_set_passkey_cmd,
      "no tacacs-server key",
      NO_STR
      TACACS_SERVER_HELP_STR
      SHARED_KEY_HELP_STR)
{
    execute_linux_cmd_pipe("sudo config tacacs default passkey");
    if(author_update_config())
        vty_out(vty, "Update TACACS+ configuration fail\n");

    return CMD_SUCCESS;
}

DEFUN(cli_tacacs_server_set_timeout,
      tacacs_server_set_timeout_cmd,
      "tacacs-server timeout <1-60>",
      TACACS_SERVER_HELP_STR
      TIMEOUT_HELP_STR
      TIMEOUT_RANGE_HELP_STR)
{
    TACACS_EXEC_CMD_WITH_PARAM("sudo config tacacs timeout %s", argv[0]);
    if(author_update_config())
        vty_out(vty, "Update TACACS+ configuration fail\n");

    return CMD_SUCCESS;
}

DEFUN(cli_no_tacacs_server_set_timeout,
      no_tacacs_server_set_timeout_cmd,
      "no tacacs-server timeout",
      NO_STR
      TACACS_SERVER_HELP_STR
      TIMEOUT_HELP_STR)
{
    execute_linux_cmd_pipe("sudo config tacacs default timeout");
    if(author_update_config())
        vty_out(vty, "Update TACACS+ configuration fail\n");

    return CMD_SUCCESS;
}

DEFUN(cli_tacacs_server_set_auth_type,
      tacacs_server_set_auth_type_cmd,
      "tacacs-server auth-type ( pap | chap)",
      TACACS_SERVER_HELP_STR
      AAA_AUTH_TYPE_HELP_STR
      AUTH_TYPE_PAP_HELP_STR
      AUTH_TYPE_CHAP_HELP_STR)
{
    TACACS_EXEC_CMD_WITH_PARAM("sudo config tacacs authtype %s", argv[0]);
    if(author_update_config())
        vty_out(vty, "Update TACACS+ configuration fail\n");

    return CMD_SUCCESS;
}

DEFUN(cli_no_tacacs_server_set_auth_type,
      no_tacacs_server_set_auth_type_cmd,
      "no tacacs-server auth-type",
      NO_STR
      TACACS_SERVER_HELP_STR
      AAA_AUTH_TYPE_HELP_STR)
{
    execute_linux_cmd_pipe("sudo config tacacs default authtype");
    if(author_update_config())
        vty_out(vty, "Update TACACS+ configuration fail\n");

    return CMD_SUCCESS;
}

DEFUN(cli_tacacs_server_set_src_addr,
      tacacs_server_set_src_addr_cmd,
      "tacacs-server source-address A.B.C.D",
      TACACS_SERVER_HELP_STR
      "Set source ip address\n"
      "Set the source ip address for output packets\n")
{
    TACACS_EXEC_CMD_WITH_PARAM("sudo config tacacs src_ip %s", argv[0]);
    if(author_update_config())
        vty_out(vty, "Update TACACS+ configuration fail\n");

    return CMD_SUCCESS;
}

DEFUN(cli_no_tacacs_server_set_src_addr,
      no_tacacs_server_set_src_addr_cmd,
      "no tacacs-server source-address",
      NO_STR
      TACACS_SERVER_HELP_STR
      "Set source ip address\n")
{
    execute_linux_cmd_pipe("sudo config tacacs default src_ip");
    if(author_update_config())
        vty_out(vty, "Update TACACS+ configuration fail\n");

    return CMD_SUCCESS;
}

DEFUN (cli_tacacs_server_host,
       tacacs_server_host_cmd,
       "tacacs-server host A.B.C.D {port <1-65535>|timeout <1-60>|key WORD|auth-type (pap|chap)|priority <1-64>}",
       TACACS_SERVER_HELP_STR
       TACACS_SERVER_HOST_HELP_STR
       TACACS_SERVER_NAME_HELP_STR
       AUTH_PORT_HELP_STR
       AUTH_PORT_RANGE_HELP_STR
       TIMEOUT_HELP_STR
       TIMEOUT_RANGE_HELP_STR
       SHARED_KEY_HELP_STR
       SHARED_KEY_VAL_HELP_STR
       AAA_AUTH_TYPE_HELP_STR
       AUTH_TYPE_PAP_HELP_STR
       AUTH_TYPE_CHAP_HELP_STR
       "Priority for TACACS+ server\n"
       "Priority range is 1 to 64. (Default: 1)\n")
{
    char cmd[256] = {0};
    char *buf = cmd;
    int cnt, len = 256;

    if(!argv[0])
        return CMD_ERR_INCOMPLETE;
    cnt = snprintf(buf, len, "sudo config tacacs add %s", argv[0]);
    buf += cnt;
    len -= cnt;

    if(argv[1])
    {
        cnt = snprintf(buf, len, " -o %s", argv[1]);
        buf += cnt;
        len -= cnt;
    }
    if(argv[2])
    {
        cnt = snprintf(buf, len, " -t %s", argv[2]);
        buf += cnt;
        len -= cnt;
    }
    if(argv[3])
    {
        cnt = snprintf(buf, len, " -k %s", argv[3]);
        buf += cnt;
        len -= cnt;
    }
    if(argv[4])
    {
        cnt = snprintf(buf, len, " -a %s", argv[4]);
        buf += cnt;
        len -= cnt;
    }
    if(argv[5])
    {
        cnt = snprintf(buf, len, " -p %s", argv[5]);
        buf += cnt;
        len -= cnt;
    }
    execute_linux_cmd_pipe(cmd);
    if(author_update_config())
        vty_out(vty, "Update TACACS+ configuration fail\n");

    return CMD_SUCCESS;
}

DEFUN (cli_no_tacacs_server_host,
       no_tacacs_server_host_cmd,
       "no tacacs-server host WORD",
       NO_STR
       TACACS_SERVER_HELP_STR
       TACACS_SERVER_HOST_HELP_STR
       TACACS_SERVER_NAME_HELP_STR)
{
    TACACS_EXEC_CMD_WITH_PARAM("sudo config tacacs delete %s", argv[0]);
    if(author_update_config())
        vty_out(vty, "Update TACACS+ configuration fail\n");

    return CMD_SUCCESS;
}

DEFUN (cli_show_tacacs_server,
       show_tacacs_server_cmd,
       "show tacacs-server",
       SHOW_STR
       TACACS_SERVER_HELP_STR)
{
    execute_linux_cmd_pipe("show tacacs");
    return CMD_SUCCESS;
}

DEFUN (cli_show_aaa,
       show_aaa_cmd,
       "show aaa",
       SHOW_STR
       AAA_HELP_STR)
{
    execute_linux_cmd_pipe("show aaa");
    return CMD_SUCCESS;
}

DEFUN (cli_show_privilege,
       show_privilege_cmd,
       "show privilege",
       SHOW_STR
       "Display the current privilege level\n")
{
    vty_out(vty, "Current privilege level is %d\n", author_get_privilege());
    return CMD_SUCCESS;
}

DEFUN (cli_aaa_set_auz_one,
       aaa_set_auz_one_cmd,
       "aaa authorization commands (tacacs+|none)",
       AAA_HELP_STR
       AAA_AUTHORIZATION_HELP_STR
       AAA_COMMAND_AUZ_STR
       TACACS_ENABLE_AUZ_STR
       AAA_NONE_AUTHOR_HELP_STR)
{
    TACACS_EXEC_CMD_WITH_PARAM("sudo config aaa authorization commands %s",
            argv[0]);

    if(author_update_config())
        vty_out(vty, "Update TACACS+ configuration fail\n");

    return CMD_SUCCESS;
}

DEFUN (cli_aaa_set_auz_two,
       aaa_set_auz_two_cmd,
       "aaa authorization commands tacacs+ none",
       AAA_HELP_STR
       AAA_AUTHORIZATION_HELP_STR
       AAA_COMMAND_AUZ_STR
       TACACS_ENABLE_AUZ_STR
       AAA_NONE_AUTHOR_HELP_STR)
{
    execute_linux_cmd_pipe("sudo config aaa authorization commands tacacs+ none");

    if(author_update_config())
        vty_out(vty, "Update TACACS+ configuration fail\n");

    return CMD_SUCCESS;
}

DEFUN (cli_no_aaa_set_auz,
       no_aaa_set_auz_cmd,
       "no aaa authorization commands",
       NO_STR
       AAA_HELP_STR
       AAA_AUTHORIZATION_HELP_STR
       AAA_COMMAND_AUZ_STR)
{
    execute_linux_cmd_pipe("sudo config aaa authorization commands default");
    if(author_update_config())
        vty_out(vty, "Update TACACS+ configuration fail\n");

    return CMD_SUCCESS;
}

DEFUN (cli_debug_aaa,
       debug_aaa_cmd,
       "debug aaa",
       "Debugging functions\n"
       "AAA information\n")
{
    author_set_debug(true);
    return CMD_SUCCESS;
}

DEFUN (cli_undebug_aaa,
       undebug_aaa_cmd,
       "undebug aaa",
       "Disable debugging functions (see also 'debug')\n"
       "AAA information\n")
{
    author_set_debug(false);
    return CMD_SUCCESS;
}

void
vtysh_user_init ()
{
  //userlist = list_new ();
  //install_element (CONFIG_NODE, &username_nopassword_cmd);

    install_element (CONFIG_NODE, &username_password_cmd);
    install_element (CONFIG_NODE, &username_role_password_cmd);
    install_element (CONFIG_NODE, &no_username_password_cmd);
    install_element (CONFIG_NODE, &show_user_account_cmd);
    install_element (ENABLE_NODE, &show_users_cmd);
    install_element (ENABLE_NODE, &show_user_account_cmd);
    install_element (CONFIG_NODE, &show_users_cmd);

    install_element (CONFIG_NODE, &aaa_auth_login_one_cmd);
    install_element (CONFIG_NODE, &aaa_auth_login_local_tacacs_cmd);
    install_element (CONFIG_NODE, &aaa_auth_login_tacacs_local_cmd);
    install_element (CONFIG_NODE, &no_aaa_auth_login_cmd);
    install_element (CONFIG_NODE, &aaa_allow_fail_through_cmd);
    install_element (CONFIG_NODE, &no_aaa_allow_fail_through_cmd);
    install_element (CONFIG_NODE, &aaa_set_auz_two_cmd);
    install_element (CONFIG_NODE, &aaa_set_auz_one_cmd);
    install_element (CONFIG_NODE, &no_aaa_set_auz_cmd);
    install_element (CONFIG_NODE, &debug_aaa_cmd);
    install_element (CONFIG_NODE, &undebug_aaa_cmd);

    install_element (CONFIG_NODE, &tacacs_server_set_passkey_cmd);
    install_element (CONFIG_NODE, &no_tacacs_server_set_passkey_cmd);
    install_element (CONFIG_NODE, &tacacs_server_set_timeout_cmd);
    install_element (CONFIG_NODE, &no_tacacs_server_set_timeout_cmd);
    install_element (CONFIG_NODE, &tacacs_server_set_auth_type_cmd);
    install_element (CONFIG_NODE, &no_tacacs_server_set_auth_type_cmd);
    install_element (CONFIG_NODE, &tacacs_server_set_src_addr_cmd);
    install_element (CONFIG_NODE, &no_tacacs_server_set_src_addr_cmd);
    install_element (CONFIG_NODE, &tacacs_server_host_cmd);
    install_element (CONFIG_NODE, &no_tacacs_server_host_cmd);

    install_element (CONFIG_NODE, &show_tacacs_server_cmd);
    install_element (CONFIG_NODE, &show_aaa_cmd);
    install_element (CONFIG_NODE, &show_privilege_cmd);
    install_element (ENABLE_NODE, &show_tacacs_server_cmd);
    install_element (ENABLE_NODE, &show_aaa_cmd);
    install_element (ENABLE_NODE, &show_privilege_cmd);
}

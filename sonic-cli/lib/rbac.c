#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <pwd.h>
#include <grp.h>
#include <syslog.h>

#include "rbac.h"

static enum rbac_access role_access = RBAC_NONE_ACCESS;

/* User role access profile map:
     root: ADMIN
     admin: ADMIN
     user in ConfigDB: (Role value in configDB)
     TACACS+ user priv-lvl = 1-14: READ
     TACACS+ user priv-lvl = 15: WRITE
     other: READ (defautly)
   */
int rbac_set_access(int privlege_lvl)
{
    struct passwd *passwd = NULL;
    FILE *fstream=NULL;
    char cmd[128] = {0};
    char output[512] = {0};

    passwd = getpwuid(geteuid());
    if (!passwd)
    {
        fprintf(stderr, "Exiting: failed to find user in passwd.\n");
        exit(1);
    }

    if(!strcmp("root", passwd->pw_name) || !strcmp("admin", passwd->pw_name))
    {
        role_access = RBAC_ADMIN_ACCESS;
        return 0;
    }

    snprintf(cmd, 128,
        "redis-cli --csv -n 4 hget 'USER_METADATA|%s' 'role'", passwd->pw_name);
    if(!(fstream = popen(cmd, "r")))
    {
        fprintf(stderr, "Exiting: failed to get user role.\n");
        exit(1);
    }

    while(fgets(output, sizeof(output), fstream))
    {
        if(!strncmp(output, "\"READ\"", 6))
            role_access = RBAC_READ_ACCESS;
        else if(!strncmp(output, "\"WRITE\"", 7))
            role_access = RBAC_WRITE_ACCESS;
        else if(!strncmp(output, "\"ADMIN\"", 7))
            role_access = RBAC_ADMIN_ACCESS;
    }
    pclose(fstream);

    /* Assume TACACS+ user is not saved in configDB. If there is the same user
           name, it will get configDB user's access */
    if(RBAC_NONE_ACCESS == role_access)
    {
        if(privlege_lvl == 15)
            role_access = RBAC_WRITE_ACCESS;
        else if(privlege_lvl <= 14 && privlege_lvl >= 1)
            role_access = RBAC_READ_ACCESS;
        else
            syslog(LOG_ERR, "rbac: invalid privlege_lvl %d", privlege_lvl);
    }

    return role_access == RBAC_NONE_ACCESS ? -1 : 0;
}

int rbac_get_access()
{
    // If not found role access, set READ_ACCESS by default
    if (role_access == RBAC_NONE_ACCESS)
        role_access = RBAC_READ_ACCESS;

    return role_access;
}

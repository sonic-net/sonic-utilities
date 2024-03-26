#ifndef _RBAC_H
#define _RBAC_H

enum rbac_access
{
    RBAC_NONE_ACCESS = 0,
    RBAC_READ_ACCESS,
    RBAC_WRITE_ACCESS,
    RBAC_ADMIN_ACCESS
};

int rbac_set_access(int privlege_lvl);
int rbac_get_access();

#endif /* _RBAC_H */

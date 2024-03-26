#ifndef _AUTHORIZATION_H
#define _AUTHORIZATION_H

#include <stdbool.h>

#define AUTHOR_OK         0  /* Authorized */
#define AUTHOR_FAIL       1  /* Authorization was denied */
#define AUTHOR_ADDR_ERR   2  /* Error when resolving TACACS server address */
#define AUTHOR_CONN_ERR   3  /* Connection to TACACS server failed */
#define AUTHOR_SEND_ERR   4  /* Error when sending authorization request */
#define AUTHOR_READ_ERR   5  /* Error when reading authorization reply */
#define AUTHOR_ERR        6  /* local error */

void author_set_debug(bool enable);
int author_update_config();
int author_check_cmd(const char* cmd);
int author_get_privilege();

#endif /* _AUTHORIZATION_H */

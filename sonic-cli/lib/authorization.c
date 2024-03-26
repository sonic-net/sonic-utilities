#include <stdlib.h>
#include <stdbool.h>
#include <string.h>
#include <syslog.h>
#include <errno.h>
#include <fcntl.h>
#include <ctype.h>
#include <netdb.h>
#include <unistd.h>
#include <sys/types.h>
#include <pwd.h>
#include <utmp.h>

#include "authorization.h"
#include "libtac/libtac.h"


#define MAX_PRIV_LVL (15)
#define MIN_PRIV_LVL (1)

typedef struct {
    struct addrinfo *addr;
    char *key;
    int timeout;
}tacplus_server_t;

enum author_type{
    AUTHOR_ENABLE_NONE = 0,
    AUTHOR_ENABLE_TACACS,
    AUTHOR_ENABLE_ALL
};

static tacplus_server_t tac_srv[TAC_PLUS_MAXSERVERS];
static int tac_srv_no;
static struct addrinfo *source_addr;

static const char *vtysh_author = "[author]"; /* for syslogs */
static const char *config_file = "/etc/tacplus_nss.conf";
static char *tac_service = "shell";
static char *tac_protocol = "ip";
static bool debug = false;

static char user_name[32];
static char tac_tty[32];
static char tac_remote_addr[32];
static enum author_type author_enable_grp[2];

#define AUTHOR_LOG_DBG(format, ...) \
    do { \
        if(debug) \
            syslog(LOG_DEBUG, format, __VA_ARGS__); \
    }while(0)


void author_set_debug(bool enable)
{
    debug = enable;
    if(!debug)
        setlogmask(LOG_UPTO(LOG_NOTICE));
    else
        setlogmask(LOG_UPTO(LOG_DEBUG));
}

/* Parse TACACS+ server line in tacplus_nss.conf */
static int parse_tac_server(char *srv_buf)
{
    char *token;
    char delim[] = " ,\t\n\r\f";

    token = strsep(&srv_buf, delim);
    while(token)
    {
        if('\0' != token)
        {
            if(!strncmp(token, "server=", 7))
            {
                struct addrinfo hints, *server;
                int rv;
                char *srv, *port;

                memset(&hints, 0, sizeof hints);
                hints.ai_family = AF_UNSPEC;
                hints.ai_socktype = SOCK_STREAM;

                srv = token + 7;
                port = strchr(srv, ':');
                if(port)
                {
                    *port = '\0';
                    port++;
                }

                if((rv = getaddrinfo(srv, (port == NULL) ? "49" : port, &hints,
                    &server)) == 0)
                {
                    if(server)
                    {
                        if(tac_srv[tac_srv_no].addr)
                            freeaddrinfo(tac_srv[tac_srv_no].addr);
                        if(tac_srv[tac_srv_no].key)
                            free(tac_srv[tac_srv_no].key);
                        memset(tac_srv + tac_srv_no, 0, sizeof(tacplus_server_t));

                        tac_srv[tac_srv_no].addr = server;
                    }
                    else
                    {
                        syslog(LOG_ERR, "%s: server NULL", vtysh_author);
                    }
                }
                else
                {
                    syslog(LOG_ERR, "%s: invalid server: %s (getaddrinfo: %s)",
                        vtysh_author, srv, gai_strerror(rv));
                    return -1;
                }
            }
            else if(!strncmp(token, "secret=", 7))
            {
                if(tac_srv[tac_srv_no].key)
                    free(tac_srv[tac_srv_no].key);
                tac_srv[tac_srv_no].key = strdup(token + 7);
            }
            else if(!strncmp(token, "timeout=", 8))
            {
                tac_srv[tac_srv_no].timeout = (int)strtoul(token + 8, NULL, 0);
                if(tac_srv[tac_srv_no].timeout < 0)
                    tac_srv[tac_srv_no].timeout = 0;
            }
        }
        token = strsep(&srv_buf, delim);
    }

    return 0;
}


/* Temporarily use tacplus_nss.conf to parse tacplus_server. */
static int update_tacplus_server()
{
    FILE *fp;
    char buf[512] = {0};

    fp = fopen(config_file, "r");
    if(!fp)
    {
        syslog(LOG_ERR, "%s: %s fopen failed", vtysh_author, config_file);
        return -1;
    }

    tac_srv_no = 0;
    while(fgets(buf, sizeof buf, fp))
    {
        if('#' == *buf || isspace(*buf))
            continue;

        if(!strncmp(buf, "src_ip=", 7))
        {
            struct addrinfo hints;
            char *ip = buf + 7;

            memset(&hints, 0, sizeof hints);
            hints.ai_family = AF_UNSPEC;
            hints.ai_socktype = SOCK_STREAM;

            if(source_addr)
                freeaddrinfo(source_addr);

            if(0 != getaddrinfo(ip, NULL, &hints, &source_addr))
                syslog(LOG_ERR, "%s: error setting the source ip information",
                    vtysh_author);
        }
        else if(!strncmp(buf, "server=", 7))
        {
            if(TAC_PLUS_MAXSERVERS <= tac_srv_no)
            {
                syslog(LOG_ERR, "%s: tac server num is more than %d",
                    vtysh_author, TAC_PLUS_MAXSERVERS);
            }
            else if(0 == parse_tac_server(buf))
                ++tac_srv_no;
        }
    }
    fclose(fp);

    if(debug)
    {
        int n;

        for(n = 0; n < tac_srv_no; n++)
        {
            AUTHOR_LOG_DBG("%s: server[%d] { addr=%s, key=%s, timeout=%d }",
                        vtysh_author, n, tac_ntop(tac_srv[n].addr->ai_addr),
                        tac_srv[n].key, tac_srv[n].timeout);
        }
        AUTHOR_LOG_DBG("%s: src_ip=%s", vtysh_author, NULL == source_addr
                    ? "NULL" : tac_ntop(source_addr->ai_addr));
    }

    return 0;
}

/* To avoid the complexity of dynamically updating tacplus server,  cache
 * the tacacs configuration at two scenarios.
 *   1) Get the tacacs configuration when initialize vtysh
 *   2) Update the cache when current process modified the tacacs configuration
 */
int author_update_config()
{
    FILE *fstream=NULL;
    char output[512] = {0};

    if(!(fstream = popen(
        "redis-cli --csv -n 4 hget 'AAA|authorization' 'commands'", "r")))
    {
        fprintf(stderr, "Exiting: failed to get authorization config.\n");
        exit(1);
    }

    while(fgets(output, sizeof(output), fstream))
    {
        if(!strncmp(output, "\"tacacs+,none\"", 14))
        {
            author_enable_grp[0] = AUTHOR_ENABLE_TACACS;
            author_enable_grp[1] = AUTHOR_ENABLE_ALL;
        }
        else if(!strncmp(output, "\"tacacs+\"",  9))
        {
            author_enable_grp[0] = AUTHOR_ENABLE_TACACS;
            author_enable_grp[1] = AUTHOR_ENABLE_NONE;
        }
        /* default authorization none */
        else
        {
            author_enable_grp[0] = AUTHOR_ENABLE_ALL;
            author_enable_grp[1] = AUTHOR_ENABLE_NONE;
        }
    }
    pclose(fstream);

    return update_tacplus_server();
}

static char* get_user_name()
{
    struct passwd *pw;

    if(0 != *user_name)
        return user_name;

    pw = getpwuid(getuid());
    if(!pw->pw_name)
    {
        syslog(LOG_ERR, "%s: can't get user name (uid=%d)",
                vtysh_author, getuid());
        return NULL;
    }

    memcpy(user_name, pw->pw_name, strlen(pw->pw_name));
    return user_name;
}

/* Send athorization packet to TACACS+ server to receive the attribute 'priv-lvl' */
static int tac_get_priv_level(char *user, tacplus_server_t *server, int *priv_level)
{
    struct areply arep;
    struct tac_attrib *attr = NULL;
    int tac_fd;
    int ret = AUTHOR_OK;

    arep.msg = NULL;
    arep.attr = NULL;
    arep.status = TAC_PLUS_AUTHOR_STATUS_ERROR;

    tac_fd = tac_connect_single(server->addr, server->key,
                                source_addr, server->timeout);
    if(tac_fd < 0)
    {
        syslog(LOG_WARNING, "%s: failed to connect TACACS+ server %s, ret=%d",
            vtysh_author, tac_ntop(server->addr->ai_addr), tac_fd);
        return AUTHOR_CONN_ERR;
    }

    tac_add_attrib(&attr, "service", tac_service);
    tac_add_attrib(&attr, "cmd", "");

    ret = tac_author_send(tac_fd, user, "", "", attr);
    if(ret < 0)
    {
        syslog(LOG_WARNING, "%s: TACACS+ server %s send failed (%d) for user %s",
            vtysh_author, tac_ntop(server->addr->ai_addr), ret, user);
        ret = AUTHOR_SEND_ERR;
        goto CLEAN_UP;
    }

    ret = tac_author_read(tac_fd, &arep);
    if (ret < 0)
    {
        syslog(LOG_WARNING, "%s: TACACS+ server %s read failed (%d) for user %s",
            vtysh_author, tac_ntop(server->addr->ai_addr), ret, user);
        close(tac_fd);
        ret = AUTHOR_READ_ERR;
        goto CLEAN_UP;
    }

    close(tac_fd);

    if(arep.status == AUTHOR_STATUS_PASS_ADD ||
        arep.status == AUTHOR_STATUS_PASS_REPL)
    {
        struct tac_attrib *attr_t = arep.attr;
        while(attr_t != NULL)
        {
            /* looking for the privilege attribute,  priv-lvl= or priv_lvl= */
            if(strncasecmp(attr_t->attr, "priv", 4) == 0)
            {
                char *ok, *val;
                unsigned long priv_lvl = 0;

                for(val=attr_t->attr; *val && *val != '*' && *val != '='; val++)
                    ;
                if(!*val)
                    continue;
                val++;

                priv_lvl = strtoul(val, &ok, 0);
                *priv_level = priv_lvl;
                ret = 0;
                AUTHOR_LOG_DBG("%s privilege for %s, (%lu)", vtysh_author,
                    user, priv_lvl);
            }
            attr_t = attr_t->next;
        }
    }

    CLEAN_UP:
        tac_free_attrib(&attr);
        if(arep.msg)
            free(arep.msg);
        if(arep.attr)
            tac_free_attrib(&arep.attr);

    return ret;
}

/* Obtain privilege level for TACACS+ user, only filter the user 'root' and 'admin'.
 * The other local user will try to obtain privilege level. If tacacs servers didn't
 * return valid value, return MIN privilege level.*/
int author_get_privilege()
{
    tacplus_server_t *server;
    int i, priv_level = 0;
    int ret = 0;

    if(!get_user_name())
        return -1;

    if(!strcmp("root", user_name) || !strcmp("admin", user_name))
        return MAX_PRIV_LVL;

    for(i = 0; i < tac_srv_no; i++)
    {
        server = &tac_srv[i];
        if(!server->addr || !server->key)
        {
            syslog(LOG_ERR, "%s: Invalid TACACS+ server[%d]=%s", vtysh_author,
                i, server->addr ? tac_ntop(server->addr->ai_addr) : "unknown");
        }
        else
        {
            ret = tac_get_priv_level(user_name, server, &priv_level);
            if(!ret)
            {
                if(priv_level < MIN_PRIV_LVL || priv_level > MAX_PRIV_LVL)
                    syslog(LOG_ERR, "%s: Invalid privilege %d", vtysh_author,
                        priv_level);
                break;
            }
        }
    }

    return ret == 0 ? priv_level : MIN_PRIV_LVL;
}

static char* get_tac_tty()
{
    if(*tac_tty == 0)
    {
        char *ret = NULL;
        ret = ttyname(STDIN_FILENO);
        if(ret)
        {
            if(!strncmp(ret, "/dev/", strlen("/dev/")))
                ret += strlen("/dev/");
            strcpy(tac_tty, ret);
        }
        else
        {
            syslog(LOG_ERR, "[%s] get ttyname error", vtysh_author);
            strcpy(tac_tty, "unkown");
        }
    }

    return tac_tty;
}

static char* get_tac_remote_addr()
{
    if(*tac_remote_addr == 0)
    {
        struct utmp ut, *ret = NULL;

        strncpy(ut.ut_line, get_tac_tty(), UT_LINESIZE);
        ret = getutline(&ut);
        if(ret)
        {
            // Only convert ipv4 address
            snprintf(tac_remote_addr, 32, "%d.%d.%d.%d",
                        (ret->ut_addr_v6[0]) & 0xFF,
                        (ret->ut_addr_v6[0] >> 8) & 0xFF,
                        (ret->ut_addr_v6[0] >> 16) & 0xFF,
                        (ret->ut_addr_v6[0] >> 24) & 0xFF);
        }
        else
            strcpy(tac_remote_addr, "");
    }
    return tac_remote_addr;
}

/* Send authorization request to TACACS+ server to check command */
static int tac_cmd_author(const tacplus_server_t *server,const char *user, char *command)
{
    int tac_fd;
    int send_status;
    int status_code;
    struct areply arep;
    struct addrinfo hints;
    struct tac_attrib *attr = NULL;
    char *arg = command;
    char buf[128] = {0};

    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;

    /* Set TACACS attributes */
    tac_add_attrib(&attr, "service", tac_service);
    tac_add_attrib(&attr, "protocol", tac_protocol);

    while(*arg != ' ' && *arg != '\0')
        arg++;
    if(*arg == ' ')
    {
        memcpy(buf, command, arg - command);
        buf[arg - command] = '\0';
        tac_add_attrib(&attr, "cmd", buf);
        tac_add_attrib(&attr, "cmd-arg", arg + 1);
    }
    else
    {
        tac_add_attrib(&attr, "cmd", command);
    }

    /* TACACS connection to tac_server */
    tac_fd = tac_connect_single(server->addr, server->key,
                                source_addr, server->timeout);

    if (tac_fd < 0)
    {
        AUTHOR_LOG_DBG("%s: Error connecting to TACACS+ server %s",
                    vtysh_author, tac_ntop(server->addr->ai_addr));
        status_code = AUTHOR_CONN_ERR;
        goto CLEAN_UP;
    }

    /* TACACS authorization request to the connected server fd */
    send_status = tac_author_send(tac_fd, user, get_tac_tty(),
                                    get_tac_remote_addr(), attr);

    if (send_status < 0)
    {
        AUTHOR_LOG_DBG("%s: Sending authorization request failed", vtysh_author);
        status_code = AUTHOR_SEND_ERR;
        goto CLEAN_UP;
    }

    /* Read TACACS server authorization response */
    tac_author_read(tac_fd, &arep);

    if (arep.status != AUTHOR_STATUS_PASS_ADD
        && arep.status != AUTHOR_STATUS_PASS_REPL)
    {
        AUTHOR_LOG_DBG("%s: Authorization FAILED: %s", vtysh_author, arep.msg);
        status_code = AUTHOR_FAIL;
    }
    else
    {
        AUTHOR_LOG_DBG("%s: Authorization OK: %s", vtysh_author, arep.msg);
        status_code = AUTHOR_OK;
    }

    CLEAN_UP:
    if(attr)
        tac_free_attrib(&attr);
    if(arep.msg)
        free(arep.msg);
    if(arep.attr)
        tac_free_attrib(&arep.attr);

    return status_code;
}

/* TACACS+ command authorization */
int author_check_cmd(const char* cmd)
{
    char command[256] = {0};
    tacplus_server_t *server;
    int i, ret = AUTHOR_OK;

    if(AUTHOR_ENABLE_ALL != author_enable_grp[0] && 
        AUTHOR_ENABLE_TACACS != author_enable_grp[0])
    {
        syslog(LOG_ERR, "%s: Invalid authorization config %d",
            vtysh_author, author_enable_grp[0]);
        return AUTHOR_ERR;
    }
        
    if(AUTHOR_ENABLE_ALL == author_enable_grp[0])
        return AUTHOR_OK;

    if(!get_user_name())
        return AUTHOR_ERR;

    // If user is root or admin, doesn't need command authorization and permit all.
    if(!strcmp("root", user_name) || !strcmp("admin", user_name))
        return 0;

    strcpy(command, cmd);
    for(i = 0; i < tac_srv_no; i++)
    {
        server = &tac_srv[i];
        if(server->addr && server->key)
        {
            ret = tac_cmd_author(server, user_name, command);
            if(AUTHOR_OK == ret || AUTHOR_FAIL == ret)
            {
                syslog(LOG_INFO, "command '%s' authorized %s", cmd,
                    ret == AUTHOR_OK ? "success" : "fail");
                return ret;
            }
        }
    }

    /* If TACACS+ command authorization fails, need to check the second
     * authorization config. */
    if(AUTHOR_ENABLE_ALL == author_enable_grp[1])
    {
        return AUTHOR_OK;
    }
    
    return AUTHOR_CONN_ERR;
}

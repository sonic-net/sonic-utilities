"""
Module holding the correct values for show CLI command outputs for the ldap_test.py
"""

show_ldap_global = """\
BIND DN                       BIND PASSWORD      BIND TIMEOUT    VERSION  BASE DN              PORT    TIMEOUT
----------------------------  ---------------  --------------  ---------  -----------------  ------  ---------
cn=ldapadm,dc=test1,dc=test2  password                      3          3  dc=test1,dc=test2     389          2
"""

show_ldap_server = """\
HOSTNAME      PRIORITY
----------  ----------
10.0.0.1             1
"""

show_ldap_server_deleted = """\
HOSTNAME    PRIORITY
----------  ----------
"""

"""
Module holding the correct values for show CLI command outputs for the passw_hardening_test.py
"""

show_passw_hardening_policies_default="""\
STATE       EXPIRATION    EXPIRATION WARNING    HISTORY CNT    LEN MIN  REJECT USER PASSW MATCH    LOWER CLASS    UPPER CLASS    DIGITS CLASS    SPECIAL CLASS
--------  ------------  --------------------  -------------  ---------  -------------------------  -------------  -------------  --------------  ---------------
disabled           180                    15             10          8  true                       true           true           true            true
"""

show_passw_hardening_policies_classes_disabled="""\
STATE       EXPIRATION    EXPIRATION WARNING    HISTORY CNT    LEN MIN  REJECT USER PASSW MATCH    LOWER CLASS    UPPER CLASS    DIGITS CLASS    SPECIAL CLASS
--------  ------------  --------------------  -------------  ---------  -------------------------  -------------  -------------  --------------  ---------------
disabled           180                    15             10          8  false                      false          false          false           false
"""

show_passw_hardening_policies_enabled="""\
STATE      EXPIRATION    EXPIRATION WARNING    HISTORY CNT    LEN MIN  REJECT USER PASSW MATCH    LOWER CLASS    UPPER CLASS    DIGITS CLASS    SPECIAL CLASS
-------  ------------  --------------------  -------------  ---------  -------------------------  -------------  -------------  --------------  ---------------
enabled           180                    15             10          8  true                       true           true           true            true
"""


show_passw_hardening_policies_expiration="""\
STATE      EXPIRATION    EXPIRATION WARNING    HISTORY CNT    LEN MIN  REJECT USER PASSW MATCH    LOWER CLASS    UPPER CLASS    DIGITS CLASS    SPECIAL CLASS
-------  ------------  --------------------  -------------  ---------  -------------------------  -------------  -------------  --------------  ---------------
enabled           100                    15             10          8  true                       true           true           true            true
"""

show_passw_hardening_policies_history_cnt="""\
STATE       EXPIRATION    EXPIRATION WARNING    HISTORY CNT    LEN MIN  REJECT USER PASSW MATCH    LOWER CLASS    UPPER CLASS    DIGITS CLASS    SPECIAL CLASS
--------  ------------  --------------------  -------------  ---------  -------------------------  -------------  -------------  --------------  ---------------
disabled           180                    15             40          8  true                       true           true           true            true
"""

show_passw_hardening_policies_len_min="""\
STATE       EXPIRATION    EXPIRATION WARNING    HISTORY CNT    LEN MIN  REJECT USER PASSW MATCH    LOWER CLASS    UPPER CLASS    DIGITS CLASS    SPECIAL CLASS
--------  ------------  --------------------  -------------  ---------  -------------------------  -------------  -------------  --------------  ---------------
disabled           180                    15             10         30  true                       true           true           true            true
"""
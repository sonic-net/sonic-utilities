"""
Module holding the correct values for show CLI command outputs for the portstat_test.py
"""

trim_counters_all = """\
    IFACE    STATE    TRIM_PKTS    TRIM_TX_PKTS    TRIM_DRP_PKTS
---------  -------  -----------  --------------  ---------------
Ethernet0        D          100              50               50
Ethernet4      N/A       20,000          10,000           10,000
Ethernet8      N/A          N/A             N/A              N/A
"""
trim_counters_all_json = """\
{
    "Ethernet0": {
        "STATE": "D",
        "TRIM_DRP_PKTS": "50",
        "TRIM_PKTS": "100",
        "TRIM_TX_PKTS": "50"
    },
    "Ethernet4": {
        "STATE": "N/A",
        "TRIM_DRP_PKTS": "10,000",
        "TRIM_PKTS": "20,000",
        "TRIM_TX_PKTS": "10,000"
    },
    "Ethernet8": {
        "STATE": "N/A",
        "TRIM_DRP_PKTS": "N/A",
        "TRIM_PKTS": "N/A",
        "TRIM_TX_PKTS": "N/A"
    }
}
"""

trim_eth0_counters = """\
    IFACE    STATE    TRIM_PKTS    TRIM_TX_PKTS    TRIM_DRP_PKTS
---------  -------  -----------  --------------  ---------------
Ethernet0        D          100              50               50
"""
trim_eth0_counters_json = """\
{
    "Ethernet0": {
        "STATE": "D",
        "TRIM_DRP_PKTS": "50",
        "TRIM_PKTS": "100",
        "TRIM_TX_PKTS": "50"
    }
}
"""

trim_eth4_counters = """\
    IFACE    STATE    TRIM_PKTS    TRIM_TX_PKTS    TRIM_DRP_PKTS
---------  -------  -----------  --------------  ---------------
Ethernet4      N/A       20,000          10,000           10,000
"""
trim_eth4_counters_json = """\
{
    "Ethernet4": {
        "STATE": "N/A",
        "TRIM_DRP_PKTS": "10,000",
        "TRIM_PKTS": "20,000",
        "TRIM_TX_PKTS": "10,000"
    }
}
"""

trim_eth8_counters = """\
    IFACE    STATE    TRIM_PKTS    TRIM_TX_PKTS    TRIM_DRP_PKTS
---------  -------  -----------  --------------  ---------------
Ethernet8      N/A          N/A             N/A              N/A
"""
trim_eth8_counters_json = """\
{
    "Ethernet8": {
        "STATE": "N/A",
        "TRIM_DRP_PKTS": "N/A",
        "TRIM_PKTS": "N/A",
        "TRIM_TX_PKTS": "N/A"
    }
}
"""

trim_counters_period = """\
The rates are calculated within 3 seconds period
    IFACE    STATE    TRIM_PKTS    TRIM_TX_PKTS    TRIM_DRP_PKTS
---------  -------  -----------  --------------  ---------------
Ethernet0        D            0               0                0
Ethernet4      N/A            0               0                0
Ethernet8      N/A          N/A             N/A              N/A
"""

trim_counters_clear_msg = """\
Cleared counters
"""
trim_counters_clear_stat = """\
    IFACE    STATE    TRIM_PKTS    TRIM_TX_PKTS    TRIM_DRP_PKTS
---------  -------  -----------  --------------  ---------------
Ethernet0        D            0               0                0
Ethernet4      N/A            0               0                0
Ethernet8      N/A          N/A             N/A              N/A
"""

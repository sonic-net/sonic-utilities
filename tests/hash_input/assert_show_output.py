"""
Module holding the correct values for show CLI command outputs for the hash_test.py
"""

show_hash_empty="""\
No configuration is present in CONFIG DB
"""

show_hash_ecmp="""\
+--------+-------------------------------------+
| Hash   | Configuration                       |
+========+=====================================+
| ECMP   | +-------------------+-------------+ |
|        | | Hash Field        | Algorithm   | |
|        | |-------------------+-------------| |
|        | | DST_MAC           | CRC         | |
|        | | SRC_MAC           |             | |
|        | | ETHERTYPE         |             | |
|        | | IP_PROTOCOL       |             | |
|        | | DST_IP            |             | |
|        | | SRC_IP            |             | |
|        | | L4_DST_PORT       |             | |
|        | | L4_SRC_PORT       |             | |
|        | | INNER_DST_MAC     |             | |
|        | | INNER_SRC_MAC     |             | |
|        | | INNER_ETHERTYPE   |             | |
|        | | INNER_IP_PROTOCOL |             | |
|        | | INNER_DST_IP      |             | |
|        | | INNER_SRC_IP      |             | |
|        | | INNER_L4_DST_PORT |             | |
|        | | INNER_L4_SRC_PORT |             | |
|        | +-------------------+-------------+ |
+--------+-------------------------------------+
| LAG    | +--------------+-------------+      |
|        | | Hash Field   | Algorithm   |      |
|        | |--------------+-------------|      |
|        | | N/A          | N/A         |      |
|        | +--------------+-------------+      |
+--------+-------------------------------------+
"""
show_hash_ecmp_json="""\
{
    "ecmp": {
        "hash_field": [
            "DST_MAC",
            "SRC_MAC",
            "ETHERTYPE",
            "IP_PROTOCOL",
            "DST_IP",
            "SRC_IP",
            "L4_DST_PORT",
            "L4_SRC_PORT",
            "INNER_DST_MAC",
            "INNER_SRC_MAC",
            "INNER_ETHERTYPE",
            "INNER_IP_PROTOCOL",
            "INNER_DST_IP",
            "INNER_SRC_IP",
            "INNER_L4_DST_PORT",
            "INNER_L4_SRC_PORT"
        ],
        "algorithm": "CRC"
    },
    "lag": {
        "hash_field": "N/A",
        "algorithm": "N/A"
    }
}
"""

show_hash_lag="""\
+--------+-------------------------------------+
| Hash   | Configuration                       |
+========+=====================================+
| ECMP   | +--------------+-------------+      |
|        | | Hash Field   | Algorithm   |      |
|        | |--------------+-------------|      |
|        | | N/A          | N/A         |      |
|        | +--------------+-------------+      |
+--------+-------------------------------------+
| LAG    | +-------------------+-------------+ |
|        | | Hash Field        | Algorithm   | |
|        | |-------------------+-------------| |
|        | | DST_MAC           | XOR         | |
|        | | SRC_MAC           |             | |
|        | | ETHERTYPE         |             | |
|        | | IP_PROTOCOL       |             | |
|        | | DST_IP            |             | |
|        | | SRC_IP            |             | |
|        | | L4_DST_PORT       |             | |
|        | | L4_SRC_PORT       |             | |
|        | | INNER_DST_MAC     |             | |
|        | | INNER_SRC_MAC     |             | |
|        | | INNER_ETHERTYPE   |             | |
|        | | INNER_IP_PROTOCOL |             | |
|        | | INNER_DST_IP      |             | |
|        | | INNER_SRC_IP      |             | |
|        | | INNER_L4_DST_PORT |             | |
|        | | INNER_L4_SRC_PORT |             | |
|        | +-------------------+-------------+ |
+--------+-------------------------------------+
"""
show_hash_lag_json="""\
{
    "ecmp": {
        "hash_field": "N/A",
        "algorithm": "N/A"
    },
    "lag": {
        "hash_field": [
            "DST_MAC",
            "SRC_MAC",
            "ETHERTYPE",
            "IP_PROTOCOL",
            "DST_IP",
            "SRC_IP",
            "L4_DST_PORT",
            "L4_SRC_PORT",
            "INNER_DST_MAC",
            "INNER_SRC_MAC",
            "INNER_ETHERTYPE",
            "INNER_IP_PROTOCOL",
            "INNER_DST_IP",
            "INNER_SRC_IP",
            "INNER_L4_DST_PORT",
            "INNER_L4_SRC_PORT"
        ],
        "algorithm": "XOR"
    }
}
"""

show_hash_ecmp_and_lag="""\
+--------+-------------------------------------+
| Hash   | Configuration                       |
+========+=====================================+
| ECMP   | +-------------------+-------------+ |
|        | | Hash Field        | Algorithm   | |
|        | |-------------------+-------------| |
|        | | DST_MAC           | CRC         | |
|        | | SRC_MAC           |             | |
|        | | ETHERTYPE         |             | |
|        | | IP_PROTOCOL       |             | |
|        | | DST_IP            |             | |
|        | | SRC_IP            |             | |
|        | | L4_DST_PORT       |             | |
|        | | L4_SRC_PORT       |             | |
|        | | INNER_DST_MAC     |             | |
|        | | INNER_SRC_MAC     |             | |
|        | | INNER_ETHERTYPE   |             | |
|        | | INNER_IP_PROTOCOL |             | |
|        | | INNER_DST_IP      |             | |
|        | | INNER_SRC_IP      |             | |
|        | | INNER_L4_DST_PORT |             | |
|        | | INNER_L4_SRC_PORT |             | |
|        | +-------------------+-------------+ |
+--------+-------------------------------------+
| LAG    | +-------------------+-------------+ |
|        | | Hash Field        | Algorithm   | |
|        | |-------------------+-------------| |
|        | | DST_MAC           | XOR         | |
|        | | SRC_MAC           |             | |
|        | | ETHERTYPE         |             | |
|        | | IP_PROTOCOL       |             | |
|        | | DST_IP            |             | |
|        | | SRC_IP            |             | |
|        | | L4_DST_PORT       |             | |
|        | | L4_SRC_PORT       |             | |
|        | | INNER_DST_MAC     |             | |
|        | | INNER_SRC_MAC     |             | |
|        | | INNER_ETHERTYPE   |             | |
|        | | INNER_IP_PROTOCOL |             | |
|        | | INNER_DST_IP      |             | |
|        | | INNER_SRC_IP      |             | |
|        | | INNER_L4_DST_PORT |             | |
|        | | INNER_L4_SRC_PORT |             | |
|        | +-------------------+-------------+ |
+--------+-------------------------------------+
"""
show_hash_ecmp_and_lag_json="""\
{
    "ecmp": {
        "hash_field": [
            "DST_MAC",
            "SRC_MAC",
            "ETHERTYPE",
            "IP_PROTOCOL",
            "DST_IP",
            "SRC_IP",
            "L4_DST_PORT",
            "L4_SRC_PORT",
            "INNER_DST_MAC",
            "INNER_SRC_MAC",
            "INNER_ETHERTYPE",
            "INNER_IP_PROTOCOL",
            "INNER_DST_IP",
            "INNER_SRC_IP",
            "INNER_L4_DST_PORT",
            "INNER_L4_SRC_PORT"
        ],
        "algorithm": "CRC"
    },
    "lag": {
        "hash_field": [
            "DST_MAC",
            "SRC_MAC",
            "ETHERTYPE",
            "IP_PROTOCOL",
            "DST_IP",
            "SRC_IP",
            "L4_DST_PORT",
            "L4_SRC_PORT",
            "INNER_DST_MAC",
            "INNER_SRC_MAC",
            "INNER_ETHERTYPE",
            "INNER_IP_PROTOCOL",
            "INNER_DST_IP",
            "INNER_SRC_IP",
            "INNER_L4_DST_PORT",
            "INNER_L4_SRC_PORT"
        ],
        "algorithm": "XOR"
    }
}
"""

show_hash_capabilities_no="""\
+--------+---------------------------------------+
| Hash   | Capabilities                          |
+========+=======================================+
| ECMP   | +-----------------+-----------------+ |
|        | | Hash Field      | Algorithm       | |
|        | |-----------------+-----------------| |
|        | | no capabilities | no capabilities | |
|        | +-----------------+-----------------+ |
+--------+---------------------------------------+
| LAG    | +-----------------+-----------------+ |
|        | | Hash Field      | Algorithm       | |
|        | |-----------------+-----------------| |
|        | | no capabilities | no capabilities | |
|        | +-----------------+-----------------+ |
+--------+---------------------------------------+
"""
show_hash_capabilities_no_json="""\
{
    "ecmp": {
        "hash_field": "no capabilities",
        "algorithm": "no capabilities"
    },
    "lag": {
        "hash_field": "no capabilities",
        "algorithm": "no capabilities"
    }
}
"""

show_hash_capabilities_na="""\
+--------+--------------------------------+
| Hash   | Capabilities                   |
+========+================================+
| ECMP   | +--------------+-------------+ |
|        | | Hash Field   | Algorithm   | |
|        | |--------------+-------------| |
|        | | N/A          | N/A         | |
|        | +--------------+-------------+ |
+--------+--------------------------------+
| LAG    | +--------------+-------------+ |
|        | | Hash Field   | Algorithm   | |
|        | |--------------+-------------| |
|        | | N/A          | N/A         | |
|        | +--------------+-------------+ |
+--------+--------------------------------+
"""
show_hash_capabilities_na_json="""\
{
    "ecmp": {
        "hash_field": "N/A",
        "algorithm": "N/A"
    },
    "lag": {
        "hash_field": "N/A",
        "algorithm": "N/A"
    }
}
"""

show_hash_capabilities_empty="""\
+--------+-----------------------------------+
| Hash   | Capabilities                      |
+========+===================================+
| ECMP   | +---------------+---------------+ |
|        | | Hash Field    | Algorithm     | |
|        | |---------------+---------------| |
|        | | not supported | not supported | |
|        | +---------------+---------------+ |
+--------+-----------------------------------+
| LAG    | +---------------+---------------+ |
|        | | Hash Field    | Algorithm     | |
|        | |---------------+---------------| |
|        | | not supported | not supported | |
|        | +---------------+---------------+ |
+--------+-----------------------------------+
"""
show_hash_capabilities_empty_json="""\
{
    "ecmp": {
        "hash_field": "not supported",
        "algorithm": "not supported"
    },
    "lag": {
        "hash_field": "not supported",
        "algorithm": "not supported"
    }
}
"""

show_hash_capabilities_ecmp="""\
+--------+-------------------------------------+
| Hash   | Capabilities                        |
+========+=====================================+
| ECMP   | +-------------------+-------------+ |
|        | | Hash Field        | Algorithm   | |
|        | |-------------------+-------------| |
|        | | IN_PORT           | CRC         | |
|        | | DST_MAC           | XOR         | |
|        | | SRC_MAC           | RANDOM      | |
|        | | ETHERTYPE         | CRC_32LO    | |
|        | | VLAN_ID           | CRC_32HI    | |
|        | | IP_PROTOCOL       | CRC_CCITT   | |
|        | | DST_IP            | CRC_XOR     | |
|        | | SRC_IP            |             | |
|        | | L4_DST_PORT       |             | |
|        | | L4_SRC_PORT       |             | |
|        | | INNER_DST_MAC     |             | |
|        | | INNER_SRC_MAC     |             | |
|        | | INNER_ETHERTYPE   |             | |
|        | | INNER_IP_PROTOCOL |             | |
|        | | INNER_DST_IP      |             | |
|        | | INNER_SRC_IP      |             | |
|        | | INNER_L4_DST_PORT |             | |
|        | | INNER_L4_SRC_PORT |             | |
|        | +-------------------+-------------+ |
+--------+-------------------------------------+
| LAG    | +---------------+---------------+   |
|        | | Hash Field    | Algorithm     |   |
|        | |---------------+---------------|   |
|        | | not supported | not supported |   |
|        | +---------------+---------------+   |
+--------+-------------------------------------+
"""
show_hash_capabilities_ecmp_json="""\
{
    "ecmp": {
        "hash_field": [
            "IN_PORT",
            "DST_MAC",
            "SRC_MAC",
            "ETHERTYPE",
            "VLAN_ID",
            "IP_PROTOCOL",
            "DST_IP",
            "SRC_IP",
            "L4_DST_PORT",
            "L4_SRC_PORT",
            "INNER_DST_MAC",
            "INNER_SRC_MAC",
            "INNER_ETHERTYPE",
            "INNER_IP_PROTOCOL",
            "INNER_DST_IP",
            "INNER_SRC_IP",
            "INNER_L4_DST_PORT",
            "INNER_L4_SRC_PORT"
        ],
        "algorithm": [
            "CRC",
            "XOR",
            "RANDOM",
            "CRC_32LO",
            "CRC_32HI",
            "CRC_CCITT",
            "CRC_XOR"
        ]
    },
    "lag": {
        "hash_field": "not supported",
        "algorithm": "not supported"
    }
}
"""

show_hash_capabilities_lag="""\
+--------+-------------------------------------+
| Hash   | Capabilities                        |
+========+=====================================+
| ECMP   | +---------------+---------------+   |
|        | | Hash Field    | Algorithm     |   |
|        | |---------------+---------------|   |
|        | | not supported | not supported |   |
|        | +---------------+---------------+   |
+--------+-------------------------------------+
| LAG    | +-------------------+-------------+ |
|        | | Hash Field        | Algorithm   | |
|        | |-------------------+-------------| |
|        | | IN_PORT           | CRC         | |
|        | | DST_MAC           | XOR         | |
|        | | SRC_MAC           | RANDOM      | |
|        | | ETHERTYPE         | CRC_32LO    | |
|        | | VLAN_ID           | CRC_32HI    | |
|        | | IP_PROTOCOL       | CRC_CCITT   | |
|        | | DST_IP            | CRC_XOR     | |
|        | | SRC_IP            |             | |
|        | | L4_DST_PORT       |             | |
|        | | L4_SRC_PORT       |             | |
|        | | INNER_DST_MAC     |             | |
|        | | INNER_SRC_MAC     |             | |
|        | | INNER_ETHERTYPE   |             | |
|        | | INNER_IP_PROTOCOL |             | |
|        | | INNER_DST_IP      |             | |
|        | | INNER_SRC_IP      |             | |
|        | | INNER_L4_DST_PORT |             | |
|        | | INNER_L4_SRC_PORT |             | |
|        | +-------------------+-------------+ |
+--------+-------------------------------------+
"""
show_hash_capabilities_lag_json="""\
{
    "ecmp": {
        "hash_field": "not supported",
        "algorithm": "not supported"
    },
    "lag": {
        "hash_field": [
            "IN_PORT",
            "DST_MAC",
            "SRC_MAC",
            "ETHERTYPE",
            "VLAN_ID",
            "IP_PROTOCOL",
            "DST_IP",
            "SRC_IP",
            "L4_DST_PORT",
            "L4_SRC_PORT",
            "INNER_DST_MAC",
            "INNER_SRC_MAC",
            "INNER_ETHERTYPE",
            "INNER_IP_PROTOCOL",
            "INNER_DST_IP",
            "INNER_SRC_IP",
            "INNER_L4_DST_PORT",
            "INNER_L4_SRC_PORT"
        ],
        "algorithm": [
            "CRC",
            "XOR",
            "RANDOM",
            "CRC_32LO",
            "CRC_32HI",
            "CRC_CCITT",
            "CRC_XOR"
        ]
    }
}
"""

show_hash_capabilities_ecmp_and_lag="""\
+--------+-------------------------------------+
| Hash   | Capabilities                        |
+========+=====================================+
| ECMP   | +-------------------+-------------+ |
|        | | Hash Field        | Algorithm   | |
|        | |-------------------+-------------| |
|        | | IN_PORT           | CRC         | |
|        | | DST_MAC           | XOR         | |
|        | | SRC_MAC           | RANDOM      | |
|        | | ETHERTYPE         | CRC_32LO    | |
|        | | VLAN_ID           | CRC_32HI    | |
|        | | IP_PROTOCOL       | CRC_CCITT   | |
|        | | DST_IP            | CRC_XOR     | |
|        | | SRC_IP            |             | |
|        | | L4_DST_PORT       |             | |
|        | | L4_SRC_PORT       |             | |
|        | | INNER_DST_MAC     |             | |
|        | | INNER_SRC_MAC     |             | |
|        | | INNER_ETHERTYPE   |             | |
|        | | INNER_IP_PROTOCOL |             | |
|        | | INNER_DST_IP      |             | |
|        | | INNER_SRC_IP      |             | |
|        | | INNER_L4_DST_PORT |             | |
|        | | INNER_L4_SRC_PORT |             | |
|        | +-------------------+-------------+ |
+--------+-------------------------------------+
| LAG    | +-------------------+-------------+ |
|        | | Hash Field        | Algorithm   | |
|        | |-------------------+-------------| |
|        | | IN_PORT           | CRC         | |
|        | | DST_MAC           | XOR         | |
|        | | SRC_MAC           | RANDOM      | |
|        | | ETHERTYPE         | CRC_32LO    | |
|        | | VLAN_ID           | CRC_32HI    | |
|        | | IP_PROTOCOL       | CRC_CCITT   | |
|        | | DST_IP            | CRC_XOR     | |
|        | | SRC_IP            |             | |
|        | | L4_DST_PORT       |             | |
|        | | L4_SRC_PORT       |             | |
|        | | INNER_DST_MAC     |             | |
|        | | INNER_SRC_MAC     |             | |
|        | | INNER_ETHERTYPE   |             | |
|        | | INNER_IP_PROTOCOL |             | |
|        | | INNER_DST_IP      |             | |
|        | | INNER_SRC_IP      |             | |
|        | | INNER_L4_DST_PORT |             | |
|        | | INNER_L4_SRC_PORT |             | |
|        | +-------------------+-------------+ |
+--------+-------------------------------------+
"""
show_hash_capabilities_ecmp_and_lag_json="""\
{
    "ecmp": {
        "hash_field": [
            "IN_PORT",
            "DST_MAC",
            "SRC_MAC",
            "ETHERTYPE",
            "VLAN_ID",
            "IP_PROTOCOL",
            "DST_IP",
            "SRC_IP",
            "L4_DST_PORT",
            "L4_SRC_PORT",
            "INNER_DST_MAC",
            "INNER_SRC_MAC",
            "INNER_ETHERTYPE",
            "INNER_IP_PROTOCOL",
            "INNER_DST_IP",
            "INNER_SRC_IP",
            "INNER_L4_DST_PORT",
            "INNER_L4_SRC_PORT"
        ],
        "algorithm": [
            "CRC",
            "XOR",
            "RANDOM",
            "CRC_32LO",
            "CRC_32HI",
            "CRC_CCITT",
            "CRC_XOR"
        ]
    },
    "lag": {
        "hash_field": [
            "IN_PORT",
            "DST_MAC",
            "SRC_MAC",
            "ETHERTYPE",
            "VLAN_ID",
            "IP_PROTOCOL",
            "DST_IP",
            "SRC_IP",
            "L4_DST_PORT",
            "L4_SRC_PORT",
            "INNER_DST_MAC",
            "INNER_SRC_MAC",
            "INNER_ETHERTYPE",
            "INNER_IP_PROTOCOL",
            "INNER_DST_IP",
            "INNER_SRC_IP",
            "INNER_L4_DST_PORT",
            "INNER_L4_SRC_PORT"
        ],
        "algorithm": [
            "CRC",
            "XOR",
            "RANDOM",
            "CRC_32LO",
            "CRC_32HI",
            "CRC_CCITT",
            "CRC_XOR"
        ]
    }
}
"""

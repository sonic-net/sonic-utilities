"""
Module holding the correct values for show CLI command outputs for the bgp_test.py
"""

show_device_global_empty = """\
No configuration is present in CONFIG DB
"""

show_device_global_all_disabled = """\
TSA       W-ECMP
--------  --------
disabled  disabled
"""
show_device_global_all_disabled_json = """\
{
    "tsa": "disabled",
    "w-ecmp": "disabled"
}
"""

show_device_global_all_enabled = """\
TSA      W-ECMP
-------  --------
enabled  enabled
"""
show_device_global_all_enabled_json = """\
{
    "tsa": "enabled",
    "w-ecmp": "enabled"
}
"""

show_device_global_tsa_enabled = """\
TSA      W-ECMP
-------  --------
enabled  disabled
"""
show_device_global_tsa_enabled_json = """\
{
    "tsa": "enabled",
    "w-ecmp": "disabled"
}
"""

show_device_global_wcmp_enabled = """\
TSA       W-ECMP
--------  --------
disabled  enabled
"""
show_device_global_wcmp_enabled_json = """\
{
    "tsa": "disabled",
    "w-ecmp": "enabled"
}
"""

show_aggregate_address_ipv4 = """\
Flags: A - As Set, B - BBR Required, S - Summary Only

Prefix          State    Option Flags    Aggregate Address Prefix List    Contributing Address Prefix List
--------------  -------  --------------  -------------------------------  ----------------------------------
10.0.0.0/24     N/A      A,B,S
192.168.0.0/24  N/A      B               AGG_ROUTES_V4                    AGG_CONTRIBUTING_ROUTES_V4
"""

show_aggregate_address_ipv6 = """\
Flags: A - As Set, B - BBR Required, S - Summary Only

Prefix       State    Option Flags    Aggregate Address Prefix List    Contributing Address Prefix List
-----------  -------  --------------  -------------------------------  ----------------------------------
fc00:1::/64  N/A      A               AGG_ROUTES_V6                    AGG_CONTRIBUTING_ROUTES_V6
fc00:3::/64  N/A      B,S
"""

show_aggregate_address_empty = """\
Flags: A - As Set, B - BBR Required, S - Summary Only

Prefix    State    Option Flags    Aggregate Address Prefix List    Contributing Address Prefix List
--------  -------  --------------  -------------------------------  ----------------------------------
"""

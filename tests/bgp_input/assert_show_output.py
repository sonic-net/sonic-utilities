"""
Module holding the correct values for show CLI command outputs for the bgp_test.py
"""

show_device_global_empty = """\
No configuration is present in CONFIG DB
"""

show_device_global_all_disabled = """\
TSA       ORIGINATE-BANDWIDTH    RECEIVED-BANDWIDTH
--------  ---------------------  --------------------
disabled  disabled               ignore
"""
show_device_global_all_disabled_json = """\
{
    "tsa": "disabled",
    "originate-bandwidth": "disabled",
    "received-bandwidth": "ignore"
}
"""

show_device_global_all_enabled = """\
TSA      ORIGINATE-BANDWIDTH    RECEIVED-BANDWIDTH
-------  ---------------------  --------------------
enabled  5 Mbps                 allow
"""
show_device_global_all_enabled_json = """\
{
    "tsa": "enabled",
    "originate-bandwidth": "5 Mbps",
    "received-bandwidth": "allow"
}
"""

show_device_global_tsa_enabled = """\
TSA      ORIGINATE-BANDWIDTH    RECEIVED-BANDWIDTH
-------  ---------------------  --------------------
enabled  cumulative             skip_missing
"""
show_device_global_tsa_enabled_json = """\
{
    "tsa": "enabled",
    "originate-bandwidth": "cumulative",
    "received-bandwidth": "skip_missing"
}
"""

show_device_global_diff_originate_received = """\
TSA       ORIGINATE-BANDWIDTH    RECEIVED-BANDWIDTH
--------  ---------------------  --------------------------
disabled  num_multipaths         default_weight_for_missing
"""
show_device_global_diff_originate_received_json = """\
{
    "tsa": "disabled",
    "originate-bandwidth": "num_multipaths",
    "received-bandwidth": "default_weight_for_missing"
}
"""

show_device_global_all_disabled_multi_asic = """\
ASIC ID    TSA       ORIGINATE-BANDWIDTH    RECEIVED-BANDWIDTH
---------  --------  ---------------------  --------------------
asic0      disabled  disabled               ignore
asic1      disabled  disabled               ignore
"""
show_device_global_all_disabled_multi_asic_json = """\
{
    "asic0": {
        "tsa": "disabled",
        "originate-bandwidth": "disabled",
        "received-bandwidth": "ignore"
    },
    "asic1": {
        "tsa": "disabled",
        "originate-bandwidth": "disabled",
        "received-bandwidth": "ignore"
    }
}
"""

show_device_global_all_enabled_multi_asic = """\
ASIC ID    TSA      ORIGINATE-BANDWIDTH    RECEIVED-BANDWIDTH
---------  -------  ---------------------  --------------------
asic0      enabled  5 Mbps                 allow
asic1      enabled  5 Mbps                 allow
"""
show_device_global_all_enabled_multi_asic_json = """\
{
    "asic0": {
        "tsa": "enabled",
        "originate-bandwidth": "5 Mbps",
        "received-bandwidth": "allow"
    },
    "asic1": {
        "tsa": "enabled",
        "originate-bandwidth": "5 Mbps",
        "received-bandwidth": "allow"
    }
}
"""

show_device_global_tsa_enabled_multi_asic = """\
ASIC ID    TSA      ORIGINATE-BANDWIDTH    RECEIVED-BANDWIDTH
---------  -------  ---------------------  --------------------
asic0      enabled  cumulative             skip_missing
asic1      enabled  cumulative             skip_missing
"""
show_device_global_tsa_enabled_multi_asic_json = """\
{
    "asic0": {
        "tsa": "enabled",
        "originate-bandwidth": "cumulative",
        "received-bandwidth": "skip_missing"
    },
    "asic1": {
        "tsa": "enabled",
        "originate-bandwidth": "cumulative",
        "received-bandwidth": "skip_missing"
    }
}
"""

show_device_global_diff_originate_received_multi_asic = """\
ASIC ID    TSA       ORIGINATE-BANDWIDTH    RECEIVED-BANDWIDTH
---------  --------  ---------------------  --------------------------
asic0      disabled  num_multipaths         default_weight_for_missing
asic1      disabled  num_multipaths         default_weight_for_missing
"""
show_device_global_diff_originate_received_multi_asic_json = """\
{
    "asic0": {
        "tsa": "disabled",
        "originate-bandwidth": "num_multipaths",
        "received-bandwidth": "default_weight_for_missing"
    },
    "asic1": {
        "tsa": "disabled",
        "originate-bandwidth": "num_multipaths",
        "received-bandwidth": "default_weight_for_missing"
    }
}
"""

show_device_global_opposite_multi_asic = """\
ASIC ID    TSA       ORIGINATE-BANDWIDTH    RECEIVED-BANDWIDTH
---------  --------  ---------------------  --------------------------
asic0      enabled   cumulative             skip_missing
asic1      disabled  num_multipaths         default_weight_for_missing
"""
show_device_global_opposie_multi_asic_json = """\
{
    "asic0": {
        "tsa": "enabled",
        "originate-bandwidth": "cumulative",
        "received-bandwidth": "skip_missing"
    },
    "asic1": {
        "tsa": "disabled",
        "originate-bandwidth": "num_multipaths",
        "received-bandwidth": "default_weight_for_missing"
    }
}
"""

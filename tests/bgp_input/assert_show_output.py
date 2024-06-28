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

show_device_global_all_disabled_multi_asic = """\
ASIC ID    TSA       W-ECMP
---------  --------  --------
asic0      disabled  disabled
asic1      disabled  disabled
"""
show_device_global_all_disabled_multi_asic_json = """\
{
    "asic0": {
        "tsa": "disabled",
        "w-ecmp": "disabled"
    },
    "asic1": {
        "tsa": "disabled",
        "w-ecmp": "disabled"
    }
}
"""

show_device_global_all_enabled_multi_asic = """\
ASIC ID    TSA      W-ECMP
---------  -------  --------
asic0      enabled  enabled
asic1      enabled  enabled
"""
show_device_global_all_enabled_multi_asic_json = """\
{
    "asic0": {
        "tsa": "enabled",
        "w-ecmp": "enabled"
    },
    "asic1": {
        "tsa": "enabled",
        "w-ecmp": "enabled"
    }
}
"""

show_device_global_tsa_enabled_multi_asic = """\
ASIC ID    TSA      W-ECMP
---------  -------  --------
asic0      enabled  disabled
asic1      enabled  disabled
"""
show_device_global_tsa_enabled_multi_asic_json = """\
{
    "asic0": {
        "tsa": "enabled",
        "w-ecmp": "disabled"
    },
    "asic1": {
        "tsa": "enabled",
        "w-ecmp": "disabled"
    }
}
"""

show_device_global_wcmp_enabled_multi_asic = """\
ASIC ID    TSA       W-ECMP
---------  --------  --------
asic0      disabled  enabled
asic1      disabled  enabled
"""
show_device_global_wcmp_enabled_multi_asic_json = """\
{
    "asic0": {
        "tsa": "disabled",
        "w-ecmp": "enabled"
    },
    "asic1": {
        "tsa": "disabled",
        "w-ecmp": "enabled"
    }
}
"""

show_device_global_opposite_multi_asic = """\
ASIC ID    TSA       W-ECMP
---------  --------  --------
asic0      enabled   disabled
asic1      disabled  enabled
"""
show_device_global_opposie_multi_asic_json = """\
{
    "asic0": {
        "tsa": "enabled",
        "w-ecmp": "disabled"
    },
    "asic1": {
        "tsa": "disabled",
        "w-ecmp": "enabled"
    }
}
"""

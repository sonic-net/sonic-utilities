"""
Module holding the correct values for show CLI command outputs for the trimming_test.py
"""

show_trim_empty = """\
No configuration is present in CONFIG DB
"""

show_trim_partial = """\
+-----------------------------+---------+
| Configuration               | Value   |
+=============================+=========+
| Packet trimming size        | 200     |
+-----------------------------+---------+
| Packet trimming DSCP value  | 20      |
+-----------------------------+---------+
| Packet trimming TC value    | N/A     |
+-----------------------------+---------+
| Packet trimming queue index | N/A     |
+-----------------------------+---------+
"""
show_trim_partial_json = """\
{
    "size": "200",
    "dscp_value": "20",
    "tc_value": "N/A",
    "queue_index": "N/A"
}
"""

show_trim_dscp_asymmetric = """\
+-----------------------------+---------+
| Configuration               | Value   |
+=============================+=========+
| Packet trimming size        | 200     |
+-----------------------------+---------+
| Packet trimming DSCP value  | from-tc |
+-----------------------------+---------+
| Packet trimming TC value    | 2       |
+-----------------------------+---------+
| Packet trimming queue index | 2       |
+-----------------------------+---------+
"""
show_trim_dscp_asymmetric_json = """\
{
    "size": "200",
    "dscp_value": "from-tc",
    "tc_value": "2",
    "queue_index": "2"
}
"""

show_trim_queue_dynamic = """\
+-----------------------------+---------+
| Configuration               | Value   |
+=============================+=========+
| Packet trimming size        | 200     |
+-----------------------------+---------+
| Packet trimming DSCP value  | 20      |
+-----------------------------+---------+
| Packet trimming TC value    | N/A     |
+-----------------------------+---------+
| Packet trimming queue index | dynamic |
+-----------------------------+---------+
"""
show_trim_queue_dynamic_json = """\
{
    "size": "200",
    "dscp_value": "20",
    "tc_value": "N/A",
    "queue_index": "dynamic"
}
"""

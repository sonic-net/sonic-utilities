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
| Packet trimming queue index | N/A     |
+-----------------------------+---------+
"""
show_trim_partial_json = """\
{
    "size": "200",
    "dscp_value": "20",
    "queue_index": "N/A"
}
"""

show_trim_queue_static = """\
+-----------------------------+---------+
| Configuration               |   Value |
+=============================+=========+
| Packet trimming size        |     200 |
+-----------------------------+---------+
| Packet trimming DSCP value  |      20 |
+-----------------------------+---------+
| Packet trimming queue index |       2 |
+-----------------------------+---------+
"""
show_trim_queue_static_json = """\
{
    "size": "200",
    "dscp_value": "20",
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
| Packet trimming queue index | dynamic |
+-----------------------------+---------+
"""
show_trim_queue_dynamic_json = """\
{
    "size": "200",
    "dscp_value": "20",
    "queue_index": "dynamic"
}
"""

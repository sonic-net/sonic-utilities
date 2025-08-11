"""
Module holding the correct values for show CLI command outputs for the switchstat_test.py
"""

# show section ------------------------------------------------------------------------------------------------------ #

show_switch_all = """\
  TrimSent/pkts    TrimDrop/pkts
---------------  ---------------
          2,000            1,000
"""
show_switch_all_json = """\
{
    "trim_drop": "1,000",
    "trim_sent": "2,000"
}
"""

show_switch_detailed = """\
Trimmed Sent Packets........................... 2,000
Trimmed Dropped Packets........................ 1,000
"""

# diff section -------------------------------------------------------------------------------------------------------#

show_switch_updated = """\
  TrimSent/pkts    TrimDrop/pkts
---------------  ---------------
            500              500
"""
show_switch_updated_json = """\
{
    "trim_drop": "500",
    "trim_sent": "500"
}
"""

show_switch_updated_detailed = """\
Trimmed Sent Packets........................... 500
Trimmed Dropped Packets........................ 500
"""

# negative section ---------------------------------------------------------------------------------------------------#

show_switch_neg_na = """\
  TrimSent/pkts    TrimDrop/pkts
---------------  ---------------
            N/A              N/A
"""
show_switch_neg_na_json = """\
{
    "trim_drop": "N/A",
    "trim_sent": "N/A"
}
"""

show_switch_neg_partial = """\
  TrimSent/pkts    TrimDrop/pkts
---------------  ---------------
            N/A            1,000
"""
show_switch_neg_partial_json = """\
{
    "trim_drop": "1,000",
    "trim_sent": "N/A"
}
"""

# period section ---------------------------------------------------------------------------------------------------- #

show_switch_period = """\
The switch stats are calculated within 1 seconds period
Trimmed Sent Packets........................... 0
Trimmed Dropped Packets........................ 0
"""

# clear section ----------------------------------------------------------------------------------------------------- #

show_switch_updated_tag = """\
  TrimSent/pkts    TrimDrop/pkts
---------------  ---------------
          1,000            1,000
"""

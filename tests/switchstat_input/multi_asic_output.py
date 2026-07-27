"""
Module holding the correct values for show CLI command outputs for the switchstat_test.py
"""

# show section ------------------------------------------------------------------------------------------------------ #

show_switch_all = """\
Namespace: asic0

  TrimSent/pkts    TrimDrop/pkts
---------------  ---------------
          2,000            1,000

Namespace: asic1

  TrimSent/pkts    TrimDrop/pkts
---------------  ---------------
          2,000            1,000

Namespace: asic2

  TrimSent/pkts    TrimDrop/pkts
---------------  ---------------
          2,000            1,000
"""
show_switch_all_json = """\
{
    "asic0": {
        "trim_drop": "1,000",
        "trim_sent": "2,000"
    },
    "asic1": {
        "trim_drop": "1,000",
        "trim_sent": "2,000"
    },
    "asic2": {
        "trim_drop": "1,000",
        "trim_sent": "2,000"
    }
}
"""

show_switch_detailed = """\
Namespace: asic0

Trimmed Sent Packets........................... 2,000
Trimmed Dropped Packets........................ 1,000

Namespace: asic1

Trimmed Sent Packets........................... 2,000
Trimmed Dropped Packets........................ 1,000

Namespace: asic2

Trimmed Sent Packets........................... 2,000
Trimmed Dropped Packets........................ 1,000
"""

# diff section -------------------------------------------------------------------------------------------------------#

show_switch_updated = """\
Namespace: asic0

  TrimSent/pkts    TrimDrop/pkts
---------------  ---------------
            500              500

Namespace: asic1

  TrimSent/pkts    TrimDrop/pkts
---------------  ---------------
            500              500

Namespace: asic2

  TrimSent/pkts    TrimDrop/pkts
---------------  ---------------
            500              500
"""
show_switch_updated_json = """\
{
    "asic0": {
        "trim_drop": "500",
        "trim_sent": "500"
    },
    "asic1": {
        "trim_drop": "500",
        "trim_sent": "500"
    },
    "asic2": {
        "trim_drop": "500",
        "trim_sent": "500"
    }
}
"""

show_switch_updated_detailed = """\
Namespace: asic0

Trimmed Sent Packets........................... 500
Trimmed Dropped Packets........................ 500


Namespace: asic1

Trimmed Sent Packets........................... 500
Trimmed Dropped Packets........................ 500


Namespace: asic2

Trimmed Sent Packets........................... 500
Trimmed Dropped Packets........................ 500
"""

# negative section ---------------------------------------------------------------------------------------------------#

show_switch_neg_na = """\
Namespace: asic0

  TrimSent/pkts    TrimDrop/pkts
---------------  ---------------
            N/A              N/A

Namespace: asic1

  TrimSent/pkts    TrimDrop/pkts
---------------  ---------------
            N/A              N/A

Namespace: asic2

  TrimSent/pkts    TrimDrop/pkts
---------------  ---------------
            N/A              N/A
"""
show_switch_neg_na_json = """\
{
    "asic0": {
        "trim_drop": "N/A",
        "trim_sent": "N/A"
    },
    "asic1": {
        "trim_drop": "N/A",
        "trim_sent": "N/A"
    },
    "asic2": {
        "trim_drop": "N/A",
        "trim_sent": "N/A"
    }
}
"""

show_switch_neg_partial = """\
Namespace: asic0

  TrimSent/pkts    TrimDrop/pkts
---------------  ---------------
            N/A            1,000

Namespace: asic1

  TrimSent/pkts    TrimDrop/pkts
---------------  ---------------
            N/A            1,000

Namespace: asic2

  TrimSent/pkts    TrimDrop/pkts
---------------  ---------------
            N/A            1,000
"""
show_switch_neg_partial_json = """\
{
    "asic0": {
        "trim_drop": "1,000",
        "trim_sent": "N/A"
    },
    "asic1": {
        "trim_drop": "1,000",
        "trim_sent": "N/A"
    },
    "asic2": {
        "trim_drop": "1,000",
        "trim_sent": "N/A"
    }
}
"""

# period section ---------------------------------------------------------------------------------------------------- #

show_switch_period = """\
The switch stats are calculated within 1 seconds period
Namespace: asic0

Trimmed Sent Packets........................... 0
Trimmed Dropped Packets........................ 0


Namespace: asic1

Trimmed Sent Packets........................... 0
Trimmed Dropped Packets........................ 0


Namespace: asic2

Trimmed Sent Packets........................... 0
Trimmed Dropped Packets........................ 0
"""

# clear section ----------------------------------------------------------------------------------------------------- #

show_switch_updated_tag = """\
Namespace: asic0

  TrimSent/pkts    TrimDrop/pkts
---------------  ---------------
          1,000            1,000

Namespace: asic1

  TrimSent/pkts    TrimDrop/pkts
---------------  ---------------
          1,000            1,000

Namespace: asic2

  TrimSent/pkts    TrimDrop/pkts
---------------  ---------------
          1,000            1,000
"""

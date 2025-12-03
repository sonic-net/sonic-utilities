import json
import os
import sys

from click.testing import CliRunner

import clear.main as clear
import show.main as show
from utilities_common.cli import json_dump
from utilities_common.cli import UserCache

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

show_wred_queue_counters = """\
     Port    TxQ    WredDrp/pkts    WredDrp/bytes    EcnMarked/pkts    EcnMarked/bytes
---------  -----  --------------  ---------------  ----------------  -----------------
Ethernet0    UC0               0                0                 0                  0
Ethernet0    UC1              60               43                39                  1
Ethernet0    UC2              82                7                39                 21
Ethernet0    UC3              52               70                19                 76
Ethernet0    UC4              11               59                12                 94
Ethernet0    UC5              36               62                35                 40
Ethernet0    UC6              49               91                 2                 88
Ethernet0    UC7              33               17                94                 74
Ethernet0    UC8              40               71                95                 33
Ethernet0    UC9              54                8                93                 78
Ethernet0   MC10              83               96                74                  9
Ethernet0   MC11              15               60                61                 31
Ethernet0   MC12              45               52                82                 94
Ethernet0   MC13              55               88                89                 52
Ethernet0   MC14              14               70                95                 79
Ethernet0   MC15              68               60                66                 81
Ethernet0   MC16              63                4                48                 76
Ethernet0   MC17              41               73                77                 74
Ethernet0   MC18              60               21                56                 54
Ethernet0   MC19              57               31                12                 39
Ethernet0  ALL20             N/A              N/A               N/A                N/A
Ethernet0  ALL21             N/A              N/A               N/A                N/A
Ethernet0  ALL22             N/A              N/A               N/A                N/A
Ethernet0  ALL23             N/A              N/A               N/A                N/A
Ethernet0  ALL24             N/A              N/A               N/A                N/A
Ethernet0  ALL25             N/A              N/A               N/A                N/A
Ethernet0  ALL26             N/A              N/A               N/A                N/A
Ethernet0  ALL27             N/A              N/A               N/A                N/A
Ethernet0  ALL28             N/A              N/A               N/A                N/A
Ethernet0  ALL29             N/A              N/A               N/A                N/A

     Port    TxQ    WredDrp/pkts    WredDrp/bytes    EcnMarked/pkts    EcnMarked/bytes
---------  -----  --------------  ---------------  ----------------  -----------------
Ethernet4    UC0              41               96                70                 98
Ethernet4    UC1              18               49                63                 36
Ethernet4    UC2              99               90                 3                 15
Ethernet4    UC3              60               89                48                 41
Ethernet4    UC4               8               84                82                 94
Ethernet4    UC5              83               15                75                 92
Ethernet4    UC6              84               26                50                 71
Ethernet4    UC7              27               19                49                 80
Ethernet4    UC8              13               89                13                 33
Ethernet4    UC9              43               48                86                 31
Ethernet4   MC10              50                1                57                 82
Ethernet4   MC11              67               99                84                 59
Ethernet4   MC12               4               58                27                  5
Ethernet4   MC13              74                5                57                 39
Ethernet4   MC14              21               59                 4                 14
Ethernet4   MC15              24               61                19                 53
Ethernet4   MC16              51               15                15                 32
Ethernet4   MC17              98               18                23                 15
Ethernet4   MC18              41               34                 9                 57
Ethernet4   MC19              57                7                18                 99
Ethernet4  ALL20             N/A              N/A               N/A                N/A
Ethernet4  ALL21             N/A              N/A               N/A                N/A
Ethernet4  ALL22             N/A              N/A               N/A                N/A
Ethernet4  ALL23             N/A              N/A               N/A                N/A
Ethernet4  ALL24             N/A              N/A               N/A                N/A
Ethernet4  ALL25             N/A              N/A               N/A                N/A
Ethernet4  ALL26             N/A              N/A               N/A                N/A
Ethernet4  ALL27             N/A              N/A               N/A                N/A
Ethernet4  ALL28             N/A              N/A               N/A                N/A
Ethernet4  ALL29             N/A              N/A               N/A                N/A

     Port    TxQ    WredDrp/pkts    WredDrp/bytes    EcnMarked/pkts    EcnMarked/bytes
---------  -----  --------------  ---------------  ----------------  -----------------
Ethernet8    UC0               0                0                 0                  0
Ethernet8    UC1              38               17                68                 91
Ethernet8    UC2              16               65                79                 51
Ethernet8    UC3              11               97                63                 72
Ethernet8    UC4              54               89                62                 62
Ethernet8    UC5              13               84                30                 59
Ethernet8    UC6              49               67                99                 85
Ethernet8    UC7               2               63                38                 88
Ethernet8    UC8               0               82                93                 43
Ethernet8    UC9              80               17                91                 61
Ethernet8   MC10              81               63                76                 73
Ethernet8   MC11              29               16                29                 66
Ethernet8   MC12              32               12                61                 35
Ethernet8   MC13              79               17                72                 93
Ethernet8   MC14              23               21                67                 50
Ethernet8   MC15              37               10                97                 14
Ethernet8   MC16              30               17                74                 43
Ethernet8   MC17               0               63                54                 84
Ethernet8   MC18              69               88                24                 79
Ethernet8   MC19              20               12                84                  3
Ethernet8  ALL20             N/A              N/A               N/A                N/A
Ethernet8  ALL21             N/A              N/A               N/A                N/A
Ethernet8  ALL22             N/A              N/A               N/A                N/A
Ethernet8  ALL23             N/A              N/A               N/A                N/A
Ethernet8  ALL24             N/A              N/A               N/A                N/A
Ethernet8  ALL25             N/A              N/A               N/A                N/A
Ethernet8  ALL26             N/A              N/A               N/A                N/A
Ethernet8  ALL27             N/A              N/A               N/A                N/A
Ethernet8  ALL28             N/A              N/A               N/A                N/A
Ethernet8  ALL29             N/A              N/A               N/A                N/A

"""


show_wred_queue_counters_port = """\
     Port    TxQ    WredDrp/pkts    WredDrp/bytes    EcnMarked/pkts    EcnMarked/bytes
---------  -----  --------------  ---------------  ----------------  -----------------
Ethernet8    UC0               0                0                 0                  0
Ethernet8    UC1              38               17                68                 91
Ethernet8    UC2              16               65                79                 51
Ethernet8    UC3              11               97                63                 72
Ethernet8    UC4              54               89                62                 62
Ethernet8    UC5              13               84                30                 59
Ethernet8    UC6              49               67                99                 85
Ethernet8    UC7               2               63                38                 88
Ethernet8    UC8               0               82                93                 43
Ethernet8    UC9              80               17                91                 61
Ethernet8   MC10              81               63                76                 73
Ethernet8   MC11              29               16                29                 66
Ethernet8   MC12              32               12                61                 35
Ethernet8   MC13              79               17                72                 93
Ethernet8   MC14              23               21                67                 50
Ethernet8   MC15              37               10                97                 14
Ethernet8   MC16              30               17                74                 43
Ethernet8   MC17               0               63                54                 84
Ethernet8   MC18              69               88                24                 79
Ethernet8   MC19              20               12                84                  3
Ethernet8  ALL20             N/A              N/A               N/A                N/A
Ethernet8  ALL21             N/A              N/A               N/A                N/A
Ethernet8  ALL22             N/A              N/A               N/A                N/A
Ethernet8  ALL23             N/A              N/A               N/A                N/A
Ethernet8  ALL24             N/A              N/A               N/A                N/A
Ethernet8  ALL25             N/A              N/A               N/A                N/A
Ethernet8  ALL26             N/A              N/A               N/A                N/A
Ethernet8  ALL27             N/A              N/A               N/A                N/A
Ethernet8  ALL28             N/A              N/A               N/A                N/A
Ethernet8  ALL29             N/A              N/A               N/A                N/A

"""

show_queue_counters_json = """\
{
  "Ethernet0": {
    "ALL20": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL21": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL22": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL23": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL24": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL25": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL26": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL27": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL28": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL29": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "MC10": {
      "ecnmarkedbytes": "9",
      "ecnmarkedpacket": "74",
      "wreddropbytes": "96",
      "wreddroppacket": "83"
    },
    "MC11": {
      "ecnmarkedbytes": "31",
      "ecnmarkedpacket": "61",
      "wreddropbytes": "60",
      "wreddroppacket": "15"
    },
    "MC12": {
      "ecnmarkedbytes": "94",
      "ecnmarkedpacket": "82",
      "wreddropbytes": "52",
      "wreddroppacket": "45"
    },
    "MC13": {
      "ecnmarkedbytes": "52",
      "ecnmarkedpacket": "89",
      "wreddropbytes": "88",
      "wreddroppacket": "55"
    },
    "MC14": {
      "ecnmarkedbytes": "79",
      "ecnmarkedpacket": "95",
      "wreddropbytes": "70",
      "wreddroppacket": "14"
    },
    "MC15": {
      "ecnmarkedbytes": "81",
      "ecnmarkedpacket": "66",
      "wreddropbytes": "60",
      "wreddroppacket": "68"
    },
    "MC16": {
      "ecnmarkedbytes": "76",
      "ecnmarkedpacket": "48",
      "wreddropbytes": "4",
      "wreddroppacket": "63"
    },
    "MC17": {
      "ecnmarkedbytes": "74",
      "ecnmarkedpacket": "77",
      "wreddropbytes": "73",
      "wreddroppacket": "41"
    },
    "MC18": {
      "ecnmarkedbytes": "54",
      "ecnmarkedpacket": "56",
      "wreddropbytes": "21",
      "wreddroppacket": "60"
    },
    "MC19": {
      "ecnmarkedbytes": "39",
      "ecnmarkedpacket": "12",
      "wreddropbytes": "31",
      "wreddroppacket": "57"
    },
    "UC0": {
      "ecnmarkedbytes": "0",
      "ecnmarkedpacket": "0",
      "wreddropbytes": "0",
      "wreddroppacket": "0"
    },
    "UC1": {
      "ecnmarkedbytes": "1",
      "ecnmarkedpacket": "39",
      "wreddropbytes": "43",
      "wreddroppacket": "60"
    },
    "UC2": {
      "ecnmarkedbytes": "21",
      "ecnmarkedpacket": "39",
      "wreddropbytes": "7",
      "wreddroppacket": "82"
    },
    "UC3": {
      "ecnmarkedbytes": "76",
      "ecnmarkedpacket": "19",
      "wreddropbytes": "70",
      "wreddroppacket": "52"
    },
    "UC4": {
      "ecnmarkedbytes": "94",
      "ecnmarkedpacket": "12",
      "wreddropbytes": "59",
      "wreddroppacket": "11"
    },
    "UC5": {
      "ecnmarkedbytes": "40",
      "ecnmarkedpacket": "35",
      "wreddropbytes": "62",
      "wreddroppacket": "36"
    },
    "UC6": {
      "ecnmarkedbytes": "88",
      "ecnmarkedpacket": "2",
      "wreddropbytes": "91",
      "wreddroppacket": "49"
    },
    "UC7": {
      "ecnmarkedbytes": "74",
      "ecnmarkedpacket": "94",
      "wreddropbytes": "17",
      "wreddroppacket": "33"
    },
    "UC8": {
      "ecnmarkedbytes": "33",
      "ecnmarkedpacket": "95",
      "wreddropbytes": "71",
      "wreddroppacket": "40"
    },
    "UC9": {
      "ecnmarkedbytes": "78",
      "ecnmarkedpacket": "93",
      "wreddropbytes": "8",
      "wreddroppacket": "54"
    }
  },
  "Ethernet4": {
    "ALL20": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL21": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL22": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL23": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL24": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL25": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL26": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL27": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL28": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL29": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "MC10": {
      "ecnmarkedbytes": "82",
      "ecnmarkedpacket": "57",
      "wreddropbytes": "1",
      "wreddroppacket": "50"
    },
    "MC11": {
      "ecnmarkedbytes": "59",
      "ecnmarkedpacket": "84",
      "wreddropbytes": "99",
      "wreddroppacket": "67"
    },
    "MC12": {
      "ecnmarkedbytes": "5",
      "ecnmarkedpacket": "27",
      "wreddropbytes": "58",
      "wreddroppacket": "4"
    },
    "MC13": {
      "ecnmarkedbytes": "39",
      "ecnmarkedpacket": "57",
      "wreddropbytes": "5",
      "wreddroppacket": "74"
    },
    "MC14": {
      "ecnmarkedbytes": "14",
      "ecnmarkedpacket": "4",
      "wreddropbytes": "59",
      "wreddroppacket": "21"
    },
    "MC15": {
      "ecnmarkedbytes": "53",
      "ecnmarkedpacket": "19",
      "wreddropbytes": "61",
      "wreddroppacket": "24"
    },
    "MC16": {
      "ecnmarkedbytes": "32",
      "ecnmarkedpacket": "15",
      "wreddropbytes": "15",
      "wreddroppacket": "51"
    },
    "MC17": {
      "ecnmarkedbytes": "15",
      "ecnmarkedpacket": "23",
      "wreddropbytes": "18",
      "wreddroppacket": "98"
    },
    "MC18": {
      "ecnmarkedbytes": "57",
      "ecnmarkedpacket": "9",
      "wreddropbytes": "34",
      "wreddroppacket": "41"
    },
    "MC19": {
      "ecnmarkedbytes": "99",
      "ecnmarkedpacket": "18",
      "wreddropbytes": "7",
      "wreddroppacket": "57"
    },
    "UC0": {
      "ecnmarkedbytes": "98",
      "ecnmarkedpacket": "70",
      "wreddropbytes": "96",
      "wreddroppacket": "41"
    },
    "UC1": {
      "ecnmarkedbytes": "36",
      "ecnmarkedpacket": "63",
      "wreddropbytes": "49",
      "wreddroppacket": "18"
    },
    "UC2": {
      "ecnmarkedbytes": "15",
      "ecnmarkedpacket": "3",
      "wreddropbytes": "90",
      "wreddroppacket": "99"
    },
    "UC3": {
      "ecnmarkedbytes": "41",
      "ecnmarkedpacket": "48",
      "wreddropbytes": "89",
      "wreddroppacket": "60"
    },
    "UC4": {
      "ecnmarkedbytes": "94",
      "ecnmarkedpacket": "82",
      "wreddropbytes": "84",
      "wreddroppacket": "8"
    },
    "UC5": {
      "ecnmarkedbytes": "92",
      "ecnmarkedpacket": "75",
      "wreddropbytes": "15",
      "wreddroppacket": "83"
    },
    "UC6": {
      "ecnmarkedbytes": "71",
      "ecnmarkedpacket": "50",
      "wreddropbytes": "26",
      "wreddroppacket": "84"
    },
    "UC7": {
      "ecnmarkedbytes": "80",
      "ecnmarkedpacket": "49",
      "wreddropbytes": "19",
      "wreddroppacket": "27"
    },
    "UC8": {
      "ecnmarkedbytes": "33",
      "ecnmarkedpacket": "13",
      "wreddropbytes": "89",
      "wreddroppacket": "13"
    },
    "UC9": {
      "ecnmarkedbytes": "31",
      "ecnmarkedpacket": "86",
      "wreddropbytes": "48",
      "wreddroppacket": "43"
    }
  },
  "Ethernet8": {
    "ALL20": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL21": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL22": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL23": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL24": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL25": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL26": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL27": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL28": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL29": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "MC10": {
      "ecnmarkedbytes": "73",
      "ecnmarkedpacket": "76",
      "wreddropbytes": "63",
      "wreddroppacket": "81"
    },
    "MC11": {
      "ecnmarkedbytes": "66",
      "ecnmarkedpacket": "29",
      "wreddropbytes": "16",
      "wreddroppacket": "29"
    },
    "MC12": {
      "ecnmarkedbytes": "35",
      "ecnmarkedpacket": "61",
      "wreddropbytes": "12",
      "wreddroppacket": "32"
    },
    "MC13": {
      "ecnmarkedbytes": "93",
      "ecnmarkedpacket": "72",
      "wreddropbytes": "17",
      "wreddroppacket": "79"
    },
    "MC14": {
      "ecnmarkedbytes": "50",
      "ecnmarkedpacket": "67",
      "wreddropbytes": "21",
      "wreddroppacket": "23"
    },
    "MC15": {
      "ecnmarkedbytes": "14",
      "ecnmarkedpacket": "97",
      "wreddropbytes": "10",
      "wreddroppacket": "37"
    },
    "MC16": {
      "ecnmarkedbytes": "43",
      "ecnmarkedpacket": "74",
      "wreddropbytes": "17",
      "wreddroppacket": "30"
    },
    "MC17": {
      "ecnmarkedbytes": "84",
      "ecnmarkedpacket": "54",
      "wreddropbytes": "63",
      "wreddroppacket": "0"
    },
    "MC18": {
      "ecnmarkedbytes": "79",
      "ecnmarkedpacket": "24",
      "wreddropbytes": "88",
      "wreddroppacket": "69"
    },
    "MC19": {
      "ecnmarkedbytes": "3",
      "ecnmarkedpacket": "84",
      "wreddropbytes": "12",
      "wreddroppacket": "20"
    },
    "UC0": {
      "ecnmarkedbytes": "0",
      "ecnmarkedpacket": "0",
      "wreddropbytes": "0",
      "wreddroppacket": "0"
    },
    "UC1": {
      "ecnmarkedbytes": "91",
      "ecnmarkedpacket": "68",
      "wreddropbytes": "17",
      "wreddroppacket": "38"
    },
    "UC2": {
      "ecnmarkedbytes": "51",
      "ecnmarkedpacket": "79",
      "wreddropbytes": "65",
      "wreddroppacket": "16"
    },
    "UC3": {
      "ecnmarkedbytes": "72",
      "ecnmarkedpacket": "63",
      "wreddropbytes": "97",
      "wreddroppacket": "11"
    },
    "UC4": {
      "ecnmarkedbytes": "62",
      "ecnmarkedpacket": "62",
      "wreddropbytes": "89",
      "wreddroppacket": "54"
    },
    "UC5": {
      "ecnmarkedbytes": "59",
      "ecnmarkedpacket": "30",
      "wreddropbytes": "84",
      "wreddroppacket": "13"
    },
    "UC6": {
      "ecnmarkedbytes": "85",
      "ecnmarkedpacket": "99",
      "wreddropbytes": "67",
      "wreddroppacket": "49"
    },
    "UC7": {
      "ecnmarkedbytes": "88",
      "ecnmarkedpacket": "38",
      "wreddropbytes": "63",
      "wreddroppacket": "2"
    },
    "UC8": {
      "ecnmarkedbytes": "43",
      "ecnmarkedpacket": "93",
      "wreddropbytes": "82",
      "wreddroppacket": "0"
    },
    "UC9": {
      "ecnmarkedbytes": "61",
      "ecnmarkedpacket": "91",
      "wreddropbytes": "17",
      "wreddroppacket": "80"
    }
  }
}"""

show_queue_counters_port_json = """\
{
  "Ethernet8": {
    "ALL20": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL21": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL22": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL23": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL24": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL25": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL26": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL27": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL28": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "ALL29": {
      "ecnmarkedbytes": "N/A",
      "ecnmarkedpacket": "N/A",
      "wreddropbytes": "N/A",
      "wreddroppacket": "N/A"
    },
    "MC10": {
      "ecnmarkedbytes": "73",
      "ecnmarkedpacket": "76",
      "wreddropbytes": "63",
      "wreddroppacket": "81"
    },
    "MC11": {
      "ecnmarkedbytes": "66",
      "ecnmarkedpacket": "29",
      "wreddropbytes": "16",
      "wreddroppacket": "29"
    },
    "MC12": {
      "ecnmarkedbytes": "35",
      "ecnmarkedpacket": "61",
      "wreddropbytes": "12",
      "wreddroppacket": "32"
    },
    "MC13": {
      "ecnmarkedbytes": "93",
      "ecnmarkedpacket": "72",
      "wreddropbytes": "17",
      "wreddroppacket": "79"
    },
    "MC14": {
      "ecnmarkedbytes": "50",
      "ecnmarkedpacket": "67",
      "wreddropbytes": "21",
      "wreddroppacket": "23"
    },
    "MC15": {
      "ecnmarkedbytes": "14",
      "ecnmarkedpacket": "97",
      "wreddropbytes": "10",
      "wreddroppacket": "37"
    },
    "MC16": {
      "ecnmarkedbytes": "43",
      "ecnmarkedpacket": "74",
      "wreddropbytes": "17",
      "wreddroppacket": "30"
    },
    "MC17": {
      "ecnmarkedbytes": "84",
      "ecnmarkedpacket": "54",
      "wreddropbytes": "63",
      "wreddroppacket": "0"
    },
    "MC18": {
      "ecnmarkedbytes": "79",
      "ecnmarkedpacket": "24",
      "wreddropbytes": "88",
      "wreddroppacket": "69"
    },
    "MC19": {
      "ecnmarkedbytes": "3",
      "ecnmarkedpacket": "84",
      "wreddropbytes": "12",
      "wreddroppacket": "20"
    },
    "UC0": {
      "ecnmarkedbytes": "0",
      "ecnmarkedpacket": "0",
      "wreddropbytes": "0",
      "wreddroppacket": "0"
    },
    "UC1": {
      "ecnmarkedbytes": "91",
      "ecnmarkedpacket": "68",
      "wreddropbytes": "17",
      "wreddroppacket": "38"
    },
    "UC2": {
      "ecnmarkedbytes": "51",
      "ecnmarkedpacket": "79",
      "wreddropbytes": "65",
      "wreddroppacket": "16"
    },
    "UC3": {
      "ecnmarkedbytes": "72",
      "ecnmarkedpacket": "63",
      "wreddropbytes": "97",
      "wreddroppacket": "11"
    },
    "UC4": {
      "ecnmarkedbytes": "62",
      "ecnmarkedpacket": "62",
      "wreddropbytes": "89",
      "wreddroppacket": "54"
    },
    "UC5": {
      "ecnmarkedbytes": "59",
      "ecnmarkedpacket": "30",
      "wreddropbytes": "84",
      "wreddroppacket": "13"
    },
    "UC6": {
      "ecnmarkedbytes": "85",
      "ecnmarkedpacket": "99",
      "wreddropbytes": "67",
      "wreddroppacket": "49"
    },
    "UC7": {
      "ecnmarkedbytes": "88",
      "ecnmarkedpacket": "38",
      "wreddropbytes": "63",
      "wreddroppacket": "2"
    },
    "UC8": {
      "ecnmarkedbytes": "43",
      "ecnmarkedpacket": "93",
      "wreddropbytes": "82",
      "wreddroppacket": "0"
    },
    "UC9": {
      "ecnmarkedbytes": "61",
      "ecnmarkedpacket": "91",
      "wreddropbytes": "17",
      "wreddroppacket": "80"
    }
  }
}"""

show_queue_voq_counters = """\
            Port    Voq    WredDrp/pkts    WredDrp/bytes    EcnMarked/pkts    EcnMarked/bytes
----------------  -----  --------------  ---------------  ----------------  -----------------
testsw|Ethernet0   VOQ0               0                0                 0                  0
testsw|Ethernet0   VOQ1              60               43                39                  1
testsw|Ethernet0   VOQ2              82                7                39                 21
testsw|Ethernet0   VOQ3              11               59                12                 94
testsw|Ethernet0   VOQ4              36               62                35                 40
testsw|Ethernet0   VOQ5              49               91                 2                 88
testsw|Ethernet0   VOQ6              33               17                94                 74
testsw|Ethernet0   VOQ7              40               71                95                 33

            Port    Voq    WredDrp/pkts    WredDrp/bytes    EcnMarked/pkts    EcnMarked/bytes
----------------  -----  --------------  ---------------  ----------------  -----------------
testsw|Ethernet4   VOQ0              54                8                93                 78
testsw|Ethernet4   VOQ1              83               96                74                  9
testsw|Ethernet4   VOQ2              15               60                61                 31
testsw|Ethernet4   VOQ3              45               52                82                 94
testsw|Ethernet4   VOQ4              55               88                89                 52
testsw|Ethernet4   VOQ5              14               70                95                 79
testsw|Ethernet4   VOQ6              68               60                66                 81
testsw|Ethernet4   VOQ7              63                4                48                 76

            Port    Voq    WredDrp/pkts    WredDrp/bytes    EcnMarked/pkts    EcnMarked/bytes
----------------  -----  --------------  ---------------  ----------------  -----------------
testsw|Ethernet8   VOQ0              41               73                77                 74
testsw|Ethernet8   VOQ1              60               21                56                 54
testsw|Ethernet8   VOQ2              57               31                12                 39
testsw|Ethernet8   VOQ3              41               96                70                 98
testsw|Ethernet8   VOQ4              18               49                63                 36
testsw|Ethernet8   VOQ5              99               90                 3                 15
testsw|Ethernet8   VOQ6               8               84                82                 94
testsw|Ethernet8   VOQ7              83               15                75                 92

"""

show_queue_port_voq_counters = """\
            Port    Voq    WredDrp/pkts    WredDrp/bytes    EcnMarked/pkts    EcnMarked/bytes
----------------  -----  --------------  ---------------  ----------------  -----------------
testsw|Ethernet0   VOQ0               0                0                 0                  0
testsw|Ethernet0   VOQ1              60               43                39                  1
testsw|Ethernet0   VOQ2              82                7                39                 21
testsw|Ethernet0   VOQ3              11               59                12                 94
testsw|Ethernet0   VOQ4              36               62                35                 40
testsw|Ethernet0   VOQ5              49               91                 2                 88
testsw|Ethernet0   VOQ6              33               17                94                 74
testsw|Ethernet0   VOQ7              40               71                95                 33

"""

show_queue_voq_counters_json = """\
{
  "testsw|Ethernet0": {
    "VOQ0": {
      "ecnmarkedbytes": "0",
      "ecnmarkedpacket": "0",
      "wreddropbytes": "0",
      "wreddroppacket": "0"
    },
    "VOQ1": {
      "ecnmarkedbytes": "1",
      "ecnmarkedpacket": "39",
      "wreddropbytes": "43",
      "wreddroppacket": "60"
    },
    "VOQ2": {
      "ecnmarkedbytes": "21",
      "ecnmarkedpacket": "39",
      "wreddropbytes": "7",
      "wreddroppacket": "82"
    },
    "VOQ3": {
      "ecnmarkedbytes": "94",
      "ecnmarkedpacket": "12",
      "wreddropbytes": "59",
      "wreddroppacket": "11"
    },
    "VOQ4": {
      "ecnmarkedbytes": "40",
      "ecnmarkedpacket": "35",
      "wreddropbytes": "62",
      "wreddroppacket": "36"
    },
    "VOQ5": {
      "ecnmarkedbytes": "88",
      "ecnmarkedpacket": "2",
      "wreddropbytes": "91",
      "wreddroppacket": "49"
    },
    "VOQ6": {
      "ecnmarkedbytes": "74",
      "ecnmarkedpacket": "94",
      "wreddropbytes": "17",
      "wreddroppacket": "33"
    },
    "VOQ7": {
      "ecnmarkedbytes": "33",
      "ecnmarkedpacket": "95",
      "wreddropbytes": "71",
      "wreddroppacket": "40"
    }
  },
  "testsw|Ethernet4": {
    "VOQ0": {
      "ecnmarkedbytes": "78",
      "ecnmarkedpacket": "93",
      "wreddropbytes": "8",
      "wreddroppacket": "54"
    },
    "VOQ1": {
      "ecnmarkedbytes": "9",
      "ecnmarkedpacket": "74",
      "wreddropbytes": "96",
      "wreddroppacket": "83"
    },
    "VOQ2": {
      "ecnmarkedbytes": "31",
      "ecnmarkedpacket": "61",
      "wreddropbytes": "60",
      "wreddroppacket": "15"
    },
    "VOQ3": {
      "ecnmarkedbytes": "94",
      "ecnmarkedpacket": "82",
      "wreddropbytes": "52",
      "wreddroppacket": "45"
    },
    "VOQ4": {
      "ecnmarkedbytes": "52",
      "ecnmarkedpacket": "89",
      "wreddropbytes": "88",
      "wreddroppacket": "55"
    },
    "VOQ5": {
      "ecnmarkedbytes": "79",
      "ecnmarkedpacket": "95",
      "wreddropbytes": "70",
      "wreddroppacket": "14"
    },
    "VOQ6": {
      "ecnmarkedbytes": "81",
      "ecnmarkedpacket": "66",
      "wreddropbytes": "60",
      "wreddroppacket": "68"
    },
    "VOQ7": {
      "ecnmarkedbytes": "76",
      "ecnmarkedpacket": "48",
      "wreddropbytes": "4",
      "wreddroppacket": "63"
    }
  },
  "testsw|Ethernet8": {
    "VOQ0": {
      "ecnmarkedbytes": "74",
      "ecnmarkedpacket": "77",
      "wreddropbytes": "73",
      "wreddroppacket": "41"
    },
    "VOQ1": {
      "ecnmarkedbytes": "54",
      "ecnmarkedpacket": "56",
      "wreddropbytes": "21",
      "wreddroppacket": "60"
    },
    "VOQ2": {
      "ecnmarkedbytes": "39",
      "ecnmarkedpacket": "12",
      "wreddropbytes": "31",
      "wreddroppacket": "57"
    },
    "VOQ3": {
      "ecnmarkedbytes": "98",
      "ecnmarkedpacket": "70",
      "wreddropbytes": "96",
      "wreddroppacket": "41"
    },
    "VOQ4": {
      "ecnmarkedbytes": "36",
      "ecnmarkedpacket": "63",
      "wreddropbytes": "49",
      "wreddroppacket": "18"
    },
    "VOQ5": {
      "ecnmarkedbytes": "15",
      "ecnmarkedpacket": "3",
      "wreddropbytes": "90",
      "wreddroppacket": "99"
    },
    "VOQ6": {
      "ecnmarkedbytes": "94",
      "ecnmarkedpacket": "82",
      "wreddropbytes": "84",
      "wreddroppacket": "8"
    },
    "VOQ7": {
      "ecnmarkedbytes": "92",
      "ecnmarkedpacket": "75",
      "wreddropbytes": "15",
      "wreddroppacket": "83"
    }
  }
}"""

show_queue_port_voq_counters_json = """\
{
  "testsw|Ethernet0": {
    "VOQ0": {
      "ecnmarkedbytes": "0",
      "ecnmarkedpacket": "0",
      "wreddropbytes": "0",
      "wreddroppacket": "0"
    },
    "VOQ1": {
      "ecnmarkedbytes": "1",
      "ecnmarkedpacket": "39",
      "wreddropbytes": "43",
      "wreddroppacket": "60"
    },
    "VOQ2": {
      "ecnmarkedbytes": "21",
      "ecnmarkedpacket": "39",
      "wreddropbytes": "7",
      "wreddroppacket": "82"
    },
    "VOQ3": {
      "ecnmarkedbytes": "94",
      "ecnmarkedpacket": "12",
      "wreddropbytes": "59",
      "wreddroppacket": "11"
    },
    "VOQ4": {
      "ecnmarkedbytes": "40",
      "ecnmarkedpacket": "35",
      "wreddropbytes": "62",
      "wreddroppacket": "36"
    },
    "VOQ5": {
      "ecnmarkedbytes": "88",
      "ecnmarkedpacket": "2",
      "wreddropbytes": "91",
      "wreddroppacket": "49"
    },
    "VOQ6": {
      "ecnmarkedbytes": "74",
      "ecnmarkedpacket": "94",
      "wreddropbytes": "17",
      "wreddroppacket": "33"
    },
    "VOQ7": {
      "ecnmarkedbytes": "33",
      "ecnmarkedpacket": "95",
      "wreddropbytes": "71",
      "wreddroppacket": "40"
    }
  }
}"""


def remove_tmp_cnstat_file():
    # remove the tmp wredstat
    cache = UserCache("wredstat")
    cache.remove_all()


class TestWredQueue(object):
    @classmethod
    def setup_class(cls):
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        remove_tmp_cnstat_file()
        print("SETUP")

    def test_queue_counters(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["queue"].commands["wredcounters"],
            []
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_wred_queue_counters

    def test_queue_counters_port(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["queue"].commands["wredcounters"],
            ["Ethernet8"]
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_wred_queue_counters_port

    def test_queue_counters_json(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["queue"].commands["wredcounters"],
            ["--json"]
        )
        assert result.exit_code == 0
        print(result.output)
        json_output = json.loads(result.output)

        # remove "time" from the output
        for _, v in json_output.items():
            del v["time"]
        assert json_dump(json_output) == show_queue_counters_json

    def test_queue_counters_port_json(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["queue"].commands["wredcounters"],
            ["Ethernet8", "--json"]
        )
        assert result.exit_code == 0
        print(result.output)
        json_output = json.loads(result.output)

        # remove "time" from the output
        for _, v in json_output.items():
            del v["time"]
        assert json_dump(json_output) == show_queue_counters_port_json

    def test_queue_voq_counters(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["queue"].commands["wredcounters"],
            ["--voq"]
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_queue_voq_counters

    def test_queue_port_voq_counters(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["queue"].commands["wredcounters"],
            ["testsw|Ethernet0", "--voq"]
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_queue_port_voq_counters

    def test_queue_voq_counters_json(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["queue"].commands["wredcounters"],
            ["--voq", "--json"]
        )
        assert result.exit_code == 0
        print(result.output)
        json_output = json.loads(result.output)

        # remove "time" from the output
        for _, v in json_output.items():
            del v["time"]
        print(json_dump(json_output))
        print(show_queue_voq_counters_json)
        assert json_dump(json_output) == show_queue_voq_counters_json

    def test_queue_voq_counters_port_json(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["queue"].commands["wredcounters"],
            ["testsw|Ethernet0", "--voq", "--json"]
        )
        assert result.exit_code == 0
        print(result.output)
        json_output = json.loads(result.output)

        # remove "time" from the output
        for _, v in json_output.items():
            del v["time"]
        assert json_dump(json_output) == show_queue_port_voq_counters_json

    def test_clear_wredstats(self):
        wredstat_clear_str = "Clear and update saved counters"
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands["queue"].commands["wredcounters"], [])
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert (wredstat_clear_str in result.output)

    def test_invalid_port(self):
        wredstat_inv_port = "Port does not exist"
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["queue"].commands["wredcounters"],
            ["testsw|Ethernet5000"]
        )
        print(result.output)
        assert result.exit_code == 1
        assert (wredstat_inv_port in result.output)

    @classmethod
    def teardown_class(cls):
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")

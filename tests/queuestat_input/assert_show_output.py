"""
Module holding the correct values for show CLI command outputs for the queuestat_test.py
"""

counters_all="""\
For namespace :
     Port    TxQ    Counter/pkts    Counter/bytes    Drop/pkts    Drop/bytes    Trim/pkts
---------  -----  --------------  ---------------  -----------  ------------  -----------
Ethernet0    UC0               0                0            0             0            0
Ethernet0    UC1              60               43           39             1          100
Ethernet0    UC2              82                7           39            21          N/A
Ethernet0    UC3              52               70           19            76          N/A
Ethernet0    UC4              11               59           12            94          N/A
Ethernet0    UC5              36               62           35            40          N/A
Ethernet0    UC6              49               91            2            88          N/A
Ethernet0    UC7              33               17           94            74          N/A
Ethernet0    UC8              40               71           95            33          N/A
Ethernet0    UC9              54                8           93            78          N/A
Ethernet0   MC10              83               96           74             9          N/A
Ethernet0   MC11              15               60           61            31          N/A
Ethernet0   MC12              45               52           82            94          N/A
Ethernet0   MC13              55               88           89            52          N/A
Ethernet0   MC14              14               70           95            79          N/A
Ethernet0   MC15              68               60           66            81          N/A
Ethernet0   MC16              63                4           48            76          N/A
Ethernet0   MC17              41               73           77            74          N/A
Ethernet0   MC18              60               21           56            54          N/A
Ethernet0   MC19              57               31           12            39          N/A
Ethernet0  ALL20             N/A              N/A          N/A           N/A          N/A
Ethernet0  ALL21             N/A              N/A          N/A           N/A          N/A
Ethernet0  ALL22             N/A              N/A          N/A           N/A          N/A
Ethernet0  ALL23             N/A              N/A          N/A           N/A          N/A
Ethernet0  ALL24             N/A              N/A          N/A           N/A          N/A
Ethernet0  ALL25             N/A              N/A          N/A           N/A          N/A
Ethernet0  ALL26             N/A              N/A          N/A           N/A          N/A
Ethernet0  ALL27             N/A              N/A          N/A           N/A          N/A
Ethernet0  ALL28             N/A              N/A          N/A           N/A          N/A
Ethernet0  ALL29             N/A              N/A          N/A           N/A          N/A

For namespace :
     Port    TxQ    Counter/pkts    Counter/bytes    Drop/pkts    Drop/bytes    Trim/pkts
---------  -----  --------------  ---------------  -----------  ------------  -----------
Ethernet4    UC0              41               96           70            98            0
Ethernet4    UC1              18               49           63            36          100
Ethernet4    UC2              99               90            3            15          N/A
Ethernet4    UC3              60               89           48            41          N/A
Ethernet4    UC4               8               84           82            94          N/A
Ethernet4    UC5              83               15           75            92          N/A
Ethernet4    UC6              84               26           50            71          N/A
Ethernet4    UC7              27               19           49            80          N/A
Ethernet4    UC8              13               89           13            33          N/A
Ethernet4    UC9              43               48           86            31          N/A
Ethernet4   MC10              50                1           57            82          N/A
Ethernet4   MC11              67               99           84            59          N/A
Ethernet4   MC12               4               58           27             5          N/A
Ethernet4   MC13              74                5           57            39          N/A
Ethernet4   MC14              21               59            4            14          N/A
Ethernet4   MC15              24               61           19            53          N/A
Ethernet4   MC16              51               15           15            32          N/A
Ethernet4   MC17              98               18           23            15          N/A
Ethernet4   MC18              41               34            9            57          N/A
Ethernet4   MC19              57                7           18            99          N/A
Ethernet4  ALL20             N/A              N/A          N/A           N/A          N/A
Ethernet4  ALL21             N/A              N/A          N/A           N/A          N/A
Ethernet4  ALL22             N/A              N/A          N/A           N/A          N/A
Ethernet4  ALL23             N/A              N/A          N/A           N/A          N/A
Ethernet4  ALL24             N/A              N/A          N/A           N/A          N/A
Ethernet4  ALL25             N/A              N/A          N/A           N/A          N/A
Ethernet4  ALL26             N/A              N/A          N/A           N/A          N/A
Ethernet4  ALL27             N/A              N/A          N/A           N/A          N/A
Ethernet4  ALL28             N/A              N/A          N/A           N/A          N/A
Ethernet4  ALL29             N/A              N/A          N/A           N/A          N/A

For namespace :
     Port    TxQ    Counter/pkts    Counter/bytes    Drop/pkts    Drop/bytes    Trim/pkts
---------  -----  --------------  ---------------  -----------  ------------  -----------
Ethernet8    UC0               0                0            0             0            0
Ethernet8    UC1              38               17           68            91          100
Ethernet8    UC2              16               65           79            51          N/A
Ethernet8    UC3              11               97           63            72          N/A
Ethernet8    UC4              54               89           62            62          N/A
Ethernet8    UC5              13               84           30            59          N/A
Ethernet8    UC6              49               67           99            85          N/A
Ethernet8    UC7               2               63           38            88          N/A
Ethernet8    UC8               0               82           93            43          N/A
Ethernet8    UC9              80               17           91            61          N/A
Ethernet8   MC10              81               63           76            73          N/A
Ethernet8   MC11              29               16           29            66          N/A
Ethernet8   MC12              32               12           61            35          N/A
Ethernet8   MC13              79               17           72            93          N/A
Ethernet8   MC14              23               21           67            50          N/A
Ethernet8   MC15              37               10           97            14          N/A
Ethernet8   MC16              30               17           74            43          N/A
Ethernet8   MC17               0               63           54            84          N/A
Ethernet8   MC18              69               88           24            79          N/A
Ethernet8   MC19              20               12           84             3          N/A
Ethernet8  ALL20             N/A              N/A          N/A           N/A          N/A
Ethernet8  ALL21             N/A              N/A          N/A           N/A          N/A
Ethernet8  ALL22             N/A              N/A          N/A           N/A          N/A
Ethernet8  ALL23             N/A              N/A          N/A           N/A          N/A
Ethernet8  ALL24             N/A              N/A          N/A           N/A          N/A
Ethernet8  ALL25             N/A              N/A          N/A           N/A          N/A
Ethernet8  ALL26             N/A              N/A          N/A           N/A          N/A
Ethernet8  ALL27             N/A              N/A          N/A           N/A          N/A
Ethernet8  ALL28             N/A              N/A          N/A           N/A          N/A
Ethernet8  ALL29             N/A              N/A          N/A           N/A          N/A

"""
counters_all_json="""\
{
  "Ethernet0": {
    "ALL20": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL21": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL22": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL23": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL24": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL25": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL26": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL27": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL28": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL29": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "MC10": {
      "dropbytes": "9",
      "droppacket": "74",
      "totalbytes": "96",
      "totalpacket": "83",
      "trimpacket": "N/A"
    },
    "MC11": {
      "dropbytes": "31",
      "droppacket": "61",
      "totalbytes": "60",
      "totalpacket": "15",
      "trimpacket": "N/A"
    },
    "MC12": {
      "dropbytes": "94",
      "droppacket": "82",
      "totalbytes": "52",
      "totalpacket": "45",
      "trimpacket": "N/A"
    },
    "MC13": {
      "dropbytes": "52",
      "droppacket": "89",
      "totalbytes": "88",
      "totalpacket": "55",
      "trimpacket": "N/A"
    },
    "MC14": {
      "dropbytes": "79",
      "droppacket": "95",
      "totalbytes": "70",
      "totalpacket": "14",
      "trimpacket": "N/A"
    },
    "MC15": {
      "dropbytes": "81",
      "droppacket": "66",
      "totalbytes": "60",
      "totalpacket": "68",
      "trimpacket": "N/A"
    },
    "MC16": {
      "dropbytes": "76",
      "droppacket": "48",
      "totalbytes": "4",
      "totalpacket": "63",
      "trimpacket": "N/A"
    },
    "MC17": {
      "dropbytes": "74",
      "droppacket": "77",
      "totalbytes": "73",
      "totalpacket": "41",
      "trimpacket": "N/A"
    },
    "MC18": {
      "dropbytes": "54",
      "droppacket": "56",
      "totalbytes": "21",
      "totalpacket": "60",
      "trimpacket": "N/A"
    },
    "MC19": {
      "dropbytes": "39",
      "droppacket": "12",
      "totalbytes": "31",
      "totalpacket": "57",
      "trimpacket": "N/A"
    },
    "UC0": {
      "dropbytes": "0",
      "droppacket": "0",
      "totalbytes": "0",
      "totalpacket": "0",
      "trimpacket": "0"
    },
    "UC1": {
      "dropbytes": "1",
      "droppacket": "39",
      "totalbytes": "43",
      "totalpacket": "60",
      "trimpacket": "100"
    },
    "UC2": {
      "dropbytes": "21",
      "droppacket": "39",
      "totalbytes": "7",
      "totalpacket": "82",
      "trimpacket": "N/A"
    },
    "UC3": {
      "dropbytes": "76",
      "droppacket": "19",
      "totalbytes": "70",
      "totalpacket": "52",
      "trimpacket": "N/A"
    },
    "UC4": {
      "dropbytes": "94",
      "droppacket": "12",
      "totalbytes": "59",
      "totalpacket": "11",
      "trimpacket": "N/A"
    },
    "UC5": {
      "dropbytes": "40",
      "droppacket": "35",
      "totalbytes": "62",
      "totalpacket": "36",
      "trimpacket": "N/A"
    },
    "UC6": {
      "dropbytes": "88",
      "droppacket": "2",
      "totalbytes": "91",
      "totalpacket": "49",
      "trimpacket": "N/A"
    },
    "UC7": {
      "dropbytes": "74",
      "droppacket": "94",
      "totalbytes": "17",
      "totalpacket": "33",
      "trimpacket": "N/A"
    },
    "UC8": {
      "dropbytes": "33",
      "droppacket": "95",
      "totalbytes": "71",
      "totalpacket": "40",
      "trimpacket": "N/A"
    },
    "UC9": {
      "dropbytes": "78",
      "droppacket": "93",
      "totalbytes": "8",
      "totalpacket": "54",
      "trimpacket": "N/A"
    }
  },
  "Ethernet4": {
    "ALL20": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL21": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL22": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL23": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL24": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL25": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL26": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL27": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL28": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL29": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "MC10": {
      "dropbytes": "82",
      "droppacket": "57",
      "totalbytes": "1",
      "totalpacket": "50",
      "trimpacket": "N/A"
    },
    "MC11": {
      "dropbytes": "59",
      "droppacket": "84",
      "totalbytes": "99",
      "totalpacket": "67",
      "trimpacket": "N/A"
    },
    "MC12": {
      "dropbytes": "5",
      "droppacket": "27",
      "totalbytes": "58",
      "totalpacket": "4",
      "trimpacket": "N/A"
    },
    "MC13": {
      "dropbytes": "39",
      "droppacket": "57",
      "totalbytes": "5",
      "totalpacket": "74",
      "trimpacket": "N/A"
    },
    "MC14": {
      "dropbytes": "14",
      "droppacket": "4",
      "totalbytes": "59",
      "totalpacket": "21",
      "trimpacket": "N/A"
    },
    "MC15": {
      "dropbytes": "53",
      "droppacket": "19",
      "totalbytes": "61",
      "totalpacket": "24",
      "trimpacket": "N/A"
    },
    "MC16": {
      "dropbytes": "32",
      "droppacket": "15",
      "totalbytes": "15",
      "totalpacket": "51",
      "trimpacket": "N/A"
    },
    "MC17": {
      "dropbytes": "15",
      "droppacket": "23",
      "totalbytes": "18",
      "totalpacket": "98",
      "trimpacket": "N/A"
    },
    "MC18": {
      "dropbytes": "57",
      "droppacket": "9",
      "totalbytes": "34",
      "totalpacket": "41",
      "trimpacket": "N/A"
    },
    "MC19": {
      "dropbytes": "99",
      "droppacket": "18",
      "totalbytes": "7",
      "totalpacket": "57",
      "trimpacket": "N/A"
    },
    "UC0": {
      "dropbytes": "98",
      "droppacket": "70",
      "totalbytes": "96",
      "totalpacket": "41",
      "trimpacket": "0"
    },
    "UC1": {
      "dropbytes": "36",
      "droppacket": "63",
      "totalbytes": "49",
      "totalpacket": "18",
      "trimpacket": "100"
    },
    "UC2": {
      "dropbytes": "15",
      "droppacket": "3",
      "totalbytes": "90",
      "totalpacket": "99",
      "trimpacket": "N/A"
    },
    "UC3": {
      "dropbytes": "41",
      "droppacket": "48",
      "totalbytes": "89",
      "totalpacket": "60",
      "trimpacket": "N/A"
    },
    "UC4": {
      "dropbytes": "94",
      "droppacket": "82",
      "totalbytes": "84",
      "totalpacket": "8",
      "trimpacket": "N/A"
    },
    "UC5": {
      "dropbytes": "92",
      "droppacket": "75",
      "totalbytes": "15",
      "totalpacket": "83",
      "trimpacket": "N/A"
    },
    "UC6": {
      "dropbytes": "71",
      "droppacket": "50",
      "totalbytes": "26",
      "totalpacket": "84",
      "trimpacket": "N/A"
    },
    "UC7": {
      "dropbytes": "80",
      "droppacket": "49",
      "totalbytes": "19",
      "totalpacket": "27",
      "trimpacket": "N/A"
    },
    "UC8": {
      "dropbytes": "33",
      "droppacket": "13",
      "totalbytes": "89",
      "totalpacket": "13",
      "trimpacket": "N/A"
    },
    "UC9": {
      "dropbytes": "31",
      "droppacket": "86",
      "totalbytes": "48",
      "totalpacket": "43",
      "trimpacket": "N/A"
    }
  },
  "Ethernet8": {
    "ALL20": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL21": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL22": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL23": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL24": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL25": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL26": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL27": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL28": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "ALL29": {
      "dropbytes": "N/A",
      "droppacket": "N/A",
      "totalbytes": "N/A",
      "totalpacket": "N/A",
      "trimpacket": "N/A"
    },
    "MC10": {
      "dropbytes": "73",
      "droppacket": "76",
      "totalbytes": "63",
      "totalpacket": "81",
      "trimpacket": "N/A"
    },
    "MC11": {
      "dropbytes": "66",
      "droppacket": "29",
      "totalbytes": "16",
      "totalpacket": "29",
      "trimpacket": "N/A"
    },
    "MC12": {
      "dropbytes": "35",
      "droppacket": "61",
      "totalbytes": "12",
      "totalpacket": "32",
      "trimpacket": "N/A"
    },
    "MC13": {
      "dropbytes": "93",
      "droppacket": "72",
      "totalbytes": "17",
      "totalpacket": "79",
      "trimpacket": "N/A"
    },
    "MC14": {
      "dropbytes": "50",
      "droppacket": "67",
      "totalbytes": "21",
      "totalpacket": "23",
      "trimpacket": "N/A"
    },
    "MC15": {
      "dropbytes": "14",
      "droppacket": "97",
      "totalbytes": "10",
      "totalpacket": "37",
      "trimpacket": "N/A"
    },
    "MC16": {
      "dropbytes": "43",
      "droppacket": "74",
      "totalbytes": "17",
      "totalpacket": "30",
      "trimpacket": "N/A"
    },
    "MC17": {
      "dropbytes": "84",
      "droppacket": "54",
      "totalbytes": "63",
      "totalpacket": "0",
      "trimpacket": "N/A"
    },
    "MC18": {
      "dropbytes": "79",
      "droppacket": "24",
      "totalbytes": "88",
      "totalpacket": "69",
      "trimpacket": "N/A"
    },
    "MC19": {
      "dropbytes": "3",
      "droppacket": "84",
      "totalbytes": "12",
      "totalpacket": "20",
      "trimpacket": "N/A"
    },
    "UC0": {
      "dropbytes": "0",
      "droppacket": "0",
      "totalbytes": "0",
      "totalpacket": "0",
      "trimpacket": "0"
    },
    "UC1": {
      "dropbytes": "91",
      "droppacket": "68",
      "totalbytes": "17",
      "totalpacket": "38",
      "trimpacket": "100"
    },
    "UC2": {
      "dropbytes": "51",
      "droppacket": "79",
      "totalbytes": "65",
      "totalpacket": "16",
      "trimpacket": "N/A"
    },
    "UC3": {
      "dropbytes": "72",
      "droppacket": "63",
      "totalbytes": "97",
      "totalpacket": "11",
      "trimpacket": "N/A"
    },
    "UC4": {
      "dropbytes": "62",
      "droppacket": "62",
      "totalbytes": "89",
      "totalpacket": "54",
      "trimpacket": "N/A"
    },
    "UC5": {
      "dropbytes": "59",
      "droppacket": "30",
      "totalbytes": "84",
      "totalpacket": "13",
      "trimpacket": "N/A"
    },
    "UC6": {
      "dropbytes": "85",
      "droppacket": "99",
      "totalbytes": "67",
      "totalpacket": "49",
      "trimpacket": "N/A"
    },
    "UC7": {
      "dropbytes": "88",
      "droppacket": "38",
      "totalbytes": "63",
      "totalpacket": "2",
      "trimpacket": "N/A"
    },
    "UC8": {
      "dropbytes": "43",
      "droppacket": "93",
      "totalbytes": "82",
      "totalpacket": "0",
      "trimpacket": "N/A"
    },
    "UC9": {
      "dropbytes": "61",
      "droppacket": "91",
      "totalbytes": "17",
      "totalpacket": "80",
      "trimpacket": "N/A"
    }
  }
}
"""

trim_counters_all="""\
For namespace :
     Port    TxQ    Trim/pkts
---------  -----  -----------
Ethernet0    UC0            0
Ethernet0    UC1          100
Ethernet0    UC2          N/A
Ethernet0    UC3          N/A
Ethernet0    UC4          N/A
Ethernet0    UC5          N/A
Ethernet0    UC6          N/A
Ethernet0    UC7          N/A
Ethernet0    UC8          N/A
Ethernet0    UC9          N/A
Ethernet0   MC10          N/A
Ethernet0   MC11          N/A
Ethernet0   MC12          N/A
Ethernet0   MC13          N/A
Ethernet0   MC14          N/A
Ethernet0   MC15          N/A
Ethernet0   MC16          N/A
Ethernet0   MC17          N/A
Ethernet0   MC18          N/A
Ethernet0   MC19          N/A
Ethernet0  ALL20          N/A
Ethernet0  ALL21          N/A
Ethernet0  ALL22          N/A
Ethernet0  ALL23          N/A
Ethernet0  ALL24          N/A
Ethernet0  ALL25          N/A
Ethernet0  ALL26          N/A
Ethernet0  ALL27          N/A
Ethernet0  ALL28          N/A
Ethernet0  ALL29          N/A

For namespace :
     Port    TxQ    Trim/pkts
---------  -----  -----------
Ethernet4    UC0            0
Ethernet4    UC1          100
Ethernet4    UC2          N/A
Ethernet4    UC3          N/A
Ethernet4    UC4          N/A
Ethernet4    UC5          N/A
Ethernet4    UC6          N/A
Ethernet4    UC7          N/A
Ethernet4    UC8          N/A
Ethernet4    UC9          N/A
Ethernet4   MC10          N/A
Ethernet4   MC11          N/A
Ethernet4   MC12          N/A
Ethernet4   MC13          N/A
Ethernet4   MC14          N/A
Ethernet4   MC15          N/A
Ethernet4   MC16          N/A
Ethernet4   MC17          N/A
Ethernet4   MC18          N/A
Ethernet4   MC19          N/A
Ethernet4  ALL20          N/A
Ethernet4  ALL21          N/A
Ethernet4  ALL22          N/A
Ethernet4  ALL23          N/A
Ethernet4  ALL24          N/A
Ethernet4  ALL25          N/A
Ethernet4  ALL26          N/A
Ethernet4  ALL27          N/A
Ethernet4  ALL28          N/A
Ethernet4  ALL29          N/A

For namespace :
     Port    TxQ    Trim/pkts
---------  -----  -----------
Ethernet8    UC0            0
Ethernet8    UC1          100
Ethernet8    UC2          N/A
Ethernet8    UC3          N/A
Ethernet8    UC4          N/A
Ethernet8    UC5          N/A
Ethernet8    UC6          N/A
Ethernet8    UC7          N/A
Ethernet8    UC8          N/A
Ethernet8    UC9          N/A
Ethernet8   MC10          N/A
Ethernet8   MC11          N/A
Ethernet8   MC12          N/A
Ethernet8   MC13          N/A
Ethernet8   MC14          N/A
Ethernet8   MC15          N/A
Ethernet8   MC16          N/A
Ethernet8   MC17          N/A
Ethernet8   MC18          N/A
Ethernet8   MC19          N/A
Ethernet8  ALL20          N/A
Ethernet8  ALL21          N/A
Ethernet8  ALL22          N/A
Ethernet8  ALL23          N/A
Ethernet8  ALL24          N/A
Ethernet8  ALL25          N/A
Ethernet8  ALL26          N/A
Ethernet8  ALL27          N/A
Ethernet8  ALL28          N/A
Ethernet8  ALL29          N/A

"""
trim_counters_all_json="""\
{
  "Ethernet0": {
    "ALL20": {
      "trimpacket": "N/A"
    },
    "ALL21": {
      "trimpacket": "N/A"
    },
    "ALL22": {
      "trimpacket": "N/A"
    },
    "ALL23": {
      "trimpacket": "N/A"
    },
    "ALL24": {
      "trimpacket": "N/A"
    },
    "ALL25": {
      "trimpacket": "N/A"
    },
    "ALL26": {
      "trimpacket": "N/A"
    },
    "ALL27": {
      "trimpacket": "N/A"
    },
    "ALL28": {
      "trimpacket": "N/A"
    },
    "ALL29": {
      "trimpacket": "N/A"
    },
    "MC10": {
      "trimpacket": "N/A"
    },
    "MC11": {
      "trimpacket": "N/A"
    },
    "MC12": {
      "trimpacket": "N/A"
    },
    "MC13": {
      "trimpacket": "N/A"
    },
    "MC14": {
      "trimpacket": "N/A"
    },
    "MC15": {
      "trimpacket": "N/A"
    },
    "MC16": {
      "trimpacket": "N/A"
    },
    "MC17": {
      "trimpacket": "N/A"
    },
    "MC18": {
      "trimpacket": "N/A"
    },
    "MC19": {
      "trimpacket": "N/A"
    },
    "UC0": {
      "trimpacket": "0"
    },
    "UC1": {
      "trimpacket": "100"
    },
    "UC2": {
      "trimpacket": "N/A"
    },
    "UC3": {
      "trimpacket": "N/A"
    },
    "UC4": {
      "trimpacket": "N/A"
    },
    "UC5": {
      "trimpacket": "N/A"
    },
    "UC6": {
      "trimpacket": "N/A"
    },
    "UC7": {
      "trimpacket": "N/A"
    },
    "UC8": {
      "trimpacket": "N/A"
    },
    "UC9": {
      "trimpacket": "N/A"
    }
  },
  "Ethernet4": {
    "ALL20": {
      "trimpacket": "N/A"
    },
    "ALL21": {
      "trimpacket": "N/A"
    },
    "ALL22": {
      "trimpacket": "N/A"
    },
    "ALL23": {
      "trimpacket": "N/A"
    },
    "ALL24": {
      "trimpacket": "N/A"
    },
    "ALL25": {
      "trimpacket": "N/A"
    },
    "ALL26": {
      "trimpacket": "N/A"
    },
    "ALL27": {
      "trimpacket": "N/A"
    },
    "ALL28": {
      "trimpacket": "N/A"
    },
    "ALL29": {
      "trimpacket": "N/A"
    },
    "MC10": {
      "trimpacket": "N/A"
    },
    "MC11": {
      "trimpacket": "N/A"
    },
    "MC12": {
      "trimpacket": "N/A"
    },
    "MC13": {
      "trimpacket": "N/A"
    },
    "MC14": {
      "trimpacket": "N/A"
    },
    "MC15": {
      "trimpacket": "N/A"
    },
    "MC16": {
      "trimpacket": "N/A"
    },
    "MC17": {
      "trimpacket": "N/A"
    },
    "MC18": {
      "trimpacket": "N/A"
    },
    "MC19": {
      "trimpacket": "N/A"
    },
    "UC0": {
      "trimpacket": "0"
    },
    "UC1": {
      "trimpacket": "100"
    },
    "UC2": {
      "trimpacket": "N/A"
    },
    "UC3": {
      "trimpacket": "N/A"
    },
    "UC4": {
      "trimpacket": "N/A"
    },
    "UC5": {
      "trimpacket": "N/A"
    },
    "UC6": {
      "trimpacket": "N/A"
    },
    "UC7": {
      "trimpacket": "N/A"
    },
    "UC8": {
      "trimpacket": "N/A"
    },
    "UC9": {
      "trimpacket": "N/A"
    }
  },
  "Ethernet8": {
    "ALL20": {
      "trimpacket": "N/A"
    },
    "ALL21": {
      "trimpacket": "N/A"
    },
    "ALL22": {
      "trimpacket": "N/A"
    },
    "ALL23": {
      "trimpacket": "N/A"
    },
    "ALL24": {
      "trimpacket": "N/A"
    },
    "ALL25": {
      "trimpacket": "N/A"
    },
    "ALL26": {
      "trimpacket": "N/A"
    },
    "ALL27": {
      "trimpacket": "N/A"
    },
    "ALL28": {
      "trimpacket": "N/A"
    },
    "ALL29": {
      "trimpacket": "N/A"
    },
    "MC10": {
      "trimpacket": "N/A"
    },
    "MC11": {
      "trimpacket": "N/A"
    },
    "MC12": {
      "trimpacket": "N/A"
    },
    "MC13": {
      "trimpacket": "N/A"
    },
    "MC14": {
      "trimpacket": "N/A"
    },
    "MC15": {
      "trimpacket": "N/A"
    },
    "MC16": {
      "trimpacket": "N/A"
    },
    "MC17": {
      "trimpacket": "N/A"
    },
    "MC18": {
      "trimpacket": "N/A"
    },
    "MC19": {
      "trimpacket": "N/A"
    },
    "UC0": {
      "trimpacket": "0"
    },
    "UC1": {
      "trimpacket": "100"
    },
    "UC2": {
      "trimpacket": "N/A"
    },
    "UC3": {
      "trimpacket": "N/A"
    },
    "UC4": {
      "trimpacket": "N/A"
    },
    "UC5": {
      "trimpacket": "N/A"
    },
    "UC6": {
      "trimpacket": "N/A"
    },
    "UC7": {
      "trimpacket": "N/A"
    },
    "UC8": {
      "trimpacket": "N/A"
    },
    "UC9": {
      "trimpacket": "N/A"
    }
  }
}
"""

trim_eth0_counters="""\
For namespace :
     Port    TxQ    Trim/pkts
---------  -----  -----------
Ethernet0    UC0            0
Ethernet0    UC1          100
Ethernet0    UC2          N/A
Ethernet0    UC3          N/A
Ethernet0    UC4          N/A
Ethernet0    UC5          N/A
Ethernet0    UC6          N/A
Ethernet0    UC7          N/A
Ethernet0    UC8          N/A
Ethernet0    UC9          N/A
Ethernet0   MC10          N/A
Ethernet0   MC11          N/A
Ethernet0   MC12          N/A
Ethernet0   MC13          N/A
Ethernet0   MC14          N/A
Ethernet0   MC15          N/A
Ethernet0   MC16          N/A
Ethernet0   MC17          N/A
Ethernet0   MC18          N/A
Ethernet0   MC19          N/A
Ethernet0  ALL20          N/A
Ethernet0  ALL21          N/A
Ethernet0  ALL22          N/A
Ethernet0  ALL23          N/A
Ethernet0  ALL24          N/A
Ethernet0  ALL25          N/A
Ethernet0  ALL26          N/A
Ethernet0  ALL27          N/A
Ethernet0  ALL28          N/A
Ethernet0  ALL29          N/A

"""
trim_eth0_counters_json="""\
{
  "Ethernet0": {
    "ALL20": {
      "trimpacket": "N/A"
    },
    "ALL21": {
      "trimpacket": "N/A"
    },
    "ALL22": {
      "trimpacket": "N/A"
    },
    "ALL23": {
      "trimpacket": "N/A"
    },
    "ALL24": {
      "trimpacket": "N/A"
    },
    "ALL25": {
      "trimpacket": "N/A"
    },
    "ALL26": {
      "trimpacket": "N/A"
    },
    "ALL27": {
      "trimpacket": "N/A"
    },
    "ALL28": {
      "trimpacket": "N/A"
    },
    "ALL29": {
      "trimpacket": "N/A"
    },
    "MC10": {
      "trimpacket": "N/A"
    },
    "MC11": {
      "trimpacket": "N/A"
    },
    "MC12": {
      "trimpacket": "N/A"
    },
    "MC13": {
      "trimpacket": "N/A"
    },
    "MC14": {
      "trimpacket": "N/A"
    },
    "MC15": {
      "trimpacket": "N/A"
    },
    "MC16": {
      "trimpacket": "N/A"
    },
    "MC17": {
      "trimpacket": "N/A"
    },
    "MC18": {
      "trimpacket": "N/A"
    },
    "MC19": {
      "trimpacket": "N/A"
    },
    "UC0": {
      "trimpacket": "0"
    },
    "UC1": {
      "trimpacket": "100"
    },
    "UC2": {
      "trimpacket": "N/A"
    },
    "UC3": {
      "trimpacket": "N/A"
    },
    "UC4": {
      "trimpacket": "N/A"
    },
    "UC5": {
      "trimpacket": "N/A"
    },
    "UC6": {
      "trimpacket": "N/A"
    },
    "UC7": {
      "trimpacket": "N/A"
    },
    "UC8": {
      "trimpacket": "N/A"
    },
    "UC9": {
      "trimpacket": "N/A"
    }
  }
}
"""

trim_eth4_counters="""\
For namespace :
     Port    TxQ    Trim/pkts
---------  -----  -----------
Ethernet4    UC0            0
Ethernet4    UC1          100
Ethernet4    UC2          N/A
Ethernet4    UC3          N/A
Ethernet4    UC4          N/A
Ethernet4    UC5          N/A
Ethernet4    UC6          N/A
Ethernet4    UC7          N/A
Ethernet4    UC8          N/A
Ethernet4    UC9          N/A
Ethernet4   MC10          N/A
Ethernet4   MC11          N/A
Ethernet4   MC12          N/A
Ethernet4   MC13          N/A
Ethernet4   MC14          N/A
Ethernet4   MC15          N/A
Ethernet4   MC16          N/A
Ethernet4   MC17          N/A
Ethernet4   MC18          N/A
Ethernet4   MC19          N/A
Ethernet4  ALL20          N/A
Ethernet4  ALL21          N/A
Ethernet4  ALL22          N/A
Ethernet4  ALL23          N/A
Ethernet4  ALL24          N/A
Ethernet4  ALL25          N/A
Ethernet4  ALL26          N/A
Ethernet4  ALL27          N/A
Ethernet4  ALL28          N/A
Ethernet4  ALL29          N/A

"""
trim_eth4_counters_json="""\
{
  "Ethernet4": {
    "ALL20": {
      "trimpacket": "N/A"
    },
    "ALL21": {
      "trimpacket": "N/A"
    },
    "ALL22": {
      "trimpacket": "N/A"
    },
    "ALL23": {
      "trimpacket": "N/A"
    },
    "ALL24": {
      "trimpacket": "N/A"
    },
    "ALL25": {
      "trimpacket": "N/A"
    },
    "ALL26": {
      "trimpacket": "N/A"
    },
    "ALL27": {
      "trimpacket": "N/A"
    },
    "ALL28": {
      "trimpacket": "N/A"
    },
    "ALL29": {
      "trimpacket": "N/A"
    },
    "MC10": {
      "trimpacket": "N/A"
    },
    "MC11": {
      "trimpacket": "N/A"
    },
    "MC12": {
      "trimpacket": "N/A"
    },
    "MC13": {
      "trimpacket": "N/A"
    },
    "MC14": {
      "trimpacket": "N/A"
    },
    "MC15": {
      "trimpacket": "N/A"
    },
    "MC16": {
      "trimpacket": "N/A"
    },
    "MC17": {
      "trimpacket": "N/A"
    },
    "MC18": {
      "trimpacket": "N/A"
    },
    "MC19": {
      "trimpacket": "N/A"
    },
    "UC0": {
      "trimpacket": "0"
    },
    "UC1": {
      "trimpacket": "100"
    },
    "UC2": {
      "trimpacket": "N/A"
    },
    "UC3": {
      "trimpacket": "N/A"
    },
    "UC4": {
      "trimpacket": "N/A"
    },
    "UC5": {
      "trimpacket": "N/A"
    },
    "UC6": {
      "trimpacket": "N/A"
    },
    "UC7": {
      "trimpacket": "N/A"
    },
    "UC8": {
      "trimpacket": "N/A"
    },
    "UC9": {
      "trimpacket": "N/A"
    }
  }
}
"""

trim_eth8_counters="""\
For namespace :
     Port    TxQ    Trim/pkts
---------  -----  -----------
Ethernet8    UC0            0
Ethernet8    UC1          100
Ethernet8    UC2          N/A
Ethernet8    UC3          N/A
Ethernet8    UC4          N/A
Ethernet8    UC5          N/A
Ethernet8    UC6          N/A
Ethernet8    UC7          N/A
Ethernet8    UC8          N/A
Ethernet8    UC9          N/A
Ethernet8   MC10          N/A
Ethernet8   MC11          N/A
Ethernet8   MC12          N/A
Ethernet8   MC13          N/A
Ethernet8   MC14          N/A
Ethernet8   MC15          N/A
Ethernet8   MC16          N/A
Ethernet8   MC17          N/A
Ethernet8   MC18          N/A
Ethernet8   MC19          N/A
Ethernet8  ALL20          N/A
Ethernet8  ALL21          N/A
Ethernet8  ALL22          N/A
Ethernet8  ALL23          N/A
Ethernet8  ALL24          N/A
Ethernet8  ALL25          N/A
Ethernet8  ALL26          N/A
Ethernet8  ALL27          N/A
Ethernet8  ALL28          N/A
Ethernet8  ALL29          N/A

"""
trim_eth8_counters_json="""\
{
  "Ethernet8": {
    "ALL20": {
      "trimpacket": "N/A"
    },
    "ALL21": {
      "trimpacket": "N/A"
    },
    "ALL22": {
      "trimpacket": "N/A"
    },
    "ALL23": {
      "trimpacket": "N/A"
    },
    "ALL24": {
      "trimpacket": "N/A"
    },
    "ALL25": {
      "trimpacket": "N/A"
    },
    "ALL26": {
      "trimpacket": "N/A"
    },
    "ALL27": {
      "trimpacket": "N/A"
    },
    "ALL28": {
      "trimpacket": "N/A"
    },
    "ALL29": {
      "trimpacket": "N/A"
    },
    "MC10": {
      "trimpacket": "N/A"
    },
    "MC11": {
      "trimpacket": "N/A"
    },
    "MC12": {
      "trimpacket": "N/A"
    },
    "MC13": {
      "trimpacket": "N/A"
    },
    "MC14": {
      "trimpacket": "N/A"
    },
    "MC15": {
      "trimpacket": "N/A"
    },
    "MC16": {
      "trimpacket": "N/A"
    },
    "MC17": {
      "trimpacket": "N/A"
    },
    "MC18": {
      "trimpacket": "N/A"
    },
    "MC19": {
      "trimpacket": "N/A"
    },
    "UC0": {
      "trimpacket": "0"
    },
    "UC1": {
      "trimpacket": "100"
    },
    "UC2": {
      "trimpacket": "N/A"
    },
    "UC3": {
      "trimpacket": "N/A"
    },
    "UC4": {
      "trimpacket": "N/A"
    },
    "UC5": {
      "trimpacket": "N/A"
    },
    "UC6": {
      "trimpacket": "N/A"
    },
    "UC7": {
      "trimpacket": "N/A"
    },
    "UC8": {
      "trimpacket": "N/A"
    },
    "UC9": {
      "trimpacket": "N/A"
    }
  }
}
"""

trim_counters_clear_msg="""\
Clear and update saved counters for Ethernet0
Clear and update saved counters for Ethernet4
Clear and update saved counters for Ethernet8
"""
trim_counters_clear_stat="""\
     Port    TxQ    Trim/pkts
---------  -----  -----------
Ethernet0    UC0            0
Ethernet0    UC1            0
Ethernet0    UC2          N/A
Ethernet0    UC3          N/A
Ethernet0    UC4          N/A
Ethernet0    UC5          N/A
Ethernet0    UC6          N/A
Ethernet0    UC7          N/A
Ethernet0    UC8          N/A
Ethernet0    UC9          N/A
Ethernet0   MC10          N/A
Ethernet0   MC11          N/A
Ethernet0   MC12          N/A
Ethernet0   MC13          N/A
Ethernet0   MC14          N/A
Ethernet0   MC15          N/A
Ethernet0   MC16          N/A
Ethernet0   MC17          N/A
Ethernet0   MC18          N/A
Ethernet0   MC19          N/A
Ethernet0  ALL20          N/A
Ethernet0  ALL21          N/A
Ethernet0  ALL22          N/A
Ethernet0  ALL23          N/A
Ethernet0  ALL24          N/A
Ethernet0  ALL25          N/A
Ethernet0  ALL26          N/A
Ethernet0  ALL27          N/A
Ethernet0  ALL28          N/A
Ethernet0  ALL29          N/A

     Port    TxQ    Trim/pkts
---------  -----  -----------
Ethernet4    UC0            0
Ethernet4    UC1            0
Ethernet4    UC2          N/A
Ethernet4    UC3          N/A
Ethernet4    UC4          N/A
Ethernet4    UC5          N/A
Ethernet4    UC6          N/A
Ethernet4    UC7          N/A
Ethernet4    UC8          N/A
Ethernet4    UC9          N/A
Ethernet4   MC10          N/A
Ethernet4   MC11          N/A
Ethernet4   MC12          N/A
Ethernet4   MC13          N/A
Ethernet4   MC14          N/A
Ethernet4   MC15          N/A
Ethernet4   MC16          N/A
Ethernet4   MC17          N/A
Ethernet4   MC18          N/A
Ethernet4   MC19          N/A
Ethernet4  ALL20          N/A
Ethernet4  ALL21          N/A
Ethernet4  ALL22          N/A
Ethernet4  ALL23          N/A
Ethernet4  ALL24          N/A
Ethernet4  ALL25          N/A
Ethernet4  ALL26          N/A
Ethernet4  ALL27          N/A
Ethernet4  ALL28          N/A
Ethernet4  ALL29          N/A

     Port    TxQ    Trim/pkts
---------  -----  -----------
Ethernet8    UC0            0
Ethernet8    UC1            0
Ethernet8    UC2          N/A
Ethernet8    UC3          N/A
Ethernet8    UC4          N/A
Ethernet8    UC5          N/A
Ethernet8    UC6          N/A
Ethernet8    UC7          N/A
Ethernet8    UC8          N/A
Ethernet8    UC9          N/A
Ethernet8   MC10          N/A
Ethernet8   MC11          N/A
Ethernet8   MC12          N/A
Ethernet8   MC13          N/A
Ethernet8   MC14          N/A
Ethernet8   MC15          N/A
Ethernet8   MC16          N/A
Ethernet8   MC17          N/A
Ethernet8   MC18          N/A
Ethernet8   MC19          N/A
Ethernet8  ALL20          N/A
Ethernet8  ALL21          N/A
Ethernet8  ALL22          N/A
Ethernet8  ALL23          N/A
Ethernet8  ALL24          N/A
Ethernet8  ALL25          N/A
Ethernet8  ALL26          N/A
Ethernet8  ALL27          N/A
Ethernet8  ALL28          N/A
Ethernet8  ALL29          N/A
"""

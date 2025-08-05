pfcwd_show_config_output="""\
Changed polling interval to 600ms
     PORT    ACTION    DETECTION TIME    RESTORATION TIME    HISTORY
---------  --------  ----------------  ------------------  ---------
Ethernet0      drop               600                 600    disable
Ethernet4      drop               600                 600    disable
Ethernet8      drop               600                 600    disable
"""

pfcwd_show_start_config_output_pass = """\
Changed polling interval to 600ms
     PORT    ACTION    DETECTION TIME    RESTORATION TIME    HISTORY
---------  --------  ----------------  ------------------  ---------
Ethernet0   forward               102                 101    disable
Ethernet4      drop               600                 600    disable
Ethernet8      drop               600                 600    disable
"""

pfcwd_show_enable_history_config_output_pass = """\
Changed polling interval to 600ms
     PORT    ACTION    DETECTION TIME    RESTORATION TIME    HISTORY
---------  --------  ----------------  ------------------  ---------
Ethernet0      drop               600                 600     enable
Ethernet4      drop               600                 600    disable
Ethernet8      drop               600                 600    disable
"""

pfcwd_show_start_action_forward_output = """\
Changed polling interval to 600ms
     PORT    ACTION    DETECTION TIME    RESTORATION TIME    HISTORY
---------  --------  ----------------  ------------------  ---------
Ethernet0   forward               302                 301    disable
Ethernet4   forward               302                 301    disable
Ethernet8      drop               600                 600    disable
"""

pfcwd_show_start_action_alert_output = """\
Changed polling interval to 600ms
     PORT    ACTION    DETECTION TIME    RESTORATION TIME    HISTORY
---------  --------  ----------------  ------------------  ---------
Ethernet0     alert               502                 501    disable
Ethernet4     alert               502                 501    disable
Ethernet8      drop               600                 600    disable
"""

pfcwd_show_start_action_drop_output = """\
Changed polling interval to 600ms
     PORT    ACTION    DETECTION TIME    RESTORATION TIME    HISTORY
---------  --------  ----------------  ------------------  ---------
Ethernet0      drop               602                 601    disable
Ethernet4      drop               602                 601    disable
Ethernet8      drop               600                 600    disable
"""

pfcwd_show_start_default = """\
Changed polling interval to 200ms
     PORT    ACTION    DETECTION TIME    RESTORATION TIME    HISTORY
---------  --------  ----------------  ------------------  ---------
Ethernet0      drop               200                 200    disable
Ethernet4      drop               200                 200    disable
Ethernet8      drop               600                 600    disable
"""

pfcwd_show_start_history_output = """\
Changed polling interval to 600ms
     PORT    ACTION    DETECTION TIME    RESTORATION TIME    HISTORY
---------  --------  ----------------  ------------------  ---------
Ethernet0      drop               600                 601     enable
Ethernet4      drop               600                 601     enable
Ethernet8      drop               600                 600    disable
"""

show_pfc_config_invalid_options_fail = """\
Failed to run command, invalid options:
Ethernet1000
"""

pfcwd_show_config_single_port_output="""\
Changed polling interval to 600ms
     PORT    ACTION    DETECTION TIME    RESTORATION TIME    HISTORY
---------  --------  ----------------  ------------------  ---------
Ethernet0      drop               600                 600    disable
"""

pfcwd_show_config_multi_port_output="""\
Changed polling interval to 600ms
     PORT    ACTION    DETECTION TIME    RESTORATION TIME    HISTORY
---------  --------  ----------------  ------------------  ---------
Ethernet0      drop               600                 600    disable
Ethernet4      drop               600                 600    disable
"""

pfcwd_show_config_invalid_port_output="""\
  PORT    ACTION    DETECTION TIME    RESTORATION TIME    HISTORY
------  --------  ----------------  ------------------  ---------
"""

pfcwd_show_stats_output="""\
      QUEUE       STATUS    STORM DETECTED/RESTORED    TX OK/DROP    RX OK/DROP    TX LAST OK/DROP    RX LAST OK/DROP
-----------  -----------  -------------------------  ------------  ------------  -----------------  -----------------
Ethernet0:3      stormed                        1/0       100/300       100/300              0/200              0/200
Ethernet4:3  operational                        2/2       100/100       100/100                0/0                0/0
Ethernet8:4      stormed                        3/2       100/300       100/300              0/200              0/200
"""

pfcwd_show_stats_single_queue_output="""\
      QUEUE    STATUS    STORM DETECTED/RESTORED    TX OK/DROP    RX OK/DROP    TX LAST OK/DROP    RX LAST OK/DROP
-----------  --------  -------------------------  ------------  ------------  -----------------  -----------------
Ethernet0:3   stormed                        1/0       100/300       100/300              0/200              0/200
"""

pfcwd_show_stats_multi_queue_output="""\
      QUEUE       STATUS    STORM DETECTED/RESTORED    TX OK/DROP    RX OK/DROP    TX LAST OK/DROP    RX LAST OK/DROP
-----------  -----------  -------------------------  ------------  ------------  -----------------  -----------------
Ethernet0:3      stormed                        1/0       100/300       100/300              0/200              0/200
Ethernet4:3  operational                        2/2       100/100       100/100                0/0                0/0
"""

pfcwd_show_stats_invalid_queue_output="""\
  QUEUE    STATUS    STORM DETECTED/RESTORED    TX OK/DROP    RX OK/DROP    TX LAST OK/DROP    RX LAST OK/DROP
-------  --------  -------------------------  ------------  ------------  -----------------  -----------------
"""

pfc_is_not_enabled = "SKIPPED: PFC is not enabled on port: Ethernet8\n"
pfc_is_not_enabled_masic = "SKIPPED: PFC is not enabled on port: Ethernet-BP260\n"

testData = {
             'pfcwd_show_config' :  [ {'cmd' : ['show', 'config'],
                                       'args': [],
                                       'rc': 0,
                                       'rc_output': pfcwd_show_config_output
                                      }
                                    ],
             'pfcwd_show_config_single_port' :  [ {'cmd' : ['show', 'config'],
                                       'args': ['Ethernet0'],
                                       'rc': 0,
                                       'rc_output': pfcwd_show_config_single_port_output
                                      }
                                    ],
             'pfcwd_show_config_multi_port' :  [ {'cmd' : ['show', 'config'],
                                       'args': ['Ethernet0', 'Ethernet4'],
                                       'rc': 0,
                                       'rc_output': pfcwd_show_config_multi_port_output
                                      }
                                    ],
             'pfcwd_show_config_invalid_port' :  [ {'cmd' : ['show', 'config'],
                                       'args': ['Ethernet400'],
                                       'rc': 0,
                                       'rc_output': pfcwd_show_config_invalid_port_output
                                      }
                                    ],
             'pfcwd_show_stats' :  [ {'cmd' : ['show', 'stats'],
                                      'args': [],
                                      'rc': 0,
                                      'rc_output': pfcwd_show_stats_output
                                      }
                                    ],
             'pfcwd_show_stats_single_queue' :  [ {'cmd' : ['show', 'stats'],
                                                   'args': ['Ethernet0:3'],
                                                   'rc': 0,
                                                   'rc_output': pfcwd_show_stats_single_queue_output
                                                  }
                                                ],
             'pfcwd_show_stats_multi_queue' :  [ {'cmd' : ['show', 'stats'],
                                                  'args': ['Ethernet0:3', 'Ethernet4:3'],
                                                  'rc': 0,
                                                  'rc_output': pfcwd_show_stats_multi_queue_output
                                                 }
                                               ],
             'pfcwd_show_stats_invalid_queue' :  [ {'cmd' : ['show', 'stats'],
                                                    'args': ['Ethernet0:100'],
                                                    'rc': 0,
                                                    'rc_output': pfcwd_show_stats_invalid_queue_output
                                                   }
                                                 ]
           }

""" Multi ASIC show command output """

show_pfcwd_stats_all = """\
            QUEUE    STATUS    STORM DETECTED/RESTORED    TX OK/DROP    RX OK/DROP    TX LAST OK/DROP    RX LAST OK/DROP
-----------------  --------  -------------------------  ------------  ------------  -----------------  -----------------
      Ethernet0:0       N/A                        0/0       5871/11       4740/47              499/2            7886/13
      Ethernet0:1       N/A                        0/1        724/13        8548/2              226/5            8318/92
      Ethernet0:2       N/A                        1/0       3307/99       8919/20              999/0            9885/99
      Ethernet0:3       N/A                        0/1        8814/0       1757/49              470/5            9734/35
      Ethernet0:4       N/A                        0/0       8245/25       1954/26              880/1            8957/10
      Ethernet0:5       N/A                        1/0       6730/99       5743/97              633/8            9538/54
      Ethernet0:6       N/A                        0/1         74/72       3683/59              934/6            1060/53
      Ethernet0:7       N/A                        0/1       8805/95       4224/85              216/7             4283/0
      Ethernet0:8       N/A                        1/0       1530/16       9282/62              235/6            3256/22
      Ethernet0:9       N/A                        0/1       3041/68       4391/86              172/9            8458/35
     Ethernet0:10       N/A                        0/1       5356/70       2716/68              360/1            1394/13
     Ethernet0:11       N/A                        1/1       5114/68       8389/23              777/4            8694/34
     Ethernet0:12       N/A                        0/0       8759/98       8378/75              444/4            6390/11
     Ethernet0:13       N/A                        0/0        9133/6       8308/65              496/5            3181/96
     Ethernet0:14       N/A                        0/0       1819/34       7127/42              126/1             487/69
     Ethernet0:15       N/A                        1/0       8152/34       3690/68              347/6            2844/88
      Ethernet4:0       N/A                        1/1       1960/67       3987/77              997/3            4406/93
      Ethernet4:1       N/A                        0/1       1880/83       8205/56              560/7            4320/95
      Ethernet4:2       N/A                        0/1       7068/13       8087/35              196/2             150/56
      Ethernet4:3       N/A                        1/0       1659/31       6912/79              515/3            5525/57
      Ethernet4:4       N/A                        1/1       5010/55       7553/13              995/6            9133/46
      Ethernet4:5       N/A                        0/1       5746/92       8459/74               30/8             1972/4
      Ethernet4:6       N/A                        1/1       3919/76        649/35              908/3            6804/10
      Ethernet4:7       N/A                        1/1       3089/56       9521/83              875/0            2979/48
      Ethernet4:8       N/A                        1/0       8636/72       9950/76               67/2             4005/8
      Ethernet4:9       N/A                        0/0       6259/80       7033/96              226/8            1732/86
     Ethernet4:10       N/A                        0/0       4585/17        3176/7              567/5            9822/32
     Ethernet4:11       N/A                        0/0       8590/76       7472/64              527/7             2772/1
     Ethernet4:12       N/A                        0/1       5447/25       7670/60              537/4            4423/30
     Ethernet4:13       N/A                        0/0        485/17         458/1              364/3            6280/94
     Ethernet4:14       N/A                        1/1       8894/21       6258/57               69/8            5812/39
     Ethernet4:15       N/A                        0/1       8073/38       2374/96              115/8             7589/9
   Ethernet-BP0:0       N/A                        0/0       5380/14       6152/83              719/9            7806/73
   Ethernet-BP0:1       N/A                        1/1       9206/77       2276/35              737/4            6904/71
   Ethernet-BP0:2       N/A                        1/0       9789/96       3424/34              946/9            7498/13
   Ethernet-BP0:3       N/A                        0/1         640/9        5797/4                5/0            1876/43
   Ethernet-BP0:4       N/A                        1/0       6613/67        849/73              648/8            1599/78
   Ethernet-BP0:5       N/A                        0/1        7360/2       7571/21              127/8            2939/48
   Ethernet-BP0:6       N/A                        0/1       9634/51       7451/76              940/0            3828/20
   Ethernet-BP0:7       N/A                        1/0       1435/95       8539/54              685/9            9058/54
   Ethernet-BP0:8       N/A                        0/0        695/68        8592/5              181/4            4963/85
   Ethernet-BP0:9       N/A                        0/1       6729/15       7587/66              359/8            5498/36
  Ethernet-BP0:10       N/A                        0/0       6733/76        3287/6              902/0            8748/26
  Ethernet-BP0:11       N/A                        1/1       1394/51        988/15              116/4            8272/94
  Ethernet-BP0:12       N/A                        0/1       5088/71        373/19               74/8             5817/0
  Ethernet-BP0:13       N/A                        1/0       6203/97       6916/49              253/4            4833/65
  Ethernet-BP0:14       N/A                        0/0       1970/26       6055/83              573/5            2860/48
  Ethernet-BP0:15       N/A                        0/1       4331/30       6559/27              230/4            6469/50
   Ethernet-BP4:0       N/A                        0/1       3836/77        891/99              962/2            3473/45
   Ethernet-BP4:1       N/A                        0/0       3922/54       4771/10              788/8            8089/15
   Ethernet-BP4:2       N/A                        0/0        972/34       6501/56              413/3             9569/8
   Ethernet-BP4:3       N/A                        0/0       4753/76       4747/60              701/7            8669/96
   Ethernet-BP4:4       N/A                        0/0        4486/8       5426/25              860/4            3633/92
   Ethernet-BP4:5       N/A                        1/1       1848/39       1624/78               45/8            5074/10
   Ethernet-BP4:6       N/A                        1/1       3999/71       7447/15                6/7            3372/93
   Ethernet-BP4:7       N/A                        1/1       6653/11       1168/90              440/1             1084/7
   Ethernet-BP4:8       N/A                        1/0       3865/47       7067/53              281/1            5858/45
   Ethernet-BP4:9       N/A                        0/0       5094/92       6991/96              636/8            1734/63
  Ethernet-BP4:10       N/A                        0/1       9421/50       9647/44              625/7             3991/1
  Ethernet-BP4:11       N/A                        1/1       9667/70       3847/79              778/0             133/29
  Ethernet-BP4:12       N/A                        1/0       4691/26       7944/34              573/7            6631/57
  Ethernet-BP4:13       N/A                        0/1       8728/32       5931/39              768/1            9010/41
  Ethernet-BP4:14       N/A                        0/1       2668/54       8344/63              288/1            4343/60
  Ethernet-BP4:15       N/A                        0/1       9808/12        6644/2              758/7             7599/8
 Ethernet-BP256:0       N/A                        0/1       5844/42       7126/54              286/1            8381/53
 Ethernet-BP256:1       N/A                        1/0       1926/34       4091/88              421/8             858/11
 Ethernet-BP256:2       N/A                        1/0       1140/80       6288/71              962/9            4965/15
 Ethernet-BP256:3       N/A                        1/0       3774/65       5501/86              327/5            2963/25
 Ethernet-BP256:4       N/A                        1/0       9515/34        682/62              601/9            6934/59
 Ethernet-BP256:5       N/A                        1/0       5953/12         47/21              129/2            3149/85
 Ethernet-BP256:6       N/A                        1/1       2419/61       4296/53              132/9              447/1
 Ethernet-BP256:7       N/A                        1/0       1194/96       5915/41              418/0            2540/60
 Ethernet-BP256:8       N/A                        0/1       7366/36       6813/41              342/3            8365/84
 Ethernet-BP256:9       N/A                        0/1       3419/18       6963/36              113/3            2178/39
Ethernet-BP256:10       N/A                        1/0       4559/78       8647/85                6/5            9111/92
Ethernet-BP256:11       N/A                        0/0       6226/95       5515/94              377/1            1879/61
Ethernet-BP256:12       N/A                        1/1       5660/10       9653/88               69/3            6656/59
Ethernet-BP256:13       N/A                        0/1       3522/10        106/19              114/6            4592/40
Ethernet-BP256:14       N/A                        0/1       3252/68       6306/55               78/7            7846/99
Ethernet-BP256:15       N/A                        1/0        968/15       8387/98               15/2            6495/35
 Ethernet-BP260:0       N/A                        1/0       2030/40       6262/29              922/2            4880/84
 Ethernet-BP260:1       N/A                        0/1        935/94       8236/44              139/0             3945/6
 Ethernet-BP260:2       N/A                        0/0       3989/29       4700/54              250/3            5431/27
 Ethernet-BP260:3       N/A                        0/0       8774/59       5977/88              853/6             123/22
 Ethernet-BP260:4       N/A                        1/1       3289/58       8762/40              509/9            5097/75
 Ethernet-BP260:5       N/A                        1/0       3083/84       1933/90              818/8             590/24
 Ethernet-BP260:6       N/A                        1/0       1460/71        5827/5              775/5            9836/77
 Ethernet-BP260:7       N/A                        0/1       7692/28        3935/8              299/3            2368/75
 Ethernet-BP260:8       N/A                        1/1       7370/87       6133/16              581/1            7944/62
 Ethernet-BP260:9       N/A                        1/1       5719/87       1561/11              235/1            4054/49
Ethernet-BP260:10       N/A                        1/0        6526/9       5217/26              260/4            9338/69
Ethernet-BP260:11       N/A                        1/1       5615/81       9506/12              185/5            9902/28
Ethernet-BP260:12       N/A                        1/1         76/28       4344/45              532/7            8590/69
Ethernet-BP260:13       N/A                        0/1       3839/80       8143/47              601/7             575/97
Ethernet-BP260:14       N/A                        1/1       3787/72        9865/4              493/6             537/95
Ethernet-BP260:15       N/A                        0/1       6803/57        804/71              104/3            8343/72
"""

show_pfc_config_all = """\
Changed polling interval to 199ms on asic0
BIG_RED_SWITCH status is enable on asic0
Changed polling interval to 199ms on asic1
BIG_RED_SWITCH status is enable on asic1
          PORT    ACTION    DETECTION TIME    RESTORATION TIME    HISTORY
--------------  --------  ----------------  ------------------  ---------
     Ethernet0      drop               200                 200    disable
     Ethernet4      drop               200                 200    disable
  Ethernet-BP0      drop               200                 200    disable
  Ethernet-BP4      drop               200                 200    disable
Ethernet-BP256      drop               200                 200    disable
Ethernet-BP260      drop               200                 200    disable
"""

show_pfc_config_start_pass = """\
Changed polling interval to 199ms on asic0
BIG_RED_SWITCH status is enable on asic0
Changed polling interval to 199ms on asic1
BIG_RED_SWITCH status is enable on asic1
          PORT    ACTION    DETECTION TIME    RESTORATION TIME    HISTORY
--------------  --------  ----------------  ------------------  ---------
     Ethernet0   forward               102                 101    disable
     Ethernet4      drop               200                 200    disable
  Ethernet-BP0      drop               200                 200    disable
  Ethernet-BP4   forward               102                 101    disable
Ethernet-BP256      drop               200                 200    disable
Ethernet-BP260      drop               200                 200    disable
"""

show_pfc_config_enable_history_pass = """\
Changed polling interval to 199ms on asic0
BIG_RED_SWITCH status is enable on asic0
Changed polling interval to 199ms on asic1
BIG_RED_SWITCH status is enable on asic1
          PORT    ACTION    DETECTION TIME    RESTORATION TIME    HISTORY
--------------  --------  ----------------  ------------------  ---------
     Ethernet0      drop               200                 200     enable
     Ethernet4      drop               200                 200    disable
  Ethernet-BP0      drop               200                 200    disable
  Ethernet-BP4      drop               200                 200     enable
Ethernet-BP256      drop               200                 200    disable
Ethernet-BP260      drop               200                 200    disable
"""

show_pfc_config_start_action_drop_masic = """\
Changed polling interval to 199ms on asic0
BIG_RED_SWITCH status is enable on asic0
Changed polling interval to 199ms on asic1
BIG_RED_SWITCH status is enable on asic1
          PORT    ACTION    DETECTION TIME    RESTORATION TIME    HISTORY
--------------  --------  ----------------  ------------------  ---------
     Ethernet0      drop               302                 301    disable
     Ethernet4      drop               302                 301    disable
  Ethernet-BP0      drop               302                 301    disable
  Ethernet-BP4      drop               302                 301    disable
Ethernet-BP256      drop               302                 301    disable
Ethernet-BP260      drop               200                 200    disable
"""

show_pfc_config_start_action_alert_masic = """\
Changed polling interval to 199ms on asic0
BIG_RED_SWITCH status is enable on asic0
Changed polling interval to 199ms on asic1
BIG_RED_SWITCH status is enable on asic1
          PORT    ACTION    DETECTION TIME    RESTORATION TIME    HISTORY
--------------  --------  ----------------  ------------------  ---------
     Ethernet0     alert               402                 401    disable
     Ethernet4     alert               402                 401    disable
  Ethernet-BP0     alert               402                 401    disable
  Ethernet-BP4     alert               402                 401    disable
Ethernet-BP256     alert               402                 401    disable
Ethernet-BP260      drop               200                 200    disable
"""

show_pfc_config_start_action_forward_masic = """\
Changed polling interval to 199ms on asic0
BIG_RED_SWITCH status is enable on asic0
Changed polling interval to 199ms on asic1
BIG_RED_SWITCH status is enable on asic1
          PORT    ACTION    DETECTION TIME    RESTORATION TIME    HISTORY
--------------  --------  ----------------  ------------------  ---------
     Ethernet0   forward               702                 701    disable
     Ethernet4   forward               702                 701    disable
  Ethernet-BP0   forward               702                 701    disable
  Ethernet-BP4   forward               702                 701    disable
Ethernet-BP256   forward               702                 701    disable
Ethernet-BP260      drop               200                 200    disable
"""

pfcwd_show_start_history_output_masic = """\
Changed polling interval to 199ms on asic0
BIG_RED_SWITCH status is enable on asic0
Changed polling interval to 199ms on asic1
BIG_RED_SWITCH status is enable on asic1
          PORT    ACTION    DETECTION TIME    RESTORATION TIME    HISTORY
--------------  --------  ----------------  ------------------  ---------
     Ethernet0      drop               600                 601     enable
     Ethernet4      drop               600                 601     enable
  Ethernet-BP0      drop               600                 601     enable
  Ethernet-BP4      drop               600                 601     enable
Ethernet-BP256      drop               600                 601     enable
Ethernet-BP260      drop               200                 200    disable
"""

show_pfc_config_invalid_options_fail_masic = """\
Failed to run command, invalid options:
Ethernet-500
"""

show_pfcwd_stats_with_queues = """\
            QUEUE    STATUS    STORM DETECTED/RESTORED    TX OK/DROP    RX OK/DROP    TX LAST OK/DROP    RX LAST OK/DROP
-----------------  --------  -------------------------  ------------  ------------  -----------------  -----------------
      Ethernet0:3       N/A                        0/1        8814/0       1757/49              470/5            9734/35
     Ethernet4:15       N/A                        0/1       8073/38       2374/96              115/8             7589/9
  Ethernet-BP0:13       N/A                        1/0       6203/97       6916/49              253/4            4833/65
Ethernet-BP260:10       N/A                        1/0        6526/9       5217/26              260/4            9338/69
"""

show_pfcwd_config_with_ports = """\
Changed polling interval to 199ms on asic0
BIG_RED_SWITCH status is enable on asic0
Changed polling interval to 199ms on asic1
BIG_RED_SWITCH status is enable on asic1
          PORT    ACTION    DETECTION TIME    RESTORATION TIME    HISTORY
--------------  --------  ----------------  ------------------  ---------
     Ethernet0      drop               200                 200    disable
  Ethernet-BP0      drop               200                 200    disable
Ethernet-BP256      drop               200                 200    disable
"""

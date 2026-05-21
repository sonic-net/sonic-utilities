# flake8: noqa: E501

show_pfc_counters_history_output = """\
     Port    Priority    RX Pause Transitions    Total RX Pause Time US    Recent RX Pause Time US    Recent RX Pause Timestamp
---------  ----------  ----------------------  ------------------------  -------------------------  ---------------------------
Ethernet0        PFC0                      12                12,000,000                  1,200,000         01/10/2008, 21:20:00
Ethernet0        PFC1                      21                20,000,001                  2,000,001         05/18/2033, 03:33:20
Ethernet0        PFC2                      22                20,000,002                  2,000,002         05/18/2033, 03:33:20
Ethernet0        PFC3                      23                20,000,003                  2,000,003         05/18/2033, 03:33:20
Ethernet0        PFC4                      24                20,000,004                  2,000,004         05/18/2033, 03:33:20
Ethernet0        PFC5                      25                20,000,005                  2,000,005         05/18/2033, 03:33:20
Ethernet0        PFC6                      26                20,000,006                  2,000,006         05/18/2033, 03:33:20
Ethernet0        PFC7                      27                20,000,007                  2,000,007         05/18/2033, 03:33:20

Ethernet4        PFC0                      14                14,000,000                  1,400,000         05/13/2014, 16:53:20
Ethernet4        PFC1                      41                40,000,001                  4,000,001         10/02/2096, 07:06:40
Ethernet4        PFC2                      42                40,000,002                  4,000,002         10/02/2096, 07:06:40
Ethernet4        PFC3                      43                40,000,003                  4,000,003         10/02/2096, 07:06:40
Ethernet4        PFC4                      44                40,000,004                  4,000,004         10/02/2096, 07:06:40
Ethernet4        PFC5                      45                40,000,005                  4,000,005         10/02/2096, 07:06:40
Ethernet4        PFC6                      46                40,000,006                  4,000,006         10/02/2096, 07:06:40
Ethernet4        PFC7                      47                40,000,007                  4,000,007         10/02/2096, 07:06:40

Ethernet8        PFC0                      18                18,000,000                  1,800,000         01/15/2027, 08:00:00
Ethernet8        PFC1                      81                80,000,001                  8,000,001         07/06/2223, 14:13:20
Ethernet8        PFC2                      82                80,000,002                  8,000,002         07/06/2223, 14:13:20
Ethernet8        PFC3                      83                80,000,003                  8,000,003         07/06/2223, 14:13:20
Ethernet8        PFC4                      84                80,000,004                  8,000,004         07/06/2223, 14:13:20
Ethernet8        PFC5                      85                80,000,005                  8,000,005         07/06/2223, 14:13:20
Ethernet8        PFC6                      86                80,000,006                  8,000,006         07/06/2223, 14:13:20
Ethernet8        PFC7                      87                80,000,007                  8,000,007         07/06/2223, 14:13:20

"""

show_pfc_counters_history_output_with_clear = """\
     Port    Priority    RX Pause Transitions    Total RX Pause Time US    Recent RX Pause Time US    Recent RX Pause Timestamp
---------  ----------  ----------------------  ------------------------  -------------------------  ---------------------------
Ethernet0        PFC0                       0                         0                  1,200,000         01/10/2008, 21:20:00
Ethernet0        PFC1                       0                         0                  2,000,001         05/18/2033, 03:33:20
Ethernet0        PFC2                       0                         0                  2,000,002         05/18/2033, 03:33:20
Ethernet0        PFC3                       0                         0                  2,000,003         05/18/2033, 03:33:20
Ethernet0        PFC4                       0                         0                  2,000,004         05/18/2033, 03:33:20
Ethernet0        PFC5                       0                         0                  2,000,005         05/18/2033, 03:33:20
Ethernet0        PFC6                       0                         0                  2,000,006         05/18/2033, 03:33:20
Ethernet0        PFC7                       0                         0                  2,000,007         05/18/2033, 03:33:20

Ethernet4        PFC0                       0                         0                  1,400,000         05/13/2014, 16:53:20
Ethernet4        PFC1                       0                         0                  4,000,001         10/02/2096, 07:06:40
Ethernet4        PFC2                       0                         0                  4,000,002         10/02/2096, 07:06:40
Ethernet4        PFC3                       0                         0                  4,000,003         10/02/2096, 07:06:40
Ethernet4        PFC4                       0                         0                  4,000,004         10/02/2096, 07:06:40
Ethernet4        PFC5                       0                         0                  4,000,005         10/02/2096, 07:06:40
Ethernet4        PFC6                       0                         0                  4,000,006         10/02/2096, 07:06:40
Ethernet4        PFC7                       0                         0                  4,000,007         10/02/2096, 07:06:40

Ethernet8        PFC0                       0                         0                  1,800,000         01/15/2027, 08:00:00
Ethernet8        PFC1                       0                         0                  8,000,001         07/06/2223, 14:13:20
Ethernet8        PFC2                       0                         0                  8,000,002         07/06/2223, 14:13:20
Ethernet8        PFC3                       0                         0                  8,000,003         07/06/2223, 14:13:20
Ethernet8        PFC4                       0                         0                  8,000,004         07/06/2223, 14:13:20
Ethernet8        PFC5                       0                         0                  8,000,005         07/06/2223, 14:13:20
Ethernet8        PFC6                       0                         0                  8,000,006         07/06/2223, 14:13:20
Ethernet8        PFC7                       0                         0                  8,000,007         07/06/2223, 14:13:20

"""

show_pfc_counters_history_all = """\
          Port    Priority    RX Pause Transitions    Total RX Pause Time US    Recent RX Pause Time US    Recent RX Pause Timestamp
--------------  ----------  ----------------------  ------------------------  -------------------------  ---------------------------
     Ethernet0        PFC0                      12                12,000,000                  1,200,000         01/10/2008, 21:20:00
     Ethernet0        PFC1                      21                20,000,001                  2,000,001         05/18/2033, 03:33:20
     Ethernet0        PFC2                      22                20,000,002                  2,000,002         05/18/2033, 03:33:20
     Ethernet0        PFC3                      23                20,000,003                  2,000,003         05/18/2033, 03:33:20
     Ethernet0        PFC4                      24                20,000,004                  2,000,004         05/18/2033, 03:33:20
     Ethernet0        PFC5                      25                20,000,005                  2,000,005         05/18/2033, 03:33:20
     Ethernet0        PFC6                      26                20,000,006                  2,000,006         05/18/2033, 03:33:20
     Ethernet0        PFC7                      27                20,000,007                  2,000,007         05/18/2033, 03:33:20

     Ethernet4        PFC0                      14                14,000,000                  1,400,000         05/13/2014, 16:53:20
     Ethernet4        PFC1                      41                40,000,001                  4,000,001         10/02/2096, 07:06:40
     Ethernet4        PFC2                      42                40,000,002                  4,000,002         10/02/2096, 07:06:40
     Ethernet4        PFC3                      43                40,000,003                  4,000,003         10/02/2096, 07:06:40
     Ethernet4        PFC4                      44                40,000,004                  4,000,004         10/02/2096, 07:06:40
     Ethernet4        PFC5                      45                40,000,005                  4,000,005         10/02/2096, 07:06:40
     Ethernet4        PFC6                      46                40,000,006                  4,000,006         10/02/2096, 07:06:40
     Ethernet4        PFC7                      47                40,000,007                  4,000,007         10/02/2096, 07:06:40

  Ethernet-BP0        PFC0                      16                16,000,000                  1,600,000         09/13/2020, 12:26:40
  Ethernet-BP0        PFC1                      61                60,000,001                  6,000,001         02/18/2160, 10:40:00
  Ethernet-BP0        PFC2                      62                60,000,002                  6,000,002         02/18/2160, 10:40:00
  Ethernet-BP0        PFC3                      63                60,000,003                  6,000,003         02/18/2160, 10:40:00
  Ethernet-BP0        PFC4                      64                60,000,004                  6,000,004         02/18/2160, 10:40:00
  Ethernet-BP0        PFC5                      65                60,000,005                  6,000,005         02/18/2160, 10:40:00
  Ethernet-BP0        PFC6                      66                60,000,006                  6,000,006         02/18/2160, 10:40:00
  Ethernet-BP0        PFC7                      67                60,000,007                  6,000,007         02/18/2160, 10:40:00

  Ethernet-BP4        PFC0                      18                18,000,000                  1,800,000         01/15/2027, 08:00:00
  Ethernet-BP4        PFC1                      81                80,000,001                  8,000,001         07/06/2223, 14:13:20
  Ethernet-BP4        PFC2                      82                80,000,002                  8,000,002         07/06/2223, 14:13:20
  Ethernet-BP4        PFC3                      83                80,000,003                  8,000,003         07/06/2223, 14:13:20
  Ethernet-BP4        PFC4                      84                80,000,004                  8,000,004         07/06/2223, 14:13:20
  Ethernet-BP4        PFC5                      85                80,000,005                  8,000,005         07/06/2223, 14:13:20
  Ethernet-BP4        PFC6                      86                80,000,006                  8,000,006         07/06/2223, 14:13:20
  Ethernet-BP4        PFC7                      87                80,000,007                  8,000,007         07/06/2223, 14:13:20

Ethernet-BP256        PFC0                     N/A                       N/A                        N/A                          N/A
Ethernet-BP256        PFC1                     N/A                       N/A                        N/A                          N/A
Ethernet-BP256        PFC2                     N/A                       N/A                        N/A                          N/A
Ethernet-BP256        PFC3                     N/A                       N/A                        N/A                          N/A
Ethernet-BP256        PFC4                     N/A                       N/A                        N/A                          N/A
Ethernet-BP256        PFC5                     N/A                       N/A                        N/A                          N/A
Ethernet-BP256        PFC6                     N/A                       N/A                        N/A                          N/A
Ethernet-BP256        PFC7                     N/A                       N/A                        N/A                          N/A

Ethernet-BP260        PFC0                     N/A                       N/A                        N/A                          N/A
Ethernet-BP260        PFC1                     N/A                       N/A                        N/A                          N/A
Ethernet-BP260        PFC2                     N/A                       N/A                        N/A                          N/A
Ethernet-BP260        PFC3                     N/A                       N/A                        N/A                          N/A
Ethernet-BP260        PFC4                     N/A                       N/A                        N/A                          N/A
Ethernet-BP260        PFC5                     N/A                       N/A                        N/A                          N/A
Ethernet-BP260        PFC6                     N/A                       N/A                        N/A                          N/A
Ethernet-BP260        PFC7                     N/A                       N/A                        N/A                          N/A

"""

show_pfc_counters_history_all_with_clear = """\
          Port    Priority    RX Pause Transitions    Total RX Pause Time US    Recent RX Pause Time US    Recent RX Pause Timestamp
--------------  ----------  ----------------------  ------------------------  -------------------------  ---------------------------
     Ethernet0        PFC0                       0                         0                  1,200,000         01/10/2008, 21:20:00
     Ethernet0        PFC1                       0                         0                  2,000,001         05/18/2033, 03:33:20
     Ethernet0        PFC2                       0                         0                  2,000,002         05/18/2033, 03:33:20
     Ethernet0        PFC3                       0                         0                  2,000,003         05/18/2033, 03:33:20
     Ethernet0        PFC4                       0                         0                  2,000,004         05/18/2033, 03:33:20
     Ethernet0        PFC5                       0                         0                  2,000,005         05/18/2033, 03:33:20
     Ethernet0        PFC6                       0                         0                  2,000,006         05/18/2033, 03:33:20
     Ethernet0        PFC7                       0                         0                  2,000,007         05/18/2033, 03:33:20

     Ethernet4        PFC0                       0                         0                  1,400,000         05/13/2014, 16:53:20
     Ethernet4        PFC1                       0                         0                  4,000,001         10/02/2096, 07:06:40
     Ethernet4        PFC2                       0                         0                  4,000,002         10/02/2096, 07:06:40
     Ethernet4        PFC3                       0                         0                  4,000,003         10/02/2096, 07:06:40
     Ethernet4        PFC4                       0                         0                  4,000,004         10/02/2096, 07:06:40
     Ethernet4        PFC5                       0                         0                  4,000,005         10/02/2096, 07:06:40
     Ethernet4        PFC6                       0                         0                  4,000,006         10/02/2096, 07:06:40
     Ethernet4        PFC7                       0                         0                  4,000,007         10/02/2096, 07:06:40

  Ethernet-BP0        PFC0                       0                         0                  1,600,000         09/13/2020, 12:26:40
  Ethernet-BP0        PFC1                       0                         0                  6,000,001         02/18/2160, 10:40:00
  Ethernet-BP0        PFC2                       0                         0                  6,000,002         02/18/2160, 10:40:00
  Ethernet-BP0        PFC3                       0                         0                  6,000,003         02/18/2160, 10:40:00
  Ethernet-BP0        PFC4                       0                         0                  6,000,004         02/18/2160, 10:40:00
  Ethernet-BP0        PFC5                       0                         0                  6,000,005         02/18/2160, 10:40:00
  Ethernet-BP0        PFC6                       0                         0                  6,000,006         02/18/2160, 10:40:00
  Ethernet-BP0        PFC7                       0                         0                  6,000,007         02/18/2160, 10:40:00

  Ethernet-BP4        PFC0                       0                         0                  1,800,000         01/15/2027, 08:00:00
  Ethernet-BP4        PFC1                       0                         0                  8,000,001         07/06/2223, 14:13:20
  Ethernet-BP4        PFC2                       0                         0                  8,000,002         07/06/2223, 14:13:20
  Ethernet-BP4        PFC3                       0                         0                  8,000,003         07/06/2223, 14:13:20
  Ethernet-BP4        PFC4                       0                         0                  8,000,004         07/06/2223, 14:13:20
  Ethernet-BP4        PFC5                       0                         0                  8,000,005         07/06/2223, 14:13:20
  Ethernet-BP4        PFC6                       0                         0                  8,000,006         07/06/2223, 14:13:20
  Ethernet-BP4        PFC7                       0                         0                  8,000,007         07/06/2223, 14:13:20

Ethernet-BP256        PFC0                     N/A                       N/A                        N/A                          N/A
Ethernet-BP256        PFC1                     N/A                       N/A                        N/A                          N/A
Ethernet-BP256        PFC2                     N/A                       N/A                        N/A                          N/A
Ethernet-BP256        PFC3                     N/A                       N/A                        N/A                          N/A
Ethernet-BP256        PFC4                     N/A                       N/A                        N/A                          N/A
Ethernet-BP256        PFC5                     N/A                       N/A                        N/A                          N/A
Ethernet-BP256        PFC6                     N/A                       N/A                        N/A                          N/A
Ethernet-BP256        PFC7                     N/A                       N/A                        N/A                          N/A

Ethernet-BP260        PFC0                     N/A                       N/A                        N/A                          N/A
Ethernet-BP260        PFC1                     N/A                       N/A                        N/A                          N/A
Ethernet-BP260        PFC2                     N/A                       N/A                        N/A                          N/A
Ethernet-BP260        PFC3                     N/A                       N/A                        N/A                          N/A
Ethernet-BP260        PFC4                     N/A                       N/A                        N/A                          N/A
Ethernet-BP260        PFC5                     N/A                       N/A                        N/A                          N/A
Ethernet-BP260        PFC6                     N/A                       N/A                        N/A                          N/A
Ethernet-BP260        PFC7                     N/A                       N/A                        N/A                          N/A

"""

show_pfc_counters_history_all_asic = """\
        Port    Priority    RX Pause Transitions    Total RX Pause Time US    Recent RX Pause Time US    Recent RX Pause Timestamp
------------  ----------  ----------------------  ------------------------  -------------------------  ---------------------------
   Ethernet0        PFC0                      12                12,000,000                  1,200,000         01/10/2008, 21:20:00
   Ethernet0        PFC1                      21                20,000,001                  2,000,001         05/18/2033, 03:33:20
   Ethernet0        PFC2                      22                20,000,002                  2,000,002         05/18/2033, 03:33:20
   Ethernet0        PFC3                      23                20,000,003                  2,000,003         05/18/2033, 03:33:20
   Ethernet0        PFC4                      24                20,000,004                  2,000,004         05/18/2033, 03:33:20
   Ethernet0        PFC5                      25                20,000,005                  2,000,005         05/18/2033, 03:33:20
   Ethernet0        PFC6                      26                20,000,006                  2,000,006         05/18/2033, 03:33:20
   Ethernet0        PFC7                      27                20,000,007                  2,000,007         05/18/2033, 03:33:20

   Ethernet4        PFC0                      14                14,000,000                  1,400,000         05/13/2014, 16:53:20
   Ethernet4        PFC1                      41                40,000,001                  4,000,001         10/02/2096, 07:06:40
   Ethernet4        PFC2                      42                40,000,002                  4,000,002         10/02/2096, 07:06:40
   Ethernet4        PFC3                      43                40,000,003                  4,000,003         10/02/2096, 07:06:40
   Ethernet4        PFC4                      44                40,000,004                  4,000,004         10/02/2096, 07:06:40
   Ethernet4        PFC5                      45                40,000,005                  4,000,005         10/02/2096, 07:06:40
   Ethernet4        PFC6                      46                40,000,006                  4,000,006         10/02/2096, 07:06:40
   Ethernet4        PFC7                      47                40,000,007                  4,000,007         10/02/2096, 07:06:40

Ethernet-BP0        PFC0                      16                16,000,000                  1,600,000         09/13/2020, 12:26:40
Ethernet-BP0        PFC1                      61                60,000,001                  6,000,001         02/18/2160, 10:40:00
Ethernet-BP0        PFC2                      62                60,000,002                  6,000,002         02/18/2160, 10:40:00
Ethernet-BP0        PFC3                      63                60,000,003                  6,000,003         02/18/2160, 10:40:00
Ethernet-BP0        PFC4                      64                60,000,004                  6,000,004         02/18/2160, 10:40:00
Ethernet-BP0        PFC5                      65                60,000,005                  6,000,005         02/18/2160, 10:40:00
Ethernet-BP0        PFC6                      66                60,000,006                  6,000,006         02/18/2160, 10:40:00
Ethernet-BP0        PFC7                      67                60,000,007                  6,000,007         02/18/2160, 10:40:00

Ethernet-BP4        PFC0                      18                18,000,000                  1,800,000         01/15/2027, 08:00:00
Ethernet-BP4        PFC1                      81                80,000,001                  8,000,001         07/06/2223, 14:13:20
Ethernet-BP4        PFC2                      82                80,000,002                  8,000,002         07/06/2223, 14:13:20
Ethernet-BP4        PFC3                      83                80,000,003                  8,000,003         07/06/2223, 14:13:20
Ethernet-BP4        PFC4                      84                80,000,004                  8,000,004         07/06/2223, 14:13:20
Ethernet-BP4        PFC5                      85                80,000,005                  8,000,005         07/06/2223, 14:13:20
Ethernet-BP4        PFC6                      86                80,000,006                  8,000,006         07/06/2223, 14:13:20
Ethernet-BP4        PFC7                      87                80,000,007                  8,000,007         07/06/2223, 14:13:20

"""

show_pfc_counters_history_asic0_frontend = """\
     Port    Priority    RX Pause Transitions    Total RX Pause Time US    Recent RX Pause Time US    Recent RX Pause Timestamp
---------  ----------  ----------------------  ------------------------  -------------------------  ---------------------------
Ethernet0        PFC0                      12                12,000,000                  1,200,000         01/10/2008, 21:20:00
Ethernet0        PFC1                      21                20,000,001                  2,000,001         05/18/2033, 03:33:20
Ethernet0        PFC2                      22                20,000,002                  2,000,002         05/18/2033, 03:33:20
Ethernet0        PFC3                      23                20,000,003                  2,000,003         05/18/2033, 03:33:20
Ethernet0        PFC4                      24                20,000,004                  2,000,004         05/18/2033, 03:33:20
Ethernet0        PFC5                      25                20,000,005                  2,000,005         05/18/2033, 03:33:20
Ethernet0        PFC6                      26                20,000,006                  2,000,006         05/18/2033, 03:33:20
Ethernet0        PFC7                      27                20,000,007                  2,000,007         05/18/2033, 03:33:20

Ethernet4        PFC0                      14                14,000,000                  1,400,000         05/13/2014, 16:53:20
Ethernet4        PFC1                      41                40,000,001                  4,000,001         10/02/2096, 07:06:40
Ethernet4        PFC2                      42                40,000,002                  4,000,002         10/02/2096, 07:06:40
Ethernet4        PFC3                      43                40,000,003                  4,000,003         10/02/2096, 07:06:40
Ethernet4        PFC4                      44                40,000,004                  4,000,004         10/02/2096, 07:06:40
Ethernet4        PFC5                      45                40,000,005                  4,000,005         10/02/2096, 07:06:40
Ethernet4        PFC6                      46                40,000,006                  4,000,006         10/02/2096, 07:06:40
Ethernet4        PFC7                      47                40,000,007                  4,000,007         10/02/2096, 07:06:40

"""

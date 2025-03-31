import importlib
import os
import shutil
import sys

from click.testing import CliRunner

import show.main as show
import clear.main as clear
from .utils import get_result_and_return_code
from utilities_common.cli import UserCache

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")

show_pfc_counters_output = """\
  Port Rx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
---------  ------  ------  ------  ------  ------  ------  ------  ------
Ethernet0   1,200     201     202     203     204     205     206     207
Ethernet4   1,400     401     402     403     404     405     406     407
Ethernet8   1,800     801     802     803     804     805     806     807

  Port Tx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
---------  ------  ------  ------  ------  ------  ------  ------  ------
Ethernet0   1,210     211     212     213     214     215     216     217
Ethernet4   1,410     411     412     413     414     415     416     417
Ethernet8   1,810     811     812     813     814     815     816     817
"""

show_pfc_counters_history_output = """\
     Port    Priority    RX Pause Transitions    Total RX Pause Time MS    Recent RX Pause Time MS    Recent RX Pause Timestamp
---------  ----------  ----------------------  ------------------------  -------------------------  ---------------------------
Ethernet0        PFC0                      12                    12,000                      1,200         01/10/2008, 21:20:00
Ethernet0        PFC1                      21                    20,001                      2,001         05/18/2033, 03:33:20
Ethernet0        PFC2                      22                    20,002                      2,002         05/18/2033, 03:33:20
Ethernet0        PFC3                      23                    20,003                      2,003         05/18/2033, 03:33:20
Ethernet0        PFC4                      24                    20,004                      2,004         05/18/2033, 03:33:20
Ethernet0        PFC5                      25                    20,005                      2,005         05/18/2033, 03:33:20
Ethernet0        PFC6                      26                    20,006                      2,006         05/18/2033, 03:33:20
Ethernet0        PFC7                      27                    20,007                      2,007         05/18/2033, 03:33:20

Ethernet4        PFC0                      14                    14,000                      1,400         05/13/2014, 16:53:20
Ethernet4        PFC1                      41                    40,001                      4,001         10/02/2096, 07:06:40
Ethernet4        PFC2                      42                    40,002                      4,002         10/02/2096, 07:06:40
Ethernet4        PFC3                      43                    40,003                      4,003         10/02/2096, 07:06:40
Ethernet4        PFC4                      44                    40,004                      4,004         10/02/2096, 07:06:40
Ethernet4        PFC5                      45                    40,005                      4,005         10/02/2096, 07:06:40
Ethernet4        PFC6                      46                    40,006                      4,006         10/02/2096, 07:06:40
Ethernet4        PFC7                      47                    40,007                      4,007         10/02/2096, 07:06:40

Ethernet8        PFC0                      18                    18,000                      1,800         01/15/2027, 08:00:00
Ethernet8        PFC1                      81                    80,001                      8,001         07/06/2223, 14:13:20
Ethernet8        PFC2                      82                    80,002                      8,002         07/06/2223, 14:13:20
Ethernet8        PFC3                      83                    80,003                      8,003         07/06/2223, 14:13:20
Ethernet8        PFC4                      84                    80,004                      8,004         07/06/2223, 14:13:20
Ethernet8        PFC5                      85                    80,005                      8,005         07/06/2223, 14:13:20
Ethernet8        PFC6                      86                    80,006                      8,006         07/06/2223, 14:13:20
Ethernet8        PFC7                      87                    80,007                      8,007         07/06/2223, 14:13:20

"""

show_pfc_counters_output_with_clear = ["""\
  Port Rx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
---------  ------  ------  ------  ------  ------  ------  ------  ------
Ethernet0       0       0       0       0       0       0       0       0
Ethernet4       0       0       0       0       0       0       0       0
Ethernet8       0       0       0       0       0       0       0       0
""", """\
  Port Tx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
---------  ------  ------  ------  ------  ------  ------  ------  ------
Ethernet0       0       0       0       0       0       0       0       0
Ethernet4       0       0       0       0       0       0       0       0
Ethernet8       0       0       0       0       0       0       0       0
"""]

show_pfc_counters_history_output_with_clear = """\
     Port    Priority    RX Pause Transitions    Total RX Pause Time MS    Recent RX Pause Time MS    Recent RX Pause Timestamp
---------  ----------  ----------------------  ------------------------  -------------------------  ---------------------------
Ethernet0        PFC0                       0                         0                      1,200         01/10/2008, 21:20:00
Ethernet0        PFC1                       0                         0                      2,001         05/18/2033, 03:33:20
Ethernet0        PFC2                       0                         0                      2,002         05/18/2033, 03:33:20
Ethernet0        PFC3                       0                         0                      2,003         05/18/2033, 03:33:20
Ethernet0        PFC4                       0                         0                      2,004         05/18/2033, 03:33:20
Ethernet0        PFC5                       0                         0                      2,005         05/18/2033, 03:33:20
Ethernet0        PFC6                       0                         0                      2,006         05/18/2033, 03:33:20
Ethernet0        PFC7                       0                         0                      2,007         05/18/2033, 03:33:20

Ethernet4        PFC0                       0                         0                      1,400         05/13/2014, 16:53:20
Ethernet4        PFC1                       0                         0                      4,001         10/02/2096, 07:06:40
Ethernet4        PFC2                       0                         0                      4,002         10/02/2096, 07:06:40
Ethernet4        PFC3                       0                         0                      4,003         10/02/2096, 07:06:40
Ethernet4        PFC4                       0                         0                      4,004         10/02/2096, 07:06:40
Ethernet4        PFC5                       0                         0                      4,005         10/02/2096, 07:06:40
Ethernet4        PFC6                       0                         0                      4,006         10/02/2096, 07:06:40
Ethernet4        PFC7                       0                         0                      4,007         10/02/2096, 07:06:40

Ethernet8        PFC0                       0                         0                      1,800         01/15/2027, 08:00:00
Ethernet8        PFC1                       0                         0                      8,001         07/06/2223, 14:13:20
Ethernet8        PFC2                       0                         0                      8,002         07/06/2223, 14:13:20
Ethernet8        PFC3                       0                         0                      8,003         07/06/2223, 14:13:20
Ethernet8        PFC4                       0                         0                      8,004         07/06/2223, 14:13:20
Ethernet8        PFC5                       0                         0                      8,005         07/06/2223, 14:13:20
Ethernet8        PFC6                       0                         0                      8,006         07/06/2223, 14:13:20
Ethernet8        PFC7                       0                         0                      8,007         07/06/2223, 14:13:20

"""

show_pfc_counters_output_diff = """\
  Port Rx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
---------  ------  ------  ------  ------  ------  ------  ------  ------
Ethernet0       0       0       0       0       0       0       0       0
Ethernet4       0       0       0       0       0       0       0       0
Ethernet8       0       0       0       0       0       0       0       0

  Port Tx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
---------  ------  ------  ------  ------  ------  ------  ------  ------
Ethernet0       0       0       0       0       0       0       0       0
Ethernet4       0       0       0       0       0       0       0       0
Ethernet8       0       0       0       0       0       0       0       0
"""

show_pfc_counters_all = """\
       Port Rx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
--------------  ------  ------  ------  ------  ------  ------  ------  ------
     Ethernet0   1,200     201     202     203     204     205     206     207
     Ethernet4   1,400     401     402     403     404     405     406     407
  Ethernet-BP0   1,600     601     602     603     604     605     606     607
  Ethernet-BP4   1,800     801     802     803     804     805     806     807
Ethernet-BP256     N/A     N/A     N/A     N/A     N/A     N/A     N/A     N/A
Ethernet-BP260     N/A     N/A     N/A     N/A     N/A     N/A     N/A     N/A

       Port Tx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
--------------  ------  ------  ------  ------  ------  ------  ------  ------
     Ethernet0   1,210     211     212     213     214     215     216     217
     Ethernet4   1,410     411     412     413     414     415     416     417
  Ethernet-BP0   1,610     611     612     613     614     615     616     617
  Ethernet-BP4   1,810     811     812     813     814     815     816     817
Ethernet-BP256     N/A     N/A     N/A     N/A     N/A     N/A     N/A     N/A
Ethernet-BP260     N/A     N/A     N/A     N/A     N/A     N/A     N/A     N/A
"""

show_pfc_counters_history_all = """\
          Port    Priority    RX Pause Transitions    Total RX Pause Time MS    Recent RX Pause Time MS    Recent RX Pause Timestamp
--------------  ----------  ----------------------  ------------------------  -------------------------  ---------------------------
     Ethernet0        PFC0                      12                    12,000                      1,200         01/10/2008, 21:20:00
     Ethernet0        PFC1                      21                    20,001                      2,001         05/18/2033, 03:33:20
     Ethernet0        PFC2                      22                    20,002                      2,002         05/18/2033, 03:33:20
     Ethernet0        PFC3                      23                    20,003                      2,003         05/18/2033, 03:33:20
     Ethernet0        PFC4                      24                    20,004                      2,004         05/18/2033, 03:33:20
     Ethernet0        PFC5                      25                    20,005                      2,005         05/18/2033, 03:33:20
     Ethernet0        PFC6                      26                    20,006                      2,006         05/18/2033, 03:33:20
     Ethernet0        PFC7                      27                    20,007                      2,007         05/18/2033, 03:33:20

     Ethernet4        PFC0                      14                    14,000                      1,400         05/13/2014, 16:53:20
     Ethernet4        PFC1                      41                    40,001                      4,001         10/02/2096, 07:06:40
     Ethernet4        PFC2                      42                    40,002                      4,002         10/02/2096, 07:06:40
     Ethernet4        PFC3                      43                    40,003                      4,003         10/02/2096, 07:06:40
     Ethernet4        PFC4                      44                    40,004                      4,004         10/02/2096, 07:06:40
     Ethernet4        PFC5                      45                    40,005                      4,005         10/02/2096, 07:06:40
     Ethernet4        PFC6                      46                    40,006                      4,006         10/02/2096, 07:06:40
     Ethernet4        PFC7                      47                    40,007                      4,007         10/02/2096, 07:06:40

  Ethernet-BP0        PFC0                      16                    16,000                      1,600         09/13/2020, 12:26:40
  Ethernet-BP0        PFC1                      61                    60,001                      6,001         02/18/2160, 10:40:00
  Ethernet-BP0        PFC2                      62                    60,002                      6,002         02/18/2160, 10:40:00
  Ethernet-BP0        PFC3                      63                    60,003                      6,003         02/18/2160, 10:40:00
  Ethernet-BP0        PFC4                      64                    60,004                      6,004         02/18/2160, 10:40:00
  Ethernet-BP0        PFC5                      65                    60,005                      6,005         02/18/2160, 10:40:00
  Ethernet-BP0        PFC6                      66                    60,006                      6,006         02/18/2160, 10:40:00
  Ethernet-BP0        PFC7                      67                    60,007                      6,007         02/18/2160, 10:40:00

  Ethernet-BP4        PFC0                      18                    18,000                      1,800         01/15/2027, 08:00:00
  Ethernet-BP4        PFC1                      81                    80,001                      8,001         07/06/2223, 14:13:20
  Ethernet-BP4        PFC2                      82                    80,002                      8,002         07/06/2223, 14:13:20
  Ethernet-BP4        PFC3                      83                    80,003                      8,003         07/06/2223, 14:13:20
  Ethernet-BP4        PFC4                      84                    80,004                      8,004         07/06/2223, 14:13:20
  Ethernet-BP4        PFC5                      85                    80,005                      8,005         07/06/2223, 14:13:20
  Ethernet-BP4        PFC6                      86                    80,006                      8,006         07/06/2223, 14:13:20
  Ethernet-BP4        PFC7                      87                    80,007                      8,007         07/06/2223, 14:13:20

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

show_pfc_counters_all_with_clear = ["""\
       Port Rx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
--------------  ------  ------  ------  ------  ------  ------  ------  ------
     Ethernet0       0       0       0       0       0       0       0       0
     Ethernet4       0       0       0       0       0       0       0       0
  Ethernet-BP0       0       0       0       0       0       0       0       0
  Ethernet-BP4       0       0       0       0       0       0       0       0
Ethernet-BP256       0       0       0       0       0       0       0       0
Ethernet-BP260       0       0       0       0       0       0       0       0
""", """\
       Port Tx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
--------------  ------  ------  ------  ------  ------  ------  ------  ------
     Ethernet0       0       0       0       0       0       0       0       0
     Ethernet4       0       0       0       0       0       0       0       0
  Ethernet-BP0       0       0       0       0       0       0       0       0
  Ethernet-BP4       0       0       0       0       0       0       0       0
Ethernet-BP256       0       0       0       0       0       0       0       0
Ethernet-BP260       0       0       0       0       0       0       0       0
"""]

show_pfc_counters_history_all_with_clear = """\
          Port    Priority    RX Pause Transitions    Total RX Pause Time MS    Recent RX Pause Time MS    Recent RX Pause Timestamp
--------------  ----------  ----------------------  ------------------------  -------------------------  ---------------------------
     Ethernet0        PFC0                       0                         0                      1,200         01/10/2008, 21:20:00
     Ethernet0        PFC1                       0                         0                      2,001         05/18/2033, 03:33:20
     Ethernet0        PFC2                       0                         0                      2,002         05/18/2033, 03:33:20
     Ethernet0        PFC3                       0                         0                      2,003         05/18/2033, 03:33:20
     Ethernet0        PFC4                       0                         0                      2,004         05/18/2033, 03:33:20
     Ethernet0        PFC5                       0                         0                      2,005         05/18/2033, 03:33:20
     Ethernet0        PFC6                       0                         0                      2,006         05/18/2033, 03:33:20
     Ethernet0        PFC7                       0                         0                      2,007         05/18/2033, 03:33:20

     Ethernet4        PFC0                       0                         0                      1,400         05/13/2014, 16:53:20
     Ethernet4        PFC1                       0                         0                      4,001         10/02/2096, 07:06:40
     Ethernet4        PFC2                       0                         0                      4,002         10/02/2096, 07:06:40
     Ethernet4        PFC3                       0                         0                      4,003         10/02/2096, 07:06:40
     Ethernet4        PFC4                       0                         0                      4,004         10/02/2096, 07:06:40
     Ethernet4        PFC5                       0                         0                      4,005         10/02/2096, 07:06:40
     Ethernet4        PFC6                       0                         0                      4,006         10/02/2096, 07:06:40
     Ethernet4        PFC7                       0                         0                      4,007         10/02/2096, 07:06:40

  Ethernet-BP0        PFC0                       0                         0                      1,600         09/13/2020, 12:26:40
  Ethernet-BP0        PFC1                       0                         0                      6,001         02/18/2160, 10:40:00
  Ethernet-BP0        PFC2                       0                         0                      6,002         02/18/2160, 10:40:00
  Ethernet-BP0        PFC3                       0                         0                      6,003         02/18/2160, 10:40:00
  Ethernet-BP0        PFC4                       0                         0                      6,004         02/18/2160, 10:40:00
  Ethernet-BP0        PFC5                       0                         0                      6,005         02/18/2160, 10:40:00
  Ethernet-BP0        PFC6                       0                         0                      6,006         02/18/2160, 10:40:00
  Ethernet-BP0        PFC7                       0                         0                      6,007         02/18/2160, 10:40:00

  Ethernet-BP4        PFC0                       0                         0                      1,800         01/15/2027, 08:00:00
  Ethernet-BP4        PFC1                       0                         0                      8,001         07/06/2223, 14:13:20
  Ethernet-BP4        PFC2                       0                         0                      8,002         07/06/2223, 14:13:20
  Ethernet-BP4        PFC3                       0                         0                      8,003         07/06/2223, 14:13:20
  Ethernet-BP4        PFC4                       0                         0                      8,004         07/06/2223, 14:13:20
  Ethernet-BP4        PFC5                       0                         0                      8,005         07/06/2223, 14:13:20
  Ethernet-BP4        PFC6                       0                         0                      8,006         07/06/2223, 14:13:20
  Ethernet-BP4        PFC7                       0                         0                      8,007         07/06/2223, 14:13:20

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

show_pfc_counters_all_asic = """\
     Port Rx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
------------  ------  ------  ------  ------  ------  ------  ------  ------
   Ethernet0   1,200     201     202     203     204     205     206     207
   Ethernet4   1,400     401     402     403     404     405     406     407
Ethernet-BP0   1,600     601     602     603     604     605     606     607
Ethernet-BP4   1,800     801     802     803     804     805     806     807

     Port Tx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
------------  ------  ------  ------  ------  ------  ------  ------  ------
   Ethernet0   1,210     211     212     213     214     215     216     217
   Ethernet4   1,410     411     412     413     414     415     416     417
Ethernet-BP0   1,610     611     612     613     614     615     616     617
Ethernet-BP4   1,810     811     812     813     814     815     816     817
"""

show_pfc_counters_history_all_asic = """\
        Port    Priority    RX Pause Transitions    Total RX Pause Time MS    Recent RX Pause Time MS    Recent RX Pause Timestamp
------------  ----------  ----------------------  ------------------------  -------------------------  ---------------------------
   Ethernet0        PFC0                      12                    12,000                      1,200         01/10/2008, 21:20:00
   Ethernet0        PFC1                      21                    20,001                      2,001         05/18/2033, 03:33:20
   Ethernet0        PFC2                      22                    20,002                      2,002         05/18/2033, 03:33:20
   Ethernet0        PFC3                      23                    20,003                      2,003         05/18/2033, 03:33:20
   Ethernet0        PFC4                      24                    20,004                      2,004         05/18/2033, 03:33:20
   Ethernet0        PFC5                      25                    20,005                      2,005         05/18/2033, 03:33:20
   Ethernet0        PFC6                      26                    20,006                      2,006         05/18/2033, 03:33:20
   Ethernet0        PFC7                      27                    20,007                      2,007         05/18/2033, 03:33:20

   Ethernet4        PFC0                      14                    14,000                      1,400         05/13/2014, 16:53:20
   Ethernet4        PFC1                      41                    40,001                      4,001         10/02/2096, 07:06:40
   Ethernet4        PFC2                      42                    40,002                      4,002         10/02/2096, 07:06:40
   Ethernet4        PFC3                      43                    40,003                      4,003         10/02/2096, 07:06:40
   Ethernet4        PFC4                      44                    40,004                      4,004         10/02/2096, 07:06:40
   Ethernet4        PFC5                      45                    40,005                      4,005         10/02/2096, 07:06:40
   Ethernet4        PFC6                      46                    40,006                      4,006         10/02/2096, 07:06:40
   Ethernet4        PFC7                      47                    40,007                      4,007         10/02/2096, 07:06:40

Ethernet-BP0        PFC0                      16                    16,000                      1,600         09/13/2020, 12:26:40
Ethernet-BP0        PFC1                      61                    60,001                      6,001         02/18/2160, 10:40:00
Ethernet-BP0        PFC2                      62                    60,002                      6,002         02/18/2160, 10:40:00
Ethernet-BP0        PFC3                      63                    60,003                      6,003         02/18/2160, 10:40:00
Ethernet-BP0        PFC4                      64                    60,004                      6,004         02/18/2160, 10:40:00
Ethernet-BP0        PFC5                      65                    60,005                      6,005         02/18/2160, 10:40:00
Ethernet-BP0        PFC6                      66                    60,006                      6,006         02/18/2160, 10:40:00
Ethernet-BP0        PFC7                      67                    60,007                      6,007         02/18/2160, 10:40:00

Ethernet-BP4        PFC0                      18                    18,000                      1,800         01/15/2027, 08:00:00
Ethernet-BP4        PFC1                      81                    80,001                      8,001         07/06/2223, 14:13:20
Ethernet-BP4        PFC2                      82                    80,002                      8,002         07/06/2223, 14:13:20
Ethernet-BP4        PFC3                      83                    80,003                      8,003         07/06/2223, 14:13:20
Ethernet-BP4        PFC4                      84                    80,004                      8,004         07/06/2223, 14:13:20
Ethernet-BP4        PFC5                      85                    80,005                      8,005         07/06/2223, 14:13:20
Ethernet-BP4        PFC6                      86                    80,006                      8,006         07/06/2223, 14:13:20
Ethernet-BP4        PFC7                      87                    80,007                      8,007         07/06/2223, 14:13:20

"""

show_pfc_counters_all = """\
       Port Rx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
--------------  ------  ------  ------  ------  ------  ------  ------  ------
     Ethernet0   1,200     201     202     203     204     205     206     207
     Ethernet4   1,400     401     402     403     404     405     406     407
  Ethernet-BP0   1,600     601     602     603     604     605     606     607
  Ethernet-BP4   1,800     801     802     803     804     805     806     807
Ethernet-BP256   1,900     901     902     903     904     905     906     907
Ethernet-BP260   1,100     101     102     103     104     105     106     107

       Port Tx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
--------------  ------  ------  ------  ------  ------  ------  ------  ------
     Ethernet0   1,210     211     212     213     214     215     216     217
     Ethernet4   1,410     411     412     413     414     415     416     417
  Ethernet-BP0   1,610     611     612     613     614     615     616     617
  Ethernet-BP4   1,810     811     812     813     814     815     816     817
Ethernet-BP256   1,910     911     912     913     914     915     916     917
Ethernet-BP260   1,110     111     112     113     114     115     116     117
"""

show_pfc_counters_asic0_frontend = """\
  Port Rx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
---------  ------  ------  ------  ------  ------  ------  ------  ------
Ethernet0   1,200     201     202     203     204     205     206     207
Ethernet4   1,400     401     402     403     404     405     406     407

  Port Tx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
---------  ------  ------  ------  ------  ------  ------  ------  ------
Ethernet0   1,210     211     212     213     214     215     216     217
Ethernet4   1,410     411     412     413     414     415     416     417
"""

show_pfc_counters_history_asic0_frontend = """\
     Port    Priority    RX Pause Transitions    Total RX Pause Time MS    Recent RX Pause Time MS    Recent RX Pause Timestamp
---------  ----------  ----------------------  ------------------------  -------------------------  ---------------------------
Ethernet0        PFC0                      12                    12,000                      1,200         01/10/2008, 21:20:00
Ethernet0        PFC1                      21                    20,001                      2,001         05/18/2033, 03:33:20
Ethernet0        PFC2                      22                    20,002                      2,002         05/18/2033, 03:33:20
Ethernet0        PFC3                      23                    20,003                      2,003         05/18/2033, 03:33:20
Ethernet0        PFC4                      24                    20,004                      2,004         05/18/2033, 03:33:20
Ethernet0        PFC5                      25                    20,005                      2,005         05/18/2033, 03:33:20
Ethernet0        PFC6                      26                    20,006                      2,006         05/18/2033, 03:33:20
Ethernet0        PFC7                      27                    20,007                      2,007         05/18/2033, 03:33:20

Ethernet4        PFC0                      14                    14,000                      1,400         05/13/2014, 16:53:20
Ethernet4        PFC1                      41                    40,001                      4,001         10/02/2096, 07:06:40
Ethernet4        PFC2                      42                    40,002                      4,002         10/02/2096, 07:06:40
Ethernet4        PFC3                      43                    40,003                      4,003         10/02/2096, 07:06:40
Ethernet4        PFC4                      44                    40,004                      4,004         10/02/2096, 07:06:40
Ethernet4        PFC5                      45                    40,005                      4,005         10/02/2096, 07:06:40
Ethernet4        PFC6                      46                    40,006                      4,006         10/02/2096, 07:06:40
Ethernet4        PFC7                      47                    40,007                      4,007         10/02/2096, 07:06:40

"""

show_pfc_counters_msaic_output_diff = """\
       Port Rx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
--------------  ------  ------  ------  ------  ------  ------  ------  ------
     Ethernet0       0       0       0       0       0       0       0       0
     Ethernet4       0       0       0       0       0       0       0       0
  Ethernet-BP0       0       0       0       0       0       0       0       0
  Ethernet-BP4       0       0       0       0       0       0       0       0
Ethernet-BP256       0       0       0       0       0       0       0       0
Ethernet-BP260       0       0       0       0       0       0       0       0

       Port Tx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
--------------  ------  ------  ------  ------  ------  ------  ------  ------
     Ethernet0       0       0       0       0       0       0       0       0
     Ethernet4       0       0       0       0       0       0       0       0
  Ethernet-BP0       0       0       0       0       0       0       0       0
  Ethernet-BP4       0       0       0       0       0       0       0       0
Ethernet-BP256       0       0       0       0       0       0       0       0
Ethernet-BP260       0       0       0       0       0       0       0       0
"""


def del_cached_stats():
    cache = UserCache("pfcstat")
    cache.remove_all()


def pfc_clear(expected_output, pfc_stat_show_args=[]):
    counters_file_list = ['0tx', '0rx']
    del_cached_stats()

    return_code, result = get_result_and_return_code(
        ['pfcstat', '-c']
    )

    return_code, result = get_result_and_return_code(
        ['pfcstat', '-s', 'all'] + pfc_stat_show_args
    )
    result_stat = [s for s in result.split("\n") if "Last cached" not in s]
    expected = expected_output.split("\n")
    # this will also verify the saved counters are correct since the
    # expected counters are all '0s'
    assert result_stat == expected
    del_cached_stats()


class TestPfcstat(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        del_cached_stats()

    def setup_method(self, method):
        del_cached_stats()

    def test_pfc_counters(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["pfc"].commands["counters"],
            []
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_pfc_counters_output

    def test_pfc_counters_with_clear(self):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands['pfccounters'], [])
        assert result.exit_code == 0
        result = runner.invoke(
            show.cli.commands["pfc"].commands["counters"],
            []
        )
        print(result.output)
        show.run_command(['pfcstat', '-d'])
        assert result.exit_code == 0
        assert "Last cached time was" in result.output
        assert show_pfc_counters_output_with_clear[0] in result.output and \
                show_pfc_counters_output_with_clear[1] in result.output

    def test_pfc_clear(self):
        pfc_clear(show_pfc_counters_output_diff)


    def test_pfc_counters_history(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["pfc"].commands["counters"],
            ["--history"]
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_pfc_counters_history_output

    def test_pfc_counters_history_with_clear(self):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands['pfccounters'], [])
        assert result.exit_code == 0
        result = runner.invoke(
            show.cli.commands["pfc"].commands["counters"],
            ["--history"]
        )
        print(result.output)
        show.run_command(['pfcstat', '-d'])
        assert result.exit_code == 0
        assert "Last cached time was" in result.output
        assert show_pfc_counters_history_output_with_clear in result.output

    def test_pfc_history_clear(self):
        pfc_clear(show_pfc_counters_history_output_with_clear, ["--history"])

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(
            os.environ["PATH"].split(os.pathsep)[:-1]
        )
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        del_cached_stats()



class TestMultiAsicPfcstat(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        del_cached_stats()

    def setup_method(self, method):
        del_cached_stats()

    def test_pfc_counters_all(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["pfc"].commands["counters"],
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_pfc_counters_all

    def test_pfc_counters_all_with_clear(self):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands['pfccounters'], [])
        assert result.exit_code == 0
        result = runner.invoke(
            show.cli.commands["pfc"].commands["counters"],
            []
        )
        print(result.output)
        show.run_command(['pfcstat', '-d'])
        assert result.exit_code == 0
        assert "Last cached time was" in result.output
        assert show_pfc_counters_all_with_clear[0] in result.output and \
                show_pfc_counters_all_with_clear[1] in result.output

    def test_pfc_counters_frontend(self):
        return_code, result = get_result_and_return_code(
            ['pfcstat', '-s', 'frontend']
        )
        assert return_code == 0
        assert result == show_pfc_counters_asic0_frontend

    def test_pfc_counters_asic(self):
        return_code, result = get_result_and_return_code(
            ['pfcstat', '-n', 'asic0']
        )
        assert return_code == 0
        assert result == show_pfc_counters_asic0_frontend

    def test_pfc_counters_asic_all(self):
        return_code, result = get_result_and_return_code(
            ['pfcstat', '-n', 'asic0', '-s', 'all']
        )
        assert return_code == 0
        assert result == show_pfc_counters_all_asic

    def test_masic_pfc_clear(self):
        pfc_clear(show_pfc_counters_msaic_output_diff)

    def test_pfc_counters_history_all(self):
        runner = CliRunner()
        result = runner.invoke(
            show.cli.commands["pfc"].commands["counters"],
            ["--history"]
        )
        print(result.output)
        assert result.exit_code == 0
        assert result.output == show_pfc_counters_history_all

    def test_pfc_counters_history_all_with_clear(self):
        runner = CliRunner()
        result = runner.invoke(clear.cli.commands['pfccounters'], [])
        assert result.exit_code == 0
        result = runner.invoke(
            show.cli.commands["pfc"].commands["counters"],
            ["--history"]
        )
        print(result.output)
        show.run_command(['pfcstat', '-d'])
        assert result.exit_code == 0
        assert "Last cached time was" in result.output
        assert show_pfc_counters_history_all_with_clear in result.output

    def test_pfc_counters_history_frontend(self):
        return_code, result = get_result_and_return_code(
            ['pfcstat', '-s', 'frontend', '--history']
        )
        assert return_code == 0
        assert result == show_pfc_counters_history_asic0_frontend

    def test_pfc_counters_history_asic(self):
        return_code, result = get_result_and_return_code(
            ['pfcstat', '-n', 'asic0', '--history']
        )
        assert return_code == 0
        assert result == show_pfc_counters_history_asic0_frontend

    def test_pfc_counters_history_asic_all(self):
        return_code, result = get_result_and_return_code(
            ['pfcstat', '-n', 'asic0', '-s', 'all', '--history']
        )
        assert return_code == 0
        assert result == show_pfc_counters_history_all_asic

    def test_masic_pfc_history_clear(self):
        pfc_clear(show_pfc_counters_history_all_with_clear, ["--history"])

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(
            os.environ["PATH"].split(os.pathsep)[:-1]
        )
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        del_cached_stats()
        import mock_tables.mock_single_asic
        importlib.reload(mock_tables.mock_single_asic)
        import pfcwd.main
        importlib.reload(pfcwd.main)

import imp
import json
import os
import sys

from click.testing import CliRunner
from unittest import TestCase
from swsscommon.swsscommon import ConfigDBConnector

from .mock_tables import dbconnector

import show.main as show
from utilities_common.cli import json_dump
from utilities_common.db import Db
from .utils import get_result_and_return_code

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)


show_queue_counters = """\
For namespace asic0:
     Port    TxQ    Counter/pkts    Counter/bytes    Drop/pkts    Drop/bytes
---------  -----  --------------  ---------------  -----------  ------------
Ethernet0    UC0              68               30           56            74
Ethernet0    UC1              69               31           55            73
Ethernet0    UC2              70               32           54            72
Ethernet0    UC3              71               33           53            71
Ethernet0    UC4              72               34           52            70
Ethernet0    UC5              73               35           51            69
Ethernet0    UC6              74               36           50            68
Ethernet0    UC7              75               37           49            67
Ethernet0    MC8              76               38           48            66
Ethernet0    MC9              77               39           47            65
Ethernet0   MC10              78               40           46            64
Ethernet0   MC11              79               41           45            63
Ethernet0   MC12              80               42           44            62
Ethernet0   MC13              81               43           43            61
Ethernet0   MC14              82               44           42            60
Ethernet0   MC15              83               45           41            59

For namespace asic0:
     Port    TxQ    Counter/pkts    Counter/bytes    Drop/pkts    Drop/bytes
---------  -----  --------------  ---------------  -----------  ------------
Ethernet4    UC0              84               46           40            58
Ethernet4    UC1              85               47           39            57
Ethernet4    UC2              86               48           38            56
Ethernet4    UC3              87               49           37            55
Ethernet4    UC4              88               50           36            54
Ethernet4    UC5              89               51           35            53
Ethernet4    UC6              90               52           34            52
Ethernet4    UC7              91               53           33            51
Ethernet4    MC8              92               54           32            50
Ethernet4    MC9              93               55           31            49
Ethernet4   MC10              94               56           30            48
Ethernet4   MC11              95               57           29            47
Ethernet4   MC12              96               58           28            46
Ethernet4   MC13              97               59           27            45
Ethernet4   MC14              98               60           26            44
Ethernet4   MC15              99               61           25            43

For namespace asic0:
        Port    TxQ    Counter/pkts    Counter/bytes    Drop/pkts    Drop/bytes
------------  -----  --------------  ---------------  -----------  ------------
Ethernet-BP0    UC0             100               62           24            42
Ethernet-BP0    UC1             101               63           23            41
Ethernet-BP0    UC2             102               64           22            40
Ethernet-BP0    UC3             103               65           21            39
Ethernet-BP0    UC4             104               66           20            38
Ethernet-BP0    UC5             105               67           19            37
Ethernet-BP0    UC6             106               68           18            36
Ethernet-BP0    UC7             107               69           17            35
Ethernet-BP0    MC8             108               70           16            34
Ethernet-BP0    MC9             109               71           15            33
Ethernet-BP0   MC10             110               72           14            32
Ethernet-BP0   MC11             111               73           13            31
Ethernet-BP0   MC12             112               74           12            30
Ethernet-BP0   MC13             113               75           11            29
Ethernet-BP0   MC14             114               76           10            28
Ethernet-BP0   MC15             115               77            9            27

For namespace asic0:
        Port    TxQ    Counter/pkts    Counter/bytes    Drop/pkts    Drop/bytes
------------  -----  --------------  ---------------  -----------  ------------
Ethernet-BP4    UC0             116               78            8            26
Ethernet-BP4    UC1             117               79            7            25
Ethernet-BP4    UC2             118               80            6            24
Ethernet-BP4    UC3             119               81            5            23
Ethernet-BP4    UC4             120               82            4            22
Ethernet-BP4    UC5             121               83            3            21
Ethernet-BP4    UC6             122               84            2            20
Ethernet-BP4    UC7             123               85            1            19
Ethernet-BP4   ALL8             124               86            0            18
Ethernet-BP4   ALL9             125               87            1            17
Ethernet-BP4  ALL10             126               88            2            16
Ethernet-BP4  ALL11             127               89            3            15
Ethernet-BP4  ALL12             128               90            4            14
Ethernet-BP4  ALL13             129               91            5            13
Ethernet-BP4  ALL14             130               92            6            12
Ethernet-BP4  ALL15             131               93            7            11

"""

show_queue_counters_all_asics = """\
For namespace asic0:
     Port    TxQ    Counter/pkts    Counter/bytes    Drop/pkts    Drop/bytes
---------  -----  --------------  ---------------  -----------  ------------
Ethernet0    UC0              68               30           56            74
Ethernet0    UC1              69               31           55            73
Ethernet0    UC2              70               32           54            72
Ethernet0    UC3              71               33           53            71
Ethernet0    UC4              72               34           52            70
Ethernet0    UC5              73               35           51            69
Ethernet0    UC6              74               36           50            68
Ethernet0    UC7              75               37           49            67
Ethernet0    MC8              76               38           48            66
Ethernet0    MC9              77               39           47            65
Ethernet0   MC10              78               40           46            64
Ethernet0   MC11              79               41           45            63
Ethernet0   MC12              80               42           44            62
Ethernet0   MC13              81               43           43            61
Ethernet0   MC14              82               44           42            60
Ethernet0   MC15              83               45           41            59

For namespace asic0:
     Port    TxQ    Counter/pkts    Counter/bytes    Drop/pkts    Drop/bytes
---------  -----  --------------  ---------------  -----------  ------------
Ethernet4    UC0              84               46           40            58
Ethernet4    UC1              85               47           39            57
Ethernet4    UC2              86               48           38            56
Ethernet4    UC3              87               49           37            55
Ethernet4    UC4              88               50           36            54
Ethernet4    UC5              89               51           35            53
Ethernet4    UC6              90               52           34            52
Ethernet4    UC7              91               53           33            51
Ethernet4    MC8              92               54           32            50
Ethernet4    MC9              93               55           31            49
Ethernet4   MC10              94               56           30            48
Ethernet4   MC11              95               57           29            47
Ethernet4   MC12              96               58           28            46
Ethernet4   MC13              97               59           27            45
Ethernet4   MC14              98               60           26            44
Ethernet4   MC15              99               61           25            43

For namespace asic0:
        Port    TxQ    Counter/pkts    Counter/bytes    Drop/pkts    Drop/bytes
------------  -----  --------------  ---------------  -----------  ------------
Ethernet-BP0    UC0             100               62           24            42
Ethernet-BP0    UC1             101               63           23            41
Ethernet-BP0    UC2             102               64           22            40
Ethernet-BP0    UC3             103               65           21            39
Ethernet-BP0    UC4             104               66           20            38
Ethernet-BP0    UC5             105               67           19            37
Ethernet-BP0    UC6             106               68           18            36
Ethernet-BP0    UC7             107               69           17            35
Ethernet-BP0    MC8             108               70           16            34
Ethernet-BP0    MC9             109               71           15            33
Ethernet-BP0   MC10             110               72           14            32
Ethernet-BP0   MC11             111               73           13            31
Ethernet-BP0   MC12             112               74           12            30
Ethernet-BP0   MC13             113               75           11            29
Ethernet-BP0   MC14             114               76           10            28
Ethernet-BP0   MC15             115               77            9            27

For namespace asic0:
        Port    TxQ    Counter/pkts    Counter/bytes    Drop/pkts    Drop/bytes
------------  -----  --------------  ---------------  -----------  ------------
Ethernet-BP4    UC0             116               78            8            26
Ethernet-BP4    UC1             117               79            7            25
Ethernet-BP4    UC2             118               80            6            24
Ethernet-BP4    UC3             119               81            5            23
Ethernet-BP4    UC4             120               82            4            22
Ethernet-BP4    UC5             121               83            3            21
Ethernet-BP4    UC6             122               84            2            20
Ethernet-BP4    UC7             123               85            1            19
Ethernet-BP4   ALL8             124               86            0            18
Ethernet-BP4   ALL9             125               87            1            17
Ethernet-BP4  ALL10             126               88            2            16
Ethernet-BP4  ALL11             127               89            3            15
Ethernet-BP4  ALL12             128               90            4            14
Ethernet-BP4  ALL13             129               91            5            13
Ethernet-BP4  ALL14             130               92            6            12
Ethernet-BP4  ALL15             131               93            7            11

For namespace asic1:
          Port    TxQ    Counter/pkts    Counter/bytes    Drop/pkts    Drop/bytes
--------------  -----  --------------  ---------------  -----------  ------------
Ethernet-BP256    UC0             N/A              N/A          N/A           N/A
Ethernet-BP256    UC1             N/A              N/A          N/A           N/A
Ethernet-BP256    UC2             N/A              N/A          N/A           N/A
Ethernet-BP256    UC3             N/A              N/A          N/A           N/A
Ethernet-BP256    UC4             N/A              N/A          N/A           N/A
Ethernet-BP256    UC5             N/A              N/A          N/A           N/A
Ethernet-BP256    UC6             N/A              N/A          N/A           N/A
Ethernet-BP256    UC7             N/A              N/A          N/A           N/A
Ethernet-BP256    MC8             N/A              N/A          N/A           N/A
Ethernet-BP256    MC9             N/A              N/A          N/A           N/A
Ethernet-BP256   MC10             N/A              N/A          N/A           N/A
Ethernet-BP256   MC11             N/A              N/A          N/A           N/A
Ethernet-BP256   MC12             N/A              N/A          N/A           N/A
Ethernet-BP256   MC13             N/A              N/A          N/A           N/A
Ethernet-BP256   MC14             N/A              N/A          N/A           N/A
Ethernet-BP256   MC15             N/A              N/A          N/A           N/A

For namespace asic1:
          Port    TxQ    Counter/pkts    Counter/bytes    Drop/pkts    Drop/bytes
--------------  -----  --------------  ---------------  -----------  ------------
Ethernet-BP260    UC0             N/A              N/A          N/A           N/A
Ethernet-BP260    UC1             N/A              N/A          N/A           N/A
Ethernet-BP260    UC2             N/A              N/A          N/A           N/A
Ethernet-BP260    UC3             N/A              N/A          N/A           N/A
Ethernet-BP260    UC4             N/A              N/A          N/A           N/A
Ethernet-BP260    UC5             N/A              N/A          N/A           N/A
Ethernet-BP260    UC6             N/A              N/A          N/A           N/A
Ethernet-BP260    UC7             N/A              N/A          N/A           N/A
Ethernet-BP260   ALL8             N/A              N/A          N/A           N/A
Ethernet-BP260   ALL9             N/A              N/A          N/A           N/A
Ethernet-BP260  ALL10             N/A              N/A          N/A           N/A
Ethernet-BP260  ALL11             N/A              N/A          N/A           N/A
Ethernet-BP260  ALL12             N/A              N/A          N/A           N/A
Ethernet-BP260  ALL13             N/A              N/A          N/A           N/A
Ethernet-BP260  ALL14             N/A              N/A          N/A           N/A
Ethernet-BP260  ALL15             N/A              N/A          N/A           N/A

"""

show_queue_counters_port = """\
For namespace asic0:
        Port    TxQ    Counter/pkts    Counter/bytes    Drop/pkts    Drop/bytes
------------  -----  --------------  ---------------  -----------  ------------
Ethernet-BP4    UC0             116               78            8            26
Ethernet-BP4    UC1             117               79            7            25
Ethernet-BP4    UC2             118               80            6            24
Ethernet-BP4    UC3             119               81            5            23
Ethernet-BP4    UC4             120               82            4            22
Ethernet-BP4    UC5             121               83            3            21
Ethernet-BP4    UC6             122               84            2            20
Ethernet-BP4    UC7             123               85            1            19
Ethernet-BP4   ALL8             124               86            0            18
Ethernet-BP4   ALL9             125               87            1            17
Ethernet-BP4  ALL10             126               88            2            16
Ethernet-BP4  ALL11             127               89            3            15
Ethernet-BP4  ALL12             128               90            4            14
Ethernet-BP4  ALL13             129               91            5            13
Ethernet-BP4  ALL14             130               92            6            12
Ethernet-BP4  ALL15             131               93            7            11

"""

class TestQueueMultiAsic(object):
    @classmethod
    def setup_class(cls):
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        os.environ['UTILITIES_UNIT_TESTING_IS_SUP'] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        print("SETUP")

    def test_queue_counters(self):
        return_code, result = get_result_and_return_code(['queuestat', '-n', 'asic0'])
        assert return_code == 0
        print(result)
        assert result == show_queue_counters

    def test_queue_counters_port(self):
        return_code, result = get_result_and_return_code(['queuestat', '-p', 'Ethernet-BP4', '-n', 'asic0'])
        assert return_code == 0
        print(result)
        assert result == show_queue_counters_port

    def test_queue_counters_all_masic(self):
        return_code, result = get_result_and_return_code(['queuestat'])
        assert return_code == 0
        print(result)
        assert result == show_queue_counters_all_asics

    @classmethod
    def teardown_class(cls):
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        print("TEARDOWN")

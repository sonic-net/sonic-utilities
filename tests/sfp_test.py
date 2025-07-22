import sys
import os
from click.testing import CliRunner
from .mock_tables import dbconnector
from unittest.mock import patch, MagicMock

from utilities_common.platform_sfputil_helper import (
    load_platform_sfputil, logical_port_to_physical_port_index,
    logical_port_name_to_physical_port_list, is_sfp_present,
    get_first_subport, get_subport, get_sfp_object, get_value_from_db_by_field
)

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, modules_path)

import show.main as show
import show as show_module

ERROR_INVALID_PORT = 1
EXIT_FAIL = -1
ERROR_NOT_IMPLEMENTED = 2

test_sfp_eeprom_with_dom_output = """\
Ethernet0: SFP EEPROM detected
        Application Advertisement: N/A
        Connector: No separable connector
        Encoding: 64B66B
        Extended Identifier: Power Class 3(2.5W max), CDR present in Rx Tx
        Extended RateSelect Compliance: QSFP+ Rate Select Version 1
        Identifier: QSFP28 or later
        Length Cable Assembly(m): 3
        Nominal Bit Rate(100Mbs): 255
        Specification compliance:
                10/40G Ethernet Compliance Code: 40G Active Cable (XLPPI)
        Vendor Date Code(YYYY-MM-DD Lot): 2017-01-13
        Vendor Name: Mellanox
        Vendor OUI: 00-02-c9
        Vendor PN: MFA1A00-C003
        Vendor Rev: AC
        Vendor SN: MT1706FT02064
        ChannelMonitorValues:
                RX1Power: 0.3802dBm
                RX2Power: -0.4871dBm
                RX3Power: -0.0860dBm
                RX4Power: 0.3830dBm
                TX1Bias: 6.7500mA
                TX2Bias: 6.7500mA
                TX3Bias: 6.7500mA
                TX4Bias: 6.7500mA
        ChannelThresholdValues:
                RxPowerHighAlarm  : 3.4001dBm
                RxPowerHighWarning: 2.4000dBm
                RxPowerLowAlarm   : -13.5067dBm
                RxPowerLowWarning : -9.5001dBm
                TxBiasHighAlarm   : 10.0000mA
                TxBiasHighWarning : 9.5000mA
                TxBiasLowAlarm    : 0.5000mA
                TxBiasLowWarning  : 1.0000mA
        ModuleMonitorValues:
                Temperature: 30.9258C
                Vcc: 3.2824Volts
        ModuleThresholdValues:
                TempHighAlarm  : 75.0000C
                TempHighWarning: 70.0000C
                TempLowAlarm   : -5.0000C
                TempLowWarning : 0.0000C
                VccHighAlarm   : 3.6300Volts
                VccHighWarning : 3.4650Volts
                VccLowAlarm    : 2.9700Volts
                VccLowWarning  : 3.1349Volts
"""

test_qsfp_dd_eeprom_with_dom_output = """\
Ethernet8: SFP EEPROM detected
        Application Advertisement: 400GAUI-8 C2M (Annex 120E) - Active Cable assembly with BER < 2.6x10^-4
				   IB EDR (Arch.Spec.Vol.2) - Active Cable assembly with BER < 5x10^-5
				   IB QDR (Arch.Spec.Vol.2) - Active Cable assembly with BER < 10^-12
        Connector: No separable connector
        Encoding: Not supported for CMIS cables
        Extended Identifier: Power Class 1(10.0W Max)
        Extended RateSelect Compliance: Not supported for CMIS cables
        Identifier: QSFP-DD Double Density 8X Pluggable Transceiver
        Length Cable Assembly(m): 10
        Nominal Bit Rate(100Mbs): Not supported for CMIS cables
        Specification compliance: Not supported for CMIS cables
        Vendor Date Code(YYYY-MM-DD Lot): 2020-05-22
        Vendor Name: INNOLIGHT
        Vendor OUI: 44-7c-7f
        Vendor PN: C-DQ8FNM010-N00
        Vendor Rev: 2A
        Vendor SN: INKAO2900002A
        ChannelMonitorValues:
                RX1Power: -3.8595dBm
                RX2Power: 8.1478dBm
                RX3Power: -22.9243dBm
                RX4Power: 1.175dBm
                RX5Power: 1.2421dBm
                RX6Power: 8.1489dBm
                RX7Power: -3.5962dBm
                RX8Power: -3.6131dBm
                TX1Bias: 17.4760mA
                TX1Power: 1.175dBm
                TX2Bias: 17.4760mA
                TX2Power: 1.175dBm
                TX3Bias: 0.0000mA
                TX3Power: 1.175dBm
                TX4Bias: 0.0000mA
                TX4Power: 1.175dBm
                TX5Bias: 0.0000mA
                TX5Power: 1.175dBm
                TX6Bias: 8.2240mA
                TX6Power: 1.175dBm
                TX7Bias: 8.2240mA
                TX7Power: 1.175dBm
                TX8Bias: 8.2240mA
                TX8Power: 1.175dBm
        ChannelThresholdValues:
                RxPowerHighAlarm  : 6.9999dBm
                RxPowerHighWarning: 4.9999dBm
                RxPowerLowAlarm   : -11.9044dBm
                RxPowerLowWarning : -8.9008dBm
                TxBiasHighAlarm   : 14.9960mA
                TxBiasHighWarning : 12.9980mA
                TxBiasLowAlarm    : 4.4960mA
                TxBiasLowWarning  : 5.0000mA
                TxPowerHighAlarm  : 6.9999dBm
                TxPowerHighWarning: 4.9999dBm
                TxPowerLowAlarm   : -10.5012dBm
                TxPowerLowWarning : -7.5007dBm
        ModuleMonitorValues:
                Temperature: 44.9883C
                Vcc: 3.2999Volts
        ModuleThresholdValues:
                TempHighAlarm  : 80.0000C
                TempHighWarning: 75.0000C
                TempLowAlarm   : -10.0000C
                TempLowWarning : -5.0000C
                VccHighAlarm   : 3.6352Volts
                VccHighWarning : 3.4672Volts
                VccLowAlarm    : 2.9696Volts
                VccLowWarning  : 3.1304Volts
"""

test_osfp_eeprom_with_dom_output = """\
Ethernet72: SFP EEPROM detected
        Active Firmware: 0.0
        Active application selected code assigned to host lane 1: N/A
        Active application selected code assigned to host lane 2: N/A
        Active application selected code assigned to host lane 3: N/A
        Active application selected code assigned to host lane 4: N/A
        Active application selected code assigned to host lane 5: N/A
        Active application selected code assigned to host lane 6: N/A
        Active application selected code assigned to host lane 7: N/A
        Active application selected code assigned to host lane 8: N/A
        Application Advertisement: IB NDR - Host Assign (0x11) - Copper cable - Media Assign (Unknown)
                                   IB SDR (Arch.Spec.Vol.2) - Host Assign (0x11) - Copper cable - Media Assign (Unknown)
        CMIS Rev: 5.0
        Connector: No separable connector
        Encoding: N/A
        Extended Identifier: Power Class 1 (0.25W Max)
        Extended RateSelect Compliance: N/A
        Host Lane Count: 4
        Identifier: OSFP 8X Pluggable Transceiver
        Inactive Firmware: N/A
        Length Cable Assembly(m): 1.0
        Media Interface Technology: Copper cable unequalized
        Media Lane Count: 0
        Module Hardware Rev: 0.0
        Nominal Bit Rate(100Mbs): 0
        Specification compliance: passive_copper_media_interface
        Supported Max Laser Frequency: N/A
        Supported Max TX Power: N/A
        Supported Min Laser Frequency: N/A
        Supported Min TX Power: N/A
        Vendor Date Code(YYYY-MM-DD Lot): 2022-05-28   
        Vendor Name: vendor1          
        Vendor OUI: some-oui
        Vendor PN: some-model    
        Vendor Rev: A3
        Vendor SN: serial1   
        ChannelMonitorValues:
                RX1Power: 0.5dBm
                RX2Power: 0.3dBm
                RX3Power: 0.1dBm
                RX4Power: 0.7dBm
                RX5Power: 0.8dBm
                RX6Power: 0.2dBm
                RX7Power: 0.2dBm
                RX8Power: 0.3dBm
                TX1Bias: 6.5mA
                TX1Power: 0.6dBm
                TX2Bias: 6.5mA
                TX2Power: 0.4dBm
                TX3Bias: 6.6mA
                TX3Power: 0.2dBm
                TX4Bias: 6.7mA
                TX4Power: 0.8dBm
                TX5Bias: 6.4mA
                TX5Power: 0.9dBm
                TX6Bias: 6.3mA
                TX6Power: 0.1dBm
                TX7Bias: 6.2mA
                TX7Power: 0.5dBm
                TX8Bias: 6.1mA
                TX8Power: 0.4dBm
        ChannelThresholdValues:
        ModuleMonitorValues:
                Temperature: 40.5C
                Vcc: 3.331Volts
        ModuleThresholdValues:
"""

test_sfp_eeprom_output = """\
Ethernet0: SFP EEPROM detected
        Application Advertisement: N/A
        Connector: No separable connector
        Encoding: 64B66B
        Extended Identifier: Power Class 3(2.5W max), CDR present in Rx Tx
        Extended RateSelect Compliance: QSFP+ Rate Select Version 1
        Identifier: QSFP28 or later
        Length Cable Assembly(m): 3
        Nominal Bit Rate(100Mbs): 255
        Specification compliance:
                10/40G Ethernet Compliance Code: 40G Active Cable (XLPPI)
        Vendor Date Code(YYYY-MM-DD Lot): 2017-01-13
        Vendor Name: Mellanox
        Vendor OUI: 00-02-c9
        Vendor PN: MFA1A00-C003
        Vendor Rev: AC
        Vendor SN: MT1706FT02064
"""

test_qsfp_dd_eeprom_output = """\
Ethernet8: SFP EEPROM detected
        Application Advertisement: 400GAUI-8 C2M (Annex 120E) - Active Cable assembly with BER < 2.6x10^-4
				   IB EDR (Arch.Spec.Vol.2) - Active Cable assembly with BER < 5x10^-5
				   IB QDR (Arch.Spec.Vol.2) - Active Cable assembly with BER < 10^-12
        Connector: No separable connector
        Encoding: Not supported for CMIS cables
        Extended Identifier: Power Class 1(10.0W Max)
        Extended RateSelect Compliance: Not supported for CMIS cables
        Identifier: QSFP-DD Double Density 8X Pluggable Transceiver
        Length Cable Assembly(m): 10
        Nominal Bit Rate(100Mbs): Not supported for CMIS cables
        Specification compliance: Not supported for CMIS cables
        Vendor Date Code(YYYY-MM-DD Lot): 2020-05-22
        Vendor Name: INNOLIGHT
        Vendor OUI: 44-7c-7f
        Vendor PN: C-DQ8FNM010-N00
        Vendor Rev: 2A
        Vendor SN: INKAO2900002A
"""

test_qsfp_dd_eeprom_adv_app_output = """\
Ethernet40: SFP EEPROM detected
        Application Advertisement: 400G CR8 - Host Assign (0x1) - Copper cable - Media Assign (0x2)
                                   200GBASE-CR4 (Clause 136) - Host Assign (Unknown) - Unknown - Media Assign (Unknown)
        Connector: No separable connector
        Encoding: Not supported for CMIS cables
        Extended Identifier: Power Class 1(10.0W Max)
        Extended RateSelect Compliance: Not supported for CMIS cables
        Identifier: QSFP-DD Double Density 8X Pluggable Transceiver
        Length Cable Assembly(m): 10
        Nominal Bit Rate(100Mbs): Not supported for CMIS cables
        Specification compliance: Not supported for CMIS cables
        Vendor Date Code(YYYY-MM-DD Lot): 2020-05-22
        Vendor Name: INNOLIGHT
        Vendor OUI: 44-7c-7f
        Vendor PN: C-DQ8FNM010-N00
        Vendor Rev: 2A
        Vendor SN: INKAO2900002A
"""

test_qsfp_dd_pm_output = """\
Ethernet44:
    Parameter        Unit    Min       Avg       Max       Threshold    Threshold    Threshold     Threshold    Threshold    Threshold
                                                           High         High         Crossing      Low          Low          Crossing
                                                           Alarm        Warning      Alert-High    Alarm        Warning      Alert-Low
    ---------------  ------  --------  --------  --------  -----------  -----------  ------------  -----------  -----------  -----------
    Tx Power         dBm     -8.22     -8.23     -8.24     -5.0         -6.0         False         -16.99       -16.003      False
    Rx Total Power   dBm     -10.61    -10.62    -10.62    2.0          0.0          False         -21.0        -18.0        False
    Rx Signal Power  dBm     -40.0     0.0       40.0      13.0         10.0         True          -18.0        -15.0        True
    CD-short link    ps/nm   0.0       0.0       0.0       1000.0       500.0        False         -1000.0      -500.0       False
    PDL              dB      0.5       0.6       0.6       4.0          4.0          False         0.0          0.0          False
    OSNR             dB      36.5      36.5      36.5      99.0         99.0         False         0.0          0.0          False
    eSNR             dB      30.5      30.5      30.5      99.0         99.0         False         0.0          0.0          False
    CFO              MHz     54.0      70.0      121.0     3800.0       3800.0       False         -3800.0      -3800.0      False
    DGD              ps      5.37      5.56      5.81      7.0          7.0          False         0.0          0.0          False
    SOPMD            ps^2    0.0       0.0       0.0       655.35       655.35       False         0.0          0.0          False
    SOP ROC          krad/s  1.0       1.0       2.0       N/A          N/A          N/A           N/A          N/A          N/A
    Pre-FEC BER      N/A     4.58E-04  4.66E-04  5.76E-04  1.25E-02     1.10E-02     0.0           0.0          0.0          0.0
    Post-FEC BER     N/A     0.0       0.0       0.0       1000.0       1.0          False         0.0          0.0          False
    EVM              %       100.0     100.0     100.0     N/A          N/A          N/A           N/A          N/A          N/A
"""

test_qsfp_status_output = """\
Ethernet4:
        Tx fault flag on media lane 1: False
        Tx fault flag on media lane 2: False
        Tx fault flag on media lane 3: False
        Tx fault flag on media lane 4: False
        Rx loss of signal flag on media lane 1: False
        Rx loss of signal flag on media lane 2: False
        Rx loss of signal flag on media lane 3: False
        Rx loss of signal flag on media lane 4: False
        TX disable status on lane 1: False
        TX disable status on lane 2: False
        TX disable status on lane 3: False
        TX disable status on lane 4: False
        Disabled TX channels: 0
"""

test_qsfp_dd_status_output = """\
Ethernet44:
        CMIS State (SW): READY
        Tx fault flag on media lane 1: False
        Tx fault flag on media lane 2: False
        Tx fault flag on media lane 3: False
        Tx fault flag on media lane 4: False
        Tx fault flag on media lane 5: False
        Tx fault flag on media lane 6: False
        Tx fault flag on media lane 7: False
        Tx fault flag on media lane 8: False
        Rx loss of signal flag on media lane 1: False
        Rx loss of signal flag on media lane 2: False
        Rx loss of signal flag on media lane 3: False
        Rx loss of signal flag on media lane 4: False
        Rx loss of signal flag on media lane 5: False
        Rx loss of signal flag on media lane 6: False
        Rx loss of signal flag on media lane 7: False
        Rx loss of signal flag on media lane 8: False
        TX disable status on lane 1: False
        TX disable status on lane 2: False
        TX disable status on lane 3: False
        TX disable status on lane 4: False
        TX disable status on lane 5: False
        TX disable status on lane 6: False
        TX disable status on lane 7: False
        TX disable status on lane 8: False
        Disabled TX channels: 0
        Current module state: ModuleReady
        Reason of entering the module fault state: No Fault detected
        Datapath firmware fault: False
        Module firmware fault: False
        Module state changed: False
        Data path state indicator on host lane 1: DataPathActivated
        Data path state indicator on host lane 2: DataPathActivated
        Data path state indicator on host lane 3: DataPathActivated
        Data path state indicator on host lane 4: DataPathActivated
        Data path state indicator on host lane 5: DataPathActivated
        Data path state indicator on host lane 6: DataPathActivated
        Data path state indicator on host lane 7: DataPathActivated
        Data path state indicator on host lane 8: DataPathActivated
        Tx output status on media lane 1: False
        Tx output status on media lane 2: False
        Tx output status on media lane 3: False
        Tx output status on media lane 4: False
        Tx output status on media lane 5: False
        Tx output status on media lane 6: False
        Tx output status on media lane 7: False
        Tx output status on media lane 8: False
        Rx output status on host lane 1: True
        Rx output status on host lane 2: True
        Rx output status on host lane 3: True
        Rx output status on host lane 4: True
        Rx output status on host lane 5: True
        Rx output status on host lane 6: True
        Rx output status on host lane 7: True
        Rx output status on host lane 8: True
        Tx loss of signal flag on host lane 1: False
        Tx loss of signal flag on host lane 2: False
        Tx loss of signal flag on host lane 3: False
        Tx loss of signal flag on host lane 4: False
        Tx loss of signal flag on host lane 5: False
        Tx loss of signal flag on host lane 6: False
        Tx loss of signal flag on host lane 7: False
        Tx loss of signal flag on host lane 8: False
        Tx clock and data recovery loss of lock on host lane 1: False
        Tx clock and data recovery loss of lock on host lane 2: False
        Tx clock and data recovery loss of lock on host lane 3: False
        Tx clock and data recovery loss of lock on host lane 4: False
        Tx clock and data recovery loss of lock on host lane 5: False
        Tx clock and data recovery loss of lock on host lane 6: False
        Tx clock and data recovery loss of lock on host lane 7: False
        Tx clock and data recovery loss of lock on host lane 8: False
        Rx clock and data recovery loss of lock on media lane 1: False
        Rx clock and data recovery loss of lock on media lane 2: False
        Rx clock and data recovery loss of lock on media lane 3: False
        Rx clock and data recovery loss of lock on media lane 4: False
        Rx clock and data recovery loss of lock on media lane 5: False
        Rx clock and data recovery loss of lock on media lane 6: False
        Rx clock and data recovery loss of lock on media lane 7: False
        Rx clock and data recovery loss of lock on media lane 8: False
        Configuration status for the data path of host line 1: ConfigSuccess
        Configuration status for the data path of host line 2: ConfigSuccess
        Configuration status for the data path of host line 3: ConfigSuccess
        Configuration status for the data path of host line 4: ConfigSuccess
        Configuration status for the data path of host line 5: ConfigSuccess
        Configuration status for the data path of host line 6: ConfigSuccess
        Configuration status for the data path of host line 7: ConfigSuccess
        Configuration status for the data path of host line 8: ConfigSuccess
        Data path configuration updated on host lane 1: False
        Data path configuration updated on host lane 2: False
        Data path configuration updated on host lane 3: False
        Data path configuration updated on host lane 4: False
        Data path configuration updated on host lane 5: False
        Data path configuration updated on host lane 6: False
        Data path configuration updated on host lane 7: False
        Data path configuration updated on host lane 8: False
        Temperature high alarm flag: False
        Temperature high warning flag: False
        Temperature low warning flag: False
        Temperature low alarm flag: False
        Vcc high alarm flag: False
        Vcc high warning flag: False
        Vcc low warning flag: False
        Vcc low alarm flag: False
        Tx power high alarm flag on lane 1: False
        Tx power high alarm flag on lane 2: False
        Tx power high alarm flag on lane 3: False
        Tx power high alarm flag on lane 4: False
        Tx power high alarm flag on lane 5: False
        Tx power high alarm flag on lane 6: False
        Tx power high alarm flag on lane 7: False
        Tx power high alarm flag on lane 8: False
        Tx power high warning flag on lane 1: False
        Tx power high warning flag on lane 2: False
        Tx power high warning flag on lane 3: False
        Tx power high warning flag on lane 4: False
        Tx power high warning flag on lane 5: False
        Tx power high warning flag on lane 6: False
        Tx power high warning flag on lane 7: False
        Tx power high warning flag on lane 8: False
        Tx power low warning flag on lane 1: False
        Tx power low warning flag on lane 2: False
        Tx power low warning flag on lane 3: False
        Tx power low warning flag on lane 4: False
        Tx power low warning flag on lane 5: False
        Tx power low warning flag on lane 6: False
        Tx power low warning flag on lane 7: False
        Tx power low warning flag on lane 8: False
        Tx power low alarm flag on lane 1: False
        Tx power low alarm flag on lane 2: False
        Tx power low alarm flag on lane 3: False
        Tx power low alarm flag on lane 4: False
        Tx power low alarm flag on lane 5: False
        Tx power low alarm flag on lane 6: False
        Tx power low alarm flag on lane 7: False
        Tx power low alarm flag on lane 8: False
        Rx power high alarm flag on lane 1: False
        Rx power high alarm flag on lane 2: False
        Rx power high alarm flag on lane 3: False
        Rx power high alarm flag on lane 4: False
        Rx power high alarm flag on lane 5: False
        Rx power high alarm flag on lane 6: False
        Rx power high alarm flag on lane 7: False
        Rx power high alarm flag on lane 8: False
        Rx power high warning flag on lane 1: False
        Rx power high warning flag on lane 2: False
        Rx power high warning flag on lane 3: False
        Rx power high warning flag on lane 4: False
        Rx power high warning flag on lane 5: False
        Rx power high warning flag on lane 6: False
        Rx power high warning flag on lane 7: False
        Rx power high warning flag on lane 8: False
        Rx power low warning flag on lane 1: False
        Rx power low warning flag on lane 2: False
        Rx power low warning flag on lane 3: False
        Rx power low warning flag on lane 4: False
        Rx power low warning flag on lane 5: False
        Rx power low warning flag on lane 6: False
        Rx power low warning flag on lane 7: False
        Rx power low warning flag on lane 8: False
        Rx power low alarm flag on lane 1: False
        Rx power low alarm flag on lane 2: False
        Rx power low alarm flag on lane 3: False
        Rx power low alarm flag on lane 4: False
        Rx power low alarm flag on lane 5: False
        Rx power low alarm flag on lane 6: False
        Rx power low alarm flag on lane 7: False
        Rx power low alarm flag on lane 8: False
        Tx bias high alarm flag on lane 1: False
        Tx bias high alarm flag on lane 2: False
        Tx bias high alarm flag on lane 3: False
        Tx bias high alarm flag on lane 4: False
        Tx bias high alarm flag on lane 5: False
        Tx bias high alarm flag on lane 6: False
        Tx bias high alarm flag on lane 7: False
        Tx bias high alarm flag on lane 8: False
        Tx bias high warning flag on lane 1: False
        Tx bias high warning flag on lane 2: False
        Tx bias high warning flag on lane 3: False
        Tx bias high warning flag on lane 4: False
        Tx bias high warning flag on lane 5: False
        Tx bias high warning flag on lane 6: False
        Tx bias high warning flag on lane 7: False
        Tx bias high warning flag on lane 8: False
        Tx bias low warning flag on lane 1: False
        Tx bias low warning flag on lane 2: False
        Tx bias low warning flag on lane 3: False
        Tx bias low warning flag on lane 4: False
        Tx bias low warning flag on lane 5: False
        Tx bias low warning flag on lane 6: False
        Tx bias low warning flag on lane 7: False
        Tx bias low warning flag on lane 8: False
        Tx bias low alarm flag on lane 1: False
        Tx bias low alarm flag on lane 2: False
        Tx bias low alarm flag on lane 3: False
        Tx bias low alarm flag on lane 4: False
        Tx bias low alarm flag on lane 5: False
        Tx bias low alarm flag on lane 6: False
        Tx bias low alarm flag on lane 7: False
        Tx bias low alarm flag on lane 8: False
        Laser temperature high alarm flag: False
        Laser temperature high warning flag: False
        Laser temperature low warning flag: False
        Laser temperature low alarm flag: False
        Prefec ber high alarm flag: False
        Prefec ber high warning flag: False
        Prefec ber low warning flag: False
        Prefec ber low alarm flag: False
        Postfec ber high alarm flag: False
        Postfec ber high warning flag: False
        Postfec ber low warning flag: False
        Postfec ber low alarm flag: False
        Tuning in progress status: False
        Laser unlocked status: False
        Target output power out of range flag: False
        Fine tuning out of range flag: False
        Tuning not accepted flag: False
        Invalid channel number flag: False
        Tuning complete flag: False
        Bias xi high alarm flag: False
        Bias xi high warning flag: False
        Bias xi low warning flag: False
        Bias xi low alarm flag: False
        Bias xq high alarm flag: False
        Bias xq high warning flag: False
        Bias xq low warning flag: False
        Bias xq low alarm flag: False
        Bias xp high alarm flag: False
        Bias xp high warning flag: False
        Bias xp low warning flag: False
        Bias xp low alarm flag: False
        Bias yi high alarm flag: False
        Bias yi high warning flag: False
        Bias yi low warning flag: False
        Bias yi low alarm flag: False
        Bias yq high alarm flag: False
        Bias yq high warning flag: False
        Bias yq low warning flag: False
        Bias yq low alarm flag: False
        Bias yp high alarm flag: False
        Bias yp high warning flag: False
        Bias yp low warning flag: False
        Bias yp low alarm flag: False
        CD short high alarm flag: False
        CD short high warning flag: False
        CD short low warning flag: False
        CD short low alarm flag: False
        CD long high alarm flag: False
        CD long high warning flag: False
        CD long low warning flag: False
        CD long low alarm flag: False
        DGD high alarm flag: False
        DGD high warning flag: False
        DGD low warning flag: False
        DGD low alarm flag: False
        PDL high alarm flag: False
        PDL high warning flag: False
        PDL low warning flag: False
        PDL low alarm flag: False
        OSNR high alarm flag: False
        OSNR high warning flag: False
        OSNR low warning flag: False
        OSNR low alarm flag: False
        ESNR high alarm flag: False
        ESNR high warning flag: False
        ESNR low warning flag: False
        ESNR low alarm flag: False
        CFO high alarm flag: False
        CFO high warning flag: False
        CFO low warning flag: False
        CFO low alarm flag: False
        Txcurrpower high alarm flag: False
        Txcurrpower high warning flag: False
        Txcurrpower low warning flag: False
        Txcurrpower low alarm flag: False
        Rxtotpower high alarm flag: False
        Rxtotpower high warning flag: False
        Rxtotpower low warning flag: False
        Rxtotpower low alarm flag: False
"""

test_cmis_eeprom_output = """\
Ethernet64: SFP EEPROM detected
        Active Firmware: X.X
        Active application selected code assigned to host lane 1: 1
        Active application selected code assigned to host lane 2: 1
        Active application selected code assigned to host lane 3: 1
        Active application selected code assigned to host lane 4: 1
        Active application selected code assigned to host lane 5: 1
        Active application selected code assigned to host lane 6: 1
        Active application selected code assigned to host lane 7: 1
        Active application selected code assigned to host lane 8: 1
        Application Advertisement: 400GAUI-8 C2M (Annex 120E) - Host Assign (0x1) - 400ZR, DWDM, amplified - Media Assign (0x1)
                                   400GAUI-8 C2M (Annex 120E) - Host Assign (0x1) - 400ZR, Single Wavelength, Unamplified - Media Assign (0x1)
                                   100GAUI-2 C2M (Annex 135G) - Host Assign (0x55) - 400ZR, DWDM, amplified - Media Assign (0x1)
        CMIS Rev: 4.1
        Connector: LC
        E1 Active Firmware: X.X
        E1 Inactive Firmware: Y.Y
        E1 Server Firmware: A.B.C.D
        E2 Active Firmware: X.X
        E2 Inactive Firmware: Y.Y
        E2 Server Firmware: A.B.C.D
        Encoding: N/A
        Extended Identifier: Power Class 8 (20.0W Max)
        Extended RateSelect Compliance: N/A
        Host Lane Count: 8
        Identifier: QSFP-DD Double Density 8X Pluggable Transceiver
        Inactive Firmware: X.X
        Length Cable Assembly(m): 0.0
        Media Interface Technology: 1550 nm DFB
        Media Lane Count: 1
        Module Hardware Rev: X.X
        Nominal Bit Rate(100Mbs): 0
        Specification compliance: sm_media_interface
        Supported Max Laser Frequency: 196100
        Supported Max TX Power: 4.0
        Supported Min Laser Frequency: 191300
        Supported Min TX Power: -22.9
        Vendor Date Code(YYYY-MM-DD Lot): 2021-11-19
        Vendor Name: XXXX
        Vendor OUI: XX-XX-XX
        Vendor PN: XXX
        Vendor Rev: XX
        Vendor SN: 0123456789
"""

test_sfp_eeprom_dom_all_output = """\
Ethernet0: SFP EEPROM detected
        Application Advertisement: N/A
        Connector: No separable connector
        Encoding: 64B66B
        Extended Identifier: Power Class 3(2.5W max), CDR present in Rx Tx
        Extended RateSelect Compliance: QSFP+ Rate Select Version 1
        Identifier: QSFP28 or later
        Length Cable Assembly(m): 3
        Nominal Bit Rate(100Mbs): 255
        Specification compliance:
                10/40G Ethernet Compliance Code: 40G Active Cable (XLPPI)
        Vendor Date Code(YYYY-MM-DD Lot): 2017-01-13
        Vendor Name: Mellanox
        Vendor OUI: 00-02-c9
        Vendor PN: MFA1A00-C003
        Vendor Rev: AC
        Vendor SN: MT1706FT02064
        ChannelMonitorValues:
                RX1Power: 0.3802dBm
                RX2Power: -0.4871dBm
                RX3Power: -0.0860dBm
                RX4Power: 0.3830dBm
                TX1Bias: 6.7500mA
                TX2Bias: 6.7500mA
                TX3Bias: 6.7500mA
                TX4Bias: 6.7500mA
        ChannelThresholdValues:
                RxPowerHighAlarm  : 3.4001dBm
                RxPowerHighWarning: 2.4000dBm
                RxPowerLowAlarm   : -13.5067dBm
                RxPowerLowWarning : -9.5001dBm
                TxBiasHighAlarm   : 10.0000mA
                TxBiasHighWarning : 9.5000mA
                TxBiasLowAlarm    : 0.5000mA
                TxBiasLowWarning  : 1.0000mA
        ModuleMonitorValues:
                Temperature: 30.9258C
                Vcc: 3.2824Volts
        ModuleThresholdValues:
                TempHighAlarm  : 75.0000C
                TempHighWarning: 70.0000C
                TempLowAlarm   : -5.0000C
                TempLowWarning : 0.0000C
                VccHighAlarm   : 3.6300Volts
                VccHighWarning : 3.4650Volts
                VccLowAlarm    : 2.9700Volts
                VccLowWarning  : 3.1349Volts

Ethernet4: SFP EEPROM Not detected

Ethernet64: SFP EEPROM detected
        Active Firmware: X.X
        Active application selected code assigned to host lane 1: 1
        Active application selected code assigned to host lane 2: 1
        Active application selected code assigned to host lane 3: 1
        Active application selected code assigned to host lane 4: 1
        Active application selected code assigned to host lane 5: 1
        Active application selected code assigned to host lane 6: 1
        Active application selected code assigned to host lane 7: 1
        Active application selected code assigned to host lane 8: 1
        Application Advertisement: 400GAUI-8 C2M (Annex 120E) - Host Assign (0x1) - 400ZR, DWDM, amplified - Media Assign (0x1)
                                   400GAUI-8 C2M (Annex 120E) - Host Assign (0x1) - 400ZR, Single Wavelength, Unamplified - Media Assign (0x1)
                                   100GAUI-2 C2M (Annex 135G) - Host Assign (0x55) - 400ZR, DWDM, amplified - Media Assign (0x1)
        CMIS Rev: 4.1
        Connector: LC
        E1 Active Firmware: X.X
        E1 Inactive Firmware: Y.Y
        E1 Server Firmware: A.B.C.D
        E2 Active Firmware: X.X
        E2 Inactive Firmware: Y.Y
        E2 Server Firmware: A.B.C.D
        Encoding: N/A
        Extended Identifier: Power Class 8 (20.0W Max)
        Extended RateSelect Compliance: N/A
        Host Lane Count: 8
        Identifier: QSFP-DD Double Density 8X Pluggable Transceiver
        Inactive Firmware: X.X
        Length Cable Assembly(m): 0.0
        Media Interface Technology: 1550 nm DFB
        Media Lane Count: 1
        Module Hardware Rev: X.X
        Nominal Bit Rate(100Mbs): 0
        Specification compliance: sm_media_interface
        Supported Max Laser Frequency: 196100
        Supported Max TX Power: 4.0
        Supported Min Laser Frequency: 191300
        Supported Min TX Power: -22.9
        Vendor Date Code(YYYY-MM-DD Lot): 2021-11-19
        Vendor Name: XXXX
        Vendor OUI: XX-XX-XX
        Vendor PN: XXX
        Vendor Rev: XX
        Vendor SN: 0123456789
        ChannelMonitorValues:
                RX1Power: 0.3802dBm
                RX2Power: -0.4871dBm
                RX3Power: -0.0860dBm
                RX4Power: 0.3830dBm
                TX1Bias: 6.7500mA
                TX2Bias: 6.7500mA
                TX3Bias: 6.7500mA
                TX4Bias: 6.7500mA
        ChannelThresholdValues:
                RxPowerHighAlarm  : 3.4001dBm
                RxPowerHighWarning: 2.4000dBm
                RxPowerLowAlarm   : -13.5067dBm
                RxPowerLowWarning : -9.5001dBm
                TxBiasHighAlarm   : 10.0000mA
                TxBiasHighWarning : 9.5000mA
                TxBiasLowAlarm    : 0.5000mA
                TxBiasLowWarning  : 1.0000mA
        ModuleMonitorValues:
                Temperature: 30.9258C
                Vcc: 3.2824Volts
        ModuleThresholdValues:
                TempHighAlarm  : 75.0000C
                TempHighWarning: 70.0000C
                TempLowAlarm   : -5.0000C
                TempLowWarning : 0.0000C
                VccHighAlarm   : 3.6300Volts
                VccHighWarning : 3.4650Volts
                VccLowAlarm    : 2.9700Volts
                VccLowWarning  : 3.1349Volts
"""

test_sfp_eeprom_all_output = """\
Ethernet0: SFP EEPROM detected
        Application Advertisement: N/A
        Connector: No separable connector
        Encoding: 64B66B
        Extended Identifier: Power Class 3(2.5W max), CDR present in Rx Tx
        Extended RateSelect Compliance: QSFP+ Rate Select Version 1
        Identifier: QSFP28 or later
        Length Cable Assembly(m): 3
        Nominal Bit Rate(100Mbs): 255
        Specification compliance:
                10/40G Ethernet Compliance Code: 40G Active Cable (XLPPI)
        Vendor Date Code(YYYY-MM-DD Lot): 2017-01-13
        Vendor Name: Mellanox
        Vendor OUI: 00-02-c9
        Vendor PN: MFA1A00-C003
        Vendor Rev: AC
        Vendor SN: MT1706FT02064

Ethernet4: SFP EEPROM Not detected

Ethernet64: SFP EEPROM detected
        Active Firmware: X.X
        Active application selected code assigned to host lane 1: 1
        Active application selected code assigned to host lane 2: 1
        Active application selected code assigned to host lane 3: 1
        Active application selected code assigned to host lane 4: 1
        Active application selected code assigned to host lane 5: 1
        Active application selected code assigned to host lane 6: 1
        Active application selected code assigned to host lane 7: 1
        Active application selected code assigned to host lane 8: 1
        Application Advertisement: 400GAUI-8 C2M (Annex 120E) - Host Assign (0x1) - 400ZR, DWDM, amplified - Media Assign (0x1)
                                   400GAUI-8 C2M (Annex 120E) - Host Assign (0x1) - 400ZR, Single Wavelength, Unamplified - Media Assign (0x1)
                                   100GAUI-2 C2M (Annex 135G) - Host Assign (0x55) - 400ZR, DWDM, amplified - Media Assign (0x1)
        CMIS Rev: 4.1
        Connector: LC
        E1 Active Firmware: X.X
        E1 Inactive Firmware: Y.Y
        E1 Server Firmware: A.B.C.D
        E2 Active Firmware: X.X
        E2 Inactive Firmware: Y.Y
        E2 Server Firmware: A.B.C.D
        Encoding: N/A
        Extended Identifier: Power Class 8 (20.0W Max)
        Extended RateSelect Compliance: N/A
        Host Lane Count: 8
        Identifier: QSFP-DD Double Density 8X Pluggable Transceiver
        Inactive Firmware: X.X
        Length Cable Assembly(m): 0.0
        Media Interface Technology: 1550 nm DFB
        Media Lane Count: 1
        Module Hardware Rev: X.X
        Nominal Bit Rate(100Mbs): 0
        Specification compliance: sm_media_interface
        Supported Max Laser Frequency: 196100
        Supported Max TX Power: 4.0
        Supported Min Laser Frequency: 191300
        Supported Min TX Power: -22.9
        Vendor Date Code(YYYY-MM-DD Lot): 2021-11-19
        Vendor Name: XXXX
        Vendor OUI: XX-XX-XX
        Vendor PN: XXX
        Vendor Rev: XX
        Vendor SN: 0123456789
"""

test_sfp_presence_all_output = """\
Port        Presence
----------  -----------
Ethernet0   Present
Ethernet4   Not present
Ethernet64  Present
"""

test_qsfp_dd_pm_all_output = """\
Ethernet0: Transceiver performance monitoring not applicable

Ethernet4: Transceiver performance monitoring not applicable

Ethernet64: Transceiver performance monitoring not applicable
"""

test_qsfp_dd_status_all_output = """\
Ethernet0: Transceiver status info not applicable

Ethernet4: Transceiver status info not applicable

Ethernet64: Transceiver status info not applicable
"""

class TestSFP(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"

    def test_sfp_presence(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["presence"], ["Ethernet0"])
        expected = """Port       Presence
---------  ----------
Ethernet0  Present
"""
        assert result.exit_code == 0
        assert result.output == expected

        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["presence"], ["Ethernet200"])
        expected = """Port         Presence
-----------  -----------
Ethernet200  Not present
"""
        assert result.exit_code == 0
        assert result.output == expected

        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["presence"], ["Ethernet16"])
        expected = """Port        Presence
----------  ----------
Ethernet16  Present
"""
        assert result.exit_code == 0
        assert result.output == expected

        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["presence"], ["Ethernet28"])
        expected = """Port        Presence
----------  ----------
Ethernet28  Present
"""
        assert result.exit_code == 0
        assert result.output == expected

        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["presence"], ["Ethernet29"])
        expected = """Port        Presence
----------  -----------
Ethernet29  Not present
"""
        assert result.exit_code == 0
        assert result.output == expected

        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["presence"], ["Ethernet36"])
        expected = """Port        Presence
----------  ----------
Ethernet36  Present
"""
        assert result.exit_code == 0
        assert result.output == expected

    def test_sfp_dpc_ports(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["presence"])
        assert result.exit_code == 0
        assert "Ethernet24" not in result.output

        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"])
        assert result.exit_code == 0
        assert "Ethernet24" not in result.output

        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["status"])
        assert result.exit_code == 0
        assert "Ethernet24" not in result.output

        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["pm"])
        assert result.exit_code == 0
        assert "Ethernet24" not in result.output

        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["info"])
        assert result.exit_code == 0
        assert "Ethernet24" not in result.output

    def test_sfp_eeprom_with_dom(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ["Ethernet0", "-d"])
        assert result.exit_code == 0
        assert "\n".join([ l.rstrip() for l in result.output.split('\n')]) == test_sfp_eeprom_with_dom_output

    def test_qsfp_dd_eeprom_with_dom(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ["Ethernet8", "-d"])
        assert result.exit_code == 0
        assert result.output == test_qsfp_dd_eeprom_with_dom_output
        
    def test_osfp_eeprom_with_dom(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ["Ethernet72", "-d"])
        assert result.exit_code == 0
        assert result.output == test_osfp_eeprom_with_dom_output

    def test_sfp_eeprom(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ["Ethernet0"])
        assert result.exit_code == 0
        assert "\n".join([ l.rstrip() for l in result.output.split('\n')]) == test_sfp_eeprom_output

        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ["Ethernet200"])
        result_lines = result.output.strip('\n')
        expected = "Ethernet200: SFP EEPROM Not detected"
        assert result_lines == expected

    def test_qsfp_dd_eeprom(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ["Ethernet8"])
        assert result.exit_code == 0
        assert result.output == test_qsfp_dd_eeprom_output

    def test_qsfp_dd_eeprom_adv_app(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ["Ethernet40"])
        assert result.exit_code == 0
        print(result.output)
        assert result.output == test_qsfp_dd_eeprom_adv_app_output

    def test_cmis_info(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["info"], ["Ethernet64"])
        assert result.exit_code == 0
        assert result.output == test_cmis_eeprom_output

    def test_rj45_eeprom(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ["Ethernet36"])
        result_lines = result.output.strip('\n')
        expected = "Ethernet36: SFP EEPROM is not applicable for RJ45 port"
        assert result_lines == expected

    def test_qsfp_dd_pm(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["pm"], ["Ethernet44"])
        assert result.exit_code == 0
        assert "\n".join([ l.rstrip() for l in result.output.split('\n')]) == test_qsfp_dd_pm_output

        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["pm"], ["Ethernet200"])
        result_lines = result.output.strip('\n')
        expected = "Ethernet200: Transceiver performance monitoring not applicable"
        assert result_lines == expected

    def test_qsfp_status(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["status"], ["Ethernet4"])
        assert result.exit_code == 0
        assert "\n".join([ l.rstrip() for l in result.output.split('\n')]) == test_qsfp_status_output

    def test_qsfp_dd_status(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["status"], ["Ethernet44"])
        assert result.exit_code == 0
        assert "\n".join([ l.rstrip() for l in result.output.split('\n')]) == test_qsfp_dd_status_output

        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["status"], ["Ethernet200"])
        result_lines = result.output.strip('\n')
        expected = "Ethernet200: Transceiver status info not applicable"
        assert result_lines == expected

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""

class Test_multiAsic_SFP(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"

    def test_sfp_presence_without_ns(self):
        runner = CliRunner()
        result = runner.invoke(
                show.cli.commands["interfaces"].commands["transceiver"].commands["presence"], ['Ethernet0'])
        expected = """Port       Presence
---------  ----------
Ethernet0  Present
"""
        assert result.exit_code == 0
        assert result.output == expected

        result = runner.invoke(
                show.cli.commands["interfaces"].commands["transceiver"].commands["presence"], ['Ethernet4'])
        expected = """Port       Presence
---------  -----------
Ethernet4  Not present
"""
        assert result.exit_code == 0
        assert result.output == expected

        result = runner.invoke(
                show.cli.commands["interfaces"].commands["transceiver"].commands["presence"], ['Ethernet200'])
        expected = """Port         Presence
-----------  -----------
Ethernet200  Not present
"""
        assert result.exit_code == 1
        assert result.output == expected

    @patch.object(show_module.interfaces.click.Choice, 'convert', MagicMock(return_value='asic0'))
    def test_sfp_presence_with_ns(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["presence"], ['Ethernet0', '-n', 'asic0'])
        expected = """Port       Presence
---------  ----------
Ethernet0  Present
"""
        assert result.exit_code == 0
        assert result.output == expected

        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["presence"], ['Ethernet200', '-n', 'asic0'])
        expected = """Port         Presence
-----------  -----------
Ethernet200  Not present
"""
        assert result.exit_code == 0
        assert result.output == expected

    def test_sfp_presence_all(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["presence"])
        assert result.exit_code == 0
        assert "\n".join([ l.rstrip() for l in result.output.split('\n')]) == test_sfp_presence_all_output

    @patch.object(show_module.interfaces.click.Choice, 'convert', MagicMock(return_value='asic0'))
    def test_sfp_eeprom_with_dom_with_ns(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ['Ethernet0', '-d', '-n', 'asic0'])
        assert result.exit_code == 0
        assert "\n".join([ l.rstrip() for l in result.output.split('\n')]) == test_sfp_eeprom_with_dom_output

    @patch.object(show_module.interfaces.click.Choice, 'convert', MagicMock(return_value='asic0'))
    def test_sfp_eeprom_with_ns(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ['Ethernet0', '-n', 'asic0'])
        assert result.exit_code == 0
        assert "\n".join([ l.rstrip() for l in result.output.split('\n')]) == test_sfp_eeprom_output

        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ['Ethernet200', '-n', 'asic0'])
        result_lines = result.output.strip('\n')
        expected = "Ethernet200: SFP EEPROM Not detected"
        assert result_lines == expected

    def test_sfp_eeprom_without_ns(self):
        runner = CliRunner()
        result = runner.invoke(
                show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ['Ethernet0'])
        assert result.exit_code == 0
        assert "\n".join([line.rstrip() for line in result.output.split('\n')]) == test_sfp_eeprom_output

        result = runner.invoke(
                show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ['Ethernet4'])
        result_lines = result.output.strip('\n')
        expected = "Ethernet4: SFP EEPROM Not detected"
        assert result_lines == expected

    @patch.object(show_module.interfaces.click.Choice, 'convert', MagicMock(return_value='asic0'))
    def test_qsfp_dd_pm_with_ns(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["pm"], ['Ethernet0', '-n', 'asic0'])
        result_lines = result.output.strip('\n')
        expected = "Ethernet0: Transceiver performance monitoring not applicable"
        assert result_lines == expected

    def test_qsfp_dd_pm_without_ns(self):
        runner = CliRunner()
        result = runner.invoke(
                show.cli.commands["interfaces"].commands["transceiver"].commands["pm"], ['Ethernet0'])
        result_lines = result.output.strip('\n')
        expected = "Ethernet0: Transceiver performance monitoring not applicable"
        assert result_lines == expected

    @patch.object(show_module.interfaces.click.Choice, 'convert', MagicMock(return_value='asic0'))
    def test_qsfp_dd_status_with_ns(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["status"], ['Ethernet0', '-n', 'asic0'])
        result_lines = result.output.strip('\n')
        expected = "Ethernet0: Transceiver status info not applicable"
        assert result_lines == expected

    def test_qsfp_dd_status_without_ns(self):
        runner = CliRunner()
        result = runner.invoke(
                show.cli.commands["interfaces"].commands["transceiver"].commands["status"], ['Ethernet0'])
        result_lines = result.output.strip('\n')
        expected = "Ethernet0: Transceiver status info not applicable"
        assert result_lines == expected

    @patch.object(show_module.interfaces.click.Choice, 'convert', MagicMock(return_value='asic1'))
    def test_cmis_sfp_info_with_ns(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["info"], ['Ethernet64', '-n', 'asic1'])
        assert result.exit_code == 0
        assert "\n".join([ l.rstrip() for l in result.output.split('\n')]) == test_cmis_eeprom_output

    def test_cmis_sfp_info_without_ns(self):
        runner = CliRunner()
        result = runner.invoke(
                show.cli.commands["interfaces"].commands["transceiver"].commands["info"], ['Ethernet64'])
        assert result.exit_code == 0
        assert "\n".join([line.rstrip() for line in result.output.split('\n')]) == test_cmis_eeprom_output

    def test_sfp_eeprom_all(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"])
        assert result.exit_code == 0
        assert "\n".join([ l.rstrip() for l in result.output.split('\n')]) == test_sfp_eeprom_all_output

    def test_sfp_info_all(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["info"])
        assert result.exit_code == 0
        assert "\n".join([ l.rstrip() for l in result.output.split('\n')]) == test_sfp_eeprom_all_output

    def test_sfp_eeprom_dom_all(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["eeprom"], ["-d"])
        assert result.exit_code == 0
        assert "\n".join([ l.rstrip() for l in result.output.split('\n')]) == test_sfp_eeprom_dom_all_output

    def test_is_rj45_port(self):
        import utilities_common.platform_sfputil_helper as platform_sfputil_helper
        platform_sfputil_helper.platform_chassis = None
        if 'sonic_platform' in sys.modules:
            sys.modules.pop('sonic_platform')
        assert platform_sfputil_helper.is_rj45_port("Ethernet0") == False

    def test_qsfp_dd_pm_all(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["pm"])
        assert result.exit_code == 0
        assert "\n".join([ l.rstrip() for l in result.output.split('\n')]) == test_qsfp_dd_pm_all_output

    def test_qsfp_dd_status_all(self):
        runner = CliRunner()
        result = runner.invoke(show.cli.commands["interfaces"].commands["transceiver"].commands["status"])
        assert result.exit_code == 0
        assert "\n".join([ l.rstrip() for l in result.output.split('\n')]) == test_qsfp_dd_status_all_output

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""


class TestMultiAsicSFP(object):

    @patch('utilities_common.platform_sfputil_helper.platform_chassis', None)
    def test_load_platform_sfputil(self):
        # Test that the function returns 0 as expected
        assert load_platform_sfputil() == 0

    @patch('utilities_common.platform_sfputil_helper.platform_sfputil',
           MagicMock(is_logical_port=MagicMock(return_value=1)))
    @patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list',
           MagicMock(return_value=[1]))
    @patch('utilities_common.platform_sfputil_helper.platform_chassis')
    @patch('utilities_common.platform_sfputil_helper.is_rj45_port')
    def test_logical_port_to_physical_port_index(self, mock_is_rj45_port, mock_chassis):
        mock_sfp = MagicMock()
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        # Test for sfp presence
        mock_is_rj45_port.return_value = False

        port_name = "Ethernet0"
        result = logical_port_to_physical_port_index(port_name)
        assert result == 1

    @patch('utilities_common.platform_sfputil_helper.logical_port_to_physical_port_index',
           MagicMock(return_value=1))
    @patch('utilities_common.platform_sfputil_helper.platform_sfputil',
           MagicMock(is_logical_port=MagicMock(return_value=1)))
    @patch('utilities_common.platform_sfputil_helper.platform_chassis')
    @patch('utilities_common.platform_sfputil_helper.is_rj45_port')
    def test_logical_port_name_to_physical_port_list(self, mock_is_rj45_port, mock_chassis):
        # Set up mocks
        mock_sfp = MagicMock()
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        # Test for sfp presence
        mock_is_rj45_port.return_value = False

        port_name = "Ethernet0"
        result = logical_port_name_to_physical_port_list(port_name)
        assert result is not None
        mock_is_rj45_port.return_value = False

    @patch('utilities_common.platform_sfputil_helper.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('utilities_common.platform_sfputil_helper.platform_chassis')
    @patch('utilities_common.platform_sfputil_helper.is_rj45_port')
    def test_is_sfp_present(self, mock_is_rj45_port, mock_chassis):
        mock_sfp = MagicMock()
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        # Test for sfp presence
        mock_is_rj45_port.return_value = False

        result = is_sfp_present("Ethernet0")
        assert result is True  # or whatever the expected result is

    @patch('utilities_common.platform_sfputil_helper.logical_port_to_physical_port_index', MagicMock(return_value=1))
    @patch('utilities_common.platform_sfputil_helper.is_sfp_present')
    @patch('utilities_common.platform_sfputil_helper.platform_chassis')
    @patch('utilities_common.platform_sfputil_helper.is_rj45_port')
    def test_get_sfp_object(self, mock_is_rj45_port, mock_chassis, sfp_present):
        mock_sfp = MagicMock()
        mock_chassis.get_sfp = MagicMock(return_value=mock_sfp)
        # Test for sfp presence
        mock_is_rj45_port.return_value = False

        result = get_sfp_object(1)
        assert result == mock_sfp
        mock_is_rj45_port.return_value = True
        sfp_present.return_value = True

        try:
            get_sfp_object(1)
            assert False, "Expected SystemExit but it did not occur"
        except SystemExit as e:
            assert e.code == EXIT_FAIL
        mock_is_rj45_port.return_value = False
        sfp_present.return_value = False
        try:
            get_sfp_object(1)
            assert False, "Expected SystemExit but it did not occur"
        except SystemExit as e:
            assert e.code == EXIT_FAIL

    @patch('utilities_common.platform_sfputil_helper.platform_sfputil',
           MagicMock(get_physical_to_logical=MagicMock(return_value=["Ethernet0", "Ethernet4"])))
    @patch('utilities_common.platform_sfputil_helper.platform_sfputil',
           MagicMock(get_logical_to_physical=MagicMock(return_value=[1])))
    def test_get_first_subport(self):
        assert get_first_subport("Ethernet0") == "Ethernet0"

    @patch('utilities_common.platform_sfputil_helper.platform_sfputil',
           MagicMock(get_logical_to_physical=MagicMock(return_value=None)))
    def test_get_first_subport_invalid_physical_port(self):
        assert get_first_subport("Ethernet0") is None

    @patch('utilities_common.platform_sfputil_helper.platform_sfputil',
           MagicMock(get_physical_to_logical=MagicMock(side_effect=KeyError)))
    @patch('utilities_common.platform_sfputil_helper.platform_sfputil',
           MagicMock(get_logical_to_physical=MagicMock(return_value=[1])))
    def test_get_first_subport_keyerror(self):
        assert get_first_subport("Ethernet0") is None

    @patch('utilities_common.platform_sfputil_helper.get_value_from_db_by_field')
    def test_get_subport(self, mock_get_value_from_db_by_field):
        mock_get_value_from_db_by_field.return_value = '2'

        # assuming config_db is passed or mocked elsewhere
        result = get_subport("Ethernet0")
        assert result == 2

    @patch('utilities_common.platform_sfputil_helper.SonicV2Connector')
    @patch('utilities_common.platform_sfputil_helper.ConfigDBConnector')
    @patch('utilities_common.platform_sfputil_helper.multi_asic.get_namespace_for_port', return_value='asic0')
    def test_get_value_from_db_by_field(self, mock_get_namespace, mock_config_db, mock_sonic_db):
        # Mock CONFIG_DB case
        mock_config_instance = MagicMock()
        mock_config_instance.get.return_value = "test_value"
        mock_config_instance.connect.return_value = None  # No actual connection
        mock_config_db.return_value = mock_config_instance

        # Mock for SonicV2Connector case
        mock_sonic_instance = MagicMock()
        mock_sonic_instance.get.return_value = "test_value"
        mock_sonic_instance.connect.return_value = None  # Mock connect to not do anything
        mock_sonic_db.return_value = mock_sonic_instance

        # Now call function
        result = get_value_from_db_by_field("CONFIG_DB", "TEST_TABLE", "test_field", "Ethernet0")
        assert result == "test_value"
        mock_config_instance.connect.assert_called_once()
        mock_config_instance.get.assert_called_once_with("CONFIG_DB", "TEST_TABLE|Ethernet0", "test_field")
        # Mock STATE_DB case

        mock_sonic_instance.get.return_value = "state_value"
        result = get_value_from_db_by_field("STATE_DB", "TEST_TABLE", "test_field", "Ethernet0")
        assert result == "state_value"
        mock_sonic_instance.get.assert_called_once_with("STATE_DB", "TEST_TABLE|Ethernet0", "test_field")
        mock_sonic_instance.close.assert_called_once()

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""

"""CPO-specific display labels and units."""

from utilities_common.platform_sfputil_helper import (
    CMIS_INFO_FIELD_MAP,
    DOM_MODULE_MONITOR_MAP,
    DOM_MODULE_THRESHOLD_MAP,
    CMIS_DOM_VALUE_UNIT_MAP as DOM_VALUE_UNIT_MAP,
    DOM_MODULE_THRESHOLD_UNIT_MAP,
)


CPO_INFO_FIELD_MAP = {
    **CMIS_INFO_FIELD_MAP,
    'type_abbrv_name': 'Identifier Abbreviation',
    'vdm_supported': 'VDM Supported',
    'cdb_supported': 'CDB Supported',
    'specification_compliance': 'Specification Compliance',
    'cable_length': 'Cable Length',
    'lane_count': 'Laser Count',
    'control_mode': 'Control Mode',
    'max_optical_power': 'Maximum Optical Power',
    'min_optical_power': 'Minimum Optical Power',
    'max_laser_bias': 'Maximum Laser Bias',
    'min_laser_bias': 'Minimum Laser Bias',
}


CPO_INFO_LANE_FIELD_MAP = {
    "fiber_mapping": "Fiber Mapping",
    "frequency": "Frequency",
}

CPO_DOM_MODULE_MONITOR_MAP = {
    **DOM_MODULE_MONITOR_MAP,
    "laser_temperature": "Laser Temperature",
}

CPO_DOM_MODULE_THRESHOLD_MAP = {
    **DOM_MODULE_THRESHOLD_MAP,
    "lasertemphighalarm": "LaserTempHighAlarm",
    "lasertemplowalarm": "LaserTempLowAlarm",
    "lasertemphighwarning": "LaserTempHighWarning",
    "lasertemplowwarning": "LaserTempLowWarning",
}

CPO_DOM_VALUE_UNIT_MAP = {**DOM_VALUE_UNIT_MAP, "laser_temperature": "C"}
CPO_DOM_MODULE_THRESHOLD_UNIT_MAP = {
    **DOM_MODULE_THRESHOLD_UNIT_MAP,
    **{key: "C" for key in CPO_DOM_MODULE_THRESHOLD_MAP if key.startswith("lasertemp")},
}


ELS_DOM_MONITOR_MAP = {
    "temperature": "Temperature",
    "voltage": "Vcc",
    "icc": "Icc",
}

ELS_STATUS_FIELD_MAP = {
    "module_state": "Module State",
    "module_fault_cause": "Module Fault Cause",
    "module_low_power_state": "Module Low Power State",
    "interrupt_status": "Interrupt Status",
}

ELS_THRESHOLD_MAP = {
    "temperature_alarm_high": "TempHighAlarm",
    "temperature_alarm_low": "TempLowAlarm",
    "temperature_warn_high": "TempHighWarning",
    "temperature_warn_low": "TempLowWarning",
    "voltage_alarm_high": "VccHighAlarm",
    "voltage_alarm_low": "VccLowAlarm",
    "voltage_warn_high": "VccHighWarning",
    "voltage_warn_low": "VccLowWarning",
    "optical_power_alarm_high": "TxPowerHighAlarm",
    "optical_power_alarm_low": "TxPowerLowAlarm",
    "optical_power_warn_high": "TxPowerHighWarning",
    "optical_power_warn_low": "TxPowerLowWarning",
    "laser_bias_alarm_high": "TxBiasHighAlarm",
    "laser_bias_alarm_low": "TxBiasLowAlarm",
    "laser_bias_warn_high": "TxBiasHighWarning",
    "laser_bias_warn_low": "TxBiasLowWarning",
}


ELS_DOM_MONITOR_UNIT_MAP = {
    "temperature": "C",
    "voltage": "Volts",
    "icc": "A",
}

ELS_THRESHOLD_UNIT_MAP = {
    key: (
        "C" if "temp" in key else
        "Volts" if "voltage" in key or "vcc" in key else
        "mA" if "laser_bias" in key or "txbias" in key else
        "dBm"
    )
    for key in ELS_THRESHOLD_MAP
}

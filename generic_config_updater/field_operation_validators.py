import os
import re
import json
import jsonpointer
import subprocess
from sonic_py_common import device_info
from .gu_common import GenericConfigUpdaterError
from swsscommon import swsscommon
from utilities_common.constants import DEFAULT_SUPPORTED_FECS_LIST

STATE_DB_NAME = 'STATE_DB'
REDIS_TIMEOUT_MSECS = 0
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
GCU_TABLE_MOD_CONF_FILE = f"{SCRIPT_DIR}/gcu_field_operation_validators.conf.json"
GET_HWSKU_CMD = "sonic-cfggen -d -v DEVICE_METADATA.localhost.hwsku"


def get_asic_name():
    asic = "unknown"
    
    if os.path.exists(GCU_TABLE_MOD_CONF_FILE):
        with open(GCU_TABLE_MOD_CONF_FILE, "r") as s:
            gcu_field_operation_conf = json.load(s)
    else:
        raise GenericConfigUpdaterError("GCU table modification validators config file not found")
    
    asic_mapping = gcu_field_operation_conf["helper_data"]["rdma_config_update_validator"]
    asic_type = device_info.get_sonic_version_info()['asic_type'] 

    if asic_type == 'cisco-8000':
        asic = "cisco-8000"
    if asic_type == 'marvell-teralynx':
        asic = "marvell-teralynx"
    elif asic_type == 'mellanox' or asic_type == 'vs' or asic_type == 'broadcom':
        proc = subprocess.Popen(GET_HWSKU_CMD, shell=True, universal_newlines=True, stdout=subprocess.PIPE)
        output, err = proc.communicate()
        hwsku = output.rstrip('\n')
        if asic_type == 'mellanox' or asic_type == 'vs':
            spc1_hwskus = asic_mapping["mellanox_asics"]["spc1"]
            spc2_hwskus = asic_mapping["mellanox_asics"]["spc2"]
            spc3_hwskus = asic_mapping["mellanox_asics"]["spc3"]
            spc4_hwskus = asic_mapping["mellanox_asics"]["spc4"]
            spc5_hwskus = asic_mapping["mellanox_asics"]["spc5"]
            if hwsku.lower() in [spc1_hwsku.lower() for spc1_hwsku in spc1_hwskus]:
                asic = "spc1"
                return asic
            if hwsku.lower() in [spc2_hwsku.lower() for spc2_hwsku in spc2_hwskus]:
                asic = "spc2"
                return asic
            if hwsku.lower() in [spc3_hwsku.lower() for spc3_hwsku in spc3_hwskus]:
                asic = "spc3"
                return asic
            if hwsku.lower() in [spc4_hwsku.lower() for spc4_hwsku in spc4_hwskus]:
                asic = "spc4"
                return asic
            if hwsku.lower() in [spc5_hwsku.lower() for spc5_hwsku in spc5_hwskus]:
                asic = "spc5"
                return asic
        if asic_type == 'broadcom' or asic_type == 'vs':
            broadcom_asics = asic_mapping["broadcom_asics"]
            for asic_shorthand, hwskus in broadcom_asics.items():
                if asic != "unknown":
                    break
                for hwsku_cur in hwskus:
                    if hwsku_cur.lower() in hwsku.lower():
                        asic = asic_shorthand
                        break

    return asic


def fields_match_exact(cleaned_patch_field, gcu_field):
    return cleaned_patch_field == gcu_field


def fields_match_endswith(cleaned_patch_field, gcu_field):
    """
    Checks if cleaned_patch_field ends with gcu_field
    """
    field = cleaned_patch_field.split('/')[-1]
    return field == gcu_field


# If exact_field_match is True, then each field in GCU_TABLE_MOD_CONF_FILE must match exactly with
# the corresponding cleaned field from the patch.
# If exact_field_match is False, then each field in GCU_TABLE_MOD_CONF_FILE must appear at the end of
# the corresponding cleaned fields from the patch.
# remove_port controls the behavior of the _get_fields_in_patch function.
def rdma_config_update_validator_common(scope, patch_element, exact_field_match=False, remove_port=False):
    asic = get_asic_name()
    if asic == "unknown":
        return False
    version_info = device_info.get_sonic_version_info()
    build_version = version_info.get('build_version')
    version_substrings = build_version.split('.')
    branch_version = None

    for substring in version_substrings:
        if substring.isdigit() and re.match(r'^\d{8}$', substring):
            branch_version = substring

    path = patch_element["path"]
    table = jsonpointer.JsonPointer(path).parts[0]

    # Helper function to return relevant cleaned paths, considers case where the jsonpatch value is a dict
    # If remove_port is True, then for paths like /PFC_WD/Ethernet112/action, remove Ethernet112 from
    # the path so that we can clearly determine the relevant field (i.e. action, not Ethernet112)
    def _get_fields_in_patch():
        cleaned_fields = []

        field_elements = jsonpointer.JsonPointer(path).parts[1:]
        if remove_port:
            cleaned_field_elements = [elem for elem in field_elements if not any(char.isdigit() for char in elem)]
        else:
            cleaned_field_elements = field_elements
        cleaned_field = '/'.join(cleaned_field_elements).lower()


        if 'value' in patch_element.keys() and isinstance(patch_element['value'], dict):
            for key in patch_element['value']:
                if len(cleaned_field) > 0:
                    cleaned_fields.append(cleaned_field + '/' + key)
                else:
                    cleaned_fields.append(key)
        else:
            cleaned_fields.append(cleaned_field)

        return cleaned_fields

    if os.path.exists(GCU_TABLE_MOD_CONF_FILE):
        with open(GCU_TABLE_MOD_CONF_FILE, "r") as s:
            gcu_field_operation_conf = json.load(s)
    else:
        raise GenericConfigUpdaterError("GCU table modification validators config file not found")

    tables = gcu_field_operation_conf["tables"]
    scenarios = tables[table]["validator_data"]["rdma_config_update_validator"]
    cleaned_patch_fields = _get_fields_in_patch()
    fields_match = fields_match_exact if exact_field_match else fields_match_endswith
    for cleaned_patch_field in cleaned_patch_fields:
        scenario = None
        for key in scenarios.keys():
            for gcu_field in scenarios[key]["fields"]:
                if fields_match(cleaned_patch_field, gcu_field):
                    scenario = scenarios[key]
                    break
            if scenario:
                break

        if scenario is None:
            return False

        if not scenario["platforms"].get(asic):  # None or empty string
            return False

        if patch_element['op'] not in scenario["operations"]:
            return False

        if branch_version is not None:
            if asic in scenario["platforms"]:
                if branch_version < scenario["platforms"][asic]:
                    return False
            else:
                return False

    return True


def rdma_config_update_validator(scope, patch_element):
    return rdma_config_update_validator_common(scope, patch_element, exact_field_match=True, remove_port=True)


def wred_profile_config_update_validator(scope, patch_element):
    return rdma_config_update_validator_common(scope, patch_element)


def read_statedb_entry(scope, table, key, field):
    state_db = swsscommon.DBConnector(STATE_DB_NAME, REDIS_TIMEOUT_MSECS, True, scope)
    tbl = swsscommon.Table(state_db, table)
    return tbl.hget(key, field)[1]


def port_config_update_validator(scope, patch_element):

    def _validate_field(field, port, value):
        if field == "fec":
            supported_fecs_str = read_statedb_entry(scope, "PORT_TABLE", port, "supported_fecs")
            if supported_fecs_str:
                if supported_fecs_str != 'N/A':
                    supported_fecs_list = [element.strip() for element in supported_fecs_str.split(',')]
                else:
                    supported_fecs_list = []
            else:
                supported_fecs_list = DEFAULT_SUPPORTED_FECS_LIST
            if value.strip() not in supported_fecs_list:
                return False
            return True
        if field == "speed":
            supported_speeds_str = read_statedb_entry(scope, "PORT_TABLE", port, "supported_speeds") or ''
            try:
                supported_speeds = [int(s) for s in supported_speeds_str.split(',') if s]
                if supported_speeds and int(value) not in supported_speeds:
                    return False
            except ValueError:
                return False
            return True
        return False
    
    def _parse_port_from_path(path):
        match = re.search(r"Ethernet\d+", path)
        if match:
            port = match.group(0)
            return port
        return None
    
    if patch_element["op"] == "remove":
        return True
    
    # for PORT speed and fec configs, need to ensure value is allowed based on StateDB
    patch_element_str = json.dumps(patch_element)
    path = patch_element["path"]
    value = patch_element.get("value")
    fields = ['fec', 'speed']
    for field in fields:
        if field in patch_element_str:
            if path.endswith(field):
                port = _parse_port_from_path(path)
                if not _validate_field(field, port, value):
                    return False
            elif isinstance(value, dict):
                if field in value.keys():
                    port = _parse_port_from_path(path)
                    value = value[field]
                    if not _validate_field(field, port, value):
                        return False
                else:
                    for port_name, port_info in value.items():
                        if isinstance(port_info, dict):
                            port = port_name
                            if field in port_info.keys():
                                value = port_info[field]
                                if not _validate_field(field, port, value):
                                    return False
                            else:
                                continue
    return True

import os
import re
import json
import jsonpointer
import subprocess
from sonic_py_common import device_info, multi_asic
from .gu_common import GenericConfigUpdaterError, genericUpdaterLogging
from swsscommon import swsscommon

logger = genericUpdaterLogging.get_logger(title="Field Operation Validator")

# Default FEC modes when STATE_DB does not advertise supported_fecs for a port.
# Kept local to avoid pulling utilities_common into the GCU wheel.
# NOTE: A duplicate of this list exists in utilities_common/constants.py.
# If you update this list, update that copy too.
DEFAULT_SUPPORTED_FECS_LIST = ['rs', 'fc', 'none', 'auto']

STATE_DB_NAME = 'STATE_DB'
CONFIG_DB_NAME = 'CONFIG_DB'
PG_PROFILE_LOOKUP_FILE = 'pg_profile_lookup.ini'
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

    if asic_type in ('cisco-8000', 'cisco'):
        asic = asic_type
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
            spc6_hwskus = asic_mapping["mellanox_asics"]["spc6"]
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
            if hwsku.lower() in [spc6_hwsku.lower() for spc6_hwsku in spc6_hwskus]:
                asic = "spc6"
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
                    cleaned_fields.append(cleaned_field + '/' + key.lower())
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


def buffer_profile_config_update_validator(scope, patch_element):
    """
    Enhanced buffer profile validator that handles both field-level and object-level operations.
    - Field-level operations (e.g., /BUFFER_PROFILE/profile/dynamic_th) follow existing rules
    - Object-level operations (e.g., /BUFFER_PROFILE/profile) allow remove operations
    """
    path = patch_element["path"]
    path_parts = jsonpointer.JsonPointer(path).parts

    # Determine if this is an object-level operation (entire profile) or field-level operation
    # Object-level: /BUFFER_PROFILE/profile_name (2 parts)
    # Field-level: /BUFFER_PROFILE/profile_name/field_name (3+ parts)
    is_object_level = len(path_parts) == 2  # table + profile_name only

    if is_object_level:
        # For object-level operations, we're more permissive
        # Allow add/remove/replace operations for entire profile objects
        allowed_object_operations = ['add', 'remove', 'replace']

        if patch_element['op'] in allowed_object_operations:
            return True  # Allow object-level operations
        else:
            return False  # Disallow unsupported operations

    # For field-level operations, use the existing validation logic
    return rdma_config_update_validator_common(scope, patch_element)


def read_statedb_entry(scope, table, key, field):
    state_db = swsscommon.DBConnector(STATE_DB_NAME, REDIS_TIMEOUT_MSECS, True, scope)
    tbl = swsscommon.Table(state_db, table)
    return tbl.hget(key, field)[1]


def read_configdb_field(scope, table, key, field):
    """A field of the running config, or None when the entry or the field is absent"""
    config_db = swsscommon.DBConnector(CONFIG_DB_NAME, REDIS_TIMEOUT_MSECS, True, scope)
    tbl = swsscommon.Table(config_db, table)
    found, value = tbl.hget(key, field)
    return value if found else None


def get_pg_profile_lookup(scope=None):
    """Lossless PG profile rows of the HWSKU's pg_profile_lookup.ini as
    ``{speed: {cable length, ...}}``, parsed the way buffermgrd does (whitespace
    separated, '#' comments). On a multi-ASIC SKU the file lives in the ASIC's
    subdirectory, named after its namespace (``scope``); the HWSKU root is the
    fallback. None when no file is found (dynamic-buffer SKUs, VS) or the HWSKU
    directory can't be resolved."""
    try:
        _, hwsku_path = device_info.get_paths_to_platform_and_hwsku_dirs()
    except Exception as e:
        logger.log_warning("cannot resolve the HWSKU directory: {}".format(e))
        return None
    candidate_dirs = [hwsku_path]
    if scope and scope != multi_asic.DEFAULT_NAMESPACE:
        candidate_dirs.insert(0, os.path.join(hwsku_path, scope))
    lookup_file = next((f for f in (os.path.join(d, PG_PROFILE_LOOKUP_FILE) for d in candidate_dirs)
                        if os.path.isfile(f)), None)
    if lookup_file is None:
        return None
    lookup = {}
    with open(lookup_file) as f:
        for line in f:
            parts = line.split()
            if len(parts) < 2 or parts[0].startswith('#'):
                continue
            lookup.setdefault(parts[0], set()).add(parts[1])
    return lookup


def port_config_update_validator(scope, patch_element, target_config=None):

    def _validate_field(field, port, value):
        if field == "fec":
            # For chassis, skip fec validation as desired fec is not in supported_fecs of StateDB.
            if device_info.is_chassis():
                return True
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
            # For chassis, skip speed validation as desired speed is not in supported_speeds of StateDB.
            if device_info.is_chassis():
                return True
            supported_speeds_str = read_statedb_entry(scope, "PORT_TABLE", port, "supported_speeds") or ''
            try:
                supported_speeds = [int(s) for s in supported_speeds_str.split(',') if s]
                if supported_speeds and int(value) not in supported_speeds:
                    return False
            except ValueError:
                return False
            # buffermgrd rebuilds the port's lossless PG profile at the new speed from
            # pg_profile_lookup.ini; with no row for the port's cable length it drops the
            # update and keeps the old profile (see cable_length_config_update_validator).
            lookup = _pg_profile_lookup_to_check(scope, target_config)
            if lookup is not None:
                cable_length = _port_cable_length(scope, target_config, port)
                if not _has_pg_profile(lookup, port, str(value), cable_length):
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


def cable_length_config_update_validator(scope, patch_element, target_config=None):
    """
    Refuses a CABLE_LENGTH value the traditional buffer model can't act on.

    buffermgrd derives a port's lossless PG profile from the (speed, cable length)
    row of the HWSKU's pg_profile_lookup.ini. For a length with no row at the
    port's speed it logs an error, drops the update and leaves BUFFER_PG on the
    previous profile, while CONFIG_DB claims the new length: the headroom silently
    stays sized for the old cable. The YANG model only checks the ``<num>m`` shape.

    The port's speed and the buffer model come from ``target_config`` (the
    simulated post-patch config, so a speed changed by the same patch counts) and
    from CONFIG_DB when no target config is given. Permissive wherever the check
    can't be made: dynamic buffer model, no lookup file, port speed unknown.

    A port with no lossless PGs is checked too, although buffermgrd would not
    consult the lookup for it yet: enabling PFC on it later would hit the same
    silent failure, and that PORT_QOS_MAP change is not validated.
    """
    if patch_element["op"] not in ("add", "replace"):
        return True

    lengths = _cable_lengths_in_patch(patch_element)
    if not lengths:
        return True

    lookup = _pg_profile_lookup_to_check(scope, target_config)
    if lookup is None:
        return True

    return all(_has_pg_profile(lookup, port, _config_field(scope, target_config, "PORT", port, "speed"), length)
               for port, length in lengths)


def _cable_lengths_in_patch(patch_element):
    """(port, length) pairs a CABLE_LENGTH patch element sets, whether it targets
    the table, one group, or one port. Values of an unexpected shape are left to
    YANG validation."""
    parts = jsonpointer.JsonPointer(patch_element["path"]).parts
    value = patch_element.get("value")
    depth = len(parts)  # 1: /CABLE_LENGTH, 2: /CABLE_LENGTH/<group>, 3: /CABLE_LENGTH/<group>/<port>
    if depth == 3 and isinstance(value, str):
        return [(parts[2], value)]
    groups = []
    if depth == 2 and isinstance(value, dict):
        groups = [value]
    elif depth == 1 and isinstance(value, dict):
        groups = [g for g in value.values() if isinstance(g, dict)]
    return [(port, length) for g in groups for port, length in g.items() if isinstance(length, str)]


def _config_field(scope, target_config, table, key, field):
    if target_config is not None:
        return target_config.get(table, {}).get(key, {}).get(field)
    return read_configdb_field(scope, table, key, field)


def _port_cable_length(scope, target_config, port):
    """``port``'s cable length from whichever CABLE_LENGTH group lists it, or None."""
    if target_config is not None:
        groups = target_config.get("CABLE_LENGTH", {}).values()
        return next((g[port] for g in groups if isinstance(g, dict) and port in g), None)
    config_db = swsscommon.DBConnector(CONFIG_DB_NAME, REDIS_TIMEOUT_MSECS, True, scope)
    tbl = swsscommon.Table(config_db, "CABLE_LENGTH")
    for group in tbl.getKeys():
        found, length = tbl.hget(group, port)
        if found:
            return length
    return None


def _pg_profile_lookup_to_check(scope, target_config):
    """The pg_profile_lookup.ini table a (speed, cable length) pair must have a row
    in, or None when buffermgrd would not consult one: no lookup file, or the
    dynamic buffer model. The file is probed before CONFIG_DB so hosts without
    one never need a database connection."""
    lookup = get_pg_profile_lookup(scope)
    if lookup is None:
        return None
    if _config_field(scope, target_config, "DEVICE_METADATA", "localhost", "buffer_model") == "dynamic":
        return None
    return lookup


def _has_pg_profile(lookup, port, speed, cable_length):
    """Whether buffermgrd can build ``port``'s lossless PG profile from ``lookup``
    at ``speed`` and ``cable_length``. Missing speed or length can't be checked;
    0m means "no lossless profile" to buffermgrd. A miss is logged."""
    if not speed or not cable_length or cable_length == "0m":
        return True
    if cable_length in lookup.get(speed, ()):
        return True
    logger.log_error(
        "port {}: no PG profile for speed {} and cable length {} in {}; lengths listed at that speed: {}"
        .format(port, speed, cable_length, PG_PROFILE_LOOKUP_FILE,
                ", ".join(sorted(lookup.get(speed, ()))) or "none"))
    return False

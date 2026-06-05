#All the constant used in sonic-utilities

DEFAULT_NAMESPACE = ''

# NOTE: A duplicate of this list exists in generic_config_updater/field_operation_validators.py
# (kept separate to avoid a utilities_common dependency in the GCU wheel).
# If you update this list, update that copy too.
DEFAULT_SUPPORTED_FECS_LIST = [ 'rs', 'fc', 'none', 'auto']
DISPLAY_ALL = 'all'
DISPLAY_EXTERNAL = 'frontend'
BGP_NEIGH_OBJ = 'BGP_NEIGH'
PORT_CHANNEL_OBJ = 'PORT_CHANNEL'
PORT_OBJ = 'PORT'
IPV4 = 'v4'
IPV6 = 'v6'
VTYSH_COMMAND = 'vtysh'
RVTYSH_COMMAND = 'rvtysh'

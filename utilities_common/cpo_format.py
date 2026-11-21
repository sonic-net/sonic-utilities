"""Reserved CPO display dictionaries and pure formatting functions.

These maps intentionally contain no field definitions yet. OE/ELS platform
objects supply additional label/unit maps through their format hooks; they
do not own the functions below. CPOShow obtains those maps and passes them in.
This module must not initialize a chassis, read STATE_DB or access hardware.
"""

# Populate common field definitions separately from platform-specific labels.
CPO_INFO_FIELD_MAP = {}
CPO_STATUS_MAP = {}
CPO_DOM_MODULE_MONITOR_MAP = {}
CPO_DOM_CHANNEL_MONITOR_MAP = {}
CPO_DOM_MODULE_THRESHOLD_MAP = {}
CPO_DOM_VALUE_UNIT_MAP = {}
CPO_DOM_FLAG_MAP = {}

# ELS fields retain their own semantics; do not merge laser fields into OE data.
ELS_INFO_FIELD_MAP = {}
ELS_STATUS_MAP = {}
ELS_DOM_MONITOR_MAP = {}
ELS_DOM_UNIT_MAP = {}
ELS_DOM_THRESHOLD_MAP = {}
ELS_DOM_FLAG_MAP = {}


def normalize_field_key(raw_key):
    """Return the formatting lookup pattern and channel index for a DB key.

    Recognize explicit lane/hostlane forms without changing the original key
    used by JSON or confusing bank-local lanes with absolute laser IDs.
    """
    raise NotImplementedError("CPO field-key normalization is not implemented yet")


def merge_format_maps(common, platform):
    """Return common maps with platform keys taking precedence.

    Do not mutate shared dictionaries or obtain platform objects here.
    """
    raise NotImplementedError("CPO format-map merging is not implemented yet")


def select_fields(data, maps, selection):
    """Group module, selected channel, platform and suppressed fields.

    Preserve original data and explicit OE/ELS ownership. Unknown table fields
    remain available for JSON and suppressed-field diagnostics.
    """
    raise NotImplementedError("CPO field selection is not implemented yet")


def format_fields(data, labels, units):
    """Return text from raw data and caller-supplied display dictionaries.

    Keep ordering stable, render missing values as N/A, and avoid duplicate
    units. This function must neither fetch format hooks nor print output.
    """
    raise NotImplementedError("CPO field formatting is not implemented yet")

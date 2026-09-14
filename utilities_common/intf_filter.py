# Interface filtering functions

SONIC_PORT_NAME_PREFIX = "Ethernet"
SONIC_LAG_NAME_PREFIX = "PortChannel"
SONIC_BACK_PORT_NAME_PREFIX = "Ethernet-BP"


def expand_range(intf_filter, prefix):
    """Try to expand a prefixed interface filter as a numeric range.

    If the suffix after the prefix starts with a digit and contains '-',
    it is treated as a range (e.g. Ethernet0-3). If the range is malformed
    (e.g. Ethernet0-ff), a ValueError is raised.

    Returns (interfaces, is_range).
    """
    suffix = intf_filter[len(prefix):]
    if not suffix or not suffix[0].isdigit():
        return ([intf_filter], False)
    if '-' not in suffix:
        return ([intf_filter], False)
    range_start, range_end = suffix.split('-', 1)
    if not range_start.isdigit() or not range_end.isdigit():
        raise ValueError(
            "Invalid interface range '{}'. Expected a range like "
            "'{}0-3'.".format(intf_filter, prefix))
    start, end = int(range_start), int(range_end)
    if start > end:
        raise ValueError(
            "Invalid interface range '{}'. The start of the range "
            "must not be greater than the end.".format(intf_filter))
    return ([prefix + str(i) for i in range(start, end + 1)], True)


def expand_single_intf_filter(intf_filter):
    """Expand a single interface filter segment (no commas) into interface names.

    Returns (interfaces, is_range) where is_range indicates whether the filter
    used range syntax (e.g. Ethernet0-4) vs an explicit name (e.g. Ethernet0).
    """
    if intf_filter.startswith(SONIC_BACK_PORT_NAME_PREFIX):
        return expand_range(intf_filter, SONIC_BACK_PORT_NAME_PREFIX)

    if '-' in intf_filter:
        if intf_filter.startswith(SONIC_PORT_NAME_PREFIX):
            suffix = intf_filter[len(SONIC_PORT_NAME_PREFIX):]
            # Range expansion is not applicable to recirculation ports (e.g., Ethernet-Rec0)
            # or in-band ports (e.g., Ethernet-IB0), so return an empty list.
            if suffix.startswith(("-Rec", "-IB")):
                return ([], False)
            return expand_range(intf_filter, SONIC_PORT_NAME_PREFIX)
        elif intf_filter.startswith(SONIC_LAG_NAME_PREFIX):
            return expand_range(intf_filter, SONIC_LAG_NAME_PREFIX)
        else:
            raise ValueError(
                "Invalid interface range '{}'. A range must start with "
                "'{}' or '{}'.".format(intf_filter, SONIC_PORT_NAME_PREFIX, SONIC_LAG_NAME_PREFIX))

    return ([intf_filter], False)


def parse_interface_in_filter(intf_filter):
    intf_fs = []

    if intf_filter is None:
        return intf_fs

    fs = intf_filter.split(',')
    for x in fs:
        names, _ = expand_single_intf_filter(x)
        intf_fs.extend(names)

    return intf_fs


def interface_in_filter(intf, filter):
    if filter is None:
        return True

    intf_fs = parse_interface_in_filter(filter)
    if intf in intf_fs:
        return True

    return False

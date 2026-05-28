# Interface filtering functions

SONIC_PORT_NAME_PREFIX = "Ethernet"
SONIC_LAG_NAME_PREFIX = "PortChannel"
SONIC_BACK_PORT_NAME_PREFIX = "Ethernet-BP"

def parse_interface_in_filter(intf_filter):
    intf_fs = []

    if intf_filter is None:
        return intf_fs

    fs = intf_filter.split(',')
    for x in fs:
        if x.startswith(SONIC_BACK_PORT_NAME_PREFIX):
            intf = SONIC_BACK_PORT_NAME_PREFIX
            x = x.split(intf)[1]
            if '-' in x:
                start = x.split('-')[0]
                end = x.split('-')[1]
                if not start.isdigit() or not end.isdigit():
                    raise ValueError(
                        "Invalid interface range '{}{}'. Expected a range like "
                        "'{}0-3'.".format(intf, x, intf))
                for i in range(int(start), int(end)+1):
                    intf_fs.append(intf+str(i))
            else:
                intf_fs.append(intf+x)
        elif '-' in x:
            # handle range
            if x.startswith(SONIC_PORT_NAME_PREFIX):
                intf = SONIC_PORT_NAME_PREFIX
            elif x.startswith(SONIC_LAG_NAME_PREFIX):
                intf = SONIC_LAG_NAME_PREFIX
            else:
                raise ValueError(
                    "Invalid interface range '{}'. A range must start with "
                    "'{}' or '{}'.".format(x, SONIC_PORT_NAME_PREFIX, SONIC_LAG_NAME_PREFIX))
            start = x.split('-')[0].split(intf,1)[1]
            end = x.split('-')[1]

            if not start.isdigit() or not end.isdigit():
                raise ValueError(
                    "Invalid interface range '{}'. Expected a range like "
                    "'{}0-3'.".format(x, intf))
            for i in range(int(start), int(end)+1):
                intf_fs.append(intf+str(i))
        else:
            intf_fs.append(x)

    return intf_fs

def interface_in_filter(intf, filter):
    if filter is None:
        return True

    intf_fs = parse_interface_in_filter(filter)
    if intf in intf_fs:
        return True

    return False

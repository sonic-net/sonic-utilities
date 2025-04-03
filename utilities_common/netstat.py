# network statistics utility functions #

import json

STATUS_NA = 'N/A'
PORT_RATE = 40

def ns_diff(newstr, oldstr):
    """
        Calculate the diff.
    """
    if newstr == STATUS_NA:
        return STATUS_NA

    # if new is valid but old is not we should return new
    if oldstr == STATUS_NA:
        oldstr = '0'

    new, old = int(newstr), int(oldstr)
    return '{:,}'.format(max(0, new - old))

def ns_brate(newstr, oldstr, delta):
    """
        Calculate the byte rate.
    """
    if newstr == STATUS_NA or oldstr == STATUS_NA:
        return STATUS_NA
    else:
        rate = int(ns_diff(newstr, oldstr).replace(',',''))/delta
        if rate > 1000*1000*10:
            rate = "{:.2f}".format(rate/1000/1000)+' MB'
        elif rate > 1000*10:
            rate = "{:.2f}".format(rate/1000)+' KB'
        else:
            rate = "{:.2f}".format(rate)+' B'
        return rate+'/s'

def ns_prate(newstr, oldstr, delta):
    """
        Calculate the packet rate.
    """
    if newstr == STATUS_NA or oldstr == STATUS_NA:
        return STATUS_NA
    else:
        rate = int(ns_diff(newstr, oldstr).replace(',',''))/delta
        return "{:.2f}".format(rate)+'/s'

def ns_util(newstr, oldstr, delta, port_rate=PORT_RATE):
    """
        Calculate the util.
    """
    if newstr == STATUS_NA or oldstr == STATUS_NA:
        return STATUS_NA
    else:
        rate = int(ns_diff(newstr, oldstr).replace(',',''))/delta
        util = rate/(port_rate*1000*1000*1000/8.0)*100
        return "{:.2f}%".format(util)

def table_as_json(table, header):
    """
        Print table as json format.
    """
    output = {}

    # Build a dictionary where the if_name is the key and the value is
    # a dictionary that holds MTU, TX_DRP, etc
    for line in table:
        if_name = line[0]
        output[if_name] = {header[i]: line[i] for i in range(1, len(header))}
    
    return json.dumps(output, indent=4, sort_keys=True)


def format_number_with_comma(number_in_str):
    """
        Format the number with comma.
    """
    if number_in_str.isdecimal():
        return '{:,}'.format(int(number_in_str))
    else:
        return number_in_str


def format_brate(rate):
    """
    Show the byte rate.
    """
    if rate == STATUS_NA:
        return STATUS_NA
    else:
        rate = float(rate)
        if rate > 1000*1000*10:
            rate = "{:.2f}".format(rate/1000/1000.0)+' MB'
        elif rate > 1000*10:
            rate = "{:.2f}".format(rate/1000.0)+' KB'
        else:
            rate = "{:.2f}".format(rate)+' B'
        return rate+'/s'


def format_prate(rate):
    """
    Show the packet rate.
    """
    if rate == STATUS_NA:
        return STATUS_NA
    else:
        return "{:.2f}".format(float(rate))+'/s'


def format_fec_ber(rate):
    """
    Show the ber rate.
    """
    if rate == STATUS_NA:
        return STATUS_NA
    else:
        return "{:.2e}".format(float(rate))


def format_util(brate, port_rate):
    """
        Calculate the util.
    """
    if brate == STATUS_NA or port_rate == STATUS_NA:
        return STATUS_NA
    else:
        util = brate/(float(port_rate)*1000*1000/8.0)*100
        return "{:.2f}%".format(util)


def format_util_directly(util):
    """
        Format the util without calculation.
    """
    if util == STATUS_NA:
        return STATUS_NA
    else:
        return "{:.2f}%".format(float(util))

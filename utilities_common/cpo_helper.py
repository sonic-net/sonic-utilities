"""Helpers for the CPO command-line utility."""

import re


def natural_sort_key(value, case_sensitive=False):
    """Order numeric parts naturally, optionally preserving letter case."""
    text = str(value)
    if not case_sensitive:
        text = text.lower()
    return [int(part) if part.isdigit() else part
            for part in re.split(r"(\d+)", text)]


def get_physical_port_name(logical_port, physical_port, ganged):
    """Return a physical port label, including its member index when ganged."""
    if logical_port == physical_port:
        return str(logical_port)
    if ganged:
        return "{}:{} (ganged)".format(logical_port, physical_port)
    return str(logical_port)


def convert_byte_to_valid_ascii_char(byte):
    """Render non-printable EEPROM bytes as dots."""
    return chr(byte) if 32 <= byte <= 126 else '.'


def hexdump(indent, data, mem_address, start_newline=True):
    """Format EEPROM bytes in rows of sixteen with an ASCII column."""
    size = len(data)
    offset = 0
    lines = [''] if start_newline else []
    while size > 0:
        offset_str = "{}{:08x}".format(indent, mem_address)
        if size >= 16:
            first_half = ' '.join("{:02x}".format(x) for x in data[offset:offset + 8])
            second_half = ' '.join("{:02x}".format(x) for x in data[offset + 8:offset + 16])
            ascii_str = ''.join(convert_byte_to_valid_ascii_char(x) for x in data[offset:offset + 16])
            lines.append(f'{offset_str} {first_half}  {second_half} |{ascii_str}|')
        elif size > 8:
            first_half = ' '.join("{:02x}".format(x) for x in data[offset:offset + 8])
            second_half = ' '.join("{:02x}".format(x) for x in data[offset + 8:offset + size])
            padding = '   ' * (16 - size)
            ascii_str = ''.join(convert_byte_to_valid_ascii_char(x) for x in data[offset:offset + size])
            lines.append(f'{offset_str} {first_half}  {second_half}{padding} |{ascii_str}|')
            break
        else:
            hex_part = ' '.join("{:02x}".format(x) for x in data[offset:offset + size])
            padding = '   ' * (16 - size)
            ascii_str = ''.join(convert_byte_to_valid_ascii_char(x) for x in data[offset:offset + size])
            lines.append(f'{offset_str} {hex_part} {padding} |{ascii_str}|')
            break
        size -= 16
        offset += 16
        mem_address += 16
    return '\n'.join(lines)


def format_value_with_unit(value, unit):
    """Append a DOM unit without duplicating it or changing Unknown values."""
    if isinstance(value, str) and (value == 'Unknown' or not unit or value.endswith(unit)):
        return value
    return "{}{}".format(value, unit)


def format_dict_value_to_string(sorted_key_table, dom_info_dict, dom_value_map,
                                dom_unit_map, alignment=0):
    """Format available DOM fields in the caller's order and alignment."""
    output = ''
    indent = ' ' * 16
    separator = ': '
    for key in sorted_key_table:
        if dom_info_dict is not None and key in dom_info_dict and dom_info_dict[key] != 'N/A':
            label = dom_value_map[key]
            output += '{}{}{}{}\n'.format(
                indent, label,
                separator.rjust(len(separator) + alignment - len(label)),
                format_value_with_unit(dom_info_dict[key], dom_unit_map[key]))
    return output

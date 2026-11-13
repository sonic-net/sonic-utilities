import os
import re

from sonic_py_common import device_info

_PORT_MAP_CACHE = None


def _parse_port_ids(hwsku_dir):
    yaml_candidates = [
        os.path.join(hwsku_dir, name)
        for name in os.listdir(hwsku_dir)
        if name.endswith('.yml') or name.endswith('.yaml')
    ]
    port_ids = []
    for yaml_path in sorted(yaml_candidates):
        in_map = False
        with open(yaml_path) as yaml_file:
            for line in yaml_file:
                if 'PC_PORT_PHYS_MAP:' in line:
                    in_map = True
                    continue
                if not in_map:
                    continue
                match = re.match(r'\s+PORT_ID:\s*(\d+)', line)
                if match:
                    port_id = int(match.group(1))
                    if port_id != 0:
                        port_ids.append(port_id)
        if port_ids:
            return port_ids
    return port_ids


def _parse_port_config(hwsku_dir):
    port_config_path = os.path.join(hwsku_dir, 'port_config.ini')
    ports = []
    with open(port_config_path) as port_config:
        for line in port_config:
            line = line.strip()
            if not line or line.startswith('#') or not line.startswith('Ethernet'):
                continue
            parts = line.split()
            name = parts[0]
            if not name.startswith('Ethernet'):
                continue
            index = None
            for idx, part in enumerate(parts):
                if part == 'index' and idx + 1 < len(parts):
                    index = int(parts[idx + 1])
                    break
            if index is None and len(parts) >= 4 and parts[3].isdigit():
                index = int(parts[3])
            if index is not None:
                ports.append((index, name))
    ports.sort(key=lambda item: item[0])
    return ports


def get_ethernet_to_bcm_port_map():
    global _PORT_MAP_CACHE
    if _PORT_MAP_CACHE is not None:
        return _PORT_MAP_CACHE

    hwsku_dir = device_info.get_path_to_hwsku_dir()
    port_ids = _parse_port_ids(hwsku_dir)
    ports = _parse_port_config(hwsku_dir)
    if not port_ids or not ports:
        _PORT_MAP_CACHE = {}
        return _PORT_MAP_CACHE

    if len(port_ids) < len(ports):
        raise RuntimeError('BCM port map is shorter than port_config.ini')

    mapping = {}
    for (index, name), bcm_port in zip(ports, port_ids):
        mapping[name] = bcm_port
    _PORT_MAP_CACHE = mapping
    return mapping


def interface_to_bcm_port(interface):
    mapping = get_ethernet_to_bcm_port_map()
    if interface not in mapping:
        raise ValueError('No BCM port mapping for {}'.format(interface))
    return mapping[interface]

import base64
import uuid
import socket
import ipaddress
from google.protobuf.message import Message
from dash_api.types_pb2 import Guid, IpAddress, IpPrefix
from google.protobuf.json_format import MessageToDict


def format_ip(node):
    return str(ipaddress.IPv4Address(socket.ntohl(node)))


def format_mac(node):
    b64 = base64.b64decode(node)
    return ':'.join(b64.hex()[i:i + 2] for i in range(0, 12, 2))


def format_guid_dict(node):
    b64 = base64.b64decode(node['value'])
    return str(uuid.UUID(bytes=b64))


def format_ip_address_dict(node):
    if 'ipv4' in node:
        return format_ip(node['ipv4'])


def format_ip_prefix(node):
    ip = format_ip_address_dict(node['ip'])
    mask = format_ip_address_dict(node['mask'])
    network = ipaddress.IPv4Network(f'{ip}/{mask}', strict=False)
    return str(network)


def get_decoded_value(pb, pb_data):
    pb.ParseFromString(pb_data[b'pb'])
    json_string = MessageToDict(pb, preserving_proto_field_name=True)
    json_string = find_known_types_sec(pb, json_string)
    return json_string


decode_types = [IpAddress, Guid, IpPrefix]
decode_types = [cls.__module__ + '.' + cls.__name__ for cls in decode_types]
decode_fn = {'IpAddress': format_ip_address_dict,
             'Guid': format_guid_dict,
             'mac_address': format_mac,
             'IpPrefix': format_ip_prefix}


def find_known_types_sec(pb2_obj, pb2_dict):

    def process_msg_field(obj, proto_dict, field_name):
        class_name = type(obj).__name__
        obj_type = f"{type(obj).__module__}.{type(obj).__name__}"
        if obj_type in decode_types:
            proto_dict[field_name] = decode_fn[class_name](proto_dict[field_name])
        else:
            find_index(obj, proto_dict[field_name])

    def process_rep_field(obj, proto_dict, field_name):
        final_list = []
        requires_change = False
        for ind, value in enumerate(obj):
            if isinstance(value, Message):
                obj_type = f"{type(value).__module__}.{type(value).__name__}"
                if obj_type in decode_types:
                    requires_change = True
                    class_name = type(value).__name__
                    final_list.append(decode_fn[class_name](proto_dict[field_name][ind]))
                else:
                    find_index(value, pb2_dict[field_name][ind])
        if requires_change:
            proto_dict[field_name] = final_list

    def find_index(proto_obj, proto_dict=pb2_dict):
        for field_descriptor, value in proto_obj.ListFields():
            field_name = field_descriptor.name
            field_type = field_descriptor.type
            if field_type == field_descriptor.TYPE_MESSAGE:
                obj = getattr(proto_obj, field_name)
                if field_descriptor.label == field_descriptor.LABEL_REPEATED:
                    process_rep_field(obj, proto_dict, field_name)
                else:
                    process_msg_field(obj, proto_dict, field_name)
            elif field_name in decode_fn:
                proto_dict[field_name] = decode_fn[field_name](proto_dict[field_name])

    find_index(pb2_obj)
    return pb2_dict

import pytest

pytest.importorskip("dash_api.types_pb2")

from dump.dash_util import find_known_types_sec


class LegacyRepeatedField:
    name = "children"
    type = 11
    TYPE_MESSAGE = 11
    label = 3
    LABEL_REPEATED = 3


class LegacyProto:
    children = []

    def ListFields(self):
        return [(LegacyRepeatedField(), self.children)]


def test_find_known_types_supports_legacy_repeated_descriptor():
    proto_dict = {"children": []}

    assert find_known_types_sec(LegacyProto(), proto_dict) == proto_dict

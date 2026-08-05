# MONKEY PATCH!!!
import mock
from sonic_py_common import multi_asic

def mock_get_num_asics():
    return 3


def mock_is_multi_asic():
    return True


def mock_get_namespace_list(namespace=None):
    return ['asic0', 'asic1', 'asic2']


def mock_get_all_namespaces():
    return {'front_ns': ['asic0', 'asic2'], 'back_ns': ['asic1'], 'fabric_ns': []}


multi_asic.get_num_asics = mock_get_num_asics
multi_asic.is_multi_asic = mock_is_multi_asic
multi_asic.get_namespace_list = mock_get_namespace_list
multi_asic.get_all_namespaces = mock_get_all_namespaces
multi_asic.get_namespaces_from_linux = mock_get_namespace_list

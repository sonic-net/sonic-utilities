import mock
import unittest
import generic_config_updater
import generic_config_updater.field_operation_validators as fov
import generic_config_updater.gu_common as gu_common

from unittest.mock import MagicMock, Mock, mock_open
from mock import patch
from sonic_py_common.device_info import get_hwsku, get_sonic_version_info


class TestValidateFieldOperation(unittest.TestCase):

    @patch("generic_config_updater.field_operation_validators.read_statedb_entry", mock.Mock(return_value=""))
    def test_port_config_update_validator_valid_speed_no_state_db(self):
        patch_element = {"path": "/PORT/Ethernet3", "op": "add", "value": {"speed": "234"}}
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                port_config_update_validator(scope, patch_element) is True

    @patch("generic_config_updater.field_operation_validators.read_statedb_entry",
           mock.Mock(return_value="40000,30000"))
    def test_port_config_update_validator_invalid_speed_existing_state_db(self):
        patch_element = {"path": "/PORT/Ethernet3", "op": "add", "value": {"speed": "xyz"}}
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                port_config_update_validator(scope, patch_element) is False

    @patch("generic_config_updater.field_operation_validators.read_statedb_entry",
           mock.Mock(return_value="123,234"))
    def test_port_config_update_validator_valid_speed_existing_state_db(self):
        patch_element = {"path": "/PORT/Ethernet3", "op": "add", "value": {"speed": "234"}}
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                port_config_update_validator(scope, patch_element) is True

    @patch("generic_config_updater.field_operation_validators.read_statedb_entry",
           mock.Mock(return_value="123,234"))
    def test_port_config_update_validator_valid_speed_existing_state_db(self):
        patch_element = {"path": "/PORT/Ethernet3/speed", "op": "add", "value": "234"}
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                port_config_update_validator(scope, patch_element) is True

    @patch("generic_config_updater.field_operation_validators.read_statedb_entry",
           mock.Mock(return_value="123,234"))
    def test_port_config_update_validator_invalid_speed_existing_state_db(self):
        patch_element = {"path": "/PORT/Ethernet3/speed", "op": "add", "value": "235"}
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                port_config_update_validator(scope, patch_element) is False

    @patch("generic_config_updater.field_operation_validators.read_statedb_entry",
           mock.Mock(return_value="123,234"))
    def test_port_config_update_validator_invalid_speed_existing_state_db_nested(self):
        patch_element = {
            "path": "/PORT",
            "op": "add",
            "value": {"Ethernet3": {"alias": "Eth0", "speed": "235"}}
        }
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                port_config_update_validator(scope, patch_element) is False

    @patch("generic_config_updater.field_operation_validators.read_statedb_entry",
           mock.Mock(return_value="123,234"))
    def test_port_config_update_validator_valid_speed_existing_state_db_nested(self):
        patch_element = {
            "path": "/PORT",
            "op": "add",
            "value": {
                "Ethernet3": {"alias": "Eth0", "speed": "234"},
                "Ethernet4": {"alias": "Eth4", "speed": "234"}
            }
        }
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                port_config_update_validator(scope, patch_element) is True

    @patch("generic_config_updater.field_operation_validators.read_statedb_entry",
           mock.Mock(return_value="123,234"))
    def test_port_config_update_validator_invalid_speed_existing_state_db_nested_2(self):
        patch_element = {
            "path": "/PORT",
            "op": "add",
            "value": {
                "Ethernet3": {"alias": "Eth0", "speed": "234"},
                "Ethernet4": {"alias": "Eth4", "speed": "236"}
            }
        }
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                port_config_update_validator(scope, patch_element) is False

    def test_port_config_update_validator_remove(self):
        patch_element = {"path": "/PORT/Ethernet3", "op": "remove"}
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                port_config_update_validator(scope, patch_element) is True

    @patch("generic_config_updater.field_operation_validators.read_statedb_entry",
           mock.Mock(return_value="rs, fc"))
    def test_port_config_update_validator_invalid_fec_existing_state_db(self):
        patch_element = {"path": "/PORT/Ethernet3/fec", "op": "add", "value": "asf"}
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                port_config_update_validator(scope, patch_element) is False

    @patch("generic_config_updater.field_operation_validators.read_statedb_entry",
           mock.Mock(return_value="rs, fc"))
    def test_port_config_update_validator_invalid_fec_existing_state_db_nested(self):
        patch_element = {
            "path": "/PORT",
            "op": "add",
            "value": {
                "Ethernet3": {"alias": "Eth0", "fec": "none"},
                "Ethernet4": {"alias": "Eth4", "fec": "fs"}
            }
        }
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                port_config_update_validator(scope, patch_element) is False

    @patch("generic_config_updater.field_operation_validators.read_statedb_entry",
           mock.Mock(return_value="rs, fc"))
    def test_port_config_update_validator_valid_fec_existing_state_db_nested(self):
        patch_element = {
            "path": "/PORT",
            "op": "add",
            "value": {"Ethernet3": {"alias": "Eth0", "fec": "fc"}}
        }
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                port_config_update_validator(scope, patch_element) is True

    @patch("generic_config_updater.field_operation_validators.read_statedb_entry",
           mock.Mock(return_value="rs, fc"))
    def test_port_config_update_validator_valid_fec_existing_state_db_nested_2(self):
        patch_element = {
            "path": "/PORT",
            "op": "add",
            "value": {
                "Ethernet3": {"alias": "Eth0", "fec": "rs"},
                "Ethernet4": {"alias": "Eth4", "fec": "fc"}
            }
        }
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                port_config_update_validator(scope, patch_element) is True

    @patch("generic_config_updater.field_operation_validators.read_statedb_entry",
           mock.Mock(return_value="rs, fc"))
    def test_port_config_update_validator_valid_fec_existing_state_db(self):
        patch_element = {"path": "/PORT/Ethernet3/fec", "op": "add", "value": "rs"}
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                port_config_update_validator(scope, patch_element) is True

    @patch("generic_config_updater.field_operation_validators.read_statedb_entry",
           mock.Mock(return_value=""))
    def test_port_config_update_validator_valid_fec_no_state_db(self):
        patch_element = {"path": "/PORT/Ethernet3", "op": "add", "value": {"fec": "rs"}}
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                port_config_update_validator(scope, patch_element) is True

    @patch("generic_config_updater.field_operation_validators.read_statedb_entry",
           mock.Mock(return_value=""))
    def test_port_config_update_validator_invalid_fec_no_state_db(self):
        patch_element = {"path": "/PORT/Ethernet3/fec", "op": "add", "value": "rsf"}
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                port_config_update_validator(scope, patch_element) is False

    @patch("generic_config_updater.field_operation_validators.get_asic_name",
           mock.Mock(return_value="unknown"))
    def test_rdma_config_update_validator_unknown_asic(self):
        patch_element = {
            "path": "/PFC_WD/Ethernet4/restoration_time",
            "op": "replace",
            "value": "234234"
        }
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                rdma_config_update_validator(scope, patch_element) is False

    @patch("sonic_py_common.device_info.get_sonic_version_info",
           mock.Mock(return_value={"build_version": "SONiC.20220530"}))
    @patch("generic_config_updater.field_operation_validators.get_asic_name",
           mock.Mock(return_value="td3"))
    @patch("os.path.exists", mock.Mock(return_value=True))
    @patch("builtins.open", mock_open(read_data='''{"tables": {"BUFFER_POOL": {"validator_data": {
        "rdma_config_update_validator": {"Shared/headroom pool size changes": {"fields": [
            "ingress_lossless_pool/xoff", "ingress_lossless_pool/size", "egress_lossy_pool/size"
        ], "operations": ["replace"], "platforms": {"td3": "20221100"}}}}}}}'''))
    def test_rdma_config_update_validator_td3_asic_invalid_version(self):
        patch_element = {
            "path": "/BUFFER_POOL/ingress_lossless_pool/xoff",
            "op": "replace",
            "value": "234234"
        }
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                rdma_config_update_validator(scope, patch_element) is False

    @patch("sonic_py_common.device_info.get_sonic_version_info",
           mock.Mock(return_value={"build_version": "SONiC.20220530"}))
    @patch("generic_config_updater.field_operation_validators.get_asic_name",
           mock.Mock(return_value="spc1"))
    @patch("os.path.exists", mock.Mock(return_value=True))
    @patch("builtins.open", mock_open(read_data='''{"tables": {"PFC_WD": {"validator_data": {
        "rdma_config_update_validator": {"PFCWD enable/disable": {"fields": [
            "detection_time", "action"
        ], "operations": ["remove", "replace", "add"], "platforms": {"spc1": "20181100"}}}}}}}'''))
    def test_rdma_config_update_validator_spc_asic_valid_version_remove(self):
        patch_element = {"path": "/PFC_WD/Ethernet8/detection_time", "op": "remove"}
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                rdma_config_update_validator(scope, patch_element) is True

    @patch("sonic_py_common.device_info.get_sonic_version_info",
           mock.Mock(return_value={"build_version": "SONiC.20220530"}))
    @patch("generic_config_updater.field_operation_validators.get_asic_name",
           mock.Mock(return_value="spc1"))
    @patch("os.path.exists", mock.Mock(return_value=True))
    @patch("builtins.open", mock_open(read_data='''{"tables": {"PFC_WD": {"validator_data": {
        "rdma_config_update_validator": {"PFCWD enable/disable": {"fields": [
            "detection_time", "restoration_time", "action"
        ], "operations": ["remove", "replace", "add"], "platforms": {"spc1": "20181100"}}}}}}}'''))
    def test_rdma_config_update_validator_spc_asic_valid_version_add_pfcwd(self):
        patch_element = {
            "path": "/PFC_WD/Ethernet8",
            "op": "add",
            "value": {
                "action": "drop",
                "detection_time": "300",
                "restoration_time": "200"
            }
        }
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                rdma_config_update_validator(scope, patch_element) is True

    @patch("sonic_py_common.device_info.get_sonic_version_info",
           mock.Mock(return_value={"build_version": "SONiC.20220530"}))
    @patch("generic_config_updater.field_operation_validators.get_asic_name",
           mock.Mock(return_value="spc1"))
    @patch("os.path.exists", mock.Mock(return_value=True))
    @patch("builtins.open", mock_open(read_data='''{"tables": {"PFC_WD": {"validator_data": {
        "rdma_config_update_validator": {"PFCWD enable/disable": {"fields": [
            "detection_time", "action", ""
        ], "operations": ["remove", "replace", "add"], "platforms": {"spc1": "20181100"}}}}}}}'''))
    def test_rdma_config_update_validator_spc_asic_valid_version(self):
        patch_element = {"path": "/PFC_WD/Ethernet8", "op": "remove"}
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                rdma_config_update_validator(scope, patch_element) is True

    @patch("sonic_py_common.device_info.get_sonic_version_info",
           mock.Mock(return_value={"build_version": "SONiC.20220530"}))
    @patch("generic_config_updater.field_operation_validators.get_asic_name",
           mock.Mock(return_value="spc1"))
    @patch("os.path.exists", mock.Mock(return_value=True))
    @patch("builtins.open", mock_open(read_data='''{"tables": {"BUFFER_POOL": {"validator_data": {
        "rdma_config_update_validator": {"Shared/headroom pool size changes": {"fields": [
            "ingress_lossless_pool/xoff", "egress_lossy_pool/size"
        ], "operations": ["replace"], "platforms": {"spc1": "20181100"}}}}}}}'''))
    def test_rdma_config_update_validator_spc_asic_invalid_op(self):
        patch_element = {
            "path": "/BUFFER_POOL/ingress_lossless_pool/xoff",
            "op": "remove"
        }
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                rdma_config_update_validator(scope, patch_element) is False

    @patch("sonic_py_common.device_info.get_sonic_version_info",
           mock.Mock(return_value={"build_version": "SONiC.20220530"}))
    @patch("generic_config_updater.field_operation_validators.get_asic_name",
           mock.Mock(return_value="spc1"))
    @patch("os.path.exists", mock.Mock(return_value=True))
    @patch("builtins.open", mock_open(read_data='''{"tables": {"PFC_WD": {"validator_data": {
        "rdma_config_update_validator": {"PFCWD enable/disable": {"fields": [
            "detection_time", "action"
        ], "operations": ["remove", "replace", "add"], "platforms": {"spc1": "20181100"}}}}}}}'''))
    def test_rdma_config_update_validator_spc_asic_other_field(self):
        patch_element = {
            "path": "/PFC_WD/Ethernet8/other_field",
            "op": "add",
            "value": "sample_value"
        }
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                rdma_config_update_validator(scope, patch_element) is False

    def test_validate_field_operation_illegal__pfcwd(self):
        old_config = {"PFC_WD": {"GLOBAL": {"POLL_INTERVAL": "60"}}}
        target_config = {"PFC_WD": {"GLOBAL": {}}}
        config_wrapper = gu_common.ConfigWrapper()
        self.assertRaises(
            gu_common.IllegalPatchOperationError,
            config_wrapper.validate_field_operation,
            old_config,
            target_config
        )

    def test_validate_field_operation_legal__rm_loopback1(self):
        old_config = {
            "LOOPBACK_INTERFACE": {
                "Loopback0": {},
                "Loopback0|10.1.0.32/32": {},
                "Loopback1": {},
                "Loopback1|10.1.0.33/32": {}
            }
        }
        target_config = {
            "LOOPBACK_INTERFACE": {
                "Loopback0": {},
                "Loopback0|10.1.0.32/32": {}
            }
        }
        config_wrapper = gu_common.ConfigWrapper()
        config_wrapper.validate_field_operation(old_config, target_config)

    def test_validate_field_operation_illegal__rm_loopback0(self):
        old_config = {
            "LOOPBACK_INTERFACE": {
                "Loopback0": {},
                "Loopback0|10.1.0.32/32": {},
                "Loopback1": {},
                "Loopback1|10.1.0.33/32": {}
            }
        }
        target_config = {
            "LOOPBACK_INTERFACE": {
                "Loopback1": {},
                "Loopback1|10.1.0.33/32": {}
            }
        }
        config_wrapper = gu_common.ConfigWrapper()
        self.assertRaises(
            gu_common.IllegalPatchOperationError,
            config_wrapper.validate_field_operation,
            old_config,
            target_config
        )

class TestGetAsicName(unittest.TestCase):

    @patch('sonic_py_common.device_info.get_sonic_version_info')
    @patch('subprocess.Popen')
    def test_get_asic_spc1(self, mock_popen, mock_get_sonic_version_info):
        mock_get_sonic_version_info.return_value = {'asic_type': 'mellanox'}
        mock_popen.return_value = mock.Mock()
        mock_popen.return_value.communicate.return_value = ["Mellanox-SN2700-D48C8", 0]
        for scope in ["localhost", "asic0"]:
            self.assertEqual(fov.get_asic_name(), "spc1")

    @patch('sonic_py_common.device_info.get_sonic_version_info')
    @patch('subprocess.Popen')
    def test_get_asic_spc2(self, mock_popen, mock_get_sonic_version_info):
        mock_get_sonic_version_info.return_value = {'asic_type': 'mellanox'}
        mock_popen.return_value = mock.Mock()
        mock_popen.return_value.communicate.return_value = ["ACS-MSN3800", 0]
        for scope in ["localhost", "asic0"]:
            self.assertEqual(fov.get_asic_name(), "spc2")

    @patch('sonic_py_common.device_info.get_sonic_version_info')
    @patch('subprocess.Popen')
    def test_get_asic_spc3(self, mock_popen, mock_get_sonic_version_info):
        mock_get_sonic_version_info.return_value = {'asic_type': 'mellanox'}
        mock_popen.return_value = mock.Mock()
        mock_popen.return_value.communicate.return_value = ["Mellanox-SN4600C-C64", 0]
        for scope in ["localhost", "asic0"]:
            self.assertEqual(fov.get_asic_name(), "spc3")

    @patch('sonic_py_common.device_info.get_sonic_version_info')
    @patch('subprocess.Popen')
    def test_get_asic_spc4(self, mock_popen, mock_get_sonic_version_info):
        mock_get_sonic_version_info.return_value = {'asic_type': 'mellanox'}
        mock_popen.return_value = mock.Mock()
        mock_popen.return_value.communicate.return_value = ["ACS-SN5600", 0]
        for scope in ["localhost", "asic0"]:
            self.assertEqual(fov.get_asic_name(), "spc4")

    @patch('sonic_py_common.device_info.get_sonic_version_info')
    @patch('subprocess.Popen')
    def test_get_asic_spc4(self, mock_popen, mock_get_sonic_version_info):
        mock_get_sonic_version_info.return_value = {'asic_type': 'mellanox'}
        mock_popen.return_value = mock.Mock()
        mock_popen.return_value.communicate.return_value = ["Mellanox-SN2700-A1", 0]
        for scope in ["localhost", "asic0"]:
            self.assertEqual(fov.get_asic_name(), "spc1")

    @patch('sonic_py_common.device_info.get_sonic_version_info')
    @patch('subprocess.Popen')
    def test_get_asic_spc5(self, mock_popen, mock_get_sonic_version_info):
        mock_get_sonic_version_info.return_value = {'asic_type': 'mellanox'}
        mock_popen.return_value = mock.Mock()
        mock_popen.return_value.communicate.return_value = ["Mellanox-SN5640-C512S2", 0]
        for scope in ["localhost", "asic0"]:
            self.assertEqual(fov.get_asic_name(), "spc5")

    @patch('sonic_py_common.device_info.get_sonic_version_info')
    @patch('subprocess.Popen')
    def test_get_asic_th(self, mock_popen, mock_get_sonic_version_info):
        mock_get_sonic_version_info.return_value = {'asic_type': 'broadcom'}
        mock_popen.return_value = mock.Mock()
        mock_popen.return_value.communicate.return_value = ["Force10-S6100", 0]
        for scope in ["localhost", "asic0"]:
            self.assertEqual(fov.get_asic_name(), "th")

    @patch('sonic_py_common.device_info.get_sonic_version_info')
    @patch('subprocess.Popen')
    def test_get_asic_th2(self, mock_popen, mock_get_sonic_version_info):
        mock_get_sonic_version_info.return_value = {'asic_type': 'broadcom'}
        mock_popen.return_value = mock.Mock()
        mock_popen.return_value.communicate.return_value = ["Arista-7260CX3-D108C8", 0]
        for scope in ["localhost", "asic0"]:
            self.assertEqual(fov.get_asic_name(), "th2")

    @patch('sonic_py_common.device_info.get_sonic_version_info')
    @patch('subprocess.Popen')
    def test_get_asic_th3(self, mock_popen, mock_get_sonic_version_info):
        mock_get_sonic_version_info.return_value = {'asic_type': 'broadcom'}
        mock_popen.return_value = mock.Mock()
        mock_popen.return_value.communicate.return_value = ["Nokia-IXR7220-H3", 0]
        for scope in ["localhost", "asic0"]:
            self.assertEqual(fov.get_asic_name(), "th3")

    @patch('sonic_py_common.device_info.get_sonic_version_info')
    @patch('subprocess.Popen')
    def test_get_asic_th4(self, mock_popen, mock_get_sonic_version_info):
        mock_get_sonic_version_info.return_value = {'asic_type': 'broadcom'}
        mock_popen.return_value = mock.Mock()
        mock_popen.return_value.communicate.return_value = ["Nokia-IXR7220-H4-64D", 0]
        for scope in ["localhost", "asic0"]:
            self.assertEqual(fov.get_asic_name(), "th4")

    @patch('sonic_py_common.device_info.get_sonic_version_info')
    @patch('subprocess.Popen')
    def test_get_asic_th5(self, mock_popen, mock_get_sonic_version_info):
        mock_get_sonic_version_info.return_value = {'asic_type': 'broadcom'}
        mock_popen.return_value = mock.Mock()
        mock_popen.return_value.communicate.return_value = ["Nokia-IXR7220-H5-64D", 0]
        for scope in ["localhost", "asic0"]:
            self.assertEqual(fov.get_asic_name(), "th5")

    @patch('sonic_py_common.device_info.get_sonic_version_info')
    @patch('subprocess.Popen')
    def test_get_asic_td2(self, mock_popen, mock_get_sonic_version_info):
        mock_get_sonic_version_info.return_value = {'asic_type': 'broadcom'}
        mock_popen.return_value = mock.Mock()
        mock_popen.return_value.communicate.return_value = ["Force10-S6000", 0]
        for scope in ["localhost", "asic0"]:
            self.assertEqual(fov.get_asic_name(), "td2")

    @patch('sonic_py_common.device_info.get_sonic_version_info')
    @patch('subprocess.Popen')
    def test_get_asic_td3(self, mock_popen, mock_get_sonic_version_info):
        mock_get_sonic_version_info.return_value = {'asic_type': 'broadcom'}
        mock_popen.return_value = mock.Mock()
        mock_popen.return_value.communicate.return_value = ["Arista-7050CX3-32S-C32", 0]
        for scope in ["localhost", "asic0"]:
            self.assertEqual(fov.get_asic_name(), "td3")

    @patch('sonic_py_common.device_info.get_sonic_version_info')
    @patch('subprocess.Popen')
    def test_get_asic_td4(self, mock_popen, mock_get_sonic_version_info):
        mock_get_sonic_version_info.return_value = {'asic_type': 'broadcom'}
        mock_popen.return_value = mock.Mock()
        mock_popen.return_value.communicate.return_value = ["Nokia-IXR7220-D4-36D", 0]
        for scope in ["localhost", "asic0"]:
            self.assertEqual(fov.get_asic_name(), "td4")

    @patch('sonic_py_common.device_info.get_sonic_version_info')
    @patch('subprocess.Popen')
    def test_get_asic_j2cplus(self, mock_popen, mock_get_sonic_version_info):
        mock_get_sonic_version_info.return_value = {'asic_type': 'broadcom'}
        mock_popen.return_value = mock.Mock()
        mock_popen.return_value.communicate.return_value = ["Nokia-IXR7250E-36x100G", 0]
        for scope in ["localhost", "asic0"]:
            self.assertEqual(fov.get_asic_name(), "j2c+")

    @patch('sonic_py_common.device_info.get_sonic_version_info')
    @patch('subprocess.Popen')
    def test_get_asic_q2cplus(self, mock_popen, mock_get_sonic_version_info):
        mock_get_sonic_version_info.return_value = {'asic_type': 'broadcom'}
        mock_popen.return_value = mock.Mock()
        mock_popen.return_value.communicate.return_value = ["Nokia-IXR7250-X1B", 0]
        for scope in ["localhost", "asic0"]:
            self.assertEqual(fov.get_asic_name(), "q2c+")

    @patch('sonic_py_common.device_info.get_sonic_version_info')
    @patch('subprocess.Popen')
    def test_get_asic_cisco(self, mock_popen, mock_get_sonic_version_info):
        mock_get_sonic_version_info.return_value = {'asic_type': 'cisco-8000'}
        for scope in ["localhost", "asic0"]:
            self.assertEqual(fov.get_asic_name(), "cisco-8000")

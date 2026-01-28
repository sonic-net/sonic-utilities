import pytest
import mock
import unittest
import generic_config_updater
import generic_config_updater.field_operation_validators as fov
import generic_config_updater.gu_common as gu_common

from unittest.mock import mock_open
from mock import patch


class TestValidateFieldOperation:

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

    @patch("sonic_py_common.device_info.is_chassis", mock.MagicMock(return_value=True))
    @patch("generic_config_updater.field_operation_validators.read_statedb_entry",
           mock.Mock(return_value="123,234"))
    def test_port_config_update_validator_invalid_speed_for_chassis(self):
        # 235 is in supported speeds, but for chassis, skip speed validation
        patch_element = {"path": "/PORT/Ethernet3", "op": "add", "value": {"speed": 235}}
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                port_config_update_validator(scope, patch_element) is True

    @patch("sonic_py_common.device_info.is_chassis", mock.MagicMock(return_value=False))
    @patch("generic_config_updater.field_operation_validators.read_statedb_entry",
           mock.Mock(return_value="123,234"))
    def test_port_config_update_validator_valid_speed_for_nonchassis(self):
        # 234 is not in supported speeds, but for chassis, skip speed validation
        patch_element = {"path": "/PORT/Ethernet3", "op": "add", "value": {"speed": 234}}
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                port_config_update_validator(scope, patch_element) is True

    @patch("sonic_py_common.device_info.is_chassis", mock.MagicMock(return_value=False))
    @patch("generic_config_updater.field_operation_validators.read_statedb_entry",
           mock.Mock(return_value="123,234"))
    def test_port_config_update_validator_invalid_speed_for_nonchassis(self):
        # 235 is not in supported speeds, but for chassis, skip speed validation
        patch_element = {"path": "/PORT/Ethernet3", "op": "add", "value": {"speed": 235}}
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                port_config_update_validator(scope, patch_element) is False

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

    @pytest.mark.parametrize(
        "field,value,op", [
            pytest.param("xoff", "1000", "replace"),
            pytest.param("dynamic_th", "0", "replace"),
            pytest.param("packet_discard_action", "trim", "add"),
            pytest.param("packet_discard_action", "drop", "replace")
        ]
    )
    @pytest.mark.parametrize(
        "asic", [
            "spc4",
            "spc5",
            "th5"
        ]
    )
    @pytest.mark.parametrize(
        "scope", [
            "localhost",
            "asic0"
        ]
    )
    def test_buffer_profile_config_update_validator(self, scope, asic, field, value, op):
        patch_element = {
            "path": "/BUFFER_PROFILE/sample_profile/{}".format(field),
            "op": op,
            "value": value
        }

        with (
            patch(
                "generic_config_updater.field_operation_validators.get_asic_name",
                return_value=asic
            ),
            patch(
                "sonic_py_common.device_info.get_sonic_version_info",
                return_value={"build_version": "SONiC.20241200"}
            )
        ):
            assert fov.buffer_profile_config_update_validator(scope, patch_element) is True

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

    @patch("sonic_py_common.device_info.get_sonic_version_info",
           mock.Mock(return_value={"build_version": "SONiC.20220530"}))
    @patch("generic_config_updater.field_operation_validators.get_asic_name",
           mock.Mock(return_value="spc1"))
    @patch("os.path.exists", mock.Mock(return_value=True))
    @patch("builtins.open", mock_open(read_data='''{"tables": {"PFC_WD": {"validator_data": {
        "rdma_config_update_validator": {"PFCWD enable/disable": {"fields": [
            "restoration_time", "detection_time", "action", "global/poll_interval", "pfc_stat_history"
        ], "operations": ["remove", "replace", "add"], "platforms": {"spc1": "20181100"}}}}}}}'''))
    def test_rdma_config_update_validator_spc_asic_pfc_stat_history(self):
        patch_element = {
            "path": "/PFC_WD/Ethernet8/pfc_stat_history",
            "op": "replace",
            "value": "enable"
        }
        for scope in ["localhost", "asic0"]:
            assert generic_config_updater.field_operation_validators.\
                rdma_config_update_validator(scope, patch_element) is True

    def test_validate_field_operation_illegal__pfcwd(self):
        old_config = {"PFC_WD": {"GLOBAL": {"POLL_INTERVAL": "60"}}}
        target_config = {"PFC_WD": {"GLOBAL": {}}}
        config_wrapper = gu_common.ConfigWrapper()
        pytest.raises(
            gu_common.IllegalPatchOperationError,
            config_wrapper.validate_field_operation,
            old_config,
            target_config
        )

    @patch("sonic_py_common.device_info.get_sonic_version_info",
           mock.Mock(return_value={"build_version": "20241211.49"}))
    @patch("generic_config_updater.field_operation_validators.get_asic_name",
           mock.Mock(return_value="spc1"))
    @patch("os.path.exists", mock.Mock(return_value=True))
    @patch(
        "builtins.open",
        mock_open(
            read_data=(
                '{"tables": {"BUFFER_POOL": {'
                '"field_operation_validators": ['
                '"generic_config_updater.field_operation_validators.rdma_config_update_validator"'
                '], "validator_data": {"rdma_config_update_validator": {"Blocked ops": '
                '{"fields": ["ingress_lossless_pool/xoff", '
                '"ingress_lossless_pool/size", "egress_lossy_pool/size"], '
                '"operations": [], "platforms": {"spc1": "20181100"}}}}}}}'
            )
        )
    )
    def test_validate_field_operation_illegal__buffer_pool(self):
        old_config = {
            "BUFFER_POOL": {
                "ingress_lossless_pool": {"xoff": "1000"}
            }
        }
        target_config = {
            "BUFFER_POOL": {
                "ingress_lossless_pool": {"xoff": "2000"}
            }
        }
        config_wrapper = gu_common.ConfigWrapper()
        pytest.raises(
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
        pytest.raises(
            gu_common.IllegalPatchOperationError,
            config_wrapper.validate_field_operation,
            old_config,
            target_config
        )

    def test_validate_field_operation_buffer_queue_replace_profile(self):
        old_config = {
            "BUFFER_QUEUE": {
                "Ethernet0|3": {"profile": "ingress_lossless_profile"}
            }
        }
        target_config = {
            "BUFFER_QUEUE": {
                "Ethernet0|3": {"profile": "ingress_lossless_profile_new"}
            }
        }
        config_wrapper = gu_common.ConfigWrapper()
        config_wrapper.validate_field_operation(old_config, target_config)

    def test_validate_field_operation_buffer_queue_add_profile(self):
        old_config = {"BUFFER_QUEUE": {}}
        target_config = {
            "BUFFER_QUEUE": {
                "Ethernet0|4": {"profile": "ingress_lossless_profile"}
            }
        }
        config_wrapper = gu_common.ConfigWrapper()
        config_wrapper.validate_field_operation(old_config, target_config)

    def test_validate_field_operation_buffer_queue_remove_entry(self):
        old_config = {
            "BUFFER_QUEUE": {
                "Ethernet0|5": {"profile": "ingress_lossless_profile"}
            }
        }
        target_config = {"BUFFER_QUEUE": {}}
        config_wrapper = gu_common.ConfigWrapper()
        config_wrapper.validate_field_operation(old_config, target_config)

    def test_validate_field_operation_buffer_pg_replace_profile(self):
        old_config = {
            "BUFFER_PG": {
                "Ethernet0|3-4": {"profile": "pg_lossless_40000_5m_profile"}
            }
        }
        target_config = {
            "BUFFER_PG": {
                "Ethernet0|3-4": {"profile": "pg_lossless_40000_10m_profile"}
            }
        }
        config_wrapper = gu_common.ConfigWrapper()
        config_wrapper.validate_field_operation(old_config, target_config)

    def test_validate_field_operation_buffer_pg_add_profile(self):
        old_config = {"BUFFER_PG": {}}
        target_config = {
            "BUFFER_PG": {
                "Ethernet0|5-6": {"profile": "pg_lossless_40000_5m_profile"}
            }
        }
        config_wrapper = gu_common.ConfigWrapper()
        config_wrapper.validate_field_operation(old_config, target_config)

    def test_validate_field_operation_buffer_pg_remove_entry(self):
        old_config = {
            "BUFFER_PG": {
                "Ethernet0|7": {"profile": "pg_lossless_40000_5m_profile"}
            }
        }
        target_config = {"BUFFER_PG": {}}
        config_wrapper = gu_common.ConfigWrapper()
        config_wrapper.validate_field_operation(old_config, target_config)

    @pytest.mark.parametrize(
        "field,old_value,new_value,op", [
            ("ecn", "ecn_all", "ecn_green", "replace"),
            ("green_drop_probability", "5", "6", "replace"),
            ("green_max_threshold", "136200192", "136200193", "replace"),
            ("green_min_threshold", "136200192", "136200193", "replace"),
            ("red_drop_probability", "5", "6", "replace"),
            ("red_max_threshold", "282624", "282625", "replace"),
            ("red_min_threshold", "166912", "166913", "replace"),
            ("wred_green_enable", "false", "true", "replace"),
            ("wred_red_enable", "false", "true", "replace"),
            ("wred_yellow_enable", "false", "true", "replace"),
            ("yellow_drop_probability", "5", "6", "replace"),
            ("yellow_max_threshold", "282624", "282625", "replace"),
            ("yellow_min_threshold", "166912", "166913", "replace")
        ]
    )
    def test_validate_field_operation_wred_profile_replace(self, field, old_value, new_value, op):
        old_config = {"WRED_PROFILE": {"AZURE_LOSSY": {field: old_value}}}
        target_config = {"WRED_PROFILE": {"AZURE_LOSSY": {field: new_value}}}
        config_wrapper = gu_common.ConfigWrapper()
        config_wrapper.validate_field_operation(old_config, target_config)

    @pytest.mark.parametrize(
        "field,value", [
            ("green_min_threshold", "1200"),
            ("yellow_max_threshold", "2400"),
            ("red_min_threshold", "3200"),
            ("green_drop_probability", "10"),
            ("wred_green_enable", "true"),
            ("wred_yellow_enable", "true"),
            ("wred_red_enable", "true")
        ]
    )
    def test_validate_field_operation_wred_profile_add(self, field, value):
        old_config = {"WRED_PROFILE": {"AZURE_LOSSY": {}}}
        target_config = {"WRED_PROFILE": {"AZURE_LOSSY": {field: value}}}
        config_wrapper = gu_common.ConfigWrapper()
        config_wrapper.validate_field_operation(old_config, target_config)

    @pytest.mark.parametrize(
        "table", [
            "BUFFER_PORT_EGRESS_PROFILE_LIST",
            "BUFFER_PORT_INGRESS_PROFILE_LIST"
        ]
    )
    def test_validate_field_operation_buffer_port_profile_list_add(self, table):
        old_config = {table: {"Ethernet0": {}}}
        target_config = {table: {"Ethernet0": {"profile_list": "AZURE_PROFILE"}}}
        config_wrapper = gu_common.ConfigWrapper()
        config_wrapper.validate_field_operation(old_config, target_config)

    @pytest.mark.parametrize(
        "table", [
            "BUFFER_PORT_EGRESS_PROFILE_LIST",
            "BUFFER_PORT_INGRESS_PROFILE_LIST"
        ]
    )
    def test_validate_field_operation_buffer_port_profile_list_replace(self, table):
        old_config = {table: {"Ethernet0": {"profile_list": "AZURE_PROFILE"}}}
        target_config = {table: {"Ethernet0": {"profile_list": "NEW_PROFILE"}}}
        config_wrapper = gu_common.ConfigWrapper()
        config_wrapper.validate_field_operation(old_config, target_config)

    @pytest.mark.parametrize(
        "table", [
            "BUFFER_PORT_EGRESS_PROFILE_LIST",
            "BUFFER_PORT_INGRESS_PROFILE_LIST"
        ]
    )
    def test_validate_field_operation_buffer_port_profile_list_remove(self, table):
        old_config = {table: {"Ethernet0": {"profile_list": "AZURE_PROFILE"}}}
        target_config = {table: {"Ethernet0": {}}}
        config_wrapper = gu_common.ConfigWrapper()
        config_wrapper.validate_field_operation(old_config, target_config)

    def test_validate_field_operation_queue_scheduler_replace(self):
        old_config = {"QUEUE": {"Ethernet0|0": {"scheduler": "sched0"}}}
        target_config = {"QUEUE": {"Ethernet0|0": {"scheduler": "sched1"}}}
        config_wrapper = gu_common.ConfigWrapper()
        config_wrapper.validate_field_operation(old_config, target_config)

    def test_validate_field_operation_queue_wred_profile_add(self):
        old_config = {"QUEUE": {"Ethernet0|1": {}}}
        target_config = {"QUEUE": {"Ethernet0|1": {"wred_profile": "WRED_PROFILE"}}}
        config_wrapper = gu_common.ConfigWrapper()
        config_wrapper.validate_field_operation(old_config, target_config)

    def test_validate_field_operation_queue_wred_profile_replace(self):
        old_config = {"QUEUE": {"Ethernet0|1": {"wred_profile": "WRED_PROFILE"}}}
        target_config = {"QUEUE": {"Ethernet0|1": {"wred_profile": "WRED_PROFILE_NEW"}}}
        config_wrapper = gu_common.ConfigWrapper()
        config_wrapper.validate_field_operation(old_config, target_config)

    @pytest.mark.parametrize(
        "field,new_value", [
            ("dscp_to_tc_map", "AZURE"),
            ("tc_to_pg_map", "AZURE"),
            ("tc_to_queue_map", "AZURE")
        ]
    )
    def test_validate_field_operation_port_qos_map_replace(self, field, new_value):
        old_config = {"PORT_QOS_MAP": {"Ethernet0": {field: "DEFAULT"}}}
        target_config = {"PORT_QOS_MAP": {"Ethernet0": {field: new_value}}}
        config_wrapper = gu_common.ConfigWrapper()
        config_wrapper.validate_field_operation(old_config, target_config)

    def test_validate_field_operation_port_qos_map_tc_to_dscp_add(self):
        old_config = {"PORT_QOS_MAP": {"Ethernet0": {}}}
        target_config = {"PORT_QOS_MAP": {"Ethernet0": {"tc_to_dscp_map": "AZURE"}}}
        config_wrapper = gu_common.ConfigWrapper()
        config_wrapper.validate_field_operation(old_config, target_config)

    def test_validate_field_operation_port_qos_map_tc_to_dscp_replace(self):
        old_config = {"PORT_QOS_MAP": {"Ethernet0": {"tc_to_dscp_map": "DEFAULT"}}}
        target_config = {"PORT_QOS_MAP": {"Ethernet0": {"tc_to_dscp_map": "AZURE"}}}
        config_wrapper = gu_common.ConfigWrapper()
        config_wrapper.validate_field_operation(old_config, target_config)

    def test_validate_field_operation_port_qos_map_dscp_to_tc_replace(self):
        old_config = {"PORT_QOS_MAP": {"Ethernet0": {"dscp_to_tc_map": "DEFAULT"}}}
        target_config = {"PORT_QOS_MAP": {"Ethernet0": {"dscp_to_tc_map": "AZURE"}}}
        config_wrapper = gu_common.ConfigWrapper()
        config_wrapper.validate_field_operation(old_config, target_config)

    def test_validate_field_operation_port_qos_map_tc_to_pg_replace(self):
        old_config = {"PORT_QOS_MAP": {"Ethernet0": {"tc_to_pg_map": "DEFAULT"}}}
        target_config = {"PORT_QOS_MAP": {"Ethernet0": {"tc_to_pg_map": "AZURE"}}}
        config_wrapper = gu_common.ConfigWrapper()
        config_wrapper.validate_field_operation(old_config, target_config)

    def test_validate_field_operation_port_qos_map_tc_to_queue_replace(self):
        old_config = {"PORT_QOS_MAP": {"Ethernet0": {"tc_to_queue_map": "DEFAULT"}}}
        target_config = {"PORT_QOS_MAP": {"Ethernet0": {"tc_to_queue_map": "AZURE"}}}
        config_wrapper = gu_common.ConfigWrapper()
        config_wrapper.validate_field_operation(old_config, target_config)

    def test_validate_field_operation_scheduler_weight_replace(self):
        old_config = {"SCHEDULER": {"scheduler.0": {"weight": "10", "type": "DWRR"}}}
        target_config = {"SCHEDULER": {"scheduler.0": {"weight": "20", "type": "DWRR"}}}
        config_wrapper = gu_common.ConfigWrapper()
        config_wrapper.validate_field_operation(old_config, target_config)

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
    def test_get_asic_jr2(self, mock_popen, mock_get_sonic_version_info):
        mock_get_sonic_version_info.return_value = {'asic_type': 'broadcom'}
        mock_popen.return_value = mock.Mock()
        mock_popen.return_value.communicate.return_value = ["Arista-7800R3-48CQ2-C48", 0]
        for scope in ["localhost", "asic0"]:
            self.assertEqual(fov.get_asic_name(), "jr2")

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

    @patch('sonic_py_common.device_info.get_sonic_version_info')
    def test_get_asic_marvell_teralynx(self, mock_get_sonic_version_info):
        mock_get_sonic_version_info.return_value = {'asic_type': 'marvell-teralynx'}
        for scope in ["localhost", "asic0"]:
            self.assertEqual(fov.get_asic_name(), "marvell-teralynx")

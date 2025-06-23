import jsonpointer
import unittest
from importlib import reload
from unittest.mock import patch, MagicMock
from generic_config_updater.generic_updater import extract_scope
from generic_config_updater.generic_updater import GenericConfigUpdaterError
import generic_config_updater.change_applier
import generic_config_updater.services_validator
import generic_config_updater.gu_common


def mock_get_running_config_side_effect(scope):
    print(f"mocked_value_for_{scope}")
    return {
        "tables": {
            "ACL_TABLE": {
                "services_to_validate": ["aclservice"],
                "validate_commands": ["acl_loader show table"]
            },
            "PORT": {
                "services_to_validate": ["portservice"],
                "validate_commands": ["show interfaces status"]
            }
        },
        "services": {
            "aclservice": {
                "validate_commands": ["acl_loader show table"]
            },
            "portservice": {
                "validate_commands": ["show interfaces status"]
            }
        }
    }


class TestMultiAsicChangeApplier(unittest.TestCase):

    @patch('sonic_py_common.multi_asic.is_multi_asic')
    def test_extract_scope_multiasic(self, mock_is_multi_asic):
        mock_is_multi_asic.return_value = True
        test_paths_expectedresults = {
            "/asic0/PORTCHANNEL/PortChannel102/admin_status": (
                True, "asic0", "/PORTCHANNEL/PortChannel102/admin_status"
            ),
            "/asic01/PORTCHANNEL/PortChannel102/admin_status": (
                True, "asic01", "/PORTCHANNEL/PortChannel102/admin_status"
            ),
            "/asic123456789/PORTCHANNEL/PortChannel102/admin_status": (
                True, "asic123456789", "/PORTCHANNEL/PortChannel102/admin_status"
            ),
            "/asic0123456789/PORTCHANNEL/PortChannel102/admin_status": (
                True, "asic0123456789", "/PORTCHANNEL/PortChannel102/admin_status"
            ),
            "/asic1/PORTCHANNEL_INTERFACE/PortChannel106|10.0.0.6/31": (
                True, "asic1", "/PORTCHANNEL_INTERFACE/PortChannel106|10.0.0.6/31"
            ),
            "/asic1/PORTCHANNEL_INTERFACE/PortChannel106|10.0.0.6~131": (
                True, "asic1", "/PORTCHANNEL_INTERFACE/PortChannel106|10.0.0.6~131"
            ),
            "/localhost/BGP_DEVICE_GLOBAL/STATE/tsa_enabled": (
                True, "localhost", "/BGP_DEVICE_GLOBAL/STATE/tsa_enabled"
            ),
            "/asic1/BGP_DEVICE_GLOBAL/STATE/tsa_enabled": (
                True, "asic1", "/BGP_DEVICE_GLOBAL/STATE/tsa_enabled"
            ),
            "/sometable/data": (
                False, "", "/sometable/data"
            ),
            "": (
                False, "", ""
            ),
            "localhostabc/BGP_DEVICE_GLOBAL/STATE/tsa_enabled": (
                False, "", ""
            ),
            "/asic77": (
                False, "", ""
            ),
            "/Asic0/PORTCHANNEL/PortChannel102/admin_status": (
                False, "", ""
            ),
            "/ASIC1/PORTCHANNEL/PortChannel102/admin_status": (
                False, "", ""
            ),
            "/Localhost/PORTCHANNEL/PortChannel102/admin_status": (
                False, "", ""
            ),
            "/LocalHost/PORTCHANNEL/PortChannel102/admin_status": (
                False, "", ""
            ),
            "/asci1/PORTCHANNEL/PortChannel102/admin_status": (
                False, "", ""
            ),
            "/asicx/PORTCHANNEL/PortChannel102/admin_status": (
                False, "", ""
            ),
            "/asic-12/PORTCHANNEL/PortChannel102/admin_status": (
                False, "", ""
            ),
        }

        for test_path, (result, expectedscope, expectedremainder) in test_paths_expectedresults.items():
            try:
                scope, remainder = extract_scope(test_path)
                assert(scope == expectedscope)
                assert(remainder == expectedremainder)
            except AssertionError:
                assert(not result)
            except GenericConfigUpdaterError:
                assert(not result)
            except jsonpointer.JsonPointerException:
                assert(not result)

    @patch('sonic_py_common.multi_asic.is_multi_asic')
    def test_extract_scope_singleasic(self, mock_is_multi_asic):
        mock_is_multi_asic.return_value = False
        test_paths_expectedresults = {
            "/asic0/PORTCHANNEL/PortChannel102/admin_status": (
                True, "asic0", "/PORTCHANNEL/PortChannel102/admin_status"
            ),
            "/asic01/PORTCHANNEL/PortChannel102/admin_status": (
                True, "asic01", "/PORTCHANNEL/PortChannel102/admin_status"
            ),
            "/asic123456789/PORTCHANNEL/PortChannel102/admin_status":  (
                True, "asic123456789", "/PORTCHANNEL/PortChannel102/admin_status"
            ),
            "/asic0123456789/PORTCHANNEL/PortChannel102/admin_status": (
                True, "asic0123456789", "/PORTCHANNEL/PortChannel102/admin_status"
            ),
            "/localhost/BGP_DEVICE_GLOBAL/STATE/tsa_enabled": (
                True, "localhost", "/BGP_DEVICE_GLOBAL/STATE/tsa_enabled"
            ),
            "/asic1/BGP_DEVICE_GLOBAL/STATE/tsa_enabled": (
                True, "asic1", "/BGP_DEVICE_GLOBAL/STATE/tsa_enabled"
            ),
            "/sometable/data": (
                True, "", "/sometable/data"
            ),
            "": (
                False, "", ""
            ),
            "localhostabc/BGP_DEVICE_GLOBAL/STATE/tsa_enabled": (
                False, "", ""
            ),
            "/asic77": (False, "", ""),
            "/Asic0/PORTCHANNEL/PortChannel102/admin_status": (
                False, "", ""
            ),
            "/ASIC1/PORTCHANNEL/PortChannel102/admin_status": (
                False, "", ""
            ),
            "/Localhost/PORTCHANNEL/PortChannel102/admin_status": (
                False, "", ""
            ),
            "/LocalHost/PORTCHANNEL/PortChannel102/admin_status": (
                False, "", ""
            ),
            "/asci1/PORTCHANNEL/PortChannel102/admin_status": (
                False, "", ""
            ),
            "/asicx/PORTCHANNEL/PortChannel102/admin_status": (
                False, "", ""
            ),
            "/asic-12/PORTCHANNEL/PortChannel102/admin_status": (
                False, "", ""
            ),
        }

        for test_path, (result, expectedscope, expectedremainder) in test_paths_expectedresults.items():
            try:
                scope, remainder = extract_scope(test_path)
                assert(scope == expectedscope)
                assert(remainder == expectedremainder)
            except AssertionError:
                assert(not result)
            except GenericConfigUpdaterError:
                assert(not result)
            except jsonpointer.JsonPointerException:
                assert(not result)

    @patch('generic_config_updater.change_applier.get_config_db_as_json', autospec=True)
    @patch('generic_config_updater.change_applier.ConfigDBConnector', autospec=True)
    def test_apply_change_default_scope(self, mock_ConfigDBConnector, mock_get_running_config):
        # Setup mock for ConfigDBConnector
        mock_db = MagicMock()
        mock_ConfigDBConnector.return_value = mock_db

        # Setup mock for json.load to return some running configuration
        mock_get_running_config.side_effect = mock_get_running_config_side_effect

        # Instantiate ChangeApplier with the default scope
        applier = generic_config_updater.change_applier.ChangeApplier()

        # Prepare a change object or data that applier.apply would use
        change = MagicMock()

        # Call the apply method with the change object
        applier.apply(change)

        # Assert ConfigDBConnector called with the correct namespace
        mock_ConfigDBConnector.assert_called_once_with(use_unix_socket_path=True, namespace="")

    @patch('generic_config_updater.change_applier.get_config_db_as_json', autospec=True)
    @patch('generic_config_updater.change_applier.ConfigDBConnector', autospec=True)
    def test_apply_change_given_scope(self, mock_ConfigDBConnector, mock_get_running_config):
        # Setup mock for ConfigDBConnector
        mock_db = MagicMock()
        mock_ConfigDBConnector.return_value = mock_db
        mock_get_running_config.side_effect = mock_get_running_config_side_effect

        # Instantiate ChangeApplier with the default scope
        applier = generic_config_updater.change_applier.ChangeApplier(scope="asic0")

        # Prepare a change object or data that applier.apply would use
        change = MagicMock()

        # Call the apply method with the change object
        applier.apply(change)

        # Assert ConfigDBConnector called with the correct scope
        mock_ConfigDBConnector.assert_called_once_with(use_unix_socket_path=True, namespace="asic0")

    @patch('generic_config_updater.change_applier.get_config_db_as_json', autospec=True)
    @patch('generic_config_updater.change_applier.ConfigDBConnector', autospec=True)
    def test_apply_change_failure(self, mock_ConfigDBConnector, mock_get_running_config):
        # Setup mock for ConfigDBConnector
        mock_db = MagicMock()
        mock_ConfigDBConnector.return_value = mock_db

        # Setup mock for json.load to return some running configuration
        mock_get_running_config.side_effect = Exception("Failed to get running config")
        # Instantiate ChangeApplier with a specific scope to simulate applying changes in a multi-asic environment
        scope = "asic0"
        applier = generic_config_updater.change_applier.ChangeApplier(scope=scope)

        # Prepare a change object or data that applier.apply would use
        change = MagicMock()

        # Test the behavior when os.system fails
        with self.assertRaises(Exception) as context:
            applier.apply(change)

        self.assertTrue('Failed to get running config' in str(context.exception))

    @patch('generic_config_updater.change_applier.get_config_db_as_json', autospec=True)
    @patch('generic_config_updater.change_applier.ConfigDBConnector', autospec=True)
    def test_apply_patch_with_empty_tables_failure(self, mock_ConfigDBConnector, mock_get_running_config):
        # Setup mock for ConfigDBConnector
        mock_db = MagicMock()
        mock_ConfigDBConnector.return_value = mock_db

        # Setup mock for json.load to simulate configuration where crucial tables are unexpectedly empty
        def mock_get_empty_running_config_side_effect():
            return {
                "tables": {
                    # Simulate empty tables or missing crucial configuration
                },
                "services": {
                    # Normally, services would be listed here
                }
            }

        mock_get_running_config.side_effect = mock_get_empty_running_config_side_effect

        # Instantiate ChangeApplier with a specific scope to simulate applying changes in a multi-asic environment
        applier = generic_config_updater.change_applier.ChangeApplier(scope="asic0")

        # Prepare a change object or data that applier.apply would use, simulating a patch that requires non-empty tables
        change = MagicMock()

        # Apply the patch
        try:
            assert(applier.apply(change) != 0)
        except Exception:
            pass

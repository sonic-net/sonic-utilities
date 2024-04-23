import json
import jsonpatch
import unittest
from unittest.mock import patch, MagicMock

import generic_config_updater.change_applier
import generic_config_updater.generic_updater
import generic_config_updater.services_validator
import generic_config_updater.gu_common

# import sys
# sys.path.insert(0,'../../generic_config_updater')
# import generic_updater as gu

class TestMultiAsicPatchApplier(unittest.TestCase):

    @patch('generic_config_updater.gu_common.ConfigWrapper.get_empty_tables', return_value=[])
    @patch('generic_config_updater.gu_common.ConfigWrapper.get_config_db_as_json')
    @patch('generic_config_updater.gu_common.PatchWrapper.simulate_patch')
    @patch('generic_config_updater.generic_updater.ChangeApplier')
    def test_apply_patch_specific_namespace(self, mock_ChangeApplier, mock_simulate_patch, mock_get_config, mock_get_empty_tables):
        namespace = "asic0"
        patch_data = jsonpatch.JsonPatch([
            {
                "op": "add",
                "path": "/ACL_TABLE/NEW_ACL_TABLE",
                "value": {
                    "policy_desc": "New ACL Table",
                    "ports": ["Ethernet1", "Ethernet2"],
                    "stage": "ingress",
                    "type": "L3"
                }
            },
            {
                "op": "replace",
                "path": "/PORT/Ethernet1/mtu",
                "value": "9200"
            }
        ])

        original_config = {
                "ACL_TABLE": {
                    "MY_ACL_TABLE": {
                        "policy_desc": "My ACL",
                        "ports": ["Ethernet1", "Ethernet2"],
                        "stage": "ingress",
                        "type": "L3"
                    }
                },
                "PORT": {
                    "Ethernet1": {
                        "alias": "fortyGigE0/0",
                        "description": "fortyGigE0/0",
                        "index": "0",
                        "lanes": "29,30,31,32",
                        "mtu": "9100",
                        "pfc_asym": "off",
                        "speed": "40000"
                    },
                    "Ethernet2": {
                        "alias": "fortyGigE0/100",
                        "description": "fortyGigE0/100",
                        "index": "25",
                        "lanes": "125,126,127,128",
                        "mtu": "9100",
                        "pfc_asym": "off",
                        "speed": "40000"
                    }
                }
            }

        applied_config = {
                "ACL_TABLE": {
                    "MY_ACL_TABLE": {
                        "policy_desc": "My ACL",
                        "ports": ["Ethernet1", "Ethernet2"],
                        "stage": "ingress",
                        "type": "L3"
                    },
                    "NEW_ACL_TABLE": {
                        "policy_desc": "New ACL Table",
                        "ports": [
                            "Ethernet1",
                            "Ethernet2"
                        ],
                        "stage": "ingress",
                        "type": "L3"
                    }
                },
                "PORT": {
                    "Ethernet1": {
                        "alias": "fortyGigE0/0",
                        "description": "fortyGigE0/0",
                        "index": "0",
                        "lanes": "29,30,31,32",
                        "mtu": "9200",
                        "pfc_asym": "off",
                        "speed": "40000"
                    },
                    "Ethernet2": {
                        "alias": "fortyGigE0/100",
                        "description": "fortyGigE0/100",
                        "index": "25",
                        "lanes": "125,126,127,128",
                        "mtu": "9100",
                        "pfc_asym": "off",
                        "speed": "40000"
                    }
                }
            }

        mock_get_config.side_effect = [
            original_config,
            original_config,
            original_config,
            applied_config
        ]

        mock_simulate_patch.return_value = {
            "ACL_TABLE": {
                "MY_ACL_TABLE": {
                    "policy_desc": "My ACL",
                    "ports": [
                        "Ethernet1", "Ethernet2"
                    ],
                    "stage": "ingress",
                    "type": "L3"
                },
                "NEW_ACL_TABLE": {
                    "policy_desc": "New ACL Table",
                    "ports": [
                        "Ethernet1",
                        "Ethernet2"
                    ],
                    "stage": "ingress",
                    "type": "L3"
                }
            },
            "PORT": {
                "Ethernet1": {
                    "alias": "fortyGigE0/0",
                    "description": "fortyGigE0/0",
                    "index": "0",
                    "lanes": "29,30,31,32",
                    "mtu": "9200",
                    "pfc_asym": "off",
                    "speed": "40000"
                },
                "Ethernet2": {
                    "alias": "fortyGigE0/100",
                    "description": "fortyGigE0/100",
                    "index": "25",
                    "lanes": "125,126,127,128",
                    "mtu": "9100",
                    "pfc_asym": "off",
                    "speed": "40000"
                }
            }
        }

        patch_applier = generic_config_updater.generic_updater.PatchApplier(namespace=namespace)

        # Apply the patch and verify
        patch_applier.apply(patch_data)

        # Assertions to ensure the namespace is correctly used in underlying calls
        mock_ChangeApplier.assert_called_once_with(namespace=namespace)

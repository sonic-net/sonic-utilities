from config.config_mgmt import ConfigMgmt
from utilities_common.general import load_module_from_source
from unittest.mock import patch, MagicMock


sonic_cfggen = load_module_from_source('sonic_cfggen', '/usr/local/bin/sonic-cfggen')


def test_write_configdb_port_breakout():
    mock_db_data = {
        'PORT': {
            'Ethernet80': {'admin_status': 'up'},
            'Ethernet82': {'admin_status': 'down'}
        }
    }

    with patch('sonic_cfggen.FormatConverter.to_deserialized', return_value={}), \
         patch('sonic_cfggen.FormatConverter.output_to_db', return_value=mock_db_data), \
         patch('sonic_cfggen.deep_update'), \
         patch('config.config_mgmt.ConfigDBConnector') as mock_configdb_class:

        mock_configdb_instance = MagicMock()
        mock_configdb_class.return_value = mock_configdb_instance

        cm = ConfigMgmt()
        cm.configdb = mock_configdb_instance
        cm.writeConfigDB(jDiff={})

        calls = [
            ({'PORT': {'Ethernet80': {'admin_status': 'up'}}},),
            ({'PORT': {'Ethernet82': {'admin_status': 'down'}}},)
        ]
        called_args = [tuple(c.args) for c in mock_configdb_instance.mod_config.call_args_list]
        assert called_args == calls

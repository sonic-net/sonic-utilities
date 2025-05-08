import pytest
from config.config_mgmt import ConfigMgmt
from utilities_common.general import load_module_from_source

sonic_cfggen = load_module_from_source('sonic_cfggen', '/usr/local/bin/sonic-cfggen')

def test_output_to_db_and_mod_config(mocker):
    mock_db_data = {
        'PORT': {
            'Ethernet0': {'admin_status': 'up'},
            'Ethernet4': {'admin_status': 'down'}
        }
    }

    mocker.patch('sonic_cfggen.FormatConverter.output_to_db', return_value=mock_db_data)

    mock_mod_config = mocker.patch.object(ConfigMgmt, 'mod_config')

    cm = ConfigMgmt()
    cm.configdb = mocker.Mock()

    data = {} 
    cm._ConfigMgmt__process_db_diff(data, {})  

    sonic_cfggen.FormatConverter.output_to_db.assert_called_once()

    assert mock_mod_config.call_count == 2
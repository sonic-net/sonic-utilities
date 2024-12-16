import json
import os
import re
from unittest import mock

import pytest
from click.testing import CliRunner
from utilities_common.db import Db
from utilities_common.general import load_module_from_source

import config.main as config

# Load sonic-cfggen from source since /usr/local/bin/sonic-cfggen does not have .py extension.
sonic_cfggen = load_module_from_source('sonic_cfggen', '/usr/local/bin/sonic-cfggen')

# Import config_mgmt.py
config_mgmt_py_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config_mgmt.py')
config_mgmt = load_module_from_source('config_mgmt', config_mgmt_py_path)


# Sample platform.json for Test
BRKOUT_CFG_FILE_JSON = {
    "interfaces": {
        "Ethernet0": {
            "index": "1,1,1,1",
            "lanes": "65,66,67,68",
            "breakout_modes": {
                "1x100G[40G]": ["Eth1"],
                "2x50G": ["Eth1/1", "Eth1/3"],
                "4x25G[10G]": ["Eth1/1", "Eth1/2", "Eth1/3", "Eth1/4"]
            }
        },
        "Ethernet4": {
            "index": "2,2,2,2",
            "lanes": "69,70,71,72",
            "breakout_modes": {
                "1x100G[40G]": ["Eth2"],
                "2x50G": ["Eth2/1", "Eth2/3"],
                "4x25G[10G]": ["Eth2/1", "Eth2/2", "Eth2/3", "Eth2/4"],
                "1x50G(2)+2x25G(2)": ["Eth2/1", "Eth2/3", "Eth2/4"]
            }
        },
        "Ethernet8": {
            "index": "3,3,3,3",
            "lanes": "73,74,75,76",
            "breakout_modes": {
                "1x100G[40G]": ["Eth3"],
                "2x50G": ["Eth3/1", "Eth3/3"],
                "4x25G[10G]": ["Eth3/1", "Eth3/2", "Eth3/3", "Eth3/4"],
                "1x50G(2)+2x25G(2)": ["Eth3/1", "Eth3/3", "Eth3/4"]
            }
        },
        "Ethernet12": {
            "index": "4,4,4,4",
            "lanes": "77,78,79,80",
            "breakout_modes": {
                "1x100G[40G]": ["Eth4"],
                "2x50G": ["Eth4/1", "Eth4/3"],
                "4x25G[10G]": ["Eth4/1", "Eth4/2", "Eth4/3", "Eth4/4"]
            }
        }
    }
}

# Default Parameter
PREFIX = "Ethernet"
SPEED_LANE_MAP = {
    "4x25G[10G]": [1,1,1,1],
    "2x50G": [2,2],
    "1x100G[40G]": [4],
    "1x50G(2)+2x25G(2)": [2,1,1],
    "2x25G(2)+1x50G(2)": [1,1,2]
}
LANE_SPEED = 25000

@pytest.fixture(scope='module')
def breakout_cfg_file():
    '''
    Create a function to create a file as platform.json
    '''
    file = '/tmp/breakout_cfg_file.json'
    print("File is:{}",file)
    with open(file, 'w') as f:
        json.dump(BRKOUT_CFG_FILE_JSON, f, indent=4)
    yield file

    os.system("rm /tmp/breakout_cfg_file.json")
    return

@pytest.fixture(scope='module')
def sonic_db(scope='module'):
    '''
    Read config Db, And Update it with starting config for DPB.
    @return: db
    '''
    db = Db()
    tables = db.cfgdb.get_config()
    # delete all tables
    for table in tables:
        db.cfgdb.delete_table(table)
    # load new config
    write_config_db(db.cfgdb, configDbJson)
    return db

mock_funcs = [None]*4
@pytest.fixture(scope='function')
def mock_func(breakout_cfg_file, sonic_db):
    '''
    Mock functions in config/main.py, then unmocked them after test funtion.
    Note: Always remember to unmock the function if done in a file after
    importing.

    @Param: breakout_cfg_file [PyFixture], Equivalent to platform.json
    @Param: sonic_db [PyFixture], db.cfgdb -> Config DB.
    '''
    # stored mock funcs
    print("We are mocking")
    mock_funcs[0] = config.device_info.get_path_to_port_config_file
    mock_funcs[1] = config.load_ConfigMgmt
    mock_funcs[2] = config.breakout_warnUser_extraTables
    mock_funcs[3] = config.asic_type

    config.asic_type = mock.MagicMock(return_value = "broadcom")
    config.device_info.get_path_to_port_config_file = \
        mock.MagicMock(return_value = breakout_cfg_file)
    config.load_ConfigMgmt = \
        mock.MagicMock(return_value = config_mgmt_dpb(sonic_db.cfgdb))
    config.breakout_warnUser_extraTables = \
        mock.MagicMock(return_value = True)
    yield

    config.device_info.get_path_to_port_config_file = mock_funcs[0]
    config.load_ConfigMgmt = mock_funcs[1]
    config.breakout_warnUser_extraTables = mock_funcs[2]
    config.asic_type = mock_funcs[3]

    return

def write_config_db(cfgdb, config):
    data = dict()
    sonic_cfggen.deep_update(data, sonic_cfggen.FormatConverter.to_deserialized(config))
    cfgdb.mod_config(sonic_cfggen.FormatConverter.output_to_db(data))
    return

def read_config_db(cfgdb):
    data = dict()
    sonic_cfggen.deep_update(data, sonic_cfggen.FormatConverter.db_to_output(cfgdb.get_config()))
    return sonic_cfggen.FormatConverter.to_serialized(data)

def writeJson(d, file):
    with open(file, 'w') as f:
        json.dump(d, f, indent=4)
    return

def config_mgmt_dpb(cfgdb):
    '''
    config_mgmt. ConfigMgmtDPB class instance with mocked functions. Not using
    pytest fixture, because it is used in mocked funcs.
    @param: cfgdb -> configDb.
    @return:
    cmdpb (ConfigMgmtDPB): Class instance of ConfigMgmtDPB with mocked funcs.
    '''
    curConfig = read_config_db(cfgdb)
    # create object
    config_mgmt.CONFIG_DB_JSON_FILE = "/tmp/startConfigDb.json"
    config_mgmt.DEFAULT_CONFIG_DB_JSON_FILE = "/tmp/portBreakOutConfigDb.json"
    # write in temp file
    writeJson(curConfig, config_mgmt.CONFIG_DB_JSON_FILE)
    writeJson(portBreakOutConfigDbJson, config_mgmt.DEFAULT_CONFIG_DB_JSON_FILE)
    cmdpb = config_mgmt.ConfigMgmtDPB(source=config_mgmt.CONFIG_DB_JSON_FILE)
    # mock funcs
    cmdpb.writeConfigDB = mock.MagicMock(return_value=True)
    cmdpb._verifyAsicDB = mock.MagicMock(return_value=True)
    return cmdpb

def _generate_args(portIdx, laneIdx, mode):
        '''
        Generate port to deleted, added and {lanes, speed} setting based on
        current and new mode.

        Parameters:
            portIdx (int): Port Index.
            laneIdx (int): Lane Index.
            mode (str): can be current breakout mode or target breakout mode of Port.

            Example ->
                For generate_args(0, 65, '4x25G', '2x25G(2)+1x50G(2)'):
        Return:
            childPorts, pJson (tuple)[list, dict]
            Example ->
            childPorts: ['Ethernet0', 'Ethernet1', 'Ethernet2', 'Ethernet3']
            pJson:  {
                        'PORT': {
                            'Ethernet0': {'speed': '25000', 'lanes': '65'},
                            'Ethernet1': {'speed': '25000', 'lanes': '66'},
                            'Ethernet2': {'speed': '50000', 'lanes': '67,68'}
                        }
                    }
        '''

        # Generate child Ports
        l = list(SPEED_LANE_MAP[mode])
        l.insert(0, 0)
        id = portIdx
        childPorts = list()

        for i in l[:-1]:
            id = id + i
            portName = portName = "{}{}".format(PREFIX, id)
            childPorts.append(portName)

        # Generate port Json for child ports
        l = SPEED_LANE_MAP[mode]
        pJson = {"PORT": {}}
        li = laneIdx
        pi = 0

        for i in l:
            speed = int(LANE_SPEED)*int(i)
            lanes = [str(int(li)+int(j)) for j in range(i)]; lanes = ','.join(lanes)
            pJson['PORT'][childPorts[pi]] = {"speed": str(speed), "lanes": str(lanes)}
            li = int(li)+int(i); pi = pi + 1

        return childPorts, pJson

def get_child_ports_mock(interface, mode):
    '''
    get_child_ports function. portconfig class instance with mocked functions.

    Parameters:
            interface (str): Interface Name.
            mode (str): can be current breakout mode or target breakout mode of Port.

    Return:
            childPorts, pJson (tuple)[list, dict]
            Example-> Input sample: interface = 'Ethernet0'
                                    mode = "2x25G(2)+1x50G(2)"

            childPorts: ['Ethernet0', 'Ethernet1', 'Ethernet2']
            pJson:  {
                        'PORT': {
                            'Ethernet0': {'speed': '25000', 'lanes': '65'},
                            'Ethernet1': {'speed': '25000', 'lanes': '66'},
                            'Ethernet2': {'speed': '50000', 'lanes': '67,68'}
                        }
                    }
    '''

    interface_portmap = dict()
    if interface in BRKOUT_CFG_FILE_JSON["interfaces"].keys():
        fv = BRKOUT_CFG_FILE_JSON["interfaces"][interface]
        portIdx_reg = re.search("{}(\d+)".format(PREFIX), interface)
        if portIdx_reg is not None:
            portIdx = int(portIdx_reg.group(1))
            laneIdx = fv["lanes"].split(",")[0]
            interface_portmap[interface] = { "portIdx": portIdx, "laneIdx": laneIdx }

            _, pJson  = _generate_args(portIdx, laneIdx, mode)
            return pJson['PORT']
        else:
            return {}
    else:
        return {}

class TestConfigDPB(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"
        return

    @pytest.mark.usefixtures('mock_func')
    def test_get_breakout_options(self):
        '''
        Test mode options, which are generated from platform.json,
        when TAB is pressed while DPB command.
        Such as: sudo config interface breakout Ethernet4 2x<TAB><TAB>
        '''

        ctx = None
        args = ['config', 'interface', 'breakout', 'Ethernet4']
        ##############
        incomplete = '1'
        output = config._get_breakout_options(ctx, args, incomplete)
        assert output == ['1x100G[40G]', '4x25G[10G]', '1x50G(2)+2x25G(2)']
        ##############
        incomplete = '2'
        output = config._get_breakout_options(ctx, args, incomplete)
        assert output == ['2x50G', '4x25G[10G]', '1x50G(2)+2x25G(2)']
        ##############
        incomplete = '1x'
        output = config._get_breakout_options(ctx, args, incomplete)
        assert output == ['1x100G[40G]', '1x50G(2)+2x25G(2)']
        ##############
        incomplete = '2x'
        output = config._get_breakout_options(ctx, args, incomplete)
        assert output == ['2x50G', '1x50G(2)+2x25G(2)']
        ##############
        incomplete = '4x'
        output = config._get_breakout_options(ctx, args, incomplete)
        assert output == ['4x25G[10G]']
        ##############
        #Negattive case, Wrong Interface
        args = ['config', 'interface', 'breakout', 'Etherne']
        output = config._get_breakout_options(ctx, args, incomplete)
        #TODO: Uncomment it after Dev Fix, Right now Python BT for this.
        #assert output == []
        return

    def test_config_breakout_extra_table_warning(self, breakout_cfg_file, sonic_db):
        '''
        Test breakout_extra_table_warning for breakout port.
        Warning and ask User confirmation from user for the tablesWithOutYang.

        @Param: breakout_cfg_file [PyFixture], Equivalent to platform.json
        @Param: sonic_db [PyFixture], db.cfgdb -> Config DB.
        '''

        db = sonic_db
        # add unknown table in config
        unknown =  {
            "UNKNOWN_TABLE": {
                "Ethernet0": {
                    "pkey": "pvalue"
                }
            }
        }
        write_config_db(db.cfgdb, unknown)
        print(db.cfgdb.get_table('UNKNOWN_TABLE'))

        # Input Data
        interface = 'Ethernet0'
        curMode = '4x25G[10G]'
        newMode = '2x50G'

        # Mock functions except breakout_warnUser_extraTables
        mock_funcs[0] = config.device_info.get_path_to_port_config_file
        mock_funcs[1] = config.load_ConfigMgmt
        config.device_info.get_path_to_port_config_file = \
            mock.MagicMock(return_value = breakout_cfg_file)
        config.load_ConfigMgmt = \
            mock.MagicMock(return_value = config_mgmt_dpb(db.cfgdb))
        config.get_child_ports = mock.MagicMock(
            side_effect = [get_child_ports_mock(interface, curMode), get_child_ports_mock(interface, newMode)])

        runner = CliRunner()
        obj = {'config_db':db.cfgdb}

        result = runner.invoke(config.config.commands["interface"].\
            commands["breakout"], ['{}'.format(interface), '{}'.format(newMode), '-v', '-y'], obj=obj)

        print(result.exit_code, result.output)
        assert result.exit_code == 1
        assert 'Below Config can not be verified' in result.output
        assert 'UNKNOWN_TABLE' in result.output
        assert 'Do you wish to Continue?' in result.output

        brk_cfg_table = db.cfgdb.get_table('BREAKOUT_CFG')
        assert brk_cfg_table["Ethernet0"]["brkout_mode"] == '{}'.format(curMode)

        # remove unknown table in config
        unknown =  {
            "UNKNOWN_TABLE": None
        }
        write_config_db(db.cfgdb, unknown)
        assert db.cfgdb.get_table('UNKNOWN_TABLE') == {}
        # revert mocking
        config.device_info.get_path_to_port_config_file = mock_funcs[0]
        config.load_ConfigMgmt = mock_funcs[1]

        return

    @pytest.mark.usefixtures('mock_func')
    def test_config_breakout_verbose(self, sonic_db):
        '''
        Test verbose option for breakout port. Verbose option must be passed
        to ConfigMgmtDPB Class.
        @Param: sonic_db [PyFixture], db.cfgdb -> Config DB.
        '''

        db = sonic_db
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}

        # Input Data
        interface = 'Ethernet0'
        curMode = '4x25G[10G]'
        newMode = '2x50G'

        print("Mocked Child ports data-> {}".format([get_child_ports_mock(interface, curMode), get_child_ports_mock(interface, newMode)]))

        config.get_child_ports = mock.MagicMock(
            side_effect = [get_child_ports_mock(interface, curMode), get_child_ports_mock(interface, newMode)])

        result = runner.invoke(config.config.commands["interface"].\
            commands["breakout"], ['{}'.format(interface), '{}'.format(newMode), '-v', '-y'], obj=obj)

        print(result.exit_code, result.output)
        assert result.exit_code == 1
        assert 'Dependencies Exist.' in result.output

        # verbose must be set while creating instance of ConfigMgmt class
        calls = [mock.call(True)]
        assert config.load_ConfigMgmt.call_count == 1
        config.load_ConfigMgmt.assert_has_calls(calls, any_order=False)

        return

    @pytest.mark.usefixtures('mock_func')
    def test_config_breakout_negative_cases(self, sonic_db):
        '''
        Test negative case of breakout port. Such as:
        Wrong Interface, wrong option and Wrong breakout Mode.
        @Param: sonic_db [PyFixture], db.cfgdb -> Config DB.
        '''

        db = sonic_db
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}

        # Input Data
        interface = 'Ethern'
        curMode = '4x25G[10G]'
        newMode = '2x50G'


        # Wrong interface name
        result = runner.invoke(config.config.commands["interface"].\
            commands["breakout"], ['{}'.format(interface), '{}'.format(newMode), '-v', '-y'], obj=obj)

        print(result.exit_code, result.output)
        assert result.exit_code == 1
        assert "Ethern interface is NOT present" in result.output

        # Input Data
        interface = 'Ethernet0'
        curMode = '4x25G[10G]'
        newMode = '1x50G'

        # Wrong mode
        result = runner.invoke(config.config.commands["interface"].\
            commands["breakout"], ['Ethernet0', '1x50G', '-v', '-y'], obj=obj)

        print(result.exit_code, result.output)
        assert result.exit_code == 1
        assert "Target mode 1x50G is not available for the port Ethernet0" in result.output

        brk_cfg_table = db.cfgdb.get_table('BREAKOUT_CFG')
        assert brk_cfg_table["Ethernet0"]["brkout_mode"] == '4x25G[10G]'

        # Input Data
        interface = 'Ethernet0'
        curMode = '4x25G[10G]'
        newMode = '2x50G'

        # Wrong option
        result = runner.invoke(config.config.commands["interface"].\
            commands["breakout"], ['Ethernet0', '2x50G', '-v', '-p' '-y'], obj=obj)

        print(result.exit_code, result.output)
        assert result.exit_code == 2
        assert "no such option: -p" in result.output

        brk_cfg_table = db.cfgdb.get_table('BREAKOUT_CFG')
        assert brk_cfg_table["Ethernet0"]["brkout_mode"] == '4x25G[10G]'

        return

    @pytest.mark.usefixtures('mock_func')
    @pytest.mark.skip(reason="not stable")
    def test_config_breakout_various_modes(self, sonic_db):
        '''
        Test different combination of breakout port.
        @Param: sonic_db [PyFixture], db.cfgdb -> Config DB.

        How this function works:
        mock_func creates a mock for load_ConfigMgmt, which inturn create one
        mocked object of ConfigMgmtDPB, each time when config breakout command
        is executed, same object of ConfigMgmtDPB will be returned.
        The object will also have data tree loaded and updated with each breakout
        command, so we can run breakout command in continution assuming
        config changes are happening to DB.

        writeConfigDB in ConfigMgmtDPB writes in new object of DB, so those
        changes will be lost, i.e. not reflected in db.cfgdb. So we mock
        writeConfigDB() or not, does not matter.

        config/main.py part will use db (sonic_db) while configDb update,
        so brk_cfg_table updates will be seen in db.
        '''

        db = sonic_db
        runner = CliRunner()
        obj = {'config_db':db.cfgdb}

        '''
            INNER FUNCTIONS
        '''
        # Ethernet8: start from 4x25G-->2x50G with -f -l
        def config_dpb_port8_4x25G_2x50G_f_l():

            # Input Data
            interface = 'Ethernet8'
            curMode = '4x25G[10G]'
            newMode = '2x50G'

            print("Mocked Child ports data-> {}".format([get_child_ports_mock(interface, curMode), get_child_ports_mock(interface, newMode)]))

            config.get_child_ports = mock.MagicMock(
                side_effect = [get_child_ports_mock(interface, curMode), get_child_ports_mock(interface, newMode)])

            result = runner.invoke(config.config.commands["interface"].\
                commands["breakout"], ['{}'.format(interface), '{}'.format(newMode), '-v', '-f',\
                 '-l', '-y'], obj=obj)

            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert 'Breakout process got successfully completed.' in result.output

            brk_cfg_table = db.cfgdb.get_table('BREAKOUT_CFG')
            assert brk_cfg_table["Ethernet8"]["brkout_mode"] == '{}'.format(newMode)
            return

        # Ethernet8: move from 2x50G-->1x100G without force, list deps
        def config_dpb_port8_2x50G_1x100G():

            # Input Data
            interface = 'Ethernet8'
            curMode = '2x50G'
            newMode = '1x100G[40G]'

            print("Mocked Child ports data-> {}".format([get_child_ports_mock(interface, curMode), get_child_ports_mock(interface, newMode)]))

            config.get_child_ports = mock.MagicMock(
                side_effect = [get_child_ports_mock(interface, curMode), get_child_ports_mock(interface, newMode)])

            result = runner.invoke(config.config.commands["interface"].\
                commands["breakout"], ['{}'.format(interface), '{}'.format(newMode), '-v','-y'], obj=obj)

            print(result.exit_code, result.output)
            assert result.exit_code == 1
            assert 'Dependencies Exist.' in result.output
            assert 'Printing dependencies' in result.output
            assert 'NO-NSW-PACL-V4' in result.output

            brk_cfg_table = db.cfgdb.get_table('BREAKOUT_CFG')
            assert brk_cfg_table["Ethernet8"]["brkout_mode"] == '{}'.format(curMode)
            return

        # Ethernet8: move from 2x50G-->1x100G with force, where deps exists
        def config_dpb_port8_2x50G_1x100G_f():

            # Input Data
            interface = 'Ethernet8'
            curMode = '2x50G'
            newMode = '1x100G[40G]'

            print("Mocked Child ports data-> {}".format([get_child_ports_mock(interface, curMode), get_child_ports_mock(interface, newMode)]))

            config.get_child_ports = mock.MagicMock(
                side_effect = [get_child_ports_mock(interface, curMode), get_child_ports_mock(interface, newMode)])

            result = runner.invoke(config.config.commands["interface"].\
                commands["breakout"], ['{}'.format(interface), '{}'.format(newMode), '-v', '-f',\
                 '-y'], obj=obj)

            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert 'Breakout process got successfully completed.' in result.output

            brk_cfg_table = db.cfgdb.get_table('BREAKOUT_CFG')
            assert brk_cfg_table["Ethernet8"]["brkout_mode"] == '{}'.format(newMode)
            return

        # Ethernet8: move from 1x100G-->4x25G without force, no deps
        def config_dpb_port8_1x100G_4x25G():

            # Input Data
            interface = 'Ethernet8'
            curMode = '1x100G[40G]'
            newMode = '4x25G[10G]'

            print("Mocked Child ports data-> {}".format([get_child_ports_mock(interface, curMode), get_child_ports_mock(interface, newMode)]))

            config.get_child_ports = mock.MagicMock(
                side_effect = [get_child_ports_mock(interface, curMode), get_child_ports_mock(interface, newMode)])


            result = runner.invoke(config.config.commands["interface"].\
                commands["breakout"], ['{}'.format(interface), '{}'.format(newMode), '-v',\
                 '-y'], obj=obj)

            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert 'Breakout process got successfully completed.' in result.output

            brk_cfg_table = db.cfgdb.get_table('BREAKOUT_CFG')
            assert brk_cfg_table["Ethernet8"]["brkout_mode"] == '{}'.format(newMode)
            return

        # Ethernet8: move from 4x25G-->1x100G with force, no deps
        def config_dpb_port8_4x25G_1x100G_f():

            # Input Data
            interface = 'Ethernet8'
            curMode = '4x25G[10G]'
            newMode = '1x100G[40G]'

            print("Mocked Child ports data-> {}".format([get_child_ports_mock(interface, curMode), get_child_ports_mock(interface, newMode)]))

            config.get_child_ports = mock.MagicMock(
                side_effect = [get_child_ports_mock(interface, curMode), get_child_ports_mock(interface, newMode)])

            result = runner.invoke(config.config.commands["interface"].\
                commands["breakout"], ['{}'.format(interface), '{}'.format(newMode), '-v', '-f',\
                 '-y'], obj=obj)

            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert 'Breakout process got successfully completed.' in result.output

            brk_cfg_table = db.cfgdb.get_table('BREAKOUT_CFG')
            assert brk_cfg_table["Ethernet8"]["brkout_mode"] == '{}'.format(newMode)
            return

        # Ethernet8: move from 1x100G-->1x50G(2)+2x25G(2) with -f -l,
        def config_dpb_port8_1x100G_1x50G_2x25G_f_l():

            # Input Data
            interface = 'Ethernet8'
            curMode = '1x100G[40G]'
            newMode = '1x50G(2)+2x25G(2)'

            print("Mocked Child ports data-> {}".format([get_child_ports_mock(interface, curMode), get_child_ports_mock(interface, newMode)]))

            config.get_child_ports = mock.MagicMock(
                side_effect = [get_child_ports_mock(interface, curMode), get_child_ports_mock(interface, newMode)])

            result = runner.invoke(config.config.commands["interface"].\
                commands["breakout"], ['{}'.format(interface), '{}'.format(newMode), '-v',\
                '-f', '-l', '-y'], obj=obj)

            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert 'Breakout process got successfully completed.' in result.output

            brk_cfg_table = db.cfgdb.get_table('BREAKOUT_CFG')
            assert brk_cfg_table["Ethernet8"]["brkout_mode"] == '{}'.format(newMode)
            return

        # Ethernet4: breakout from 4x25G to 2x50G with -f -l
        def config_dpb_port4_4x25G_2x50G_f_l():

            # Input Data
            interface = 'Ethernet4'
            curMode = '4x25G[10G]'
            newMode = '2x50G'

            print("Mocked Child ports data-> {}".format([get_child_ports_mock(interface, curMode), get_child_ports_mock(interface, newMode)]))

            config.get_child_ports = mock.MagicMock(
                side_effect = [get_child_ports_mock(interface, curMode), get_child_ports_mock(interface, newMode)])

            result = runner.invoke(config.config.commands["interface"].\
                commands["breakout"], ['{}'.format(interface), '{}'.format(newMode), '-v',\
                '-f', '-l', '-y'], obj=obj)

            print(result.exit_code, result.output)
            assert result.exit_code == 0
            assert 'Breakout process got successfully completed.' in result.output

            brk_cfg_table = db.cfgdb.get_table('BREAKOUT_CFG')
            assert brk_cfg_table["Ethernet4"]["brkout_mode"] == '{}'.format(newMode)
            assert brk_cfg_table["Ethernet8"]["brkout_mode"] == '1x50G(2)+2x25G(2)'
            return
        '''
            END OF INNER FUNCTIONS
        '''

        # Ethernet8: start from 4x25G-->2x50G with -f -l
        config_dpb_port8_4x25G_2x50G_f_l()

        # Ethernet8: move from 2x50G-->1x100G without force, list deps
        config_dpb_port8_2x50G_1x100G()

        # Ethernet8: move from 2x50G-->1x100G with force, where deps exists
        config_dpb_port8_2x50G_1x100G_f()

        # Ethernet8: move from 1x100G-->4x25G without force, no deps
        config_dpb_port8_1x100G_4x25G()

        # Ethernet8: move from 4x25G-->1x100G with force, no deps
        config_dpb_port8_4x25G_1x100G_f()

        # Ethernet8: move from 1x100G-->1x50G(2)+2x25G(2) with -f -l,
        config_dpb_port8_1x100G_1x50G_2x25G_f_l()

        # Ethernet4: breakout from 4x25G to 2x50G with -f -l
        config_dpb_port4_4x25G_2x50G_f_l()

        return

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.system("rm /tmp/startConfigDb.json")
        os.system("rm /tmp/portBreakOutConfigDb.json")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        return

###########GLOBAL Configs#####################################
'''
Below Config will used as starting config for Dynamic Port Breakout
'''
configDbJson =  {
    "BREAKOUT_CFG": {
        "Ethernet0": {
            "brkout_mode": "4x25G[10G]"
        },
        "Ethernet4": {
            "brkout_mode": "4x25G[10G]"
        },
        "Ethernet8": {
            "brkout_mode": "4x25G[10G]"
        },
    },
    "ACL_TABLE": {
        "NO-NSW-PACL-TEST": {
            "policy_desc": "NO-NSW-PACL-TEST",
            "type": "L3",
            "stage": "INGRESS",
            "ports": [
                "Ethernet9",
                "Ethernet11",
                ]
        },
        "NO-NSW-PACL-V4": {
            "policy_desc": "NO-NSW-PACL-V4",
            "type": "L3",
            "stage": "INGRESS",
            "ports": [
                "Ethernet0",
                "Ethernet4",
                "Ethernet8",
                "Ethernet10"
                ]
        }
    },
    "VLAN": {
        "Vlan100": {
            "admin_status": "up",
            "description": "server_vlan",
            "dhcp_servers": [
                "10.186.72.116"
            ]
        },
    },
    "VLAN_MEMBER": {
        "Vlan100|Ethernet0": {
            "tagging_mode": "untagged"
        },
        "Vlan100|Ethernet2": {
            "tagging_mode": "untagged"
        },
        "Vlan100|Ethernet8": {
            "tagging_mode": "untagged"
        },
        "Vlan100|Ethernet11": {
            "tagging_mode": "untagged"
        },
    },
    "INTERFACE": {
        "Ethernet10": {},
        "Ethernet10|2a04:0000:40:a709::1/126": {
            "scope": "global",
            "family": "IPv6"
        }
    },
    "PORT": {
        "Ethernet0": {
            "alias": "Eth1/1",
            "lanes": "65",
            "description": "",
            "speed": "25000",
            "admin_status": "up"
        },
        "Ethernet1": {
            "alias": "Eth1/2",
            "lanes": "66",
            "description": "",
            "speed": "25000",
            "admin_status": "up"
        },
        "Ethernet2": {
            "alias": "Eth1/3",
            "lanes": "67",
            "description": "",
            "speed": "25000",
            "admin_status": "up"
        },
        "Ethernet3": {
            "alias": "Eth1/4",
            "lanes": "68",
            "description": "",
            "speed": "25000",
            "admin_status": "up"
        },
        "Ethernet4": {
            "alias": "Eth2/1",
            "lanes": "69",
            "description": "",
            "speed": "25000",
            "admin_status": "up"
        },
        "Ethernet5": {
            "alias": "Eth2/2",
            "lanes": "70",
            "description": "",
            "speed": "25000",
            "admin_status": "up"
        },
        "Ethernet6": {
            "alias": "Eth2/3",
            "lanes": "71",
            "description": "",
            "speed": "25000",
            "admin_status": "up"
        },
        "Ethernet7": {
            "alias": "Eth2/4",
            "lanes": "72",
            "description": "",
            "speed": "25000",
            "admin_status": "up"
        },
        "Ethernet8": {
            "alias": "Eth3/1",
            "lanes": "73",
            "description": "",
            "speed": "25000",
            "admin_status": "up"
        },
        "Ethernet9": {
            "alias": "Eth3/2",
            "lanes": "74",
            "description": "",
            "speed": "25000",
            "admin_status": "up"
        },
        "Ethernet10": {
            "alias": "Eth3/3",
            "lanes": "75",
            "description": "",
            "speed": "25000",
            "admin_status": "up"
        },
        "Ethernet11": {
            "alias": "Eth3/4",
            "lanes": "76",
            "description": "",
            "speed": "25000",
            "admin_status": "up"
        }
    }
}

portBreakOutConfigDbJson = {
    "ACL_TABLE": {
        "NO-NSW-PACL-TEST": {
            "ports": [
                "Ethernet9",
                "Ethernet11",
                ]
        },
        "NO-NSW-PACL-V4": {
            "policy_desc": "NO-NSW-PACL-V4",
            "ports": [
                "Ethernet0",
                "Ethernet4",
                "Ethernet8",
                "Ethernet10"
                ]
        }
    },
    "VLAN": {
        "Vlan100": {
            "admin_status": "up",
            "description": "server_vlan",
            "dhcp_servers": [
                "10.186.72.116"
            ]
        }
    },
    "VLAN_MEMBER": {
        "Vlan100|Ethernet8": {
            "tagging_mode": "untagged"
        },
        "Vlan100|Ethernet11": {
            "tagging_mode": "untagged"
       }
    },
    "INTERFACE": {
        "Ethernet11": {},
        "Ethernet11|2a04:1111:40:a709::1/126": {
            "scope": "global",
            "family": "IPv6"
        }
    }
}

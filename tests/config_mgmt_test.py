import os
import sys
from json import dump
from copy import deepcopy
from unittest import mock, TestCase

import pytest
from utilities_common.general import load_module_from_source

# Import file under test i.e., config_mgmt.py
config_mgmt_py_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config_mgmt.py')
config_mgmt = load_module_from_source('config_mgmt', config_mgmt_py_path)

model = "module test_name {namespace urn:test_urn; prefix test_prefix;}"

class TestConfigMgmt(TestCase):
    '''
        Test Class for config_mgmt.py
    '''

    def setUp(self):
        config_mgmt.CONFIG_DB_JSON_FILE = "startConfigDb.json"
        config_mgmt.DEFAULT_CONFIG_DB_JSON_FILE = "portBreakOutConfigDb.json"
        return

    def test_config_get_module_check(self):
        curConfig = deepcopy(configDbJson)
        self.writeJson(curConfig, config_mgmt.CONFIG_DB_JSON_FILE)
        cm = config_mgmt.ConfigMgmt(source=config_mgmt.CONFIG_DB_JSON_FILE)
        assert cm.get_module_name(model) == "test_name"
        return

    def test_config_validation(self):
        curConfig = deepcopy(configDbJson)
        self.writeJson(curConfig, config_mgmt.CONFIG_DB_JSON_FILE)
        cm = config_mgmt.ConfigMgmt(source=config_mgmt.CONFIG_DB_JSON_FILE)
        assert cm.validateConfigData() == True
        return

    def test_table_without_yang(self):
        curConfig = deepcopy(configDbJson)
        unknown = {"unknown_table": {"ukey": "uvalue"}}
        self.updateConfig(curConfig, unknown)
        self.writeJson(curConfig, config_mgmt.CONFIG_DB_JSON_FILE)
        cm = config_mgmt.ConfigMgmt(source=config_mgmt.CONFIG_DB_JSON_FILE)
        assert "unknown_table" in cm.tablesWithOutYang()
        return

    def test_search_keys(self):
        curConfig = deepcopy(configDbJson)
        self.writeJson(curConfig, config_mgmt.CONFIG_DB_JSON_FILE)
        cmdpb = config_mgmt.ConfigMgmtDPB(source=config_mgmt.CONFIG_DB_JSON_FILE)
        out = cmdpb.configWithKeys(portBreakOutConfigDbJson,
                                   ["Ethernet8", "Ethernet9"])
        assert "VLAN" not in out
        assert "INTERFACE" not in out
        for k in out['ACL_TABLE']:
            # only ports must be chosen
            len(out['ACL_TABLE'][k]) == 1
        out = cmdpb.configWithKeys(portBreakOutConfigDbJson,
                                   ["Ethernet10", "Ethernet11"])
        assert "INTERFACE" in out
        for k in out['ACL_TABLE']:
            # only ports must be chosen
            len(out['ACL_TABLE'][k]) == 1
        return

    def test_upper_case_mac_fix(self):
        '''
        Issue:
        https://github.com/Azure/sonic-buildimage/issues/9478

        LibYang converts ietf yang types to lower case internally,which
        creates false config diff for us while DPB.
        This tests is to verify the fix done in config_mgmt.py to resolve this
        issue.

        Example:
        For DEVICE_METADATA['localhost']['mac'] type is yang:mac-address.
        Libyang converts from 'XX:XX:XX:E4:B3:DD' -> 'xx:xx:xx:e4:b3:dd'
        '''
        curConfig = deepcopy(configDbJson)
        # Keep only PORT part to skip dependencies.
        curConfig = {'PORT': curConfig['PORT']}
        # add DEVICE_METADATA Config
        curConfig['DEVICE_METADATA'] = {
            "localhost": {
                "bgp_asn": "65100",
                "default_bgp_status": "up",
                "default_pfcwd_status": "disable",
                "docker_routing_config_mode": "split",
                "hostname": "sonic",
                "hwsku": "Seastone-DX010",
                "mac": "00:11:22:BB:CC:DD",
                "platform": "x86_64-cel_seastone-r0",
                "type": "LeafRouter"
            }
        }
        cmdpb = self.config_mgmt_dpb(curConfig)
        # create ARGS
        dPorts, pJson = self.generate_args(portIdx=0, laneIdx=65, \
            curMode='4x25G', newMode='2x50G')

        # use side effect to mock _createConfigToLoad but with call to same
        # function
        cmdpb._createConfigToLoad = mock.MagicMock(side_effect=cmdpb._createConfigToLoad)

        # Try to breakout and see if writeConfigDB is called thrice
        deps, ret = cmdpb.breakOutPort(delPorts=dPorts, portJson=pJson, \
            force=True, loadDefConfig=False)

        '''
        assert call to _createConfigToLoad has
        DEVICE_METADATA': {'localhost': {'mac': ['XX:XX:XX:E4:B3:DD',
        'xx:xx:xx:e4:b3:dd']}} in diff
        '''
        (args, kwargs) = cmdpb._createConfigToLoad.call_args_list[0]
        print(args)
        # in case of tuple get first arg, which is diff
        if type(args) == tuple:
            args = args[0]
        assert args['DEVICE_METADATA']['localhost']['mac'] == \
            ['00:11:22:BB:CC:DD', '00:11:22:bb:cc:dd']

        # verify correct function call to writeConfigDB
        assert cmdpb.writeConfigDB.call_count == 3
        print(cmdpb.writeConfigDB.call_args_list[0])
        # args is populated if call is done as writeConfigDB(a, b), kwargs is
        # populated if call is done as writeConfigDB(A=a, B=b)
        (args, kwargs) = cmdpb.writeConfigDB.call_args_list[0]
        print(args)
        # in case of tuple also, we should have only one element writeConfigDB
        if type(args) == tuple:
            args = args[0]
        # Make sure no DEVICE_METADATA in the args to func
        assert "DEVICE_METADATA" not in args

        return

    @pytest.mark.skip(reason="not stable")
    def test_break_out(self):
        # prepare default config
        self.writeJson(portBreakOutConfigDbJson,
                       config_mgmt.DEFAULT_CONFIG_DB_JSON_FILE)
        # prepare config dj json to start with
        curConfig = deepcopy(configDbJson)
        # Ethernet8: start from 4x25G-->2x50G with -f -l
        self.dpb_port8_4x25G_2x50G_f_l(curConfig)
        # Ethernet8: move from 2x50G-->1x100G without force, list deps
        self.dpb_port8_2x50G_1x100G(curConfig)
        # Ethernet8: move from 2x50G-->1x100G with force, where deps exists
        self.dpb_port8_2x50G_1x100G_f(curConfig)
        # Ethernet8: move from 1x100G-->4x25G without force, no deps
        self.dpb_port8_1x100G_4x25G(curConfig)
        # Ethernet8: move from 4x25G-->1x100G with force, no deps
        self.dpb_port8_4x25G_1x100G_f(curConfig)
        # Ethernet8: move from 1x100G-->1x50G(2)+2x25G(2) with -f -l,
        self.dpb_port8_1x100G_1x50G_2x25G_f_l(curConfig)
        # Ethernet4: breakout from 4x25G to 2x50G with -f -l
        self.dpb_port4_4x25G_2x50G_f_l(curConfig)
        return

    @pytest.mark.skip(reason="not stable")
    def test_shutdownIntf_call(self):
        '''
        Verify that _shutdownIntf() is called with deleted ports while calling
        breakOutPort()
        '''
        curConfig = deepcopy(configDbJson)
        cmdpb = self.config_mgmt_dpb(curConfig)

        # create ARGS
        dPorts, pJson = self.generate_args(portIdx=8, laneIdx=73, \
            curMode='1x50G(2)+2x25G(2)', newMode='2x50G')

        # Try to breakout and see if _shutdownIntf is called
        deps, ret = cmdpb.breakOutPort(delPorts=dPorts, portJson=pJson, \
            force=True, loadDefConfig=False)

        # verify correct function call to writeConfigDB after _shutdownIntf()
        assert cmdpb.writeConfigDB.call_count == 3
        print(cmdpb.writeConfigDB.call_args_list[0])
        (args, kwargs) = cmdpb.writeConfigDB.call_args_list[0]
        print(args)

        # in case of tuple also, we should have only one element
        if type(args) == tuple:
            args = args[0]
        assert "PORT" in args

        # {"admin_status": "down"} should be set for Ethernet8
        # The admin_status of Ethernet8 is 'up'.
        # Only need to shutdown Ethernet8
        assert len(args["PORT"]) == 1
        # each port should have {"admin_status": "down"}
        for port in args["PORT"].keys():
            assert args["PORT"][port]['admin_status'] == 'down'

        return

    def tearDown(self):
        try:
            os.remove(config_mgmt.CONFIG_DB_JSON_FILE)
            os.remove(config_mgmt.DEFAULT_CONFIG_DB_JSON_FILE)
        except Exception as e:
            pass
        return

    ########### HELPER FUNCS #####################################
    def writeJson(self, d, file):
        with open(file, 'w') as f:
            dump(d, f, indent=4)
        return

    def config_mgmt_dpb(self, curConfig):
        '''
        config_mgmt.ConfigMgmtDPB class instance with mocked functions. Not using
        pytest fixture, because it is used in non test funcs.

        Parameter:
            curConfig (dict): Config to start with.

        Return:
            cmdpb (ConfigMgmtDPB): Class instance of ConfigMgmtDPB.
        '''
        # create object
        self.writeJson(curConfig, config_mgmt.CONFIG_DB_JSON_FILE)
        cmdpb = config_mgmt.ConfigMgmtDPB(source=config_mgmt.CONFIG_DB_JSON_FILE)
        # mock funcs
        cmdpb.writeConfigDB = mock.MagicMock(return_value=True)
        cmdpb._verifyAsicDB = mock.MagicMock(return_value=True)
        cmdpb._verifyPortShutdown = mock.MagicMock(return_value=True)
        from .mock_tables import dbconnector
        return cmdpb

    def generate_args(self, portIdx, laneIdx, curMode, newMode):
        '''
        Generate port to deleted, added and {lanes, speed} setting based on
        current and new mode.
        Example:
        For generate_args(8, 73, '4x25G', '2x50G'):
        output:
        (
        ['Ethernet8', 'Ethernet9', 'Ethernet10', 'Ethernet11'],
        ['Ethernet8', 'Ethernet10'],
        {'Ethernet8': {'lanes': '73,74', 'speed': '50000'},
         'Ethernet10': {'lanes': '75,76', 'speed': '50000'}})

        Parameters:
            portIdx (int): Port Index.
            laneIdx (int): Lane Index.
            curMode (str): current breakout mode of Port.
            newMode (str): new breakout mode of Port.

        Return:
            dPorts, pJson (tuple)[list, dict]
        '''
        # default params
        pre = "Ethernet"
        laneMap = {"4x25G": [1, 1, 1, 1], "2x50G": [2, 2], "1x100G": [4],
                   "1x50G(2)+2x25G(2)": [2, 1, 1], "2x25G(2)+1x50G(2)": [1, 1, 2]}
        laneSpeed = 25000
        # generate dPorts
        l = list(laneMap[curMode])
        l.insert(0, 0)
        id = portIdx
        dPorts = list()
        for i in l[:-1]:
            id = id + i
            portName = portName = "{}{}".format(pre, id)
            dPorts.append(portName)
        # generate aPorts
        l = list(laneMap[newMode])
        l.insert(0, 0)
        id = portIdx
        aPorts = list()
        for i in l[:-1]:
            id = id + i
            portName = portName = "{}{}".format(pre, id)
            aPorts.append(portName)
        # generate pJson
        l = laneMap[newMode]
        pJson = {"PORT": {}}
        li = laneIdx
        pi = 0
        for i in l:
            speed = laneSpeed*i
            lanes = [str(li+j) for j in range(i)]
            lanes = ','.join(lanes)
            pJson['PORT'][aPorts[pi]] = {"speed": str(speed), "lanes": str(lanes)}
            li = li+i
            pi = pi + 1
        return dPorts, pJson

    def updateConfig(self, conf, uconf):
        '''
        update the config to emulate continous breakingout a single port.

        Parameters:
            conf (dict): current config in config DB.
            uconf (dict): config Diff to be pushed in config DB.

        Return:
            void
            conf will be updated with uconf, i.e. config diff.
        '''
        try:
            for it in list(uconf.keys()):
                # if conf has the key
                if conf.get(it):
                    # if marked for deletion
                    if uconf[it] == None:
                        del conf[it]
                    else:
                        if isinstance(conf[it], list) and isinstance(uconf[it], list):
                            conf[it] = list(uconf[it])
                            '''
                                configDb stores []->[""], i.e. empty list as
                                list of empty string. So we need to replicate
                                same behaviour here.
                            '''
                            if len(conf[it]) == 0:
                                conf[it] = [""]
                        elif isinstance(conf[it], dict) and isinstance(uconf[it], dict):
                            self.updateConfig(conf[it], uconf[it])
                        else:
                            conf[it] = uconf[it]
                    del uconf[it]
            # update new keys in conf
            conf.update(uconf)
        except Exception as e:
            print("update Config failed")
            print(e)
            raise e
        return

    def checkResult(self, cmdpb, delConfig, addConfig):
        '''
        Usual result check in many test is: Make sure delConfig and addConfig is
        pushed in order to configDb

        Parameters:
            cmdpb (ConfigMgmtDPB): Class instance of ConfigMgmtDPB.
            delConfig (dict): config Diff to be pushed in config DB while deletion
                of ports.
            addConfig (dict): config Diff to be pushed in config DB while addition
                of ports.

        Return:
            void
        '''
        calls = [mock.call(delConfig), mock.call(addConfig)]
        assert cmdpb.writeConfigDB.call_count == 3
        cmdpb.writeConfigDB.assert_has_calls(calls, any_order=False)
        return

    def postUpdateConfig(self, curConfig, delConfig, addConfig):
        '''
        After breakout, update the config to emulate continous breakingout a
        single port.

        Parameters:
            curConfig (dict): current Config in config DB.
            delConfig (dict): config Diff to be pushed in config DB while deletion
                of ports.
            addConfig (dict): config Diff to be pushed in config DB while addition
                of ports.

        Return:
            void
            curConfig will be updated with delConfig and addConfig.
        '''
        # update the curConfig with change
        self.updateConfig(curConfig, delConfig)
        self.updateConfig(curConfig, addConfig)
        return

    def dpb_port8_1x100G_1x50G_2x25G_f_l(self, curConfig):
        '''
        Breakout Port 8 1x100G->1x50G_2x25G with -f -l

        Parameters:
            curConfig (dict): current Config in config DB.

        Return:
            void
            assert for success and failure.
        '''
        cmdpb = self.config_mgmt_dpb(curConfig)
        # create ARGS
        dPorts, pJson = self.generate_args(portIdx=8, laneIdx=73,
                                           curMode='1x100G', newMode='1x50G(2)+2x25G(2)')
        deps, ret = cmdpb.breakOutPort(delPorts=dPorts, portJson=pJson,
                                       force=True, loadDefConfig=True)
        # Expected Result delConfig and addConfig is pushed in order
        delConfig = {
            'PORT': {
                'Ethernet8': None
            }
        }
        addConfig = {
            'ACL_TABLE': {
                'NO-NSW-PACL-V4': {
                    'ports': ['Ethernet0', 'Ethernet4', 'Ethernet8', 'Ethernet10']
                },
                'NO-NSW-PACL-TEST': {
                    'ports': ['Ethernet11']
                }
            },
            'INTERFACE': {
                'Ethernet11|2a04:1111:40:a709::1/126': {
                    'scope': 'global',
                    'family': 'IPv6'
                },
                'Ethernet11': {}
            },
            'VLAN_MEMBER': {
                'Vlan100|Ethernet8': {
                    'tagging_mode': 'untagged'
                },
                'Vlan100|Ethernet11': {
                    'tagging_mode': 'untagged'
                }
            },
            'PORT': {
                'Ethernet8': {
                    'speed': '50000',
                    'lanes': '73,74'
                },
                'Ethernet10': {
                    'speed': '25000',
                    'lanes': '75'
                },
                'Ethernet11': {
                    'speed': '25000',
                    'lanes': '76'
                }
            }
        }
        self.checkResult(cmdpb, delConfig, addConfig)
        self.postUpdateConfig(curConfig, delConfig, addConfig)
        return

    def dpb_port8_4x25G_1x100G_f(self, curConfig):
        '''
        Breakout Port 8 4x25G->1x100G with -f

        Parameters:
            curConfig (dict): current Config in config DB.

        Return:
            void
            assert for success and failure.
        '''
        cmdpb = self.config_mgmt_dpb(curConfig)
        # create ARGS
        dPorts, pJson = self.generate_args(portIdx=8, laneIdx=73,
                                           curMode='4x25G', newMode='1x100G')
        deps, ret = cmdpb.breakOutPort(delPorts=dPorts, portJson=pJson,
                                       force=False, loadDefConfig=False)
        # Expected Result delConfig and addConfig is pushed in order
        delConfig = {
            'PORT': {
                'Ethernet8': None,
                'Ethernet9': None,
                'Ethernet10': None,
                'Ethernet11': None
            }
        }
        addConfig = pJson
        self.checkResult(cmdpb, delConfig, addConfig)
        self.postUpdateConfig(curConfig, delConfig, addConfig)
        return

    def dpb_port8_1x100G_4x25G(self, curConfig):
        '''
        Breakout Port 8 1x100G->4x25G

        Parameters:
            curConfig (dict): current Config in config DB.

        Return:
            void
            assert for success and failure.
        '''
        cmdpb = self.config_mgmt_dpb(curConfig)
        dPorts, pJson = self.generate_args(portIdx=8, laneIdx=73,
                                           curMode='1x100G', newMode='4x25G')
        deps, ret = cmdpb.breakOutPort(delPorts=dPorts, portJson=pJson,
                                       force=False, loadDefConfig=False)
        # Expected Result delConfig and addConfig is pushed in order
        delConfig = {
            'PORT': {
                'Ethernet8': None
            }
        }
        addConfig = pJson
        self.checkResult(cmdpb, delConfig, addConfig)
        self.postUpdateConfig(curConfig, delConfig, addConfig)
        return

    def dpb_port8_2x50G_1x100G_f(self, curConfig):
        '''
        Breakout Port 8 2x50G->1x100G with -f

        Parameters:
            curConfig (dict): current Config in config DB.

        Return:
            void
            assert for success and failure.
        '''
        cmdpb = self.config_mgmt_dpb(curConfig)
        # create ARGS
        dPorts, pJson = self.generate_args(portIdx=8, laneIdx=73,
                                           curMode='2x50G', newMode='1x100G')
        deps, ret = cmdpb.breakOutPort(delPorts=dPorts, portJson=pJson,
                                       force=True, loadDefConfig=False)
        # Expected Result delConfig and addConfig is pushed in order
        delConfig = {
            'ACL_TABLE': {
                'NO-NSW-PACL-V4': {
                    'ports': ['Ethernet0', 'Ethernet4']
                }
            },
            'VLAN_MEMBER': {
                'Vlan100|Ethernet8': None
            },
            'PORT': {
                'Ethernet8': None,
                'Ethernet10': None
            }
        }
        addConfig = pJson
        self.checkResult(cmdpb, delConfig, addConfig)
        self.postUpdateConfig(curConfig, delConfig, addConfig)

    def dpb_port8_2x50G_1x100G(self, curConfig):
        '''
        Breakout Port 8 2x50G->1x100G

        Parameters:
            curConfig (dict): current Config in config DB.

        Return:
            void
            assert for success and failure.
        '''
        cmdpb = self.config_mgmt_dpb(curConfig)
        # create ARGS
        dPorts, pJson = self.generate_args(portIdx=8, laneIdx=73,
                                           curMode='2x50G', newMode='1x100G')
        deps, ret = cmdpb.breakOutPort(delPorts=dPorts, portJson=pJson,
                                       force=False, loadDefConfig=False)
        # Expected Result
        assert ret == False and len(deps) == 3
        assert cmdpb.writeConfigDB.call_count == 0
        return

    def dpb_port8_4x25G_2x50G_f_l(self, curConfig):
        '''
        Breakout Port 8 4x25G->2x50G with -f -l

        Parameters:
            curConfig (dict): current Config in config DB.

        Return:
            void
            assert for success and failure.
        '''
        cmdpb = self.config_mgmt_dpb(curConfig)
        # create ARGS
        dPorts, pJson = self.generate_args(portIdx=8, laneIdx=73,
                                           curMode='4x25G', newMode='2x50G')
        cmdpb.breakOutPort(delPorts=dPorts, portJson=pJson, force=True,
                           loadDefConfig=True)
        # Expected Result delConfig and addConfig is pushed in order
        delConfig = {
            'ACL_TABLE': {
                'NO-NSW-PACL-V4': {
                    'ports': ['Ethernet0', 'Ethernet4']
                },
                'NO-NSW-PACL-TEST': {
                    'ports': []
                }
            },
            'INTERFACE': None,
            'VLAN_MEMBER': {
                'Vlan100|Ethernet8': None,
                'Vlan100|Ethernet11': None
            },
            'PORT': {
                'Ethernet8': None,
                'Ethernet9': None,
                'Ethernet10': None,
                'Ethernet11': None
            }
        }
        addConfig = {
            'ACL_TABLE': {
                'NO-NSW-PACL-V4': {
                    'ports': ['Ethernet0', 'Ethernet4', 'Ethernet8', 'Ethernet10']
                }
            },
            'VLAN_MEMBER': {
                'Vlan100|Ethernet8': {
                    'tagging_mode': 'untagged'
                }
            },
            'PORT': {
                'Ethernet8': {
                    'speed': '50000',
                    'lanes': '73,74'
                },
                'Ethernet10': {
                    'speed': '50000',
                    'lanes': '75,76'
                }
            }
        }
        self.checkResult(cmdpb, delConfig, addConfig)
        self.postUpdateConfig(curConfig, delConfig, addConfig)
        return

    def dpb_port4_4x25G_2x50G_f_l(self, curConfig):
        '''
        Breakout Port 4 4x25G->2x50G with -f -l

        Parameters:
            curConfig (dict): current Config in config DB.

        Return:
            void
            assert for success and failure.
        '''
        cmdpb = self.config_mgmt_dpb(curConfig)
        # create ARGS
        dPorts, pJson = self.generate_args(portIdx=4, laneIdx=69,
                                           curMode='4x25G', newMode='2x50G')
        cmdpb.breakOutPort(delPorts=dPorts, portJson=pJson, force=True,
                           loadDefConfig=True)
        # Expected Result delConfig and addConfig is pushed in order
        delConfig = {
            'ACL_TABLE': {
                'NO-NSW-PACL-V4': {
                    'ports': ['Ethernet0', 'Ethernet8', 'Ethernet10']
                }
            },
            'PORT': {
                'Ethernet4': None,
                'Ethernet5': None,
                'Ethernet6': None,
                'Ethernet7': None
            }
        }
        addConfig = {
            'ACL_TABLE': {
                'NO-NSW-PACL-V4': {
                    'ports': ['Ethernet0', 'Ethernet8', 'Ethernet10', 'Ethernet4']
                }
            },
            'PORT': {
                'Ethernet4': {
                    'speed': '50000',
                    'lanes': '69,70'
                },
                'Ethernet6': {
                    'speed': '50000',
                    'lanes': '71,72'
                }
            }
        }
        self.checkResult(cmdpb, delConfig, addConfig)
        self.postUpdateConfig(curConfig, delConfig, addConfig)
        return


###########GLOBAL Configs#####################################
configDbJson = {
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

DESCR = "Description"
MULTI_ASIC = "multi_asic"
NAMESPACE = "namespace-list"
ARGS = "args"
RET = "return"
APPL_DB = 0
ASIC_DB = 1
CONFIG_DB = 4
APPL_STATE_DB = 14
PRE = "pre-value"
UPD = "update"
FRR_ROUTES = "frr-routes"
RESULT = "res"
DEFAULTNS=""
ASIC0 = "asic0"
ASIC1 = "asic1"

OP_SET = "SET"
OP_DEL = "DEL"

NEIGH_TABLE = 'NEIGH_TABLE'
ROUTE_TABLE = 'ROUTE_TABLE'
VNET_ROUTE_TABLE = 'VNET_ROUTE_TABLE'
INTF_TABLE = 'INTF_TABLE'
RT_ENTRY_TABLE = 'ASIC_STATE'
FEATURE_TABLE = 'FEATURE'
SEPARATOR = ":"
DEVICE_METADATA = "DEVICE_METADATA"
MUX_CABLE = "MUX_CABLE"

LOCALHOST = "localhost"

RT_ENTRY_KEY_PREFIX = 'SAI_OBJECT_TYPE_ROUTE_ENTRY:{\"dest":\"'
RT_ENTRY_KEY_SUFFIX = '\",\"switch_id\":\"oid:0x21000000000000\",\"vr\":\"oid:0x3000000000023\"}'

DEFAULT_CONFIG_DB = {
    DEVICE_METADATA: {
        LOCALHOST: {
            }
        },
    FEATURE_TABLE: {
        "bgp": {
            "state": "enabled"
            }
        }
    }

TEST_DATA = {
    "0": {
        DESCR: "basic good one",
        MULTI_ASIC: False,
        NAMESPACE: [''],
        ARGS: "route_check -m INFO -i 1000",
        PRE: {
            DEFAULTNS: {
                APPL_DB: {
                    ROUTE_TABLE: {
                        "0.0.0.0/0" : { "ifname": "portchannel0" },
                        "10.10.196.12/31" : { "ifname": "portchannel0" },
                        "10.10.196.20/31" : { "ifname": "portchannel0" },
                        "10.10.196.30/31" : { "ifname": "lo" }
                    },
                    INTF_TABLE: {
                        "PortChannel1013:10.10.196.24/31": {},
                        "PortChannel1023:2603:10b0:503:df4::5d/126": {},
                        "PortChannel1024": {}
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "10.10.196.12/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.20/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "2603:10b0:503:df4::5d/128" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {}
                    }
                }
            }
        }
    },
    "1": {
        DESCR: "With updates",
        MULTI_ASIC: False,
        NAMESPACE: [''],
        ARGS: "route_check -m DEBUG -i 1",
        PRE: {
            DEFAULTNS: {
                APPL_DB: {
                    ROUTE_TABLE: {
                        "0.0.0.0/0" : { "ifname": "portchannel0" },
                        "10.10.196.12/31" : { "ifname": "portchannel0" },
                        "10.10.196.20/31" : { "ifname": "portchannel0" },
                        "10.10.196.30/31" : { "ifname": "lo" }
                    },
                    INTF_TABLE: {
                        "PortChannel1013:10.10.196.24/31": {},
                        "PortChannel1023:2603:10b0:503:df4::5d/126": {}
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "10.10.196.20/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "2603:10b0:503:df4::5d/128" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.10.10/32" + RT_ENTRY_KEY_SUFFIX: {}
                    }
                }
            }
        },
        UPD: {
            DEFAULTNS: {
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        OP_SET: {
                            RT_ENTRY_KEY_PREFIX + "10.10.196.12/31" + RT_ENTRY_KEY_SUFFIX: {},
                        },
                        OP_DEL: {
                            RT_ENTRY_KEY_PREFIX + "10.10.10.10/32" + RT_ENTRY_KEY_SUFFIX: {}
                        }
                    }
                }
            }
        }
    },
    "2": {
        DESCR: "basic failure one",
        MULTI_ASIC: False,
        NAMESPACE: [''],
        ARGS: "route_check -i 15",
        RET: -1,
        PRE: {
            DEFAULTNS: {
                APPL_DB: {
                    ROUTE_TABLE: {
                        "0.0.0.0/0" : { "ifname": "portchannel0" },
                        "10.10.196.12/31" : { "ifname": "portchannel0" },
                        "10.10.196.20/31" : { "ifname": "portchannel0" },
                        "10.10.196.30/31" : { "ifname": "lo" }
                    },
                    INTF_TABLE: {
                        "PortChannel1013:90.10.196.24/31": {},
                        "PortChannel1023:9603:10b0:503:df4::5d/126": {},
                        "PortChannel1024": {}
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "20.10.196.12/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "20.10.196.20/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "20.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "3603:10b0:503:df4::5d/128" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {}
                    }
                }
            }
        },
        RESULT: {
            DEFAULTNS: {
                "missed_ROUTE_TABLE_routes": [
                    "10.10.196.12/31",
                    "10.10.196.20/31"
                ],
                "missed_INTF_TABLE_entries": [
                    "90.10.196.24/32",
                    "9603:10b0:503:df4::5d/128"
                ],
                "Unaccounted_ROUTE_ENTRY_TABLE_entries": [
                    "20.10.196.12/31",
                    "20.10.196.20/31",
                    "20.10.196.24/32",
                    "3603:10b0:503:df4::5d/128"
                ]
            }
        }
    },
    "3": {
        DESCR: "basic good one with no args",
        MULTI_ASIC: False,
        NAMESPACE: [''],
        ARGS: "route_check",
        PRE: {
            DEFAULTNS: {
                APPL_DB: {
                    ROUTE_TABLE: {
                        "0.0.0.0/0" : { "ifname": "portchannel0" },
                        "10.10.196.12/31" : { "ifname": "portchannel0" },
                        "10.10.196.20/31" : { "ifname": "portchannel0" },
                        "10.10.196.30/31" : { "ifname": "lo" }
                    },
                    INTF_TABLE: {
                        "PortChannel1013:10.10.196.24/31": {},
                        "PortChannel1023:2603:10b0:503:df4::5d/126": {},
                        "PortChannel1024": {}
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "10.10.196.12/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.20/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "2603:10b0:503:df4::5d/128" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {}
                    }
                }
            }
        }
    },
    "4": {
        DESCR: "Good one with routes on voq inband interface",
        MULTI_ASIC: False,
        NAMESPACE: [''],
        ARGS: "route_check",
        PRE: {
            DEFAULTNS: {
                APPL_DB: {
                    ROUTE_TABLE: {
                        "0.0.0.0/0" : { "ifname": "portchannel0" },
                        "10.10.196.12/31" : { "ifname": "portchannel0" },
                        "10.10.196.20/31" : { "ifname": "portchannel0" },
                        "10.10.196.30/31" : { "ifname": "lo" },
                        "10.10.197.1" : { "ifname": "Ethernet-IB0", "nexthop": "0.0.0.0"},
                        "2603:10b0:503:df5::1" : { "ifname": "Ethernet-IB0", "nexthop": "::"},
                        "100.0.0.2/32" : { "ifname": "Ethernet-IB0", "nexthop": "0.0.0.0" },
                        "2064:100::2/128" : { "ifname": "Ethernet-IB0", "nexthop": "::" },
                        "101.0.0.0/24" : { "ifname": "Ethernet-IB0", "nexthop": "100.0.0.2"}
                    },
                    INTF_TABLE: {
                        "PortChannel1013:10.10.196.24/31": {},
                        "PortChannel1023:2603:10b0:503:df4::5d/126": {},
                        "PortChannel1024": {},
                        "Ethernet-IB0:10.10.197.1/24": {},
                        "Ethernet-IB0:2603:10b0:503:df5::1/64": {}
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "10.10.196.12/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.20/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "2603:10b0:503:df4::5d/128" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.197.1/32" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "2603:10b0:503:df5::1/128" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "101.0.0.0/24" + RT_ENTRY_KEY_SUFFIX: {}
                    }
                }
            }
        }
    },
    "5": {
        DESCR: "local route with nexthop - fail",
        MULTI_ASIC: False,
        NAMESPACE: [''],
        ARGS: "route_check -m INFO -i 1000",
        RET: -1,
        PRE: {
            DEFAULTNS: {
                APPL_DB: {
                    ROUTE_TABLE: {
                        "0.0.0.0/0" : { "ifname": "portchannel0" },
                        "10.10.196.12/31" : { "ifname": "portchannel0" },
                        "10.10.196.20/31" : { "ifname": "portchannel0" },
                        "10.10.196.30/31" : { "ifname": "lo", "nexthop": "100.0.0.2" }
                    },
                    INTF_TABLE: {
                        "PortChannel1013:10.10.196.24/31": {},
                        "PortChannel1023:2603:10b0:503:df4::5d/126": {},
                        "PortChannel1024": {}
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "10.10.196.12/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.20/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "2603:10b0:503:df4::5d/128" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {}
                    }
                }
            }
        },
        RESULT: {
            DEFAULTNS: {
                "missed_ROUTE_TABLE_routes": [
                    "10.10.196.30/31"
                ]
            }
        }
    },
    "6": {
        DESCR: "Good one with VNET routes",
        MULTI_ASIC: False,
        NAMESPACE: [''],
        ARGS: "route_check",
        PRE: {
            DEFAULTNS: {
                APPL_DB: {
                    ROUTE_TABLE: {
                        "0.0.0.0/0" : { "ifname": "portchannel0" },
                        "10.10.196.12/31" : { "ifname": "portchannel0" },
                        "10.10.196.20/31" : { "ifname": "portchannel0" },
                        "10.10.196.30/31" : { "ifname": "lo" }
                    },
                    VNET_ROUTE_TABLE: {
                        "Vnet1:30.1.10.0/24": { "ifname": "Vlan3001" },
                        "Vnet1:50.1.1.0/24": { "ifname": "Vlan3001" },
                        "Vnet1:50.2.2.0/24": { "ifname": "Vlan3001" }
                    },
                    INTF_TABLE: {
                        "PortChannel1013:10.10.196.24/31": {},
                        "PortChannel1023:2603:10b0:503:df4::5d/126": {},
                        "PortChannel1024": {},
                        "Vlan3001": { "vnet_name": "Vnet1" },
                        "Vlan3001:30.1.10.1/24": {}
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "10.10.196.12/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.20/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "2603:10b0:503:df4::5d/128" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "30.1.10.1/32" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "30.1.10.0/24" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "50.1.1.0/24" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "50.2.2.0/24" + RT_ENTRY_KEY_SUFFIX: {}
                    }
                }
            }
        }
    },
    "7": {
        DESCR: "dualtor standalone tunnel route case",
        MULTI_ASIC: False,
        NAMESPACE: [''],
        ARGS: "route_check",
        PRE: {
            DEFAULTNS: {
                CONFIG_DB: {
                    DEVICE_METADATA: {
                        LOCALHOST: {"subtype": "DualToR"}
                    },
                    FEATURE_TABLE: {
                        "bgp": {
                            "state": "enabled"
                        }
                    }
                },
                APPL_DB: {
                    NEIGH_TABLE: {
                        "Vlan1000:fc02:1000::99": { "neigh": "00:00:00:00:00:00", "family": "IPv6"}
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "fc02:1000::99/128" + RT_ENTRY_KEY_SUFFIX: {},
                    }
                }
            }
        }
    },
    "8": {
        DESCR: "Good one with VRF routes",
        MULTI_ASIC: False,
        NAMESPACE: [''],
        ARGS: "route_check",
        PRE: {
            DEFAULTNS: {
                APPL_DB: {
                    ROUTE_TABLE: {
                        "Vrf1:0.0.0.0/0" : { "ifname": "portchannel0" },
                        "Vrf1:10.10.196.12/31" : { "ifname": "portchannel0" },
                        "Vrf1:10.10.196.20/31" : { "ifname": "portchannel0" }
                    },
                    INTF_TABLE: {
                        "PortChannel1013:10.10.196.24/31": {},
                        "PortChannel1023:2603:10b0:503:df4::5d/126": {},
                        "PortChannel1024": {}
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "10.10.196.12/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.20/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "2603:10b0:503:df4::5d/128" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {}
                    }
                }
            }
        }
    },
    "9": {
        DESCR: "SOC IPs on Libra ToRs should be ignored",
        MULTI_ASIC: False,
        NAMESPACE: [''],
        ARGS: "route_check",
        PRE: {
            DEFAULTNS: {
                CONFIG_DB: {
                    DEVICE_METADATA: {
                        LOCALHOST: {"subtype": "DualToR"}
                    },
                    MUX_CABLE: {
                        "Ethernet4": {
                            "cable_type": "active-active",
                            "server_ipv4": "192.168.0.2/32",
                            "server_ipv6": "fc02:1000::2/128",
                            "soc_ipv4": "192.168.0.3/32",
                            "soc_ipv6": "fc02:1000::3/128",
                            "state": "auto"
                        },
                    },
                    FEATURE_TABLE: {
                        "bgp": {
                            "state": "enabled"
                        }
                    }
                },
                APPL_DB: {
                    ROUTE_TABLE: {
                        "192.168.0.2/32": {"ifname": "tun0"},
                        "fc02:1000::2/128": {"ifname": "tun0"}
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "192.168.0.2/32" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "fc02:1000::2/128" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "192.168.0.3/32" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "fc02:1000::3/128" + RT_ENTRY_KEY_SUFFIX: {}
                    }
                }
            }
        }
    },
    "10": {
        DESCR: "basic good one, check FRR routes",
        MULTI_ASIC: False,
        NAMESPACE: [''],
        ARGS: "route_check -m INFO -i 1000",
        PRE: {
            DEFAULTNS: {
                APPL_DB: {
                    ROUTE_TABLE: {
                        "0.0.0.0/0" : { "ifname": "portchannel0" },
                        "10.10.196.12/31" : { "ifname": "portchannel0" },
                    },
                    INTF_TABLE: {
                        "PortChannel1013:10.10.196.24/31": {},
                        "PortChannel1023:2603:10b0:503:df4::5d/126": {},
                        "PortChannel1024": {}
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "10.10.196.12/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "2603:10b0:503:df4::5d/128" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {}
                    }
                },
            },
        },
        FRR_ROUTES: {
            DEFAULTNS: {
                "0.0.0.0/0": [
                    {
                        "prefix": "0.0.0.0/0",
                        "vrfName": "default",
                        "protocol": "bgp",
                        "selected": True,
                        "offloaded": True,
                    },
                ],
                "10.10.196.12/31": [
                    {
                        "prefix": "10.10.196.12/31",
                        "vrfName": "default",
                        "protocol": "bgp",
                        "selected": True,
                        "offloaded": True,
                    },
                ],
                "10.10.196.24/31": [
                    {
                        "protocol": "connected",
                        "selected": True,
                    },
                ],
            }
        },
    },
    "11": {
        DESCR: "failure test case, missing FRR routes",
        MULTI_ASIC: False,
        NAMESPACE: [''],
        ARGS: "route_check -m INFO -i 1000",
        PRE: {
            DEFAULTNS: {
                APPL_DB: {
                    ROUTE_TABLE: {
                        "0.0.0.0/0" : { "ifname": "portchannel0" },
                        "10.10.196.12/31" : { "ifname": "portchannel0" },
                    },
                    INTF_TABLE: {
                        "PortChannel1013:10.10.196.24/31": {},
                        "PortChannel1023:2603:10b0:503:df4::5d/126": {},
                        "PortChannel1024": {}
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "10.10.196.12/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "2603:10b0:503:df4::5d/128" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {}
                    }
                },
            },
        },
        FRR_ROUTES: {
            DEFAULTNS: {
                "0.0.0.0/0": [
                    {
                        "prefix": "0.0.0.0/0",
                        "vrfName": "default",
                        "protocol": "bgp",
                        "selected": True,
                        "offloaded": True,
                    },
                ],
                "10.10.196.12/31": [
                    {
                        "prefix": "10.10.196.12/31",
                        "vrfName": "default",
                        "protocol": "bgp",
                        "selected": True,
                    },
                ],
                "1.1.1.0/24": [
                    {
                        "prefix": "1.1.1.0/24",
                        "vrfName": "default",
                        "protocol": "static",
                        "selected": True,
                    },
                ],
                "10.10.196.24/31": [
                    {
                        "protocol": "connected",
                        "selected": True,
                    },
                ],
            },
        },
        RESULT: {
            DEFAULTNS: {
                "missed_FRR_routes": [
                    {"prefix": "10.10.196.12/31", "vrfName": "default", "protocol": "bgp", "selected": True},
                    {"prefix": "1.1.1.0/24", "vrfName": "default", "protocol": "static", "selected": True},
                ],
            },
        },
        RET: -1,
    },
    "12": {
        DESCR: "skip bgp routes offloaded check, if not selected as best",
        MULTI_ASIC: False,
        NAMESPACE: [''],
        ARGS: "route_check -m INFO -i 1000",
        PRE: {
            DEFAULTNS: {
                APPL_DB: {
                    ROUTE_TABLE: {
                        "0.0.0.0/0" : { "ifname": "portchannel0" },
                        "10.10.196.12/31" : { "ifname": "portchannel0" },
                    },
                    INTF_TABLE: {
                        "PortChannel1013:10.10.196.24/31": {},
                        "PortChannel1023:2603:10b0:503:df4::5d/126": {},
                        "PortChannel1024": {}
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "10.10.196.12/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "2603:10b0:503:df4::5d/128" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {}
                    }
                },
            },
        },
        FRR_ROUTES: {
            DEFAULTNS: {
                "0.0.0.0/0": [
                    {
                        "prefix": "0.0.0.0/0",
                        "vrfName": "default",
                        "protocol": "bgp",
                        "selected": True,
                        "offloaded": True,
                    },
                ],
                "10.10.196.12/31": [
                    {
                        "prefix": "10.10.196.12/31",
                        "vrfName": "default",
                        "protocol": "bgp",
                    },
                ],
                "10.10.196.24/31": [
                    {
                        "protocol": "connected",
                        "selected": True,
                    },
                ],
            },
        },
    },
    "13": {
        DESCR: "basic good one with IPv6 address",
        MULTI_ASIC: False,
        NAMESPACE: [''],
        ARGS: "route_check -m INFO -i 1000",
        PRE: {
            DEFAULTNS: {
                APPL_DB: {
                    ROUTE_TABLE: {
                    },
                    INTF_TABLE: {
                        "PortChannel1013:2000:31:0:0::1/64": {},
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "2000:31::1/128" + RT_ENTRY_KEY_SUFFIX: {},
                    }
                }
            }
        }
    },
    "14": {
        DESCR: "dualtor ignore vlan neighbor route miss case",
        MULTI_ASIC: False,
        NAMESPACE: [''],
        ARGS: "route_check -i 15",
        RET: -1,
        PRE: {
            DEFAULTNS: {
                CONFIG_DB: {
                    DEVICE_METADATA: {
                        LOCALHOST: {"subtype": "DualToR"}
                    },
                    FEATURE_TABLE: {
                        "bgp": {
                            "state": "enabled"
                        }
                    }
                },
                APPL_DB: {
                    ROUTE_TABLE: {
                        "10.10.196.12/31" : { "ifname": "portchannel0" },
                        "10.10.196.20/31" : { "ifname": "portchannel0" },
                        "192.168.0.101/32": { "ifname": "tun0" },
                        "192.168.0.103/32": { "ifname": "tun0" },
                    },
                    INTF_TABLE: {
                        "PortChannel1013:90.10.196.24/31": {},
                        "PortChannel1023:9603:10b0:503:df4::5d/126": {},
                    },
                    NEIGH_TABLE: {
                        "Vlan1000:192.168.0.100": {},
                        "Vlan1000:192.168.0.101": {},
                        "Vlan1000:192.168.0.102": {},
                        "Vlan1000:192.168.0.103": {},
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "20.10.196.12/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "20.10.196.20/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "20.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "192.168.0.101/32" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "192.168.0.102/32" + RT_ENTRY_KEY_SUFFIX: {},
                    }
                }
            }
        },
        RESULT: {
            DEFAULTNS: {
                "missed_ROUTE_TABLE_routes": [
                    "10.10.196.12/31",
                    "10.10.196.20/31"
                ],
                "missed_INTF_TABLE_entries": [
                    "90.10.196.24/32",
                    "9603:10b0:503:df4::5d/128"
                ],
                "Unaccounted_ROUTE_ENTRY_TABLE_entries": [
                    "20.10.196.12/31",
                    "20.10.196.20/31",
                    "20.10.196.24/32",
                ]
            }
        }
    },
    "15": {
        DESCR: "basic good one on multi-asic on a particular asic",
        MULTI_ASIC: True,
        NAMESPACE: ['asic0', 'asic1'],
        ARGS: "route_check -n asic0 -m INFO -i 1000",
        PRE: {
            ASIC0: {
                APPL_DB: {
                    ROUTE_TABLE: {
                        "0.0.0.0/0" : { "ifname": "portchannel0" },
                        "10.10.196.12/31" : { "ifname": "portchannel0" },
                        "10.10.196.20/31" : { "ifname": "portchannel0" },
                        "10.10.196.30/31" : { "ifname": "lo" }
                    },
                    INTF_TABLE: {
                        "PortChannel1013:10.10.196.24/31": {},
                        "PortChannel1023:2603:10b0:503:df4::5d/126": {},
                        "PortChannel1024": {}
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "10.10.196.12/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.20/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "2603:10b0:503:df4::5d/128" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {}
                    }
                }
            }
        }
    },
    "16": {
        DESCR: "basic good one on multi-asic on all asics",
        MULTI_ASIC: True,
        NAMESPACE: ['asic0', 'asic1'],
        ARGS: "route_check -m INFO -i 1000",
        PRE: {
            ASIC0: {
                APPL_DB: {
                    ROUTE_TABLE: {
                        "0.0.0.0/0" : { "ifname": "portchannel0" },
                        "10.10.196.12/31" : { "ifname": "portchannel0" },
                        "10.10.196.20/31" : { "ifname": "portchannel0" },
                        "10.10.196.30/31" : { "ifname": "lo" }
                    },
                    INTF_TABLE: {
                        "PortChannel1013:10.10.196.24/31": {},
                        "PortChannel1023:2603:10b0:503:df4::5d/126": {},
                        "PortChannel1024": {}
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "10.10.196.12/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.20/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "2603:10b0:503:df4::5d/128" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {}
                    }
                }
            },
            ASIC1: {
               APPL_DB: {
                   ROUTE_TABLE: {
                       "0.0.0.0/0" : { "ifname": "portchannel0" },
                       "10.10.196.12/31" : { "ifname": "portchannel0" },
                       "10.10.196.20/31" : { "ifname": "portchannel0" },
                       "10.10.196.30/31" : { "ifname": "lo" }
                   },
                   INTF_TABLE: {
                       "PortChannel1013:10.10.196.24/31": {},
                       "PortChannel1023:2603:10b0:503:df4::5d/126": {},
                       "PortChannel1024": {}
                   }
               },
               ASIC_DB: {
                   RT_ENTRY_TABLE: {
                       RT_ENTRY_KEY_PREFIX + "10.10.196.12/31" + RT_ENTRY_KEY_SUFFIX: {},
                       RT_ENTRY_KEY_PREFIX + "10.10.196.20/31" + RT_ENTRY_KEY_SUFFIX: {},
                       RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                       RT_ENTRY_KEY_PREFIX + "2603:10b0:503:df4::5d/128" + RT_ENTRY_KEY_SUFFIX: {},
                       RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {}
                   }
               }
           },
        }
    },
    "17": {
        DESCR: "simple failure case on multi-asic on a particular asic",
        MULTI_ASIC: True,
        NAMESPACE: ['asic0', 'asic1'],
        ARGS: "route_check -n asic0 -m INFO -i 1000",
        PRE: {
            ASIC0: {
                APPL_DB: {
                    ROUTE_TABLE: {
                        "0.0.0.0/0" : { "ifname": "portchannel0" },
                        "10.10.196.12/31" : { "ifname": "portchannel0" },
                        "10.10.196.20/31" : { "ifname": "portchannel0" },
                        "10.10.196.30/31" : { "ifname": "lo" }
                    },
                    INTF_TABLE: {
                        "PortChannel1013:10.10.196.24/31": {},
                        "PortChannel1023:2603:10b0:503:df4::5d/126": {},
                        "PortChannel1024": {}
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "10.10.196.20/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "2603:10b0:503:df4::5d/128" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {}
                    }
                }
            }
        },
        RESULT: {
            ASIC0: {
                "missed_ROUTE_TABLE_routes": [
                    "10.10.196.12/31"
                ],
            }
        },
        RET: -1,
    },
    "18": {
        DESCR: "simple failure case on multi-asic on all asics",
        MULTI_ASIC: True,
        NAMESPACE: ['asic0', 'asic1'],
        ARGS: "route_check -m INFO -i 1000",
        PRE: {
            ASIC0: {
                APPL_DB: {
                    ROUTE_TABLE: {
                        "0.0.0.0/0" : { "ifname": "portchannel0" },
                        "10.10.196.12/31" : { "ifname": "portchannel0" },
                        "10.10.196.20/31" : { "ifname": "portchannel0" },
                        "10.10.196.30/31" : { "ifname": "lo" }
                    },
                    INTF_TABLE: {
                        "PortChannel1013:10.10.196.24/31": {},
                        "PortChannel1023:2603:10b0:503:df4::5d/126": {},
                        "PortChannel1024": {}
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "10.10.196.20/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "2603:10b0:503:df4::5d/128" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {}
                    }
                }
            },
            ASIC1: {
               APPL_DB: {
                   ROUTE_TABLE: {
                       "0.0.0.0/0" : { "ifname": "portchannel0" },
                       "10.10.196.20/31" : { "ifname": "portchannel0" },
                       "10.10.196.30/31" : { "ifname": "lo" }
                   },
                   INTF_TABLE: {
                       "PortChannel1013:10.10.196.24/31": {},
                       "PortChannel1023:2603:10b0:503:df4::5d/126": {},
                       "PortChannel1024": {}
                   }
               },
               ASIC_DB: {
                   RT_ENTRY_TABLE: {
                       RT_ENTRY_KEY_PREFIX + "10.10.196.12/31" + RT_ENTRY_KEY_SUFFIX: {},
                       RT_ENTRY_KEY_PREFIX + "10.10.196.20/31" + RT_ENTRY_KEY_SUFFIX: {},
                       RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                       RT_ENTRY_KEY_PREFIX + "2603:10b0:503:df4::5d/128" + RT_ENTRY_KEY_SUFFIX: {},
                       RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {}
                   }
               }
           },
        },
        RESULT: {
            ASIC0: {
                "missed_ROUTE_TABLE_routes": [
                    "10.10.196.12/31"
                ],
            },
            ASIC1: {
                "Unaccounted_ROUTE_ENTRY_TABLE_entries": [
                    "10.10.196.12/31"
                ],
            },
        },
        RET: -1,
    },
    "19": {
        DESCR: "validate namespace input on multi-asic",
        MULTI_ASIC: True,
        NAMESPACE: ['asic0', 'asic1'],
        ARGS: "route_check -n random -m INFO -i 1000",
        RET: -1,
    },
    "20": {
        DESCR: "validate namespace input on single-asic",
        MULTI_ASIC: False,
        NAMESPACE: [''],
        ARGS: "route_check -n random -m INFO -i 1000",
        RET: -1,
    },
    "21": {
        DESCR: "multi-asic failure test case, missing FRR routes",
        MULTI_ASIC: True,
        NAMESPACE: ['asic0', 'asic1'],
        ARGS: "route_check -n asic1 -m INFO -i 1000",
        PRE: {
            ASIC1: {
                APPL_DB: {
                    ROUTE_TABLE: {
                        "0.0.0.0/0" : { "ifname": "portchannel0" },
                        "10.10.196.12/31" : { "ifname": "portchannel0" },
                    },
                    INTF_TABLE: {
                        "PortChannel1013:10.10.196.24/31": {},
                        "PortChannel1023:2603:10b0:503:df4::5d/126": {},
                        "PortChannel1024": {}
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "10.10.196.12/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "2603:10b0:503:df4::5d/128" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {}
                    }
                },
            },
        },
        FRR_ROUTES: {
            ASIC1: {
                "0.0.0.0/0": [
                    {
                        "prefix": "0.0.0.0/0",
                        "vrfName": "default",
                        "protocol": "bgp",
                        "selected": True,
                        "offloaded": True,
                    },
                ],
                "10.10.196.12/31": [
                    {
                        "prefix": "10.10.196.12/31",
                        "vrfName": "default",
                        "protocol": "bgp",
                        "selected": True,
                    },
                ],
                "10.10.196.24/31": [
                    {
                        "protocol": "connected",
                        "selected": True,
                    },
                ],
            },
        },
        RESULT: {
            ASIC1: {
                "missed_FRR_routes": [
                    {"prefix": "10.10.196.12/31", "vrfName": "default", "protocol": "bgp", "selected": True}
                ],
            },
        },
        RET: -1,
    },
    "22": {
        DESCR: "basic good one on single asic, bgp disabled",
        MULTI_ASIC: False,
        NAMESPACE: [''],
        ARGS: "route_check -m INFO -i 1000",
        PRE: {
            DEFAULTNS: {
                CONFIG_DB: {
                    DEVICE_METADATA: {
                        LOCALHOST: {
                        }
                    },
                    FEATURE_TABLE: {
                        "bgp": {
                            "state": "disabled"
                        }
                    }
                },
                APPL_DB: {
                    ROUTE_TABLE: {
                        "0.0.0.0/0" : { "ifname": "portchannel0" },
                        "10.10.196.12/31" : { "ifname": "portchannel0" },
                    },
                    INTF_TABLE: {
                        "PortChannel1013:10.10.196.24/31": {},
                        "PortChannel1023:2603:10b0:503:df4::5d/126": {},
                        "PortChannel1024": {}
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "10.10.196.12/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "2603:10b0:503:df4::5d/128" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {}
                    }
                },
            },
        },
        FRR_ROUTES: {
            DEFAULTNS: {
                "0.0.0.0/0": [
                    {
                        "prefix": "0.0.0.0/0",
                        "vrfName": "default",
                        "protocol": "bgp",
                        "offloaded": "true",
                    },
                ],
                "10.10.196.12/31": [
                    {
                        "prefix": "10.10.196.12/31",
                        "vrfName": "default",
                        "protocol": "bgp",
                    },
                ],
                "10.10.196.24/31": [
                    {
                        "protocol": "connected",
                    },
                ],
            },
        },
    },
    "23": {
        DESCR: "basic good one on multi-asic, bgp disabled",
        MULTI_ASIC: True,
        NAMESPACE: ['asic0'],
        ARGS: "route_check -m INFO -i 1000",
        PRE: {
            ASIC0: {
                CONFIG_DB: {
                    DEVICE_METADATA: {
                        LOCALHOST: {
                        }
                    },
                    FEATURE_TABLE: {
                        "bgp": {
                            "state": "disabled"
                        }
                    }
                },
                APPL_DB: {
                    ROUTE_TABLE: {
                        "0.0.0.0/0" : { "ifname": "portchannel0" },
                        "10.10.196.12/31" : { "ifname": "portchannel0" },
                    },
                    INTF_TABLE: {
                        "PortChannel1013:10.10.196.24/31": {},
                        "PortChannel1023:2603:10b0:503:df4::5d/126": {},
                        "PortChannel1024": {}
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "10.10.196.12/31" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "2603:10b0:503:df4::5d/128" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {}
                    }
                },
            },
        },
        FRR_ROUTES: {
            ASIC0: {
                "0.0.0.0/0": [
                    {
                        "prefix": "0.0.0.0/0",
                        "vrfName": "default",
                        "protocol": "bgp",
                        "offloaded": "true",
                    },
                ],
                "10.10.196.12/31": [
                    {
                        "prefix": "10.10.196.12/31",
                        "vrfName": "default",
                        "protocol": "bgp",
                    },
                ],
                "10.10.196.24/31": [
                    {
                        "protocol": "connected",
                    },
                ],
            },
        },
    },
    "24": {
        DESCR: "FRR route check with failed routes detection",
        MULTI_ASIC: False,
        NAMESPACE: [''],
        ARGS: "route_check -m INFO -i 1000",
        RET: -1,
        PRE: {
            DEFAULTNS: {
                APPL_DB: {
                    ROUTE_TABLE: {
                        "10.2.1.0/24" : { "ifname": "portchannel0" },
                        "10.3.1.0/24" : { "ifname": "portchannel0" },
                    },
                    INTF_TABLE: {
                        "PortChannel1013:10.10.196.24/31": {},
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "10.2.1.0/24" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.3.1.0/24" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                    }
                },
            },
        },
        FRR_ROUTES: {
            DEFAULTNS: {
                "10.2.1.0/24": [
                    {
                        "prefix": "10.2.1.0/24",
                        "vrfName": "default",
                        "protocol": "bgp",
                        "selected": True,
                        "offloaded": True,
                        "failed": True,
                    },
                ],
                "10.3.1.0/24": [
                    {
                        "prefix": "10.3.1.0/24",
                        "vrfName": "default",
                        "protocol": "bgp",
                        "selected": True,
                        "offloaded": False,
                        "failed": True,
                    },
                ],
            },
        },
        RESULT: {
            DEFAULTNS: {
                "failed_FRR_routes": [
                    {
                        "prefix": "10.2.1.0/24",
                        "vrfName": "default",
                        "protocol": "bgp", 
                        "selected": True,
                        "offloaded": True,
                        "failed": True,
                    },
                    {
                        "prefix": "10.3.1.0/24",
                        "vrfName": "default",
                        "protocol": "bgp",
                        "selected": True, 
                        "offloaded": False,
                        "failed": True,
                    },
                ],
            },
        },
    },
    "25": {
        DESCR: "FRR route check with suppress-fib-pending disabled - tests prefix filtering",
        MULTI_ASIC: False,
        NAMESPACE: [''],
        ARGS: "route_check -m INFO -i 1000",
        RET: -1,
        PRE: {
            DEFAULTNS: {
                CONFIG_DB: {
                    DEVICE_METADATA: {
                        LOCALHOST: {
                            "suppress-fib-pending": "disabled"
                        }
                    },
                    FEATURE_TABLE: {
                        "bgp": {
                            "state": "enabled"
                        }
                    }
                },
                APPL_DB: {
                    ROUTE_TABLE: {
                        "0.0.0.0/0" : { "ifname": "portchannel0" },
                        "10.1.1.0/24" : { "ifname": "portchannel0" },
                    },
                    INTF_TABLE: {
                        "PortChannel1013:10.10.196.24/31": {},
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "0.0.0.0/0" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.1.1.0/24" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                    }
                },
            },
        },
        # This will trigger check_frr_pending_routes() with prefix="0.0.0.0/0" and prefix="::/0"
        # internally testing the IPv4 and IPv6 prefix filtering functionality
        FRR_ROUTES: {
            DEFAULTNS: {
                "0.0.0.0/0": [
                    {
                        "prefix": "0.0.0.0/0",
                        "vrfName": "default",
                        "protocol": "bgp",
                        "selected": True,
                        "offloaded": False,
                        "failed": True,
                    },
                ],
                "::/0": [
                    {
                        "prefix": "::/0",
                        "vrfName": "default",
                        "protocol": "bgp",
                        "selected": True,
                        "offloaded": True,
                        "failed": False,
                    },
                ],
            },
        },
        RESULT: {
            DEFAULTNS: {
                "missed_FRR_routes": [
                    {
                        "prefix": "0.0.0.0/0",
                        "vrfName": "default",
                        "protocol": "bgp",
                        "selected": True,
                        "offloaded": False,
                        "failed": True,
                    },
                ],
                "failed_FRR_routes": [
                    {
                        "prefix": "0.0.0.0/0",
                        "vrfName": "default",
                        "protocol": "bgp",
                        "selected": True,
                        "offloaded": False,
                        "failed": True,
                    },
                ],
            },
        },
    },
    "26": {
        DESCR: "Multi-ASIC FRR route check with failed routes detection",
        MULTI_ASIC: True,
        NAMESPACE: ['asic0', 'asic1'],
        ARGS: "route_check -n asic0 -m INFO -i 1000",
        RET: -1,
        PRE: {
            ASIC0: {
                APPL_DB: {
                    ROUTE_TABLE: {
                        "203.0.113.0/24" : { "ifname": "portchannel0" },
                        "198.51.100.0/24" : { "ifname": "portchannel0" },
                    },
                    INTF_TABLE: {
                        "PortChannel1013:10.10.196.24/31": {},
                    }
                },
                ASIC_DB: {
                    RT_ENTRY_TABLE: {
                        RT_ENTRY_KEY_PREFIX + "203.0.113.0/24" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "198.51.100.0/24" + RT_ENTRY_KEY_SUFFIX: {},
                        RT_ENTRY_KEY_PREFIX + "10.10.196.24/32" + RT_ENTRY_KEY_SUFFIX: {},
                    }
                },
            },
        },
        FRR_ROUTES: {
            ASIC0: {
                "203.0.113.0/24": [
                    {
                        "prefix": "203.0.113.0/24",
                        "vrfName": "default",
                        "protocol": "bgp",
                        "selected": True,
                        "offloaded": True,
                        "failed": True,
                    },
                ],
                "198.51.100.0/24": [
                    {
                        "prefix": "198.51.100.0/24",
                        "vrfName": "default",
                        "protocol": "bgp",
                        "selected": True,
                        "offloaded": False,
                        "failed": True,
                    },
                ],
            },
        },
        RESULT: {
            ASIC0: {
                "failed_FRR_routes": [
                    {
                        "prefix": "203.0.113.0/24",
                        "vrfName": "default",
                        "protocol": "bgp",
                        "selected": True,
                        "offloaded": True,
                        "failed": True,
                    },
                    {
                        "prefix": "198.51.100.0/24",
                        "vrfName": "default",
                        "protocol": "bgp",
                        "selected": True,
                        "offloaded": False,
                        "failed": True,
                    },
                ],
            },
        },
    },

}

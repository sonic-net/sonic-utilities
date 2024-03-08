DESCR = "Description"
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

OP_SET = "SET"
OP_DEL = "DEL"

NEIGH_TABLE = 'NEIGH_TABLE'
ROUTE_TABLE = 'ROUTE_TABLE'
VNET_ROUTE_TABLE = 'VNET_ROUTE_TABLE'
INTF_TABLE = 'INTF_TABLE'
RT_ENTRY_TABLE = 'ASIC_STATE'
SEPARATOR = ":"
DEVICE_METADATA = "DEVICE_METADATA"
MUX_CABLE = "MUX_CABLE"

LOCALHOST = "localhost"

RT_ENTRY_KEY_PREFIX = 'SAI_OBJECT_TYPE_ROUTE_ENTRY:{\"dest":\"'
RT_ENTRY_KEY_SUFFIX = '\",\"switch_id\":\"oid:0x21000000000000\",\"vr\":\"oid:0x3000000000023\"}'

DEFAULT_CONFIG_DB = {DEVICE_METADATA: {LOCALHOST: {}}}

TEST_DATA = {
    "0": {
        DESCR: "basic good one",
        ARGS: "route_check -m INFO -i 1000",
        PRE: {
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
    },
    "1": {
        DESCR: "With updates",
        ARGS: "route_check -m DEBUG -i 1",
        PRE: {
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
        },
        UPD: {
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
    },
    "2": {
        DESCR: "basic failure one",
        ARGS: "route_check -i 15",
        RET: -1,
        PRE: {
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
        },
        RESULT: {
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
    },
    "3": {
        DESCR: "basic good one with no args",
        ARGS: "route_check",
        PRE: {
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
    },
    "4": {
        DESCR: "Good one with routes on voq inband interface",
        ARGS: "route_check",
        PRE: {
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
    },
    "5": {
        DESCR: "local route with nexthop - fail",
        ARGS: "route_check -m INFO -i 1000",
        RET: -1,
        PRE: {
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
        },
        RESULT: {
            "missed_ROUTE_TABLE_routes": [
                "10.10.196.30/31"
            ]
        }
    },
    "6": {
        DESCR: "Good one with VNET routes",
        ARGS: "route_check",
        PRE: {
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
    },
    "7": {
        DESCR: "dualtor standalone tunnel route case",
        ARGS: "route_check",
        PRE: {
            CONFIG_DB: {
                DEVICE_METADATA: {
                    LOCALHOST: {"subtype": "DualToR"}
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
    },
    "8": {
        DESCR: "Good one with VRF routes",
        ARGS: "route_check",
        PRE: {
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
    },
    "9": {
        DESCR: "SOC IPs on Libra ToRs should be ignored",
        ARGS: "route_check",
        PRE: {
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
    },
    "10": {
        DESCR: "basic good one, check FRR routes",
        ARGS: "route_check -m INFO -i 1000",
        PRE: {
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
        FRR_ROUTES: {
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
        },
    },
    "11": {
        DESCR: "failure test case, missing FRR routes",
        ARGS: "route_check -m INFO -i 1000",
        PRE: {
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
        FRR_ROUTES: {
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
        RESULT: {
            "missed_FRR_routes": [
                {"prefix": "10.10.196.12/31", "vrfName": "default", "protocol": "bgp", "selected": True},
                {"prefix": "1.1.1.0/24", "vrfName": "default", "protocol": "static", "selected": True},
            ],
        },
        RET: -1,
    },
    "12": {
        DESCR: "skip bgp routes offloaded check, if not selected as best",
        ARGS: "route_check -m INFO -i 1000",
        PRE: {
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
        FRR_ROUTES: {
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
    "13": {
        DESCR: "basic good one with IPv6 address",
        ARGS: "route_check -m INFO -i 1000",
        PRE: {
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
    },
    "14": {
        DESCR: "dualtor ignore vlan neighbor route miss case",
        ARGS: "route_check -i 15",
        RET: -1,
        PRE: {
            CONFIG_DB: {
                DEVICE_METADATA: {
                    LOCALHOST: {"subtype": "DualToR"}
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
        },
        RESULT: {
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
    },
}

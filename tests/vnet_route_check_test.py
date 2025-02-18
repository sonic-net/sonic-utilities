import copy
import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.append("scripts")
import vnet_route_check

DESCR = "Description"
ARGS = "args"
RET = "return"
APPL_DB = 0
ASIC_DB = 1
CNTR_DB = 2
STATE_DB = 6
PRE = "pre-value"
UPD = "update"
RESULT = "res"

OP_SET = "SET"
OP_DEL = "DEL"

VXLAN_TUNNEL_TABLE = "VXLAN_TUNNEL_TABLE"
VNET_TABLE = "VNET_TABLE"
VNET_ROUTE_TABLE = "VNET_ROUTE_TABLE"
INTF_TABLE = "INTF_TABLE"
ASIC_STATE = "ASIC_STATE"
VNET_ROUTE_TUNNEL_TABLE = "VNET_ROUTE_TUNNEL_TABLE"
RT_ENTRY_KEY_PREFIX = 'SAI_OBJECT_TYPE_ROUTE_ENTRY:{\"dest":\"'
RT_ENTRY_KEY_SUFFIX = '\",\"switch_id\":\"oid:0x21000000000000\",\"vr\":\"oid:0x3000000000d4b\"}'

current_test_name = None
current_test_no = None
current_test_data = None

tables_returned = {}

test_data = {
    "0": {
        DESCR: "All VNET routes are configured in both APP and ASIC DBs",
        ARGS: "vnet_route_check --all",
        PRE: {
            APPL_DB: {
                VXLAN_TUNNEL_TABLE: {
                    "tunnel_v4": {"src_ip": "10.1.0.32"}
                },
                VNET_TABLE: {
                    "Vnet1": {"vxlan_tunnel": "tunnel_v4", "vni": "10001"}
                },
                INTF_TABLE: {
                    "Vlan3001": {"vnet_name": "Vnet1"},
                    "Vlan3001:30.1.10.1/24": {}
                },
                VNET_ROUTE_TABLE: {
                    "Vnet1:30.1.10.0/24": {"ifname": "Vlan3001"},
                    "Vnet1:50.1.1.0/24": {"ifname": "Vlan3001"},
                    "Vnet1:50.2.2.0/24": {"ifname": "Vlan3001"}
                }
            },
            ASIC_DB: {
                ASIC_STATE: {
                    RT_ENTRY_KEY_PREFIX + "30.1.10.0/24" + RT_ENTRY_KEY_SUFFIX: {},
                    RT_ENTRY_KEY_PREFIX + "50.1.1.0/24" + RT_ENTRY_KEY_SUFFIX: {},
                    RT_ENTRY_KEY_PREFIX + "50.2.2.0/24" + RT_ENTRY_KEY_SUFFIX: {},
                    "SAI_OBJECT_TYPE_ROUTER_INTERFACE:oid:0x6000000000d76": {
                        "SAI_ROUTER_INTERFACE_ATTR_VIRTUAL_ROUTER_ID": "oid:0x3000000000d4b"
                    }
                }
            },
            CNTR_DB: {
                "COUNTERS_RIF_NAME_MAP": {"Vlan3001": "oid:0x6000000000d76"}
            },
            STATE_DB: {
                VNET_ROUTE_TUNNEL_TABLE: {
                    "Vnet1|30.1.10.0/24": [("active_endpoints", ""), ("state", "inactive")],
                    "Vnet1|50.1.1.0/24": [("active_endpoints", ""), ("state", "inactive")],
                    "Vnet1|50.2.2.0/24": [("active_endpoints", ""), ("state", "inactive")]
                }
            }
        }
    },
    "1": {
        DESCR: "VNET route is missed in ASIC DB",
        ARGS: "vnet_route_check -a",
        RET: -1,
        PRE: {
            APPL_DB: {
                VXLAN_TUNNEL_TABLE: {
                    "tunnel_v4": {"src_ip": "10.1.0.32"}
                },
                VNET_TABLE: {
                    "Vnet1": {"vxlan_tunnel": "tunnel_v4", "vni": "10001"}
                },
                INTF_TABLE: {
                    "Vlan3001": {"vnet_name": "Vnet1"},
                    "Vlan3001:30.1.10.1/24": {}
                },
                VNET_ROUTE_TABLE: {
                    "Vnet1:30.1.10.0/24": {"ifname": "Vlan3001"},
                    "Vnet1:50.1.1.0/24": {"ifname": "Vlan3001"},
                    "Vnet1:50.2.2.0/24": {"ifname": "Vlan3001"}
                }
            },
            ASIC_DB: {
                ASIC_STATE: {
                    RT_ENTRY_KEY_PREFIX + "30.1.10.0/24" + RT_ENTRY_KEY_SUFFIX: {},
                    RT_ENTRY_KEY_PREFIX + "50.1.1.0/24" + RT_ENTRY_KEY_SUFFIX: {},
                    "SAI_OBJECT_TYPE_ROUTER_INTERFACE:oid:0x6000000000d76": {
                        "SAI_ROUTER_INTERFACE_ATTR_VIRTUAL_ROUTER_ID": "oid:0x3000000000d4b"
                    }
                }
            },
            CNTR_DB: {
                "COUNTERS_RIF_NAME_MAP": {"Vlan3001": "oid:0x6000000000d76"}
            },
            STATE_DB: {
                VNET_ROUTE_TUNNEL_TABLE: {
                    "Vnet1|30.1.10.0/24": [("active_endpoints", ""), ("state", "inactive")],
                    "Vnet1|50.1.1.0/24": [("active_endpoints", "30.1.10.10"), ("state", "active")],
                    "Vnet1|50.2.2.0/24": [("active_endpoints", ""), ("state", "inactive")]
                }
            }
        },
        RESULT: {
            "results": {
                "missed_in_asic_db_routes": {
                    "Vnet1": {
                        "routes": [
                            "50.2.2.0/24"
                        ]
                    }
                }
            }
        }
    },
    "2": {
        DESCR: "VNET route is missed in APP DB",
        ARGS: "vnet_route_check -a",
        RET: -1,
        PRE: {
            APPL_DB: {
                VXLAN_TUNNEL_TABLE: {
                    "tunnel_v4": {"src_ip": "10.1.0.32"}
                },
                VNET_TABLE: {
                    "Vnet1": {"vxlan_tunnel": "tunnel_v4", "vni": "10001"}
                },
                INTF_TABLE: {
                    "Vlan3001": {"vnet_name": "Vnet1"},
                    "Vlan3001:30.1.10.1/24": {}
                },
                VNET_ROUTE_TABLE: {
                    "Vnet1:30.1.10.0/24": {"ifname": "Vlan3001"},
                    "Vnet1:50.1.1.0/24": {"ifname": "Vlan3001"},
                }
            },
            ASIC_DB: {
                ASIC_STATE: {
                    RT_ENTRY_KEY_PREFIX + "30.1.10.0/24" + RT_ENTRY_KEY_SUFFIX: {},
                    RT_ENTRY_KEY_PREFIX + "50.1.1.0/24" + RT_ENTRY_KEY_SUFFIX: {},
                    RT_ENTRY_KEY_PREFIX + "50.2.2.0/24" + RT_ENTRY_KEY_SUFFIX: {},
                    "SAI_OBJECT_TYPE_ROUTER_INTERFACE:oid:0x6000000000d76": {
                        "SAI_ROUTER_INTERFACE_ATTR_VIRTUAL_ROUTER_ID": "oid:0x3000000000d4b"
                    }
                }
            },
            CNTR_DB: {
                "COUNTERS_RIF_NAME_MAP": {"Vlan3001": "oid:0x6000000000d76"}
            },
            STATE_DB: {
                VNET_ROUTE_TUNNEL_TABLE: {
                    "Vnet1|30.1.10.0/24": [("active_endpoints", "30.1.10.5"), ("state", "active")],
                    "Vnet1|50.1.1.0/24": [("active_endpoints", "30.1.10.10"), ("state", "active")]
                }
            }
        },
        RESULT: {
            "results": {
                "missed_in_app_db_routes": {
                    "Vnet1": {
                        "routes": [
                            "50.2.2.0/24"
                        ]
                    }
                }
            }
        }
    },
    "3": {
        DESCR: "VNET routes are missed in both ASIC and APP DB",
        ARGS: "vnet_route_check -a",
        RET: -1,
        PRE: {
            APPL_DB: {
                VXLAN_TUNNEL_TABLE: {
                    "tunnel_v4": {"src_ip": "10.1.0.32"}
                },
                VNET_TABLE: {
                    "Vnet1": {"vxlan_tunnel": "tunnel_v4", "vni": "10001"}
                },
                INTF_TABLE: {
                    "Vlan3001": {"vnet_name": "Vnet1"},
                    "Vlan3001:30.1.10.1/24": {}
                },
                VNET_ROUTE_TABLE: {
                    "Vnet1:30.1.10.0/24": {"ifname": "Vlan3001"},
                    "Vnet1:50.1.1.0/24": {"ifname": "Vlan3001"},
                }
            },
            ASIC_DB: {
                ASIC_STATE: {
                    RT_ENTRY_KEY_PREFIX + "30.1.10.0/24" + RT_ENTRY_KEY_SUFFIX: {},
                    RT_ENTRY_KEY_PREFIX + "50.2.2.0/24" + RT_ENTRY_KEY_SUFFIX: {},
                    "SAI_OBJECT_TYPE_ROUTER_INTERFACE:oid:0x6000000000d76": {
                        "SAI_ROUTER_INTERFACE_ATTR_VIRTUAL_ROUTER_ID": "oid:0x3000000000d4b"
                    }
                }
            },
            CNTR_DB: {
                "COUNTERS_RIF_NAME_MAP": {"Vlan3001": "oid:0x6000000000d76"}
            },
            STATE_DB: {
                VNET_ROUTE_TUNNEL_TABLE: {
                    "Vnet1|30.1.10.0/24": [("active_endpoints", ""), ("state", "inactive")],
                    "Vnet1|50.1.1.0/24": [("active_endpoints", ""), ("state", "inactive")]
                }
            }
        },
        RESULT: {
            "results": {
                "missed_in_app_db_routes": {
                    "Vnet1": {
                        "routes": [
                            "50.2.2.0/24"
                        ]
                    }
                },
                "missed_in_asic_db_routes": {
                    "Vnet1": {
                        "routes": [
                            "50.1.1.0/24"
                        ]
                    }
                }
            }
        }
    },
    "4": {
        DESCR: "All tunnel routes are configured in both APP and ASIC DB",
        ARGS: "vnet_route_check --all",
        PRE: {
            APPL_DB: {
                VXLAN_TUNNEL_TABLE: {
                    "tunnel_v4": {"src_ip": "10.1.0.32"},
                    "tunnel_v6": {"src_ip": "3001:2000::1"}
                },
                VNET_TABLE: {
                    "Vnet_v4_in_v4-0": [("vxlan_tunnel", "tunnel_v4"), ("scope", "default"), ("vni", "10000"), ("peer_list", "")],
                    "Vnet_v6_in_v6-0": [("vxlan_tunnel", "tunnel_v6"), ("scope", "default"), ("vni", "10002"), ("peer_list", "")]

                },
                VNET_ROUTE_TUNNEL_TABLE: {
                    "Vnet_v4_in_v4-0:150.62.191.1/32": {"endpoint": "100.251.7.1,100.251.7.2"},
                    "Vnet_v6_in_v6-0:fd01:fc00::1/128": {"endpoint": "fc02:1000::1,fc02:1000::2"}

                }
            },
            ASIC_DB: {
                "ASIC_STATE:SAI_OBJECT_TYPE_VIRTUAL_ROUTER": {
                         "oid:0x3000000000d4b": {"": ""}
                },
                ASIC_STATE: {
                    RT_ENTRY_KEY_PREFIX + "150.62.191.1/32" + RT_ENTRY_KEY_SUFFIX: {},
                    RT_ENTRY_KEY_PREFIX + "fd01:fc00::1/128" + RT_ENTRY_KEY_SUFFIX: {}
                }
            },
            STATE_DB: {
                VNET_ROUTE_TUNNEL_TABLE: {
                    "Vnet_v4_in_v4-0|150.62.191.1/32": [("active_endpoints", "100.251.7.1"), ("state", "active")],
                    "Vnet_v6_in_v6-0|fd01:fc00::1/128": [("active_endpoints", "fc02:1000::1"), ("state", "active")]
                }
            }
        }
    },
    "5": {
        DESCR: "Tunnel route present in APP DB but mssing in ASIC DB",
        ARGS: "vnet_route_check -a",
        RET: -1,
        PRE: {
            APPL_DB: {
                VXLAN_TUNNEL_TABLE: {
                    "tunnel_v4": {"src_ip": "10.1.0.32"}
                },
                VNET_TABLE: {
                    "Vnet_v4_in_v4-0": [("vxlan_tunnel", "tunnel_v4"), ("scope", "default"), ("vni", "10000"), ("peer_list", "")]
                },
                VNET_ROUTE_TUNNEL_TABLE: {
                   "Vnet_v4_in_v4-0:150.62.191.1/32": {"endpoint": "100.251.7.1,100.251.7.2"}
                }
            },
            ASIC_DB: {
                "ASIC_STATE:SAI_OBJECT_TYPE_VIRTUAL_ROUTER": {
                         "oid:0x3000000000d4b": {"": ""}
                },
                ASIC_STATE: {
                }
            },
            STATE_DB: {
                VNET_ROUTE_TUNNEL_TABLE: {
                    "Vnet_v4_in_v4-0|150.62.191.1/32": [("active_endpoints", "100.251.7.2"), ("state", "active")]
                }
            }
        },
        RESULT: {
            "results": {
                "missed_in_asic_db_routes": {
                    "Vnet_v4_in_v4-0": {
                        "routes": [
                            "150.62.191.1/32"
                        ]
                    }
                }
            }
        }
    },
    "6": {
        DESCR: "Only Vxlan tunnel configured, No routes.",
        ARGS: "vnet_route_check --all",
        PRE: {
            APPL_DB: {
                VXLAN_TUNNEL_TABLE: {
                    "tunnel_v4": {"src_ip": "10.1.0.32"}
                },
                VNET_TABLE: {
                    "Vnet1": {"vxlan_tunnel": "tunnel_v4", "vni": "10001"}
                },
                INTF_TABLE: {
                    "Vlan3001": {"vnet_name": "Vnet1"},
                    "Vlan3001:30.1.10.1/24": {}
                },
            },
        }
    },
    "7": {
        DESCR: "VNET routes are missed in both ASIC and APP DB, but routes in APP DB are inactive",
        ARGS: "vnet_route_check",
        RET: -1,
        PRE: {
            APPL_DB: {
                VXLAN_TUNNEL_TABLE: {
                    "tunnel_v4": {"src_ip": "10.1.0.32"}
                },
                VNET_TABLE: {
                    "Vnet1": {"vxlan_tunnel": "tunnel_v4", "vni": "10001"}
                },
                INTF_TABLE: {
                    "Vlan3001": {"vnet_name": "Vnet1"},
                    "Vlan3001:30.1.10.1/24": {}
                },
                VNET_ROUTE_TABLE: {
                    "Vnet1:30.1.10.0/24": {"ifname": "Vlan3001"},
                    "Vnet1:50.1.1.0/24": {"ifname": "Vlan3001"},
                }
            },
            ASIC_DB: {
                ASIC_STATE: {
                    RT_ENTRY_KEY_PREFIX + "30.1.10.0/24" + RT_ENTRY_KEY_SUFFIX: {},
                    RT_ENTRY_KEY_PREFIX + "50.2.2.0/24" + RT_ENTRY_KEY_SUFFIX: {},
                    "SAI_OBJECT_TYPE_ROUTER_INTERFACE:oid:0x6000000000d76": {
                        "SAI_ROUTER_INTERFACE_ATTR_VIRTUAL_ROUTER_ID": "oid:0x3000000000d4b"
                    }
                }
            },
            CNTR_DB: {
                "COUNTERS_RIF_NAME_MAP": {"Vlan3001": "oid:0x6000000000d76"}
            },
            STATE_DB: {
                VNET_ROUTE_TUNNEL_TABLE: {
                    "Vnet1|30.1.10.0/24": [("active_endpoints", ""), ("state", "inactive")],
                    "Vnet1|50.1.1.0/24": [("active_endpoints", ""), ("state", "inactive")]
                }
            }
        },
        RESULT: {
            "results": {
                "missed_in_app_db_routes": {
                    "Vnet1": {
                        "routes": [
                            "50.2.2.0/24"
                        ]
                    }
                }
            }
        }
    },
    "8": {
        DESCR: "A VNET route is missed in ASIC DB, but it is inactive",
        ARGS: "vnet_route_check",
        PRE: {
            APPL_DB: {
                VXLAN_TUNNEL_TABLE: {
                    "tunnel_v4": {"src_ip": "10.1.0.32"}
                },
                VNET_TABLE: {
                    "Vnet1": {"vxlan_tunnel": "tunnel_v4", "vni": "10001"}
                },
                INTF_TABLE: {
                    "Vlan3001": {"vnet_name": "Vnet1"},
                    "Vlan3001:30.1.10.1/24": {}
                },
                VNET_ROUTE_TABLE: {
                    "Vnet1:30.1.10.0/24": {"ifname": "Vlan3001"},
                    "Vnet1:50.1.1.0/24": {"ifname": "Vlan3001"},
                }
            },
            ASIC_DB: {
                ASIC_STATE: {
                    RT_ENTRY_KEY_PREFIX + "30.1.10.0/24" + RT_ENTRY_KEY_SUFFIX: {},
                    "SAI_OBJECT_TYPE_ROUTER_INTERFACE:oid:0x6000000000d76": {
                        "SAI_ROUTER_INTERFACE_ATTR_VIRTUAL_ROUTER_ID": "oid:0x3000000000d4b"
                    }
                }
            },
            CNTR_DB: {
                "COUNTERS_RIF_NAME_MAP": {"Vlan3001": "oid:0x6000000000d76"}
            },
            STATE_DB: {
                VNET_ROUTE_TUNNEL_TABLE: {
                    "Vnet1|30.1.10.0/24": [("active_endpoints", "30.1.10.5"), ("state", "active")],
                    "Vnet1|50.1.1.0/24": [("active_endpoints", ""), ("state", "inactive")]
                }
            }
        }
    },
    "9": {
        DESCR: "A VNET route is missed in ASIC DB and it is active",
        ARGS: "vnet_route_check",
        RET: -1,
        PRE: {
            APPL_DB: {
                VXLAN_TUNNEL_TABLE: {
                    "tunnel_v4": {"src_ip": "10.1.0.32"}
                },
                VNET_TABLE: {
                    "Vnet1": {"vxlan_tunnel": "tunnel_v4", "vni": "10001"}
                },
                INTF_TABLE: {
                    "Vlan3001": {"vnet_name": "Vnet1"},
                    "Vlan3001:30.1.10.1/24": {}
                },
                VNET_ROUTE_TABLE: {
                    "Vnet1:30.1.10.0/24": {"ifname": "Vlan3001"},
                    "Vnet1:50.1.1.0/24": {"ifname": "Vlan3001"},
                }
            },
            ASIC_DB: {
                ASIC_STATE: {
                    RT_ENTRY_KEY_PREFIX + "30.1.10.0/24" + RT_ENTRY_KEY_SUFFIX: {},
                    "SAI_OBJECT_TYPE_ROUTER_INTERFACE:oid:0x6000000000d76": {
                        "SAI_ROUTER_INTERFACE_ATTR_VIRTUAL_ROUTER_ID": "oid:0x3000000000d4b"
                    }
                }
            },
            CNTR_DB: {
                "COUNTERS_RIF_NAME_MAP": {"Vlan3001": "oid:0x6000000000d76"}
            },
            STATE_DB: {
                VNET_ROUTE_TUNNEL_TABLE: {
                    "Vnet1|30.1.10.0/24": [("active_endpoints", ""), ("state", "inactive")],
                    "Vnet1|50.1.1.0/24": [("active_endpoints", "30.1.10.10"), ("state", "active")]
                }
            }
        },
        RESULT: {
            "results": {
                "missed_in_asic_db_routes": {
                    "Vnet1": {
                        "routes": [
                            "50.1.1.0/24"
                        ]
                    }
                }
            }
        }
    },
    "10": {
        DESCR: "An IPv6 VNET route is missed in ASIC DB, but it is inactive",
        ARGS: "vnet_route_check",
        PRE: {
            APPL_DB: {
                VXLAN_TUNNEL_TABLE: {
                    "tunnel_v6": {"src_ip": "3001:2000::1"}
                },
                VNET_TABLE: {
                    "Vnet_v6": [("vxlan_tunnel", "tunnel_v6"), ("scope", "default"), ("vni", "10002"),
                                ("peer_list", "")]
                },
                VNET_ROUTE_TABLE: {
                    "Vnet_v6:fd01:fc00::1/128": {"endpoint": "fc02:1000::1,fc02:1000::2"}
                }
            },
            ASIC_DB: {
                ASIC_STATE: {
                    "SAI_OBJECT_TYPE_ROUTER_INTERFACE:oid:0x6000000000d76": {
                        "SAI_ROUTER_INTERFACE_ATTR_VIRTUAL_ROUTER_ID": "oid:0x3000000000d4b"
                    },
                    "SAI_OBJECT_TYPE_VIRTUAL_ROUTER": {
                         "oid:0x3000000000d4b": {"": ""}
                    },
                }
            },
            STATE_DB: {
                VNET_ROUTE_TUNNEL_TABLE: {
                    "Vnet_v6|fd01:fc00::1/128": [("active_endpoints", ""), ("state", "inactive")]
                }
            }
        }
    },
    "11": {
        DESCR: "An IPv6 VNET route is missed in ASIC DB and it is active",
        ARGS: "vnet_route_check",
        RET: -1,
        PRE: {
            APPL_DB: {
                VXLAN_TUNNEL_TABLE: {
                    "tunnel_v6": {"src_ip": "3001:2000::1"}
                },
                VNET_TABLE: {
                    "Vnet_v6": [("vxlan_tunnel", "tunnel_v6"), ("scope", "default"), ("vni", "10002"),
                                ("peer_list", "")]
                },
                VNET_ROUTE_TABLE: {
                    "Vnet_v6:fd01:fc00::1/128": {"endpoint": "fc02:1000::1,fc02:1000::2"}
                }
            },
            ASIC_DB: {
                ASIC_STATE: {
                    "SAI_OBJECT_TYPE_ROUTER_INTERFACE:oid:0x6000000000d76": {
                        "SAI_ROUTER_INTERFACE_ATTR_VIRTUAL_ROUTER_ID": "oid:0x3000000000d4b"
                    },
                    "SAI_OBJECT_TYPE_VIRTUAL_ROUTER": {
                         "oid:0x3000000000d4b": {"": ""}
                    },
                }
            },
            STATE_DB: {
                VNET_ROUTE_TUNNEL_TABLE: {
                    "Vnet_v6|fd01:fc00::1/128": [("active_endpoints", "fc02:1000::2"), ("state", "active")]
                }
            }
        },
        RESULT: {
            "results": {
                "missed_in_asic_db_routes": {
                    "Vnet_v6": {
                        "routes": [
                            "fd01:fc00::1/128"
                        ]
                    }
                }
            }
        }
    },
    "12": {
        DESCR: "An IPv6 VNET route that is missing in STATE DB and ASIC DB",
        ARGS: "vnet_route_check",
        RET: -1,
        PRE: {
            APPL_DB: {
                VXLAN_TUNNEL_TABLE: {
                    "tunnel_v6": {"src_ip": "3001:2000::1"}
                },
                VNET_TABLE: {
                    "Vnet_v6": [("vxlan_tunnel", "tunnel_v6"), ("scope", "default"), ("vni", "10002"),
                                ("peer_list", "")]
                },
                VNET_ROUTE_TABLE: {
                    "Vnet_v6:fd01:fc00::1/128": {"endpoint": "fc02:1000::1,fc02:1000::2"}
                }
            },
            ASIC_DB: {
                ASIC_STATE: {
                    "SAI_OBJECT_TYPE_ROUTER_INTERFACE:oid:0x6000000000d76": {
                        "SAI_ROUTER_INTERFACE_ATTR_VIRTUAL_ROUTER_ID": "oid:0x3000000000d4b"
                    },
                    "SAI_OBJECT_TYPE_VIRTUAL_ROUTER": {
                         "oid:0x3000000000d4b": {"": ""}
                    },
                }
            }
        },
        RESULT: {
            "results": {
                "missed_in_asic_db_routes": {
                    "Vnet_v6": {
                        "routes": [
                            "fd01:fc00::1/128"
                        ]
                    }
                }
            }
        }
    },
    "13": {
        DESCR: "A VNET route is missing in ASIC DB and STATE DB, and another inactive route is missing in ASIC DB",
        ARGS: "vnet_route_check",
        PRE: {
            APPL_DB: {
                VXLAN_TUNNEL_TABLE: {
                    "tunnel_v4": {"src_ip": "10.1.0.32"}
                },
                VNET_TABLE: {
                    "Vnet1": {"vxlan_tunnel": "tunnel_v4", "vni": "10001"}
                },
                INTF_TABLE: {
                    "Vlan3001": {"vnet_name": "Vnet1"},
                    "Vlan3001:30.1.10.1/24": {}
                },
                VNET_ROUTE_TABLE: {
                    "Vnet1:30.1.10.0/24": {"ifname": "Vlan3001"},
                    "Vnet1:50.1.1.0/24": {"ifname": "Vlan3001"},
                }
            },
            ASIC_DB: {
                ASIC_STATE: {
                    RT_ENTRY_KEY_PREFIX + "30.1.10.0/24" + RT_ENTRY_KEY_SUFFIX: {},
                    "SAI_OBJECT_TYPE_ROUTER_INTERFACE:oid:0x6000000000d76": {
                        "SAI_ROUTER_INTERFACE_ATTR_VIRTUAL_ROUTER_ID": "oid:0x3000000000d4b"
                    }
                }
            },
            CNTR_DB: {
                "COUNTERS_RIF_NAME_MAP": {"Vlan3001": "oid:0x6000000000d76"}
            },
            STATE_DB: {
                VNET_ROUTE_TUNNEL_TABLE: {
                    "Vnet1|50.1.1.0/24": [("active_endpoints", ""), ("state", "inactive")]
                }
            }
        }
    }
}


def do_start_test(tname, tno, ctdata):
    global current_test_name, current_test_no, current_test_data
    global tables_returned

    current_test_name = tname
    current_test_no = tno
    current_test_data = ctdata
    tables_returned = {}

    print("Starting test case {} number={}".format(tname, tno))


class Table:
    def __init__(self, db, tbl):
        self.db = db
        self.tbl = tbl
        self.data = copy.deepcopy(self.get_val(current_test_data[PRE], [db, tbl]))

    def get_val(self, d, keys):
        for k in keys:
            d = d[k] if k in d else {}
        return d

    def getKeys(self):
        return list(self.data.keys())

    def get(self, key):
        ret = copy.deepcopy(self.data.get(key, self.data))
        return (True, ret)


db_conns = {"APPL_DB": APPL_DB, "ASIC_DB": ASIC_DB, "COUNTERS_DB": CNTR_DB, "STATE_DB": STATE_DB}


def conn_side_effect(arg, _, __):
    return db_conns[arg]


def table_side_effect(db, tbl):
    if not db in tables_returned:
        tables_returned[db] = {}
    if not tbl in tables_returned[db]:
        tables_returned[db][tbl] = Table(db, tbl)
    return tables_returned[db][tbl]


class mock_db_conn:
    def __init__(self, db):
        self.db_name = None
        for (k, v) in db_conns.items():
            if v == db:
                self.db_name = k
        assert self.db_name != None

    def getDbName(self):
        return self.db_name


def set_mock(mock_table, mock_conn):
    mock_conn.side_effect = conn_side_effect
    mock_table.side_effect = table_side_effect


class TestVnetRouteCheck(object):
    def setup(self):
        pass

    def init(self):
        vnet_route_check.UNIT_TESTING = 1

    @patch("vnet_route_check.swsscommon.DBConnector")
    @patch("vnet_route_check.swsscommon.Table")
    def test_vnet_route_check(self, mock_table, mock_conn):
        self.init()
        ret = 0

        set_mock(mock_table, mock_conn)
        for (i, ct_data) in test_data.items():
            do_start_test("route_test", i, ct_data)

            with patch('sys.argv', ct_data[ARGS].split()):
                expect_ret = ct_data[RET] if RET in ct_data else 0
                expect_res = ct_data[RESULT] if RESULT in ct_data else None
                res = None
                if expect_ret == 0:
                    ret = vnet_route_check.main()
                    if ret != 0:
                        ret, res = vnet_route_check.main()
                else:
                    ret, res = vnet_route_check.main()
                if res:
                    print("res={}".format(json.dumps(res, indent=4)))
                if expect_res:
                    print("expect_res={}".format(json.dumps(expect_res, indent=4)))
                assert ret == expect_ret
                assert res == expect_res

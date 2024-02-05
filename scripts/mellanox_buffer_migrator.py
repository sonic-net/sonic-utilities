"""
Mellanox buffer migrator:
    Migrate buffer configuration to the default one in the new version automatically
    if the configuration matched the default on in the old version.

    Current version: 2.0.0 for shared headroom pool and dynamic buffer calculation support.
    Historical version:
     - 201911:
       - 1.0.6 for 2km cable support
       - 1.0.5 for shared headroom pool support
       - 1.0.4 for optimized headroom calculation:
          - For Microsoft SKUs, calculate headroom with small packet percentage as 50%
          - For all SKUs, fix some bugs in the formula
       - 1.0.3 for updating the buffer pool size according to the SDK update
     - 201811:
       - 1.0.2 initial version. Also used in early 201911.

    The dict mellanox_default_parameter is introduced to represent:
     - The default configuration of BUFFER_POOL and BUFFER_PROFILE for all versions
     - The mapping from the old version to new version
       In each version there are variant configuration sets according to the topology, SKU, platform, etc.
       It's possible that there are more flavors in old version and less flavors in the new one or vice versa.
       In both case, a mapping is required to map from the old version to the new version.

    It includes the following data for each of the version (Mandatory except explicitly mentioned)
     - pool_configuration_list: Optional.
         Represents all the flavors of the pool configuration
         Not providing it means all items in buffer_pools will be checked.
     - pool_mapped_from_old_version: Optional.
         A dict represents the mapping from a flavor of buffer pool configuration in the old version to that in the new one
         Not having this field means all the flavors in the old version will be mapped to that in the new version with the same name
         The keys are the name of flavors and the data can be in the following forms:
           - a string, representing the name of the flavor to which the key is mapped in the new version
           - a tuple consisting of:
              - a "type" which can be "sku" only for now (probably support "platform" in the future)
              - a "map" which should be a key in pool_convert_map. The map represents to which flavor the current flavor will be mapped according to the device's SKU
     - pool_convert_map: Optional.
         A map from SKU to flavor in the new image. Referenced by pool_mapped_from_old_version. (see above for details)
     - buffer_pool_list: The list of buffer pools in each flavor. For testing whether the configuration in old version matches one of the default
     - buffer_pools: The detailed information of each flavor of the pools
         Most of the pools in each flavor share the same number. To avoid repeating code the pool info is represented in a "condensed" way.
         Basically, each flavor has the following convention:
           flavor: {"doublepool|singlepool": { "size": <size>, "xoff": <xoff>}, "egress_lossless_pool": { "size": <size>}}
           doublepool: The flavor has two ingress pools. Each pool's size is <size>. There won't be size in the pool if <size> is "dynamic".
                       The field "xoff" is optional. Providing it means the xoff of ingress_lossless_pool is <xoff>.
           singlepool: The same as doublepool except that the flavor has only one ingress pools
           egress_lossless_pool: The size of egress_lossless_pool.
     - buffer_pools_inherited: Optional. If the current pool has the same pool configurations as that in an old version, we don't need to repeat it.
         It's a dict object, containing the list of names of flavors of buffer pool configuration inherited from the version whose name is the key.

     - headrooms: Optional. A dict representing the headrooms of different series of platforms, including the following keys:
        - spc1_headroom: Represents headroom data for all SPC1 switches
        - spc2_headroom: Represents headroom data for all SPC2 switches except 3800
        - spc2_3800_headroom: Represents headroom data for 3800 switch (for gearbox)
        - spc3_headroom: Represents headroom data for all SPC3 switches
       Value for each of the above keys is an object, including the following type:
        - default: The default headroom information for generic SKUs.
        - msft: The headroom info for MSFT SKUs, calculated with dedicated parameters for MSFT
        - shp: The default headroom with shared headroom pool support. Based on msft parameters and size == xon
       Each of the above object can be:
        - A dict object. In this case, it represents the headroom info.
          The key is the profile name with convention "pg_lossless_<speed>_<cable-length>_profile" and the object is a dict containing the size and xon or xoff and xon. The other value can be deducted.
        - A tuple. This is a backtrace pointer, consisting of the version and the key to the headroom.
          It means the headroom info is exactly the same as that in a previous version.
          For example, ("version_1_0_4", "spc1_headroom") means the headroom info is the same as param["version_1_0_4"]["headrooms"]["spc1_headroom"]["default"]
        Besides the spcxxx_headroom, there is a mappings dict in the headrooms, representing to which headroom info the old headroom should be mapped.
        For example, in the following example,
         - the headroom info "msft" in the old version should be mapped to "msft" in the new version
         - the headroom info "default" in the old version should be mapped to "msft" in the new version if the SKU is Mellanox-xxxx or "default" otherwise
                "mapping": {
                    "default": ("skumap", {"Mellanox-SN2700": "msft", "Mellanox-SN2700-C28D8": "msft", "Mellanox-SN2700-D48C8": "msft"})
                },

     - buffer_profiles: Optional. A dict representing the default buffer profile configuration in the current version.
       There are following flavors:
        - default: The default buffer profile configuration for generic SKUs
        - singlepool: The buffer profile configuration for MSFT SKUs which has only one ingress pool.
       During migration, if the profiles match one of the flavor in the old version, it will be migrated to the new flavor with the same name
       Not providing it means no buffer profile migration required.
"""
from sonic_py_common import logger
import re

SYSLOG_IDENTIFIER = 'mellanox_buffer_migrator'

# Global logger instance
log = logger.Logger(SYSLOG_IDENTIFIER)

class MellanoxBufferMigrator():
    def __init__(self, configDB, appDB, stateDB):
        self.configDB = configDB
        self.appDB = appDB
        self.stateDB = stateDB

        self.platform = None
        self.sku = None

        device_data = self.configDB.get_entry('DEVICE_METADATA', 'localhost')
        if device_data:
            self.platform = device_data.get('platform')
            self.sku = device_data.get('hwsku')
            self.ready = True
        if not self.platform or not self.sku:
            log.log_notice("Trying to get DEVICE_METADATA from DB but doesn't exist, skip migration")
            self.ready = False

        self.spc1_platforms = ["x86_64-mlnx_msn2010-r0", "x86_64-mlnx_msn2100-r0", "x86_64-mlnx_msn2410-r0", "x86_64-mlnx_msn2700-r0", "x86_64-mlnx_msn2740-r0"]
        self.spc2_platforms = ["x86_64-mlnx_msn3700-r0", "x86_64-mlnx_msn3700c-r0"]
        self.spc3_platforms = ["x86_64-mlnx_msn4600-r0", "x86_64-mlnx_msn4600c-r0", "x86_64-mlnx_msn4700-r0"]

        msftskus = ["Mellanox-SN2700", "Mellanox-SN2700-C28D8", "Mellanox-SN2700-D48C8", "Mellanox-SN2700-D40C8S8",
                    "Mellanox-SN3800-C64", "Mellanox-SN3800-D24C52", "Mellanox-SN3800-D112C8", "Mellanox-SN3800-D28C50"]

        self.is_msft_sku = self.sku in msftskus

        self.pending_update_items = list()
        self.default_speed_list = ['1000', '10000', '25000', '40000', '50000', '100000', '200000', '400000']
        self.default_cable_len_list = ['5m', '40m', '300m']
        self.is_buffer_config_default = True
        self.is_buffer_config_empty = False

    mellanox_default_parameter = {
        "version_1_0_2": {
            # This is the buffer configuration from the very beginning
            # Buffer pool configuration info
            "buffer_pool_list" : ['ingress_lossless_pool', 'egress_lossless_pool', 'ingress_lossy_pool', 'egress_lossy_pool'],
            # Default buffer pools
            "buffer_pools": {
                "spc1_t0_pool": {"ingress_lossless_pool": { "size": "4194304", "type": "ingress", "mode": "dynamic" },
                                 "ingress_lossy_pool": { "size": "7340032", "type": "ingress", "mode": "dynamic" },
                                 "egress_lossless_pool": { "size": "16777152", "type": "egress", "mode": "dynamic" },
                                 "egress_lossy_pool": {"size": "7340032", "type": "egress", "mode": "dynamic" } },
                "spc1_t1_pool": {"ingress_lossless_pool": { "size": "2097152", "type": "ingress", "mode": "dynamic" },
                                 "ingress_lossy_pool": { "size": "5242880", "type": "ingress", "mode": "dynamic" },
                                 "egress_lossless_pool": { "size": "16777152", "type": "egress", "mode": "dynamic" },
                                 "egress_lossy_pool": {"size": "5242880", "type": "egress", "mode": "dynamic" } },
                "spc2_t0_pool": {"doublepool": { "size": "8224768" }, "egress_lossless_pool": { "size": "35966016"}},
                "spc2_t1_pool": {"doublepool": { "size": "12042240" }, "egress_lossless_pool": { "size": "35966016"}},

                # buffer pools with shared headroom pool supported
                "spc1_t0_pool_shp": {"doublepool": { "size": "3988992" }, "egress_lossless_pool": { "size": "13945824"}},
                "spc1_t1_pool_shp": {"doublepool": { "size": "4554240" }, "egress_lossless_pool": { "size": "13945824"}}
            }
        },
        "version_1_0_3": {
            # On Mellanox platform the buffer pool size changed since
            # version with new SDK 4.3.3052, SONiC to SONiC update
            # from version with old SDK will be broken without migration.
            "pool_mapped_from_old_version": {
                "spc1_t0_pool_shp": "spc1_t0_pool",
                "spc1_t1_pool_shp": "spc1_t1_pool"
            },

            # Buffer pool configuration info
            "buffer_pool_list" : ['ingress_lossless_pool', 'egress_lossless_pool', 'ingress_lossy_pool', 'egress_lossy_pool'],
            "buffer_pools": {
                "spc1_t0_pool": {"doublepool": { "size": "5029836" }, "egress_lossless_pool": { "size": "14024599"}},
                "spc1_t1_pool": {"doublepool": { "size": "2097100" }, "egress_lossless_pool": { "size": "14024599"}},
                "spc2_t0_pool": {"doublepool": { "size": "14983147" }, "egress_lossless_pool": { "size": "34340822"}},
                "spc2_t1_pool": {"doublepool": { "size": "9158635" }, "egress_lossless_pool": { "size": "34340822"}}
            },

            "headrooms": {
                # Lossless headroom info
                "spc1_headroom": {
                    "default": {"pg_lossless_10000_5m_profile": {"size": "34816", "xon": "18432"},
                                "pg_lossless_25000_5m_profile": {"size": "34816", "xon": "18432"},
                                "pg_lossless_40000_5m_profile": {"size": "34816", "xon": "18432"},
                                "pg_lossless_50000_5m_profile": {"size": "34816", "xon": "18432"},
                                "pg_lossless_100000_5m_profile": {"size": "36864", "xon": "18432"},
                                "pg_lossless_10000_40m_profile": {"size": "36864", "xon": "18432"},
                                "pg_lossless_25000_40m_profile": {"size": "39936", "xon": "18432"},
                                "pg_lossless_40000_40m_profile": {"size": "41984", "xon": "18432"},
                                "pg_lossless_50000_40m_profile": {"size": "41984", "xon": "18432"},
                                "pg_lossless_100000_40m_profile": {"size": "54272", "xon": "18432"},
                                "pg_lossless_10000_300m_profile": {"size": "49152", "xon": "18432"},
                                "pg_lossless_25000_300m_profile": {"size": "71680", "xon": "18432"},
                                "pg_lossless_40000_300m_profile": {"size": "94208", "xon": "18432"},
                                "pg_lossless_50000_300m_profile": {"size": "94208", "xon": "18432"},
                                "pg_lossless_100000_300m_profile": {"size": "184320", "xon": "18432"}}
                },
                "spc2_headroom": {
                    "default": {"pg_lossless_1000_5m_profile": {"size": "35840", "xon": "18432"},
                                "pg_lossless_10000_5m_profile": {"size": "36864", "xon": "18432"},
                                "pg_lossless_25000_5m_profile": {"size": "36864", "xon": "18432"},
                                "pg_lossless_40000_5m_profile": {"size": "36864", "xon": "18432"},
                                "pg_lossless_50000_5m_profile": {"size": "37888", "xon": "18432"},
                                "pg_lossless_100000_5m_profile": {"size": "38912", "xon": "18432"},
                                "pg_lossless_200000_5m_profile": {"size": "41984", "xon": "18432"},
                                "pg_lossless_1000_40m_profile": {"size": "36864", "xon": "18432"},
                                "pg_lossless_10000_40m_profile": {"size": "38912", "xon": "18432"},
                                "pg_lossless_25000_40m_profile": {"size": "41984", "xon": "18432"},
                                "pg_lossless_40000_40m_profile": {"size": "45056", "xon": "18432"},
                                "pg_lossless_50000_40m_profile": {"size": "47104", "xon": "18432"},
                                "pg_lossless_100000_40m_profile": {"size": "59392", "xon": "18432"},
                                "pg_lossless_200000_40m_profile": {"size": "81920", "xon": "18432"},
                                "pg_lossless_1000_300m_profile": {"size": "37888", "xon": "18432"},
                                "pg_lossless_10000_300m_profile": {"size": "53248", "xon": "18432"},
                                "pg_lossless_25000_300m_profile": {"size": "78848", "xon": "18432"},
                                "pg_lossless_40000_300m_profile": {"size": "104448", "xon": "18432"},
                                "pg_lossless_50000_300m_profile": {"size": "121856", "xon": "18432"},
                                "pg_lossless_100000_300m_profile": {"size": "206848", "xon": "18432"},
                                "pg_lossless_200000_300m_profile": {"size": "376832", "xon": "18432"}}
                }
            },

            # Buffer profile info
            "buffer_profiles": {
                "default": {"ingress_lossless_profile": {"dynamic_th": "0", "pool": "[BUFFER_POOL|ingress_lossless_pool]", "size": "0"},
                            "ingress_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|ingress_lossy_pool]", "size": "0"},
                            "egress_lossless_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|egress_lossless_pool]", "size": "0"},
                            "egress_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|egress_lossy_pool]", "size": "4096"},
                            "q_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|egress_lossy_pool]", "size": "0"}}
            }
        },
        "version_1_0_4": {
            # Version 1.0.4 is introduced for updating the buffer settings
            # Buffer pool info for normal mode
            "buffer_pool_list" : ['ingress_lossless_pool', 'ingress_lossy_pool', 'egress_lossless_pool', 'egress_lossy_pool'],
            "buffer_pools": {
                "spc1_t0_pool": {"doublepool": { "size": "4580864" }, "egress_lossless_pool": { "size": "13945824"}},
                "spc1_t1_pool": {"doublepool": { "size": "3302912" }, "egress_lossless_pool": { "size": "13945824"}},
                "spc2_t0_pool": {"doublepool": { "size": "14542848" }, "egress_lossless_pool": { "size": "34287552"}},
                "spc2_t1_pool": {"doublepool": { "size": "11622400" }, "egress_lossless_pool": { "size": "34287552"}},

                # The following pools are used only for migrating from 1.0.4 to newer version
                "spc1_2700_t0_pool": {"singlepool": {"size": "9489408"}, "egress_lossless_pool": {"size": "13945824"}},
                "spc1_2700_t1_pool": {"singlepool": {"size": "7719936"}, "egress_lossless_pool": {"size": "13945824"}},
                "spc1_2700-d48c8_t0_pool": {"singlepool": {"size": "6687744"}, "egress_lossless_pool": {"size": "13945824"}},
                "spc1_2700-d48c8_t1_pool": {"singlepool": {"size": "8506368"}, "egress_lossless_pool": {"size": "13945824"}},

                # SPC3 is used only when migrating from 1.0.4 to newer version
                "spc3_t0_pool": {"doublepool": { "size": "26451968" }, "egress_lossless_pool": { "size": "60817392" }},
                "spc3_t1_pool": {"doublepool": { "size": "20627456" }, "egress_lossless_pool": { "size": "60817392" }}
            },

            "headrooms": {
                # Lossless headroom info
                "spc1_headroom":{
                    "default": {"pg_lossless_10000_5m_profile": {"size": "49152", "xon":"19456"},
                                "pg_lossless_25000_5m_profile": {"size": "49152", "xon":"19456"},
                                "pg_lossless_40000_5m_profile": {"size": "49152", "xon":"19456"},
                                "pg_lossless_50000_5m_profile": {"size": "49152", "xon":"19456"},
                                "pg_lossless_100000_5m_profile": {"size": "50176", "xon":"19456"},
                                "pg_lossless_10000_40m_profile": {"size": "49152", "xon":"19456"},
                                "pg_lossless_25000_40m_profile": {"size": "51200", "xon":"19456"},
                                "pg_lossless_40000_40m_profile": {"size": "52224", "xon":"19456"},
                                "pg_lossless_50000_40m_profile": {"size": "53248", "xon":"19456"},
                                "pg_lossless_100000_40m_profile": {"size": "58368", "xon":"19456"},
                                "pg_lossless_10000_300m_profile": {"size": "56320", "xon":"19456"},
                                "pg_lossless_25000_300m_profile": {"size": "67584", "xon":"19456"},
                                "pg_lossless_40000_300m_profile": {"size": "78848", "xon":"19456"},
                                "pg_lossless_50000_300m_profile": {"size": "86016", "xon":"19456"},
                                "pg_lossless_100000_300m_profile": {"size": "123904", "xon":"19456"}},
                    # Lossless headroom info for MSFT SKUs.
                    "msft": {"pg_lossless_10000_5m_profile": {"size": "41984", "xon":"19456"},
                             "pg_lossless_25000_5m_profile": {"size": "41984", "xon":"19456"},
                             "pg_lossless_40000_5m_profile": {"size": "41984", "xon":"19456"},
                             "pg_lossless_50000_5m_profile": {"size": "41984", "xon":"19456"},
                             "pg_lossless_100000_5m_profile": {"size": "43008", "xon":"19456"},
                             "pg_lossless_10000_40m_profile": {"size": "41984", "xon":"19456"},
                             "pg_lossless_25000_40m_profile": {"size": "44032", "xon":"19456"},
                             "pg_lossless_40000_40m_profile": {"size": "45056", "xon":"19456"},
                             "pg_lossless_50000_40m_profile": {"size": "45056", "xon":"19456"},
                             "pg_lossless_100000_40m_profile": {"size": "49152", "xon":"19456"},
                             "pg_lossless_10000_300m_profile": {"size": "47104", "xon":"19456"},
                             "pg_lossless_25000_300m_profile": {"size": "56320", "xon":"19456"},
                             "pg_lossless_40000_300m_profile": {"size": "64512", "xon":"19456"},
                             "pg_lossless_50000_300m_profile": {"size": "69632", "xon":"19456"},
                             "pg_lossless_100000_300m_profile": {"size": "98304", "xon":"19456"}}
                },
                "spc2_headroom": {
                    "default": {"pg_lossless_10000_5m_profile": {"size": "52224", "xon":"19456"},
                                "pg_lossless_25000_5m_profile": {"size": "52224", "xon":"19456"},
                                "pg_lossless_40000_5m_profile": {"size": "53248", "xon":"19456"},
                                "pg_lossless_50000_5m_profile": {"size": "53248", "xon":"19456"},
                                "pg_lossless_100000_5m_profile": {"size": "53248", "xon":"19456"},
                                "pg_lossless_200000_5m_profile": {"size": "55296", "xon":"19456"},
                                "pg_lossless_10000_40m_profile": {"size": "53248", "xon":"19456"},
                                "pg_lossless_25000_40m_profile": {"size": "55296", "xon":"19456"},
                                "pg_lossless_40000_40m_profile": {"size": "57344", "xon":"19456"},
                                "pg_lossless_50000_40m_profile": {"size": "58368", "xon":"19456"},
                                "pg_lossless_100000_40m_profile": {"size": "63488", "xon":"19456"},
                                "pg_lossless_200000_40m_profile": {"size": "74752", "xon":"19456"},
                                "pg_lossless_10000_300m_profile": {"size": "60416", "xon":"19456"},
                                "pg_lossless_25000_300m_profile": {"size": "73728", "xon":"19456"},
                                "pg_lossless_40000_300m_profile": {"size": "86016", "xon":"19456"},
                                "pg_lossless_50000_300m_profile": {"size": "95232", "xon":"19456"},
                                "pg_lossless_100000_300m_profile": {"size": "137216", "xon":"19456"},
                                "pg_lossless_200000_300m_profile": {"size": "223232", "xon":"19456"}}
                },
                "spc3_headroom": {
                    "default": {"pg_lossless_10000_5m_profile": {"size": "52224", "xon":"19456"},
                                "pg_lossless_25000_5m_profile": {"size": "52224", "xon":"19456"},
                                "pg_lossless_40000_5m_profile": {"size": "53248", "xon":"19456"},
                                "pg_lossless_50000_5m_profile": {"size": "53248", "xon":"19456"},
                                "pg_lossless_100000_5m_profile": {"size": "53248", "xon":"19456"},
                                "pg_lossless_200000_5m_profile": {"size": "55296", "xon":"19456"},
                                "pg_lossless_400000_5m_profile": {"size": "86016", "xon":"37888"},
                                "pg_lossless_10000_40m_profile": {"size": "53248", "xon":"19456"},
                                "pg_lossless_25000_40m_profile": {"size": "55296", "xon":"19456"},
                                "pg_lossless_40000_40m_profile": {"size": "57344", "xon":"19456"},
                                "pg_lossless_50000_40m_profile": {"size": "58368", "xon":"19456"},
                                "pg_lossless_100000_40m_profile": {"size": "63488", "xon":"19456"},
                                "pg_lossless_200000_40m_profile": {"size": "74752", "xon":"19456"},
                                "pg_lossless_400000_40m_profile": {"size": "124928", "xon":"37888"},
                                "pg_lossless_10000_300m_profile": {"size": "60416", "xon":"19456"},
                                "pg_lossless_25000_300m_profile": {"size": "73728", "xon":"19456"},
                                "pg_lossless_40000_300m_profile": {"size": "86016", "xon":"19456"},
                                "pg_lossless_50000_300m_profile": {"size": "95232", "xon":"19456"},
                                "pg_lossless_100000_300m_profile": {"size": "137216", "xon":"19456"},
                                "pg_lossless_200000_300m_profile": {"size": "223232", "xon":"19456"},
                                "pg_lossless_400000_300m_profile": {"size": "420864", "xon":"37888"}}
                }
            },

            # Buffer profile info
            "buffer_profiles": {
                "default": {"ingress_lossless_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|ingress_lossless_pool]", "size": "0"},
                               "ingress_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|ingress_lossy_pool]", "size": "0"},
                               "egress_lossless_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|egress_lossless_pool]", "size": "0"},
                               "egress_lossy_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|egress_lossy_pool]", "size": "9216"},
                               "q_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|egress_lossy_pool]", "size": "0"}},
                "singlepool": {"ingress_lossless_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|ingress_lossless_pool]", "size": "0"},
                               "ingress_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|ingress_lossless_pool]", "size": "0"},
                               "egress_lossless_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|egress_lossless_pool]", "size": "0"},
                               "egress_lossy_profile": {"dynamic_th": "7", "pool": "[BUFFER_POOL|egress_lossy_pool]", "size": "9216"},
                               "q_lossy_profile": {"dynamic_th": "3", "pool": "[BUFFER_POOL|egress_lossy_pool]", "size": "0"}}
            }
        },
        "version_1_0_5": {
            # Version 1.0.5 is introduced for shared headroom pools
            "pool_convert_map": {
                "spc1_t0_pool_sku_map": {"Mellanox-SN2700-C28D8": "spc1_2700-d48c8_t0_pool_shp",
                                         "Mellanox-SN2700-D48C8": "spc1_2700-d48c8_t0_pool_shp",
                                         "Mellanox-SN2700-D40C8S8": "spc1_2700-d48c8_t0_single_pool_shp",
                                         "Mellanox-SN2700": "spc1_2700_t0_pool_shp"},
                "spc1_t1_pool_sku_map": {"Mellanox-SN2700-C28D8": "spc1_2700-d48c8_t1_pool_shp",
                                         "Mellanox-SN2700-D48C8": "spc1_2700-d48c8_t1_pool_shp",
                                         "Mellanox-SN2700-D40C8S8": "spc1_2700-d48c8_t1_single_pool_shp",
                                         "Mellanox-SN2700": "spc1_2700_t1_pool_shp"}
            },
            "pool_mapped_from_old_version": {
                # MSFT SKUs and generic SKUs may have different pool seetings
                "spc1_t0_pool": ("sku", "spc1_t0_pool_sku_map"),
                "spc1_t1_pool": ("sku", "spc1_t1_pool_sku_map"),
                "spc1_2700_t0_pool": "spc1_2700_t0_single_pool_shp",
                "spc1_2700_t1_pool": "spc1_2700_t1_single_pool_shp",
                "spc1_2700-d48c8_t0_pool": "spc1_2700-d48c8_t0_single_pool_shp",
                "spc1_2700-d48c8_t1_pool": "spc1_2700-d48c8_t1_single_pool_shp"
            },

            # Buffer pool info for normal mode
            "buffer_pool_list" : ['ingress_lossless_pool', 'ingress_lossy_pool', 'egress_lossless_pool', 'egress_lossy_pool'],

            "buffer_pools": {
                "spc1_2700_t0_pool_shp": {"doublepool": { "size": "5088768", "xoff": "688128" }, "egress_lossless_pool": { "size": "13945824"}},
                "spc1_2700_t1_pool_shp": {"doublepool": { "size": "4646400", "xoff": "1572864" }, "egress_lossless_pool": { "size": "13945824"}},
                "spc1_2700-d48c8_t0_pool_shp": {"doublepool": { "size": "3859968", "xoff": "1032192" }, "egress_lossless_pool": { "size": "13945824"}},
                "spc1_2700-d48c8_t1_pool_shp": {"doublepool": { "size": "4843008", "xoff": "1179648" }, "egress_lossless_pool": { "size": "13945824"}},

                # Buffer pool for single pool
                "spc1_2700_t0_single_pool_shp": {"singlepool": { "size": "10177536", "xoff": "688128" }, "egress_lossless_pool": { "size": "13945824"}},
                "spc1_2700_t1_single_pool_shp": {"singlepool": { "size": "9292800", "xoff": "1572864" }, "egress_lossless_pool": { "size": "13945824"}},
                "spc1_2700-d48c8_t0_single_pool_shp": {"singlepool": { "size": "7719936", "xoff": "1032192" }, "egress_lossless_pool": { "size": "13945824"}},
                "spc1_2700-d48c8_t1_single_pool_shp": {"singlepool": { "size": "9686016", "xoff": "1179648" }, "egress_lossless_pool": { "size": "13945824"}},

                # 3800 generic profiles
                # 1.0.5 should be the first version supporting 3800
                "spc2_3800_t0_pool": {"doublepool": { "size": "13924352" }, "egress_lossless_pool": { "size": "34287552" }},
                "spc2_3800_t1_pool": {"doublepool": { "size": "12457984" }, "egress_lossless_pool": { "size": "34287552" }},

                # The following pools are used for upgrading from 1.0.5 to the newer version
                "spc2_3800-c64_t0_pool_shp": {"singlepool": {"size": "25866240", "xoff": "2523136"}, "egress_lossless_pool": {"size": "34287552"}},
                "spc2_3800-c64_t1_pool_shp": {"singlepool": {"size": "23900160", "xoff": "4489216"}, "egress_lossless_pool": {"size": "34287552"}},
                "spc2_3800-d112c8_t0_pool_shp": {"singlepool": {"size": "20017152", "xoff": "3440640"}, "egress_lossless_pool": {"size": "34287552"}},
                "spc2_3800-d112c8_t1_pool_shp": {"singlepool": {"size": "19124224", "xoff": "4333568"}, "egress_lossless_pool": {"size": "34287552"}},
                "spc2_3800-d24c52_t0_pool_shp": {"singlepool": {"size": "24576000", "xoff": "2756608"}, "egress_lossless_pool": {"size": "34287552"}},
                "spc2_3800-d24c52_t1_pool_shp": {"singlepool": {"size": "22597632", "xoff": "4734976"}, "egress_lossless_pool": {"size": "34287552"}},
                "spc2_3800-d28c50_t0_pool_shp": {"singlepool": {"size": "24360960", "xoff": "2795520"}, "egress_lossless_pool": {"size": "34287552"}},
                "spc2_3800-d28c50_t1_pool_shp": {"singlepool": {"size": "22380544", "xoff": "4775936"}, "egress_lossless_pool": {"size": "34287552"}}
            },
            "buffer_pools_inherited": {
                "version_1_0_4": ["spc1_t0_pool", "spc1_t1_pool", "spc2_t0_pool", "spc2_t1_pool", "spc3_t0_pool", "spc3_t1_pool"]
            },

            "headrooms": {
                "mapping": {
                    "default": ("skumap", {"Mellanox-SN2700": "msft", "Mellanox-SN2700-C28D8": "msft", "Mellanox-SN2700-D48C8": "msft", "Mellanox-SN2700-D40C8S8": "msft"})
                },
                "spc1_headroom": {
                    "default": ("version_1_0_4", "spc1_headroom"),
                    "msft": {"pg_lossless_10000_5m_profile": {"xoff": "22528", "xon":"19456"},
                            "pg_lossless_25000_5m_profile": {"xoff": "22528", "xon":"19456"},
                            "pg_lossless_40000_5m_profile": {"xoff": "22528", "xon":"19456"},
                            "pg_lossless_50000_5m_profile": {"xoff": "22528", "xon":"19456"},
                            "pg_lossless_100000_5m_profile": {"xoff": "23552", "xon":"19456"},
                            "pg_lossless_10000_40m_profile": {"xoff": "22528", "xon":"19456"},
                            "pg_lossless_25000_40m_profile": {"xoff": "24576", "xon":"19456"},
                            "pg_lossless_40000_40m_profile": {"xoff": "25600", "xon":"19456"},
                            "pg_lossless_50000_40m_profile": {"xoff": "25600", "xon":"19456"},
                            "pg_lossless_100000_40m_profile": {"xoff": "29696", "xon":"19456"},
                            "pg_lossless_10000_300m_profile": {"xoff": "27648", "xon":"19456"},
                            "pg_lossless_25000_300m_profile": {"xoff": "36864", "xon":"19456"},
                            "pg_lossless_40000_300m_profile": {"xoff": "45056", "xon":"19456"},
                            "pg_lossless_50000_300m_profile": {"xoff": "50176", "xon":"19456"},
                            "pg_lossless_100000_300m_profile": {"xoff": "78848", "xon":"19456"}}
                },
                "spc2_headroom": {
                    "default": ("version_1_0_4", "spc2_headroom")
                },
                "spc2_3800_headroom": {
                    "default": {"pg_lossless_10000_5m_profile": {"size": "54272", "xon":"19456"},
                                "pg_lossless_25000_5m_profile": {"size": "58368", "xon":"19456"},
                                "pg_lossless_40000_5m_profile": {"size": "61440", "xon":"19456"},
                                "pg_lossless_50000_5m_profile": {"size": "64512", "xon":"19456"},
                                "pg_lossless_100000_5m_profile": {"size": "75776", "xon":"19456"},
                                "pg_lossless_10000_40m_profile": {"size": "55296", "xon":"19456"},
                                "pg_lossless_25000_40m_profile": {"size": "60416", "xon":"19456"},
                                "pg_lossless_40000_40m_profile": {"size": "65536", "xon":"19456"},
                                "pg_lossless_50000_40m_profile": {"size": "69632", "xon":"19456"},
                                "pg_lossless_100000_40m_profile": {"size": "86016", "xon":"19456"},
                                "pg_lossless_10000_300m_profile": {"size": "63488", "xon":"19456"},
                                "pg_lossless_25000_300m_profile": {"size": "78848", "xon":"19456"},
                                "pg_lossless_40000_300m_profile": {"size": "95232", "xon":"19456"},
                                "pg_lossless_50000_300m_profile": {"size": "106496", "xon":"19456"},
                                "pg_lossless_100000_300m_profile": {"size": "159744", "xon":"19456"}},
                    "msft": {"pg_lossless_10000_5m_profile": {"xoff": "25600", "xon":"19456"},
                            "pg_lossless_25000_5m_profile": {"xoff": "28672", "xon":"19456"},
                            "pg_lossless_40000_5m_profile": {"xoff": "30720", "xon":"19456"},
                            "pg_lossless_50000_5m_profile": {"xoff": "32768", "xon":"19456"},
                            "pg_lossless_100000_5m_profile": {"xoff": "40960", "xon":"19456"},
                            "pg_lossless_10000_40m_profile": {"xoff": "26624", "xon":"19456"},
                            "pg_lossless_25000_40m_profile": {"xoff": "30720", "xon":"19456"},
                            "pg_lossless_40000_40m_profile": {"xoff": "33792", "xon":"19456"},
                            "pg_lossless_50000_40m_profile": {"xoff": "36864", "xon":"19456"},
                            "pg_lossless_100000_40m_profile": {"xoff": "48128", "xon":"19456"},
                            "pg_lossless_10000_300m_profile": {"xoff": "31744", "xon":"19456"},
                            "pg_lossless_25000_300m_profile": {"xoff": "44032", "xon":"19456"},
                            "pg_lossless_40000_300m_profile": {"xoff": "55296", "xon":"19456"},
                            "pg_lossless_50000_300m_profile": {"xoff": "63488", "xon":"19456"},
                            "pg_lossless_100000_300m_profile": {"xoff": "102400", "xon":"19456"}}
                },
                "spc3_headroom": {
                    "default": ("version_1_0_4", "spc3_headroom")
                }
            }
        },
        "version_1_0_6": {
            # Version 1.0.6 is introduced for 2km cable support
            #
            # pool_mapped_from_old_version is not required because no pool flavor mapping changed

            # Buffer pool info for normal mode
            "buffer_pool_list" : ['ingress_lossless_pool', 'ingress_lossy_pool', 'egress_lossless_pool', 'egress_lossy_pool'],

            "buffer_pools": {
                "spc1_2700_t1_pool_shp": {"doublepool": { "size": "4439552", "xoff": "2146304" }, "egress_lossless_pool": { "size": "13945824"}},

                # Buffer pool for single pool
                "spc1_2700_t1_single_pool_shp": {"singlepool": { "size": "8719360", "xoff": "2146304" }, "egress_lossless_pool": { "size": "13945824"}},

                # The following pools are used for upgrading from 1.0.5 to the newer version
                "spc2_3800-c64_t1_pool_shp": {"singlepool": {"size": "24219648", "xoff": "4169728"}, "egress_lossless_pool": {"size": "34287552"}}
            },
            "buffer_pools_inherited": {
                "version_1_0_4": ["spc1_t0_pool", "spc1_t1_pool", "spc2_t0_pool", "spc2_t1_pool", "spc3_t0_pool", "spc3_t1_pool"],
                "version_1_0_5": [# Generic SKUs for 3800
                                  "spc2_3800_t0_pool",
                                  "spc2_3800_t1_pool",
                                  # Non generic SKUs
                                  "spc1_2700_t0_pool_shp",
                                  "spc1_2700_t0_single_pool_shp",
                                  "spc1_2700-d48c8_t0_pool_shp",
                                  "spc1_2700-d48c8_t0_single_pool_shp",
                                  "spc2_3800-c64_t0_pool_shp", "spc2_3800-d112c8_t0_pool_shp",
                                  "spc2_3800-d24c52_t0_pool_shp", "spc2_3800-d28c50_t0_pool_shp",
                                  "spc1_2700-d48c8_t1_pool_shp",
                                  "spc1_2700-d48c8_t1_single_pool_shp",
                                  "spc2_3800-d112c8_t1_pool_shp",
                                  "spc2_3800-d24c52_t1_pool_shp", "spc2_3800-d28c50_t1_pool_shp"],
            }
        },
        "version_2_0_0": {
            # Version 2.0.0 is introduced for dynamic buffer calculation
            #
            "pool_mapped_from_old_version": {
                "spc1_t0_pool": "spc1_pool",
                "spc1_t1_pool": "spc1_pool",
                "spc2_t0_pool": "spc2_pool",
                "spc2_t1_pool": "spc2_pool",
                "spc2_3800_t0_pool": "spc2_pool",
                "spc2_3800_t1_pool": "spc2_pool",
                "spc3_t0_pool": "spc3_pool",
                "spc3_t1_pool": "spc3_pool"
            },

            # Buffer pool info for normal mode
            "buffer_pool_list" : ['ingress_lossless_pool', 'ingress_lossy_pool', 'egress_lossless_pool', 'egress_lossy_pool'],
            "buffer_pools": {
                "spc1_pool": {"doublepool": {"size": "dynamic"}, "egress_lossless_pool": { "size": "13945824" }},
                "spc2_pool": {"doublepool": {"size": "dynamic"}, "egress_lossless_pool": { "size": "34287552" }},
                "spc3_pool": {"doublepool": {"size": "dynamic"}, "egress_lossless_pool": { "size": "60817392" }}
            },
            "buffer_pools_inherited": {
                "version_1_0_5": ["spc1_2700_t0_pool_shp",
                                  "spc1_2700_t0_single_pool_shp",
                                  "spc1_2700-d48c8_t0_pool_shp",
                                  "spc1_2700-d48c8_t0_single_pool_shp",
                                  "spc2_3800-c64_t0_pool_shp", "spc2_3800-d112c8_t0_pool_shp",
                                  "spc2_3800-d24c52_t0_pool_shp", "spc2_3800-d28c50_t0_pool_shp",
                                  "spc1_2700-d48c8_t1_pool_shp",
                                  "spc1_2700-d48c8_t1_single_pool_shp",
                                  "spc2_3800-d112c8_t1_pool_shp",
                                  "spc2_3800-d24c52_t1_pool_shp", "spc2_3800-d28c50_t1_pool_shp"],
                "version_1_0_6": ["spc1_2700_t1_pool_shp",
                                  "spc1_2700_t1_single_pool_shp",
                                  "spc2_3800-c64_t1_pool_shp"]
            }
        }
    }

    def mlnx_default_buffer_parameters(self, db_version, table):
        """
        We extract buffer configurations to a common function
        so that it can be reused among different migration
        The logic of buffer parameters migrating:
        1. Compare the current buffer configuration with the default settings
        2. If there is a match, migrate the old value to the new one
        3. Insert the new setting into database
        Each settings defined below (except that for version_1_0_2) will be used twice:
        1. It is referenced as new setting when database is migrated to that version
        2. It is referenced as old setting when database is migrated from that version
        """

        return self.mellanox_default_parameter[db_version].get(table)

    def mlnx_merge_inherited_info(self, db_version, buffer_pools):
        inherited_info = self.mlnx_default_buffer_parameters(db_version, "buffer_pools_inherited")
        if inherited_info:
            for from_version, inherited_pool_list in inherited_info.items():
                pools_in_base_version = self.mlnx_default_buffer_parameters(from_version, "buffer_pools")
                log.log_info("inherited pool list {} from version {} loaded".format(inherited_pool_list, from_version))
                for key in inherited_pool_list:
                    pool_config = pools_in_base_version.get(key)
                    if pool_config:
                        buffer_pools[key] = pool_config

    def mlnx_migrate_map_old_pool_to_new(self, pool_mapping, pool_convert_map, old_config_name):
        new_config_name = None
        if pool_mapping:
            new_config_map = pool_mapping.get(old_config_name)
            if type(new_config_map) is tuple:
                method, mapname = new_config_map
                if method == "sku":
                    skumap = pool_convert_map.get(mapname)
                    new_config_name = skumap.get(self.sku)
                else:
                    log.log_error("Unsupported mapping method {} found. Stop db_migrator".format(method))
                    return None
            else:
                new_config_name = new_config_map
        return new_config_name

    def mlnx_migrate_extend_condensed_pool(self, pool_config, config_name=None):
        condensedpool = pool_config.get("doublepool")
        doublepool = False
        if not condensedpool:
            condensedpool = pool_config.get("singlepool")
            if condensedpool:
                pool_config.pop("singlepool")
            else:
                log.log_info("Got old default pool configuration {} {}".format(config_name, pool_config))
        else:
            pool_config.pop("doublepool")
            doublepool = True

        if condensedpool:
            xoff = condensedpool.get('xoff')
            if xoff:
                condensedpool.pop('xoff')
            if condensedpool['size'] == 'dynamic':
                condensedpool.pop('size')
            log.log_info("condensed pool {}".format(condensedpool))
            condensedpool['type'] = 'egress'
            condensedpool['mode'] = 'dynamic'
            pool_config['egress_lossy_pool'] = {}
            pool_config['egress_lossy_pool'].update(condensedpool)

            pool_config['egress_lossless_pool']['type'] = 'egress'
            pool_config['egress_lossless_pool']['mode'] = 'dynamic'

            condensedpool['type'] = 'ingress'
            pool_config['ingress_lossless_pool'] = {}
            pool_config['ingress_lossless_pool'].update(condensedpool)

            if doublepool:
                pool_config['ingress_lossy_pool'] = {}
                pool_config['ingress_lossy_pool'].update(condensedpool)

            if xoff:
                pool_config['ingress_lossless_pool']['xoff'] = xoff

            log.log_info("Initialize condensed buffer pool: {}".format(pool_config))

    def mlnx_migrate_get_headroom_profiles(self, headroom_profile_set):
        if type(headroom_profile_set) is tuple:
            version, key = headroom_profile_set
            result = self.mlnx_default_buffer_parameters(version, "headrooms")[key]["default"]
        elif type(headroom_profile_set) is dict:
            result = headroom_profile_set

        return result

    def mlnx_migrate_extend_headroom_profile(self, headroom_profile):
        headroom_profile['dynamic_th'] = '0'
        if not 'xoff' in headroom_profile.keys():
            headroom_profile['xoff'] = str(int(headroom_profile['size']) - int(headroom_profile['xon']))
        elif not 'size' in headroom_profile.keys():
            headroom_profile['size'] = headroom_profile['xon']
        headroom_profile['pool'] = '[BUFFER_POOL|ingress_lossless_pool]'

        return headroom_profile

    def mlnx_migrate_buffer_pool_size(self, old_version, new_version):
        """
        To migrate buffer pool configuration
        """
        self.is_buffer_config_default = False

        # Buffer pools defined in old version
        default_buffer_pool_list_old = self.mlnx_default_buffer_parameters(old_version, "buffer_pool_list")

        # Try to get related info from DB
        configdb_buffer_pools = self.configDB.get_table('BUFFER_POOL')

        # Get current buffer pool configuration, only migrate configuration which
        # with default values, if it's not default, leave it as is.
        configdb_buffer_pool_names = configdb_buffer_pools.keys()

        # Buffer pool numbers is different from default, we don't need to migrate it
        if len(configdb_buffer_pool_names) > len(default_buffer_pool_list_old):
            log.log_notice("Pools in CONFIG_DB ({}) don't match default ({}), skip buffer pool migration".format(configdb_buffer_pool_names, default_buffer_pool_list_old))
            return True

        # If some buffer pool is not default ones, don't need migrate
        for buffer_pool in default_buffer_pool_list_old:
            if buffer_pool not in configdb_buffer_pool_names and buffer_pool != 'ingress_lossy_pool':
                # Check whether it's empty buffer configuration
                log.log_notice("Default pool {} isn't in CONFIG_DB, skip buffer pool migration".format(buffer_pool))
                if not self.configDB.get_keys('BUFFER_*'):
                    self.is_buffer_config_empty = True
                return True

        default_buffer_pools_old = self.mlnx_default_buffer_parameters(old_version, "buffer_pools")
        self.mlnx_merge_inherited_info(old_version, default_buffer_pools_old)
        default_pool_conf_list_old = self.mlnx_default_buffer_parameters(old_version, "pool_configuration_list")
        if not default_pool_conf_list_old:
            if default_buffer_pools_old:
                default_pool_conf_list_old = default_buffer_pools_old.keys()
            if not default_pool_conf_list_old:
                log.log_error("Trying to get pool configuration list or migration control failed, skip migration")
                return False

        new_config_name = None
        pool_mapping = self.mlnx_default_buffer_parameters(new_version, "pool_mapped_from_old_version")
        pool_convert_map = self.mlnx_default_buffer_parameters(new_version, "pool_convert_map")
        log.log_info("got old configuration {}".format(configdb_buffer_pools))

        for old_config_name in default_pool_conf_list_old:
            old_config = default_buffer_pools_old[old_config_name]
            self.mlnx_migrate_extend_condensed_pool(old_config, old_config_name)

            log.log_info("Checking old pool configuration {} {}".format(old_config_name, old_config))
            if configdb_buffer_pools == old_config:
                new_config_name = self.mlnx_migrate_map_old_pool_to_new(pool_mapping, pool_convert_map, old_config_name)
                if not new_config_name:
                    new_config_name = old_config_name
                log.log_info("Old buffer pool configuration {} will be migrate to new one {}".format(old_config_name, new_config_name))
                break

        if not new_config_name:
            log.log_notice("The configuration doesn't match any default configuration, migration for pool isn't required")
            return True

        default_buffer_pools_new = self.mlnx_default_buffer_parameters(new_version, "buffer_pools")
        self.mlnx_merge_inherited_info(new_version, default_buffer_pools_new)
        new_buffer_pool_conf = default_buffer_pools_new.get(new_config_name)
        if not new_buffer_pool_conf:
            log.log_error("Can't find the buffer pool configuration for {} in {}".format(new_config_name, new_version))
            return False

        self.mlnx_migrate_extend_condensed_pool(new_buffer_pool_conf, new_config_name)

        # Migrate old buffer conf to latest.
        for pool in configdb_buffer_pools:
            self.pending_update_items.append(('BUFFER_POOL', pool, None))
        for pool in new_buffer_pool_conf:
            self.pending_update_items.append(('BUFFER_POOL', pool, new_buffer_pool_conf.get(pool)))

        self.is_buffer_config_default = True

        return True

    def mlnx_migrate_buffer_profile(self, old_version, new_version):
        """
        This is to migrate BUFFER_PROFILE configuration
        """
        if not self.is_buffer_config_default:
            return True
        else:
            self.is_buffer_config_default = False

        # get profile
        default_buffer_profiles_old = self.mlnx_default_buffer_parameters(old_version, "buffer_profiles")
        default_buffer_profiles_new = self.mlnx_default_buffer_parameters(new_version, "buffer_profiles")

        configdb_buffer_profiles = self.configDB.get_table('BUFFER_PROFILE')

        # we need to transform lossless pg profiles to new settings
        # to achieve that, we just need to remove this kind of profiles, buffermgrd will generate them automatically
        default_headroom_sets_old = self.mlnx_default_buffer_parameters(old_version, "headrooms")
        default_headroom_sets_new = self.mlnx_default_buffer_parameters(new_version, "headrooms")
        default_headrooms_old = None
        default_headrooms_new = None
        if default_headroom_sets_old and default_headroom_sets_new:
            if self.platform == 'x86_64-mlnx_msn3800-r0':
                default_headrooms_old = default_headroom_sets_old.get("spc2_3800_headroom")
                default_headrooms_new = default_headroom_sets_new.get("spc2_3800_headroom")
            elif self.platform in self.spc2_platforms:
                default_headrooms_old = default_headroom_sets_old.get("spc2_headroom")
                default_headrooms_new = default_headroom_sets_new.get("spc2_headroom")
            elif self.platform in self.spc1_platforms:
                default_headrooms_old = default_headroom_sets_old.get("spc1_headroom")
                default_headrooms_new = default_headroom_sets_new.get("spc1_headroom")
            elif self.platform in self.spc3_platforms:
                default_headrooms_old = default_headroom_sets_old.get("spc3_headroom")
                default_headrooms_new = default_headroom_sets_new.get("spc3_headroom")

        if default_headrooms_old and default_headrooms_new:
            # match the old lossless profiles?
            for headroom_set_name, lossless_profiles in default_headrooms_old.items():
                lossless_profiles = self.mlnx_migrate_get_headroom_profiles(lossless_profiles)
                matched = True
                for name, profile in configdb_buffer_profiles.items():
                    if name in lossless_profiles.keys():
                        default_profile = self.mlnx_migrate_extend_headroom_profile(lossless_profiles.get(name))
                        if profile != default_profile:
                            log.log_info("Skip headroom profile set {} due to {} mismatched: {} vs {}".format(
                                headroom_set_name, name, default_profile, profile))
                            matched = False
                            break
                if matched:
                    mapping = default_headroom_sets_new.get("mapping")
                    if not mapping:
                        new_headroom_set_name = headroom_set_name
                        log.log_info("Migrate profile set {} ".format(headroom_set_name))
                    else:
                        new_headroom_set_name = mapping.get(headroom_set_name)
                        if type(new_headroom_set_name) is tuple:
                            log.log_info("Use headroom profiles map {}".format(mapping))
                            maptype, sku_mapping = new_headroom_set_name
                            if maptype == "skumap":
                                new_headroom_set_name = sku_mapping.get(self.sku)
                        if not new_headroom_set_name:
                            new_headroom_set_name = headroom_set_name
                    log.log_info("{} has been mapped to {} according to sku".format(headroom_set_name, new_headroom_set_name))
                    break

            if not matched:
                log.log_notice("Headroom profiles don't match any of the default value, skip migrating")
                return True

            default_headrooms_new = default_headrooms_new.get(new_headroom_set_name)
            if type(default_headrooms_new) is dict:
                for name, profile in configdb_buffer_profiles.items():
                    if name in default_headrooms_new.keys():
                        default_profile = self.mlnx_migrate_extend_headroom_profile(default_headrooms_new.get(name))
                        self.pending_update_items.append(('BUFFER_PROFILE', name, default_profile))
                        log.log_info("Profile {} has been migrated to {}".format(name, default_profile))

        self.is_buffer_config_default = True

        if not default_buffer_profiles_new:
            # Not providing new profile configure in new version means they do need to be changed
            log.log_notice("No buffer profile in {}, don't need to migrate non-lossless profiles".format(new_version))
            return True

        profile_matched = True
        for _, profiles in default_buffer_profiles_old.items():
            for name, profile in profiles.items():
                if name in configdb_buffer_profiles.keys() and profile == configdb_buffer_profiles[name]:
                    continue
                # return if any default profile isn't in cofiguration
                profile_matched = False
                break

        if not profile_matched:
            log.log_notice("Profiles doesn't match default value".format(name))
            return True

        for name, profile in default_buffer_profiles_new["default"].items():
            log.log_info("Successfully migrate profile {}".format(name))
            self.pending_update_items.append(('BUFFER_PROFILE', name, profile))
        return True

    def mlnx_append_item_on_pending_configuration_list(self, item):
        self.pending_update_items.append(item)

    def mlnx_abandon_pending_buffer_configuration(self):
        """
        We found the buffer configuration on the device doesn't match the default one, so no migration performed
        Clear pending update item list in this case
        """
        self.pending_update_items = []
        self.is_buffer_config_default = False

    def mlnx_flush_new_buffer_configuration(self):
        """
        Flush all the pending items to config database
        """
        if not self.ready:
            return True

        if not self.is_buffer_config_default and not self.is_buffer_config_empty or self.is_msft_sku:
            log.log_notice("No item pending to be updated")
            metadata = self.configDB.get_entry('DEVICE_METADATA', 'localhost')
            metadata['buffer_model'] = 'traditional'
            self.configDB.set_entry('DEVICE_METADATA', 'localhost', metadata)
            log.log_notice("Set buffer_model as traditional")

        for item in self.pending_update_items:
            table, key, value = item
            self.configDB.set_entry(table, key, value)
            if value:
                log.log_notice("Successfully migrate {} {} to {}".format(table, key, value))
            else:
                log.log_notice("Successfully remove {} {} which is no longer used".format(table, key))

        return True

    def mlnx_is_buffer_model_dynamic(self):
        return self.is_buffer_config_default and not self.is_msft_sku

    def mlnx_reorganize_buffer_tables(self, buffer_table, name):
        """
        This is to reorganize the BUFFER_PG and BUFFER_QUEUE tables from single tier index to double tiers index.
        Originally, the index is like <port>|<ids>. However, we need to check all the items with respect to a port,
        which requires two tiers index, <port> and then <ids>
        Eg.
        Before reorganize:
        {
          "Ethernet0|0": {"profile" : "ingress_lossy_profile"},
          "Ethernet0|3-4": {"profile": "pg_lossless_100000_5m_profile"},
          "Ethernet4|0": {"profile" : "ingress_lossy_profile"},
          "Ethernet4|3-4": {"profile": "pg_lossless_50000_5m_profile"}
        }
        After reorganize:
        {
          "Ethernet0": {
             "0": {"profile" : "ingress_lossy_profile"},
             "3-4": {"profile": "pg_lossless_100000_5m_profile"}
          },
          "Ethernet4": {
             "0": {"profile" : "ingress_lossy_profile"},
             "3-4": {"profile": "pg_lossless_50000_5m_profile"}
          }
        }
        """
        result = {}
        for key, item in buffer_table.items():
            if len(key) != 2:
                log.log_error('Table {} contains invalid key {}, skip this item'.format(name, key))
                continue
            port, ids = key
            if not port in result:
                result[port] = {}
            result[port][ids] = item

        return result

    def mlnx_reclaiming_unused_buffer(self):
        cable_length_key = self.configDB.get_keys('CABLE_LENGTH')
        if not cable_length_key:
            log.log_notice("No cable length table defined, do not migrate buffer objects for reclaiming buffer")
            return;

        log.log_info("Migrate buffer objects for reclaiming buffer based on 'CABLE_LENGTH|{}'".format(cable_length_key[0]))

        device_metadata = self.configDB.get_entry('DEVICE_METADATA', 'localhost')
        is_dynamic = (device_metadata.get('buffer_model') == 'dynamic')

        port_table = self.configDB.get_table('PORT')
        buffer_pool_table = self.configDB.get_table('BUFFER_POOL')
        buffer_profile_table = self.configDB.get_table('BUFFER_PROFILE')
        buffer_pg_table = self.configDB.get_table('BUFFER_PG')
        buffer_queue_table = self.configDB.get_table('BUFFER_QUEUE')
        buffer_ingress_profile_list_table = self.configDB.get_table('BUFFER_PORT_INGRESS_PROFILE_LIST')
        buffer_egress_profile_list_table = self.configDB.get_table('BUFFER_PORT_EGRESS_PROFILE_LIST')
        cable_length_entries = self.configDB.get_entry('CABLE_LENGTH', cable_length_key[0])

        buffer_pg_items = self.mlnx_reorganize_buffer_tables(buffer_pg_table, 'BUFFER_PG')
        buffer_queue_items = self.mlnx_reorganize_buffer_tables(buffer_queue_table, 'BUFFER_QUEUE')

        single_pool = True
        if 'ingress_lossy_pool' in buffer_pool_table:
            ingress_lossy_profile = buffer_profile_table.get('ingress_lossy_profile')
            if ingress_lossy_profile:
                if 'ingress_lossy_pool' == ingress_lossy_profile.get('pool'):
                    single_pool = False

        # Construct buffer items to be applied to admin down ports
        if is_dynamic:
            # For dynamic model, we just need to add the default buffer objects to admin down ports
            # Buffer manager will apply zero profiles automatically when a port is shutdown
            lossy_pg_item = {'profile': 'ingress_lossy_profile'} if 'ingress_lossy_profile' in buffer_profile_table else None
            lossy_queue_item = {'profile': 'q_lossy_profile'} if 'q_lossy_profile' in buffer_profile_table else None
            lossless_queue_item = {'profile': 'egress_lossless_profile'} if 'egress_lossless_profile' in buffer_profile_table else None

            queue_items_to_apply = {'0-2': lossy_queue_item,
                                    '3-4': lossless_queue_item,
                                    '5-6': lossy_queue_item}

            if single_pool:
                if 'ingress_lossless_profile' in buffer_profile_table:
                    ingress_profile_list_item = {'profile_list': 'ingress_lossless_profile'}
                else:
                    ingress_profile_list_item = None
            else:
                if 'ingress_lossless_profile' in buffer_profile_table and 'ingress_lossy_profile' in buffer_profile_table:
                    ingress_profile_list_item = {'profile_list': 'ingress_lossless_profile,ingress_lossy_profile'}
                else:
                    ingress_profile_list_item = None

            if 'egress_lossless_profile' in buffer_profile_table and 'egress_lossy_profile' in buffer_profile_table:
                egress_profile_list_item = {'profile_list': 'egress_lossless_profile,egress_lossy_profile'}
            else:
                egress_profile_list_item = None

            pools_to_insert = None
            profiles_to_insert = None

        else:
            # For static model, we need more.
            # Define zero buffer pools and profiles
            ingress_zero_pool = {'size': '0', 'mode': 'static', 'type': 'ingress'}
            ingress_lossy_pg_zero_profile = {
                "pool":"ingress_zero_pool",
                "size":"0",
                "static_th":"0"
            }
            lossy_pg_item = {'profile': 'ingress_lossy_pg_zero_profile'}

            ingress_lossless_zero_profile = {
                "pool":"ingress_lossless_pool",
                "size":"0",
                "dynamic_th":"-8"
            }

            if single_pool:
                ingress_profile_list_item = {'profile_list': 'ingress_lossless_zero_profile'}
            else:
                ingress_lossy_zero_profile = {
                    "pool":"ingress_lossy_pool",
                    "size":"0",
                    "dynamic_th":"-8"
                }
                ingress_profile_list_item = {'profile_list': 'ingress_lossless_zero_profile,ingress_lossy_zero_profile'}

            egress_lossless_zero_profile = {
                "pool":"egress_lossless_pool",
                "size":"0",
                "dynamic_th":"-8"
            }
            lossless_queue_item = {'profile': 'egress_lossless_zero_profile'}

            egress_lossy_zero_profile = {
                "pool":"egress_lossy_pool",
                "size":"0",
                "dynamic_th":"-8"
            }
            lossy_queue_item = {'profile': 'egress_lossy_zero_profile'}
            egress_profile_list_item = {'profile_list': 'egress_lossless_zero_profile,egress_lossy_zero_profile'}

            queue_items_to_apply = {'0-2': lossy_queue_item,
                                    '3-4': lossless_queue_item,
                                    '5-6': lossy_queue_item}

            pools_to_insert = {'ingress_zero_pool': ingress_zero_pool}
            profiles_to_insert = {'ingress_lossy_pg_zero_profile': ingress_lossy_pg_zero_profile,
                                  'ingress_lossless_zero_profile': ingress_lossless_zero_profile,
                                  'egress_lossless_zero_profile': egress_lossless_zero_profile,
                                  'egress_lossy_zero_profile': egress_lossy_zero_profile}
            if not single_pool:
                profiles_to_insert['ingress_lossy_zero_profile'] = ingress_lossy_zero_profile

        lossless_profile_pattern = 'pg_lossless_([1-9][0-9]*000)_([1-9][0-9]*m)_profile'
        zero_item_count = 0
        reclaimed_ports = set()
        for port_name, port_info in port_table.items():
            if port_info.get('admin_status') == 'up':
                # Handles admin down ports only
                continue

            # If items to be applied to admin down port of BUFFER_PG table have been generated,
            # Check whether the BUFFER_PG items with respect to the port align with the default one,
            # and insert the items to BUFFER_PG
            # The same logic for BUFFER_QUEUE, BUFFER_PORT_INGRESS_PROFILE_LIST and BUFFER_PORT_EGRESS_PROFILE_LIST
            if lossy_pg_item:
                port_pgs = buffer_pg_items.get(port_name)
                is_default = False
                if not port_pgs:
                    is_default = True
                else:
                    if set(port_pgs.keys()) == set(['3-4']):
                        if is_dynamic:
                            reclaimed_ports.add(port_name)
                            if port_pgs['3-4']['profile'] == 'NULL':
                                is_default = True
                        else:
                            match = re.search(lossless_profile_pattern, port_pgs['3-4']['profile'])
                            if match:
                                speed = match.group(1)
                                cable_length = match.group(2)
                                if speed == port_info.get('speed') and cable_length == cable_length_entries.get(port_name):
                                    is_default = True

                if is_default:
                    lossy_pg_key = '{}|0'.format(port_name)
                    lossless_pg_key = '{}|3-4'.format(port_name)
                    self.configDB.set_entry('BUFFER_PG', lossy_pg_key, lossy_pg_item)
                    if is_dynamic:
                        self.configDB.set_entry('BUFFER_PG', lossless_pg_key, {'profile': 'NULL'})
                        # For traditional model, we must NOT remove the default lossless PG
                        # because it has been popagated to APPL_DB during db_migrator
                        # Leaving it untouched in CONFIG_DB enables traditional buffer manager to
                        # remove it from CONFIG_DB as well as APPL_DB
                        # However, removing it from CONFIG_DB causes it left in APPL_DB
                    zero_item_count += 1

            if lossy_queue_item and lossless_queue_item:
                port_queues = buffer_queue_items.get(port_name)
                if not port_queues:
                    for ids, item in queue_items_to_apply.items():
                        self.configDB.set_entry('BUFFER_QUEUE', port_name + '|' + ids, item)
                    zero_item_count += 1

            if ingress_profile_list_item:
                port_ingress_profile_list = buffer_ingress_profile_list_table.get(port_name)
                if not port_ingress_profile_list:
                    self.configDB.set_entry('BUFFER_PORT_INGRESS_PROFILE_LIST', port_name, ingress_profile_list_item)
                    zero_item_count += 1

            if egress_profile_list_item:
                port_egress_profile_list = buffer_egress_profile_list_table.get(port_name)
                if not port_egress_profile_list:
                    self.configDB.set_entry('BUFFER_PORT_EGRESS_PROFILE_LIST', port_name, egress_profile_list_item)
                    zero_item_count += 1

        if zero_item_count > 0:
            if pools_to_insert:
                for name, pool in pools_to_insert.items():
                    self.configDB.set_entry('BUFFER_POOL', name, pool)

            if profiles_to_insert:
                for name, profile in profiles_to_insert.items():
                    self.configDB.set_entry('BUFFER_PROFILE', name, profile)

        # We need to remove BUFFER_PG table items for admin down ports from APPL_DB
        # and then remove the buffer profiles which are no longer referenced
        # We do it here because
        #  - The buffer profiles were copied from CONFIG_DB by db_migrator when the database was being migrated from 1.0.6 to 2.0.0
        #  - In this migrator the buffer priority-groups have been removed from CONFIG_DB.BUFFER_PG table
        #  - The dynamic buffer manager will not generate buffer profile by those buffer PG items
        #    In case a buffer profile was referenced by an admin down port only, the dynamic buffer manager won't create it after starting
        #    This kind of buffer profiles will be left in APPL_DB and can not be removed.
        if not is_dynamic:
            return

        warmreboot_state = self.stateDB.get(self.stateDB.STATE_DB, 'WARM_RESTART_ENABLE_TABLE|system', 'enable')
        if warmreboot_state == 'true':
            referenced_profiles = set()
            keys = self.appDB.keys(self.appDB.APPL_DB, "BUFFER_PG_TABLE:*")
            if keys is None:
                return
            for buffer_pg_key in keys:
                port, pg = buffer_pg_key.split(':')[1:]
                if port in reclaimed_ports:
                    self.appDB.delete(self.appDB.APPL_DB, buffer_pg_key)
                else:
                    buffer_pg_items = self.appDB.get_all(self.appDB.APPL_DB, buffer_pg_key)
                    profile = buffer_pg_items.get('profile')
                    if profile:
                        referenced_profiles.add(profile)
            keys = self.appDB.keys(self.appDB.APPL_DB, "BUFFER_PROFILE_TABLE:*")
            for buffer_profile_key in keys:
                profile = buffer_profile_key.split(':')[1]
                if profile not in referenced_profiles and profile not in buffer_profile_table.keys():
                    self.appDB.delete(self.appDB.APPL_DB, buffer_profile_key)

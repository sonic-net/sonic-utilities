show_mmu_config = """\
Lossless traffic pattern:
--------------------  -
default_dynamic_th    0
over_subscribe_ratio  2
--------------------  -

Pool: egress_lossless_pool
----  --------
mode  dynamic
size  13945824
type  egress
----  --------

Pool: egress_lossy_pool
----  -------
mode  dynamic
type  egress
----  -------

Pool: ingress_lossless_pool
----  -------
mode  dynamic
type  ingress
----  -------

Pool: ingress_lossy_pool
----  -------
mode  dynamic
type  ingress
----  -------

Pool: ingress_lossless_pool_hbm
----  ---------
mode  static
size  139458240
type  ingress
----  ---------

Profile: ingress_lossy_profile
----------  ------------------
dynamic_th  3
pool        ingress_lossy_pool
size        0
----------  ------------------

Profile: ingress_lossless_profile_hbm
---------  -------------------------
static_th  12121212
pool       ingress_lossless_pool_hbm
size       0
---------  -------------------------

Profile: headroom_profile
----------  ---------------------
dynamic_th  0
pool        ingress_lossless_pool
xon         18432
xoff        32768
size        51200
----------  ---------------------

Profile: alpha_profile
-------------  ---------------------
dynamic_th     0
pool           ingress_lossless_pool
headroom_type  dynamic
-------------  ---------------------

Profile: egress_lossless_profile
----------  --------------------
dynamic_th  0
pool        egress_lossless_pool
size        0
----------  --------------------

Profile: egress_lossy_profile
----------  -----------------
dynamic_th  0
pool        egress_lossy_pool
size        0
----------  -----------------

"""

testData = {
             'mmuconfig_list' : {'cmd' : ['show'],
                                    'args' : [],
                                    'rc' : 0,
                                    'rc_output': show_mmu_config
                                },
             'mmu_cfg_static_th' : {'cmd' : ['config'],
                                   'args' : ['-p', 'ingress_lossless_profile_hbm', '-s', '12121213'],
                                   'rc' : 0,
                                   'db_table' : 'BUFFER_PROFILE',
                                   'cmp_args' : ['ingress_lossless_profile_hbm,static_th,12121213'],
                                   'rc_msg' : ''
                                  },
             'mmu_cfg_alpha' :    {'cmd' : ['config'],
                                   'args' : ['-p', 'alpha_profile', '-a', '2'],
                                   'rc' : 0,
                                   'db_table' : 'BUFFER_PROFILE',
                                   'cmp_args' : ['alpha_profile,dynamic_th,2'],
                                   'rc_msg' : ''
                                  },
             'mmu_cfg_alpha_invalid' :    {'cmd' : ['config'],
                                   'args' : ['-p', 'alpha_profile', '-a', '12'],
                                   'rc' : 2,
                                   'rc_msg' : 'Usage: mmu [OPTIONS]\nTry "mmu --help" for help.\n\nError: Invalid value for "-a": 12 is not in the valid range of -8 to 8.\n'
                                  }

           }

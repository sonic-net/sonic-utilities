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

Profile: q_lossy_profile
---------------------  -----------------
packet_discard_action  drop
dynamic_th             0
pool                   egress_lossy_pool
size                   0
---------------------  -----------------

"""

show_mmu_config_asic0 = """\
Pool for namespace asic0: ingress_lossy_pool
----  -------
mode  dynamic
type  ingress
----  -------

Pool for namespace asic0: ingress_lossless_pool_hbm
----  ---------
mode  static
size  139458240
type  ingress
----  ---------

Profile for namespace asic0: ingress_lossy_profile
----------  ------------------
dynamic_th  3
pool        ingress_lossy_pool
size        0
----------  ------------------

Profile for namespace asic0: ingress_lossless_profile_hbm
---------  -------------------------
static_th  12121212
pool       ingress_lossless_pool_hbm
size       0
---------  -------------------------

"""

show_mmu_config_asic1_verbose = """\
Pool for namespace asic1: ingress_lossless_pool
----  -------
mode  dynamic
type  ingress
----  -------

Pool for namespace asic1: egress_lossless_pool
----  --------
mode  dynamic
size  13945824
type  egress
----  --------

Pool for namespace asic1: egress_lossy_pool
----  -------
mode  dynamic
type  egress
----  -------

Total pools: 3


Profile for namespace asic1: alpha_profile
-------------  ---------------------
dynamic_th     0
pool           ingress_lossless_pool
headroom_type  dynamic
-------------  ---------------------

Profile for namespace asic1: headroom_profile
----------  ---------------------
dynamic_th  0
pool        ingress_lossless_pool
xon         18432
xoff        32768
size        51200
----------  ---------------------

Profile for namespace asic1: egress_lossless_profile
----------  --------------------
dynamic_th  0
pool        egress_lossless_pool
size        0
----------  --------------------

Profile for namespace asic1: egress_lossy_profile
----------  -----------------
dynamic_th  0
pool        egress_lossy_pool
size        0
----------  -----------------

Total profiles: 4
"""

show_mmu_config_all_masic = """\
Pool for namespace asic0: ingress_lossy_pool
----  -------
mode  dynamic
type  ingress
----  -------

Pool for namespace asic0: ingress_lossless_pool_hbm
----  ---------
mode  static
size  139458240
type  ingress
----  ---------

Profile for namespace asic0: ingress_lossy_profile
----------  ------------------
dynamic_th  3
pool        ingress_lossy_pool
size        0
----------  ------------------

Profile for namespace asic0: ingress_lossless_profile_hbm
---------  -------------------------
static_th  12121212
pool       ingress_lossless_pool_hbm
size       0
---------  -------------------------

Pool for namespace asic1: ingress_lossless_pool
----  -------
mode  dynamic
type  ingress
----  -------

Pool for namespace asic1: egress_lossless_pool
----  --------
mode  dynamic
size  13945824
type  egress
----  --------

Pool for namespace asic1: egress_lossy_pool
----  -------
mode  dynamic
type  egress
----  -------

Profile for namespace asic1: alpha_profile
-------------  ---------------------
dynamic_th     0
pool           ingress_lossless_pool
headroom_type  dynamic
-------------  ---------------------

Profile for namespace asic1: headroom_profile
----------  ---------------------
dynamic_th  0
pool        ingress_lossless_pool
xon         18432
xoff        32768
size        51200
----------  ---------------------

Profile for namespace asic1: egress_lossless_profile
----------  --------------------
dynamic_th  0
pool        egress_lossless_pool
size        0
----------  --------------------

Profile for namespace asic1: egress_lossy_profile
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
             'mmu_cfg_static_th': {'cmd': ['config'],
                                   'args': ['-p', 'ingress_lossless_profile_hbm', '-s', '12121213'],
                                   'rc': 0,
                                   'db_table': 'BUFFER_PROFILE',
                                   'cmp_args': [',ingress_lossless_profile_hbm,static_th,12121213'],
                                   'rc_msg': ''
                                   },
             'mmu_cfg_alpha' :    {'cmd' : ['config'],
                                   'args' : ['-p', 'alpha_profile', '-a', '2'],
                                   'rc' : 0,
                                   'db_table' : 'BUFFER_PROFILE',
                                   'cmp_args': [',alpha_profile,dynamic_th,2'],
                                   'rc_msg' : ''
                                  },
             'mmu_cfg_alpha_invalid': {'cmd': ['config'],
                                       'args': ['-p', 'alpha_profile', '-a', '12'],
                                       'rc': 2,
                                       'rc_msg': ('Usage: mmu [OPTIONS]\nTry "mmu --help" for help.\n'
                                                  '\nError: Invalid value for "-a": 12 is not in the '
                                                  'valid range of -8 to 8.\n')
                                       },
             'mmu_cfg_trim': {
                              'cmd': ['config'],
                              'args': ['-p', 'q_lossy_profile', '-t', 'on'],
                              'rc': 0,
                              'db_table': 'BUFFER_PROFILE',
                              'cmp_args': [',q_lossy_profile,packet_discard_action,trim'],
                              'rc_msg': ''
                             },
             'mmu_cfg_trim_invalid': {
                                      'cmd': ['config'],
                                      'args': ['-p', 'q_lossy_profile', '-t', 'INVALID_VALUE'],
                                      'rc': 2,
                                      'rc_msg': ('Usage: mmu [OPTIONS]\nTry "mmu --help" for help.\n'
                                                 '\nError: Invalid value for "-t": invalid choice: INVALID_VALUE. '
                                                 '(choose from on, off)\n')
                                     },
             'mmu_cfg_list_one_masic': {'cmd': ['show'],
                                        'args': ['-n', 'asic0'],
                                        'rc': 0,
                                        'rc_output': show_mmu_config_asic0
                                        },
             'mmu_cfg_list_one_verbose_masic': {'cmd': ['show'],
                                                'args': ['-n', 'asic1', '-vv'],
                                                'rc': 0,
                                                'rc_output': show_mmu_config_asic1_verbose
                                                },
             'mmu_cfg_list_all_masic': {'cmd': ['show'],
                                        'args': [],
                                        'rc': 0,
                                        'rc_output': show_mmu_config_all_masic
                                        },
             'mmu_cfg_alpha_one_masic': {'cmd': ['config'],
                                         'args': ['-p', 'alpha_profile', '-a', '2', '-n', 'asic0'],
                                         'rc': 0,
                                         'db_table': 'BUFFER_PROFILE',
                                         'cmp_args': ['asic0,alpha_profile,dynamic_th,2'],
                                         'rc_msg': ''
                                         },
             'mmu_cfg_alpha_all_verbose_masic': {'cmd': ['config'],
                                                 'args': ['-p', 'alpha_profile', '-a', '2', '-vv'],
                                                 'rc': 0,
                                                 'db_table': 'BUFFER_PROFILE',
                                                 'cmp_args': ['asic0,alpha_profile,dynamic_th,2',
                                                              'asic1,alpha_profile,dynamic_th,2'],
                                                 'rc_msg': ('Setting alpha_profile dynamic_th value '
                                                            'to 2 for namespace asic0\n'
                                                            'Setting alpha_profile dynamic_th value '
                                                            'to 2 for namespace asic1\n')
                                                 },
             'mmu_cfg_static_th_one_masic': {'cmd': ['config'],
                                             'args': ['-p', 'ingress_lossless_profile_hbm',
                                                      '-s', '12121215', '-n', 'asic0'],
                                             'rc': 0,
                                             'db_table': 'BUFFER_PROFILE',
                                             'cmp_args': ['asic0,ingress_lossless_profile_hbm,static_th,12121215'],
                                             'rc_msg': ''
                                             },
             'mmu_cfg_static_th_all_verbose_masic': {'cmd': ['config'],
                                                     'args': ['-p', 'ingress_lossless_profile_hbm',
                                                              '-s', '12121214', '-vv'],
                                                     'rc': 0,
                                                     'db_table': 'BUFFER_PROFILE',
                                                     'cmp_args': [('asic0,ingress_lossless_profile_hbm,'
                                                                   'static_th,12121214'),
                                                                  ('asic1,ingress_lossless_profile_hbm,'
                                                                   'static_th,12121214')],
                                                     'rc_msg': ('Setting ingress_lossless_profile_hbm static_th '
                                                                'value to 12121214 for namespace asic0\n'
                                                                'Setting ingress_lossless_profile_hbm static_th '
                                                                'value to 12121214 for namespace asic1\n')
                                                     },
             'mmu_cfg_alpha_invalid_masic': {'cmd': ['config'],
                                             'args': ['-p', 'alpha_profile', '-a', '12'],
                                             'rc': 2,
                                             'rc_msg': ('Usage: mmu [OPTIONS]\n'
                                                        'Try "mmu --help" for help.\n\n'
                                                        'Error: Invalid value for "-a": 12 '
                                                        'is not in the valid range of -8 to 8.\n')
                                             },
             'mmu_cfg_static_th_invalid_masic': {'cmd': ['config'],
                                                 'args': ['-p', 'ingress_lossless_profile_hbm', '-s', '-1'],
                                                 'rc': 2,
                                                 'rc_msg': ('Usage: mmu [OPTIONS]\n'
                                                            'Try "mmu --help" for help.\n\n'
                                                            'Error: Invalid value for "-s": '
                                                            '-1 is smaller than the minimum valid value 0.\n')
                                                 }
           }

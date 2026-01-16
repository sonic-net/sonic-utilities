# Golden outputs
show_asym_all_asic0_masic = """\
Namespace asic0
Interface     Asymmetric
------------  ------------
Ethernet0     off
Ethernet4     off
Ethernet16    off
Ethernet-BP0  off
Ethernet-BP4  off

"""

show_asym_all_asic1_masic = """\
Namespace asic1
Interface       Asymmetric
--------------  ------------
Ethernet64      off
Ethernet-BP256  off
Ethernet-BP260  off

"""

show_asym_all_masic = """\
Namespace asic0
Interface     Asymmetric
------------  ------------
Ethernet0     off
Ethernet4     off
Ethernet16    off
Ethernet-BP0  off
Ethernet-BP4  off

Namespace asic1
Interface       Asymmetric
--------------  ------------
Ethernet64      off
Ethernet-BP256  off
Ethernet-BP260  off

"""

show_asym_intf_one_masic = """\
Namespace asic0
Interface    Asymmetric
-----------  ------------
Ethernet0    off

"""

show_asym_intf_all_masic = """\
Namespace asic0
Interface    Asymmetric
-----------  ------------
Ethernet0    off

Namespace asic1
Interface    Asymmetric
-----------  ------------

"""

show_asym_intf_fake_one_masic = """\
Namespace asic0
Interface    Asymmetric
-----------  ------------

"""

show_prio_all_asic0_masic = """\
Namespace asic0
Interface       Lossless priorities
--------------  ---------------------
Ethernet0       3,4
Ethernet4       3,4
Ethernet8       3,4
Ethernet-BP0    3,4
Ethernet-BP4    3,4
Ethernet-BP256  3,4
Ethernet-BP260  3,4

"""

show_prio_all_asic1_masic = """\
Namespace asic1
Interface       Lossless priorities
--------------  ---------------------
Ethernet0       3,4
Ethernet4       3,4
Ethernet8       3,4
Ethernet-BP0    3,4
Ethernet-BP4    3,4
Ethernet-BP256  3,4

"""

show_prio_all_masic = """\
Namespace asic0
Interface       Lossless priorities
--------------  ---------------------
Ethernet0       3,4
Ethernet4       3,4
Ethernet8       3,4
Ethernet-BP0    3,4
Ethernet-BP4    3,4
Ethernet-BP256  3,4
Ethernet-BP260  3,4

Namespace asic1
Interface       Lossless priorities
--------------  ---------------------
Ethernet0       3,4
Ethernet4       3,4
Ethernet8       3,4
Ethernet-BP0    3,4
Ethernet-BP4    3,4
Ethernet-BP256  3,4

"""

show_prio_intf_one_masic = """\
Namespace asic0
Interface    Lossless priorities
-----------  ---------------------
Ethernet0    3,4

"""

show_prio_intf_all_masic = """\
Namespace asic0
Interface    Lossless priorities
-----------  ---------------------
Ethernet0    3,4

Namespace asic1
Interface    Lossless priorities
-----------  ---------------------
Ethernet0    3,4

"""

show_prio_intf_fake_one_masic = """\
Cannot find interface Ethernet1234 for Namespace asic0
"""

show_prio_intf_fake_all_masic = """\
Cannot find interface Ethernet1234 for Namespace asic0
Cannot find interface Ethernet1234 for Namespace asic1
"""

testData = {
             'pfc_show_asymmetric_all_asic0_masic': {'cmd': ['show', 'asymmetric',
                                                             '--namespace', 'asic0'],
                                                     'rc': 0,
                                                     'rc_output': show_asym_all_asic0_masic
                                                     },
             'pfc_show_asymmetric_all_asic1_masic': {'cmd': ['show', 'asymmetric',
                                                             '--namespace', 'asic1'],
                                                     'rc': 0,
                                                     'rc_output': show_asym_all_asic1_masic
                                                     },
             'pfc_show_asymmetric_all_masic': {'cmd': ['show', 'asymmetric'],
                                               'rc': 0,
                                               'rc_output': show_asym_all_masic
                                               },
             'pfc_show_asymmetric_intf_one_masic': {'cmd': ['show', 'asymmetric',
                                                            'Ethernet0', '--namespace',
                                                            'asic0'],
                                                    'rc': 0,
                                                    'rc_output': show_asym_intf_one_masic
                                                    },
             'pfc_show_asymmetric_intf_all_masic': {'cmd': ['show', 'asymmetric',
                                                            'Ethernet0'],
                                                    'rc': 0,
                                                    'rc_output': show_asym_intf_all_masic
                                                    },
             'pfc_show_asymmetric_intf_fake_one_masic': {'cmd': ['show', 'asymmetric',
                                                                 'Ethernet1234', '--namespace',
                                                                 'asic0'],
                                                         'rc': 0,
                                                         'rc_output': show_asym_intf_fake_one_masic
                                                         },
             'pfc_show_priority_all_asic0_masic': {'cmd': ['show', 'priority',
                                                           '--namespace', 'asic0'],
                                                   'rc': 0,
                                                   'rc_output': show_prio_all_asic0_masic
                                                   },
             'pfc_show_priority_all_asic1_masic': {'cmd': ['show', 'priority',
                                                           '--namespace', 'asic1'],
                                                   'rc': 0,
                                                   'rc_output': show_prio_all_asic1_masic
                                                   },
             'pfc_show_priority_all_masic': {'cmd': ['show', 'priority'],
                                             'rc': 0,
                                             'rc_output': show_prio_all_masic
                                             },
             'pfc_show_priority_intf_one_masic': {'cmd': ['show', 'priority',
                                                          'Ethernet0', '--namespace',
                                                          'asic0'],
                                                  'rc': 0,
                                                  'rc_output': show_prio_intf_one_masic
                                                  },
             'pfc_show_priority_intf_all_masic': {'cmd': ['show', 'priority',
                                                          'Ethernet0'],
                                                  'rc': 0,
                                                  'rc_output': show_prio_intf_all_masic
                                                  },
             'pfc_show_priority_intf_fake_one_masic': {'cmd': ['show', 'priority',
                                                               'Ethernet1234', '--namespace',
                                                               'asic0'],
                                                       'rc': 0,
                                                       'rc_output': show_prio_intf_fake_one_masic
                                                       },
             'pfc_show_priority_intf_fake_all_masic': {'cmd': ['show', 'priority',
                                                               'Ethernet1234'],
                                                       'rc': 0,
                                                       'rc_output': show_prio_intf_fake_all_masic
                                                       },
             'pfc_config_asymmetric_one_masic': {'cmd': ['config', 'asymmetric',
                                                         'on', 'Ethernet0', '--namespace',
                                                         'asic0'],
                                                 'rc': 0,
                                                 'cmp_args': [['asic0', 'PORT', 'Ethernet0', 'pfc_asym', 'on']]
                                                 },
             'pfc_config_asymmetric_invalid_one_masic': {'cmd': ['config', 'asymmetric',
                                                                 'onn', 'Ethernet0', '--namespace',
                                                                 'asic0'],
                                                         'rc': 2,
                                                         'rc_msg': ('Invalid value for '
                                                                    '\'{on|off}\': \'onn\' is not '
                                                                    'one of \'on\', \'off\'')
                                                         },
             'pfc_config_asymmetric_all_masic': {'cmd': ['config', 'asymmetric',
                                                         'on', 'Ethernet0'],
                                                 'rc': 0,
                                                 'cmp_args': [['asic0', 'PORT', 'Ethernet0', 'pfc_asym', 'on'],
                                                              ['asic1', 'PORT', 'Ethernet0', 'pfc_asym', 'on']]
                                                 },
             'pfc_config_asymmetric_invalid_all_masic': {'cmd': ['config', 'asymmetric',
                                                                 'onn', 'Ethernet0'],
                                                         'rc': 2,
                                                         'rc_msg': ('Invalid value for '
                                                                    '\'{on|off}\': \'onn\' is not '
                                                                    'one of \'on\', \'off\'')
                                                         },
             'pfc_config_priority_one_masic': {'cmd': ['config', 'priority',
                                                       'on', 'Ethernet0', '5',
                                                       '--namespace', 'asic0'],
                                               'rc': 0,
                                               'cmp_args': [['asic0', 'PORT_QOS_MAP', 'Ethernet0',
                                                             'pfc_enable', '3,4,5']]
                                               },
             'pfc_config_priority_invalid_one_masic': {'cmd': ['config', 'priority',
                                                               'onn', 'Ethernet0', '5',
                                                               '--namespace', 'asic0'],
                                                       'rc': 2,
                                                       'rc_msg': ('Invalid value for '
                                                                  '\'{on|off}\': \'onn\' is not '
                                                                  'one of \'on\', \'off\'')
                                                       },
             'pfc_config_priority_all_masic': {'cmd': ['config', 'priority',
                                                       'on', 'Ethernet0', '5'],
                                               'rc': 0,
                                               'cmp_args': [['asic0', 'PORT_QOS_MAP', 'Ethernet0',
                                                             'pfc_enable', '3,4,5'],
                                                            ['asic1', 'PORT_QOS_MAP', 'Ethernet0',
                                                             'pfc_enable', '3,4,5']]
                                               },
             'pfc_config_priority_invalid_all_masic': {'cmd': ['config', 'priority',
                                                               'onn', 'Ethernet0', '5'],
                                                       'rc': 2,
                                                       'rc_msg': ('Invalid value for '
                                                                  '\'{on|off}\': \'onn\' is not '
                                                                  'one of \'on\', \'off\'')
                                                       },
}

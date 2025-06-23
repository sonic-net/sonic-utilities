ecn_show_config_output="""\
Profile: AZURE_LOSSLESS
-----------------------  -------
red_max_threshold        2097152
wred_green_enable        true
ecn                      ecn_all
green_min_threshold      1048576
red_min_threshold        1048576
wred_yellow_enable       true
yellow_min_threshold     1048576
green_max_threshold      2097152
green_drop_probability   5
yellow_max_threshold     2097152
wred_red_enable          true
yellow_drop_probability  5
red_drop_probability     5
-----------------------  -------

"""

ecn_show_config_output_specific_namespace = """\
Profile: AZURE_LOSSLESS
-----------------------  -------
red_max_threshold        2097152
ecn                      ecn_all
green_min_threshold      1048576
red_min_threshold        1048576
yellow_min_threshold     1048576
green_max_threshold      2097152
green_drop_probability   5
yellow_max_threshold     2097152
yellow_drop_probability  5
red_drop_probability     5
-----------------------  -------

"""

ecn_show_config_output_multi = """\
Profile: AZURE_LOSSLESS
-----------------------  -------
red_max_threshold        2097152
ecn                      ecn_all
green_min_threshold      1048576
red_min_threshold        1048576
yellow_min_threshold     1048576
green_max_threshold      2097152
green_drop_probability   5
yellow_max_threshold     2097152
yellow_drop_probability  5
red_drop_probability     5
-----------------------  -------

Profile: AZURE_LOSSY
-----------------------  -----
red_max_threshold        32760
red_min_threshold         4095
yellow_max_threshold     32760
yellow_min_threshold      4095
green_max_threshold      32760
green_min_threshold       4095
yellow_drop_probability      2
-----------------------  -----

"""

testData = {
             'ecn_show_config': {'cmd': ['show'],
                                 'args': [],
                                 'rc': 0,
                                 'rc_output': ecn_show_config_output
                                 },
             'ecn_show_config_verbose': {'cmd': ['q_cmd'],
                                         'args': ['-l', '-vv'],
                                         'rc': 0,
                                         'rc_output': ecn_show_config_output + 'Total profiles: 1\n'
                                         },
             'ecn_cfg_gmin': {'cmd': ['config'],
                              'args': ['-profile', 'AZURE_LOSSLESS', '-gmin', '1048600'],
                              'rc': 0,
                              'cmp_args': [',AZURE_LOSSLESS,green_min_threshold,1048600']
                              },
             'ecn_cfg_gmin_verbose': {'cmd': ['config'],
                                      'args': ['-profile', 'AZURE_LOSSLESS', '-gmin', '1048600', '-vv'],
                                      'rc': 0,
                                      'cmp_args': [',AZURE_LOSSLESS,green_min_threshold,1048600'],
                                      'rc_output': ('Running command: ecnconfig -p AZURE_LOSSLESS -gmin 1048600 -vv\n'
                                                    'Setting green_min_threshold value to 1048600\n')
                                      },
             'ecn_cfg_gmax': {'cmd': ['config'],
                              'args': ['-profile', 'AZURE_LOSSLESS', '-gmax', '2097153'],
                              'rc': 0,
                              'cmp_args': [',AZURE_LOSSLESS,green_max_threshold,2097153']
                              },
             'ecn_cfg_ymin': {'cmd': ['config'],
                              'args': ['-profile', 'AZURE_LOSSLESS', '-ymin', '1048600'],
                              'rc': 0,
                              'cmp_args': [',AZURE_LOSSLESS,yellow_min_threshold,1048600']
                              },
             'ecn_cfg_ymax': {'cmd': ['config'],
                              'args': ['-profile', 'AZURE_LOSSLESS', '-ymax', '2097153'],
                              'rc': 0,
                              'cmp_args': [',AZURE_LOSSLESS,yellow_max_threshold,2097153']
                              },
             'ecn_cfg_rmin': {'cmd': ['config'],
                              'args': ['-profile', 'AZURE_LOSSLESS', '-rmin', '1048600'],
                              'rc': 0,
                              'cmp_args': [',AZURE_LOSSLESS,red_min_threshold,1048600']
                              },
             'ecn_cfg_rmax': {'cmd': ['config'],
                              'args': ['-profile', 'AZURE_LOSSLESS', '-rmax', '2097153'],
                              'rc': 0,
                              'cmp_args': [',AZURE_LOSSLESS,red_max_threshold,2097153']
                              },
             'ecn_cfg_rdrop': {'cmd': ['config'],
                               'args': ['-profile', 'AZURE_LOSSLESS', '-rdrop', '10'],
                               'rc': 0,
                               'cmp_args': [',AZURE_LOSSLESS,red_drop_probability,10']
                               },
             'ecn_cfg_ydrop': {'cmd': ['config'],
                               'args': ['-profile', 'AZURE_LOSSLESS', '-ydrop', '11'],
                               'rc': 0,
                               'cmp_args': [',AZURE_LOSSLESS,yellow_drop_probability,11']
                               },
             'ecn_cfg_gdrop': {'cmd': ['config'],
                               'args': ['-profile', 'AZURE_LOSSLESS', '-gdrop', '12'],
                               'rc': 0,
                               'cmp_args': [',AZURE_LOSSLESS,green_drop_probability,12']
                               },
             'ecn_cfg_gdrop_verbose': {'cmd': ['config'],
                                       'args': ['-profile', 'AZURE_LOSSLESS', '-gdrop', '12', '-vv'],
                                       'rc': 0,
                                       'cmp_args': [',AZURE_LOSSLESS,green_drop_probability,12'],
                                       'rc_output': ('Running command: ecnconfig -p AZURE_LOSSLESS -gdrop 12 -vv\n'
                                                     'Setting green_drop_probability value to 12%\n')
                                       },
             'ecn_cfg_multi_set': {'cmd': ['config'],
                                   'args': ['-profile', 'AZURE_LOSSLESS', '-gdrop', '12', '-gmax', '2097153'],
                                   'rc': 0,
                                   'cmp_args': [',AZURE_LOSSLESS,green_drop_probability,12',
                                                ',AZURE_LOSSLESS,green_max_threshold,2097153']
                                   },
             'ecn_cfg_gmin_gmax_invalid': {'cmd': ['config'],
                                           'args': ['-profile', 'AZURE_LOSSLESS', '-gmax',
                                                    '2097153', '-gmin', '2097154'],
                                           'rc': 1,
                                           'rc_msg': ('Invalid gmin (2097154) and gmax (2097153).'
                                                      ' gmin should be smaller than gmax')
                                           },
             'ecn_cfg_ymin_ymax_invalid': {'cmd': ['config'],
                                           'args': ['-profile', 'AZURE_LOSSLESS', '-ymax',
                                                    '2097153', '-ymin', '2097154'],
                                           'rc': 1,
                                           'rc_msg': ('Invalid ymin (2097154) and ymax (2097153).'
                                                      ' ymin should be smaller than ymax')
                                           },
             'ecn_cfg_rmin_rmax_invalid': {'cmd': ['config'],
                                           'args': ['-profile', 'AZURE_LOSSLESS', '-rmax',
                                                    '2097153', '-rmin', '2097154'],
                                           'rc': 1,
                                           'rc_msg': ('Invalid rmin (2097154) and rmax (2097153).'
                                                      ' rmin should be smaller than rmax')
                                           },
             'ecn_cfg_rmax_invalid': {'cmd': ['config'],
                                      'args': ['-profile', 'AZURE_LOSSLESS', '-rmax', '-2097153'],
                                      'rc': 1,
                                      'rc_msg': 'Invalid rmax (-2097153). rmax should be an non-negative integer'
                                      },
             'ecn_cfg_rdrop_invalid': {'cmd': ['config'],
                                       'args': ['-profile', 'AZURE_LOSSLESS', '-rdrop', '105'],
                                       'rc': 1,
                                       'rc_msg': 'Invalid value for "-rdrop": 105 is not in the valid range of 0 to 100'
                                       },
             'ecn_q_get': {'cmd': ['q_cmd'],
                           'args': ['-q', '3'],
                           'rc': 0,
                           'rc_msg': 'ECN status:\nqueue 3: on\n',
                           'cmp_args': [',wred_profile,AZURE_LOSSLESS'],
                           'cmp_q_args': ['3', '4']
                           },
             'ecn_q_get_verbose': {'cmd': ['q_cmd'],
                                   'args': ['-q', '3', '-vv'],
                                   'rc': 0,
                                   'rc_msg': 'ECN status:\n{0} queue 3: on\n',
                                   'cmp_args': [',wred_profile,AZURE_LOSSLESS'],
                                   'cmp_q_args': ['3', '4'],
                                   'db_table': 'DEVICE_NEIGHBOR'
                                   },
             'ecn_lossy_q_get': {'cmd': ['q_cmd'],
                                 'args': ['-q', '2'],
                                 'rc': 0,
                                 'rc_msg': 'ECN status:\nqueue 2: off\n',
                                 'cmp_args': [',None,None'],
                                 'cmp_q_args': ['2']
                                 },
             'ecn_q_all_get_verbose': {'cmd': ['q_cmd'],
                                       'args': ['-q', '3,4', '-vv'],
                                       'rc': 0,
                                       'rc_msg': 'ECN status:\n{0} queue 3: on\n{0} queue 4: on\n',
                                       'cmp_args': [',wred_profile,AZURE_LOSSLESS'],
                                       'cmp_q_args': ['3', '4'],
                                       'db_table': 'DEVICE_NEIGHBOR'
                                       },
             'ecn_q_all_get': {'cmd': ['q_cmd'],
                               'args': ['-q', '3,4'],
                               'rc': 0,
                               'rc_msg': 'ECN status:\nqueue 3: on\nqueue 4: on\n',
                               'cmp_args': [',wred_profile,AZURE_LOSSLESS'],
                               'cmp_q_args': ['3', '4']
                               },
             'ecn_cfg_q_all_off': {'cmd': ['q_cmd'],
                                   'args': ['-q', '3,4', 'off'],
                                   'rc': 0,
                                   'cmp_args': [',None,None'],
                                   'cmp_q_args': ['3', '4']
                                   },
             'ecn_cfg_q_all_off_verbose': {'cmd': ['q_cmd'],
                                           'args': ['-q', '3,4', 'off', '-vv'],
                                           'rc': 0,
                                           'cmp_args': [',None,None'],
                                           'cmp_q_args': ['3', '4'],
                                           'db_table': 'DEVICE_NEIGHBOR',
                                           'rc_msg': 'Disable ECN on {0} queue 3\nDisable ECN on {0} queue 4'
                                           },
             'ecn_cfg_q_off': {'cmd': ['q_cmd'],
                               'args': ['-q', '3', 'off'],
                               'rc': 0,
                               'cmp_args': [',None,None', ',wred_profile,AZURE_LOSSLESS'],
                               'cmp_q_args': ['3'],
                               'other_q': ['4']
                               },
             'ecn_cfg_q_off_verbose': {'cmd': ['q_cmd'],
                                       'args': ['-q', '3', 'off', '-vv'],
                                       'rc': 0,
                                       'cmp_args': [',None,None', ',wred_profile,AZURE_LOSSLESS'],
                                       'cmp_q_args': ['3'],
                                       'other_q': ['4'],
                                       'db_table': 'DEVICE_NEIGHBOR',
                                       'rc_msg': 'Disable ECN on {0} queue 3'
                                       },
             'ecn_cfg_q_all_on': {'cmd': ['q_cmd'],
                                  'args': ['-q', '3,4', 'on'],
                                  'rc': 0,
                                  'cmp_args': [',wred_profile,AZURE_LOSSLESS'],
                                  'cmp_q_args': ['3', '4']
                                  },
             'ecn_cfg_q_all_on_verbose': {'cmd': ['q_cmd'],
                                          'args': ['-q', '3,4', 'on', '-vv'],
                                          'rc': 0,
                                          'cmp_args': [',wred_profile,AZURE_LOSSLESS'],
                                          'cmp_q_args': ['3', '4'],
                                          'db_table': 'DEVICE_NEIGHBOR',
                                          'rc_msg': 'Enable ECN on {0} queue 3\nEnable ECN on {0} queue 4'
                                          },
             'ecn_cfg_q_on': {'cmd': ['q_cmd'],
                              'args': ['-q', '4', 'on'],
                              'rc': 0,
                              'cmp_args': [',wred_profile,AZURE_LOSSLESS'],
                              'cmp_q_args': ['3', '4']
                              },
             'ecn_cfg_q_on_verbose': {'cmd': ['q_cmd'],
                                      'args': ['-q', '4', 'on', '-vv'],
                                      'rc': 0,
                                      'cmp_args': [',wred_profile,AZURE_LOSSLESS'],
                                      'cmp_q_args': ['3', '4'],
                                      'db_table': 'DEVICE_NEIGHBOR',
                                      'rc_msg': 'Enable ECN on {0} queue 4'
                                      },
             'ecn_cfg_lossy_q_on': {'cmd': ['q_cmd'],
                                    'args': ['-q', '0,1,2,5,6,7', 'on'],
                                    'rc': 0,
                                    'cmp_args': [',wred_profile,AZURE_LOSSLESS'],
                                    'cmp_q_args': ['0', '1', '2', '5', '6', '7']
                                    },
             'ecn_show_config_masic': {'cmd': ['show_masic'],
                                       'args': ['-l'],
                                       'rc': 0,
                                       'rc_output': ecn_show_config_output_multi,
                                       },
             'test_ecn_show_config_verbose_masic': {'cmd': ['show_masic'],
                                                    'args': ['-l', '-vv'],
                                                    'rc': 0,
                                                    'rc_output': ecn_show_config_output_multi + 'Total profiles: 2\n',
                                                    },
             'test_ecn_show_config_namespace': {'cmd': ['show_masic'],
                                                'args': ['-l', '-n', 'asic0'],
                                                'rc': 0,
                                                'rc_output': ecn_show_config_output_specific_namespace,
                                                },
             'test_ecn_show_config_namespace_verbose': {'cmd': ['show_masic'],
                                                        'args': ['-l', '-n', 'asic0', '-vv'],
                                                        'rc': 0,
                                                        'rc_output': ecn_show_config_output_specific_namespace
                                                        + 'Total profiles: 1\n',
                                                        },
             'ecn_cfg_threshold_masic': {'cmd': ['config_masic'],
                                         'args': ['-p', 'AZURE_LOSSY', '-gmax', '35000', '-n', 'asic1'],
                                         'rc': 0,
                                         'cmp_args': ['asic1,AZURE_LOSSY,green_max_threshold,35000']
                                         },
             'ecn_cfg_probability_masic': {'cmd': ['config_masic'],
                                           'args': ['-p', 'AZURE_LOSSY', '-ydrop', '3', '-n', 'asic1'],
                                           'rc': 0,
                                           'cmp_args': ['asic1,AZURE_LOSSY,yellow_drop_probability,3']
                                           },
             'ecn_cfg_gdrop_verbose_all_masic': {'cmd': ['config_masic'],
                                                 'args': ['-p', 'AZURE_LOSSLESS', '-gdrop', '12', '-vv'],
                                                 'rc': 0,
                                                 'cmp_args': ['asic0-asic1,AZURE_LOSSLESS,green_drop_probability,12'],
                                                 'rc_output': ('Setting green_drop_probability value to 12% '
                                                               'for namespace asic0\n'
                                                               'Setting green_drop_probability value to 12% '
                                                               'for namespace asic1\n')
                                                 },
             'ecn_cfg_multi_set_verbose_all_masic': {'cmd': ['config_masic'],
                                                     'args': ['-p', 'AZURE_LOSSLESS', '-gdrop',
                                                              '14', '-gmax', '2097153', '-vv'],
                                                     'rc': 0,
                                                     'cmp_args': [('asic0-asic1,AZURE_LOSSLESS,'
                                                                   'green_drop_probability,14'),
                                                                  ('asic0-asic1,AZURE_LOSSLESS,'
                                                                   'green_max_threshold,2097153')],
                                                     'rc_output': ('Setting green_max_threshold value to 2097153 '
                                                                   'for namespace asic0\n'
                                                                   'Setting green_max_threshold value to 2097153 '
                                                                   'for namespace asic1\n'
                                                                   'Setting green_drop_probability value to 14% '
                                                                   'for namespace asic0\n'
                                                                   'Setting green_drop_probability value to 14% '
                                                                   'for namespace asic1\n')
                                                     },
             'ecn_q_get_masic': {'cmd': ['q_cmd'],
                                 'args': ['-q', '1', '-n', 'asic0'],
                                 'rc': 0,
                                 'rc_msg': 'ECN status for namespace asic0:\nqueue 1: on\n',
                                 'cmp_args': ['asic0,wred_profile,AZURE_LOSSLESS'],
                                 'cmp_q_args': ['1']
                                 },
             'ecn_q_get_verbose_masic': {'cmd': ['q_cmd'],
                                         'args': ['-q', '1', '-vv', '-n', 'asic0'],
                                         'rc': 0,
                                         'rc_msg': 'ECN status for namespace asic0:\nEthernet4 queue 1: on\n',
                                         'cmp_args': ['asic0,wred_profile,AZURE_LOSSLESS'],
                                         'cmp_q_args': ['1'],
                                         'db_table': 'DEVICE_NEIGHBOR'
                                         },
             'ecn_q_get_all_ns_masic': {'cmd': ['q_cmd'],
                                        'args': ['-q', '0'],
                                        'rc': 0,
                                        'rc_msg': ('ECN status for namespace asic0:\nqueue 0: off\n'
                                                   'ECN status for namespace asic1:\nqueue 0: on\n')
                                        },
             'ecn_q_get_all_ns_verbose_masic': {'cmd': ['q_cmd'],
                                                'args': ['-q', '0', '-vv'],
                                                'rc': 0,
                                                'rc_msg': ('ECN status for namespace asic0:\nEthernet4 queue 0: off\n'
                                                           'ECN status for namespace asic1:\nEthernet0 queue 0: on\n')
                                                },
             'ecn_cfg_q_all_ns_off_masic': {'cmd': ['q_cmd'],
                                            'args': ['-q', '0,1', 'off'],
                                            'rc': 0,
                                            'cmp_args': ['asic0-asic1,None,None'],
                                            'cmp_q_args': ['0', '1']
                                            },
             'ecn_cfg_q_one_ns_off_verbose_masic': {'cmd': ['q_cmd'],
                                                    'args': ['-q', '1', 'on', '-n', 'asic1', '-vv'],
                                                    'rc': 0,
                                                    'rc_msg': 'Enable ECN on Ethernet0 queue 1\n',
                                                    'cmp_args': ['asic1,wred_profile,AZURE_LOSSLESS',
                                                                 'asic1,wred_profile,AZURE_LOSSLESS'],
                                                    'cmp_q_args': ['0'],
                                                    'other_q': ['1']
                                                    },
             'ecn_cfg_q_voq': {'cmd': ['q_cmd'],
                               'args': ['-q', '3', 'off'],
                               'rc': 0,
                               }
           }

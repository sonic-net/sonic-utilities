"""
Module holding correct dictionaries for test YANG models
"""

one_table_container = {
   "tables":[
      {
         "description":"TABLE_1 description",
         "name":"TABLE_1",
         "static-objects":[
            {
            }
         ]
      }
   ]
}

two_table_containers = {
   "tables":[
      {
         "description":"TABLE_1 description",
         "name":"TABLE_1",
         "static-objects":[
            {
               
            }
         ]
      },
      {
         "description":"TABLE_2 description",
         "name":"TABLE_2",
         "static-objects":[
            {
               
            }
         ]
      }
   ]
}

one_object_container = {
   "tables":[
      {
         "description":"TABLE_1 description",
         "name":"TABLE_1",
         "static-objects":[
            {
                "name":"OBJECT_1",
                "description":"OBJECT_1 description",
                "attrs":[
                ]
            }
         ]
      }
   ]
}

two_object_containers = {
   "tables":[
      {
         "description":"FIRST_TABLE description",
         "name":"TABLE_1",
         "static-objects":[
            {
                "name":"OBJECT_1",
                "description":"OBJECT_1 description",
                "attrs":[
                ]
            },
            {
                "name":"OBJECT_2",
                "description":"OBJECT_2 description",
                "attrs":[
                ]
            }
         ]
      }
   ]
}

one_list = {
   "tables":[
      {
         "description":"TABLE_1 description",
         "name":"TABLE_1",
         "dynamic-objects":[
            {
                "name":"TABLE_1_LIST",
                "description":"TABLE_1_LIST description",
                "keys":[
                    {
                        "name": "key_name",
                        "description": "",
                    }
                ],
                "attrs":[
                ]
            }
         ]
      }
   ]
}

two_lists = {
   "tables":[
      {
         "description":"TABLE_1 description",
         "name":"TABLE_1",
         "dynamic-objects":[
            {
                "name":"TABLE_1_LIST_1",
                "description":"TABLE_1_LIST_1 description",
                "keys":[
                    {
                        "name": "key_name1",
                        "description": "",
                    }
                ],
                "attrs":[
                ]
            },
            {
                "name":"TABLE_1_LIST_2",
                "description":"TABLE_1_LIST_2 description",
                "keys":[
                    {
                        "name": "key_name2",
                        "description": "",
                    }
                ],
                "attrs":[
                ]
            }
         ]
      }
   ]
}

static_object_complex_1 = {
   "tables":[
      {
         "description":"TABLE_1 description",
         "name":"TABLE_1",
         "static-objects":[
            {
                "name":"OBJECT_1",
                "description":"OBJECT_1 description",
                "attrs":[
                    {
                        "name":"OBJ_1_LEAF_1",
                        "description": "OBJ_1_LEAF_1 description",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"OBJ_1_LEAF_LIST_1",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": True
                    },
                    {
                        "name":"OBJ_1_CHOICE_1_LEAF_1",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"OBJ_1_CHOICE_1_LEAF_2",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    }
                ]
            }
         ]
      }
   ]
}

static_object_complex_2 = {
   "tables":[
      {
         "description":"TABLE_1 description",
         "name":"TABLE_1",
         "static-objects":[
            {
                "name":"OBJECT_1",
                "description":"OBJECT_1 description",
                "attrs":[
                    {
                        "name":"OBJ_1_LEAF_1",
                        "description": "OBJ_1_LEAF_1 description",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"OBJ_1_LEAF_2",
                        "description": "OBJ_1_LEAF_2 description",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"OBJ_1_LEAF_LIST_1",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": True
                    },
                    {
                        "name":"OBJ_1_LEAF_LIST_2",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": True
                    },
                    {
                        "name":"OBJ_1_CHOICE_1_LEAF_1",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"OBJ_1_CHOICE_1_LEAF_2",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"OBJ_1_CHOICE_2_LEAF_1",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"OBJ_1_CHOICE_2_LEAF_2",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                ]
            }
         ]
      }
   ]
}

dynamic_object_complex_1 = {
   "tables":[
      {
         "description":"TABLE_1 description",
         "name":"TABLE_1",
         "dynamic-objects":[
            {
                "name":"OBJECT_1_LIST",
                "description":"OBJECT_1_LIST description",
                "attrs":[
                    {
                        "name":"OBJ_1_LEAF_1",
                        "description": "OBJ_1_LEAF_1 description",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"OBJ_1_LEAF_LIST_1",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": True
                    },
                    {
                        "name":"OBJ_1_CHOICE_1_LEAF_1",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"OBJ_1_CHOICE_1_LEAF_2",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    }
                ],
                "keys":[
                    {
                        "name": "KEY_LEAF_1",
                        "description": "KEY_LEAF_1 description",
                    }
                ]
            }
         ]
      }
   ]
}

dynamic_object_complex_2 = {
   "tables":[
      {
         "description":"TABLE_1 description",
         "name":"TABLE_1",
         "dynamic-objects":[
            {
                "name":"OBJECT_1_LIST",
                "description":"OBJECT_1_LIST description",
                "attrs":[
                    {
                        "name":"OBJ_1_LEAF_1",
                        "description": "OBJ_1_LEAF_1 description",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"OBJ_1_LEAF_2",
                        "description": "OBJ_1_LEAF_2 description",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"OBJ_1_LEAF_LIST_1",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": True
                    },
                    {
                        "name":"OBJ_1_LEAF_LIST_2",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": True
                    },
                    {
                        "name":"OBJ_1_CHOICE_1_LEAF_1",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"OBJ_1_CHOICE_1_LEAF_2",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"OBJ_1_CHOICE_2_LEAF_1",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"OBJ_1_CHOICE_2_LEAF_2",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    }
                ],
                "keys":[
                    {
                        "name": "KEY_LEAF_1",
                        "description": "KEY_LEAF_1 description",
                    },
                    {
                        "name": "KEY_LEAF_2",
                        "description": "KEY_LEAF_2 description",
                    }
                ]
            }
         ]
      }
   ]
}

choice_complex = {
   "tables":[
      {
         "description":"TABLE_1 description",
         "name":"TABLE_1",
         "static-objects":[
            {
                "name":"OBJECT_1",
                "description":"OBJECT_1 description",
                "attrs":[
                    {
                        "name":"LEAF_1",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"GR_1_LEAF_1",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"GR_1_LEAF_2",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"LEAF_LIST_1",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": True
                    },
                    {
                        "name":"LEAF_2",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"LEAF_3",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"GR_5_LEAF_1",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"GR_5_LEAF_2",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"GR_2_LEAF_1",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"GR_2_LEAF_2",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"GR_3_LEAF_1",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"GR_3_LEAF_2",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"LEAF_LIST_2",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": True
                    },
                    {
                        "name":"LEAF_LIST_3",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": True
                    },
                ]
            }
         ]
      }
   ]
}

grouping_complex = {
   "tables":[
      {
         "description":"TABLE_1 description",
         "name":"TABLE_1",
         "static-objects":[
            {
                "name":"OBJECT_1",
                "description":"OBJECT_1 description",
                "attrs":[
                    {
                        "name":"GR_1_LEAF_1",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"GR_1_LEAF_2",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                ]
            },
            {
                "name":"OBJECT_2",
                "description":"OBJECT_2 description",
                "attrs":[
                    {
                        "name":"GR_5_LEAF_1",
                        "description": "GR_5_LEAF_1 refine description",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"GR_6_LEAF_1",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"GR_6_LEAF_2",
                        "description": "GR_6_LEAF_2 refine description",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"GR_4_LEAF_1",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"GR_4_LEAF_2",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"GR_5_LEAF_LIST_1",
                        "description": "GR_5_LEAF_LIST_1 refine description",
                        "is-mandatory": False,
                        "is-leaf-list": True
                    },
                    {
                        "name":"GR_6_CASE_1_LEAF_1",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"GR_6_CASE_1_LEAF_LIST_1",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": True
                    },
                    {
                        "name":"GR_6_CASE_2_LEAF_1",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"GR_6_CASE_2_LEAF_2",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": False
                    },
                    {
                        "name":"GR_6_CASE_2_LEAF_LIST_1",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": True
                    },
                    {
                        "name":"GR_6_CASE_2_LEAF_LIST_2",
                        "description": "",
                        "is-mandatory": False,
                        "is-leaf-list": True
                    },
                ]
            }
         ]
      }
   ]
}


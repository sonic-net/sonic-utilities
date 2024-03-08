show_buffer_configuration="""\
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

show_buffer_information_output="""\
Pool: egress_lossless_pool
----  --------
mode  dynamic
size  13945824
type  egress
----  --------

Pool: egress_lossy_pool
----  -------
mode  dynamic
size  4580864
type  egress
----  -------

Pool: ingress_lossless_pool
----  -------
mode  dynamic
size  4580864
type  ingress
----  -------

Pool: ingress_lossy_pool
----  -------
mode  dynamic
size  4580864
type  ingress
----  -------

Profile: ingress_lossy_profile
----------  ------------------
dynamic_th  3
pool        ingress_lossy_pool
size        0
----------  ------------------

Profile: headroom_profile
----------  ---------------------
dynamic_th  0
pool        ingress_lossless_pool
xon         18432
xoff        32768
size        51200
----------  ---------------------

"""

testData = {
             'show_buffer_configuration' :  [ {'cmd' : ['buffer', 'configuration'],
                                       'rc_output': show_buffer_configuration
                                      }
                                    ],
             'show_buffer_information' :  [ {'cmd' : ['buffer', 'information'],
                                       'rc_output': show_buffer_information_output
                                      }
                                    ]
           }

import os
import sys
import traceback

import mock_tables.dbconnector
from click.testing import CliRunner
from unittest import mock
from utilities_common.db import Db

sys.modules['sonic_platform_base'] = mock.Mock()
sys.modules['sonic_platform_base.sonic_sfp'] = mock.Mock()
sys.modules['sonic_platform_base.sonic_sfp.sfputilhelper'] = mock.Mock()
sys.modules['sonic_y_cable'] = mock.Mock()
sys.modules['y_cable'] = mock.Mock()
sys.modules['sonic_y_cable.y_cable'] = mock.Mock()
sys.modules['platform_sfputil'] = mock.Mock()
sys.modules['platform_sfputil_helper'] = mock.Mock()
sys.modules['utilities_common.platform_sfputil_helper'] = mock.Mock()
sys.modules['show.muxcable.platform_sfputil'] = mock.Mock()
#sys.modules['os'] = mock.Mock()
#sys.modules['os.geteuid'] = mock.Mock()
#sys.modules['platform_sfputil'] = mock.Mock()
import config.main as config
import show.main as show


tabular_data_status_output_expected = """\
PORT        STATUS    SERVER_STATUS    HEALTH     HWSTATUS      LAST_SWITCHOVER_TIME
----------  --------  ---------------  ---------  ------------  ---------------------------
Ethernet0   active    active           healthy    inconsistent  2021-May-13 10:01:15.696728
Ethernet4   standby   standby          healthy    consistent
Ethernet8   standby   standby          unhealthy  consistent
Ethernet12  active    unknown          unhealthy  inconsistent
Ethernet16  standby   standby          healthy    consistent
Ethernet32  active    active           healthy    inconsistent
"""

tabular_data_status_output_expected_alias = """\
PORT    STATUS    SERVER_STATUS    HEALTH     HWSTATUS      LAST_SWITCHOVER_TIME
------  --------  ---------------  ---------  ------------  ---------------------------
etp1    active    active           healthy    inconsistent  2021-May-13 10:01:15.696728
etp2    standby   standby          healthy    consistent
etp3    standby   standby          unhealthy  consistent
etp4    active    unknown          unhealthy  inconsistent
etp5    standby   standby          healthy    consistent
etp9    active    active           healthy    inconsistent
"""


json_data_status_output_expected = """\
{
    "MUX_CABLE": {
        "Ethernet0": {
            "STATUS": "active",
            "SERVER_STATUS": "active",
            "HEALTH": "healthy",
            "HWSTATUS": "inconsistent",
            "LAST_SWITCHOVER_TIME": "2021-May-13 10:01:15.696728"
        },
        "Ethernet4": {
            "STATUS": "standby",
            "SERVER_STATUS": "standby",
            "HEALTH": "healthy",
            "HWSTATUS": "consistent",
            "LAST_SWITCHOVER_TIME": ""
        },
        "Ethernet8": {
            "STATUS": "standby",
            "SERVER_STATUS": "standby",
            "HEALTH": "unhealthy",
            "HWSTATUS": "consistent",
            "LAST_SWITCHOVER_TIME": ""
        },
        "Ethernet12": {
            "STATUS": "active",
            "SERVER_STATUS": "unknown",
            "HEALTH": "unhealthy",
            "HWSTATUS": "inconsistent",
            "LAST_SWITCHOVER_TIME": ""
        },
        "Ethernet16": {
            "STATUS": "standby",
            "SERVER_STATUS": "standby",
            "HEALTH": "healthy",
            "HWSTATUS": "consistent",
            "LAST_SWITCHOVER_TIME": ""
        },
        "Ethernet32": {
            "STATUS": "active",
            "SERVER_STATUS": "active",
            "HEALTH": "healthy",
            "HWSTATUS": "inconsistent",
            "LAST_SWITCHOVER_TIME": ""
        }
    }
}
"""

json_data_status_output_expected_alias = """\
{
    "MUX_CABLE": {
        "etp1": {
            "STATUS": "active",
            "SERVER_STATUS": "active",
            "HEALTH": "healthy",
            "HWSTATUS": "inconsistent",
            "LAST_SWITCHOVER_TIME": "2021-May-13 10:01:15.696728"
        },
        "etp2": {
            "STATUS": "standby",
            "SERVER_STATUS": "standby",
            "HEALTH": "healthy",
            "HWSTATUS": "consistent",
            "LAST_SWITCHOVER_TIME": ""
        },
        "etp3": {
            "STATUS": "standby",
            "SERVER_STATUS": "standby",
            "HEALTH": "unhealthy",
            "HWSTATUS": "consistent",
            "LAST_SWITCHOVER_TIME": ""
        },
        "etp4": {
            "STATUS": "active",
            "SERVER_STATUS": "unknown",
            "HEALTH": "unhealthy",
            "HWSTATUS": "inconsistent",
            "LAST_SWITCHOVER_TIME": ""
        },
        "etp5": {
            "STATUS": "standby",
            "SERVER_STATUS": "standby",
            "HEALTH": "healthy",
            "HWSTATUS": "consistent",
            "LAST_SWITCHOVER_TIME": ""
        },
        "etp9": {
            "STATUS": "active",
            "SERVER_STATUS": "active",
            "HEALTH": "healthy",
            "HWSTATUS": "inconsistent",
            "LAST_SWITCHOVER_TIME": ""
        }
    }
}
"""


tabular_data_config_output_expected = """\
SWITCH_NAME    PEER_TOR
-------------  ----------
sonic-switch   10.2.2.2
port        state    ipv4      ipv6      cable_type      soc_ipv4
----------  -------  --------  --------  --------------  ----------
Ethernet0   active   10.2.1.1  e800::46
Ethernet4   auto     10.3.1.1  e801::46
Ethernet8   active   10.4.1.1  e802::46
Ethernet12  active   10.4.1.1  e802::46
Ethernet16  standby  10.1.1.1  fc00::75  active-standby
Ethernet28  manual   10.1.1.1  fc00::75
Ethernet32  auto     10.1.1.1  fc00::75  active-active   10.1.1.2
"""

tabular_data_config_output_expected_alias = """\
SWITCH_NAME    PEER_TOR
-------------  ----------
sonic-switch   10.2.2.2
port    state    ipv4      ipv6      cable_type      soc_ipv4
------  -------  --------  --------  --------------  ----------
etp1    active   10.2.1.1  e800::46
etp2    auto     10.3.1.1  e801::46
etp3    active   10.4.1.1  e802::46
etp4    active   10.4.1.1  e802::46
etp5    standby  10.1.1.1  fc00::75  active-standby
etp8    manual   10.1.1.1  fc00::75
etp9    auto     10.1.1.1  fc00::75  active-active   10.1.1.2
"""

json_data_status_config_output_expected = """\
{
    "MUX_CABLE": {
        "PEER_TOR": "10.2.2.2",
        "PORTS": {
            "Ethernet0": {
                "STATE": "active",
                "SERVER": {
                    "IPv4": "10.2.1.1",
                    "IPv6": "e800::46"
                }
            },
            "Ethernet4": {
                "STATE": "auto",
                "SERVER": {
                    "IPv4": "10.3.1.1",
                    "IPv6": "e801::46"
                }
            },
            "Ethernet8": {
                "STATE": "active",
                "SERVER": {
                    "IPv4": "10.4.1.1",
                    "IPv6": "e802::46"
                }
            },
            "Ethernet12": {
                "STATE": "active",
                "SERVER": {
                    "IPv4": "10.4.1.1",
                    "IPv6": "e802::46"
                }
            },
            "Ethernet16": {
                "STATE": "standby",
                "SERVER": {
                    "IPv4": "10.1.1.1",
                    "IPv6": "fc00::75",
                    "cable_type": "active-standby"
                }
            },
            "Ethernet28": {
                "STATE": "manual",
                "SERVER": {
                    "IPv4": "10.1.1.1",
                    "IPv6": "fc00::75"
                }
            },
            "Ethernet32": {
                "STATE": "auto",
                "SERVER": {
                    "IPv4": "10.1.1.1",
                    "IPv6": "fc00::75",
                    "cable_type": "active-active",
                    "soc_ipv4": "10.1.1.2"
                }
            }
        }
    }
}
"""

json_data_status_config_output_expected_alias = """\
{
    "MUX_CABLE": {
        "PEER_TOR": "10.2.2.2",
        "PORTS": {
            "etp1": {
                "STATE": "active",
                "SERVER": {
                    "IPv4": "10.2.1.1",
                    "IPv6": "e800::46"
                }
            },
            "etp2": {
                "STATE": "auto",
                "SERVER": {
                    "IPv4": "10.3.1.1",
                    "IPv6": "e801::46"
                }
            },
            "etp3": {
                "STATE": "active",
                "SERVER": {
                    "IPv4": "10.4.1.1",
                    "IPv6": "e802::46"
                }
            },
            "etp4": {
                "STATE": "active",
                "SERVER": {
                    "IPv4": "10.4.1.1",
                    "IPv6": "e802::46"
                }
            },
            "etp5": {
                "STATE": "standby",
                "SERVER": {
                    "IPv4": "10.1.1.1",
                    "IPv6": "fc00::75",
                    "cable_type": "active-standby"
                }
            },
            "etp8": {
                "STATE": "manual",
                "SERVER": {
                    "IPv4": "10.1.1.1",
                    "IPv6": "fc00::75"
                }
            },
            "etp9": {
                "STATE": "auto",
                "SERVER": {
                    "IPv4": "10.1.1.1",
                    "IPv6": "fc00::75",
                    "cable_type": "active-active",
                    "soc_ipv4": "10.1.1.2"
                }
            }
        }
    }
}
"""

json_port_data_status_config_output_expected = """\
{
    "MUX_CABLE": {
        "PEER_TOR": "10.2.2.2",
        "PORTS": {
            "Ethernet32": {
                "STATE": "auto",
                "SERVER": {
                    "IPv4": "10.1.1.1",
                    "IPv6": "fc00::75"
                }
            }
        }
    }
}
"""

json_port_data_status_config_output_expected_alias = """\
{
    "MUX_CABLE": {
        "PEER_TOR": "10.2.2.2",
        "PORTS": {
            "etp9": {
                "STATE": "auto",
                "SERVER": {
                    "IPv4": "10.1.1.1",
                    "IPv6": "fc00::75"
                }
            }
        }
    }
}
"""

json_data_config_output_auto_expected = """\
{
    "Ethernet32": "OK",
    "Ethernet0": "OK",
    "Ethernet4": "OK",
    "Ethernet8": "OK",
    "Ethernet16": "OK",
    "Ethernet12": "OK"
}
"""

json_data_config_output_auto_expected_alias = """\
{
    "etp9": "OK",
    "etp1": "OK",
    "etp2": "OK",
    "etp3": "OK",
    "etp5": "OK",
    "etp4": "OK"
}
"""

json_data_config_output_active_expected = """\
{
    "Ethernet32": "OK",
    "Ethernet0": "OK",
    "Ethernet4": "INPROGRESS",
    "Ethernet8": "OK",
    "Ethernet16": "INPROGRESS",
    "Ethernet12": "OK"
}
"""

json_data_config_output_active_expected_alias = """\
{
    "etp9": "OK",
    "etp1": "OK",
    "etp2": "INPROGRESS",
    "etp3": "OK",
    "etp5": "INPROGRESS",
    "etp4": "OK"
}
"""

expected_muxcable_cableinfo_output = """\
Vendor    Model
--------  ---------------
Credo     CACL1X321P2PA1M
"""

expected_muxcable_cableinfo_invalid_port_output = """\
Invalid port 'abc'
ERR: Unable to get a port on muxcable port
"""

show_muxcable_hwmode_muxdirection_active_expected_output = """\
Port        Direction    Presence
----------  -----------  ----------
Ethernet12  active       True
"""

show_muxcable_hwmode_muxdirection_active_expected_output_alias = """\
Port    Direction    Presence
------  -----------  ----------
etp4    active       True
"""

show_muxcable_hwmode_muxdirection_standby_expected_output = """\
Port        Direction    Presence
----------  -----------  ----------
Ethernet12  standby      True
"""

show_muxcable_hwmode_muxdirection_standby_expected_output_alias = """\
Port    Direction    Presence
------  -----------  ----------
etp4    standby      True
"""

show_muxcable_firmware_version_expected_output = """\
{
    "version_self_active": "0.6MS",
    "version_self_inactive": "0.6MS",
    "version_self_next": "0.6MS",
    "version_peer_active": "0.6MS",
    "version_peer_inactive": "0.6MS",
    "version_peer_next": "0.6MS",
    "version_nic_active": "0.6MS",
    "version_nic_inactive": "0.6MS",
    "version_nic_next": "0.6MS"
}
"""

show_muxcable_firmware_version_all_expected_output = """\
{
    "Ethernet12": {
        "version_nic_active": "0.1MS",
        "version_nic_inactive": "0.1MS",
        "version_nic_next": "0.1MS",
        "version_peer_active": "0.1MS",
        "version_peer_inactive": "0.1MS",
        "version_peer_next": "0.1MS",
        "version_self_active": "0.1MS",
        "version_self_inactive": "0.1MS",
        "version_self_next": "0.1MS"
    }
}
"""

show_muxcable_firmware_version_all_active_expected_output = """\
{
    "Ethernet12": {
        "version_nic_active": "0.1MS",
        "version_peer_active": "0.1MS",
        "version_self_active": "0.1MS"
    }
}
"""



show_muxcable_firmware_version_active_expected_output = """\
{
    "version_self_active": "0.6MS",
    "version_peer_active": "0.6MS",
    "version_nic_active": "0.6MS"
}
"""

show_muxcable_metrics_expected_output = """\
PORT       EVENT                         TIME
---------  ----------------------------  ---------------------------
Ethernet0  linkmgrd_switch_active_start  2021-May-13 10:00:21.420898
Ethernet0  xcvrd_switch_standby_start    2021-May-13 10:01:15.690835
Ethernet0  xcvrd_switch_standby_end      2021-May-13 10:01:15.696051
Ethernet0  linkmgrd_switch_standby_end   2021-May-13 10:01:15.696728
"""

show_muxcable_metrics_expected_output_alias = """\
PORT    EVENT                         TIME
------  ----------------------------  ---------------------------
etp1    linkmgrd_switch_active_start  2021-May-13 10:00:21.420898
etp1    xcvrd_switch_standby_start    2021-May-13 10:01:15.690835
etp1    xcvrd_switch_standby_end      2021-May-13 10:01:15.696051
etp1    linkmgrd_switch_standby_end   2021-May-13 10:01:15.696728
"""

show_muxcable_metrics_expected_output_json = """\
{
    "linkmgrd_switch_active_start": "2021-May-13 10:00:21.420898",
    "xcvrd_switch_standby_start": "2021-May-13 10:01:15.690835",
    "xcvrd_switch_standby_end": "2021-May-13 10:01:15.696051",
    "linkmgrd_switch_standby_end": "2021-May-13 10:01:15.696728"
}
"""

show_muxcable_packetloss_expected_output="""\
PORT       COUNT                 VALUE
---------  ------------------  -------
Ethernet0  pck_loss_count          612
Ethernet0  pck_expected_count      840
PORT       EVENT                      TIME
---------  -------------------------  ---------------------------
Ethernet0  link_prober_unknown_start  2022-Jan-26 03:13:05.366900
Ethernet0  link_prober_unknown_end    2022-Jan-26 03:17:35.446580
"""

show_muxcable_packetloss_expected_output_json="""\
{
    "link_prober_unknown_start": "2022-Jan-26 03:13:05.366900",
    "link_prober_unknown_end": "2022-Jan-26 03:17:35.446580",
    "pck_loss_count": "612",
    "pck_expected_count": "840"
}
"""

show_muxcable_tunnel_route_expected_output_json="""\
{
    "TUNNEL_ROUTE": {
        "Ethernet0": {
            "server_ipv4": {
                "DEST": "10.2.1.1",
                "kernel": 1,
                "asic": 1
            }
        },
        "Ethernet4": {
            "server_ipv4": {
                "DEST": "10.3.1.1",
                "kernel": 1,
                "asic": false
            }
        }
    }
}
"""

show_muxcable_tunnel_route_expected_output="""\
PORT       DEST_TYPE    DEST_ADDRESS    kernel    asic
---------  -----------  --------------  --------  ------
Ethernet0  server_ipv4  10.2.1.1        added     added
Ethernet4  server_ipv4  10.3.1.1        added     -
"""

show_muxcable_tunnel_route_expected_output_port_json="""\
{
    "TUNNEL_ROUTE": {
        "Ethernet0": {
            "server_ipv4": {
                "DEST": "10.2.1.1",
                "kernel": 1,
                "asic": 1
            }
        }
    }
}
"""

show_muxcable_tunnel_route_expected_port_output="""\
PORT       DEST_TYPE    DEST_ADDRESS    kernel    asic
---------  -----------  --------------  --------  ------
Ethernet0  server_ipv4  10.2.1.1        added     added
"""

class TestMuxcable(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        #show.muxcable.platform_sfputil.logical = mock.Mock(return_value=["Ethernet0", "Ethernet4"])
        print("SETUP")

    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value=({ 0 :"active",
                                                                                              1  :"standby",
                                                                                              2 : "True"})))
    def test_muxcable_status(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands["muxcable"].commands["status"], obj=db)

        assert result.exit_code == 0
        assert result.output == tabular_data_status_output_expected

    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value=({ 0 :"active",
                                                                                              1  :"standby",
                                                                                              2 : "True"})))
    def test_muxcable_status_alias(self):
        runner = CliRunner()
        db = Db()
        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["muxcable"].commands["status"], obj=db)
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"

        assert result.exit_code == 0
        assert result.output == tabular_data_status_output_expected_alias

    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value=({ 0 :"active",
                                                                                              1  :"standby",
                                                                                              2 : "True"})))
    def test_muxcable_status_json(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["status"], ["--json"], obj=db)

        assert result.exit_code == 0
        assert result.output == json_data_status_output_expected

    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value=({ 0 :"active",
                                                                                              1  :"standby",
                                                                                              2 : "True"})))
    def test_muxcable_status_json_alias(self):
        runner = CliRunner()
        db = Db()

        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["muxcable"].commands["status"], ["--json"], obj=db)
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"

        assert result.exit_code == 0
        assert result.output == json_data_status_output_expected_alias

    def test_muxcable_status_config(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["config"], obj=db)

        assert result.exit_code == 0
        assert result.output == tabular_data_config_output_expected

    def test_muxcable_status_config_alias(self):
        runner = CliRunner()
        db = Db()

        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["muxcable"].commands["config"], obj=db)
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"

        assert result.exit_code == 0
        assert result.output == tabular_data_config_output_expected_alias

    def test_muxcable_status_config_json(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["config"], ["--json"], obj=db)

        assert result.exit_code == 0
        assert result.output == json_data_status_config_output_expected

    def test_muxcable_status_config_json_alias(self):
        runner = CliRunner()
        db = Db()

        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["muxcable"].commands["config"], ["--json"], obj=db)
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"

        assert result.exit_code == 0
        assert result.output == json_data_status_config_output_expected_alias


    def test_muxcable_config_json_with_incorrect_port(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["config"], ["Ethernet33", "--json"], obj=db)

        assert result.exit_code == 1

    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value=({ 0 :"active",
                                                                                              1  :"standby",
                                                                                              2 : "True"})))
    def test_muxcable_status_json_with_correct_port(self):
        runner = CliRunner()
        db = Db()
        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(show.cli.commands["muxcable"].commands["status"], ["Ethernet0", "--json"], obj=db)

        assert result.exit_code == 0

    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value=({ 0 :"active",
                                                                                              1  :"standby",
                                                                                              2 : "True"})))
    def test_muxcable_status_json_with_correct_port_alias(self):
        runner = CliRunner()
        db = Db()
        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(show.cli.commands["muxcable"].commands["status"], ["Ethernet0", "--json"], obj=db)
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"

        assert result.exit_code == 0


    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value=({ 0 :"active",
                                                                                              1  :"standby",
                                                                                              2 : "True"})))
    def test_muxcable_status_json_port_incorrect_index(self):
        runner = CliRunner()
        db = Db()
        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 1
            result = runner.invoke(show.cli.commands["muxcable"].commands["status"], ["Ethernet0", "--json"], obj=db)

        assert result.exit_code == 1

    def test_muxcable_status_with_patch(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"], obj=db)

    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value=({ 0 :"active",
                                                                                              1  :"standby",
                                                                                              2 : "True"})))
    def test_muxcable_status_json_with_incorrect_port(self):
        runner = CliRunner()
        db = Db()
        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(show.cli.commands["muxcable"].commands["status"], ["Ethernet33", "--json"], obj=db)

        assert result.exit_code == 1

    def test_muxcable_config_with_correct_port(self):
        runner = CliRunner()
        db = Db()
        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(show.cli.commands["muxcable"].commands["config"], ["Ethernet0"], obj=db)

        assert result.exit_code == 0

    def test_muxcable_config_json_with_correct_port(self):
        runner = CliRunner()
        db = Db()
        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(show.cli.commands["muxcable"].commands["config"], ["Ethernet0", "--json"], obj=db)

        assert result.exit_code == 0

    def test_muxcable_config_json_port_with_incorrect_index(self):
        runner = CliRunner()
        db = Db()
        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 1
            result = runner.invoke(show.cli.commands["muxcable"].commands["config"], ["Ethernet0", "--json"], obj=db)

        assert result.exit_code == 0

    def test_muxcable_config_json_with_incorrect_port_patch(self):
        runner = CliRunner()
        db = Db()
        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(show.cli.commands["muxcable"].commands["config"], ["Ethernet33", "--json"], obj=db)

        assert result.exit_code == 1

    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value=({ 0 :"active",
                                                                                              1  :"standby",
                                                                                              2 : "True"})))
    def test_muxcable_status_json_port_eth0(self):
        runner = CliRunner()
        db = Db()
        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(show.cli.commands["muxcable"].commands["status"], ["Ethernet0"], obj=db)

        assert result.exit_code == 0

    def test_config_muxcable_tabular_port_Ethernet8_active(self):
        runner = CliRunner()
        db = Db()

        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(config.config.commands["muxcable"].commands["mode"], ["active", "Ethernet8"], obj=db)

        assert result.exit_code == 0

    def test_config_muxcable_tabular_port_Ethernet8_auto(self):
        runner = CliRunner()
        db = Db()

        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(config.config.commands["muxcable"].commands["mode"], ["auto", "Ethernet8"], obj=db)

        assert result.exit_code == 0

    def test_config_muxcable_tabular_port_Ethernet8_manual(self):
        runner = CliRunner()
        db = Db()

        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(config.config.commands["muxcable"].commands["mode"], ["manual", "Ethernet8"], obj=db)

        assert result.exit_code == 0

    def test_config_muxcable_tabular_port_Ethernet16_standby(self):
        runner = CliRunner()
        db = Db()

        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(config.config.commands["muxcable"].commands["mode"], ["standby", "Ethernet16"], obj=db)

        assert result.exit_code == 0

    def test_config_muxcable_mode_auto_json(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["mode"], ["auto", "all", "--json"], obj=db)

        assert result.exit_code == 0
        assert result.output == json_data_config_output_auto_expected

    def test_config_muxcable_mode_auto_json_alias(self):
        runner = CliRunner()
        db = Db()

        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(config.config.commands["muxcable"].commands["mode"], ["auto", "all", "--json"], obj=db)
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"

        assert result.exit_code == 0
        assert result.output == json_data_config_output_auto_expected_alias

    def test_config_muxcable_mode_active_json(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["mode"], ["active", "all", "--json"], obj=db)

        assert result.exit_code == 0
        assert result.output == json_data_config_output_active_expected

    def test_config_muxcable_mode_active_json_alias(self):
        runner = CliRunner()
        db = Db()

        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(config.config.commands["muxcable"].commands["mode"], ["active", "all", "--json"], obj=db)
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"

        assert result.exit_code == 0
        assert result.output == json_data_config_output_active_expected_alias

    def test_config_muxcable_json_port_auto_Ethernet0(self):
        runner = CliRunner()
        db = Db()

        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(config.config.commands["muxcable"].commands["mode"], [
                                   "auto", "Ethernet0", "--json"], obj=db)

        assert result.exit_code == 0

    def test_config_muxcable_json_port_active_Ethernet0(self):
        runner = CliRunner()
        db = Db()

        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(config.config.commands["muxcable"].commands["mode"], [
                                   "active", "Ethernet0", "--json"], obj=db)

        assert result.exit_code == 0

    def test_config_muxcable_mode_auto_tabular(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(config.config.commands["muxcable"].commands["mode"], ["auto", "all"], obj=db)
        assert result.exit_code == 0

    def test_config_muxcable_mode_active_tabular(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["mode"], ["active", "all"], obj=db)
        f = open("newfile", "w")
        f.write(result.output)

        assert result.exit_code == 0

    def test_config_muxcable_tabular_port(self):
        runner = CliRunner()
        db = Db()

        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(config.config.commands["muxcable"].commands["mode"], ["active", "Ethernet0"], obj=db)

        assert result.exit_code == 0

    def test_config_muxcable_tabular_port_Ethernet4_active(self):
        runner = CliRunner()
        db = Db()

        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(config.config.commands["muxcable"].commands["mode"], ["active", "Ethernet4"], obj=db)

        assert result.exit_code == 0

    def test_config_muxcable_tabular_port_Ethernet4_auto(self):
        runner = CliRunner()
        db = Db()

        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(config.config.commands["muxcable"].commands["mode"], ["auto", "Ethernet4"], obj=db)

        assert result.exit_code == 0

    def test_config_muxcable_tabular_port_with_incorrect_index(self):
        runner = CliRunner()
        db = Db()

        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 2
            result = runner.invoke(config.config.commands["muxcable"].commands["mode"], ["active", "Ethernet0"], obj=db)

        assert result.exit_code == 1

    def test_config_muxcable_tabular_port_with_incorrect_port_index(self):
        runner = CliRunner()
        db = Db()

        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 7
            result = runner.invoke(config.config.commands["muxcable"].commands["mode"], [
                                   "active", "Ethernet33"], obj=db)

        assert result.exit_code == 1

    def test_config_muxcable_tabular_port_with_incorrect_port(self):
        runner = CliRunner()
        db = Db()

        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(config.config.commands["muxcable"].commands["mode"], [
                                   "active", "Ethernet33"], obj=db)

        assert result.exit_code == 1

    def test_config_muxcable_packetloss_reset_Ethernet0(self):
        runner = CliRunner()
        db = Db()

        with mock.patch('sonic_platform_base.sonic_sfp.sfputilhelper') as patched_util:
            patched_util.SfpUtilHelper.return_value.get_asic_id_for_logical_port.return_value = 0
            result = runner.invoke(config.config.commands["muxcable"].commands["packetloss"], ["reset", "Ethernet0"], obj=db)

        assert result.exit_code == 0

    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "active"}))
    @mock.patch('show.muxcable.get_result', mock.MagicMock(return_value={0: 0,
                                                                          1: "active"}))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    @mock.patch('os.geteuid', mock.MagicMock(return_value=0))
    @mock.patch('sonic_y_cable.y_cable.get_eye_info', mock.MagicMock(return_value=[0, 0]))
    def test_show_muxcable_eye_info(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["eyeinfo"],
                               ["Ethernet0", "NIC"], obj=db)

        assert result.exit_code == 0

    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "True"}))
    @mock.patch('show.muxcable.get_result', mock.MagicMock(return_value={0: 0,
                                                                          1: "active"}))
    def test_show_mux_debugdeumpregisters(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["debugdumpregisters"],
                               ["Ethernet0"], obj=db)

        assert result.exit_code == 0

    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "True"}))
    @mock.patch('show.muxcable.get_result', mock.MagicMock(return_value={0: 0,
                                                                          1: "active"}))
    def test_show_mux_pcsstatistics(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["pcsstatistics"],
                               ["Ethernet0", "NIC"], obj=db)

        assert result.exit_code == 0

    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "True"}))
    @mock.patch('show.muxcable.get_result', mock.MagicMock(return_value={0: 0,
                                                                          1: "active"}))
    def test_show_mux_fecstatistics(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["fecstatistics"],
                               ["Ethernet0", "NIC"], obj=db)

        assert result.exit_code == 0


    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "True"}))
    @mock.patch('show.muxcable.get_event_logs', mock.MagicMock(return_value={0: 0,
                                                                          2: "log"}))
    def test_show_mux_event_log(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["event-log"],
                               ["Ethernet0"], obj=db)

        assert result.exit_code == 0


    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "True"}))
    @mock.patch('show.muxcable.get_result', mock.MagicMock(return_value={0: 0,
                                                                          1: "active"}))
    def test_show_mux_get_fec_anlt_speed(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["get-fec-anlt-speed"],
                               ["Ethernet0"], obj=db)

        assert result.exit_code == 0

    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "active"}))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    def test_show_muxcable_ber_info(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["berinfo"],
                               ["Ethernet0", "NIC"], obj=db)

        assert result.exit_code == 0

    @mock.patch('config.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "active"}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    def test_config_muxcable_enable_prbs(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["prbs"].commands["enable"],
                               ["Ethernet0", "NIC", "0", "0"], obj=db)

        assert result.exit_code == 0

    @mock.patch('config.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "active"}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    def test_config_muxcable_enable_loopback(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["loopback"].commands["enable"],
                               ["Ethernet0", "NIC", "0"], obj=db)

        assert result.exit_code == 0

    @mock.patch('config.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "active"}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    def test_config_muxcable_disble_prbs(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["prbs"].commands["disable"],
                               ["Ethernet0", "NIC"], obj=db)

        assert result.exit_code == 0

    @mock.patch('config.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "active"}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    def test_config_muxcable_disable_loopback(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["loopback"].commands["disable"],
                               ["Ethernet0", "NIC"], obj=db)

        assert result.exit_code == 0

    @mock.patch('sonic_y_cable.y_cable.get_part_number', mock.MagicMock(return_value=("CACL1X321P2PA1M")))
    @mock.patch('sonic_y_cable.y_cable.get_vendor', mock.MagicMock(return_value=("Credo          ")))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value=1))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    def test_show_muxcable_cableinfo(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["cableinfo"],
                               ["Ethernet0"], obj=db)

        assert result.exit_code == 0
        assert result.output == expected_muxcable_cableinfo_output

    @mock.patch('sonic_y_cable.y_cable.get_part_number', mock.MagicMock(return_value=(False)))
    @mock.patch('sonic_y_cable.y_cable.get_vendor', mock.MagicMock(return_value=(False)))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value=1))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    def test_show_muxcable_cableinfo_incorrect_port(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["cableinfo"],
                               ["Ethernet0"], obj=db)
        assert result.exit_code == 1

    @mock.patch('sonic_y_cable.y_cable.get_part_number', mock.MagicMock(return_value=(False)))
    @mock.patch('sonic_y_cable.y_cable.get_vendor', mock.MagicMock(return_value=(False)))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value=1))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=0))
    def test_show_muxcable_cableinfo_incorrect_port_return_value(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["cableinfo"],
                               ["Ethernet0"], obj=db)
        assert result.exit_code == 1

    @mock.patch('sonic_y_cable.y_cable.get_part_number', mock.MagicMock(return_value=(False)))
    @mock.patch('sonic_y_cable.y_cable.get_vendor', mock.MagicMock(return_value=(False)))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value=1))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0, 1]))
    def test_show_muxcable_cableinfo_incorrect_logical_port_return_value(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["cableinfo"],
                               ["Ethernet0"], obj=db)
        assert result.exit_code == 1

    @mock.patch('sonic_y_cable.y_cable.get_part_number', mock.MagicMock(return_value=(False)))
    @mock.patch('sonic_y_cable.y_cable.get_vendor', mock.MagicMock(return_value=(False)))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value=1))
    def test_show_muxcable_cableinfo_invalid_port(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["cableinfo"],
                               ["Ethernet0"], obj=db)
        assert result.exit_code == 1

        result = runner.invoke(show.cli.commands["muxcable"].commands["cableinfo"],
                               ["abc"], obj=db)
        assert result.exit_code == 1
        assert result.output == expected_muxcable_cableinfo_invalid_port_output

    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "active"}))
    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value={0: 0,
                                                                                            1: "active",
                                                                                            2: "True"}))
    @mock.patch('show.muxcable.check_port_in_mux_cable_table', mock.MagicMock(return_value=True))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(1)))
    @mock.patch('re.match', mock.MagicMock(return_value=(True)))
    def test_show_muxcable_hwmode_muxdirection_port_active(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["hwmode"].commands["muxdirection"],
                               ["Ethernet12"], obj=db)
        assert result.exit_code == 0
        assert result.output == show_muxcable_hwmode_muxdirection_active_expected_output

    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "active"}))
    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value={0: 0,
                                                                                            1: "active",
                                                                                            2: "True"}))
    @mock.patch('show.muxcable.check_port_in_mux_cable_table', mock.MagicMock(return_value=True))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(1)))
    @mock.patch('re.match', mock.MagicMock(return_value=(True)))
    def test_show_muxcable_hwmode_muxdirection_active_expected_output_alias(self):
        runner = CliRunner()
        db = Db()
        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["muxcable"].commands["hwmode"].commands["muxdirection"],
                               ["etp4"], obj=db)
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        assert result.exit_code == 0
        assert result.output == show_muxcable_hwmode_muxdirection_active_expected_output_alias


    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "standby"}))
    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value={0: 0,
                                                                                            1: "standby",
                                                                                            2: "True"}))
    @mock.patch('show.muxcable.check_port_in_mux_cable_table', mock.MagicMock(return_value=True))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(1)))
    @mock.patch('re.match', mock.MagicMock(return_value=(True)))
    def test_show_muxcable_hwmode_muxdirection_active(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["hwmode"].commands["muxdirection"], obj=db)
        assert result.exit_code == 0

    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "standby"}))
    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value={0: 0,
                                                                                            1: "standby",
                                                                                            2: "True"}))
    @mock.patch('show.muxcable.check_port_in_mux_cable_table', mock.MagicMock(return_value=True))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(2)))
    @mock.patch('re.match', mock.MagicMock(return_value=(True)))
    def test_show_muxcable_hwmode_muxdirection_port_standby(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["hwmode"].commands["muxdirection"],
                               ["Ethernet12"], obj=db)
        assert result.exit_code == 0
        assert result.output == show_muxcable_hwmode_muxdirection_standby_expected_output

    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "standby"}))
    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value={0: 0,
                                                                                            1: "standby",
                                                                                            2: "True"}))
    @mock.patch('show.muxcable.check_port_in_mux_cable_table', mock.MagicMock(return_value=True))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(2)))
    @mock.patch('re.match', mock.MagicMock(return_value=(True)))
    def test_show_muxcable_hwmode_muxdirection_port_standby_alias(self):
        runner = CliRunner()
        db = Db()

        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["muxcable"].commands["hwmode"].commands["muxdirection"],
                               ["etp4"], obj=db)
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        assert result.exit_code == 0
        assert result.output == show_muxcable_hwmode_muxdirection_standby_expected_output_alias

    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "sucess"}))
    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value={0: 0,
                                                                                            1: "sucess",
                                                                                            2: "True"}))
    @mock.patch('show.muxcable.check_port_in_mux_cable_table', mock.MagicMock(return_value=True))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(2)))
    @mock.patch('re.match', mock.MagicMock(return_value=(True)))
    def test_show_muxcable_hwmode_muxdirection_standby(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["hwmode"].commands["muxdirection"], obj=db)
        assert result.exit_code == 0

    @mock.patch('config.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "sucess"}))
    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value={0: 0,
                                                                                            1: "sucess",
                                                                                            2: "True"}))
    @mock.patch('config.muxcable.swsscommon.DBConnector', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Select', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.SubscriberStateTable', mock.MagicMock(return_value=0))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.toggle_mux_to_torA', mock.MagicMock(return_value=(True)))
    @mock.patch('sonic_y_cable.y_cable.toggle_mux_to_torB', mock.MagicMock(return_value=(True)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    def test_config_muxcable_hwmode_state_port_active(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["hwmode"].commands["state"],
                               ["active", "Ethernet12"], obj=db)
        assert result.exit_code == 0

    @mock.patch('config.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "sucess"}))
    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value={0: 0,
                                                                                            1: "sucess",
                                                                                            2: "True"}))
    @mock.patch('config.muxcable.swsscommon.DBConnector', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Select', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.SubscriberStateTable', mock.MagicMock(return_value=0))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.toggle_mux_to_torA', mock.MagicMock(return_value=(True)))
    @mock.patch('sonic_y_cable.y_cable.toggle_mux_to_torB', mock.MagicMock(return_value=(True)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    def test_config_muxcable_hwmode_state_active(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["hwmode"].commands["state"],
                               ["active", "all"], obj=db)
        assert result.exit_code == 0

    @mock.patch('config.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "standby"}))
    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value={0: 0,
                                                                                            1: "standby",
                                                                                            2: "True"}))
    @mock.patch('config.muxcable.swsscommon.DBConnector', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Select', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.SubscriberStateTable', mock.MagicMock(return_value=0))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.toggle_mux_to_torA', mock.MagicMock(return_value=(True)))
    @mock.patch('sonic_y_cable.y_cable.toggle_mux_to_torB', mock.MagicMock(return_value=(True)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    def test_config_muxcable_hwmode_state_port_standby(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["hwmode"].commands["state"],
                               ["standby", "Ethernet12"], obj=db)
        assert result.exit_code == 0

    @mock.patch('config.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "standby"}))
    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value={0: 0,
                                                                                            1: "standby",
                                                                                            2: "True"}))
    @mock.patch('config.muxcable.swsscommon.DBConnector', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Select', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.SubscriberStateTable', mock.MagicMock(return_value=0))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.toggle_mux_to_torA', mock.MagicMock(return_value=(True)))
    @mock.patch('sonic_y_cable.y_cable.toggle_mux_to_torB', mock.MagicMock(return_value=(True)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    def test_config_muxcable_hwmode_state_standby(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["hwmode"].commands["state"],
                               ["standby", "all"], obj=db)
        assert result.exit_code == 0

    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "True"}))
    @mock.patch('show.muxcable.get_response_for_version', mock.MagicMock(return_value={"version_self_active": "0.6MS",
                                                                                           "version_self_inactive": "0.6MS",
                                                                                           "version_self_next": "0.6MS",
                                                                                           "version_peer_active": "0.6MS",
                                                                                           "version_peer_inactive": "0.6MS",
                                                                                           "version_peer_next": "0.6MS",
                                                                                           "version_nic_active": "0.6MS",
                                                                                           "version_nic_inactive": "0.6MS",
                                                                                           "version_nic_next": "0.6MS"}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    @mock.patch('sonic_y_cable.y_cable.get_firmware_version', mock.MagicMock(return_value={"version_active": "0.6MS",
                                                                                           "version_inactive": "0.6MS",
                                                                                           "version_next": "0.6MS"}))
    def test_show_muxcable_firmware_version(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["firmware"].commands["version"], [
                               "Ethernet0"], obj=db)
        assert result.exit_code == 0
        assert result.output == show_muxcable_firmware_version_expected_output


    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "True"}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    def test_show_muxcable_firmware_version_all(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["firmware"].commands["version"], [
                               "all"], obj=db)
        assert result.exit_code == 0
        f = open("newfile", "w")
        f.write(result.output)
        assert result.output == show_muxcable_firmware_version_all_expected_output


    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "True"}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    def test_show_muxcable_firmware_version_all_active(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["firmware"].commands["version"], [
                               "all", "--active"], obj=db)
        assert result.exit_code == 0
        f = open("newfile", "w")
        f.write(result.output)
        assert result.output == show_muxcable_firmware_version_all_active_expected_output

    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "True"}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=1))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    def test_show_muxcable_firmware_version_all_bad_asic_index(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["firmware"].commands["version"], [
                               "all"], obj=db)
        assert result.exit_code == 1 


    @mock.patch('config.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "sucess"}))
    @mock.patch('config.muxcable.swsscommon.DBConnector', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Select', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.SubscriberStateTable', mock.MagicMock(return_value=0))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    @mock.patch('sonic_y_cable.y_cable.download_fimware', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.FIRMWARE_DOWNLOAD_SUCCESS', mock.MagicMock(return_value=(1)))
    def test_config_muxcable_download_firmware(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["firmware"].commands["download"], [
                               "fwfile", "Ethernet0"], obj=db)
        assert result.exit_code == 0

    @mock.patch('config.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "sucess"}))
    @mock.patch('config.muxcable.swsscommon.DBConnector', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Select', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.SubscriberStateTable', mock.MagicMock(return_value=0))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    @mock.patch('sonic_y_cable.y_cable.activate_firmware', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.FIRMWARE_ACTIVATE_SUCCESS', mock.MagicMock(return_value=(1)))
    def test_config_muxcable_activate_firmware(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["firmware"].commands["activate"], [
                               "Ethernet0"], obj=db)
        assert result.exit_code == 0

    @mock.patch('config.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "sucess"}))
    @mock.patch("config.muxcable.swsscommon.DBConnector", mock.MagicMock(return_value=0))
    @mock.patch("config.muxcable.swsscommon.Table", mock.MagicMock(return_value=0))
    @mock.patch("config.muxcable.swsscommon.Select", mock.MagicMock(return_value=0))
    @mock.patch("config.muxcable.swsscommon.SubscriberStateTable", mock.MagicMock(return_value=0))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    @mock.patch('sonic_y_cable.y_cable.rollback_firmware', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.FIRMWARE_ROLLBACK_SUCCESS', mock.MagicMock(return_value=(1)))
    def test_config_muxcable_rollback_firmware(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["firmware"].commands["rollback"], [
                               "Ethernet0"], obj=db)
        assert result.exit_code == 0

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    def test_show_muxcable_metrics_port(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["metrics"],
                               ["Ethernet0"], obj=db)
        assert result.exit_code == 0
        assert result.output == show_muxcable_metrics_expected_output

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    def test_show_muxcable_metrics_port_alias(self):
        runner = CliRunner()
        db = Db()

        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["muxcable"].commands["metrics"],
                               ["etp1"], obj=db)

        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        assert result.exit_code == 0
        assert result.output == show_muxcable_metrics_expected_output_alias

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    def test_show_muxcable_metrics_port_json(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["metrics"],
                               ["Ethernet0", "--json"], obj=db)
        assert result.exit_code == 0
        assert result.output == show_muxcable_metrics_expected_output_json

    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "True"}))
    @mock.patch('show.muxcable.get_response_for_version', mock.MagicMock(return_value={"version_self_active": "0.6MS",
                                                                                           "version_self_inactive": "0.6MS",
                                                                                           "version_self_next": "0.6MS",
                                                                                           "version_peer_active": "0.6MS",
                                                                                           "version_peer_inactive": "0.6MS",
                                                                                           "version_peer_next": "0.6MS",
                                                                                           "version_nic_active": "0.6MS",
                                                                                           "version_nic_inactive": "0.6MS",
                                                                                           "version_nic_next": "0.6MS"}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    @mock.patch('sonic_y_cable.y_cable.get_firmware_version', mock.MagicMock(return_value={"version_active": "0.6MS",
                                                                                           "version_inactive": "0.6MS",
                                                                                           "version_next": "0.6MS"}))
    def test_show_muxcable_firmware_active_version(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["firmware"].commands["version"], [
                               "Ethernet0", "--active"], obj=db)
        assert result.exit_code == 0
        assert result.output == show_muxcable_firmware_version_active_expected_output

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")
    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "active"}))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    def test_show_muxcable_ber_info(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["berinfo"],
                               ["Ethernet0", "NIC"], obj=db)

        assert result.exit_code == 0

    @mock.patch('config.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "active"}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    def test_config_muxcable_enable_prbs(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["prbs"].commands["enable"],
                               ["Ethernet0", "NIC", "0", "0"], obj=db)

        assert result.exit_code == 0

    @mock.patch('config.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "active"}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    def test_config_muxcable_enable_loopback(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["loopback"].commands["enable"],
                               ["Ethernet0", "NIC", "0"], obj=db)

        assert result.exit_code == 0

    @mock.patch('config.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "active"}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    def test_config_muxcable_disble_prbs(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["prbs"].commands["disable"],
                               ["Ethernet0", "NIC"], obj=db)

        assert result.exit_code == 0

    @mock.patch('config.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "active"}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    def test_config_muxcable_disable_loopback(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["loopback"].commands["disable"],
                               ["Ethernet0", "NIC"], obj=db)

        assert result.exit_code == 0

    @mock.patch('sonic_y_cable.y_cable.get_part_number', mock.MagicMock(return_value=("CACL1X321P2PA1M")))
    @mock.patch('sonic_y_cable.y_cable.get_vendor', mock.MagicMock(return_value=("Credo          ")))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value=1))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    def test_show_muxcable_cableinfo(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["cableinfo"],
                               ["Ethernet0"], obj=db)

        assert result.exit_code == 0
        assert result.output == expected_muxcable_cableinfo_output

    @mock.patch('sonic_y_cable.y_cable.get_part_number', mock.MagicMock(return_value=(False)))
    @mock.patch('sonic_y_cable.y_cable.get_vendor', mock.MagicMock(return_value=(False)))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value=1))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    def test_show_muxcable_cableinfo_incorrect_port(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["cableinfo"],
                               ["Ethernet0"], obj=db)
        assert result.exit_code == 1

    @mock.patch('sonic_y_cable.y_cable.get_part_number', mock.MagicMock(return_value=(False)))
    @mock.patch('sonic_y_cable.y_cable.get_vendor', mock.MagicMock(return_value=(False)))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value=1))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=0))
    def test_show_muxcable_cableinfo_incorrect_port_return_value(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["cableinfo"],
                               ["Ethernet0"], obj=db)
        assert result.exit_code == 1

    @mock.patch('sonic_y_cable.y_cable.get_part_number', mock.MagicMock(return_value=(False)))
    @mock.patch('sonic_y_cable.y_cable.get_vendor', mock.MagicMock(return_value=(False)))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value=1))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0, 1]))
    def test_show_muxcable_cableinfo_incorrect_logical_port_return_value(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["cableinfo"],
                               ["Ethernet0"], obj=db)
        assert result.exit_code == 1


    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "active"}))
    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value={0: 0,
                                                                                            1: "active",
                                                                                            2: "True"}))
    @mock.patch('show.muxcable.check_port_in_mux_cable_table', mock.MagicMock(return_value=True))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(1)))
    @mock.patch('re.match', mock.MagicMock(return_value=(True)))
    def test_show_muxcable_hwmode_muxdirection_port_active(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["hwmode"].commands["muxdirection"],
                               ["Ethernet12"], obj=db)
        assert result.exit_code == 0
        assert result.output == show_muxcable_hwmode_muxdirection_active_expected_output

    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "active"}))
    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value={0: 0,
                                                                                            1: "active",
                                                                                            2: "True"}))
    @mock.patch('show.muxcable.check_port_in_mux_cable_table', mock.MagicMock(return_value=True))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(1)))
    @mock.patch('re.match', mock.MagicMock(return_value=(True)))
    def test_show_muxcable_hwmode_muxdirection_active_expected_output_alias(self):
        runner = CliRunner()
        db = Db()
        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["muxcable"].commands["hwmode"].commands["muxdirection"],
                               ["etp4"], obj=db)
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        assert result.exit_code == 0
        assert result.output == show_muxcable_hwmode_muxdirection_active_expected_output_alias


    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "standby"}))
    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value={0: 0,
                                                                                            1: "standby",
                                                                                            2: "True"}))
    @mock.patch('show.muxcable.check_port_in_mux_cable_table', mock.MagicMock(return_value=True))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(1)))
    @mock.patch('re.match', mock.MagicMock(return_value=(True)))
    def test_show_muxcable_hwmode_muxdirection_active(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["hwmode"].commands["muxdirection"], obj=db)
        assert result.exit_code == 0

    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "standby"}))
    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value={0: 0,
                                                                                            1: "standby",
                                                                                            2: "True"}))
    @mock.patch('show.muxcable.check_port_in_mux_cable_table', mock.MagicMock(return_value=True))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(2)))
    @mock.patch('re.match', mock.MagicMock(return_value=(True)))
    def test_show_muxcable_hwmode_muxdirection_port_standby(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["hwmode"].commands["muxdirection"],
                               ["Ethernet12"], obj=db)
        assert result.exit_code == 0
        assert result.output == show_muxcable_hwmode_muxdirection_standby_expected_output

    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "standby"}))
    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value={0: 0,
                                                                                            1: "standby",
                                                                                            2: "True"}))
    @mock.patch('show.muxcable.check_port_in_mux_cable_table', mock.MagicMock(return_value=True))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(2)))
    @mock.patch('re.match', mock.MagicMock(return_value=(True)))
    def test_show_muxcable_hwmode_muxdirection_port_standby_alias(self):
        runner = CliRunner()
        db = Db()

        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["muxcable"].commands["hwmode"].commands["muxdirection"],
                               ["etp4"], obj=db)
        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        assert result.exit_code == 0
        assert result.output == show_muxcable_hwmode_muxdirection_standby_expected_output_alias

    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "sucess"}))
    @mock.patch('show.muxcable.get_hwmode_mux_direction_port', mock.MagicMock(return_value={0: 0,
                                                                                            1: "sucess",
                                                                                            2: "True"}))
    @mock.patch('show.muxcable.check_port_in_mux_cable_table', mock.MagicMock(return_value=True))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(2)))
    @mock.patch('re.match', mock.MagicMock(return_value=(True)))
    def test_show_muxcable_hwmode_muxdirection_standby(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["hwmode"].commands["muxdirection"], obj=db)
        assert result.exit_code == 0

    @mock.patch('config.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "sucess"}))
    @mock.patch('config.muxcable.swsscommon.DBConnector', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Select', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.SubscriberStateTable', mock.MagicMock(return_value=0))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.toggle_mux_to_torA', mock.MagicMock(return_value=(True)))
    @mock.patch('sonic_y_cable.y_cable.toggle_mux_to_torB', mock.MagicMock(return_value=(True)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    def test_config_muxcable_hwmode_state_port_active(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["hwmode"].commands["state"],
                               ["active", "Ethernet12"], obj=db)
        assert result.exit_code == 0

    @mock.patch('config.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "sucess"}))
    @mock.patch('config.muxcable.swsscommon.DBConnector', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Select', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.SubscriberStateTable', mock.MagicMock(return_value=0))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.toggle_mux_to_torA', mock.MagicMock(return_value=(True)))
    @mock.patch('sonic_y_cable.y_cable.toggle_mux_to_torB', mock.MagicMock(return_value=(True)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    def test_config_muxcable_hwmode_state_active(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["hwmode"].commands["state"],
                               ["active", "all"], obj=db)
        assert result.exit_code == 0

    @mock.patch('config.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "standby"}))
    @mock.patch('config.muxcable.swsscommon.DBConnector', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Select', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.SubscriberStateTable', mock.MagicMock(return_value=0))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.toggle_mux_to_torA', mock.MagicMock(return_value=(True)))
    @mock.patch('sonic_y_cable.y_cable.toggle_mux_to_torB', mock.MagicMock(return_value=(True)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    def test_config_muxcable_hwmode_state_port_standby(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["hwmode"].commands["state"],
                               ["standby", "Ethernet12"], obj=db)
        assert result.exit_code == 0

    @mock.patch('config.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "standby"}))
    @mock.patch('config.muxcable.swsscommon.DBConnector', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Select', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.SubscriberStateTable', mock.MagicMock(return_value=0))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.check_mux_direction', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.toggle_mux_to_torA', mock.MagicMock(return_value=(True)))
    @mock.patch('sonic_y_cable.y_cable.toggle_mux_to_torB', mock.MagicMock(return_value=(True)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    def test_config_muxcable_hwmode_state_standby(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["hwmode"].commands["state"],
                               ["standby", "all"], obj=db)
        assert result.exit_code == 0

    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "True"}))
    @mock.patch('show.muxcable.get_response_for_version', mock.MagicMock(return_value={"version_self_active": "0.6MS",
                                                                                           "version_self_inactive": "0.6MS",
                                                                                           "version_self_next": "0.6MS",
                                                                                           "version_peer_active": "0.6MS",
                                                                                           "version_peer_inactive": "0.6MS",
                                                                                           "version_peer_next": "0.6MS",
                                                                                           "version_nic_active": "0.6MS",
                                                                                           "version_nic_inactive": "0.6MS",
                                                                                           "version_nic_next": "0.6MS"}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    @mock.patch('sonic_y_cable.y_cable.get_firmware_version', mock.MagicMock(return_value={"version_active": "0.6MS",
                                                                                           "version_inactive": "0.6MS",
                                                                                           "version_next": "0.6MS"}))
    def test_show_muxcable_firmware_version(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["firmware"].commands["version"], [
                               "Ethernet0"], obj=db)
        assert result.exit_code == 0
        assert result.output == show_muxcable_firmware_version_expected_output

    @mock.patch('config.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "sucess"}))
    @mock.patch('config.muxcable.swsscommon.DBConnector', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Select', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.SubscriberStateTable', mock.MagicMock(return_value=0))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    @mock.patch('sonic_y_cable.y_cable.download_fimware', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.FIRMWARE_DOWNLOAD_SUCCESS', mock.MagicMock(return_value=(1)))
    def test_config_muxcable_download_firmware(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["firmware"].commands["download"], [
                               "fwfile", "Ethernet0"], obj=db)
        assert result.exit_code == 0

    @mock.patch('config.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "sucess"}))
    @mock.patch('config.muxcable.swsscommon.DBConnector', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Select', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.SubscriberStateTable', mock.MagicMock(return_value=0))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    @mock.patch('sonic_y_cable.y_cable.activate_firmware', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.FIRMWARE_ACTIVATE_SUCCESS', mock.MagicMock(return_value=(1)))
    def test_config_muxcable_activate_firmware(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["firmware"].commands["activate"], [
                               "Ethernet0"], obj=db)
        assert result.exit_code == 0

    @mock.patch('config.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "sucess"}))
    @mock.patch("config.muxcable.swsscommon.DBConnector", mock.MagicMock(return_value=0))
    @mock.patch("config.muxcable.swsscommon.Table", mock.MagicMock(return_value=0))
    @mock.patch("config.muxcable.swsscommon.Select", mock.MagicMock(return_value=0))
    @mock.patch("config.muxcable.swsscommon.SubscriberStateTable", mock.MagicMock(return_value=0))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    @mock.patch('sonic_y_cable.y_cable.rollback_firmware', mock.MagicMock(return_value=(1)))
    @mock.patch('sonic_y_cable.y_cable.FIRMWARE_ROLLBACK_SUCCESS', mock.MagicMock(return_value=(1)))
    def test_config_muxcable_rollback_firmware(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["firmware"].commands["rollback"], [
                               "Ethernet0"], obj=db)
        assert result.exit_code == 0

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    def test_show_muxcable_metrics_port(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["metrics"],
                               ["Ethernet0"], obj=db)
        assert result.exit_code == 0
        assert result.output == show_muxcable_metrics_expected_output

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    def test_show_muxcable_metrics_port_alias(self):
        runner = CliRunner()
        db = Db()

        os.environ['SONIC_CLI_IFACE_MODE'] = "alias"
        result = runner.invoke(show.cli.commands["muxcable"].commands["metrics"],
                               ["etp1"], obj=db)

        os.environ['SONIC_CLI_IFACE_MODE'] = "default"
        assert result.exit_code == 0
        assert result.output == show_muxcable_metrics_expected_output_alias

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    def test_show_muxcable_metrics_port_json(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["metrics"],
                               ["Ethernet0", "--json"], obj=db)
        assert result.exit_code == 0
        assert result.output == show_muxcable_metrics_expected_output_json

    @mock.patch('show.muxcable.delete_all_keys_in_db_table', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.update_and_get_response_for_xcvr_cmd', mock.MagicMock(return_value={0: 0,
                                                                                                      1: "True"}))
    @mock.patch('show.muxcable.get_response_for_version', mock.MagicMock(return_value={"version_self_active": "0.6MS",
                                                                                           "version_self_inactive": "0.6MS",
                                                                                           "version_self_next": "0.6MS",
                                                                                           "version_peer_active": "0.6MS",
                                                                                           "version_peer_inactive": "0.6MS",
                                                                                           "version_peer_next": "0.6MS",
                                                                                           "version_nic_active": "0.6MS",
                                                                                           "version_nic_inactive": "0.6MS",
                                                                                           "version_nic_next": "0.6MS"}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.get_physical_to_logical', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    @mock.patch('sonic_y_cable.y_cable.check_read_side', mock.MagicMock(return_value=(1)))
    @mock.patch('click.confirm', mock.MagicMock(return_value=("y")))
    @mock.patch('sonic_y_cable.y_cable.get_firmware_version', mock.MagicMock(return_value={"version_active": "0.6MS",
                                                                                           "version_inactive": "0.6MS",
                                                                                           "version_next": "0.6MS"}))
    def test_show_muxcable_firmware_active_version(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["firmware"].commands["version"], [
                               "Ethernet0", "--active"], obj=db)
        assert result.exit_code == 0
        assert result.output == show_muxcable_firmware_version_active_expected_output

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    def test_show_muxcable_packetloss_port(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["packetloss"],
                               ["Ethernet0"], obj=db)
        assert result.exit_code == 0
        assert result.output == show_muxcable_packetloss_expected_output

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    def test_show_muxcable_packetloss_port_json(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["packetloss"],
                               ["Ethernet0", "--json"], obj=db)
        assert result.exit_code == 0
        assert result.output == show_muxcable_packetloss_expected_output_json

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    def test_show_muxcable_tunnel_route(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["tunnel-route"], obj=db)

        assert result.exit_code == 0
        assert result.output == show_muxcable_tunnel_route_expected_output
    
    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    def test_show_muxcable_tunnel_route_json(self):
        runner = CliRunner()
        db = Db()
        
        result = runner.invoke(show.cli.commands["muxcable"].commands["tunnel-route"],
                               ["--json"], obj=db)

        assert result.exit_code == 0
        assert result.output == show_muxcable_tunnel_route_expected_output_json

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    def test_show_muxcable_tunnel_route_port(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["tunnel-route"],
                               ["Ethernet0"], obj=db)

        assert result.exit_code == 0
        assert result.output == show_muxcable_tunnel_route_expected_port_output

    @mock.patch('utilities_common.platform_sfputil_helper.get_logical_list', mock.MagicMock(return_value=["Ethernet0", "Ethernet12"]))
    @mock.patch('utilities_common.platform_sfputil_helper.get_asic_id_for_logical_port', mock.MagicMock(return_value=0))
    @mock.patch('show.muxcable.platform_sfputil', mock.MagicMock(return_value={0: ["Ethernet12", "Ethernet0"]}))
    @mock.patch('utilities_common.platform_sfputil_helper.logical_port_name_to_physical_port_list', mock.MagicMock(return_value=[0]))
    def test_show_muxcable_tunnel_route_json_port(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["muxcable"].commands["tunnel-route"],
                               ["Ethernet0", "--json"], obj=db)
        assert result.exit_code == 0
        assert result.output == show_muxcable_tunnel_route_expected_output_port_json

    @mock.patch('config.muxcable.swsscommon.DBConnector', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Select', mock.MagicMock(return_value=0))
    def test_config_muxcable_telemetry_enable_without_patch(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["telemetry"], [
                               "enable"], obj=db)
        assert result.exit_code == 1

    @mock.patch('config.muxcable.swsscommon.DBConnector', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Select', mock.MagicMock(return_value=0))
    def test_config_muxcable_telemetry_disable_without_patch(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["telemetry"], [
                               "disable"], obj=db)
        assert result.exit_code == 1

    @mock.patch('config.muxcable.swsscommon.DBConnector', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Table', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.swsscommon.Select', mock.MagicMock(return_value=0))
    @mock.patch('config.muxcable.update_configdb_ycable_telemetry_data', mock.MagicMock(return_value=0))
    def test_config_muxcable_telemetry_enable(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(config.config.commands["muxcable"].commands["telemetry"], [
                               "enable"], obj=db)
        assert result.exit_code == 0

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")

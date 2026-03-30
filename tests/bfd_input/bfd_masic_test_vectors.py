expected_show_bfd_summary_output = """\
Total number of BFD sessions: 4
Peer Addr    Interface    Vrf      State    Type          Local Addr      TX Interval    RX Interval    Multiplier  Multihop    Local Discriminator
-----------  -----------  -------  -------  ------------  ------------  -------------  -------------  ------------  ----------  ---------------------
10.0.1.1     default      default  DOWN     async_active  10.0.0.1                300            500             3  true        NA
10.0.2.1     Ethernet12   default  UP       async_active  10.0.0.1                200            600             3  false       88
2000::10:1   default      default  UP       async_active  2000::1                 100            700             3  false       NA
10.0.1.1     default      VrfRed   UP       async_active  10.0.0.1                400            500             5  false       NA
"""  # noqa: E501

expected_show_bfd_summary_all_output = """\
Total number of BFD sessions: 6
Peer Addr    Interface    Vrf      State    Type          Local Addr      TX Interval    RX Interval    Multiplier  Multihop    Local Discriminator
-----------  -----------  -------  -------  ------------  ------------  -------------  -------------  ------------  ----------  ---------------------
10.0.1.1     default      default  DOWN     async_active  10.0.0.1                300            500             3  true        NA
10.0.2.1     Ethernet12   default  UP       async_active  10.0.0.1                200            600             3  false       88
2000::10:1   default      default  UP       async_active  2000::1                 100            700             3  false       NA
10.0.1.1     default      VrfRed   UP       async_active  10.0.0.1                400            500             5  false       NA
10.0.3.1     Ethernet36   default  DOWN     async_active  10.0.0.2                150            450             3  true        99
2000::20:1   default      VrfBlue  UP       async_active  2000::2                 250            750             4  false       NA
"""  # noqa: E501

expected_show_bfd_peer_output = """\
Total number of BFD sessions for peer IP 10.0.1.1: 2
Peer Addr    Interface    Vrf      State    Type          Local Addr      TX Interval    RX Interval    Multiplier  Multihop    Local Discriminator
-----------  -----------  -------  -------  ------------  ------------  -------------  -------------  ------------  ----------  ---------------------
10.0.1.1     default      default  DOWN     async_active  10.0.0.1                300            500             3  true        NA
10.0.1.1     default      VrfRed   UP       async_active  10.0.0.1                400            500             5  false       NA
"""  # noqa: E501

test_data = {
    "show_bfd_summary_masic_asic0": {
        "cmd": "summary",
        "args": ["-n", "asic0"],
        "expected_output": expected_show_bfd_summary_output,
    },
    "show_bfd_summary_masic_all": {
        "cmd": "summary",
        "args": [],
        "expected_output": expected_show_bfd_summary_all_output,
    },
    "show_bfd_peer_masic_asic0": {
        "cmd": "peer",
        "args": ["10.0.1.1", "-n", "asic0"],
        "expected_output": expected_show_bfd_peer_output,
    },
}

show_mac_masic_asic0_output = """\
  No.    Vlan  MacAddress         Port       Type
-----  ------  -----------------  ---------  -------
    1       2  11:22:33:44:55:66  Ethernet0  Dynamic
Total number of entries 1
"""

test_data = {
    "show_mac_masic_asic0": {
        "cmd": "mac",
        "args": "-n asic0",
        "expected_output": show_mac_masic_asic0_output,
    }
}

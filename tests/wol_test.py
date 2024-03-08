import click
import io
import pytest
import wol.main as wol
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

ETHER_TYPE_WOL = b'\x08\x42'
BROADCAST_MAC = wol.MacAddress('ff:ff:ff:ff:ff:ff')

SAMPLE_INTERFACE_ETH0 = "Ethernet0"
SAMPLE_INTERFACE_VLAN1000 = "Vlan1000"
SAMPLE_INTERFACE_PO100 = "PortChannel100"

SAMPLE_ETH0_MAC = wol.MacAddress('11:33:55:77:99:bb')
SAMPLE_VLAN1000_MAC = wol.MacAddress('22:44:66:88:aa:cc')
SAMPLE_PO100_MAC = wol.MacAddress('33:55:77:99:bb:dd')
SAMPLE_TARGET_MAC = wol.MacAddress('44:66:88:aa:cc:ee')
SAMPLE_TARGET_MAC_LIST = [wol.MacAddress('44:66:88:aa:cc:ee'), wol.MacAddress('55:77:99:bb:dd:ff')]

SAMPLE_MAGIC_PACKET_UNICAST = SAMPLE_TARGET_MAC.to_bytes() + SAMPLE_ETH0_MAC.to_bytes() + ETHER_TYPE_WOL + b'\xff' * 6 + SAMPLE_TARGET_MAC.to_bytes() * 16
SAMPLE_MAGIC_PACKET_BROADCAST = BROADCAST_MAC.to_bytes() + SAMPLE_ETH0_MAC.to_bytes() + ETHER_TYPE_WOL + b'\xff' * 6 + SAMPLE_TARGET_MAC.to_bytes() * 16


class TestMacAddress():
    def test_init(self):
        # Test Case 1: Test with a valid MAC address
        assert wol.MacAddress('00:11:22:33:44:55').address == b'\x00\x11\x22\x33\x44\x55'
        # Test Case 2: Test with an invalid MAC address
        with pytest.raises(ValueError) as exc_info:
            wol.MacAddress('INVALID_MAC_ADDRESS')
            assert exc_info.value.message == "invalid MAC address"
        with pytest.raises(ValueError) as exc_info:
            wol.MacAddress('00:11:22:33:44')
            assert exc_info.value.message == "invalid MAC address"

    def test_str(self):
        assert str(wol.MacAddress('00:01:0a:a0:aa:ee')) == '00:01:0a:a0:aa:ee'
        assert str(wol.MacAddress('ff:ff:ff:ff:ff:ff')) == 'ff:ff:ff:ff:ff:ff'

    def test_eq(self):
        # Test Case 1: Test with two equal MAC addresses
        assert wol.MacAddress('00:11:22:33:44:55') == wol.MacAddress('00:11:22:33:44:55')
        # Test Case 2: Test with two unequal MAC addresses
        assert wol.MacAddress('00:11:22:33:44:55') != wol.MacAddress('55:44:33:22:11:00')

    def test_to_bytes(self):
        assert wol.MacAddress('00:11:22:33:44:55').to_bytes() == b'\x00\x11\x22\x33\x44\x55'


@patch('wol.main.get_interface_mac', MagicMock(return_value=SAMPLE_ETH0_MAC))
def test_build_magic_packet():
    # Test Case 1: Test build magic packet basic
    expected_output = SAMPLE_TARGET_MAC.to_bytes() + SAMPLE_ETH0_MAC.to_bytes() + ETHER_TYPE_WOL \
        + b'\xff' * 6 + SAMPLE_TARGET_MAC.to_bytes() * 16
    assert wol.build_magic_packet(SAMPLE_INTERFACE_ETH0, SAMPLE_TARGET_MAC, broadcast=False, password=b'') == expected_output
    # Test Case 2: Test build magic packet with broadcast flag
    expected_output = BROADCAST_MAC.to_bytes() + SAMPLE_ETH0_MAC.to_bytes() + ETHER_TYPE_WOL \
        + b'\xff' * 6 + SAMPLE_TARGET_MAC.to_bytes() * 16
    assert wol.build_magic_packet(SAMPLE_INTERFACE_ETH0, SAMPLE_TARGET_MAC, broadcast=True, password=b'') == expected_output
    # Test Case 3: Test build magic packet with 4-byte password
    password = b'\x12\x34'
    expected_output = SAMPLE_TARGET_MAC.to_bytes() + SAMPLE_ETH0_MAC.to_bytes() + ETHER_TYPE_WOL \
        + b'\xff' * 6 + SAMPLE_TARGET_MAC.to_bytes() * 16 + password
    assert wol.build_magic_packet(SAMPLE_INTERFACE_ETH0, SAMPLE_TARGET_MAC, broadcast=False, password=password) == expected_output
    # Test Case 4: Test build magic packet with 6-byte password
    password = b'\x12\x34\x56\x78\x9a\xbc'
    expected_output = SAMPLE_TARGET_MAC.to_bytes() + SAMPLE_ETH0_MAC.to_bytes() + ETHER_TYPE_WOL \
        + b'\xff' * 6 + SAMPLE_TARGET_MAC.to_bytes() * 16 + password
    assert wol.build_magic_packet(SAMPLE_INTERFACE_ETH0, SAMPLE_TARGET_MAC, broadcast=False, password=password) == expected_output


def test_send_magic_packet():
    # Test Case 1: Test send magic packet with count is 1
    with patch('socket.socket') as mock_socket:
        wol.send_magic_packet(SAMPLE_INTERFACE_ETH0, SAMPLE_TARGET_MAC, SAMPLE_MAGIC_PACKET_UNICAST, count=1, interval=0, verbose=False)
        mock_socket.return_value.bind.assert_called_once_with((SAMPLE_INTERFACE_ETH0, 0))
        mock_socket.return_value.send.assert_called_once_with(SAMPLE_MAGIC_PACKET_UNICAST)
    # Test Case 2: Test send magic packet with count is 3
    with patch('socket.socket') as mock_socket:
        wol.send_magic_packet(SAMPLE_INTERFACE_ETH0, SAMPLE_TARGET_MAC, SAMPLE_MAGIC_PACKET_UNICAST, count=3, interval=0, verbose=False)
        assert mock_socket.return_value.bind.call_count == 1
        assert mock_socket.return_value.send.call_count == 3
    # Test Case 3: Test send magic packet with interval is 1000
    with patch('socket.socket') as mock_socket, \
         patch('time.sleep') as mock_sleep:
        wol.send_magic_packet(SAMPLE_INTERFACE_ETH0, SAMPLE_TARGET_MAC, SAMPLE_MAGIC_PACKET_UNICAST, count=3, interval=1000, verbose=False)
        assert mock_socket.return_value.bind.call_count == 1
        assert mock_socket.return_value.send.call_count == 3
        assert mock_sleep.call_count == 2  # sleep twice between 3 packets
        mock_sleep.assert_called_with(1)
    # Test Case 4: Test send magic packet with verbose is True
    expected_verbose_output = f"Sending 5 magic packet to {SAMPLE_TARGET_MAC} via interface {SAMPLE_INTERFACE_ETH0}\n" + \
                              f"1st magic packet sent to {SAMPLE_TARGET_MAC}\n" + \
                              f"2nd magic packet sent to {SAMPLE_TARGET_MAC}\n" + \
                              f"3rd magic packet sent to {SAMPLE_TARGET_MAC}\n" + \
                              f"4th magic packet sent to {SAMPLE_TARGET_MAC}\n" + \
                              f"5th magic packet sent to {SAMPLE_TARGET_MAC}\n"
    with patch('socket.socket') as mock_socket, patch('time.sleep'), patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        wol.send_magic_packet(SAMPLE_INTERFACE_ETH0, SAMPLE_TARGET_MAC, SAMPLE_MAGIC_PACKET_UNICAST, count=5, interval=1000, verbose=True)
        assert mock_socket.return_value.bind.call_count == 1
        assert mock_socket.return_value.send.call_count == 5
        assert mock_stdout.getvalue() == expected_verbose_output


@patch('netifaces.interfaces', MagicMock(return_value=[SAMPLE_INTERFACE_ETH0]))
@patch('wol.main.get_interface_operstate', MagicMock(return_value="up"))
def test_validate_interface():
    # Test Case 1: Test with a valid SONiC interface name
    assert wol.validate_interface(None, None, SAMPLE_INTERFACE_ETH0) == SAMPLE_INTERFACE_ETH0
    # Test Case 2: Test with an invalid SONiC interface name
    with pytest.raises(click.BadParameter) as exc_info:
        wol.validate_interface(None, None, "INVALID_SONIC_INTERFACE")
        assert exc_info.value.message == "invalid SONiC interface name INVALID_SONIC_INTERFACE"
    # Test Case 3: Test with an valid SONiC interface name, but the interface operstat is down
    with patch('wol.main.get_interface_operstate', MagicMock(return_value="down")):
        with pytest.raises(click.BadParameter) as exc_info:
            wol.validate_interface(None, None, SAMPLE_INTERFACE_ETH0)
            assert exc_info.value.message == f"interface {SAMPLE_INTERFACE_ETH0} is not up"


def test_parse_target_mac():
    # Test Case 1: Test with a single valid target MAC address
    wol.parse_target_mac(None, None, str(SAMPLE_TARGET_MAC)) == [SAMPLE_TARGET_MAC]
    # Test Case 2: Test with a list of valid target MAC addresses
    mac_list = [SAMPLE_ETH0_MAC, SAMPLE_VLAN1000_MAC, SAMPLE_PO100_MAC]
    assert wol.parse_target_mac(None, None, ",".join([str(x) for x in mac_list])) == mac_list
    # Test Case 3: Test with a single invalid target MAC address
    with pytest.raises(click.BadParameter) as exc_info:
        wol.parse_target_mac(None, None, "INVALID_MAC_ADDRESS")
        assert exc_info.value.message == "invalid MAC address INVALID_MAC_ADDRESS"
    # Test Case 4: Test with a list of target MAC addresses, one of them is invalid
    with pytest.raises(click.BadParameter) as exc_info:
        wol.parse_target_mac(None, None, ",".join([str(SAMPLE_ETH0_MAC), "INVALID_MAC_ADDRESS"]))
        assert exc_info.value.message == "invalid MAC address INVALID_MAC_ADDRESS"


def test_parse_password():
    # Test Case 1: Test with an empty password
    assert wol.parse_password(None, None, "") == b''
    # Test Case 2: Test with a valid 4-byte password
    assert wol.parse_password(None, None, "1.2.3.4") == b'\x01\x02\x03\x04'
    # Test Case 3: Test with an invalid 4-byte password
    with pytest.raises(click.BadParameter) as exc_info:
        wol.parse_password(None, None, "1.2.3.999")
        assert exc_info.value.message == "invalid password 1.2.3.999"
    # Test Case 4: Test with a valid 6-byte password
    assert wol.parse_password(None, None, str(SAMPLE_TARGET_MAC)) == SAMPLE_TARGET_MAC.to_bytes()
    # Test Case 5: Test with an invalid 6-byte password
    with pytest.raises(click.BadParameter) as exc_info:
        wol.parse_password(None, None, "11:22:33:44:55:999")
        assert exc_info.value.message == "invalid password 11:22:33:44:55:999"
    # Test Case 6: Test with an invalid password string
    with pytest.raises(click.BadParameter) as exc_info:
        wol.parse_password(None, None, "INVALID_PASSWORD")
        assert exc_info.value.message == "invalid password INVALID_PASSWORD"


def test_validate_count_interval():
    # Test Case 1: input valid count and interval
    assert wol.validate_count_interval(1, 1000) == (1, 1000)
    # Test Case 2: Test with both count and interval are not provided
    assert wol.validate_count_interval(None, None) == (1, 0)
    # Test Case 3: Test count and interval not provided together
    with pytest.raises(click.BadParameter) as exc_info:
        wol.validate_count_interval(3, None)
        assert exc_info.value.message == "count and interval must be used together"
    with pytest.raises(click.BadParameter) as exc_info:
        wol.validate_count_interval(None, 1000)
        assert exc_info.value.message == "count and interval must be used together"
    # Test Case 4: Test with count or interval not in valid range
    # This restriction is validated by click.IntRange(), so no need to call the command line function
    runner = CliRunner()
    result = runner.invoke(wol.wol, [SAMPLE_INTERFACE_ETH0, str(SAMPLE_TARGET_MAC), '-c', '100', '-i', '1000'])
    assert 'Invalid value for "-c": 100 is not in the valid range of 1 to 5.' in result.stdout
    result = runner.invoke(wol.wol, [SAMPLE_INTERFACE_ETH0, str(SAMPLE_TARGET_MAC), '-c', '3', '-i', '100000'])
    assert 'Invalid value for "-i": 100000 is not in the valid range of 0 to 2000.' in result.stdout


@patch('netifaces.interfaces', MagicMock(return_value=[SAMPLE_INTERFACE_ETH0]))
@patch('wol.main.is_root', MagicMock(return_value=True))
@patch('wol.main.get_interface_operstate', MagicMock(return_value="up"))
@patch('wol.main.get_interface_mac', MagicMock(return_value=SAMPLE_ETH0_MAC))
def test_wol_send_magic_packet_call_count():
    """
    Test the count of send_magic_packet() function call in wol is correct.
    """
    runner = CliRunner()
    # Test Case 1: Test with only required arguments
    # 1.1 Single Target Mac
    with patch('wol.main.send_magic_packet') as mock_send_magic_packet:
        result = runner.invoke(wol.wol, [SAMPLE_INTERFACE_ETH0, str(SAMPLE_TARGET_MAC)])
        assert result.exit_code == 0
        mock_send_magic_packet.assert_called_once_with(SAMPLE_INTERFACE_ETH0, SAMPLE_TARGET_MAC, SAMPLE_MAGIC_PACKET_UNICAST, 1, 0, False)
    # 1.2 Multiple Target Mac
    with patch('wol.main.send_magic_packet') as mock_send_magic_packet:
        result = runner.invoke(wol.wol, [SAMPLE_INTERFACE_ETH0, ','.join([str(v) for v in SAMPLE_TARGET_MAC_LIST])])
        assert result.exit_code == 0
        assert mock_send_magic_packet.call_count == 2
    # Test Case 2: Test with specified count and interval
    # 2.1 Single Target Mac
    with patch('wol.main.send_magic_packet') as mock_send_magic_packet:
        result = runner.invoke(wol.wol, [SAMPLE_INTERFACE_ETH0, str(SAMPLE_TARGET_MAC), '-c', '5', '-i', '1000'])
        assert result.exit_code == 0
        mock_send_magic_packet.assert_called_once_with(SAMPLE_INTERFACE_ETH0, SAMPLE_TARGET_MAC, SAMPLE_MAGIC_PACKET_UNICAST, 5, 1000, False)
    # 2.2 Multiple Target Mac
    with patch('wol.main.send_magic_packet') as mock_send_magic_packet:
        result = runner.invoke(wol.wol, [SAMPLE_INTERFACE_ETH0, ','.join([str(v) for v in SAMPLE_TARGET_MAC_LIST]), '-c', '5', '-i', '1000'])
        assert result.exit_code == 0
        assert mock_send_magic_packet.call_count == 2


@patch('netifaces.interfaces', MagicMock(return_value=[SAMPLE_INTERFACE_ETH0]))
@patch('wol.main.is_root', MagicMock(return_value=True))
@patch('wol.main.get_interface_operstate', MagicMock(return_value="up"))
@patch('wol.main.get_interface_mac', MagicMock(return_value=SAMPLE_ETH0_MAC))
def test_wol_send_magic_packet_throw_exception():
    """
    Test the exception handling of send_magic_packet() function in wol.
    """
    runner = CliRunner()
    # Test Case 1: Test with OSError exception (interface flap)
    with patch('wol.main.send_magic_packet', MagicMock(side_effect=OSError("[Errno 100] Network is down"))):
        result = runner.invoke(wol.wol, [SAMPLE_INTERFACE_ETH0, str(SAMPLE_TARGET_MAC)])
        assert "Exception: [Errno 100] Network is down" in result.stdout
    # Test Case 2: Test with other exception
    with patch('wol.main.send_magic_packet', MagicMock(side_effect=Exception("Exception message"))):
        result = runner.invoke(wol.wol, [SAMPLE_INTERFACE_ETH0, str(SAMPLE_TARGET_MAC)])
        assert "Exception: Exception message" in result.stdout

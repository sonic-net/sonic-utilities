#!/usr/bin/env python3
"""
Unit tests for the chunk-based reading logic in fetch_routes() function.
Tests various scenarios including:
- Complete JSON in single chunk
- JSON split across multiple chunks
- Incomplete JSON objects at chunk boundaries
- UTF-8 sequences split across chunks
- Empty responses
- Malformed JSON
"""

import json
from unittest.mock import Mock, patch
from io import BytesIO
import sys

sys.path.append("scripts")
import route_check  # noqa: E402


class TestFetchRoutes:
    """Test suite for chunk-based reading in fetch_routes()"""

    def setup_method(self):
        """Setup for each test method"""
        route_check.UNIT_TESTING = 1
        route_check.FRR_WAIT_TIME = 0

    def create_mock_process(self, data_bytes):
        """
        Create a mock subprocess.Popen object with stdout that returns data
        in chunks.

        Args:
            data_bytes: bytes to return from stdout

        Returns:
            Mock Popen object
        """
        mock_proc = Mock()
        mock_proc.stdout = BytesIO(data_bytes)
        mock_proc.wait = Mock(return_value=0)
        mock_proc.__enter__ = Mock(return_value=mock_proc)
        mock_proc.__exit__ = Mock(return_value=False)
        return mock_proc

    def test_complete_json_single_chunk(self):
        """Test parsing when complete JSON fits in a single chunk"""
        json_data = {
            "192.168.1.0/24": [{
                "prefix": "192.168.1.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False
            }]
        }
        json_bytes = json.dumps(json_data).encode('utf-8')

        mock_proc = self.create_mock_process(json_bytes)

        with patch('route_check.subprocess.Popen', return_value=mock_proc):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        assert result == (["192.168.1.0/24"], [])

    def test_json_split_across_chunks(self):
        """Test parsing when JSON is split across multiple chunks"""
        json_data = {
            "10.0.0.0/8": [{
                "prefix": "10.0.0.0/8",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False
            }],
            "172.16.0.0/12": [{
                "prefix": "172.16.0.0/12",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False
            }]
        }
        json_str = json.dumps(json_data)

        # Split the JSON string in the middle
        split_point = len(json_str) // 2
        chunk1 = json_str[:split_point].encode('utf-8')
        chunk2 = json_str[split_point:].encode('utf-8')

        # Create a custom BytesIO that returns data in specific chunk sizes
        class ChunkedBytesIO:
            def __init__(self, chunks):
                self.chunks = chunks
                self.index = 0

            def read(self, size):
                if self.index >= len(self.chunks):
                    return b''
                chunk = self.chunks[self.index]
                self.index += 1
                return chunk

        mock_proc = Mock()
        mock_proc.stdout = ChunkedBytesIO([chunk1, chunk2])
        mock_proc.wait = Mock(return_value=0)
        mock_proc.__enter__ = Mock(return_value=mock_proc)
        mock_proc.__exit__ = Mock(return_value=False)

        with patch('route_check.subprocess.Popen', return_value=mock_proc):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        assert set(result[0]) == {"10.0.0.0/8", "172.16.0.0/12"}

    def test_routes_with_offloaded_flag(self):
        """Test that routes with offloaded=True are not included in missing
           routes"""
        json_data = {
            "192.168.1.0/24": [{
                "prefix": "192.168.1.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": True  # This should NOT be in missing routes
            }],
            "192.168.2.0/24": [{
                "prefix": "192.168.2.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False  # This SHOULD be in missing routes
            }]
        }
        json_bytes = json.dumps(json_data).encode('utf-8')

        mock_proc = self.create_mock_process(json_bytes)

        with patch('route_check.subprocess.Popen', return_value=mock_proc):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        assert result == (["192.168.2.0/24"], [])

    def test_filter_connected_kernel_static_protocols(self):
        """Test that connected, kernel and static protocols are filtered out"""
        json_data = {
            "192.168.1.0/24": [{
                "prefix": "192.168.1.0/24",
                "protocol": "connected",
                "vrfName": "default",
                "selected": True,
                "offloaded": False
            }],
            "192.168.2.0/24": [{
                "prefix": "192.168.2.0/24",
                "protocol": "kernel",
                "vrfName": "default",
                "selected": True,
                "offloaded": False
            }],
            "192.168.3.0/24": [{
                "prefix": "192.168.3.0/24",
                "protocol": "static",
                "vrfName": "default",
                "selected": True,
                "offloaded": False
            }],
            "192.168.4.0/24": [{
                "prefix": "192.168.4.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False
            }]
        }
        json_bytes = json.dumps(json_data).encode('utf-8')

        mock_proc = self.create_mock_process(json_bytes)

        with patch('route_check.subprocess.Popen', return_value=mock_proc):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        # Only BGP route should be in the result
        assert result == (["192.168.4.0/24"], [])

    def test_filter_non_default_vrf(self):
        """Test that routes in non-default VRF are filtered out"""
        json_data = {
            "192.168.1.0/24": [{
                "prefix": "192.168.1.0/24",
                "protocol": "bgp",
                "vrfName": "Vrf_RED",
                "selected": True,
                "offloaded": False
            }],
            "192.168.2.0/24": [{
                "prefix": "192.168.2.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False
            }],
            "192.168.3.0/24": [{
                "prefix": "192.168.3.0/24",
                "protocol": "bgp",
                "vrfName": "mgmt",
                "selected": True,
                "offloaded": False
            }]
        }
        json_bytes = json.dumps(json_data).encode('utf-8')

        mock_proc = self.create_mock_process(json_bytes)

        with patch('route_check.subprocess.Popen', return_value=mock_proc):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        # Only default VRF route should be in the result
        assert result == (["192.168.2.0/24"], [])

    def test_filter_not_selected_routes(self):
        """Test that routes not selected as best are filtered out"""
        json_data = {
            "192.168.1.0/24": [{
                "prefix": "192.168.1.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": False,
                "offloaded": False
            }],
            "192.168.2.0/24": [{
                "prefix": "192.168.2.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False
            }]
        }
        json_bytes = json.dumps(json_data).encode('utf-8')

        mock_proc = self.create_mock_process(json_bytes)

        with patch('route_check.subprocess.Popen', return_value=mock_proc):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        # Only selected route should be in the result
        assert result == (["192.168.2.0/24"], [])

    def test_empty_json_response(self):
        """Test handling of empty JSON response"""
        json_data = {}
        json_bytes = json.dumps(json_data).encode('utf-8')

        mock_proc = self.create_mock_process(json_bytes)

        with patch('route_check.subprocess.Popen', return_value=mock_proc):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        assert result == ([], [])

    def test_utf8_split_across_chunks(self):
        """Test handling of UTF-8 multibyte characters split across chunks"""
        # Create JSON with UTF-8 characters
        json_data = {
            "192.168.1.0/24": [{
                "prefix": "192.168.1.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False,
                "description": "Test route with émojis 🚀"
            }]
        }
        json_str = json.dumps(json_data)
        json_bytes = json_str.encode('utf-8')

        # Find a multibyte character and split there
        # The emoji 🚀 is 4 bytes in UTF-8
        emoji_pos = json_bytes.find('🚀'.encode('utf-8'))
        if emoji_pos > 0:
            # Split in the middle of the emoji
            split_point = emoji_pos + 2
            chunk1 = json_bytes[:split_point]
            chunk2 = json_bytes[split_point:]

            class ChunkedBytesIO:
                def __init__(self, chunks):
                    self.chunks = chunks
                    self.index = 0

                def read(self, size):
                    if self.index >= len(self.chunks):
                        return b''
                    chunk = self.chunks[self.index]
                    self.index += 1
                    return chunk

            mock_proc = Mock()
            mock_proc.stdout = ChunkedBytesIO([chunk1, chunk2])
            mock_proc.wait = Mock(return_value=0)
            mock_proc.__enter__ = Mock(return_value=mock_proc)
            mock_proc.__exit__ = Mock(return_value=False)

            with patch('route_check.subprocess.Popen', return_value=mock_proc):
                result = route_check.fetch_routes(['show', 'ip', 'route',
                                                   'json'])

            assert result == (["192.168.1.0/24"], [])

    def test_very_small_chunks(self):
        """Test parsing with very small chunk sizes (byte-by-byte)"""
        json_data = {
            "10.0.0.0/8": [{
                "prefix": "10.0.0.0/8",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False
            }]
        }
        json_bytes = json.dumps(json_data).encode('utf-8')

        # Create chunks of 10 bytes each
        chunks = [json_bytes[i:i+10] for i in range(0, len(json_bytes), 10)]

        class ChunkedBytesIO:
            def __init__(self, chunks):
                self.chunks = chunks
                self.index = 0

            def read(self, size):
                if self.index >= len(self.chunks):
                    return b''
                chunk = self.chunks[self.index]
                self.index += 1
                return chunk

        mock_proc = Mock()
        mock_proc.stdout = ChunkedBytesIO(chunks)
        mock_proc.wait = Mock(return_value=0)
        mock_proc.__enter__ = Mock(return_value=mock_proc)
        mock_proc.__exit__ = Mock(return_value=False)

        with patch('route_check.subprocess.Popen', return_value=mock_proc):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        assert result == (["10.0.0.0/8"], [])

    def test_large_json_with_many_routes(self):
        """Test parsing large JSON with many route entries"""
        json_data = {}
        expected_missing = []

        # Create 100 routes
        for i in range(100):
            prefix = f"10.{i}.0.0/16"
            json_data[prefix] = [{
                "prefix": prefix,
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False
            }]
            expected_missing.append(prefix)

        json_bytes = json.dumps(json_data).encode('utf-8')

        mock_proc = self.create_mock_process(json_bytes)

        with patch('route_check.subprocess.Popen', return_value=mock_proc):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        assert set(result[0]) == set(expected_missing)
        assert len(result[0]) == 100

    def test_ipv6_command(self):
        """Test that IPv6 command is properly constructed"""
        json_data = {
            "2001:db8::/32": [{
                "prefix": "2001:db8::/32",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False
            }]
        }
        json_bytes = json.dumps(json_data).encode('utf-8')

        mock_proc = self.create_mock_process(json_bytes)

        with patch('route_check.subprocess.Popen', return_value=mock_proc) \
                as mock_popen:
            result = route_check.fetch_routes(['show', 'ipv6',
                                               'route', 'json'])

            # Verify the correct command was called
            mock_popen.assert_called_once()
            call_args = mock_popen.call_args[0][0]
            assert call_args == ["sudo", "vtysh", "-c", "show ipv6 route json"]

        assert result == (["2001:db8::/32"], [])

    def test_subprocess_non_zero_exit_code(self):
        """Test handling of subprocess with non-zero exit code"""
        json_data = {
            "192.168.1.0/24": [{
                "prefix": "192.168.1.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False
            }]
        }
        json_bytes = json.dumps(json_data).encode('utf-8')

        mock_proc = Mock()
        mock_proc.stdout = BytesIO(json_bytes)
        mock_proc.wait = Mock(return_value=1)  # Non-zero exit code
        mock_proc.__enter__ = Mock(return_value=mock_proc)
        mock_proc.__exit__ = Mock(return_value=False)

        with patch('route_check.subprocess.Popen', return_value=mock_proc):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        # Should still return the parsed routes
        assert result == (["192.168.1.0/24"], [])

    def test_file_not_found_error(self):
        """Test handling of FileNotFoundError when vtysh is not found"""
        with patch('route_check.subprocess.Popen',
                   side_effect=FileNotFoundError("vtysh not found")):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        # Should return empty list on error
        assert result == ([], [])

    def test_multiple_route_entries_per_prefix(self):
        """Test handling of multiple route entries for the same prefix"""
        json_data = {
            "192.168.1.0/24": [
                {
                    "prefix": "192.168.1.0/24",
                    "protocol": "bgp",
                    "vrfName": "default",
                    "selected": True,
                    "offloaded": True
                },
                {
                    "prefix": "192.168.1.0/24",
                    "protocol": "bgp",
                    "vrfName": "default",
                    "selected": False,
                    "offloaded": False
                }
            ]
        }
        json_bytes = json.dumps(json_data).encode('utf-8')

        mock_proc = self.create_mock_process(json_bytes)

        with patch('route_check.subprocess.Popen', return_value=mock_proc):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        # First entry is offloaded, second is not selected, so no missing
        # routes
        assert result == ([], [])

    def test_json_with_nested_objects(self):
        """Test parsing JSON with deeply nested objects"""
        json_data = {
            "192.168.1.0/24": [{
                "prefix": "192.168.1.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False,
                "nexthops": [
                    {
                        "ip": "10.0.0.1",
                        "interfaceName": "Ethernet0",
                        "active": True
                    }
                ]
            }]
        }
        json_bytes = json.dumps(json_data).encode('utf-8')

        mock_proc = self.create_mock_process(json_bytes)

        with patch('route_check.subprocess.Popen', return_value=mock_proc):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        assert result == (["192.168.1.0/24"], [])

    def test_variable_chunk_boundary(self):
        """Test when chunk boundary falls at variious locations"""
        json_data = {
            "192.168.1.0/24": [{
                "prefix": "192.168.1.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False
            }]
        }
        json_str = json.dumps(json_data)
        json_bytes = json_str.encode('utf-8')

        class ChunkedBytesIO:
            def __init__(self, chunks):
                self.chunks = chunks
                self.index = 0

            def read(self, size):
                if self.index >= len(self.chunks):
                    return b''
                chunk = self.chunks[self.index]
                self.index += 1
                return chunk

        json_len = len(json_str)
        for chunk_boundary in range(1, json_len):
            # Find the position of the first closing brace
            chunk1 = json_bytes[:chunk_boundary+1]
            chunk2 = json_bytes[chunk_boundary+1:]

            mock_proc = Mock()
            mock_proc.stdout = ChunkedBytesIO([chunk1, chunk2])
            mock_proc.wait = Mock(return_value=0)
            mock_proc.__enter__ = Mock(return_value=mock_proc)
            mock_proc.__exit__ = Mock(return_value=False)

            with patch('route_check.subprocess.Popen', return_value=mock_proc):
                result = route_check.fetch_routes(['show', 'ip', 'route',
                                                   'json'])

            assert result == (["192.168.1.0/24"], [])

    def test_chunk_boundary_in_string_value(self):
        """Test when chunk boundary falls in the middle of a string value"""
        json_data = {
            "192.168.1.0/24": [{
                "prefix": "192.168.1.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False,
                "description": "This is a very long description that will be split across chunks"
            }]
        }
        json_str = json.dumps(json_data)
        json_bytes = json_str.encode('utf-8')

        # Find the description and split in the middle of it
        desc_start = json_str.find("This is a very long")
        split_point = desc_start + 10
        chunk1 = json_bytes[:split_point]
        chunk2 = json_bytes[split_point:]

        class ChunkedBytesIO:
            def __init__(self, chunks):
                self.chunks = chunks
                self.index = 0

            def read(self, size):
                if self.index >= len(self.chunks):
                    return b''
                chunk = self.chunks[self.index]
                self.index += 1
                return chunk

        mock_proc = Mock()
        mock_proc.stdout = ChunkedBytesIO([chunk1, chunk2])
        mock_proc.wait = Mock(return_value=0)
        mock_proc.__enter__ = Mock(return_value=mock_proc)
        mock_proc.__exit__ = Mock(return_value=False)

        with patch('route_check.subprocess.Popen', return_value=mock_proc):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        assert result == (["192.168.1.0/24"], [])

    def test_escaped_quotes_in_json(self):
        """Test handling of escaped quotes in JSON strings"""
        json_data = {
            "192.168.1.0/24": [{
                "prefix": "192.168.1.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False,
                "description": "Route with \"escaped\" quotes"
            }]
        }
        json_bytes = json.dumps(json_data).encode('utf-8')

        mock_proc = self.create_mock_process(json_bytes)

        with patch('route_check.subprocess.Popen', return_value=mock_proc):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        assert result == (["192.168.1.0/24"], [])

    def test_whitespace_handling(self):
        """Test handling of JSON with various whitespace"""
        json_data = {
            "192.168.1.0/24": [{
                "prefix": "192.168.1.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False
            }]
        }
        # Add extra whitespace
        json_str = json.dumps(json_data, indent=4)
        json_str = json_str.replace(',', '   \n,')
        json_bytes = json_str.encode('utf-8')

        mock_proc = self.create_mock_process(json_bytes)

        with patch('route_check.subprocess.Popen', return_value=mock_proc):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        assert result == (["192.168.1.0/24"], [])

    def test_mixed_ipv4_and_ipv6_routes(self):
        """Test parsing JSON with both IPv4 and IPv6 routes"""
        json_data = {
            "192.168.1.0/24": [{
                "prefix": "192.168.1.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False
            }],
            "2001:db8::/32": [{
                "prefix": "2001:db8::/32",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False
            }]
        }
        json_bytes = json.dumps(json_data).encode('utf-8')

        mock_proc = self.create_mock_process(json_bytes)

        with patch('route_check.subprocess.Popen', return_value=mock_proc):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        assert set(result[0]) == {"192.168.1.0/24", "2001:db8::/32"}

    def test_malformed_json_in_buffer(self):
        """Test handling of malformed JSON that cannot be parsed"""
        malformed_json = b'{"192.168.1.0/24": [{"prefix": "192.168.1.0/24", "protocol": "bgp"'

        mock_proc = self.create_mock_process(malformed_json)

        with patch('route_check.subprocess.Popen', return_value=mock_proc):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        # Should return empty list for malformed JSON
        assert result == ([], [])

    def test_incremental_parsing_multiple_prefixes(self):
        """Test that multiple prefix entries are parsed one at a time"""
        json_data = {
            "192.168.1.0/24": [{
                "prefix": "192.168.1.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False
            }],
            "192.168.2.0/24": [{
                "prefix": "192.168.2.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False
            }],
            "192.168.3.0/24": [{
                "prefix": "192.168.3.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False
            }]
        }
        json_bytes = json.dumps(json_data).encode('utf-8')

        mock_proc = self.create_mock_process(json_bytes)

        with patch('route_check.subprocess.Popen', return_value=mock_proc):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        assert set(result[0]) == {"192.168.1.0/24",
                               "192.168.2.0/24",
                               "192.168.3.0/24"}

    def test_incremental_parsing_prefix_split_across_chunks(self):
        """Test that a prefix entry split across chunks is parsed correctly"""
        json_data = {
            "192.168.1.0/24": [{
                "prefix": "192.168.1.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False,
                "description": "This is a long description to make the entry larger"
            }],
            "192.168.2.0/24": [{
                "prefix": "192.168.2.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False,
                "description": "Another long description for the second prefix"
            }]
        }
        json_str = json.dumps(json_data)
        json_bytes = json_str.encode('utf-8')

        # Split in the middle of the first prefix entry
        # Find the position after the first prefix key
        first_prefix_end = json_str.find(']', json_str.find('"192.168.1.0/24"'))
        split_point = first_prefix_end - 20  # Split before the end of first entry

        chunk1 = json_bytes[:split_point]
        chunk2 = json_bytes[split_point:]

        class ChunkedBytesIO:
            def __init__(self, chunks):
                self.chunks = chunks
                self.index = 0

            def read(self, size):
                if self.index >= len(self.chunks):
                    return b''
                chunk = self.chunks[self.index]
                self.index += 1
                return chunk

        mock_proc = Mock()
        mock_proc.stdout = ChunkedBytesIO([chunk1, chunk2])
        mock_proc.wait = Mock(return_value=0)
        mock_proc.__enter__ = Mock(return_value=mock_proc)
        mock_proc.__exit__ = Mock(return_value=False)

        with patch('route_check.subprocess.Popen', return_value=mock_proc):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        assert set(result[0]) == {"192.168.1.0/24", "192.168.2.0/24"}

    def test_incremental_parsing_across_multiple_chunks(self):
        # Create a large JSON with many prefixes
        json_data = {}
        expected_missing = []

        for i in range(50):
            prefix = f"10.{i}.0.0/16"
            json_data[prefix] = [{
                "prefix": prefix,
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False,
                "description": f"Route {i} with some description text to make it larger"
            }]
            expected_missing.append(prefix)

        json_bytes = json.dumps(json_data).encode('utf-8')

        # Split into multiple small chunks to test incremental parsing
        chunk_size = 500
        chunks = [json_bytes[i:i+chunk_size] for i in range(0, len(json_bytes), chunk_size)]

        class ChunkedBytesIO:
            def __init__(self, chunks):
                self.chunks = chunks
                self.index = 0

            def read(self, size):
                if self.index >= len(self.chunks):
                    return b''
                chunk = self.chunks[self.index]
                self.index += 1
                return chunk

        mock_proc = Mock()
        mock_proc.stdout = ChunkedBytesIO(chunks)
        mock_proc.wait = Mock(return_value=0)
        mock_proc.__enter__ = Mock(return_value=mock_proc)
        mock_proc.__exit__ = Mock(return_value=False)

        with patch('route_check.subprocess.Popen', return_value=mock_proc):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        assert set(result[0]) == set(expected_missing)
        assert len(result[0]) == 50

    def test_incremental_parsing_prefix_boundary_at_comma(self):
        """Test parsing when chunk boundary falls at comma between prefix entries"""
        json_data = {
            "192.168.1.0/24": [{
                "prefix": "192.168.1.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False
            }],
            "192.168.2.0/24": [{
                "prefix": "192.168.2.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False
            }]
        }
        json_str = json.dumps(json_data)
        json_bytes = json_str.encode('utf-8')

        # Find the comma between the two entries
        comma_pos = json_str.find('],') + 2  # Position after "],"

        chunk1 = json_bytes[:comma_pos]
        chunk2 = json_bytes[comma_pos:]

        class ChunkedBytesIO:
            def __init__(self, chunks):
                self.chunks = chunks
                self.index = 0

            def read(self, size):
                if self.index >= len(self.chunks):
                    return b''
                chunk = self.chunks[self.index]
                self.index += 1
                return chunk

        mock_proc = Mock()
        mock_proc.stdout = ChunkedBytesIO([chunk1, chunk2])
        mock_proc.wait = Mock(return_value=0)
        mock_proc.__enter__ = Mock(return_value=mock_proc)
        mock_proc.__exit__ = Mock(return_value=False)

        with patch('route_check.subprocess.Popen', return_value=mock_proc):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        assert set(result[0]) == {"192.168.1.0/24", "192.168.2.0/24"}

    def test_incremental_parsing_mixed_offloaded_states(self):
        """Test incremental parsing with mixed offloaded states across multiple prefixes"""
        json_data = {
            "192.168.1.0/24": [{
                "prefix": "192.168.1.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": True  # This one is offloaded
            }],
            "192.168.2.0/24": [{
                "prefix": "192.168.2.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False  # This one is missing
            }],
            "192.168.3.0/24": [{
                "prefix": "192.168.3.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": True  # This one is offloaded
            }],
            "192.168.4.0/24": [{
                "prefix": "192.168.4.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False  # This one is missing
            }]
        }
        json_bytes = json.dumps(json_data).encode('utf-8')

        mock_proc = self.create_mock_process(json_bytes)

        with patch('route_check.subprocess.Popen', return_value=mock_proc):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        # Only the non-offloaded routes should be in the result
        assert set(result[0]) == {"192.168.2.0/24", "192.168.4.0/24"}

    def test_incremental_parsing_with_whitespace_variations(self):
        """Test incremental parsing with various whitespace formatting"""
        # Create JSON with extra whitespace and newlines
        json_str = """{
            "192.168.1.0/24": [
                {
                    "prefix": "192.168.1.0/24",
                    "protocol": "bgp",
                    "vrfName": "default",
                    "selected": true,
                    "offloaded": false
                }
            ],
            "192.168.2.0/24": [
                {
                    "prefix": "192.168.2.0/24",
                    "protocol": "bgp",
                    "vrfName": "default",
                    "selected": true,
                    "offloaded": false
                }
            ]
        }"""
        json_bytes = json_str.encode('utf-8')

        mock_proc = self.create_mock_process(json_bytes)

        with patch('route_check.subprocess.Popen', return_value=mock_proc):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        assert set(result[0]) == {"192.168.1.0/24", "192.168.2.0/24"}

    def test_incremental_parsing_prefix_with_special_characters(self):
        """Test incremental parsing of prefixes with special characters in descriptions"""
        json_data = {
            "192.168.1.0/24": [{
                "prefix": "192.168.1.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False,
                "description": "Route with special chars: {}, [], \", \\"
            }],
            "192.168.2.0/24": [{
                "prefix": "192.168.2.0/24",
                "protocol": "bgp",
                "vrfName": "default",
                "selected": True,
                "offloaded": False,
                "description": "Another route with: commas, colons: and braces {}"
            }]
        }
        json_bytes = json.dumps(json_data).encode('utf-8')

        mock_proc = self.create_mock_process(json_bytes)

        with patch('route_check.subprocess.Popen', return_value=mock_proc):
            result = route_check.fetch_routes(['show', 'ip', 'route', 'json'])

        assert set(result[0]) == {"192.168.1.0/24", "192.168.2.0/24"}

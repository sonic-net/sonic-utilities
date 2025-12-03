import os
import sys
from unittest import TestCase
from unittest import mock
from mock import patch
from io import StringIO 
import tests.mock_tables.dbconnector
import importlib

from utilities_common.general import load_module_from_source
# Load the file under test
port2alias_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'port2alias')


class TestPort2Alias(TestCase):
    def setUp(self):
        self.port2alias = load_module_from_source('port2alias', port2alias_path)
        self.ports = {
                "Ethernet1": {"alias" : "fortyG0/1"},
                "Ethernet2": {"alias" : "fortyG0/2"},
                "Ethernet10": {"alias" : "fortyG0/10"},
                "Ethernet_11": {"alias" : "fortyG0/11"},
                }

    @mock.patch('sys.stdout.write')
    def test_main(self, mock_stdout):
        with patch('sys.stdin', StringIO("Ethernet0")):
            self.port2alias.main()
            mock_stdout.assert_called_with("etp1")

    def test_translate_line_single_word(self):
        self.assertEqual(self.port2alias.translate_line("1", self.ports),"1")
        self.assertEqual(self.port2alias.translate_line("1\n", self.ports),"1\n")
        self.assertEqual(self.port2alias.translate_line("Ethernet1", self.ports),"fortyG0/1")
        self.assertEqual(self.port2alias.translate_line("Ethernet1\n", self.ports),"fortyG0/1\n")
        self.assertEqual(self.port2alias.translate_line("Ethernet2\n", self.ports),"fortyG0/2\n")
        self.assertEqual(self.port2alias.translate_line("Ethernet10\n", self.ports),"fortyG0/10\n")
        self.assertEqual(self.port2alias.translate_line("Ethernet20\n", self.ports),"Ethernet20\n")

    def test_translate_line_with_symbol(self):
        self.assertEqual(self.port2alias.translate_line("Ethernet_11\n", self.ports),"fortyG0/11\n")
        self.assertEqual(self.port2alias.translate_line("Ethernet1_1\n", self.ports),"Ethernet1_1\n")
        self.assertEqual(self.port2alias.translate_line("Ethernet1-1\n", self.ports),"Ethernet1-1\n")
        self.assertEqual(self.port2alias.translate_line("Ethernet1/1\n", self.ports),"fortyG0/1/1\n")
        self.assertEqual(self.port2alias.translate_line("Ethernet1:1\n", self.ports),"fortyG0/1:1\n")
        self.assertEqual(self.port2alias.translate_line("Ethernet1 U\n", self.ports),"fortyG0/1 U\n")

    def test_translate_line_multiple_words(self):
        self.assertEqual(self.port2alias.translate_line(" Ethernet1 Ethernet2 \n", self.ports)," fortyG0/1 fortyG0/2 \n")
        self.assertEqual(self.port2alias.translate_line("Ethernet1,Ethernet1,Ethernet1,Ethernet1\n", self.ports),"fortyG0/1,fortyG0/1,fortyG0/1,fortyG0/1\n")

    def test_translate_line_empty_ports(self):
        self.assertEqual(self.port2alias.translate_line("Ethernet1\n", {}),"Ethernet1\n")

class TestPort2AliasNamespace(TestCase):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        from .mock_tables import dbconnector
        from .mock_tables import mock_multi_asic
        importlib.reload(mock_multi_asic)
        dbconnector.load_namespace_config()

    def setUp(self):
        self.port2alias = load_module_from_source('port2alias', port2alias_path)

    @mock.patch('sys.stdout.write')
    def test_main(self, mock_stdout):
        with patch('sys.stdin', StringIO("Ethernet0")):
            self.port2alias.main()
            mock_stdout.assert_called_with("Ethernet1/1")

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        # change back to single asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_single_asic
        importlib.reload(mock_single_asic)
        dbconnector.load_namespace_config()

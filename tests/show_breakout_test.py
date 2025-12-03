import os
import sys
from click.testing import CliRunner
from unittest import TestCase
from swsscommon.swsscommon import ConfigDBConnector

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)

from .mock_tables import dbconnector

import show.main as show

# Expected output for 'show breakout current-mode'
current_mode_all_output = ''+ \
"""+-------------+-------------------------+
| Interface   | Current Breakout Mode   |
+=============+=========================+
| Ethernet0   | 4x25G[10G]              |
+-------------+-------------------------+
| Ethernet4   | 2x50G                   |
+-------------+-------------------------+
| Ethernet8   | 1x100G[40G]             |
+-------------+-------------------------+
"""

# Expected output for 'show breakout current-mode Ethernet0'
current_mode_intf_output = ''+ \
"""+-------------+-------------------------+
| Interface   | Current Breakout Mode   |
+=============+=========================+
| Ethernet0   | 4x25G[10G]              |
+-------------+-------------------------+
"""

# Negetive Test
# Expected output for 'show breakout current-mode Ethernet60'
current_mode_intf_output_Ethernet60 = ''+ \
"""+-------------+-------------------------+
| Interface   | Current Breakout Mode   |
+=============+=========================+
| Ethernet60  | Not Available           |
+-------------+-------------------------+
"""

class TestBreakout(TestCase):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def setUp(self):
        self.runner = CliRunner()
        self.config_db = ConfigDBConnector()
        self.config_db.connect()
        self.obj = {'db': self.config_db}

    # Test 'show interfaces  breakout current-mode'
    def test_all_intf_current_mode(self):
        result = self.runner.invoke(show.cli.commands["interfaces"].commands["breakout"].commands["current-mode"], [], obj=self.obj)
        print(sys.stderr, result.output)
        assert result.output == current_mode_all_output

    # Test 'show interfaces  breakout current-mode Ethernet0'
    def test_single_intf_current_mode(self):
        result = self.runner.invoke(show.cli.commands["interfaces"].commands["breakout"].commands["current-mode"], ["Ethernet0"], obj=self.obj)
        print(sys.stderr, result.output)
        assert result.output == current_mode_intf_output

    # Negetive Test 'show interfaces  breakout current-mode Ethernet60'
    def test_single_intf_current_mode(self):
        result = self.runner.invoke(show.cli.commands["interfaces"].commands["breakout"].commands["current-mode"], ["Ethernet60"], obj=self.obj)
        print(sys.stderr, result.output)
        assert result.output == current_mode_intf_output_Ethernet60

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

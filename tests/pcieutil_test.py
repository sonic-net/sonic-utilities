import sys
import os
from unittest import mock

from click.testing import CliRunner
from io import StringIO

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
sys.path.insert(0, modules_path)

import pcieutil.main as pcieutil

pcieutil_pcie_aer_correctable_output = """\
+---------------------+-----------+-----------+
| AER - CORRECTABLE   |   00:01.0 |   01:00.0 |
|                     |    0x0001 |    0x0002 |
+=====================+===========+===========+
| RxErr               |         0 |         1 |
+---------------------+-----------+-----------+
| BadTLP              |         1 |         0 |
+---------------------+-----------+-----------+
| TOTAL_ERR_COR       |         1 |         1 |
+---------------------+-----------+-----------+
"""

pcieutil_pcie_aer_nonfatal_output = """\
+--------------------+-----------+
| AER - NONFATAL     |   00:01.0 |
|                    |    0x0001 |
+====================+===========+
| MalfTLP            |         1 |
+--------------------+-----------+
| TOTAL_ERR_NONFATAL |         1 |
+--------------------+-----------+
"""

pcieutil_pcie_aer_correctable_verbose_output = """\
+---------------------+-----------+-----------+
| AER - CORRECTABLE   |   00:01.0 |   01:00.0 |
|                     |    0x0001 |    0x0002 |
+=====================+===========+===========+
| RxErr               |         0 |         1 |
+---------------------+-----------+-----------+
| BadTLP              |         1 |         0 |
+---------------------+-----------+-----------+
| BadDLLP             |         0 |         0 |
+---------------------+-----------+-----------+
| Rollover            |         0 |         0 |
+---------------------+-----------+-----------+
| Timeout             |         0 |         0 |
+---------------------+-----------+-----------+
| NonFatalErr         |         0 |         0 |
+---------------------+-----------+-----------+
| CorrIntErr          |         0 |         0 |
+---------------------+-----------+-----------+
| HeaderOF            |         0 |         0 |
+---------------------+-----------+-----------+
| TOTAL_ERR_COR       |         1 |         1 |
+---------------------+-----------+-----------+
"""

pcieutil_pcie_aer_fatal_verbose_output = """\
+-----------------+-----------+-----------+
| AER - FATAL     |   00:01.0 |   01:00.0 |
|                 |    0x0001 |    0x0002 |
+=================+===========+===========+
| Undefined       |         0 |         0 |
+-----------------+-----------+-----------+
| DLP             |         0 |         0 |
+-----------------+-----------+-----------+
| SDES            |         0 |         0 |
+-----------------+-----------+-----------+
| TLP             |         0 |         0 |
+-----------------+-----------+-----------+
| FCP             |         0 |         0 |
+-----------------+-----------+-----------+
| CmpltTO         |         0 |         0 |
+-----------------+-----------+-----------+
| CmpltAbrt       |         0 |         0 |
+-----------------+-----------+-----------+
| UnxCmplt        |         0 |         0 |
+-----------------+-----------+-----------+
| RxOF            |         0 |         0 |
+-----------------+-----------+-----------+
| MalfTLP         |         0 |         0 |
+-----------------+-----------+-----------+
| ECRC            |         0 |         0 |
+-----------------+-----------+-----------+
| UnsupReq        |         0 |         0 |
+-----------------+-----------+-----------+
| ACSViol         |         0 |         0 |
+-----------------+-----------+-----------+
| UncorrIntErr    |         0 |         0 |
+-----------------+-----------+-----------+
| BlockedTLP      |         0 |         0 |
+-----------------+-----------+-----------+
| AtomicOpBlocked |         0 |         0 |
+-----------------+-----------+-----------+
| TLPBlockedErr   |         0 |         0 |
+-----------------+-----------+-----------+
| TOTAL_ERR_FATAL |         0 |         0 |
+-----------------+-----------+-----------+
"""

pcieutil_pcie_aer_nonfatal_verbose_output = """\
+--------------------+-----------+-----------+
| AER - NONFATAL     |   00:01.0 |   01:00.0 |
|                    |    0x0001 |    0x0002 |
+====================+===========+===========+
| Undefined          |         0 |         0 |
+--------------------+-----------+-----------+
| DLP                |         0 |         0 |
+--------------------+-----------+-----------+
| SDES               |         0 |         0 |
+--------------------+-----------+-----------+
| TLP                |         0 |         0 |
+--------------------+-----------+-----------+
| FCP                |         0 |         0 |
+--------------------+-----------+-----------+
| CmpltTO            |         0 |         0 |
+--------------------+-----------+-----------+
| CmpltAbrt          |         0 |         0 |
+--------------------+-----------+-----------+
| UnxCmplt           |         0 |         0 |
+--------------------+-----------+-----------+
| RxOF               |         0 |         0 |
+--------------------+-----------+-----------+
| MalfTLP            |         1 |         0 |
+--------------------+-----------+-----------+
| ECRC               |         0 |         0 |
+--------------------+-----------+-----------+
| UnsupReq           |         0 |         0 |
+--------------------+-----------+-----------+
| ACSViol            |         0 |         0 |
+--------------------+-----------+-----------+
| UncorrIntErr       |         0 |         0 |
+--------------------+-----------+-----------+
| BlockedTLP         |         0 |         0 |
+--------------------+-----------+-----------+
| AtomicOpBlocked    |         0 |         0 |
+--------------------+-----------+-----------+
| TLPBlockedErr      |         0 |         0 |
+--------------------+-----------+-----------+
| TOTAL_ERR_NONFATAL |         1 |         0 |
+--------------------+-----------+-----------+
"""

pcieutil_pcie_aer_correctable_dev_output = """\
+---------------------+-----------+
| AER - CORRECTABLE   |   00:01.0 |
|                     |    0x0001 |
+=====================+===========+
| BadTLP              |         1 |
+---------------------+-----------+
| TOTAL_ERR_COR       |         1 |
+---------------------+-----------+
"""

pcieutil_load_module_warning_msg = "Failed to load platform Pcie module. Warning : No module named 'sonic_platform.pcie', fallback to load Pcie common utility."

class TestPcieUtil(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["UTILITIES_UNIT_TESTING"] = "1"

    def test_aer_all(self):
        runner = CliRunner()
        result = runner.invoke(pcieutil.cli.commands["pcie-aer"].commands["all"], [])
        assert result.output == (pcieutil_pcie_aer_correctable_output + "\n"
                                 + pcieutil_pcie_aer_nonfatal_output)

    def test_aer_correctable(self):
        runner = CliRunner()
        result = runner.invoke(pcieutil.cli.commands["pcie-aer"].commands["correctable"], [])
        assert result.output == pcieutil_pcie_aer_correctable_output

    def test_aer_fatal(self):
        runner = CliRunner()
        result = runner.invoke(pcieutil.cli.commands["pcie-aer"].commands["fatal"], [])
        assert result.output == ""

    def test_aer_non_fatal(self):
        runner = CliRunner()
        result = runner.invoke(pcieutil.cli.commands["pcie-aer"].commands["non-fatal"], [])
        assert result.output == pcieutil_pcie_aer_nonfatal_output

    def test_aer_option_verbose(self):
        runner = CliRunner()
        result = runner.invoke(pcieutil.cli.commands["pcie-aer"].commands["correctable"], ["-v"])
        assert result.output == pcieutil_pcie_aer_correctable_verbose_output

        result = runner.invoke(pcieutil.cli.commands["pcie-aer"].commands["fatal"], ["-v"])
        assert result.output == pcieutil_pcie_aer_fatal_verbose_output

        result = runner.invoke(pcieutil.cli.commands["pcie-aer"].commands["non-fatal"], ["-v"])
        assert result.output == pcieutil_pcie_aer_nonfatal_verbose_output

    def test_aer_option_device(self):
        runner = CliRunner()
        result = runner.invoke(pcieutil.cli.commands["pcie-aer"].commands["correctable"], ["-d", "0:1.0"])
        assert result.output == pcieutil_pcie_aer_correctable_dev_output

    def test_load_pcie_module_warning(self): 
        stdout = sys.stdout
        sys.stdout = result = StringIO()
        try:
            pcieutil.load_platform_pcieutil()
        except ImportError:
            pass
        sys.stdout = stdout
        assert pcieutil_load_module_warning_msg not in result.getvalue()

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["UTILITIES_UNIT_TESTING"] = "0"

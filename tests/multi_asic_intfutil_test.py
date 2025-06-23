import os
import subprocess

from click.testing import CliRunner

from .utils import get_result_and_return_code

root_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(root_path)
scripts_path = os.path.join(modules_path, "scripts")

intf_status_all = """\
      Interface         Lanes    Speed    MTU    FEC           Alias             Vlan    Oper    Admin                                             Type    Asym PFC
---------------  ------------  -------  -----  -----  --------------  ---------------  ------  -------  -----------------------------------------------  ----------
      Ethernet0   33,34,35,36      40G   9100    N/A     Ethernet1/1  PortChannel1002      up       up                                  QSFP28 or later         off
      Ethernet4   29,30,31,32      40G   9100    N/A     Ethernet1/2  PortChannel1002      up       up                                              N/A         off
     Ethernet64   29,30,31,32      40G   9100    N/A    Ethernet1/17           routed      up       up  QSFP-DD Double Density 8X Pluggable Transceiver         off
   Ethernet-BP0   93,94,95,96      40G   9100    N/A    Ethernet-BP0  PortChannel4001      up       up                                              N/A         off
   Ethernet-BP4  97,98,99,100      40G   9100    N/A    Ethernet-BP4  PortChannel4001      up       up                                              N/A         off
 Ethernet-BP256   61,62,63,64      40G   9100    N/A  Ethernet-BP256  PortChannel4009      up       up                                              N/A         off
 Ethernet-BP260   57,58,59,60      40G   9100    N/A  Ethernet-BP260  PortChannel4009      up       up                                              N/A         off
PortChannel1002           N/A      80G   9100    N/A             N/A            trunk      up       up                                              N/A         N/A
PortChannel4001           N/A      80G   9100    N/A             N/A           routed      up       up                                              N/A         N/A
PortChannel4009           N/A      80G   9100    N/A             N/A           routed      up       up                                              N/A         N/A
"""
intf_status = """\
      Interface        Lanes    Speed    MTU    FEC        Alias             Vlan    Oper    Admin             Type    Asym PFC
---------------  -----------  -------  -----  -----  -----------  ---------------  ------  -------  ---------------  ----------
      Ethernet0  33,34,35,36      40G   9100    N/A  Ethernet1/1  PortChannel1002      up       up  QSFP28 or later         off
      Ethernet4  29,30,31,32      40G   9100    N/A  Ethernet1/2  PortChannel1002      up       up              N/A         off
PortChannel1002          N/A      80G   9100    N/A          N/A            trunk      up       up              N/A         N/A
"""

intf_status_asic0 = """\
      Interface        Lanes    Speed    MTU    FEC        Alias             Vlan    Oper    Admin             Type    Asym PFC
---------------  -----------  -------  -----  -----  -----------  ---------------  ------  -------  ---------------  ----------
      Ethernet0  33,34,35,36      40G   9100    N/A  Ethernet1/1  PortChannel1002      up       up  QSFP28 or later         off
      Ethernet4  29,30,31,32      40G   9100    N/A  Ethernet1/2  PortChannel1002      up       up              N/A         off
PortChannel1002          N/A      80G   9100    N/A          N/A            trunk      up       up              N/A         N/A
"""

intf_status_asic0_all = """\
      Interface         Lanes    Speed    MTU    FEC         Alias             Vlan    Oper    Admin             Type    Asym PFC
---------------  ------------  -------  -----  -----  ------------  ---------------  ------  -------  ---------------  ----------
      Ethernet0   33,34,35,36      40G   9100    N/A   Ethernet1/1  PortChannel1002      up       up  QSFP28 or later         off
      Ethernet4   29,30,31,32      40G   9100    N/A   Ethernet1/2  PortChannel1002      up       up              N/A         off
   Ethernet-BP0   93,94,95,96      40G   9100    N/A  Ethernet-BP0  PortChannel4001      up       up              N/A         off
   Ethernet-BP4  97,98,99,100      40G   9100    N/A  Ethernet-BP4  PortChannel4001      up       up              N/A         off
PortChannel1002           N/A      80G   9100    N/A           N/A            trunk      up       up              N/A         N/A
PortChannel4001           N/A      80G   9100    N/A           N/A           routed      up       up              N/A         N/A
"""

intf_status_asic0_bp0 = """\
   Interface        Lanes    Speed    MTU    FEC         Alias             Vlan    Oper    Admin    Type    Asym PFC
------------  -----------  -------  -----  -----  ------------  ---------------  ------  -------  ------  ----------
Ethernet-BP0  93,94,95,96      40G   9100    N/A  Ethernet-BP0  PortChannel4001      up       up     N/A         off
"""

intf_description = """\
  Interface    Oper    Admin        Alias               Description
-----------  ------  -------  -----------  ------------------------
  Ethernet0      up       up  Ethernet1/1  ARISTA01T2:Ethernet3/1/1
  Ethernet4      up       up  Ethernet1/2  ARISTA01T2:Ethernet3/2/1
"""

intf_description_all = """\
     Interface    Oper    Admin           Alias               Description
--------------  ------  -------  --------------  ------------------------
     Ethernet0      up       up     Ethernet1/1  ARISTA01T2:Ethernet3/1/1
     Ethernet4      up       up     Ethernet1/2  ARISTA01T2:Ethernet3/2/1
    Ethernet64      up       up    Ethernet1/17  ARISTA01T2:Ethernet3/2/1
  Ethernet-BP0      up       up    Ethernet-BP0          ASIC1:Eth0-ASIC1
  Ethernet-BP4      up       up    Ethernet-BP4          ASIC1:Eth1-ASIC1
Ethernet-BP256      up       up  Ethernet-BP256         ASIC0:Eth16-ASIC0
Ethernet-BP260      up       up  Ethernet-BP260         ASIC0:Eth17-ASIC0
"""

intf_description_bp0 = """\
   Interface    Oper    Admin         Alias       Description
------------  ------  -------  ------------  ----------------
Ethernet-BP0      up       up  Ethernet-BP0  ASIC1:Eth0-ASIC1
"""

intf_description_asic0 = """\
  Interface    Oper    Admin        Alias               Description
-----------  ------  -------  -----------  ------------------------
  Ethernet0      up       up  Ethernet1/1  ARISTA01T2:Ethernet3/1/1
  Ethernet4      up       up  Ethernet1/2  ARISTA01T2:Ethernet3/2/1
"""

intf_description_asic0_all = """\
   Interface    Oper    Admin         Alias               Description
------------  ------  -------  ------------  ------------------------
   Ethernet0      up       up   Ethernet1/1  ARISTA01T2:Ethernet3/1/1
   Ethernet4      up       up   Ethernet1/2  ARISTA01T2:Ethernet3/2/1
Ethernet-BP0      up       up  Ethernet-BP0          ASIC1:Eth0-ASIC1
Ethernet-BP4      up       up  Ethernet-BP4          ASIC1:Eth1-ASIC1
"""

intf_invalid_asic_error="""ValueError: Unknown Namespace asic99"""

class TestInterfacesMultiAsic(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ["UTILITIES_UNIT_TESTING"] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"

    def setUp(self):
        self.runner = CliRunner()

    def test_multi_asic_interface_status_all(self):
        return_code, result = get_result_and_return_code(['intfutil', '-c', 'status', '-d', 'all'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_status_all

    def test_multi_asic_interface_status(self):
        return_code, result = get_result_and_return_code(['intfutil', '-c', 'status'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_status

    def test_multi_asic_interface_status_asic0_all(self):
        return_code, result = get_result_and_return_code(['intfutil', '-c', 'status', '-n', 'asic0', '-d', 'all'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_status_asic0_all

    def test_multi_asic_interface_status_bp0(self):
        return_code, result = get_result_and_return_code(
            ['intfutil', '-c', 'status', '-i', 'Ethernet-BP0', '-d', 'all']
        )

        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_status_asic0_bp0

    def test_multi_asic_interface_status_asic0(self):
        return_code, result = get_result_and_return_code(['intfutil', '-c', 'status', '-n', 'asic0'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_status_asic0

    def test_multi_asic_interface_desc(self):
        return_code, result = get_result_and_return_code(['intfutil', '-c', 'description'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_description

    def test_multi_asic_interface_desc_all(self):
        return_code, result = get_result_and_return_code(['intfutil', '-c', 'description', '-d', 'all'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_description_all

    def test_multi_asic_interface_desc_bp0(self):
        return_code, result = get_result_and_return_code(
            ['intfutil', '-c', 'description', '-i', 'Ethernet-BP0', '-d', 'all']
        )

        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_description_bp0

    def test_multi_asic_interface_asic0(self):
        return_code, result = get_result_and_return_code(['intfutil', '-c', 'description', '-n', 'asic0'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_description_asic0

    def test_multi_asic_interface_desc_asic0_all(self):
        return_code, result = get_result_and_return_code(['intfutil', '-c', 'description', '-n', 'asic0', '-d', 'all'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 0
        assert result == intf_description_asic0_all

    def test_invalid_asic_name_all(self):
        return_code, result = get_result_and_return_code(['intfutil', '-c', 'description', '-n', 'asic99', '-d', 'all'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 1
        assert result == intf_invalid_asic_error

    def test_invalid_asic_name(self):
        return_code, result = get_result_and_return_code(['intfutil', '-c', 'status', '-n', 'asic99'])
        print("return_code: {}".format(return_code))
        print("result = {}".format(result))
        assert return_code == 1
        assert result == intf_invalid_asic_error

    def teardown_class(cls):
        print("TEARDOWN")
        os.environ["PATH"] = os.pathsep.join(
            os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ["UTILITIES_UNIT_TESTING"] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""

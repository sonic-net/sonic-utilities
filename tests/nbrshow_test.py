"""
Regression tests for F046: CLI argument injection via shell=True in nbrshow.

ArpShow/NeighShow used to concatenate --ipaddr/--iface/--namespace directly into a shell
command string executed via subprocess.Popen(cmd, shell=True), so shell metacharacters in
those arguments could inject and run arbitrary commands. The fix builds the command as an
argv list instead, so those values can never be interpreted as shell syntax, and
fetch_nbr_data() no longer passes shell=True to subprocess.Popen.
"""
import os
import importlib.machinery
import importlib.util
from unittest import TestCase, mock

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")

# nbrshow is an extensionless script; load it directly as a module for unit testing
# (spec_from_file_location returns None for extensionless scripts, so use SourceFileLoader).
_nbrshow_loader = importlib.machinery.SourceFileLoader("nbrshow", os.path.join(scripts_path, "nbrshow"))
_nbrshow_spec = importlib.util.spec_from_loader("nbrshow", _nbrshow_loader)
nbrshow = importlib.util.module_from_spec(_nbrshow_spec)
_nbrshow_loader.exec_module(nbrshow)

# From the confirmed PoC: previously created /tmp/probe_f046 when passed as --ipaddr.
INJECTION_PAYLOAD = '127.0.0.1; echo VULN_PROBE_F046 > /tmp/probe_f046 #'


class TestArpNeighShowCommandBuilding(TestCase):
    """ArpShow/NeighShow must build an argv list, never a shell string, from user input."""

    def _built_cmd(self, cls, ipaddr, iface, namespace=None):
        with mock.patch.object(nbrshow.NbrBase, "__init__", return_value=None) as mock_init:
            cls(ipaddr, iface, namespace)
        return mock_init.call_args[0][1]

    def test_arpshow_injection_payload_stays_a_single_argv_element(self):
        cmd = self._built_cmd(nbrshow.ArpShow, INJECTION_PAYLOAD, "eth0")
        self.assertIsInstance(cmd, list)
        self.assertEqual(cmd, ["/usr/sbin/arp", "-n", INJECTION_PAYLOAD, "-i", "eth0"])

    def test_neighshow_injection_payload_stays_a_single_argv_element(self):
        cmd = self._built_cmd(nbrshow.NeighShow, INJECTION_PAYLOAD, "Ethernet0")
        self.assertIsInstance(cmd, list)
        self.assertEqual(cmd, ["/bin/ip", "-6", "neigh", "show", INJECTION_PAYLOAD, "dev", "Ethernet0"])

    def test_arpshow_clean_arguments_render_unchanged(self):
        cmd = self._built_cmd(nbrshow.ArpShow, "10.0.0.1", "Ethernet0")
        self.assertEqual(cmd, ["/usr/sbin/arp", "-n", "10.0.0.1", "-i", "Ethernet0"])

    def test_neighshow_clean_arguments_render_unchanged(self):
        cmd = self._built_cmd(nbrshow.NeighShow, "fc00::72", "PortChannel0001")
        self.assertEqual(cmd, ["/bin/ip", "-6", "neigh", "show", "fc00::72", "dev", "PortChannel0001"])

    def test_arpshow_omitted_arguments_are_omitted(self):
        cmd = self._built_cmd(nbrshow.ArpShow, None, None)
        self.assertEqual(cmd, ["/usr/sbin/arp", "-n"])


class TestFetchNbrDataNeverUsesShell(TestCase):
    """fetch_nbr_data() must invoke subprocess.Popen with an argv list and shell=False."""

    @staticmethod
    def _make_nbr(cmd, namespace=None):
        # Bypass NbrBase.__init__ (DB/ASIC connections) to isolate the subprocess call itself.
        nbr = nbrshow.NbrBase.__new__(nbrshow.NbrBase)
        nbr.namespace = namespace
        nbr.cmd = cmd
        nbr.err = None
        return nbr

    def test_no_namespace_passes_cmd_list_unmodified(self):
        nbr = self._make_nbr(["/usr/sbin/arp", "-n", INJECTION_PAYLOAD])

        with mock.patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value.communicate.return_value = ("", "")
            mock_popen.return_value.wait.return_value = 0
            nbr.fetch_nbr_data()

        args, kwargs = mock_popen.call_args
        self.assertEqual(args[0], nbr.cmd)
        self.assertNotIn(True, [kwargs.get("shell")], "subprocess.Popen must not be called with shell=True")

    def test_malicious_namespace_stays_a_single_argv_element(self):
        nbr = self._make_nbr(["/usr/sbin/arp", "-n"], namespace=INJECTION_PAYLOAD)

        with mock.patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value.communicate.return_value = ("", "")
            mock_popen.return_value.wait.return_value = 0
            nbr.fetch_nbr_data()

        args, kwargs = mock_popen.call_args
        self.assertEqual(args[0], ["ip", "netns", "exec", INJECTION_PAYLOAD, "/usr/sbin/arp", "-n"])
        self.assertNotIn(True, [kwargs.get("shell")], "subprocess.Popen must not be called with shell=True")

import os
import pytest
from unittest import mock
from click.testing import CliRunner

import show.main as show


@pytest.fixture(autouse=True)
def setup_env():
    os.environ['UTILITIES_UNIT_TESTING'] = "1"
    yield
    os.environ['UTILITIES_UNIT_TESTING'] = "0"


MOCK_EVPN_OUTPUT = "EVPN summary output"
MOCK_ES_OUTPUT = "ES list output"
MOCK_ES_EVI_OUTPUT = "ES-EVI list output"
MOCK_ES_EVI_DETAIL_OUTPUT = "ES-EVI detail output"
MOCK_L2_NH_OUTPUT = "L2-NH output"


class TestShowEvpn:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.runner = CliRunner()

    def test_show_evpn(self):
        with mock.patch('utilities_common.bgp_util.run_bgp_show_command',
                        return_value=MOCK_EVPN_OUTPUT) as mock_bgp:
            result = self.runner.invoke(show.cli.commands['evpn'], [])
            assert result.exit_code == 0, result.output
            mock_bgp.assert_called_once_with("show evpn")
            assert MOCK_EVPN_OUTPUT in result.output

    def test_show_evpn_es_no_arg(self):
        with mock.patch('utilities_common.bgp_util.run_bgp_show_command',
                        return_value=MOCK_ES_OUTPUT) as mock_bgp:
            result = self.runner.invoke(show.cli.commands['evpn'].commands['es'], [])
            assert result.exit_code == 0, result.output
            mock_bgp.assert_called_once_with("show evpn es")
            assert MOCK_ES_OUTPUT in result.output

    def test_show_evpn_es_valid_esi(self):
        esi = "01:02:03:04:05:06:07:08:09:0a"
        with mock.patch('utilities_common.bgp_util.run_bgp_show_command',
                        return_value=MOCK_ES_OUTPUT) as mock_bgp:
            result = self.runner.invoke(show.cli.commands['evpn'].commands['es'], [esi])
            assert result.exit_code == 0, result.output
            mock_bgp.assert_called_once_with("show evpn es {}".format(esi))
            assert MOCK_ES_OUTPUT in result.output

    def test_show_evpn_es_invalid_esi(self):
        with mock.patch('utilities_common.bgp_util.run_bgp_show_command') as mock_bgp:
            result = self.runner.invoke(show.cli.commands['evpn'].commands['es'],
                                        ["not-an-esi"])
            assert result.exit_code == 0, result.output
            assert "Invalid ESI format" in result.output
            mock_bgp.assert_not_called()

    def test_show_evpn_es_short_esi(self):
        with mock.patch('utilities_common.bgp_util.run_bgp_show_command') as mock_bgp:
            result = self.runner.invoke(show.cli.commands['evpn'].commands['es'],
                                        ["01:02:03"])
            assert result.exit_code == 0, result.output
            assert "Invalid ESI format" in result.output
            mock_bgp.assert_not_called()

    def test_show_evpn_es_evi_no_arg(self):
        with mock.patch('utilities_common.bgp_util.run_bgp_show_command',
                        return_value=MOCK_ES_EVI_OUTPUT) as mock_bgp:
            result = self.runner.invoke(show.cli.commands['evpn'].commands['es-evi'], [])
            assert result.exit_code == 0, result.output
            mock_bgp.assert_called_once_with("show evpn es-evi")
            assert MOCK_ES_EVI_OUTPUT in result.output

    def test_show_evpn_es_evi_valid_vni(self):
        with mock.patch('utilities_common.bgp_util.run_bgp_show_command',
                        return_value=MOCK_ES_EVI_OUTPUT) as mock_bgp:
            result = self.runner.invoke(show.cli.commands['evpn'].commands['es-evi'],
                                        ["100"])
            assert result.exit_code == 0, result.output
            mock_bgp.assert_called_once_with("show evpn es-evi vni 100")
            assert MOCK_ES_EVI_OUTPUT in result.output

    def test_show_evpn_es_evi_vni_zero(self):
        with mock.patch('utilities_common.bgp_util.run_bgp_show_command') as mock_bgp:
            result = self.runner.invoke(show.cli.commands['evpn'].commands['es-evi'], ["0"])
            assert result.exit_code == 0, result.output
            assert "Invalid VNI" in result.output
            mock_bgp.assert_not_called()

    def test_show_evpn_es_evi_vni_too_large(self):
        with mock.patch('utilities_common.bgp_util.run_bgp_show_command') as mock_bgp:
            result = self.runner.invoke(show.cli.commands['evpn'].commands['es-evi'],
                                        ["16777216"])
            assert result.exit_code == 0, result.output
            assert "Invalid VNI" in result.output
            mock_bgp.assert_not_called()

    def test_show_evpn_es_evi_vni_non_numeric(self):
        with mock.patch('utilities_common.bgp_util.run_bgp_show_command') as mock_bgp:
            result = self.runner.invoke(show.cli.commands['evpn'].commands['es-evi'],
                                        ["abc"])
            assert result.exit_code == 0, result.output
            assert "Invalid VNI" in result.output
            mock_bgp.assert_not_called()

    def test_show_evpn_es_evi_detail(self):
        with mock.patch('utilities_common.bgp_util.run_bgp_show_command',
                        return_value=MOCK_ES_EVI_DETAIL_OUTPUT) as mock_bgp:
            result = self.runner.invoke(
                show.cli.commands['evpn'].commands['es-evi'].commands['detail'], [])
            assert result.exit_code == 0, result.output
            mock_bgp.assert_called_once_with("show evpn es-evi detail")
            assert MOCK_ES_EVI_DETAIL_OUTPUT in result.output

    def test_show_evpn_l2_nh(self):
        with mock.patch('utilities_common.bgp_util.run_bgp_show_command',
                        return_value=MOCK_L2_NH_OUTPUT) as mock_bgp:
            result = self.runner.invoke(show.cli.commands['evpn'].commands['l2-nh'], [])
            assert result.exit_code == 0, result.output
            mock_bgp.assert_called_once_with("show evpn l2-nh")
            assert MOCK_L2_NH_OUTPUT in result.output

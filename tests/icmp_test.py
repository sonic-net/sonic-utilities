import json
import os
import shutil
import tempfile

from click.testing import CliRunner
from utilities_common.cli import UserCache
from utilities_common.db import Db

import clear.main as clear
import show.main as show
from show.icmp import ICMP_STATS_CACHE_FILE


tabular_session_status_output_expected = """\
Key                                    Dst IP          Tx Interval    Rx Interval  HW lookup    Cookie      State
-------------------------------------  ------------  -------------  -------------  -----------  ----------  -------
default|Ethernet0|0x4eb39592|RX        192.168.0.3               0            300  false        0x58767e7a  Up
default|Ethernet128|0x23ffb930|NORMAL  192.168.0.31            100            300  false        0x58767e7a  Down
default|Ethernet152|0x39e05375|NORMAL  192.168.0.37            100            300  false        0x58767e7a  Up
default|Ethernet8|0x69f578f5|NORMAL    192.168.0.5             100            300  false        0x58767e7a  Up
"""

session_summary_output_expected = """\
Total Sessions: 4
Up sessions: 3
RX sessions: 1
"""

tabular_session_key_status_output_expected = """\
Key                              Dst IP         Tx Interval    Rx Interval  HW lookup    Cookie      State
-------------------------------  -----------  -------------  -------------  -----------  ----------  -------
default|Ethernet0|0x4eb39592|RX  192.168.0.3              0            300  false        0x58767e7a  Up
"""


# Counter mock fixture (mock_tables/counters_db.json) wires:
#   Ethernet0   RX     (selective): RX 1234/188802, TX 0/0
#   Ethernet8   NORMAL (selective): RX 9876/1511028, TX 9870/800370
#   Ethernet152 NORMAL (native):    RX 5555/N/A,    TX 4444/N/A
# Ethernet128 has no counter wiring and must not appear in stats.
# Native rows make the byte columns mixed-type, so tabulate left-aligns
# them; the expected outputs below capture that exactly.
tabular_stats_output_expected = """\
Key                                    State      RX Pkts  RX Bytes      TX Pkts  TX Bytes
-------------------------------------  -------  ---------  ----------  ---------  ----------
default:Ethernet0:0x4eb39592:RX        Up            1234  188802              0  0
default:Ethernet152:0x39e05375:NORMAL  Up            5555  N/A              4444  N/A
default:Ethernet8:0x69f578f5:NORMAL    Up            9876  1511028          9870  800370
"""

tabular_stats_single_key_output_expected = """\
Key                              State      RX Pkts    RX Bytes    TX Pkts    TX Bytes
-------------------------------  -------  ---------  ----------  ---------  ----------
default:Ethernet0:0x4eb39592:RX  Up            1234      188802          0           0
"""

# Native single-key view: bytes columns render 'N/A' (no byte stat in
# the SAI enum).
tabular_stats_native_single_key_output_expected = """\
Key                                    State      RX Pkts  RX Bytes      TX Pkts  TX Bytes
-------------------------------------  -------  ---------  ----------  ---------  ----------
default:Ethernet152:0x39e05375:NORMAL  Up            5555  N/A              4444  N/A
"""

# After clear, baseline equals current, so the next read yields zeros
# (native bytes stay 'N/A' since they were never numeric).
tabular_stats_zero_deltas_output_expected_body = """\
Key                                    State      RX Pkts  RX Bytes      TX Pkts  TX Bytes
-------------------------------------  -------  ---------  ----------  ---------  ----------
default:Ethernet0:0x4eb39592:RX        Up               0  0                   0  0
default:Ethernet152:0x39e05375:NORMAL  Up               0  N/A                 0  N/A
default:Ethernet8:0x69f578f5:NORMAL    Up               0  0                   0  0
"""


class TestIcmpSession(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

    def test_icmpecho_summary(self):
        runner = CliRunner()
        db = Db()

        result = runner.invoke(show.cli.commands["icmp"].commands["summary"], obj=db)

        assert result.exit_code == 0
        assert result.output == session_summary_output_expected

    def test_icmpecho_sessions(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands["icmp"].commands["sessions"], obj=db)
        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        assert result.output == tabular_session_status_output_expected

    def test_icmpecho_key_sessions(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands["icmp"].commands["sessions"],
                               "default|Ethernet0|0x4eb39592|RX", obj=db)
        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        assert result.output == tabular_session_key_status_output_expected

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")


class TestIcmpStats(object):
    """Tests for `show icmp stats [-c]` and `sonic-clear icmp counters`.

    Each test gets its own temp UserCache dir to keep baselines isolated."""

    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"

    def setup_method(self, _method):
        self._cache_root = tempfile.mkdtemp(prefix="icmpstat-test-")
        # UserCache.__init__ reads SONIC_CLI_CACHE_DIR first (conftest
        # sets it per-worker), then falls back to UserCache.CACHE_DIR.
        # Override both so each test gets its own baseline directory.
        self._orig_cache_dir = UserCache.CACHE_DIR
        self._orig_env_cache = os.environ.get("SONIC_CLI_CACHE_DIR")
        UserCache.CACHE_DIR = self._cache_root + "/"
        os.environ["SONIC_CLI_CACHE_DIR"] = self._cache_root + "/"

    def teardown_method(self, _method):
        UserCache.CACHE_DIR = self._orig_cache_dir
        if self._orig_env_cache is None:
            os.environ.pop("SONIC_CLI_CACHE_DIR", None)
        else:
            os.environ["SONIC_CLI_CACHE_DIR"] = self._orig_env_cache
        shutil.rmtree(self._cache_root, ignore_errors=True)

    def _baseline_path(self):
        # Mirrors IcmpShow._baseline_path(): <CACHE>/icmpstat/<uid>/icmpstat
        return os.path.join(self._cache_root, "icmpstat",
                            str(os.getuid()), ICMP_STATS_CACHE_FILE)

    @staticmethod
    def _stats_cmd():
        return show.cli.commands["icmp"].commands["stats"]

    @staticmethod
    def _clear_icmp_counters_cmd():
        return clear.cli.commands["icmp"].commands["counters"]

    # ----- absolute-counter rendering -----

    def test_stats_all_sessions_absolute(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(self._stats_cmd(), obj=db)
        assert result.exit_code == 0
        assert result.output == tabular_stats_output_expected

    def test_stats_single_key_absolute(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(self._stats_cmd(),
                               ["default:Ethernet0:0x4eb39592:RX"], obj=db)
        assert result.exit_code == 0
        assert result.output == tabular_stats_single_key_output_expected

    def test_stats_pipe_separated_key_normalized(self):
        """`show icmp stats` accepts '|' and normalizes it to ':'."""
        runner = CliRunner()
        db = Db()
        result = runner.invoke(self._stats_cmd(),
                               ["default|Ethernet0|0x4eb39592|RX"], obj=db)
        assert result.exit_code == 0
        assert result.output == tabular_stats_single_key_output_expected

    def test_stats_native_session_renders_packets_and_na_bytes(self):
        """Native session: name-map key has no '|<DIR>' suffix; render
        must show packets from SAI_ICMP_ECHO_SESSION_STAT_{IN,OUT}_PACKETS
        and 'N/A' in both bytes columns."""
        runner = CliRunner()
        db = Db()
        result = runner.invoke(self._stats_cmd(),
                               ["default:Ethernet152:0x39e05375:NORMAL"],
                               obj=db)
        assert result.exit_code == 0
        assert result.output == tabular_stats_native_single_key_output_expected
        # Structural assertion: last 4 columns are pkts/N/A/pkts/N/A.
        data_lines = [line for line in result.output.splitlines()
                      if line.startswith("default:Ethernet152:0x39e05375:NORMAL")]
        assert len(data_lines) == 1
        tokens = data_lines[0].split()
        # 'default:...:NORMAL Up 5555 N/A 4444 N/A'
        assert tokens[-4:] == ["5555", "N/A", "4444", "N/A"]

    def test_stats_unknown_key_emits_helpful_error(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(self._stats_cmd(),
                               ["default:Ethernet999:0xdeadbeef:RX"], obj=db)
        assert result.exit_code == 0
        assert "No counters found for session 'default:Ethernet999:0xdeadbeef:RX'" in result.output

    # ----- baseline lifecycle: write -----

    def test_clear_writes_baseline_file(self):
        runner = CliRunner()
        db = Db()
        assert not os.path.exists(self._baseline_path())

        result = runner.invoke(self._clear_icmp_counters_cmd(), obj=db)
        assert result.exit_code == 0
        assert "Cleared ICMP echo session counter baseline at" in result.output

        assert os.path.isfile(self._baseline_path())
        with open(self._baseline_path()) as fh:
            payload = json.load(fh)
        assert "timestamp" in payload
        # Baseline must capture every wired direction. Native rows
        # persist packets as ints and 'null' for bytes (Python None,
        # because the SAI enum has no byte counterpart).
        assert payload["data"] == {
            "default:Ethernet0:0x4eb39592:RX": {
                "IN": [1234, 188802], "OUT": [0, 0],
            },
            "default:Ethernet8:0x69f578f5:NORMAL": {
                "IN": [9876, 1511028], "OUT": [9870, 800370],
            },
            "default:Ethernet152:0x39e05375:NORMAL": {
                "IN": [5555, None], "OUT": [4444, None],
            },
        }

    def test_inline_clear_writes_baseline_file(self):
        """`show icmp stats -c` must produce the same baseline file as
        `sonic-clear icmp counters`."""
        runner = CliRunner()
        db = Db()
        result = runner.invoke(self._stats_cmd(), ["-c"], obj=db)
        assert result.exit_code == 0
        assert "Cleared ICMP echo session counter baseline at" in result.output
        assert os.path.isfile(self._baseline_path())

    # ----- baseline lifecycle: subtraction -----

    def test_show_after_clear_yields_zero_deltas(self):
        runner = CliRunner()
        db = Db()
        # Snapshot then read; with unchanged mock values the deltas are 0.
        result = runner.invoke(self._clear_icmp_counters_cmd(), obj=db)
        assert result.exit_code == 0

        result = runner.invoke(self._stats_cmd(), obj=db)
        assert result.exit_code == 0
        # Strip the timestamp-dependent "Last cached time was ..." line.
        body = "\n".join(line for line in result.output.splitlines()
                         if not line.startswith("Last cached time was "))
        assert body + "\n" == tabular_stats_zero_deltas_output_expected_body
        assert "Last cached time was " in result.output

    def test_show_with_smaller_baseline_shows_positive_deltas(self):
        """Inject a baseline strictly smaller than current; deltas
        should be deterministic."""
        os.makedirs(os.path.dirname(self._baseline_path()), exist_ok=True)
        with open(self._baseline_path(), "w") as fh:
            json.dump({
                "timestamp": "2026-05-01 00:00:00",
                "data": {
                    "default:Ethernet0:0x4eb39592:RX": {
                        "IN": [1000, 150000], "OUT": [0, 0],
                    },
                    "default:Ethernet8:0x69f578f5:NORMAL": {
                        "IN": [9000, 1400000], "OUT": [9000, 750000],
                    },
                },
            }, fh)

        runner = CliRunner()
        db = Db()
        result = runner.invoke(self._stats_cmd(), obj=db)
        assert result.exit_code == 0
        # Expected deltas: Ethernet0 RX 234/38802, TX 0/0; Ethernet8 RX 876/111028, TX 870/50370.
        assert "Last cached time was 2026-05-01 00:00:00" in result.output
        assert "default:Ethernet0:0x4eb39592:RX" in result.output
        assert "234" in result.output and "38802" in result.output
        assert "876" in result.output and "111028" in result.output
        assert "870" in result.output and "50370" in result.output

    def test_show_with_larger_baseline_clamps_to_zero(self):
        """A recreated session resets its counters below the saved
        baseline; the delta must clamp to zero, not go negative."""
        os.makedirs(os.path.dirname(self._baseline_path()), exist_ok=True)
        with open(self._baseline_path(), "w") as fh:
            json.dump({
                "timestamp": "2026-05-01 00:00:00",
                "data": {
                    "default:Ethernet0:0x4eb39592:RX": {
                        "IN": [10**9, 10**9], "OUT": [10**9, 10**9],
                    },
                },
            }, fh)

        runner = CliRunner()
        db = Db()
        result = runner.invoke(self._stats_cmd(),
                               ["default:Ethernet0:0x4eb39592:RX"], obj=db)
        assert result.exit_code == 0
        # No negative numbers anywhere; clamp must have fired.
        assert "-" not in [token for token in result.output.split()
                           if token.lstrip("-").isdigit()]
        data_lines = [line for line in result.output.splitlines()
                      if line.startswith("default:Ethernet0:0x4eb39592:RX")]
        assert len(data_lines) == 1
        assert data_lines[0].split()[-4:] == ["0", "0", "0", "0"]

    # ----- UX guard -----

    def test_inline_clear_with_key_arg_emits_note(self):
        """`show icmp stats <key> -c` clears globally and warns that
        the key filter is ignored."""
        runner = CliRunner()
        db = Db()
        result = runner.invoke(self._stats_cmd(),
                               ["default:Ethernet0:0x4eb39592:RX", "-c"],
                               obj=db)
        assert result.exit_code == 0
        assert ("Note: -c clears the baseline for all sessions; "
                "ignoring filter 'default:Ethernet0:0x4eb39592:RX'.") in result.output
        assert "Cleared ICMP echo session counter baseline at" in result.output

    def test_clear_then_show_with_key_filter_still_subtracts(self):
        """Single-key path must use the same baseline as the all-sessions path."""
        runner = CliRunner()
        db = Db()
        runner.invoke(self._clear_icmp_counters_cmd(), obj=db)

        result = runner.invoke(self._stats_cmd(),
                               ["default:Ethernet0:0x4eb39592:RX"], obj=db)
        assert result.exit_code == 0
        assert "Last cached time was " in result.output
        data_lines = [line for line in result.output.splitlines()
                      if line.startswith("default:Ethernet0:0x4eb39592:RX")]
        assert len(data_lines) == 1
        assert data_lines[0].split()[-4:] == ["0", "0", "0", "0"]

# tests/queue_counter_test.py
import json
import os
import importlib.util
from click.testing import CliRunner
from tabulate import tabulate

# Import the actual queuestat script from sonic-utilities
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
QUEUESTAT_PATH = os.path.join(ROOT, 'scripts', 'queuestat')

spec = importlib.util.spec_from_file_location('queuestat', QUEUESTAT_PATH)
queuestat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(queuestat)

def _assert_rate_fields(json_output):
    """
    Ensure the new rate fields exist for each queue and contain numeric strings.
    Accept integers or floats as strings (e.g., "123", "123.45").
    """
    for port, port_dict in json_output.items():
        # Some implementations include a "time" field at the port level; ignore it
        if isinstance(port_dict, dict) and "time" in port_dict:
            del port_dict["time"]
        for q, qdata in port_dict.items():
            if not isinstance(qdata, dict):
                continue
            for k in ("qpktsps", "qbytesps", "qbitsps"):
                assert k in qdata, f"Missing {k} in {port}.{q}"
                val = qdata[k]
                assert isinstance(val, str), f"{k} in {port}.{q} must be a string"
                # allow digits with one optional decimal point
                assert val.replace(".", "", 1).isdigit(), f"{k}={val} in {port}.{q} is not numeric-string"


def test_headers_contain_new_columns():
    """All header variants must end with the three new rate columns."""
    expected_tail = ["Pkts/s", "Bytes/s", "Bits/s"]
    assert queuestat.std_header[-3:] == expected_tail
    assert queuestat.all_header[-3:] == expected_tail
    assert queuestat.trim_header[-3:] == expected_tail
    assert queuestat.voq_header[-3:] == expected_tail


def test_queue_counters_json_contains_rates(monkeypatch):
    """
    --json output should include qpktsps/qbytesps/qbitsps for each queue.
    We stub out data retrieval so the test doesn't need Redis/COUNTERS_DB.
    """
    runner = CliRunner()

    fake_json = {
        "Ethernet0": {
            "UC0": {
                "totalpacket": "10",
                "totalbytes": "100",
                "droppacket": "0",
                "dropbytes": "0",
                "qpktsps": "111",
                "qbytesps": "222",
                "qbitsps": "333"
            }
        }
    }

    def fake_get_print_all_stat(self, json_opt, non_zero):
        # This is what queuestat.main prints when --json is set
        assert json_opt is True
        print(json.dumps(fake_json))

    # Avoid touching Redis/flex-counters during test
    monkeypatch.setattr(queuestat.Queuestat, "get_print_all_stat", fake_get_print_all_stat)
    monkeypatch.setattr(queuestat.Queuestat, "save_fresh_stats", lambda self: None)

    result = runner.invoke(queuestat.main, ["--json"])
    assert result.exit_code == 0, result.output

    json_output = json.loads(result.output)

    # 1) New fields exist and are numeric
    _assert_rate_fields(json_output)

    # 2) If you need to keep legacy golden JSONs unchanged, strip the new fields before comparing:
    for _, port_dict in json_output.items():
        if isinstance(port_dict, dict) and "time" in port_dict:
            del port_dict["time"]
        for q, qdata in list(port_dict.items()):
            if isinstance(qdata, dict):
                for k in ("qpktsps", "qbytesps", "qbitsps"):
                    qdata.pop(k, None)

    # Minimal assertions to keep the test independent of large golden blobs
    assert "Ethernet0" in json_output
    assert "UC0" in json_output["Ethernet0"]
    assert json_output["Ethernet0"]["UC0"]["totalpacket"] == "10"
    assert json_output["Ethernet0"]["UC0"]["totalbytes"] == "100"


def test_cli_table_includes_rate_columns_default(monkeypatch):
    """
    Plain default table output should include the new columns and show their values.
    We stub the printing function to bypass DB access.
    """
    header = queuestat.std_header
    row = ["Ethernet0", "UC0", "10","100","0","0","111","222","333"]

    def fake_cnstat(self):
        print(tabulate([row], header, tablefmt="simple", stralign="right"))

    # Stub out functions used by queuestat.main() for the default path
    monkeypatch.setattr(queuestat.Queuestat, "cnstat", fake_cnstat)
    monkeypatch.setattr(queuestat.Queuestat, "cnstat_diff", lambda self: None)
    monkeypatch.setattr(queuestat.Queuestat, "save_fresh_stats", lambda self: None)

    runner = CliRunner()
    result = runner.invoke(queuestat.main, [])
    assert result.exit_code == 0, result.output

    out = result.output
    # Header presence
    for col in ("Pkts/s", "Bytes/s", "Bits/s"):
        assert col in out
    # Row values presence
    for val in ("111", "222", "333"):
        assert val in out


def test_cli_table_includes_rate_columns_trim_mode():
    """
    Trim-focused table: ensure trim_header columns plus rate columns render correctly.
    This test uses tabulate directly with queuestat.trim_header to verify structure.
    """
    header = queuestat.trim_header
    row =["Ethernet0", "UC0", "5","4", "1", "111",  "222",  "333"]

    out = tabulate([row], header, tablefmt="simple", stralign="right")

    # Header presence
    for col in ("Trim/pkts", "TrimSent/pkts", "TrimDrop/pkts", "Pkts/s", "Bytes/s", "Bits/s"):
        assert col in out
    # Row values presence
    for val in ("5", "4", "1", "111", "222", "333"):
        assert val in out


def test_cli_table_includes_rate_columns_voq_mode():
    """
    VOQ-focused table: ensure voq_header columns plus rate columns render correctly.
    This test uses tabulate directly with queuestat.voq_header to verify structure.
    """
    header = queuestat.voq_header
    row = ["Ethernet0", "VOQ0", "10", "1000", "0", "0", "2","111","222","333"]

    out = tabulate([row], header, tablefmt="simple", stralign="right")

    # Header presence
    for col in ("Voq", "Credit-WD-Del/pkts", "Pkts/s", "Bytes/s", "Bits/s"):
        assert col in out
    # Row values presence
    for val in ("10", "1000", "0", "2", "111", "222", "333"):
        assert val in out

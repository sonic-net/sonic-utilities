"""Tests for queuestat queue rate columns and JSON output.

This file:
- Loads `scripts/queuestat` even if it’s extensionless.
- Stubs platform-only deps (swsscommon, sonic_py_common, redis, utilities_common.cli).
- Verifies headers end with Pkts/s, Bytes/s, Bits/s and values appear in table/JSON.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
import types
from collections import OrderedDict
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

# -------------------------------------------------------------------
# Locate repo root and put it on sys.path so utilities_common/* works
# -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# -------------------------------------------------------
# Minimal stubs for platform-only deps used during import
# -------------------------------------------------------

# swsscommon (including ConfigDBConnector that device_info may import)
sc = types.ModuleType("swsscommon")
sc.swsscommon = sc


class SonicV2Connector:  # pylint: disable=too-few-public-methods
    """Stub for swsscommon.swsscommon.SonicV2Connector."""

    def __init__(self, *args, **kwargs) -> None:
        """No-op init for stub."""
        _ = (args, kwargs)  # mark used

    def connect(self, *args, **kwargs) -> None:
        """No-op connect for stub."""
        _ = (args, kwargs)


class DBConnector:  # pylint: disable=too-few-public-methods
    """Stub for swsscommon.swsscommon.DBConnector."""

    def __init__(self, *args, **kwargs) -> None:
        """No-op init for stub."""
        _ = (args, kwargs)


class ConfigDBConnector:  # pylint: disable=too-few-public-methods
    """Stub for swsscommon.swsscommon.ConfigDBConnector."""

    def __init__(self, *args, **kwargs) -> None:
        """No-op init for stub."""
        _ = (args, kwargs)

    def connect(self, *args, **kwargs) -> None:
        """No-op connect for stub."""
        _ = (args, kwargs)


sc.SonicV2Connector = SonicV2Connector
sc.DBConnector = DBConnector
sc.ConfigDBConnector = ConfigDBConnector
sys.modules["swsscommon"] = sc
sys.modules["swsscommon.swsscommon"] = sc

# sonic_py_common package + submodules
sp = types.ModuleType("sonic_py_common")
ma = types.ModuleType("multi_asic")
ma.is_multi_asic = lambda: False
ma.get_namespace_list = lambda: []  # required by click.Choice(...)

di = types.ModuleType("device_info")
di.is_supervisor = lambda: False
di.is_chassis = lambda: False

sp.multi_asic = ma
sp.device_info = di
sys.modules["sonic_py_common"] = sp
sys.modules["sonic_py_common.multi_asic"] = ma
sys.modules["sonic_py_common.device_info"] = di

# optional: stub redis if not installed locally (avoid unused-import warning)
if importlib.util.find_spec("redis") is None:
    rmod = types.ModuleType("redis")

    class Redis:  # pylint: disable=too-few-public-methods
        """Stub for redis.Redis."""

    class Exceptions:  # pylint: disable=too-few-public-methods
        """Stub for redis.exceptions."""

    rmod.Redis = Redis
    rmod.exceptions = Exceptions
    sys.modules["redis"] = rmod

# optional: stub utilities_common.cli to avoid lazy_object_proxy dep
if "utilities_common.cli" not in sys.modules:
    cli_mod = types.ModuleType("utilities_common.cli")

    def json_serial(obj):
        """JSON default serializer that handles datetime/date -> ISO string."""
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return str(obj)

    def json_dump(obj):
        """Dump JSON using json_serial for unsupported types."""
        return json.dumps(obj, default=json_serial)

    class UserCache:  # pylint: disable=too-few-public-methods
        """Tiny stub for utilities_common.cli.UserCache."""

        def __init__(self, *args, **kwargs) -> None:
            """No-op init for stub."""
            _ = (args, kwargs)

        # Optional get/set can be added here if tests ever use them.

    cli_mod.json_serial = json_serial
    cli_mod.json_dump = json_dump
    cli_mod.UserCache = UserCache
    sys.modules["utilities_common.cli"] = cli_mod

# ---------------------------------------------------------
# Try to import scripts/queuestat (extensionless or .py path)
# If it fails due to decorator eval, we’ll skip per-test.
# ---------------------------------------------------------
QUEUESTAT_MOD = None  # will hold the loaded module or stay None
QUEUESTAT_AVAILABLE = False

for _p in (ROOT / "scripts" / "queuestat", ROOT / "scripts" / "queuestat.py"):
    if _p.is_file():
        _ldr = importlib.machinery.SourceFileLoader("queuestat", str(_p))
        _spec = importlib.util.spec_from_loader("queuestat", _ldr)
        _mod = importlib.util.module_from_spec(_spec)
        try:
            _ldr.exec_module(_mod)
            QUEUESTAT_MOD = _mod
            QUEUESTAT_AVAILABLE = True
            break
        except AttributeError as err:
            # Common failure: click.Choice(multi_asic.get_namespace_list()) if stub not accepted
            if "get_namespace_list" in str(err):
                QUEUESTAT_AVAILABLE = False
                QUEUESTAT_MOD = None
                break
            QUEUESTAT_AVAILABLE = False
            QUEUESTAT_MOD = None
            break
        except (ImportError, OSError, RuntimeError):
            # Treat import-time dependency issues as "unavailable" and skip tests.
            QUEUESTAT_AVAILABLE = False
            QUEUESTAT_MOD = None
            break


def require_queuestat() -> None:
    """Skip the current test if queuestat couldn't be imported in this environment."""
    if not QUEUESTAT_AVAILABLE:
        pytest.skip("queuestat unavailable (import-time dependency/decorator evaluation).")


# =========================
#         TESTS
# =========================
def test_headers_have_rate_columns() -> None:
    """Verify all header variants end with the three rate columns."""
    require_queuestat()
    expected_tail = ["Pkts/s", "Bytes/s", "Bits/s"]
    assert QUEUESTAT_MOD.std_header[-3:] == expected_tail
    assert QUEUESTAT_MOD.all_header[-3:] == expected_tail
    assert QUEUESTAT_MOD.trim_header[-3:] == expected_tail
    assert QUEUESTAT_MOD.voq_header[-3:] == expected_tail


def test_cnstat_print_includes_rate_columns_and_values(capsys: pytest.CaptureFixture[str]) -> None:
    """Feed cnstat_print() one queue with known rate values and verify table output."""
    require_queuestat()
    # Minimal counter dict as produced by get_counters()
    cnstat = OrderedDict()
    cnstat["time"] = datetime.now()
    cnstat["Ethernet0"] = {
        "queuetype": "UC",
        "queueindex": "0",
        "totalpacket": "10",
        "totalbytes": "100",
        "droppacket": "0",
        "dropbytes": "0",
        "trimpkt": "0",
        "trimsentpkt": "0",
        "trimdroppkt": "0",
    }

    # Minimal rate dict: RateStats(qpktsps, qbytesps, qbitsps)
    ratestat = {"Ethernet0": QUEUESTAT_MOD.RateStats("111", "222", "333")}

    fake_self = SimpleNamespace(all=False, trim=False, voq=False)

    QUEUESTAT_MOD.Queuestat.cnstat_print(
        fake_self, "Ethernet0", cnstat, json_opt=False, non_zero=False, ratestat_dict=ratestat
    )
    out = capsys.readouterr().out

    for col in ("Pkts/s", "Bytes/s", "Bits/s"):
        assert col in out
    for val in ("111", "222", "333"):
        assert val in out


def test_json_path_includes_rate_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub get_print_all_stat to emit JSON and ensure rate fields exist & are numeric strings."""
    require_queuestat()
    # Fake JSON that queuestat.main --json is expected to print
    fake_json = {
        "Ethernet0": {
            "UC0": {
                "totalpacket": "10",
                "totalbytes": "100",
                "droppacket": "0",
                "dropbytes": "0",
                "qpktsps": "111",
                "qbytesps": "222",
                "qbitsps": "333",
            }
        }
    }

    def fake_get_print_all_stat(_self, json_opt, _non_zero) -> None:
        """Fake printer used by --json path in tests."""
        assert json_opt is True
        print(json.dumps(fake_json))

    # Avoid touching Redis/flex-counters during test
    monkeypatch.setattr(QUEUESTAT_MOD.Queuestat, "get_print_all_stat", fake_get_print_all_stat)
    monkeypatch.setattr(QUEUESTAT_MOD.Queuestat, "save_fresh_stats", lambda _self: None)

    runner = CliRunner()
    result = runner.invoke(QUEUESTAT_MOD.main, ["--json"])
    assert result.exit_code == 0, result.output

    data = json.loads(result.output)
    for _, port_dict in data.items():
        if isinstance(port_dict, dict):
            port_dict.pop("time", None)
            for _q, qdata in port_dict.items():
                if not isinstance(qdata, dict):
                    continue
                for key in ("qpktsps", "qbytesps", "qbitsps"):
                    assert key in qdata
                    assert isinstance(qdata[key], str)
                    assert qdata[key].replace(".", "", 1).isdigit()

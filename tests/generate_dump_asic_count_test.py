# Copyright 2026 Nexthop Systems Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the ASIC-count probe in scripts/generate_dump.

The bash functions get_asic_count, save_asic_count_unknown and
save_status_marker are extracted from the script and run under bash with a
fake `python3`, together with the lines of main that set NUM_ASICS from the
probe. Nothing else in main is exercised: not its ERR trap, not the
ASIC_SUFFIXES computation, and not the -r exit path through finalize.
"""
import os
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "generate_dump"


def extract_function(name):
    """Return the source of one top-level bash function from generate_dump."""
    text = SCRIPT.read_text()
    start = text.index("\n{}() {{\n".format(name)) + 1
    end = text.index("\n}\n", start) + 3
    return text[start:end]


def extract_main_asic_count_block():
    """Return the lines of main that set NUM_ASICS from get_asic_count."""
    main = extract_function("main")
    start = main.index("if ! NUM_ASICS=$(get_asic_count)")
    end = main.index("\n    fi\n", start) + len("\n    fi\n")
    return main[start:end]


# A fake `python3` that prints the given streams and exits with PY_RC.
FAKE_PYTHON = '''
python3() {
    if [ -n "$PY_STDERR" ]; then printf '%s\\n' "$PY_STDERR" >&2; fi
    if [ -n "$PY_STDOUT" ]; then printf '%s\\n' "$PY_STDOUT"; fi
    return "$PY_RC"
}
'''


def run_bash(script, py_stdout="", py_stderr="", py_rc=0):
    env = os.environ.copy()
    env["PY_STDOUT"] = py_stdout
    env["PY_STDERR"] = py_stderr
    env["PY_RC"] = str(py_rc)
    return subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)


def run_get_asic_count(py_stdout="", py_stderr="", py_rc=0):
    """Run get_asic_count with a fake `python3` that prints the given streams."""
    script = "set -u\n{}\n{}\nget_asic_count\n".format(extract_function("get_asic_count"), FAKE_PYTHON)
    return run_bash(script, py_stdout, py_stderr, py_rc)


def recorder_prelude(logdir, noop=False):
    return '''
set -u
EXT_GENERAL=1
RETURN_CODE=0
MKDIR=mkdir
V=""
NOOP={noop}
LOGDIR="{logdir}"
logger() {{ :; }}
{marker}
{recorder}
'''.format(logdir=logdir, noop="true" if noop else "false",
           marker=extract_function("save_status_marker"),
           recorder=extract_function("save_asic_count_unknown"))


def run_save_asic_count_unknown(logdir, noop=False):
    script = "{}\nsave_asic_count_unknown\necho \"RETURN_CODE=$RETURN_CODE\"\n".format(
        recorder_prelude(logdir, noop))
    return run_bash(script)


def run_main_asic_count(logdir, py_stdout="", py_stderr="", py_rc=0):
    """Run main's NUM_ASICS block with the real helpers and a fake `python3`."""
    script = "{}\n{}\n{}\n{}\necho \"NUM_ASICS=$NUM_ASICS RETURN_CODE=$RETURN_CODE\"\n".format(
        recorder_prelude(logdir),
        FAKE_PYTHON,
        extract_function("get_asic_count"),
        extract_main_asic_count_block(),
    )
    return run_bash(script, py_stdout, py_stderr, py_rc)


def test_get_asic_count_returns_probe_output():
    result = run_get_asic_count(py_stdout="2")
    assert result.returncode == 0
    assert result.stdout == "2\n"


def test_get_asic_count_ignores_stderr_traces():
    # Text on stderr is not part of the count, whatever writes it.
    trace = "TACACS+: Authorization parameters:\nTACACS+:     Command full path: /usr/bin/python3"
    result = run_get_asic_count(py_stdout="4", py_stderr=trace)
    assert result.returncode == 0
    assert result.stdout == "4\n"
    assert "TACACS+" in result.stderr


def test_get_asic_count_takes_last_stdout_line():
    # Only the last stdout line is the count; earlier lines are ignored.
    noise = "python3 not authorized by TACACS+ with given arguments, not executing\n2"
    result = run_get_asic_count(py_stdout=noise)
    assert result.returncode == 0
    assert result.stdout == "2\n"


def test_get_asic_count_fails_when_probe_prints_nothing():
    # The probe exits 0, so only the positive-integer check rejects this.
    result = run_get_asic_count(py_stdout="", py_rc=0)
    assert result.returncode == 1
    assert result.stdout == ""


def test_get_asic_count_fails_when_probe_exits_nonzero():
    # A number printed by a probe that then fails is not trusted.
    result = run_get_asic_count(py_stdout="2", py_rc=1)
    assert result.returncode == 1
    assert result.stdout == ""


def test_get_asic_count_fails_when_probe_raises():
    result = run_get_asic_count(py_stderr="Traceback: num_asics is not defined", py_rc=1)
    assert result.returncode == 1
    assert result.stdout == ""


def test_get_asic_count_rejects_zero():
    result = run_get_asic_count(py_stdout="0")
    assert result.returncode == 1
    assert result.stdout == ""


def test_save_asic_count_unknown_records_failure(tmp_path):
    # RETURN_CODE becomes the exit status in finalize under -r, as for every
    # other collector error; the status file and the warning are the record.
    logdir = tmp_path / "dump"
    result = run_save_asic_count_unknown(logdir)
    assert result.returncode == 0
    assert "RETURN_CODE=1" in result.stdout
    assert "WARNING: unable to determine the ASIC count" in result.stderr
    assert "per-ASIC data may be missing" in (logdir / "asic_count.status").read_text()


def test_save_asic_count_unknown_dry_run_writes_nothing(tmp_path):
    logdir = tmp_path / "dump"
    result = run_save_asic_count_unknown(logdir, noop=True)
    assert result.returncode == 0
    assert "asic_count.status" in result.stdout
    assert "RETURN_CODE=1" in result.stdout
    assert not logdir.exists()


def test_main_uses_probe_count(tmp_path):
    logdir = tmp_path / "dump"
    result = run_main_asic_count(logdir, py_stdout="3")
    assert result.returncode == 0
    assert "NUM_ASICS=3 RETURN_CODE=0" in result.stdout
    assert not (logdir / "asic_count.status").exists()


def test_main_falls_back_when_probe_fails(tmp_path):
    logdir = tmp_path / "dump"
    result = run_main_asic_count(logdir, py_stderr="Traceback: num_asics is not defined", py_rc=1)
    assert result.returncode == 0
    assert "NUM_ASICS=1 RETURN_CODE=1" in result.stdout
    assert "WARNING: unable to determine the ASIC count" in result.stderr
    assert (logdir / "asic_count.status").exists()

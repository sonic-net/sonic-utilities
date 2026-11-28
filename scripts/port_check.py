#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
portmonitor -- SONiC CPO port health monitor

Watches the CPO ports of a SONiC switch together with their OE / ELS, the
fiber path, the PHY/SerDes signal and the link quality, so that a hardware
defect or a signal-quality regression shows up every round while it lasts
(`--log-all false` drops the repeats and reports only the transition, see
Logging below).

Same operational shape as the community monit routeCheck:

    * single-shot by default (--once), result expressed as process exit code
    * every table it judges is opened read-only; the only writes are its own
      verdict snapshot in STATE_DB.PORT_HEALTH and the FEC baseline in
      STATE_DB.PORT_FEC_UNCOUNTERS
    * exit code: 0 PASS / 1 FAIL / 2 self-check error / 3 data unavailable

Data source
------------------------------------------

    CONFIG_DB   (4)  PORT            admin/speed/fec/lanes intent
    STATE_DB    (6)  PORT_TABLE      runtime admin/oper status
                     TRANSCEIVER_INFO / _DOM_SENSOR / _DOM_THRESHOLD
                     TRANSCEIVER_DOM_FLAG / _DOM_FLAG_CHANGE_COUNT
                     TRANSCEIVER_STATUS / _STATUS_SW / _STATUS_FLAG
                     PORT_HEALTH (written: last verdict per port)
    COUNTERS_DB (2)  PORT_PHY_ATTR   SD / LOCK / SNR per lane
                     COUNTERS_PORT_NAME_MAP + COUNTERS:<oid>  FEC/FDR counters

Gate ladder
-----------
Every checker declares the gates that can block it. The ladder is evaluated
cheapest-and-most-decisive first, and a fired gate short-circuits the gates
below it -- the operator is told the outermost cause, not its symptoms:

    L1  XCVRD_STATUS, CPO_CMIS_SM_NOT_READY
    L2  CPO_PORT_ADMIN_DOWN
    L3  ELS_MODULE_ABSENT
    L4  CPO_FIBER_ABSENT
    L5  CPO_PORT_OPER_DOWN, ELS_NO_DOM, ELS_NO_DOM_THRESHOLD
    L6  CPO_NO_COUNTERS_OID

Logging
-------
Two channels, one verdict:

    syslog                    one line per verdict change, for the operator
    cpo_port_monitor.log      the gate ladder, the evidence and the counters
                              behind that verdict, for whoever debugs it

Logging policy
--------------
STATE_DB.PORT_HEALTH is the monitor's memory. A round compares
(severity, error_code, active_codes, lane_mask, gated_by) with the stored row:

    different -> rewrite the row, first_seen=now, change_count+1
    identical -> no write, counters unchanged

The row counts changes; what syslog says is a separate decision:

    default          a faulty port is written every round with the same line,
                     so silence means healthy and a line means "still broken"
    --log-all false  a verdict is written on the round it changes, so a fault
                     that sits there for a day is one line, not 288

Both modes are one line per faulty port per round at most, and the line has
the same shape either way; only the repeat policy differs.

Announced once either way are the two edges of an episode: the recovery
(ERR_CODE_RECOVERED) and the port that stops being judged
(MONITOR_SUSPENDED, i.e. a gate fired). Both go out at NOTICE -- they are
the lines the operator waits for, and the default syslog threshold would
otherwise drop them. A port whose checkers were *all* skipped keeps its
codes in the row's `retained_codes` next to the gate name, so the table
alone answers "why is this port quiet" and a gate is never mistaken for a
repair. A port where only some checkers were skipped keeps a normal verdict
row: part of it was judged, and which part did not run is the detail log's
question, not the table's.

Usage
-----
    portmonitor --once                    # one round, exit code for monit
    portmonitor --once --json             # JSON on stdout
    portmonitor --once --port Ethernet0   # single port, troubleshooting
    portmonitor --once --thresholds /path/to/port_health_thresholds.json
    portmonitor --interval 30             # resident mode
    portmonitor -m DEBUG --once           # gate details also to syslog
    portmonitor --log-all false --interval 30   # only on change, not every round
    portmonitor --list-checks             # catalogue: checks, gates, codes
"""

from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import os
import re
import signal
import socket
import sys
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple
import sonic_platform.platform

try:
    import psutil
except ImportError:      # a probe that cannot run must not stop the program
    psutil = None

VERSION = "6.0.0"
SYSLOG_IDENTIFIER = "port_monitor"
# The detailed channel: gate ladder, evidence, counters. Nothing outside
# this program rotates it -- a box may have no logrotate entry for the file
# at all, and one that gets added later must not be the only thing standing
# between a fault and a full /var/log. So the file caps itself: once it
# reaches the limit it is emptied and starts over, keeping one path, one
# inode and a hard ceiling on how much space this program can ever take.
DETAIL_LOG_PATH = "/var/log/cpo_port_monitor.log"
DETAIL_LOG_MAX_BYTES = 250 * 1024 * 1024

# ---------------------------------------------------------------------------
# Databases and tables
# ---------------------------------------------------------------------------
DB_CONFIG = "CONFIG_DB"
DB_STATE = "STATE_DB"
DB_COUNTERS = "COUNTERS_DB"

T_PORT = "PORT"
T_PORT_TABLE = "PORT_TABLE"
T_TRANSCEIVER_INFO = "TRANSCEIVER_INFO"
T_TRANSCEIVER_DOM_SENSOR = "TRANSCEIVER_DOM_SENSOR"
T_TRANSCEIVER_DOM_THRESHOLD = "TRANSCEIVER_DOM_THRESHOLD"
T_TRANSCEIVER_DOM_FLAG = "TRANSCEIVER_DOM_FLAG"
T_TRANSCEIVER_DOM_FLAG_CHANGE_COUNT = "TRANSCEIVER_DOM_FLAG_CHANGE_COUNT"
T_TRANSCEIVER_STATUS = "TRANSCEIVER_STATUS"
T_TRANSCEIVER_STATUS_SW = "TRANSCEIVER_STATUS_SW"
T_TRANSCEIVER_STATUS_FLAG = "TRANSCEIVER_STATUS_FLAG"
T_TRANSCEIVER_STATUS_FLAG_CHANG_COUNT = "TRANSCEIVER_STATUS_FLAG_CHANGE_COUNT"
T_PORT_PHY_ATTR = "PORT_PHY_ATTR"
T_COUNTERS_NAME_MAP = "COUNTERS_PORT_NAME_MAP"
# Written by this program: the last result per port, used as the memory
# that turns repeated findings into one log line per transition.
T_PORT_HEALTH = "PORT_HEALTH"
T_PORT_FEC_UNCOUNTERS = "PORT_FEC_UNCOUNTERS"

platform_chassis = sonic_platform.platform.Platform().get_chassis()

# ---------------------------------------------------------------------------
# Severity: the eight syslog levels, used numerically
#
# FAIL line is LOG_ERR(3): {EMERG, ALERT, CRIT, ERR} make the run fail,
# WARNING and below do not. This matches routeCheck's default reporting
# level.
# ---------------------------------------------------------------------------


class Severity(IntEnum):
    EMERG = 0
    ALERT = 1
    CRIT = 2
    ERR = 3
    WARNING = 4
    NOTICE = 5
    INFO = 6
    DEBUG = 7


FAIL_MAX = int(Severity.ERR)


class Action:
    NO_ACTION = "NO_ACTION"
    LOG_ONLY = "LOG_ONLY"
    CHECK_CONFIG = "CHECK_CONFIG"
    CHECK_REMOTE = "CHECK_REMOTE"
    CHECK_THERMAL = "CHECK_THERMAL"
    CHECK_FIBER_ATTACHMENT = "CHECK_FIBER_ATTACHMENT"
    CHECK_MODULE_ATTACHMENT = "CHECK_MODULE_ATTACHMENT"
    UPGRADE_FW = "UPGRADE_FW"
    VENDOR_ESCALATION = "VENDOR_ESCALATION"


# ---------------------------------------------------------------------------
# Issue registry
#
# Internal identifiers only. They are used to merge per-lane findings and to
# key the STATE_DB snapshot. syslog carries the code next to the plain-language
# message, severity and suggested action, so an operator can grep either one.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class IssueDef:
    key: str
    severity: Severity
    action: str
    summary: str
    implemented: bool = True


ISSUES: Dict[str, IssueDef] = {}


def register(key: str, severity: Severity, action: str, summary: str,
             implemented: bool = True) -> None:
    if key in ISSUES:
        raise RuntimeError("duplicate issue key %s" % key)
    ISSUES[key] = IssueDef(key, severity, action, summary, implemented)


# --- module presence ---------------------------------------------------------
# An empty cage is normal, so it is INFO with no action. It is still
# evaluated because ELS_MODULE_ABSENT is derived from it and gates everything
# downstream.
register("MODULE_PRESENCE_ABSENT", Severity.INFO, Action.NO_ACTION,
         "pluggable module is not present")

register("ELS_MODULE_PRESENCE_ABSENT", Severity.ERR, Action.CHECK_MODULE_ATTACHMENT,
         "ELS is not present")

# --- EEPROM ------------------------------------------------------------------
register("OE_MODULE_EEPROM_BAD_ID", Severity.ERR, Action.VENDOR_ESCALATION,
         "OE module identifier is not recognised")

register("ELS_MODULE_EEPROM_BAD_ID", Severity.ERR, Action.VENDOR_ESCALATION,
         "ELS module identifier is not recognised")

# --- CMIS state --------------------------------------------------------------
register("OE_CMIS_SW_NOT_READY", Severity.ERR, Action.VENDOR_ESCALATION,
         "OE CMIS state machine is not ready")

register("ELS_CMIS_SW_NOT_READY", Severity.ERR, Action.VENDOR_ESCALATION,
         "ELS CMIS state machine is not ready")

# --- DOM data and flags ------------------------------------------------------
register("OE_MODULE_NO_DOM_INFO", Severity.ERR, Action.VENDOR_ESCALATION,
         "OE module reports no DOM data")
register("OE_MODULE_NO_DOM_THRESHOLD", Severity.ERR, Action.VENDOR_ESCALATION,
         "OE module reports no DOM thresholds")

register("OE_MODULE_TX_POWER_LOW_ALARM", Severity.ERR,
         Action.CHECK_FIBER_ATTACHMENT, "TX power low alarm")
register("OE_MODULE_TX_POWER_HIGH_ALARM", Severity.ERR,
         Action.CHECK_FIBER_ATTACHMENT, "TX power high alarm")
register("OE_MODULE_TX_POWER_LOW_WARN", Severity.WARNING,
         Action.CHECK_FIBER_ATTACHMENT, "TX power low warning")
register("OE_MODULE_TX_POWER_HIGH_WARN", Severity.WARNING,
         Action.CHECK_FIBER_ATTACHMENT, "TX power high warning")

register("OE_MODULE_TX_BIAS_LOW_ALARM", Severity.ERR, Action.VENDOR_ESCALATION,
         "TX bias low alarm")
register("OE_MODULE_TX_BIAS_HIGH_ALARM", Severity.ERR, Action.VENDOR_ESCALATION,
         "TX bias high alarm")
register("OE_MODULE_TX_BIAS_LOW_WARN", Severity.WARNING, Action.VENDOR_ESCALATION,
         "TX bias low warning")
register("OE_MODULE_TX_BIAS_HIGH_WARN", Severity.WARNING, Action.VENDOR_ESCALATION,
         "TX bias high warning")

register("OE_MODULE_TX_FAULT", Severity.WARNING, Action.VENDOR_ESCALATION,
         "OE module TX fault flag is set")
register("OE_MODULE_TX_LOS", Severity.WARNING, Action.VENDOR_ESCALATION,
         "OE module TX LOS flag is set")

register("OE_MODULE_RX_POWER_LOW_ALARM", Severity.ERR,
         Action.CHECK_FIBER_ATTACHMENT, "RX power low alarm")
register("OE_MODULE_RX_POWER_HIGH_ALARM", Severity.ERR,
         Action.CHECK_FIBER_ATTACHMENT, "RX power high alarm")
register("OE_MODULE_RX_POWER_LOW_WARN", Severity.WARNING,
         Action.CHECK_FIBER_ATTACHMENT, "RX power low warning")
register("OE_MODULE_RX_POWER_HIGH_WARN", Severity.WARNING, Action.CHECK_FIBER_ATTACHMENT,
         "RX power high warning")
register("OE_MODULE_RX_LOS", Severity.WARNING, Action.CHECK_FIBER_ATTACHMENT,
         "OE module RX LOS flag is set")

register("OE_MODULE_TEMP_HIGH_ALARM", Severity.ERR, Action.CHECK_THERMAL,
         "OE module temperature high alarm")
register("OE_MODULE_TEMP_LOW_ALARM", Severity.ERR, Action.CHECK_THERMAL,
         "OE module temperature low alarm")
register("OE_MODULE_TEMP_HIGH_WARN", Severity.WARNING, Action.CHECK_THERMAL,
         "OE module temperature high warning")
register("OE_MODULE_TEMP_LOW_WARN", Severity.WARNING, Action.CHECK_THERMAL,
         "OE module temperature low warning")

register("OE_MODULE_VOLTAGE_HIGH_ALARM", Severity.ERR, Action.VENDOR_ESCALATION,
         "OE module supply voltage high alarm")
register("OE_MODULE_VOLTAGE_LOW_ALARM", Severity.ERR, Action.VENDOR_ESCALATION,
         "OE module supply voltage low alarm")
register("OE_MODULE_VOLTAGE_HIGH_WARN", Severity.WARNING, Action.VENDOR_ESCALATION,
         "OE module supply voltage high warning")
register("OE_MODULE_VOLTAGE_LOW_WARN", Severity.WARNING, Action.VENDOR_ESCALATION,
         "OE module supply voltage low warning")

register("ELS_MODULE_TEMP_HIGH_ALARM", Severity.ERR, Action.CHECK_THERMAL,
         "ELS module temperature high alarm")
register("ELS_MODULE_TEMP_LOW_ALARM", Severity.ERR, Action.CHECK_THERMAL,
         "ELS module temperature low alarm")
register("ELS_MODULE_TEMP_HIGH_WARN", Severity.WARNING, Action.CHECK_THERMAL,
         "ELS module temperature high warning")
register("ELS_MODULE_TEMP_LOW_WARN", Severity.WARNING, Action.CHECK_THERMAL,
         "ELS module temperature low warning")

register("ELS_MODULE_VOLTAGE_HIGH_ALARM", Severity.ERR, Action.VENDOR_ESCALATION,
         "ELS module supply voltage high alarm")
register("ELS_MODULE_VOLTAGE_LOW_ALARM", Severity.ERR, Action.VENDOR_ESCALATION,
         "ELS module supply voltage low alarm")
register("ELS_MODULE_VOLTAGE_HIGH_WARN", Severity.WARNING, Action.VENDOR_ESCALATION,
         "ELS module supply voltage high warning")
register("ELS_MODULE_VOLTAGE_LOW_WARN", Severity.WARNING, Action.VENDOR_ESCALATION,
         "ELS module supply voltage low warning")

# --- module firmware  --------------------------------------------
register("OE_MODULE_FW_FAULT", Severity.WARNING, Action.UPGRADE_FW,
         "OE module firmware fault")

# --- ASIC / SerDes -----------------------------------------------------------
# The design document's PORT_HEALTH sample carries ASIC_SIGNAL_ASSERT with
# action=VENDOR_ESCALATION: a lane that lost SD/LOCK while light arrives is a
# SerDes/ASIC issue, not something a fiber reseat fixes.
register("ASIC_SIGNAL_ASSERT", Severity.ERR, Action.VENDOR_ESCALATION,
         "SerDes lane lost signal or the signal unlocked")

# --- signal quality ----------------------------------------------------------
# One code, capped at WARNING: a bad pre-FEC BER is a quality warning, not
# a claim that the port is unusable, so it must not turn the run into FAIL.
register("SIGNAL_WARNING", Severity.WARNING, Action.VENDOR_ESCALATION,
         "Port has uncorrectable codeword or the FDR degradation")


# ---------------------------------------------------------------------------
# Gates
#
# A gate is a named boolean. A checker that lists a gate in its `gates`
# tuple is skipped when that gate evaluates True: no sampling, no judgement,
# no entry in the active findings. Anything else -- False or unknown --
# lets the check run, and the check reports what the data actually says.
# Every decision is logged to the detail log.
#
# The names are the ones the design document uses, so a gate written in a
# bug report, in --list-checks and in the detail log are the same string.
# ---------------------------------------------------------------------------
G_XCVRD_STATUS = "XCVRD_STATUS"
G_CPO_CMIS_SM_NOT_READY = "CPO_CMIS_SM_NOT_READY"
G_CPO_PORT_ADMIN_DOWN = "CPO_PORT_ADMIN_DOWN"
G_ELS_MODULE_ABSENT = "ELS_MODULE_ABSENT"
G_CPO_FIBER_ABSENT = "CPO_FIBER_ABSENT"
G_CPO_PORT_OPER_DOWN = "CPO_PORT_OPER_DOWN"
G_ELS_NO_DOM = "ELS_NO_DOM"
G_ELS_NO_DOM_THRESHOLD = "ELS_NO_DOM_THRESHOLD"
G_CPO_NO_COUNTERS_OID = "CPO_NO_COUNTERS_OID"

# Threshold gate. Not a hardware condition but missing configuration: the
# fiber check cannot run at all without a floor to compare against, so it is
# skipped instead of being run against a number nobody chose (design doc 8.3).
G_NO_RX_LOW_THRESHOLD = "NO_RX_LOW_THRESHOLD"

# Gate layers. A gate is evaluated only after every gate of a lower
# layer allowed the port through, so higher layers can assume the
# preconditions below them hold.
GATE_LAYER: Dict[str, int] = {
    G_XCVRD_STATUS: 1,
    G_CPO_CMIS_SM_NOT_READY: 1,
    G_CPO_PORT_ADMIN_DOWN: 2,
    G_ELS_MODULE_ABSENT: 3,
    G_CPO_FIBER_ABSENT: 4,
    G_CPO_PORT_OPER_DOWN: 5,
    G_ELS_NO_DOM: 5,
    G_ELS_NO_DOM_THRESHOLD: 5,
    G_CPO_NO_COUNTERS_OID: 6,
    G_NO_RX_LOW_THRESHOLD: 9,
}

# Names used by earlier builds. They resolve to the gate of the same
# meaning, so an operator script, a saved JSON result or a test that still
# says MODULE_ABSENT keeps working instead of silently reading "no gate".
GATE_ALIASES: Dict[str, str] = {
    "PORT_ADMIN_DOWN": G_CPO_PORT_ADMIN_DOWN,
    "MODULE_ABSENT": G_ELS_MODULE_ABSENT,
    "CMIS_SM_NOT_READY": G_CPO_CMIS_SM_NOT_READY,
    "PORT_OPER_DOWN": G_CPO_PORT_OPER_DOWN,
    "NO_DOM": G_ELS_NO_DOM,
    "CPO_NO_DOM": G_ELS_NO_DOM,
    "NO_DOM_THRESHOLD": G_ELS_NO_DOM_THRESHOLD,
    "CPO_NO_DOM_THRESHOLD": G_ELS_NO_DOM_THRESHOLD,
    "NO_COUNTERS_OID": G_CPO_NO_COUNTERS_OID,
    "FIBER_ABSENT": G_CPO_FIBER_ABSENT,
}

GATE_MEANING: Dict[str, Tuple[str, str]] = {
    G_XCVRD_STATUS:
        ("no xcvrd process is running, so every TRANSCEIVER_* table is frozen",
         "xcvrd is running and refreshing the TRANSCEIVER_* tables"),
    G_CPO_PORT_ADMIN_DOWN:
        ("admin_status is not up",
         "admin_status is up"),
    G_CPO_PORT_OPER_DOWN:
        ("netdev_oper_status is not up",
         "netdev_oper_status is up"),
    G_ELS_MODULE_ABSENT:
        ("STATE_DB has no TRANSCEIVER_INFO for the ELS of this port",
         "the ELS module is present"),
    G_CPO_CMIS_SM_NOT_READY:
        ("cmis_state is failed or not yet ready",
         "CMIS state machine is ready"),
    G_ELS_NO_DOM:
        ("TRANSCEIVER_DOM_SENSOR has no tx power, rx power or temperature",
         "ELS DOM data is present"),
    G_ELS_NO_DOM_THRESHOLD:
        ("TRANSCEIVER_DOM_THRESHOLD has no txpower, rxpower, temp or vcc",
         "ELS DOM thresholds are present"),
    G_CPO_NO_COUNTERS_OID:
        ("COUNTERS_PORT_NAME_MAP has no oid for the port",
         "FEC / FDR counters are addressable"),
    G_CPO_FIBER_ABSENT:
        ("RX LOS is set on every lane",
         "at least one lane receives light"),
    G_NO_RX_LOW_THRESHOLD:
        ("fiber.rx_low_dbm is missing from the threshold file",
         "fiber.rx_low_dbm is configured"),
}


def gate_skip_reason(name: str) -> str:
    return GATE_MEANING.get(canonical_gate(name), (name, name))[0]


def gate_run_condition(name: str) -> str:
    return GATE_MEANING.get(canonical_gate(name), (name, name))[1]


def canonical_gate(name: str) -> str:
    """The design-document name of a gate, accepting the legacy spelling."""
    return GATE_ALIASES.get(name, name)


def gate_is_set(name: str, gates: Dict[str, bool]) -> bool:
    """
    True when `name` fired, under either its own or its legacy spelling.

    The gate dict is keyed by the canonical name; the alias arm keeps dicts
    produced elsewhere -- tests that inject a single gate by its old name,
    an older cached JSON result -- from reading as "did not fire".
    """
    canonical = canonical_gate(name)
    if gates.get(canonical):
        return True
    for alias, target in GATE_ALIASES.items():
        if target == canonical and gates.get(alias):
            return True
    return False


def topmost_fired_gate(gate_names: Sequence[str], gates: Dict[str, bool]) -> str:
    """
    The gate that fired first in the ladder, or "" when none fired.

    A checker is skipped by the outermost gate that fired, not by the
    symptom it caused: an absent ELS is why there is no DOM data to read,
    so "ELS_MODULE_ABSENT" is what the operator is told, not "ELS_NO_DOM".

    Ties -- same layer, or two implementation gates -- go to the one
    written first in the checker's `gates` tuple, so that tuple stays in
    operational order rather than alphabetical.
    """
    blocker = ""
    for name in gate_names:
        if not gate_is_set(name, gates):
            continue
        if not blocker:
            blocker = name
            continue
        if GATE_LAYER.get(canonical_gate(name), 9) < GATE_LAYER.get(canonical_gate(blocker), 9):
            blocker = name
    return canonical_gate(blocker) if blocker else ""


def xcvrd_is_running() -> bool:
    """
    True while an xcvrd process is visible.

    xcvrd is what refreshes every TRANSCEIVER_* table. When it is gone the
    DB keeps its last values forever: the tables still look healthy, they
    just describe a moment that has passed. That is the one thing this
    program cannot tell from the data itself, so it asks the process list.

    A missing psutil counts as running -- the probe must never be the
    reason a round stays silent.
    """
    if psutil is None:
        return True
    for proc in psutil.process_iter(["name", "cmdline"]):
        try:
            name = proc.info["name"] or ""
            cmdline = proc.info["cmdline"] or []

            if name == "xcvrd":
                return True
            for arg in cmdline:
                if arg.endswith("/xcvrd") or arg == "xcvrd":
                    return True

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def to_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def to_lower_text(value: Any) -> str:
    return to_text(value).lower()


def to_float(value: Any) -> Optional[float]:
    s = to_text(value).replace(",", "")
    if not s:
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return f


def to_int(value: Any) -> Optional[int]:
    f = to_float(value)
    return int(f) if f is not None else None


def to_bool(value: Any) -> Optional[bool]:
    s = to_lower_text(value)
    if s in ("1", "true", "yes", "on", "up", "ok", "present"):
        return True
    if s in ("0", "false", "no", "off", "down", "absent"):
        return False
    return None


def lowercase_field_names(row: Dict[str, str]) -> Dict[str, str]:
    """Same row, same values, every field name in lower case."""
    out: Dict[str, str] = {}
    for key, value in row.items():
        out[key.lower()] = value
    return out


def all_at_or_below(values: Iterable[float], limit: float) -> bool:
    """True when every value read from the table sits at or below `limit`."""
    for value in values:
        if value > limit:
            return False
    return True


def all_in(values: Iterable[Any], allowed: Iterable[Any]) -> bool:
    """True when every value is one of `allowed`."""
    for value in values:
        if value not in allowed:
            return False
    return True


def first_field(row: Dict[str, str], *names: str) -> str:
    """Case-insensitive field lookup, returns the first non-empty value."""
    if not row:
        return ""
    fields = lowercase_field_names(row)
    for name in names:
        value = fields.get(name.lower())
        if value not in (None, ""):
            return str(value)
    return ""


def first_float_field(row: Dict[str, str], *names: str) -> Optional[float]:
    return to_float(first_field(row, *names))


def lane_mask(lanes: Iterable[int]) -> str:
    mask = 0
    for lane in lanes:
        if lane is not None and lane >= 0:
            mask |= 1 << lane
    return "0x%02x" % mask if mask else ""


def port_name_sort_key(name: str) -> Tuple[str, int, str]:
    m = re.match(r"([A-Za-z]+)(\d+)", name)
    if m:
        return m.group(1), int(m.group(2)), name
    return name, 0, name


def truncate(text: str, limit: int = 1000) -> str:
    return text if len(text) <= limit else text[:limit - 3] + "..."


def join_or_dash(items: Iterable[str]) -> str:
    """Comma-join, or a single "-" when the list is empty."""
    text = ",".join(items)
    if not text:
        return "-"
    return text


def num_text(value: Optional[int]) -> str:
    """
    A counter as text, or "n/a" when the table did not publish it.

    A missing counter is normal on a port whose ASIC does not export that
    statistic; it must degrade the evidence, not raise while formatting it.
    """
    return "n/a" if value is None else "%d" % value


def evidence(pairs: Sequence[Tuple[str, Any]]) -> str:
    parts = []
    for key, value in pairs:
        if value is None or value == "":
            continue
        parts.append("%s=%s" % (key, value))
    return truncate(";".join(parts))


# ---------------------------------------------------------------------------
# Thresholds
#
# There is deliberately no built-in table: thresholds come from exactly one
# JSON file, either the path given with --thresholds or the per-hwsku
# default below. A missing or unreadable file is a configuration error
# (exit 2), because a monitor with no numbers at all is not monitoring --
# monit must say so instead of staying quiet. A file that loads but lacks a
# specific key only disables the checker that needs that key (design doc
# 8.3), which is reported as a skip, not as a fault.
# ---------------------------------------------------------------------------
THRESHOLD_FILENAME = "port_health_thresholds.json"
LEGACY_THRESHOLD_PATH = "/usr/share/sonic/hwsku/%s" % THRESHOLD_FILENAME


def device_hwsku() -> str:
    try:
        from sonic_py_common import device_info
        hwsku = to_text(device_info.get_hwsku())
        if hwsku:
            return hwsku
    except Exception:
        pass
    return None


def default_threshold_path() -> str:
    """
    /usr/share/sonic/device/<platform>/<hwsku>/port_health_thresholds.json

    The platform and hwsku are read from sonic_py_common, because that is
    where the rest of SONiC keeps per-SKU data. A build without those
    helpers falls back to the older flat path so the program still starts.
    """
    try:
        from sonic_py_common import device_info
        platform = to_text(device_info.get_platform())
        hwsku = to_text(device_info.get_hwsku())
        if platform and hwsku:
            return os.path.join("/usr/share/sonic/device", platform, hwsku,
                                THRESHOLD_FILENAME)
    except Exception:
        pass
    return LEGACY_THRESHOLD_PATH


DEFAULT_THRESHOLD_PATH = default_threshold_path()

# Keys the code indexes directly, as (path, description). They are checked
# after loading; a key that is absent or not numeric disables the checker
# that reads it and is reported once per round.
REQUIRED_NUMERIC_KEYS: Tuple[Tuple[str, ...], ...] = (
    ("fiber", "rx_low_dbm"),
    ("fdr", "critical_bin"),
)


class ConfigError(Exception):
    pass


def threshold_number(cfg: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[float]:
    """
    The number at `keys`, or None when it is absent or not numeric.

    None is what the gates read: it becomes NO_RX_LOW_THRESHOLD /
    NO_FDR_THRESHOLD, so the dependent checker is skipped rather than run
    against a default nobody chose.
    """
    node: Any = cfg
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return to_float(node)


def validate_thresholds(cfg: Dict[str, Any]) -> List[str]:
    """Describe every required key that is missing or not a number."""
    problems: List[str] = []
    for keys in REQUIRED_NUMERIC_KEYS:
        if threshold_number(cfg, keys) is None:
            problems.append("missing_or_invalid:%s" % ".".join(keys))
    return problems


def load_thresholds(path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load the threshold file -- the only source of thresholds.

    path is --thresholds when it was given, otherwise the per-hwsku
    default. File missing, unreadable, not JSON or not an object raises
    ConfigError so the caller exits 2 and monit alerts. Individual keys are
    validated by validate_thresholds(): they must not stop the round,
    because the other checks are still worth running.
    """
    source = path or DEFAULT_THRESHOLD_PATH
    if not os.path.isfile(source):
        raise ConfigError("file_not_found:%s" % source)
    try:
        with open(source, "r") as f:
            cfg = json.load(f)
    except (OSError, ValueError) as e:
        raise ConfigError("cannot_load:%s:%s" % (source, e))
    if not isinstance(cfg, dict):
        raise ConfigError("not_an_object:%s" % source)
    return cfg


# ---------------------------------------------------------------------------
# Database access (read-only)
# ---------------------------------------------------------------------------
class DbAccess:
    """
    Minimal wrapper over swsscommon.

    Every read method returns empty data on failure instead of raising: a
    single unreadable table must not abort the round (NFR-2). Connection
    failures are recorded in `self.failed` so the self-check can turn a
    total DB outage into exit code 2.

    The only table this program writes is STATE_DB.PORT_HEALTH, which
    holds its own result snapshot; every table it judges stays read-only.
    """

    def __init__(self, log: "MonitorLogger"):
        self.log = log
        self._conns: Dict[Tuple[str, str], Any] = {}
        self._tables: Dict[Tuple[str, str, str], Any] = {}
        self._rows_cache: Dict[Tuple[str, str, str], Dict[str, Dict[str, str]]] = {}
        self.failed = False

    @staticmethod
    def _swss():
        from swsscommon import swsscommon
        return swsscommon

    def connect(self, db_name: str, namespace: str = "") -> Optional[Any]:
        key = (db_name, namespace or "")
        if key in self._conns:
            return self._conns[key]
        conn = None
        try:
            from sonic_py_common import daemon_base
            conn = daemon_base.db_connect(db_name, namespace or "")
        except Exception:
            try:
                swsscommon = self._swss()
                conn = swsscommon.DBConnector(db_name, 0, True)
            except Exception as e:
                self.log.debug("connect %s/%s failed: %s" % (db_name, namespace, e))
        if conn is None:
            self.failed = True
            return None
        self._conns[key] = conn
        return conn

    def table(self, db_name: str, table_name: str, namespace: str = "") -> Optional[Any]:
        key = (db_name, table_name, namespace or "")
        if key in self._tables:
            return self._tables[key]
        conn = self.connect(db_name, namespace)
        if conn is None:
            return None
        try:
            tbl = self._swss().Table(conn, table_name)
        except Exception as e:
            self.log.debug("open %s failed: %s" % (table_name, e))
            return None
        self._tables[key] = tbl
        return tbl

    def get_all(self, db_name: str, table_name: str,
                namespace: str = "") -> Dict[str, Dict[str, str]]:
        key = (db_name, table_name, namespace or "")
        if key in self._rows_cache:
            return self._rows_cache[key]
        tbl = self.table(db_name, table_name, namespace)
        if tbl is None:
            return {}
        out: Dict[str, Dict[str, str]] = {}
        try:
            keys = tbl.getKeys()
        except Exception as e:
            self.log.debug("getKeys %s failed: %s" % (table_name, e))
            return {}
        for k in keys:
            try:
                found, field_pairs = tbl.get(k)
            except Exception:
                continue
            if found:
                # fvs is a list of (field, value) tuples; dict() turns it
                # into the plain mapping the rest of the code expects.
                out[k] = dict(field_pairs)
        self._rows_cache[key] = out
        return out

    def get_one(self, db_name: str, table_name: str, key: str,
                namespace: str = "") -> Dict[str, str]:
        tbl = self.table(db_name, table_name, namespace)
        if tbl is None:
            return {}
        try:
            found, field_pairs = tbl.get(key)
        except Exception:
            return {}
        if not found:
            return {}
        row: Dict[str, str] = {}
        for field_name, field_value in field_pairs:
            row[field_name] = field_value
        return row

    def has_rows(self, db_name: str, table_name: str, namespace: str = "") -> bool:
        return bool(self.get_all(db_name, table_name, namespace))

    def portname_to_oid_map(self, namespace: str = "") -> Dict[str, str]:
        """
        COUNTERS_PORT_NAME_MAP: port -> OID.

        SONiC stores this as one hash with an empty key holding port->oid
        fields, but a few builds store one row per port instead. Support both.
        """
        flat = self.get_one(DB_COUNTERS, T_COUNTERS_NAME_MAP, "", namespace)
        if flat:
            mapped: Dict[str, str] = {}
            for port, oid in flat.items():
                if oid:
                    mapped[port] = oid
            return mapped
        out: Dict[str, str] = {}
        for port, field_pairs in self.get_all(DB_COUNTERS, T_COUNTERS_NAME_MAP, namespace).items():
            if "oid" in field_pairs:
                out[port] = field_pairs["oid"]
            elif len(field_pairs) == 1:
                out[port] = list(field_pairs.values())[0]
        return out

    def reset(self) -> None:
        self._conns.clear()
        self._tables.clear()
        self._rows_cache.clear()

    def write_row(self, db_name: str, table_name: str, key: str,
                  fields: Dict[str, Any], namespace: str = "") -> bool:
        """
        Replace one row and report whether the write succeeded.

        swsscommon's Table.set() overwrites the whole hash (delete + HSET),
        so callers must pass every field they want to keep. A failed write
        is a warning, not an exception: losing the snapshot costs a couple
        of duplicate log lines, it must not fail the round.
        """
        tbl = self.table(db_name, table_name, namespace)
        if tbl is None:
            return False
        try:
            pairs = []
            for field_name, field_value in fields.items():
                pairs.append((field_name, str(field_value)))
            tbl.set(key, pairs)
            self._rows_cache.pop((db_name, table_name, namespace or ""), None)
            return True
        except Exception as e:
            self.log.warning("write %s/%s/%s failed: %s"
                             % (db_name, table_name, key, e))
            return False


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
class TruncatingFileHandler(logging.FileHandler):
    """
    One file, one ceiling: when the file reaches max_bytes it is emptied and
    writing continues from the top.

    Why not RotatingFileHandler: with backupCount=0 it does no rollover at
    all (doRollover only renames when backupCount > 0), so the file grows
    forever while looking configured; with backupCount>0 it leaves the old
    content behind as .1/.2, which means the steady-state footprint is
    max_bytes times the number of files, not max_bytes. What is wanted here
    is a single path whose size can be quoted as an upper bound, so the file
    clears itself instead.

    Why not logrotate: it needs a config file on the box, and in create mode
    it needs the writer to reopen the path -- a process that has held the
    descriptor since start would keep writing to the renamed inode and the
    space would not come back. This handler owns its own ceiling.

    What this costs: at the moment of truncation the whole history goes, not
    just the oldest part. That is why a marker line is written immediately
    after the truncate -- without it, a file that starts mid-story is
    indistinguishable from a service that was just restarted.
    """

    def __init__(self, filename: str, max_bytes: int = 0, mode: str = "a",
                 encoding: Optional[str] = None, delay: bool = False) -> None:
        self.max_bytes = int(max_bytes or 0)
        self.truncation_count = 0
        super().__init__(filename, mode, encoding, delay)

    def emit(self, record: logging.LogRecord) -> None:
        # Checked before every line rather than on a timer: a round writes
        # tens of lines at most, so the stat is noise, and checking first
        # means the file never goes over the limit by more than one batch.
        if self.max_bytes > 0 and self._size() >= self.max_bytes:
            self._truncate()
        super().emit(record)

    def _size(self) -> int:
        try:
            return os.path.getsize(self.baseFilename)
        except OSError:
            # Missing file is not an error to log about: the next write
            # recreates it, and a size that cannot be measured must not be
            # the reason a line is dropped.
            return 0

    def _truncate(self) -> None:
        previous = self._size()
        try:
            self.stream.flush()
            self.stream.seek(0)
            self.stream.truncate(0)
        except (OSError, ValueError):
            # A failed truncate leaves a file that is too big, not a program
            # that stops monitoring; say so in the marker and carry on.
            pass
        self.truncation_count += 1
        self.handle(self._marker_record(previous))

    def _marker_record(self, previous: int) -> logging.LogRecord:
        return logging.LogRecord(
            name="port_monitor.detail", level=logging.WARNING,
            pathname=__file__, lineno=0,
            msg=("PORT_CHECK: DETAIL_LOG_TRUNCATED SIZE_LIMIT=%d "
                 "PREVIOUS_BYTES=%d NOTE=\"earlier lines are gone, "
                 "the file was emptied on purpose\""
                 % (self.max_bytes, previous)),
            args=(), exc_info=None)


class MonitorLogger:
    """
    Two channels, one message.

    syslog carries the verdicts at the numeric level of the finding, so an
    alerting rule can simply count ERR lines. With per-round logging on
    (`PortMonitor.log_all`, the default) the line is written on every round
    the fault lasts -- same shape, same level, just more often, because
    there silence has to mean healthy. `--log-all false` narrows it back to
    one line per transition.
    The detail log carries the same verdict plus the gate ladder and the
    evidence that produced it, for whoever has to explain the verdict
    afterwards. Keeping them apart is what lets syslog stay readable on a
    128-port box without losing any of the reasoning.
    """

    def __init__(self, ident: str = SYSLOG_IDENTIFIER, level: str = "NOTICE",
                 use_syslog: bool = True,
                 detail_path: Optional[str] = DETAIL_LOG_PATH,
                 detail_max_bytes: int = DETAIL_LOG_MAX_BYTES):
        # Python has no NOTICE level. Register it and teach SysLogHandler its
        # priority, otherwise an unknown level name falls back to "warning"
        # and a PASS summary would look like a warning in syslog.
        logging.addLevelName(logging.INFO + 1, "NOTICE")
        logging.handlers.SysLogHandler.priority_map["NOTICE"] = "notice"

        self.logger = logging.getLogger(ident)
        self.logger.setLevel(self._level(level))
        self.logger.handlers = []
        self.logger.propagate = False

        fmt = logging.Formatter("%(name)s[%(process)d]: %(message)s")
        if use_syslog:
            try:
                h = logging.handlers.SysLogHandler(
                    address="/dev/log",
                    facility=logging.handlers.SysLogHandler.LOG_USER,
                    socktype=socket.SOCK_DGRAM)
                h.setFormatter(fmt)
                self.logger.addHandler(h)
            except (OSError, AttributeError):
                pass
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(self._detail_formatter())
        self.logger.addHandler(sh)

        # The detail channel is always at DEBUG: the gate lines that explain
        # a verdict are DEBUG by definition, and dropping them because the
        # operator ran with -m NOTICE would leave the file unable to answer
        # the only question it exists for.
        self.detail_logger = logging.getLogger(ident + ".detail")
        self.detail_logger.setLevel(logging.DEBUG)
        self.detail_logger.handlers = []
        self.detail_logger.propagate = False
        self.detail_path = ""
        if detail_path:
            try:
                dh = TruncatingFileHandler(detail_path,
                                           max_bytes=detail_max_bytes)
                dh.setFormatter(self._detail_formatter())
                self.detail_logger.addHandler(dh)
                self.detail_path = detail_path
            except OSError as e:
                self.warning("PORT_CHECK: cannot open detail log %s, "
                             "detail lines go to stderr only: %s"
                             % (detail_path, e))
        if not self.detail_logger.handlers:
            dh = logging.StreamHandler(sys.stderr)
            dh.setFormatter(self._detail_formatter())
            self.detail_logger.addHandler(dh)

    @staticmethod
    def _detail_formatter() -> logging.Formatter:
        """The timestamp shape the design document shows: 2026-10-30 06:05:00,255"""
        return logging.Formatter(
            "%(asctime)s,%(msecs)03d %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _level(name: str) -> int:
        return {
            "DEBUG": logging.DEBUG, "INFO": logging.INFO,
            "NOTICE": logging.INFO + 1, "WARNING": logging.WARNING,
            "ERROR": logging.ERROR, "CRIT": logging.CRITICAL,
        }.get(to_text(name).upper(), logging.INFO + 1)

    @staticmethod
    def _py_level(severity: Severity) -> int:
        # Map the eight severities onto Python's five logging levels.
        # The textual severity is always present in the message itself, so
        # no information is lost by this compression.
        if severity <= Severity.CRIT:
            return logging.CRITICAL
        if severity == Severity.ERR:
            return logging.ERROR
        if severity == Severity.WARNING:
            return logging.WARNING
        if severity == Severity.NOTICE:
            return logging.INFO + 1
        if severity == Severity.INFO:
            return logging.INFO
        return logging.DEBUG

    def log(self, severity: Severity, msg: str) -> None:
        """An operator-facing line: syslog and detail log, same level."""
        level = self._py_level(severity)
        self.logger.log(level, msg)
        self.detail_logger.log(level, msg)

    def to_syslog(self, severity: Severity, msg: str) -> None:
        """An operator-facing line that the detail log does not need twice."""
        self.logger.log(self._py_level(severity), msg)

    def detail(self, severity: Severity, msg: str) -> None:
        """A line that only belongs in the detail log."""
        self.detail_logger.log(self._py_level(severity), msg)

    def debug(self, msg: str) -> None:
        # Syslog gets DEBUG only when the operator asked for it; the detail
        # log always keeps it.
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.log(logging.DEBUG, msg)
        self.detail_logger.log(logging.DEBUG, msg)

    @staticmethod
    def gate_line(port: str, name: str, value: bool,
                  raw: Optional[bool]) -> str:
        """GATE L2 CPO_PORT_ADMIN_DOWN=false for Ethernet0 (raw=false)"""
        gate = canonical_gate(name)
        layer = GATE_LAYER.get(gate)
        return ("GATE L%s %s=%s for %s (raw=%s)"
                % (layer if layer is not None else "-", gate,
                   str(bool(value)).lower(), port,
                   "unknown" if raw is None else str(bool(raw)).lower()))

    def notice(self, msg: str) -> None:
        self.log(Severity.NOTICE, msg)

    def warning(self, msg: str) -> None:
        self.log(Severity.WARNING, msg)

    def error(self, msg: str) -> None:
        self.log(Severity.ERR, msg)

    def info(self, msg: str) -> None:
        self.log(Severity.INFO, msg)


# ---------------------------------------------------------------------------
# Per-port database view
# ---------------------------------------------------------------------------
class PortData:
    """
    Lazy, cached view of one port across the three databases.

    `thresholds` is the parsed JSON file and `portname_to_oid_map` the COUNTERS_DB
    port->OID map. Both describe the port, not the check, so they live
    here and every checker reads them from one place instead of taking
    extra arguments.

    A CPO port asks the same object three more questions (is_cpo, cpo_oe,
    cpo_els); a pluggable port never asks them and therefore never touches
    the CPO tables.
    """

    def __init__(self, port: str, namespace: str, db: DbAccess,
                 thresholds: Optional[Dict[str, Any]] = None,
                 portname_to_oid_map: Optional[Dict[str, str]] = None):
        self.port = port
        self.namespace = namespace
        self.db = db
        self.thresholds = thresholds or {}
        self.portname_to_oid_map = portname_to_oid_map or {}
        self._cache: Dict[str, Any] = {}

    def _row(self, db_name: str, table: str) -> Dict[str, str]:
        key = "row:%s:%s" % (db_name, table)
        if key not in self._cache:
            self._cache[key] = self.db.get_one(db_name, table, self.port, self.namespace)
        return self._cache[key]

    # --- raw rows -----------------------------------------------------------
    @property
    def port_config_info(self) -> Dict[str, str]:
        """CONFIG_DB.PORT: what the operator asked for."""
        return self._row(DB_CONFIG, T_PORT)

    @property
    def port_state_info(self) -> Dict[str, str]:
        """STATE_DB.PORT_TABLE: what the ASIC reports."""
        return self._row(DB_STATE, T_PORT_TABLE)

    @property
    def module_eeprom_info(self) -> Dict[str, str]:
        return self._row(DB_STATE, T_TRANSCEIVER_INFO)

    @property
    def module_dom_info(self) -> Dict[str, str]:
        return self._row(DB_STATE, T_TRANSCEIVER_DOM_SENSOR)

    @property
    def module_dom_threshold_info(self) -> Dict[str, str]:
        return self._row(DB_STATE, T_TRANSCEIVER_DOM_THRESHOLD)

    @property
    def module_dom_flags_info(self) -> Dict[str, str]:
        return self._row(DB_STATE, T_TRANSCEIVER_DOM_FLAG)

    @property
    def module_dom_flags_change_count(self) -> Dict[str, str]:
        return self._row(DB_STATE, T_TRANSCEIVER_DOM_FLAG_CHANGE_COUNT)

    @property
    def module_hw_status(self) -> Dict[str, str]:
        return self._row(DB_STATE, T_TRANSCEIVER_STATUS)

    @property
    def module_cmis_sw_status_info(self) -> Dict[str, str]:
        return self._row(DB_STATE, T_TRANSCEIVER_STATUS_SW)

    @property
    def module_status_flag_info(self) -> Dict[str, str]:
        return self._row(DB_STATE, T_TRANSCEIVER_STATUS_FLAG)

    @property
    def module_status_flag_change_count(self) -> Dict[str, str]:
        return self._row(DB_STATE, T_TRANSCEIVER_STATUS_FLAG_CHANG_COUNT)

    @property
    def port_sd_info(self) -> Dict[str, str]:
        oid = self.portname_to_oid_map.get(self.port)
        if not oid:
            return {}
        return self.db.get_one(DB_COUNTERS, "PORT_PHY_ATTR:%s" % oid, "", self.namespace,)

    def is_cpo_port(self) -> bool:
        if platform_chassis is None:
            return False
        try:
            index_text = first_field(self.port_config_info, "index")
            if not index_text:
                return False
            return platform_chassis.get_cpo(int(index_text)) is not None
        except (NotImplementedError, AttributeError, IndexError,
                TypeError, ValueError):
            return False

    @property
    def admin(self) -> str:
        return to_lower_text(first_field(self.port_config_info, "admin_status") or
                             first_field(self.port_state_info, "admin_status")
                             or "unknown")

    def oper_status(self) -> bool:
        return False if to_lower_text(first_field(self.port_state_info, "netdev_oper_status")) == "up" else True

    def admin_down_value(self) -> bool:
        """
        True unless both the configured and the applied admin state say up.

        CONFIG_DB is the intent, STATE_DB is what the ASIC actually has. A
        disagreement is treated as down: monitoring a port whose real state
        cannot be pinned down only produces noise.
        """
        wanted = to_lower_text(first_field(self.port_config_info, "admin_status"))
        applied = to_lower_text(first_field(self.port_state_info, "admin_status"))
        if wanted and applied and wanted != applied:
            return True
        return (wanted or applied) != "up"

    @property
    def cmis_state(self) -> str:
        return to_lower_text(first_field(self.module_cmis_sw_status_info, "cmis_state") or "")

    @property
    def els_cmis_state(self) -> str:
        return to_lower_text(first_field(self.module_status_flag_info, "els_module_low_power_state") or "")

    @property
    def module_state(self) -> str:
        return to_lower_text(first_field(self.module_hw_status, "module_state") or "")

    # --- derived predicates used by gates -----------------------------------
    def module_presence_value(self) -> Optional[bool]:
        if self.module_eeprom_info:
            return True
        return False

    def eeprom_unreadable_value(self) -> Optional[bool]:
        if not self.module_eeprom_info:
            return True if self.module_presence_value() is not False else False
        ident = to_lower_text(first_field(self.module_eeprom_info, "type", "type_abbrv_name"))
        if ident in ("n/a", "na", "unknown"):
            return True
        vendor = to_lower_text(
            first_field(self.module_eeprom_info, "manufacturer", "vendor_name"))
        model = to_lower_text(first_field(self.module_eeprom_info, "model"))
        serial = to_lower_text(first_field(self.module_eeprom_info, "serial"))
        blanks = ("", "n/a", "na", "0", "0x00")
        if all_in((vendor, model, serial), blanks):
            return True
        if all_in((vendor, model, serial), ("0x00", "0xff", "\x00", "\xff")):
            return True
        return False

    def copper_value(self) -> Optional[bool]:
        temperature = to_lower_text(first_field(self.module_dom_info, "temperature"))
        if temperature:
            if "N/A" in temperature or "n/a" in temperature:
                return True
            else:
                return False
        return True if self.module_presence_value() is not False else False

    def cmis_not_ready_value(self) -> Optional[bool]:
        state = self.cmis_state
        if not state:
            return True
        return state in ("failed", "unknown", "not ready", "not_ready")

    def dom_missing_value(self) -> Optional[bool]:
        if not self.module_dom_info:
            return True
        return not (self.lane_tx_rx_power_bias_info("tx", "power") or self.lane_tx_rx_power_bias_info("rx", "power") or
                    first_float_field(self.module_dom_info, "temperature") is not None)

    def threshold_missing_value(self) -> Optional[bool]:
        if not self.module_dom_threshold_info:
            return True
        # A threshold table with none of the DOM keys is as good as absent.
        for key in self.module_dom_threshold_info:
            if key.lower().startswith(("txpower", "rxpower", "temp", "vcc")):
                return False
        return True

    def fiber_absent_value(self) -> Optional[bool]:
        rx_los = self.lane_tx_rx_power_bias_temp_alarm_info(self.module_status_flag_info, "rx", "los")
        for lane, value in sorted(rx_los.items()):
            if value is False:
                return False
        return True

    def lane_tx_rx_power_bias_temp_alarm_info(
        self,
        module_flag_info: dict,
        direction: str,
        kind: str,
        flag_type: Optional[str] = None,
        variant: Optional[str] = None,
    ) -> Dict[int, bool]:
        """Parse lane-based or module-level flags."""

        out: Dict[int, bool] = {}

        kind = kind.lower()

        # Module-level flags have no lane number.
        if kind in ("temp", "vcc"):
            pattern = re.compile(
                r"^(temp|vcc)(HAlarm|LAlarm|HWarn|LWarn)$",
                re.IGNORECASE,
            )

            for key, value in module_flag_info.items():
                match = pattern.fullmatch(to_lower_text(key))
                if not match:
                    continue

                field_kind = match.group(1).lower()
                field_flag_type = match.group(2).lower()

                if field_kind != kind:
                    continue

                if flag_type is not None:
                    if field_flag_type != flag_type.lower():
                        continue

                flag = to_bool(value)
                if flag is not None:
                    out[0] = flag

            return out

        if kind in ("els_temp", "els_vcc"):
            pattern = re.compile(
                r"^(els_temp|els_vcc)(HAlarm|LAlarm|HWarn|LWarn)$",
                re.IGNORECASE,
            )

            for key, value in module_flag_info.items():
                match = pattern.fullmatch(to_lower_text(key))
                if not match:
                    continue

                field_kind = match.group(1).lower()
                field_flag_type = match.group(2).lower()

                if field_kind != kind:
                    continue

                if flag_type is not None:
                    if field_flag_type != flag_type.lower():
                        continue

                flag = to_bool(value)
                if flag is not None:
                    out[0] = flag

            return out

        patterns = {
            "power": r"^(rx|tx)(\d+)power(HAlarm|LAlarm|HWarn|LWarn)$",
            "bias": r"^(tx)(\d+)bias(HAlarm|LAlarm|HWarn|LWarn)$",
            "fault": r"^(tx)(\d+)fault$",
            "los": r"^(rx|tx)(\d+)los(?:_(hostlane))?$",
            "cdrlol": r"^(rx|tx)(\d+)cdrlol(?:_(hostlane))?$",
            "eq_fault": r"^(tx)(\d+)_eq_fault$",
        }

        pattern_text = patterns.get(kind)
        if pattern_text is None:
            return out

        pattern = re.compile(pattern_text, re.IGNORECASE)

        for key, value in module_flag_info.items():
            match = pattern.fullmatch(to_lower_text(key))
            if not match:
                continue

            field_direction = match.group(1).lower()
            lane = int(match.group(2))

            if field_direction != direction.lower():
                continue

            if kind in ("power", "bias"):
                field_flag_type = match.group(3).lower()
                if flag_type is not None:
                    if field_flag_type != flag_type.lower():
                        continue

            if kind in ("los", "cdrlol"):
                field_variant = match.group(3)
                field_variant = field_variant.lower() if field_variant else None

                if variant is not None and field_variant != variant.lower():
                    continue

            flag = to_bool(value)
            if flag is not None:
                out[lane] = flag

        return out

    POWER_RE = re.compile(r"^(rx|tx)(\d*)power$")
    BIAS_RE = re.compile(r"^tx(\d*)bias$")

    def lane_tx_rx_power_bias_info(self, direction: str, kind: str) -> Dict[int, float]:
        out = {}
        pattern = self.POWER_RE if kind == "power" else self.BIAS_RE

        for key, value in self.module_dom_info.items():
            m = pattern.fullmatch(key.lower())
            if not m:
                continue

            if kind == "power":
                field_direction = m.group(1).lower()
                lane = int(m.group(2) or 1)
                if field_direction != direction.lower():
                    continue
            else:
                lane = int(m.group(1) or 1)

            parsed = to_float(value)
            if parsed is not None:
                out[lane] = parsed

        return out

    def lane_attr(self, *names: str) -> Dict[int, bool]:
        """Read per-lane boolean attributes from PORT_PHY_ATTR."""

        out: Dict[int, bool] = {}
        wanted = {to_lower_text(name) for name in names}

        for key, value in self.port_sd_info.items():
            k = to_lower_text(key)

            if k not in wanted:
                continue

            # Parse JSON values such as:
            # {"0": ["F", 0, 0], "1": ["T", 0, 0]}
            try:
                data = json.loads(value) if isinstance(value, str) else value
            except (ValueError, TypeError):
                continue

            if not isinstance(data, dict):
                continue

            for lane_key, lane_value in data.items():
                try:
                    lane = int(lane_key)
                except (ValueError, TypeError):
                    continue

                # Extract the state from a list such as ["F", 0, 0].
                if isinstance(lane_value, list) and lane_value:
                    state = lane_value[0]
                else:
                    state = lane_value

                if isinstance(state, str):
                    state = state.strip().lower()
                    if state in ("t", "true", "1"):
                        out[lane] = True
                    elif state in ("f", "false", "0"):
                        out[lane] = False
                elif isinstance(state, bool):
                    out[lane] = state
                elif isinstance(state, int) and state in (0, 1):
                    out[lane] = bool(state)

        return out

    def lane_snr_vga_info(self, *names: str) -> Dict[int, float]:
        """
        Read per-lane numeric attributes from PORT_PHY_ATTR.

        VGA and SNR live here as well. They are recorded but not judged:
        hardware does not publish a bound, so they only appear as context
        in the evidence of a real finding.
        """
        out: Dict[int, float] = {}
        for key, value in self.port_sd_info.items():
            k = to_lower_text(key)
            for name in names:
                m = re.match(r"^(?:lane)?(\d+)?[_\-\s]?%s$" % re.escape(name), k)
                if not m:
                    m = re.match(r"^(?:%s)[_\-\s]?(\d+)$" % re.escape(name), k)
                if m:
                    lane = int(m.group(1)) if m.group(1) else 0
                    number = to_float(value)
                    if number is not None:
                        out[lane] = number
                    break
        return out

    def get_counters(self) -> Dict[str, str]:
        oid = self.portname_to_oid_map.get(self.port)
        if not oid:
            return {}

        return self.db.get_one(DB_COUNTERS, "COUNTERS:%s" % oid, "", self.namespace,)

    def get_counters_field(self, field: str) -> Optional[int]:
        value = self.get_counters().get(field)
        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def get_fdr_counters(self) -> Dict[str, str]:
        oid = self.portname_to_oid_map.get(self.port)
        if not oid:
            return {}

        return self.db.get_one(DB_COUNTERS, "RATES:%s" % oid, "", self.namespace,)

    def get_fdr_counters_field(self, field: str) -> Optional[int]:
        value = self.get_fdr_counters().get(field)
        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def has_counters_oid_value(self) -> Optional[bool]:
        if not self.portname_to_oid_map:
            return None
        return self.port in self.portname_to_oid_map

    def port_missing_signal_value(self) -> Optional[bool]:
        if not self.port_sd_info:
            return True
        parsed = self.lane_attr("phy_rx_signal_detect")
        return not parsed


def row_says_present(row: Optional[Dict[str, str]]) -> Optional[bool]:
    """
    The presence field of an OE / ELS row.

    None means "there is no such device for this port", which is not the
    same as absent: a port with no ELS row is not a port whose ELS is
    missing, so callers must test `is False`, never `not value`.
    """
    if not row:
        return None
    return to_bool(first_field(row, "presence", "present", "status"))


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------
@dataclass
class Finding:
    port: str
    code: str
    lanes: str = ""
    msg: str = ""
    evidence: str = ""

    @property
    def definition(self) -> IssueDef:
        return ISSUES[self.code]

    @property
    def severity(self) -> Severity:
        return ISSUES[self.code].severity


def sort_most_severe_first(findings: List[Finding]) -> List[Finding]:
    """Sort findings worst first; ties broken by code so order is stable."""
    def sort_key(finding: Finding) -> Tuple[int, str]:
        return int(finding.severity), finding.code

    ordered = sorted(findings, key=sort_key)
    return ordered


def most_severe_finding(findings: List[Finding]) -> Optional[Finding]:
    """
    The single most severe finding, or None when the list is empty.

    Defined as the head of `sort_most_severe_first` on purpose: a second "pick the
    worst" rule would have to repeat the tie-break, and any drift between
    the two would make the STATE_DB row disagree with the syslog line.
    """
    ordered = sort_most_severe_first(findings)
    if not ordered:
        return None
    return ordered[0]


def join_finding_codes(findings: List[Finding]) -> str:
    """The codes of `findings` joined in the order given; "" if empty."""
    codes = []
    for finding in findings:
        codes.append(finding.code)
    return ",".join(codes)


class FindingCollector:
    """
    Collects the findings of one port and merges them per code.

    A four-lane module with low power on every lane would otherwise produce
    four identical findings. Here they collapse into one, with the lanes
    turned into a bitmap.
    """

    def __init__(self, port: str):
        self.port = port
        self._items: Dict[str, Dict[str, Any]] = {}
        self._order: List[str] = []

    def add(self, code: str, lane: int = 0, msg: str = "",
            evidence_pairs: Optional[Sequence[Tuple[str, Any]]] = None,
            pairs: Optional[Sequence[Tuple[str, Any]]] = None) -> None:
        # `pairs` is accepted as a short alias so call sites stay readable.
        extra = pairs if pairs is not None else evidence_pairs
        entry = self._items.get(code)
        if entry is None:
            entry = {"lanes": set(), "msg": msg, "pairs": []}
            self._items[code] = entry
            self._order.append(code)

        entry["lanes"].add(lane)
        if msg and not entry["msg"]:
            entry["msg"] = msg
        if extra:
            entry["pairs"].extend(extra)

    def findings(self) -> List[Finding]:
        out = []
        for code in self._order:
            entry = self._items[code]
            out.append(Finding(port=self.port, code=code,
                               lanes=lane_mask(entry["lanes"]),
                               msg=entry["msg"] or ISSUES[code].summary,
                               evidence=evidence(entry["pairs"])))
        return out

    def __bool__(self) -> bool:
        return bool(self._items)


# ---------------------------------------------------------------------------
# Checkers
# ---------------------------------------------------------------------------
class Checker:
    """
    One check.

    `gates` is the list of skip conditions: if any of them fires, run() is
    never called. Read it the other way round -- `runs_when` -- and it
    becomes the precondition, e.g. module presence is
    checked only while the port is administratively up and is not a CPO
    port.
    """

    name = "checker"
    gates: Tuple[str, ...] = ()
    codes: Tuple[str, ...] = ()  # internal issue keys

    def run(self, port_data) -> List[Finding]:
        raise NotImplementedError

    @property
    def runs_when(self) -> str:
        """Positive form of `gates`: all of these must hold to run."""
        parts = []
        for gate_name in self.gates:
            parts.append(gate_run_condition(gate_name))
        if not parts:
            return "always"
        return " AND ".join(parts)

    @property
    def skipped_when(self) -> str:
        """Negative form of `gates`, as stored: any one of these skips it."""
        parts = []
        for gate_name in self.gates:
            parts.append(gate_skip_reason(gate_name))
        if not parts:
            return "never"
        return " OR ".join(parts)

    def _finding(self, port_data, code: str, lanes: Iterable[int] = (),
                 msg: str = "",
                 pairs: Optional[Sequence[Tuple[str, Any]]] = None) -> Finding:
        return Finding(port=port_data.port, code=code, lanes=lane_mask(lanes),
                       msg=msg or ISSUES[code].summary,
                       evidence=evidence(pairs or []))


class ELS_ModulePresenceChecker(Checker):
    name = "els_module_presence"
    codes = ("MODULE_PRESENCE_ABSENT", "ELS_MODULE_PRESENCE_ABSENT")

    def run(self, port_data) -> List[Finding]:
        if port_data.module_presence_value() is False:
            if port_data.is_cpo_port() is False:
                return [self._finding(port_data, "MODULE_PRESENCE_ABSENT", pairs=[("table", T_TRANSCEIVER_INFO)])]
            else:
                return [self._finding(port_data, "ELS_MODULE_PRESENCE_ABSENT", pairs=[("table", T_TRANSCEIVER_INFO)])]
        return []


class ELS_ModuleEepromChecker(Checker):
    name = "els_module_eeprom"
    gates = (G_ELS_MODULE_ABSENT,)
    codes = ("ELS_MODULE_EEPROM_BAD_ID",)

    BLANK = ("", "n/a", "na", "0x00", "0xff", "0", "\x00")

    def run(self, port_data) -> List[Finding]:
        info = port_data.module_eeprom_info
        findings = []
        vendor_pn = to_lower_text(first_field(info, "els_vendor_pn"))
        vendor_sn = to_lower_text(first_field(info, "els_vendor_sn"))
        vendor_oui = to_lower_text(first_field(info, "els_vendor_oui"))
        if all_in((vendor_pn, vendor_sn, vendor_oui), self.BLANK):
            findings.append(self._finding(port_data, "ELS_MODULE_EEPROM_BAD_ID",
                                          pairs=[("vendor_pn", vendor_pn), ("vendor_sn", vendor_sn),
                                                 ("vendor_oui", vendor_oui)]))
        return findings


class OE_ModuleEepromChecker(Checker):
    name = "oe_module_eeprom"
    gates = (G_ELS_MODULE_ABSENT,)
    codes = ("OE_MODULE_EEPROM_BAD_ID",)

    BLANK = ("", "n/a", "na", "0x00", "0xff", "0", "\x00")

    def run(self, port_data) -> List[Finding]:
        info = port_data.module_eeprom_info
        findings = []
        vendor = to_lower_text(first_field(info, "manufacturer", "vendor_oui"))
        model = to_lower_text(first_field(info, "model"))
        serial = to_lower_text(first_field(info, "serial"))
        if all_in((vendor, model, serial), self.BLANK):
            findings.append(self._finding(port_data, "OE_MODULE_EEPROM_BAD_ID",
                                          pairs=[("vendor", vendor), ("model", model),
                                                 ("serial", serial)]))
        return findings


class ELS_CmisStateChecker(Checker):
    name = "els_cmis_state"
    gates = (G_ELS_MODULE_ABSENT, G_CPO_PORT_ADMIN_DOWN)
    codes = ("ELS_CMIS_SW_NOT_READY",)
    READY_STATES = ("high power mode", "high power", "module ready")

    @staticmethod
    def normalize_state(value: Any) -> str:
        return " ".join(to_lower_text(value).replace("_", " ").split())

    def run(self, port_data) -> List[Finding]:
        acc = FindingCollector(port_data.port)
        state = self.normalize_state(port_data.els_cmis_state)
        if not state or state in ("unknown", "n/a", "na"):
            return []
        if state in self.READY_STATES:
            return []
        acc.add("ELS_CMIS_SW_NOT_READY",
                evidence_pairs=[("els_module_low_power_state", state)])
        return acc.findings()


class OE_CmisStateChecker(Checker):
    name = "oe_cmis_state"
    gates = (G_ELS_MODULE_ABSENT, G_CPO_PORT_ADMIN_DOWN)
    codes = ("OE_CMIS_SW_NOT_READY",)

    def run(self, port_data) -> List[Finding]:
        acc = FindingCollector(port_data.port)
        cmis = port_data.cmis_state
        if cmis == "failed":
            acc.add("OE_CMIS_SW_NOT_READY", evidence_pairs=[("oe_module_state_info", port_data.module_hw_status)])

        return acc.findings()


class OE_DomInfoChecker(Checker):
    """Reports the absence of DOM data; must run before the ELS_NO_DOM gate."""

    name = "oe_module_dom_info"
    gates = (G_CPO_PORT_ADMIN_DOWN, G_ELS_MODULE_ABSENT, G_CPO_CMIS_SM_NOT_READY)
    codes = ("OE_MODULE_NO_DOM_INFO", "OE_MODULE_NO_DOM_THRESHOLD")

    def run(self, port_data) -> List[Finding]:
        findings = []
        if port_data.dom_missing_value():
            findings.append(self._finding(port_data, "OE_MODULE_NO_DOM_INFO",
                            pairs=[("dom_info", port_data.module_dom_info)]))
        if port_data.threshold_missing_value():
            findings.append(self._finding(port_data, "OE_MODULE_NO_DOM_THRESHOLD", pairs=[
                            ("threshold_info", port_data.module_dom_threshold_info)]))
        return findings


class OE_DomTxInfoChecker(Checker):
    name = "oe_module_dom_tx"
    gates = (G_CPO_PORT_ADMIN_DOWN, G_ELS_MODULE_ABSENT, G_ELS_NO_DOM, G_ELS_NO_DOM_THRESHOLD, G_CPO_CMIS_SM_NOT_READY)
    codes = ("OE_MODULE_TX_POWER_LOW_ALARM", "OE_MODULE_TX_POWER_HIGH_ALARM",
             "OE_MODULE_TX_POWER_LOW_WARN", "OE_MODULE_TX_POWER_HIGH_WARN",
             "OE_MODULE_TX_BIAS_LOW_ALARM", "OE_MODULE_TX_BIAS_HIGH_ALARM",
             "OE_MODULE_TX_BIAS_LOW_WARN", "OE_MODULE_TX_BIAS_HIGH_WARN",
             "OE_MODULE_TX_FAULT", "OE_MODULE_TX_LOS")

    def run(self, port_data) -> List[Finding]:
        acc = FindingCollector(port_data.port)
        tx_power_high_alarm = port_data.lane_tx_rx_power_bias_temp_alarm_info(
            port_data.module_dom_flags_info, "tx", "power", "HAlarm")
        tx_power_low_alarm = port_data.lane_tx_rx_power_bias_temp_alarm_info(
            port_data.module_dom_flags_info, "tx", "power", "LAlarm")
        tx_power_high_warn = port_data.lane_tx_rx_power_bias_temp_alarm_info(
            port_data.module_dom_flags_info, "tx", "power", "HWarn")
        tx_power_low_warn = port_data.lane_tx_rx_power_bias_temp_alarm_info(
            port_data.module_dom_flags_info, "tx", "power", "LWarn")

        tx_bias_high_alarm = port_data.lane_tx_rx_power_bias_temp_alarm_info(
            port_data.module_dom_flags_info, "tx", "bias", "HAlarm")
        tx_bias_low_alarm = port_data.lane_tx_rx_power_bias_temp_alarm_info(
            port_data.module_dom_flags_info, "tx", "bias", "LAlarm")
        tx_bias_high_warn = port_data.lane_tx_rx_power_bias_temp_alarm_info(
            port_data.module_dom_flags_info, "tx", "bias", "HWarn")
        tx_bias_low_warn = port_data.lane_tx_rx_power_bias_temp_alarm_info(
            port_data.module_dom_flags_info, "tx", "bias", "LWarn")

        tx_fault = port_data.lane_tx_rx_power_bias_temp_alarm_info(port_data.module_status_flag_info, "tx", "fault")
        tx_los = port_data.lane_tx_rx_power_bias_temp_alarm_info(port_data.module_status_flag_info, "tx", "los")

        for lane, value in sorted(tx_power_low_alarm.items()):
            if value:
                acc.add("OE_MODULE_TX_POWER_LOW_ALARM", lane=(lane - 1), pairs=[("tx%dpowerLAlarm" % lane, value)])

        for lane, value in sorted(tx_power_high_alarm.items()):
            if value:
                acc.add("OE_MODULE_TX_POWER_HIGH_ALARM", lane=(lane - 1), pairs=[("tx%dpowerHAlarm" % lane, value)])

        for lane, value in sorted(tx_power_low_warn.items()):
            if value:
                acc.add("OE_MODULE_TX_POWER_LOW_WARN", lane=(lane - 1), pairs=[("tx%dpowerLWarn" % lane, value)])

        for lane, value in sorted(tx_power_high_warn.items()):
            if value:
                acc.add("OE_MODULE_TX_POWER_HIGH_WARN", lane=(lane - 1), pairs=[("tx%dpowerHWarn" % lane, value)])

        for lane, value in sorted(tx_bias_low_alarm.items()):
            if value:
                acc.add("OE_MODULE_TX_BIAS_LOW_ALARM", lane=(lane - 1), pairs=[("tx%dbiasLAlarm" % lane, value)])

        for lane, value in sorted(tx_bias_high_alarm.items()):
            if value:
                acc.add("OE_MODULE_TX_BIAS_HIGH_ALARM", lane=(lane - 1), pairs=[("tx%dbiasHAlarm" % lane, value)])

        for lane, value in sorted(tx_bias_low_warn.items()):
            if value:
                acc.add("OE_MODULE_TX_BIAS_LOW_WARN", lane=(lane - 1), pairs=[("tx%dbiasLWarn" % lane, value)])

        for lane, value in sorted(tx_bias_high_warn.items()):
            if value:
                acc.add("OE_MODULE_TX_BIAS_HIGH_WARN", lane=(lane - 1), pairs=[("tx%dbiasHWarn" % lane, value)])

        for lane, value in sorted(tx_fault.items()):
            if value:
                acc.add("OE_MODULE_TX_FAULT", lane=(lane - 1), pairs=[("tx%dfault" % lane, value)])

        for lane, value in sorted(tx_los.items()):
            if value:
                acc.add("OE_MODULE_TX_LOS", lane=(lane - 1), pairs=[("tx%dlos" % lane, value)])

        return acc.findings()


class OE_DomRxChecker(Checker):
    name = "oe_module_dom_rx"
    gates = (G_CPO_PORT_ADMIN_DOWN, G_ELS_MODULE_ABSENT, G_ELS_NO_DOM,
             G_CPO_FIBER_ABSENT, G_ELS_NO_DOM_THRESHOLD, G_CPO_CMIS_SM_NOT_READY)
    codes = ("OE_MODULE_RX_POWER_LOW_ALARM", "OE_MODULE_RX_POWER_HIGH_ALARM",
             "OE_MODULE_RX_POWER_LOW_WARN", "OE_MODULE_RX_POWER_HIGH_WARN",
             "OE_MODULE_RX_LOS")

    def run(self, port_data) -> List[Finding]:
        acc = FindingCollector(port_data.port)
        rx_power_high_alarm = port_data.lane_tx_rx_power_bias_temp_alarm_info(
            port_data.module_dom_flags_info, "rx", "power", "HAlarm")
        rx_power_low_alarm = port_data.lane_tx_rx_power_bias_temp_alarm_info(
            port_data.module_dom_flags_info, "rx", "power", "LAlarm")
        rx_power_high_warn = port_data.lane_tx_rx_power_bias_temp_alarm_info(
            port_data.module_dom_flags_info, "rx", "power", "HWarn")
        rx_power_low_warn = port_data.lane_tx_rx_power_bias_temp_alarm_info(
            port_data.module_dom_flags_info, "rx", "power", "LWarn")
        rx_los = port_data.lane_tx_rx_power_bias_temp_alarm_info(port_data.module_status_flag_info, "rx", "los")

        for lane, value in sorted(rx_power_low_alarm.items()):
            if value:
                acc.add("OE_MODULE_RX_POWER_LOW_ALARM", lane=(lane - 1), pairs=[("rx%dpowerLAlarm" % lane, value)])

        for lane, value in sorted(rx_power_high_alarm.items()):
            if value:
                acc.add("OE_MODULE_RX_POWER_HIGH_ALARM", lane=(lane - 1), pairs=[("rx%dpowerHAlarm" % lane, value)])

        for lane, value in sorted(rx_power_low_warn.items()):
            if value:
                acc.add("OE_MODULE_RX_POWER_LOW_WARN", lane=(lane - 1), pairs=[("rx%dpowerLWarn" % lane, value)])

        for lane, value in sorted(rx_power_high_warn.items()):
            if value:
                acc.add("OE_MODULE_RX_POWER_HIGH_WARN", lane=(lane - 1), pairs=[("rx%dpowerHWarn" % lane, value)])

        for lane, value in sorted(rx_los.items()):
            if value:
                acc.add("OE_MODULE_RX_LOS", lane=(lane - 1), pairs=[("rx%dlos" % lane, value)])

        return acc.findings()


class ELS_DomTempVoltChecker(Checker):
    """Temperature and voltage of a module on an enabled port."""

    name = "els_module_temp_voltage"
    gates = (G_CPO_PORT_ADMIN_DOWN, G_ELS_MODULE_ABSENT, G_ELS_NO_DOM, G_ELS_NO_DOM_THRESHOLD)
    codes = ("ELS_MODULE_TEMP_HIGH_ALARM", "ELS_MODULE_TEMP_LOW_ALARM",
             "ELS_MODULE_TEMP_HIGH_WARN", "ELS_MODULE_TEMP_LOW_WARN",
             "ELS_MODULE_VOLTAGE_HIGH_ALARM", "ELS_MODULE_VOLTAGE_LOW_ALARM",
             "ELS_MODULE_VOLTAGE_HIGH_WARN", "ELS_MODULE_VOLTAGE_LOW_WARN")

    def run(self, port_data) -> List[Finding]:
        findings = []
        # Temperature and voltage alarms
        module_alarms = [
            ("els_temp", "HAlarm", "ELS_MODULE_TEMP_HIGH_ALARM", "tempHAlarm"),
            ("els_temp", "LAlarm", "ELS_MODULE_TEMP_LOW_ALARM", "tempLAlarm"),
            ("els_temp", "HWarn", "ELS_MODULE_TEMP_HIGH_WARN", "tempHWarn"),
            ("els_temp", "LWarn", "ELS_MODULE_TEMP_LOW_WARN", "tempLWarn"),
            ("els_vcc", "HAlarm", "ELS_MODULE_VOLTAGE_HIGH_ALARM", "vccHAlarm"),
            ("els_vcc", "LAlarm", "ELS_MODULE_VOLTAGE_LOW_ALARM", "vccLAlarm"),
            ("els_vcc", "HWarn", "ELS_MODULE_VOLTAGE_HIGH_WARN", "vccHWarn"),
            ("els_vcc", "LWarn", "ELS_MODULE_VOLTAGE_LOW_WARN", "vccLWarn"),
        ]

        for kind, flag_type, finding_name, field_name in module_alarms:
            flags = port_data.lane_tx_rx_power_bias_temp_alarm_info(
                port_data.module_dom_flags_info, "", kind, flag_type,)
            value = flags.get(0)
            if value is True:
                findings.append(self._finding(port_data, finding_name, pairs=[(field_name, value)],))
        return findings


class OE_DomTempVoltChecker(Checker):
    """Temperature and voltage of a module on an enabled port."""

    name = "oe_module_temp_voltage"
    gates = (G_CPO_PORT_ADMIN_DOWN, G_ELS_MODULE_ABSENT, G_ELS_NO_DOM, G_ELS_NO_DOM_THRESHOLD)
    codes = ("OE_MODULE_TEMP_HIGH_ALARM", "OE_MODULE_TEMP_LOW_ALARM",
             "OE_MODULE_TEMP_HIGH_WARN", "OE_MODULE_TEMP_LOW_WARN",
             "OE_MODULE_VOLTAGE_HIGH_ALARM", "OE_MODULE_VOLTAGE_LOW_ALARM",
             "OE_MODULE_VOLTAGE_HIGH_WARN", "OE_MODULE_VOLTAGE_LOW_WARN")

    def run(self, port_data) -> List[Finding]:
        findings = []
        # Temperature and voltage alarms
        module_alarms = [
            ("temp", "HAlarm", "OE_MODULE_TEMP_HIGH_ALARM", "tempHAlarm"),
            ("temp", "LAlarm", "OE_MODULE_TEMP_LOW_ALARM", "tempLAlarm"),
            ("temp", "HWarn", "OE_MODULE_TEMP_HIGH_WARN", "tempHWarn"),
            ("temp", "LWarn", "OE_MODULE_TEMP_LOW_WARN", "tempLWarn"),
            ("vcc", "HAlarm", "OE_MODULE_VOLTAGE_HIGH_ALARM", "vccHAlarm"),
            ("vcc", "LAlarm", "OE_MODULE_VOLTAGE_LOW_ALARM", "vccLAlarm"),
            ("vcc", "HWarn", "OE_MODULE_VOLTAGE_HIGH_WARN", "vccHWarn"),
            ("vcc", "LWarn", "OE_MODULE_VOLTAGE_LOW_WARN", "vccLWarn"),
        ]

        for kind, flag_type, finding_name, field_name in module_alarms:
            flags = port_data.lane_tx_rx_power_bias_temp_alarm_info(
                port_data.module_dom_flags_info, "", kind, flag_type,)
            value = flags.get(0)
            if value is True:
                findings.append(self._finding(port_data, finding_name, pairs=[(field_name, value)],))
        return findings


class AsicSignalChecker(Checker):
    """
    SD / LOCK per lane from COUNTERS_DB.PORT_PHY_ATTR.

    A lane that lost signal detect or lock while the receiver has light is
    CRIT: the optics delivered photons and the electrical path did not
    recover them. SD and LOCK both high only proves the lane carries a
    basic signal -- neither says anything about quality, which is judged
    separately.

    VGA and SNR are copied into the evidence when there is a finding, but
    never compared: the hardware publishes no bound for them.

    RX_NO_LIGHT: with no light arriving, SD and LOCK are expected to be
    low. Reporting them would restate the optical fault as a SerDes fault,
    so the SD/LOCK judgement starts only once the receiver sees light.
    """

    name = "asic_serdes"
    gates = (G_CPO_PORT_ADMIN_DOWN, G_ELS_MODULE_ABSENT, G_CPO_FIBER_ABSENT,
             G_CPO_CMIS_SM_NOT_READY, G_CPO_NO_COUNTERS_OID)
    codes = ("ASIC_SIGNAL_ASSERT",)

    def run(self, port_data) -> List[Finding]:
        acc = FindingCollector(port_data.port)
        sd = port_data.lane_attr("phy_rx_signal_detect")
        lock = port_data.lane_attr("phy_rx_lock")
        sd_bad = set()
        for lane, value in sd.items():
            if value is False:
                sd_bad.add(lane)
        lock_bad = set()
        for lane, value in lock.items():
            if sd.get(lane) is True and value is False:
                lock_bad.add(lane)

        context = [("sd", self._fmt(sd)), ("lock", self._fmt(lock))]
        snr = port_data.lane_snr_vga_info("snr")
        vga = port_data.lane_snr_vga_info("vga")
        if snr:
            context.append(("snr", self._fmt_num(snr)))
        if vga:
            context.append(("vga", self._fmt_num(vga)))
        # The sd/lock dump covers the whole port, not one lane, so it is
        # attached once. Handing it to every bad lane repeated the same 56
        # characters per lane, filled the 1000 character evidence budget
        # with identical copies, and pushed the lock half out of the
        # truncated line -- the half that separates a SerDes fault from an
        # optical one.
        first = True
        for lane in sorted(sd_bad | lock_bad):
            extra = None
            if first:
                extra = context
                first = False
            acc.add("ASIC_SIGNAL_ASSERT", lane=lane,
                    msg="signal detect or lock is low",
                    evidence_pairs=extra)

        return acc.findings()

    @staticmethod
    def _fmt(values: Dict[int, bool]) -> str:
        parts = []
        for lane, value in sorted(values.items()):
            parts.append("%d:%d" % (lane, int(value)))
        return ",".join(parts)

    @staticmethod
    def _fmt_num(values: Dict[int, float]) -> str:
        parts = []
        for lane, value in sorted(values.items()):
            parts.append("%d:%g" % (lane, value))
        return ",".join(parts)


class SignalQualityChecker(Checker):
    name = "signal_quality"
    gates = (G_ELS_MODULE_ABSENT, G_CPO_PORT_ADMIN_DOWN, G_CPO_PORT_OPER_DOWN,
             G_CPO_NO_COUNTERS_OID, G_CPO_CMIS_SM_NOT_READY)
    codes = ("SIGNAL_WARNING",)
    FEC_NOT_CORRECTABLE_FIELD = ("SAI_PORT_STAT_IF_IN_FEC_NOT_CORRECTABLE_FRAMES")
    # A single sample can be a transient spike: the counter must be seen
    # growing in FEC_CONFIRM_ROUNDS consecutive reads, taken
    # FEC_CONFIRM_DELAY seconds apart, before an alarm is raised.
    FEC_CONFIRM_ROUNDS = 3
    FEC_CONFIRM_DELAY = 3.0

    def _get_previous_fec_count(self, port_data) -> Optional[int]:
        """Read the previous-round counter snapshot from STATE_DB."""
        row = port_data.db.get_one(
            DB_STATE,
            T_PORT_FEC_UNCOUNTERS,
            port_data.port,
            port_data.namespace,
        )

        if not row:
            return None

        value = row.get("fec_not_correctable")
        if value is None or value == "":
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _save_fec_count(self, port_data, value: int) -> bool:
        return port_data.db.write_row(
            DB_STATE,
            T_PORT_FEC_UNCOUNTERS,
            port_data.port,
            {"fec_not_correctable": value},
            port_data.namespace,
        )

    def _read_fec_count(self, port_data) -> Optional[int]:
        """Read the live counter once and normalize it to an int."""
        value = port_data.get_counters_field(self.FEC_NOT_CORRECTABLE_FIELD)
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _confirm_consecutive_growth(self, port_data, first_count: int):
        """Re-read the counter until the growth chain confirms or breaks.

        ``first_count`` is the first read of this round: either the first
        observation of the port (no baseline yet) or a read already known
        to be greater than the persisted baseline. Each further read is taken
        FEC_CONFIRM_DELAY seconds later and must be strictly greater than
        the previous read; the first read that is missing, unparseable or
        not growing breaks the chain.

        Returns ``(confirmed, last_count)``: ``confirmed`` is True only when
        the counter grew in FEC_CONFIRM_ROUNDS consecutive reads;
        ``last_count`` is the most recent observation either way, so the
        caller can persist it as the baseline for the next round.
        """
        last_count = first_count
        confirmed = True
        for round_no in range(2, self.FEC_CONFIRM_ROUNDS + 1):
            time.sleep(self.FEC_CONFIRM_DELAY)
            current = self._read_fec_count(port_data)
            if current is None or current <= last_count:
                confirmed = False
                break
            last_count = current
        return confirmed, last_count

    def run(self, port_data) -> List[Finding]:
        # The FDR bin is a threshold-derived sub-check: without
        # fdr.critical_bin the FDR comparison is dropped, only the
        # counter-growth half below runs.
        fdr_bin = threshold_number(port_data.thresholds, ("fdr", "critical_bin"))
        fec_correctable = port_data.get_counters_field("SAI_PORT_STAT_IF_IN_FEC_CORRECTABLE_FRAMES")
        fec_symbol_errors = port_data.get_counters_field("SAI_PORT_STAT_IF_IN_FEC_SYMBOL_ERRORS")
        fdr_bin_data = None
        if fdr_bin is not None:
            fdr_bin_data = port_data.get_fdr_counters_field(
                "SAI_PORT_STAT_IF_IN_FEC_CODEWORD_ERRORS_S%d_last" % int(fdr_bin))

        # First read of this round. Do not compare or overwrite the
        # baseline if the counter is missing.
        current_count = self._read_fec_count(port_data)
        if current_count is None:
            return []

        # Read the previous-round snapshot before updating it.
        previous_count = self._get_previous_fec_count(port_data)

        # A decreasing counter may indicate a counter reset or wraparound.
        # Refresh the baseline without treating it as a new fault.
        if previous_count is not None and current_count < previous_count:
            self._save_fec_count(port_data, current_count)
            return []

        # Same as the persisted baseline: no growth, nothing to report and
        # nothing to persist.
        if previous_count is not None and current_count == previous_count:
            return []

        # First observation (no baseline yet) and growth against the
        # baseline follow the same path: confirm the increase with
        # FEC_CONFIRM_ROUNDS consecutive reads spaced FEC_CONFIRM_DELAY
        # seconds apart; any read that stops growing breaks the chain.
        confirmed, confirmed_count = self._confirm_consecutive_growth(port_data, current_count)

        # Persist the latest observed value for the next round. When the
        # chain broke this also absorbs the partial growth, so a
        # one-step increase that never repeats does not re-arm the check.
        self._save_fec_count(port_data, confirmed_count)

        if not confirmed:
            return []

        previous_text = ("%d" % previous_count if previous_count is not None
                         else "n/a(first observation)")

        return [self._finding(port_data, "SIGNAL_WARNING",
                msg="Uncorrectable FEC codewords kept growing in %d consecutive reads"
                              % self.FEC_CONFIRM_ROUNDS,
                pairs=[
                    ("fec_symbol_errors", "%s" % fec_symbol_errors),
                    ("fec_correctable", "%s" % fec_correctable),
                    ("previous uncorrectable", previous_text),
                    ("first read", "%d" % current_count),
                    ("confirmed uncorrectable", "%d" % confirmed_count),
                    ("new uncorrectable", "%d" % (confirmed_count - current_count)),
                    ("confirm rounds", "%d x %.0fs" % (self.FEC_CONFIRM_ROUNDS,
                                                       self.FEC_CONFIRM_DELAY)),
                    ("fdr_bin_data", "%s" % fdr_bin_data),
                ],
            )
        ]


class OE_FirmwareChecker(Checker):
    name = "module_firmware"
    gates = (G_ELS_MODULE_ABSENT, G_CPO_PORT_ADMIN_DOWN)
    codes = ("OE_MODULE_FW_FAULT",)

    def run(self, port_data) -> List[Finding]:
        status_flags = port_data.module_status_flag_info
        datapath_firmware_fault = to_bool(status_flags.get("datapath_firmware_fault"))
        module_firmware_fault = to_bool(status_flags.get("module_firmware_fault"))
        if datapath_firmware_fault or module_firmware_fault:
            return [
                self._finding(
                    port_data, "OE_MODULE_FW_FAULT",
                    pairs=[("datapath_firmware_fault", datapath_firmware_fault),
                           ("module_firmware_fault", module_firmware_fault)]
                )
            ]
        return []


ALL_CHECKERS: Tuple[Checker, ...] = (
    ELS_ModulePresenceChecker(),
    ELS_ModuleEepromChecker(),
    OE_ModuleEepromChecker(),
    ELS_CmisStateChecker(),
    OE_CmisStateChecker(),
    OE_DomInfoChecker(),
    OE_DomTxInfoChecker(),
    OE_DomRxChecker(),
    ELS_DomTempVoltChecker(),
    OE_DomTempVoltChecker(),
    AsicSignalChecker(),
    SignalQualityChecker(),
    OE_FirmwareChecker(),
)


# ---------------------------------------------------------------------------
# Reporting model
#
# There is deliberately no root-cause suppression. The design document gives a
# port exactly one verdict -- the most severe finding -- and lists every other
# code in `active_codes`, so a broken fiber and the RX alarms it causes are
# both reported, ordered severity-first.
#
# An earlier revision hid the symptoms behind their root cause. That table
# could never change the verdict (every code it suppressed already ranked
# below the root cause) and it made syslog's ACTIVE_CODE disagree with
# STATE_DB's active_codes. One rule, one output.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------
@dataclass
class PortResult:
    port: str
    namespace: str = ""
    findings: List[Finding] = field(default_factory=list)
    skipped: List[Tuple[str, str]] = field(default_factory=list)  # (checker, gate)
    gated: bool = False
    # Which gate stopped the whole port. "Gated" alone cannot tell a port
    # we chose not to judge (admin down) from a port we could not judge
    # (xcvrd dead), and those two need opposite treatment in the table.
    gated_by: str = ""
    device_key: str = ""
    device_ports: str = ""
    changed: bool = False
    first_seen: str = ""
    change_count: int = 0

    @property
    def worst(self) -> Optional[Severity]:
        """The most severe finding on the port; None when it is healthy."""
        worst = most_severe_finding(self.findings)
        if worst is None:
            return None
        return worst.severity

    @property
    def failed(self) -> bool:
        worst = self.worst
        return worst is not None and int(worst) <= FAIL_MAX


@dataclass
class RunResult:
    exit_code: int = 0
    result: str = "PASS"
    worst: Optional[Severity] = None
    ports: List[PortResult] = field(default_factory=list)
    duration_ms: int = 0
    data_unavailable: bool = False
    self_check_error: str = ""
    emitted: int = 0
    recovered: int = 0
    changed_ports: int = 0
    top_issues: List[str] = field(default_factory=list)


class SelfCheckError(Exception):
    pass


# ---------------------------------------------------------------------------
# Result snapshot in STATE_DB
# ---------------------------------------------------------------------------
class StateDbStore:
    """
    The last result per port, kept in STATE_DB.PORT_HEALTH.

    This table is the monitor's memory across rounds and restarts. Each
    round compares what it just collected with the stored row and does one
    of two things:

        different  -> rewrite the row, count the change
        identical  -> no write

    `change_count` therefore counts verdict changes, not rounds: a fault
    that has been sitting there for a day still reads count=1. What syslog
    says is decided elsewhere (`PortMonitor._log_port_result`): by default
    one line per change, with `--log-all` one line per round while the
    fault lasts. The store never has to know which of the two is running --
    it reports what moved, and the reporter decides how loud to be.

    The comparison covers the verdict -- severity, error code, the whole
    active code set, the lane mask -- plus `gated_by`, which says whether
    the monitor is judging the port at all. Measurements are deliberately
    not part of it -- a temperature drifting from 75.0 to 75.1 is the same
    fault, and must not re-log every cycle -- and they are not stored
    either, so there is no second copy to disagree with.
    """

    FINGERPRINT = ("severity", "error_code", "active_codes", "lane_mask",
                   "gated_by")

    # Exactly the fields the design document's HGETALL shows, plus
    # `gated_by`: `message`, `evidence` and `last_seen` are deliberately not
    # stored -- the detail log keeps the reasoning, and every extra field is
    # one more thing that can differ between two rounds that mean the same
    # thing.
    #
    # `gated_by` is stored because the table has to answer "why is this port
    # quiet" without the log. An empty value means the port is being judged;
    # a gate name means it is not, and `retained_codes` holds what was wrong
    # when judgement stopped. Neither field is ever read as a live fault:
    # `severity` is the only field consumers judge by, and freezing sets it
    # back to OK.
    ROW_FIELDS = ("error_code", "severity", "action", "lane_mask",
                  "active_codes", "first_seen", "change_count", "gated_by",
                  "retained_codes")

    def __init__(self, db: "DbAccess", log: "MonitorLogger"):
        self.db = db
        self.log = log
        self.rows: Dict[str, Dict[str, str]] = {}

    @staticmethod
    def row_key(port: str, namespace: str) -> str:
        return port if not namespace else "%s|%s" % (namespace, port)

    def load(self, namespaces: Iterable[str]) -> None:
        """Read the table once per namespace; one HGETALL, not one per port."""
        self.rows = {}
        for namespace in namespaces:
            rows = self.db.get_all(DB_STATE, T_PORT_HEALTH, namespace)
            for port, row in rows.items():
                self.rows[self.row_key(port, namespace)] = dict(row)

    @staticmethod
    def empty_state_row() -> Dict[str, str]:
        """The row a healthy port writes: every field present, all empty."""
        row: Dict[str, str] = {}
        row["error_code"] = ""
        row["severity"] = "OK"
        row["action"] = Action.NO_ACTION
        row["lane_mask"] = ""
        row["active_codes"] = ""
        row["first_seen"] = ""
        row["change_count"] = "0"
        row["gated_by"] = ""
        row["retained_codes"] = ""
        return row

    @staticmethod
    def build_state_row(port_result) -> Dict[str, str]:
        """
        Build one row with exactly the fields the design document lists.

        `error_code`, `severity`, `action` and `lane_mask` describe the most
        severe finding: that is the operator-facing conclusion. `active_codes`
        keeps every finding of the port, worst first, which is what the
        document's own HGETALL shows (error_code=ASIC_SIGNAL_ASSERT with
        MODULE_RX_* alarms still listed). The row therefore carries the whole
        picture while the verdict stays single.
        """
        ordered = sort_most_severe_first(port_result.findings)

        # A port with nothing to report still gets a full row: the table
        # records health, not only faults.
        row = StateDbStore.empty_state_row()
        if not ordered:
            return row

        worst = ordered[0]
        row["error_code"] = worst.code
        row["severity"] = worst.severity.name
        row["action"] = worst.definition.action
        row["lane_mask"] = worst.lanes
        row["active_codes"] = join_finding_codes(ordered)
        return row

    @classmethod
    def frozen_row(cls, old: Dict[str, str], gate: str) -> Dict[str, str]:
        """
        The row of a port we stopped judging: healthy verdict, kept history.

        A gate fires for one of two reasons and neither of them repairs
        anything: admin down is a decision about the port, and every other
        gate means the readings a checker needs are missing (no module, no
        DOM, counters not mapped, port not up). The lane that lost signal
        detect before the gate fired did not fix itself, so the codes are
        not thrown away.

        They are, however, moved out of the fields that carry the verdict.
        `severity`, `error_code`, `active_codes` and `lane_mask` describe
        what is happening *now*, and now nothing is being measured: a
        consumer reading those four would either raise a fault nobody can
        act on, or -- worse -- watch it disappear and conclude the port
        healed. So the verdict fields go back to their healthy values and
        the codes move to `retained_codes`, which nothing interprets as a
        live fault -- it is a note to whoever asks why the port went quiet.

        `first_seen` and `change_count` are carried over untouched: the
        episode is the same episode, paused.
        """
        row = cls.empty_state_row()
        row["gated_by"] = gate
        # A port that was healthy when the gate fired retains nothing, and
        # that is the normal case on a box where most ports are unlit: there
        # is no fault to keep, so the row says only "not being judged". A
        # port that was already frozen has its codes in `retained_codes`
        # rather than `active_codes`, so both are read, and `error_code` is
        # the last resort for a row written by an older build.
        retained = old.get("active_codes") or old.get("retained_codes")
        if not retained:
            retained = old.get("error_code", "")
        row["retained_codes"] = retained
        row["first_seen"] = old.get("first_seen", "")
        row["change_count"] = old.get("change_count", "") or "0"
        return row

    @staticmethod
    def active_codes_of(row: Dict[str, str]) -> Set[str]:
        """The active_codes field split back into a set; a missing row is empty."""
        codes: Set[str] = set()
        for code in (row.get("active_codes") or "").split(","):
            if code:
                codes.add(code)
        return codes

    @staticmethod
    def retained_codes_of(row: Dict[str, str]) -> Set[str]:
        """
        The codes a frozen row kept aside; empty for a row under judgement.

        Frozen and live codes are added together wherever the question is
        "what was wrong with this port", so that a fault which existed
        before a shutdown and is gone after it still gets reported as
        recovered -- it cleared, we just did not watch it clear.
        """
        codes: Set[str] = set()
        for code in (row.get("retained_codes") or "").split(","):
            if code:
                codes.add(code)
        return codes

    @staticmethod
    def change_count_of(row: Dict[str, str]) -> int:
        """How many times the verdict changed so far; a fresh row counts 0."""
        try:
            return int(row.get("change_count") or 0)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def verdict_unchanged(cls, old: Dict[str, str], new: Dict[str, str]) -> bool:
        """
        True when the stored row already says what this round would say.

        The comparison is exactly the four verdict fields plus `gated_by`.
        Nothing else in the row is compared, and nothing else is stored, so
        "same fields" and "same row" cannot drift apart.

        `gated_by` is in there so that going quiet and staying quiet are
        different events: the round a port stops being judged writes once
        and logs once, and every round after it matches and says nothing.
        Without it, a gated port and a healthy port would be the same row,
        and the gate that explains the silence would be lost.
        """
        for field_name in cls.FINGERPRINT:
            if old.get(field_name, "") != new[field_name]:
                return False
        return True

    @staticmethod
    def change_result(changed: bool, first_seen: str, count: int,
                      recovered: List[str],
                      retained: str = "") -> Dict[str, Any]:
        """The answers run_once() and _log_port_result() need, one shape.

        `retained` is the code set the row holds right now. It only matters
        for a frozen port, where it is the list the operator is still on the
        hook for even though this round produced no findings.
        """
        return {"changed": changed, "first_seen": first_seen,
                "change_count": count, "recovered": recovered,
                "retained": retained}

    def record(self, port_result) -> Dict[str, Any]:
        """
        Compare this port with its stored row, persist only on change.

        The comparison key is the verdict, not the measurements: the same
        fields mean the row already says this, so nothing is written.
        `change_count` therefore counts verdict changes, not rounds -- there
        is no per-round write, whichever logging mode is running.

        Three cases, exactly as the design document states them:

        * unchanged  -- no write, change_count and first_seen kept;
        * changed    -- row rewritten, first_seen=now, change_count+1;
        * recovered  -- the codes that disappeared are reported, and a port
                        with no remaining fault is stored as healthy (OK).

        A fourth case sits before all three: a port the ladder did not judge.
        A fired gate removes the lights, the traffic or the readings, so a
        checker that only looked for faults would conclude that every fault
        cleared. It did not -- the monitor stopped looking, and that is not a
        repair. Such a port keeps the row it had, records `gated_by`, and is
        never reported as recovered.

        Returns {"changed", "first_seen", "change_count", "recovered"}; `recovered`
        lists the codes that were in the stored row and are gone now.
        """
        key = self.row_key(port_result.port, port_result.namespace)
        old = self.rows.get(key, {})
        new = self.build_state_row(port_result)

        # Step 0: a port that was not judged keeps the row it had, with the
        # gate recorded. Which gate it was does not matter: nothing was
        # measured, so nothing may be reported as repaired, and the table
        # has to be able to answer "why is this port quiet" on its own. The
        # global xcvrd gate never reaches here -- run_once() leaves the row
        # untouched for it, because then even the stored row cannot be
        # trusted to describe the same moment.
        if port_result.gated_by:
            new = self.frozen_row(old, port_result.gated_by)

        # Step 1: the verdict did not move, so the operator already has this
        # line. Nothing to write, nothing to log, and the counters stay put.
        # This is the normal case on a device whose faults are not changing.
        if self.verdict_unchanged(old, new):
            return self.change_result(changed=False,
                                      first_seen=old.get("first_seen", ""),
                                      count=self.change_count_of(old),
                                      recovered=[])

        # Step 2: the verdict moved. Work out what came back. "Wrong with
        # this port" means live codes plus frozen ones, so a fault that was
        # put on ice by a shutdown and is gone when judgement resumes is
        # still reported as recovered instead of vanishing silently.
        old_codes = self.active_codes_of(old) | self.retained_codes_of(old)
        new_codes = self.active_codes_of(new) | self.retained_codes_of(new)
        recovered = sorted(old_codes - new_codes)

        # A change starts a new episode: the row describes what is true now,
        # and the clock that matters for the operator is "since when does
        # the device look like this".
        first_seen = now_iso()
        if port_result.gated_by:
            # Nothing was measured this round, so there is no new episode
            # to date. The fault is as old as it was.
            previous = old.get("first_seen", "")
            if previous:
                first_seen = previous
        elif old.get("gated_by") and new.get("error_code"):
            # The port came back under judgement. If it came back carrying
            # the faults it had before it was shut down, then nothing
            # recovered while it was dark and the episode clock keeps
            # running -- restarting it would make an old fault look new.
            added = new_codes - old_codes
            if not added:
                previous = old.get("first_seen", "")
                if previous:
                    first_seen = previous
        count = self.change_count_of(old) + 1

        # Step 3: persist. The stored row is next round's memory, so it is
        # replaced only after the write succeeded; a failed write leaves the
        # old row in place and the change is retried next round (design doc
        # 6.5) -- an unpersisted result must not be remembered as saved.
        row = {name: new.get(name, "") for name in self.ROW_FIELDS}
        row["first_seen"] = first_seen
        row["change_count"] = str(count)
        written = self.db.write_row(DB_STATE, T_PORT_HEALTH, port_result.port,
                                    row, port_result.namespace)
        if written:
            self.rows[key] = row

        return self.change_result(changed=True, first_seen=first_seen,
                                  count=count, recovered=recovered,
                                  retained=new.get("retained_codes", ""))


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class PortMonitor:
    """One round of collection, gating, checking and reporting."""

    def __init__(self, thresholds: Dict[str, Any], log: MonitorLogger,
                 db: Optional[DbAccess] = None,
                 only_port: Optional[str] = None, verbose: bool = False,
                 # The CLI default is True (see build_parser); the class keeps
                 # False so a caller that constructs it directly has to say
                 # which repeat policy it wants instead of inheriting one.
                 log_all: bool = False):
        self.thresholds = thresholds
        self.log = log
        self.db = db or DbAccess(log)
        self.only_port = only_port
        self.verbose = verbose
        self.log_all = log_all
        self._started = time.time()
        self._stop = False
        self._reported_devices: set = set()

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def namespaces() -> List[str]:
        try:
            from sonic_py_common import multi_asic
            namespace = multi_asic.get_namespace_list()
            return namespace or [""]
        except Exception:
            return [""]

    def get_port_name(self, namespace: str) -> List[str]:
        cfg = self.db.get_all(DB_CONFIG, T_PORT, namespace)
        state = self.db.get_all(DB_STATE, T_PORT_TABLE, namespace)
        names = set()
        for port in list(cfg) + list(state):
            if port.startswith("Ethernet"):
                names.add(port)
        if self.only_port:
            wanted = set()
            for port in names:
                if port == self.only_port:
                    wanted.add(port)
            names = wanted
        return sorted(names, key=port_name_sort_key)

    # ---------------------------------------------------------------- gates
    def _collect_gate_flags(self, port_data,
                            global_gates: Dict[str, bool]) -> Tuple[Dict[str, bool], List[str]]:
        """
        Evaluate the ladder and return (gates, gate lines).

        The lines are returned rather than logged because they are only
        written for a port that ends up with a finding: the detail log is a
        record of what went wrong, and 128 healthy ports worth of
        "GATE ...=false" would bury that. The caller flushes them right
        before the verdict line, which is the order the design document
        shows.

        Two gates short-circuit the ladder: a shut-down port and an absent
        ELS make every gate below them meaningless, so they are not even
        read -- which is also why the log stops there instead of listing
        gates nobody evaluated.
        """
        g = dict(global_gates)
        lines: List[str] = []

        def put(name: str, value: Optional[bool]) -> None:
            g[name] = bool(value)
            lines.append(self.log.gate_line(port_data.port, name, bool(value), value))

        put(G_CPO_PORT_ADMIN_DOWN, port_data.admin_down_value())
        if g[G_CPO_PORT_ADMIN_DOWN]:
            return g, lines

        present = port_data.module_presence_value()
        put(G_ELS_MODULE_ABSENT, present is False)
        if g[G_ELS_MODULE_ABSENT]:
            return g, lines

        put(G_CPO_CMIS_SM_NOT_READY, port_data.cmis_not_ready_value())
        put(G_CPO_FIBER_ABSENT, port_data.fiber_absent_value())
        put(G_CPO_PORT_OPER_DOWN, port_data.oper_status())
        put(G_ELS_NO_DOM, port_data.dom_missing_value())
        put(G_ELS_NO_DOM_THRESHOLD, port_data.threshold_missing_value())
        put(G_CPO_NO_COUNTERS_OID, not port_data.has_counters_oid_value())

        # Configuration gate last: it says nothing about the port, only
        # about whether this build is allowed to judge it.
        put(G_NO_RX_LOW_THRESHOLD, threshold_number(self.thresholds, ("fiber", "rx_low_dbm")) is None)
        return g, lines

    # ---------------------------------------------------------------- round
    def run_once(self) -> RunResult:
        result = RunResult()
        try:
            self._self_check()
        except SelfCheckError as e:
            result.exit_code = 2
            result.result = "ERROR"
            result.self_check_error = str(e)
            self.log.error("PORT_CHECK: SELF_CHECK_FAILED REASON=%s." % e)
            return result

        global_gates = {G_XCVRD_STATUS: not xcvrd_is_running()}
        if global_gates[G_XCVRD_STATUS]:
            result.data_unavailable = True
            self.log.warning(
                "PORT_CHECK: XCVRD_NOT_RUNNING ACTION=CHECK_CONTAINER "
                "DETAIL=\"transceiver tables are frozen; every check is skipped "
                "this round and PORT_HEALTH is left untouched\".")

        total_checked = 0
        failed_ports = 0
        gated_ports = 0
        top_counter: Dict[str, int] = {}

        store = StateDbStore(self.db, self.log)
        store.load(self.namespaces())

        self._reported_devices = set()
        for namespace in self.namespaces():
            if self._stop:
                break
            # One COUNTERS_DB map for the whole namespace;
            port_oid = self.db.portname_to_oid_map(namespace)
            ports = self.get_port_name(namespace)
            for port in ports:
                if self._stop:
                    break
                total_checked += 1
                port_data = PortData(port, namespace, self.db, thresholds=self.thresholds, portname_to_oid_map=port_oid)
                gates, gate_lines = self._collect_gate_flags(port_data, global_gates)
                plan, skipped = self._choose_checkers(gates)
                if not plan:
                    gated_ports += 1
                if self.verbose and skipped:
                    self._log_skipped_checkers(port_data, gates, skipped)
                findings: List[Finding] = []
                for checker in plan:
                    try:
                        findings.extend(checker.run(port_data) or [])
                    except Exception as e:
                        # NFR-2: one checker must never take down the round.
                        # The failure is recorded and the next checker runs.
                        self.log.error('PORT_CHECK: PORT=%s CHECKER_FAILED CHECKER=%s ERROR="%s"'
                                       % (port, checker.name, e))
                # Which gate silenced the whole port. Every skipped entry
                # names the same gate in that case, so the first one is it.
                gated_by = ""
                if not plan and skipped:
                    gated_by = skipped[0][1]
                port_result = PortResult(port=port, namespace=namespace, findings=findings,
                                         skipped=skipped, gated=not plan, gated_by=gated_by)
                if result.data_unavailable:
                    # xcvrd is not refreshing the TRANSCEIVER_* tables, so
                    # this round carries no evidence. Recording "healthy"
                    # here would erase a real fault and log a recovery that
                    # was never observed, so the memory is left untouched.
                    state = {"changed": False, "first_seen": "", "change_count": 0,
                             "recovered": []}
                else:
                    state = store.record(port_result)
                port_result.changed = bool(state["changed"])
                port_result.first_seen = state.get("first_seen", "")
                port_result.change_count = int(state.get("change_count") or 0)
                if port_result.changed:
                    result.changed_ports += 1
                result.ports.append(port_result)

                if port_result.failed:
                    failed_ports += 1
                for finding in port_result.findings:
                    top_counter[finding.code] = top_counter.get(finding.code, 0) + 1

                # Every port goes through the reporting path, including a
                # healthy or gated one: that is where a recovery is logged.
                self._log_port_result(port_result, result, state, gate_lines)

        result.duration_ms = int((time.time() - self._started) * 1000)
        result.worst = self._most_severe_of_ports(result.ports)
        if result.self_check_error:
            result.exit_code = 2
            result.result = "ERROR"
        elif failed_ports:
            result.exit_code = 1
            result.result = "FAIL"
        else:
            result.exit_code = 0
            result.result = "PASS"
        # Rank the codes: most frequent first, ties broken by the code name
        # so the same input always prints the same three lines.

        def rank_key(code: str) -> Tuple[int, str]:
            return -top_counter[code], code

        ranked = sorted(top_counter, key=rank_key)
        result.top_issues = []
        for code in ranked[:3]:
            result.top_issues.append(ISSUES[code].summary)
        # The summary is what proves the monitor ran, so it is written every
        # round; the run detail behind it stays in the detail log.
        self._log_summary(result, total_checked, failed_ports, gated_ports)
        return result

    # ---------------------------------------------------------------- self-check
    def _self_check(self) -> None:
        conn = self.db.connect(DB_CONFIG)
        if conn is None:
            raise SelfCheckError("db_unreachable")
        if not self.db.has_rows(DB_CONFIG, T_PORT):
            # Not fatal: some platforms only populate STATE_DB. But if both
            # are empty the program has nothing to work on.
            if not self.db.has_rows(DB_STATE, T_PORT_TABLE):
                raise SelfCheckError("no_port_inventory")

    def _choose_checkers(self, gates: Dict[str, bool]) -> Tuple[List[Checker], List[Tuple[str, str]]]:
        """
        Turn gate values into the list of checks that may run for this port.

        A checker runs only when none of its gates fired. ModulePresenceChecker
        lists CPO_PORT_ADMIN_DOWN as well even though the branch below already
        covers it: keeping it in the class makes `runs_when` (and
        --list-checks) tell the truth for that class in isolation.
        """
        plan: List[Checker] = []
        skipped: List[Tuple[str, str]] = []
        if gate_is_set(G_XCVRD_STATUS, gates):
            return plan, self._skip_every_checker(G_XCVRD_STATUS)
        if gate_is_set(G_CPO_PORT_ADMIN_DOWN, gates):
            # Administration wins over every other consideration: a port
            # that is shut down is not checked at all, not even for presence
            # or temperature.
            return plan, self._skip_every_checker(G_CPO_PORT_ADMIN_DOWN)
        for checker in ALL_CHECKERS:
            blocker = topmost_fired_gate(checker.gates, gates)
            if blocker:
                skipped.append((checker.name, blocker))
            else:
                plan.append(checker)
        return plan, skipped

    @staticmethod
    def _skip_every_checker(gate: str) -> List[Tuple[str, str]]:
        """Every checker is skipped for the same reason; name it once each."""
        skipped: List[Tuple[str, str]] = []
        for checker in ALL_CHECKERS:
            skipped.append((checker.name, gate))
        return skipped

    # ---------------------------------------------------------------- output
    def _log_skipped_checkers(
        self,
        port_data,
        gates: Dict[str, bool],
        skipped: List[Tuple[str, str]],
    ) -> None:
        """Log each skipped checker with its actual blocking gate."""
        if not skipped:
            return

        active_gates = [
            gate_name
            for gate_name, fired in gates.items()
            if fired
        ]

        self.log.detail(
            Severity.DEBUG,
            "PORT_CHECK: PORT=%s ACTIVE_GATES=%s"
            % (
                port_data.port,
                join_or_dash(active_gates),
            )
        )

        for checker_name, gate_name in skipped:
            self.log.detail(
                Severity.DEBUG,
                "PORT_CHECK: PORT=%s CHECK=%s SKIPPED_BY=%s REASON=%s"
                % (
                    port_data.port,
                    checker_name,
                    gate_name,
                    gate_skip_reason(gate_name),
                )
            )

    def _log_port_result(self, port_result, result: RunResult,
                         state: Dict[str, Any],
                         gate_lines: Optional[List[str]] = None) -> None:
        """
        Report one port: on the round its verdict changed, or -- with
        `log_all` on -- every round it still has a finding.

        Two audiences, two formats:

        * syslog gets one short line that says what to do --
          PORT=Ethernet0 ERR_CODE=... ACTION=...
        * the detail log gets the gate ladder that led there, then the
          verdict with severity, lanes, evidence, first_seen and
          change_count.

        The stored row is what the operator was already told last round, so
        with repeats switched off an identical verdict would repeat nothing.
        `log_all` (the default) says the opposite on purpose: silence then
        has to mean healthy, and a fault that is still there is written
        again, in the same shape. Either way the two edges are announced
        once -- a code that left the row is reported as recovered, a port
        that stopped being judged as suspended.

        The gate lines are flushed only when the verdict moved, or when the
        operator asked for DEBUG. They explain a verdict; repeating the
        same thirteen lines every five minutes for a fault nobody has
        touched would bury the one line they belong to.
        """
        recovered = list(state.get("recovered") or [])
        changed = bool(state.get("changed"))

        # Nothing moved and the operator did not ask for a status line: the
        # quiet case, and the normal case on a box whose faults are stable.
        if not changed and not self.log_all:
            return

        # The ladder comes first: it is what the verdict line builds on, and
        # reading them in that order is what the design document shows.
        if self.log_all:
            flush_ladder = changed
        else:
            flush_ladder = bool(port_result.findings) or bool(recovered)
        if gate_lines and (flush_ladder or self.verbose):
            for line in gate_lines:
                self.log.detail(Severity.DEBUG, line)

        # A port the ladder did not judge is neither a recovery nor a new
        # verdict, and it is the one case the operator cannot infer from the
        # run: the port went quiet because a gate fired, not because it got
        # better. One line on the round the state flips; `gated_by` in the
        # stored row keeps it from repeating every cycle while the port stays
        # that way. A port that had nothing to suspend still gets the line
        # in the detail log only -- see _log_suspended() for why.
        if port_result.gated_by:
            if changed:
                self._log_suspended(port_result, state)
            return

        # What came back. A port whose faults all cleared has nothing else
        # to say this round, so this line is the whole story of a repair.
        # NOTICE, not INFO: the syslog threshold defaults to NOTICE, and the
        # one line the operator is waiting for must not be the one the
        # default level throws away.
        if recovered:
            self.log.detail(
                Severity.NOTICE,
                self._format_recovery_line(port_result, recovered))
            if not self.log_all:
                self.log.log(
                    Severity.NOTICE,
                    self._format_recovery_line(port_result, recovered))

            result.recovered += len(recovered)

        if not port_result.findings:
            return

        # The verdict. syslog gets the actionable line, the detail log gets
        # the same verdict with everything needed to explain it. In the
        # change-only mode this runs once per transition; with `log_all` it
        # runs every round, which is the whole point of the switch.
        worst = most_severe_finding(port_result.findings)
        self.log.to_syslog(worst.severity, self._format_brief_line(port_result, worst))
        self.log.detail(worst.severity, truncate(self._format_verdict_line(port_result, worst, state)))
        result.emitted += 1

    def _log_suspended(self, port_result, state: Dict[str, Any]) -> None:
        """
        PORT_CHECK: PORT=Ethernet0 ERR_CODE=MONITOR_SUSPENDED CAUSE=...

        Says the two things the run would otherwise leave ambiguous: the
        monitor stopped judging the port on purpose, and the codes it holds
        are retained rather than cleared. Without the second part a port
        that was shut down -- or whose module was pulled -- looks exactly
        like a port that was repaired, which is what used to be reported.

        Only a port that had something to suspend is worth a syslog line.
        A port that was healthy when the gate fired has no fault that the
        gate is hiding, and on a box where most ports are unlit that is the
        normal case: dozens of them, every time the table is first written,
        saying nothing. The row still records `gated_by`, which is what
        answers "why is this port quiet"; syslog would only add lines nobody
        acts on. Such a port gets a DEBUG line in the detail log instead,
        where the question "did it even look at this port" is asked.
        """
        cause = port_result.gated_by
        retained = state.get("retained", "")

        detail_parts = ["PORT_CHECK: PORT=%s" % port_result.port]
        if port_result.namespace:
            detail_parts.append("NS=%s" % port_result.namespace)
        detail_parts.append("STATE=MONITOR_SUSPENDED")
        detail_parts.append("CAUSE=%s" % cause)

        if not retained:
            detail_parts.append("RETAINED_CODE=-")
            detail_parts.append("ACTION=%s." % Action.NO_ACTION)
            self.log.detail(Severity.DEBUG, " ".join(detail_parts))
            return

        short_parts = ["PORT_CHECK: PORT=%s" % port_result.port]
        if port_result.namespace:
            short_parts.append("NS=%s" % port_result.namespace)
        short_parts.append("ERR_CODE=MONITOR_SUSPENDED")
        short_parts.append("CAUSE=%s" % cause)
        short_parts.append("ACTION=%s." % Action.NO_ACTION)
        if not self.log_all:
            self.log.log(Severity.NOTICE, " ".join(short_parts))
        self.log.detail(Severity.NOTICE, " ".join(short_parts))

        detail_parts.append("RETAINED_CODE=%s" % retained)
        first_seen = state.get("first_seen", "")
        if first_seen:
            detail_parts.append("SINCE=%s" % first_seen)
        detail_parts.append("CHANGE_COUNT=%d" % int(state.get("change_count") or 0))
        self.log.detail(Severity.NOTICE, truncate(" ".join(detail_parts)))

    @staticmethod
    def _format_recovery_line(port_result, codes: Sequence[str]) -> str:
        """PORT_CHECK: PORT=Ethernet0 ERR_CODE=ERR_CODE_RECOVERED ACTION=NO_ACTION"""
        parts = ["PORT_CHECK: PORT=%s" % port_result.port]
        parts.append("ERR_CODE=ERR_CODE_RECOVERED")
        parts.append("ACTION=%s" % Action.NO_ACTION)
        if port_result.namespace:
            parts.append("NS=%s" % port_result.namespace)
        parts.append("RECOVERED=%s" % ",".join(codes))
        return " ".join(parts)

    @staticmethod
    def _format_brief_line(port_result, finding: Finding) -> str:
        """PORT_CHECK: PORT=Ethernet0 ERR_CODE=... ACTION=CHECK_FIBER_ATTACHMENT."""
        parts = ["PORT_CHECK: PORT=%s" % port_result.port]
        if port_result.namespace:
            parts.append("NS=%s" % port_result.namespace)
        parts.append("ERR_CODE=%s" % finding.code)
        parts.append("ACTION=%s." % finding.definition.action)
        return " ".join(parts)

    @staticmethod
    def _join_active_codes(port_result) -> str:
        """
        Every finding of the port, worst first. The verdict names one code;
        this is the whole chain that led to it.
        """
        return join_finding_codes(sort_most_severe_first(port_result.findings))

    def _format_verdict_line(self, port_result, finding: Finding,
                             state: Dict[str, Any]) -> str:
        """
        PORT_CHECK: PORT=Ethernet0 SEVERITY=ERR ERR_CODE=... ACTION=...
                    LANES=0x01 ACTIVE_CODE=... MSG="..." EVIDENCE="..."
                    SINCE=... CHANGE_COUNT=1

        One line, upper-case keys, so the detail log can be parsed with the
        same field=value reader as syslog without a second grammar.
        """
        parts = ["PORT_CHECK: PORT=%s" % port_result.port]
        if port_result.namespace:
            parts.append("NS=%s" % port_result.namespace)
        parts.append("SEVERITY=%s" % finding.severity.name)
        parts.append("ERR_CODE=%s" % finding.code)
        parts.append("ACTION=%s" % finding.definition.action)
        if finding.lanes:
            parts.append("LANES=%s" % finding.lanes)
        if port_result.device_ports:
            parts.append("PORTS=%s" % port_result.device_ports.replace(" ", ""))
        active = self._join_active_codes(port_result)
        if active:
            parts.append("ACTIVE_CODE=%s" % active)
        parts.append('MSG="%s"' % finding.msg.replace('"', "'")[:200])
        chain = finding.evidence
        if chain:
            parts.append('EVIDENCE="%s"' % chain.replace('"', "'"))
        first_seen = state.get("first_seen", "")
        if first_seen:
            parts.append("SINCE=%s" % first_seen)
        parts.append("CHANGE_COUNT=%d" % int(state.get("change_count") or 0))
        return " ".join(parts)

    @staticmethod
    def _summary_severity(result: RunResult) -> Severity:
        if result.result == "FAIL":
            return Severity.WARNING
        if result.result in ("ERROR", "DATA_UNAVAILABLE"):
            return Severity.WARNING
        return Severity.NOTICE

    def _log_summary(self, result: RunResult, checked: int = 0,
                     failed: int = 0, gated: int = 0) -> None:
        """PORT_CHECK: SUMMARY RESULT=PASS."""
        self.log.log(self._summary_severity(result),
                     "PORT_CHECK: SUMMARY RESULT=%s." % result.result)
        worst = result.worst.name if result.worst is not None else "-"
        self.log.detail(Severity.INFO,
                        'PORT_CHECK: SUMMARY RESULT=%s EXIT=%d WORST=%s '
                        "PORTS_CHECKED=%d PORTS_FAILED=%d GATED_PORTS=%d "
                        "CHANGED_PORTS=%d RECOVERED=%d DATA_UNAVAILABLE=%s "
                        'TOP="%s" DURATION_MS=%d'
                        % (result.result, result.exit_code, worst, checked,
                           failed, gated, result.changed_ports,
                           result.recovered,
                           str(result.data_unavailable).lower(),
                           "; ".join(result.top_issues or ["-"]),
                           result.duration_ms))

    @staticmethod
    def _most_severe_of_ports(ports: List[PortResult]) -> Optional[Severity]:
        values = []
        for port_result in ports:
            if port_result.worst is not None:
                values.append(int(port_result.worst))
        if not values:
            return None
        return Severity(min(values))

    # ---------------------------------------------------------------- loop
    def request_stop(self, *_args) -> None:
        self._stop = True

    def run_forever(self, interval: int) -> int:
        self.log.notice("PORT_CHECK: START VERSION=%s MODE=interval INTERVAL=%ds "
                        "SOURCE=DB" % (VERSION, interval))
        code = 0
        while not self._stop:
            result = self.run_once()
            code = result.exit_code
            for _ in range(interval):
                if self._stop:
                    break
                time.sleep(1)
        self.log.notice("PORT_CHECK: STOP VERSION=%s" % VERSION)
        return code


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------
def finding_to_dict(finding: Finding) -> Dict[str, Any]:
    """
    One finding as a JSON object.

    There is no `suppressed` / `suppressed_by` pair: every finding is
    reported, so there is no second class of finding to describe. The design
    document's 12.3 sample still shows those two fields; that sample predates
    the removal of root-cause suppression and is the one part of it this
    output deliberately does not follow.
    """
    item: Dict[str, Any] = {}
    item["code"] = finding.code
    item["severity"] = finding.severity.name
    item["action"] = finding.definition.action
    item["lanes"] = finding.lanes
    item["message"] = finding.msg
    item["evidence"] = finding.evidence
    return item


def port_to_dict(port_result) -> Dict[str, Any]:
    """One port as a JSON object, with its findings and skipped checks."""
    severity_name = "OK"
    if port_result.worst:
        severity_name = port_result.worst.name

    active = []
    for finding in port_result.findings:
        active.append(finding_to_dict(finding))

    skipped = []
    for checker_name, gate_name in port_result.skipped:
        skipped.append({"checker": checker_name, "gate": gate_name})

    item: Dict[str, Any] = {}
    item["port"] = port_result.port
    item["namespace"] = port_result.namespace
    item["severity"] = severity_name
    item["failed"] = port_result.failed
    item["gated"] = port_result.gated
    item["gated_by"] = port_result.gated_by or None
    item["changed"] = port_result.changed
    item["first_seen"] = port_result.first_seen or None
    item["change_count"] = port_result.change_count
    item["active"] = active
    item["skipped"] = skipped
    return item


def result_to_dict(result: RunResult, checked: int = 0, failed: int = 0, gated: int = 0) -> Dict[str, Any]:
    worst_name = None
    if result.worst:
        worst_name = result.worst.name

    ports = []
    for port_result in result.ports:
        ports.append(port_to_dict(port_result))

    out: Dict[str, Any] = {}
    out["result"] = result.result
    out["exit_code"] = result.exit_code
    out["worst_severity"] = worst_name
    out["duration_ms"] = result.duration_ms
    out["data_unavailable"] = result.data_unavailable
    out["self_check_error"] = result.self_check_error or None
    out["ports_checked"] = checked
    out["ports_failed"] = failed
    out["gated_ports"] = gated
    out["changed_ports"] = result.changed_ports
    out["top_issues"] = result.top_issues
    out["ports"] = ports
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def gate_layer_key(name: str) -> Tuple[int, str]:
    """Order gates by layer, then by name, so the listing is stable."""
    return GATE_LAYER[name], name


def _arg_bool(text: str) -> bool:
    """Read a command-line boolean.

    `store_true` cannot express "on by default, off on request": it has no
    way to spell the off state at all. A string -> bool conversion plus
    `nargs="?"` can, and keeps `--log-all` alone meaning "on" so the flag
    reads the same way it always did.

    Words are matched case-insensitively, and an unrecognised value is an
    error rather than a silent default -- a monitor that quietly picks the
    wrong mode logs too little or too much without saying so.
    """
    lowered = text.strip().lower()
    if lowered in ("1", "true", "yes", "on"):
        return True
    if lowered in ("0", "false", "no", "off"):
        return False
    raise argparse.ArgumentTypeError(
        "expected true or false, got %r" % text)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="SONiC CPO port health monitor (DB-only, routeCheck style)")
    p.add_argument("--once", action="store_true",
                   help="run one round and exit (default)")
    p.add_argument("--interval", type=int, default=None,
                   help="run as a daemon with this poll interval")
    p.add_argument("--json", action="store_true",
                   help="print the round result as JSON on stdout")
    p.add_argument("--port", default=None,
                   help="only check this port (troubleshooting)")
    p.add_argument("--thresholds", default=None,
                   help="threshold JSON file (default: %s)" % DEFAULT_THRESHOLD_PATH)
    p.add_argument("--detail-log", default=DETAIL_LOG_PATH,
                   help="detailed log file (default: %s)" % DETAIL_LOG_PATH)
    p.add_argument("--no-detail-log", action="store_true",
                   help="do not write the detailed log; keep only syslog")
    p.add_argument("--detail-log-max-bytes", type=int,
                   default=DETAIL_LOG_MAX_BYTES,
                   help="empty the detail log once it reaches this many bytes "
                        "(default: %d, i.e. %d MiB); 0 means no cap"
                        % (DETAIL_LOG_MAX_BYTES,
                           DETAIL_LOG_MAX_BYTES // (1024 * 1024)))
    p.add_argument("-m", "--log-level", default="NOTICE",
                   choices=("DEBUG", "INFO", "NOTICE", "WARNING", "ERROR"))
    p.add_argument("--no-syslog", action="store_true",
                   help="stderr only, useful for tests and containers without /dev/log")
    p.add_argument("--log-all", nargs="?", const=True, default=True,
                   type=_arg_bool, metavar="{true,false}",
                   help="write a faulty port every round instead of only when "
                        "its verdict changes (default: true); "
                        "--log-all false keeps one line per change")
    p.add_argument("--list-checks", action="store_true",
                   help="print the check catalogue (what is checked, when it is skipped)")
    p.add_argument("--version", action="version", version="portmonitor %s" % VERSION)
    return p


def print_checks() -> int:
    """Print a readable check catalogue and its skip conditions."""

    print("=" * 76)
    print("Port Monitor Check Catalogue")
    print("=" * 76)
    print(f"Version        : {VERSION}")
    print(f"Thresholds     : {DEFAULT_THRESHOLD_PATH}")
    print(f"Result storage : STATE_DB.{T_PORT_HEALTH}")
    print(f"Verdicts       : syslog ({SYSLOG_IDENTIFIER})")
    print(f"Detail log     : {DETAIL_LOG_PATH}")
    print(f"Detail cap     : {DETAIL_LOG_MAX_BYTES // (1024 * 1024)} MiB, "
          f"then emptied in place (--detail-log-max-bytes)")
    print("Log mode       : a faulty port is written every round "
          "(--log-all false: only when its verdict changes)")
    print()
    print("Execution rules:")
    print("  - A check is skipped when ANY of its skip gates is active.")
    print("  - A check runs only when ALL of its skip gates are inactive.")
    print("  - The gate with the lowest layer that fired is the skip reason.")
    print("  - This catalogue lists possible skip gates, not their current state.")
    print()

    for index, checker in enumerate(ALL_CHECKERS, start=1):
        print("-" * 76)
        print(f"[{index}] {checker.name}")

        # Show the conditions under which the check can run.
        print("  Runs when:")
        for condition in checker.runs_when.split(" AND "):
            print(f"    - {condition}")

        # List each gate separately so the operator can identify
        # the exact condition that would cause the check to be skipped.
        print("  Skip gates (ANY active gate skips this check):")
        if not checker.gates:
            print("    None")
        else:
            for gate_name in checker.gates:
                reason = gate_skip_reason(gate_name)
                layer = GATE_LAYER.get(canonical_gate(gate_name))
                layer_text = f"L{layer}" if layer is not None else "--"
                print(
                    f"    [{layer_text:<2}] {canonical_gate(gate_name):<24} {reason}"
                )

        print("  Reports:")
        if not checker.codes:
            print("    None")
        else:
            for code in checker.codes:
                issue = ISSUES[code]
                status = "" if issue.implemented else " [NOT IMPLEMENTED]"
                print(
                    f"    {code:<30} "
                    f"{issue.severity.name:<9} "
                    f"{issue.action}{status}"
                )

        print()

    print("=" * 76)
    print("Gates by layer")
    print("=" * 76)
    for name in sorted(GATE_LAYER, key=gate_layer_key):
        scope = "round" if name == G_XCVRD_STATUS else "port"
        print(f"  L{GATE_LAYER[name]}  {name:<24} [{scope}] {gate_skip_reason(name)}")

    print()
    print("Note: For the actual skip reason of a port, read the GATE lines in")
    print(f"      {DETAIL_LOG_PATH}; this catalogue only describes possible gates.")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list_checks:
        return print_checks()
    # For now, use HWSKU for identification. Once the master branch is merged
    # into the 202608 branch, switch to using the hardware ID for identification.
    if device_hwsku() != "M2-W6940-64X1-FR4":
        return 0

    try:
        thresholds = load_thresholds(args.thresholds)
    except ConfigError as e:
        sys.stderr.write("PORT_CHECK: SELF_CHECK_FAILED REASON=config:%s\n" % e)
        return 2

    log = MonitorLogger(SYSLOG_IDENTIFIER, level=args.log_level,
                        use_syslog=not args.no_syslog,
                        detail_path=None if args.no_detail_log else args.detail_log,
                        detail_max_bytes=args.detail_log_max_bytes)
    log.detail(Severity.INFO,
               "PORT_CHECK: START VERSION=%s THRESHOLDS=%s DETAIL_LOG=%s"
               % (VERSION, args.thresholds or DEFAULT_THRESHOLD_PATH,
                  log.detail_path or "-"))
    # A missing key disables one sub-check, not the round. Say which ones,
    # once, so "the fiber check never fires" has a written reason.
    for problem in validate_thresholds(thresholds):
        log.warning("PORT_CHECK: THRESHOLD_INVALID %s, the dependent check "
                    "is skipped this round." % problem)
    if "bootup_silence_sec" in thresholds:
        # Left over from 2.0.x on already-deployed devices: say so once
        # instead of silently ignoring a setting the operator still trusts.
        log.notice("PORT_CHECK: bootup_silence_sec is ignored: the monitor no "
                   "longer silences itself after boot")

    monitor = PortMonitor(thresholds, log, only_port=args.port,
                          verbose=args.log_level == "DEBUG",
                          log_all=args.log_all)
    if args.log_all:
        # Say which mode is running, once. The two modes look identical on a
        # quiet box and completely different on a broken one, and the first
        # question about either log is "why so many lines" or "why so few".
        log.detail(Severity.NOTICE, "PORT_CHECK: LOG_MODE=all a faulty port is written every "
                   "round, not only when its code changes")
    else:
        log.detail(Severity.NOTICE, "PORT_CHECK: LOG_MODE=changes a faulty port is written "
                   "only when its code changes")

    try:
        if args.interval:
            signal.signal(signal.SIGTERM, monitor.request_stop)
            signal.signal(signal.SIGINT, monitor.request_stop)
            return monitor.run_forever(max(2, args.interval))

        result = monitor.run_once()
        if args.json:
            checked = len(result.ports)
            failed = 0
            gated = 0
            for port_result in result.ports:
                if port_result.failed:
                    failed += 1
                if port_result.gated:
                    gated += 1
            if result.ports:
                sys.stdout.write(json.dumps(result_to_dict(result, checked, failed, gated),
                                            ensure_ascii=False, indent=2) + "\n")
        return result.exit_code
    except SelfCheckError as e:
        log.error("PORT_CHECK: SELF_CHECK_FAILED REASON=%s." % e)
        return 2


if __name__ == "__main__":
    sys.exit(main())

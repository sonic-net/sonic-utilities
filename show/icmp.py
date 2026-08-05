#!/usr/bin/env python3

import click
import utilities_common.cli as clicommon
import datetime
import json
import os
import socket

from swsscommon.swsscommon import SonicV2Connector
from sonic_py_common import multi_asic
from tabulate import tabulate
from utilities_common.cli import UserCache


COUNTERS_ICMP_ECHO_SESSION_NAME_MAP = "COUNTERS_ICMP_ECHO_SESSION_NAME_MAP"
ICMP_ECHO_SESSION_STATE_TABLE = "ICMP_ECHO_SESSION_TABLE"

# Baseline cache file written by `show icmp stats -c` / `sonic-clear
# icmp counters`. Per-user via UserCache(app_name='icmpstat'), matching
# portstat / switchstat / srv6stat.
ICMP_STATS_CACHE_FILE = "icmpstat"


class IcmpShow:
    def __init__(self, click):
        self.click = click
        namespaces = multi_asic.get_front_end_namespaces()
        self.asic_ids = []
        self.per_npu_statedb = {}
        self.per_npu_countersdb = {}
        self.icmp_echo_table_keys = {}
        self.icmp_counter_name_map = {}
        self.ctx = self.click.get_current_context()
        for namespace in namespaces:
            asic_id = multi_asic.get_asic_index_from_namespace(namespace)
            self.asic_ids.append(asic_id)
            self.per_npu_statedb[asic_id] = SonicV2Connector(use_unix_socket_path=False, namespace=namespace)
            try:
                self.per_npu_statedb[asic_id].connect(self.per_npu_statedb[asic_id].STATE_DB)
                self.icmp_echo_table_keys[asic_id] = sorted(
                        self.per_npu_statedb[asic_id].keys(self.per_npu_statedb[asic_id].STATE_DB,
                                                           'ICMP_ECHO_SESSION_TABLE|*'))
            except (socket.error, IOError) as e:
                self.ctx.fail("Socket error in connecting with ICMP_ECHO_SESSION_TABLE: {}".format(str(e)))
            except (KeyError, ValueError) as e:
                self.ctx.fail("Error getting keys from ICMP_ECHO_SESSION_TABLE: {}".format(str(e)))

            # COUNTERS_DB is best-effort: counters only appear when the
            # ICMP session flex-counter group is enabled. The name-map
            # can carry selective rows (one OID per direction, suffixed
            # '|IN'/'|OUT') and native rows (one OID per session, no
            # suffix) depending on what orchagent negotiated per session.
            self.per_npu_countersdb[asic_id] = SonicV2Connector(use_unix_socket_path=False, namespace=namespace)
            try:
                self.per_npu_countersdb[asic_id].connect(self.per_npu_countersdb[asic_id].COUNTERS_DB)
                name_map = self.per_npu_countersdb[asic_id].get_all(
                        self.per_npu_countersdb[asic_id].COUNTERS_DB,
                        COUNTERS_ICMP_ECHO_SESSION_NAME_MAP) or {}
                self.icmp_counter_name_map[asic_id] = name_map
            except (socket.error, IOError, KeyError, ValueError):
                # Counters are optional; leave the map empty so the
                # shared command still serves sessions / summary.
                self.icmp_counter_name_map[asic_id] = {}

    def get_icmp_echo_entry(self, asic_id, key):
        """Show icmp echo session entry from state db."""
        state_db = self.per_npu_statedb[asic_id]
        tbl_dict = state_db.get_all(state_db.STATE_DB, key)
        if tbl_dict:
            # Prepare data for tabulate
            fields = {
                "key": key.removeprefix("ICMP_ECHO_SESSION_TABLE|"),
                "state": None,
                "dst_ip": None,
                "tx_interval": None,
                "rx_interval": None,
                "hw_lookup": None,
                "session_cookie": None
            }
            for f in tbl_dict:
                if f in fields:
                    fields[f] = tbl_dict[f]
            return [fields["key"], fields["dst_ip"], fields["tx_interval"], fields["rx_interval"], fields["hw_lookup"],
                    fields["session_cookie"], fields["state"]]
        else:
            return None

    def show_icmp_sessions(self, key):
        table_data = []
        for asic_id in self.asic_ids:
            keys = []
            if key is None:
                keys = self.icmp_echo_table_keys[asic_id]
            else:
                keys.append("ICMP_ECHO_SESSION_TABLE|" + key.replace(":", "|"))

            for k in keys:
                entry = self.get_icmp_echo_entry(asic_id, k)
                if entry:
                    table_data.append(entry)

        if table_data:
            headers = ["Key", "Dst IP", "Tx Interval", "Rx Interval", "HW lookup", "Cookie", "State"]
            click.echo(tabulate(table_data, headers=headers))
        else:
            click.echo("Keys not found in ICMP_ECHO_SESSION_TABLE")

    def _get_session_state(self, asic_id, session_key):
        """Look up Up/Down state in STATE_DB. session_key uses ':';
        STATE_DB redis keys use '|' so translate before lookup."""
        state_db = self.per_npu_statedb[asic_id]
        state_key = "{}|{}".format(ICMP_ECHO_SESSION_STATE_TABLE,
                                   session_key.replace(":", "|"))
        tbl = state_db.get_all(state_db.STATE_DB, state_key) or {}
        return tbl.get("state", "N/A")

    # Direction suffixes orchagent appends to the COUNTERS_DB name-map
    # key in selective mode.
    _DIRECTIONS = ("IN", "OUT")
    _NAMEMAP_SEP = "|"

    # Counter mode tags. selective: per-direction OID with '|IN'/'|OUT'
    # suffix; native: per-session OID, no suffix.
    _MODE_SELECTIVE = "selective"
    _MODE_NATIVE = "native"

    # Stat field names published by syncd per mode.
    _SELECTIVE_PACKETS_FIELD = "SAI_COUNTER_STAT_PACKETS"
    _SELECTIVE_BYTES_FIELD = "SAI_COUNTER_STAT_BYTES"
    _NATIVE_IN_PACKETS_FIELD = "SAI_ICMP_ECHO_SESSION_STAT_IN_PACKETS"
    _NATIVE_OUT_PACKETS_FIELD = "SAI_ICMP_ECHO_SESSION_STAT_OUT_PACKETS"

    @classmethod
    def _classify_namemap_key(cls, raw_key):
        """Classify a name-map key as selective or native.

        Returns (session_key, direction_or_None):
          - selective: ('<session_key>', 'IN'|'OUT')
          - native:    ('<raw_key>', None)
        """
        for direction in cls._DIRECTIONS:
            suffix = cls._NAMEMAP_SEP + direction
            if raw_key.endswith(suffix):
                return raw_key[:-len(suffix)], direction
        return raw_key, None

    def _read_selective_counter(self, asic_id, counter_oid):
        """(packets, bytes) for a selective counter OID; 'N/A' when not
        yet polled by syncd."""
        counters_db = self.per_npu_countersdb[asic_id]
        cdict = counters_db.get_all(counters_db.COUNTERS_DB,
                                    "COUNTERS:" + counter_oid) or {}
        # Each ICMP variant declares one stat_id (IN_PACKETS or
        # OUT_PACKETS), so SAI_COUNTER_STAT_PACKETS is per-direction.
        return (cdict.get(self._SELECTIVE_PACKETS_FIELD, "N/A"),
                cdict.get(self._SELECTIVE_BYTES_FIELD, "N/A"))

    def _read_native_counter(self, asic_id, session_oid):
        """{'IN': (pkts, 'N/A'), 'OUT': (pkts, 'N/A')} for a native
        session OID. Native SAI stats expose only packets; bytes
        always 'N/A'."""
        counters_db = self.per_npu_countersdb[asic_id]
        cdict = counters_db.get_all(counters_db.COUNTERS_DB,
                                    "COUNTERS:" + session_oid) or {}
        return {
            "IN":  (cdict.get(self._NATIVE_IN_PACKETS_FIELD,  "N/A"), "N/A"),
            "OUT": (cdict.get(self._NATIVE_OUT_PACKETS_FIELD, "N/A"), "N/A"),
        }

    def _build_session_index(self, asic_id):
        """Group raw name_map into per-session entries keyed by session_key:

            selective: {'mode': 'selective', 'IN': <oid>, 'OUT': <oid>}
            native:    {'mode': 'native',    'oid': <oid>}

        Callers iterate sorted(session_key) for stable output."""
        name_map = self.icmp_counter_name_map.get(asic_id, {})
        index = {}
        for raw_key, oid in name_map.items():
            session_key, direction = self._classify_namemap_key(raw_key)
            if direction is None:
                index[session_key] = {"mode": self._MODE_NATIVE,
                                      "oid":  oid}
            else:
                entry = index.setdefault(session_key,
                                         {"mode": self._MODE_SELECTIVE})
                # Mixed forms shouldn't occur; if they do, selective wins.
                entry["mode"] = self._MODE_SELECTIVE
                entry[direction] = oid
        return index

    def _read_session_counters(self, asic_id, session_entry):
        """{'IN': (pkts, bytes), 'OUT': (pkts, bytes)} for one
        session_entry. Missing directions surface as ('N/A', 'N/A')."""
        if session_entry.get("mode") == self._MODE_NATIVE:
            return self._read_native_counter(asic_id, session_entry["oid"])

        per_dir = {}
        for d in self._DIRECTIONS:
            oid = session_entry.get(d)
            if oid is None:
                per_dir[d] = ("N/A", "N/A")
                continue
            per_dir[d] = self._read_selective_counter(asic_id, oid)
        return per_dir

    @staticmethod
    def _to_int(val):
        """Coerce a redis counter cell to int; None for missing /
        non-numeric so callers can render 'N/A' without raising."""
        try:
            return int(val)
        except (TypeError, ValueError):
            return None

    def _snapshot_counters(self):
        """Walk every session and return
        {session_key: {'IN': (pkts, bytes), 'OUT': (pkts, bytes)}}
        with ints, or None for missing / native bytes. Single source of
        truth for both snapshot and baseline-diff paths."""
        snapshot = {}
        for asic_id in self.asic_ids:
            session_index = self._build_session_index(asic_id)
            for sk, entry in session_index.items():
                per_dir_raw = self._read_session_counters(asic_id, entry)
                snapshot[sk] = {
                    d: (self._to_int(per_dir_raw[d][0]),
                        self._to_int(per_dir_raw[d][1]))
                    for d in self._DIRECTIONS
                }
        return snapshot

    @staticmethod
    def _baseline_path():
        """Absolute path of this user's baseline cache file (created
        on first call as a UserCache side-effect)."""
        cache = UserCache(app_name="icmpstat")
        return os.path.join(cache.get_directory(), ICMP_STATS_CACHE_FILE)

    @classmethod
    def _load_baseline(cls):
        """(timestamp, snapshot) or (None, {}) when missing. Corrupt
        files are treated as missing so callers see absolute counters."""
        path = cls._baseline_path()
        if not os.path.isfile(path):
            return None, {}
        try:
            with open(path, "r") as fh:
                payload = json.load(fh)
            return payload.get("timestamp"), payload.get("data") or {}
        except (OSError, ValueError):
            return None, {}

    def clear_baseline(self):
        """Snapshot current counters as the baseline. Subsequent
        `show icmp stats` subtracts it. Hardware counters are untouched."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        snapshot = self._snapshot_counters()
        # Tuples become 2-element lists for JSON.
        serializable = {
            sk: {d: list(v) for d, v in per_dir.items()}
            for sk, per_dir in snapshot.items()
        }
        path = self._baseline_path()
        # Atomic write to avoid leaving a half-written file behind.
        tmp_path = path + ".tmp"
        with open(tmp_path, "w") as fh:
            json.dump({"timestamp": timestamp, "data": serializable}, fh)
        os.replace(tmp_path, path)
        click.echo("Cleared ICMP echo session counter baseline at {}"
                   .format(timestamp))

    @staticmethod
    def _apply_baseline(current, baseline_pair):
        """current - baseline, clamped at zero; pass non-numeric values
        through. The clamp guards against counter resets (e.g. session
        recreated since the snapshot)."""
        cur_i = IcmpShow._to_int(current)
        if cur_i is None or baseline_pair is None:
            return current
        base_i = IcmpShow._to_int(baseline_pair)
        if base_i is None:
            return current
        return max(0, cur_i - base_i)

    def get_icmp_stats_entry(self, asic_id, session_key, session_entry,
                             baseline=None):
        """One tabulate row for one session. With `baseline`, values are
        rendered as deltas. Native sessions render 'N/A' for bytes."""
        per_dir = self._read_session_counters(asic_id, session_entry)

        state = self._get_session_state(asic_id, session_key)

        in_packets, in_bytes = per_dir["IN"]
        out_packets, out_bytes = per_dir["OUT"]

        if baseline:
            base_in = baseline.get("IN") or [None, None]
            base_out = baseline.get("OUT") or [None, None]
            in_packets = self._apply_baseline(in_packets, base_in[0])
            in_bytes = self._apply_baseline(in_bytes, base_in[1])
            out_packets = self._apply_baseline(out_packets, base_out[0])
            out_bytes = self._apply_baseline(out_bytes, base_out[1])

        return [
            session_key, state,
            in_packets, in_bytes,
            out_packets, out_bytes,
        ]

    def show_icmp_stats(self, key, clear=False):
        """Tabulated per-session ICMP echo stats with IN (RX) / OUT (TX)
        columns. Native sessions render bytes as 'N/A'.

        <key> uses 'scope:port:guid:mode' (':' or '|' separators).

        clear=True snapshots current counters as the baseline; <key> is
        ignored (clear is global, mirroring `portstat -c`)."""
        if clear:
            self.clear_baseline()
            return

        if key is not None:
            normalized_key = key.replace("|", ":")
        else:
            normalized_key = None

        baseline_ts, baseline_data = self._load_baseline()

        rows = []
        for asic_id in self.asic_ids:
            session_index = self._build_session_index(asic_id)
            if normalized_key is not None:
                if normalized_key in session_index:
                    rows.append(self.get_icmp_stats_entry(
                            asic_id, normalized_key,
                            session_index[normalized_key],
                            baseline=baseline_data.get(normalized_key)))
                continue

            for sk in sorted(session_index.keys()):
                rows.append(self.get_icmp_stats_entry(
                        asic_id, sk, session_index[sk],
                        baseline=baseline_data.get(sk)))

        if not rows:
            if normalized_key is not None:
                click.echo("No counters found for session '{}'. "
                           "Make sure the ICMP session counter group is "
                           "enabled and the session exists in "
                           "COUNTERS_ICMP_ECHO_SESSION_NAME_MAP."
                           .format(normalized_key))
            else:
                click.echo("No ICMP echo session counters found in COUNTERS_DB. "
                           "ICMP session counters may not be enabled, or no "
                           "sessions are currently provisioned.")
            return

        if baseline_ts is not None:
            click.echo("Last cached time was {}".format(baseline_ts))

        headers = [
            "Key", "State",
            "RX Pkts", "RX Bytes",
            "TX Pkts", "TX Bytes",
        ]
        click.echo(tabulate(rows, headers=headers,
                            tablefmt="simple", numalign="right"))

    def show_summary(self):
        total_sessions = 0
        total_up = 0
        total_rx = 0
        for asic_id in self.asic_ids:
            keys = self.icmp_echo_table_keys[asic_id]

            for k in keys:
                if 'RX' in k:
                    total_rx = total_rx + 1
                entry = self.get_icmp_echo_entry(asic_id, k)
                total_sessions = total_sessions + 1
                if entry and entry[6] == "Up":
                    total_up = total_up + 1

        self.click.echo("Total Sessions: {}".format(total_sessions))
        self.click.echo("Up sessions: {}".format(total_up))
        self.click.echo("RX sessions: {}".format(total_rx))


@click.group(cls=clicommon.AliasedGroup)
def icmp():
    """Show icmp-offload information"""
    pass


@icmp.command()
@click.argument('key', required=False)
def sessions(key):
    s_icmp = IcmpShow(click)
    s_icmp.show_icmp_sessions(key)


@icmp.command()
def summary():
    s_icmp = IcmpShow(click)
    s_icmp.show_summary()


@icmp.command()
@click.argument('key', required=False)
@click.option('-c', '--clear', 'clear', is_flag=True, default=False,
              help='Snapshot current counters as baseline; subsequent '
                   '`show icmp stats` calls subtract it. Same as '
                   '`sonic-clear icmp counters`.')
def stats(key, clear):
    """Per-session ICMP echo counter stats.

    Selective back-end reports packets + bytes; native back-end reports
    packets only (bytes 'N/A').

    Without <key>: list every session in
    COUNTERS_ICMP_ECHO_SESSION_NAME_MAP. With <key> 'scope:port:guid:mode'
    (e.g. 'default:Ethernet8:0x00270003:NORMAL'; ':' or '|'): just that
    session.

    With `-c`: snapshot current values as the new baseline and exit.
    """
    if clear and key is not None:
        click.echo("Note: -c clears the baseline for all sessions; "
                   "ignoring filter '{}'.".format(key))
    s_icmp = IcmpShow(click)
    s_icmp.show_icmp_stats(key, clear=clear)

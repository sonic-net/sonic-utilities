import ast
import os
import subprocess
import tempfile
import threading
from pathlib import Path

REPO = Path(__file__).parents[1]
SCRIPT = REPO / "scripts" / "teamd_increase_retry_count.py"
FAST_REBOOT = REPO / "scripts" / "fast-reboot"
DEFINITIONS = {
    "LacpPacketListenThread",
    "PortChannelProbeThread",
    "probePortChannel",
    "probePortChannels",
}


class FakeLog:
    def __init__(self):
        self.messages = []

    def __getattr__(self, method):
        def record(message, **kwargs):
            self.messages.append((method, message, kwargs))

        return record


def load_probe_code(overrides=None):
    tree = ast.parse(SCRIPT.read_text())
    definitions = [
        node
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
        and node.name in DEFINITIONS
    ]
    assert {node.name for node in definitions} == DEFINITIONS
    namespace = {
        "Thread": threading.Thread,
        "Event": threading.Event,
        "log": FakeLog(),
    }
    exec(
        compile(ast.Module(body=definitions, type_ignores=[]), str(SCRIPT), "exec"),
        namespace,
    )
    namespace.update(overrides or {})
    return namespace


def make_config(port_name, target_mac):
    return {
        "ports": {
            port_name: {
                "runner": {
                    "actor_lacpdu_info": {},
                    "partner_lacpdu_info": {"system": target_mac},
                }
            }
        }
    }


def make_lldp(port_names):
    return {
        "lldp": {
            "interface": [
                {
                    port_name: {
                        "chassis": {
                            "peer-{}".format(port_name): {
                                "descr": "SONiC Software Version: test"
                            }
                        }
                    }
                }
                for port_name in port_names
            ]
        }
    }


def test_unsupported_portchannels_probe_concurrently():
    port_channels = [
        "PortChannel104",
        "PortChannel101",
        "PortChannel103",
        "PortChannel102",
    ]
    port_names = ["Ethernet101", "Ethernet102", "Ethernet103", "Ethernet104"]
    configs = {
        port_channel: make_config(port_name, "target-{}".format(port_name))
        for port_channel, port_name in zip(sorted(port_channels), port_names)
    }
    barrier = threading.Barrier(len(port_channels))
    lldp_calls = []
    sent = []
    config_calls = []

    class FakeListener:
        def __init__(self, port, target_mac, ready_event):
            self.port = port
            self.ready_event = ready_event
            self.detectedNewVersion = False
            self.error = None

        def start(self):
            self.ready_event.set()

        def join(self):
            # This barrier breaks if PortChannels are processed serially.
            barrier.wait(timeout=2)

        def is_alive(self):
            return False

    namespace = load_probe_code(
        {
            "LacpPacketListenThread": FakeListener,
            "getPortChannelConfig": lambda name, ns: (
                config_calls.append((name, ns)) or configs[name]
            ),
            "getLldpNeighbors": lambda ns: (
                lldp_calls.append(ns) or make_lldp(port_names)
            ),
            "craftLacpPacket": lambda config, port, **kwargs: (
                port,
                kwargs.get("newVersion", True),
            ),
            "sendp": lambda packet, **kwargs: sent.append((packet, kwargs)),
            "time": type("FakeTime", (), {"sleep": staticmethod(lambda seconds: None)}),
        }
    )

    failed = namespace["probePortChannels"](set(port_channels), "asic0")

    assert failed == sorted(port_channels)
    assert lldp_calls == ["asic0"]
    assert config_calls == [(name, "asic0") for name in sorted(port_channels)]
    assert len(sent) == 8
    assert sum(1 for _, kwargs in sent if "count" not in kwargs) == 4
    assert sum(1 for _, kwargs in sent if kwargs.get("count") == 2) == 4


def test_each_probe_resets_without_waiting_for_slowest_peer():
    port_channels = ["PortChannel101", "PortChannel102"]
    port_names = ["Ethernet101", "Ethernet102"]
    configs = {
        port_channel: make_config(port_name, "target-{}".format(port_name))
        for port_channel, port_name in zip(port_channels, port_names)
    }
    release_slow = threading.Event()
    fast_reset = threading.Event()

    class FakeListener:
        def __init__(self, port, target_mac, ready_event):
            self.port = port
            self.ready_event = ready_event
            self.detectedNewVersion = False
            self.error = None

        def start(self):
            self.ready_event.set()

        def join(self):
            if self.port == "Ethernet102":
                assert release_slow.wait(timeout=2)

        def is_alive(self):
            return False

    def record_send(packet, **kwargs):
        if packet == ("Ethernet101", False):
            fast_reset.set()

    namespace = load_probe_code(
        {
            "LacpPacketListenThread": FakeListener,
            "getPortChannelConfig": lambda name, ns: configs[name],
            "getLldpNeighbors": lambda ns: make_lldp(port_names),
            "craftLacpPacket": lambda config, port, **kwargs: (
                port,
                kwargs.get("newVersion", True),
            ),
            "sendp": record_send,
            "time": type("FakeTime", (), {"sleep": staticmethod(lambda seconds: None)}),
        }
    )

    result = []
    coordinator = threading.Thread(
        target=lambda: result.extend(namespace["probePortChannels"](port_channels))
    )
    coordinator.start()
    assert fast_reset.wait(timeout=1)
    assert coordinator.is_alive()
    release_slow.set()
    coordinator.join(timeout=2)

    assert not coordinator.is_alive()
    assert result == port_channels


def test_mixed_results_remain_per_portchannel_and_deterministic():
    port_channels = ["PortChannel102", "PortChannel101"]
    port_names = ["Ethernet101", "Ethernet102"]
    configs = {
        port_channel: make_config(port_name, "target-{}".format(port_name))
        for port_channel, port_name in zip(sorted(port_channels), port_names)
    }

    class FakeListener:
        def __init__(self, port, target_mac, ready_event):
            self.port = port
            self.ready_event = ready_event
            self.detectedNewVersion = port == "Ethernet101"
            self.error = None

        def start(self):
            self.ready_event.set()

        def join(self):
            pass

        def is_alive(self):
            return False

    log = FakeLog()
    namespace = load_probe_code(
        {
            "LacpPacketListenThread": FakeListener,
            "getPortChannelConfig": lambda name, ns: configs[name],
            "getLldpNeighbors": lambda ns: make_lldp(port_names),
            "craftLacpPacket": lambda config, port, **kwargs: object(),
            "sendp": lambda *args, **kwargs: None,
            "time": type("FakeTime", (), {"sleep": staticmethod(lambda seconds: None)}),
            "log": log,
        }
    )

    assert namespace["probePortChannels"](port_channels) == ["PortChannel102"]
    assert any(
        method == "log_notice" and "peer-Ethernet101" in message
        for method, message, _ in log.messages
    )
    assert any(
        method == "log_warning" and "peer-Ethernet102" in message
        for method, message, _ in log.messages
    )


def test_worker_exception_is_reported_as_probe_failure():
    port_names = ["Ethernet101", "Ethernet102"]

    class FakeListener:
        def __init__(self, port, target_mac, ready_event):
            self.ready_event = ready_event
            self.detectedNewVersion = True
            self.error = None

        def start(self):
            self.ready_event.set()

        def join(self):
            pass

        def is_alive(self):
            return False

    def get_config(name, namespace):
        if name == "PortChannel102":
            raise RuntimeError("teamdctl failed")
        return make_config("Ethernet101", "target")

    namespace = load_probe_code(
        {
            "LacpPacketListenThread": FakeListener,
            "getPortChannelConfig": get_config,
            "getLldpNeighbors": lambda ns: make_lldp(port_names),
            "craftLacpPacket": lambda config, port, **kwargs: object(),
            "sendp": lambda *args, **kwargs: None,
            "time": type("FakeTime", (), {"sleep": staticmethod(lambda seconds: None)}),
        }
    )

    assert namespace["probePortChannels"](["PortChannel102", "PortChannel101"]) == [
        "PortChannel102"
    ]
    assert any(
        method == "log_error" and "teamdctl failed" in message
        for method, message, _ in namespace["log"].messages
    )


def test_listener_error_after_detection_remains_a_probe_failure_and_resets():
    sent = []

    class FakeListener:
        def __init__(self, port, target_mac, ready_event):
            self.ready_event = ready_event
            self.detectedNewVersion = True
            self.error = None

        def start(self):
            self.ready_event.set()

        def join(self):
            self.error = RuntimeError("capture failed after detection")

        def is_alive(self):
            return False

    namespace = load_probe_code(
        {
            "LacpPacketListenThread": FakeListener,
            "getPortChannelConfig": lambda name, ns: make_config(
                "Ethernet101", "target"
            ),
            "craftLacpPacket": lambda config, port, **kwargs: (
                port,
                kwargs.get("newVersion", True),
            ),
            "sendp": lambda packet, **kwargs: sent.append((packet, kwargs)),
            "time": type("FakeTime", (), {"sleep": staticmethod(lambda seconds: None)}),
        }
    )

    assert not namespace["probePortChannel"](
        "PortChannel101", "", make_lldp(["Ethernet101"])
    )
    assert any(kwargs.get("count") == 2 for _, kwargs in sent)
    assert any(
        method == "log_error" and "capture failed after detection" in message
        for method, message, _ in namespace["log"].messages
    )


def test_non_sonic_peer_is_unsupported_without_operational_error():
    lldp = make_lldp(["Ethernet101"])
    peer = lldp["lldp"]["interface"][0]["Ethernet101"]["chassis"]["peer-Ethernet101"]
    peer["descr"] = "Arista EOS"
    namespace = load_probe_code(
        {
            "getPortChannelConfig": lambda name, ns: make_config(
                "Ethernet101", "target"
            ),
        }
    )

    assert not namespace["probePortChannel"]("PortChannel101", "", lldp)
    assert any(
        method == "log_warning" and "not a SONiC device" in message
        for method, message, _ in namespace["log"].messages
    )
    assert not any(method == "log_error" for method, _, _ in namespace["log"].messages)


def test_listener_setup_failure_releases_sender():
    error = RuntimeError("capture setup failed")
    ready = threading.Event()
    namespace = load_probe_code(
        {
            "LACP_ETHERTYPE": 0x8809,
            "sniff": lambda **kwargs: (_ for _ in ()).throw(error),
        }
    )

    listener = namespace["LacpPacketListenThread"](
        "Ethernet0", "00:11:22:33:44:55", ready
    )
    listener.start()
    assert ready.wait(timeout=1)
    listener.join(timeout=1)

    assert listener.error is error
    assert not listener.is_alive()


def test_missing_lldp_fails_all_without_starting_workers():
    namespace = load_probe_code(
        {
            "getLldpNeighbors": lambda ns: None,
            "getPortChannelConfig": lambda name, ns: (_ for _ in ()).throw(
                AssertionError("unexpected config read")
            ),
        }
    )

    assert namespace["probePortChannels"]({"PortChannel2", "PortChannel1"}) == [
        "PortChannel1",
        "PortChannel2",
    ]


def extract_shell_function(name):
    lines = FAST_REBOOT.read_text().splitlines()
    start = lines.index("function {}()".format(name))
    for end in range(start + 1, len(lines)):
        if lines[end] == "}":
            return "\n".join(lines[start : end + 1]) + "\n"
    raise AssertionError("function {} has no closing brace".format(name))


def run_strict_check(required, check_rc):
    script = extract_shell_function("require_teamd_retry_count_probe_success")
    script += r"""
error() { echo "error:$*" >&2; }
check_teamd_retry_count_probe_success() { return "$CHECK_RC"; }
require_teamd_retry_count_probe_success
rc=$?
echo "rc=$rc"
exit "$rc"
"""
    env = os.environ.copy()
    env.update(
        {
            "REQUIRE_TEAMD_RETRY_COUNT": required,
            "EXIT_TEAMD_RETRY_COUNT_FAILURE": "23",
            "CHECK_RC": str(check_rc),
        }
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        return subprocess.run(
            ["bash", "-c", script],
            cwd=tmpdir,
            env=env,
            capture_output=True,
            text=True,
        )


def test_strict_retry_count_gate_callsite_is_present():
    source = FAST_REBOOT.read_text()
    assert 'require_teamd_retry_count_probe_success || exit "$?"' in source


def test_strict_retry_count_gate_only_fails_on_failed_required_probe():
    non_strict = run_strict_check("no", 1)
    assert non_strict.returncode == 0
    assert non_strict.stdout.strip() == "rc=0"
    assert non_strict.stderr == ""

    strict_success = run_strict_check("yes", 0)
    assert strict_success.returncode == 0
    assert strict_success.stdout.strip() == "rc=0"

    strict_failure = run_strict_check("yes", 1)
    assert strict_failure.returncode == 23
    assert strict_failure.stdout.strip() == "rc=23"
    assert "Could not confirm" in strict_failure.stderr

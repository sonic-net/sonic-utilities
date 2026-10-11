import os
import socket
import stat
import threading
from types import SimpleNamespace
from unittest import mock

import pytest

from redis_read_broker import server
from redis_read_broker.policy import PolicyDenied


@pytest.fixture
def broker_config(tmp_path):
    runtime = tmp_path / "run"
    runtime.mkdir()
    return SimpleNamespace(
        instance="default",
        namespace="",
        database_ids=(4, 6),
        database_names=("CONFIG_DB", "STATE_DB"),
        skipped_databases=(),
        upstream_socket=str(runtime / "upstream.sock"),
        broker_socket=str(runtime / "redis.sock"),
    )


def _request(*arguments):
    raw = b"*%d\r\n" % len(arguments)
    for argument in arguments:
        raw += b"$%d\r\n%s\r\n" % (len(argument), argument)
    return raw


def _recv_exact(sock, expected_size):
    chunks = []
    received = 0
    while received < expected_size:
        chunk = sock.recv(expected_size - received)
        assert chunk, "socket closed before all expected bytes arrived"
        chunks.append(chunk)
        received += len(chunk)
    return b"".join(chunks)


class ProxyHarness(object):
    """Run one real broker connection between local Unix socket pairs."""

    def __init__(self, config):
        self.broker = server.BrokerServer(config)
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(config.upstream_socket)
        self.listener.listen(1)
        self.listener.settimeout(3.0)

        self.client, broker_client = socket.socketpair()
        self.client.settimeout(3.0)
        with self.broker._clients_lock:
            self.broker._clients.add(broker_client)
        self.thread = threading.Thread(
            target=self.broker._client_thread, args=(broker_client,))
        self.thread.daemon = True
        self.thread.start()

        self.upstream, _ = self.listener.accept()
        self.upstream.settimeout(3.0)

    def wait(self):
        self.thread.join(3.0)
        assert not self.thread.is_alive(), "broker connection did not stop"

    def close(self):
        self.broker.shutdown()
        for sock in (self.client, self.upstream, self.listener):
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()
        self.thread.join(3.0)
        assert not self.thread.is_alive(), "broker connection did not stop"


@pytest.fixture
def proxy(broker_config):
    harness = ProxyHarness(broker_config)
    try:
        yield harness
    finally:
        harness.close()


def test_listener_lifecycle_and_connect_permissions(broker_config):
    broker = server.BrokerServer(broker_config)
    listener = broker._create_listener()
    broker.listener = listener

    path_stat = os.lstat(broker_config.broker_socket)
    assert stat.S_ISSOCK(path_stat.st_mode)
    assert stat.S_IMODE(path_stat.st_mode) == 0o622

    broker.shutdown()

    assert not os.path.exists(broker_config.broker_socket)


def test_listener_replaces_stale_socket_and_rejects_occupied_path(broker_config):
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale.bind(broker_config.broker_socket)
    stale.close()

    broker = server.BrokerServer(broker_config)
    listener = broker._create_listener()
    listener.close()
    broker.shutdown()

    with open(broker_config.broker_socket, "w") as stream:
        stream.write("occupied")
    with pytest.raises(RuntimeError, match="occupied"):
        broker._create_listener()


def test_client_thread_uses_fixed_upstream_and_handles_clean_eof(
        proxy, broker_config):
    # ProxyHarness can accept this connection only because _client_thread used
    # the exact root-configured upstream path.
    assert proxy.broker.config.upstream_socket == broker_config.upstream_socket

    proxy.client.shutdown(socket.SHUT_WR)
    proxy.wait()

    assert proxy.upstream.recv(1) == b""
    assert proxy.client.recv(1) == b""
    assert not proxy.broker._clients


def test_fragmented_and_coalesced_requests_are_forwarded_byte_for_byte(proxy):
    fragmented = _request(b"HGETALL", b"FEATURE|bgp")
    proxy.client.sendall(fragmented[:1])
    proxy.client.sendall(fragmented[1:-1])

    proxy.upstream.settimeout(0.1)
    with pytest.raises(socket.timeout):
        proxy.upstream.recv(1)

    proxy.upstream.settimeout(3.0)
    proxy.client.sendall(fragmented[-1:])
    assert _recv_exact(proxy.upstream, len(fragmented)) == fragmented

    coalesced = b"".join((
        _request(b"SELECT", b"4"),
        _request(b"EXISTS", b"FEATURE|bgp"),
        _request(b"KEYS", b"FEATURE|*"),
        _request(b"HGETALL", b"FEATURE|bgp"),
    ))
    proxy.client.sendall(coalesced)
    assert _recv_exact(proxy.upstream, len(coalesced)) == coalesced


def test_arbitrary_upstream_bytes_are_relayed_without_response_parsing(proxy):
    response = b"\x00not-resp\xff\r\n*broken\r\n$999\r\n"

    proxy.upstream.sendall(response)

    assert _recv_exact(proxy.client, len(response)) == response


def test_large_upstream_response_is_streamed_byte_for_byte(proxy):
    first = b"first-chunk-without-a-complete-resp-frame"
    proxy.upstream.sendall(first)

    # Receiving this before the remaining bytes are sent proves that the
    # broker does not wait for or buffer a complete Redis response.
    assert _recv_exact(proxy.client, len(first)) == first

    large = (b"\x00raw-response-data\xff" * 131072)[:2 * 1024 * 1024]
    send_errors = []

    def send_large_response():
        try:
            proxy.upstream.sendall(large)
        except Exception as error:  # pragma: no cover - reported below
            send_errors.append(error)

    sender = threading.Thread(target=send_large_response)
    sender.start()
    received = _recv_exact(proxy.client, len(large))
    sender.join(3.0)

    assert not sender.is_alive()
    assert not send_errors
    assert received == large


def test_more_than_1024_pipelined_requests_stay_on_one_connection(proxy):
    pipeline = _request(b"PING") * 4096

    proxy.client.sendall(pipeline)

    assert _recv_exact(proxy.upstream, len(pipeline)) == pipeline
    assert proxy.thread.is_alive()

    final_request = _request(b"PING")
    proxy.client.sendall(final_request)
    assert _recv_exact(proxy.upstream, len(final_request)) == final_request


@pytest.mark.parametrize("payload", [
    _request(b"SET", b"probe", b"value"),
    b"".join((
        _request(b"PING"),
        _request(b"SET", b"probe", b"value"),
        _request(b"PING"),
    )),
])
def test_denied_write_is_never_forwarded(broker_config, monkeypatch, payload):
    broker = server.BrokerServer(broker_config)
    client = mock.Mock()
    client.recv.return_value = payload
    upstream = mock.Mock()
    monkeypatch.setattr(
        server.select, "select", lambda *_args: ([client], [], []))

    with pytest.raises(PolicyDenied):
        broker._proxy(client, upstream)

    upstream.sendall.assert_not_called()


def test_client_thread_closes_a_denied_write_without_upstream_data(proxy):
    proxy.client.sendall(_request(b"SET", b"probe", b"value"))

    proxy.wait()

    assert proxy.upstream.recv(1) == b""
    assert proxy.client.recv(1) == b""


def test_command_like_bytes_inside_bulk_argument_are_not_reparsed(proxy):
    key = (
        b"FEATURE|looks-like-protocol\r\n"
        b"*3\r\n$3\r\nSET\r\n$5\r\nprobe\r\n$5\r\nvalue\r\n"
    )
    request = _request(b"HGETALL", key)

    proxy.client.sendall(request)

    assert _recv_exact(proxy.upstream, len(request)) == request


def test_incomplete_request_at_eof_is_not_forwarded(proxy):
    proxy.client.sendall(b"*2\r\n$7\r\nHGETALL\r\n$9\r\npartial")
    proxy.client.shutdown(socket.SHUT_WR)

    proxy.wait()

    assert proxy.upstream.recv(1) == b""
    assert proxy.client.recv(1) == b""


def test_main_reports_config_and_server_errors(monkeypatch, broker_config):
    monkeypatch.setattr(
        server, "_arguments", lambda: SimpleNamespace(instance="default"))
    monkeypatch.setattr(
        server,
        "load_instance_config",
        mock.Mock(side_effect=server.BrokerConfigError("bad")),
    )
    assert server.main() == 1

    monkeypatch.setattr(
        server, "load_instance_config", mock.Mock(return_value=broker_config))
    fake_server = mock.Mock()
    fake_server.serve.side_effect = RuntimeError("failed")
    monkeypatch.setattr(server, "BrokerServer", mock.Mock(return_value=fake_server))
    monkeypatch.setattr(server.signal, "signal", mock.Mock())
    assert server.main() == 1

    fake_server.serve.side_effect = None
    assert server.main() == 0

import os
import socket
import stat
import struct
from types import SimpleNamespace
from unittest import mock

import pytest

from redis_read_broker import server
from redis_read_broker.policy import PolicyDenied
from redis_read_broker.resp import (
    ConnectionClosed,
    Frame,
    FrameTooLarge,
    InvalidFrame,
    ParsedFrame,
    RESPError,
    RESPParser,
)


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
        upstream_socket="/var/run/redis/redis.sock",
        broker_socket=str(runtime / "redis.sock"),
    )


def _request(*arguments):
    raw = b"*%d\r\n" % len(arguments)
    for argument in arguments:
        raw += b"$%d\r\n%s\r\n" % (len(argument), argument)
    frame = RESPParser(4096).parse(raw)
    return ParsedFrame(frame, raw)


def _response(raw):
    return ParsedFrame(RESPParser(4096).parse(raw), raw)


def test_listener_has_connect_only_permissions(broker_config):
    broker = server.BrokerServer(broker_config)
    listener = broker._create_listener()
    try:
        assert stat.S_IMODE(os.stat(broker_config.broker_socket).st_mode) == 0o622
    finally:
        listener.close()
        broker.shutdown()


def test_listener_rejects_non_directory_and_occupied_path(broker_config):
    broker = server.BrokerServer(broker_config)
    with mock.patch.object(server.os, "stat", return_value=SimpleNamespace(st_mode=stat.S_IFREG)):
        with pytest.raises(RuntimeError, match="not a directory"):
            broker._create_listener()

    with open(broker_config.broker_socket, "w") as stream:
        stream.write("occupied")
    with pytest.raises(RuntimeError, match="occupied"):
        broker._create_listener()


def test_shutdown_closes_listener_clients_and_socket(broker_config):
    broker = server.BrokerServer(broker_config)
    broker.listener = mock.Mock()
    client = mock.Mock()
    broker._clients.add(client)
    with open(broker_config.broker_socket, "w") as stream:
        stream.write("not a socket")

    broker.shutdown()

    assert broker.stop_event.is_set()
    client.shutdown.assert_called_once_with(socket.SHUT_RDWR)
    client.close.assert_called_once_with()
    assert os.path.exists(broker_config.broker_socket)


def test_peer_credentials_and_account_policy(broker_config, monkeypatch):
    broker = server.BrokerServer(broker_config)
    client = mock.Mock()
    client.getsockopt.return_value = struct.pack("3i", 123, 1001, 1002)
    assert broker._peer_credentials(client) == (1001, 1002)

    assert broker._peer_allowed(0)
    assert not broker._peer_allowed(999)
    assert not broker._peer_allowed(65534)
    monkeypatch.setattr(server.pwd, "getpwuid", lambda _uid: SimpleNamespace(pw_shell="/bin/bash"))
    assert broker._peer_allowed(1001)
    monkeypatch.setattr(server.pwd, "getpwuid", lambda _uid: SimpleNamespace(pw_shell="/usr/sbin/nologin"))
    assert not broker._peer_allowed(1001)
    monkeypatch.setattr(server.pwd, "getpwuid", mock.Mock(side_effect=KeyError))
    assert not broker._peer_allowed(1001)


def test_send_error_handles_closed_client():
    client = mock.Mock()
    server.BrokerServer._send_error(client, server.DENIED_RESPONSE)
    client.settimeout.assert_called_once_with(1.0)
    client.sendall.assert_called_once_with(server.DENIED_RESPONSE)

    client.sendall.side_effect = OSError
    server.BrokerServer._send_error(client, server.DENIED_RESPONSE)


def test_read_request_batch_collects_buffered_pipeline(monkeypatch):
    monkeypatch.setattr(server, "MAX_REQUEST_BYTES", 100)
    first = _request(b"PING")
    second = _request(b"ECHO", b"hi")
    reader = mock.Mock()
    reader.read_frame.return_value = first
    reader.try_frame.side_effect = [second, None]
    reader.buffer = bytearray()
    reader.is_readable.return_value = False

    assert server.BrokerServer._read_request_batch(mock.Mock(), reader) == [first, second]


def test_read_request_batch_reads_partial_buffer():
    first = _request(b"PING")
    second = _request(b"ECHO", b"hi")
    reader = mock.Mock()
    frames = iter((first, second))

    def read_frame(_client, _timeout):
        frame = next(frames)
        if frame is second:
            reader.buffer.clear()
        return frame

    reader.read_frame.side_effect = read_frame
    reader.try_frame.side_effect = [None, None]
    reader.buffer = bytearray(b"partial")
    reader.is_readable.return_value = False

    batch = server.BrokerServer._read_request_batch(mock.Mock(), reader)

    assert batch == [first, second]


def test_read_request_batch_enforces_byte_and_depth_limits(monkeypatch):
    first = _request(b"PING")
    reader = mock.Mock()
    reader.read_frame.return_value = first
    reader.try_frame.return_value = first
    reader.buffer = bytearray()
    reader.is_readable.return_value = False
    monkeypatch.setattr(server, "MAX_REQUEST_BYTES", len(first.raw) + 1)
    with pytest.raises(FrameTooLarge, match="batch"):
        server.BrokerServer._read_request_batch(mock.Mock(), reader)

    monkeypatch.setattr(server, "MAX_REQUEST_BYTES", 10000)
    monkeypatch.setattr(server, "MAX_PIPELINE_DEPTH", 1)
    reader.buffer = bytearray(b"more")
    with pytest.raises(FrameTooLarge, match="depth"):
        server.BrokerServer._read_request_batch(mock.Mock(), reader)


def test_read_command_response_skips_attributes_and_pushes(monkeypatch):
    reader = mock.Mock()
    reader.read_frame.side_effect = [
        _response(b"|1\r\n+meta\r\n+value\r\n"),
        _response(b">1\r\n+notice\r\n"),
        _response(b"+OK\r\n"),
    ]
    monkeypatch.setattr(server.time, "monotonic", lambda: 1.0)

    raw, frame = server.BrokerServer._read_command_response(mock.Mock(), reader, 2.0)

    assert raw.endswith(b"+OK\r\n")
    assert frame.value == b"OK"


def test_read_command_response_enforces_limits(monkeypatch):
    monkeypatch.setattr(server.time, "monotonic", lambda: 2.0)
    with pytest.raises(socket.timeout):
        server.BrokerServer._read_command_response(mock.Mock(), mock.Mock(), 1.0)

    reader = mock.Mock()
    reader.read_frame.side_effect = ConnectionClosed()
    monkeypatch.setattr(server.time, "monotonic", lambda: 1.0)
    with pytest.raises(RESPError, match="closed"):
        server.BrokerServer._read_command_response(mock.Mock(), reader, 2.0)

    reader.read_frame.side_effect = None
    reader.read_frame.return_value = _response(b"+long\r\n")
    monkeypatch.setattr(server, "MAX_RESPONSE_BYTES", 2)
    with pytest.raises(FrameTooLarge, match="response"):
        server.BrokerServer._read_command_response(mock.Mock(), reader, 2.0)

    monkeypatch.setattr(server, "MAX_RESPONSE_BYTES", 1000)
    monkeypatch.setattr(server, "MAX_AUXILIARY_RESPONSES", 0)
    reader.read_frame.return_value = _response(b">1\r\n+notice\r\n")
    with pytest.raises(FrameTooLarge, match="auxiliary"):
        server.BrokerServer._read_command_response(mock.Mock(), reader, 2.0)


def test_proxy_forwards_authorized_pipeline(broker_config, monkeypatch):
    broker = server.BrokerServer(broker_config)
    client = mock.Mock()
    upstream = mock.Mock()
    request_batch = [
        _request(b"SELECT", b"4"),
        _request(b"HGETALL", b"FEATURE|bgp"),
        _request(b"QUIT"),
    ]
    monkeypatch.setattr(broker, "_read_request_batch", mock.Mock(return_value=request_batch))
    monkeypatch.setattr(broker, "_read_command_response", mock.Mock(side_effect=[
        (b"+OK\r\n", Frame(b"+", value=b"OK")),
        (b"*0\r\n", Frame(b"*", children=())),
        (b"+OK\r\n", Frame(b"+", value=b"OK")),
    ]))

    assert broker._proxy(client, upstream, 1001, 1001) == 3
    assert upstream.sendall.call_args_list == [
        mock.call(item.raw) for item in request_batch]
    client.sendall.assert_called_once_with(b"+OK\r\n*0\r\n+OK\r\n")


def test_proxy_rejects_failed_select_and_connection_limit(broker_config, monkeypatch):
    broker = server.BrokerServer(broker_config)
    monkeypatch.setattr(broker, "_read_request_batch", mock.Mock(return_value=[
        _request(b"SELECT", b"4")]))
    monkeypatch.setattr(broker, "_read_command_response", mock.Mock(return_value=(
        b"-ERR\r\n", Frame(b"-", value=b"ERR"))))
    with pytest.raises(RESPError, match="selection"):
        broker._proxy(mock.Mock(), mock.Mock(), 1001, 1001)

    monkeypatch.setattr(server, "MAX_REQUESTS_PER_CONNECTION", 0)
    with pytest.raises(FrameTooLarge, match="request limit"):
        broker._proxy(mock.Mock(), mock.Mock(), 1001, 1001)


@pytest.mark.parametrize(("error", "response"), [
    (PolicyDenied("SET"), server.DENIED_RESPONSE),
    (FrameTooLarge(), server.LIMIT_RESPONSE),
    (InvalidFrame(), server.PROTOCOL_RESPONSE),
    (RESPError(), server.UPSTREAM_RESPONSE),
    (RuntimeError(), server.UPSTREAM_RESPONSE),
])
def test_client_thread_maps_failures_to_safe_errors(
        broker_config, monkeypatch, error, response):
    broker = server.BrokerServer(broker_config)
    client = mock.Mock()
    broker.connection_slots.acquire()
    monkeypatch.setattr(broker, "_peer_credentials", mock.Mock(return_value=(1001, 1001)))
    monkeypatch.setattr(broker, "_peer_allowed", mock.Mock(return_value=True))
    monkeypatch.setattr(broker, "_proxy", mock.Mock(side_effect=error))
    upstream = mock.Mock()
    socket_factory = mock.Mock(return_value=upstream)
    monkeypatch.setattr(server.socket, "socket", socket_factory)
    send_error = mock.Mock()
    monkeypatch.setattr(broker, "_send_error", send_error)

    broker._client_thread(client)

    send_error.assert_called_once_with(client, response)
    upstream.connect.assert_called_once_with(broker_config.upstream_socket)
    client.close.assert_called_once_with()


def test_client_thread_rejects_disallowed_peer_without_upstream(broker_config, monkeypatch):
    broker = server.BrokerServer(broker_config)
    client = mock.Mock()
    broker.connection_slots.acquire()
    monkeypatch.setattr(broker, "_peer_credentials", mock.Mock(return_value=(999, 999)))
    send_error = mock.Mock()
    monkeypatch.setattr(broker, "_send_error", send_error)

    broker._client_thread(client)

    send_error.assert_called_once_with(client, server.DENIED_RESPONSE)
    client.close.assert_called_once_with()


def test_main_reports_config_and_server_errors(monkeypatch, broker_config):
    monkeypatch.setattr(server, "_arguments", lambda: SimpleNamespace(instance="default"))
    monkeypatch.setattr(server, "load_instance_config", mock.Mock(
        side_effect=server.BrokerConfigError("bad")))
    assert server.main() == 1

    monkeypatch.setattr(server, "load_instance_config", mock.Mock(return_value=broker_config))
    fake_server = mock.Mock()
    fake_server.serve.side_effect = RuntimeError("failed")
    monkeypatch.setattr(server, "BrokerServer", mock.Mock(return_value=fake_server))
    monkeypatch.setattr(server.signal, "signal", mock.Mock())
    assert server.main() == 1

    fake_server.serve.side_effect = None
    assert server.main() == 0

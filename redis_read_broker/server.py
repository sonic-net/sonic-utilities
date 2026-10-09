"""Redis-compatible read broker for local, non-admin display clients."""

import argparse
import logging
import os
import pwd
import signal
import socket
import stat
import struct
import threading
import time

from redis_read_broker.config import BrokerConfigError, load_instance_config
from redis_read_broker.policy import PolicyDenied, ReadPolicy
from redis_read_broker.resp import (
    ConnectionClosed,
    FrameTooLarge,
    InvalidFrame,
    RESPError,
    SocketReader,
    request_arguments,
)


LOGGER = logging.getLogger("sonic-redis-read-broker")

MAX_CONNECTIONS = 16
MAX_REQUEST_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_PIPELINE_DEPTH = 32
MAX_REQUESTS_PER_CONNECTION = 1024
MAX_AUXILIARY_RESPONSES = 16
IDLE_TIMEOUT_SECONDS = 60.0
COMMAND_TIMEOUT_SECONDS = 5.0

DENIED_RESPONSE = b"-NOPERM redis read broker denied the request\r\n"
PROTOCOL_RESPONSE = b"-ERR redis read broker received an invalid request\r\n"
LIMIT_RESPONSE = b"-ERR redis read broker limit exceeded\r\n"
UPSTREAM_RESPONSE = b"-ERR redis read broker upstream unavailable\r\n"
BUSY_RESPONSE = b"-ERR redis read broker connection limit reached\r\n"


class BrokerServer(object):
    def __init__(self, config):
        self.config = config
        self.policy = ReadPolicy(config.database_ids)
        self.database_names = dict(zip(config.database_ids, config.database_names))
        self.stop_event = threading.Event()
        self.connection_slots = threading.BoundedSemaphore(MAX_CONNECTIONS)
        self.listener = None
        self._clients = set()
        self._clients_lock = threading.Lock()

    def serve(self):
        self.listener = self._create_listener()
        LOGGER.info(
            "started instance=%s namespace=%s endpoint=%s databases=%s",
            self.config.instance,
            self.config.namespace or "host",
            self.config.upstream_socket,
            ",".join(self.config.database_names),
        )
        if self.config.skipped_databases:
            LOGGER.warning(
                "excluded databases on other or missing endpoints instance=%s databases=%s",
                self.config.instance,
                ",".join(self.config.skipped_databases),
            )

        try:
            while not self.stop_event.is_set():
                try:
                    client, _ = self.listener.accept()
                except socket.timeout:
                    continue
                except OSError:
                    if self.stop_event.is_set():
                        break
                    raise

                if not self.connection_slots.acquire(False):
                    try:
                        uid, gid = self._peer_credentials(client)
                    except Exception:
                        uid, gid = -1, -1
                    self._send_error(client, BUSY_RESPONSE)
                    client.close()
                    LOGGER.warning(
                        "connection rejected instance=%s uid=%d gid=%d reason=limit",
                        self.config.instance, uid, gid)
                    continue

                with self._clients_lock:
                    self._clients.add(client)
                thread = threading.Thread(target=self._client_thread, args=(client,))
                thread.daemon = True
                thread.start()
        finally:
            self.shutdown()

    def shutdown(self):
        self.stop_event.set()
        if self.listener is not None:
            try:
                self.listener.close()
            except OSError:
                pass
            self.listener = None
        with self._clients_lock:
            clients = list(self._clients)
        for client in clients:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                client.close()
            except OSError:
                pass
        try:
            path_stat = os.lstat(self.config.broker_socket)
            if stat.S_ISSOCK(path_stat.st_mode):
                os.unlink(self.config.broker_socket)
        except FileNotFoundError:
            pass
        LOGGER.info("stopped instance=%s", self.config.instance)

    def _create_listener(self):
        runtime_directory = os.path.dirname(self.config.broker_socket)
        directory_stat = os.stat(runtime_directory, follow_symlinks=False)
        if not stat.S_ISDIR(directory_stat.st_mode):
            raise RuntimeError("broker runtime path is not a directory")

        try:
            existing = os.lstat(self.config.broker_socket)
        except FileNotFoundError:
            existing = None
        if existing is not None:
            if not stat.S_ISSOCK(existing.st_mode):
                raise RuntimeError("broker socket path is occupied")
            os.unlink(self.config.broker_socket)

        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            listener.bind(self.config.broker_socket)
            os.chmod(self.config.broker_socket, 0o666)
            listener.listen(MAX_CONNECTIONS)
            listener.settimeout(1.0)
            return listener
        except Exception:
            listener.close()
            raise

    def _client_thread(self, client):
        uid = -1
        gid = -1
        processed = 0
        upstream = None
        try:
            uid, gid = self._peer_credentials(client)
            if not self._peer_allowed(uid):
                LOGGER.warning(
                    "connection denied instance=%s uid=%d gid=%d",
                    self.config.instance, uid, gid)
                self._send_error(client, DENIED_RESPONSE)
                return

            LOGGER.info(
                "connection opened instance=%s uid=%d gid=%d",
                self.config.instance, uid, gid)
            upstream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            upstream.settimeout(COMMAND_TIMEOUT_SECONDS)
            upstream.connect(self.config.upstream_socket)
            processed = self._proxy(client, upstream, uid, gid)
        except ConnectionClosed:
            pass
        except PolicyDenied as error:
            LOGGER.warning(
                "request denied instance=%s uid=%d gid=%d command=%s",
                self.config.instance, uid, gid, error.command)
            self._send_error(client, DENIED_RESPONSE)
        except FrameTooLarge:
            LOGGER.warning(
                "request failed instance=%s uid=%d gid=%d reason=limit",
                self.config.instance, uid, gid)
            self._send_error(client, LIMIT_RESPONSE)
        except InvalidFrame:
            LOGGER.warning(
                "request failed instance=%s uid=%d gid=%d reason=protocol",
                self.config.instance, uid, gid)
            self._send_error(client, PROTOCOL_RESPONSE)
        except (socket.timeout, OSError, RESPError) as error:
            LOGGER.warning(
                "request failed instance=%s uid=%d gid=%d reason=upstream type=%s",
                self.config.instance, uid, gid, type(error).__name__)
            self._send_error(client, UPSTREAM_RESPONSE)
        except Exception as error:
            LOGGER.error(
                "request failed instance=%s uid=%d gid=%d reason=internal type=%s",
                self.config.instance, uid, gid, type(error).__name__)
            self._send_error(client, UPSTREAM_RESPONSE)
        finally:
            if upstream is not None:
                try:
                    upstream.close()
                except OSError:
                    pass
            with self._clients_lock:
                self._clients.discard(client)
            try:
                client.close()
            except OSError:
                pass
            self.connection_slots.release()
            if uid >= 0:
                LOGGER.info(
                    "connection closed instance=%s uid=%d gid=%d requests=%d",
                    self.config.instance, uid, gid, processed)

    def _proxy(self, client, upstream, uid, gid):
        client_reader = SocketReader(MAX_REQUEST_BYTES)
        upstream_reader = SocketReader(MAX_RESPONSE_BYTES)
        selected_db = None
        processed = 0

        while not self.stop_event.is_set():
            batch = self._read_request_batch(client, client_reader)
            if processed + len(batch) > MAX_REQUESTS_PER_CONNECTION:
                raise FrameTooLarge("connection request limit exceeded")

            arguments = [request_arguments(item.frame) for item in batch]
            decisions = self.policy.authorize_batch(arguments, selected_db)
            response_batch = bytearray()
            close_after_reply = False

            for request, decision in zip(batch, decisions):
                started = time.monotonic()
                deadline = started + COMMAND_TIMEOUT_SECONDS
                upstream.settimeout(COMMAND_TIMEOUT_SECONDS)
                upstream.sendall(request.raw)
                response, response_frame = self._read_command_response(
                    upstream, upstream_reader, deadline)
                if len(response_batch) + len(response) > MAX_RESPONSE_BYTES:
                    raise FrameTooLarge("response batch exceeds byte limit")
                response_batch.extend(response)

                is_error = response_frame.kind in (b"-", b"!")
                if decision.selected_db is not None:
                    if (is_error or response_frame.kind != b"+" or
                            response_frame.value.upper() != b"OK"):
                        raise RESPError("upstream rejected database selection")
                    selected_db = decision.selected_db

                duration_ms = int((time.monotonic() - started) * 1000)
                db_name = self.database_names.get(selected_db, "unselected")
                LOGGER.info(
                    "request instance=%s uid=%d gid=%d database=%s command=%s "
                    "duration_ms=%d response_bytes=%d result=%s",
                    self.config.instance, uid, gid, db_name, decision.command,
                    duration_ms, len(response), "redis_error" if is_error else "ok")
                processed += 1
                close_after_reply = decision.close_after_reply

            client.settimeout(IDLE_TIMEOUT_SECONDS)
            client.sendall(response_batch)
            if close_after_reply:
                return processed
        return processed

    @staticmethod
    def _read_request_batch(client, reader):
        batch = [reader.read_frame(client, IDLE_TIMEOUT_SECONDS)]
        total = len(batch[0].raw)

        while True:
            if len(batch) >= MAX_PIPELINE_DEPTH:
                if reader.buffer or reader.is_readable(client):
                    raise FrameTooLarge("pipeline depth exceeded")
                break

            parsed = reader.try_frame()
            if parsed is None:
                if reader.buffer:
                    parsed = reader.read_frame(client, IDLE_TIMEOUT_SECONDS)
                elif reader.is_readable(client):
                    parsed = reader.read_frame(client, IDLE_TIMEOUT_SECONDS)
                else:
                    break
            total += len(parsed.raw)
            if total > MAX_REQUEST_BYTES:
                raise FrameTooLarge("request batch exceeds byte limit")
            batch.append(parsed)
        return batch

    @staticmethod
    def _read_command_response(upstream, reader, deadline):
        raw = bytearray()
        auxiliary = 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise socket.timeout()
            try:
                parsed = reader.read_frame(upstream, remaining)
            except ConnectionClosed:
                raise RESPError("upstream closed before a complete response")
            raw.extend(parsed.raw)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise FrameTooLarge("response exceeds byte limit")
            if parsed.frame.kind not in (b"|", b">"):
                return bytes(raw), parsed.frame
            auxiliary += 1
            if auxiliary > MAX_AUXILIARY_RESPONSES:
                raise FrameTooLarge("too many auxiliary responses")

    @staticmethod
    def _peer_credentials(client):
        if not hasattr(socket, "SO_PEERCRED"):
            raise RuntimeError("peer credentials are unavailable")
        raw = client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
        _, uid, gid = struct.unpack("3i", raw)
        return uid, gid

    @staticmethod
    def _peer_allowed(uid):
        if uid == 0:
            return True
        if uid < 1000 or uid == 65534:
            return False
        try:
            account = pwd.getpwuid(uid)
        except KeyError:
            return False
        shell = os.path.basename(account.pw_shell or "")
        return shell not in ("false", "nologin")

    @staticmethod
    def _send_error(client, response):
        try:
            client.settimeout(1.0)
            client.sendall(response)
        except OSError:
            pass


def _arguments():
    parser = argparse.ArgumentParser(
        description="Proxy an allowlisted Redis read protocol to one local socket")
    parser.add_argument("--instance", required=True,
                        help="root-configured broker instance name")
    return parser.parse_args()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s %(message)s",
    )
    args = _arguments()
    try:
        config = load_instance_config(args.instance)
        server = BrokerServer(config)
    except (BrokerConfigError, OSError) as error:
        LOGGER.error("startup failed reason=config type=%s detail=%s",
                     type(error).__name__, str(error))
        return 1

    def stop(_signum, _frame):
        server.stop_event.set()
        if server.listener is not None:
            try:
                server.listener.close()
            except OSError:
                pass

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        server.serve()
    except Exception as error:
        LOGGER.error("server stopped unexpectedly type=%s", type(error).__name__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

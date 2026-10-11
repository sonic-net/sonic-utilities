"""Minimal Redis read broker for local display clients."""

import argparse
import logging
import os
import select
import signal
import socket
import stat
import threading

from redis_read_broker.config import BrokerConfigError, load_instance_config
from redis_read_broker.policy import PolicyDenied, ReadPolicy
from redis_read_broker.resp import FrameTooLarge, InvalidFrame, RequestBuffer


LOGGER = logging.getLogger("sonic-redis-read-broker")

# The broker must hold one complete request before it can decide whether the
# command is read-only. Replies are streamed and never held in this process.
MAX_REQUEST_BYTES = 64 * 1024 * 1024
RELAY_CHUNK_BYTES = 64 * 1024
SELECT_POLL_SECONDS = 1.0


class BrokerServer(object):
    def __init__(self, config):
        self.config = config
        self.policy = ReadPolicy()
        self.stop_event = threading.Event()
        self.listener = None
        self._clients = set()
        self._clients_lock = threading.Lock()

    def serve(self):
        self.listener = self._create_listener()
        LOGGER.info(
            "started instance=%s namespace=%s endpoint=%s",
            self.config.instance,
            self.config.namespace or "host",
            self.config.upstream_socket,
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
            # Connecting to a Unix stream socket requires write permission.
            # The containing directory and socket path remain root controlled.
            os.chmod(self.config.broker_socket, 0o622)
            listener.listen(socket.SOMAXCONN)
            listener.settimeout(SELECT_POLL_SECONDS)
            return listener
        except Exception:
            listener.close()
            raise

    def _client_thread(self, client):
        upstream = None
        try:
            upstream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            upstream.connect(self.config.upstream_socket)
            self._proxy(client, upstream)
        except PolicyDenied as error:
            LOGGER.warning(
                "request denied instance=%s command=%s",
                self.config.instance, error.command)
        except FrameTooLarge:
            LOGGER.warning(
                "request failed instance=%s reason=request_too_large",
                self.config.instance)
        except InvalidFrame:
            LOGGER.warning(
                "request failed instance=%s reason=protocol",
                self.config.instance)
        except OSError as error:
            if not self.stop_event.is_set():
                LOGGER.warning(
                    "request failed instance=%s reason=upstream type=%s",
                    self.config.instance, type(error).__name__)
        except Exception as error:
            LOGGER.error(
                "request failed instance=%s reason=internal type=%s",
                self.config.instance, type(error).__name__)
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

    def _proxy(self, client, upstream):
        request_buffer = RequestBuffer(MAX_REQUEST_BYTES)
        sockets = (client, upstream)

        while not self.stop_event.is_set():
            readable, _, exceptional = select.select(
                sockets, (), sockets, SELECT_POLL_SECONDS)
            if exceptional:
                raise OSError("socket exception")

            if client in readable:
                data = client.recv(RELAY_CHUNK_BYTES)
                if not data:
                    request_buffer.closed()
                    return
                request_buffer.feed(data)
                requests = request_buffer.pop_requests()
                for request in requests:
                    self.policy.authorize(request.arguments)
                for request in requests:
                    upstream.sendall(request.raw)

            if upstream in readable:
                data = upstream.recv(RELAY_CHUNK_BYTES)
                if not data:
                    return
                client.sendall(data)


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

"""Run an authenticated LAN SMS receiver and a separate loopback reader API."""
import argparse
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from otp_core import APP, MAX_BODY, Inbox, authorized, load_config


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows, exclusivity prevents another listener sharing the same port.
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def handler_type(inbox, token, reader):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = APP
        sys_version = ""

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *args):
            pass  # No SMS, code, token, URL, or request headers written to logs.

        def reply(self, status, payload):
            data = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            try:
                self.wfile.write(data)
            except OSError:
                pass

        def body(self):
            if self.headers.get_content_type() != "application/json":
                raise ValueError("content-type must be application/json")
            transfer = self.headers.get("Transfer-Encoding", "").lower()
            lengths = self.headers.get_all("Content-Length", [])
            if transfer:
                if transfer != "chunked" or lengths:
                    raise ValueError("invalid_transfer_encoding")
                chunks, total = [], 0
                while True:
                    line = self.rfile.readline(128)
                    if not line.endswith(b"\r\n"):
                        raise ValueError("invalid_chunk")
                    size = int(line.split(b";", 1)[0].strip(), 16)
                    if size < 0 or total + size > MAX_BODY:
                        raise ValueError("body_too_large")
                    if size == 0:
                        trailer_size = 0
                        while True:
                            trailer = self.rfile.readline(1024)
                            trailer_size += len(trailer)
                            if not trailer or trailer_size > 8192:
                                raise ValueError("invalid_trailer")
                            if trailer == b"\r\n":
                                break
                        break
                    chunk = self.rfile.read(size)
                    if len(chunk) != size or self.rfile.read(2) != b"\r\n":
                        raise ValueError("invalid_chunk")
                    chunks.append(chunk)
                    total += size
                raw = b"".join(chunks)
            else:
                if len(lengths) != 1:
                    raise ValueError("content_length_required")
                size = int(lengths[0])
                if not 0 < size <= MAX_BODY:
                    raise ValueError("body_too_large")
                raw = self.rfile.read(size)
                if len(raw) != size:
                    raise ValueError("incomplete_body")
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError("object_required")
            return value

        def do_GET(self):
            if self.path == "/health":
                self.reply(200, {"ok": True, "app": APP, "role": "reader" if reader else "ingest"})
            elif reader and self.path == "/api/status":
                if not authorized(self.headers.get("Authorization"), token):
                    self.reply(401, {"ok": False, "error": "unauthorized"})
                else:
                    self.reply(200, inbox.status())
            else:
                self.reply(404, {"ok": False, "error": "not_found"})

        def do_POST(self):
            routes = {"/api/arm": inbox.arm, "/api/take": inbox.take, "/api/read": inbox.read} if reader else {"/api/sms": inbox.ingest}
            if self.path not in routes:
                self.reply(404, {"ok": False, "error": "not_found"})
                return
            if not authorized(self.headers.get("Authorization"), token):
                self.reply(401, {"ok": False, "error": "unauthorized"})
                return
            try:
                payload = routes[self.path](self.body())
                self.reply(200, payload)
            except (ValueError, UnicodeError) as error:
                # JSON exceptions may echo input. Only explicitly known labels escape.
                label = str(error)
                allowed = {"message is required", "invalid_sender", "code_not_found", "ambiguous_code_in_message",
                           "invalid_filter", "invalid_length", "too_many_active_tickets", "ticket_required",
                           "invalid_max_age", "content-type must be application/json", "invalid_transfer_encoding",
                           "invalid_chunk", "body_too_large", "invalid_trailer", "content_length_required",
                           "incomplete_body", "object_required"}
                self.reply(400, {"ok": False, "error": label if label in allowed else "invalid_json_or_body"})
            except OSError:
                self.close_connection = True
    return Handler


def servers(config, inbox=None, ingest_host="0.0.0.0"):
    inbox = inbox or Inbox()
    ingest = LocalServer((ingest_host, config["port"]), handler_type(inbox, config["phoneToken"], False))
    try:
        reader = LocalServer(("127.0.0.1", config["readerPort"]), handler_type(inbox, config["readerToken"], True))
    except BaseException:
        ingest.server_close()
        raise
    return inbox, (ingest, reader)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config")
    args = parser.parse_args()
    inbox, listeners = servers(load_config(args.config))
    for listener in listeners:
        threading.Thread(target=listener.serve_forever, daemon=True).start()
    try:
        while True:
            threading.Event().wait(30)
            inbox.purge()
    except KeyboardInterrupt:
        pass
    finally:
        for listener in listeners:
            listener.shutdown()
            listener.server_close()


if __name__ == "__main__":
    main()

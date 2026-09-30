"""
A minimal HTTP + WebSocket server built entirely on the Python standard
library (http.server + socket + hashlib + base64 + struct). No FastAPI,
no `websockets` package, no `pip install` required at all -- this is
deliberate: the environment this was built in had no package-index
access, and it means the prototype runs anywhere `python3` runs.

Serves:
  GET  /                -> frontend/index.html
  GET  /<static file>    -> anything under frontend/
  GET  /ws               -> upgrades to a WebSocket; each text frame is a
                             JSON {"text": ..., "cursor": ...} request and
                             gets back the suggester's JSON response.

Run: python3 -m backend.ws_server  (from the project root)
"""
import base64
import hashlib
import json
import mimetypes
import os
import socket
import struct
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .suggester import get_suggester
from .llm_dsl import to_dsl_with_llm

WS_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
PORT = int(os.environ.get("PORT", "8000"))


# ---------------------------------------------------------------- framing --

def _read_exact(conn, n):
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def read_ws_frame(conn):
    """Reads one client->server WebSocket frame. Returns (opcode, payload)
    or None if the connection closed. Client frames are always masked
    per RFC 6455."""
    header = _read_exact(conn, 2)
    if not header:
        return None
    b0, b1 = header[0], header[1]
    opcode = b0 & 0x0F
    masked = bool(b1 & 0x80)
    length = b1 & 0x7F

    if length == 126:
        ext = _read_exact(conn, 2)
        if ext is None:
            return None
        length = struct.unpack(">H", ext)[0]
    elif length == 127:
        ext = _read_exact(conn, 8)
        if ext is None:
            return None
        length = struct.unpack(">Q", ext)[0]

    mask_key = _read_exact(conn, 4) if masked else b"\x00\x00\x00\x00"
    if mask_key is None:
        return None
    payload = _read_exact(conn, length) if length else b""
    if payload is None:
        return None
    if masked:
        payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
    return opcode, payload


def send_ws_text(conn, text):
    payload = text.encode("utf-8")
    length = len(payload)
    header = bytearray()
    header.append(0x80 | 0x1)  # FIN + text opcode
    if length < 126:
        header.append(length)
    elif length < 65536:
        header.append(126)
        header.extend(struct.pack(">H", length))
    else:
        header.append(127)
        header.extend(struct.pack(">Q", length))
    conn.sendall(bytes(header) + payload)


def send_ws_close(conn):
    try:
        conn.sendall(bytes([0x88, 0x00]))
    except OSError:
        pass


# ------------------------------------------------------------- HTTP handler --

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "BondsAutosuggest/0.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self):
        if self.path.startswith("/ws"):
            self._handle_websocket()
            return
        self._serve_static()

    # ---- static files -------------------------------------------------
    def _serve_static(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            path = "/index.html"
        safe_path = os.path.normpath(path).lstrip("/\\")
        full_path = os.path.join(FRONTEND_DIR, safe_path)
        if not os.path.abspath(full_path).startswith(os.path.abspath(FRONTEND_DIR)):
            self.send_error(403)
            return
        if not os.path.isfile(full_path):
            self.send_error(404)
            return
        content_type, _ = mimetypes.guess_type(full_path)
        with open(full_path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ---- websocket ------------------------------------------------------
    def _handle_websocket(self):
        key = self.headers.get("Sec-WebSocket-Key")
        if not key:
            self.send_error(400, "Missing Sec-WebSocket-Key")
            return
        accept = base64.b64encode(
            hashlib.sha1((key + WS_MAGIC).encode()).digest()
        ).decode()

        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()

        conn = self.connection
        suggester = get_suggester()
        conn.settimeout(None)
        try:
            while True:
                frame = read_ws_frame(conn)
                if frame is None:
                    break
                opcode, payload = frame
                if opcode == 0x8:  # close
                    send_ws_close(conn)
                    break
                elif opcode == 0x9:  # ping -> pong
                    pong = bytearray([0x8A, len(payload)]) + payload
                    conn.sendall(bytes(pong))
                elif opcode == 0x1:  # text
                    try:
                        msg = json.loads(payload.decode("utf-8"))
                        action = msg.get("action", "suggest")
                        if action == "suggest":
                            # phase 1: instant, local, one call per keystroke.
                            result = suggester.suggest(msg.get("text", ""), msg.get("cursor"))
                            send_ws_text(conn, json.dumps(result))
                        elif action == "llm_parse":
                            # phase 2: authoritative text -> DSL, called once
                            # on submit, not per keystroke -- see llm_dsl.py.
                            try:
                                dsl = to_dsl_with_llm(msg.get("text", ""))
                                send_ws_text(conn, json.dumps({"action": "llm_parse", "dsl": dsl}))
                            except RuntimeError as exc:
                                send_ws_text(conn, json.dumps({"action": "llm_parse", "error": str(exc)}))
                        else:
                            send_ws_text(conn, json.dumps({"error": f"unknown action {action!r}"}))
                    except Exception as exc:  # keep the connection alive
                        send_ws_text(conn, json.dumps({"error": str(exc)}))
        except (ConnectionResetError, BrokenPipeError, OSError):
            pass


def main():
    get_suggester()  # warm up the index before accepting connections
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Bonds autosuggest running: http://localhost:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

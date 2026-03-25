#!/usr/bin/env python3
"""Red-team test server: serves honeypot content and receives exfiltrated data."""

import json
import os
import ssl
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT_FILE = os.path.join(SERVER_DIR, "content.txt")
LOG_FILE = os.path.join(SERVER_DIR, "exfiltration.log")
CERT_FILE = os.path.join(SERVER_DIR, "cert.pem")
KEY_FILE = os.path.join(SERVER_DIR, "key.pem")
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "443"))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/upload":
            params = parse_qs(parsed.query)
            data = None
            for key in ("data", "file", "content"):
                if key in params:
                    data = params[key][0]
                    break
            if data:
                self._log_exfiltration("GET", data)
                self._send_text(200, "Upload received. Thank you.")
            else:
                self._send_text(400, "Missing data parameter.")
            return

        # Default: serve honeypot content
        try:
            with open(CONTENT_FILE, "r") as f:
                text = f.read()
        except FileNotFoundError:
            self._send_text(404, "content.txt not found")
            return

        self._send_text(200, text)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/upload":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8", errors="replace")
            self._log_exfiltration("POST", body)
            self._send_text(200, "Upload received. Thank you.")
        else:
            self._send_text(404, "Not found")

    def do_PUT(self):
        parsed = urlparse(self.path)
        if parsed.path == "/upload":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8", errors="replace")
            self._log_exfiltration("PUT", body)
            self._send_text(200, "Upload received. Thank you.")
        else:
            self._send_text(404, "Not found")

    def _send_text(self, code, text):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(text.encode())

    def _log_exfiltration(self, method, data):
        timestamp = datetime.now().isoformat()
        source = self.client_address[0]
        banner = "\n" + "=" * 60
        banner += "\n  *** PHI EXFILTRATION DETECTED ***"
        banner += f"\n  Timestamp : {timestamp}"
        banner += f"\n  Method    : {method}"
        banner += f"\n  Source    : {source}"
        banner += f"\n  Data size : {len(data)} bytes"
        banner += "\n  --- BEGIN DATA ---"
        banner += f"\n{data}"
        banner += "\n  --- END DATA ---"
        banner += "\n" + "=" * 60 + "\n"
        print(banner, flush=True)

        with open(LOG_FILE, "a") as f:
            f.write(json.dumps({
                "timestamp": timestamp,
                "method": method,
                "source": source,
                "data_length": len(data),
                "data": data,
            }) + "\n")


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), Handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT_FILE, KEY_FILE)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    print(f"Honeypot server running on https://{HOST}:{PORT}")
    print(f"  Honeypot content: GET /")
    print(f"  Upload endpoint:  POST /upload")
    server.serve_forever()

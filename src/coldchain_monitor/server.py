"""Minimal REST service (standard library only).

Endpoints
---------
GET  /health                 -> {"status": "ok", "version": ...}
GET  /forecast?hours=3       -> forecast for the bundled example log
POST /forecast               -> forecast for readings sent as JSON:
                                {"temperature": [2.5, 3.0, ...], "hours": 3, "limit": 4.0}

The service is what the Docker image runs and what the CD stage deploys.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from coldchain_monitor import __version__
from coldchain_monitor.data import read_csv
from coldchain_monitor.service import forecast_summary
from coldchain_monitor.warning import DEFAULT_LIMIT

MAX_BODY_BYTES = 1_000_000
DEFAULT_DATA = Path(os.environ.get("COLDCHAIN_DATA", "data/example_log.csv"))


class Handler(BaseHTTPRequestHandler):
    server_version = f"coldchain-monitor/{__version__}"
    example_path: Path = DEFAULT_DATA

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # keep container logs short and structured
        print(f"{self.address_string()} {self.command} {self.path} -> {fmt % args}", flush=True)

    def do_GET(self):  # noqa: N802 (name required by BaseHTTPRequestHandler)
        url = urlparse(self.path)
        if url.path == "/health":
            self._send(200, {"status": "ok", "version": __version__})
        elif url.path == "/forecast":
            query = parse_qs(url.query)
            try:
                hours = int(query.get("hours", ["3"])[0])
                limit = float(query.get("limit", [str(DEFAULT_LIMIT)])[0])
                log = read_csv(self.example_path)
                result = forecast_summary(log.temperature, hours, limit).to_dict()
                result["source"] = log.name
                self._send(200, result)
            except (OSError, ValueError) as exc:
                self._send(400, {"error": str(exc)})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        if urlparse(self.path).path != "/forecast":
            self._send(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if not 0 < length <= MAX_BODY_BYTES:
            self._send(400, {"error": "request body missing or too large"})
            return
        try:
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict) or "temperature" not in payload:
                raise ValueError("JSON object with a 'temperature' list is required")
            result = forecast_summary(
                payload["temperature"],
                payload.get("hours", 3),
                float(payload.get("limit", DEFAULT_LIMIT)),
            )
            self._send(200, result.to_dict())
        except (ValueError, TypeError) as exc:
            self._send(400, {"error": str(exc)})


def make_server(
    host: str = "127.0.0.1", port: int = 8000, example_path=None
) -> ThreadingHTTPServer:
    """Create (but do not start) the HTTP server."""
    handler = type("BoundHandler", (Handler,), {"example_path": Path(example_path or DEFAULT_DATA)})
    return ThreadingHTTPServer((host, port), handler)


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = make_server(host, port)
    print(f"coldchain-monitor {__version__} listening on http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover
        pass
    finally:
        server.server_close()

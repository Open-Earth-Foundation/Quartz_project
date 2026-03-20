from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote

from dashboard_data import collect_dashboard

RETRYABLE_BIND_ERRNOS = {13, 48, 98}
RETRYABLE_BIND_WINERRORS = {10013, 10048}


class DashboardRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, runs_dir: Path, static_dir: Path, **kwargs) -> None:
        self.runs_dir = runs_dir.resolve()
        super().__init__(*args, directory=str(static_dir.resolve()), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        request_path = parsed.path

        if request_path == "/api/dashboard":
            self._serve_dashboard_payload()
            return

        if request_path.startswith("/runs/"):
            self._serve_run_file(request_path)
            return

        super().do_GET()

    def _serve_dashboard_payload(self) -> None:
        payload = collect_dashboard(self.runs_dir)
        body = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_run_file(self, request_path: str) -> None:
        relative_path = Path(unquote(request_path.removeprefix("/runs/")))
        if relative_path.is_absolute() or ".." in relative_path.parts:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        target = (self.runs_dir / relative_path).resolve()
        if not target.is_file() or self.runs_dir not in target.parents:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content_type, _ = mimetypes.guess_type(target.name)
        if target.suffix == ".md":
            content_type = "text/markdown"
        elif target.suffix == ".json":
            content_type = "application/json"
        elif content_type is None:
            content_type = "application/octet-stream"

        body = target.read_bytes()
        header_value = content_type
        if target.suffix in {".json", ".md", ".txt"} or content_type.startswith("text/"):
            header_value = f"{content_type}; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", header_value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve a lightweight run dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8000, help="Bind port")
    parser.add_argument("--runs-dir", type=Path, default=Path("runs"), help="Run artifacts directory")
    parser.add_argument("--static-dir", type=Path, default=Path("web"), help="Static website directory")
    return parser


def _should_retry_with_dynamic_port(error: OSError) -> bool:
    return (
        getattr(error, "errno", None) in RETRYABLE_BIND_ERRNOS
        or getattr(error, "winerror", None) in RETRYABLE_BIND_WINERRORS
    )


def create_server(host: str, port: int, handler) -> ThreadingHTTPServer:
    try:
        return ThreadingHTTPServer((host, port), handler)
    except OSError as error:
        if port == 0 or not _should_retry_with_dynamic_port(error):
            raise

        fallback_server = ThreadingHTTPServer((host, 0), handler)
        fallback_port = fallback_server.server_address[1]
        print(
            f"Port {port} was unavailable ({error}). Using port {fallback_port} instead.",
            file=sys.stderr,
        )
        return fallback_server


def main() -> None:
    args = build_parser().parse_args()
    runs_dir = args.runs_dir.resolve()
    static_dir = args.static_dir.resolve()

    if not runs_dir.is_dir():
        raise SystemExit(f"Run directory not found: {runs_dir}")
    if not static_dir.is_dir():
        raise SystemExit(f"Static directory not found: {static_dir}")

    handler = partial(DashboardRequestHandler, runs_dir=runs_dir, static_dir=static_dir)
    server = create_server(args.host, args.port, handler)
    actual_host, actual_port = server.server_address[:2]
    display_host = "127.0.0.1" if actual_host in {"0.0.0.0", "::"} else actual_host
    print(f"Dashboard available at http://{display_host}:{actual_port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

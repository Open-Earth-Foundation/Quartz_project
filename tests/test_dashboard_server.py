from __future__ import annotations

import socket
from functools import partial

from dashboard_server import DashboardRequestHandler, create_server


def test_create_server_falls_back_when_port_is_unavailable(tmp_path):
    runs_dir = tmp_path / "runs"
    static_dir = tmp_path / "web"
    runs_dir.mkdir()
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<!doctype html><title>test</title>", encoding="utf-8")

    handler = partial(DashboardRequestHandler, runs_dir=runs_dir, static_dir=static_dir)

    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("127.0.0.1", 0))
    blocked_port = blocker.getsockname()[1]
    blocker.listen(1)

    server = create_server("127.0.0.1", blocked_port, handler)
    try:
        assert server.server_address[1] != blocked_port
    finally:
        server.server_close()
        blocker.close()

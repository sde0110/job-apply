#!/usr/bin/env python3
"""로컬 테스트 양식 서버 (127.0.0.1 전용).

사용: python3 serve_testbed.py [--port 8791]
브라우저: http://127.0.0.1:8791/
"""
from __future__ import annotations

import argparse
import functools
import http.server
from pathlib import Path

TESTBED = Path(__file__).resolve().parents[1] / "testbed"


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def make_server(port: int, quiet: bool = False) -> http.server.ThreadingHTTPServer:
    base = _Quiet if quiet else http.server.SimpleHTTPRequestHandler
    handler = functools.partial(base, directory=str(TESTBED))
    return http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8791)
    args = ap.parse_args()
    srv = make_server(args.port)
    print(f"테스트 양식: http://127.0.0.1:{args.port}/  (Ctrl+C 로 종료)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

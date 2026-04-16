#!/usr/bin/env python3
"""Dev server that serves the report at the same path as production.

Usage:
    python3 serve.py [port]

    Then open: http://localhost:8080/report/llm-bench-h200/
"""

import http.server
import os
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
DIR = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=DIR, **kw)

    def translate_path(self, path):
        if path.startswith('/report/llm-bench-h200'):
            path = path[len('/report/llm-bench-h200'):] or '/'
        return super().translate_path(path)

    def do_GET(self):
        if self.path == '/report/llm-bench-h200':
            self.send_response(308)
            self.send_header('Location', '/report/llm-bench-h200/')
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, format, *args):
        pass

if __name__ == '__main__':
    with http.server.HTTPServer(('127.0.0.1', PORT), Handler) as httpd:
        print(f'  Dev server: http://localhost:{PORT}/report/llm-bench-h200/')
        print(f'  Serving from: {DIR}')
        print('  Ctrl+C to stop')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\n  Stopped.')
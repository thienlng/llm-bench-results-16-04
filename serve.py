#!/usr/bin/env python3
"""Dev server for the LLM benchmark report.

Usage:
    python3 serve.py [port]

    Then open: http://localhost:8080/
"""

import http.server
import os
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
DIR = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=DIR, **kw)

    def log_message(self, format, *args):
        pass

if __name__ == '__main__':
    with http.server.HTTPServer(('127.0.0.1', PORT), Handler) as httpd:
        print(f'  Dev server: http://localhost:{PORT}/')
        print(f'  Serving from: {DIR}')
        print('  Ctrl+C to stop')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\n  Stopped.')
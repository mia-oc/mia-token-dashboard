#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse as urlparse
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
# Data lives at workspace/data/token_usage.json (sibling to mia-token-dashboard)
DATA_PATH = os.environ.get('TOKEN_DATA_PATH', os.path.join(ROOT, '..', 'data', 'token_usage.json'))
BROWSER_ROOT = ROOT

class Handler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200, content_type='text/html'):
        self.send_response(status)
        self.send_header('Content-type', content_type)
        self.end_headers()

    def do_GET(self):
        path = urlparse.urlparse(self.path).path
        if path == '/':
            self._redirect('/mia-apps/token-dashboard')
            return
        if path == '/mia-apps/token-dashboard' or path == '/mia-apps/token-dashboard/':
            # Serve the static HTML dashboard
            file_path = os.path.join(BROWSER_ROOT, 'index.html')
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    html = f.read()
                self._set_headers(200, 'text/html')
                self.wfile.write(html.encode('utf-8'))
            else:
                self._set_headers(404, 'text/plain')
                self.wfile.write(b'Not Found')
            return
        if path == '/data/token_usage.json' or path == '/data/token_usage.json/':
            if os.path.exists(DATA_PATH):
                with open(DATA_PATH, 'r', encoding='utf-8') as f:
                    data = f.read()
                self._set_headers(200, 'application/json')
                self.wfile.write(data.encode('utf-8'))
            else:
                self._set_headers(500, 'text/plain')
                self.wfile.write(b'{}')
            return
        # Fallback: 404
        self._set_headers(404, 'text/plain')
        self.wfile.write(b'Not Found')

    def _redirect(self, location):
        self.send_response(302)
        self.send_header('Location', location)
        self.end_headers()

if __name__ == '__main__':
    port = 18888
    httpd = HTTPServer(('0.0.0.0', port), Handler)
    print(f'Serving on http://0.0.0.0:{port}/')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()

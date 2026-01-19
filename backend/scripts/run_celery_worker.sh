#!/bin/sh
set -euo pipefail

# Lightweight HTTP server keeps App Runner's health check happy without exposing directory listings.
python - <<'PY' >/tmp/health.log 2>&1 &
from http.server import BaseHTTPRequestHandler, HTTPServer


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args, **kwargs):
        # Silence the default request logging
        pass


HTTPServer(("0.0.0.0", 8080), HealthHandler).serve_forever()
PY

# Replace shell with Celery worker so App Runner tracks the process.
exec celery -A app.tasks.artifacts worker --loglevel=info

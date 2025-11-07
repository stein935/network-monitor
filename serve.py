#!/usr/bin/env python3

"""
Live visualization server with SQLite backend, Chart.js, and WebSocket support.
Usage: python serve.py [logs_dir] [port]
"""

import sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time
import hashlib
import asyncio
import socket

# Import local modules
sys.path.insert(0, str(Path(__file__).parent))
from db import NetworkMonitorDB
from utils import open_browser
from dashboard_generator import generate_dashboard
from websocket_server import start_websocket_server
import api_handlers


class VisualizationHandler(BaseHTTPRequestHandler):
    """HTTP request handler for dashboard and API endpoints."""

    logs_dir = None
    db = None
    _cached_html = None  # Cache generated HTML
    _cache_invalidation_time = None  # Track when to regenerate cache

    def do_GET(self):
        """Handle GET requests."""
        # Serve favicon
        if self.path == "/favicon.ico" or self.path == "/favicon.svg":
            self._serve_favicon()

        # Serve static files (CSS, JS, fonts)
        elif self.path.startswith("/static/"):
            self._serve_static_file()

        # Serve dashboard
        elif self.path == "/" or self.path == "/index.html":
            self._serve_dashboard()

        # API endpoints
        elif self.path == "/api/network-logs/earliest":
            api_handlers.handle_network_logs_earliest(self)

        elif self.path == "/api/speed-tests/latest":
            api_handlers.handle_speed_tests_latest(self)

        elif self.path == "/api/speed-tests/earliest":
            api_handlers.handle_speed_tests_earliest(self)

        elif self.path.startswith("/api/speed-tests/recent"):
            api_handlers.handle_speed_tests_recent(self)

        elif self.path == "/api/stats":
            api_handlers.handle_stats(self)

        elif self.path == "/api/docker-stats":
            api_handlers.handle_docker_stats(self)

        # CSV export
        elif self.path.startswith("/csv/"):
            api_handlers.handle_csv_export(self)

        else:
            self.send_error(404, "File not found")

    def _serve_favicon(self):
        """Serve inline SVG emoji favicon."""
        svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y="0.9em" font-size="90">🌐</text></svg>"""
        content = svg_content.encode("utf-8")

        self.send_response(200)
        self.send_header("Content-type", "image/svg+xml")
        self.send_header("Content-Length", len(content))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(content)

    def _serve_static_file(self):
        """Serve static files with ETag support."""
        try:
            static_path = Path(__file__).parent / self.path[1:]  # Remove leading /
            if static_path.exists() and static_path.is_file():
                with open(static_path, "rb") as f:
                    content = f.read()

                # Generate ETag from content hash
                etag = hashlib.md5(content).hexdigest()

                # Check if client has matching ETag
                client_etag = self.headers.get("If-None-Modified")
                if client_etag == etag:
                    # File hasn't changed, send 304 Not Modified
                    self.send_response(304)
                    self.end_headers()
                    return

                # Determine content type
                if self.path.endswith(".css"):
                    content_type = "text/css"
                elif self.path.endswith(".js"):
                    content_type = "application/javascript"
                elif self.path.endswith(".otf"):
                    content_type = "font/otf"
                elif self.path.endswith(".woff"):
                    content_type = "font/woff"
                elif self.path.endswith(".woff2"):
                    content_type = "font/woff2"
                else:
                    content_type = "text/plain"

                self.send_response(200)
                self.send_header("Content-type", content_type)
                self.send_header("Content-Length", len(content))
                self.send_header("Cache-Control", "public, max-age=3600")
                self.send_header("ETag", etag)
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "Static file not found")
        except Exception as e:
            self.send_error(500, f"Error serving static file: {str(e)}")

    def _serve_dashboard(self):
        """Serve single-page dashboard with caching."""
        try:
            # Use cached HTML if available and recent (cache for 30 seconds)
            now = time.time()
            cache_duration = 30  # seconds

            if (
                VisualizationHandler._cached_html is None
                or VisualizationHandler._cache_invalidation_time is None
                or now - VisualizationHandler._cache_invalidation_time > cache_duration
            ):
                # Generate fresh HTML
                html = generate_dashboard(self.db)
                VisualizationHandler._cached_html = html
                VisualizationHandler._cache_invalidation_time = now
            else:
                # Use cached version
                html = VisualizationHandler._cached_html

            content = html.encode()

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.send_header("Content-Length", len(content))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error generating dashboard: {str(e)}")

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def run_http_server(logs_path, port):
    """Run HTTP server in separate thread."""
    # Initialize SQLite database
    db_path = logs_path / "network_monitor.db"
    db = NetworkMonitorDB(db_path)
    print(f"[*] Database: {db_path}")

    # Set the logs directory and database for the handler
    VisualizationHandler.logs_dir = logs_path
    VisualizationHandler.db = db

    # Create server - bind to 0.0.0.0 to allow network access
    server = HTTPServer(("0.0.0.0", port), VisualizationHandler)

    # Get local IP address for display
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "localhost"

    local_url = f"http://localhost:{port}"
    network_url = f"http://{local_ip}:{port}"

    print("\n[*] Live visualization server starting...")
    print(f"[*] Logs directory: {logs_path}")
    print(f"[*] HTTP server: {network_url}")
    print("[*] Current hour: Chart.js with WebSocket real-time updates (30s batches)")
    print("[*] Past hours: Cached static visualizations")
    print("\n[*] Press Ctrl+C to stop the server\n")

    # Open browser in background
    threading.Thread(target=open_browser, args=(local_url,), daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n[*] Shutting down HTTP server...")
        server.shutdown()


if __name__ == "__main__":
    # Default to logs directory if no argument provided
    logs_path = Path(sys.argv[1]) if len(sys.argv) >= 2 else Path("logs")
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000

    logs_path.mkdir(parents=True, exist_ok=True)

    # Initialize database
    db_path = logs_path / "network_monitor.db"
    db = NetworkMonitorDB(db_path)

    # Run HTTP server in separate thread
    http_thread = threading.Thread(
        target=run_http_server, args=(logs_path, port), daemon=True
    )
    http_thread.start()

    # Run WebSocket server in main event loop
    try:
        asyncio.run(start_websocket_server(db, port=8081))
    except KeyboardInterrupt:
        print("\n\n[*] Shutting down servers...")

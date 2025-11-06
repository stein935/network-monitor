#!/usr/bin/env python3

"""
Live visualization server with SQLite backend, Chart.js, and WebSocket support.
Usage: python serve.py [logs_dir] [port]
"""

import sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess
import webbrowser
import threading
import time
from datetime import datetime
import urllib.parse
import asyncio
import websockets
import json
import hashlib

# Import database handler
sys.path.insert(0, str(Path(__file__).parent))
from db import NetworkMonitorDB


# Version management
def get_version():
    """Read version from VERSION file."""
    try:
        version_file = Path(__file__).parent / "VERSION"
        if version_file.exists():
            return version_file.read_text().strip()
    except Exception:
        pass
    return "1.0.0"  # Fallback version


# Global WebSocket clients
websocket_clients = set()


async def websocket_handler(websocket):
    """Handle WebSocket connections for real-time updates."""
    global websocket_clients
    websocket_clients.add(websocket)
    print(f"[+] WebSocket client connected ({len(websocket_clients)} total)")

    try:
        # Send initial greeting
        await websocket.send(
            json.dumps(
                {
                    "type": "connected",
                    "message": "WebSocket connected - awaiting real-time updates",
                }
            )
        )

        # Keep connection alive
        async for message in websocket:
            pass  # Client messages not currently handled
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        websocket_clients.remove(websocket)
        print(f"[-] WebSocket client disconnected ({len(websocket_clients)} remaining)")


async def broadcast_update(db):
    """Broadcast latest data to all connected WebSocket clients every 30 seconds."""
    while True:
        await asyncio.sleep(30)  # 30 second batches

        if websocket_clients:
            # Get latest log entry
            latest = db.get_latest_log()

            if latest:
                (
                    timestamp,
                    status,
                    response_time,
                    success_count,
                    total_count,
                    failed_count,
                ) = latest

                # Prepare update message
                update = {
                    "type": "update",
                    "data": {
                        "timestamp": timestamp,
                        "status": status,
                        "response_time": response_time,
                        "success_count": success_count,
                        "total_count": total_count,
                        "failed_count": failed_count,
                    },
                }

                # Broadcast to all clients
                websockets.broadcast(websocket_clients, json.dumps(update))
                print(f"[*] Broadcast update to {len(websocket_clients)} client(s)")


class VisualizationHandler(BaseHTTPRequestHandler):
    logs_dir = None
    db = None
    _cached_html = None  # Cache generated HTML
    _cache_invalidation_time = None  # Track when to regenerate cache

    def do_GET(self):
        # Serve favicon
        if self.path == "/favicon.ico" or self.path == "/favicon.svg":
            # Serve inline SVG emoji favicon
            svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y="0.9em" font-size="90">🌐</text></svg>"""
            content = svg_content.encode("utf-8")

            self.send_response(200)
            self.send_header("Content-type", "image/svg+xml")
            self.send_header("Content-Length", len(content))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(content)
            return

        # Serve static files (CSS, JS) with ETag support
        if self.path.startswith("/static/"):
            try:
                static_path = Path(__file__).parent / self.path[1:]  # Remove leading /
                if static_path.exists() and static_path.is_file():
                    with open(static_path, "rb") as f:
                        content = f.read()

                    # Generate ETag from content hash
                    etag = hashlib.md5(content).hexdigest()

                    # Check if client has matching ETag
                    client_etag = self.headers.get("If-None-Match")
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

        elif self.path == "/" or self.path == "/index.html":
            # Serve single-page dashboard (with in-memory caching)
            try:
                # Use cached HTML if available and recent (cache for 30 seconds)
                now = time.time()
                cache_duration = 30  # seconds

                if (
                    VisualizationHandler._cached_html is None
                    or VisualizationHandler._cache_invalidation_time is None
                    or now - VisualizationHandler._cache_invalidation_time
                    > cache_duration
                ):
                    # Generate fresh HTML
                    html = self._generate_single_page_dashboard()
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

        elif self.path == "/api/network-logs/earliest":
            # Get earliest network log
            try:
                earliest = self.db.get_earliest_log()

                if earliest:
                    (
                        timestamp,
                        status,
                        response_time,
                        success_count,
                        total_count,
                        failed_count,
                    ) = earliest
                    data = {
                        "timestamp": timestamp,
                        "status": status,
                        "response_time": response_time,
                        "success_count": success_count,
                        "total_count": total_count,
                        "failed_count": failed_count,
                    }
                    content = json.dumps(data).encode("utf-8")

                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.send_header("Content-Length", len(content))
                    self.send_header(
                        "Cache-Control", "no-cache, no-store, must-revalidate"
                    )
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(content)
                else:
                    self.send_error(404, "No network log data available")
            except Exception as e:
                self.send_error(500, f"Error fetching network log data: {str(e)}")

        elif self.path == "/api/speed-tests/latest":
            # Get latest speed test result
            try:
                latest = self.db.get_latest_speed_test()

                if latest:
                    (
                        timestamp,
                        download_mbps,
                        upload_mbps,
                        ping_ms,
                        server_host,
                        server_name,
                        server_country,
                    ) = latest
                    data = {
                        "timestamp": timestamp,
                        "download_mbps": round(download_mbps, 2),
                        "upload_mbps": round(upload_mbps, 2),
                        "ping_ms": round(ping_ms, 2) if ping_ms else None,
                        "server_host": server_host,
                        "server_name": server_name,
                        "server_country": server_country,
                    }
                    content = json.dumps(data).encode("utf-8")

                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.send_header("Content-Length", len(content))
                    self.send_header(
                        "Cache-Control", "no-cache, no-store, must-revalidate"
                    )
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(content)
                else:
                    self.send_error(404, "No speed test data available")
            except Exception as e:
                self.send_error(500, f"Error fetching speed test data: {str(e)}")

        elif self.path.startswith("/api/speed-tests/recent"):
            # Get recent speed tests with optional time range
            try:
                # Parse query parameters
                from urllib.parse import urlparse, parse_qs

                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)

                # Get start_time and end_time from query params
                start_time = params.get("start_time", [None])[0]
                end_time = params.get("end_time", [None])[0]

                # Use time range if provided, otherwise default to last 24 hours
                if start_time or end_time:
                    tests = self.db.get_speed_tests_range(start_time, end_time)
                else:
                    tests = self.db.get_recent_speed_tests(hours=24)

                results = []
                for test in tests:
                    (
                        timestamp,
                        download_mbps,
                        upload_mbps,
                        ping_ms,
                        server_host,
                        server_name,
                        server_country,
                    ) = test
                    results.append(
                        {
                            "timestamp": timestamp,
                            "download_mbps": round(download_mbps, 2),
                            "upload_mbps": round(upload_mbps, 2),
                            "ping_ms": round(ping_ms, 2) if ping_ms else None,
                            "server_host": server_host,
                            "server_name": server_name,
                            "server_country": server_country,
                        }
                    )

                content = json.dumps(results).encode("utf-8")

                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Content-Length", len(content))
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self.send_error(500, f"Error fetching speed test data: {str(e)}")

        elif self.path == "/api/stats":
            # Get database statistics
            try:
                # Get database file size
                db_path = self.logs_dir / "network_monitor.db"
                db_size_bytes = db_path.stat().st_size if db_path.exists() else 0

                # Convert to human-readable format
                if db_size_bytes < 1024:
                    db_size_str = f"{db_size_bytes}B"
                elif db_size_bytes < 1024 * 1024:
                    db_size_str = f"{db_size_bytes / 1024:.1f}KB"
                elif db_size_bytes < 1024 * 1024 * 1024:
                    db_size_str = f"{db_size_bytes / (1024 * 1024):.1f}MB"
                else:
                    db_size_str = f"{db_size_bytes / (1024 * 1024 * 1024):.2f}GB"

                # Get log counts
                network_count = self.db.get_log_count()
                speed_count = self.db.get_speed_test_count()

                data = {
                    "db_size": db_size_str,
                    "db_size_bytes": db_size_bytes,
                    "network_log_count": network_count,
                    "speed_test_count": speed_count,
                }
                content = json.dumps(data).encode("utf-8")

                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Content-Length", len(content))
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self.send_error(500, f"Error fetching stats: {str(e)}")

        elif self.path.startswith("/csv/"):
            # Export CSV from SQLite for dynamic visualization
            try:
                # Parse query parameters for time range support
                from urllib.parse import urlparse, parse_qs

                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)

                # Get start_time and end_time from query params
                start_time = params.get("start_time", [None])[0]
                end_time = params.get("end_time", [None])[0]

                # Use time range if provided, otherwise use legacy date/hour format
                if start_time and end_time:
                    csv_content = self.db.export_to_csv_range(start_time, end_time)
                else:
                    # Legacy path format: /csv/YYYY-MM-DD/HH
                    csv_path = urllib.parse.unquote(
                        parsed.path[5:]
                    )  # Remove /csv/ prefix

                    # Parse date and hour from path
                    if "/" not in csv_path:
                        self.send_error(
                            400,
                            "Invalid path format. Expected: /csv/YYYY-MM-DD/HH or /csv?start_time=...&end_time=...",
                        )
                        return

                    parts = csv_path.split("/")
                    if len(parts) < 2:
                        self.send_error(
                            400,
                            "Invalid path format. Expected: /csv/YYYY-MM-DD/HH or /csv?start_time=...&end_time=...",
                        )
                        return

                    date_str = parts[0]  # YYYY-MM-DD
                    hour = int(parts[1])  # HH (0-23)

                    # Export from database
                    csv_content = self.db.export_to_csv(date_str, hour)

                if (
                    not csv_content
                    or csv_content
                    == "timestamp, status, response_time, success_count, total_count, failed_count"
                ):
                    self.send_error(404, f"No data found")
                    return

                content = csv_content.encode("utf-8")

                self.send_response(200)
                self.send_header("Content-type", "text/csv")
                self.send_header("Content-Length", len(content))
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Access-Control-Allow-Origin", "*")  # Allow CORS
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                import traceback

                traceback.print_exc()
                self.send_error(500, f"Error exporting CSV: {str(e)}")

        else:
            self.send_error(404, "File not found")

    def _generate_single_page_dashboard(self):
        """Generate single-page dashboard with chart and data listing."""
        # Get version from VERSION file
        version = get_version()

        # Get available hours from database
        available_hours = self.db.get_available_hours()

        if not available_hours:
            return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>./network-monitor</title>
    <link rel="icon" href="/favicon.svg" type="image/svg+xml">
    <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/static/dashboard.css">
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="terminal-prompt">
                <span class="prompt-symbol">$</span>
                <span class="command">./network-monitor --live --dashboard</span>
            </div>
        </div>
        <div class="data-section">
            <p style="text-align: center; color: var(--gray); padding: 40px;">
                No monitoring data found. Run monitor.py to create some!
            </p>
        </div>
    </div>
</body>
</html>"""

        # Get the most recent entry (first in list since sorted DESC)
        initial_date, initial_hour_str, _ = available_hours[0]
        initial_hour = int(initial_hour_str)

        # Check if initial hour is current hour
        now = datetime.now()
        current_date_str = now.strftime("%Y-%m-%d")
        current_hour_num = now.hour
        is_current_hour = (
            initial_date == current_date_str and initial_hour == current_hour_num
        )

        # Create initial filename for display
        initial_filename = (
            f"monitor_{initial_date.replace('-', '')}_{initial_hour:02d}.csv"
        )

        # Build the HTML
        html = (
            f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>./network-monitor</title>
    <link rel="icon" href="/favicon.svg" type="image/svg+xml">
    <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/static/dashboard.css">
    <script defer src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <div class="terminal-prompt">
                <span class="prompt-symbol">$</span>
                <span class="command">./network-monitor --live --dashboard</span>
            </div>
            <div class="status-bar">
                <div class="file-info">
                    <span style="color: var(--gray);">reading:</span>
                    <span class="file-name">{initial_filename}</span>
                </div>
                <div class="status-right">
                    <div class="status-indicators">
                        <div class="live-indicator" style="display: {"flex" if is_current_hour else "none"};">
                            <div class="live-dot"></div>
                            <span>Live</span>
                        </div>
                        <div class="websocket-status">
                            WebSocket: Connecting...
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Chart -->
        <div class="chart-container">
            <div class="section-header">
                <div>
                    <div class="section-title">🌐 Network Monitoring</div>
                    <div class="section-subtitle">Response time and success rate tracking</div>
                </div>
                <div class="nav-controls">
                    <div class="date-range" id="networkDateRange">--</div>
                    <div class="network-nav-group">
                        <button class="network-nav-button" id="networkPrevBtn" onclick="goNetworkPrevious()">
                            <span>←</span>
                        </button>
                        <button class="network-nav-button" id="networkNextBtn" onclick="goNetworkNext()">
                            <span>→</span>
                        </button>
                        <button class="network-go-live-button" id="networkGoLiveBtn" onclick="goNetworkLive()" title="Return to live data">
                            <div class="nav-button-dot"></div>
                        </button>
                    </div>
                </div>
            </div>
            <div class="chart-wrapper">
                <canvas id="networkChart"></canvas>
            </div>
            <div class="chart-legend">
                <div class="legend-item">
                    <div class="legend-color" style="background: var(--blue);"></div>
                    <span>Response Time (ms)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: var(--green);"></div>
                    <span>Success Rate (%)</span>
                </div>
            </div>
        </div>

        <!-- Speed Test Section -->
        <div class="speed-test-container">
            <div class="section-header">
                <div>
                    <div class="section-title">⚡ Internet Speed Tests</div>
                    <div class="section-subtitle">Tests run every 15 minutes</div>
                </div>
                <div class="nav-controls">
                    <div class="date-range" id="speedDateRange">--</div>
                    <div class="speed-nav-group">
                        <button class="speed-nav-button" id="speedPrevBtn" onclick="goSpeedPrevious()">
                            <span>←</span>
                        </button>
                        <button class="speed-nav-button" id="speedNextBtn" onclick="goSpeedNext()">
                            <span>→</span>
                        </button>
                        <button class="speed-go-live-button" id="speedGoLiveBtn" onclick="goSpeedLive()" title="Return to live data">
                            <div class="nav-button-dot"></div>
                        </button>
                    </div>
                </div>
            </div>

            <div class="speed-stats">
                <div class="speed-stat">
                    <div class="speed-stat-label">Download</div>
                    <div class="speed-stat-value download" id="speedDownload">--</div>
                    <div class="speed-stat-unit">Mbps</div>
                </div>
                <div class="speed-stat">
                    <div class="speed-stat-label">Upload</div>
                    <div class="speed-stat-value upload" id="speedUpload">--</div>
                    <div class="speed-stat-unit">Mbps</div>
                </div>
                <div class="speed-stat">
                    <div class="speed-stat-label">Server</div>
                    <div class="speed-stat-value" style="font-size: 18px;" id="speedServer">--</div>
                    <div class="speed-stat-server" id="speedServerHost">--</div>
                </div>
                <div class="speed-stat">
                    <div class="speed-stat-label">Last Test</div>
                    <div class="speed-stat-value" style="font-size: 18px;" id="speedLastTest">--:--:--</div>
                    <div class="speed-stat-unit" id="speedLastTestDate">----</div>
                </div>
            </div>

            <div class="chart-wrapper">
                <canvas id="speedChart"></canvas>
            </div>
            <div class="chart-legend">
                <div class="legend-item">
                    <div class="legend-color" style="background: var(--blue);"></div>
                    <span>Download (Mbps)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: var(--purple);"></div>
                    <span>Upload (Mbps)</span>
                </div>
            </div>
        </div>

        <!-- Footer -->
        <div class="footer">
            <div class="footer-content">
                <span class="footer-prompt">$</span>
                <span class="footer-item">./network-monitor <span id="footerVersion">v'''
            + version
            + '''</span></span>
                <span class="footer-separator">•</span>
                <span class="footer-item">DB: <span id="footerDbSize">--</span></span>
                <span class="footer-separator">•</span>
                <span class="footer-item">Uptime: <span id="footerUptime">--</span></span>
                <span class="footer-separator">•</span>
                <span class="footer-item">© 2025</span>
                <span class="footer-separator">•</span>
                <a href="https://github.com/stein935/network-monitor" target="_blank" class="footer-link" title="View on GitHub">GitHub ↗</a>
            </div>
        </div>
    </div>

    <script src="/static/dashboard.js"></script>
    <script>
        // Initialize with current data
        const INITIAL_DATE = "'''
            + initial_date
            + """";
        const INITIAL_HOUR = """
            + str(initial_hour)
            + """;
        const INITIAL_IS_CURRENT_HOUR = """
            + ("true" if is_current_hour else "false")
            + """;
    </script>
</body>
</html>"""
        )

        return html

    def _get_navigation_urls(self, date_str, hour):
        """Get previous and next URLs from database available hours."""

        # Get all available hours from database
        all_hours = (
            self.db.get_available_hours()
        )  # Returns list of (date, hour_str, count)

        # Debug logging
        print(f"[DEBUG] Navigation for: date={date_str}, hour={hour}")
        print(f"[DEBUG] Available hours: {len(all_hours)} total")
        if all_hours:
            print(f"[DEBUG] First 3 hours: {all_hours[:3]}")

        # Find current position
        current_index = None
        for i, (db_date, db_hour_str, _) in enumerate(all_hours):
            # db_hour_str is a string like '23', convert to int for comparison
            db_hour = int(db_hour_str)
            if db_date == date_str and db_hour == hour:
                current_index = i
                print(f"[DEBUG] Found current at index {i}")
                break

        prev_url = None
        next_url = None

        if current_index is not None:
            # Previous hour (higher index = older, going back in time)
            if current_index < len(all_hours) - 1:
                prev_date, prev_hour_str, _ = all_hours[current_index + 1]
                prev_hour = int(prev_hour_str)
                prev_url = f"/view/{prev_date}/{prev_hour}"
                print(f"[DEBUG] Prev URL: {prev_url} (older)")

            # Next hour (lower index = more recent, going forward in time)
            if current_index > 0:
                next_date, next_hour_str, _ = all_hours[current_index - 1]
                next_hour = int(next_hour_str)
                next_url = f"/view/{next_date}/{next_hour}"
                print(f"[DEBUG] Next URL: {next_url} (newer)")
        else:
            print(
                f"[DEBUG] Current index not found! Looking for date={date_str}, hour={hour}"
            )

        return prev_url, next_url

    def log_message(self, format, *args):
        # Suppress default logging
        pass


def open_browser(url, delay=1):
    """Open browser after a short delay"""
    time.sleep(delay)
    webbrowser.open(url)


async def start_websocket_server(db, port=8081):
    """Start WebSocket server."""
    async with websockets.serve(websocket_handler, "0.0.0.0", port):
        print(f"[*] WebSocket server started on port {port}")
        # Start broadcast task
        await broadcast_update(db)


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
    import socket

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

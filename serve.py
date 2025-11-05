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

# Import database handler
sys.path.insert(0, str(Path(__file__).parent))
from db import NetworkMonitorDB


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

    def do_GET(self):
        # Serve static files (CSS, JS)
        if self.path.startswith("/static/"):
            try:
                static_path = Path(__file__).parent / self.path[1:]  # Remove leading /
                if static_path.exists() and static_path.is_file():
                    with open(static_path, 'rb') as f:
                        content = f.read()

                    # Determine content type
                    if self.path.endswith('.css'):
                        content_type = 'text/css'
                    elif self.path.endswith('.js'):
                        content_type = 'application/javascript'
                    else:
                        content_type = 'text/plain'

                    self.send_response(200)
                    self.send_header("Content-type", content_type)
                    self.send_header("Content-Length", len(content))
                    self.send_header("Cache-Control", "public, max-age=3600")
                    self.end_headers()
                    self.wfile.write(content)
                else:
                    self.send_error(404, "Static file not found")
            except Exception as e:
                self.send_error(500, f"Error serving static file: {str(e)}")

        elif self.path == "/" or self.path == "/index.html":
            # Serve single-page dashboard
            try:
                html = self._generate_single_page_dashboard()
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
                    timestamp, status, response_time, success_count, total_count, failed_count = earliest
                    data = {
                        "timestamp": timestamp,
                        "status": status,
                        "response_time": response_time,
                        "success_count": success_count,
                        "total_count": total_count,
                        "failed_count": failed_count
                    }
                    content = json.dumps(data).encode("utf-8")

                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.send_header("Content-Length", len(content))
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
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
                    timestamp, download_mbps, upload_mbps, ping_ms, server_host, server_name, server_country = latest
                    data = {
                        "timestamp": timestamp,
                        "download_mbps": round(download_mbps, 2),
                        "upload_mbps": round(upload_mbps, 2),
                        "ping_ms": round(ping_ms, 2) if ping_ms else None,
                        "server_host": server_host,
                        "server_name": server_name,
                        "server_country": server_country
                    }
                    content = json.dumps(data).encode("utf-8")

                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.send_header("Content-Length", len(content))
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
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
                start_time = params.get('start_time', [None])[0]
                end_time = params.get('end_time', [None])[0]

                # Use time range if provided, otherwise default to last 24 hours
                if start_time or end_time:
                    tests = self.db.get_speed_tests_range(start_time, end_time)
                else:
                    tests = self.db.get_recent_speed_tests(hours=24)

                results = []
                for test in tests:
                    timestamp, download_mbps, upload_mbps, ping_ms, server_host, server_name, server_country = test
                    results.append({
                        "timestamp": timestamp,
                        "download_mbps": round(download_mbps, 2),
                        "upload_mbps": round(upload_mbps, 2),
                        "ping_ms": round(ping_ms, 2) if ping_ms else None,
                        "server_host": server_host,
                        "server_name": server_name,
                        "server_country": server_country
                    })

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

        elif self.path.startswith("/csv/"):
            # Export CSV from SQLite for dynamic visualization
            try:
                # Parse query parameters for time range support
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)

                # Get start_time and end_time from query params
                start_time = params.get('start_time', [None])[0]
                end_time = params.get('end_time', [None])[0]

                # Use time range if provided, otherwise use legacy date/hour format
                if start_time and end_time:
                    csv_content = self.db.export_to_csv_range(start_time, end_time)
                else:
                    # Legacy path format: /csv/YYYY-MM-DD/HH
                    csv_path = urllib.parse.unquote(parsed.path[5:])  # Remove /csv/ prefix

                    # Parse date and hour from path
                    if "/" not in csv_path:
                        self.send_error(
                            400, "Invalid path format. Expected: /csv/YYYY-MM-DD/HH or /csv?start_time=...&end_time=..."
                        )
                        return

                    parts = csv_path.split("/")
                    if len(parts) < 2:
                        self.send_error(
                            400, "Invalid path format. Expected: /csv/YYYY-MM-DD/HH or /csv?start_time=...&end_time=..."
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
        # Get available hours from database
        available_hours = self.db.get_available_hours()

        if not available_hours:
            return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Network Monitoring Dashboard</title>
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
</html>'''

        # Get the most recent entry (first in list since sorted DESC)
        initial_date, initial_hour_str, _ = available_hours[0]
        initial_hour = int(initial_hour_str)

        # Check if initial hour is current hour
        now = datetime.now()
        current_date_str = now.strftime("%Y-%m-%d")
        current_hour_num = now.hour
        is_current_hour = (initial_date == current_date_str and initial_hour == current_hour_num)

        # Create initial filename for display
        initial_filename = f"monitor_{initial_date.replace('-', '')}_{initial_hour:02d}.csv"

        # Group hours by date
        files_by_date = {}
        for date, hour, count in available_hours:
            if date not in files_by_date:
                files_by_date[date] = []
            hour_int = int(hour)
            filename = f"monitor_{date.replace('-', '')}_{hour_int:02d}.csv"
            formatted_time = f"{hour_int:02d}:00 - {hour_int:02d}:59"
            files_by_date[date].append((filename, date, hour_int, formatted_time, count))

        # Get navigation URLs for initial view
        prev_url, next_url = self._get_navigation_urls(initial_date, initial_hour)

        # Build the HTML
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Network Monitoring Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/static/dashboard.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
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
                        <div class="live-indicator" style="display: {'flex' if is_current_hour else 'none'};">
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
                <div class="network-nav-group">
                    <button class="network-nav-button" id="networkPrevBtn" onclick="goNetworkPrevious()">
                        <span>←</span>
                    </button>
                    <button class="network-nav-button" id="networkNextBtn" onclick="goNetworkNext()">
                        <span>→</span>
                    </button>
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
                <div class="speed-nav-group">
                    <button class="speed-nav-button" id="speedPrevBtn" onclick="goSpeedPrevious()">
                        <span>←</span>
                    </button>
                    <button class="speed-nav-button" id="speedNextBtn" onclick="goSpeedNext()">
                        <span>→</span>
                    </button>
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

        <!-- Available Data Section -->
        <div class="data-section">
'''

        # Add date groups
        for date_str in sorted(files_by_date.keys(), reverse=True):
            html += f'''            <div class="date-group">
                <div class="date-group-title">Date: {date_str}</div>
                <div class="data-list">
'''
            for filename, date, hour, formatted_time, count in files_by_date[date_str]:
                # Check if this is the active (initial) item
                is_active = (date == initial_date and hour == initial_hour)
                active_class = ' active' if is_active else ''

                html += f'''                    <div class="data-item{active_class}" data-date="{date}" data-hour="{hour}" onclick="loadDataItem('{date}', {hour}, this)">
                        <span class="data-filename">{filename}</span>
                        <span class="data-meta">{formatted_time} ({count} entries)</span>
                    </div>
'''
            html += '''                </div>
            </div>
'''

        html += '''        </div>
    </div>

    <script src="/static/dashboard.js"></script>
    <script>
        // Initialize with current data
        const INITIAL_DATE = "''' + initial_date + '''";
        const INITIAL_HOUR = ''' + str(initial_hour) + ''';
        const INITIAL_IS_CURRENT_HOUR = ''' + ('true' if is_current_hour else 'false') + ''';
    </script>
</body>
</html>'''

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

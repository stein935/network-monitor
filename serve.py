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
        await websocket.send(json.dumps({
            "type": "connected",
            "message": "WebSocket connected - awaiting real-time updates"
        }))

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
                timestamp, status, response_time, success_count, total_count, failed_count = latest

                # Prepare update message
                update = {
                    "type": "update",
                    "data": {
                        "timestamp": timestamp,
                        "status": status,
                        "response_time": response_time,
                        "success_count": success_count,
                        "total_count": total_count,
                        "failed_count": failed_count
                    }
                }

                # Broadcast to all clients
                websockets.broadcast(websocket_clients, json.dumps(update))
                print(f"[*] Broadcast update to {len(websocket_clients)} client(s)")


class VisualizationHandler(BaseHTTPRequestHandler):
    logs_dir = None
    db = None

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            # Serve index page with list of all CSV files
            try:
                html = self._generate_index()
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
                self.send_error(500, f"Error generating index: {str(e)}")

        elif self.path.startswith("/csv/"):
            # Export CSV from SQLite for dynamic visualization
            try:
                # Path format: /csv/YYYY-MM-DD/HH or /csv/YYYY-MM-DD/monitor_YYYYMMDD_HH.csv
                csv_path = urllib.parse.unquote(self.path[5:])  # Remove /csv/ prefix

                # Parse date and hour from path
                if '/' in csv_path:
                    parts = csv_path.split('/')
                    date_str = parts[0]  # YYYY-MM-DD

                    # Extract hour from filename or second part
                    if len(parts) > 1:
                        if parts[1].endswith('.csv'):
                            # Format: monitor_YYYYMMDD_HH.csv
                            hour_str = parts[1].split('_')[-1].replace('.csv', '')
                            hour = int(hour_str)
                        else:
                            # Format: HH
                            hour = int(parts[1])
                    else:
                        self.send_error(400, "Invalid CSV path format")
                        return
                else:
                    self.send_error(400, "Invalid CSV path format")
                    return

                # Export from database
                csv_content = self.db.export_to_csv(date_str, hour)

                if not csv_content or csv_content == "timestamp, status, response_time, success_count, total_count, failed_count":
                    self.send_error(404, f"No data found for {date_str} hour {hour}")
                    return

                content = csv_content.encode('utf-8')

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

        elif self.path.startswith("/view/"):
            # Serve specific visualization
            # Path format: /view/YYYY-MM-DD/monitor_YYYYMMDD_HHMMSS.csv
            try:
                # Extract the path components
                parts = self.path[6:].split("/")  # Remove /view/ prefix
                if len(parts) < 2:
                    self.send_error(400, "Invalid path format")
                    return

                date_str = parts[0]
                csv_filename = "/".join(parts[1:])

                # Extract hour from filename (format: monitor_YYYYMMDD_HH.csv)
                hour_str = csv_filename.split('_')[-1].replace('.csv', '')
                hour = int(hour_str)

                # Check if data exists in database
                logs = self.db.get_logs_by_hour(date_str, hour)
                if not logs:
                    self.send_error(404, f"No data found for {date_str} hour {hour}")
                    return

                # For compatibility, create a pseudo csv_file path
                csv_file = self.logs_dir / date_str / "csv" / csv_filename

                # Check if this is the current hour's file
                now = datetime.now()
                current_date_str = now.strftime("%Y-%m-%d")
                current_hour_str = now.strftime("%Y%m%d_%H")
                is_current_hour = (date_str == current_date_str and current_hour_str in csv_filename)

                print(f"\n[*] Serving visualization for: {csv_file.name} (current_hour={is_current_hour})")

                html_dir = self.logs_dir / date_str / "html"
                html_file = html_dir / f"{csv_file.stem}_visualization.html"

                # For current hour: use dynamic visualization with WebSocket support
                # For past hours: generate once and cache
                if is_current_hour:
                    # Serve dynamic HTML with Chart.js and WebSocket
                    print("[*] Using dynamic Chart.js visualization with WebSocket (current hour)")
                    html_content = self._generate_dynamic_chartjs_html(csv_file, date_str, csv_filename)
                else:
                    # For past hours, check if HTML exists, if not generate it once
                    if not html_file.exists():
                        print("[*] Generating static visualization (past hour, first time)")
                        script_dir = Path(__file__).parent
                        visualize_script = script_dir / "visualize.py"

                        # Check if running in Docker (use system python3) or native (use venv)
                        if Path("/.dockerenv").exists():
                            python_executable = "python3"
                        else:
                            venv_python = script_dir / "venv" / "bin" / "python"
                            python_executable = str(venv_python)

                        result = subprocess.run(
                            [python_executable, str(visualize_script), str(csv_file)],
                            capture_output=True,
                            text=True,
                        )

                        if result.returncode != 0:
                            self.send_error(
                                500, f"Failed to generate visualization: {result.stderr}"
                            )
                            return
                    else:
                        print("[*] Using cached static visualization (past hour)")

                    # Read the cached HTML file
                    if not html_file.exists():
                        self.send_error(404, "Visualization file not found")
                        return

                    with open(html_file, "r", encoding="utf-8") as f:
                        html_content = f.read()

                # Find all CSV files for navigation
                all_csv_files = sorted(self.logs_dir.rglob("*/csv/*.csv"))
                current_index = None
                for i, f in enumerate(all_csv_files):
                    if f == csv_file:
                        current_index = i
                        break

                # Determine previous and next files
                prev_url = None
                next_url = None
                if current_index is not None:
                    if current_index > 0:
                        prev_file = all_csv_files[current_index - 1]
                        prev_date = prev_file.parent.parent.name
                        prev_url = f"/view/{prev_date}/{prev_file.name}"
                    if current_index < len(all_csv_files) - 1:
                        next_file = all_csv_files[current_index + 1]
                        next_date = next_file.parent.parent.name
                        next_url = f"/view/{next_date}/{next_file.name}"

                # Inject Gruvbox background CSS and navigation buttons
                gruvbox_css = """
<style>
    html, body {
        background-color: #1d2021 !important;
        margin: 0;
        padding: 0;
        min-height: 100vh;
    }
    .nav-buttons {
        position: fixed;
        top: 630px;
        left: 40px;
        z-index: 1000;
    }
    .nav-buttons-right {
        position: fixed;
        top: 630px;
        right: 40px;
        display: flex;
        gap: 10px;
        z-index: 1000;
    }
    .nav-btn {
        background: #3c3836;
        color: #ebdbb2;
        border: 2px solid #665c54;
        padding: 10px 20px;
        border-radius: 4px;
        cursor: pointer;
        font-family: monospace;
        font-size: 14px;
        font-weight: bold;
        transition: all 0.2s;
    }
    .nav-btn:hover:not(:disabled) {
        background: #504945;
        border-color: #fe8019;
        color: #fe8019;
    }
    .nav-btn:disabled {
        opacity: 0.3;
        cursor: not-allowed;
    }
</style>
"""
                # Create navigation buttons HTML
                prev_btn_attr = "disabled" if not prev_url else f'onclick="window.location.href=\'{prev_url}\'"'
                next_btn_attr = "disabled" if not next_url else f'onclick="window.location.href=\'{next_url}\'"'

                nav_buttons = f"""
<div class="nav-buttons">
    <button class="nav-btn" onclick="window.location.href='/'" title="Back to index">← Home</button>
</div>
<div class="nav-buttons-right">
    <button class="nav-btn" {prev_btn_attr} title="Previous file">← Prev</button>
    <button class="nav-btn" {next_btn_attr} title="Next file">Next →</button>
</div>
"""
                # Inject CSS and navigation buttons
                html_content = html_content.replace("</head>", gruvbox_css + "</head>")
                html_content = html_content.replace("<body>", "<body>" + nav_buttons)

                content = html_content.encode("utf-8")

                # Send response
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.send_header("Content-Length", len(content))
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.end_headers()
                self.wfile.write(content)

                print("[+] Served visualization")

            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_error(500, f"Error: {str(e)}")
        else:
            self.send_error(404, "File not found")

    def _generate_index(self):
        """Generate an index page listing all available hours from SQLite."""
        # Get available hours from database
        available_hours = self.db.get_available_hours()

        # Group by date
        files_by_date = {}
        for date, hour, count in available_hours:
            if date not in files_by_date:
                files_by_date[date] = []
            # Create a pseudo-filename for compatibility
            filename = f"monitor_{date.replace('-', '')}_{hour}.csv"
            files_by_date[date].append((filename, hour, count))

        # Generate HTML
        html = """<!DOCTYPE html>
<html style="background: #1d2021;">
<head>
    <title>Network Monitor - Visualizations</title>
    <style>
        /* Gruvbox color scheme */
        :root {
            --bg0: #282828;
            --bg0-hard: #1d2021;
            --bg1: #3c3836;
            --bg2: #504945;
            --bg3: #665c54;
            --bg4: #7c6f64;
            --fg0: #fbf1c7;
            --fg1: #ebdbb2;
            --fg2: #d5c4a1;
            --fg3: #bdae93;
            --fg4: #a89984;
            --red: #fb4934;
            --green: #b8bb26;
            --yellow: #fabd2f;
            --blue: #83a598;
            --purple: #d3869b;
            --aqua: #8ec07c;
            --orange: #fe8019;
            --gray: #928374;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        html {
            background: var(--bg0-hard);
            min-height: 100vh;
        }

        body {
            font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Code', 'Dank Mono', monospace, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: var(--bg0-hard);
            color: var(--fg1);
            min-height: 100vh;
        }
        h1 {
            color: var(--orange);
            border-bottom: 3px solid var(--orange);
            padding-bottom: 10px;
            margin-bottom: 15px;
            font-weight: bold;
        }
        h2 {
            color: var(--yellow);
            margin-top: 30px;
            margin-bottom: 15px;
            font-weight: bold;
        }
        .file-list {
            background: var(--bg1);
            border-radius: 4px;
            padding: 15px;
            margin-bottom: 20px;
            border: 1px solid var(--bg3);
        }
        .file-item {
            padding: 10px;
            margin: 5px 0;
            border-left: 4px solid var(--aqua);
            background: var(--bg2);
            border-radius: 2px;
            transition: all 0.2s;
        }
        .file-item:hover {
            background: var(--bg3);
            border-left-color: var(--green);
        }
        .file-item a {
            color: var(--blue);
            text-decoration: none;
            font-weight: 500;
        }
        .file-item a:hover {
            color: var(--aqua);
            text-decoration: underline;
        }
        .file-meta {
            color: var(--fg4);
            font-size: 0.9em;
            margin-left: 10px;
        }
        .no-files {
            color: var(--gray);
            font-style: italic;
            padding: 20px;
            text-align: center;
        }
        .refresh-note {
            background: var(--bg2);
            border: 1px solid var(--orange);
            border-radius: 4px;
            padding: 10px;
            margin-bottom: 20px;
            color: var(--fg1);
        }
        .refresh-note strong {
            color: var(--orange);
        }
    </style>
</head>
<body>
    <h1>Steineck Network Monitor</h1>
    <div class="refresh-note">
        <strong>Tip:</strong> Current hour uses live Chart.js visualization with WebSocket updates. Past hours are cached.
    </div>
"""

        if not files_by_date:
            html += '<div class="no-files">No monitoring data found. Run monitor.py to create some!</div>'
        else:
            for date_str in sorted(files_by_date.keys(), reverse=True):
                html += f'<h2>Date: {date_str}</h2>\n<div class="file-list">\n'

                for filename, hour, count in sorted(files_by_date[date_str], reverse=True):
                    # Format time display
                    formatted_time = f"{hour}:00 - {hour}:59"

                    view_url = f"/view/{date_str}/{filename}"
                    html += f'''    <div class="file-item">
        <a href="{view_url}">{filename}</a>
        <span class="file-meta">{formatted_time} ({count} entries)</span>
    </div>
'''

                html += "</div>\n"

        html += """</body>
</html>"""

        return html

    def _generate_dynamic_chartjs_html(self, csv_file, date_str, csv_filename):
        """Generate dynamic HTML with Chart.js and WebSocket support."""
        csv_url = f"/csv/{date_str}/{csv_filename}"

        # Get WebSocket URL (same host, different port)
        ws_port = 8081  # WebSocket server port
        ws_url = f"ws://{{location.hostname}}:{ws_port}"

        # Find all CSV files for navigation
        all_csv_files = sorted(self.logs_dir.rglob("*/csv/*.csv"))
        current_index = None
        for i, f in enumerate(all_csv_files):
            if f == csv_file:
                current_index = i
                break

        # Determine previous and next files
        prev_url = None
        next_url = None
        if current_index is not None:
            if current_index > 0:
                prev_file = all_csv_files[current_index - 1]
                prev_date = prev_file.parent.parent.name
                prev_url = f"/view/{prev_date}/{prev_file.name}"
            if current_index < len(all_csv_files) - 1:
                next_file = all_csv_files[current_index + 1]
                next_date = next_file.parent.parent.name
                next_url = f"/view/{next_date}/{next_file.name}"

        prev_btn_attr = "disabled" if not prev_url else f'onclick="window.location.href=\'{prev_url}\'"'
        next_btn_attr = "disabled" if not next_url else f'onclick="window.location.href=\'{next_url}\'"'

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Network Monitor - {csv_filename} (Live)</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        html, body {{
            background-color: #1d2021 !important;
            margin: 0;
            padding: 0;
            min-height: 100vh;
            color: #ebdbb2;
            font-family: monospace;
        }}
        .chart-container {{
            position: relative;
            width: 95%;
            height: 600px;
            margin: 20px auto;
            padding: 20px;
            background: #282828;
            border-radius: 8px;
        }}
        .chart-title {{
            text-align: center;
            color: #fe8019;
            font-size: 20px;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        .chart-subtitle {{
            text-align: center;
            color: #ebdbb2;
            font-size: 14px;
            margin-bottom: 20px;
        }}
        .nav-buttons {{
            position: fixed;
            top: 630px;
            left: 40px;
            z-index: 1000;
        }}
        .nav-buttons-right {{
            position: fixed;
            top: 630px;
            right: 40px;
            display: flex;
            gap: 10px;
            z-index: 1000;
        }}
        .nav-btn {{
            background: #3c3836;
            color: #ebdbb2;
            border: 2px solid #665c54;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-family: monospace;
            font-size: 14px;
            font-weight: bold;
            transition: all 0.2s;
        }}
        .nav-btn:hover:not(:disabled) {{
            background: #504945;
            border-color: #fe8019;
            color: #fe8019;
        }}
        .nav-btn:disabled {{
            opacity: 0.3;
            cursor: not-allowed;
        }}
        .live-indicator {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: #b8bb26;
            color: #1d2021;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
            z-index: 1000;
        }}
        .ws-status {{
            position: fixed;
            top: 60px;
            right: 20px;
            padding: 8px 16px;
            border-radius: 4px;
            font-size: 12px;
            z-index: 1000;
        }}
        .ws-connected {{
            background: #8ec07c;
            color: #1d2021;
        }}
        .ws-disconnected {{
            background: #fb4934;
            color: #1d2021;
        }}
    </style>
</head>
<body>
    <div class="live-indicator">🔴 LIVE</div>
    <div id="ws-status" class="ws-status ws-disconnected">WebSocket: Connecting...</div>

    <div class="chart-title">Network Monitoring Dashboard (Live)</div>
    <div class="chart-subtitle">{csv_filename}</div>

    <div class="chart-container">
        <canvas id="chart"></canvas>
    </div>

    <div class="nav-buttons">
        <button class="nav-btn" onclick="window.location.href='/'" title="Back to index">← Home</button>
    </div>
    <div class="nav-buttons-right">
        <button class="nav-btn" {prev_btn_attr} title="Previous file">← Prev</button>
        <button class="nav-btn" {next_btn_attr} title="Next file">Next →</button>
    </div>

    <script>
        const csvUrl = '{csv_url}';
        const wsUrl = '{ws_url}';
        let chart;
        let updateInterval;
        let ws;

        function parseCSV(csv) {{
            const lines = csv.trim().split('\\n');
            const headers = lines[0].split(',').map(h => h.trim());
            const data = [];

            for (let i = 1; i < lines.length; i++) {{
                const values = lines[i].split(',');
                const row = {{}};
                headers.forEach((header, index) => {{
                    row[header] = values[index] ? values[index].trim() : null;
                }});
                data.push(row);
            }}

            return data;
        }}

        function updateChart() {{
            fetch(csvUrl)
                .then(response => response.text())
                .then(csvText => {{
                    const data = parseCSV(csvText);

                    // Parse timestamps and values
                    const timestamps = data.map(row => row.timestamp);
                    const responseTimes = data.map(row => row.response_time === 'null' ? null : parseFloat(row.response_time));
                    const successRates = data.map(row => {{
                        const success = parseInt(row.success_count || 0);
                        const total = parseInt(row.total_count || 1);
                        return (success / total) * 100;
                    }});

                    // Color-code markers based on success rate
                    const pointColors = successRates.map(rate => {{
                        if (rate === 100) return '#b8bb26'; // green
                        if (rate === 0) return '#fb4934';   // red
                        return '#fe8019';                    // orange
                    }});

                    const chartData = {{
                        labels: timestamps,
                        datasets: [
                            {{
                                label: 'Response Time (ms)',
                                data: responseTimes,
                                borderColor: '#83a598',
                                backgroundColor: 'rgba(131, 165, 152, 0.1)',
                                borderWidth: 2,
                                pointRadius: 3,
                                pointHoverRadius: 5,
                                yAxisID: 'y',
                                tension: 0.1
                            }},
                            {{
                                label: 'Success Rate (%)',
                                data: successRates,
                                borderColor: '#8ec07c',
                                backgroundColor: 'rgba(142, 192, 124, 0.2)',
                                borderWidth: 2,
                                pointRadius: 4,
                                pointHoverRadius: 6,
                                pointBackgroundColor: pointColors,
                                pointBorderColor: pointColors,
                                fill: true,
                                yAxisID: 'y1',
                                tension: 0.1
                            }}
                        ]
                    }};

                    const config = {{
                        type: 'line',
                        data: chartData,
                        options: {{
                            responsive: true,
                            maintainAspectRatio: false,
                            interaction: {{
                                mode: 'index',
                                intersect: false,
                            }},
                            plugins: {{
                                legend: {{
                                    display: true,
                                    position: 'bottom',
                                    labels: {{
                                        color: '#ebdbb2',
                                        font: {{
                                            family: 'monospace',
                                            size: 12
                                        }},
                                        padding: 20
                                    }}
                                }},
                                tooltip: {{
                                    backgroundColor: '#3c3836',
                                    titleColor: '#fe8019',
                                    bodyColor: '#ebdbb2',
                                    borderColor: '#665c54',
                                    borderWidth: 1,
                                    padding: 12,
                                    displayColors: true
                                }}
                            }},
                            scales: {{
                                x: {{
                                    display: true,
                                    title: {{
                                        display: true,
                                        text: 'Time',
                                        color: '#ebdbb2',
                                        font: {{
                                            family: 'monospace',
                                            size: 14
                                        }}
                                    }},
                                    ticks: {{
                                        color: '#ebdbb2',
                                        font: {{
                                            family: 'monospace'
                                        }},
                                        maxRotation: 45,
                                        minRotation: 45
                                    }},
                                    grid: {{
                                        color: '#504945',
                                        drawBorder: true
                                    }}
                                }},
                                y: {{
                                    type: 'linear',
                                    display: true,
                                    position: 'left',
                                    title: {{
                                        display: true,
                                        text: 'Response Time (ms)',
                                        color: '#83a598',
                                        font: {{
                                            family: 'monospace',
                                            size: 14
                                        }}
                                    }},
                                    ticks: {{
                                        color: '#ebdbb2',
                                        font: {{
                                            family: 'monospace'
                                        }}
                                    }},
                                    grid: {{
                                        color: '#504945',
                                        drawBorder: true
                                    }}
                                }},
                                y1: {{
                                    type: 'linear',
                                    display: true,
                                    position: 'right',
                                    title: {{
                                        display: true,
                                        text: 'Success Rate (%)',
                                        color: '#8ec07c',
                                        font: {{
                                            family: 'monospace',
                                            size: 14
                                        }}
                                    }},
                                    min: 0,
                                    max: 105,
                                    ticks: {{
                                        color: '#ebdbb2',
                                        font: {{
                                            family: 'monospace'
                                        }}
                                    }},
                                    grid: {{
                                        drawOnChartArea: false,
                                        drawBorder: true,
                                        color: '#504945'
                                    }}
                                }}
                            }}
                        }}
                    }};

                    if (chart) {{
                        chart.data = chartData;
                        chart.update('none'); // Update without animation for performance
                    }} else {{
                        chart = new Chart(document.getElementById('chart'), config);
                    }}
                }})
                .catch(error => {{
                    console.error('Error updating chart:', error);
                }});
        }}

        // WebSocket connection for real-time updates
        function connectWebSocket() {{
            ws = new WebSocket(wsUrl);

            ws.onopen = () => {{
                console.log('WebSocket connected');
                document.getElementById('ws-status').textContent = 'WebSocket: Connected';
                document.getElementById('ws-status').className = 'ws-status ws-connected';
            }};

            ws.onmessage = (event) => {{
                const message = JSON.parse(event.data);

                if (message.type === 'update') {{
                    console.log('Received WebSocket update:', message.data);
                    // Refresh chart with new data
                    updateChart();
                }}
            }};

            ws.onerror = (error) => {{
                console.error('WebSocket error:', error);
                document.getElementById('ws-status').textContent = 'WebSocket: Error';
                document.getElementById('ws-status').className = 'ws-status ws-disconnected';
            }};

            ws.onclose = () => {{
                console.log('WebSocket disconnected - falling back to polling');
                document.getElementById('ws-status').textContent = 'WebSocket: Disconnected (Polling)';
                document.getElementById('ws-status').className = 'ws-status ws-disconnected';

                // Fallback to HTTP polling if WebSocket fails
                startAutoUpdate();
            }};
        }}

        // Initial load
        updateChart();

        // Try WebSocket connection
        connectWebSocket();

        // Auto-update every 60 seconds when page is visible (fallback if WebSocket fails)
        function startAutoUpdate() {{
            updateInterval = setInterval(() => {{
                if (!document.hidden) {{
                    console.log('Auto-updating chart data (HTTP polling)...');
                    updateChart();
                }}
            }}, 60000); // 60 seconds
        }}

        function stopAutoUpdate() {{
            if (updateInterval) {{
                clearInterval(updateInterval);
            }}
        }}

        // Pause/resume based on page visibility
        document.addEventListener('visibilitychange', () => {{
            if (document.hidden) {{
                stopAutoUpdate();
                if (ws) ws.close();
            }} else {{
                if (!ws || ws.readyState !== WebSocket.OPEN) {{
                    connectWebSocket();
                }}
                startAutoUpdate();
            }}
        }});
    </script>
</body>
</html>"""

        return html

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
    http_thread = threading.Thread(target=run_http_server, args=(logs_path, port), daemon=True)
    http_thread.start()

    # Run WebSocket server in main event loop
    try:
        asyncio.run(start_websocket_server(db, port=8081))
    except KeyboardInterrupt:
        print("\n\n[*] Shutting down servers...")

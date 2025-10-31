#!/usr/bin/env python3

"""
Live visualization server that regenerates the chart on each page load.
Usage: python serve.py [logs_dir] [port]
"""

import sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess
import webbrowser
import threading
import time


class VisualizationHandler(BaseHTTPRequestHandler):
    logs_dir = None

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

                csv_file = self.logs_dir / date_str / "csv" / csv_filename

                if not csv_file.exists():
                    self.send_error(404, f"CSV file not found: {csv_file}")
                    return

                # Regenerate visualization
                print(f"\n[*] Regenerating visualization for: {csv_file.name}")

                # Run visualize.py to generate fresh HTML
                script_dir = Path(__file__).parent
                venv_python = script_dir / "venv" / "bin" / "python"
                visualize_script = script_dir / "visualize.py"

                result = subprocess.run(
                    [str(venv_python), str(visualize_script), str(csv_file)],
                    capture_output=True,
                    text=True,
                )

                if result.returncode != 0:
                    self.send_error(
                        500, f"Failed to generate visualization: {result.stderr}"
                    )
                    return

                # Read the generated HTML file
                html_dir = self.logs_dir / date_str / "html"
                html_file = html_dir / f"{csv_file.stem}_visualization.html"

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
                nav_buttons = f"""
<div class="nav-buttons">
    <button class="nav-btn" onclick="window.location.href='/'" title="Back to index">← Home</button>
</div>
<div class="nav-buttons-right">
    <button class="nav-btn" {"disabled" if not prev_url else f"onclick=\"window.location.href='{prev_url}'\""} title="Previous file">← Prev</button>
    <button class="nav-btn" {"disabled" if not next_url else f"onclick=\"window.location.href='{next_url}'\""} title="Next file">Next →</button>
</div>
"""
                # Inject auto-refresh script before </body>
                auto_refresh_script = """
<script>
    // Auto-refresh every 60 seconds when page is visible
    let refreshInterval;
    
    function startAutoRefresh() {
        refreshInterval = setInterval(() => {
            if (!document.hidden) {
                console.log('Auto-refreshing visualization...');
                location.reload();
            }
        }, 60000); // 60 seconds
    }
    
    function stopAutoRefresh() {
        if (refreshInterval) {
            clearInterval(refreshInterval);
        }
    }
    
    // Start auto-refresh when page loads
    startAutoRefresh();
    
    // Pause/resume based on page visibility
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            stopAutoRefresh();
        } else {
            startAutoRefresh();
        }
    });
</script>
"""
                # Inject CSS, navigation buttons, and script
                html_content = html_content.replace("</head>", gruvbox_css + "</head>")
                html_content = html_content.replace("<body>", "<body>" + nav_buttons)
                html_content = html_content.replace(
                    "</body>", auto_refresh_script + "</body>"
                )
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

                print("[+] Served fresh visualization")

            except Exception as e:
                self.send_error(500, f"Error: {str(e)}")
        else:
            self.send_error(404, "File not found")

    def _generate_index(self):
        """Generate an index page listing all available CSV files."""
        # Find all CSV files in the logs directory
        csv_files = sorted(self.logs_dir.rglob("*/csv/*.csv"), reverse=True)

        # Group by date
        files_by_date = {}
        for csv_file in csv_files:
            date_str = csv_file.parent.parent.name  # Get YYYY-MM-DD from path
            if date_str not in files_by_date:
                files_by_date[date_str] = []
            files_by_date[date_str].append(csv_file)

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
        <strong>Tip:</strong> Each visualization is regenerated fresh when you click on it.
    </div>
"""

        if not files_by_date:
            html += '<div class="no-files">No monitoring data found. Run monitor.sh to create some!</div>'
        else:
            for date_str in sorted(files_by_date.keys(), reverse=True):
                html += f'<h2>Date: {date_str}</h2>\n<div class="file-list">\n'

                for csv_file in sorted(files_by_date[date_str], reverse=True):
                    filename = csv_file.name
                    # Extract timestamp from filename: monitor_YYYYMMDD_HHMMSS.csv
                    try:
                        time_part = filename.split("_")[2].replace(".csv", "")
                        formatted_time = f"{time_part[0:2]}:00 - {time_part[0:2]}:59"
                    except Exception:
                        formatted_time = "Unknown time"

                    view_url = f"/view/{date_str}/{filename}"
                    html += f'''    <div class="file-item">
        <a href="{view_url}">{filename}</a>
        <span class="file-meta">Started at {formatted_time}</span>
    </div>
'''

                html += "</div>\n"

        html += """</body>
</html>"""

        return html

    def log_message(self, format, *args):
        # Suppress default logging
        pass


def open_browser(url, delay=1):
    """Open browser after a short delay"""
    time.sleep(delay)
    webbrowser.open(url)


if __name__ == "__main__":
    # Default to logs directory if no argument provided
    logs_path = Path(sys.argv[1]) if len(sys.argv) >= 2 else Path("logs")
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000

    if not logs_path.exists():
        print(f"[!] Error: Directory not found: {logs_path}")
        print(f"\nUsage: python serve.py [logs_dir] [port]")
        print("\nExamples:")
        print("  python serve.py                  # Use default 'logs' directory")
        print("  python serve.py logs             # Specify logs directory")
        print("  python serve.py logs 8080        # Specify directory and port")
        sys.exit(1)

    # Set the logs directory for the handler
    VisualizationHandler.logs_dir = logs_path

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
    print(f"[*] Local access: {local_url}")
    print(f"[*] Network access: {network_url}")
    print("[*] Each visualization will regenerate fresh when you click on it")
    print("\n[*] Press Ctrl+C to stop the server\n")

    # Open browser in background
    threading.Thread(target=open_browser, args=(local_url,), daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n[*] Shutting down server...")
        server.shutdown()

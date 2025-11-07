#!/usr/bin/env python3

"""
HTML dashboard generation for network monitor.
"""

from datetime import datetime
from utils import get_version


def generate_dashboard(db):
    """
    Generate single-page dashboard with chart and data listing.

    Args:
        db: NetworkMonitorDB instance

    Returns:
        str: Complete HTML page
    """
    # Get version from VERSION file
    version = get_version()

    # Get available hours from database
    available_hours = db.get_available_hours()

    if not available_hours:
        return _generate_empty_dashboard()

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
    initial_filename = f"monitor_{initial_date.replace('-', '')}_{initial_hour:02d}.csv"

    # Build the HTML
    html = (
        f"""<!DOCTYPE html>
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
                            󰴽 Connecting...
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Chart -->
        <div class="chart-container">
            <div class="section-header">
                <div>
                    <div class="section-title"> Network Monitoring</div>
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
                    <div class="section-title"> Internet Speed Tests</div>
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

        <!-- Docker Resources Section -->
        <div class="docker-resources-container">
            <div class="section-header">
                <div>
                    <div class="section-title">󰡨 Docker Container Resources</div>
                    <div class="section-subtitle">Live resource consumption • Updates every 5s</div>
                </div>
            </div>

            <div class="resources-grid">
                <!-- CPU Usage -->
                <div class="resource-box large">
                    <div class="resource-label">CPU Usage</div>
                    <div class="bar-container">
                        <div class="bar" id="dockerCpuBar"></div>
                        <div class="percentage" id="dockerCpuPercent">0%</div>
                    </div>
                </div>

                <!-- Memory -->
                <div class="resource-box large">
                    <div class="resource-label">Memory</div>
                    <div class="bar-container">
                        <div class="bar" id="dockerMemBar"></div>
                        <div class="percentage" id="dockerMemPercent">0%</div>
                    </div>
                    <div class="value" id="dockerMemValue">-- / --</div>
                </div>

                <!-- Network I/O -->
                <div class="resource-box">
                    <div class="resource-label">Network I/O</div>
                    <div class="metrics-row">
                        <div class="metric">
                            <div class="metric-label"><span class="arrow up">↑</span> Sent</div>
                            <div class="metric-value" id="dockerNetTx">--</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label"><span class="arrow down">↓</span> Recv</div>
                            <div class="metric-value" id="dockerNetRx">--</div>
                        </div>
                    </div>
                </div>

                <!-- Disk I/O -->
                <div class="resource-box">
                    <div class="resource-label">Disk I/O</div>
                    <div class="metrics-row">
                        <div class="metric">
                            <div class="metric-label">Write</div>
                            <div class="metric-value" id="dockerDiskWrite">--</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Read</div>
                            <div class="metric-value" id="dockerDiskRead">--</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Footer -->
        <div class="footer">
            <div class="footer-content">
                <span class="footer-prompt">$</span>
                <span class="footer-item">./network-monitor <span id="footerVersion">v"""
        + version
        + '''</span></span>
                <span class="footer-separator">•</span>
                <span class="footer-item">DB: <span id="footerDbSize">--</span></span>
                <span class="footer-separator">•</span>
                <span class="footer-item">Uptime: <span id="footerUptime">--</span></span>
                <span class="footer-separator">•</span>
                <span class="footer-item">© 2025</span>
                <span class="footer-separator">•</span>
                <a href="https://github.com/stein935/network-monitor" target="_blank" class="footer-link" title="View on GitHub"> GitHub ↗</a>
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


def _generate_empty_dashboard():
    """Generate dashboard HTML when no monitoring data exists."""
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

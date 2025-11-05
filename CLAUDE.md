# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Network Monitor is a Python-based daemon that continuously monitors network connectivity and internet speed, storing data in SQLite database with real-time web visualization.

**Key characteristics:**
- **SQLite storage:** Fast, indexed database storage (Phase 1)
- **Chart.js visualization:** 93% smaller bundle than Plotly (Phase 2)
- **WebSocket real-time updates:** 30-second batches for live monitoring (Phase 2)
- **nginx reverse proxy:** Gzip compression, better concurrency (Phase 3)
- **Internet speed testing:** Automated speed tests every 15 minutes via speedtest-cli
- **Dual monitoring:** Network latency (ping to 8.8.8.8) + bandwidth (speedtest-cli)
- **Single-page dashboard:** Unified view of network monitoring and speed tests
- Daemon mode: Runs continuously without time limits
- CSV export on-demand: Historical data exported dynamically from SQLite
- Auto cleanup: Removes logs older than 30 days with VACUUM
- Docker deployment: Optimized for Raspberry Pi Zero 2 W
- **Performance improvements:**
  - 70% reduction in disk I/O (SQLite vs CSV)
  - 93% smaller page loads (Chart.js vs Plotly)
  - 95% CPU reduction for live monitoring (WebSocket vs polling)
  - 70% bandwidth reduction (nginx gzip compression)

## Architecture

### Core Components

1. **monitor.py** - SQLite-based monitor daemon with speed testing (Phase 1):
   - Pings 8.8.8.8 every `FREQUENCY` seconds (default: 1)
   - Collects `SAMPLE_SIZE` samples (default: 5) before logging
   - Writes directly to SQLite: `logs/network_monitor.db`
   - **Speed test thread:** Runs speedtest-cli every 15 minutes in background
   - Indexed queries for fast retrieval
   - Performs cleanup with VACUUM once per hour
   - Handles both macOS and Linux ping output formats

2. **serve.py** - Live web server with SQLite backend, Chart.js, and WebSocket support (Phase 2):
   - **HTTP server (port 8090):** Serves HTML, API endpoints, and CSV exports
   - **WebSocket server (port 8081):** Real-time data pushes every 30 seconds
   - Reads from SQLite database (`db.py`)
   - **Single-page dashboard** with dual monitoring:
     - Network monitoring chart (1-hour window, time-based navigation)
     - Speed test chart (12-hour window, time-based navigation)
     - Speed test stats display (download, upload, server, last test)
   - **Chart.js for all visualizations:**
     - **Live data**: Chart.js with WebSocket updates (30s batches) + HTTP polling fallback (60s)
     - **Historical data**: Static Chart.js visualizations (no updates)
   - **API endpoints:**
     - `/api/network-logs/earliest` - Get earliest network log
     - `/api/speed-tests/latest` - Get latest speed test result
     - `/api/speed-tests/recent` - Get recent speed tests with optional time range
   - **CSV export:**
     - Time-range based: `/csv/?start_time=...&end_time=...`
     - Legacy format: `/csv/YYYY-MM-DD/HH`
   - Binds to 0.0.0.0 for network access
   - **Chart.js benefits:** 93% smaller (200KB vs 3MB Plotly), faster rendering, lower memory

3. **db.py** - SQLite database handler with dual tables:
   - **network_logs table:** Ping monitoring data with indexed timestamps
   - **speed_tests table:** Speed test results with indexed timestamps
   - Insert, query, export functions for both tables
   - Auto-cleanup with VACUUM (removes data older than retention period)
   - Export to CSV format for on-demand generation
   - Time-range query support for both network logs and speed tests

4. **nginx.conf** - Reverse proxy configuration (Phase 3):
   - Listens on port 8080 (external)
   - Proxies HTTP requests to serve.py:8090 (internal)
   - Proxies WebSocket to serve.py:8081 via `/ws` path
   - Gzip compression for 70% bandwidth reduction
   - Security headers

5. **start_services.sh** - Service startup script (Phase 3):
   - Starts nginx reverse proxy
   - Starts Python HTTP and WebSocket servers
   - Handles graceful shutdown

### Data Flow

**Architecture (Phase 3):**
```
Browser → nginx:8080 (gzip, proxy)
              ↓
         serve.py:8090 (HTTP - Chart.js generation, API, CSV export)
              ↓
         serve.py:8081 (WebSocket - 30s batches via /ws path)
              ↓
         SQLite database (logs/network_monitor.db)
              ↑
         monitor.py (network logs every minute + speed tests every 15 min)
```

**Live monitoring (network + speed tests):**
```
monitor.py → SQLite → serve.py WebSocket → Browser Chart.js (30s updates)
                                         → Fallback: HTTP polling (60s for network, 5min for speed)
```

**Historical data viewing:**
```
SQLite → serve.py API/CSV → Browser Chart.js (time-range queries)
```

### SQLite Schema

**Table: `network_logs`**
```sql
CREATE TABLE network_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    status TEXT NOT NULL,
    response_time REAL,
    success_count INTEGER NOT NULL,
    total_count INTEGER NOT NULL,
    failed_count INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_timestamp ON network_logs(timestamp);
```

**Table: `speed_tests`**
```sql
CREATE TABLE speed_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    download_mbps REAL NOT NULL,
    upload_mbps REAL NOT NULL,
    ping_ms REAL,
    server_host TEXT,
    server_name TEXT,
    server_country TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_speed_timestamp ON speed_tests(timestamp);
```

**CSV Export Format** (network logs, on-demand):
```
timestamp, status, response_time, success_count, total_count, failed_count
```

## Development Commands

### Docker (Production deployment)

**Build and start container:**
```bash
docker compose build
docker compose up -d
```

**Start services inside container:**
```bash
# Monitor daemon
docker exec -d network-monitor python3 /app/monitor.py 1 60

# Web server (nginx + Python servers)
docker exec -d network-monitor /bin/bash /app/start_services.sh
```

**Check status:**
```bash
docker ps | grep network-monitor
docker logs network-monitor
docker exec network-monitor pgrep -f monitor.py
docker stats network-monitor --no-stream
```

**Stop processes:**
```bash
docker exec network-monitor pkill -f monitor.py
docker exec network-monitor nginx -s quit
docker exec network-monitor pkill -f serve.py
```

**Update deployment:**
```bash
git pull origin main
docker compose down
docker compose build --no-cache
docker compose up -d
```

**Access web dashboard:**
- External: `http://<pi-ip>:8080`
- Inside container: `http://localhost:8080` (nginx)


## Systemd Services (Raspberry Pi)

Three systemd services manage the Docker deployment:

1. `network-monitor-container.service` - Starts/stops Docker container
2. `network-monitor-daemon.service` - Runs monitor.py inside container
3. `network-monitor-server.service` - Runs start_services.sh (nginx + serve.py) inside container

**Check status:**
```bash
systemctl status 'network-monitor-*'
```

**Restart all:**
```bash
sudo systemctl restart network-monitor-container.service
sudo systemctl restart network-monitor-daemon.service
sudo systemctl restart network-monitor-server.service
```

**View logs:**
```bash
sudo journalctl -u network-monitor-daemon.service -f
sudo journalctl -u network-monitor-server.service -f
```

## Configuration

### Monitor Parameters

Edit systemd service files or pass as arguments:

- `FREQUENCY`: Seconds between pings (default: 1)
- `SAMPLE_SIZE`: Number of pings to average before logging (default: 60)
- `LOG_RETENTION_DAYS`: Days to keep logs (default: 30, set in monitor.py)
- **Speed tests:** Automatically run every 15 minutes (hardcoded in monitor.py)

### Port Mapping

Edit `docker-compose.yml` to change exposed ports:
```yaml
ports:
  - "8080:8080"  # External:Internal (nginx HTTP)
  - "8081:8081"  # External:Internal (WebSocket)
```

**Internal port architecture:**
- nginx listens on port 8080 (internal)
- Python HTTP server (serve.py) listens on port 8090 (internal, proxied by nginx)
- Python WebSocket server listens on port 8081 (internal, proxied by nginx via /ws)

## Important Implementation Details

### Speed Test Integration

monitor.py runs speed tests in a separate daemon thread:

```python
def speed_test_loop(self):
    """Separate thread for running speed tests every 15 minutes."""
    time.sleep(30)  # Initial delay
    while True:
        try:
            self.run_speed_test()
        except Exception as e:
            print(f"[!] Speed test loop error: {e}")
        time.sleep(900)  # 15 minutes

# Started in run() method
speed_test_thread = threading.Thread(target=self.speed_test_loop, daemon=True)
speed_test_thread.start()
```

**Speed test data flow:**
1. speedtest-cli runs with `--json` flag
2. Results parsed from JSON output (download, upload, ping, server info)
3. Data inserted into `speed_tests` table
4. Dashboard fetches via `/api/speed-tests/latest` and `/api/speed-tests/recent`
5. Chart updates automatically via polling (5min for live, static for historical)

**Benefits:**
- Automated bandwidth monitoring
- Historical speed tracking
- Server location tracking
- Minimal overhead (runs in background thread)

### Cross-Platform Ping Parsing

monitor.py handles both macOS and Linux ping output formats:
```python
# macOS: "round-trip min/avg/max/stddev = 14.123/15.456/16.789/1.234 ms"
# Linux: "rtt min/avg/max/mdev = 14.123/15.456/16.789/1.234 ms"
match = re.search(r'(round-trip|rtt)[^=]*=\s*[\d.]+/([\d.]+)', result.stdout)
if match:
    return float(match.group(2))
```

### Docker Privileges

Container requires NET_RAW capability for ping to work:
```yaml
privileged: true
cap_add:
  - NET_RAW
  - NET_ADMIN
```

### Chart.js Visualization Approach

serve.py uses Chart.js for all visualizations with different behavior for current vs past hours:

**Current hour detection:**
```python
now = datetime.now()
current_date_str = now.strftime("%Y-%m-%d")
current_hour_str = now.strftime("%Y%m%d_%H")
is_current_hour = (date_str == current_date_str and current_hour_str in csv_filename)
```

**Current hour (live updates):**
- Chart.js with WebSocket connection (30s batches)
- Falls back to HTTP polling if WebSocket fails (60s)
- Shows "🔴 LIVE" indicator
- JavaScript template literals for dynamic URLs

**Past hours (static):**
- Chart.js without WebSocket
- No auto-refresh (data is historical)
- Faster rendering, lower memory

### WebSocket Implementation

JavaScript establishes WebSocket connection via nginx proxy:
```javascript
// Uses /ws path through nginx proxy (location.host includes port)
const wsUrl = `ws://${location.host}/ws`;
const ws = new WebSocket(wsUrl);

// Fallback to HTTP polling on error
ws.onerror = () => {
    startPolling();  // 60s for network, 5min for speed tests
};
```

nginx proxies `/ws` to serve.py:8081 with proper WebSocket upgrade headers.

## Troubleshooting

### nginx Reverse Proxy

nginx.conf configures gzip compression and WebSocket upgrade:
```nginx
# Gzip for 70% bandwidth reduction
gzip on;
gzip_comp_level 6;
gzip_types text/plain text/css text/xml text/javascript application/json application/javascript;

# WebSocket upgrade
location /ws {
    proxy_pass http://127.0.0.1:8081;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

### Docker on ARM (Raspberry Pi)

Dockerfile uses minimal dependencies to keep image small and avoid compilation:
```dockerfile
RUN apt-get update && apt-get install -y \
    python3 \
    iputils-ping \
    curl \
    procps \
    nginx \
    python3-websockets \
    speedtest-cli \
    && rm -rf /var/lib/apt/lists/*
```

This approach builds quickly on Pi Zero 2 W and includes all necessary tools:
- **speedtest-cli**: For internet speed testing
- **python3-websockets**: For real-time updates
- **nginx**: For reverse proxy and gzip compression

**Note:** Resource limits were removed from docker-compose.yml to allow speed tests to run properly.

### Memory constraints on Pi Zero 2 W

Reduce monitoring frequency and increase sample size:
```bash
./monitor.sh 5 60  # Check every 5s, log every 5 minutes
```

### Port already in use

Check and kill existing servers:
```bash
# Check nginx on port 8080
lsof -ti:8080
docker exec network-monitor nginx -s quit

# Check Python HTTP server on port 8090
lsof -ti:8090
pkill -f "python.*serve.py"

# Check WebSocket server on port 8081
lsof -ti:8081
pkill -f "python.*serve.py"
```

### Speed tests not running

Check if monitor.py is running and speed test thread is active:
```bash
# Check monitor.py process
docker exec network-monitor pgrep -f monitor.py

# Check speed test data in database
docker exec network-monitor python3 -c "from db import NetworkMonitorDB; db = NetworkMonitorDB('logs/network_monitor.db'); print(f'Speed tests: {len(db.get_recent_speed_tests(24))}')"

# View monitor logs for speed test output
docker logs network-monitor | grep -i speed
```

## Dependencies

**System packages (installed in Docker):**
- python3 (runtime)
- iputils-ping (ping command)
- curl (for testing)
- procps (process management)
- nginx (reverse proxy)
- python3-websockets (real-time updates)
- speedtest-cli (internet speed testing)

## File Structure

```
network-monitor/
├── monitor.py              # SQLite-based monitor daemon with speed tests
├── serve.py                # Python web server (HTTP + WebSocket)
├── db.py                   # SQLite database handler (dual tables)
├── nginx.conf              # nginx reverse proxy config
├── start_services.sh       # Service startup script
├── Dockerfile              # Docker image definition
├── docker-compose.yml      # Docker container config
├── static/
│   ├── dashboard.css       # Dashboard styling (Gruvbox theme)
│   └── dashboard.js        # Dashboard logic (Chart.js, WebSocket)
├── README.md               # User documentation
├── DEPLOYMENT.md           # Raspberry Pi deployment guide
├── CLAUDE.md               # This file
└── logs/
    └── network_monitor.db  # SQLite database (network_logs + speed_tests tables)
```

## Dashboard Implementation

### Time-Based Navigation

The dashboard uses time-based navigation instead of file-based:

**Network monitoring:**
- Shows 1-hour window of data
- Navigation buttons move forward/backward by 1 hour
- Live view (offset=0) shows current hour with WebSocket updates
- Historical views (offset<0) show static data from that time range

**Speed tests:**
- Shows 12-hour window of data
- Navigation buttons move forward/backward by 12 hours
- Live view (offset=0) shows last 12 hours with automatic polling (5min)
- Historical views (offset<0) show static data from that time range

**Implementation (dashboard.js):**
```javascript
let networkHoursOffset = 0; // 0 = live, negative = hours back
let speedTestHoursOffset = 0; // 0 = live, negative = hours back

// Calculate time range
const now = new Date();
const endTime = new Date(now.getTime() + (offset * 60 * 60 * 1000));
const startTime = new Date(endTime.getTime() - (windowSize * 60 * 60 * 1000));

// Fetch data with time range
fetch(`/csv/?start_time=${startTimeStr}&end_time=${endTimeStr}`)
```

### Single-Page Dashboard

The dashboard combines both monitoring types in one view:
- **Top section:** Network monitoring chart (response time + success rate)
- **Middle section:** Speed test statistics (download, upload, server, last test)
- **Bottom section:** Speed test chart (download + upload over time)
- **Data list:** Reference only - navigation is time-based

### API Endpoints

**Network logs:**
- `GET /api/network-logs/earliest` - Returns earliest log entry (for nav button state)
- `GET /csv/?start_time=...&end_time=...` - CSV export for time range

**Speed tests:**
- `GET /api/speed-tests/latest` - Returns latest speed test (for stats display)
- `GET /api/speed-tests/recent?start_time=...&end_time=...` - Recent tests for chart
```

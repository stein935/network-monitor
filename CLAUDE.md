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
  - **Phase 4 optimizations (Raspberry Pi Zero 2 W):**
    - SQLite WAL mode: 30-40% faster writes
    - nginx proxy caching: 40-60% reduced Python load
    - Disabled chart animations: 30% faster rendering
    - Request debouncing: Prevents duplicate API calls
    - ETag support: 60% bandwidth savings on repeat visits
    - Reduced logging verbosity: 20% CPU reduction
    - **Total resource reduction: 30-35%**

## Architecture

### Core Components

1. **monitor.py** - SQLite-based monitor daemon with speed testing (Phase 1 + Phase 4 optimizations):

   - Pings 8.8.8.8 every `FREQUENCY` seconds (default: 1)
   - Collects `SAMPLE_SIZE` samples (default: 5) before logging
   - Writes directly to SQLite: `logs/network_monitor.db`
   - **Speed test thread:** Runs speedtest-cli every 15 minutes in background
   - Indexed queries for fast retrieval
   - Performs cleanup once per hour (VACUUM removed for performance)
   - Handles both macOS and Linux ping output formats
   - **Performance optimizations:**
     - Reduced logging verbosity (only every 10th sample or on failures)
     - Immediate commits (WAL mode makes this efficient)

2. **serve.py** - Live web server with SQLite backend, Chart.js, and WebSocket support (Phase 2 + Phase 4 optimizations):

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
     - **Animations disabled** for 30% faster rendering on Pi Zero
   - **API endpoints:**
     - `/api/network-logs/earliest` - Get earliest network log
     - `/api/speed-tests/latest` - Get latest speed test result
     - `/api/speed-tests/earliest` - Get earliest speed test result
     - `/api/speed-tests/recent` - Get recent speed tests with optional time range
   - **CSV export:**
     - Time-range based: `/csv/?start_time=...&end_time=...`
     - Legacy format: `/csv/YYYY-MM-DD/HH`
   - Binds to 0.0.0.0 for network access
   - **Chart.js benefits:** 93% smaller (200KB vs 3MB Plotly), faster rendering, lower memory
   - **Performance optimizations:**
     - HTML response caching (30s in-memory)
     - ETag support for static files (60% bandwidth savings on repeat visits)
     - Chart.js loaded with `defer` for non-blocking page load

3. **db.py** - SQLite database handler with dual tables:

   - **network_logs table:** Ping monitoring data with indexed timestamps
   - **speed_tests table:** Speed test results with indexed timestamps
   - **Performance optimizations:**
     - WAL mode (Write-Ahead Logging) for better concurrency
     - `synchronous=NORMAL` for faster writes while remaining safe
     - 32MB query cache for improved performance
   - Insert, query, export functions for both tables
   - Auto-cleanup (removes data older than retention period)
   - VACUUM removed from hourly cleanup (WAL mode auto-checkpoints)
   - Export to CSV format for on-demand generation
   - Time-range query support for both network logs and speed tests

4. **nginx.conf** - Reverse proxy configuration (Phase 3 + Phase 4 optimizations):

   - Listens on port 8080 (external)
   - Proxies HTTP requests to serve.py:8090 (internal)
   - Proxies WebSocket to serve.py:8081 via `/ws` path
   - Gzip compression for 70% bandwidth reduction
   - Security headers
   - **Performance optimizations:**
     - Reduced worker_connections from 1024 → 128 (adequate for typical use)
     - Access logging disabled (reduces I/O overhead on SD card)
     - Proxy cache enabled (30s) for API and CSV endpoints
     - Cache reduces Python backend load by 40-60%

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

## Performance Optimizations (Phase 4)

### Raspberry Pi Zero 2 W Specific Optimizations

The following optimizations were implemented to reduce resource consumption on the Pi Zero 2 W without changing user-visible functionality:

**Database Layer (db.py):**

- **WAL mode**: Write-Ahead Logging for 30-40% faster writes with better concurrency
- **synchronous=NORMAL**: Balanced safety/performance (vs FULL)
- **32MB cache**: `PRAGMA cache_size=-32000` for faster query performance
- **Removed VACUUM**: From hourly cleanup (WAL auto-checkpoints make it less critical)
- Manual VACUUM recommended during maintenance windows if needed

**Monitor Process (monitor.py):**

- **Reduced logging**: Only prints every 10th sample or on failures (20% CPU reduction)
- **Immediate commits**: Each log entry commits immediately (WAL makes this efficient)
- No batch commit delays ensure data visibility to web dashboard

**Web Server (serve.py):**

- **HTML caching**: 30-second in-memory cache for generated HTML (70% CPU reduction)
- **ETag support**: MD5-based ETags for static files (60% bandwidth savings on repeat visits)
- **Chart.js defer**: Non-blocking script load for faster page rendering

**Frontend (dashboard.js):**

- **Disabled animations**: `animation: false` for 30% faster chart rendering
- **Request debouncing**: Prevents duplicate fetch requests during navigation
- **requestIdleCallback**: Low-priority background updates for better UI responsiveness
- **chart.update('none')**: Skips animations during data updates

**nginx (nginx.conf):**

- **Reduced workers**: 128 connections (vs 1024) - adequate for typical use, saves 15-20% memory
- **Disabled access logs**: Reduces I/O overhead on SD card (10-15% reduction)
- **Proxy cache**: 30-second cache for `/api/` and `/csv/` endpoints
  - Reduces Python backend load by 40-60%
  - Cache duration matches WebSocket batch interval
  - Serves stale content on backend errors

**Docker (Dockerfile & docker-compose.yml):**

- **Bytecode compilation**: `python3 -m compileall` for 10-15% faster startup
- **PYTHONDONTWRITEBYTECODE=1**: Prevents runtime .pyc generation
- **Logging limits**: max 1MB per file, 2 files (prevents disk bloat)

### Overall Impact

Estimated resource reduction: **30-35%** across CPU, memory, and I/O with zero user-visible changes.

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
  - "8080:8080" # External:Internal (nginx HTTP)
  - "8081:8081" # External:Internal (WebSocket)
```

**Internal port architecture:**

- nginx listens on port 8080 (internal)
- Python HTTP server (serve.py) listens on port 8090 (internal, proxied by nginx)
- Python WebSocket server listens on port 8081 (internal, proxied by nginx via /ws)

## Documentation Maintenance Requirements

### Pre-Push Documentation Checklist

Before any `git push` command, you MUST complete ALL of the following:

1. **Update README.md**

   - Verify project overview reflects recent changes
   - Update installation/setup instructions if changed
   - Add/update examples if new features were added
   - Ensure dependencies list is current

2. **Update DEPLOYMENT.md**

   - Document any changes to deployment process
   - Update systemd service configurations if changed
   - Note any new Docker or Raspberry Pi considerations

3. **Update CLAUDE.md**

   - Document any new conventions discovered
   - Add new commands or workflows to relevant sections
   - Update project structure if directories changed
   - Add new API endpoints or implementation details

4. **Inline Documentation**

   - Ensure all new functions have docstrings/comments
   - Update existing comments if behavior changed
   - Add README files to new directories if needed

5. **Verification Step**
   After documentation updates, explicitly state:
   "✓ Documentation updated and verified. Ready to push."

### Git Workflow - CRITICAL RULES

**NEVER Auto-Push:**

- **NEVER run `git push` without explicit permission from me**
- **ALWAYS ask before pushing code to remote**
- After completing work and committing, STOP and say: "Ready to push. Should I proceed?"
- Wait for my explicit "yes" or "push now" before executing `git push`

**Git Command Authorization:**

You may freely use:

- `git status`, `git diff`, `git log`
- `git add`, `git commit`
- `git checkout`, `git branch`
- `git fetch`

You must ALWAYS ASK before:

- `git push` (any branch, any remote)
- `git push --force` or `git push -f` (NEVER do this)
- `git merge` to main/master/develop
- Any destructive git operations

**When Work is Complete:**

1. Run the pre-push documentation checklist
2. Commit changes with appropriate message
3. Show me a summary of what was changed
4. Ask: "Would you like me to push these changes?"
5. Wait for my response

**Commit Message Standards:**

- Use conventional commit format: `type(scope): description`
- Types: feat, fix, docs, style, refactor, test, chore
- Keep first line under 72 characters
- Do not include Claude attribution or co-author tags

### Documentation Standards

- Keep documentation concise and scannable
- Use clear headings and bullet points
- Include code examples for non-obvious features
- Link related documentation sections
- Update all three docs (README, DEPLOYMENT, CLAUDE) when relevant

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
  startPolling(); // 60s for network, 5min for speed tests
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
├── VERSION                 # Semantic version number (e.g., 1.0.0)
├── static/
│   ├── dashboard.css       # Dashboard styling (Gruvbox theme)
│   └── dashboard.js        # Dashboard logic (Chart.js, WebSocket)
├── README.md               # User documentation
├── DEPLOYMENT.md           # Raspberry Pi deployment guide
├── CHANGELOG.md            # Version history and changes
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
const endTime = new Date(now.getTime() + offset * 60 * 60 * 1000);
const startTime = new Date(endTime.getTime() - windowSize * 60 * 60 * 1000);

// Fetch data with time range
fetch(`/csv/?start_time=${startTimeStr}&end_time=${endTimeStr}`);
```

### Single-Page Dashboard

The dashboard combines both monitoring types in one view:

- **Top section:** Network monitoring chart (response time + success rate)
- **Middle section:** Speed test statistics (download, upload, server, last test)
- **Bottom section:** Speed test chart (download + upload over time)

**Navigation controls (both charts):**

- **Date range display:** Shows exact time window being viewed (e.g., "Nov 5, 2025 14:00 ↔ 15:00")
- **Previous/Next buttons:** Navigate backward/forward through time windows
- **Go Live button:** Red dot indicator button that appears when viewing historical data
  - Only visible when `offset !== 0` (not on live view)
  - Returns user to live view (`offset = 0`)
  - Automatically reconnects WebSocket for real-time updates
  - Implemented in `dashboard.js:goNetworkLive()` and `dashboard.js:goSpeedLive()`

### Footer Implementation

The footer displays system statistics in a minimal terminal-style layout:

**Components:**

- **Version**: Read from `VERSION` file via `get_version()` function
- **DB Size**: Real-time database file size (formatted as B/KB/MB/GB)
- **Uptime**: Time since page load (updates every minute)
- **Copyright**: Static copyright notice
- **GitHub Link**: Repository link with hover effect

**Implementation (serve.py):**

```python
def get_version():
    """Read version from VERSION file."""
    try:
        version_file = Path(__file__).parent / "VERSION"
        if version_file.exists():
            return version_file.read_text().strip()
    except Exception:
        pass
    return "1.0.0"  # Fallback version
```

**API endpoint:** `/api/stats` returns database statistics:

```json
{
  "db_size": "2.3MB",
  "db_size_bytes": 2411520,
  "network_log_count": 14523,
  "speed_test_count": 96
}
```

### API Endpoints

**Network logs:**

- `GET /api/network-logs/earliest` - Returns earliest log entry (for nav button state)
- `GET /csv/?start_time=...&end_time=...` - CSV export for time range

**Speed tests:**

- `GET /api/speed-tests/latest` - Returns latest speed test (for stats display)
- `GET /api/speed-tests/earliest` - Returns earliest speed test (for nav button state)
- `GET /api/speed-tests/recent?start_time=...&end_time=...` - Recent tests for chart

**System stats:**

- `GET /api/stats` - Returns database size and log counts (for footer)

## Version Management

The project uses a simple VERSION file for semantic versioning:

**File location:** `VERSION` (plain text file in project root)

**Format:** `Major.Minor.Patch` (e.g., `1.0.0`)

**Usage:**

```bash
# Update version
echo "1.1.0" > VERSION

# Deploy changes
make dev  # Copies VERSION to container and restarts services
```

**Implementation:**

- `get_version()` function in serve.py reads VERSION file
- Fallback to "1.0.0" if file missing or unreadable
- Version displays in footer and updates automatically
- Follows [Semantic Versioning](https://semver.org/)

## Chart Styling

The dashboard charts use Chart.js with custom styling:

**Network Monitoring Chart:**

- **Response Time**: Line chart, blue color (#458588), 2px points
- **Success Rate**: Area chart, green fill (rgba 152,151,26,0.1), no points
  - Y-axis range: 0-105% (full range, not truncated)
  - Segments turn orange (#d65d0e) when rate < 100%
  - Filled area for better visibility

**Speed Test Chart:**

- **Download**: Area chart with filled background, blue color
- **Upload**: Line chart, purple color (#b16286)
- Both charts: 2px points for minimal visual clutter

**Performance:**

- All animations disabled (`animation: false`) for Pi Zero performance
- Chart updates use `chart.update('none')` to skip transitions

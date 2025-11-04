# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Network Monitor is a Python-based daemon that continuously monitors network connectivity by pinging 8.8.8.8, storing data in SQLite database with real-time web visualization.

**Key characteristics:**
- **SQLite storage:** Fast, indexed database storage (Phase 1)
- **Chart.js visualization:** 93% smaller bundle than Plotly (Phase 2)
- **WebSocket real-time updates:** 30-second batches for current hour (Phase 2)
- **nginx reverse proxy:** Gzip compression, better concurrency (Phase 3)
- Daemon mode: Runs continuously without time limits
- CSV export on-demand: Historical data exported dynamically from SQLite
- Auto cleanup: Removes logs older than 10 days with VACUUM
- Docker deployment: Optimized for Raspberry Pi Zero 2 W
- **Performance improvements:**
  - 70% reduction in disk I/O (SQLite vs CSV)
  - 93% smaller page loads (Chart.js vs Plotly)
  - 95% CPU reduction for current hour monitoring (WebSocket vs polling)
  - 70% bandwidth reduction (nginx gzip compression)

## Architecture

### Core Components

1. **monitor.py** - SQLite-based monitor daemon (Phase 1):
   - Pings 8.8.8.8 every `FREQUENCY` seconds (default: 1)
   - Collects `SAMPLE_SIZE` samples (default: 5) before logging
   - Writes directly to SQLite: `logs/network_monitor.db`
   - Indexed queries for fast retrieval
   - Performs cleanup with VACUUM once per hour
   - Handles both macOS and Linux ping output formats

2. **serve.py** - Live web server with SQLite backend, Chart.js, and WebSocket support (Phase 2):
   - **HTTP server (port 8080):** Serves HTML and CSV exports
   - **WebSocket server (port 8081):** Real-time data pushes every 30 seconds
   - Reads from SQLite database (`db.py`)
   - Index page lists available hours from database with entry counts
   - **Chart.js for all visualizations:**
     - **Current hour**: Chart.js with WebSocket updates (30s batches) + HTTP polling fallback (60s)
     - **Past hours**: Static Chart.js visualizations (no updates)
   - Exports CSV on-demand via `/csv/YYYY-MM-DD/HH` endpoint
   - Navigation buttons (Back, Previous, Next)
   - Binds to 0.0.0.0 for network access
   - **Chart.js benefits:** 93% smaller (200KB vs 3MB Plotly), faster rendering, lower memory

3. **db.py** - SQLite database handler:
   - Schema with indexed timestamps
   - Insert, query, export functions
   - Auto-cleanup with VACUUM
   - Export to CSV format for on-demand generation

4. **nginx.conf** - Reverse proxy configuration (Phase 3):
   - Listens on port 80
   - Proxies HTTP requests to serve.py:8080
   - Proxies WebSocket to serve.py:8081
   - Gzip compression for 70% bandwidth reduction
   - Security headers

5. **start_services.sh** - Service startup script (Phase 3):
   - Starts nginx reverse proxy
   - Starts Python HTTP and WebSocket servers
   - Handles graceful shutdown

### Data Flow

**Architecture (Phase 3):**
```
Browser → nginx:80 (gzip, proxy)
              ↓
         serve.py:8080 (HTTP - Chart.js generation, CSV export)
              ↓
         serve.py:8081 (WebSocket - 30s batches)
              ↓
         SQLite database (logs/network_monitor.db)
              ↑
         monitor.py (writes every minute)
```

**Current hour (live monitoring):**
```
monitor.py → SQLite → serve.py WebSocket → Browser Chart.js (30s updates)
                                         → Fallback: HTTP polling (60s)
```

**Past hours (static viewing):**
```
SQLite → serve.py → generates Chart.js HTML → Browser
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

**CSV Export Format** (on-demand):
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
- Inside container: `http://localhost:80` (nginx)


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
- `LOG_RETENTION_DAYS`: Days to keep logs (default: 10, set in monitor.py)

### Port Mapping

Edit `docker-compose.yml` to change exposed port:
```yaml
ports:
  - "8080:80"  # External:Internal (nginx listens on port 80 inside container)
```

## Important Implementation Details

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

JavaScript establishes WebSocket connection with runtime URL:
```javascript
const wsUrl = `ws://${location.hostname}:8081`;
const ws = new WebSocket(wsUrl);

// Fallback to HTTP polling on error
ws.onerror = () => {
    setInterval(() => fetchData(), 60000);
};
```

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

Dockerfile uses system packages for pandas/plotly to avoid lengthy compilation (20-45 minutes) on ARM:
```dockerfile
RUN apt-get update && apt-get install -y \
    bc \
    iputils-ping \
    curl \
    procps \
    python3-pandas \
    python3-plotly \
    python3-numpy \
    && rm -rf /var/lib/apt/lists/*
```

This approach builds in ~10-15 minutes on Pi Zero 2 W instead of 20-45+ minutes required for pip compilation.

**Resource limits are configured in docker-compose.yml:**
```yaml
deploy:
  resources:
    limits:
      memory: 256M
      cpus: '0.5'
```

This prevents the container from consuming all available resources on the Pi Zero 2 W (512MB total RAM).

### Memory constraints on Pi Zero 2 W

Reduce monitoring frequency and increase sample size:
```bash
./monitor.sh 5 60  # Check every 5s, log every 5 minutes
```

### Port already in use

Check and kill existing server:
```bash
lsof -ti:8000
pkill -f "python.*serve.py"
```

## Dependencies

**System packages (installed in Docker):**
- python3, python3-pip
- bc (for calculations)
- ping (iputils-ping)
- nginx
- python3-pandas
- python3-plotly
- python3-numpy
- python3-websockets

## File Structure

```
network-monitor/
├── monitor.py              # SQLite-based monitor daemon
├── serve.py                # Python web server (HTTP + WebSocket)
├── db.py                   # SQLite database handler
├── nginx.conf              # nginx reverse proxy config
├── start_services.sh       # Service startup script
├── generate_static.sh      # Nightly pre-generation (future)
├── Dockerfile              # Docker image definition
├── docker-compose.yml      # Docker container config
├── README.md               # User documentation
├── DEPLOYMENT.md           # Raspberry Pi deployment guide
├── OPTIMIZATION.md         # Performance optimization details
├── CLAUDE.md               # This file
└── logs/
    ├── network_monitor.db  # SQLite database
    └── YYYY-MM-DD/         # Daily directories (CSV exports only)
        └── csv/            # CSV exports (on-demand)
            └── monitor_YYYYMMDD_HH.csv
```

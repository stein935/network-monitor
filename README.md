# Network Monitor

A Python-based daemon for monitoring network connectivity, response times, and internet speed, with SQLite storage and real-time web visualization.

## Features

- **SQLite storage** - Fast, indexed database with automatic cleanup (Phase 1)
- **Chart.js visualization** - 93% smaller pages than Plotly (Phase 2)
- **WebSocket real-time updates** - 30-second batches for live monitoring (Phase 2)
- **nginx reverse proxy** - Gzip compression, better performance (Phase 3)
- **Internet speed testing** - Automated tests every 15 minutes via speedtest-cli
- **Dual monitoring** - Network latency (ping) + bandwidth (speed tests)
- **Single-page dashboard** - Unified view of all monitoring data
- **Daemon mode** - Runs continuously without time limits
- **Auto cleanup** - Keeps 30 days of logs
- **CSV export on-demand** - Export historical data when needed
- **Gruvbox theme** - Easy on the eyes for long monitoring
- **Docker deployment** - Optimized for Raspberry Pi Zero 2 W

## Quick Start (Docker)

For complete deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

```bash
# 1. Clone and enter directory
git clone https://github.com/stein935/network-monitor.git
cd network-monitor

# 2. Build and start container
docker compose build
docker compose up -d

# 3. Setup systemd services (see DEPLOYMENT.md)

# 4. Access at http://<raspberry-pi-ip>:8080
```

## Architecture

**Data flow:**
```
Browser → nginx:8080 (gzip, reverse proxy)
              ↓
         serve.py:8090 (HTTP - Chart.js, API, CSV export)
         serve.py:8081 (WebSocket - 30s updates via /ws)
              ↓
         SQLite database (logs/network_monitor.db)
              ↑
         monitor.py (network logs every minute + speed tests every 15 min)
```

**Performance optimizations:**
- Phase 1 (SQLite): 70% reduction in disk I/O vs CSV
- Phase 2 (Chart.js): 93% smaller pages (200KB vs 3MB Plotly)
- Phase 2 (WebSocket): 95% CPU reduction vs HTTP polling
- Phase 3 (nginx): 70% bandwidth reduction via gzip

## Features Explained

### Real-Time Monitoring
- **Network monitoring**: 1-hour window with WebSocket updates every 30 seconds
- **Speed testing**: 12-hour window with automated tests every 15 minutes
- **Live indicator**: Shows when viewing current data
- **Fallback**: HTTP polling (60s network, 5min speed) if WebSocket fails
- **Historical data**: Time-based navigation for viewing past data

### Data Storage
- **SQLite database**: `logs/network_monitor.db`
  - `network_logs` table: Ping monitoring data
  - `speed_tests` table: Speed test results
- **CSV export**: On-demand via `/csv/?start_time=...&end_time=...` endpoint
- **Auto-cleanup**: Removes data older than 30 days with VACUUM

### Web Dashboard
- **Single-page design**: Unified view of all monitoring
- **Network chart**: Dual y-axis (response time + success rate)
- **Speed test chart**: Download + upload bandwidth over time
- **Stats display**: Latest speed test results (download, upload, server)
- **Time-based navigation**: Previous/Next buttons for both charts
- **Gruvbox theme**: Dark, easy on eyes
- **Color coding**: Green (100%), Orange (partial), Red (fail)

## Configuration

### Monitor Parameters

Edit systemd service or run manually:

```bash
docker exec network-monitor python3 /app/monitor.py [frequency] [sample_size]

# Example: python3 monitor.py 1 60
# Pings every 1s, logs every 60 samples (1 minute per data point)
```

**Parameters:**
- `frequency`: Seconds between pings (default: 1)
- `sample_size`: Number of pings per log entry (default: 5)
- Retention: 30 days (configurable in monitor.py)
- Speed tests: Automatically run every 15 minutes (hardcoded)

### Port Configuration

Edit `docker-compose.yml`:
```yaml
ports:
  - "8080:8080"  # External:Internal (nginx HTTP)
  - "8081:8081"  # External:Internal (WebSocket)
```

**Internal port architecture:**
- nginx listens on port 8080 (proxies requests)
- Python HTTP server on port 8090 (internal, proxied by nginx)
- WebSocket server on port 8081 (proxied via `/ws` path)

## Data Format

### SQLite Schema

**Network Logs Table:**
```sql
CREATE TABLE network_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    status TEXT NOT NULL,              -- CONNECTED or DISCONNECTED
    response_time REAL,                 -- Avg ping time in ms
    success_count INTEGER NOT NULL,     -- Successful pings
    total_count INTEGER NOT NULL,       -- Total pings in sample
    failed_count INTEGER NOT NULL,      -- Failed pings
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_timestamp ON network_logs(timestamp);
```

**Speed Tests Table:**
```sql
CREATE TABLE speed_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    download_mbps REAL NOT NULL,        -- Download speed in Mbps
    upload_mbps REAL NOT NULL,          -- Upload speed in Mbps
    ping_ms REAL,                       -- Speedtest ping in ms
    server_host TEXT,                   -- Test server hostname
    server_name TEXT,                   -- Test server name
    server_country TEXT,                -- Test server country
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_speed_timestamp ON speed_tests(timestamp);
```

### CSV Export Format

**Network logs:**
```
timestamp, status, response_time, success_count, total_count, failed_count
2025-11-03 23:45:00, CONNECTED, 14.5, 60, 60, 0
```

## Directory Structure

```
network-monitor/
├── monitor.py              # Python monitor daemon (ping + speed tests)
├── serve.py                # Web server (HTTP + WebSocket)
├── db.py                   # SQLite database handler (dual tables)
├── nginx.conf              # Reverse proxy config
├── start_services.sh       # Service startup script
├── Dockerfile              # Docker image
├── docker-compose.yml      # Container config
├── static/
│   ├── dashboard.css       # Dashboard styling (Gruvbox theme)
│   └── dashboard.js        # Dashboard logic (Chart.js, WebSocket)
├── DEPLOYMENT.md           # Full deployment guide
└── logs/
    └── network_monitor.db  # SQLite database (network_logs + speed_tests)
```

## Management

### Systemd Services (Raspberry Pi)

See [DEPLOYMENT.md](DEPLOYMENT.md) for full setup instructions.

```bash
# Check status
systemctl status 'network-monitor-*'

# Restart services
sudo systemctl restart network-monitor-daemon.service
sudo systemctl restart network-monitor-server.service

# View logs
sudo journalctl -u network-monitor-daemon.service -f
sudo journalctl -u network-monitor-server.service -f
```

### Docker Commands

```bash
# Check processes
docker exec network-monitor pgrep -f monitor.py
docker exec network-monitor ps aux | grep -E "nginx|serve.py"

# Stop processes
docker exec network-monitor pkill -f monitor.py
docker exec network-monitor nginx -s quit
docker exec network-monitor pkill -f serve.py

# View logs
docker logs network-monitor -f
```

## Troubleshooting

### No data showing
```bash
# Check monitor is running
docker exec network-monitor pgrep -f monitor.py

# Check database
docker exec network-monitor python3 -c "from db import NetworkMonitorDB; db = NetworkMonitorDB('logs/network_monitor.db'); print(f'Hours: {len(db.get_available_hours())}')"

# Restart monitor
sudo systemctl restart network-monitor-daemon.service
```

### WebSocket disconnected
```bash
# Check server logs
sudo journalctl -u network-monitor-server.service | grep WebSocket

# Rebuild container
docker compose down
docker compose build --no-cache
docker compose up -d

# Hard refresh browser (Ctrl+Shift+R)
```

### Speed tests not running
```bash
# Check monitor process
docker exec network-monitor pgrep -f monitor.py

# Check speed test data
docker exec network-monitor python3 -c "from db import NetworkMonitorDB; db = NetworkMonitorDB('logs/network_monitor.db'); print(f'Speed tests: {len(db.get_recent_speed_tests(24))}')"

# View monitor logs
docker logs network-monitor | grep -i speed
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for more troubleshooting steps.

## Performance

Optimized for Raspberry Pi Zero 2 W (512MB RAM):

| Metric | Improvement |
|--------|-------------|
| Disk I/O | 70% reduction (SQLite vs CSV) |
| Page size | 93% smaller (Chart.js vs Plotly) |
| CPU usage | 95% reduction (WebSocket vs polling) |
| Bandwidth | 70% reduction (nginx gzip) |
| Memory | 62% reduction (optimized stack) |

## API Endpoints

The dashboard uses these API endpoints for data retrieval:

**Network monitoring:**
- `GET /api/network-logs/earliest` - Get earliest network log entry
- `GET /csv/?start_time=YYYY-MM-DD HH:MM:SS&end_time=YYYY-MM-DD HH:MM:SS` - CSV export for time range

**Speed tests:**
- `GET /api/speed-tests/latest` - Get latest speed test result
- `GET /api/speed-tests/recent?start_time=...&end_time=...` - Get speed tests in time range
- `GET /api/speed-tests/recent?hours=24` - Get speed tests from last N hours (default: 24)

**WebSocket:**
- `WS /ws` - Real-time updates for network logs (30-second batches)

## Documentation

- [DEPLOYMENT.md](DEPLOYMENT.md) - Complete Raspberry Pi deployment guide
- [CLAUDE.md](CLAUDE.md) - Developer documentation

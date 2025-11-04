# Network Monitor

A Python-based daemon for monitoring network connectivity and response times, with SQLite storage and real-time web visualization.

## Features

- **SQLite storage** - Fast, indexed database with automatic cleanup (Phase 1)
- **Chart.js visualization** - 93% smaller pages than Plotly (Phase 2)
- **WebSocket real-time updates** - 30-second batches for current hour (Phase 2)
- **nginx reverse proxy** - Gzip compression, better performance (Phase 3)
- **Daemon mode** - Runs continuously without time limits
- **Auto cleanup** - Keeps only 10 days of logs
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
Browser → nginx:80 (gzip, reverse proxy)
              ↓
         serve.py:8080 (HTTP - Chart.js, CSV export)
         serve.py:8081 (WebSocket - 30s updates)
              ↓
         SQLite database (logs/network_monitor.db)
              ↑
         monitor.py (writes every minute)
```

**Performance optimizations:**
- Phase 1 (SQLite): 70% reduction in disk I/O vs CSV
- Phase 2 (Chart.js): 93% smaller pages (200KB vs 3MB Plotly)
- Phase 2 (WebSocket): 95% CPU reduction vs HTTP polling
- Phase 3 (nginx): 70% bandwidth reduction via gzip

## Features Explained

### Real-Time Monitoring
- **Current hour**: WebSocket updates every 30 seconds with live indicator
- **Fallback**: HTTP polling (60s) if WebSocket fails
- **Past hours**: Static Chart.js visualizations

### Data Storage
- **SQLite database**: `logs/network_monitor.db`
- **CSV export**: On-demand via `/csv/YYYY-MM-DD/HH` endpoint
- **Auto-cleanup**: Removes data older than 10 days with VACUUM

### Web Dashboard
- **Index page**: Lists all available hours with entry counts
- **Navigation**: Back, Previous, Next buttons
- **Chart.js**: Dual y-axis (response time + success rate)
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
- Retention: 10 days (configurable in monitor.py)

### Port Configuration

Edit `docker-compose.yml`:
```yaml
ports:
  - "8080:80"  # External:Internal (nginx on port 80 inside container)
```

## Data Format

### SQLite Schema

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

### CSV Export Format

```
timestamp, status, response_time, success_count, total_count, failed_count
2025-11-03 23:45:00, CONNECTED, 14.5, 60, 60, 0
```

## Directory Structure

```
network-monitor/
├── monitor.py              # Python monitor daemon
├── serve.py                # Web server (HTTP + WebSocket)
├── db.py                   # SQLite database handler
├── nginx.conf              # Reverse proxy config
├── start_services.sh       # Service startup script
├── Dockerfile              # Docker image
├── docker-compose.yml      # Container config
├── DEPLOYMENT.md           # Full deployment guide
├── OPTIMIZATION.md         # Performance details
└── logs/
    ├── network_monitor.db  # SQLite database
    └── YYYY-MM-DD/         # CSV exports (on-demand)
        └── csv/
            └── monitor_YYYYMMDD_HH.csv
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

## Documentation

- [DEPLOYMENT.md](DEPLOYMENT.md) - Complete Raspberry Pi deployment guide
- [OPTIMIZATION.md](OPTIMIZATION.md) - Performance optimization details
- [CLAUDE.md](CLAUDE.md) - Developer documentation

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Network Monitor is a bash-based daemon that continuously monitors network connectivity by pinging 8.8.8.8, logging response times and connection status to hourly CSV files. It includes Python-based web visualization tools with a Gruvbox-themed dashboard.

**Key characteristics:**
- **SQLite storage:** Fast, indexed database storage (Phase 1)
- **Chart.js visualization:** 93% smaller bundle than Plotly (Phase 2)
- **WebSocket real-time updates:** 30-second batches for current hour (Phase 2)
- Daemon mode: Runs continuously without time limits
- CSV export on-demand: Historical data exported dynamically from SQLite
- Auto cleanup: Removes logs older than 10 days with VACUUM
- Dual deployment: Runs natively on macOS/Linux or in Docker on Raspberry Pi Zero 2 W
- **Performance improvements:**
  - 70% reduction in disk I/O (SQLite vs CSV)
  - 93% smaller page loads (Chart.js vs Plotly)
  - 95% CPU reduction for current hour monitoring (WebSocket vs polling)

## Architecture

### Core Components

1. **monitor.py** - SQLite-based monitor daemon (Phase 1 - recommended):
   - Pings 8.8.8.8 every `FREQUENCY` seconds (default: 1)
   - Collects `SAMPLE_SIZE` samples (default: 5) before logging
   - Writes directly to SQLite: `logs/network_monitor.db`
   - Indexed queries for fast retrieval
   - Performs cleanup with VACUUM once per hour
   - Handles both macOS and Linux ping output formats

   **Legacy:** `monitor.sh` still available for CSV-based logging

2. **visualize.py** - Generates static HTML visualizations:
   - Reads CSV and creates dual y-axis Plotly charts
   - Response time (primary y-axis, left)
   - Success rate percentage (secondary y-axis, right)
   - Saves to `logs/YYYY-MM-DD/html/monitor_YYYYMMDD_HH_visualization.html`
   - Gruvbox dark theme with color-coded markers

3. **serve.py** - Live web server with SQLite backend, Chart.js, and WebSocket support (Phase 2):
   - **HTTP server (port 8080):** Serves HTML and CSV exports
   - **WebSocket server (port 8081):** Real-time data pushes every 30 seconds
   - Reads from SQLite database (`db.py`)
   - Index page lists available hours from database with entry counts
   - **Hybrid approach for optimal performance:**
     - **Current hour**: Chart.js visualization with WebSocket updates (30s batches) + HTTP polling fallback (60s)
     - **Past hours**: Static Plotly HTML generated once and cached forever
   - Exports CSV on-demand via `/csv/YYYY-MM-DD/HH` endpoint
   - Navigation buttons (Back, Previous, Next)
   - Binds to 0.0.0.0 for network access
   - **Chart.js benefits:** 93% smaller (200KB vs 3MB Plotly), faster rendering, lower memory

4. **db.py** - SQLite database handler:
   - Schema with indexed timestamps
   - Insert, query, export functions
   - Auto-cleanup with VACUUM
   - Export to CSV format for visualization

### Data Flow

**For current hour (live monitoring with Phase 2 optimizations):**
```
monitor.py (ping loop)
    ↓
SQLite database (logs/network_monitor.db)
    ↓
serve.py WebSocket server → broadcasts updates every 30s
    ↓
Browser Chart.js → receives WebSocket updates (30s batches)
    ↓
Fallback: HTTP polling if WebSocket fails (60s)
```

**For past hours (historical viewing):**
```
SQLite database (logs/network_monitor.db)
    ↓
serve.py → exports CSV → visualize.py (called once)
    ↓
logs/YYYY-MM-DD/html/monitor_YYYYMMDD_HH_visualization.html (cached)
    ↓
serve.py → serves cached HTML
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

### Native (macOS/Linux)

**Setup virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
```

**Run monitor daemon (SQLite - recommended):**
```bash
python3 monitor.py [frequency] [sample_size]
# Example: python3 monitor.py 1 60  # Check every 1s, log every 60 samples
# Database: logs/network_monitor.db
```

**Run monitor daemon (Legacy CSV):**
```bash
./monitor.sh [frequency] [sample_size]
```

**Static visualization:**
```bash
./visualize.sh logs/2025-10-30/csv/monitor_20251030_16.csv
```

**Live web server:**
```bash
./serve.sh [logs_dir] [port]
# Example: ./serve.sh logs 8080
```

**Stop processes:**
```bash
pkill -f monitor.py       # SQLite monitor
pkill -f monitor.sh       # Legacy monitor
pkill -f "python.*serve.py"
```

### Docker (Raspberry Pi deployment)

**Build and start container:**
```bash
docker compose build
docker compose up -d
```

**Start services inside container (SQLite):**
```bash
docker exec -d network-monitor python3 /app/monitor.py 1 60
docker exec -d network-monitor python3 /app/serve.py /app/logs 80
```

**Legacy CSV mode:**
```bash
docker exec network-monitor /bin/bash -c "cd /app && ./monitor.sh 1 60"
```

**Check status:**
```bash
docker ps | grep network-monitor
docker logs network-monitor
docker exec network-monitor pgrep -f monitor.sh
docker exec network-monitor ps aux
docker stats network-monitor --no-stream
```

**Stop processes inside container:**
```bash
docker exec network-monitor pkill -f monitor.sh
docker exec network-monitor pkill -f serve.py
# Or restart entire container: docker compose restart
```

**Access web dashboard:**
- Local Pi: `http://localhost:8080`
- Network: `http://<pi-ip>:8080`

**Update deployment:**
```bash
git pull origin main
docker compose down
docker compose build
docker compose up -d
```

## Systemd Services (Raspberry Pi)

Three systemd services manage the Docker deployment:

1. `network-monitor-container.service` - Starts/stops Docker container
2. `network-monitor-daemon.service` - Runs monitor.sh inside container
3. `network-monitor-server.service` - Runs serve.sh inside container

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
- `SAMPLE_SIZE`: Number of pings to average before logging (default: 5)
- `LOG_RETENTION_DAYS`: Days to keep logs (default: 10, set in monitor.sh line 6)

### Port Mapping

Edit `docker-compose.yml` to change exposed port:
```yaml
ports:
  - "8080:80"  # External:Internal
```

### Server Port (Native)

Pass as second argument to serve.sh:
```bash
./serve.sh logs 8080
```

## Important Implementation Details

### Cross-Platform Ping Parsing

monitor.sh handles both macOS and Linux ping output formats:
```bash
# macOS: "round-trip min/avg/max/stddev = 14.123/15.456/16.789/1.234 ms"
# Linux: "rtt min/avg/max/mdev = 14.123/15.456/16.789/1.234 ms"
RESPONSE_TIME=$(echo "$PING_RESULT" | grep -oE '(round-trip|rtt) [^=]*= [0-9]+\.[0-9]+/[0-9]+\.[0-9]+' | grep -oE '/[0-9]+\.[0-9]+' | head -1 | sed 's/\///')
```

### Hourly File Rollover

monitor.sh checks on each log write if the hour has changed:
```bash
CURRENT_LOG_FILE=$(get_log_file)
if [ "$CURRENT_LOG_FILE" != "$LOG_FILE" ]; then
    LOG_FILE="$CURRENT_LOG_FILE"
    # Create header if new file
    if [ ! -f "$LOG_FILE" ]; then
        echo "timestamp, status, response_time, success_count, total_count, failed_count" >"$LOG_FILE"
    fi
fi
```

### Docker Privileges

Container requires NET_RAW capability for ping to work:
```yaml
privileged: true
cap_add:
  - NET_RAW
  - NET_ADMIN
```

### serve.py Navigation Logic

serve.py finds all CSV files and determines prev/next URLs:
```python
all_csv_files = sorted(self.logs_dir.rglob("*/csv/*.csv"))
current_index = # find index of current file
prev_url = f"/view/{prev_date}/{prev_file.name}"  # if exists
next_url = f"/view/{next_date}/{next_file.name}"  # if exists
```

### Hybrid Visualization Optimization

serve.py implements a hybrid approach for optimal performance on resource-constrained devices:

**Current hour detection:**
```python
now = datetime.now()
current_date_str = now.strftime("%Y-%m-%d")
current_hour_str = now.strftime("%Y%m%d_%H")
is_current_hour = (date_str == current_date_str and current_hour_str in csv_filename)
```

**Dynamic visualization (current hour):**
- Browser fetches CSV directly via `/csv/` endpoint
- JavaScript parses CSV and updates Plotly chart
- Updates every 60 seconds without page reload
- Shows "🔴 LIVE" indicator
- Zero Python/Plotly overhead per update (~KB CSV vs ~MB HTML)

**Static visualization (past hours):**
- HTML generated once on first access
- Cached forever (past hours never change)
- Subsequent views serve from cache
- Massive CPU/disk I/O savings

**Performance impact:**
- Current hour: ~90% reduction in CPU usage (no HTML regeneration)
- Past hours: ~100% reduction after first generation (pure cache)
- Ideal for Pi Zero 2 W with limited resources

### Auto-Refresh Implementation

JavaScript pauses refresh when tab is hidden:
```javascript
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        stopAutoRefresh();
    } else {
        startAutoRefresh();
    }
});
```

## Troubleshooting

### Docker environment detection

Shell scripts (serve.sh, visualize.sh) and serve.py detect Docker by checking for `/.dockerenv`:
```bash
# In shell scripts
if [ -f "/.dockerenv" ]; then
    python3 "$SCRIPT_DIR/serve.py" "$@"  # Use system python3
else
    source "$SCRIPT_DIR/venv/bin/activate"  # Use venv
fi
```

```python
# In serve.py
if Path("/.dockerenv").exists():
    python_executable = "python3"  # System packages
else:
    python_executable = str(venv_python)  # Venv
```

This allows the same scripts to work in both Docker (system packages) and native (venv) environments.

### Venv not activating in shell scripts

The wrapper scripts (serve.sh, visualize.sh) automatically create and use venv in native environments:
```bash
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    pip install -r requirements.txt
fi
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

**System:**
- bash
- bc (for calculations)
- ping (iputils-ping on Linux)
- Python 3.7+

**Python packages (requirements.txt):**
- pandas==2.0.3
- plotly==5.17.0

## File Structure

```
network-monitor/
├── monitor.sh              # Main daemon script
├── serve.sh                # Web server wrapper
├── visualize.sh            # Visualization wrapper
├── serve.py                # Python web server
├── visualize.py            # Python visualization generator
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker image definition
├── docker-compose.yml      # Docker container config
├── README.md               # User documentation
├── DEPLOYMENT.md           # Raspberry Pi deployment guide
├── venv/                   # Python virtual environment (auto-created)
└── logs/
    └── YYYY-MM-DD/         # Daily log directory
        ├── csv/            # CSV data files
        │   └── monitor_YYYYMMDD_HH.csv
        └── html/           # Generated visualizations
            └── monitor_YYYYMMDD_HH_visualization.html
```

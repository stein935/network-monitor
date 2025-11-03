# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Network Monitor is a bash-based daemon that continuously monitors network connectivity by pinging 8.8.8.8, logging response times and connection status to hourly CSV files. It includes Python-based web visualization tools with a Gruvbox-themed dashboard.

**Key characteristics:**
- Daemon mode: Runs continuously without time limits
- Hourly log files: Automatically creates new CSV files each hour with appending support
- Automatic date rollover: Creates new date directories at midnight
- Auto cleanup: Removes logs older than 10 days (configurable via `LOG_RETENTION_DAYS` in monitor.sh)
- Dual deployment: Runs natively on macOS/Linux or in Docker on Raspberry Pi Zero 2 W

## Architecture

### Core Components

1. **monitor.sh** - Main daemon that:
   - Pings 8.8.8.8 every `FREQUENCY` seconds (default: 1)
   - Collects `SAMPLE_SIZE` samples (default: 5) before logging
   - Writes to hourly CSV files: `logs/YYYY-MM-DD/csv/monitor_YYYYMMDD_HH.csv`
   - Performs cleanup of old logs once per hour
   - Handles both macOS and Linux ping output formats

2. **visualize.py** - Generates static HTML visualizations:
   - Reads CSV and creates dual y-axis Plotly charts
   - Response time (primary y-axis, left)
   - Success rate percentage (secondary y-axis, right)
   - Saves to `logs/YYYY-MM-DD/html/monitor_YYYYMMDD_HH_visualization.html`
   - Gruvbox dark theme with color-coded markers

3. **serve.py** - Live web server with HTTP request handling:
   - Index page listing all CSV files organized by date
   - Regenerates visualization fresh on each `/view/` request
   - Injects navigation buttons (Back, Previous, Next)
   - Injects auto-refresh script (60 seconds when tab visible)
   - Binds to 0.0.0.0 for network access
   - Default port: 8000 (or 80 inside Docker)

### Data Flow

```
monitor.sh (ping loop)
    ↓
logs/YYYY-MM-DD/csv/monitor_YYYYMMDD_HH.csv
    ↓
visualize.py (called by serve.py on request)
    ↓
logs/YYYY-MM-DD/html/monitor_YYYYMMDD_HH_visualization.html
    ↓
serve.py (web server with navigation & auto-refresh)
```

### CSV Schema

```
timestamp, status, response_time, success_count, total_count, failed_count
```

- `timestamp`: ISO format datetime
- `status`: CONNECTED or DISCONNECTED
- `response_time`: Average ping time in ms (null if disconnected)
- `success_count`: Successful pings in sample
- `total_count`: Total pings in sample (equals SAMPLE_SIZE)
- `failed_count`: Failed pings in sample

## Development Commands

### Native (macOS/Linux)

**Setup virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
```

**Run monitor daemon:**
```bash
./monitor.sh [frequency] [sample_size]
# Example: ./monitor.sh 1 60  # Check every 1s, log every 60 samples
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
pkill -f monitor.sh
pkill -f "python.*serve.py"
```

### Docker (Raspberry Pi deployment)

**Build and start container:**
```bash
docker compose build
docker compose up -d
```

**Start services inside container:**
```bash
docker exec network-monitor /bin/bash -c "cd /app && ./monitor.sh 1 60"
docker exec network-monitor /bin/bash -c "cd /app && ./serve.sh logs 80"
```

**Check status:**
```bash
docker ps | grep network-monitor
docker logs network-monitor
docker exec network-monitor pgrep -f monitor.sh
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

### Auto-Refresh Implementation

JavaScript injected into HTML pauses refresh when tab is hidden:
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

### Venv not activating in shell scripts

The wrapper scripts (serve.sh, visualize.sh) automatically create and use venv:
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
    python3-pandas \
    python3-plotly \
    python3-numpy \
    && rm -rf /var/lib/apt/lists/*
```

This approach builds in ~2-3 minutes instead of 20-45 minutes required for pip compilation.

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

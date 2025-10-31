# Network Monitor

A bash script to monitor network connectivity and response times, with Python visualization tools and a live web dashboard.

## Features

- **Daemon mode** - Runs continuously without time limits
- **Hourly log files** - Automatically creates and appends to hourly CSV files
- **Automatic date rollover** - Creates new directories when crossing midnight
- **Auto cleanup** - Keeps only 10 days of logs (configurable)
- **Real-time monitoring** - Logs network connectivity status and ping response times
- **Interactive visualizations** - Gruvbox-themed HTML dashboards with Plotly
- **Live web server** - Auto-refreshing visualizations with navigation
- **Network accessible** - Share dashboards across your local network
- **Configurable** - Adjust frequency and sample size

## Usage

### Running the Monitor Daemon

The monitor runs as a daemon (continuously) without a time limit:

```bash
./monitor.sh [frequency] [sample_size]
```

**Parameters:**

- `frequency` (optional): Check interval in seconds (default: 1)
- `sample_size` (optional): Number of pings to average per log entry (default: 5)

**Examples:**

```bash
# Run with defaults (check every second, 5 samples)
./monitor.sh

# Check every 2 seconds, average 10 samples
./monitor.sh 2 10

# Check every 5 seconds, average 60 samples (1 data point per minute)
./monitor.sh 5 60

# Run in background as daemon
./monitor.sh 1 60 &
```

**How it works:**

- Creates hourly log files: `monitor_YYYYMMDD_HH.csv`
- Automatically appends to existing file if running multiple times in same hour
- Creates new date directories when crossing midnight
- **Automatically removes logs older than 10 days** (checked hourly)
- Runs forever until stopped with Ctrl+C or `kill`

**Log retention:**

The monitor automatically cleans up old logs to save disk space. By default, only the last 10 days of logs are kept. To change this, edit the `LOG_RETENTION_DAYS` variable in `monitor.sh`.

### Visualizing Data

#### Static Visualization (one-time generation)

```bash
./visualize.sh logs/2025-10-30/csv/monitor_20251030_161404.csv
```

This will generate an HTML dashboard and display statistics in the terminal.

#### Live Visualization Server (auto-refresh + navigation)

```bash
./serve.sh [logs_dir] [port]
```

This starts a local web server that:

1. Shows an index page listing all CSV files organized by date
2. Auto-regenerates visualizations fresh when you click on any file
3. Auto-refreshes every 60 seconds when page is in focus
4. Navigation buttons: Back, Previous, Next
5. Opens your browser automatically
6. Accessible from local network

**Examples:**

```bash
./serve.sh                  # Default: logs directory, port 8000
./serve.sh logs 8080        # Custom port
./serve.sh custom_logs 9000 # Custom directory and port
```

**Access URLs:**

- Local: `http://localhost:8000`
- Network: `http://192.168.x.x:8000` (shown in terminal output)

**Features:**

- **Gruvbox theme** - Dark, retro color scheme
- **Dual y-axis chart** - Response time and success rate overlaid
- **Color-coded markers** - Green (100% success), Red (0%), Orange (partial)
- **Navigation** - Back button (left), Prev/Next buttons (right)
- **Auto-refresh** - Reloads every minute when tab is visible
- **Network access** - Share with other devices on your network

## Output Format

### CSV Columns

- `timestamp`: Date and time of the log entry
- `status`: CONNECTED or DISCONNECTED
- `response_time`: Average ping response time in milliseconds
- `success_count`: Number of successful pings in the sample
- `total_count`: Total number of pings in the sample (same as sample_size)

### Directory Structure

```
network-monitor/
├── monitor.sh              # Main monitoring script
├── visualize.sh            # Static visualization wrapper
├── visualize.py            # Python visualization script
├── serve.sh                # Live visualization server wrapper
├── serve.py                # Python web server for live updates
├── requirements.txt        # Python dependencies
├── venv/                   # Python virtual environment
└── logs/
    └── YYYY-MM-DD/         # Daily log directory
        ├── csv/            # CSV data files
        │   └── monitor_YYYYMMDD_HH.csv  # Hourly log files
        └── html/           # Generated visualizations
            └── monitor_YYYYMMDD_HH_visualization.html
```

## Installation

### Prerequisites

- **Bash** (standard on macOS and Linux)
- **Python 3** (3.7 or later)
- **bc** (for calculations - usually pre-installed)
- **ping** (standard networking tool)

### Setup

The virtual environment is automatically created when you first run `serve.sh` or `visualize.sh`.

**Manual setup (if needed):**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
```

**Required Python packages:**

- pandas
- plotly

### Platform Support

✅ **macOS** - Fully tested and supported
✅ **Linux** - Fully compatible (Ubuntu, Debian, CentOS, etc.)

**Key compatibility features:**

- Ping output parsing works on both macOS and Linux
- Automatic venv creation on first run
- Cross-platform Python libraries only

## Managing Processes

### Monitor Daemon

**Find running monitor:**

```bash
pgrep -f monitor.sh
# or
ps aux | grep monitor.sh
```

**Stop monitor:**

```bash
pkill -f monitor.sh
# or
kill <PID>
```

### Visualization Server

**Find running server:**

```bash
lsof -ti:8000  # Replace 8000 with your port
# or
pgrep -f "python.*serve.py"
```

**Stop server:**

```bash
pkill -f "python.*serve.py"
# or
kill <PID>
```

## Network Access

To access the dashboard from other devices on your local network:

1. Start the server (it binds to `0.0.0.0` automatically)
2. Note the "Network access" URL shown in terminal (e.g., `http://192.168.1.100:8080`)
3. Open that URL on any device connected to the same network

**Note:** If connections fail, check macOS Firewall settings:

- System Settings → Network → Firewall → Options
- Add Python to allowed connections

## Tips

- **Daemon mode** - Monitor runs forever, perfect for background monitoring
- **Hourly files** - Multiple runs in same hour append to same file
- **Auto-refresh** - Visualizations update every minute automatically
- **Navigation** - Use Prev/Next buttons to browse chronologically
- **Network sharing** - Access from phones, tablets, other computers
- **Frequency tuning** - Lower values = more frequent checks, more data points
- **Sample averaging** - Higher sample_size = smoother graphs, fewer data points
- **Gruvbox theme** - Easy on the eyes for long monitoring sessions

## Quick Start

```bash
# Terminal 1: Start the monitor daemon
./monitor.sh 1 60 &

# Terminal 2: Start the web server
./serve.sh logs 8080

# Open browser to http://localhost:8080
# Or access from another device using the network URL shown
```

# Network Monitor - Deployment Guide

Complete deployment guide for Raspberry Pi Zero 2 W running Raspbian GNU/Linux 12 (bookworm).

## Quick Start

For those who just want to get it running:

```bash
# 1. Clone and enter directory
git clone https://github.com/stein935/network-monitor.git
cd network-monitor

# 2. Build and start container
docker compose build
docker compose up -d

# 3. Setup systemd services (see Systemd Services section below)
# 4. Access at http://<raspberry-pi-ip>:8080
```

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Fresh Deployment](#fresh-deployment)
- [Systemd Services Setup](#systemd-services-setup)
- [Verification](#verification)
- [Updating](#updating)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

- **Device**: Raspberry Pi Zero 2 W (or similar ARM device)
- **OS**: Raspbian GNU/Linux 12 (bookworm) or compatible
- **RAM**: 512MB minimum
- **Storage**: 2GB free space recommended

### Install Docker

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in, then verify
docker --version
```

### Install Git

```bash
sudo apt install -y git
```

---

## Fresh Deployment

Follow these steps for a brand new deployment.

### Step 1: Clone Repository

```bash
cd ~
git clone https://github.com/stein935/network-monitor.git
cd network-monitor
```

### Step 2: Build Docker Image

```bash
docker compose build
```

**Note**: This may take 10-15 minutes on Raspberry Pi Zero 2 W. The build uses system packages to avoid lengthy ARM compilation.

### Step 3: Start Container

```bash
docker compose up -d
```

### Step 4: Verify Container

```bash
# Check container is running
docker ps | grep network-monitor

# View logs
docker logs network-monitor
```

You should see the container running. Now proceed to systemd services setup.

---

## Systemd Services Setup

These services ensure the monitor and web server start automatically on boot.

### Important Path Note

⚠️ **The service files below assume your project is at `/home/pi/network-monitor`.**

If your username is different (e.g., `kirk`, `user`, etc.) or you cloned to a different location, you **MUST** update the paths in the service files!

### 1. Create Monitor Daemon Service

```bash
sudo nano /etc/systemd/system/network-monitor-daemon.service
```

**Paste this content:**

```ini
[Unit]
Description=Network Monitor Daemon (Docker - SQLite)
After=docker.service network-monitor-container.service
Requires=docker.service network-monitor-container.service

[Service]
Type=simple
Restart=always
RestartSec=10
ExecStart=/usr/bin/docker exec network-monitor python3 /app/monitor.py 1 60
ExecStop=/usr/bin/docker exec network-monitor pkill -f monitor.py

[Install]
WantedBy=multi-user.target
```

**What it does**: Runs `monitor.py` which pings 8.8.8.8 every second, collecting 60 samples before writing to SQLite database.

### 2. Create Web Server Service

```bash
sudo nano /etc/systemd/system/network-monitor-server.service
```

**Paste this content:**

```ini
[Unit]
Description=Network Monitor Web Server (Docker - nginx + Chart.js + WebSocket)
After=docker.service network-monitor-container.service
Requires=docker.service network-monitor-container.service

[Service]
Type=simple
Restart=always
RestartSec=10
ExecStart=/usr/bin/docker exec network-monitor /bin/bash /app/start_services.sh
ExecStop=/usr/bin/docker exec network-monitor /bin/bash -c "nginx -s quit; pkill -f serve.py"

[Install]
WantedBy=multi-user.target
```

**What it does**: Runs nginx reverse proxy (port 80), Python HTTP server (port 8080), and WebSocket server (port 8081).

**Phase 3 nginx benefits**:
- Gzip compression (reduces bandwidth)
- Better static file serving
- Lower memory usage than Python-only
- Easier to add SSL/authentication later
- Better concurrency handling

### 3. Create Container Startup Service

```bash
sudo nano /etc/systemd/system/network-monitor-container.service
```

**Paste this content** (⚠️ UPDATE THE PATH if not using `/home/pi`):

```ini
[Unit]
Description=Network Monitor Docker Container
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/pi/network-monitor
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down

[Install]
WantedBy=multi-user.target
```

⚠️ **IMPORTANT**: Change `/home/pi/network-monitor` to match your actual path!

Examples:
- If username is `kirk`: `/home/kirk/network-monitor`
- If username is `user`: `/home/user/network-monitor`
- Custom location: `/opt/network-monitor` or wherever you cloned it

### 4. Enable and Start All Services

```bash
# Reload systemd to recognize new services
sudo systemctl daemon-reload

# Enable services to start on boot
sudo systemctl enable network-monitor-container.service
sudo systemctl enable network-monitor-daemon.service
sudo systemctl enable network-monitor-server.service

# Start container service first
sudo systemctl start network-monitor-container.service

# Wait for container to be ready
sleep 5

# Start monitor and server
sudo systemctl start network-monitor-daemon.service
sudo systemctl start network-monitor-server.service
```

### 5. Verify Services Are Running

```bash
# Check all services
systemctl status network-monitor-container.service
systemctl status network-monitor-daemon.service
systemctl status network-monitor-server.service

# All should show "active (running)"
```

---

## Verification

### Check Database Has Data

```bash
docker exec network-monitor python3 -c "
from db import NetworkMonitorDB
db = NetworkMonitorDB('logs/network_monitor.db')
hours = db.get_available_hours()
print(f'Available hours: {len(hours)}')
for date, hour, count in hours[:5]:
    print(f'  {date} {hour}:00 - {count} entries')
"
```

**Expected output** (after a few minutes of running):
```
Available hours: 1
  2025-11-03 23:00 - 45 entries
```

### Access Web Dashboard

1. **Find your Pi's IP address:**
   ```bash
   hostname -I | awk '{print $1}'
   ```

2. **Open in browser:**
   ```
   http://<raspberry-pi-ip>:8080
   ```

3. **You should see:**
   - Index page listing available hours
   - Click any hour to see Chart.js visualization
   - Current hour shows "🔴 LIVE" indicator
   - WebSocket status (should show "WebSocket: Connected" in green)

### Check Logs

```bash
# Monitor daemon logs
sudo journalctl -u network-monitor-daemon.service -f

# Web server logs
sudo journalctl -u network-monitor-server.service -f

# Container logs
docker logs network-monitor -f
```

---

## Updating

When new updates are pushed to the repository:

```bash
cd ~/network-monitor

# Pull latest code
git pull origin main

# Stop services
sudo systemctl stop network-monitor-server.service
sudo systemctl stop network-monitor-daemon.service

# Rebuild container with new code
docker compose down
docker compose build --no-cache
docker compose up -d

# Wait for container to be ready
sleep 5

# Restart services
sudo systemctl start network-monitor-daemon.service
sudo systemctl start network-monitor-server.service

# Verify everything is running
systemctl status network-monitor-daemon.service
systemctl status network-monitor-server.service
```

**Hard refresh your browser** (Ctrl+Shift+R or Cmd+Shift+R) to clear cached files.

---

## Troubleshooting

### No Data Showing on Website

**Symptoms**: Index page is blank or shows "No monitoring data found"

**Solution**:
```bash
# 1. Check if monitor.py is running
docker exec network-monitor pgrep -fa monitor.py

# 2. If not running, check the service
sudo systemctl status network-monitor-daemon.service

# 3. Check for errors in logs
sudo journalctl -u network-monitor-daemon.service -n 50

# 4. Restart the daemon
sudo systemctl restart network-monitor-daemon.service

# 5. Wait 2 minutes, then check database again
docker exec network-monitor python3 -c "from db import NetworkMonitorDB; db = NetworkMonitorDB('logs/network_monitor.db'); print(f'Entries: {len(db.get_available_hours())}')"
```

### WebSocket Shows "Disconnected (Polling)"

**Symptoms**: WebSocket status shows red "Disconnected" message

**Causes**:
1. Port 8081 not exposed
2. Old cached HTML in browser
3. Server using old code

**Solutions**:
```bash
# 1. Verify both ports are in docker-compose.yml
cat docker-compose.yml | grep -A 2 "ports:"
# Should show:
#   - "8080:8080"  # HTTP
#   - "8081:8081"  # WebSocket

# 2. Check WebSocket server is running
sudo journalctl -u network-monitor-server.service | grep "WebSocket server started"

# 3. Rebuild with no cache
docker compose down
docker compose build --no-cache
docker compose up -d
sudo systemctl restart network-monitor-server.service

# 4. Hard refresh browser (Ctrl+Shift+R)
```

### Services Fail to Start

**Symptoms**: `systemctl status` shows "failed" or "inactive"

**Solution**:
```bash
# Check detailed error logs
sudo journalctl -u network-monitor-daemon.service -n 50
sudo journalctl -u network-monitor-server.service -n 50

# Common issues:
# 1. Container not running - start it:
sudo systemctl start network-monitor-container.service

# 2. Wrong path in service file - verify:
cat /etc/systemd/system/network-monitor-container.service | grep WorkingDirectory

# 3. Python errors - check container logs:
docker logs network-monitor
```

### Port 8080 Already in Use (Pi-hole Conflict)

**Symptoms**: Container won't start, error about port 8080 in use

**Note**: If running Pi-hole or another service on port 80, the current configuration uses 8080 inside the container to avoid conflicts.

**Verify configuration**:
```bash
# Check docker-compose.yml
cat docker-compose.yml | grep "8080"
# Should show: "8080:8080"

# Check Dockerfile
docker exec network-monitor grep EXPOSE /app/Dockerfile
# Should show: EXPOSE 8080 8081
```

### Monitor Using Old Code After Update

**Symptoms**: Changes not appearing after `git pull`

**Solution**:
```bash
# Force rebuild with no cache
docker compose down
docker compose build --no-cache
docker compose up -d

# Verify new code is in container
docker exec network-monitor grep -A 2 "const wsUrl" /app/serve.py
# Should show: const wsUrl = `ws://${location.hostname}:8081`;

# Restart services
sudo systemctl restart network-monitor-daemon.service
sudo systemctl restart network-monitor-server.service
```

### Check Diagnostic Script

Run the diagnostic script to check overall status:

```bash
cd ~/network-monitor
bash check_status.sh
```

---

## Architecture Overview

**What's Running:**

1. **Docker Container** (`network-monitor`)
   - Debian bookworm base with Python 3.11
   - System packages: pandas, plotly, websockets, nginx
   - Ports: 80 (nginx), 8080 (HTTP), 8081 (WebSocket)

2. **nginx Reverse Proxy** (Phase 3)
   - Listens on port 80
   - Proxies requests to Python server (8080) and WebSocket (8081)
   - Gzip compression enabled
   - Static file caching
   - WebSocket upgrade support

3. **Monitor Daemon** (`monitor.py`)
   - Pings 8.8.8.8 every second
   - Collects 60 samples (1 minute of data)
   - Writes to SQLite: `logs/network_monitor.db`
   - Auto-cleanup: removes data older than 10 days

4. **Web Server** (`serve.py`)
   - HTTP server on port 8080 (internal)
   - WebSocket server on port 8081 (internal)
   - All hours: Chart.js visualizations (Phase 2)
   - Current hour: WebSocket updates (30s batches)
   - Past hours: Static Chart.js (no updates)
   - Gruvbox dark theme

**Data Flow:**
```
Browser → nginx:80 → serve.py:8080 → SQLite DB
                  ↓
                WebSocket:8081 (30s updates)
                  ↑
           monitor.py (writes to SQLite)
```

**Performance Optimizations:**
- **Phase 1 - SQLite**: 70% reduction in disk I/O vs CSV files
- **Phase 2 - Chart.js**: 93% smaller page loads (200KB vs 3MB Plotly)
- **Phase 2 - WebSocket**: 95% CPU reduction vs HTTP polling
- **Phase 3 - nginx**: Gzip compression, better concurrency, lower memory

---

## Configuration Options

### Monitor Frequency

Edit `/etc/systemd/system/network-monitor-daemon.service`:

```ini
# Default: ping every 1s, collect 60 samples (1 minute per data point)
ExecStart=/usr/bin/docker exec network-monitor python3 /app/monitor.py 1 60

# Conservative: ping every 5s, collect 60 samples (5 minutes per data point)
ExecStart=/usr/bin/docker exec network-monitor python3 /app/monitor.py 5 60
```

Then reload: `sudo systemctl daemon-reload && sudo systemctl restart network-monitor-daemon.service`

### Log Retention

Default is 10 days. To change, edit `monitor.py` or `db.py` and rebuild.

### Resource Limits

Configured in `docker-compose.yml`:
```yaml
deploy:
  resources:
    limits:
      memory: 256M
      cpus: '0.5'
```

Adjust if needed for your device.

---

## Next Steps

1. ✅ Access dashboard at `http://<raspberry-pi-ip>:8080`
2. ✅ Verify WebSocket connection (green "Connected" indicator)
3. ✅ Watch real-time updates every 30 seconds
4. ✅ Check logs are auto-cleaning after 10 days

For advanced optimizations (nginx, nightly pre-generation), see [OPTIMIZATION.md](OPTIMIZATION.md).

For code documentation, see [CLAUDE.md](CLAUDE.md).

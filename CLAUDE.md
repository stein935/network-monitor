# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

Network Monitor: Python daemon monitoring network connectivity + internet speed, with SQLite storage and real-time web visualization.

**Key Stack:**

- SQLite (WAL mode) + indexed queries
- Chart.js visualization (93% smaller than Plotly)
- WebSocket (30s batches) + HTTP polling fallback
- nginx reverse proxy (gzip, caching)
- Docker deployment (Raspberry Pi Zero 2 W optimized)
- Dual monitoring: Network latency (ping 8.8.8.8) + bandwidth (speedtest-cli every 15 min)

**Performance:** 30-35% resource reduction via WAL mode, nginx caching, disabled animations, request debouncing, ETag support, reduced logging.

## Architecture

### Core Components

1. **monitor.py** - Daemon with dual monitoring:

   - Pings 8.8.8.8 every `FREQUENCY` (default: 1s), logs every `SAMPLE_SIZE` samples (default: 60)
   - Speed test thread: speedtest-cli every 15 min (background)
   - Writes to SQLite: `logs/network_monitor.db`
   - Handles macOS/Linux ping formats (regex for both)
   - WAL mode immediate commits, reduced logging (every 10th sample)

2. **serve.py** - Dual server (HTTP:8090 + WebSocket:8081):

   - Single-page dashboard: network chart (1hr window) + speed test chart (12hr window) + Docker resource monitoring
   - Time-based navigation (offset from current, not file-based)
   - Live view: WebSocket updates, fallback to HTTP polling
   - Historical view: Static Chart.js, no updates
   - HTML caching (30s), ETag support for static files
   - API: `/api/network-logs/earliest`, `/api/speed-tests/{latest,earliest,recent}`, `/api/stats`, `/api/docker-stats`, `/csv/?start_time=...&end_time=...`

3. **db.py** - SQLite handler:

   - Tables: `network_logs` (timestamp, status, response_time, success/total/failed counts), `speed_tests` (timestamp, download/upload mbps, ping, server info)
   - Both indexed on timestamp
   - WAL mode, synchronous=NORMAL, 32MB cache
   - Auto-cleanup (30 days retention), VACUUM removed (WAL auto-checkpoints)

4. **nginx.conf** - Reverse proxy:

   - External :8080 → serve.py:8090 (HTTP), :8081 (WebSocket via /ws)
   - Gzip compression, proxy cache (30s for /api, /csv)
   - Reduced workers (128 conn), access logs disabled

5. **start_services.sh** - Starts nginx + serve.py servers

### Data Flow

```
Browser → nginx:8080 → serve.py:8090 (HTTP) + :8081 (WebSocket /ws) → SQLite ← monitor.py
```

Live: WebSocket 30s batches, fallback HTTP polling (60s network, 5min speed)
Historical: Time-range SQL queries

### Port Architecture

- External: 8080 (nginx HTTP), 8081 (WebSocket)
- Internal: 8080 (nginx), 8090 (serve.py HTTP), 8081 (serve.py WebSocket)

## Development Commands

### Docker

```bash
# Build/start
docker compose build && docker compose up -d

# Start services
docker exec -d network-monitor python3 /app/monitor.py 1 60
docker exec -d network-monitor /bin/bash /app/start_services.sh

# Status
docker ps | grep network-monitor
docker stats network-monitor --no-stream
docker exec network-monitor pgrep -f monitor.py

# Stop
docker exec network-monitor pkill -f monitor.py
docker exec network-monitor nginx -s quit
docker exec network-monitor pkill -f serve.py

# Update
git pull origin main
docker compose down && docker compose build --no-cache && docker compose up -d

# Access: http://<pi-ip>:8080
```

### Systemd (Raspberry Pi)

```bash
# Status
systemctl status 'network-monitor-*'

# Restart
sudo systemctl restart network-monitor-{container,daemon,server}.service

# Logs
sudo journalctl -u network-monitor-daemon.service -f
```

## Configuration

- `FREQUENCY`: Seconds between pings (default: 1)
- `SAMPLE_SIZE`: Pings before logging (default: 60)
- `LOG_RETENTION_DAYS`: Days to keep logs (default: 30)
- Speed tests: Hardcoded 15 min interval in monitor.py
- Ports: Edit docker-compose.yml (external:internal mapping)

## Documentation Maintenance - CRITICAL

### Pre-Push Checklist

Before ANY `git push`, you MUST:

1. **Update README.md** - Overview, installation, examples, dependencies
2. **Update DEPLOYMENT.md** - Deployment process, systemd, Docker, Pi considerations
3. **Update CLAUDE.md** - New conventions, commands, structure, API endpoints
4. **Inline docs** - Function docstrings, updated comments
5. **Verify** - State: "✓ Documentation updated and verified. Ready to push."

### Git Workflow - CRITICAL RULES

**NEVER Auto-Push:**

- **NEVER `git push` without explicit permission**
- After committing, STOP and ask: "Ready to push. Should I proceed?"
- Wait for explicit "yes" or "push now"

**Freely use:** `git status`, `git diff`, `git log`, `git add`, `git commit`, `git checkout`, `git branch`, `git fetch`

**ALWAYS ASK before:** `git push`, `git push --force`, `git merge` to main/master/develop, destructive operations

**When complete:**

1. Run pre-push checklist
2. Commit with conventional format: `type(scope): description`
3. Show summary
4. Ask to push
5. Wait for response

**Commit standards:**

- Types: feat, fix, docs, style, refactor, test, chore
- First line <72 chars
- NO Claude attribution or co-author tags

## Important Implementation Details

### Speed Tests

- Separate daemon thread in monitor.py
- Runs `speedtest-cli --json` every 15 min
- Inserts into `speed_tests` table
- Dashboard polls every 5 min (live) or static (historical)

### Cross-Platform Support

- Ping regex handles both macOS ("round-trip") and Linux ("rtt") output formats
- Docker requires `privileged: true` + NET_RAW/NET_ADMIN for ping

### Dashboard Navigation

- Time-based (not file-based): offset from current time
- Network: 1hr window, ±1hr navigation
- Speed tests: 12hr window, ±12hr navigation
- Live view (offset=0): WebSocket updates, "🔴 LIVE" indicator, "Go Live" button when historical
- Historical (offset<0): Static data, no updates

### WebSocket

- JavaScript connects via `ws://${location.host}/ws`
- nginx proxies /ws to serve.py:8081 with upgrade headers
- Fallback to HTTP polling on error

### Chart.js

- Animations disabled (`animation: false`) for Pi Zero performance
- Updates use `chart.update('none')` to skip transitions
- Network chart: Response time (blue line) + Success rate (green area, turns orange <100%)
- Speed chart: Download (blue area) + Upload (purple line)

### Docker Resource Monitoring

- Real-time container stats via `/api/docker-stats`
- Runs `docker stats --no-stream --format "{{json .}}"`
- Fallback: Reads `/proc/meminfo` when docker stats shows `0B / 0B` (ARM platforms like Pi Zero 2 W)
- Memory calculation: `MemTotal - MemAvailable` from /proc for actual container usage
- 4-quadrant layout: CPU (progress bar), Memory (progress bar), Network I/O (RX/TX), Disk I/O (read/write)
- Color thresholds: blue (<70%), yellow (70-85%), red (>85%)
- Updates every 30 seconds
- Requires Docker socket mount (`/var/run/docker.sock`) and Docker CLI in container

### Footer

- Version from `VERSION` file (semantic versioning)
- DB size from `/api/stats`
- Uptime client-side (page load)

## Dependencies

System packages (Docker): python3, iputils-ping, curl, procps, nginx, python3-websockets, speedtest-cli, docker.io

## File Structure

```
network-monitor/
├── monitor.py, serve.py, db.py      # Core Python
├── nginx.conf, start_services.sh    # Infrastructure
├── Dockerfile, docker-compose.yml   # Docker
├── VERSION                          # Semantic version
├── static/{dashboard.css, dashboard.js}
├── README.md, DEPLOYMENT.md, CHANGELOG.md, CLAUDE.md
└── logs/network_monitor.db          # SQLite (network_logs + speed_tests)
```

## Troubleshooting Quick Ref

- **Port conflicts:** `lsof -ti:8080` then kill processes
- **Speed tests not running:** Check `docker exec network-monitor pgrep -f monitor.py`, view logs with `docker logs network-monitor | grep -i speed`
- **Memory constraints:** Reduce frequency, increase sample size: `./monitor.sh 5 60`
- **Docker build:** Use system packages not pip (faster on Pi Zero 2 W)

# Phase 3 Deployment Guide - nginx Reverse Proxy

This guide walks through deploying Phase 3 (nginx reverse proxy) to your Raspberry Pi Zero 2 W.

## Prerequisites

- Phases 1 and 2 already deployed and working
- SSH access to your Raspberry Pi
- Systemd services configured and running

## Step 1: Backup Current Configuration

Before deploying, backup your current working setup:

```bash
# SSH into your Raspberry Pi
ssh pi@<raspberry-pi-ip>

# Navigate to project directory
cd ~/network-monitor

# Check current status
systemctl status 'network-monitor-*'
docker ps | grep network-monitor

# Backup current database (optional but recommended)
docker exec network-monitor cp /app/logs/network_monitor.db /app/logs/network_monitor.db.backup

# Note current commit
git log -1 --oneline
```

## Step 2: Pull Latest Code

Pull the Phase 3 changes from the repository:

```bash
cd ~/network-monitor

# Stash any local changes (if any)
git stash

# Pull latest code
git pull origin main

# Verify new files exist
ls -l nginx.conf start_services.sh generate_static.sh

# Check that obsolete files are gone
ls monitor.sh serve.sh visualize.sh  # Should show "No such file or directory"
```

**Expected output:**
```
remote: Enumerating objects: X, done.
remote: Counting objects: 100% (X/X), done.
...
From https://github.com/stein935/network-monitor
   xxxxxxx..693ea2a  main       -> origin/main
Updating xxxxxxx..693ea2a
Fast-forward
 CLAUDE.md          | XXX ++++------
 nginx.conf         | XXX +++++++++++
 start_services.sh  | XXX +++++++++++
 ...
```

## Step 3: Stop Current Services

Stop the running services cleanly:

```bash
# Stop services in reverse order
sudo systemctl stop network-monitor-server.service
sudo systemctl stop network-monitor-daemon.service

# Verify they're stopped
systemctl status network-monitor-daemon.service
systemctl status network-monitor-server.service

# Both should show "inactive (dead)"
```

## Step 4: Rebuild Docker Container

Rebuild the container with nginx and new configuration:

```bash
cd ~/network-monitor

# Stop and remove old container
docker compose down

# Rebuild with no cache (ensures fresh build)
docker compose build --no-cache

# This will take 10-15 minutes on Pi Zero 2 W
# You'll see:
# - Installing nginx
# - Copying nginx.conf
# - Installing system packages
# - Creating directories
```

**Expected output:**
```
[+] Building XXXs (X/X) FINISHED
 => [internal] load build definition from Dockerfile
 => => transferring dockerfile: XXXXb
 => [internal] load .dockerenv
 => [1/6] FROM debian:bookworm-slim
 => [2/6] RUN apt-get update && apt-get install -y nginx ...
 => [3/6] WORKDIR /app
 => [4/6] COPY . .
 => [5/6] COPY nginx.conf /etc/nginx/nginx.conf
 => [6/6] RUN mkdir -p logs static /var/log/nginx ...
 => exporting to image
Successfully built xxxxxxxxxx
```

## Step 5: Start Container

Start the rebuilt container:

```bash
# Start container
docker compose up -d

# Wait for container to be ready
sleep 5

# Verify container is running
docker ps | grep network-monitor

# Check container logs
docker logs network-monitor
```

**Expected output:**
```
[+] Running 1/1
 ✔ Container network-monitor  Started
```

## Step 6: Verify New Files in Container

Check that the new files are present in the container:

```bash
# Check nginx config
docker exec network-monitor cat /etc/nginx/nginx.conf | head -20

# Check start_services.sh
docker exec network-monitor cat /app/start_services.sh

# Verify scripts are executable
docker exec network-monitor ls -l /app/start_services.sh /app/generate_static.sh
```

**Expected output:**
```
-rwxr-xr-x 1 root root XXX Nov  3 XX:XX /app/start_services.sh
-rwxr-xr-x 1 root root XXX Nov  3 XX:XX /app/generate_static.sh
```

## Step 7: Update Systemd Service (if needed)

The systemd service should already be configured to use `start_services.sh`. Verify:

```bash
# Check current service configuration
cat /etc/systemd/system/network-monitor-server.service | grep ExecStart
```

**Expected output:**
```
ExecStart=/usr/bin/docker exec network-monitor /bin/bash /app/start_services.sh
```

**If it shows the old command** (e.g., `serve.sh` or `serve.py`), update it:

```bash
sudo nano /etc/systemd/system/network-monitor-server.service
```

Change the `ExecStart` line to:
```ini
ExecStart=/usr/bin/docker exec network-monitor /bin/bash /app/start_services.sh
```

Change the `ExecStop` line to:
```ini
ExecStop=/usr/bin/docker exec network-monitor /bin/bash -c "nginx -s quit; pkill -f serve.py"
```

Save and exit (Ctrl+O, Enter, Ctrl+X), then reload:
```bash
sudo systemctl daemon-reload
```

## Step 8: Start Services

Start the services in order:

```bash
# Start monitor daemon
sudo systemctl start network-monitor-daemon.service

# Wait 2 seconds
sleep 2

# Start web server (nginx + Python servers)
sudo systemctl start network-monitor-server.service

# Wait 5 seconds for services to initialize
sleep 5
```

## Step 9: Verify Services Are Running

Check that all services started successfully:

```bash
# Check systemd services
systemctl status network-monitor-daemon.service
systemctl status network-monitor-server.service

# Both should show "active (running)"

# Check processes inside container
docker exec network-monitor ps aux | grep -E "nginx|serve.py|monitor.py"
```

**Expected output:**
```
root         XXX  ... nginx: master process nginx
www-data     XXX  ... nginx: worker process
root         XXX  ... python3 /app/serve.py logs 8080
root         XXX  ... python3 /app/monitor.py 1 60
```

## Step 10: Check Service Logs

Verify nginx and WebSocket are starting correctly:

```bash
# Check server service logs
sudo journalctl -u network-monitor-server.service -n 50

# Look for these lines:
# [*] Starting Network Monitor services...
# [*] Starting nginx...
# nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
# nginx: configuration file /etc/nginx/nginx.conf test is successful
# [*] Starting Python server (HTTP: 8080, WebSocket: 8081)...
# [*] All services started
# [*] nginx: port 80
# [*] Python HTTP: port 8080
# [*] Python WebSocket: port 8081

# Check for WebSocket startup
sudo journalctl -u network-monitor-server.service | grep WebSocket
```

**Expected output:**
```
Nov 03 XX:XX:XX ... [*] Starting Python server (HTTP: 8080, WebSocket: 8081)...
Nov 03 XX:XX:XX ... [*] WebSocket server started on port 8081
```

## Step 11: Test nginx

Test that nginx is serving traffic:

```bash
# Test nginx from inside container
docker exec network-monitor curl -I http://localhost:80

# Should return HTTP 200 OK with nginx headers
```

**Expected output:**
```
HTTP/1.1 200 OK
Server: nginx/1.XX.X
Content-Type: text/html; charset=utf-8
...
```

## Step 12: Test from Browser

From your computer, test the web interface:

1. **Find your Pi's IP address:**
   ```bash
   hostname -I | awk '{print $1}'
   ```

2. **Open browser to:**
   ```
   http://<raspberry-pi-ip>:8080
   ```

3. **Check for:**
   - Index page loads
   - Hours are listed with entry counts
   - Click on current hour
   - Chart.js visualization loads
   - WebSocket status shows **"Connected"** in green (not "Disconnected")
   - Live indicator shows "🔴 LIVE"

4. **Open browser console (F12) and check:**
   - No errors in console
   - Look for: `WebSocket connection established` or similar
   - WebSocket URL should be: `ws://<raspberry-pi-ip>:8081`

## Step 13: Verify WebSocket Updates

Test that WebSocket is pushing updates:

1. Keep the current hour visualization open
2. Watch the chart - it should update every 30 seconds
3. In browser console, you should see WebSocket messages every 30s
4. If WebSocket is working, you'll see new data points appear without page refresh

**To monitor WebSocket in console:**
```javascript
// In browser console, check WebSocket readyState
// 0 = CONNECTING, 1 = OPEN, 2 = CLOSING, 3 = CLOSED
```

## Step 14: Test nginx Gzip Compression

Verify gzip compression is working:

```bash
# Test from outside container
curl -H "Accept-Encoding: gzip" -I http://<raspberry-pi-ip>:8080

# Look for header:
# Content-Encoding: gzip
```

**Or use browser DevTools:**
1. Open browser to `http://<raspberry-pi-ip>:8080`
2. Open DevTools (F12) → Network tab
3. Reload page
4. Click on the main request
5. Check Response Headers for: `Content-Encoding: gzip`
6. Compare Size vs Transferred - should show compression (e.g., "500 KB / 150 KB")

## Step 15: Performance Verification

Compare performance metrics before and after Phase 3:

### CPU Usage:
```bash
# Monitor CPU usage
docker stats network-monitor --no-stream

# Should see lower CPU% compared to Phase 2
```

### Memory Usage:
```bash
# Check memory
docker stats network-monitor --no-stream | grep network-monitor

# Should be under 256MB limit
```

### Check Database:
```bash
# Verify data is still being written
docker exec network-monitor python3 -c "
from db import NetworkMonitorDB
db = NetworkMonitorDB('logs/network_monitor.db')
hours = db.get_available_hours()
print(f'Available hours: {len(hours)}')
if hours:
    latest = hours[0]
    print(f'Latest: {latest[0]} {latest[1]}:00 - {latest[2]} entries')
"
```

**Expected output:**
```
Available hours: X
Latest: 2025-11-03 23:00 - XXX entries
```

## Step 16: Test Historical Hours

Test that past hours still work:

1. Go to index page
2. Click on a past hour (not current hour)
3. Should see Chart.js visualization
4. WebSocket status should show "Disconnected (Polling)" - this is normal for past hours
5. No auto-refresh for past hours (data is historical)

## Step 17: Monitor for Errors

Watch logs for a few minutes to catch any errors:

```bash
# Watch all logs in real-time
sudo journalctl -u network-monitor-daemon.service -u network-monitor-server.service -f

# Press Ctrl+C to stop after a few minutes
```

Look for:
- ✅ Monitor writing to database every minute
- ✅ WebSocket broadcasting updates every 30s
- ✅ No nginx errors
- ❌ Any Python exceptions
- ❌ Any "connection refused" errors

## Troubleshooting

### WebSocket Shows "Disconnected"

```bash
# Check if port 8081 is exposed
cat ~/network-monitor/docker-compose.yml | grep -A 2 "ports:"

# Should show both ports:
#   - "8080:80"

# Check WebSocket is running
sudo journalctl -u network-monitor-server.service | grep 8081

# Check from browser console for actual error
# F12 → Console → Look for WebSocket error messages
```

**Fix:** If WebSocket server isn't starting, check serve.py logs:
```bash
docker logs network-monitor | grep -i websocket
```

### nginx Not Starting

```bash
# Test nginx config
docker exec network-monitor nginx -t

# Check nginx error log
docker exec network-monitor cat /var/log/nginx/error.log

# Check nginx is running
docker exec network-monitor pgrep nginx
```

**Fix:** If config is invalid:
```bash
# Check nginx.conf syntax
docker exec network-monitor cat /etc/nginx/nginx.conf
```

### Port 8080 Returns 502 Bad Gateway

This means nginx is running but can't reach Python server:

```bash
# Check Python server is running on 8080
docker exec network-monitor netstat -tlnp | grep 8080

# Check serve.py logs
sudo journalctl -u network-monitor-server.service | grep serve.py
```

**Fix:** Restart server service:
```bash
sudo systemctl restart network-monitor-server.service
```

### No Data After Update

```bash
# Check monitor is running
docker exec network-monitor pgrep -f monitor.py

# If not running, check service
sudo systemctl status network-monitor-daemon.service

# Restart if needed
sudo systemctl restart network-monitor-daemon.service
```

## Rollback (If Needed)

If Phase 3 has issues, you can rollback:

```bash
# Stop services
sudo systemctl stop network-monitor-server.service
sudo systemctl stop network-monitor-daemon.service

# Revert to previous commit
cd ~/network-monitor
git log --oneline -10  # Find previous commit
git reset --hard <previous-commit-hash>

# Rebuild
docker compose down
docker compose build --no-cache
docker compose up -d

# Restart services
sudo systemctl start network-monitor-daemon.service
sudo systemctl start network-monitor-server.service
```

## Success Criteria

Phase 3 is successfully deployed if:

- ✅ nginx is running and serving on port 80 (inside container)
- ✅ Port 8080 is accessible from browser
- ✅ WebSocket shows "Connected" on current hour
- ✅ Data updates every 30 seconds without page refresh
- ✅ Past hours show static visualizations
- ✅ Gzip compression is active (check DevTools)
- ✅ CPU usage is stable and low
- ✅ No errors in systemd logs
- ✅ Database continues to grow

## Performance Expectations

After Phase 3, you should see:

| Metric | Phase 2 | Phase 3 | Improvement |
|--------|---------|---------|-------------|
| Page size (current hour) | ~200 KB | ~60 KB | 70% smaller (gzip) |
| Page size (past hour) | ~200 KB | ~60 KB | 70% smaller (gzip) |
| Bandwidth usage | Medium | Low | 70% reduction |
| Memory usage | ~60 MB | ~50 MB | 16% reduction |
| CPU usage | ~5% | ~3% | 40% reduction |

## Next Steps

Once Phase 3 is verified:

1. Monitor for 24 hours to ensure stability
2. Check that auto-cleanup works (removes old data after 10 days)
3. Consider setting up automatic database backups
4. Optional: Implement nightly pre-generation (future enhancement)

## Support

If you encounter issues:

1. Check [DEPLOYMENT.md](DEPLOYMENT.md) troubleshooting section
2. Review systemd logs: `sudo journalctl -u network-monitor-server.service -n 100`
3. Check container logs: `docker logs network-monitor --tail 100`
4. Verify all processes: `docker exec network-monitor ps aux`

---

**Phase 3 Deployment Complete!** 🎉

All three optimization phases are now deployed:
- Phase 1: SQLite storage ✅
- Phase 2: Chart.js + WebSocket ✅
- Phase 3: nginx reverse proxy ✅

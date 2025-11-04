# Phase 3 Deployment Checklist

Quick reference checklist for deploying Phase 3. See [PHASE3_DEPLOYMENT.md](PHASE3_DEPLOYMENT.md) for detailed instructions.

## Pre-Deployment

- [ ] SSH into Raspberry Pi
- [ ] Navigate to `~/network-monitor`
- [ ] Check current services are running: `systemctl status 'network-monitor-*'`
- [ ] Backup database (optional): `docker exec network-monitor cp /app/logs/network_monitor.db /app/logs/network_monitor.db.backup`
- [ ] Note current commit: `git log -1 --oneline`

## Deployment

- [ ] Pull latest code: `git pull origin main`
- [ ] Verify new files exist: `ls -l nginx.conf start_services.sh`
- [ ] Stop services: `sudo systemctl stop network-monitor-server.service network-monitor-daemon.service`
- [ ] Rebuild container: `docker compose down && docker compose build --no-cache`
  - ⏱️ Wait 10-15 minutes for build
- [ ] Start container: `docker compose up -d`
- [ ] Wait 5 seconds: `sleep 5`
- [ ] Verify container running: `docker ps | grep network-monitor`

## Service Configuration

- [ ] Check server service config: `cat /etc/systemd/system/network-monitor-server.service | grep ExecStart`
- [ ] Should see: `ExecStart=/usr/bin/docker exec network-monitor /bin/bash /app/start_services.sh`
- [ ] If not, update service file and run: `sudo systemctl daemon-reload`

## Start Services

- [ ] Start monitor: `sudo systemctl start network-monitor-daemon.service`
- [ ] Wait 2 seconds
- [ ] Start server: `sudo systemctl start network-monitor-server.service`
- [ ] Wait 5 seconds

## Verification - Services

- [ ] Check daemon status: `systemctl status network-monitor-daemon.service` → Should be "active (running)"
- [ ] Check server status: `systemctl status network-monitor-server.service` → Should be "active (running)"
- [ ] Check processes: `docker exec network-monitor ps aux | grep -E "nginx|serve.py|monitor.py"`
  - [ ] nginx master process
  - [ ] nginx worker process
  - [ ] python3 serve.py
  - [ ] python3 monitor.py

## Verification - Logs

- [ ] Check server startup: `sudo journalctl -u network-monitor-server.service -n 50`
  - [ ] `[*] Starting nginx...`
  - [ ] `nginx: configuration file /etc/nginx/nginx.conf test is successful`
  - [ ] `[*] Starting Python server (HTTP: 8080, WebSocket: 8081)...`
  - [ ] `[*] All services started`
- [ ] Check WebSocket: `sudo journalctl -u network-monitor-server.service | grep WebSocket`
  - [ ] Should see "WebSocket server started on port 8081"

## Verification - nginx

- [ ] Test nginx: `docker exec network-monitor curl -I http://localhost:80`
  - [ ] Should return "HTTP/1.1 200 OK"
  - [ ] Should see "Server: nginx"

## Verification - Web Browser

- [ ] Get Pi IP: `hostname -I | awk '{print $1}'`
- [ ] Open browser to: `http://<pi-ip>:8080`
- [ ] Index page loads with hours listed
- [ ] Click on current hour
- [ ] Chart.js visualization loads
- [ ] WebSocket status shows **"Connected"** in green ✅
- [ ] Live indicator shows "🔴 LIVE"
- [ ] Open browser console (F12)
  - [ ] No errors in console
  - [ ] WebSocket URL: `ws://<pi-ip>:8081`

## Verification - WebSocket Updates

- [ ] Keep current hour page open
- [ ] Wait 30 seconds
- [ ] New data point appears without page refresh
- [ ] Chart updates automatically

## Verification - Gzip Compression

- [ ] Browser DevTools → Network tab
- [ ] Reload page
- [ ] Click main request
- [ ] Check Response Headers: `Content-Encoding: gzip` ✅
- [ ] Compare Size vs Transferred (should show ~70% reduction)

## Verification - Performance

- [ ] Check CPU/memory: `docker stats network-monitor --no-stream`
  - [ ] CPU% should be low (~3-5%)
  - [ ] Memory should be under 256MB
- [ ] Check database: `docker exec network-monitor python3 -c "from db import NetworkMonitorDB; db = NetworkMonitorDB('logs/network_monitor.db'); print(f'Hours: {len(db.get_available_hours())}')"`
  - [ ] Should show hours of data

## Verification - Past Hours

- [ ] Go to index page
- [ ] Click on a past hour (not current)
- [ ] Chart.js visualization loads
- [ ] WebSocket shows "Disconnected (Polling)" - this is normal ✅
- [ ] No auto-refresh (data is static)

## Monitor for Issues

- [ ] Watch logs: `sudo journalctl -u network-monitor-daemon.service -u network-monitor-server.service -f`
- [ ] Monitor for 5 minutes
  - [ ] Monitor writes to database every minute
  - [ ] WebSocket broadcasts every 30s
  - [ ] No errors in logs
- [ ] Press Ctrl+C to stop monitoring

## Success Criteria

All items below should be ✅:

- [ ] nginx serving on port 80 (inside container)
- [ ] Port 8080 accessible from browser
- [ ] WebSocket shows "Connected" on current hour
- [ ] Data updates every 30 seconds
- [ ] Past hours show static visualizations
- [ ] Gzip compression active
- [ ] CPU usage stable and low
- [ ] No errors in logs
- [ ] Database continues to grow

## Common Issues

### WebSocket shows "Disconnected"
```bash
# Check WebSocket is running
sudo journalctl -u network-monitor-server.service | grep 8081
docker logs network-monitor | grep -i websocket

# Restart service
sudo systemctl restart network-monitor-server.service
```

### nginx not starting
```bash
# Test config
docker exec network-monitor nginx -t

# Check error log
docker exec network-monitor cat /var/log/nginx/error.log
```

### Port 8080 returns 502
```bash
# Check Python server
docker exec network-monitor netstat -tlnp | grep 8080

# Restart service
sudo systemctl restart network-monitor-server.service
```

### No data
```bash
# Check monitor
docker exec network-monitor pgrep -f monitor.py

# Restart monitor
sudo systemctl restart network-monitor-daemon.service
```

## Rollback (If Needed)

```bash
# Stop services
sudo systemctl stop network-monitor-server.service network-monitor-daemon.service

# Find previous commit
cd ~/network-monitor
git log --oneline -10

# Revert
git reset --hard <previous-commit>

# Rebuild
docker compose down
docker compose build --no-cache
docker compose up -d

# Restart
sudo systemctl start network-monitor-daemon.service
sudo systemctl start network-monitor-server.service
```

---

## 🎉 Phase 3 Complete!

Expected improvements:
- 70% smaller page loads (gzip compression)
- 70% bandwidth reduction
- 16% memory reduction
- 40% CPU reduction
- Better concurrency handling

Monitor for 24 hours to ensure stability.

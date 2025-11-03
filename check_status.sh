#!/bin/bash
# Diagnostic script to check network monitor status

echo "=== Network Monitor Status Check ==="
echo ""

echo "1. Checking if monitor.py is running..."
if docker exec network-monitor pgrep -f monitor.py > /dev/null 2>&1; then
    echo "   ✓ monitor.py is running"
    docker exec network-monitor pgrep -fa monitor.py
else
    echo "   ✗ monitor.py is NOT running"
    echo "   Start it with: sudo systemctl start network-monitor-daemon.service"
fi
echo ""

echo "2. Checking database file..."
if docker exec network-monitor test -f logs/network_monitor.db 2>/dev/null; then
    echo "   ✓ Database exists"
    docker exec network-monitor ls -lh logs/network_monitor.db
else
    echo "   ✗ Database does not exist"
    echo "   It will be created when monitor.py runs"
fi
echo ""

echo "3. Checking database contents..."
docker exec network-monitor python3 -c "
from db import NetworkMonitorDB
import sys
try:
    db = NetworkMonitorDB('logs/network_monitor.db')
    hours = db.get_available_hours()
    print(f'   Available hours: {len(hours)}')
    if hours:
        print('   Recent hours:')
        for date, hour, count in hours[:5]:
            print(f'     - {date} {hour}:00 ({count} entries)')
    else:
        print('   ⚠ Database is empty - no data yet')
        print('   Data will appear after monitor.py runs for a few minutes')
    db.close()
except Exception as e:
    print(f'   ✗ Error reading database: {e}')
    sys.exit(1)
" 2>&1
echo ""

echo "4. Checking web server..."
if docker exec network-monitor pgrep -f serve.py > /dev/null 2>&1; then
    echo "   ✓ serve.py is running"
else
    echo "   ✗ serve.py is NOT running"
    echo "   Start it with: sudo systemctl start network-monitor-server.service"
fi
echo ""

echo "5. Checking systemd services..."
echo "   Monitor daemon:"
systemctl is-active network-monitor-daemon.service 2>&1 | sed 's/^/     /'
echo "   Web server:"
systemctl is-active network-monitor-server.service 2>&1 | sed 's/^/     /'
echo ""

echo "=== Summary ==="
echo "If everything is running but you see no data:"
echo "  1. Wait a few minutes for data to accumulate"
echo "  2. Refresh the web page at http://$(hostname -I | awk '{print $1}'):8080"
echo "  3. You should see hours listed under today's date"
echo ""

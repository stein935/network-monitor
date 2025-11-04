#!/bin/bash
# Startup script to run nginx, Python HTTP server, and WebSocket server

set -e

echo "[*] Starting Network Monitor services..."

# Start nginx
echo "[*] Starting nginx..."
nginx -t  # Test configuration
nginx

# Start Python server in background (HTTP on 8090, WebSocket on 8081)
# nginx listens on 8080 and proxies to Python on 8090
echo "[*] Starting Python server (HTTP: 8090, WebSocket: 8081)..."
python3 /app/serve.py logs 8090 &
PYTHON_PID=$!

echo "[*] All services started"
echo "[*] nginx: port 8080 (internal)"
echo "[*] Python HTTP: port 8090 (internal, proxied by nginx)"
echo "[*] Python WebSocket: port 8081"
echo "[*] Python PID: $PYTHON_PID"

# Keep script running and monitor processes
trap 'echo "[*] Stopping services..."; nginx -s quit; kill $PYTHON_PID; exit 0' SIGTERM SIGINT

# Wait for Python process
wait $PYTHON_PID

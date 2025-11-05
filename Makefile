.PHONY: help dev build start stop restart logs shell test clean deploy rebuild-prod update-prod status

# Default target
help:
	@echo "Network Monitor - Development Commands"
	@echo ""
	@echo "Local Development:"
	@echo "  make dev          - Quick dev: copy code to running container & restart"
	@echo "  make build        - Build Docker image from scratch"
	@echo "  make start        - Start container and services"
	@echo "  make restart      - Restart services in container"
	@echo "  make stop         - Stop and remove container"
	@echo ""
	@echo "Debugging:"
	@echo "  make logs         - Follow container logs"
	@echo "  make shell        - Open bash shell in container"
	@echo "  make status       - Check status of all services"
	@echo "  make test         - Test HTTP endpoints"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy       - Deploy to Raspberry Pi (via GitHub)"
	@echo "  make rebuild-prod - Full rebuild (use on Pi after git pull)"
	@echo "  make update-prod  - Quick update (on Pi, no rebuild)"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean        - Remove container, image, and logs"

# Quick development: copy code and restart
dev:
	@echo "📦 Copying code to container..."
	@docker cp serve.py network-monitor:/app/serve.py
	@docker cp db.py network-monitor:/app/db.py
	@docker cp monitor.py network-monitor:/app/monitor.py
	@docker cp start_services.sh network-monitor:/app/start_services.sh
	@docker cp nginx.conf network-monitor:/etc/nginx/nginx.conf
	@docker cp static network-monitor:/app/
	@docker exec network-monitor chmod +x /app/start_services.sh
	@echo "🔄 Stopping services..."
	@docker exec network-monitor pkill -f serve.py 2>/dev/null || true
	@docker exec network-monitor nginx -s quit 2>/dev/null || true
	@sleep 2
	@echo "🚀 Starting nginx..."
	@docker exec network-monitor nginx -t
	@docker exec network-monitor nginx
	@echo "🚀 Starting Python server..."
	@docker exec -d network-monitor python3 /app/serve.py logs 8090
	@sleep 2
	@echo "🔍 Verifying services..."
	@docker exec network-monitor pgrep -f serve.py > /dev/null && echo "  ✅ serve.py running" || echo "  ❌ serve.py failed to start"
	@docker exec network-monitor pgrep nginx > /dev/null && echo "  ✅ nginx running" || echo "  ❌ nginx failed to start"
	@docker exec network-monitor netstat -tlnp 2>/dev/null | grep -q 8090 && echo "  ✅ Port 8090 listening" || echo "  ⚠️  Port 8090 not listening"
	@docker exec network-monitor netstat -tlnp 2>/dev/null | grep -q 8081 && echo "  ✅ Port 8081 listening" || echo "  ⚠️  Port 8081 not listening"
	@echo "✅ Dev environment updated!"
	@echo "🌐 Open http://localhost:8080"

# Build from scratch
build:
	@echo "🏗️  Building Docker image..."
	docker compose down || true
	docker compose build --no-cache
	@echo "✅ Build complete!"

# Start everything fresh
start:
	@echo "🚀 Starting container..."
	docker compose up -d
	@sleep 3
	@echo "📊 Starting monitor (generates data)..."
	docker exec -d network-monitor python3 /app/monitor.py 1 60
	@echo "⏳ Waiting 30 seconds for initial data..."
	@sleep 30
	@echo "🌐 Starting web services..."
	docker exec -d network-monitor /bin/bash /app/start_services.sh
	@sleep 2
	@echo "✅ All services started!"
	@echo "🌐 Open http://localhost:8080"

# Restart services only (no rebuild)
restart:
	@echo "🔄 Restarting services..."
	docker exec network-monitor pkill -f monitor.py || true
	docker exec network-monitor pkill -f serve.py || true
	docker exec network-monitor nginx -s quit || true
	@sleep 2
	docker exec -d network-monitor python3 /app/monitor.py 1 60
	docker exec -d network-monitor /bin/bash /app/start_services.sh
	@echo "✅ Services restarted!"

# Stop everything
stop:
	@echo "🛑 Stopping container..."
	docker compose down
	@echo "✅ Stopped!"

# View logs
logs:
	@echo "📋 Following logs (Ctrl+C to exit)..."
	docker logs network-monitor -f

# Open shell in container
shell:
	@echo "🐚 Opening shell in container..."
	docker exec -it network-monitor /bin/bash

# Check status
status:
	@echo "📊 Container Status:"
	@docker ps | grep network-monitor || echo "  ❌ Container not running"
	@echo ""
	@echo "📊 Processes in Container:"
	@docker exec network-monitor ps aux | grep -E "nginx|serve.py|monitor.py" || echo "  ❌ No services running"
	@echo ""
	@echo "📊 Database Status:"
	@docker exec network-monitor python3 -c "from db import NetworkMonitorDB; db = NetworkMonitorDB('logs/network_monitor.db'); hours = db.get_available_hours(); print(f'  ✅ {len(hours)} hours of data available')" || echo "  ❌ Database error"
	@echo ""
	@echo "📊 Listening Ports:"
	@docker exec network-monitor netstat -tlnp 2>/dev/null | grep -E "8080|8081|8090" || echo "  ❌ No ports listening"

# Test endpoints
test:
	@echo "🧪 Testing HTTP endpoint..."
	@curl -s http://localhost:8080 | head -5 || echo "❌ Failed"
	@echo ""
	@echo "🧪 Testing WebSocket port..."
	@nc -zv localhost 8081 2>&1 | head -1

# Clean everything
clean:
	@echo "🧹 Cleaning up..."
	docker compose down || true
	docker rm -f network-monitor 2>/dev/null || true
	docker rmi network-monitor:latest 2>/dev/null || true
	@echo "⚠️  Delete logs? (y/N): " && read ans && [ $${ans:-N} = y ] && rm -rf logs/* || true
	@echo "✅ Cleanup complete!"

# Deploy to Raspberry Pi (automated if PI_HOST is set)
deploy:
	@echo "🚀 Deploying to Raspberry Pi..."
	@echo "📤 Pushing to GitHub..."
	git push origin main
ifdef PI_HOST
	@echo "📥 Deploying to $(PI_HOST)..."
	ssh $(PI_HOST) 'cd ~/network-monitor && git pull origin main && make rebuild-prod'
	@echo "✅ Deployment complete!"
	@echo "🌐 Visit http://$(PI_HOST):8080"
else
	@echo ""
	@echo "📥 Manual deployment steps:"
	@echo "  1. SSH to your Raspberry Pi"
	@echo "  2. cd ~/network-monitor"
	@echo "  3. git pull origin main"
	@echo "  4. make rebuild-prod"
	@echo ""
	@echo "Or set PI_HOST environment variable for automated deployment:"
	@echo "  export PI_HOST=pi@192.168.1.100"
	@echo "  make deploy"
endif

# Full rebuild for production (use on Pi after pull)
rebuild-prod:
	@echo "🏗️  Rebuilding for production..."
	docker compose down || true
	docker compose build --no-cache
	docker compose up -d
	@sleep 5
	@echo "📊 Starting monitor..."
	docker exec -d network-monitor python3 /app/monitor.py 5 12
	@echo "⏳ Waiting 30 seconds for initial data..."
	@sleep 30
	@echo "🌐 Starting web services..."
	docker exec -d network-monitor /bin/bash /app/start_services.sh
	@sleep 3
	@echo "✅ Production deployment complete!"
	@make status

# Quick update for production (faster, no rebuild)
update-prod:
	@echo "⚡ Quick production update..."
	git pull origin main
	@make dev
	@echo "✅ Production updated!"

.PHONY: help dev build start stop stop-prod restart logs shell test clean deploy rebuild-prod update-prod status

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
	@echo "  make stop-prod    - Complete shutdown (systemd + container, no cleanup)"
	@echo ""
	@echo "Debugging:"
	@echo "  make logs         - Follow container logs"
	@echo "  make shell        - Open bash shell in container"
	@echo "  make status       - Check status of all services"
	@echo "  make test         - Test HTTP endpoints"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy       - Deploy to remote server (via rsync, set DEPLOY_HOST)"
	@echo "  make rebuild-prod - Full rebuild (use on server after deploy)"
	@echo "  make update-prod  - Quick update (on server, no rebuild)"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean        - Remove container, image, and logs"

# Quick development: copy code and restart
dev:
	@echo "📦 Copying code to container..."
	@docker cp serve.py network-monitor:/app/serve.py
	@docker cp db.py network-monitor:/app/db.py
	@docker cp monitor.py network-monitor:/app/monitor.py
	@docker cp utils.py network-monitor:/app/utils.py
	@docker cp dashboard_generator.py network-monitor:/app/dashboard_generator.py
	@docker cp websocket_server.py network-monitor:/app/websocket_server.py
	@docker cp api_handlers.py network-monitor:/app/api_handlers.py
	@docker cp start_services.sh network-monitor:/app/start_services.sh
	@docker cp nginx.conf network-monitor:/etc/nginx/nginx.conf
	@docker cp VERSION network-monitor:/app/VERSION
	@docker cp static network-monitor:/app/
	@docker exec network-monitor chmod +x /app/start_services.sh
	@echo "🔄 Stopping services..."
	@docker exec network-monitor pkill -f serve.py 2>/dev/null || true
	@docker exec network-monitor pkill nginx 2>/dev/null || true
	@sleep 3
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
	@echo "🌐 Refreshing http://localhost..."
	@osascript -e 'tell application "Google Chrome"' \
		-e '  set found to false' \
		-e '  set targetURL to "localhost"' \
		-e '  repeat with w in windows' \
		-e '    set tabIndex to 1' \
		-e '    repeat with t in tabs of w' \
		-e '      if URL of t contains targetURL then' \
		-e '        set found to true' \
		-e '        set index of w to 1' \
		-e '        set active tab index of w to tabIndex' \
		-e '        activate' \
		-e '        tell application "System Events"' \
		-e '          keystroke "r" using {command down, shift down}' \
		-e '        end tell' \
		-e '        exit repeat' \
		-e '      end if' \
		-e '      set tabIndex to tabIndex + 1' \
		-e '    end repeat' \
		-e '    if found then exit repeat' \
		-e '  end repeat' \
		-e '  if not found then' \
		-e '    activate' \
		-e '    make new tab at end of tabs of front window with properties {URL:"http://localhost"}' \
		-e '  end if' \
		-e 'end tell' 2>/dev/null || open -a "Google Chrome" http://localhost

# Build from scratch
build:
	@echo "🏗️  Building Docker image..."
	docker-compose down || true
	docker-compose build --no-cache
	@echo "✅ Build complete!"

# Start everything fresh
start:
	@echo "🚀 Starting container..."
	docker-compose up -d
	@sleep 3
	@echo "📊 Starting monitor (generates data)..."
	docker exec -d network-monitor python3 /app/monitor.py 5 12
	@echo "🌐 Starting web services..."
	docker exec -d network-monitor /bin/bash /app/start_services.sh
	@sleep 2
	@echo "✅ All services started!"
	@echo "🌐 Open http://localhost"

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
	docker-compose down
	@echo "✅ Stopped!"

# Complete production shutdown (systemd + container, no cleanup)
stop-prod:
	@echo "🛑 Complete shutdown initiated..."
	@echo "🛑 Stopping systemd services..."
	sudo systemctl stop network-monitor-server.service 2>/dev/null || true
	sudo systemctl stop network-monitor-daemon.service 2>/dev/null || true
	sudo systemctl stop network-monitor-container.service 2>/dev/null || true
	@echo "🔒 Disabling systemd services..."
	sudo systemctl disable network-monitor-server.service 2>/dev/null || true
	sudo systemctl disable network-monitor-daemon.service 2>/dev/null || true
	sudo systemctl disable network-monitor-container.service 2>/dev/null || true
	@echo "🛑 Stopping Docker container..."
	docker-compose down || true
	@echo "✅ Complete shutdown finished!"
	@echo "📝 Image and logs preserved"

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
	@docker exec network-monitor ss -tlnp 2>/dev/null | grep -E "8080|8081|8090" || echo "  ❌ No ports listening"

# Test endpoints
test:
	@echo "🧪 Testing HTTP endpoint..."
	@curl -s http://localhost | head -5 || echo "❌ Failed"
	@echo ""
	@echo "🧪 Testing WebSocket port..."
	@nc -zv localhost 8081 2>&1 | head -1

# Clean everything
clean:
	@echo "🧹 Cleaning up..."
	docker-compose down || true
	docker rm -f network-monitor 2>/dev/null || true
	docker rmi network-monitor:latest 2>/dev/null || true
	@echo "⚠️  Delete logs? (y/N): " && read ans && [ $${ans:-N} = y ] && rm -rf logs/* || true
	@echo "✅ Cleanup complete!"

# Deploy to remote server via rsync (set DEPLOY_HOST environment variable)
deploy:
ifndef DEPLOY_HOST
	@echo "❌ Error: DEPLOY_HOST not set"
	@echo ""
	@echo "Set DEPLOY_HOST environment variable first:"
	@echo "  export DEPLOY_HOST=ubuntu@192.168.10.151"
	@echo "  make deploy"
	@exit 1
endif
	@echo "🚀 Deploying to $(DEPLOY_HOST)..."
	@echo "📤 Transferring files via rsync..."
	@rsync -avz --delete \
		--include='*.py' \
		--include='Dockerfile' \
		--include='docker-compose.yml' \
		--include='.dockerignore' \
		--include='nginx.conf' \
		--include='start_services.sh' \
		--include='VERSION' \
		--include='Makefile' \
		--include='static/' --include='static/***' \
		--include='systemd/' --include='systemd/***' \
		--exclude='*' \
		./ $(DEPLOY_HOST):/opt/network-monitor/
	@echo "📥 Building and starting services on $(DEPLOY_HOST)..."
	@ssh -t $(DEPLOY_HOST) 'cd /opt/network-monitor && sudo make install-services && make rebuild-prod'
	@echo "✅ Deployment complete!"
	@echo "🌐 Visit http://$(DEPLOY_HOST)"

# Install systemd services (requires sudo, run once)
install-services:
	@echo "📋 Installing systemd services..."
	sudo cp systemd/*.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable network-monitor-container.service
	sudo systemctl enable network-monitor-daemon.service
	sudo systemctl enable network-monitor-server.service
	@echo "✅ Services installed!"

# Full rebuild for production (use on Pi after pull)
rebuild-prod: install-services
	@echo "🏗️  Rebuilding for production..."
	@echo "🛑 Stopping existing services..."
	sudo systemctl stop network-monitor-server.service || true
	sudo systemctl stop network-monitor-daemon.service || true
	sudo systemctl stop network-monitor-container.service || true
	@echo "🐳 Rebuilding Docker container..."
	docker-compose down || true
	docker-compose build --no-cache
	@echo "🚀 Starting services via systemd..."
	sudo systemctl start network-monitor-container.service
	@sleep 5
	sudo systemctl start network-monitor-daemon.service
	@sleep 30
	sudo systemctl start network-monitor-server.service
	@sleep 3
	@echo "✅ Production deployment complete!"
	@make status

# Quick update for production (faster, no rebuild)
update-prod:
	@echo "⚡ Quick production update..."
	git pull origin main
	@echo "📋 Updating systemd services..."
	sudo cp systemd/*.service /etc/systemd/system/
	sudo systemctl daemon-reload
	@echo "🔄 Restarting services..."
	sudo systemctl restart network-monitor-server.service
	sudo systemctl restart network-monitor-daemon.service
	@sleep 3
	@echo "✅ Production updated!"
	@make status

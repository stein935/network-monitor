# Deployment Guide

This guide covers deploying Network Monitor to a remote Linux server using Docker and rsync.

## Overview

Network Monitor uses:
- **Docker** for containerization
- **systemd** for service management
- **rsync** for file transfer (no git required on server)

This guide has been tested on:
- Ubuntu Server 22.04+
- Raspberry Pi OS (Debian-based)
- Raspberry Pi Zero 2 W (ARM optimization included)

## Prerequisites

### Local Machine

1. **SSH access** to the remote server
2. **rsync** installed (usually pre-installed on macOS/Linux)
3. **Network Monitor repository** cloned locally

### Remote Server

SSH to your server and install dependencies:

```bash
# Update package index
sudo apt update

# Install Docker, Docker Compose, and utilities
sudo apt install -y docker.io docker-compose make rsync

# Add your user to docker group (avoids needing sudo for docker commands)
sudo usermod -aG docker $USER

# Start and enable Docker
sudo systemctl start docker
sudo systemctl enable docker

# Log out and back in for group changes to take effect
exit
```

## Initial Setup

### 1. Set Up SSH Key Authentication

From your local machine:

```bash
# Generate SSH key if you don't have one
ssh-keygen -t ed25519 -C "network-monitor-deploy"

# Copy SSH key to remote server
ssh-copy-id user@your-server-ip

# Test SSH connection
ssh user@your-server-ip
```

### 2. Create Deployment Directory

On the remote server:

```bash
# Create deployment directory
sudo mkdir -p /opt/network-monitor

# Set ownership to your user
sudo chown $USER:$USER /opt/network-monitor

# Verify
ls -ld /opt/network-monitor
```

### 3. Configure Local Deployment

On your local machine:

```bash
# Set environment variable for deployment
export DEPLOY_HOST=user@your-server-ip

# Add to ~/.bashrc or ~/.zshrc to persist:
echo 'export DEPLOY_HOST=user@your-server-ip' >> ~/.bashrc
source ~/.bashrc
```

## Deployment

### First Deployment

From your local machine, in the network-monitor directory:

```bash
# Verify environment variable is set
echo $DEPLOY_HOST

# Deploy (transfers files via rsync, builds container, starts services)
make deploy
```

This will:
1. Transfer all required files to `/opt/network-monitor` on the server
2. Install systemd services
3. Build Docker container
4. Start all services

### Verify Deployment

```bash
# SSH to server
ssh $DEPLOY_HOST

# Check container status
docker ps | grep network-monitor

# Check systemd services
systemctl status 'network-monitor-*'

# Check processes inside container
docker exec network-monitor ps aux | grep -E "nginx|serve.py|monitor.py"

# Check listening ports
docker exec network-monitor ss -tlnp | grep -E "8080|8081|8090"
```

Access the dashboard at: `http://your-server-ip`

## Subsequent Deployments

After making changes to your local code:

```bash
# Deploy updates
make deploy
```

This automatically:
- Syncs changed files
- Rebuilds the container
- Restarts services

## Systemd Service Management

The deployment uses three systemd services:

1. **network-monitor-container.service** - Manages Docker container lifecycle
2. **network-monitor-daemon.service** - Runs monitoring daemon inside container
3. **network-monitor-server.service** - Runs web server (nginx + Python) inside container

### Common Commands

```bash
# Check all services
systemctl status 'network-monitor-*'

# Restart a specific service
sudo systemctl restart network-monitor-daemon.service
sudo systemctl restart network-monitor-server.service

# View logs
sudo journalctl -u network-monitor-daemon.service -f
sudo journalctl -u network-monitor-server.service -f

# Stop all services
sudo systemctl stop network-monitor-server.service
sudo systemctl stop network-monitor-daemon.service
sudo systemctl stop network-monitor-container.service

# Start all services
sudo systemctl start network-monitor-container.service
sleep 5
sudo systemctl start network-monitor-daemon.service
sleep 30
sudo systemctl start network-monitor-server.service
```

### Service Dependencies

- `network-monitor-daemon.service` requires `network-monitor-container.service`
- `network-monitor-server.service` requires `network-monitor-container.service`

## Manual Deployment (Without Makefile)

If you prefer not to use the Makefile:

### Transfer Files

```bash
# From local machine
rsync -avz --delete \
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
  ./ $DEPLOY_HOST:/opt/network-monitor/
```

### Build and Start on Server

```bash
# SSH to server
ssh $DEPLOY_HOST

cd /opt/network-monitor

# Install systemd services
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable network-monitor-container.service
sudo systemctl enable network-monitor-daemon.service
sudo systemctl enable network-monitor-server.service

# Build container
docker compose down || true
docker compose build --no-cache

# Start services
sudo systemctl start network-monitor-container.service
sleep 5
sudo systemctl start network-monitor-daemon.service
sleep 30
sudo systemctl start network-monitor-server.service
```

## Configuration

### Monitor Parameters

Edit on the server or locally before deploying:

`systemd/network-monitor-daemon.service`:
```bash
ExecStart=/usr/bin/docker exec network-monitor python3 /app/monitor.py 5 12
#                                                                     ^  ^^
#                                                                     |  |
#                                              FREQUENCY (seconds) ---|  |--- SAMPLE_SIZE (pings)
```

- **FREQUENCY**: Seconds between pings (default: 5)
- **SAMPLE_SIZE**: Number of pings before logging (default: 12)
- Result: One log entry every 60 seconds (5 × 12)

After changing, redeploy or restart the daemon service:
```bash
sudo systemctl daemon-reload
sudo systemctl restart network-monitor-daemon.service
```

### Port Configuration

Default ports (in `docker-compose.yml`):
- `80:8080` - nginx HTTP (external:internal)
- `8081:8081` - WebSocket (external:internal)

To change external ports (example):
```yaml
ports:
  - "9000:8080"  # Access at port 9000 instead of 80
  - "9001:8081"  # Access at port 9001 instead of 8081
```

After changing:
```bash
docker compose down
docker compose up -d
```

## Troubleshooting

### Check Service Status

```bash
# On server
systemctl status 'network-monitor-*'
docker ps
docker logs network-monitor
```

### Port Conflicts

If port 80 or 8081 is already in use:

```bash
# Find process using port
sudo ss -tlnp | grep 80

# Kill process if needed
sudo kill <PID>

# Or change ports in docker-compose.yml
```

### Speed Tests Not Running

```bash
# Check if monitor.py is running
docker exec network-monitor pgrep -f monitor.py

# View logs for speed test entries
docker logs network-monitor | grep -i speed
```

### Database Issues

```bash
# Check database on server
docker exec network-monitor python3 -c "from db import NetworkMonitorDB; db = NetworkMonitorDB('logs/network_monitor.db'); print(f'Hours available: {len(db.get_available_hours())}')"
```

### Memory Constraints (Raspberry Pi)

On Raspberry Pi Zero 2 W with limited RAM:

1. Increase ping frequency, reduce sample size:
   ```bash
   # In systemd/network-monitor-daemon.service
   ExecStart=/usr/bin/docker exec network-monitor python3 /app/monitor.py 10 60
   ```

2. Reduce Docker resource limits in `docker-compose.yml`

### Container Won't Start

```bash
# Check Docker status
sudo systemctl status docker

# Check container logs
docker logs network-monitor

# Rebuild from scratch
docker compose down
docker compose build --no-cache
docker compose up -d
```

## Updating After Code Changes

### Quick Update (No Container Rebuild)

If you only changed Python files, nginx config, or static files:

```bash
# On server
cd /opt/network-monitor
git pull origin main  # If using git on server
# OR: run 'make deploy' from local machine to rsync changes

sudo systemctl restart network-monitor-server.service
```

### Full Rebuild

For Dockerfile or dependency changes:

```bash
make deploy  # From local machine
# OR on server:
cd /opt/network-monitor
make rebuild-prod
```

## Uninstalling

```bash
# On server
sudo systemctl stop network-monitor-server.service
sudo systemctl stop network-monitor-daemon.service
sudo systemctl stop network-monitor-container.service

sudo systemctl disable network-monitor-server.service
sudo systemctl disable network-monitor-daemon.service
sudo systemctl disable network-monitor-container.service

sudo rm /etc/systemd/system/network-monitor-*.service
sudo systemctl daemon-reload

docker compose down
docker rmi network-monitor:latest

sudo rm -rf /opt/network-monitor
```

## Security Considerations

1. **Firewall**: Only expose port 80 if needed externally
   ```bash
   sudo ufw allow 80/tcp
   sudo ufw enable
   ```

2. **HTTPS**: Consider using nginx reverse proxy with Let's Encrypt for HTTPS

3. **SSH keys**: Use key-based authentication, disable password auth

4. **Updates**: Keep server packages updated:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

## Performance Tuning

### Raspberry Pi Optimizations

Already included in the project:
- WAL mode for SQLite (30% faster writes)
- nginx caching and compression
- Disabled Chart.js animations
- Reduced logging frequency
- 15-minute speed test intervals (vs continuous)

### For Higher-End Servers

You can increase monitoring frequency:

```bash
# In systemd/network-monitor-daemon.service
ExecStart=/usr/bin/docker exec network-monitor python3 /app/monitor.py 1 60
#                                                                     ^ ping every 1 second
```

## Next Steps

- Set up automated backups of `/opt/network-monitor/logs/network_monitor.db`
- Configure firewall rules
- Set up monitoring alerts (via custom scripts reading the database)
- Consider HTTPS with Let's Encrypt

## Support

For issues or questions:
- Check [README.md](README.md) for architecture details
- Review [CLAUDE.md](CLAUDE.md) for developer documentation
- File issues on GitHub

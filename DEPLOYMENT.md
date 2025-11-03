# Network Monitor - Raspberry Pi Zero 2 W Deployment Guide

This guide covers deploying the Network Monitor as a Docker container on a Raspberry Pi Zero 2 W Rev 1.0 running Raspbian GNU/Linux 12 (bookworm).

## Table of Contents

- [Hardware Specifications](#hardware-specifications)
- [Prerequisites](#prerequisites)
- [Docker Setup](#docker-setup)
- [Project Deployment](#project-deployment)
- [Systemd Services](#systemd-services)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

## Hardware Specifications

- **Device**: Raspberry Pi Zero 2 W Rev 1.0
- **OS**: Raspbian GNU/Linux 12 (bookworm)
- **Architecture**: ARM (armv7l or aarch64)

## Prerequisites

### 1. Update System

```bash
sudo apt update
sudo apt upgrade -y
```

### 2. Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group
sudo usermod -aG docker $USER

# Log out and back in for group changes to take effect
# Or run: newgrp docker

# Verify installation
docker --version
```

### 3. Install Required System Packages

```bash
sudo apt install -y \
    git \
    python3 \
    python3-pip \
    python3-venv \
    bc \
    iputils-ping
```

## Docker Setup

### 1. Create Dockerfile

Create a `Dockerfile` in the project root:

> **Note**: This Dockerfile uses Miniconda base image for much faster builds with pre-compiled pandas and plotly packages. This is especially important for ARM devices like Raspberry Pi where compilation can take 30+ minutes.

```dockerfile
FROM continuumio/miniconda3:latest

# Install system dependencies
RUN apt-get update && apt-get install -y \
    bc \
    iputils-ping \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python dependencies using conda (much faster)
RUN conda install -y pandas plotly && \
    conda clean -a

# Copy application files
COPY . .

# Create logs directory
RUN mkdir -p logs

# Expose web server port
EXPOSE 80

# Set environment variables
ENV PYTHONUNBUFFERED=1

```

### 2. Create Docker Compose File

### 2. Create Docker Compose File

Create `docker-compose.yml`:

```yaml
version: "3.8"

services:
  network-monitor:
    build: .
    container_name: network-monitor
    restart: unless-stopped
    ports:
      - "80:80"
    volumes:
      - ./logs:/app/logs
    network_mode: bridge
    privileged: true # Required for ping
    cap_add:
      - NET_RAW
      - NET_ADMIN
```

### 3. Create .dockerignore

Create `.dockerignore` to exclude unnecessary files:

```
venv/
__pycache__/
*.pyc
.git/
.gitignore
README.md
DEPLOYMENT.md
logs/
```

## Project Deployment

### 1. Clone Repository

```bash
cd ~
git clone https://github.com/stein935/network-monitor.git
cd network-monitor
```

### 2. Build Docker Image

```bash
docker compose build
```

### 3. Start Container

```bash
docker compose up -d
```

### 4. Verify Container is Running

```bash
docker ps
docker logs network-monitor
```

## Systemd Services

### 1. Create Monitor Service

Create `/etc/systemd/system/network-monitor-daemon.service`:

```bash
sudo nano /etc/systemd/system/network-monitor-daemon.service
```

Add the following content:

```ini
[Unit]
Description=Network Monitor Daemon (Docker)
After=docker.service
Requires=docker.service

[Service]
Type=simple
Restart=always
RestartSec=10
ExecStart=/usr/bin/docker exec network-monitor /bin/bash -c "cd /app && ./monitor.sh 1 60"
ExecStop=/usr/bin/docker exec network-monitor pkill -f monitor.sh

[Install]
WantedBy=multi-user.target
```

### 2. Create Web Server Service

Create `/etc/systemd/system/network-monitor-server.service`:

```bash
sudo nano /etc/systemd/system/network-monitor-server.service
```

Add the following content:

```ini
[Unit]
Description=Network Monitor Web Server (Docker)
After=docker.service network-monitor-daemon.service
Requires=docker.service

[Service]
Type=simple
Restart=always
RestartSec=10
ExecStart=/usr/bin/docker exec network-monitor /bin/bash -c "cd /app && ./serve.sh logs 80"
ExecStop=/usr/bin/docker exec network-monitor pkill -f serve.py

[Install]
WantedBy=multi-user.target
```

### 3. Create Docker Container Startup Service

Create `/etc/systemd/system/network-monitor-container.service`:

```bash
sudo nano /etc/systemd/system/network-monitor-container.service
```

Add the following content:

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

### 4. Enable and Start Services

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable services to start on boot
sudo systemctl enable network-monitor-container.service
sudo systemctl enable network-monitor-daemon.service
sudo systemctl enable network-monitor-server.service

# Start container first
sudo systemctl start network-monitor-container.service

# Wait a few seconds for container to be ready
sleep 5

# Start monitor and server
sudo systemctl start network-monitor-daemon.service
sudo systemctl start network-monitor-server.service
```

### 5. Check Service Status

```bash
sudo systemctl status network-monitor-container.service
sudo systemctl status network-monitor-daemon.service
sudo systemctl status network-monitor-server.service
```

## Verification

### 1. Check Docker Container

```bash
# Container is running
docker ps | grep network-monitor

# View container logs
docker logs network-monitor

# Enter container shell
docker exec -it network-monitor /bin/bash
```

### 2. Check Monitor Process

```bash
# Inside container
docker exec network-monitor pgrep -f monitor.sh

# View monitor logs
docker exec network-monitor ls -la /app/logs/
```

### 3. Check Web Server

```bash
# Test locally on Pi
curl http://localhost:80

# From another device on network
# Open browser to: http://<raspberry-pi-ip>
```

### 4. View Service Logs

```bash
# Monitor daemon logs
sudo journalctl -u network-monitor-daemon.service -f

# Web server logs
sudo journalctl -u network-monitor-server.service -f

# Container logs
sudo journalctl -u network-monitor-container.service -f
```

## Configuration

### Environment Variables

To configure the monitor or server, you can modify the systemd service files or create an environment file.

Create `/home/pi/scripts/network-monitor/.env`:

```bash
MONITOR_FREQUENCY=1
MONITOR_SAMPLE_SIZE=60
SERVER_PORT=80
LOG_RETENTION_DAYS=10
```

Update the service files to use these variables:

```ini
[Service]
EnvironmentFile=/home/pi/scripts/network-monitor/.env
ExecStart=/usr/bin/docker exec network-monitor /bin/bash -c "cd /app && ./monitor.sh ${MONITOR_FREQUENCY} ${MONITOR_SAMPLE_SIZE}"
```

### Port Mapping

To change the external port (default is 80), edit `docker-compose.yml`:

```yaml
ports:
  - "8080:80" # Change 8080 to your desired port
```

Then recreate the container:

```bash
docker compose down
docker compose up -d
```

## Maintenance

### Update Project

```bash
cd ~/network-monitor
git pull origin main
docker compose down
docker compose build
docker compose up -d
sudo systemctl restart network-monitor-daemon.service
sudo systemctl restart network-monitor-server.service
```

### View Logs

```bash
# Real-time CSV data
docker exec network-monitor tail -f /app/logs/$(date +%Y-%m-%d)/csv/monitor_$(date +%Y%m%d_%H).csv

# Monitor script output
sudo journalctl -u network-monitor-daemon.service -f

# Web server output
sudo journalctl -u network-monitor-server.service -f
```

### Backup Logs

```bash
# Logs are stored in ./logs on the host
cd ~/scripts/network-monitor
tar -czf network-monitor-logs-$(date +%Y%m%d).tar.gz logs/
```

### Clean Up Old Containers

```bash
# Remove stopped containers
docker container prune -f

# Remove unused images
docker image prune -a -f
```

## Troubleshooting

### Container Won't Start

```bash
# Check Docker logs
docker logs network-monitor

# Check if port 80 is already in use
sudo netstat -tlnp | grep :80

# Try rebuilding
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Monitor Not Running

```bash
# Check if process is running inside container
docker exec network-monitor pgrep -f monitor.sh

# Manually start monitor for testing
docker exec -it network-monitor /bin/bash
cd /app
./monitor.sh 1 60
```

### Web Server Not Accessible

```bash
# Check if server is running
docker exec network-monitor pgrep -f serve.py

# Check if port is exposed
docker port network-monitor

# Test from inside container
docker exec network-monitor curl http://localhost:80

# Check firewall (if enabled)
sudo ufw status
sudo ufw allow 80/tcp
```

### Permission Issues

```bash
# Fix log directory permissions
sudo chown -R $(whoami):$(whoami) ~/scripts/network-monitor/logs

# Ensure container has necessary capabilities
# Edit docker-compose.yml and add:
# cap_add:
#   - NET_RAW
#   - NET_ADMIN
```

### Ping Not Working

```bash
# Verify container has NET_RAW capability
docker inspect network-monitor | grep -A 10 CapAdd

# Test ping inside container
docker exec network-monitor ping -c 1 8.8.8.8
```

### Services Not Starting on Boot

```bash
# Check if services are enabled
sudo systemctl is-enabled network-monitor-container.service
sudo systemctl is-enabled network-monitor-daemon.service
sudo systemctl is-enabled network-monitor-server.service

# Re-enable if needed
sudo systemctl enable network-monitor-container.service
sudo systemctl enable network-monitor-daemon.service
sudo systemctl enable network-monitor-server.service

# Check boot logs
sudo journalctl -b | grep network-monitor
```

### Memory/Performance Issues (Pi Zero 2 W)

The Raspberry Pi Zero 2 W has limited resources. If experiencing issues:

```bash
# Increase swap space
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# Set CONF_SWAPSIZE=512
sudo dphys-swapfile setup
sudo dphys-swapfile swapon

# Reduce monitor frequency
# Edit systemd service to use: ./monitor.sh 5 60

# Monitor resource usage
docker stats network-monitor
```

## Security Considerations

### 1. Change Default Port

If exposing to the internet, avoid using port 80:

```yaml
ports:
  - "8443:80"
```

### 2. Add Authentication

Consider adding nginx with basic auth in front of the web server.

### 3. Firewall Rules

```bash
# Enable firewall
sudo apt install ufw
sudo ufw enable

# Allow SSH
sudo ufw allow ssh

# Allow web server port
sudo ufw allow 80/tcp

# Check status
sudo ufw status
```

### 4. Limit Docker Resources

Edit `docker-compose.yml`:

```yaml
services:
  network-monitor:
    # ... existing config ...
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 256M
```

## Performance Tuning for Raspberry Pi Zero 2 W

### Optimize Docker

```bash
# Edit Docker daemon config
sudo nano /etc/docker/daemon.json
```

Add:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

Restart Docker:

```bash
sudo systemctl restart docker
```

### Reduce Monitor Frequency

For the resource-constrained Pi Zero 2 W, consider:

```bash
# Check every 5 seconds with 60 samples (1 data point per 5 minutes)
./monitor.sh 5 60
```

## Quick Reference

### Common Commands

```bash
# View all services status
systemctl status 'network-monitor-*'

# Restart everything
sudo systemctl restart network-monitor-container.service
sudo systemctl restart network-monitor-daemon.service
sudo systemctl restart network-monitor-server.service

# View web server URL
echo "http://$(hostname -I | awk '{print $1}')"

# Access container shell
docker exec -it network-monitor /bin/bash

# Follow monitor logs in real-time
docker exec network-monitor tail -f /app/logs/$(date +%Y-%m-%d)/csv/monitor_$(date +%Y%m%d_%H).csv
```

## Next Steps

1. Access the web dashboard at `http://<raspberry-pi-ip>`
2. Monitor the Gruvbox-themed visualizations
3. Check logs are being created in the `logs/` directory
4. Verify auto-cleanup is removing logs older than 10 days

For more information, see the main [README.md](README.md).

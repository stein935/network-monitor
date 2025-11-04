FROM debian:bookworm-slim

# Install system dependencies including Python, nginx, and pre-built packages
# Using Debian base with system packages avoids lengthy compilation on ARM devices
RUN apt-get update && apt-get install -y \
  python3 \
  python3-pip \
  bc \
  iputils-ping \
  curl \
  procps \
  cron \
  nginx \
  python3-pandas \
  python3-plotly \
  python3-numpy \
  python3-websockets \
  && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy application files
COPY . .

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Create necessary directories
RUN mkdir -p logs static /var/log/nginx /var/lib/nginx /run

# Expose nginx and WebSocket ports
EXPOSE 8080 8081

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Make scripts executable
RUN chmod +x /app/start_services.sh /app/generate_static.sh

# Keep container running
CMD ["tail", "-f", "/dev/null"]
FROM debian:bookworm-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
  python3 \
  iputils-ping \
  curl \
  procps \
  nginx \
  python3-websockets \
  speedtest-cli \
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
RUN chmod +x /app/start_services.sh

# Keep container running
CMD ["tail", "-f", "/dev/null"]
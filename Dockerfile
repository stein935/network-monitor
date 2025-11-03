FROM debian:bookworm-slim

# Install system dependencies including Python and pre-built packages
# Using Debian base with system packages avoids lengthy compilation on ARM devices
RUN apt-get update && apt-get install -y \
  python3 \
  bc \
  iputils-ping \
  curl \
  procps \
  python3-pandas \
  python3-plotly \
  python3-numpy \
  && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy application files
COPY . .

# Create logs directory
RUN mkdir -p logs

# Expose web server port
EXPOSE 80

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Keep container running
CMD ["tail", "-f", "/dev/null"]
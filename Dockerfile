FROM python:3.11-slim-bookworm

# Install system dependencies including build tools for ARM
RUN apt-get update && apt-get install -y \
  bc \
  iputils-ping \
  curl \
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
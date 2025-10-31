FROM python:3.11-slim-bookworm

# Install system dependencies including build tools
RUN apt-get update && apt-get install -y \
  bc \
  iputils-ping \
  curl \
  build-essential \
  gcc \
  g++ \
  python3-dev \
  && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN python3 -m venv venv && \
  . venv/bin/activate && \
  pip install --upgrade pip && \
  pip install --only-binary=all --no-cache-dir -r requirements.txt || \
  pip install --no-cache-dir -r requirements.txt

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
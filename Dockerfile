FROM python:3.11-slim-bookworm

# Install system dependencies and Python scientific packages from apt
RUN apt-get update && apt-get install -y \
  bc \
  iputils-ping \
  curl \
  python3-pandas \
  python3-plotly \
  python3-pip \
  python3-venv \
  && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies (should be much faster with system packages)
RUN python3 -m venv venv --system-site-packages && \
  . venv/bin/activate && \
  pip install --upgrade pip && \
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
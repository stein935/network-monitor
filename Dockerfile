FROM python:3.11-slim-bookworm

# Install system dependencies including build tools for ARM
RUN apt-get update && apt-get install -y \
  bc \
  iputils-ping \
  curl \
  gcc \
  g++ \
  gfortran \
  libopenblas-dev \
  liblapack-dev \
  python3-dev \
  && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy application files
COPY . .

# Install Python packages using pip
RUN pip install --no-cache-dir pandas==2.0.3 plotly==5.17.0

# Create logs directory
RUN mkdir -p logs

# Expose web server port
EXPOSE 80

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Keep container running
CMD ["tail", "-f", "/dev/null"]
FROM python:3.11-slim-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y \
  bc \
  iputils-ping \
  curl \
  && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy application files
COPY . .

# Install Python dependencies directly (no venv for Docker)
# Use specific versions that have ARM wheels available
RUN pip install --upgrade pip && \
  pip install --only-binary=:all: \
  pandas==2.0.3 \
  plotly==5.17.0 \
  || pip install \
  pandas==2.0.3 \
  plotly==5.17.0

# Create logs directory
RUN mkdir -p logs

# Expose web server port
EXPOSE 80

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Keep container running
CMD ["tail", "-f", "/dev/null"]
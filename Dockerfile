FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Anvil
RUN pip install --no-cache-dir fableforge-anvil-agent[all]

# Create non-root user
RUN useradd -m -s /bin/bash anvil
USER anvil
WORKDIR /home/anvil

# Expose web UI port
EXPOSE 8000

# Default command: start web UI
CMD ["anvil", "serve", "--host", "0.0.0.0", "--port", "8000"]

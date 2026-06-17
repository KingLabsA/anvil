FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app/

# Install Anvil with all dependencies
RUN pip install --no-cache-dir -e ".[all]"

# Create non-root user
RUN useradd -m -u 1000 anvil && \
    chown -R anvil:anvil /app
USER anvil

# Expose port for web UI
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["anvil", "serve", "--host", "0.0.0.0", "--port", "8000"]

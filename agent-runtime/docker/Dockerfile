FROM python:3.12.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ src/

RUN pip install --no-cache-dir -e .

RUN mkdir -p /root/.agent_runtime

EXPOSE 8721

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8721/health')" || exit 1

ENTRYPOINT ["agentd"]
CMD ["start"]

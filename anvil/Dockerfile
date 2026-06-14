FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl git && \
    rm -rf /var/lib/apt/lists/*

FROM base AS builder

WORKDIR /build
COPY . /build/anvil/
RUN pip install --no-cache-dir /build/anvil httpx

FROM base AS runtime

RUN groupadd --gid 1000 anvil && \
    useradd --uid 1000 --gid anvil --shell /bin/bash --create-home anvil

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

WORKDIR /home/anvil

RUN mkdir -p /home/anvil/.anvil && chown anvil:anvil /home/anvil/.anvil

USER anvil

EXPOSE 8765

VOLUME ["/home/anvil/.anvil"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8765/health || exit 1

ENV ANVIL_HOME=/home/anvil/.anvil \
    ANVIL_HOST=0.0.0.0 \
    ANVIL_PORT=8765

ENTRYPOINT ["anvil"]
CMD ["daemon", "--host", "0.0.0.0", "--port", "8765"]
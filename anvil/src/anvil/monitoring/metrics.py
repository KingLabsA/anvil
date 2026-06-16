"""Monitoring and metrics for Anvil using Prometheus."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Optional

from prometheus_client import Counter, Histogram, Gauge, Summary, generate_latest, CONTENT_TYPE_LATEST


# ============================================================================
# Metrics Definitions
# ============================================================================

# Request metrics
REQUEST_COUNT = Counter(
    'anvil_requests_total',
    'Total number of API requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'anvil_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint'],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

# Task metrics
TASK_COUNT = Counter(
    'anvil_tasks_total',
    'Total number of tasks executed',
    ['status', 'model']
)

TASK_DURATION = Histogram(
    'anvil_task_duration_seconds',
    'Task execution duration in seconds',
    ['model'],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0)
)

TASK_ITERATIONS = Histogram(
    'anvil_task_iterations',
    'Number of iterations per task',
    ['model'],
    buckets=(1, 2, 3, 5, 10, 15, 20, 30, 50)
)

# Verification metrics
VERIFICATION_COUNT = Counter(
    'anvil_verifications_total',
    'Total number of verifications',
    ['result']
)

VERIFICATION_DURATION = Histogram(
    'anvil_verification_duration_seconds',
    'Verification duration in seconds',
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5)
)

# Model metrics
MODEL_REQUEST_COUNT = Counter(
    'anvil_model_requests_total',
    'Total number of model requests',
    ['model', 'status']
)

MODEL_TOKEN_USAGE = Counter(
    'anvil_model_tokens_total',
    'Total number of tokens used',
    ['model', 'type']  # type: 'input' or 'output'
)

MODEL_DURATION = Histogram(
    'anvil_model_duration_seconds',
    'Model request duration in seconds',
    ['model'],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)
)

# Session metrics
ACTIVE_SESSIONS = Gauge(
    'anvil_active_sessions',
    'Number of active sessions'
)

SESSION_COUNT = Counter(
    'anvil_sessions_total',
    'Total number of sessions created'
)

# User metrics
ACTIVE_USERS = Gauge(
    'anvil_active_users',
    'Number of active users'
)

USER_COUNT = Counter(
    'anvil_users_total',
    'Total number of users registered'
)

# WebSocket metrics
WEBSOCKET_CONNECTIONS = Gauge(
    'anvil_websocket_connections',
    'Number of active WebSocket connections'
)

WEBSOCKET_MESSAGES = Counter(
    'anvil_websocket_messages_total',
    'Total number of WebSocket messages',
    ['type']
)

# Error metrics
ERROR_COUNT = Counter(
    'anvil_errors_total',
    'Total number of errors',
    ['type', 'source']
)

# Memory metrics
MEMORY_USAGE = Gauge(
    'anvil_memory_usage_bytes',
    'Memory usage in bytes',
    ['type']  # type: 'rss', 'vms', 'shared'
)

# Database metrics
DB_QUERY_COUNT = Counter(
    'anvil_db_queries_total',
    'Total number of database queries',
    ['operation', 'table']
)

DB_QUERY_DURATION = Histogram(
    'anvil_db_query_duration_seconds',
    'Database query duration in seconds',
    ['operation', 'table'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
)

# Cache metrics
CACHE_HITS = Counter(
    'anvil_cache_hits_total',
    'Total number of cache hits',
    ['cache_type']
)

CACHE_MISSES = Counter(
    'anvil_cache_misses_total',
    'Total number of cache misses',
    ['cache_type']
)

# Extension metrics
EXTENSION_COUNT = Gauge(
    'anvil_extensions_total',
    'Total number of installed extensions'
)

EXTENSION_LOAD_DURATION = Histogram(
    'anvil_extension_load_duration_seconds',
    'Extension load duration in seconds',
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0)
)


# ============================================================================
# Metrics Context Managers
# ============================================================================

@contextmanager
def track_request(method: str, endpoint: str):
    """Track request metrics."""
    start_time = time.time()
    try:
        yield
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status='200').inc()
    except Exception as e:
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status='500').inc()
        raise
    finally:
        duration = time.time() - start_time
        REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)


@contextmanager
def track_task(model: str):
    """Track task execution metrics."""
    start_time = time.time()
    try:
        yield
        TASK_COUNT.labels(status='success', model=model).inc()
    except Exception as e:
        TASK_COUNT.labels(status='error', model=model).inc()
        raise
    finally:
        duration = time.time() - start_time
        TASK_DURATION.labels(model=model).observe(duration)


@contextmanager
def track_verification():
    """Track verification metrics."""
    start_time = time.time()
    try:
        yield
        VERIFICATION_COUNT.labels(result='passed').inc()
    except Exception as e:
        VERIFICATION_COUNT.labels(result='failed').inc()
        raise
    finally:
        duration = time.time() - start_time
        VERIFICATION_DURATION.observe(duration)


@contextmanager
def track_model_request(model: str):
    """Track model request metrics."""
    start_time = time.time()
    try:
        yield
        MODEL_REQUEST_COUNT.labels(model=model, status='success').inc()
    except Exception as e:
        MODEL_REQUEST_COUNT.labels(model=model, status='error').inc()
        raise
    finally:
        duration = time.time() - start_time
        MODEL_DURATION.labels(model=model).observe(duration)


@contextmanager
def track_db_query(operation: str, table: str):
    """Track database query metrics."""
    start_time = time.time()
    try:
        yield
        DB_QUERY_COUNT.labels(operation=operation, table=table).inc()
    finally:
        duration = time.time() - start_time
        DB_QUERY_DURATION.labels(operation=operation, table=table).observe(duration)


# ============================================================================
# Metrics API
# ============================================================================

def get_metrics() -> tuple[str, str]:
    """Get all metrics in Prometheus format."""
    return generate_latest().decode('utf-8'), CONTENT_TYPE_LATEST


def record_task_iterations(model: str, iterations: int):
    """Record the number of iterations for a task."""
    TASK_ITERATIONS.labels(model=model).observe(iterations)


def record_token_usage(model: str, input_tokens: int, output_tokens: int):
    """Record token usage for a model request."""
    MODEL_TOKEN_USAGE.labels(model=model, type='input').inc(input_tokens)
    MODEL_TOKEN_USAGE.labels(model=model, type='output').inc(output_tokens)


def record_error(error_type: str, source: str):
    """Record an error."""
    ERROR_COUNT.labels(type=error_type, source=source).inc()


def set_active_sessions(count: int):
    """Set the number of active sessions."""
    ACTIVE_SESSIONS.set(count)


def increment_session_count():
    """Increment the total session count."""
    SESSION_COUNT.inc()


def set_active_users(count: int):
    """Set the number of active users."""
    ACTIVE_USERS.set(count)


def increment_user_count():
    """Increment the total user count."""
    USER_COUNT.inc()


def set_websocket_connections(count: int):
    """Set the number of active WebSocket connections."""
    WEBSOCKET_CONNECTIONS.set(count)


def record_websocket_message(message_type: str):
    """Record a WebSocket message."""
    WEBSOCKET_MESSAGES.labels(type=message_type).inc()


def set_memory_usage(rss: int, vms: int, shared: int):
    """Set memory usage metrics."""
    MEMORY_USAGE.labels(type='rss').set(rss)
    MEMORY_USAGE.labels(type='vms').set(vms)
    MEMORY_USAGE.labels(type='shared').set(shared)


def record_cache_hit(cache_type: str):
    """Record a cache hit."""
    CACHE_HITS.labels(cache_type=cache_type).inc()


def record_cache_miss(cache_type: str):
    """Record a cache miss."""
    CACHE_MISSES.labels(cache_type=cache_type).inc()


def set_extension_count(count: int):
    """Set the number of installed extensions."""
    EXTENSION_COUNT.set(count)


def record_extension_load_duration(duration: float):
    """Record extension load duration."""
    EXTENSION_LOAD_DURATION.observe(duration)

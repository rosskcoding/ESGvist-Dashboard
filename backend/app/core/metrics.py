import re

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path", "status"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 10.0),
)

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

ACTIVE_REQUESTS = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently being processed",
    ["method"],
)

DB_QUERY_LATENCY = Histogram(
    "db_query_duration_seconds",
    "Database query latency in seconds",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

NON_BLOCKING_FAILURES = Counter(
    "non_blocking_failures_total",
    "Failures observed in non-blocking side effects",
    ["component", "operation"],
)

HEALTH_CHECK_RESULTS = Counter(
    "health_check_results_total",
    "Health check probe results",
    ["dependency", "status"],
)

CLIENT_RUNTIME_EVENTS = Counter(
    "client_runtime_events_total",
    "Client-side runtime events received by the backend",
    ["event_type", "level"],
)

# Pattern to normalize paths: replace numeric segments with {id}
_NUMERIC_SEGMENT = re.compile(r"/\d+")


def normalize_path(path: str) -> str:
    return _NUMERIC_SEGMENT.sub("/{id}", path)


def record_non_blocking_failure(component: str, operation: str) -> None:
    NON_BLOCKING_FAILURES.labels(component=component, operation=operation).inc()


def record_health_check_result(dependency: str, status: str) -> None:
    HEALTH_CHECK_RESULTS.labels(dependency=dependency, status=status).inc()


def record_client_runtime_event(event_type: str, level: str) -> None:
    CLIENT_RUNTIME_EVENTS.labels(event_type=event_type, level=level).inc()


def generate_metrics_response() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST

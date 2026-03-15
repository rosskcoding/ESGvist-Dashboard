"""
Celery client for dispatching background tasks from API.

The API container does NOT run a worker, but it can publish tasks to the broker.
Worker container consumes tasks (see apps/worker).
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

try:
    from celery import Celery
except Exception:  # pragma: no cover
    Celery = None  # type: ignore[assignment]


_celery_app: Any | None = None


def get_celery_app() -> Any | None:
    """Create Celery app lazily (or return None if celery isn't installed)."""
    global _celery_app
    if _celery_app is not None:
        return _celery_app

    if Celery is None:
        logger.warning("Celery is not installed; task dispatch is disabled.")
        _celery_app = None
        return None

    broker_url = str(settings.redis_url)
    _celery_app = Celery(
        "esg_report_api_dispatcher",
        broker=broker_url,
        backend=broker_url,
    )
    return _celery_app


def send_task(
    task_name: str,
    *args: Any,
    task_kwargs: dict[str, Any] | None = None,
    **options: Any,
) -> None:
    """
    Publish a task to the broker.

    - Positional `*args` are passed to the task.
    - `task_kwargs` are passed as task keyword-arguments.
    - `**options` are passed as Celery send options (e.g. `queue=...`, `countdown=...`).

    Automatically propagates X-Request-ID from current request context to task headers.

    Raises RuntimeError if celery isn't available.
    """
    app = get_celery_app()
    if app is None:
        raise RuntimeError("Celery is not installed; cannot dispatch tasks")

    # Propagate request_id from middleware context to Celery headers
    try:
        from app.middleware.correlation import get_request_id
        request_id = get_request_id()
        if request_id and request_id != "unknown":
            if "headers" not in options:
                options["headers"] = {}
            options["headers"]["x_request_id"] = request_id
    except Exception:
        # Fail silently if correlation middleware not available
        pass

    app.send_task(task_name, args=list(args), kwargs=task_kwargs or {}, **options)








from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Protocol, TypeVar, cast

from django.conf import settings

F = TypeVar("F", bound=Callable[..., Any])


class Enqueueable(Protocol):
    def enqueue(self, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class TaskConfig:
    queue_name: str


class TaskWrapper:
    def __init__(self, func: Callable[..., Any], config: TaskConfig):
        self._func = func
        self._config = config

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._func(*args, **kwargs)

    def enqueue(self, **kwargs: Any) -> None:
        """
        Minimal async task enqueuer for environments without `django-tasks`.

        In tests, `CELERY_TASK_ALWAYS_EAGER=True` runs the task inline for determinism.
        In other environments, run in a background thread to preserve API responsiveness.
        """

        run_inline = bool(getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False))
        if run_inline:
            self._func(**kwargs)
            return

        thread = threading.Thread(
            target=self._func,
            kwargs=kwargs,
            name=f"task:{self._config.queue_name}:{self._func.__name__}",
            daemon=True,
        )
        thread.start()


def task(*, queue_name: str) -> Callable[[F], Enqueueable]:
    """
    Compatibility decorator for `django.tasks.task(queue_name=...)`.

    If `django-tasks` is installed, prefer its implementation. Otherwise, use a
    lightweight wrapper that provides `.enqueue(...)`.
    """

    def should_use_django_tasks() -> bool:
        if bool(getattr(settings, "EKKO_DISABLE_DJANGO_TASKS", False)):
            return False
        tasks_config = getattr(settings, "TASKS", {})
        if isinstance(tasks_config, dict):
            backend = tasks_config.get("default", {}).get("BACKEND")
            if isinstance(backend, str) and backend.endswith("ImmediateBackend"):
                return False
        return True

    try:
        from django.tasks import task as django_task  # type: ignore
    except Exception:
        django_task = None

    def decorator(func: F) -> Enqueueable:
        if django_task is not None and should_use_django_tasks():
            return cast(Enqueueable, django_task(queue_name=queue_name)(func))
        return cast(Enqueueable, TaskWrapper(func, TaskConfig(queue_name=queue_name)))

    return decorator

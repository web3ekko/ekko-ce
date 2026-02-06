"""
Process Role Detection - Determine if current process is a task worker.

Used to gate NLP initialization to task workers only, keeping web workers
lightweight and avoiding unnecessary LiteLLM/NLP model loading.
"""

import os
import sys


def is_task_worker() -> bool:
    """
    Check if the current process is a Django task worker.

    Detection methods (in order of precedence):
    1. IS_NLP_WORKER=1 environment variable (explicit flag)
    2. Running 'django-tasks' or 'enqueue' command (argv inspection)

    Returns:
        True if this is a task worker process, False otherwise.
    """
    # Method 1: Explicit environment variable
    if os.environ.get("IS_NLP_WORKER", "").lower() in ("1", "true", "yes"):
        return True

    # Method 2: Check if running task worker command
    if len(sys.argv) > 1:
        command = sys.argv[1] if len(sys.argv) > 1 else ""
        # Django 6.0 task worker commands
        if command in ("django-tasks", "enqueue", "runtask", "runworker"):
            return True
        # Check for manage.py task commands
        if len(sys.argv) > 2 and sys.argv[0].endswith("manage.py"):
            subcommand = sys.argv[1]
            if subcommand in ("django-tasks", "enqueue", "runtask", "runworker"):
                return True

    return False


def is_web_worker() -> bool:
    """
    Check if the current process is a web worker (Gunicorn/Uvicorn/runserver).

    Returns:
        True if this is a web worker process, False otherwise.
    """
    # Explicit flag takes precedence
    if os.environ.get("IS_WEB_WORKER", "").lower() in ("1", "true", "yes"):
        return True

    # Check for web server processes
    if len(sys.argv) > 0:
        executable = sys.argv[0].lower()
        if any(server in executable for server in ("gunicorn", "uvicorn", "daphne")):
            return True

    # Check for Django runserver
    if len(sys.argv) > 1 and sys.argv[0].endswith("manage.py"):
        if sys.argv[1] == "runserver":
            return True

    return False


def get_process_role() -> str:
    """
    Get the current process role as a string.

    Returns:
        'task_worker', 'web_worker', or 'unknown'
    """
    if is_task_worker():
        return "task_worker"
    if is_web_worker():
        return "web_worker"
    return "unknown"

from __future__ import annotations

import atexit
import asyncio
import logging
from typing import Any, Awaitable, Callable

try:
    from celery import Celery
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    Celery = None

from src.exceptions import TaskRuntimeError
from src.models.settings import app_settings

logger = logging.getLogger(__name__)
_worker_loop: asyncio.AbstractEventLoop | None = None


def _get_worker_loop() -> asyncio.AbstractEventLoop:
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)
    return _worker_loop


def _close_worker_loop() -> None:
    global _worker_loop
    loop = _worker_loop
    if loop is None or loop.is_closed():
        return

    try:
        loop.run_until_complete(loop.shutdown_asyncgens())
    except Exception:
        logger.debug("Failed to shutdown async generators for worker loop", exc_info=True)
    finally:
        loop.close()
        _worker_loop = None


def _run_worker_job(coro: Awaitable[None]) -> None:
    loop = _get_worker_loop()
    loop.run_until_complete(_run_worker_coroutine(coro))


atexit.register(_close_worker_loop)


async def _run_worker_coroutine(coro: Awaitable[None]) -> None:
    """Run one async worker job and release loop-bound runtime resources afterwards."""
    from src.core.ai_service import ai_service

    try:
        await coro
    finally:
        await ai_service.close()


def _build_celery_app() -> Celery | None:
    if Celery is None:
        return None

    app = Celery(
        "neofin",
        broker=app_settings.task_queue_broker_url,
        backend=app_settings.task_queue_result_backend,
    )
    app.conf.update(
        task_default_queue=app_settings.task_queue_name,
        task_track_started=True,
        task_ignore_result=True,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_always_eager=app_settings.task_queue_eager,
        task_eager_propagates=app_settings.task_queue_eager,
        worker_hijack_root_logger=False,
        broker_connection_retry_on_startup=True,
    )
    return app


celery_app = _build_celery_app()


def _ensure_celery_runtime() -> None:
    if app_settings.task_runtime != "celery":
        raise TaskRuntimeError("Persistent task runtime is not enabled")
    if celery_app is None:
        raise TaskRuntimeError("Celery dependency is not installed")
    if not app_settings.task_queue_broker_url:
        raise TaskRuntimeError("TASK_QUEUE_BROKER_URL is required for celery runtime")


if celery_app is not None:

    @celery_app.task(name="neofin.process_pdf")
    def run_pdf_task(task_id: str, file_path: str) -> None:
        from src.tasks import process_pdf

        _run_worker_job(process_pdf(task_id, file_path))


    @celery_app.task(name="neofin.process_multi_analysis")
    def run_multi_analysis_task(
        session_id: str,
        periods_payload: list[dict[str, str]],
    ) -> None:
        from src.tasks import process_multi_analysis

        _run_worker_job(process_multi_analysis(session_id, periods_payload))
else:

    class _MissingCeleryTask:
        def apply_async(self, *args, **kwargs) -> None:
            raise TaskRuntimeError("Celery dependency is not installed")

    run_pdf_task = _MissingCeleryTask()
    run_multi_analysis_task = _MissingCeleryTask()


async def dispatch_pdf_task(
    background_tasks: Any,
    *,
    task_id: str,
    file_path: str,
    background_callable: Callable[..., Any],
) -> None:
    if app_settings.task_runtime == "background":
        background_tasks.add_task(background_callable, task_id, file_path)
        return

    _ensure_celery_runtime()
    try:
        run_pdf_task.apply_async(
            args=[task_id, file_path],
            task_id=task_id,
            queue=app_settings.task_queue_name,
        )
    except Exception as exc:
        raise TaskRuntimeError("Failed to dispatch PDF task") from exc


async def dispatch_multi_analysis_task(
    background_tasks: Any,
    *,
    session_id: str,
    periods_payload: list[dict[str, str]],
    background_callable: Callable[..., Any],
) -> None:
    if app_settings.task_runtime == "background":
        background_tasks.add_task(background_callable, session_id, periods_payload)
        return

    _ensure_celery_runtime()
    try:
        run_multi_analysis_task.apply_async(
            args=[session_id, periods_payload],
            task_id=session_id,
            queue=app_settings.task_queue_name,
        )
    except Exception as exc:
        raise TaskRuntimeError("Failed to dispatch multi-analysis task") from exc


def revoke_runtime_task(task_id: str) -> bool:
    if app_settings.task_runtime != "celery":
        return False

    _ensure_celery_runtime()
    try:
        celery_app.control.revoke(task_id)
        return True
    except Exception as exc:
        logger.warning("Failed to revoke task %s: %s", task_id, exc)
        return False
